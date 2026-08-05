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


def read(name: str) -> str:
    return (INFRA / name).read_text(encoding="utf-8")


def code(name: str) -> str:
    """Fichero sin comentarios: las aserciones miran el codigo, no la prosa."""
    return "\n".join(line for line in read(name).splitlines()
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

    assert names.index("Precheck") < names.index("InstallPatchBaseline")
    assert names.index("BranchOnApplicability") < names.index("InstallPatchBaseline")
    assert "FailAdvisoryNotApplicable" in names
    assert names.index("Postcheck") > names.index("InstallPatchBaseline")
    assert doc["outputs"] == [
        "Report.Advisory", "Report.PreviousKernel", "Report.CurrentKernel",
        "Report.RebootPerformed", "Report.PatchStatus", "Report.HealthStatus",
        "Report.InstanceId", "Report.CorrelationId"]


def test_reset_runbook_validates_tags_before_terminating():
    doc = document("MSR-ResetLabInstance.yaml")
    names = [step["name"] for step in doc["mainSteps"]]

    assert names.index("ValidateResettableTarget") < names.index("TerminateCurrentInstance")
    assert names.index("DescribeCurrentInstance") < names.index("TerminateCurrentInstance")
    assert names.index("LaunchReplacement") > names.index("TerminateCurrentInstance")
    assert set(doc["parameters"]) == {"CurrentInstanceId", "LaunchTemplateId",
                                      "LaunchTemplateVersion", "AutomationAssumeRole",
                                      "CorrelationId"}
    assert doc["outputs"] == [
        "Report.OldInstanceId", "Report.NewInstanceId", "Report.LogicalLabId",
        "Report.VulnerableState", "Report.HealthState", "Report.CorrelationId"]


def test_reset_runbook_recreates_from_a_fixed_launch_template_version():
    doc = document("MSR-ResetLabInstance.yaml")
    launch = next(s for s in doc["mainSteps"] if s["name"] == "LaunchReplacement")

    assert launch["inputs"]["Api"] == "RunInstances"
    template = launch["inputs"]["LaunchTemplate"]
    assert template["LaunchTemplateId"] == "{{ LaunchTemplateId }}"
    assert template["Version"] == "{{ LaunchTemplateVersion }}"
    assert "$Latest" not in str(launch)


def test_no_runbook_accepts_free_form_commands_from_the_caller():
    for name in ("MSR-PatchLinuxInstance.yaml", "MSR-ResetLabInstance.yaml"):
        parameters = document(name)["parameters"]
        forbidden = {"Commands", "Command", "Script", "SourceInfo", "Parameters",
                     "DocumentName", "Operation", "InstallOverrideList"}
        assert not forbidden & set(parameters)


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
