"""Schemas de catálogos (categorías y prioridades)."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class CategoryResponse(BaseModel):
    name: str
    description: Optional[str] = None
    examples: Optional[list] = None

    model_config = {"from_attributes": True}


class PriorityResponse(BaseModel):
    name: str
    definition: Optional[str] = None

    model_config = {"from_attributes": True}
