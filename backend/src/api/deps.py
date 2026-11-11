"""Dependencias FastAPI."""
from __future__ import annotations

from typing import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from src.core.security import decode_access_token
from src.db import SessionLocal
from src.models import User
from src.services.exceptions import DomainError
from src.services.user_service import get_user

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        subject = decode_access_token(token)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido o expirado")
    try:
        return get_user(db, subject)
    except DomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


def require_roles(*roles: str) -> Callable:
    def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Permisos insuficientes")
        return user

    return _dep
