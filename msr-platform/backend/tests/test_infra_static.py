"""Comprobaciones estáticas de la infraestructura (sin Terraform ni AWS).

Se leen los ficheros de `infra/terraform/` como texto/YAML: ningún test
ejecuta `terraform`, `plan`, `apply` ni contacta con la cuenta.
"""
from __future__ import annotations

import pathlib
import re

import pytest
import yaml

INFRA = pathlib.Path(__file__).resolve().parents[2] / "infra" / "terraform"
DOCUMENTS = INFRA / "documents"


def policy_document(name: str) -> str:
    """Cuerpo exacto de un `aws_iam_policy_document` (sin arrastrar los siguientes)."""
    pattern = rf'^data "aws_iam_policy_document" "{re.escape(name)}" \{{(.*?)^\}}'
    match = re.search(pattern, code("iam.tf"), re.S | re.M)
    assert match, f"no existe el policy document '{name}'"
    return match.group(1)


def read(name: str) -> str:
    return (INFRA / name).read_text(encoding="utf-8")


def code(name: str) -> str:
    """Fichero sin comentarios: las aserciones miran el codigo, no la prosa."""
    return "\n".join(line for line in read(name).splitlines()
                     if not line.lstrip().startswith("#"))


def document_source(name: str) -> str:
    """Runbook sin comentarios: las aserciones miran el YAML, no la prosa."""
    raw = (DOCUMENTS / name).read_text(encoding="utf-8")
    return "\n".join(line for line in raw.splitlines()
                     if not line.lstrip().startswith("#"))


def document(name: str) -> dict:
    """Runbook renderizado: los marcadores `${...}` se sustituyen por texto."""
    raw = (DOCUMENTS / name).read_text(encoding="utf-8")
    rendered = re.sub(r"\$\{[a-z_]+\}", "PLACEHOLDER", raw)
    return yaml.safe_load(rendered)


def test_default_configuration_creates_no_real_resources():
    variables = read("variables.tf")
    block = variables.split('variable "enable_real_resources"')[1]

    assert re.search(r"default\s*=\s*false", block)
    # Todos los recursos mutativos dependen del interruptor maestro.
    assert "enabled = var.enable_real_resources ? 1 : 0" in read("locals.tf")
    for filename in ("ec2.tf", "networking.tf", "iam.tf", "patching.tf",
                     "automation-documents.tf"):
        content = read(filename)
        resources = re.findall(r'^resource "([^"]+)" "([^"]+)" \{(.*?)^\}',
                               content, re.S | re.M)
        assert resources
        for kind, name, body in resources:
            assert "count = local.enabled" in body, f"{kind}.{name} sin interruptor"


def test_launch_template_enforces_imdsv2_and_encrypted_gp3_root_volume():
    ec2 = read("ec2.tf")

    assert 'http_tokens                 = "required"' in ec2
    assert 'volume_type           = "gp3"' in ec2
    assert "encrypted             = true" in ec2
    assert "delete_on_termination = true" in ec2
    assert "var.root_volume_size_gib" in ec2
    assert re.search(r"condition\s*=\s*var\.root_volume_size_gib >= 8", read("variables.tf"))


def test_the_lab_instance_has_no_key_pair_and_no_detailed_monitoring():
    ec2 = read("ec2.tf")

    assert "key_name  = null" in ec2
    assert re.search(r"monitoring \{\s*enabled = false", ec2)


def test_security_group_has_no_ingress_rules():
    networking = code("networking.tf")

    assert "aws_vpc_security_group_ingress_rule" not in networking
    assert not re.search(r"^\s*ingress\s*\{", networking, re.M)
    assert "aws_vpc_security_group_egress_rule" in networking


def test_open_ui_cidr_is_rejected_by_variable_validation():
    block = read("variables.tf").split('variable "allowed_ui_cidr"')[1]

    assert 'var.allowed_ui_cidr != "0.0.0.0/0"' in block


def test_user_data_does_not_upgrade_the_system_and_leaves_the_baseline():
    user_data = read("user-data.sh.tftpl")

    assert "dnf update" not in user_data
    assert "dnf upgrade" not in user_data
    assert "dnf install -y --setopt=install_weak_deps=False httpd" in user_data
    assert "MSR_POC_HEALTHY" in user_data
    assert "/var/lib/msr-poc/bootstrap-complete" in user_data
    assert "/var/lib/msr-poc/baseline.json" in user_data


