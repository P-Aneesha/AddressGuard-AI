"""
Explainable Decision Engine
------------------------------
Maps the confidence score to one of four statuses, but hard validation
rules can always override the raw score band - an address can never
become VERIFIED if a hard rule says otherwise.
"""

STATUS_VERIFIED = "VERIFIED"
STATUS_NEEDS_CONFIRMATION = "NEEDS CUSTOMER CONFIRMATION"
STATUS_SUSPICIOUS = "SUSPICIOUS"
STATUS_FAKE = "FAKE ADDRESS"

RECOMMENDATIONS = {
    STATUS_VERIFIED: "Safe to ship.",
    STATUS_NEEDS_CONFIRMATION: "Please contact the customer before dispatch.",
    STATUS_SUSPICIOUS: "This address contains inconsistent information. Verify with the customer before shipping.",
    STATUS_FAKE: "This address appears invalid. Contact the customer and request a complete delivery address.",
}


def decide(confidence_result, risk_result, location_result, anomaly_result, fields) -> dict:
    score = confidence_result["score"]

    hard_conflict = any(
        c["check"] in ("PIN_CITY", "PIN_STATE", "CITY_STATE") and c["result"] == "CONFLICT"
        for c in location_result["checks"]
    )
    random_text_detected = any(a["type"] == "RANDOM_TEXT" for a in anomaly_result["anomalies"])
    missing_geo = not fields.get("city") or not fields.get("pin_code")

    if random_text_detected:
        status = STATUS_FAKE
    elif hard_conflict and score < 50:
        status = STATUS_SUSPICIOUS
    elif score >= 95 and not missing_geo and not hard_conflict:
        status = STATUS_VERIFIED
    elif score >= 85 and not missing_geo and not hard_conflict:
        status = STATUS_VERIFIED
    elif score >= 50:
        status = STATUS_NEEDS_CONFIRMATION
    elif score >= 20:
        status = STATUS_SUSPICIOUS
    else:
        status = STATUS_FAKE

    # Hard gate: never allow VERIFIED with unresolved geographic conflicts or missing core geo fields
    if status == STATUS_VERIFIED and (hard_conflict or missing_geo):
        status = STATUS_NEEDS_CONFIRMATION

    reasons = []
    problems = []

    for name, pts in confidence_result["evidence_hits"].items():
        reasons.append(f"\u2713 {name.replace('_', ' ').capitalize()} (+{pts})")
    for name, pts in confidence_result["penalty_hits"].items():
        problems.append(f"\u2717 {name.replace('_', ' ').capitalize()} ({pts})")
    for c in location_result["checks"]:
        if c["result"] == "CONFLICT":
            problems.append(c["message"])
    for a in anomaly_result["anomalies"]:
        problems.append(a["message"])

    # Explicit, human-readable missing-field problem messages. These are
    # shown even when a field's absence only triggers a score CAP (no
    # separate penalty_hits entry) - otherwise "Problems Detected" could
    # misleadingly say "None detected" on an address that is capped well
    # below what its raw evidence total would otherwise suggest.
    if not fields.get("street"):
        problems.append("Street/Road information not detected.")

    # If a hard cap actually pulled the score down below what the raw
    # evidence total earned, say so explicitly - so "Confidence: 84%"
    # is never left unexplained next to a Reasons list that adds up to
    # more than that. This mirrors confidence_result["score"] exactly;
    # nothing here recomputes or overrides the engine's own number.
    raw_score = confidence_result.get("raw_score_before_caps")
    applied_cap = confidence_result.get("applied_cap")
    if applied_cap and raw_score is not None and raw_score > score:
        problems.append(
            f"Confidence capped at {score}% (raw evidence total was {raw_score}%): {applied_cap}"
        )

    if not problems:
        problems = ["None detected."]

    return {
        "final_status": status,
        "recommendation": RECOMMENDATIONS[status],
        "reasons": reasons,
        "problems": problems,
    }