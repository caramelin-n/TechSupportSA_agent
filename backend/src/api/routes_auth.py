"""Endpoints de autenticación."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.deps import get_current_user, get_db
from src.core.security import create_access_token
from src.schemas.auth import LoginRequest, TokenResponse
from src.schemas.user import UserResponse
from src.services.exceptions import DomainError
from src.services.user_service import authenticate

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    try:
        user = authenticate(db, payload.email, payload.password)
    except DomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    return TokenResponse(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserResponse)
def me(current_user=Depends(get_current_user)):
    return current_user
