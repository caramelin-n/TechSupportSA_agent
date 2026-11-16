"""Endpoints de catálogos: categorías y prioridades válidas."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.deps import get_current_user, get_db
from src.models import Category, Priority
from src.schemas.catalog import CategoryResponse, PriorityResponse

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/categories", response_model=list[CategoryResponse])
def list_categories(
    current_user=Depends(get_current_user), db: Session = Depends(get_db)
):
    """Categorías cargadas en la base (las usa el alta de tickets)."""
    return list(db.execute(select(Category).order_by(Category.name)).scalars())


@router.get("/priorities", response_model=list[PriorityResponse])
def list_priorities(
    current_user=Depends(get_current_user), db: Session = Depends(get_db)
):
    """Prioridades cargadas en la base."""
    return list(db.execute(select(Priority).order_by(Priority.name)).scalars())
