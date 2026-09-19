"""
Address Pattern / Anomaly Detection Service
----------------------------------------------
Flags extremely short input, random text, repeated meaningless words,
suspicious numeric-only strings, and missing critical components.
"""
import re
from collections import Counter


def detect_anomalies(raw_text: str, fields: dict) -> dict:
    anomalies = []
    text = raw_text.strip()

    if len(text) < 12:
        anomalies.append({"type": "TOO_SHORT", "message": "Input text is extremely short for a delivery address."})

    words = re.findall(r"[A-Za-z]+", text.lower())
    if words:
        counts = Counter(words)
        repeated = [w for w, c in counts.items() if c >= 3 and len(w) > 2]
        if repeated:
            anomalies.append({
                "type": "REPEATED_MEANINGLESS_WORDS",
                "message": f"Word(s) repeated suspiciously often: {', '.join(repeated)}.",
            })

    alpha_chars = re.sub(r"[^A-Za-z]", "", text)
    if alpha_chars:
        vowels = sum(1 for c in alpha_chars.lower() if c in "aeiou")
        vowel_ratio = vowels / len(alpha_chars)
        if len(alpha_chars) > 8 and vowel_ratio < 0.15:
            anomalies.append({
                "type": "RANDOM_TEXT",
                "message": "Text has an unusually low vowel ratio, suggesting random/keyboard-mash characters.",
            })

    digit_ratio = sum(c.isdigit() for c in text) / max(len(text), 1)
    non_field_digits = digit_ratio > 0.6
    if non_field_digits:
        anomalies.append({
            "type": "SUSPICIOUS_NUMERIC_INPUT",
            "message": "Input is overwhelmingly numeric, which is unusual for a full delivery address.",
        })

    critical_missing = [k for k in ("house_number", "street", "locality", "city", "pin_code") if not fields.get(k)]
    if len(critical_missing) >= 4:
        anomalies.append({
            "type": "MISSING_CRITICAL_COMPONENTS",
            "message": f"Most critical address components are missing: {', '.join(critical_missing)}.",
        })

    return {"anomalies": anomalies, "anomaly_count": len(anomalies)}
