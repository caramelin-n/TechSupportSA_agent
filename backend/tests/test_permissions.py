"""Tests de permisos."""
import pytest

USER = "lucia.benitez@cliente-demo.com"
SOPORTE = "diego.salinas@techsupport-demo.com"
ADMIN = "raul.gimenez@techsupport-demo.com"


def _token(client, email):
    return client.post("/auth/login", json={"email": email, "password": "techsupport123"}).json()["access_token"]


def _create(client, tok):
    r = client.post("/tickets", json={"title": "Ticket permisos", "description": "descripcion suficiente para crear", "category": "Hardware", "priority": "Media"}, headers={"Authorization": f"Bearer {tok}"})
    return r.json()["id"]


def test_usuario_no_puede_cambiar_estado(client):
    utok = _token(client, USER)
    tid = _create(client, utok)
    r = client.patch(f"/tickets/{tid}/status", json={"new_status": "En revisión"}, headers={"Authorization": f"Bearer {utok}"})
    assert r.status_code == 403


def test_soporte_puede_cambiar_estado(client):
    utok = _token(client, USER)
    tid = _create(client, utok)
    stok = _token(client, SOPORTE)
    r = client.patch(f"/tickets/{tid}/status", json={"new_status": "En revisión"}, headers={"Authorization": f"Bearer {stok}"})
    assert r.status_code == 200


def test_prioridad_solo_admin(client):
    utok = _token(client, USER)
    tid = _create(client, utok)
    stok = _token(client, SOPORTE)
    r = client.patch(f"/tickets/{tid}/priority", json={"priority": "Alta"}, headers={"Authorization": f"Bearer {stok}"})
    assert r.status_code == 403
    atok = _token(client, ADMIN)
    r = client.patch(f"/tickets/{tid}/priority", json={"priority": "Alta"}, headers={"Authorization": f"Bearer {atok}"})
    assert r.status_code == 200
    assert r.json()["priority"] == "Alta"


def test_listar_usuarios_requiere_soporte(client):
    utok = _token(client, USER)
    r = client.get("/users", headers={"Authorization": f"Bearer {utok}"})
    assert r.status_code == 403
    stok = _token(client, SOPORTE)
    r = client.get("/users", headers={"Authorization": f"Bearer {stok}"})
    assert r.status_code == 200
