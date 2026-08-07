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

# Estado operativo observado en AWS (nunca inferido del histórico de jobs).
LAB_STATE_UNKNOWN = "unknown"
LAB_STATE_VULNERABLE = "vulnerable"
LAB_STATE_PATCHED = "patched"

# Estado del reconciliador de laboratorio, independiente del de los jobs.
RECONCILE_IDLE = "idle"
RECONCILE_RUNNING = "running"
RECONCILE_READY = "ready"
RECONCILE_RESETTING = "resetting"
RECONCILE_FAILED = "failed"
RECONCILE_SKIPPED = "skipped"

__all__ = ["LabTarget", "RESTORE_KINDS", "RESTORE_KIND_RESET_LAB",
           "RESTORE_KIND_ROLLBACK", "synthetic_instance_id",
           "LAB_STATE_UNKNOWN", "LAB_STATE_VULNERABLE", "LAB_STATE_PATCHED",
           "RECONCILE_IDLE", "RECONCILE_RUNNING", "RECONCILE_READY",
           "RECONCILE_RESETTING", "RECONCILE_FAILED", "RECONCILE_SKIPPED"]


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
    # Release de Amazon Linux con la corrección (`dnf --releasever`) y kernel
    # mínimo esperado tras el parcheo. Ambos salen de la IaC, nunca de la API.
    candidate_releasever: str | None = None
    expected_fixed_kernel: str | None = None
    required_tags: dict[str, str] = field(default_factory=dict)
    last_reset_job_id: str | None = None
    # --- Estado operativo reconciliado con AWS (fase 2.6) ---------------
    previous_instance_id: str | None = None
    lab_state: str = LAB_STATE_UNKNOWN
    current_kernel: str | None = None
    advisory_applicable: bool | None = None
    ssm_state: str | None = None
    health_state: str | None = None
    evidence_source: str | None = None
    last_patch_job_id: str | None = None
    last_patch_execution_id: str | None = None
    last_reset_execution_id: str | None = None
    reconciliation_state: str = RECONCILE_IDLE
    last_reconciled_at: object = None
    last_reconciliation_error: str | None = None
    last_correlation_id: str | None = None
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
            "candidate_releasever": self.candidate_releasever,
            "expected_fixed_kernel": self.expected_fixed_kernel,
            "required_tags": dict(self.required_tags or {}),
            "last_reset_job_id": self.last_reset_job_id,
            "previous_instance_id": self.previous_instance_id,
            "lab_state": self.lab_state,
            "current_kernel": self.current_kernel,
            "advisory_applicable": self.advisory_applicable,
            "ssm_state": self.ssm_state,
            "health_state": self.health_state,
            "evidence_source": self.evidence_source,
            "last_patch_job_id": self.last_patch_job_id,
            "last_patch_execution_id": self.last_patch_execution_id,
            "last_reset_execution_id": self.last_reset_execution_id,
            "reconciliation_state": self.reconciliation_state,
            "last_reconciled_at": (iso_utc(self.last_reconciled_at)
                                   if self.last_reconciled_at else None),
            "last_reconciliation_error": self.last_reconciliation_error,
            "last_correlation_id": self.last_correlation_id,
            "updated_at": iso_utc(self.updated_at) if self.updated_at else None,
        }
