# Backend — TechSupport S.A.

> Documento de **explicación** (Diátaxis): describe cómo está armado el backend, por qué se tomaron ciertas decisiones y qué queda pendiente. No es un tutorial paso a paso ni la referencia exhaustiva de la API (eso está en `/docs` de FastAPI).

## 1. Visión general y alcance

### 1.1 Qué hace hoy

El backend expone una API REST para gestión de tickets de soporte con autenticación JWT y control de acceso por roles. Está **completo en la fase CRUD/tools**:

- Auth con email+password, emisión de JWT HS256.
- CRUD de tickets con filtros y paginación.
- Máquina de estados estricta.
- Comentarios e historial de eventos.
- Resumen de incidencias por estado/categoría/prioridad.
- Gestión de usuarios (lectura).

**Pendiente (fase agente):** RAG, `buscar_tickets_similares` con pgvector, function calling, multimodal (imágenes/logs), endpoint de chat. **Pendiente (frontend):** la UI es solo un scaffold que consulta `/api/health`.

### 1.2 Stack y decisiones

- **Framework:** FastAPI (`uvicorn src.main:app`), Python 3.12.
- **ORM/migraciones:** SQLAlchemy 2.0 + Alembic (no psycopg crudo).
- **DB:** PostgreSQL 16 + pgvector (`pgvector/pgvector:pg16`). SQLite quedó eliminado.
- **Auth:** JWT HS256 con `pyjwt`, hashing argon2 vía `pwdlib[argon2]`.
- **Validación:** Pydantic v2, enums para `Priority`/`Status`/`HistoryEventType`.
- **Contenedores:** Docker Compose (db/backend/frontend), backend con `uv` y capa de dependencias cacheada.

Razón del split en dos fases: aislar la lógica de negocio verificable (CRUD + permisos) del agente de IA, que depende de un proveedor de embeddings y prompts todavía no definidos.

## 2. Cómo correr y desplegar

### 2.1 Prerrequisitos

- Docker + Docker Compose.
- Archivo `.env` en la raíz (gitignored). Sin él compose **no levanta** (usa `${VAR:?}`).

```bash
cp .env.example .env
```

Variables (`DATABASE_URL`, `POSTGRES_*`, `SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES`). `SECRET_KEY` es **obligatoria** (sin default) y debe tener ≥16 caracteres; `config.py` la valida al arrancar.

### 2.2 Arranque

```bash
docker compose up --build
docker compose exec backend python seed.py
```

`entrypoint.sh` corre `alembic upgrade head` automáticamente antes de uvicorn. La extensión `vector` se crea en el primer boot del volumen (`db/init/01-init.sql`); para re-ejecutarla: `docker compose down -v`.

### 2.3 Tests

**Importante:** los tests deben correr **dentro del contenedor**, porque `db` no publica el puerto 5432.

```bash
docker compose exec backend python -m pytest -q          # 18 tests
docker compose exec backend python -m pytest tests/test_state_machine.py -q
```

Gotchas:

- `tests/conftest.py` tiene un fixture `autouse` que ejecuta `seed.main()` una vez por sesión: correr tests **borra y recarga la DB** (destructivo).
- El fixture `client` sobreescribe `get_db` y usa rollback por test con `join_transaction_mode="create_savepoint"`; si se cambia a `commit()` directo sin ese modo se pierde el aislamiento.
- `TestClient` requiere `httpx`.

### 2.4 Dependencias

`requirements.txt` lleva **pins exactos** por freeze. Para agregar una:

```bash
cd backend
uv venv --python 3.12 .venv
uv pip install <paquete>
uv pip freeze --python .venv/bin/python > requirements.txt
```

No editar a mano con rangos `>=`. `psycopg[binary]` es obligatorio (la imagen slim no trae libpq).

## 3. Arquitectura por capas

```
backend/src/
├── main.py              # entrypoint, incluye routers
├── db.py                # engine, SessionLocal, get_session
├── core/
│   ├── config.py        # pydantic-settings (DATABASE_URL, SECRET_KEY, ...)
│   └── security.py      # argon2 hash + JWT HS256
├── models/__init__.py   # 8 modelos SQLAlchemy (paquete)
├── schemas/             # Pydantic + enums
│   ├── ticket.py
│   ├── user.py
│   └── auth.py
├── services/
│   ├── ticket_service.py
│   ├── user_service.py
│   └── exceptions.py
└── api/
    ├── deps.py
    ├── routes_auth.py
    ├── routes_users.py
    ├── routes_tickets.py
    └── routes_health.py
```

- **`core/`**: configuración y seguridad. `config.py` valida `DATABASE_URL` (prefijo `postgresql`) y `SECRET_KEY` (≥16). `security.py` expone `hash_password`, `verify_password`, `create_access_token`, `decode_access_token`.
- **`models/`**: paquete (no módulo). Los 8 modelos: `User`, `Ticket`, `Attachment`, `Comment`, `HistoryEvent`, `Category`, `Priority`, `DocumentEmbedding`. Las FKs son **strings planos**, no relaciones ORM, por eso el seed hace flush por etapas.
- **`schemas/`**: Pydantic v2. `Priority`, `Status`, `HistoryEventType` son enums `str`. `TicketCreate` valida categoría contra el catálogo en el servicio (no en el schema).
- **`services/`**: lógica pura, sin HTTP. Lanza excepciones de dominio (`NotFound`, `Forbidden`, `InvalidTransition`, `ValidationError`, `Unauthorized`) que la capa API mapea a HTTP.
- **`api/`**: routers FastAPI + `deps.py` (`get_db`, `get_current_user`, `require_roles`).

## 4. Autenticación y permisos

