"""Contrato explícito de runbooks de Systems Manager Automation.

`StartAutomationExecution` sólo acepta documentos de tipo `Automation`. Los
documentos de tipo `Command` (por ejemplo `AWS-RunPatchBaseline`) se ejecutan
con `SendCommand` y por tanto NO pueden usarse aquí: un runbook propio de tipo
Automation es el que los invoca internamente mediante `aws:runCommand`.

Cada operación declara su propio esquema de parámetros: el backend nunca envía
parámetros genéricos (`Operation=Install`, `TargetVersion`, ...) a un runbook
que no los declara.

Los runbooks de la PoC no declaran `assumeRole` ni admiten
`AutomationAssumeRole`: la cuenta no permite crear un service role de Automation,
así que la ejecución usa siempre los permisos de la identidad que la inicia (el
ECS Task Role del backend desplegado) y la identidad efectiva no es configurable.
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
            "implemented": self.implemented,
        }


# Parámetros que ningún runbook de la PoC puede recibir: son la vía habitual
# para inyectar comandos arbitrarios en un documento de Automation.
# `AutomationAssumeRole` también está prohibido: permitiría cambiar desde fuera la
# identidad con la que se ejecutan los pasos.
_FORBIDDEN = frozenset({"Commands", "Command", "Script", "SourceInfo", "Parameters",
                        "DocumentName", "Operation", "InstallOverrideList",
                        "AutomationAssumeRole"})

CONTRACTS: dict[str, RunbookContract] = {
    OPERATION_PATCH: RunbookContract(
        operation=OPERATION_PATCH,
        required_parameters=frozenset({"InstanceId"}),
        optional_parameters=frozenset({"CorrelationId"}),
        forbidden_parameters=_FORBIDDEN | frozenset({"TargetVersion", "SnapshotId",
                                                     "RebootOption"}),
    ),
    OPERATION_ROLLBACK: RunbookContract(
        operation=OPERATION_ROLLBACK,
        required_parameters=frozenset({"InstanceId"}),
        optional_parameters=frozenset({"TargetVersion", "SnapshotId"}),
        forbidden_parameters=_FORBIDDEN,
    ),
    # Reset del laboratorio: Auto Scaling sustituye la instancia actual dentro
    # del grupo de capacidad fija 1. El Launch Template y su versión son
    # propiedad del ASG y ya no se envían como parámetros del runbook.
    OPERATION_RESET_LAB: RunbookContract(
        operation=OPERATION_RESET_LAB,
        required_parameters=frozenset({"CurrentInstanceId", "AutoScalingGroupName"}),
        optional_parameters=frozenset({"CorrelationId"}),
        forbidden_parameters=_FORBIDDEN | frozenset({"VulnerableAmiId", "TargetVersion",
                                                     "SnapshotId", "LogicalLabId",
                                                     "LaunchTemplateId",
                                                     "LaunchTemplateVersion"}),
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
                                   f"Operation '{operation}' has no declared runbook contract.")
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
            f"There is no Automation runbook configured for operation '{operation}'.")
    if name in KNOWN_COMMAND_DOCUMENTS:
        raise RunbookContractError(
            "DOCUMENT_TYPE_NOT_SUPPORTED",
            f"'{name}' is a Command-type document and cannot be started with "
            "StartAutomationExecution; it must be invoked from a dedicated Automation "
            "runbook via aws:runCommand.")
    if name not in settings.allowed_runbooks:
        raise RunbookContractError("RUNBOOK_NOT_ALLOWED",
                                   f"Runbook '{name}' is not in the internal allowlist.")
    return ResolvedRunbook(name=name, contract=contract)


def assert_document_type(name: str, document_type: str | None, contract: RunbookContract) -> None:
    """Comprueba el tipo devuelto por `ssm.describe_document` antes de ejecutar."""
    if document_type != contract.document_type:
        raise RunbookContractError(
            "DOCUMENT_TYPE_NOT_SUPPORTED",
            f"Document '{name}' is of type '{document_type or 'unknown'}' and "
            f"requires '{contract.document_type}'.")


def assert_track_supported(track: str | None, contract: RunbookContract) -> None:
    if (track or "") not in contract.allowed_tracks:
        raise RunbookContractError(
            "UNSUPPORTED_REMEDIATION_TRACK",
            f"Track '{track or 'not set'}' does not run on AWS: runbook "
            f"'{contract.operation}' only supports {', '.join(sorted(contract.allowed_tracks))}.")


def assert_operating_system_supported(operating_system: str | None,
                                      contract: RunbookContract) -> None:
    value = (operating_system or "").lower()
    if not any(allowed in value for allowed in contract.allowed_operating_systems):
        raise RunbookContractError(
            "TARGET_OS_NOT_SUPPORTED",
            f"Operating system '{operating_system or 'unknown'}' is not supported by "
            f"the {contract.operation} runbook.")


def validate_parameters(contract: RunbookContract, parameters: dict) -> dict:
    """Los parámetros deben provenir del esquema del runbook, no de un genérico."""
    keys = set(parameters or {})
    forbidden = sorted(keys & contract.forbidden_parameters)
    if forbidden:
        raise RunbookContractError(
            "PARAMETER_FORBIDDEN",
            f"Forbidden parameters for the {contract.operation} runbook: "
            f"{', '.join(forbidden)}.")
    undeclared = sorted(keys - contract.declared_parameters)
    if undeclared:
        raise RunbookContractError(
            "PARAMETER_NOT_DECLARED",
            f"The {contract.operation} runbook does not declare: {', '.join(undeclared)}.")
    missing = sorted(contract.required_parameters - keys)
    if missing:
        raise RunbookContractError(
            "PARAMETER_REQUIRED_MISSING",
            f"Mandatory parameters missing for the {contract.operation} runbook: "
            f"{', '.join(missing)}.")
    return dict(parameters or {})
