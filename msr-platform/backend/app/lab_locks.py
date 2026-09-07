"""Lock de operación del laboratorio: exactamente una mutación a la vez.

En ECS Fargate el sistema de ficheros de cada task es efímero e independiente:
la task del servicio (patch/reset desde la UI) y la `RunTask` del hook de release
no comparten SQLite, así que un lock local no puede serializarlas. Con el
provider real el lock vive en DynamoDB —escritura condicional sobre un único
ítem por laboratorio— y lo respetan todos los procesos de la cuenta.

Reglas del lock, iguales en los dos backends:

- se adquiere si no hay ítem, si el existente ya caducó o si el dueño es el mismo
  (reentrada: la reconciliación propaga su `correlation_id` al reset que lanza);
- la caducidad se evalúa en la propia condición de escritura, de modo que un lock
  abandonado se reclama sin depender del borrado asíncrono del TTL de DynamoDB;
- sólo el dueño puede liberarlo;
- el TTL evita que la caída de un proceso bloquee el laboratorio para siempre.

En `mock` y `aws-dry-run` el lock sigue viviendo en SQLite: esos modos no mutan
nada en AWS y no deben exigir escrituras en DynamoDB.
"""
from __future__ import annotations

import logging
import os
import socket
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

from .config import Settings
from .errors import ConflictError

logger = logging.getLogger("msr.lab_locks")

OPERATION_PATCH = "patch"
OPERATION_RESET = "reset"
OPERATION_RECONCILE = "reconcile"

BACKEND_SQLITE = "sqlite"
BACKEND_DYNAMODB = "dynamodb"

ERROR_LAB_BUSY = "LAB_OPERATION_LOCKED"


class LabLockedError(ConflictError):
    """Otra operación mutativa ya tiene el laboratorio tomado."""

    code = ERROR_LAB_BUSY


