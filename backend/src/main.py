"""Entrypoint FastAPI — TechSupport S.A."""
from __future__ import annotations

from fastapi import FastAPI

from src.api.routes_auth import router as auth_router
from src.api.routes_chat import router as chat_router
from src.api.routes_health import router as health_router
from src.api.routes_tickets import router as tickets_router
from src.api.routes_users import router as users_router

app = FastAPI(title="TechSupport S.A. API")

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(tickets_router)
app.include_router(chat_router)
