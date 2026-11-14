# TechSupport S.A.

Agente de tickets (CRUD + auth JWT hoy; RAG + function calling pendiente). La spec funcional completa está en `instructions.md` (local, gitignored).

## Todo corre en Docker

El host no ejecuta nada de la app: no hay Python, Node, pytest ni alembic en el host.

```bash
cp .env.example .env

# Desarrollo (bind-mount + live reload)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build

# Producción (imágenes construidas, nginx estático)
docker compose up -d --build
```

Backend en `:8000`, frontend nginx en `:8080`. Login demo: `raul.gimenez@techsupport-demo.com` / `techsupport123` (todos los usuarios comparten esa password).

```bash
# seed, tests y migraciones (dentro del contenedor)
docker compose -f docker-compose.yml -f docker-compose.dev.yml exec backend python seed.py
docker compose -f docker-compose.yml -f docker-compose.dev.yml exec backend python -m pytest -q
docker compose -f docker-compose.yml -f docker-compose.dev.yml exec backend alembic upgrade head

# rebuild del frontend
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm frontend-build
```

## Agente

`POST /chat` (JWT) mantiene conversación por `conversation_id` y usa las
herramientas del backend (crear/consultar/actualizar tickets, historial,
resumen). Requiere `GOOGLE_API_KEY` en `.env`; sin ella el CRUD sigue
funcionando pero el agente responde error.

```bash
TOKEN=$(curl -s -X POST localhost:8000/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"raul.gimenez@techsupport-demo.com","password":"techsupport123"}' | jq -r .access_token)

curl -s -X POST localhost:8000/chat -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"message":"La impresora del 2do piso no responde","conversation_id":"demo-1"}'
```

Crear tickets, cambiar estado o prioridad y asignar requieren confirmación: la
respuesta trae `pending_actions` y se confirma con
`POST /chat/{conversation_id}/decision` (`{"decision": "approve"}` o
`{"decision": "reject", "message": "..."}`). Ver
[docs/backend-overview.md](docs/backend-overview.md#61-agente-post-chat).

```bash
curl -s -X POST localhost:8000/chat/demo-1/decision -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"decision":"approve"}'
```

Para mandar capturas, fotos o logs: `POST /chat/upload` (multipart) devuelve
un id por archivo, y `POST /chat` los recibe en `upload_ids`. Ver
[docs/backend-overview.md](docs/backend-overview.md#62-adjuntos-f02).

Pendiente: detección semántica de duplicados (pgvector).

## Documentación

- [docs/backend-overview.md](docs/backend-overview.md) — explicación de la arquitectura, auth, permisos, estados, endpoints y deploy.
- Detalles de desarrollo (dependencias, convenciones, gotchas) en `AGENTS.md` (local-only, gitignored).
