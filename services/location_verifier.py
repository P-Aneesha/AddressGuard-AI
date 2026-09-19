"""
Location Verification Service
--------------------------------
Performs geographic CONSISTENCY checks between PIN, city, and state using
the offline reference dataset. Every result is tagged with its validation
source so the UI never overstates what was actually checked:

  FORMAT_VALIDATION            - only syntax was checked
  DATASET_VALIDATION           - checked against the bundled offline dataset
  GEOGRAPHIC_CONSISTENCY_VALIDATION - cross-field consistency (PIN<->city<->state)
  EXTERNAL_VERIFICATION        - NOT used in this project (no live API configured)
"""
from utils.indian_data import CITY_STATE_MAP, PIN_PREFIX_TO_STATE, KNOWN_LOCALITIES


def verify_location(fields: dict, pin_result: dict) -> dict:
    city = (fields.get("city") or "").strip().lower()
    state = (fields.get("state") or "").strip().lower()
    pin = (fields.get("pin_code") or "").strip()

    checks = []

    # City <-> State
    if city and state:
        expected_state = CITY_STATE_MAP.get(city)
        if expected_state is None:
            checks.append({
                "check": "CITY_STATE",
                "result": "UNKNOWN",
                "source": "DATASET_VALIDATION",
                "message": f"City '{city.title()}' is not in the offline dataset - cannot confirm state match.",
            })
        elif expected_state == state:
            checks.append({
                "check": "CITY_STATE",
                "result": "CONSISTENT",
                "source": "DATASET_VALIDATION",
                "message": f"City '{city.title()}' correctly belongs to state '{state.title()}'.",
            })
        else:
            checks.append({
                "check": "CITY_STATE",
                "result": "CONFLICT",
                "source": "DATASET_VALIDATION",
                "message": f"City '{city.title()}' actually belongs to '{expected_state.title()}', not '{state.title()}'.",
            })
    else:
        checks.append({
            "check": "CITY_STATE", "result": "INCOMPLETE", "source": "FORMAT_VALIDATION",
            "message": "City or state missing - cannot check consistency."
        })

    # PIN <-> State
    if pin and len(pin) == 6 and state:
        possible_states = PIN_PREFIX_TO_STATE.get(pin[:2])
        if not possible_states:
            checks.append({
                "check": "PIN_STATE", "result": "UNKNOWN", "source": "DATASET_VALIDATION",
                "message": "PIN prefix not present in offline dataset."
            })
        elif state in possible_states:
            checks.append({
                "check": "PIN_STATE", "result": "CONSISTENT", "source": "GEOGRAPHIC_CONSISTENCY_VALIDATION",
                "message": f"PIN code {pin} is consistent with state '{state.title()}'."
            })
        else:
            checks.append({
                "check": "PIN_STATE", "result": "CONFLICT", "source": "GEOGRAPHIC_CONSISTENCY_VALIDATION",
                "message": f"PIN code {pin} does not belong to state '{state.title()}'."
            })
    else:
        checks.append({
            "check": "PIN_STATE", "result": "INCOMPLETE", "source": "FORMAT_VALIDATION",
            "message": "PIN code or state missing - cannot check consistency."
        })

    # PIN <-> City (derived transitively through state)
    if pin and len(pin) == 6 and city:
        expected_state_for_city = CITY_STATE_MAP.get(city)
        possible_states_for_pin = PIN_PREFIX_TO_STATE.get(pin[:2])
        if expected_state_for_city and possible_states_for_pin:
            if expected_state_for_city in possible_states_for_pin:
                checks.append({
                    "check": "PIN_CITY", "result": "CONSISTENT", "source": "GEOGRAPHIC_CONSISTENCY_VALIDATION",
                    "message": f"PIN code {pin} is geographically consistent with city '{city.title()}'."
                })
            else:
                checks.append({
                    "check": "PIN_CITY", "result": "CONFLICT", "source": "GEOGRAPHIC_CONSISTENCY_VALIDATION",
                    "message": f"PIN code {pin} does not match the region of city '{city.title()}'."
                })
        else:
            checks.append({
                "check": "PIN_CITY", "result": "UNKNOWN", "source": "DATASET_VALIDATION",
                "message": "Insufficient offline data to cross-check PIN against city."
            })
    else:
        checks.append({
            "check": "PIN_CITY", "result": "INCOMPLETE", "source": "FORMAT_VALIDATION",
            "message": "PIN code or city missing - cannot check consistency."
        })

    # Locality <-> City. An EXACT match against the bundled locality
    # dataset is "VERIFIED" (Recognized); any other non-empty locality is
    # "LIKELY_MATCH" (Likely Match) - there is no verified locality-level
    # dataset to confirm it beyond that heuristic. A missing locality
    # stays "INCOMPLETE" as before. Unknown/unverified is never treated
    # as evidence of a fake address on its own.
    locality = fields.get("locality")
    if locality:
        if locality.strip().lower() in KNOWN_LOCALITIES:
            checks.append({
                "check": "LOCALITY_CITY", "result": "VERIFIED", "source": "DATASET_VALIDATION",
                "message": f"Locality '{locality.title()}' matches a known locality in the offline dataset.",
            })
        else:
            checks.append({
                "check": "LOCALITY_CITY", "result": "LIKELY_MATCH" if city else "UNKNOWN",
                "source": "DATASET_VALIDATION",
                "message": "Locality was provided; no verified locality-level dataset entry matches it, so this "
                           "cannot be confirmed beyond a likely-match heuristic.",
            })
    else:
        checks.append({
            "check": "LOCALITY_CITY", "result": "INCOMPLETE", "source": "FORMAT_VALIDATION",
            "message": "Locality missing."
        })

    has_conflict = any(c["result"] == "CONFLICT" for c in checks)
    overall = "CONFLICT" if has_conflict else "CONSISTENT"

    return {"overall": overall, "checks": checks}