def test_patch_baseline_approves_only_the_candidate_advisory():
    patching = code("patching.tf")

    assert 'operating_system = "AMAZON_LINUX_2023"' in patching
    assert "approved_patches                     = [var.candidate_advisory_id]" in patching
    assert "approved_patches_enable_non_security = false" in patching
    assert "approval_rules" not in patching
    assert "aws_ssm_patch_group" in patching


@pytest.mark.parametrize("role", ["instance_boundary", "automation", "application"])
def test_no_role_grants_administrator_wildcards(role):
    iam = code("iam.tf")
    block = iam.split(f'data "aws_iam_policy_document" "{role}"')[1]
    allow_blocks = [b for b in block.split("statement {") if 'effect = "Allow"' in b]

    for allow in allow_blocks:
        actions = re.findall(r'"([a-z0-9]+:[A-Za-z*]+)"', allow)
        assert "*" not in actions
        assert not [a for a in actions if a.endswith(":*")], allow[:200]


def test_instance_role_cannot_start_automations_or_create_instances():
    block = code("iam.tf").split('data "aws_iam_policy_document" "instance_boundary"')[1]

    for denied in ("ssm:StartAutomationExecution", "ec2:RunInstances",
                   "ec2:TerminateInstances", "sts:AssumeRole", "iam:*"):
        assert f'"{denied}"' in block
    assert 'effect = "Deny"' in block


def test_application_role_can_only_start_the_two_msr_runbooks():
    block = code("iam.tf").split('data "aws_iam_policy_document" "application"')[1]

    assert "automation-definition/${var.patch_runbook_name}" in block
    assert "automation-definition/${var.reset_runbook_name}" in block
    assert '"ssm:SendCommand",' in block.split('effect = "Deny"')[1]  # denegado


def test_automation_role_only_targets_the_tagged_lab_instance():
    block = code("iam.tf").split('data "aws_iam_policy_document" "automation"')[1]

    assert "for_each = local.lab_required_tags" in block
    assert "ec2:ResourceTag/${condition.key}" in block
    assert "ssm:resourceTag/${condition.key}" in block


def test_both_documents_are_automation_documents():
    documents = code("automation-documents.tf")

    assert documents.count('document_type   = "Automation"') == 2
    assert "AWS-RunPatchBaseline" not in documents


def test_patch_runbook_installs_through_run_patch_baseline():
    doc = document("MSR-PatchLinuxInstance.yaml")
    steps = {step["name"]: step for step in doc["mainSteps"]}

    assert doc["schemaVersion"] == "0.3"
    assert set(doc["parameters"]) == {"InstanceId", "AutomationAssumeRole", "CorrelationId"}
    install = steps["InstallPatchBaseline"]
    assert install["action"] == "aws:runCommand"
    assert install["inputs"]["DocumentName"] == "AWS-RunPatchBaseline"
    assert install["inputs"]["Parameters"]["Operation"] == ["Install"]
    assert install["inputs"]["Parameters"]["RebootOption"] == ["RebootIfNeeded"]


def test_patch_runbook_prechecks_before_patching_and_can_abort():
    doc = document("MSR-PatchLinuxInstance.yaml")
    names = [step["name"] for step in doc["mainSteps"]]

    assert names.index("SendPrecheckCommand") < names.index("InstallPatchBaseline")
    assert names.index("BranchOnApplicability") < names.index("InstallPatchBaseline")
    assert "FailAdvisoryNotApplicable" in names
    assert names.index("SendPostcheckCommand") > names.index("InstallPatchBaseline")
    assert doc["outputs"] == [
        "Report.Advisory", "Report.PreviousKernel", "Report.CurrentKernel",
        "Report.LatestInstalledKernel", "Report.RebootPerformed", "Report.PatchStatus",
        "Report.HealthStatus", "Report.InstanceId", "Report.CorrelationId"]


# --- fase 2.1: un solo aws:runCommand y verificación estricta ---------------

