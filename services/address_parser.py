"""
Address Parser Service
----------------------
Turns messy, unstructured address text (WhatsApp text, courier labels,
invoice text, OCR output, labeled forms, comma-separated fields,
paragraphs...) into a structured dictionary.

Field order never matters - detection is based on regex patterns,
keyword proximity, and dictionary lookups, not position.

Never silently discards input: anything that could not be confidently
classified is returned in `unrecognized_text` instead of being dropped.
"""

import re

from utils.indian_data import (
    INDIAN_STATES,
    STATE_ALIASES,
    CITY_STATE_MAP,
    CITY_ALIASES,
    STREET_KEYWORDS,
    HOUSE_KEYWORDS,
    KNOWN_LOCALITIES,
)


# ============================================================
# REGEX PATTERNS
# ============================================================

# Indian mobile number
PHONE_RE = re.compile(
    r"(?<!\d)(\+?91[\-\s]?)?([6-9]\d{9})(?!\d)"
)

# Indian PIN code
PIN_RE = re.compile(
    r"(?<!\d)(\d{6})(?!\d)"
)

# Name / delivery prefix
NAME_PREFIX_RE = re.compile(
    r"(deliver to|customer name|name)\s*[:\-]?\s*",
    re.I
)

# House / Flat / Door number
#
# IMPORTANT: alternatives are tried left-to-right and the first match wins,
# so the more specific "house no"/"house number" patterns must come BEFORE
# the bare "house" alternative. Without this, "House No 45" or "House
# Number 45" would match on the bare word "house" alone, leaving "no"/
# "number" to be captured as if it were the value (so the real number,
# "45", was silently orphaned as an unrelated stray token elsewhere in
# the address instead of ending up in house_number).
HOUSE_NO_RE = re.compile(
    r"\b(house\s?no\.?|house\s?number|flat|h\.?\s?no\.?|"
    r"door\s?no\.?|door\s?number|d\.?\s?no\.?|plot|house)\b"
    r"\s*[:\-]?\s*([\w\-\/]+)",
    re.I
)

# The AUTHORITATIVE house-number label - deliberately excludes Flat/
# Apartment/Unit, which are a secondary "which unit within the building"
# detail, not the official house number.
HOUSE_NO_AUTH_RE = re.compile(
    r"\b(house\s?no\.?|house\s?number|h\.?\s?no\.?|"
    r"door\s?no\.?|door\s?number|d\.?\s?no\.?|plot|house)\b"
    r"\s*[:\-]?\s*([\w\-\/]+)",
    re.I
)

# Flat / Apartment / Unit number - a SECONDARY marker. Used as a fallback
# house number only when no authoritative H.No/Door No/House No is present
# anywhere else in the text (preserving old behavior for addresses that
# only ever give a flat number). When BOTH are present, this is instead
# treated as a distinct "flat/unit" detail, never overwriting the real
# house number.
FLAT_RE = re.compile(
    r"\b(flat\s?no\.?|apartment\s?no\.?|apartment|unit\s?no\.?|unit|flat)\b"
    r"\s*[:\-]?\s*([\w\-\/]+)",
    re.I
)

# When Flat/Unit and an authoritative H.No are BOTH present, the text
# immediately following the flat number on the same comma-separated
# segment (e.g. "Flat 302, Sai Residency") is very likely the building/
# society name.
_BUILDING_AFTER_FLAT_RE = re.compile(r"^\s*,\s*([A-Za-z][A-Za-z\s]{1,40}?)\s*(?=,|$)")


# ============================================================
# LABEL DETECTION
# ============================================================

LABEL_LINE_RE = re.compile(
    r"^\s*("
    r"name|customer name|deliver to|"
    r"phone|mobile|contact|contact number|"
    r"address|"
    r"locality|area|"
    r"landmark|"
    r"city|"
    r"state|"
    r"pin|pincode|pin code|"
    r"house no|house number|flat|door no|"
    r"building|apartment|society|flat no|apartment no|unit no"
    r")\s*[:\-]\s*(.+)$",
    re.I,
)


