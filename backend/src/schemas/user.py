"""Schemas Pydantic — usuarios."""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class Role(str, Enum):
    USUARIO = "usuario"
    SOPORTE = "soporte"
    ADMIN = "admin"


class UserResponse(BaseModel):
    id: str
    name: str
    email: EmailStr
    role: Role
    area: str

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8)
    role: Role = Role.USUARIO
    area: str = Field(min_length=1, max_length=80)
