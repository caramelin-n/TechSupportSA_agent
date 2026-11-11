"""Tests de máquina de estados."""
import pytest

ADMIN = "raul.gimenez@techsupport-demo.com"
USER = "lucia.benitez@cliente-demo.com"


def _token(client, email):
    return client.post("/auth/login", json={"email": email, "password": "techsupport123"}).json()["access_token"]


def _headers(tok):
    return {"Authorization": f"Bearer {tok}"}


def test_valid_transition_abierto_a_en_revision(client):
    tok = _token(client, USER)
    r = client.post("/tickets", json={"title": "Problema de prueba suficiente", "description": "descripcion suficientemente larga para validar", "category": "Hardware", "priority": "Media"}, headers=_headers(tok))
    assert r.status_code == 201
    tid = r.json()["id"]
    r = client.patch(f"/tickets/{tid}/status", json={"new_status": "En revisión"}, headers=_headers(tok))
    # usuario no puede cambiar estado
    assert r.status_code == 403


def test_invalid_transition_abierto_a_cerrado(client):
    tok = _token(client, USER)
    r = client.post("/tickets", json={"title": "Problema de prueba suficiente", "description": "descripcion suficientemente larga para validar", "category": "Hardware", "priority": "Media"}, headers=_headers(tok))
    tid = r.json()["id"]
    admin_tok = _token(client, ADMIN)
    r = client.patch(f"/tickets/{tid}/status", json={"new_status": "Cerrado"}, headers=_headers(admin_tok))
    assert r.status_code == 409


def test_full_happy_path(client):
    tok = _token(client, USER)
    admin_tok = _token(client, ADMIN)
    r = client.post("/tickets", json={"title": "Problema de prueba suficiente", "description": "descripcion suficientemente larga para validar", "category": "Hardware", "priority": "Media"}, headers=_headers(tok))
    tid = r.json()["id"]
    sop_tok = _token(client, "diego.salinas@techsupport-demo.com")
    for st in ("En revisión", "En progreso", "Resuelto"):
        r = client.patch(f"/tickets/{tid}/status", json={"new_status": st}, headers=_headers(sop_tok))
        assert r.status_code == 200, (st, r.text)
    r = client.patch(f"/tickets/{tid}/status", json={"new_status": "Cerrado"}, headers=_headers(admin_tok))
    assert r.status_code == 200
    assert r.json()["status"] == "Cerrado"
