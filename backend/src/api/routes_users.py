"""Endpoints de usuarios."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.deps import get_current_user, get_db, require_roles
from src.schemas.user import UserResponse
from src.services.exceptions import DomainError
from src.services.user_service import get_user, list_users

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserResponse])
def list_all(current_user=Depends(require_roles("soporte", "admin")), db: Session = Depends(get_db)):
    return list_users(db)


@router.get("/{user_id}", response_model=UserResponse)
def get_one(user_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        return get_user(db, user_id)
    except DomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
