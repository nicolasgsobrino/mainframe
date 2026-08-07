"""Reconciliación del ciclo de vida del laboratorio (`ensure_lab_ready`).

Servicio deliberadamente separado del `JobReconciler`: éste vigila jobs
mutativos en vuelo; el `LabLifecycleManager` responde a una pregunta distinta y
puntual — «¿el laboratorio está listo para una nueva demostración de parcheo?».

Determinismo y política:

- La instancia se descubre **siempre** en AWS por tags (`msr-poc`, `msr-lab-id`);
  ni el Instance ID guardado en SQLite ni ninguno recibido del navegador
  sustituyen ese descubrimiento.
- Cuenta, región, tags, estado EC2, pertenencia al ASG y nodo SSM se validan
  antes de considerar la instancia utilizable.
- El estado vulnerable/parcheado sale de evidencia AWS de sólo lectura
  (`precheck.py`), nunca del histórico de jobs.
- Una instancia vulnerable y sana **no se recrea**.
- Sólo si ya está parcheada (o el advisory ya no aplica) se ejecuta
  `MSR-ResetLabInstance`, y el reemplazo debe tener un Instance ID distinto,
  estar `running`, `Online`, sano y volver a ser vulnerable.
- *Fail closed*: cualquier ambigüedad, ausencia de evidencia o fallo deja el
  laboratorio en `failed` sin más operaciones destructivas.
- En `aws-dry-run` la reconciliación lee y valida, pero nunca inicia una
  Automation: informa de la acción que ejecutaría.
"""
from __future__ import annotations

import logging
import os
import socket
import time
import uuid

from .config import Settings
from .errors import ConflictError, DomainError
from .jobs import JobState, PatchJob
from .lab import (
    LAB_STATE_UNKNOWN,
    LAB_STATE_VULNERABLE,
    RECONCILE_FAILED,
    RECONCILE_READY,
    RECONCILE_RESETTING,
    RECONCILE_RUNNING,
    RECONCILE_SKIPPED,
    LabTarget,
)
from .labs import ERROR_NOT_FOUND, LabInstance, LabResolutionError
from .policy import evaluate_target, sanitize_text
from .precheck import LabEvidence
from .providers.base import ProviderError, utcnow

logger = logging.getLogger("msr.lab.lifecycle")

ACTION_NONE = "none"
ACTION_RESET = "reset"

ERROR_LOCKED = "LAB_RECONCILE_LOCKED"
ERROR_EVIDENCE = "LAB_EVIDENCE_UNAVAILABLE"
ERROR_TARGET_INVALID = "LAB_TARGET_INVALID"
ERROR_RESET_FAILED = "LAB_RESET_FAILED"
ERROR_REPLACEMENT = "LAB_REPLACEMENT_NOT_READY"
ERROR_NOT_VULNERABLE = "LAB_REPLACEMENT_NOT_VULNERABLE"
ERROR_UNCHANGED = "LAB_REPLACEMENT_NOT_REPLACED"
ERROR_CONFIRMATION = "LAB_RESET_CONFIRMATION_REQUIRED"


class LabReconciliationError(DomainError):
    """La reconciliación no pudo dejar el laboratorio listo."""

    http_status = 409
    code = "LAB_NOT_READY"


def default_holder() -> str:
    """Identidad del proceso que toma el lock (réplica + pid)."""
    return f"{socket.gethostname()}:{os.getpid()}"


