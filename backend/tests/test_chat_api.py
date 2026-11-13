"""Tests de POST /chat con el agente mockeado (sin red ni API key)."""
USUARIO = "lucia.benitez@cliente-demo.com"


def _token(client, email=USUARIO):
    r = client.post("/auth/login", json={"email": email, "password": "techsupport123"})
    return r.json()["access_token"]


def _override(app, runner):
    from src.api.routes_chat import get_run_agent

    app.dependency_overrides[get_run_agent] = lambda: runner
    return get_run_agent


def test_chat_requiere_token(client):
    r = client.post("/chat", json={"message": "hola"})
    assert r.status_code == 401


def test_chat_devuelve_respuesta_y_conversation_id(client):
    from src.main import app

    calls = []

    async def fake(user_id, conversation_id, content):
        calls.append((user_id, conversation_id, content))
        return "respuesta del agente"

    _override(app, fake)
    tok = _token(client)
    r = client.post(
        "/chat",
        json={"message": "Hola, necesito ayuda"},
        headers={"Authorization": f"Bearer {tok}"},
    )

    assert r.status_code == 200
    body = r.json()
    assert body["reply"] == "respuesta del agente"
    assert body["conversation_id"]

    # La identidad sale del JWT, no del body
    assert calls[0][0] == "U001"
    assert calls[0][2] == "Hola, necesito ayuda"


def test_chat_respeta_conversation_id_existente(client):
    from src.main import app

    async def fake(user_id, conversation_id, content):
        return f"conv={conversation_id}"

    _override(app, fake)
    tok = _token(client)
    r = client.post(
        "/chat",
        json={"message": "seguimos", "conversation_id": "demo-1"},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 200
    assert r.json()["conversation_id"] == "demo-1"
    assert r.json()["reply"] == "conv=demo-1"


def test_chat_rechaza_mensaje_vacio(client):
    tok = _token(client)
    r = client.post(
        "/chat",
        json={"message": ""},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 422
