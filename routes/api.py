import os
from flask import Blueprint, request, jsonify, current_app, send_file, session

from models import db
from models.validation import AddressValidation, ParsedAddressField, CorrectionHistory, ValidationEvent, Report
from services.explainability_service import run_full_pipeline
from services import report_service
from utils.timestamps import now_utc

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.before_request
def _require_login():
    if not session.get("user_id"):
        return jsonify({"error": "Authentication required."}), 401


def _persist_pipeline_result(record: AddressValidation, raw_text: str, pipeline_result: dict, event_type: str):
    record.raw_input = raw_text
    record.working_address = pipeline_result["fields"]
    record.confidence_score = pipeline_result["confidence_result"]["score"]
    record.confidence_breakdown = pipeline_result["confidence_result"]
    record.risk_level = pipeline_result["risk_result"]["risk_level"]
    record.risk_factors = pipeline_result["risk_result"]["risk_factors"]
    record.final_status = pipeline_result["decision_result"]["final_status"]
    record.reasons = pipeline_result["decision_result"]["reasons"]
    record.problems = pipeline_result["decision_result"]["problems"]
    record.recommendation = pipeline_result["decision_result"]["recommendation"]
    record.validation_details = {
        "pipeline_steps": pipeline_result["pipeline_steps"],
        "parser_warnings": pipeline_result["parse_result"]["parser_warnings"],
        "unrecognized_text": pipeline_result["parse_result"]["unrecognized_text"],
        "phone_result": pipeline_result["phone_result"],
        "pin_result": pipeline_result["pin_result"],
        "location_result": pipeline_result["location_result"],
        "anomaly_result": pipeline_result["anomaly_result"],
    }
    record.updated_at = now_utc()

    # replace parsed field rows
    ParsedAddressField.query.filter_by(validation_id=record.id).delete()
    for field_name, value in pipeline_result["fields"].items():
        db.session.add(ParsedAddressField(
            validation_id=record.id, field_name=field_name, field_value=value,
            extraction_confidence=pipeline_result["parse_result"]["extraction_confidence"],
        ))

    db.session.add(ValidationEvent(
        validation_id=record.id, event_type=event_type,
        event_details={"status": record.final_status, "confidence": record.confidence_score},
    ))


@api_bp.route("/validate", methods=["POST"])
def validate_address():
    payload = request.get_json(silent=True) or {}
    raw_text = (payload.get("raw_text") or "").strip()
    if not raw_text:
        return jsonify({"error": "raw_text is required"}), 400

    pipeline_result = run_full_pipeline(raw_text)

    record = AddressValidation(raw_input=raw_text, working_address={})
    db.session.add(record)
    db.session.flush()  # get record.id before persisting related rows

    _persist_pipeline_result(record, raw_text, pipeline_result, "CREATED")

    # store correction suggestions
    for s in pipeline_result["suggestions"]:
        db.session.add(CorrectionHistory(
            validation_id=record.id, field_name=s["field"],
            original_value=s["original_value"], suggested_value=s["suggested_value"],
            reason=s["reason"], suggestion_confidence=s["confidence"], decision="PENDING",
        ))

    db.session.commit()

    return jsonify({
        "validation": record.to_full_dict(),
        "suggestions": pipeline_result["suggestions"],
    }), 201


