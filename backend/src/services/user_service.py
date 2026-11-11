"""Lógica de usuarios y autenticación."""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.core.security import hash_password, verify_password
from src.models import User
from src.schemas.user import UserCreate
from src.services.exceptions import NotFound, Unauthorized


def get_user(session: Session, user_id: str) -> User:
    u = session.get(User, user_id)
    if u is None:
        raise NotFound(f"Usuario {user_id} no encontrado")
    return u


def list_users(session: Session) -> list[User]:
    return list(session.query(User).order_by(User.id).all())


def authenticate(session: Session, email: str, password: str) -> User:
    u = session.query(User).filter(User.email == email).first()
    if u is None or not verify_password(password, u.password_hash):
        raise Unauthorized("Credenciales inválidas")
    return u


def create_user(session: Session, data: UserCreate) -> User:
    if session.query(User).filter(User.email == data.email).first() is not None:
        raise ValueError("El email ya está registrado")
    u = User(
        id=_next_user_id(session),
        name=data.name,
        email=data.email,
        password_hash=hash_password(data.password),
        role=data.role.value,
        area=data.area,
    )
    session.add(u)
    session.commit()
    session.refresh(u)
    return u


def _next_user_id(session: Session) -> str:
    # ponytail: max+1; suficiente para la demo.
    last = session.query(User.id).order_by(User.id.desc()).first()
    n = 0
    if last:
        try:
            n = int(last[0].lstrip("UAS").lstrip("0") or "0")
        except ValueError:
            n = 0
    return f"U{n + 1:03d}"
