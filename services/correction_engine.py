"""
Correction & Suggestion Engine
---------------------------------
Aggregates suggestions coming from the normalizer (spelling/alias fixes)
into one uniform list the frontend can render with Accept / Reject /
Manual Edit actions. Nothing here is ever applied automatically.
"""


def build_correction_suggestions(normalization_result: dict) -> list:
    suggestions = []
    for s in normalization_result.get("suggestions", []):
        suggestions.append({
            "field": s["field"],
            "original_value": s["original"],
            "suggested_value": s["suggested"],
            "reason": s["reason"],
            "confidence": s["confidence"],
        })
    return suggestions
