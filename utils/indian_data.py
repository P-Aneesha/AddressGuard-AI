"""
Offline reference dataset used for rule-based validation.

AddressGuard AI does not call a paid third-party geolocation API. Instead it
ships with a curated dataset of Indian states, major cities, and the PIN
code prefix ranges that officially belong to each state (per India Post's
regional zoning). This is enough to perform real geographic-consistency
checks without any external dependency, while remaining fully transparent
about what kind of validation is actually happening (see
services/location_verifier.py for the DATASET / FORMAT / CONSISTENCY
distinctions).
"""

INDIAN_STATES = {
    "andhra pradesh", "arunachal pradesh", "assam", "bihar", "chhattisgarh",
    "goa", "gujarat", "haryana", "himachal pradesh", "jharkhand", "karnataka",
    "kerala", "madhya pradesh", "maharashtra", "manipur", "meghalaya", "mizoram",
    "nagaland", "odisha", "punjab", "rajasthan", "sikkim", "tamil nadu",
    "telangana", "tripura", "uttar pradesh", "uttarakhand", "west bengal",
    "andaman and nicobar islands", "chandigarh", "dadra and nagar haveli and daman and diu",
    "delhi", "jammu and kashmir", "ladakh", "lakshadweep", "puducherry",
}

# common misspellings -> canonical state name
STATE_ALIASES = {
    "telangna": "telangana", "telengana": "telangana",
    "andhra": "andhra pradesh", "ap": "andhra pradesh",
    "karnatka": "karnataka", "karnataka.": "karnataka",
    "tamilnadu": "tamil nadu", "tn": "tamil nadu",
    "maharastra": "maharashtra", "maharashta": "maharashtra", "mh": "maharashtra",
    "up": "uttar pradesh", "uttarpradesh": "uttar pradesh",
    "wb": "west bengal", "westbengal": "west bengal",
    "mp": "madhya pradesh", "madhyapradesh": "madhya pradesh",
    "new delhi": "delhi", "ncr": "delhi",
    "pondicherry": "puducherry",
    "orissa": "odisha",
}

# City -> canonical state. Not exhaustive, but covers major metros/tier-2 cities.
CITY_STATE_MAP = {
    "hyderabad": "telangana", "warangal": "telangana", "nizamabad": "telangana",
    "secunderabad": "telangana", "karimnagar": "telangana",
    "bengaluru": "karnataka", "bangalore": "karnataka", "mysuru": "karnataka", "mysore": "karnataka",
    "mangaluru": "karnataka", "hubli": "karnataka",
    "chennai": "tamil nadu", "coimbatore": "tamil nadu", "madurai": "tamil nadu", "trichy": "tamil nadu",
    "mumbai": "maharashtra", "pune": "maharashtra", "nagpur": "maharashtra", "nashik": "maharashtra",
    "thane": "maharashtra", "aurangabad": "maharashtra",
    "delhi": "delhi", "new delhi": "delhi",
    "kolkata": "west bengal", "howrah": "west bengal", "durgapur": "west bengal",
    "ahmedabad": "gujarat", "surat": "gujarat", "vadodara": "gujarat", "rajkot": "gujarat",
    "jaipur": "rajasthan", "jodhpur": "rajasthan", "udaipur": "rajasthan", "kota": "rajasthan",
    "lucknow": "uttar pradesh", "kanpur": "uttar pradesh", "noida": "uttar pradesh",
    "ghaziabad": "uttar pradesh", "agra": "uttar pradesh", "varanasi": "uttar pradesh",
    "patna": "bihar", "gaya": "bihar",
    "bhopal": "madhya pradesh", "indore": "madhya pradesh", "gwalior": "madhya pradesh", "jabalpur": "madhya pradesh",
    "chandigarh": "chandigarh",
    "gurugram": "haryana", "gurgaon": "haryana", "faridabad": "haryana",
    "kochi": "kerala", "thiruvananthapuram": "kerala", "kozhikode": "kerala", "calicut": "kerala",
    "bhubaneswar": "odisha", "cuttack": "odisha",
    "guwahati": "assam",
    "ranchi": "jharkhand", "jamshedpur": "jharkhand",
    "raipur": "chhattisgarh",
    "dehradun": "uttarakhand",
    "shimla": "himachal pradesh",
    "amritsar": "punjab", "ludhiana": "punjab",
    "visakhapatnam": "andhra pradesh", "vijayawada": "andhra pradesh", "guntur": "andhra pradesh",
}

