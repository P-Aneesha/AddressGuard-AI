"""
Phone Validation Service
-------------------------
Checks FORMAT only. AddressGuard AI never claims to verify that a phone
number actually belongs to a person - that would require a telecom-grade
verification service this project does not have access to.
"""
import re

VALID_START_DIGITS = {"6", "7", "8", "9"}


def validate_phone(phone: str) -> dict:
    if not phone:
        return {
            "status": "MISSING",
            "valid_format": False,
            "message": "No phone number was detected.",
            "ownership_note": "Actual phone ownership cannot be verified.",
        }

    digits = re.sub(r"\D", "", phone)
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]

    if len(digits) != 10:
        return {
            "status": "INVALID_FORMAT",
            "valid_format": False,
            "message": f"Phone number has {len(digits)} digits; Indian mobile numbers must have 10.",
            "ownership_note": "Actual phone ownership cannot be verified.",
        }

    if digits[0] not in VALID_START_DIGITS:
        return {
            "status": "INVALID_FORMAT",
            "valid_format": False,
            "message": "Indian mobile numbers must start with 6, 7, 8, or 9.",
            "ownership_note": "Actual phone ownership cannot be verified.",
        }

    if len(set(digits)) == 1:
        return {
            "status": "INVALID_FORMAT",
            "valid_format": False,
            "message": "Repeated single-digit pattern detected (e.g. 9999999999) - looks fabricated.",
            "ownership_note": "Actual phone ownership cannot be verified.",
        }

    if digits in ("1234567890", "0123456789"):
        return {
            "status": "INVALID_FORMAT",
            "valid_format": False,
            "message": "Sequential digit pattern detected - looks fabricated.",
            "ownership_note": "Actual phone ownership cannot be verified.",
        }

    return {
        "status": "VALID_FORMAT",
        "valid_format": True,
        "message": "Phone number matches a valid Indian mobile format.",
        "ownership_note": "Actual phone ownership cannot be verified.",
    }