LABEL_TO_FIELD = {
    "name": "name",
    "customer name": "name",
    "deliver to": "name",

    "phone": "phone",
    "mobile": "phone",
    "contact": "phone",
    "contact number": "phone",

    "city": "city",
    "state": "state",

    "pin": "pin_code",
    "pincode": "pin_code",
    "pin code": "pin_code",

    "locality": "locality",
    "area": "locality",

    "landmark": "landmark",

    "house no": "house_number",
    "house number": "house_number",
    "flat": "flat_unit",
    "flat no": "flat_unit",
    "apartment no": "flat_unit",
    "unit no": "flat_unit",
    "door no": "house_number",

    "building": "building",
    "apartment": "building",
    "society": "building",

    "address": "address_block",
}


# ============================================================
# BARE STRUCTURAL HEADER LINES
# ============================================================

# Lines like "DELIVER TO" or "SHIPPING ADDRESS" written on their own,
# with no colon/dash and no value after them, are structural headers -
# they announce that an address follows, but carry no data of their
# own. They must be recognized and ignored during parsing so they never
# end up wrongly assigned to a field (see JUNK_TOKENS below) AND never
# show up under "Unrecognized text" either - a plain header is not
# unrecognized data, it is recognized as "not data".
#
# Matched as an exact, case-insensitive match of the WHOLE line/token,
# so this never accidentally swallows real address content.

STRUCTURAL_HEADER_PHRASES = {
    "deliver to",
    "delivery address",
    "delivery details",
    "shipping address",
    "billing address",
    "ship to",
    "bill to",
    "customer details",
    "recipient",
    "recipient details",
    "consignee",
    "address",
}


def _is_structural_header(line: str) -> bool:
    return line.strip().lower() in STRUCTURAL_HEADER_PHRASES


# ============================================================
# LANDMARK KEYWORDS
# ============================================================

# Used when the user DOES NOT write:
# Landmark: Near Metro Station
#
# It will also detect:
# Near Metro Station
# Opposite Apollo Hospital
# Beside SBI Bank
# Behind City Mall
# Next to Park
# Adjacent to School

LANDMARK_KEYWORDS = [
    "near ",
    "opposite ",
    "beside ",
    "behind ",
    "next to ",
    "adjacent to ",
    "nearby ",
]


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def _is_clean_place_token(token: str) -> bool:
    """
    A short, purely alphabetic token that looks like a place/person name.
    """
    return bool(
        re.match(r"^[A-Za-z\.\s]{3,40}$", token)
    ) and len(token.split()) <= 4


def _is_landmark_token(token: str) -> bool:
    """
    Detect an unlabeled landmark phrase.

    Examples:
        Near Metro Station
        Opposite Apollo Hospital
        Beside SBI Bank
        Behind City Mall
        Next to Reliance Store
        Adjacent to Park
    """

    low = token.lower().strip()

    return any(
        low.startswith(keyword)
        for keyword in LANDMARK_KEYWORDS
    )


def _looks_like_dictionary_term(text: str) -> bool:
    """
    True if `text` matches a known state/city/locality/street/house/
    landmark term. Used to avoid stealing a genuine address component
    (e.g. a street name that happens to follow a Flat number) and
    mislabeling it as a building name.
    """

    low = text.strip().lower()

    if low in INDIAN_STATES or low in STATE_ALIASES:
        return True

    if low in CITY_STATE_MAP or low in CITY_ALIASES:
        return True

    if low in KNOWN_LOCALITIES:
        return True

    if any(keyword in low for keyword in STREET_KEYWORDS):
        return True

    if any(keyword in low for keyword in HOUSE_KEYWORDS):
        return True

    if _is_landmark_token(text):
        return True

    return False


# ============================================================
# EXPLICIT LABEL EXTRACTION
# ============================================================

def _extract_labeled_lines(raw_text: str):
    """
    Splits raw_text into:

        labeled_fields
        address_block_text
        remaining_text

    Example:

        Name: Meena Reddy
        Mobile: 9988776655
        Landmark: Near Metro Station

    becomes:

        name = Meena Reddy
        phone = 9988776655
        landmark = Near Metro Station
    """

    labeled_fields = {}
    address_block_parts = []
    remaining_lines = []

    # Normalize line separators
    for raw_line in re.split(r"[\r\n]+", raw_text):

        line = raw_line.strip()

        if not line:
            continue

        # A bare structural header ("DELIVER TO", "SHIPPING ADDRESS", ...)
        # carries no data - drop it here so it never becomes a token, and
        # therefore never shows up as "Unrecognized text" later.
        if _is_structural_header(line):
            continue

        match = LABEL_LINE_RE.match(line)

        if match:

            label = match.group(1).lower().strip()
            value = match.group(2).strip()

            field = LABEL_TO_FIELD.get(label)

            if field == "address_block":

                address_block_parts.append(value)

            elif field:

                labeled_fields[field] = value

            continue

        # Not a recognized label
        remaining_lines.append(line)

    return (
        labeled_fields,
        ", ".join(address_block_parts),
        ", ".join(remaining_lines)
    )


