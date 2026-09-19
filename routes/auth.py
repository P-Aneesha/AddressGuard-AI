from functools import wraps
from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for

from models import db
from models.user import User

auth_bp = Blueprint("auth", __name__)


def login_required(view_func):
    """Protects a view - redirects browser requests to /login, and returns
    a 401 JSON error for API/XHR requests, if no user is signed in."""
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "Authentication required."}), 401
            return redirect(url_for("auth.login_page"))
        return view_func(*args, **kwargs)
    return wrapped


@auth_bp.route("/login", methods=["GET"])
def login_page():
    if session.get("user_id"):
        return redirect(url_for("views.index"))
    return render_template("login.html")


@auth_bp.route("/register", methods=["GET"])
def register_page():
    if session.get("user_id"):
        return redirect(url_for("views.index"))
    return render_template("register.html")


@auth_bp.route("/api/auth/register", methods=["POST"])
def api_register():
    payload = request.get_json(silent=True) or {}
    username = (payload.get("username") or "").strip()
    email = (payload.get("email") or "").strip() or None
    password = payload.get("password") or ""

    if not username or len(username) < 3:
        return jsonify({"error": "Username must be at least 3 characters."}), 400
    if not password or len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters."}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({"error": "That username is already taken."}), 409

    user = User(username=username, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    session["user_id"] = user.id
    session["username"] = user.username
    return jsonify({"user": user.to_dict()}), 201


@auth_bp.route("/api/auth/login", methods=["POST"])
def api_login():
    payload = request.get_json(silent=True) or {}
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""

    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid username or password."}), 401

    session["user_id"] = user.id
    session["username"] = user.username
    return jsonify({"user": user.to_dict()})


@auth_bp.route("/api/auth/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"success": True})


@auth_bp.route("/api/auth/me", methods=["GET"])
def api_me():
    if not session.get("user_id"):
        return jsonify({"user": None})
    return jsonify({"user": {"id": session["user_id"], "username": session["username"]}})
