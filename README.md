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

## Documentación

- [docs/backend-overview.md](docs/backend-overview.md) — explicación de la arquitectura, auth, permisos, estados, endpoints y deploy.
- Detalles de desarrollo (dependencias, convenciones, gotchas) en `AGENTS.md` (local-only, gitignored).
