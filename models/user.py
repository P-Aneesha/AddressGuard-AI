from werkzeug.security import generate_password_hash, check_password_hash
from models import db
from utils.timestamps import now_utc


class User(db.Model):
    """
    A dashboard user. Passwords are never stored in plain text - only a
    salted hash (Werkzeug's PBKDF2-based hasher) is persisted.
    """
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now_utc)

    def set_password(self, raw_password: str):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)

    def to_dict(self):
        return {"id": self.id, "username": self.username, "email": self.email}
