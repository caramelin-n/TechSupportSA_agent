"""Configuración tipada desde variables de entorno."""
from __future__ import annotations

from pathlib import Path

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
