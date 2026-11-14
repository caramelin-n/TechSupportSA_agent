# Backend — TechSupport S.A.

> Documento de **explicación** (Diátaxis): describe cómo está armado el backend, por qué se tomaron ciertas decisiones y qué queda pendiente. No es un tutorial paso a paso ni la referencia exhaustiva de la API (eso está en `/docs` de FastAPI).

## 1. Visión general y alcance

### 1.1 Qué hace hoy

El backend expone una API REST para gestión de tickets de soporte con autenticación JWT y control de acceso por roles. Está **completo en la fase CRUD/tools** y **tiene el agente conversacional (texto)**:

- Auth con email+password, emisión de JWT HS256.
- CRUD de tickets con filtros y paginación (`GET /tickets?unresolved=true` trae solo los que no están Resueltos ni Cerrados).
- Máquina de estados estricta.
- Comentarios e historial de eventos.
- Resumen de incidencias por estado/categoría/prioridad.
- Gestión de usuarios (lectura).
- Agente de chat (`POST /chat`) con function calling y memoria entre turnos.

**Pendiente (frontend):** la UI es solo un scaffold que consulta `/api/health`.

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

- IDs: `TCK-####` desde la secuencia `ticket_number_seq` (numérica y segura ante creaciones simultáneas; `seed.py` la sincroniza con el ticket más alto). Al buscar, `1001`, `tck 1001`, `TCK1001` y `#1001` equivalen a `TCK-1001`.
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

- Transición inválida → `409 Conflict` (`InvalidTransition`); el mensaje dice a qué estados se puede pasar desde el actual. El prompt le indica al agente no recorrer estados intermedios por su cuenta: explica y pregunta.
- `Cerrado` solo por `admin` → `403` si no.
- Cambio de estado por `usuario` → `403` (solo soporte/admin).

### 5.3 Otros cambios

- **Prioridad** (`PATCH /tickets/{id}/priority`): soporte o admin (la consigna pide que soporte pueda revisar las prioridades propuestas); genera `PRIORITY_CHANGED`.
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
| PATCH | `/tickets/{id}/priority` | soporte, admin |
| PATCH | `/tickets/{id}/assignee` | soporte |
| POST | `/tickets/{id}/comments` | lector |
| POST | `/chat/upload` | autenticado |
| POST | `/chat` | autenticado |
| POST | `/chat/{conversation_id}/decision` | autenticado (solo su conversación) |
| GET | `/health`, `/health/db` | público |

Filtros en `GET /tickets`: `status`, `category`, `priority`, `requester_id`, `limit`, `offset`.

### 6.1 Agente (`POST /chat`)

Endpoint de chat con memoria conversacional. Recibe
`{"message": str, "conversation_id": str | null}` y devuelve
`{"reply": str, "conversation_id": str, "pending_actions": [...]}`. Si no se
envía `conversation_id`, se genera uno y se devuelve para continuar la
conversación.

Flujo:

1. `get_current_user` autentica por JWT.
2. `run_agent(user_id, conversation_id, message)` invoca el agente.
3. El agente (`create_agent` de LangChain 1.x sobre LangGraph) elige tools.
4. Cada tool recibe `ToolRuntime[AgentContext]` con el `user_id` real, abre su
   propia sesión y llama a `ticket_service`. Los permisos siguen vigentes.
5. La memoria vive en Postgres (`AsyncPostgresSaver`, ver
   `src/agent/checkpointer.py`) con `thread_id = "{user_id}:{conversation_id}"`,
   así que sobrevive a reinicios del contenedor. El pool se abre en el
   `lifespan` de FastAPI. Con `CHECKPOINTER=memory` usa memoria (solo pruebas).

#### Confirmaciones (human in the loop)

`crear_ticket`, `actualizar_estado`, `actualizar_prioridad` y `asignar_ticket`
**no se ejecutan cuando el modelo las pide**: `HumanInTheLoopMiddleware` pausa
el grafo y la respuesta trae la acción en `pending_actions`:

