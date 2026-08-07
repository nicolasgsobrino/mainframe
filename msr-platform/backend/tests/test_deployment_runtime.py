"""Runtime desplegado: contenedor, ECS Fargate e identidad de workload.

Comprobaciones estáticas sobre `Dockerfile`, `.dockerignore` y la IaC del
runtime. Ningún test ejecuta Docker, Terraform ni contacta con AWS.
"""
from __future__ import annotations

import pathlib

import pytest

PLATFORM = pathlib.Path(__file__).resolve().parents[2]
INFRA = PLATFORM / "infra" / "terraform"

CREDENTIAL_MARKERS = ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN",
                      "aws_access_key_id", "aws_secret_access_key", "aws configure",
                      "aws login", "aws sso login")


def read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def code(path: pathlib.Path) -> str:
    """Fichero sin comentarios: las aserciones miran el código, no la prosa."""
    return "\n".join(line for line in read(path).splitlines()
                     if not line.lstrip().startswith("#"))


DOCKERFILE = PLATFORM / "Dockerfile"
DOCKERIGNORE = PLATFORM / ".dockerignore"
ECS = INFRA / "backend_ecs.tf"
IAM = INFRA / "backend_iam.tf"


# --- contenedor --------------------------------------------------------------

def test_the_image_serves_the_spa_from_the_backend():
    dockerfile = code(DOCKERFILE)

    assert "npm run build" in dockerfile
    # `app.main` monta `backend/static`: un solo origen para API y SPA.
    assert "COPY --from=frontend /build/dist ./static" in dockerfile
    assert "uvicorn" in dockerfile
    assert "app.main:app" in dockerfile


def test_the_image_runs_as_a_non_root_user_and_exposes_a_health_check():
    dockerfile = code(DOCKERFILE)

    assert "USER 10001" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "/api/health" in dockerfile


def test_the_image_carries_no_aws_credentials():
    dockerfile = code(DOCKERFILE)

    for marker in CREDENTIAL_MARKERS:
        assert marker not in dockerfile, marker
    # El contexto de build nunca incluye ficheros de entorno reales.
    ignored = read(DOCKERIGNORE)
    assert ".env" in ignored
    assert "backend/static" in ignored


def test_the_hook_is_a_module_of_the_same_image():
    """Un solo artefacto: el servicio y el hook comparten imagen y código."""
    assert (PLATFORM / "backend" / "app" / "lab_hook.py").is_file()
    assert "app.lab_hook" in read(DOCKERFILE)


# --- ECS Fargate -------------------------------------------------------------

def test_the_backend_runs_on_fargate_and_never_on_the_lab_instance():
    ecs = code(ECS)

    assert 'requires_compatibilities = ["FARGATE"]' in ecs
    assert 'launch_type     = "FARGATE"' in ecs
    assert 'network_mode             = "awsvpc"' in ecs
    # La EC2 del laboratorio se termina en cada reset: no puede alojar la app.
    assert "aws_instance" not in ecs


def test_the_task_receives_the_safe_deployed_defaults():
    ecs = code(ECS)

    assert 'MSR_PATCH_PROVIDER           = "aws-automation"' in ecs
    assert 'MSR_RESTORE_PROVIDER         = "aws-automation"' in ecs
    assert 'MSR_LAB_RECONCILE_ON_STARTUP = "false"' in ecs
    assert "MSR_DRY_RUN                  = tostring(var.backend_dry_run)" in ecs


def test_the_task_gets_its_credentials_only_from_the_task_role():
    ecs = code(ECS)

    for marker in CREDENTIAL_MARKERS:
        assert marker not in ecs, marker
    # Sin perfil y sin rol que asumir: boto3 usa el endpoint de metadatos.
    assert 'MSR_AWS_PROFILE  = ""' in ecs
    assert 'MSR_AWS_ROLE_ARN = ""' in ecs
    # Nada que inyectar desde Secrets Manager o SSM Parameter Store.
    assert "secrets" not in ecs
    assert "aws_secretsmanager" not in ecs
    assert "assign_public_ip = false" in ecs


def test_the_task_definition_fails_without_a_workload_role():
    ecs = code(ECS)

    assert "precondition" in ecs
    assert "local.backend_task_role_arn" in ecs
    assert "backend_execution_role_arn" in ecs


def test_the_runtime_is_disabled_by_default():
    variables = code(INFRA / "variables.tf")

    for variable in ("enable_backend_service", "create_backend_task_role"):
        block = variables.split(f'variable "{variable}"')[1].split("\nvariable ")[0]
        assert "default     = false" in block, variable


# --- identidad de workload ---------------------------------------------------

def test_the_task_role_trusts_only_ecs_in_this_account_and_region():
    iam = code(IAM)

    assert 'Service = "ecs-tasks.amazonaws.com"' in iam
    assert '"aws:SourceAccount" = var.aws_account_id' in iam
    assert '"aws:SourceArn" = "arn:aws:ecs:${var.aws_region}:${var.aws_account_id}:*"' in iam


def test_the_workload_role_needs_no_pass_role_and_no_service_role():
    iam = code(IAM)

    # Opción B: la Automation corre en el contexto del llamante.
    assert "iam:PassRole" not in iam
    assert "ssm.amazonaws.com" not in iam
    assert "AutomationAssumeRole" not in iam


