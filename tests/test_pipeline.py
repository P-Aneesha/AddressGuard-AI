"""
Test cases for AddressGuard AI's validation pipeline.
Run with:  python -m pytest tests/ -v
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.explainability_service import run_full_pipeline


def test_complete_valid_address():
    text = "Priya Sharma, 9876543210, Flat 10-101/1/1, Sri Krishna Nagar Colony, Road No 1, Peerzadiguda, Hyderabad, Telangana, 500039"
    result = run_full_pipeline(text)
    assert result["confidence_result"]["score"] >= 50
    assert result["decision_result"]["final_status"] in ("VERIFIED", "NEEDS CUSTOMER CONFIRMATION")


def test_missing_house_number():
    text = "Ravi Kumar, 9876543210, Sri Krishna Nagar Colony, Hyderabad, Telangana, 500039"
    result = run_full_pipeline(text)
    assert result["confidence_result"]["score"] <= 84


def test_missing_street():
    text = "Ravi Kumar, 9876543210, Flat 10, Hyderabad, Telangana, 500039"
    result = run_full_pipeline(text)
    assert not result["fields"]["street"]


def test_missing_pin_code():
    text = "Ravi Kumar, 9876543210, Flat 10, Road No 1, Peerzadiguda, Hyderabad, Telangana"
    result = run_full_pipeline(text)
    assert not result["fields"]["pin_code"]
    assert result["decision_result"]["final_status"] != "VERIFIED"


def test_incorrect_city_state_combination():
    text = "Ravi Kumar, 9876543210, Flat 10, Road No 1, MG Road, Mumbai, Telangana, 500039"
    result = run_full_pipeline(text)
    conflict = any(c["result"] == "CONFLICT" for c in result["location_result"]["checks"])
    assert conflict
    assert result["decision_result"]["final_status"] != "VERIFIED"


def test_invalid_pin_code():
    from services.pin_validator import validate_pin
    # A PIN starting with 0 is not a valid Indian postal code, regardless of length.
    result = validate_pin("012345")
    assert result["status"] == "INVALID_FORMAT"


def test_random_text():
    text = "asdkj qweoiu zxcvb qwer asdf zxcv lkjh gfds"
    result = run_full_pipeline(text)
    assert result["decision_result"]["final_status"] == "FAKE ADDRESS"


def test_repeated_meaningless_words():
    text = "test test test test address address address 123456"
    result = run_full_pipeline(text)
    types = [a["type"] for a in result["anomaly_result"]["anomalies"]]
    assert "REPEATED_MEANINGLESS_WORDS" in types


def test_manual_correction_reparses():
    text = "Ravi Kumar, 9876543210, Flat 10, Road No 1, Hydrabad, Telangana, 500039"
    first = run_full_pipeline(text)
    corrected_fields = dict(first["fields"])
    corrected_fields["city"] = "Hyderabad"
    second = run_full_pipeline(text, working_fields=corrected_fields)
    assert second["fields"]["city"] == "Hyderabad"
    assert second["confidence_result"]["score"] >= first["confidence_result"]["score"]


def test_confidence_bounds_never_exceeded():
    samples = [
        "Priya Sharma, 9876543210, Flat 10, Road No 1, Peerzadiguda, Hyderabad, Telangana, 500039",
        "asdkj qwe zxcvb",
        "",
        "9999999999 123456",
    ]
    for s in samples:
        if not s.strip():
            continue
        result = run_full_pipeline(s)
        assert 0 <= result["confidence_result"]["score"] <= 100


def test_complete_address_with_locality_verified():
    """Regression test for the exact reported bug: a fully complete address
    with a valid locality must score 95-100, be VERIFIED, LOW risk, no
    problems - and the locality must be correctly extracted, not reported
    as missing."""
    text = ("Name: Rahul Sharma\nPhone: 9876543210\n"
            "Address: H.No. 2-4-15, Road No. 3, Madhapur\n"
            "City: Hyderabad\nState: Telangana\nPIN: 500081")
    result = run_full_pipeline(text)
    assert result["fields"]["locality"] == "Madhapur"
    assert result["confidence_result"]["score"] >= 95
    assert result["decision_result"]["final_status"] == "VERIFIED"
    assert result["risk_result"]["risk_level"] == "LOW"
    assert result["decision_result"]["problems"] == ["None detected."]


def test_locality_detection_not_dependent_on_whitelist():
    """A locality that is NOT in the bundled reference list must still be
    correctly recognized - proves locality detection is general, not a
    hardcoded lookup."""
    text = "Rahul Sharma, 9876543210, H.No. 2-4-15, Road No. 3, Miyapur, Hyderabad, Telangana, 500049"
    result = run_full_pipeline(text)
    assert result["fields"]["locality"] == "Miyapur"
    assert result["fields"]["name"] == "Rahul Sharma"
    assert result["confidence_result"]["score"] >= 95
    assert result["decision_result"]["final_status"] == "VERIFIED"


def test_field_order_does_not_swap_name_and_locality():
    """Regression test: shuffling field order must never cause the parser
    to swap the customer's name with an unrecognized locality."""
    text = "Rahul Sharma, 9876543210, 500049, Telangana, Hyderabad, Miyapur, Road No. 3, H.No. 2-4-15"
    result = run_full_pipeline(text)
    assert result["fields"]["name"] == "Rahul Sharma"
    assert result["fields"]["locality"] == "Miyapur"