### 4.1 Flujo

1. `POST /auth/login` recibe `{email, password}` (JSON).
2. `user_service.authenticate` busca por email y verifica argon2.
3. Se devuelve `{access_token, token_type: "bearer"}` con JWT HS256 cuyo `sub` es el `id` del usuario.
4. Rutas protegidas usan `OAuth2PasswordBearer(tokenUrl="/auth/login")`; `get_current_user` decodifica y carga el `User`.

`GET /auth/me` devuelve el usuario autenticado.

### 4.2 Matriz de permisos

| Acción | usuario | soporte | admin |
|---|---|---|---|
| Crear ticket | ✅ | ✅ | ✅ |
| Leer propio ticket | ✅ | ✅ | ✅ |
| Leer todos los tickets | ❌ | ✅ | ✅ |
| Comentar (propio) | ✅ | ✅ | ✅ |
| Cambiar estado | ❌ | ✅ | ✅ |
| Asignar ticket | ❌ | ✅ | ✅ |
| Cambiar prioridad | ❌ | ❌ | ✅ |
| Cerrar ticket (`Cerrado`) | ❌ | ❌ | ✅ |
| Listar usuarios | ❌ | ✅ | ✅ |
| Resumen de incidencias | ❌ | ✅ | ✅ |

`Cerrado` solo lo setea `admin`; `Resuelto` lo setean `soporte`/`admin`.

## 5. Dominio de tickets

### 5.1 Identidad y creación

- IDs: `TCK-####` calculados como `max(id)+1` (no concurrency-safe; aceptado para la demo).
- Estado inicial: `Abierto`.
- Evento `CREATED` en `history` con actor y timestamp.
- Adjuntos opcionales en la creación generan eventos `FILE_ATTACHED`.
- Categoría se valida contra la tabla `categories`.

### 5.2 Máquina de estados

```
Abierto → En revisión
En revisión → En progreso | Pendiente
En progreso → Resuelto | Pendiente
Pendiente → En progreso
Resuelto → Cerrado
Cerrado → (terminal)
```

- Transición inválida → `409 Conflict` (`InvalidTransition`).
- `Cerrado` solo por `admin` → `403` si no.
- Cambio de estado por `usuario` → `403` (solo soporte/admin).

### 5.3 Otros cambios

- **Prioridad** (`PATCH /tickets/{id}/priority`): solo admin; genera `PRIORITY_CHANGED`.
- **Asignación** (`PATCH /tickets/{id}/assignee`): soporte/admin; genera `ASSIGNED`.
- **Comentarios** (`POST /tickets/{id}/comments`): cualquier lector del ticket; genera `COMMENT_ADDED`.
- **Historial** (`GET /tickets/{id}/history`): solo lectores del ticket.

### 5.4 Resumen

`GET /tickets/summary` (soporte/admin) devuelve conteos por estado, categoría, prioridad y total.

## 6. Endpoints (referencia rápida)

| Método | Ruta | Rol mínimo |
|---|---|---|
| POST | `/auth/login` | público |
| GET | `/auth/me` | autenticado |
| GET | `/users` | soporte |
| GET | `/users/{id}` | autenticado |
| POST | `/tickets` | usuario |
| GET | `/tickets` | usuario (solo propios) |
| GET | `/tickets/summary` | soporte |
| GET | `/tickets/{id}` | lector |
| GET | `/tickets/{id}/history` | lector |
| PATCH | `/tickets/{id}/status` | soporte |
| PATCH | `/tickets/{id}/priority` | admin |
| PATCH | `/tickets/{id}/assignee` | soporte |
| POST | `/tickets/{id}/comments` | lector |
| GET | `/health`, `/health/db` | público |

Filtros en `GET /tickets`: `status`, `category`, `priority`, `requester_id`, `limit`, `offset`.

## 7. Datos y migraciones

### 7.1 Esquema

Tablas: `users`, `tickets`, `attachments`, `comments`, `history`, `categories`, `priorities`, `documentos_embeddings` (vector(1536)).

### 7.2 Seed

`seed.py` borra y recarga todo desde `data/seed/*.json` (6 usuarios, 13 tickets, 7 categorías, 4 prioridades, 5 adjuntos, 3 comentarios, 45 eventos). Password de todos los usuarios: `techsupport123`. Flush por etapas por las FKs string.

### 7.3 Migraciones

- `migrations/versions/`: `4f7693e83575_initial.py`, `c10c8b5597b8_add_user_password_hash.py`.
- `alembic.ini` tiene la URL vacía; `env.py` lee `settings.database_url`.
- Para agregar una migración: `docker compose exec backend alembic revision --autogenerate -m "..."` y **rebuild** del backend (el Dockerfile copia el código en build).

## 8. Gotchas y decisiones pendientes

- `psycopg[binary]` obligatorio (slim no trae libpq).
- `httpx` necesario para `TestClient`.
- `buscar_tickets_similares` (pgvector) **no implementado** — fase agente.
- Búsqueda de duplicados antes de crear ticket **no implementada** — fase agente.
- Ticket IDs `max+1` no son concurrency-safe (aceptado para demo).
- `AGENTS.md` e `instructions.md` son local-only (gitignored).
- Docstrings de `db.py`/`seed.py` citan `instructions.md §13.6/§14`, secciones que ya no existen.

## 9. Próximos pasos

- **Fase agente:** integrar LangChain/ADK, prompts, multimodal, embeddings y `buscar_tickets_similares`, endpoint de chat, duplicate check.
- **Frontend:** login y UI de tickets (hoy solo scaffold + health).
- **Docs:** docstrings en servicios y metadata OpenAPI para `/docs`.
