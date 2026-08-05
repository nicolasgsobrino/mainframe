"""Modelo persistente del laboratorio reutilizable de la PoC.

Distinción importante:

- `rollback`  → recuperación de una ejecución de parcheo fallida sobre la
  instancia actual (no recrea nada).
- `reset_lab` → recreación deliberada de la instancia vulnerable para volver a
  repetir la PoC desde cero.

Esta fase sólo modela y persiste el laboratorio: no se implementa ninguna
operación de destrucción o recreación real de EC2.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .providers.base import iso_utc, utcnow

RESTORE_KIND_ROLLBACK = "rollback"
RESTORE_KIND_RESET_LAB = "reset_lab"
RESTORE_KINDS = (RESTORE_KIND_ROLLBACK, RESTORE_KIND_RESET_LAB)


@dataclass(slots=True)
class LabTarget:
    """Instancia vulnerable reutilizable del laboratorio de la PoC."""

    logical_lab_id: str
    current_instance_id: str | None = None
    account_id: str | None = None
    region: str | None = None
    vulnerable_ami_id: str | None = None
    launch_template_id: str | None = None
    launch_template_version: str | None = None
    expected_vulnerable_package: str | None = None
    expected_vulnerable_version: str | None = None
    required_tags: dict[str, str] = field(default_factory=dict)
    last_reset_job_id: str | None = None
    updated_at: object = field(default_factory=utcnow)

    def as_dict(self) -> dict:
        return {
            "logical_lab_id": self.logical_lab_id,
            "current_instance_id": self.current_instance_id,
            "account_id": self.account_id,
            "region": self.region,
            "vulnerable_ami_id": self.vulnerable_ami_id,
            "launch_template_id": self.launch_template_id,
            "launch_template_version": self.launch_template_version,
            "expected_vulnerable_package": self.expected_vulnerable_package,
            "expected_vulnerable_version": self.expected_vulnerable_version,
            "required_tags": dict(self.required_tags or {}),
            "last_reset_job_id": self.last_reset_job_id,
            "updated_at": iso_utc(self.updated_at) if self.updated_at else None,
        }
