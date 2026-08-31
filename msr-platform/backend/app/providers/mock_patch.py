"""Provider de parcheo simulado (determinista) — el predeterminado de la demo.

Contiene la lógica de generación de acciones que antes vivía en
`engine.build_ring_actions()` (que ahora delega aquí para compatibilidad).

El mock cumple el mismo contrato que el provider de AWS: `start()` no bloquea y
la ejecución progresa entre llamadas sucesivas a `poll()` en función del tiempo
transcurrido, sin `sleep` ni workers.
"""
from __future__ import annotations

from datetime import datetime, timezone

from ..config import PROVIDER_MOCK, Settings
from .base import (
    ExecutionStatus,
    ExecutionStep,
    PatchExecution,
    PatchRequest,
    ProviderError,
    TargetPolicyResult,
    iso_utc,
    utcnow,
)

REFERENCE_PREFIX = "mock-patch"


# ---------------------------------------------------------------------------
# Generación determinista de las acciones de un anillo (antes en engine.py)
# ---------------------------------------------------------------------------
def build_ring_actions(task, ring_no, assets, executor, ts_base):
    """Acciones concretas que ejecutan Devin + el ejecutor técnico para un anillo.

    Devuelve una lista ordenada de pasos con comando, actor, herramienta,
    salida simulada, estado y duración — para que la demo muestre que las
    acciones se ejecutaron realmente (no solo que 'se aprobó').
    """
    from .. import engine  # import diferido: engine delega en este módulo

    rng = engine._rng(task["id"] + f"actions{ring_no}")
    stage = engine.RING_STAGES.get(ring_no, engine.RING_STAGES[5])
    prev = engine._prev_version(task)
    fixed = engine._fixed_version(prev)
    comp = task.get("component", task["ci_name"])
    ci = task["ci_name"]
    steps = []

    canary = stage["pct"]

    def add(actor, tool, command, output, why, duration=None):
        steps.append({
            "seq": len(steps) + 1, "actor": actor, "tool": tool,
            "command": command, "output": output, "status": "ok", "why": why,
            "duration_s": duration if duration is not None else rng.randint(2, 40),
        })

    # Prólogo por entorno: en Lab/Pre-productivo Devin levanta una RÉPLICA (IaC).
    if stage["kind"] == "replica":
        prov = "Terraform + Ansible"
        add("Devin", prov, f"terraform apply -target=replica.{stage['key']} ({assets} CIs)",
            f"Réplica de {assets} CIs aprovisionada en «{stage['env']}»",
            f"Se levanta una réplica efímera (IaC) de toda la infraestructura impactada para aplicar y probar el fix "
            f"sin tocar producción (etapa «{stage['env']}»).")

    if task["track"] == "C":
        add("Devin", "git", f"git checkout -b fix/{task['cve'].lower()}-image", f"Switched to branch 'fix/{task['cve'].lower()}-image'",
            "Se aísla el cambio en una rama para trazabilidad y revisión (dominio C: la remediación es reconstruir la imagen).")
        add("Devin", "Docker", f"update base image: {comp} {prev} → {fixed}", "Dockerfile + manifests actualizados",
            f"El fix de {task['cve']} está en la versión {fixed} de {comp}; se actualiza la imagen base, no se parchea en caliente.")
        add("GitHub Actions", "Docker", f"docker build --no-cache -t registry/{ci}:{fixed} .", f"Built image sha256:{rng.randint(10**11,10**12)}",
            "Build limpio y reproducible del artefacto inmutable que se promocionará por los anillos.")
        add("Devin", "Trivy", f"trivy image registry/{ci}:{fixed}", "0 CRITICAL / 0 HIGH · imagen firmada (cosign)",
            "Se verifica que la nueva imagen no reintroduce vulnerabilidades y se firma (cosign) antes de desplegar.")
        add("Argo CD", "Helm", f"argocd app sync {ci} --revision {fixed} (canary {canary}%)", f"Rollout progresivo a {assets} pods",
            f"Despliegue GitOps progresivo al {canary}% de los pods de este anillo para acotar el blast radius del cambio.")
    elif task["track"] == "B":
        add("Devin", "git", f"git checkout -b fix/{task['cve'].lower()}-bump", f"Switched to branch 'fix/{task['cve'].lower()}-bump'",
            "Rama dedicada para el bump de dependencia (dominio B: se remedia actualizando la librería y reconstruyendo).")
        add("Devin", "CI/CD", f"bump {comp}: {prev} → {fixed}", "1 file changed · lockfile updated",
            f"Se eleva {comp} a {fixed} (versión con el fix) y se fija el lockfile para un build determinista.")
        add("Devin", "CI/CD", f"gh pr merge --squash (ring {ring_no})", "Merged. Deploy workflow triggered.",
            "El merge del PR dispara el pipeline de despliegue; el cambio queda auditado en la PR.")
        add("GitHub Actions", "Docker", f"docker build -t {ci}:{fixed} .", f"Successfully tagged {ci}:{fixed}",
            "Se construye el artefacto con la dependencia ya parcheada.")
        add("GitHub Actions", "Helm", f"helm upgrade {ci} --set image.tag={fixed} --set canary.weight={canary}", f"Rollout deployed to {assets} pods",
            f"Rollout canary al {canary}% para validar por telemetría antes de ampliar el alcance.")
    else:
        add("Devin", executor, f"snapshot create {ci} --pre-patch (ring {ring_no})", f"Snapshot snap-{rng.randint(10000,99999)} created for {assets} hosts",
            "Se toma snapshot ANTES de parchear para garantizar rollback inmediato si un post-check falla (dominio A: parcheo in-place).")
        add(executor, executor, f"deploy patch {comp} {prev} → {fixed} --limit ring{ring_no}", f"{assets} hosts targeted · maintenance window OK",
            f"El ejecutor ({executor}) apunta solo a los {assets} hosts de este anillo, dentro de la ventana de mantenimiento aprobada.")
        add(executor, "OS", f"install {comp}-{fixed}", f"{assets}/{assets} hosts updated",
            f"Instala la versión {fixed} que corrige {task['cve']} en los hosts objetivo.")
        add(executor, "OS", "systemctl restart affected-services", f"services restarted on {assets} hosts",
            "Reinicio controlado de los servicios afectados para que el parche tome efecto.")

    # Post-checks (evidencia de validación tras aplicar)
    post_why = {
        "version-assert": "Confirma que la versión instalada es la parcheada (no un rollback silencioso).",
        "health-check": "Verifica que los servicios responden sanos tras el cambio.",
        "smoke-test": "Ejecuta el camino crítico de negocio para detectar regresiones.",
        "synthetic-probe": "Sonda sintética externa para validar disponibilidad de cara al usuario.",
    }
    for chk in ["version-assert", "health-check", "smoke-test", "synthetic-probe"]:
        add("Devin", "post-check", chk, f"{chk}: OK ({assets}/{assets})", post_why[chk], rng.randint(1, 12))

    # En Lab/Pre-productivo se ejecuta toda la batería de pruebas sobre la réplica.
    if stage["tests"]:
        n_tests = rng.randint(8, 14)
        add("Devin", "CI/CD", f"run test-suite --env {stage['key']} (MVT completo)",
            f"{n_tests}/{n_tests} pruebas PASS · regresión OK",
            f"En «{stage['env']}» se ejecuta la batería completa de pruebas (funcionales, integración y de "
            f"parche) sobre la réplica antes de promocionar; si algo falla, el despliegue no avanza.")
        if stage["key"] == "lab":
            add("Devin", "Terraform", "terraform destroy -target=replica.lab",
                "Réplica de laboratorio destruida (entorno efímero)",
                "El laboratorio es efímero: tras validar se destruye para no dejar coste ni deriva de configuración.")
    return {"steps": steps, "from_version": prev, "to_version": fixed}


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------
def _encode_reference(job_id: str, started: datetime) -> str:
    return f"{REFERENCE_PREFIX}:{job_id}:{int(started.timestamp())}"