# ============================================================
# TOKEN SPLITTER
# ============================================================

def _split_tokens(raw_text: str):

    # Convert newlines into commas
    text = raw_text.replace("\n", ", ")

    # Split sentence periods when followed by capital letters
    text = re.sub(
        r"\.\s+(?=[A-Z])",
        ", ",
        text
    )

    # Treat spaced hyphen as a separator
    #
    # Telangana - 500081
    #
    # But DON'T split:
    #
    # H.No. 2-4-15
    # 10-101/1/1

    text = re.sub(
        r"\s+[-\u2013\u2014]\s+",
        ", ",
        text
    )

    # Split commas and semicolons
    parts = re.split(
        r",|;",
        text
    )

    # Remove unnecessary punctuation
    cleaned = [
        re.sub(
            r"^[\s\-\u2013\u2014:]+|[\s\-\u2013\u2014:]+$",
            "",
            part
        )
        for part in parts
    ]

    return [
        part
        for part in cleaned
        if part
    ]


# ============================================================
# TOKEN CLASSIFICATION
# ============================================================

def _classify_tokens(tokens, result):

    """
    Classifies address tokens using:

        1. State dictionary
        2. Locality dictionary
        3. City dictionary
        4. Landmark detection
        5. Street keywords
        6. House keywords
        7. Name fallback

    Returns tokens that could not be classified.
    """

    leftover_tokens = []

    for idx, token in enumerate(tokens):

        token = token.strip()

        if not token:
            continue

        low = token.lower()


        # ====================================================
        # 1. STATE
        # ====================================================

        if (
            low in INDIAN_STATES
            or low in STATE_ALIASES
        ):

            if not result["state"]:

                result["state"] = token

                continue


        # ====================================================
        # 2. LOCALITY
        # ====================================================

        if low in KNOWN_LOCALITIES:

            if not result["locality"]:

                result["locality"] = token

                continue


        # ====================================================
        # 3. CITY
        # ====================================================

        if (
            low in CITY_STATE_MAP
            or low in CITY_ALIASES
        ):

            if not result["city"]:

                result["city"] = token

                continue

            elif not result["locality"]:

                # If another city-like token appears,
                # use it as locality instead of dropping it.

                result["locality"] = token

                continue


        # ====================================================
        # 4. LANDMARK
        # ====================================================

        # IMPORTANT FIX:
        #
        # Detect landmarks even when the user doesn't write:
        #
        # Landmark: Near Metro Station
        #
        # Example:
        #
        # Near Metro Station
        #
        # should become:
        #
        # landmark = Near Metro Station

        if _is_landmark_token(token):

            if not result["landmark"]:

                result["landmark"] = token

                continue


        # ====================================================
        # 5. STREET
        # ====================================================

        if any(
            keyword in low
            for keyword in STREET_KEYWORDS
        ):

            if not result["street"]:

                result["street"] = token

                continue

            elif not result["locality"]:

                result["locality"] = token

                continue


        # ====================================================
        # 6. HOUSE NUMBER
        # ====================================================

        if (
            any(
                keyword in low
                for keyword in HOUSE_KEYWORDS
            )
            and not result["house_number"]
        ):

            result["house_number"] = token

            continue


        # ====================================================
        # 7. NAME FALLBACK
        # ====================================================

        # Only use the first token as a name if it looks like
        # a person/place name and hasn't already been identified.

        if (
            idx == 0
            and not result["name"]
            and _is_clean_place_token(token)
            and not any(
                keyword in low
                for keyword in STREET_KEYWORDS + HOUSE_KEYWORDS
            )
            and low not in INDIAN_STATES
            and low not in STATE_ALIASES
            and low not in CITY_STATE_MAP
            and low not in CITY_ALIASES
            and low not in KNOWN_LOCALITIES
        ):

            result["name"] = token

            continue


        # ====================================================
        # UNRECOGNIZED
        # ====================================================

        leftover_tokens.append(token)


    return leftover_tokens


