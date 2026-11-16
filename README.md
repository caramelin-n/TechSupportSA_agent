# TechSupport S.A.

Agente de tickets de soporte: CRUD + auth JWT, agente conversacional con
function calling, detección semántica de duplicados, entrada multimodal
(imágenes, TXT y LOG) y frontend con login. 

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

Para detectar tickets duplicados, los tickets del seed necesitan sus
embeddings (requiere `GOOGLE_API_KEY`):

```bash
docker compose exec backend python scripts/indexar_tickets.py
```

Ver [docs/backend-overview.md](docs/backend-overview.md#63-tickets-duplicados-criterio-10).

### Escenarios de prueba (criterio 12)

13 conversaciones contra el modelo real que cubren F01–F12 y los criterios de
evaluación, con un informe en Markdown de cada conversación:

```bash
docker compose exec backend python scripts/escenarios.py --preparar
```

`--preparar` recarga el seed (borra los datos actuales). Ver
[docs/backend-overview.md](docs/backend-overview.md#8-escenarios-de-prueba-criterio-12).

## Frontend

SPA React (Vite + Tailwind) servida por nginx en `http://localhost:8080`.
El login vive en `/login`, con botones de acceso rápido para los tres roles de
la demo. Después del login hay dos pantallas:

- **Chat** (`/`): texto, adjuntos (PNG/JPG/WEBP/TXT/LOG) y botones de
  **Aprobar / Rechazar** para las acciones que requieren confirmación.
- **Tickets** (`/tickets`): listado con filtros y paginación, detalle con
  historial y comentarios, y acciones según rol (estado, prioridad, asignación).
  El alta directa está en `/tickets/new`.

```bash
# tests (vitest dentro de la imagen de build)
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm \
  --entrypoint sh frontend-build -c "npm ci --silent && npm test"

# build de producción (imagen con el dist ya compilado)
docker compose build frontend
```

Para el dev server de Vite dentro de Docker hace falta un servicio con
`target: build`; el `frontend-build` ya lo tiene. Si corrés `npm run dev` en el
host, definí `VITE_PROXY_TARGET=localhost` (ver `frontend/.env.example`).

## Documentación

- [docs/backend-overview.md](docs/backend-overview.md) — explicación de la arquitectura, auth, permisos, estados, endpoints y deploy.
- [docs/frontend-overview.md](docs/frontend-overview.md) — arquitectura del frontend, flujo de autenticación, proxy y tests.