def test_patch_runbook_has_at_most_one_run_command_action_without_outputs():
    """Automation sólo permite consumir el output de una acción `aws:runCommand`."""
    doc = document("MSR-PatchLinuxInstance.yaml")
    run_commands = [s for s in doc["mainSteps"] if s["action"] == "aws:runCommand"]

    assert len(run_commands) == 1
    assert run_commands[0]["name"] == "InstallPatchBaseline"
    assert "outputs" not in run_commands[0]
    assert "CloudWatchOutputConfig" not in run_commands[0]["inputs"]


def test_patch_prechecks_use_send_command_and_get_command_invocation():
    steps = {s["name"]: s for s in document("MSR-PatchLinuxInstance.yaml")["mainSteps"]}

    for send, wait, get in (("SendPrecheckCommand", "WaitForPrecheckCommand",
                             "GetPrecheckOutput"),
                            ("SendPostcheckCommand", "WaitForPostcheckCommand",
                             "GetPostcheckOutput")):
        assert steps[send]["inputs"]["Api"] == "SendCommand"
        assert steps[send]["inputs"]["DocumentName"] == "AWS-RunShellScript"
        assert steps[wait]["inputs"]["Api"] == "GetCommandInvocation"
        assert steps[get]["inputs"]["Api"] == "GetCommandInvocation"
        assert steps[get]["outputs"][0]["Name"] == "StandardOutputContent"


def test_patch_runbook_queries_the_advisory_and_verifies_the_running_kernel():
    raw = document_source("MSR-PatchLinuxInstance.yaml")

    assert "dnf updateinfo list --available --advisory ${candidate_advisory_id}" in raw
    # El kernel debe cambiar y quedarse en la última versión instalada.
    for error in ("ADVISORY_STILL_APPLICABLE", "KERNEL_NOT_UPDATED",
                  "KERNEL_NOT_RUNNING_LATEST", "POST_PATCH_HEALTH_FAILED"):
        assert error in raw
    assert "MSR_POC_HEALTHY" in raw


def test_reset_runbook_validates_membership_before_replacing_the_instance():
    doc = document("MSR-ResetLabInstance.yaml")
    names = [step["name"] for step in doc["mainSteps"]]
    terminate = names.index("TerminateInstanceInAutoScalingGroup")

    assert names.index("ValidateResettableTarget") < terminate
    assert names.index("DescribeCurrentInstance") < terminate
    assert names.index("DescribeAutoScalingMembership") < terminate
    assert names.index("ValidateAutoScalingGroup") < terminate
    assert names.index("WaitForReplacementInstance") > terminate
    # LaunchTemplateId/Version ya no son parámetros públicos: son del ASG.
    assert set(doc["parameters"]) == {"CurrentInstanceId", "AutoScalingGroupName",
                                      "AutomationAssumeRole", "CorrelationId"}
    assert doc["outputs"] == [
        "Report.OldInstanceId", "Report.NewInstanceId", "Report.LogicalLabId",
        "Report.VulnerableState", "Report.HealthState", "Report.CorrelationId"]


def test_reset_replaces_the_instance_only_through_auto_scaling():
    doc = document("MSR-ResetLabInstance.yaml")
    raw = document_source("MSR-ResetLabInstance.yaml")
    terminate = next(s for s in doc["mainSteps"]
                     if s["name"] == "TerminateInstanceInAutoScalingGroup")

    assert terminate["inputs"]["Service"] == "autoscaling"
    assert terminate["inputs"]["Api"] == "TerminateInstanceInAutoScalingGroup"
    assert terminate["inputs"]["ShouldDecrementDesiredCapacity"] is False
    assert "TerminateInstances" not in raw
    assert "RunInstances" not in raw


def test_reset_validates_the_expected_launch_template_and_capacity():
    raw = document_source("MSR-ResetLabInstance.yaml")

    for error in ("RESET_ASG_NOT_ALLOWED", "RESET_INSTANCE_NOT_IN_ASG",
                  "RESET_ASG_CAPACITY_UNEXPECTED",
                  "RESET_ASG_LAUNCH_TEMPLATE_UNEXPECTED",
                  "RESET_ASG_LAUNCH_TEMPLATE_VERSION_UNEXPECTED"):
        assert error in raw
    assert "$Latest" not in raw


def test_reset_rejects_an_unverifiable_ami():
    raw = document_source("MSR-ResetLabInstance.yaml")

    assert "RESET_AMI_UNVERIFIABLE" in raw
    assert 'reported_ami == "unknown"' in raw


