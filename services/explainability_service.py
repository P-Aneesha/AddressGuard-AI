"""
Explainability Service
--------------------------
This is the pipeline orchestrator: it runs every module in the exact
order defined in the workflow spec and assembles one explainable result
object containing the step-by-step status the frontend animates through.
"""
from services.address_parser import parse_address
from services.normalizer import normalize_fields
from services.phone_validator import validate_phone
from services.pin_validator import validate_pin
from services.location_verifier import verify_location
from services.anomaly_detector import detect_anomalies
from services.correction_engine import build_correction_suggestions
from services.confidence_engine import calculate_confidence
from services.risk_engine import calculate_risk
from services.decision_engine import decide

PIPELINE_STEPS = [
    "Address Parsing", "Data Normalization", "Phone Validation", "PIN Validation",
    "City and State Validation", "Locality Validation", "Address Pattern Validation",
    "Geographic Consistency", "Anomaly Detection", "Correction Suggestions",
    "Confidence Calculation", "Final Decision",
]


def run_full_pipeline(raw_text: str, working_fields: dict = None) -> dict:
    """
    If working_fields is provided (i.e. this is a re-validation after a
    correction was applied), it is used INSTEAD OF re-parsing raw_text
    for the field values, but raw_text is still kept for anomaly checks
    on the original submission context.
    """
    step_status = {s: "WAITING" for s in PIPELINE_STEPS}

    # 1. Address Parsing
    parse_result = parse_address(raw_text)
    fields = working_fields if working_fields else parse_result["fields"]
    step_status["Address Parsing"] = "COMPLETED" if any(fields.values()) else "WARNING"

    # 2. Data Normalization
    normalization_result = normalize_fields(fields)
    normalized_fields = normalization_result["normalized_fields"]
    step_status["Data Normalization"] = "COMPLETED"

    # 3. Phone Validation
    phone_result = validate_phone(normalized_fields.get("phone"))
    step_status["Phone Validation"] = "COMPLETED" if phone_result["valid_format"] else "WARNING"

    # 4. PIN Validation
    pin_result = validate_pin(normalized_fields.get("pin_code"))
    step_status["PIN Validation"] = "COMPLETED" if pin_result["valid_format"] else "FAILED" \
        if pin_result["status"] == "INVALID_FORMAT" else "WARNING"

    # 5 & 8. City/State + Geographic Consistency (location_verifier covers both)
    location_result = verify_location(normalized_fields, pin_result)
    city_state_check = next((c for c in location_result["checks"] if c["check"] == "CITY_STATE"), None)
    step_status["City and State Validation"] = "FAILED" if city_state_check and city_state_check["result"] == "CONFLICT" \
        else "COMPLETED" if city_state_check and city_state_check["result"] == "CONSISTENT" else "WARNING"
    step_status["Geographic Consistency"] = "FAILED" if location_result["overall"] == "CONFLICT" else "COMPLETED"

    # 6. Locality Validation
    locality_check = next((c for c in location_result["checks"] if c["check"] == "LOCALITY_CITY"), None)
    step_status["Locality Validation"] = "COMPLETED" if locality_check and locality_check["result"] in ("VERIFIED", "LIKELY_MATCH") \
        else "WARNING"

    # 7 & 9. Address Pattern + Anomaly Detection
    anomaly_result = detect_anomalies(raw_text, normalized_fields)
    step_status["Address Pattern Validation"] = "FAILED" if any(
        a["type"] in ("RANDOM_TEXT", "TOO_SHORT") for a in anomaly_result["anomalies"]) else "COMPLETED"
    step_status["Anomaly Detection"] = "WARNING" if anomaly_result["anomalies"] else "COMPLETED"

    # 10. Correction Suggestions
    suggestions = build_correction_suggestions(normalization_result)
    step_status["Correction Suggestions"] = "COMPLETED" if not suggestions else "WARNING"

    # 11. Confidence Calculation
    confidence_result = calculate_confidence(normalized_fields, phone_result, pin_result, location_result, anomaly_result)
    step_status["Confidence Calculation"] = "COMPLETED"

    # Risk (runs alongside confidence, not a numbered UI step but part of the result)
    risk_result = calculate_risk(normalized_fields, phone_result, pin_result, location_result, anomaly_result)

    # 12. Final Decision
    decision_result = decide(confidence_result, risk_result, location_result, anomaly_result, normalized_fields)
    step_status["Final Decision"] = "COMPLETED"

    return {
        "pipeline_steps": step_status,
        "parse_result": parse_result,
        "fields": normalized_fields,
        "normalization_result": normalization_result,
        "phone_result": phone_result,
        "pin_result": pin_result,
        "location_result": location_result,
        "anomaly_result": anomaly_result,
        "suggestions": suggestions,
        "confidence_result": confidence_result,
        "risk_result": risk_result,
        "decision_result": decision_result,
    }