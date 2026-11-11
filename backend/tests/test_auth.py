"""Tests de autenticación."""
import pytest

ADMIN_EMAIL = "raul.gimenez@techsupport-demo.com"
USER_EMAIL = "lucia.benitez@cliente-demo.com"


def test_login_ok(client):
    r = client.post("/auth/login", json={"email": ADMIN_EMAIL, "password": "techsupport123"})
    assert r.status_code == 200
    assert r.json()["token_type"] == "bearer"
    assert r.json()["access_token"]


def test_login_bad_password(client):
    r = client.post("/auth/login", json={"email": ADMIN_EMAIL, "password": "wrong"})
    assert r.status_code == 401


def test_me_requires_token(client):
    assert client.get("/auth/me").status_code == 401


def test_me_ok(client):
    tok = client.post("/auth/login", json={"email": ADMIN_EMAIL, "password": "techsupport123"}).json()["access_token"]
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    assert r.json()["role"] == "admin"
