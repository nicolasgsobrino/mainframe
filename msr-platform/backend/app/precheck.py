"""Evidencia de sólo lectura del estado real del laboratorio.

El estado operativo (vulnerable o parcheado) NO se deduce de SQLite ni del
histórico de jobs: se obtiene de AWS con APIs de sólo lectura.

Fuentes de evidencia, en orden de preferencia:

1. Inventario de Systems Manager (`ssm:ListInventoryEntries`, `AWS:Application`):
   versión instalada del paquete del advisory (`kernel`). Se compara con el
   kernel corregido esperado.
2. Resultado del último escaneo de Patch Manager (`ssm:DescribeInstancePatches`
   y `ssm:DescribeInstancePatchStates`): si el advisory sigue en estado
   `Missing`, es aplicable; si existe un escaneo y no aparece, está corregido.

Cuando ninguna fuente concluye, el estado es `unknown`: el reconciliador es
*fail-closed* y nunca ejecuta una operación destructiva sobre evidencia ausente.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .config import PROVIDER_AWS_AUTOMATION, Settings
from .labs import LabInstance

VULNERABLE = "vulnerable"
PATCHED = "patched"
STATE_UNKNOWN = "unknown"

HEALTHY = "healthy"
UNHEALTHY = "unhealthy"
HEALTH_UNKNOWN = "unknown"

SOURCE_AWS = "aws-readonly"
SOURCE_MOCK = "mock"

# «6.1.176-220.358.amzn2023.x86_64» → versión (6.1.176) y release (220.358).
_KERNEL_RE = re.compile(r"^(\d+(?:\.\d+)*)-(\d+(?:\.\d+)*)")


def kernel_key(kernel: str | None) -> tuple[tuple[int, ...], tuple[int, ...]] | None:
    """Clave comparable de un kernel de Amazon Linux, o `None` si no encaja."""
    match = _KERNEL_RE.match((kernel or "").strip())
    if match is None:
        return None
    version = tuple(int(part) for part in match.group(1).split("."))
    release = tuple(int(part) for part in match.group(2).split("."))
    return version, release


def kernel_is_older(current: str | None, expected_fixed: str | None) -> bool | None:
    """`True` si `current` es anterior al kernel corregido; `None` si no se puede comparar."""
    left, right = kernel_key(current), kernel_key(expected_fixed)
    if left is None or right is None:
        return None
    return left < right


def _capture_time(value: object) -> datetime | None:
    """`CaptureTime` del inventario, que boto3 devuelve como texto ISO."""
    if isinstance(value, datetime):
        moment = value
    elif isinstance(value, str) and value.strip():
        try:
            moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


@dataclass(frozen=True, slots=True)
class LabEvidence:
    """Estado observado del laboratorio y los checks que lo justifican."""

    vulnerable_state: str = STATE_UNKNOWN
    health_state: str = HEALTH_UNKNOWN
    ssm_state: str = HEALTH_UNKNOWN
    current_kernel: str | None = None
    expected_fixed_kernel: str | None = None
    advisory_id: str | None = None
    advisory_applicable: bool | None = None
    source: str = SOURCE_AWS
    checks: tuple[dict, ...] = ()
    detail: str = ""

    @property
    def vulnerable(self) -> bool:
        return self.vulnerable_state == VULNERABLE

    @property
    def ready(self) -> bool:
        """Listo para una nueva demostración: vulnerable, sano y gestionado."""
        return (self.vulnerable_state == VULNERABLE
                and self.health_state == HEALTHY
                and self.ssm_state == "Online"
                and self.advisory_applicable is not False)

    def as_dict(self) -> dict:
        return {
            "vulnerable_state": self.vulnerable_state,
            "health_state": self.health_state,
            "ssm_state": self.ssm_state,
            "current_kernel": self.current_kernel,
            "expected_fixed_kernel": self.expected_fixed_kernel,
            "advisory_id": self.advisory_id,
            "advisory_applicable": self.advisory_applicable,
            "source": self.source,
            "ready": self.ready,
            "checks": [dict(check) for check in self.checks],
            "detail": self.detail,
        }


@dataclass
class _Checks:
    items: list[dict] = field(default_factory=list)

    def add(self, name: str, ok: bool | None, detail: str) -> None:
        self.items.append({"check": name, "ok": ok, "detail": detail})

    def tuple(self) -> tuple[dict, ...]:
        return tuple(self.items)


class AwsLabPrecheck:
    """Precheck de sólo lectura contra EC2, Systems Manager y Auto Scaling."""

    source = SOURCE_AWS

    def __init__(self, settings: Settings, provider, repository=None):
        self._settings = settings
        self._provider = provider
        self._repo = repository

    # -- fuentes de evidencia -------------------------------------------
    def _patched_since(self, logical_lab_id: str) -> datetime | None:
        """Momento en que AWS confirmó el último parcheo de este laboratorio."""
        if self._repo is None or not logical_lab_id:
            return None
        lab = self._repo.get_lab_target(logical_lab_id)
        if lab is None:
            return None
        if isinstance(lab.last_patch_at, datetime):
            return lab.last_patch_at
        # Laboratorios parcheados antes de registrar el instante: el job durable
        # que lo aplicó conserva cuándo terminó.
        job = self._repo.get_job(lab.last_patch_job_id) if lab.last_patch_job_id else None
        completed = job.completed_at if job is not None else None
        return completed if isinstance(completed, datetime) else None

    def _inventory_kernel(self, instance_id: str,
                          patched_since: datetime | None) -> tuple[str | None, str]:
        package = self._settings.patch_package_family or "kernel"
        try:
            response = self._provider.ssm.list_inventory_entries(
                InstanceId=instance_id, TypeName="AWS:Application",
                Filters=[{"Key": "Name", "Values": [package], "Type": "Equal"}])
        except Exception as exc:
            return None, f"The Systems Manager inventory is not available ({type(exc).__name__})."
        entries = response.get("Entries") or []
        versions: list[tuple[tuple, str]] = []
        for entry in entries:
            if (entry.get("Name") or "") != package:
                continue
            version = str(entry.get("Version") or "").strip()
            release = str(entry.get("Release") or "").strip()
            architecture = str(entry.get("Architecture") or "").strip()
            candidate = version if not release else f"{version}-{release}"
            if architecture:
                candidate = f"{candidate}.{architecture}"
            key = kernel_key(candidate)
            if key is not None:
                versions.append((key, candidate))
        if not versions:
            return None, (f"The inventory contains no version of '{package}' "
                          "for this instance.")
        versions.sort()
        # La instancia arranca con el kernel más reciente instalado.
        latest = versions[-1][1]
        captured = _capture_time(response.get("CaptureTime"))
        if patched_since is not None and (captured is None or captured <= patched_since):
            # El inventario lo refresca una asociación periódica: si no se ha
            # recapturado desde el parcheo, la versión que publica es anterior
            # y no puede contradecir al informe de la Automation.
            return None, (
                "The inventory has not been recaptured since the last patching "
                f"(capture: {captured.isoformat() if captured else 'unknown'}); "
                f"the version it publishes ({latest}) is older.")
        return latest, f"Latest installed kernel according to the inventory: {latest}."

    def _advisory_applicable(self, instance_id: str) -> tuple[bool | None, str]:
        advisory = self._settings.patch_advisory_id or ""
        if not advisory:
            return None, "There is no advisory configured to check."
        try:
            missing = self._provider.ssm.describe_instance_patches(
                InstanceId=instance_id,
                Filters=[{"Key": "State", "Values": ["Missing"]}])
        except Exception as exc:
            return None, (f"Patch Manager did not return any pending patches "
                          f"({type(exc).__name__}).")
        for patch in missing.get("Patches") or []:
            haystack = " ".join(str(patch.get(key) or "") for key in ("Title", "KBId", "CVEIds"))
            if advisory in haystack:
                return True, f"Advisory {advisory} is still pending according to Patch Manager."
        if self._patch_scan_exists(instance_id):
            return False, (f"A Patch Manager scan exists and {advisory} is not listed "
                           "as pending.")
        return None, ("There is no Patch Manager scan confirming the applicability "
                      f"of {advisory}.")

    def _patch_scan_exists(self, instance_id: str) -> bool:
        try:
            states = self._provider.ssm.describe_instance_patch_states(
                InstanceIds=[instance_id])
        except Exception:
            return False
        for state in states.get("InstancePatchStates") or []:
            if state.get("OperationEndTime") or state.get("Operation"):
                return True
        return False

    def _ec2_health(self, instance_id: str) -> tuple[bool | None, str]:
        try:
            response = self._provider.ec2.describe_instance_status(InstanceIds=[instance_id])
        except Exception as exc:
            return None, f"EC2 did not return the instance status ({type(exc).__name__})."
        statuses = response.get("InstanceStatuses") or []
        if not statuses:
            return None, "EC2 does not publish status checks for the instance yet."
        status = statuses[0]
        instance_ok = ((status.get("InstanceStatus") or {}).get("Status") or "") == "ok"
        system_ok = ((status.get("SystemStatus") or {}).get("Status") or "") == "ok"
        detail = (f"EC2 checks: instance="
                  f"{(status.get('InstanceStatus') or {}).get('Status') or 'not set'}, "
                  f"system={(status.get('SystemStatus') or {}).get('Status') or 'not set'}.")
        return (instance_ok and system_ok), detail

    def _autoscaling_health(self, instance_id: str) -> tuple[bool | None, str]:
        if not self._settings.lab_autoscaling_group_name:
            return None, "No Auto Scaling Group configured."
        try:
            response = self._provider.autoscaling.describe_auto_scaling_instances(
                InstanceIds=[instance_id])
        except Exception as exc:
            return None, f"Auto Scaling did not return the instance status ({type(exc).__name__})."
        entries = response.get("AutoScalingInstances") or []
        if not entries:
            return None, "The instance does not appear in the Auto Scaling Group yet."
        entry = entries[0]
        lifecycle = entry.get("LifecycleState") or ""
        health = entry.get("HealthStatus") or ""
        # DescribeAutoScalingInstances devuelve «HEALTHY»; DescribeAutoScalingGroups, «Healthy».
        ok = lifecycle == "InService" and health.lower() == "healthy"
        return ok, f"Auto Scaling: LifecycleState={lifecycle or '-'}, HealthStatus={health or '-'}."

    # -- resultado -------------------------------------------------------
    def inspect(self, instance: LabInstance) -> LabEvidence:
        checks = _Checks()
        expected = self._settings.patch_expected_fixed_kernel or None
        advisory = self._settings.patch_advisory_id or None

        ssm_state = instance.ping_status or HEALTH_UNKNOWN
        checks.add("Node managed by SSM Online", ssm_state == "Online",
                   f"PingStatus={ssm_state}.")

        kernel, kernel_detail = self._inventory_kernel(
            instance.instance_id, self._patched_since(instance.logical_lab_id))
        checks.add("Installed kernel known", kernel is not None, kernel_detail)
        older = kernel_is_older(kernel, expected)
        if older is not None:
            checks.add("Kernel older than the fixed one", older,
                       f"Current kernel {kernel} against the expected fixed one {expected}.")

        applicable, advisory_detail = self._advisory_applicable(instance.instance_id)
        checks.add(f"Advisory {advisory or '-'} applicable", applicable, advisory_detail)

        ec2_ok, ec2_detail = self._ec2_health(instance.instance_id)
        checks.add("EC2 status checks", ec2_ok, ec2_detail)
        asg_ok, asg_detail = self._autoscaling_health(instance.instance_id)
        checks.add("Instance InService and Healthy in the ASG", asg_ok, asg_detail)

        if older is not None:
            vulnerable_state = VULNERABLE if older else PATCHED
        elif applicable is True:
            vulnerable_state = VULNERABLE
        elif applicable is False:
            vulnerable_state = PATCHED
        else:
            vulnerable_state = STATE_UNKNOWN

        # Salud estricta y fail-closed: ninguna señal disponible puede estar en
        # rojo, hace falta al menos una concluyente y, si el laboratorio declara
        # un Auto Scaling Group, la instancia debe estar InService y Healthy en
        # él (la ausencia de evidencia del ASG no se considera salud).
        signals = [signal for signal in (ec2_ok, asg_ok) if signal is not None]
        asg_required = bool(self._settings.lab_autoscaling_group_name)
        if asg_required and asg_ok is not True:
            health_state = UNHEALTHY
        elif not signals:
            health_state = HEALTH_UNKNOWN
        elif all(signals):
            health_state = HEALTHY
        else:
            health_state = UNHEALTHY

        detail = {
            VULNERABLE: "The instance is still exposed to the advisory.",
            PATCHED: "The instance is already patched.",
            STATE_UNKNOWN: "AWS does not provide enough evidence of the lab state.",
        }[vulnerable_state]
        return LabEvidence(
            vulnerable_state=vulnerable_state, health_state=health_state, ssm_state=ssm_state,
            current_kernel=kernel, expected_fixed_kernel=expected, advisory_id=advisory,
            advisory_applicable=applicable, source=self.source, checks=checks.tuple(),
            detail=detail)


class MockLabPrecheck:
    """Precheck simulado: no consulta AWS y no inventa versiones de kernel."""

    source = SOURCE_MOCK

    def __init__(self, settings: Settings, repository=None):
        self._settings = settings
        self._repo = repository

    def inspect(self, instance: LabInstance) -> LabEvidence:
        lab = self._repo.get_lab_target(instance.logical_lab_id) if self._repo else None
        patched = bool(lab is not None and lab.lab_state == PATCHED)
        expected = self._settings.patch_expected_fixed_kernel or None
        checks = _Checks()
        checks.add("Simulated precheck", True,
                   "Mock provider: the state comes from the simulated lab, "
                   "with no AWS calls.")
        return LabEvidence(
            vulnerable_state=PATCHED if patched else VULNERABLE,
            health_state=HEALTHY, ssm_state="Online",
            current_kernel=expected if patched else None,
            expected_fixed_kernel=expected,
            advisory_id=self._settings.patch_advisory_id or None,
            advisory_applicable=not patched, source=self.source, checks=checks.tuple(),
            detail=("Simulated lab patched." if patched
                    else "Simulated lab vulnerable."))


def get_lab_precheck(settings: Settings, provider, repository=None):
    """Precheck acorde al provider activo (AWS de sólo lectura o simulado)."""
    if provider.name == PROVIDER_AWS_AUTOMATION:
        return AwsLabPrecheck(settings, provider, repository)
    return MockLabPrecheck(settings, repository)
