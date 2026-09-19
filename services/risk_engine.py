"""
Address Risk Engine
----------------------
Risk is calculated independently from confidence. A low-confidence but
otherwise plausible address (e.g. missing house number) is a different
risk profile than a high-confidence-looking but geographically
impossible address.
"""


def calculate_risk(fields, phone_result, pin_result, location_result, anomaly_result) -> dict:
    risk_factors = []
    risk_points = 0

    conflicts = [c for c in location_result["checks"] if c["result"] == "CONFLICT"]
    for c in conflicts:
        risk_factors.append(f"Geographic conflict: {c['message']}")
        risk_points += 30

    if pin_result["status"] == "INVALID_FORMAT":
        risk_factors.append("Invalid PIN code format.")
        risk_points += 25
    elif pin_result["status"] == "MISSING":
        risk_factors.append("PIN code missing entirely.")
        risk_points += 15

    if phone_result["status"] == "INVALID_FORMAT":
        risk_factors.append("Invalid phone number format.")
        risk_points += 15

    unknown_checks = [c for c in location_result["checks"] if c["result"] == "UNKNOWN"]
    if len(unknown_checks) >= 2:
        risk_factors.append("Multiple location fields could not be matched to known data.")
        risk_points += 10

    for a in anomaly_result["anomalies"]:
        if a["type"] == "RANDOM_TEXT":
            risk_factors.append("Random/meaningless text pattern detected.")
            risk_points += 40
        elif a["type"] == "SUSPICIOUS_NUMERIC_INPUT":
            risk_factors.append("Suspiciously numeric-only input.")
            risk_points += 20
        elif a["type"] == "TOO_SHORT":
            risk_factors.append("Address text is extremely short.")
            risk_points += 15
        elif a["type"] == "REPEATED_MEANINGLESS_WORDS":
            risk_factors.append("Repeated meaningless words detected.")
            risk_points += 10
        elif a["type"] == "MISSING_CRITICAL_COMPONENTS":
            risk_factors.append("Most critical address components missing.")
            risk_points += 25

    missing_critical = [k for k in ("house_number", "street") if not fields.get(k)]
    if missing_critical:
        risk_points += 10 * len(missing_critical)
        risk_factors.append(f"Missing: {', '.join(missing_critical)}.")

    if risk_points >= 60:
        level = "CRITICAL"
    elif risk_points >= 35:
        level = "HIGH"
    elif risk_points >= 15:
        level = "MEDIUM"
    else:
        level = "LOW"

    return {"risk_level": level, "risk_points": risk_points, "risk_factors": risk_factors}
