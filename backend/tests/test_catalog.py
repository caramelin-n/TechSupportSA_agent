"""Tests del catálogo (categorías y prioridades)."""


def _token(client, email="lucia.benitez@cliente-demo.com"):
    r = client.post("/auth/login", json={"email": email, "password": "techsupport123"})
    return r.json()["access_token"]


def test_categorias_requiere_auth(client):
    assert client.get("/catalog/categories").status_code == 401


def test_categorias_devuelve_las_del_seed(client):
    tok = _token(client)
    r = client.get("/catalog/categories", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    nombres = [c["name"] for c in r.json()]
    assert len(nombres) == 7
    assert "Hardware" in nombres
    assert "Redes y conectividad" in nombres


def test_prioridades_devuelve_las_del_seed(client):
    tok = _token(client)
    r = client.get("/catalog/priorities", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    nombres = {p["name"] for p in r.json()}
    assert nombres == {"Baja", "Media", "Alta", "Crítica"}
