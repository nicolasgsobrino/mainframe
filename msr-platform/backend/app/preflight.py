"""Validación end-to-end de sólo lectura de la PoC contra AWS.

    python -m app.preflight

Comprueba, sin mutar nada y sin iniciar ninguna Automation:

- identidad federada (`sts:GetCallerIdentity`): cuenta, región, rol y que las
  credenciales son temporales y no hay claves estáticas;
- `MSR_DRY_RUN=true` y modo de ejecución;
- alcanzabilidad de la tabla de locks (`dynamodb:GetItem` sobre la clave del
  laboratorio, que además revela si alguien tiene el lock);
- laboratorio: descubrimiento dinámico por tags, inscripción en SSM, y que la
  instancia esté vulnerable y sana (`ensure_lab_ready` con el reset prohibido).

Código de salida 0 si todas las comprobaciones pasan, 1 en cualquier otro caso.
"""
from __future__ import annotations

import json
import sys

from .config import get_settings
from .errors import DomainError
from .identity_check import describe_identity
from .lab_locks import DynamoDbLabLockBackend
from .store import STORE


def _check(name: str, ok: bool, detail: dict) -> dict:
    return {"check": name, "ok": ok, **detail}


def check_identity() -> dict:
    identity = describe_identity()
    ok = bool(identity.get("usable") and identity.get("temporary")
              and not identity.get("static_credentials_present"))
    return _check("identity", ok, identity)


def check_safe_defaults() -> dict:
    settings = get_settings()
    detail = {
        "execution_mode": settings.execution_mode(),
        "dry_run": settings.dry_run,
        "reconcile_on_startup": settings.lab_reconcile_on_startup,
        "region": settings.aws_region,
    }
    return _check("safe_defaults", settings.dry_run and not settings.lab_reconcile_on_startup,
                  detail)


def check_lock_table() -> dict:
    """Lectura de la tabla de locks, incluso en dry-run (donde el lock es local)."""
    settings = get_settings()
    detail: dict = {"table": settings.lab_lock_table_name,
                    "active_backend": STORE.lab_locks.backend_name}
    if not settings.uses_aws():
        return _check("lock_table", False, {**detail, "error": "El provider no es AWS."})
    backend = DynamoDbLabLockBackend(settings.lab_lock_table_name, STORE.dynamodb_client)
    try:
        lock = backend.get(settings.lab_logical_id)
    except Exception as exc:  # noqa: BLE001 - cualquier fallo es "tabla inalcanzable"
        return _check("lock_table", False, {**detail, "error": f"{type(exc).__name__}: {exc}"})
    return _check("lock_table", True, {**detail, "reachable": True, "current_lock": lock})


def check_lab() -> dict:
    """Nunca resetea: `allow_reset=False` y sin confirmación."""
    try:
        result = STORE.lab_lifecycle.ensure_lab_ready(allow_reset=False, confirmed=False,
                                                      reason="preflight")
    except DomainError as exc:
        return _check("lab", False, {"error_code": exc.code, "error": exc.message})
    evidence = result.get("evidence") or {}
    ok = bool(result.get("ready"))
    return _check("lab", ok, {
        "ready": result.get("ready"),
        "action": result.get("action"),
        "account_id": result.get("account_id"),
        "region": result.get("region"),
        "autoscaling_group_name": result.get("autoscaling_group_name"),
        "instance_id": result.get("instance_id"),
        "dry_run": result.get("dry_run"),
        "ssm_state": evidence.get("ssm_state"),
        "vulnerable_state": evidence.get("vulnerable_state"),
        "health_state": evidence.get("health_state"),
        "current_kernel": evidence.get("current_kernel"),
        "error_code": result.get("error_code"),
        "error": result.get("error") or result.get("detail"),
    })


def run_preflight() -> dict:
    checks = [check_identity(), check_safe_defaults(), check_lock_table(), check_lab()]
    return {"ok": all(check["ok"] for check in checks), "checks": checks}


def main() -> int:
    report = run_preflight()
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