# Known localities/neighbourhoods (NOT full cities) - used so the parser doesn't
# mistake them for a city, and instead correctly files them as "locality".
KNOWN_LOCALITIES = {
    "peerzadiguda", "uppal", "lb nagar", "kukatpally", "madhapur", "gachibowli",
    "koramangala", "indiranagar", "whitefield", "andheri", "bandra", "dwarka",
    "rohini", "saket", "velachery", "anna nagar", "salt lake",
}

CITY_ALIASES = {
    "hydrabad": "hyderabad", "hyderbad": "hyderabad", "hydarabad": "hyderabad",
    "bangaluru": "bengaluru", "bnglr": "bengaluru",
    "bombay": "mumbai", "madras": "chennai", "calcutta": "kolkata",
    "gurugram": "gurugram",
}

# PIN prefix (first 2 digits) -> set of states officially assigned that postal circle range.
# Based on India Post regional postal circle numbering.
PIN_PREFIX_TO_STATE = {
    "11": {"delhi"},
    "12": {"haryana"}, "13": {"haryana", "punjab"},
    "14": {"punjab"}, "15": {"punjab"}, "16": {"punjab", "chandigarh"},
    "17": {"himachal pradesh"},
    "18": {"jammu and kashmir"}, "19": {"jammu and kashmir", "ladakh"},
    "20": {"uttar pradesh"}, "21": {"uttar pradesh"}, "22": {"uttar pradesh"},
    "23": {"uttar pradesh"}, "24": {"uttar pradesh"}, "25": {"uttar pradesh"},
    "26": {"uttar pradesh", "uttarakhand"}, "27": {"uttar pradesh"}, "28": {"uttar pradesh"},
    "30": {"rajasthan"}, "31": {"rajasthan"}, "32": {"rajasthan"}, "33": {"rajasthan"}, "34": {"rajasthan"},
    "36": {"gujarat"}, "37": {"gujarat"}, "38": {"gujarat"}, "39": {"gujarat"},
    "40": {"maharashtra"}, "41": {"maharashtra"}, "42": {"maharashtra"}, "43": {"maharashtra"}, "44": {"maharashtra"},
    "45": {"madhya pradesh"}, "46": {"madhya pradesh"}, "47": {"madhya pradesh", "chhattisgarh"}, "48": {"madhya pradesh"},
    "49": {"chhattisgarh"},
    "50": {"telangana", "andhra pradesh"}, "51": {"andhra pradesh", "telangana"},
    "52": {"andhra pradesh"}, "53": {"andhra pradesh"},
    "56": {"karnataka"}, "57": {"karnataka"}, "58": {"karnataka"}, "59": {"karnataka"},
    "60": {"tamil nadu"}, "61": {"tamil nadu"}, "62": {"tamil nadu"}, "63": {"tamil nadu"}, "64": {"tamil nadu"},
    "67": {"kerala"}, "68": {"kerala"}, "69": {"kerala"},
    "70": {"west bengal"}, "71": {"west bengal"}, "72": {"west bengal"}, "73": {"west bengal"}, "74": {"west bengal"},
    "75": {"odisha"}, "76": {"odisha"}, "77": {"odisha"},
    "78": {"assam"}, "79": {"assam", "arunachal pradesh", "nagaland", "manipur", "mizoram", "tripura", "meghalaya"},
    "80": {"bihar"}, "81": {"bihar"}, "82": {"bihar", "jharkhand"}, "83": {"jharkhand"},
    "84": {"bihar"}, "85": {"bihar"},
}

STREET_KEYWORDS = [
    "road", "street", "lane", "nagar", "colony", "layout", "avenue", "cross",
    "main", "block", "sector", "phase", "extension", "marg", "chowk", "gali",
]

HOUSE_KEYWORDS = [
    "flat", "house", "h.no", "h no", "hno", "door no", "door number", "plot",
    "apartment", "apt", "building", "villa", "bungalow", "d.no", "d no",
]

ABBREVIATION_EXPANSIONS = {
    "rd": "Road", "rd.": "Road",
    "st": "Street", "st.": "Street",
    "apt": "Apartment", "apt.": "Apartment",
    "bldg": "Building", "bldg.": "Building",
    "colny": "Colony",
    "h.no": "House Number", "h no": "House Number", "hno": "House Number",
    "d.no": "Door Number", "d no": "Door Number",
    "opp": "Opposite", "opp.": "Opposite",
    "nr": "Near", "nr.": "Near",
    "govt": "Government", "govt.": "Government",
}
