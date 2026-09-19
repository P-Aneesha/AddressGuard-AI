"""
PIN Code Validation Service
-----------------------------
Checks numeric format, then cross-references against the offline
PIN-prefix-to-state dataset (DATASET VALIDATION), never claiming
external, live-API verification.

Format validation goes beyond "is it 6 digits":
- Indian PIN codes assign the first digit to one of 9 postal zones.
  Zones 1-8 cover the civilian postal circles (which is everything our
  location dataset models); zone 9 is reserved for the Army Postal
  Service / Field Post Office network, not regular delivery addresses.
  A first digit of 9 on an ordinary customer address is therefore
  treated as invalid rather than "format valid, unknown region".
- Obviously fabricated patterns (all-same-digit like 999999/111111/
  000000, or straight sequential runs like 123456/654321) are rejected
  outright - they are not real allotted PIN codes and must never be
  treated as merely "unknown region".
"""
import re
from utils.indian_data import PIN_PREFIX_TO_STATE

_ASCENDING_SEQUENCES = {"123456", "234567", "345678", "456789", "567890"}
_DESCENDING_SEQUENCES = {"987654", "876543", "765432", "654321", "543210"}


def _looks_fabricated(digits: str) -> bool:
    if len(set(digits)) == 1:
        return True  # e.g. 999999, 111111, 000000
    if digits in _ASCENDING_SEQUENCES or digits in _DESCENDING_SEQUENCES:
        return True
    return False


def validate_pin(pin_code: str) -> dict:
    if not pin_code:
        return {
            "status": "MISSING",
            "valid_format": False,
            "location_data_available": False,
            "possible_states": [],
            "message": "No PIN code was detected.",
        }

    digits = re.sub(r"\D", "", pin_code)

    if len(digits) != 6 or digits[0] == "0":
        return {
            "status": "INVALID_FORMAT",
            "valid_format": False,
            "location_data_available": False,
            "possible_states": [],
            "message": "PIN code must be exactly 6 digits and cannot start with 0.",
        }

    if digits[0] == "9":
        return {
            "status": "INVALID_FORMAT",
            "valid_format": False,
            "location_data_available": False,
            "possible_states": [],
            "message": "PIN codes starting with 9 are reserved for Army Postal Service / "
                       "Field Post Office use, not civilian delivery addresses - this is not "
                       "a valid PIN code for a regular address.",
        }

    if _looks_fabricated(digits):
        return {
            "status": "INVALID_FORMAT",
            "valid_format": False,
            "location_data_available": False,
            "possible_states": [],
            "message": "This PIN code is a repeated or sequential digit pattern "
                       f"({digits}), not a real allotted postal code.",
        }

    prefix = digits[:2]
    possible_states = PIN_PREFIX_TO_STATE.get(prefix)

    if not possible_states:
        return {
            "status": "FORMAT_VALID_UNKNOWN_REGION",
            "valid_format": True,
            "location_data_available": False,
            "possible_states": [],
            "message": "PIN code format is valid but its region is not present in the offline dataset.",
        }

    return {
        "status": "VALID",
        "valid_format": True,
        "location_data_available": True,
        "possible_states": sorted(possible_states),
        "message": "PIN code format is valid and matches a known postal circle.",
    }