def decode_reference(reference: str) -> tuple[str, datetime]:
    parts = (reference or "").split(":")
    if len(parts) != 3 or parts[0] != REFERENCE_PREFIX:
        raise ProviderError("PROVIDER_REFERENCE_INVALID",
                            "La referencia de ejecución no pertenece al provider mock.")
    try:
        started = datetime.fromtimestamp(int(parts[2]), tz=timezone.utc)
    except (ValueError, OSError) as exc:
        raise ProviderError("PROVIDER_REFERENCE_INVALID",
                            "La referencia de ejecución mock es ilegible.") from exc
    return parts[1], started


class MockPatchProvider:
    """Ejecuta el parcheo de forma simulada, determinista y no bloqueante."""

    name = PROVIDER_MOCK

    def __init__(self, settings: Settings, now_fn=utcnow):
        self._settings = settings
        self._now = now_fn

    # ------------------------------------------------------------------
    def validate_target(self, request: PatchRequest) -> TargetPolicyResult:
        target = request.primary_target()
        checks = (
            {"check": "Objetivo resuelto", "ok": True,
             "detail": f"Objetivo lógico {target.logical_target_id} ({target.name or '-'})."},
            {"check": "Provider simulado", "ok": True,
             "detail": "El provider mock no ejecuta operaciones reales ni requiere credenciales."},
            {"check": "Ventana de mantenimiento", "ok": True,
             "detail": f"Anillo {request.ring_number} dentro de la ventana aprobada (simulado)."},
        )
        return TargetPolicyResult(allowed=True, checks=checks, target=target,
                                  message="Objetivo válido para ejecución simulada.")

    # ------------------------------------------------------------------
    def _plan(self, request: PatchRequest) -> dict:
        task = request.task_snapshot
        if not task:
            raise ProviderError("REQUEST_INCOMPLETE",
                                "La petición no incluye el contexto de la tarea.")
        return build_ring_actions(task, request.ring_number, max(1, request.assets_count),
                                 request.executor or "Ansible", 0)

    def start(self, request: PatchRequest, idempotency_key: str) -> PatchExecution:
        plan = self._plan(request)
        started = self._now()
        if request.dry_run:
            planned = tuple(
                ExecutionStep(seq=s["seq"], actor=s["actor"], tool=s["tool"], command=s["command"],
                              output="[dry-run] no ejecutado", status="planned", why=s["why"],
                              duration_s=0)
                for s in plan["steps"])
            return PatchExecution(
                provider=self.name, provider_reference=f"dryrun:{request.job_id}",
                status=ExecutionStatus.DRY_RUN, dry_run=True, steps=planned,
                from_version=plan["from_version"], to_version=plan["to_version"],
                started_at=iso_utc(started), completed_at=iso_utc(started),
                detail="Simulación en dry-run: no se aplica ningún cambio.")
        return PatchExecution(
            provider=self.name, provider_reference=_encode_reference(request.job_id, started),
            status=ExecutionStatus.RUNNING, dry_run=False, steps=(),
            from_version=plan["from_version"], to_version=plan["to_version"],
            started_at=iso_utc(started),
            detail=f"Ejecución simulada iniciada (idempotency-key {idempotency_key[:12]}…).")

    # ------------------------------------------------------------------
    def poll(self, provider_reference: str, request: PatchRequest | None = None) -> PatchExecution:
        if request is None:
            raise ProviderError("REQUEST_INCOMPLETE",
                                "El provider mock necesita la petición original para reconstruir el plan.")
        if provider_reference.startswith("dryrun:"):
            return self.start(request, "replay")
        _job_id, started = decode_reference(provider_reference)
        plan = self._plan(request)
        all_steps = plan["steps"]
        duration = max(1, self._settings.mock_job_duration_seconds)
        elapsed = (self._now() - started).total_seconds()
        ratio = max(0.0, min(1.0, elapsed / duration))
        # Siempre se revela al menos un paso y, hasta agotar la duración, queda
        # al menos uno pendiente: garantiza un estado no terminal antes de acabar.
        revealed = max(1, int(ratio * len(all_steps)))
        done = elapsed >= duration
        if not done:
            revealed = min(revealed, max(1, len(all_steps) - 1))
        steps = tuple(
            ExecutionStep(seq=s["seq"], actor=s["actor"], tool=s["tool"], command=s["command"],
                          output=s["output"], status=s["status"], why=s["why"],
                          duration_s=s["duration_s"])
            for s in all_steps[:revealed])
        status = ExecutionStatus.SUCCEEDED if done else ExecutionStatus.RUNNING
        return PatchExecution(
            provider=self.name, provider_reference=provider_reference, status=status,
            dry_run=False, steps=steps, from_version=plan["from_version"],
            to_version=plan["to_version"], started_at=iso_utc(started),
            completed_at=iso_utc(self._now()) if done else None,
            report=self._report(request, plan) if done else {},
            detail=f"{len(steps)}/{len(all_steps)} pasos completados.")

    def _report(self, request: PatchRequest, plan: dict) -> dict[str, str]:
        """Report simulado con la misma forma que el del runbook de Automation."""
        target = request.primary_target()
        report = {
            "Advisory": self._settings.patch_advisory_id,
            "Releasever": self._settings.patch_releasever,
            "ExpectedFixedKernel": self._settings.patch_expected_fixed_kernel,
            "PreviousKernel": plan["from_version"],
            "CurrentKernel": self._settings.patch_expected_fixed_kernel or plan["to_version"],
            "PatchStatus": "PATCHED",
            "HealthStatus": "HEALTHY",
            "CorrelationId": request.correlation_id,
        }
        if target.instance_id:
            report["InstanceId"] = target.instance_id
        return {key: value for key, value in report.items() if value}

    # ------------------------------------------------------------------
    def cancel(self, provider_reference: str, request: PatchRequest | None = None) -> PatchExecution:
        if provider_reference.startswith("dryrun:"):
            raise ProviderError("CANCEL_NOT_POSSIBLE",
                                "Una ejecución dry-run ya ha terminado; no puede cancelarse.")
        _job_id, started = decode_reference(provider_reference)
        return PatchExecution(
            provider=self.name, provider_reference=provider_reference,
            status=ExecutionStatus.CANCELLED, dry_run=False, steps=(),
            started_at=iso_utc(started), completed_at=iso_utc(self._now()),
            detail="Ejecución simulada cancelada.")
