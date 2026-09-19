from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

from models.validation import (  # noqa: E402,F401
    AddressValidation,
    ParsedAddressField,
    CorrectionHistory,
    ValidationEvent,
    Report,
)
from models.user import User  # noqa: E402,F401
