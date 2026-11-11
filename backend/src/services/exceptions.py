"""Excepciones de dominio mapeadas a HTTP en la capa API."""
from __future__ import annotations


class DomainError(Exception):
    status_code: int = 400


class NotFound(DomainError):
    status_code = 404


class Forbidden(DomainError):
    status_code = 403


class InvalidTransition(DomainError):
    status_code = 409


class ValidationError(DomainError):
    status_code = 422


class Unauthorized(DomainError):
    status_code = 401