class LabLifecycleManager:
    """Reconciliador del laboratorio AWS. No arranca nada por sí solo."""

    def __init__(self, store, sleep_fn=time.sleep, now_fn=utcnow,
                 monotonic_fn=time.monotonic, holder: str | None = None):
        self._store = store
        self._sleep = sleep_fn
        self._now = now_fn
        self._monotonic = monotonic_fn
        self._holder = holder or default_holder()
        self.last_result: dict | None = None

    # -- utilidades -----------------------------------------------------
    @property
    def settings(self) -> Settings:
        return self._store.settings

    @property
    def holder(self) -> str:
        return self._holder

    def _lab_id(self, logical_lab_id: str | None) -> str:
        return (logical_lab_id or self.settings.lab_logical_id or "").strip()

    def status(self, logical_lab_id: str | None = None) -> dict:
        """Estado observado del reconciliador, sin llamar a AWS."""
        lab_id = self._lab_id(logical_lab_id)
        lab = self._store.repo.get_lab_target(lab_id) if lab_id else None
        lock = self._store.repo.get_lab_lock(lab_id) if lab_id else None
        return {
            "logical_lab_id": lab_id,
            "execution_mode": self.settings.execution_mode(),
            "credentials_source": self.settings.credentials_source(),
            "reconcile_on_startup": bool(self.settings.lab_reconcile_on_startup),
            "holder": self._holder,
            "lock": lock,
            "reconciliation_state": lab.reconciliation_state if lab else None,
            "lab_state": lab.lab_state if lab else None,
            "current_instance_id": lab.current_instance_id if lab else None,
            "previous_instance_id": lab.previous_instance_id if lab else None,
            "last_reconciled_at": (lab.as_dict()["last_reconciled_at"] if lab else None),
            "last_reconciliation_error": lab.last_reconciliation_error if lab else None,
            "last_correlation_id": lab.last_correlation_id if lab else None,
            "last_result": self.last_result,
        }

    def record_observation(self, logical_lab_id: str, instance: LabInstance,
                           evidence: LabEvidence) -> None:
        """Persiste evidencia observada fuera de una reconciliación.

        Es el camino que usa la validación de sólo lectura: actualiza el estado
        operativo sin tocar el estado del reconciliador ni ejecutar nada.
        """
        lab_id = self._lab_id(logical_lab_id)
        if not lab_id:
            return
        lab = self._lab(lab_id)
        self._persist(lab_id, instance, evidence, correlation_id=lab.last_correlation_id or "",
                      state=lab.reconciliation_state, error=lab.last_reconciliation_error)

    # -- operación principal --------------------------------------------
    def ensure_lab_ready(self, logical_lab_id: str | None = None, *,
                         allow_reset: bool = True, confirmed: bool = False,
                         reason: str = "startup") -> dict:
        """Deja el laboratorio listo para una nueva demostración, o falla cerrado.

        `confirmed` sólo es relevante en `aws-real`: un reset destructivo lanzado
        desde la UI exige confirmación humana explícita.
        """
        lab_id = self._lab_id(logical_lab_id)
        if not lab_id:
            raise LabReconciliationError("No hay ningún laboratorio lógico configurado "
                                         "(MSR_LAB_LOGICAL_ID).", code=ERROR_TARGET_INVALID)
        correlation_id = f"lab-{uuid.uuid4().hex[:12]}"
        if not self._store.repo.acquire_lab_lock(
                lab_id, self._holder, correlation_id,
                self.settings.lab_reconcile_lock_ttl_seconds, reason=reason):
            held = self._store.repo.get_lab_lock(lab_id) or {}
            result = self._result(lab_id, RECONCILE_SKIPPED, ACTION_NONE,
                                  correlation_id=correlation_id, error_code=ERROR_LOCKED,
                                  error=("Otra réplica ya está reconciliando el laboratorio "
                                         f"(holder {held.get('holder') or 'desconocido'})."))
            self.last_result = result
            return result
        try:
            return self._reconcile(lab_id, correlation_id, allow_reset=allow_reset,
                                   confirmed=confirmed, reason=reason)
        finally:
            self._store.repo.release_lab_lock(lab_id, self._holder)

    # -- pasos ----------------------------------------------------------
    def _reconcile(self, lab_id: str, correlation_id: str, *, allow_reset: bool,
                   confirmed: bool, reason: str) -> dict:
        self._mark(lab_id, RECONCILE_RUNNING, correlation_id=correlation_id, error=None)
        try:
            instance = self._usable_instance(lab_id)
        except LabResolutionError as exc:
            return self._fail(lab_id, correlation_id, exc.code, exc.message)
        except ProviderError as exc:
            return self._fail(lab_id, correlation_id, exc.code, exc.message)

        evidence = self._store.lab_precheck.inspect(instance)
        self._persist(lab_id, instance, evidence, correlation_id=correlation_id,
                      state=RECONCILE_RUNNING)

        if evidence.ready:
            logger.info("Laboratorio %s ya listo en %s (vulnerable y sano): no se recrea.",
                        lab_id, instance.instance_id)
            return self._ready(lab_id, instance, evidence, correlation_id, ACTION_NONE)

        if evidence.vulnerable_state == LAB_STATE_UNKNOWN:
            return self._fail(lab_id, correlation_id, ERROR_EVIDENCE,
                              "AWS no aporta evidencia suficiente del estado del laboratorio: "
                              "no se ejecuta ninguna operación destructiva. "
                              f"{evidence.detail}", instance=instance, evidence=evidence)
        if evidence.vulnerable_state == LAB_STATE_VULNERABLE:
            # Vulnerable pero no sano/gestionado: recrear no es la respuesta.
            return self._fail(lab_id, correlation_id, ERROR_TARGET_INVALID,
                              "La instancia es vulnerable pero no está sana o gestionada por "
                              f"SSM (salud={evidence.health_state}, SSM={evidence.ssm_state}).",
                              instance=instance, evidence=evidence)
        if not allow_reset:
            return self._skipped(lab_id, instance, evidence, correlation_id, ACTION_RESET,
                                 "El laboratorio está parcheado y el reset no está autorizado "
                                 "en esta invocación.")
        if self.settings.real_aws_execution() and not confirmed:
            return self._skipped(lab_id, instance, evidence, correlation_id, ACTION_RESET,
                                 "Reset real no ejecutado: requiere confirmación humana "
                                 "explícita.", error_code=ERROR_CONFIRMATION)
        if not self.settings.real_aws_execution() and self.settings.uses_aws():
            return self._skipped(lab_id, instance, evidence, correlation_id, ACTION_RESET,
                                 "aws-dry-run: se ejecutaría MSR-ResetLabInstance sobre "
                                 f"{instance.instance_id} en el ASG "
                                 f"{self.settings.lab_autoscaling_group_name or '-'}; "
                                 "no se inicia ninguna Automation.")
        return self._reset(lab_id, instance, correlation_id, reason)

    def _usable_instance(self, lab_id: str) -> LabInstance:
        """Instancia del laboratorio descubierta en AWS y validada.

        Si el ASG debería tener una instancia y todavía no hay ninguna (o está en
        transición), se espera al reemplazo: nunca se crea una EC2 fuera del ASG.
        """
        instance = self._wait_for_instance(lab_id)
        self._validate(instance)
        return instance

    def _wait_for_instance(self, lab_id: str, *, exclude: str | None = None) -> LabInstance:
        deadline = self._monotonic() + max(1, self.settings.lab_replacement_timeout_seconds)
        interval = max(1, self.settings.lab_reconcile_poll_interval_seconds)
        last: LabResolutionError | None = None
        while True:
            try:
                instance = self._store.lab_resolver.resolve(lab_id)
            except LabResolutionError as exc:
                if exc.code != ERROR_NOT_FOUND:
                    raise
                last = exc
                instance = None
            if instance is not None:
                different = exclude is None or instance.instance_id != exclude
                if different and instance.state == "running" and instance.ssm_managed:
                    return instance
                if not different:
                    last = LabResolutionError(
                        ERROR_UNCHANGED,
                        "El Auto Scaling Group sigue devolviendo la misma instancia "
                        f"{instance.instance_id} después del reset.")
                else:
                    last = LabResolutionError(
                        ERROR_REPLACEMENT,
                        f"La instancia {instance.instance_id} todavía no está lista "
                        f"(estado EC2 {instance.state}, SSM "
                        f"{instance.ping_status or 'desconocido'}).")
            if self._monotonic() >= deadline:
                raise last or LabResolutionError(
                    ERROR_REPLACEMENT,
                    "El Auto Scaling Group no ha proporcionado ninguna instancia utilizable "
                    "en el plazo permitido.")
            self._sleep(interval)

    def _validate(self, instance: LabInstance) -> None:
        """Cuenta, región, tags, estado, ASG y SSM. Cualquier fallo aborta."""
        allowed_accounts = self.settings.allowed_account_ids
        if allowed_accounts and (instance.account_id or "") not in allowed_accounts:
            raise LabResolutionError(
                "LAB_TARGET_ACCOUNT_MISMATCH",
                f"La instancia {instance.instance_id} pertenece a la cuenta "
                f"{instance.account_id or 'desconocida'}, fuera de la allowlist "
                f"({', '.join(allowed_accounts)}).")
        allowed_regions = self.settings.allowed_regions
        if allowed_regions and (instance.region or "") not in allowed_regions:
            raise LabResolutionError(
                "LAB_TARGET_REGION_MISMATCH",
                f"La instancia {instance.instance_id} está en la región "
                f"{instance.region or 'desconocida'}, fuera de la allowlist "
                f"({', '.join(allowed_regions)}).")
        policy = evaluate_target(
            instance.as_target(self.settings.lab_environment), self.settings,
            instance_state=instance.state, require_instance=True,
            strict=self.settings.real_aws_execution())
        if not policy.allowed:
            raise LabResolutionError(policy.error_code or ERROR_TARGET_INVALID, policy.message)
        if instance.state != "running":
            raise LabResolutionError(
                ERROR_REPLACEMENT,
                f"La instancia {instance.instance_id} no está en ejecución "
                f"(estado {instance.state}).")
        if not instance.ssm_managed:
            raise LabResolutionError(
                "LAB_TARGET_SSM_OFFLINE",
                f"La instancia {instance.instance_id} no es un nodo gestionado Online "
                f"(PingStatus {instance.ping_status or 'desconocido'}).")

    def _reset(self, lab_id: str, instance: LabInstance, correlation_id: str,
               reason: str) -> dict:
        previous = instance.instance_id
        self._mark(lab_id, RECONCILE_RESETTING, correlation_id=correlation_id, error=None)
        logger.info("Laboratorio %s parcheado: se recrea %s mediante Automation (%s).",
                    lab_id, previous, reason)
        try:
            job = self._store.start_lab_reset_job(
                lab_id, correlation_id=correlation_id, trigger=f"lab_reconcile:{reason}")
        except ConflictError as exc:
            return self._fail(lab_id, correlation_id, ERROR_RESET_FAILED, exc.message)
        except DomainError as exc:
            return self._fail(lab_id, correlation_id, exc.code or ERROR_RESET_FAILED,
                              exc.message)
        job = self._await_job(job)
        if job.state is not JobState.RESTORED:
            return self._fail(
                lab_id, correlation_id, ERROR_RESET_FAILED,
                f"La Automation de reset terminó en estado {job.state.value} "
                f"({job.error_code or 'sin código'}): "
                f"{sanitize_text(job.error_message or '-', 300)}.")

        try:
            replacement = self._wait_for_instance(lab_id, exclude=previous)
            self._validate(replacement)
        except LabResolutionError as exc:
            return self._fail(lab_id, correlation_id, exc.code, exc.message)
        except ProviderError as exc:
            return self._fail(lab_id, correlation_id, exc.code, exc.message)

        evidence = self._store.lab_precheck.inspect(replacement)
        if not evidence.ready:
            return self._fail(
                lab_id, correlation_id, ERROR_NOT_VULNERABLE,
                f"El reemplazo {replacement.instance_id} no cumple la línea base del "
                f"laboratorio (estado={evidence.vulnerable_state}, "
                f"salud={evidence.health_state}, SSM={evidence.ssm_state}).",
                instance=replacement, evidence=evidence)
        return self._ready(lab_id, replacement, evidence, correlation_id, ACTION_RESET,
                           previous_instance_id=previous,
                           reset_execution_id=job.provider_reference, reset_job_id=job.id)

    def _await_job(self, job: PatchJob) -> PatchJob:
        """Espera el estado terminal del job de reset reconciliándolo con AWS."""
        deadline = self._monotonic() + max(1, self.settings.lab_reconcile_timeout_seconds)
        interval = max(1, self.settings.lab_reconcile_poll_interval_seconds)
        while not job.terminal:
            if self._monotonic() >= deadline:
                return job
            self._sleep(interval)
            job = self._store.reconcile_job(job)
        return job

    # -- persistencia y resultados ---------------------------------------
    def _lab(self, lab_id: str) -> LabTarget:
        lab = self._store.repo.get_lab_target(lab_id)
        if lab is None:
            lab = LabTarget(logical_lab_id=lab_id,
                            autoscaling_group_name=self.settings.lab_autoscaling_group_name or None,
                            candidate_releasever=self.settings.patch_releasever or None,
                            expected_fixed_kernel=self.settings.patch_expected_fixed_kernel or None)
        return lab

    def _mark(self, lab_id: str, state: str, *, correlation_id: str,
              error: str | None) -> LabTarget:
        lab = self._lab(lab_id)
        lab.reconciliation_state = state
        lab.last_correlation_id = correlation_id
        lab.last_reconciliation_error = error
        lab.last_reconciled_at = self._now()
        return self._store.repo.upsert_lab_target(lab)

    def _persist(self, lab_id: str, instance: LabInstance | None, evidence: LabEvidence | None,
                 *, correlation_id: str, state: str, error: str | None = None,
                 previous_instance_id: str | None = None,
                 reset_execution_id: str | None = None,
                 reset_job_id: str | None = None) -> LabTarget:
        lab = self._lab(lab_id)
        if instance is not None:
            if previous_instance_id and previous_instance_id != instance.instance_id:
                lab.previous_instance_id = previous_instance_id
            lab.current_instance_id = instance.instance_id
            lab.account_id = instance.account_id or lab.account_id
            lab.region = instance.region or lab.region
            lab.vulnerable_ami_id = instance.image_id or lab.vulnerable_ami_id
            lab.ssm_state = instance.ping_status or lab.ssm_state
        if evidence is not None:
            lab.lab_state = evidence.vulnerable_state
            lab.current_kernel = evidence.current_kernel
            lab.advisory_applicable = evidence.advisory_applicable
            lab.health_state = evidence.health_state
            lab.ssm_state = evidence.ssm_state or lab.ssm_state
            lab.evidence_source = evidence.source
            lab.expected_fixed_kernel = (evidence.expected_fixed_kernel
                                         or lab.expected_fixed_kernel)
        if reset_execution_id:
            lab.last_reset_execution_id = reset_execution_id
        if reset_job_id:
            lab.last_reset_job_id = reset_job_id
        lab.reconciliation_state = state
        lab.last_correlation_id = correlation_id
        lab.last_reconciliation_error = error
        lab.last_reconciled_at = self._now()
        return self._store.repo.upsert_lab_target(lab)

    def _result(self, lab_id: str, state: str, action: str, *, correlation_id: str,
                instance: LabInstance | None = None, evidence: LabEvidence | None = None,
                previous_instance_id: str | None = None, error_code: str | None = None,
                error: str | None = None, detail: str = "") -> dict:
        return {
            "logical_lab_id": lab_id,
            "state": state,
            "action": action,
            "ready": state == RECONCILE_READY,
            "execution_mode": self.settings.execution_mode(),
            "dry_run": self.settings.effective_dry_run(self._store.restore_provider.name),
            "account_id": instance.account_id if instance else None,
            "region": self.settings.aws_region or None,
            "autoscaling_group_name": self.settings.lab_autoscaling_group_name or None,
            "instance_id": instance.instance_id if instance else None,
            "previous_instance_id": previous_instance_id,
            "evidence": evidence.as_dict() if evidence else None,
            "correlation_id": correlation_id,
            "error_code": error_code,
            "error": error,
            "detail": detail,
            "holder": self._holder,
            "observed_at": self._now().isoformat(),
        }

    def _ready(self, lab_id: str, instance: LabInstance, evidence: LabEvidence,
               correlation_id: str, action: str, *, previous_instance_id: str | None = None,
               reset_execution_id: str | None = None,
               reset_job_id: str | None = None) -> dict:
        self._persist(lab_id, instance, evidence, correlation_id=correlation_id,
                      state=RECONCILE_READY, previous_instance_id=previous_instance_id,
                      reset_execution_id=reset_execution_id, reset_job_id=reset_job_id)
        result = self._result(lab_id, RECONCILE_READY, action, correlation_id=correlation_id,
                             instance=instance, evidence=evidence,
                             previous_instance_id=previous_instance_id,
                             detail=evidence.detail)
        self.last_result = result
        return result

    def _skipped(self, lab_id: str, instance: LabInstance, evidence: LabEvidence,
                 correlation_id: str, action: str, detail: str, *,
                 error_code: str | None = None) -> dict:
        self._persist(lab_id, instance, evidence, correlation_id=correlation_id,
                      state=RECONCILE_SKIPPED, error=detail if error_code else None)
        result = self._result(lab_id, RECONCILE_SKIPPED, action, correlation_id=correlation_id,
                             instance=instance, evidence=evidence, error_code=error_code,
                             error=detail if error_code else None, detail=detail)
        self.last_result = result
        return result

    def _fail(self, lab_id: str, correlation_id: str, code: str, message: str, *,
              instance: LabInstance | None = None,
              evidence: LabEvidence | None = None) -> dict:
        self._persist(lab_id, instance, evidence, correlation_id=correlation_id,
                      state=RECONCILE_FAILED, error=f"[{code}] {message}")
        logger.error("Reconciliación del laboratorio %s fallida: [%s] %s", lab_id, code, message)
        result = self._result(lab_id, RECONCILE_FAILED, ACTION_NONE,
                              correlation_id=correlation_id, instance=instance,
                              evidence=evidence, error_code=code, error=message)
        self.last_result = result
        return result


__all__ = ["LabLifecycleManager", "LabReconciliationError", "ACTION_NONE", "ACTION_RESET",
           "ERROR_CONFIRMATION", "ERROR_EVIDENCE", "ERROR_LOCKED",
           "ERROR_NOT_VULNERABLE", "ERROR_REPLACEMENT", "ERROR_RESET_FAILED",
           "ERROR_TARGET_INVALID", "ERROR_UNCHANGED", "default_holder"]