@api_bp.route("/correction/<validation_id>", methods=["POST"])
def apply_correction(validation_id):
    """
    Body: { "decisions": [ {"field": "city", "decision": "ACCEPT"|"REJECT"|"MANUAL_EDIT", "value": "..."} ] }
    Applies approved changes, then re-parses/re-validates the whole address.
    """
    record = AddressValidation.query.filter_by(validation_id=validation_id).first()
    if not record:
        return jsonify({"error": "Validation record not found"}), 404

    payload = request.get_json(silent=True) or {}
    decisions = payload.get("decisions", [])

    working_fields = dict(record.working_address or {})

    for d in decisions:
        field = d.get("field")
        decision = d.get("decision")
        if decision == "ACCEPT":
            corr = CorrectionHistory.query.filter_by(
                validation_id=record.id, field_name=field, decision="PENDING"
            ).order_by(CorrectionHistory.id.desc()).first()
            if corr:
                working_fields[field] = corr.suggested_value
                corr.decision = "ACCEPT"
                corr.final_value = corr.suggested_value
                corr.decided_at = now_utc()
        elif decision == "MANUAL_EDIT":
            new_value = d.get("value")
            working_fields[field] = new_value
            corr = CorrectionHistory(
                validation_id=record.id, field_name=field,
                original_value=working_fields.get(field), suggested_value=new_value,
                reason="Manually edited by user.", suggestion_confidence=100,
                decision="MANUAL_EDIT", final_value=new_value, decided_at=now_utc(),
            )
            db.session.add(corr)
        elif decision == "REJECT":
            corr = CorrectionHistory.query.filter_by(
                validation_id=record.id, field_name=field, decision="PENDING"
            ).order_by(CorrectionHistory.id.desc()).first()
            if corr:
                corr.decision = "REJECT"
                corr.final_value = corr.original_value
                corr.decided_at = now_utc()

    previous_result = record.to_summary_dict()

    # Re-parse + re-validate the whole corrected address
    pipeline_result = run_full_pipeline(record.raw_input, working_fields=working_fields)
    _persist_pipeline_result(record, record.raw_input, pipeline_result, "RE_VALIDATED")

    db.session.commit()

    return jsonify({
        "previous_result": previous_result,
        "new_result": record.to_full_dict(),
    })


@api_bp.route("/history", methods=["GET"])
def list_history():
    search = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "").strip()

    query = AddressValidation.query
    if search:
        like = f"%{search}%"
        query = query.filter(
            db.or_(
                AddressValidation.validation_id.ilike(like),
                AddressValidation.raw_input.ilike(like),
            )
        )
    if status_filter:
        query = query.filter(AddressValidation.final_status == status_filter)

    records = query.order_by(AddressValidation.created_at.desc()).limit(200).all()
    return jsonify({"results": [r.to_summary_dict() for r in records]})


@api_bp.route("/history/<validation_id>", methods=["GET"])
def get_history_record(validation_id):
    record = AddressValidation.query.filter_by(validation_id=validation_id).first()
    if not record:
        return jsonify({"error": "Validation record not found"}), 404
    return jsonify(record.to_full_dict())


def _get_record_or_404(validation_id):
    record = AddressValidation.query.filter_by(validation_id=validation_id).first()
    return record


@api_bp.route("/report/pdf/<validation_id>", methods=["GET"])
def report_pdf(validation_id):
    record = _get_record_or_404(validation_id)
    if not record:
        return jsonify({"error": "Validation record not found"}), 404
    path = report_service.generate_pdf_report(record, current_app.config["REPORTS_DIR"])
    db.session.add(Report(validation_id=record.id, report_type="PDF", file_path=path))
    db.session.commit()
    return send_file(path, as_attachment=True)


@api_bp.route("/report/csv/<validation_id>", methods=["GET"])
def report_csv(validation_id):
    record = _get_record_or_404(validation_id)
    if not record:
        return jsonify({"error": "Validation record not found"}), 404
    path = report_service.generate_csv_report(record, current_app.config["REPORTS_DIR"])
    db.session.add(Report(validation_id=record.id, report_type="CSV", file_path=path))
    db.session.commit()
    return send_file(path, as_attachment=True)


@api_bp.route("/report/qr/<validation_id>", methods=["GET"])
def report_qr(validation_id):
    record = _get_record_or_404(validation_id)
    if not record:
        return jsonify({"error": "Validation record not found"}), 404
    path = report_service.generate_qr_code(record, current_app.config["REPORTS_DIR"], current_app.config["PUBLIC_BASE_URL"])
    db.session.add(Report(validation_id=record.id, report_type="QR", file_path=path))
    db.session.commit()
    return send_file(path, mimetype="image/png")


@api_bp.route("/report/barcode/<validation_id>", methods=["GET"])
def report_barcode(validation_id):
    record = _get_record_or_404(validation_id)
    if not record:
        return jsonify({"error": "Validation record not found"}), 404
    path = report_service.generate_barcode(record, current_app.config["REPORTS_DIR"])
    db.session.add(Report(validation_id=record.id, report_type="BARCODE", file_path=path))
    db.session.commit()
    return send_file(path, mimetype="image/png")
