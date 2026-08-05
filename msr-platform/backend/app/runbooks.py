"""Contrato explícito de runbooks de Systems Manager Automation.

`StartAutomationExecution` sólo acepta documentos de tipo `Automation`. Los
documentos de tipo `Command` (por ejemplo `AWS-RunPatchBaseline`) se ejecutan
con `SendCommand` y por tanto NO pueden usarse aquí: un runbook propio de tipo
Automation es el que los invoca internamente mediante `aws:runCommand`.

Cada operación declara su propio esquema de parámetros: el backend nunca envía
parámetros genéricos (`Operation=Install`, `TargetVersion`, ...) a un runbook
que no los declara.

`AutomationAssumeRole` es opcional y sólo puede proceder de la configuración
interna: cuando no está configurado se omite por completo de
`StartAutomationExecution` y la ejecución hereda las credenciales de la
identidad que la inicia.
"""
from __future__ import annotations

from dataclasses import dataclass, field

OPERATION_PATCH = "patch"
OPERATION_ROLLBACK = "rollback"
OPERATION_RESET_LAB = "reset_lab"

DOCUMENT_TYPE_AUTOMATION = "Automation"

# Documentos gestionados por AWS de tipo Command: se ejecutan con SendCommand y
# nunca pueden enviarse a StartAutomationExecution.
KNOWN_COMMAND_DOCUMENTS = frozenset({
    "AWS-RunPatchBaseline",
    "AWS-RunShellScript",
    "AWS-RunPowerShellScript",
    "AWS-ConfigureAWSPackage",
    "AWS-UpdateSSMAgent",
    "AWS-InstallApplication",
})

# Nombres por defecto de los runbooks propios (configurables por entorno).
DEFAULT_PATCH_RUNBOOK = "MSR-PatchLinuxInstance"
DEFAULT_ROLLBACK_RUNBOOK = "MSR-RollbackLinuxInstance"
DEFAULT_RESET_RUNBOOK = "MSR-ResetLabInstance"


class RunbookContractError(Exception):
    """Violación del contrato de runbooks (tipo, allowlist o parámetros)."""

    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class RunbookContract:
    """Esquema declarado de un runbook: tipo, operación y parámetros."""

    operation: str
    document_type: str = DOCUMENT_TYPE_AUTOMATION
    required_parameters: frozenset[str] = field(default_factory=frozenset)
    optional_parameters: frozenset[str] = field(default_factory=frozenset)
    forbidden_parameters: frozenset[str] = field(default_factory=frozenset)
    allowed_tracks: frozenset[str] = frozenset({"A"})
    allowed_operating_systems: frozenset[str] = frozenset({"linux"})
    requires_assume_role: bool = True
    implemented: bool = True

    @property
    def declared_parameters(self) -> frozenset[str]:
        return self.required_parameters | self.optional_parameters

    def as_dict(self) -> dict:
        return {
            "operation": self.operation,
            "document_type": self.document_type,
            "required_parameters": sorted(self.required_parameters),
            "optional_parameters": sorted(self.optional_parameters),
            "forbidden_parameters": sorted(self.forbidden_parameters),
            "allowed_tracks": sorted(self.allowed_tracks),
            "allowed_operating_systems": sorted(self.allowed_operating_systems),
            "requires_assume_role": self.requires_assume_role,
            "implemented": self.implemented,
        }


# Parámetros que ningún runbook de la PoC puede recibir: son la vía habitual
# para inyectar comandos arbitrarios en un documento de Automation.
_FORBIDDEN = frozenset({"Commands", "Command", "Script", "SourceInfo", "Parameters",
                        "DocumentName", "Operation", "InstallOverrideList"})

CONTRACTS: dict[str, RunbookContract] = {
    OPERATION_PATCH: RunbookContract(
        operation=OPERATION_PATCH,
        required_parameters=frozenset({"InstanceId"}),
        optional_parameters=frozenset({"AutomationAssumeRole", "CorrelationId"}),
        forbidden_parameters=_FORBIDDEN | frozenset({"TargetVersion", "SnapshotId",
                                                     "RebootOption"}),
        # La cuenta deniega la creación de un service role de Automation: la
        # ejecución usa las credenciales de la identidad que la inicia.
        requires_assume_role=False,
    ),
    OPERATION_ROLLBACK: RunbookContract(
        operation=OPERATION_ROLLBACK,
        required_parameters=frozenset({"InstanceId"}),
        optional_parameters=frozenset({"AutomationAssumeRole", "TargetVersion", "SnapshotId"}),
        forbidden_parameters=_FORBIDDEN,
        requires_assume_role=False,
    ),
    # Reset del laboratorio: Auto Scaling sustituye la instancia actual dentro
    # del grupo de capacidad fija 1. El Launch Template y su versión son
    # propiedad del ASG y ya no se envían como parámetros del runbook.
    OPERATION_RESET_LAB: RunbookContract(
        operation=OPERATION_RESET_LAB,
        required_parameters=frozenset({"CurrentInstanceId", "AutoScalingGroupName"}),
        optional_parameters=frozenset({"AutomationAssumeRole", "CorrelationId"}),
        forbidden_parameters=_FORBIDDEN | frozenset({"VulnerableAmiId", "TargetVersion",
                                                     "SnapshotId", "LogicalLabId",
                                                     "LaunchTemplateId",
                                                     "LaunchTemplateVersion"}),
        requires_assume_role=False,
    ),
}