```json
{
  "reply": "Antes de seguir necesito que confirmes:\n- Crear el ticket «...»",
  "conversation_id": "demo-1",
  "pending_actions": [
    {"tool": "crear_ticket", "args": {"title": "...", "category": "Hardware", "priority": "Media", "description": "..."},
     "description": "Crear el ticket «...» (categoría Hardware, prioridad Media)"}
  ]
}
```

El cliente responde con `POST /chat/{conversation_id}/decision`:

- `{"decision": "approve"}` → se ejecuta la herramienta y el agente responde.
- `{"decision": "reject", "message": "opcional"}` → no se ejecuta; el modelo
  recibe el motivo y puede proponer otra cosa.

La decisión aplica a todas las acciones pendientes del turno. Mientras haya una
acción pendiente, `POST /chat` en esa conversación devuelve **409**; también
devuelve 409 una decisión sin nada pendiente. Solo se permiten `approve` y
`reject` (no `edit`), así el cliente no puede cambiar los argumentos. Aprobar
no saltea permisos: la herramienta sigue validando el rol del usuario.

La confirmación la impone el código, no el prompt: el prompt le indica al
modelo que no pida confirmación por texto para evitar la doble pregunta.

Herramientas expuestas: `crear_ticket`, `consultar_ticket`, `buscar_tickets`,
`actualizar_estado`, `actualizar_prioridad`, `asignar_ticket`,
`buscar_tickets_similares`, `agregar_comentario`, `adjuntar_archivo`,
`consultar_historial`, `resumen_incidencias`, `listar_usuarios`.

Errores de dominio y de validación se devuelven como `"Error: ..."` para que el
LLM los explique; nunca se propaga una excepción al modelo.

### 6.2 Adjuntos (F02)

El archivo llega **antes** de que exista el ticket, así que el flujo tiene dos
pasos:

1. `POST /chat/upload` (multipart, campo `files`, hasta 5 archivos) valida y
   guarda cada archivo y devuelve `[{"id", "filename", "kind", "size_bytes"}]`.
2. `POST /chat` con `{"message": "...", "upload_ids": [id, ...]}` manda el
   mensaje y los archivos al agente.

```bash
curl -s -X POST localhost:8000/chat/upload -H "Authorization: Bearer $TOKEN" \
  -F files=@backend/data/samples/captura_acceso_denegado.png \
  -F files=@backend/data/samples/app_facturacion.log
curl -s -X POST localhost:8000/chat -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"message":"No puedo entrar a facturación","upload_ids":[1,2]}'
```

**Validación** (`services/upload_service.py`): se aceptan PNG, JPG y WEBP
(decididos por el contenido, no por la extensión, y verificados con Pillow) y
TXT/LOG (por extensión, rechazando contenido binario). Máximo
`MAX_UPLOAD_MB` (5 por defecto). El archivo se guarda en
`UPLOAD_DIR/{user_id}/{uuid}.ext`; el nombre original queda en la tabla
`uploads`. Errores de validación → 422. Un id ajeno o inexistente → 404 (no
se distingue, para no revelar qué ids existen). Si el archivo ya no está en
disco → 410.

**Qué ve el modelo** (`agent/multimodal.py`, sin LLM, testeable): el mensaje
y, por cada adjunto, un encabezado `[Adjunto #id: nombre (tipo) — nota]`
seguido de:

- imagen: bloque `image` en base64, achicada a 1568 px de lado si hace falta
  (y rotada según EXIF);
