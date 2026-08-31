"""Errores de dominio con código estable y mapeo a estados HTTP."""
from __future__ import annotations

import uuid


class DomainError(Exception):
    """Error de negocio con código estable, mensaje sanitizado y estado HTTP."""

    http_status = 400
    code = "DOMAIN_ERROR"

    def __init__(self, message: str, code: str | None = None, correlation_id: str | None = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        # Toda respuesta de error expone un correlation_id trazable en los logs.
        self.correlation_id = correlation_id or f"corr-{uuid.uuid4().hex[:16]}"

    def to_payload(self) -> dict:
        return {"error": {"code": self.code, "message": self.message,
                          "correlation_id": self.correlation_id}}


class NotFoundError(DomainError):
    http_status = 404
    code = "NOT_FOUND"


class ConflictError(DomainError):
    """Ya existe un job mutativo activo e incompatible (target o tarea ocupados)."""

    http_status = 409
    code = "JOB_ALREADY_ACTIVE"


class ValidationError(DomainError):
    """Objetivo o estado no válido para la operación solicitada."""

    http_status = 422
    code = "INVALID_STATE"


class TargetNotAllowedError(ValidationError):
    code = "TARGET_NOT_ALLOWED"


class DependencyUnavailableError(DomainError):
    """Configuración ausente o dependencia externa no disponible."""

    http_status = 503
    code = "DEPENDENCY_UNAVAILABLE"