def test_single_missing_field_degrades_gracefully_not_to_fake():
    """A single genuinely-missing field (locality) must never collapse
    confidence to FAKE ADDRESS territory - it should land in the
    NEEDS CUSTOMER CONFIRMATION band, matching the spec's own examples."""
    text = "Rahul Sharma, 9876543210, H.No. 2-4-15, Road No. 3, Hyderabad, Telangana, 500081"
    result = run_full_pipeline(text)
    assert result["fields"]["locality"] is None
    assert result["confidence_result"]["score"] >= 50
    assert result["decision_result"]["final_status"] == "NEEDS CUSTOMER CONFIRMATION"
    assert result["risk_result"]["risk_level"] in ("LOW", "MEDIUM")


def test_fabricated_pin_codes_are_rejected():
    """Regression test: repeated-digit, sequential, and army-postal-zone
    (leading 9) PIN codes must never be accepted as merely 'unknown
    region' - they are not real allotted PIN codes and must be flagged
    INVALID_FORMAT, visibly lower confidence, and show up in Problems."""
    base = "Priya Sharma, 9876543210, H.No 10-101, Road No 1, Peerzadiguda, Hyderabad, Telangana, {pin}"

    for bad_pin in ("999999", "111111", "123456", "934521"):
        result = run_full_pipeline(base.format(pin=bad_pin))
        assert result["pin_result"]["status"] == "INVALID_FORMAT", bad_pin
        assert result["decision_result"]["final_status"] != "VERIFIED", bad_pin
        assert result["decision_result"]["problems"] != ["None detected."], bad_pin

    # control: a real, valid Hyderabad PIN must still pass cleanly
    good = run_full_pipeline(base.format(pin="500039"))
    assert good["pin_result"]["status"] == "VALID"
    assert good["confidence_result"]["score"] >= 95
    assert good["decision_result"]["final_status"] == "VERIFIED"


def test_typographic_dash_before_pin_does_not_break_state_extraction():
    """Regression test: a state name followed by an en-dash/em-dash (common
    from Windows autocorrect or text pasted from Word, e.g. 'Telangana –
    500081') must still be correctly recognized as the state, instead of
    the stray dash silently breaking the dictionary match and leaving the
    state field empty (which showed as a false WARNING on the City and
    State Validation step even though the address was fully valid)."""
    for dash in ("-", "\u2013", "\u2014"):
        text = (f"Rahul Sharma\nH.No. 2-4-15, Road No. 3, Madhapur\n"
                 f"Hyderabad, Telangana {dash} 500081\nPhone: 9876543210")
        result = run_full_pipeline(text)
        assert result["fields"]["state"] == "Telangana", dash
        assert result["pipeline_steps"]["City and State Validation"] == "COMPLETED", dash
        assert result["confidence_result"]["score"] >= 95, dash
        assert result["decision_result"]["final_status"] == "VERIFIED", dash


