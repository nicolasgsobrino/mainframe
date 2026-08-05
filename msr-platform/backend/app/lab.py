"""Modelo persistente del laboratorio reutilizable de la PoC.

Distinción importante:

- `rollback`  → recuperación de una ejecución de parcheo fallida sobre la
  instancia actual (no recrea nada).
- `reset_lab` → recreación deliberada de la instancia vulnerable para volver a
  repetir la PoC desde cero.

El Instance ID nunca se fija en la CMDB: se resuelve por tags (`labs.py`) y se
actualiza aquí cada vez que un reset recrea la instancia.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .providers.base import (
    RESTORE_KIND_RESET_LAB,
    RESTORE_KIND_ROLLBACK,
    iso_utc,
    synthetic_instance_id,
    utcnow,
)

RESTORE_KINDS = (RESTORE_KIND_ROLLBACK, RESTORE_KIND_RESET_LAB)

__all__ = ["LabTarget", "RESTORE_KINDS", "RESTORE_KIND_RESET_LAB",
           "RESTORE_KIND_ROLLBACK", "synthetic_instance_id"]


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
    # Grupo que mantiene viva la instancia: el reset la sustituye dentro de él.
    autoscaling_group_name: str | None = None
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
            "autoscaling_group_name": self.autoscaling_group_name,
            "expected_vulnerable_package": self.expected_vulnerable_package,
            "expected_vulnerable_version": self.expected_vulnerable_version,
            "required_tags": dict(self.required_tags or {}),
            "last_reset_job_id": self.last_reset_job_id,
            "updated_at": iso_utc(self.updated_at) if self.updated_at else None,
        }
