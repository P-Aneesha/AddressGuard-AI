from flask import Blueprint, render_template, session
from sqlalchemy import func

from models import db
from models.validation import AddressValidation
from routes.auth import login_required

views_bp = Blueprint("views", __name__)


@views_bp.route("/")
@login_required
def index():
    return render_template("index.html", username=session.get("username"))


@views_bp.route("/dashboard")
@login_required
def dashboard():
    total = db.session.query(func.count(AddressValidation.id)).scalar() or 0
    avg_confidence = db.session.query(func.avg(AddressValidation.confidence_score)).scalar() or 0

    status_counts = dict(
        db.session.query(AddressValidation.final_status, func.count(AddressValidation.id))
        .group_by(AddressValidation.final_status).all()
    )
    risk_counts = dict(
        db.session.query(AddressValidation.risk_level, func.count(AddressValidation.id))
        .group_by(AddressValidation.risk_level).all()
    )

    recent = AddressValidation.query.order_by(AddressValidation.created_at.desc()).limit(8).all()

    verified_count = status_counts.get("VERIFIED", 0)
    verified_rate = round((verified_count / total) * 100, 1) if total else 0

    return render_template(
        "dashboard.html",
        username=session.get("username"),
        total=total,
        avg_confidence=round(avg_confidence, 1),
        verified_rate=verified_rate,
        status_counts=status_counts,
        risk_counts=risk_counts,
        recent=recent,
    )