def test_state_parsed_when_separated_by_spaced_hyphen():
    """Regression test: 'City, State - PIN' (a spaced hyphen before the PIN,
    common in real addresses) must not swallow the state into an
    unrecognized token - the state must parse cleanly and the
    City/State validation step must report CONSISTENT, not WARNING."""
    text = ("Rahul Sharma\nH.No. 2-4-15, Road No. 3, Madhapur\n"
            "Hyderabad, Telangana - 500081\nPhone: 9876543210")
    result = run_full_pipeline(text)
    assert result["fields"]["state"] == "Telangana"
    assert result["pipeline_steps"]["City and State Validation"] == "COMPLETED"
    assert result["confidence_result"]["score"] >= 95
    assert result["decision_result"]["final_status"] == "VERIFIED"
    # house/plot numbers with bare (unspaced) hyphens must be unaffected
    assert "2-4-15" in result["fields"]["house_number"]


def test_labeled_multiline_form_reaches_verified():
    """Regression test for the reported case: a labeled 'DELIVER TO /
    Name: / Mobile: / ...' multi-line form with every real field present
    (but genuinely no street) must land at 84% / NEEDS CUSTOMER
    CONFIRMATION - not be artificially inflated by sweeping a stray
    header word like 'DELIVER TO' into the street field."""
    text = ("DELIVER TO\nName: Meena Reddy\nMobile: 9988776655\n500072\n"
            "Kukatpally\nH.No 6-4-12\nNear Metro Station\nHyderabad\nTelangana")
    result = run_full_pipeline(text)
    assert result["fields"]["street"] is None
    assert result["fields"]["landmark"] == "Near Metro Station"
    assert "Deliver To" not in (result["fields"]["street"] or "")
    assert result["confidence_result"]["score"] == 84
    assert result["decision_result"]["final_status"] == "NEEDS CUSTOMER CONFIRMATION"


def test_house_number_with_space_before_value_is_fully_captured():
    """Regression test: 'House No 45' / 'House Number 45' must capture
    the full value including the number - previously the regex matched
    only on the bare word 'house' and stopped at 'No'/'Number', leaving
    the actual number as an orphaned stray token that could get wrongly
    swept into an unrelated field (street) elsewhere in the address."""
    text = "Neha Verma, 9812345670, House No 45, Rohini, Delhi, Delhi, 110085"
    result = run_full_pipeline(text)
    assert "45" in result["fields"]["house_number"]
    assert result["fields"]["street"] is None
    assert result["confidence_result"]["score"] == 84
    assert result["decision_result"]["final_status"] == "NEEDS CUSTOMER CONFIRMATION"


def test_fabricated_phone_never_reaches_verified():
    """Regression test: a repeated-digit/fabricated phone number must
    cap the address at SUSPICIOUS, matching the spec's own example -
    a customer cannot be reached to confirm delivery on a fake number,
    so the address must never be marked 'safe to ship'."""
    text = "Priya Sharma, 9999999999, H.No 10-101, Road No 1, Peerzadiguda, Hyderabad, Telangana, 500039"
    result = run_full_pipeline(text)
    assert result["phone_result"]["status"] == "INVALID_FORMAT"
    assert result["confidence_result"]["score"] <= 49
    assert result["decision_result"]["final_status"] != "VERIFIED"


def test_hyphenated_place_names_fill_street_not_dropped():
    """Regression test: a hyphenated locality/street name like
    'C-Scheme' must not be silently discarded just because it contains
    a hyphen - it should still be used to fill a missing street/locality
    field instead of being left in unrecognized_text."""
    text = "Vikram Rathore, 9887766554, Plot 14, Civil Lines, C-Scheme, Jaipur, Rajasthan, 302001"
    result = run_full_pipeline(text)
    assert result["fields"]["locality"] == "Civil Lines"
    assert result["fields"]["street"] is not None
    assert result["confidence_result"]["score"] == 100
    assert result["decision_result"]["final_status"] == "VERIFIED"


def test_capped_confidence_shows_explanation_not_false_clean_problems():
    """Regression test: when a hard cap pulls confidence below the raw
    evidence total (e.g. missing street caps 100 -> 84), Problems must
    explain the cap instead of misleadingly saying 'None detected.'"""
    text = ("DELIVER TO\nName: Meena Reddy\nMobile: 9988776655\n500072\n"
            "Kukatpally\nH.No 6-4-12\nNear Metro Station\nHyderabad\nTelangana")
    result = run_full_pipeline(text)

    assert result["confidence_result"]["score"] == 84
    assert result["confidence_result"]["raw_score_before_caps"] == 100
    problems = result["decision_result"]["problems"]
    assert "Street/Road information not detected." in problems
    assert any("capped" in p.lower() for p in problems)
    assert problems != ["None detected."]


