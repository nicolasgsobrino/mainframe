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
    for filename in ("ec2.tf", "networking.tf", "patching.tf",
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


def test_terraform_does_not_manage_any_iam_resource():
    """La cuenta deniega iam:PutRolePolicy/AttachRolePolicy/UpdateAssumeRolePolicy."""
    assert not (INFRA / "iam.tf").exists()
    for path in INFRA.glob("*.tf"):
        content = path.read_text(encoding="utf-8")
        assert not re.search(r'^resource "aws_iam_', content, re.M), path.name
        assert 'data "aws_iam_policy_document"' not in content, path.name


def test_the_instance_reuses_the_existing_corporate_instance_profile():
    data_tf = code("data.tf")
    ec2 = code("ec2.tf")

    assert 'data "aws_iam_instance_profile" "existing"' in data_tf
    assert "name  = var.existing_instance_profile_name" in data_tf
    assert "arn = data.aws_iam_instance_profile.existing[0].arn" in ec2
    # Sólo lectura: ni tags ni ningún otro atributo del profile se gestionan.
    profile_block = data_tf.split('data "aws_iam_instance_profile" "existing"')[1].split("}")[0]
    assert "tags" not in profile_block


def test_the_existing_instance_profile_is_mandatory_in_real_mode():
    variables = code("variables.tf")
    ec2 = code("ec2.tf")

    for name in ("existing_instance_profile_name", "existing_instance_profile_role_name"):
        assert f'variable "{name}"' in variables
    assert 'var.existing_instance_profile_name != ""' in ec2
    assert 'var.existing_instance_profile_role_name != ""' in ec2
    # El profile debe contener el rol esperado y pertenecer a la cuenta.
    assert ("data.aws_iam_instance_profile.existing[0].role_name == "
            "var.existing_instance_profile_role_name") in ec2
    assert 'instance-profile/${var.existing_instance_profile_name}' in ec2


def test_the_patch_group_tag_key_has_no_space():
    locals_tf = code("locals.tf")

    assert '"PatchGroup" = var.patch_group' in locals_tf
    sources = [p for p in INFRA.rglob("*")
               if p.is_file() and p.suffix in {".tf", ".yaml", ".tftpl", ".example"}
               and ".terraform" not in p.parts]
    sources += [pathlib.Path(__file__).resolve().parents[1] / "app" / "seed.py"]
    for path in sources:
        assert "Patch Group" not in path.read_text(encoding="utf-8"), path.name


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
    assert names.index("WaitForReplacementInService") > terminate
    assert names.index("ValidateReplacementInstance") > terminate
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


def test_the_outputs_describe_the_credential_model_without_roles():
    outputs = code("outputs.tf")

    for removed in ("application_role_arn", "automation_role_arn", "automation_trust_policy"):
        assert f'output "{removed}"' not in outputs
    for added in ("instance_profile_name", "instance_profile_role_name",
                  "backend_credential_mode", "automation_credential_mode"):
        assert f'output "{added}"' in outputs
    assert 'value       = "ambient-caller"' in outputs
    assert 'value       = "caller-context"' in outputs
    assert 'MSR_AWS_ROLE_ARN               = ""' in outputs
    assert 'MSR_AUTOMATION_ASSUME_ROLE_ARN = ""' in outputs


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


# --- Fase 2.2: advisory vigente, releasever explícito y kernel corregido ----

ADVISORY = "ALAS2023-2026-1924"
RELEASEVER = "2023.12.20260706"
FIXED_KERNEL = "6.1.176-220.358.amzn2023.x86_64"
REPO_ROOT = INFRA.parents[1]
RETIRED_ADVISORY = "ALAS2023" + "-2026-1651"


def test_the_retired_advisory_is_gone_from_code_terraform_and_seeds():
    """El advisory antiguo se corrigió antes de la AMI base: no puede quedar."""
    sources = list((REPO_ROOT / "backend" / "app").rglob("*.py"))
    sources += [p for p in INFRA.rglob("*")
                if p.is_file() and p.suffix in {".tf", ".tftpl", ".yaml", ".example"}
                and ".terraform" not in p.parts]
    sources.append(REPO_ROOT / ".env.example")

    assert sources
    for path in sources:
        assert RETIRED_ADVISORY not in path.read_text(encoding="utf-8"), path


def test_the_candidate_advisory_is_the_only_one_approved():
    variables = read("variables.tf")
    block = variables.split('variable "candidate_advisory_id"')[1]

    assert f'default     = "{ADVISORY}"' in block
    assert "approved_patches                     = [var.candidate_advisory_id]" in code("patching.tf")
    assert 'rejected_patches_action              = "ALLOW_AS_DEPENDENCY"' in code("patching.tf")
    assert "approval_rules" not in code("patching.tf")


def test_candidate_releasever_exists_and_is_validated():
    block = read("variables.tf").split('variable "candidate_releasever"')[1]

    assert f'default     = "{RELEASEVER}"' in block
    # Formato YYYY.NN.YYYYMMDD comprobado por Terraform, no sólo documentado.
    assert r"^[0-9]{4}\\.[0-9]{2}\\.[0-9]{8}$" in block


def test_the_base_ami_release_is_older_than_the_fix():
    """Fase 2.3: la relación temporal se deriva de la fecha, no del texto."""
    locals_tf = code("locals.tf")

    assert "tonumber(split(\".\", var.source_ami_release)[2])" in locals_tf
    assert "tonumber(split(\".\", var.candidate_releasever)[2])" in locals_tf
    assert "local.source_ami_release_date < local.candidate_release_date" in locals_tf
    assert "condition     = local.ami_release_precedes_fix" in code("ec2.tf")
    assert read("variables.tf").split('variable "source_ami_release"')[1].count(
        '"2023.11.20260509.0"') == 1


def test_no_terraform_expression_compares_strings_with_relational_operators():
    """Terraform rechaza `<`/`>` entre strings: rompió el primer plan real."""
    for path in INFRA.rglob("*.tf"):
        if ".terraform" in path.parts:
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            expression = line.split("#")[0]
            comparisons = re.findall(r"(\S+)\s*(?:<|>|<=|>=)\s*(\S+)", expression)
            for left, right in comparisons:
                operands = f"{left} {right}"
                assert "var.source_ami_release" not in operands, line
                assert "var.candidate_releasever" not in operands, line
                assert "substr(" not in operands, line


def test_terraform_tests_cover_the_release_order_with_a_mocked_provider():
    tests = list((INFRA / "tests").glob("*.tftest.hcl"))
    bodies = {p.name: p.read_text(encoding="utf-8") for p in tests}

    assert {"release_order.tftest.hcl", "enabled_plan.tftest.hcl"} <= set(bodies)
    for body in bodies.values():
        assert 'mock_provider "aws"' in body
        # Nada de credenciales ni de recursos reales en los tests.
        assert "access_key" not in body
        assert "command = apply" not in body

    enabled = bodies["enabled_plan.tftest.hcl"]
    assert "enable_real_resources               = true" in enabled
    assert "expect_failures = [aws_autoscaling_group.lab]" in enabled
    assert "length(output.estimated_resource_summary.resources) == 10" in enabled
    assert 'startswith(name, "aws_iam_")' in enabled


def test_the_releasever_reaches_the_backend_and_the_documents():
    locals_tf = code("locals.tf")

    assert re.search(r"MSR_PATCH_RELEASEVER\s+= var\.candidate_releasever", locals_tf)
    assert re.search(r"MSR_PATCH_EXPECTED_FIXED_KERNEL\s+= var\.expected_fixed_kernel",
                     locals_tf)
    assert re.search(r"candidate_releasever\s+= var\.candidate_releasever",
                     code("automation-documents.tf"))
    assert "candidate_releasever" in read("user-data.sh.tftpl")


@pytest.mark.parametrize("name", ["MSR-PatchLinuxInstance.yaml", "MSR-ResetLabInstance.yaml"])
def test_advisory_queries_always_pin_the_releasever(name):
    raw = document_source(name)

    queries = re.findall(r"dnf updateinfo list[^\n']+", raw)
    assert queries
    for query in queries:
        assert "--advisory ${candidate_advisory_id}" in query
        assert "--releasever ${candidate_releasever}" in query


@pytest.mark.parametrize("name", ["MSR-PatchLinuxInstance.yaml", "MSR-ResetLabInstance.yaml"])
def test_an_unreachable_repository_is_not_an_inapplicable_advisory(name):
    raw = document_source(name)

    assert "PATCH_REPOSITORY_UNREACHABLE" in raw
    assert "MSR_REPO_REACHABLE" in raw
    # Sin repositorio el resultado es `unknown`, nunca `false`.
    assert 'echo "MSR_REPO_REACHABLE=false"; echo "MSR_ADVISORY_APPLICABLE=unknown"' in raw
    assert "ADVISORY_NOT_APPLICABLE" != "PATCH_REPOSITORY_UNREACHABLE"


@pytest.mark.parametrize("name", ["MSR-PatchLinuxInstance.yaml", "MSR-ResetLabInstance.yaml"])
def test_kernel_versions_are_compared_with_sort_v_not_lexicographically(name):
    raw = document_source(name)

    assert "sort -V" in raw
    assert "MSR_KERNEL_ORDER" in raw
    assert "${expected_fixed_kernel}" in raw


def test_the_postcheck_requires_the_fixed_kernel():
    raw = document_source("MSR-PatchLinuxInstance.yaml")

    assert "KERNEL_OLDER_THAN_FIXED" in raw
    assert 'after["MSR_KERNEL_ORDER"] not in ("equal", "newer")' in raw
    # `unknown` no puede darse por bueno.
    assert 'after["MSR_ADVISORY_APPLICABLE"] != "false"' in raw


def test_the_precheck_requires_amazon_linux_and_a_vulnerable_kernel():
    raw = document_source("MSR-PatchLinuxInstance.yaml")

    assert 'values["MSR_OS_ID"].startswith("amzn-2023")' in raw
    assert "UNSUPPORTED_OPERATING_SYSTEM" in raw
    assert 'values["MSR_KERNEL_ORDER"] != "older"' in raw
    assert "KERNEL_ALREADY_FIXED" in raw
    # El advisory y el releasever comprobados son los renderizados por Terraform.
    assert "PRECHECK_CONTRACT_MISMATCH" in raw


@pytest.mark.parametrize("name", ["MSR-PatchLinuxInstance.yaml",
                                  "MSR-ResetLabInstance.yaml"])
def test_no_execute_script_step_exceeds_the_aws_limit(name):
    """AWS limita cada `aws:executeScript` a 600 s: no puede haber sondeos largos."""
    doc = document(name)
    raw = document_source(name)

    scripts = [s for s in doc["mainSteps"] if s["action"] == "aws:executeScript"]
    assert scripts
    for step in scripts:
        timeout = step.get("timeoutSeconds")
        assert timeout is not None, step["name"]
        assert timeout <= 600, (step["name"], timeout)

        source = step["inputs"]["Script"]
        assert "time.sleep" not in source, step["name"]
        # Ningún deadline interno puede superar el límite de la acción.
        for seconds in re.findall(r"time\.time\(\)\s*\+\s*([0-9]+)", source):
            assert int(seconds) <= 600, (step["name"], seconds)
        for seconds in re.findall(r"deadline\s*=\s*([0-9]+)", source):
            assert int(seconds) <= 600, (step["name"], seconds)

    # Las esperas largas son nativas de Automation, no scripts.
    for step in doc["mainSteps"]:
        if step.get("timeoutSeconds", 0) > 600:
            assert step["action"] in ("aws:waitForAwsResourceProperty",
                                      "aws:runCommand"), step["name"]
    assert "while time.time()" not in raw


def test_the_replacement_wait_is_native_and_validates_a_new_instance():
    doc = document("MSR-ResetLabInstance.yaml")
    steps = {s["name"]: s for s in doc["mainSteps"]}

    in_service = steps["WaitForReplacementInService"]
    assert in_service["action"] == "aws:waitForAwsResourceProperty"
    assert in_service["timeoutSeconds"] == 1800
    assert in_service["inputs"]["Service"] == "autoscaling"
    assert in_service["inputs"]["Api"] == "DescribeAutoScalingGroups"
    assert in_service["inputs"]["DesiredValues"] == ["InService"]

    healthy = steps["WaitForReplacementHealthy"]
    assert healthy["action"] == "aws:waitForAwsResourceProperty"
    assert healthy["inputs"]["PropertySelector"].endswith("HealthStatus")
    assert healthy["inputs"]["DesiredValues"] == ["Healthy"]

    describe = steps["DescribeReplacementInstance"]
    assert describe["action"] == "aws:executeAwsApi"
    assert describe["inputs"]["Api"] == "DescribeAutoScalingGroups"

    validate = steps["ValidateReplacementInstance"]
    assert validate["action"] == "aws:executeScript"
    assert validate["timeoutSeconds"] <= 120
    script = validate["inputs"]["Script"]
    # Exactamente una instancia, distinta de la anterior, InService y Healthy.
    assert "RESET_ASG_INSTANCE_COUNT_UNEXPECTED" in script
    assert 'new["InstanceId"] == old' in script
    assert "RESET_REPLACEMENT_NOT_CREATED" in script
    assert "RESET_REPLACEMENT_NOT_IN_SERVICE" in script
    assert "RESET_REPLACEMENT_NOT_HEALTHY" in script
    assert [o["Name"] for o in validate["outputs"]] == ["NewInstanceId"]

    # Los pasos posteriores consumen el nuevo output, no el antiguo.
    raw = document_source("MSR-ResetLabInstance.yaml")
    assert "WaitForReplacementInstance.NewInstanceId" not in raw
    assert raw.count("ValidateReplacementInstance.NewInstanceId") >= 5


@pytest.mark.parametrize("name", ["MSR-PatchLinuxInstance.yaml",
                                  "MSR-ResetLabInstance.yaml"])
def test_no_execute_script_calls_aws_apis(name):
    """Sin service role de Automation, los scripts sólo validan sus inputs."""
    doc = document(name)

    for step in doc["mainSteps"]:
        if step["action"] != "aws:executeScript":
            continue
        script = step["inputs"]["Script"]
        for forbidden in ("boto3", "botocore", ".client(", "import os", "urllib",
                          "subprocess"):
            assert forbidden not in script, (step["name"], forbidden)


@pytest.mark.parametrize("name", ["MSR-PatchLinuxInstance.yaml",
                                  "MSR-ResetLabInstance.yaml"])
def test_the_assume_role_parameter_is_optional_and_empty_by_default(name):
    doc = document(name)
    parameter = doc["parameters"]["AutomationAssumeRole"]

    assert parameter["default"] == ""
    # El patrón acepta el valor vacío: la Automation usa las credenciales del
    # iniciador cuando no hay rol configurado.
    assert parameter["allowedPattern"].startswith("^$|")


def test_the_reset_checks_advisory_and_kernel_not_only_the_ami():
    raw = document_source("MSR-ResetLabInstance.yaml")

    assert "RESET_AMI_UNVERIFIABLE" in raw
    assert "RESET_AMI_RELEASE_MISMATCH" in raw
    assert "RESET_TARGET_NOT_VULNERABLE" in raw
    assert "RESET_KERNEL_NOT_VULNERABLE" in raw
    assert 'values.get("MSR_KERNEL_ORDER") != "older"' in raw
