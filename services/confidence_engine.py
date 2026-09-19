"""
Confidence Engine
-------------------
Confidence is NEVER based only on how many fields were detected. It
combines positive evidence, validation results, and geographic
consistency, then subtracts penalties for ACTIVELY BAD data (wrong
city/state, invalid phone, conflicting PIN, random text...), and
finally clamps the result to hard caps based on the most severe issue
found.

IMPORTANT: a field being genuinely absent is handled ONLY by withholding
its evidence bonus (and, where the spec calls for it, by a hard cap on
the final score - see below). It does NOT also get a separate "missing"
penalty stacked on top. Double-counting the same gap once as "evidence
not earned" and again as "penalty applied" was the root cause of a
single unrecognized field being able to drag a genuinely valid address
all the way down into SUSPICIOUS/FAKE ADDRESS territory - which
contradicts the rule that one missing field must never collapse the
score. Penalties are now reserved for signals that are actively wrong,
not merely missing.
"""

EVIDENCE_WEIGHTS = {
    "name_detected": 5,
    "valid_phone_format": 10,
    "house_number_present": 10,
    "street_present": 10,
    "recognized_locality": 15,
    "recognized_city": 15,
    "valid_state": 10,
    "valid_pin": 20,
    "pin_location_consistency": 10,
    "valid_address_pattern": 5,
}

# Only genuinely BAD (not merely absent) signals are penalized here.
PENALTIES = {
    "pin_location_conflict": -35,
    "wrong_state": -30,
    "wrong_city": -25,
    "invalid_phone": -15,
    "invalid_pin_format": -20,
    "random_text": -50,
    "duplicate_meaningless_text": -10,
}

# Missing-field caps: a field being absent (rather than wrong) can never
# drop confidence below these floors just by itself stacking with other
# missing-field caps - the LOWEST applicable cap wins, same as before,
# but there is no separate point deduction underneath it.
MISSING_FIELD_CAPS = {
    "house_number": ("Missing house number caps confidence at 84.", 84),
    "street": ("Missing street caps confidence at 84.", 84),
    "locality": ("Missing locality caps confidence at 84.", 84),
    "phone": ("Missing phone number caps confidence at 84.", 84),
}


