# TechSupport S.A.

Agente de tickets (CRUD + auth JWT hoy; RAG + function calling pendiente). La spec funcional completa está en `instructions.md` (local, gitignored).

## Arranque

```bash
cp .env.example .env
docker compose up --build
docker compose exec backend python seed.py
docker compose exec backend python -m pytest -q
```

Login demo: `raul.gimenez@techsupport-demo.com` / `techsupport123` (todos los usuarios comparten esa password).

Verificación: `curl localhost:8000/health` (backend), `curl localhost:8080/api/health` (nginx proxy).

## Frontend

SPA React (Vite + Tailwind) servida por nginx en `http://localhost:8080`.
El login vive en `/login`; hay botones de acceso rápido para los tres roles de la demo.

```bash
cd frontend
npm install
npm run dev     # dev server con proxy a la API en :8000
npm test        # vitest
npm run build   # genera dist/
```

## Documentación

- [docs/backend-overview.md](docs/backend-overview.md) — explicación de la arquitectura, auth, permisos, estados, endpoints y deploy.
- [docs/frontend-overview.md](docs/frontend-overview.md) — arquitectura del frontend, flujo de autenticación, proxy y tests.
- Detalles de desarrollo (dependencias, convenciones, gotchas) en `AGENTS.md` (local-only, gitignored).
