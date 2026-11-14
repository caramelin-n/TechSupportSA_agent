"""Configuración tipada desde variables de entorno."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    database_url: str
    secret_key: str
    access_token_expire_minutes: int = 60
    # Opcional: el CRUD funciona sin ella; solo el agente/RAG la requieren.
    google_api_key: str = ""
    # Modelo de chat del agente (multimodal y con function calling). Los 2.5
    # ya no están disponibles para claves nuevas. Los límites gratuitos por
    # modelo se ven en Google AI Studio.
    llm_model: str = "gemini-3.5-flash-lite"
    # Dónde guarda LangGraph las conversaciones (y las acciones pendientes de
    # confirmación). `postgres` persiste entre reinicios; `memory` solo sirve
    # para pruebas rápidas sin base.
    checkpointer: Literal["postgres", "memory"] = "postgres"
    # Archivos que los usuarios suben al chat (capturas, TXT, LOG).
    # En Docker queda en /app/uploads, montado como volumen.
    upload_dir: str = str(Path(__file__).resolve().parents[2] / "uploads")
    max_upload_mb: int = 5
    # Detección de duplicados (criterio 10). El modelo genera vectores de
    # 1536 dimensiones, el tamaño de la columna `ticket_embeddings.embedding`.
    embedding_model: str = "gemini-embedding-001"
    # Distancia coseno máxima (0 = idénticos, 1 = sin relación) para considerar
    # que dos tickets pueden ser la misma incidencia. Calibrala con
    # `python -m scripts.indexar_tickets --calibrar`.
    duplicate_max_distance: float = 0.14

    @property
    def checkpoint_db_url(self) -> str:
        """`DATABASE_URL` sin el driver de SQLAlchemy (`+psycopg`).

        psycopg acepta `postgresql://`, no `postgresql+psycopg://`.
        """
        return re.sub(r"^postgresql\+\w+://", "postgresql://", self.database_url)

    @field_validator("database_url")
    @classmethod
    def _validate_database_url(cls, value: str) -> str:
        if not value.startswith("postgresql"):
            raise ValueError("DATABASE_URL debe empezar con postgresql")
        return value

    @field_validator("secret_key")
    @classmethod
    def _validate_secret_key(cls, value: str) -> str:
        if len(value) < 16:
            raise ValueError("SECRET_KEY debe tener al menos 16 caracteres")
        return value


settings = Settings()