def test_the_workload_policy_covers_every_runbook_step():
    iam = code(IAM)

    for action in ("ssm:StartAutomationExecution", "ssm:StopAutomationExecution",
                   "ssm:GetAutomationExecution", "ssm:DescribeAutomationStepExecutions",
                   "ssm:DescribeDocument", "ssm:SendCommand", "ssm:GetCommandInvocation",
                   "ssm:DescribeInstanceInformation", "ssm:DescribeInstancePatchStates",
                   "ssm:DescribeInstancePatches", "ssm:ListInventoryEntries",
                   "ec2:DescribeInstances", "ec2:DescribeInstanceStatus",
                   "autoscaling:DescribeAutoScalingGroups",
                   "autoscaling:DescribeAutoScalingInstances",
                   "autoscaling:TerminateInstanceInAutoScalingGroup"):
        assert action in iam, action


@pytest.mark.parametrize("action", ["ec2:TerminateInstances", "ec2:RunInstances",
                                    "ssm:CreateDocument", "ssm:UpdateDocument",
                                    "ssm:DeleteDocument", "iam:PassRole", "iam:CreateRole",
                                    "iam:AttachRolePolicy", "iam:PutRolePolicy",
                                    "autoscaling:UpdateAutoScalingGroup",
                                    "autoscaling:SetDesiredCapacity"])
def test_the_workload_policy_grants_no_destructive_shortcut(action):
    """La sustitución sólo puede ocurrir a través del Auto Scaling Group."""
    assert action not in code(IAM)


def test_the_hook_is_the_only_authorized_path_to_a_reset():
    ecs = code(ECS)
    outputs = code(INFRA / "outputs.tf")

    # El servicio no reconcilia: el hook se lanza una vez por release.
    assert 'MSR_LAB_RECONCILE_ON_STARTUP = "false"' in ecs
    assert '"app.lab_hook"' in outputs
    assert '"--confirm"' in outputs


# --- registro de imágenes, exposición y lock ---------------------------------

ECR = INFRA / "backend_ecr.tf"
ALB = INFRA / "backend_alb.tf"
LOCKS = INFRA / "backend_locks.tf"
DEPLOY_WORKFLOW = PLATFORM.parent / ".github" / "workflows" / "msr-platform-deploy.yml"


def test_the_image_registry_is_private_scanned_and_encrypted():
    ecr = code(ECR)

    assert "scan_on_push = true" in ecr
    assert "encryption_configuration" in ecr
    assert 'image_tag_mutability = "IMMUTABLE"' in ecr
    assert "countType   = \"imageCountMoreThan\"" in ecr
    # Nada público: ni repositorio público ni política de repositorio abierta.
    assert "aws_ecrpublic" not in ecr
    assert "aws_ecr_repository_policy" not in ecr


def test_the_exposure_is_an_internal_alb_without_cloudfront_or_tunnels():
    alb = code(ALB)
    variables = code(INFRA / "variables.tf")

    block = variables.split('variable "backend_alb_internal"')[1].split("\nvariable ")[0]
    assert "default     = true" in block
    assert 'target_type = "ip"' in alb
    assert "path                = local.backend_health_path" in alb
    assert 'backend_health_path    = "/api/health"' in alb
    assert "aws_cloudfront" not in alb
    assert "cloudflared" not in alb and "ngrok" not in alb


def test_the_backend_accepts_traffic_only_from_the_load_balancer():
    alb = code(ALB)

    ingress = alb.split('resource "aws_vpc_security_group_ingress_rule" "backend_from_alb"')[1]
    ingress = ingress.split("\nresource ")[0]
    assert "referenced_security_group_id = aws_security_group.backend_alb[0].id" in ingress
    assert "cidr_ipv4" not in ingress


def test_the_lab_lock_lives_in_one_dynamodb_table_with_ttl():
    locks = code(LOCKS)

    assert 'hash_key     = "lab_id"' in locks
    assert 'attribute_name = "expires_at"' in locks
    assert "server_side_encryption" in locks
    assert locks.count('resource "aws_dynamodb_table"') == 1


def test_the_lock_permissions_are_scoped_to_the_lock_table():
    iam = code(IAM)

    for action in ("dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:DeleteItem"):
        assert action in iam, action
    assert "local.backend_lock_table_arn" in iam
    for denied in ("dynamodb:*", "dynamodb:Scan", "dynamodb:DeleteTable",
                   "dynamodb:UpdateItem", "dynamodb:UpdateTable"):
        assert denied not in iam, denied


def test_ecr_and_the_alb_and_the_lock_table_are_disabled_by_default():
    variables = code(INFRA / "variables.tf")

    for variable in ("enable_backend_ecr", "enable_backend_alb",
                     "enable_backend_lock_table"):
        block = variables.split(f'variable "{variable}"')[1].split("\nvariable ")[0]
        assert "default     = false" in block, variable


def test_the_release_pushes_to_ecr_with_oidc_and_no_static_credentials():
    workflow = read(DEPLOY_WORKFLOW)

    assert "id-token: write" in workflow
    assert "aws-actions/configure-aws-credentials@v4" in workflow
    assert "role-to-assume" in workflow
    assert "aws-actions/amazon-ecr-login@v2" in workflow
    assert "docker push" in workflow
    assert "aws ecs register-task-definition" in workflow
    # Serialización del release: un único despliegue y un único hook.
    assert "concurrency:" in workflow
    for marker in CREDENTIAL_MARKERS:
        assert marker not in workflow, marker
