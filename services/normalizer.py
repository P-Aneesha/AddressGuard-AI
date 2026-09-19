"""
Normalization Service
-----------------------
Every normalization is tagged as either:
  AUTOMATIC_SAFE   - purely cosmetic (whitespace, capitalization, known
                      abbreviation expansion) - applied immediately.
  USER_APPROVAL_REQUIRED - changes meaning (e.g. "Hydrabad" -> "Hyderabad")
                      - only ever suggested, never silently applied.
"""
import re
from difflib import get_close_matches
from utils.indian_data import (
    ABBREVIATION_EXPANSIONS, CITY_STATE_MAP, CITY_ALIASES, STATE_ALIASES, INDIAN_STATES,
    KNOWN_LOCALITIES,
)


def _clean_whitespace(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _title_case(value: str) -> str:
    return " ".join(w.capitalize() for w in value.split(" "))


def _expand_abbreviations(value: str) -> str:
    words = value.split(" ")
    out = []
    for w in words:
        key = w.lower().strip(".")
        out.append(ABBREVIATION_EXPANSIONS.get(key, w))
    return " ".join(out)


# House-number values are extracted together with their label, e.g.
# "H.No 6-4-12" or "House Number 6-4-12". Display/storage should show
# only the actual number/unit ("6-4-12"), not a duplicated label - so
# the label prefix is stripped here rather than expanded like other
# abbreviations (expanding it was what produced "House Number 6-4-12").
_HOUSE_LABEL_STRIP_RE = re.compile(
    r"^\s*(house\s*no\.?|house\s*number|h\.?\s*no\.?|"
    r"door\s*no\.?|door\s*number|d\.?\s*no\.?|"
    r"flat\s*no\.?|flat|plot\s*no\.?|plot)\s*[:\-]?\s*",
    re.I,
)


def _normalize_house_number(value: str) -> str:
    cleaned = _clean_whitespace(value)
    stripped = _HOUSE_LABEL_STRIP_RE.sub("", cleaned).strip()
    return stripped if stripped else cleaned


def _fuzzy_dictionary_suggestion(field: str, value: str, reference_set, reason: str, confidence: int, cutoff: float = 0.75):
    """
    Generic reusable fuzzy-correction check against a known reference
    dictionary - the SAME mechanism used for city/state above, applied
    here to any other field that has its own reference set (currently
    locality). Never invents a correction: if nothing in `reference_set`
    is close enough, returns None and the original value is left as-is.
    """
    if not value:
        return None
    low = value.strip().lower()
    if low in reference_set:
        return None
    close = get_close_matches(low, reference_set, n=1, cutoff=cutoff)
    if not close:
        return None
    return {
        "field": field,
        "original": value,
        "suggested": close[0].title(),
        "reason": reason,
        "confidence": confidence,
    }


# Canonical display form for each landmark keyword - defined explicitly
# (rather than via .title()) so "next to"/"adjacent to" keep a lowercase
# "to" in the corrected suggestion, consistent with landmark wording
# always being preserved rather than re-cased.
_LANDMARK_KEYWORD_DISPLAY = {
    "near": "Near", "opposite": "Opposite", "beside": "Beside",
    "behind": "Behind", "nearby": "Nearby",
    "next to": "Next to", "adjacent to": "Adjacent to",
}
_LANDMARK_SINGLE_KEYWORDS = ["near", "opposite", "beside", "behind", "nearby"]
_LANDMARK_TWO_WORD_KEYWORDS = ["next to", "adjacent to"]


def _landmark_keyword_suggestion(value: str):
    """
    Fuzzy-corrects ONLY a misspelled landmark keyword ("Opposit" ->
    "Opposite", "Besidde" -> "Beside") while leaving the rest of the
    phrase (the actual landmark name) untouched. Never fires if the
    keyword is already correct, and never touches phrases that don't
    start with something keyword-shaped in the first place.
    """
    if not value:
        return None

    stripped = value.strip()
    low = stripped.lower()

    if any(low == k or low.startswith(k + " ") for k in _LANDMARK_SINGLE_KEYWORDS + _LANDMARK_TWO_WORD_KEYWORDS):
        return None  # already correct

    words = stripped.split(" ")

    if len(words) >= 2:
        two_word_low = f"{words[0]} {words[1]}".lower()
        close_two = get_close_matches(two_word_low, _LANDMARK_TWO_WORD_KEYWORDS, n=1, cutoff=0.72)
        if close_two:
            rest = " ".join(words[2:])
            suggested = _LANDMARK_KEYWORD_DISPLAY[close_two[0]] + (f" {rest}" if rest else "")
            return {
                "field": "landmark", "original": stripped, "suggested": suggested,
                "reason": "Closest valid landmark keyword match found.", "confidence": 72,
            }

    close_one = get_close_matches(words[0].lower(), _LANDMARK_SINGLE_KEYWORDS, n=1, cutoff=0.72)
    if close_one:
        rest = " ".join(words[1:])
        suggested = _LANDMARK_KEYWORD_DISPLAY[close_one[0]] + (f" {rest}" if rest else "")
        return {
            "field": "landmark", "original": stripped, "suggested": suggested,
            "reason": "Closest valid landmark keyword match found.", "confidence": 75,
        }

    return None


def _reclassification_suggestions(fields: dict) -> list:
    """
    Generic safety net for the case where an address term ends up sitting
    in `name` because no explicit name/phone context was present to
    disambiguate it during parsing (e.g. an input that is just a
    locality/city/state/PIN with nothing else). If that value doesn't
    look confirmed elsewhere and closely matches - exactly OR via fuzzy
    match - a known locality/city/state term, it is surfaced as a
    correction suggestion for that field instead of silently being
    unreachable for correction inside `name`.

    This never fires for an ordinary person's name: it only fires when
    the value is an exact or close match against a real reference
    dictionary, using the exact same fuzzy mechanism as every other
    field - nothing is invented for a value with no dictionary evidence.
    """
    name_val = fields.get("name")
    if not name_val:
        return []

    low = name_val.strip().lower()
    out = []

    if not fields.get("locality"):
        if low in KNOWN_LOCALITIES:
            out.append({
                "field": "locality", "original": name_val, "suggested": name_val.title(),
                "reason": "This value does not look like a person's name and matches a known locality.",
                "confidence": 82,
            })
        else:
            s = _fuzzy_dictionary_suggestion(
                "locality", name_val, KNOWN_LOCALITIES,
                reason="This value does not look like a person's name and closely matches a known locality.",
                confidence=65, cutoff=0.8,
            )
            if s:
                out.append(s)

    if not fields.get("city") and not out:
        canonical = CITY_ALIASES.get(low)
        if canonical or low in CITY_STATE_MAP:
            out.append({
                "field": "city", "original": name_val, "suggested": (canonical or low).title(),
                "reason": "This value does not look like a person's name and matches a known city.",
                "confidence": 82,
            })
        else:
            s = _fuzzy_dictionary_suggestion(
                "city", name_val, CITY_STATE_MAP.keys(),
                reason="This value does not look like a person's name and closely matches a known city.",
                confidence=65, cutoff=0.8,
            )
            if s:
                out.append(s)

    if not fields.get("state") and not out:
        canonical = STATE_ALIASES.get(low)
        if canonical or low in INDIAN_STATES:
            out.append({
                "field": "state", "original": name_val, "suggested": (canonical or low).title(),
                "reason": "This value does not look like a person's name and matches a known state.",
                "confidence": 82,
            })
        else:
            s = _fuzzy_dictionary_suggestion(
                "state", name_val, INDIAN_STATES,
                reason="This value does not look like a person's name and closely matches a known state.",
                confidence=65, cutoff=0.8,
            )
            if s:
                out.append(s)

    return out


def normalize_fields(fields: dict) -> dict:
    """
    Returns:
      normalized_fields: dict of automatically-safe-normalized values
      suggestions: list of {field, original, suggested, reason, confidence}
                   requiring explicit user approval
    """
    normalized = dict(fields)
    suggestions = []

    for key in ("house_number", "flat_unit", "building", "street", "landmark", "locality", "city", "state", "name"):
        val = fields.get(key)
        if not val:
            continue

        if key == "house_number":
            # Strip the duplicated label instead of expanding/title-casing it.
            normalized[key] = _normalize_house_number(val)
            continue

        if key == "landmark":
            # Preserve the original landmark wording exactly (only whitespace
            # is cleaned) - no abbreviation expansion, no title-casing, so a
            # phrase like "Next to Mall" is never rewritten to "Next To Mall".
            normalized[key] = _clean_whitespace(val)
            continue

        cleaned = _clean_whitespace(val)
        cleaned = _expand_abbreviations(cleaned)
        cleaned = _title_case(cleaned)
        normalized[key] = cleaned

    if fields.get("phone"):
        digits = re.sub(r"\D", "", fields["phone"])
        if len(digits) > 10:
            digits = digits[-10:]
        normalized["phone"] = digits

    if fields.get("pin_code"):
        normalized["pin_code"] = re.sub(r"\D", "", fields["pin_code"])

    # ---- Fuzzy match city against known city list (USER APPROVAL REQUIRED) ----
    city_val = normalized.get("city")
    if city_val:
        low = city_val.lower()
        canonical = CITY_ALIASES.get(low)
        if canonical and canonical != low:
            suggestions.append({
                "field": "city",
                "original": city_val,
                "suggested": canonical.title(),
                "reason": "Closest valid city match found.",
                "confidence": 90,
            })
        elif low not in CITY_STATE_MAP:
            close = get_close_matches(low, CITY_STATE_MAP.keys(), n=1, cutoff=0.75)
            if close:
                suggestions.append({
                    "field": "city",
                    "original": city_val,
                    "suggested": close[0].title(),
                    "reason": "Closest valid city match found.",
                    "confidence": 75,
                })

    # ---- Fuzzy match state (USER APPROVAL REQUIRED) ----
    state_val = normalized.get("state")
    if state_val:
        low = state_val.lower()
        canonical = STATE_ALIASES.get(low)
        if canonical and canonical != low:
            suggestions.append({
                "field": "state",
                "original": state_val,
                "suggested": canonical.title(),
                "reason": "Recognized as a common short form / alias of a valid state.",
                "confidence": 92,
            })
        elif low not in INDIAN_STATES:
            close = get_close_matches(low, INDIAN_STATES, n=1, cutoff=0.75)
            if close:
                suggestions.append({
                    "field": "state",
                    "original": state_val,
                    "suggested": close[0].title(),
                    "reason": "Closest valid Indian state name match found.",
                    "confidence": 70,
                })

    # ---- Fuzzy match locality against the known locality list (USER APPROVAL REQUIRED) ----
    locality_val = normalized.get("locality")
    if locality_val:
        locality_suggestion = _fuzzy_dictionary_suggestion(
            "locality", locality_val, KNOWN_LOCALITIES,
            reason="Closest valid locality match found.", confidence=75,
        )
        if locality_suggestion:
            suggestions.append(locality_suggestion)

    # ---- Landmark keyword typo correction (USER APPROVAL REQUIRED) ----
    landmark_val = normalized.get("landmark")
    if landmark_val:
        landmark_suggestion = _landmark_keyword_suggestion(landmark_val)
        if landmark_suggestion:
            suggestions.append(landmark_suggestion)

    # ---- Safety net: an address term stranded in `name` with no other
    # context to disambiguate it (see _reclassification_suggestions) ----
    suggestions.extend(_reclassification_suggestions(normalized))

    return {
        "normalized_fields": normalized,
        "suggestions": suggestions,
    }