def test_deliver_to_header_never_shows_as_unrecognized():
    """Regression test: a bare structural header line like 'DELIVER TO'
    must be recognized and dropped, not left over as 'unrecognized text'
    nor wrongly swept into any address field."""
    text = ("DELIVER TO\nName: Meena Reddy\nMobile: 9988776655\n500072\n"
            "Kukatpally\nH.No 6-4-12\nNear Metro Station\nHyderabad\nTelangana")
    result = run_full_pipeline(text)

    assert result["parse_result"]["unrecognized_text"] == []
    assert "deliver to" not in (result["fields"]["street"] or "").lower()
    assert "deliver to" not in (result["fields"]["locality"] or "").lower()


def test_landmark_detection_all_unlabeled_phrasings():
    """Regression test: every unlabeled landmark phrasing from the spec
    must be detected without an explicit 'Landmark:' prefix."""
    phrasings = [
        "Near Metro Station", "Opposite Apollo Hospital", "Beside SBI Bank",
        "Behind City Mall", "Next to Park",
    ]
    for phrase in phrasings:
        text = f"Meena Reddy, 9988776655, H.No 6-4-12, {phrase}, Kukatpally, Hyderabad, Telangana, 500072"
        result = run_full_pipeline(text)
        assert result["fields"]["landmark"] is not None, phrase
        assert phrase.split()[0].lower() in result["fields"]["landmark"].lower(), phrase


def test_complete_address_with_street_shows_clean_problems():
    """Regression test: the new missing-street/cap-explanation problem
    messages must only appear when actually applicable - a fully
    complete address (street included) must still show a clean
    'None detected.' problems list, exactly as before."""
    text = "Priya Sharma, 9876543210, H.No 10-101, Road No 1, Peerzadiguda, Hyderabad, Telangana, 500039"
    result = run_full_pipeline(text)
    assert result["decision_result"]["problems"] == ["None detected."]
    assert result["confidence_result"]["score"] == 100
    assert result["decision_result"]["final_status"] == "VERIFIED"


def test_house_number_label_not_duplicated_in_value():
    """Regression test: house_number must show only the actual value
    ('6-4-12'), never the label duplicated in front of it
    ('House Number 6-4-12')."""
    text = "Meena Reddy, 9988776655, H.No 6-4-12, Beside Metro Station, Kukatpally, Hyderabad, Telangana, 500072"
    result = run_full_pipeline(text)
    assert result["fields"]["house_number"] == "6-4-12"


def test_landmark_wording_preserved_exactly():
    """Regression test: landmark phrasing must be preserved exactly as
    given - no title-casing (which would turn 'Next to Mall' into
    'Next To Mall') and no other rewriting."""
    cases = {
        "Opposite Metro Station": "Opposite Metro Station",
        "Beside Metro Station": "Beside Metro Station",
        "Near Bus Stop": "Near Bus Stop",
        "Behind Hospital": "Behind Hospital",
        "Next to Mall": "Next to Mall",
    }
    for phrase, expected in cases.items():
        text = f"Meena Reddy, 9988776655, H.No 6-4-12, {phrase}, Kukatpally, Hyderabad, Telangana, 500072"
        result = run_full_pipeline(text)
        assert result["fields"]["landmark"] == expected, phrase


def test_flat_and_house_number_both_present_use_house_number_authoritatively():
    """Regression test for the exact reported case: when both a Flat/Unit
    number and a separate H.No are present, House Number must come from
    H.No (never overwritten by the Flat number), the Flat number must be
    captured separately, and the trailing building/society name must be
    recognized as Building rather than left unrecognized."""
    text = ("Priya Sharma\n9876543210\nFlat 302, Sai Residency\nH.No 10-2-145\n"
            "Road No 4\nNear More Supermarket\nKukatpally\nHyderabad\nTelangana\n500072")
    result = run_full_pipeline(text)
    fields = result["fields"]
    assert fields["house_number"] == "10-2-145"
    assert fields["flat_unit"] == "302"
    assert fields["building"] == "Sai Residency"
    assert fields["street"] == "Road No 4"
    assert fields["landmark"] == "Near More Supermarket"
    assert fields["locality"] == "Kukatpally"
    assert result["parse_result"]["unrecognized_text"] == []
    assert result["confidence_result"]["score"] == 100
    assert result["decision_result"]["final_status"] == "VERIFIED"


