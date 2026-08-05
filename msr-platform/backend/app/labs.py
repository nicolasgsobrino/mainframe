"""Resolución dinámica del laboratorio reseteable por identificador lógico.

El Instance ID del laboratorio cambia en cada reset, así que nunca se fija en la
CMDB ni se acepta desde el frontend: se resuelve por tags a partir del
`logical_lab_id`, exigiendo **exactamente una** instancia activa.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .config import PROVIDER_AWS_AUTOMATION, Settings
from .lab import LabTarget, synthetic_instance_id
from .policy import INSTANCE_ID_RE
from .providers.base import ProviderError, Target

# Estados que cuentan como «instancia activa» del laboratorio. Una instancia
# terminada nunca puede volver a usarse como objetivo.
ACTIVE_INSTANCE_STATES = ("pending", "running", "stopping", "stopped")

ERROR_NOT_FOUND = "LAB_TARGET_NOT_FOUND"
ERROR_AMBIGUOUS = "LAB_TARGET_AMBIGUOUS"
ERROR_TAGS = "LAB_TARGET_TAGS_INVALID"


class LabResolutionError(Exception):
    """No se puede determinar de forma inequívoca la instancia del laboratorio."""

    def __init__(self, code: str, message: str, candidates: tuple[str, ...] = ()):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.candidates = candidates


@dataclass(frozen=True, slots=True)
class LabInstance:
    """Instancia resuelta del laboratorio (datos de sólo lectura)."""

    instance_id: str
    state: str
    logical_lab_id: str
    account_id: str | None = None
    region: str | None = None
    image_id: str | None = None
    private_ip: str | None = None
    public_ip: str | None = None
    tags: dict[str, str] = field(default_factory=dict)
    ssm_managed: bool = False
    ping_status: str | None = None
    platform: str | None = None
    launch_time: str | None = None
    source: str = "aws"

    def as_dict(self) -> dict:
        return {
            "instance_id": self.instance_id, "state": self.state,
            "logical_lab_id": self.logical_lab_id, "account_id": self.account_id,
            "region": self.region, "image_id": self.image_id,
            "private_ip": self.private_ip, "public_ip": self.public_ip,
            "tags": dict(self.tags), "ssm_managed": self.ssm_managed,
            "ping_status": self.ping_status, "platform": self.platform,
            "launch_time": self.launch_time, "source": self.source,
        }

    def as_target(self, environment: str | None = None) -> Target:
        return Target(
            logical_target_id=self.logical_lab_id, instance_id=self.instance_id,
            account_id=self.account_id, region=self.region, tags=dict(self.tags),
            operating_system=self.platform, ssm_managed=self.ssm_managed,
            environment=environment or self.tags.get("msr-environment"),
            name=self.tags.get("Name"))


def required_lab_tags(settings: Settings, logical_lab_id: str) -> dict[str, str]:
    """Tags que debe llevar la instancia del laboratorio (fijados por IaC)."""
    return {
        settings.required_target_tag_key: settings.required_target_tag_value,
        settings.lab_tag_key: logical_lab_id,
    }


def check_lab_tags(tags: dict, settings: Settings, logical_lab_id: str) -> list[str]:
    """Tags obligatorios ausentes o con un valor distinto del esperado."""
    tags = tags or {}
    return [f"{key}={value}" for key, value in
            required_lab_tags(settings, logical_lab_id).items()
            if tags.get(key) != value]


class AwsLabResolver:
    """Resuelve la instancia del laboratorio con `ec2:DescribeInstances` por tags."""

    source = "aws"

    def __init__(self, settings: Settings, provider):
        self._settings = settings
        self._provider = provider

    def resolve(self, logical_lab_id: str) -> LabInstance:
        filters = [{"Name": "instance-state-name", "Values": list(ACTIVE_INSTANCE_STATES)}]
        filters += [{"Name": f"tag:{key}", "Values": [value]}
                    for key, value in required_lab_tags(self._settings, logical_lab_id).items()]
        try:
            described = self._provider.ec2.describe_instances(Filters=filters)
        except ProviderError:
            raise
        except Exception as exc:
            raise LabResolutionError(
                "LAB_TARGET_LOOKUP_FAILED",
                f"No se pudo consultar EC2 para el laboratorio {logical_lab_id}.") from exc

        found: list[tuple[dict, str]] = [
            (instance, reservation.get("OwnerId") or "")
            for reservation in described.get("Reservations") or []
            for instance in reservation.get("Instances") or []]
        if not found:
            raise LabResolutionError(
                ERROR_NOT_FOUND,
                f"No hay ninguna instancia activa etiquetada para el laboratorio "
                f"{logical_lab_id}. Ejecuta el reset o aprovisiona la infraestructura.")
        if len(found) > 1:
            ids = tuple(sorted(i.get("InstanceId", "") for i, _ in found))
            raise LabResolutionError(
                ERROR_AMBIGUOUS,
                f"El laboratorio {logical_lab_id} resuelve {len(found)} instancias activas "
                "y sólo puede haber una. Termina las sobrantes antes de continuar.",
                candidates=ids)

        instance, owner_id = found[0]
        instance_id = instance.get("InstanceId") or ""
        if not INSTANCE_ID_RE.match(instance_id):
            raise LabResolutionError(
                ERROR_NOT_FOUND,
                f"EC2 devolvió un Instance ID no válido para {logical_lab_id}.")
        tags = {t.get("Key"): t.get("Value") for t in instance.get("Tags") or []}
        missing = check_lab_tags(tags, self._settings, logical_lab_id)
        if missing:
            raise LabResolutionError(
                ERROR_TAGS,
                f"La instancia {instance_id} no lleva los tags obligatorios: "
                f"{', '.join(missing)}.")
        az = (instance.get("Placement") or {}).get("AvailabilityZone") or ""
        state = ((instance.get("State") or {}).get("Name") or "unknown")
        ssm_managed, ping = self._managed_node(instance_id, state)
        launch_time = instance.get("LaunchTime")
        return LabInstance(
            instance_id=instance_id, state=state, logical_lab_id=logical_lab_id,
            account_id=owner_id or None, region=(az[:-1] if az else self._settings.aws_region),
            image_id=instance.get("ImageId"),
            private_ip=instance.get("PrivateIpAddress"),
            public_ip=instance.get("PublicIpAddress"), tags=tags,
            ssm_managed=ssm_managed, ping_status=ping,
            platform=instance.get("PlatformDetails") or instance.get("Platform"),
            launch_time=(launch_time.isoformat() if hasattr(launch_time, "isoformat")
                         else (str(launch_time) if launch_time else None)),
            source=self.source)

    def _managed_node(self, instance_id: str, state: str) -> tuple[bool, str | None]:
        if state != "running":
            return False, None
        try:
            info = self._provider.ssm.describe_instance_information(
                Filters=[{"Key": "InstanceIds", "Values": [instance_id]}])
        except Exception:
            return False, "unknown"
        entries = info.get("InstanceInformationList") or []
        ping = entries[0].get("PingStatus") if entries else None
        return bool(ping == "Online"), ping


class MockLabResolver:
    """Laboratorio simulado: instancia derivada de forma determinista.

    No llama a AWS. El Instance ID cambia cuando cambia la «generación» del
    laboratorio, que es lo que incrementa un reset simulado.
    """

    source = "mock"

    def __init__(self, settings: Settings, repository=None):
        self._settings = settings
        self._repo = repository

    synthetic_instance_id = staticmethod(synthetic_instance_id)

    def resolve(self, logical_lab_id: str) -> LabInstance:
        lab = self._repo.get_lab_target(logical_lab_id) if self._repo else None
        if lab is None:
            raise LabResolutionError(
                ERROR_NOT_FOUND,
                f"El laboratorio {logical_lab_id} no está registrado.")
        instance_id = lab.current_instance_id
        if not instance_id or not INSTANCE_ID_RE.match(instance_id):
            raise LabResolutionError(
                ERROR_NOT_FOUND,
                f"El laboratorio {logical_lab_id} no tiene ninguna instancia activa "
                "registrada; ejecuta un reset para recrearla.")
        tags = dict(lab.required_tags or {})
        tags.update(required_lab_tags(self._settings, logical_lab_id))
        tags.setdefault("msr-environment", self._settings.lab_environment)
        tags.setdefault("msr-resettable", "true")
        return LabInstance(
            instance_id=instance_id, state="running", logical_lab_id=logical_lab_id,
            account_id=lab.account_id, region=lab.region or self._settings.aws_region or None,
            image_id=lab.vulnerable_ami_id, tags=tags, ssm_managed=True,
            ping_status="Online", platform="Linux/UNIX", source=self.source)


def default_lab_target(settings: Settings, logical_lab_id: str) -> LabTarget:
    """Laboratorio inicial derivado de la configuración (sin Instance ID)."""
    return LabTarget(
        logical_lab_id=logical_lab_id,
        current_instance_id=None,
        account_id=(settings.allowed_account_ids[0] if settings.allowed_account_ids else None),
        region=settings.aws_region or None,
        launch_template_id=settings.lab_launch_template_id or None,
        launch_template_version=settings.lab_launch_template_version or None,
        expected_vulnerable_package=settings.patch_package_family or None,
        required_tags=required_lab_tags(settings, logical_lab_id))


def get_lab_resolver(settings: Settings, provider, repository=None):
    """Resolutor acorde al provider activo: AWS real o laboratorio simulado."""
    if getattr(provider, "name", "") == PROVIDER_AWS_AUTOMATION:
        return AwsLabResolver(settings, provider)
    return MockLabResolver(settings, repository)