# ============================================================
# MAIN ADDRESS PARSER
# ============================================================

def parse_address(raw_text: str):

    warnings = []

    # ========================================================
    # RESULT STRUCTURE
    # ========================================================

    result = {

        "name": None,

        "phone": None,

        "house_number": None,

        "flat_unit": None,

        "building": None,

        "street": None,

        "landmark": None,

        "locality": None,

        "city": None,

        "state": None,

        "pin_code": None,
    }


    # ========================================================
    # BASIC INPUT CHECK
    # ========================================================

    if not raw_text:

        warnings.append(
            "No address text was provided."
        )

        return {
            "fields": result,
            "extraction_confidence": 0,
            "unrecognized_text": [],
            "parser_warnings": warnings,
        }


    text = raw_text.strip()


    # ========================================================
    # STEP 0:
    # EXTRACT EXPLICIT LABELS
    # ========================================================

    labeled_fields, address_block_text, remaining_text = (
        _extract_labeled_lines(text)
    )


    # Copy labeled fields into result

    for field, value in labeled_fields.items():

        result[field] = value.strip()


    # ========================================================
    # CREATE WORKING TEXT
    # ========================================================

    working_parts = []

    if remaining_text:

        working_parts.append(
            remaining_text
        )

    if address_block_text:

        working_parts.append(
            address_block_text
        )


    working = ", ".join(
        working_parts
    )


    # If everything was unlabeled
    if not working:

        working = text


    # ========================================================
    # STEP 1:
    # PHONE NUMBER
    # ========================================================

    if not result["phone"]:

        phone_match = PHONE_RE.search(
            working
        )

        if phone_match:

            result["phone"] = (
                phone_match.group(2)
            )

            working = (
                working[:phone_match.start()]
                + " "
                + working[phone_match.end():]
            )

    else:

        # Remove duplicate phone from free text

        working = PHONE_RE.sub(
            " ",
            working
        )


    # ========================================================
    # STEP 2:
    # PIN CODE
    # ========================================================

    if not result["pin_code"]:

        pin_match = PIN_RE.search(
            working
        )

        if pin_match:

            result["pin_code"] = (
                pin_match.group(1)
            )

            working = (
                working[:pin_match.start()]
                + " "
                + working[pin_match.end():]
            )

    else:

        working = PIN_RE.sub(
            " ",
            working
        )


    # ========================================================
    # STEP 3:
    # NAME
    # ========================================================

    if not result["name"]:

        name_prefix = NAME_PREFIX_RE.search(
            working
        )

        if name_prefix:

            after = working[
                name_prefix.end():
            ]

            candidate = re.split(
                r"[,.\n]",
                after
            )[0].strip()

            if (
                candidate
                and len(candidate.split()) <= 5
            ):

                result["name"] = candidate

                working = (
                    working[:name_prefix.start()]
                    + " "
                    + working[
                        name_prefix.end()
                        + len(candidate):
                    ]
                )


    # ========================================================
    # STEP 4:
    # HOUSE / FLAT / BUILDING NUMBER
    # ========================================================

    # Only activate the dual-extraction path when BOTH an authoritative
    # house-number label (H.No/House No/Door No/Plot) AND a separate
    # Flat/Apartment/Unit label are present. This is deliberately gated:
    # when only one of the two is present, behavior falls through to the
    # exact original single-match logic below, unchanged - so addresses
    # that only ever give a Flat number (and no separate H.No) keep
    # working exactly as before.

    house_auth_match = HOUSE_NO_AUTH_RE.search(working) if not result["house_number"] else None
    flat_match = FLAT_RE.search(working) if not result["house_number"] else None

    if house_auth_match and flat_match and house_auth_match.start() != flat_match.start():

        result["house_number"] = house_auth_match.group(0).strip()
        result["flat_unit"] = flat_match.group(2).strip()

        # A building/society name immediately following the flat match on
        # the same comma-separated segment (e.g. "Flat 302, Sai
        # Residency") is captured here - but only if it doesn't already
        # look like a real street/locality/city/state/landmark term,
        # which is left alone for normal token classification instead.
        flat_span_end = flat_match.end()
        after_flat = working[flat_match.end():]
        building_match = _BUILDING_AFTER_FLAT_RE.match(after_flat)

        if building_match:
            candidate = building_match.group(1).strip()
            if candidate and not _looks_like_dictionary_term(candidate):
                result["building"] = candidate
                flat_span_end = flat_match.end() + building_match.end()

        # Remove both matched spans (house-auth span, and flat[+building]
        # span) from the working text, rightmost span first so removing
        # it doesn't shift the other span's indices.
        spans = sorted([
            (house_auth_match.start(), house_auth_match.end()),
            (flat_match.start(), flat_span_end),
        ])
        working = working[:spans[1][0]] + " " + working[spans[1][1]:]
        working = working[:spans[0][0]] + " " + working[spans[0][1]:]

    elif not result["house_number"]:

        house_match = HOUSE_NO_RE.search(
            working
        )

        if house_match:

            result["house_number"] = (
                house_match.group(0).strip()
            )

            working = (
                working[:house_match.start()]
                + " "
                + working[house_match.end():]
            )


    # ========================================================
    # STEP 5:
    # TOKEN CLASSIFICATION
    # ========================================================

    tokens = _split_tokens(
        working
    )

    leftover_tokens = _classify_tokens(
        tokens,
        result
    )


    # If a Flat/Unit number was found (labeled or unlabeled) but no
    # separate, authoritative house number ever was, the flat number IS
    # the house number - this preserves the original behavior for
    # addresses that only ever give a flat/unit number.
    if not result["house_number"] and result["flat_unit"]:
        result["house_number"] = result["flat_unit"]
        result["flat_unit"] = None


    # ========================================================
    # STEP 6:
    # BEST-EFFORT LOCALITY / STREET DETECTION
    # ========================================================

    # If, after every dictionary/keyword pass above, a genuinely
    # unclassified place-like token is still left over, it is not
    # discarded - it is used to fill in whichever of locality/street
    # is still missing, in that order. This is what catches street
    # names that don't happen to contain one of STREET_KEYWORDS (e.g.
    # "Anna Salai", "SG Highway", "Civil Lines") instead of silently
    # leaving `street` empty even though a street name was provided.
    #
    # Boilerplate/header words ("Deliver To", "Shipping Address", ...)
    # are explicitly excluded from this fallback - a stray unlabeled
    # header line is not a place name, and silently stuffing it into
    # `street` would fabricate a fake-looking but wrong street value
    # and falsely inflate confidence instead of honestly leaving the
    # field empty. (Normally these are already dropped at the line
    # level in _extract_labeled_lines, but this is a safety net for
    # the case where one appears comma-joined on the same line as
    # other content.)

    for token in list(leftover_tokens):

        if not re.match(r"^[A-Za-z0-9][A-Za-z0-9\s\-]{1,39}$", token):
            continue

        if _is_structural_header(token):
            continue

        if not result["locality"]:
            result["locality"] = token
            leftover_tokens.remove(token)
            continue

        if not result["street"]:
            result["street"] = token
            leftover_tokens.remove(token)
            continue

        break


    # ========================================================
    # STEP 7:
    # UNRECOGNIZED TEXT
    # ========================================================

    # Structural headers are recognized-as-not-data, not "unrecognized" -
    # they are filtered out here too as a final safety net, on top of
    # being dropped at the line level above.
    unrecognized_text = [
        token
        for token in leftover_tokens
        if token != result.get("name") and not _is_structural_header(token)
    ]


    # ========================================================
    # STEP 8:
    # EXTRACTION CONFIDENCE
    # ========================================================

    extracted_count = sum(
        1
        for value in result.values()
        if value
    )

    extraction_confidence = min(
        100,
        extracted_count * 11
    )


    # ========================================================
    # STEP 9:
    # WARNINGS
    # ========================================================

    if not result["pin_code"]:

        warnings.append(
            "No 6-digit PIN code detected in input."
        )


    if not result["phone"]:

        warnings.append(
            "No valid-looking 10-digit phone number detected."
        )


    if (
        not result["city"]
        and not result["state"]
    ):

        warnings.append(
            "Neither city nor state could be recognized from the text."
        )


    # ========================================================
    # RETURN FINAL RESULT
    # ========================================================

    return {

        "fields": result,

        "extraction_confidence":
            extraction_confidence,

        "unrecognized_text":
            unrecognized_text,

        "parser_warnings":
            warnings,
    }