@dataclass(frozen=True, slots=True)
class ResolvedRunbook:
    name: str
    contract: RunbookContract

    def as_dict(self) -> dict:
        return {"name": self.name, **self.contract.as_dict()}


def contract_for(operation: str) -> RunbookContract:
    contract = CONTRACTS.get(operation)
    if contract is None:
        raise RunbookContractError("RUNBOOK_OPERATION_UNKNOWN",
                                   f"Operación '{operation}' sin contrato de runbook declarado.")
    return contract


def configured_runbook_name(settings, operation: str) -> str:
    return {
        OPERATION_PATCH: settings.patch_runbook_name,
        OPERATION_ROLLBACK: settings.rollback_runbook_name,
        OPERATION_RESET_LAB: settings.reset_runbook_name,
    }.get(operation, "")


def resolve_runbook(settings, operation: str) -> ResolvedRunbook:
    """Nombre configurado + contrato, validando tipo y allowlist (sin llamar a AWS)."""
    contract = contract_for(operation)
    name = configured_runbook_name(settings, operation)
    if not name:
        raise RunbookContractError(
            "RUNBOOK_NOT_CONFIGURED",
            f"No hay runbook de Automation configurado para la operación '{operation}'.")
    if name in KNOWN_COMMAND_DOCUMENTS:
        raise RunbookContractError(
            "DOCUMENT_TYPE_NOT_SUPPORTED",
            f"'{name}' es un documento de tipo Command y no puede iniciarse con "
            "StartAutomationExecution; debe invocarse desde un runbook Automation "
            "propio mediante aws:runCommand.")
    if name not in settings.allowed_runbooks:
        raise RunbookContractError("RUNBOOK_NOT_ALLOWED",
                                   f"El runbook '{name}' no está en la allowlist interna.")
    return ResolvedRunbook(name=name, contract=contract)


def assert_document_type(name: str, document_type: str | None, contract: RunbookContract) -> None:
    """Comprueba el tipo devuelto por `ssm.describe_document` antes de ejecutar."""
    if document_type != contract.document_type:
        raise RunbookContractError(
            "DOCUMENT_TYPE_NOT_SUPPORTED",
            f"El documento '{name}' es de tipo '{document_type or 'desconocido'}' y se "
            f"requiere '{contract.document_type}'.")


def assert_track_supported(track: str | None, contract: RunbookContract) -> None:
    if (track or "") not in contract.allowed_tracks:
        raise RunbookContractError(
            "UNSUPPORTED_REMEDIATION_TRACK",
            f"El track '{track or 'sin valor'}' no se ejecuta en AWS: el runbook "
            f"'{contract.operation}' sólo soporta {', '.join(sorted(contract.allowed_tracks))}.")


def assert_operating_system_supported(operating_system: str | None,
                                      contract: RunbookContract) -> None:
    value = (operating_system or "").lower()
    if not any(allowed in value for allowed in contract.allowed_operating_systems):
        raise RunbookContractError(
            "TARGET_OS_NOT_SUPPORTED",
            f"El sistema operativo '{operating_system or 'desconocido'}' no está soportado por "
            f"el runbook de {contract.operation}.")


def validate_parameters(contract: RunbookContract, parameters: dict) -> dict:
    """Los parámetros deben provenir del esquema del runbook, no de un genérico."""
    keys = set(parameters or {})
    forbidden = sorted(keys & contract.forbidden_parameters)
    if forbidden:
        raise RunbookContractError(
            "PARAMETER_FORBIDDEN",
            f"Parámetros prohibidos para el runbook de {contract.operation}: "
            f"{', '.join(forbidden)}.")
    undeclared = sorted(keys - contract.declared_parameters)
    if undeclared:
        raise RunbookContractError(
            "PARAMETER_NOT_DECLARED",
            f"El runbook de {contract.operation} no declara: {', '.join(undeclared)}.")
    missing = sorted(contract.required_parameters - keys)
    if missing:
        raise RunbookContractError(
            "PARAMETER_REQUIRED_MISSING",
            f"Faltan parámetros obligatorios del runbook de {contract.operation}: "
            f"{', '.join(missing)}.")
    return dict(parameters or {})