def calculate_confidence(fields, phone_result, pin_result, location_result, anomaly_result) -> dict:
    evidence_hits = {}
    penalty_hits = {}
    score = 0

    # ---- Positive evidence ----
    if fields.get("name"):
        evidence_hits["name_detected"] = EVIDENCE_WEIGHTS["name_detected"]
    if phone_result["status"] == "VALID_FORMAT":
        evidence_hits["valid_phone_format"] = EVIDENCE_WEIGHTS["valid_phone_format"]
    if fields.get("house_number"):
        evidence_hits["house_number_present"] = EVIDENCE_WEIGHTS["house_number_present"]
    if fields.get("street"):
        evidence_hits["street_present"] = EVIDENCE_WEIGHTS["street_present"]
    if fields.get("locality"):
        evidence_hits["recognized_locality"] = EVIDENCE_WEIGHTS["recognized_locality"]
    if fields.get("city"):
        evidence_hits["recognized_city"] = EVIDENCE_WEIGHTS["recognized_city"]
    if fields.get("state"):
        evidence_hits["valid_state"] = EVIDENCE_WEIGHTS["valid_state"]
    # A PIN earns full evidence credit for being correctly FORMATTED (6 digits,
    # not a fabricated/army-reserved pattern) - this does NOT require our small
    # offline dataset to happen to recognize its 2-digit postal-circle prefix.
    # Requiring dataset coverage here was the bug: a perfectly valid PIN from a
    # region outside our bundled dataset was silently losing 20 (+10 more from
    # the consistency bonus below) points for no real fault of the address.
    # Dataset-backed geographic confirmation is still rewarded separately, as
    # a bonus, via pin_location_consistency just below.
    if pin_result["valid_format"]:
        evidence_hits["valid_pin"] = EVIDENCE_WEIGHTS["valid_pin"]
    pin_city_check = next((c for c in location_result["checks"] if c["check"] == "PIN_CITY"), None)
    if pin_city_check and pin_city_check["result"] == "CONSISTENT":
        evidence_hits["pin_location_consistency"] = EVIDENCE_WEIGHTS["pin_location_consistency"]
    if not anomaly_result["anomalies"]:
        evidence_hits["valid_address_pattern"] = EVIDENCE_WEIGHTS["valid_address_pattern"]

    score += sum(evidence_hits.values())

    # ---- Penalties (only for data that is actively WRONG, never for data that is simply absent) ----
    if any(c["check"] in ("PIN_CITY", "PIN_STATE") and c["result"] == "CONFLICT" for c in location_result["checks"]):
        penalty_hits["pin_location_conflict"] = PENALTIES["pin_location_conflict"]
    city_state_check = next((c for c in location_result["checks"] if c["check"] == "CITY_STATE"), None)
    if city_state_check and city_state_check["result"] == "CONFLICT":
        penalty_hits["wrong_city"] = PENALTIES["wrong_city"]

    if phone_result["status"] == "INVALID_FORMAT":
        penalty_hits["invalid_phone"] = PENALTIES["invalid_phone"]

    # An INVALID_FORMAT PIN (fabricated pattern, or a first-digit-9 civilian
    # address) is actively wrong data, not merely an unrecognized region -
    # FORMAT_VALID_UNKNOWN_REGION is intentionally NOT penalized here, since
    # that just means "valid-looking PIN our offline dataset doesn't cover".
    if pin_result["status"] == "INVALID_FORMAT":
        penalty_hits["invalid_pin_format"] = PENALTIES["invalid_pin_format"]

    for a in anomaly_result["anomalies"]:
        if a["type"] == "RANDOM_TEXT":
            penalty_hits["random_text"] = PENALTIES["random_text"]
        if a["type"] == "REPEATED_MEANINGLESS_WORDS":
            penalty_hits["duplicate_meaningless_text"] = PENALTIES["duplicate_meaningless_text"]

    score += sum(penalty_hits.values())

    # ---- Hard caps ----
    caps = []

    # Missing-field caps (absence only, no extra deduction) - matches the
    # spec's own classification table, where any ONE of these being absent
    # keeps the address in the "NEEDS CUSTOMER CONFIRMATION" band instead of
    # VERIFIED, without forcing it any lower than that on its own.
    for field_key, (message, cap_value) in MISSING_FIELD_CAPS.items():
        if not fields.get(field_key):
            caps.append((message, cap_value))

    if not fields.get("city") or not fields.get("pin_code"):
        caps.append(("Missing critical geographic information prevents VERIFIED status.", 94))
    if any(c["check"] in ("PIN_CITY", "PIN_STATE", "CITY_STATE") and c["result"] == "CONFLICT"
           for c in location_result["checks"]):
        caps.append(("PIN/city/state conflict caps confidence well below VERIFIED threshold.", 49))

    # A phone number that is ACTIVELY invalid (fabricated/repeated-digit
    # pattern, wrong length, bad starting digit) is not merely "missing
    # information" - the spec explicitly lists "Invalid phone" as a
    # SUSPICIOUS-band example, because a customer literally cannot be
    # reached to confirm the address. Without this cap, losing just the
    # phone evidence + penalty could still leave enough other evidence to
    # cross the VERIFIED threshold, which would wrongly mark an address
    # "safe to ship" when the one way to contact the customer is fake.
    if phone_result["status"] == "INVALID_FORMAT":
        caps.append(("Invalid/fabricated phone number caps confidence in the SUSPICIOUS range.", 49))

    # "Multiple severe inconsistencies" is reserved for genuinely severe, ACTIVE
    # problems (geographic conflicts, random/fabricated text) - never for a
    # simple combination of absent fields, which are already handled by the
    # missing-field caps above and must not compound into a false FAKE result.
    severe_issue_count = sum(1 for c in location_result["checks"] if c["result"] == "CONFLICT") + \
        len([a for a in anomaly_result["anomalies"] if a["type"] in ("RANDOM_TEXT", "SUSPICIOUS_NUMERIC_INPUT")])
    if severe_issue_count >= 2:
        caps.append(("Multiple severe inconsistencies detected - capped in SUSPICIOUS/FAKE range.", 19))
    if any(a["type"] == "RANDOM_TEXT" for a in anomaly_result["anomalies"]):
        caps.append(("Random/meaningless text detected - confidence forced very low.", 10))

    final_score = max(0, min(100, score))
    applied_cap = None
    for reason, cap_value in caps:
        if final_score > cap_value:
            final_score = cap_value
            applied_cap = reason

    final_score = max(0, min(100, final_score))

    return {
        "score": final_score,
        "raw_score_before_caps": max(0, min(100, score)),
        "evidence_hits": evidence_hits,
        "penalty_hits": penalty_hits,
        "applied_cap": applied_cap,
        "all_cap_checks": [c[0] for c in caps],
    }