- TXT/LOG de hasta 250 líneas y 15 000 caracteres: completo; en los LOG, la
  nota cuenta las líneas de error y de advertencia ("sin errores; 1
  advertencia(s) WARN"), para que el modelo no tome una advertencia aislada
  como incidencia;
- LOG más largo: solo las líneas con ERROR/WARN/FATAL/excepciones y 2 de
  contexto (tope 200); si no hay ninguna, las primeras y últimas 40, con una
  nota que lo aclara para que el modelo no invente un error.

**En el ticket**: `crear_ticket` recibe `adjuntos: [{upload_id, resumen}]` y
`adjuntar_archivo(ticket_id, upload_id, resumen)` suma uno a un ticket
existente (mismo permiso que comentar). Ambas validan que el upload sea del
usuario, lo copian a `attachments` con el resumen del análisis y registran
`FILE_ATTACHED` en el historial. La descripción de la confirmación de
`crear_ticket` indica cuántos adjuntos lleva.

### 6.3 Tickets duplicados (criterio 10)

Cada ticket tiene un vector en `ticket_embeddings` (título + categoría +
descripción, `gemini-embedding-001` a 1536 dimensiones, índice HNSW coseno).
Dos tickets que describen la misma incidencia con otras palabras quedan cerca.

- **`buscar_tickets_similares(descripcion)`**: herramienta de consulta (sin
  confirmación) que el prompt indica usar antes de crear. Devuelve hasta 3
  tickets con su porcentaje de parecido.
- **Chequeo dentro de `crear_ticket`** (impuesto por código): antes de crear,
  busca tickets parecidos. Si hay alguno a distancia ≤
  `DUPLICATE_MAX_DISTANCE`, **no crea nada** y devuelve los candidatos para que
  el modelo pregunte. Si el usuario dice que es otra incidencia, el modelo
  vuelve a llamar con `confirmar_duplicado=true`, y la confirmación se lo
  muestra al usuario («Se parece a un ticket existente, pero indicaste que es
  otra incidencia»).
- Solo se comparan tickets **no resueltos ni cerrados** y que el usuario puede
  ver (un usuario, contra los suyos; soporte y admin, contra todos).
- Si la API de embeddings falla o no hay `GOOGLE_API_KEY`, el ticket se crea
  igual y la respuesta avisa que no se pudo verificar duplicados.

Los tickets del seed no tienen vector. Después de `seed.py` hay que indexarlos
(una llamada a la API cada 50 tickets):

```bash
docker compose exec backend python scripts/indexar_tickets.py
docker compose exec backend python scripts/indexar_tickets.py --calibrar
```

`--calibrar` muestra, para cada ticket, su vecino más cercano y la distancia.
Con eso se ajusta `DUPLICATE_MAX_DISTANCE` (0.14 por defecto). Calibración con
`gemini-embedding-001` sobre el seed: los pares que son la misma incidencia
quedaron en 0.079 (TCK-1001/1007, facturación) y 0.120 (TCK-1006/1012,
backup); el primer par de problemas distintos, en 0.157. Con este modelo
todos los tickets de soporte quedan relativamente cerca entre sí (el más
lejano, a 0.26), así que el umbral tiene que ser ajustado: con 0.20 se
marcaban como duplicados tickets sin relación. Si se cambia
`EMBEDDING_MODEL`, hay que reindexar (`--todos`) y recalibrar.

En los tests, un embedder falso y determinista (`tests/conftest.py`) reemplaza
a Gemini, así que no se gasta cuota aunque haya `GOOGLE_API_KEY`.

## 7. Datos y migraciones

### 7.1 Esquema

Tablas: `users`, `tickets`, `ticket_embeddings` (vector(1536), HNSW), `attachments`, `uploads`, `comments`, `history`, `categories`, `priorities`, `documentos_embeddings` (vector(1536)).

### 7.2 Seed

`seed.py` borra y recarga todo desde `data/seed/*.json` (6 usuarios, 13 tickets, 7 categorías, 4 prioridades, 5 adjuntos, 3 comentarios, 45 eventos). Password de todos los usuarios: `techsupport123`. Flush por etapas por las FKs string.

### 7.3 Migraciones

- `migrations/versions/`: `4f7693e83575_initial.py`, `c10c8b5597b8_add_user_password_hash.py`, `8d0bc44accd2_add_named_unique_users_email.py`, `e543c2461f61_add_uploads.py`, `7f1eadfa70d3_add_ticket_embeddings.py`, `dd298544509b_ticket_number_sequence.py`.
- `alembic.ini` tiene la URL vacía; `env.py` lee `settings.database_url`.
- Para agregar una migración: `docker compose exec backend alembic revision --autogenerate -m "..."` y **rebuild** del backend (el Dockerfile copia el código en build).

## 8. Escenarios de prueba (criterio 12)

`backend/scripts/escenarios.py` corre conversaciones completas contra el
backend y el modelo real, como lo haría el frontend: sube archivos, manda
mensajes, aprueba o rechaza las confirmaciones y verifica el resultado
(qué respondió el agente y qué quedó en la base). Genera un informe en
Markdown con cada conversación y sus verificaciones, para la entrega.

```bash
# Recarga el seed, indexa los embeddings y corre los 13 escenarios
docker compose exec backend python scripts/escenarios.py --preparar
# Algunos, con pausa entre llamadas si aparecen límites de cuota
docker compose exec backend python scripts/escenarios.py --solo E02,E06 --pausa 5
```

`--preparar` **borra la base** y la recarga con el seed: los escenarios
asumen ese estado (por ejemplo, que TCK-1002 está Abierto). El informe queda
en `backend/informes/escenarios-FECHA.md` (ignorado por git: copiá el final a
`docs/` para la entrega). Termina con código 1 si algún escenario falla.

| ID | Escenario | Usuario | Requisitos | Qué verifica |
|---|---|---|---|---|
| E01 | Texto claro | Martín | F01, F03, F05–F07, F10 | Pide confirmación y crea 1 ticket Hardware |
| E02 | Captura legible | Martín | F02, F03, F07 | Lee `0x80070005`; ticket de Accesos con la captura adjunta |
| E03 | Captura borrosa | Lucía | F02, F04 | Pregunta; no intenta crear |
| E04 | Log largo | Carla | F02, F03, F07 | Identifica el timeout; ticket con el log adjunto |
| E05 | Log ambiguo | Martín | F02, F04 | Pregunta; no intenta crear |
| E06 | Duplicado | Lucía | Criterio 10 | Menciona TCK-1001/1007; no crea |
| E07 | Consultas | Lucía | F09 | Estado de «1001» y sus tickets abiertos |
| E08 | Consulta de soporte | Diego | F09 | Críticas sin resolver: TCK-1002 y TCK-1006 |
| E09 | Permisos | Lucía | F10, criterio 11 | Un usuario no puede cerrar: TCK-1004 sigue Pendiente |
| E10 | Transición inválida | Diego | F08, criterio 8 | Abierto → Resuelto no se aplica |
| E11 | Gestión e historial | Diego | F08, F10, F11, criterio 9 | Estado, asignación y comentario en el historial |
| E12 | Confirmación rechazada | Diego | F06, F10 | Rechazar deja la prioridad como estaba |
| E13 | Resumen | Raúl | F12 | Resumen por estado, categoría y prioridad |

Los escenarios que crean tickets tienen pasos de respaldo
(`si_no_propuso="crear_ticket"`): si el agente pide más datos antes de crear,
el script se los da. Los chequeos son tolerantes a la redacción del modelo
(buscan IDs, códigos de error o el estado final en la base), pero el modelo
no es determinista: si un escenario falla, el informe muestra la
conversación completa para ver por qué.

`tests/test_escenarios.py` prueba la mecánica del script con un agente falso,
sin gastar cuota.

## 9. Gotchas y decisiones pendientes

- `psycopg[binary]` obligatorio (slim no trae libpq).
- `httpx` necesario para `TestClient`.
- Las tablas `checkpoint*` las crea LangGraph (`setup()`), no Alembic; `migrations/env.py` las excluye del autogenerate.
- Las imágenes que se mandan al chat quedan guardadas en base64 dentro del checkpoint (además del archivo en `UPLOAD_DIR`).
- `uploads` no se limpia sola: los archivos que nunca se adjuntaron a un ticket quedan en disco.
- `seed.py` borra `uploads` antes que `users` (FK); los archivos en disco no.
- Al volver a correr `seed.py` se borran los vectores (`ON DELETE CASCADE`): hay que volver a correr `scripts/indexar_tickets.py`.
- `AGENTS.md` e `instructions.md` son local-only (gitignored).
- Docstrings de `db.py`/`seed.py` citan `instructions.md §13.6/§14`, secciones que ya no existen.

## 10. Próximos pasos

- **Frontend:** login y UI de tickets (hoy solo scaffold + health).
- **Docs:** docstrings en servicios y metadata OpenAPI para `/docs`.