class LabLockError(RuntimeError):
    """El lock no pudo evaluarse: fail-closed, no se muta el laboratorio."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class LabLock:
    """Ítem del lock tal y como lo ven la API y la UI."""

    lab_id: str
    owner: str
    holder: str
    operation: str
    acquired_at: str
    expires_at: str
    reason: str = ""

    def as_dict(self) -> dict:
        return {
            "logical_lab_id": self.lab_id,
            "lab_id": self.lab_id,
            "owner": self.owner,
            "correlation_id": self.owner,
            "holder": self.holder,
            "operation": self.operation,
            "acquired_at": self.acquired_at,
            "expires_at": self.expires_at,
            "reason": self.reason,
        }


class LabLockBackend(Protocol):
    """Contrato mínimo del lock. `acquire` nunca bloquea: devuelve o falla."""

    name: str

    def acquire(self, lab_id: str, owner: str, holder: str, operation: str,
                ttl_seconds: int, reason: str = "") -> bool: ...

    def release(self, lab_id: str, owner: str) -> bool: ...

    def get(self, lab_id: str) -> dict | None: ...


def default_holder() -> str:
    """Identidad diagnóstica del proceso que toma el lock (host/task + pid)."""
    return f"{socket.gethostname()}:{os.getpid()}"


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SqliteLabLockBackend:
    """Lock local, para `mock` y `aws-dry-run`: sin ninguna llamada a AWS."""

    name = BACKEND_SQLITE

    def __init__(self, repo):
        self._repo = repo

    def acquire(self, lab_id: str, owner: str, holder: str, operation: str,
                ttl_seconds: int, reason: str = "") -> bool:
        return self._repo.acquire_lab_lock(lab_id, owner, holder, operation,
                                           ttl_seconds, reason=reason)

    def release(self, lab_id: str, owner: str) -> bool:
        return self._repo.release_lab_lock(lab_id, owner)

    def get(self, lab_id: str) -> dict | None:
        return self._repo.get_lab_lock(lab_id)


class DynamoDbLabLockBackend:
    """Lock distribuido: un ítem por laboratorio y escrituras condicionales."""

    name = BACKEND_DYNAMODB

    def __init__(self, table_name: str, client_factory: Callable[[], object],
                 now_fn: Callable[[], datetime] = utcnow):
        self._table = table_name
        self._client_factory = client_factory
        self._now = now_fn

    @property
    def _client(self):
        client = self._client_factory()
        if client is None:
            raise LabLockError("LOCK_UNAVAILABLE",
                               "There is no DynamoDB client for the lab lock.")
        return client

    def acquire(self, lab_id: str, owner: str, holder: str, operation: str,
                ttl_seconds: int, reason: str = "") -> bool:
        now = self._now()
        expires = now + timedelta(seconds=max(1, ttl_seconds))
        item = {
            "lab_id": {"S": lab_id},
            "owner": {"S": owner},
            "holder": {"S": holder},
            "operation": {"S": operation},
            "reason": {"S": reason},
            "acquired_at": {"S": _iso(now)},
            # Epoch numérico: es el atributo de TTL de la tabla y permite
            # comparar la caducidad dentro de la propia condición.
            "expires_at": {"N": str(int(expires.timestamp()))},
            "expires_at_iso": {"S": _iso(expires)},
        }
        try:
            self._client.put_item(
                TableName=self._table,
                Item=item,
                ConditionExpression=("attribute_not_exists(lab_id) OR expires_at <= :now "
                                     "OR #owner = :owner"),
                # `owner` es palabra reservada de DynamoDB: sólo es utilizable
                # en una expresión a través de un alias.
                ExpressionAttributeNames={"#owner": "owner"},
                ExpressionAttributeValues={
                    ":now": {"N": str(int(now.timestamp()))},
                    ":owner": {"S": owner},
                },
            )
        except Exception as exc:
            if _is_conditional_failure(exc):
                return False
            raise self._as_lock_error(exc, "The lab lock could not be acquired.") from exc
        return True

    def release(self, lab_id: str, owner: str) -> bool:
        try:
            self._client.delete_item(
                TableName=self._table,
                Key={"lab_id": {"S": lab_id}},
                ConditionExpression="#owner = :owner",
                ExpressionAttributeNames={"#owner": "owner"},
                ExpressionAttributeValues={":owner": {"S": owner}},
            )
        except Exception as exc:
            if _is_conditional_failure(exc):
                # El lock ya no es nuestro (caducó y lo tomó otro): no se toca.
                return False
            raise self._as_lock_error(exc, "The lab lock could not be released.") from exc
        return True

    def get(self, lab_id: str) -> dict | None:
        try:
            response = self._client.get_item(TableName=self._table,
                                             Key={"lab_id": {"S": lab_id}},
                                             ConsistentRead=True)
        except Exception as exc:
            raise self._as_lock_error(exc, "The lab lock could not be read.") from exc
        item = response.get("Item") or {}
        if not item:
            return None
        expires_iso = (item.get("expires_at_iso") or {}).get("S") or ""
        lock = LabLock(
            lab_id=(item.get("lab_id") or {}).get("S") or lab_id,
            owner=(item.get("owner") or {}).get("S") or "",
            holder=(item.get("holder") or {}).get("S") or "",
            operation=(item.get("operation") or {}).get("S") or "",
            acquired_at=(item.get("acquired_at") or {}).get("S") or "",
            expires_at=expires_iso,
            reason=(item.get("reason") or {}).get("S") or "",
        )
        return lock.as_dict()

    @staticmethod
    def _as_lock_error(exc: Exception, message: str) -> LabLockError:
        from .providers.aws_ssm_automation import classify_error
        code, kind = classify_error(exc)
        return LabLockError(code, f"{message} ({kind})")


def _is_conditional_failure(exc: Exception) -> bool:
    """`ConditionalCheckFailedException` significa «el lock lo tiene otro»."""
    return type(exc).__name__ == "ConditionalCheckFailedException"


class LabLockManager:
    """Fachada del lock para el `Store`: adquiere, libera y expone su estado."""

    def __init__(self, settings: Settings, backend: LabLockBackend, holder: str):
        self._settings = settings
        self._backend = backend
        self._holder = holder

    @property
    def backend_name(self) -> str:
        return self._backend.name

    @property
    def holder(self) -> str:
        return self._holder

    def with_holder(self, holder: str) -> LabLockManager:
        """Misma tabla de locks vista por otro proceso (otra task o el hook)."""
        return LabLockManager(self._settings, self._backend, holder)

    def state(self, lab_id: str) -> dict | None:
        if not lab_id:
            return None
        return self._backend.get(lab_id)

    def acquire(self, lab_id: str, owner: str, operation: str, *,
                reason: str = "", ttl_seconds: int | None = None) -> bool:
        ttl = ttl_seconds or self._settings.lab_lock_ttl_seconds
        acquired = self._backend.acquire(lab_id, owner, self._holder, operation, ttl,
                                          reason=reason)
        if acquired:
            logger.info("Lab lock %s acquired by %s (%s, backend %s).",
                        lab_id, owner, operation, self._backend.name)
        return acquired

    def acquire_or_conflict(self, lab_id: str, owner: str, operation: str, *,
                            reason: str = "") -> None:
        """Adquiere el lock o levanta 409 describiendo quién lo tiene."""
        if self.acquire(lab_id, owner, operation, reason=reason):
            return
        held = self._backend.get(lab_id) or {}
        raise LabLockedError(
            f"Lab {lab_id} has a mutating operation in progress "
            f"({held.get('operation') or 'unknown'}, owner "
            f"{held.get('owner') or 'unknown'}): {operation} is not started.",
            correlation_id=str(held.get("owner") or ""))

    def release(self, lab_id: str, owner: str) -> bool:
        released = self._backend.release(lab_id, owner)
        if not released:
            logger.warning("Lab lock %s did not belong to %s: it is not released.",
                           lab_id, owner)
        return released


def get_lab_lock_backend(settings: Settings, repo,
                         dynamodb_client_factory: Callable[[], object],
                         now_fn: Callable[[], datetime] = utcnow) -> LabLockBackend:
    """Backend según el modo: DynamoDB sólo cuando la ejecución muta AWS."""
    choice = (settings.lab_lock_backend or "auto").strip().lower()
    if choice == BACKEND_SQLITE:
        return SqliteLabLockBackend(repo)
    if choice == BACKEND_DYNAMODB or (choice == "auto" and settings.real_aws_execution()
                                      and not settings.dry_run):
        return DynamoDbLabLockBackend(settings.lab_lock_table_name, dynamodb_client_factory,
                                       now_fn=now_fn)
    return SqliteLabLockBackend(repo)
