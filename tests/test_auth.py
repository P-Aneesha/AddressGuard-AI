"""
Auth + dashboard tests: registration, login, protected-route gating,
and logout, exercised through the real Flask app/test client.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from app import app as flask_app
from models import db


@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as client:
        with flask_app.app_context():
            db.create_all()
        yield client
        with flask_app.app_context():
            db.session.remove()
            db.drop_all()


def test_index_requires_login(client):
    r = client.get("/")
    assert r.status_code == 302
    assert "/login" in r.headers["Location"]


def test_api_requires_login(client):
    r = client.post("/api/validate", json={"raw_text": "test"})
    assert r.status_code == 401


def test_register_login_logout_flow(client):
    r = client.post("/api/auth/register", json={"username": "demo_user", "password": "password123"})
    assert r.status_code == 201

    # registering signs the user in immediately
    r = client.get("/")
    assert r.status_code == 200

    r = client.post("/api/auth/logout")
    assert r.status_code == 200

    r = client.get("/")
    assert r.status_code == 302

    r = client.post("/api/auth/login", json={"username": "demo_user", "password": "wrong-password"})
    assert r.status_code == 401

    r = client.post("/api/auth/login", json={"username": "demo_user", "password": "password123"})
    assert r.status_code == 200


def test_dashboard_reflects_validations(client):
    client.post("/api/auth/register", json={"username": "demo_user2", "password": "password123"})
    client.post("/api/validate", json={
        "raw_text": "Priya Sharma, 9876543210, H.No 10-101, Road No 1, Peerzadiguda, Hyderabad, Telangana, 500039"
    })
    r = client.get("/dashboard")
    assert r.status_code == 200
    assert b"Total Validations" in r.data