def test_flat_only_address_still_fills_house_number():
    """Regression test: an address with ONLY a Flat number (no separate
    H.No) must keep working exactly as before - the flat number becomes
    the house number."""
    text = "Suresh Patel, 9998887776, Flat 5B, SG Highway, Vastrapur, Ahmedabad, Gujarat, 380015"
    result = run_full_pipeline(text)
    assert result["fields"]["house_number"] == "5B"
    assert result["confidence_result"]["score"] == 100
    assert result["decision_result"]["final_status"] == "VERIFIED"


def test_locality_and_landmark_generic_fuzzy_suggestions():
    """Regression test: the generic fuzzy-correction mechanism must work
    for locality (not just city/state) and for landmark keywords."""
    from services.normalizer import normalize_fields

    loc = normalize_fields({"locality": "Kukatpaly"})
    assert loc["suggestions"][0]["suggested"] == "Kukatpally"

    lm = normalize_fields({"landmark": "Opposit Apollo Hospital"})
    assert lm["suggestions"][0]["suggested"] == "Opposite Apollo Hospital"

    lm2 = normalize_fields({"landmark": "Besidde SBI Bank"})
    assert lm2["suggestions"][0]["suggested"] == "Beside SBI Bank"

    # a correctly-spelled landmark must never get a spurious suggestion
    lm3 = normalize_fields({"landmark": "Beside Metro Station"})
    assert lm3["suggestions"] == []


def test_locality_verified_vs_likely_match():
    """Regression test: an exact, dataset-known locality is labeled
    VERIFIED (Recognized); any other present-but-unconfirmed locality is
    LIKELY_MATCH - never silently claimed as fully verified."""
    known = run_full_pipeline(
        "Rahul Sharma, 9876543210, H.No. 2-4-15, Road No. 3, Madhapur, Hyderabad, Telangana, 500081"
    )
    known_check = next(c for c in known["location_result"]["checks"] if c["check"] == "LOCALITY_CITY")
    assert known_check["result"] == "VERIFIED"

    unlisted = run_full_pipeline(
        "Rahul Sharma, 9876543210, H.No. 2-4-15, Road No. 3, Miyapur, Hyderabad, Telangana, 500049"
    )
    unlisted_check = next(c for c in unlisted["location_result"]["checks"] if c["check"] == "LOCALITY_CITY")
    assert unlisted_check["result"] == "LIKELY_MATCH"


def test_locality_typo_stranded_in_name_still_gets_suggestion():
    """Regression test for the reported bug: when an address has no
    name/phone context (so a misspelled locality like 'Kukatpaly' ends
    up parsed into `name` instead of `locality`), the correction engine
    must still surface a fuzzy-correction suggestion for it - the
    'No corrections suggested' message must not appear when a reliable
    fuzzy candidate exists, even in this edge case."""
    for text in ("Kukatpaly\nHyderabad\nTelangana\n500072", "Kukatpaly, Hyderabad, Telangana, 500072"):
        result = run_full_pipeline(text)
        assert result["fields"]["locality"] is None
        assert result["fields"]["name"] == "Kukatpaly"
        assert len(result["suggestions"]) == 1
        s = result["suggestions"][0]
        assert s["field"] == "locality"
        assert s["suggested_value"] == "Kukatpally"

    # accepting it must move the corrected value into locality and
    # trigger a full re-validation
    from services.normalizer import normalize_fields
    corrected_fields = {"name": "Kukatpaly", "city": "Hyderabad", "state": "Telangana", "pin_code": "500072"}
    corrected_fields["locality"] = "Kukatpally"
    result2 = run_full_pipeline("Kukatpaly\nHyderabad\nTelangana\n500072", working_fields=corrected_fields)
    assert result2["fields"]["locality"] == "Kukatpally"


def test_normal_names_never_get_spurious_reclassification_suggestions():
    """A genuine person's name (with locality already present) must
    never trigger the name-reclassification safety net."""
    result = run_full_pipeline(
        "Priya Sharma, 9876543210, H.No 10-101, Road No 1, Peerzadiguda, Hyderabad, Telangana, 500039"
    )
    assert result["suggestions"] == []