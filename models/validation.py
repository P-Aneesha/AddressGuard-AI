import uuid
from models import db
from utils.timestamps import now_utc


def gen_validation_id():
    return "AG-" + uuid.uuid4().hex[:10].upper()


class AddressValidation(db.Model):
    """
    The master record for one address validation session. Holds the raw
    input, the current parsed/corrected address, and the latest decision.
    """
    __tablename__ = "address_validations"

    id = db.Column(db.Integer, primary_key=True)
    validation_id = db.Column(db.String(32), unique=True, nullable=False, default=gen_validation_id)

    raw_input = db.Column(db.Text, nullable=False)

    # current working structured address (JSON dict), updated after corrections
    working_address = db.Column(db.JSON, nullable=False, default=dict)

    confidence_score = db.Column(db.Integer, nullable=False, default=0)
    confidence_breakdown = db.Column(db.JSON, nullable=False, default=dict)

    risk_level = db.Column(db.String(16), nullable=False, default="CRITICAL")
    risk_factors = db.Column(db.JSON, nullable=False, default=list)

    final_status = db.Column(db.String(40), nullable=False, default="FAKE ADDRESS")
    reasons = db.Column(db.JSON, nullable=False, default=list)
    problems = db.Column(db.JSON, nullable=False, default=list)
    recommendation = db.Column(db.Text, nullable=False, default="")

    validation_details = db.Column(db.JSON, nullable=False, default=dict)  # full pipeline step results

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now_utc)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now_utc, onupdate=now_utc)

    fields = db.relationship("ParsedAddressField", backref="validation", cascade="all, delete-orphan")
    corrections = db.relationship("CorrectionHistory", backref="validation", cascade="all, delete-orphan")
    events = db.relationship("ValidationEvent", backref="validation", cascade="all, delete-orphan")
    reports = db.relationship("Report", backref="validation", cascade="all, delete-orphan")

    def to_summary_dict(self):
        return {
            "validation_id": self.validation_id,
            "final_status": self.final_status,
            "confidence_score": self.confidence_score,
            "risk_level": self.risk_level,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "working_address": self.working_address,
        }

    def to_full_dict(self):
        data = self.to_summary_dict()
        data.update({
            "raw_input": self.raw_input,
            "confidence_breakdown": self.confidence_breakdown,
            "risk_factors": self.risk_factors,
            "reasons": self.reasons,
            "problems": self.problems,
            "recommendation": self.recommendation,
            "validation_details": self.validation_details,
            "corrections": [c.to_dict() for c in self.corrections],
        })
        return data


class ParsedAddressField(db.Model):
    """Individual extracted address component, with its own extraction confidence."""
    __tablename__ = "parsed_address_fields"

    id = db.Column(db.Integer, primary_key=True)
    validation_id = db.Column(db.Integer, db.ForeignKey("address_validations.id"), nullable=False)

    field_name = db.Column(db.String(40), nullable=False)   # e.g. "city", "pin_code"
    field_value = db.Column(db.String(255), nullable=True)
    extraction_confidence = db.Column(db.Integer, nullable=False, default=0)


class CorrectionHistory(db.Model):
    """One suggested correction and the human decision made about it."""
    __tablename__ = "correction_history"

    id = db.Column(db.Integer, primary_key=True)
    validation_id = db.Column(db.Integer, db.ForeignKey("address_validations.id"), nullable=False)

    field_name = db.Column(db.String(40), nullable=False)
    original_value = db.Column(db.String(255), nullable=True)
    suggested_value = db.Column(db.String(255), nullable=True)
    reason = db.Column(db.String(255), nullable=True)
    suggestion_confidence = db.Column(db.Integer, nullable=False, default=0)

    decision = db.Column(db.String(16), nullable=False, default="PENDING")  # ACCEPT / REJECT / MANUAL_EDIT / PENDING
    final_value = db.Column(db.String(255), nullable=True)

    decided_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now_utc)

    def to_dict(self):
        return {
            "field_name": self.field_name,
            "original_value": self.original_value,
            "suggested_value": self.suggested_value,
            "reason": self.reason,
            "suggestion_confidence": self.suggestion_confidence,
            "decision": self.decision,
            "final_value": self.final_value,
        }


class ValidationEvent(db.Model):
    """Append-only audit log of everything that happened to a validation record."""
    __tablename__ = "validation_events"

    id = db.Column(db.Integer, primary_key=True)
    validation_id = db.Column(db.Integer, db.ForeignKey("address_validations.id"), nullable=False)

    event_type = db.Column(db.String(40), nullable=False)  # CREATED / RE_VALIDATED / CORRECTION_APPLIED / REPORT_GENERATED
    event_details = db.Column(db.JSON, nullable=False, default=dict)
    event_timestamp = db.Column(db.DateTime(timezone=True), nullable=False, default=now_utc)


class Report(db.Model):
    """Generated PDF/CSV/QR/Barcode artifacts tied to a validation record."""
    __tablename__ = "reports"

    id = db.Column(db.Integer, primary_key=True)
    validation_id = db.Column(db.Integer, db.ForeignKey("address_validations.id"), nullable=False)

    report_type = db.Column(db.String(16), nullable=False)  # PDF / CSV / QR / BARCODE
    file_path = db.Column(db.String(255), nullable=False)
    generated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now_utc)
