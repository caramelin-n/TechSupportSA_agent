"""Tests de flujo de tickets."""
import pytest

USER = "lucia.benitez@cliente-demo.com"
ADMIN = "raul.gimenez@techsupport-demo.com"


def _token(client, email):
    return client.post("/auth/login", json={"email": email, "password": "techsupport123"}).json()["access_token"]


def test_create_and_comment_and_history(client):
    tok = _token(client, USER)
    h = {"Authorization": f"Bearer {tok}"}
    r = client.post("/tickets", json={
        "title": "Impresora no responde",
        "description": "La impresora del 2do piso no responde al imprimir PDF",
        "category": "Hardware",
        "priority": "Media",
    }, headers=h)
    assert r.status_code == 201
    tid = r.json()["id"]
    assert tid.startswith("TCK-")
    assert r.json()["status"] == "Abierto"

    r = client.post(f"/tickets/{tid}/comments", json={"text": "Probé reiniciar"}, headers=h)
    assert r.status_code == 201

    r = client.get(f"/tickets/{tid}/history", headers=h)
    assert r.status_code == 200
    events = [e["event_type"] for e in r.json()]
    assert "CREATED" in events
    assert "COMMENT_ADDED" in events


def test_summary_requires_soporte(client):
    tok = _token(client, USER)
    r = client.get("/tickets/summary", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 403
    admin_tok = _token(client, ADMIN)
    r = client.get("/tickets/summary", headers={"Authorization": f"Bearer {admin_tok}"})
    assert r.status_code == 200
    assert "total" in r.json()


def test_user_cannot_see_other_user_ticket(client):
    tok = _token(client, USER)
    h = {"Authorization": f"Bearer {tok}"}
    r = client.post("/tickets", json={"title": "Ticket privado", "description": "descripcion suficiente para crear", "category": "Hardware", "priority": "Baja"}, headers=h)
    tid = r.json()["id"]
    other = "martin.ojeda@cliente-demo.com"
    other_tok = _token(client, other)
    r = client.get(f"/tickets/{tid}", headers={"Authorization": f"Bearer {other_tok}"})
    assert r.status_code == 403


def test_filtro_status_valido_acepta_valores_en_espanol(client):
    tok = _token(client, ADMIN)
    r = client.get("/tickets", params={"status": "En revisión"}, headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200


def test_filtro_status_invalido_devuelve_422(client):
    """Un status desconocido debe ser 422 (validacion), no 500 (error interno)."""
    tok = _token(client, ADMIN)
    r = client.get("/tickets", params={"status": "INVALID"}, headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 422


def test_filtro_prioridad_invalido_devuelve_422(client):
    tok = _token(client, ADMIN)
    r = client.get("/tickets", params={"priority": "NOPE"}, headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 422


def test_buscar_sin_resolver_por_api(client):
    tok = client.post(
        "/auth/login",
        json={"email": "diego.salinas@techsupport-demo.com", "password": "techsupport123"},
    ).json()["access_token"]
    r = client.get("/tickets", params={"unresolved": "true"}, headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    estados = {t["status"] for t in r.json()}
    assert estados and not estados & {"Resuelto", "Cerrado"}