def test_no_runbook_accepts_free_form_commands_from_the_caller():
    for name in ("MSR-PatchLinuxInstance.yaml", "MSR-ResetLabInstance.yaml"):
        parameters = document(name)["parameters"]
        forbidden = {"Commands", "Command", "Script", "SourceInfo", "Parameters",
                     "DocumentName", "Operation", "InstallOverrideList"}
        assert not forbidden & set(parameters)


def test_the_lab_instance_is_managed_by_an_autoscaling_group_of_fixed_capacity():
    ec2 = code("ec2.tf")

    # Sin instancia suelta administrada por Terraform: no hay deriva posible.
    assert 'resource "aws_instance" "lab"' not in ec2
    assert 'resource "aws_autoscaling_group" "lab"' in ec2
    for key in ("min_size", "max_size", "desired_capacity"):
        assert re.search(rf"^\s*{key}\s*=\s*1$", ec2, re.M)
    assert re.search(r'^\s*health_check_type\s*=\s*"EC2"$', ec2, re.M)
    assert re.search(r"^\s*protect_from_scale_in\s*=\s*false$", ec2, re.M)
    assert "propagate_at_launch = true" in ec2
    assert "aws_autoscaling_policy" not in ec2
    assert "instance_market_options" not in ec2


def test_no_terraform_file_declares_a_standalone_lab_instance():
    for path in INFRA.glob("*.tf"):
        assert 'resource "aws_instance"' not in path.read_text(encoding="utf-8")


def test_the_autoscaling_group_pins_an_explicit_launch_template_version():
    block = code("ec2.tf").split('resource "aws_autoscaling_group" "lab"')[1]

    assert "aws_launch_template.lab[0].id" in block
    assert "aws_launch_template.lab[0].latest_version" in block
    assert "$Latest" not in block


def test_terraform_exposes_the_autoscaling_outputs():
    outputs = code("outputs.tf")

    for name in ("autoscaling_group_name", "autoscaling_group_arn", "launch_template_id",
                 "launch_template_version", "lab_instance_id"):
        assert f'output "{name}"' in outputs
    # El Instance ID es dinamico: lo mantiene el ASG, no el estado de Terraform.
    assert "DIN\u00c1MICO" in read("outputs.tf")


def test_automation_role_replaces_instances_only_through_auto_scaling():
    block = policy_document("automation")
    allow = "".join(b for b in block.split("statement {") if 'effect = "Allow"' in b)
    deny = "".join(b for b in block.split("statement {") if 'effect = "Deny"' in b)

    assert '"autoscaling:TerminateInstanceInAutoScalingGroup"' in allow
    for removed in ("ec2:RunInstances", "ec2:TerminateInstances", "ec2:CreateTags",
                    "iam:PassRole"):
        assert f'"{removed}"' not in allow
    assert '"ec2:RunInstances"' in deny
    assert '"ec2:TerminateInstances"' in deny


def test_application_role_cannot_mutate_auto_scaling_or_ec2():
    block = policy_document("application")
    deny = "".join(b for b in block.split("statement {") if 'effect = "Deny"' in b)

    for denied in ("ec2:RunInstances", "ec2:TerminateInstances",
                   "autoscaling:TerminateInstanceInAutoScalingGroup",
                   "autoscaling:SetDesiredCapacity",
                   "autoscaling:UpdateAutoScalingGroup"):
        assert f'"{denied}"' in deny


def test_terraform_state_and_tfvars_are_not_versioned():
    gitignore = (INFRA.parents[1] / ".gitignore").read_text(encoding="utf-8")

    for pattern in (".terraform/", "*.tfstate", "*.tfstate.*", "terraform.tfvars",
                    "crash.log"):
        assert pattern in gitignore


def test_no_credentials_are_committed_in_the_infrastructure():
    sources = [p for p in INFRA.rglob("*")
               if p.is_file() and p.suffix in {".tf", ".yaml", ".tftpl", ".md", ".example"}
               and ".terraform" not in p.parts]

    assert sources
    for path in sources:
        content = path.read_text(encoding="utf-8")
        assert "aws_secret_access_key" not in content
        assert not re.search(r"AKIA[0-9A-Z]{16}", content)
