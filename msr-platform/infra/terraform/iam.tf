# ---------------------------------------------------------------------------
# 1) Rol de la instancia: sólo lo imprescindible para ser un managed node.
# ---------------------------------------------------------------------------

data "aws_iam_policy_document" "instance_trust" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "instance" {
  count = local.enabled

  name                 = "${local.name_prefix}-instance-role"
  description          = "MSR PoC: managed node de Systems Manager, sin permisos administrativos"
  assume_role_policy   = data.aws_iam_policy_document.instance_trust.json
  max_session_duration = 3600
  tags                 = local.common_tags
}

# AmazonSSMManagedInstanceCore es la política gestionada mínima que permite al
# agente registrarse como managed node (ssm:UpdateInstanceInformation, canales
# de mensajes y lectura del propio inventario). No concede EC2:RunInstances,
# ec2:TerminateInstances, ssm:StartAutomationExecution ni sts:AssumeRole.
resource "aws_iam_role_policy_attachment" "instance_ssm_core" {
  count = local.enabled

  role       = aws_iam_role.instance[0].name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# Barrera explícita: aunque una política gestionada cambiara, la instancia no
# puede iniciar automatizaciones, crear/terminar EC2 ni asumir otros roles.
data "aws_iam_policy_document" "instance_boundary" {
  statement {
    sid    = "DenyPrivilegedActions"
    effect = "Deny"

    actions = [
      "ssm:StartAutomationExecution",
      "ssm:StopAutomationExecution",
      "ec2:RunInstances",
      "ec2:TerminateInstances",
      "ec2:CreateTags",
      "sts:AssumeRole",
      "iam:*",
    ]

    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "instance_boundary" {
  count = local.enabled

  name   = "${local.name_prefix}-instance-deny"
  role   = aws_iam_role.instance[0].id
  policy = data.aws_iam_policy_document.instance_boundary.json
}

resource "aws_iam_instance_profile" "instance" {
  count = local.enabled

  name = "${local.name_prefix}-instance-profile"
  role = aws_iam_role.instance[0].name
  tags = local.common_tags
}

# ---------------------------------------------------------------------------
# 2) Rol de Automation: lo asume Systems Manager para ejecutar los runbooks.
# ---------------------------------------------------------------------------

data "aws_iam_policy_document" "automation_trust" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ssm.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [var.aws_account_id]
    }
  }
}

resource "aws_iam_role" "automation" {
  count = local.enabled

  name                 = "${local.name_prefix}-automation-role"
  description          = "MSR PoC: ejecución de los runbooks MSR-* sobre la instancia etiquetada"
  assume_role_policy   = data.aws_iam_policy_document.automation_trust.json
  max_session_duration = 3600
  tags                 = local.common_tags
}

data "aws_iam_policy_document" "automation" {
  # Lectura: describir instancias, tags e inventario de managed nodes.
  # ec2:DescribeInstances y ssm:Describe* no admiten permisos a nivel de
  # recurso ni condiciones por tag (limitación documentada de la API).
  statement {
    sid    = "ReadOnlyDiscovery"
    effect = "Allow"

    actions = [
      "ec2:DescribeInstances",
      "ec2:DescribeInstanceStatus",
      "ec2:DescribeTags",
      "ec2:DescribeImages",
      "ec2:DescribeLaunchTemplates",
      "ec2:DescribeLaunchTemplateVersions",
      "ssm:DescribeInstanceInformation",
      "ssm:DescribeInstancePatchStates",
      "ssm:DescribeInstancePatches",
      "ssm:GetCommandInvocation",
      "ssm:ListCommandInvocations",
      "ssm:ListCommands",
      "ssm:DescribeAutomationExecutions",
      "ssm:DescribeAutomationStepExecutions",
      "ssm:GetAutomationExecution",
      "ssm:GetPatchBaseline",
      "ssm:DescribePatchGroups",
      # Auto Scaling no admite permisos a nivel de recurso en sus Describe*
      # (limitación documentada de la API): el filtrado real lo hace el runbook,
      # que compara el nombre del ASG con el fijado por IaC.
      "autoscaling:DescribeAutoScalingGroups",
      "autoscaling:DescribeAutoScalingInstances",
    ]

    resources = ["*"]
  }

  # Ejecución de los únicos documentos Command necesarios.
  statement {
    sid    = "RunApprovedCommandDocuments"
    effect = "Allow"

    actions = ["ssm:SendCommand"]

    resources = [
      "arn:aws:ssm:${var.aws_region}::document/AWS-RunPatchBaseline",
      "arn:aws:ssm:${var.aws_region}::document/AWS-RunShellScript",
    ]
  }

  # ...y sólo contra la instancia del laboratorio.
  statement {
    sid    = "RunCommandsOnLabInstanceOnly"
    effect = "Allow"

    actions   = ["ssm:SendCommand"]
    resources = ["arn:aws:ec2:${var.aws_region}:${var.aws_account_id}:instance/*"]

    dynamic "condition" {
      for_each = local.lab_required_tags

      content {
        test     = "StringEquals"
        variable = "ssm:resourceTag/${condition.key}"
        values   = [condition.value]
      }
    }
  }

  # Reinicio exclusivamente de la instancia del laboratorio. La sustitución ya no
  # la hace este rol con ec2:TerminateInstances, sino el Auto Scaling Group.
  statement {
    sid    = "ManageLabInstanceLifecycle"
    effect = "Allow"

    actions = [
      "ec2:RebootInstances",
      "ec2:StopInstances",
      "ec2:StartInstances",
    ]

    resources = ["arn:aws:ec2:${var.aws_region}:${var.aws_account_id}:instance/*"]

    dynamic "condition" {
      for_each = local.lab_required_tags

      content {
        test     = "StringEquals"
        variable = "ec2:ResourceTag/${condition.key}"
        values   = [condition.value]
      }
    }
  }

  # Sustitución de la instancia: Auto Scaling termina la actual y crea la nueva
  # desde el Launch Template. Restringido al ARN del ASG del laboratorio.
  statement {
    sid    = "ReplaceLabInstanceThroughAutoScalingOnly"
    effect = "Allow"

    actions   = ["autoscaling:TerminateInstanceInAutoScalingGroup"]
    resources = [try(aws_autoscaling_group.lab[0].arn, "*")]
  }

  # Prohibiciones explícitas: ni crear ni terminar instancias directamente.
  statement {
    sid    = "DenyDirectInstanceLifecycleAndIam"
    effect = "Deny"

    actions = [
      "ec2:RunInstances",
      "ec2:TerminateInstances",
      "iam:CreateRole",
      "iam:CreatePolicy",
      "iam:AttachRolePolicy",
      "iam:PutRolePolicy",
      "iam:UpdateAssumeRolePolicy",
    ]

    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "automation" {
  count = local.enabled

  name   = "${local.name_prefix}-automation-policy"
  role   = aws_iam_role.automation[0].id
  policy = data.aws_iam_policy_document.automation.json
}

# ---------------------------------------------------------------------------
# 3) Rol de la aplicación (control plane): lo asume el backend vía STS.
# ---------------------------------------------------------------------------

data "aws_iam_policy_document" "application_trust" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "AWS"
      identifiers = [var.operator_role_arn]
    }
  }
}

resource "aws_iam_role" "application" {
  count = local.enabled

  name                 = "msr-poc-application-role"
  description          = "MSR PoC: control plane; sólo inicia los runbooks MSR-* y consulta estado"
  assume_role_policy   = data.aws_iam_policy_document.application_trust.json
  max_session_duration = 3600
  tags                 = local.common_tags
}

data "aws_iam_policy_document" "application" {
  statement {
    sid    = "ReadOnlyDiscovery"
    effect = "Allow"

    actions = [
      "ec2:DescribeInstances",
      "ec2:DescribeInstanceStatus",
      "ec2:DescribeTags",
      "ssm:DescribeInstanceInformation",
      "ssm:DescribeInstancePatchStates",
      "ssm:DescribeDocument",
      "ssm:GetAutomationExecution",
      "ssm:DescribeAutomationExecutions",
      "ssm:DescribeAutomationStepExecutions",
      # Sólo lectura: confirmar que la instancia resuelta pertenece al ASG
      # esperado. Auto Scaling no admite resource-level en sus Describe*.
      "autoscaling:DescribeAutoScalingGroups",
      "autoscaling:DescribeAutoScalingInstances",
    ]

    resources = ["*"]
  }

  # Sólo los dos runbooks propios: nunca AWS-RunShellScript ni documentos
  # arbitrarios, y nunca `ssm:SendCommand`.
  statement {
    sid    = "StartOwnAutomationRunbooksOnly"
    effect = "Allow"

    actions = ["ssm:StartAutomationExecution"]

    resources = [
      "arn:aws:ssm:${var.aws_region}:${var.aws_account_id}:automation-definition/${var.patch_runbook_name}:*",
      "arn:aws:ssm:${var.aws_region}:${var.aws_account_id}:automation-definition/${var.reset_runbook_name}:*",
    ]
  }

  statement {
    sid    = "StopOwnAutomationExecutions"
    effect = "Allow"

    actions   = ["ssm:StopAutomationExecution"]
    resources = ["arn:aws:ssm:${var.aws_region}:${var.aws_account_id}:automation-execution/*"]
  }

  statement {
    sid    = "PassAutomationRoleOnly"
    effect = "Allow"

    actions   = ["iam:PassRole"]
    resources = [try(aws_iam_role.automation[0].arn, "*")]

    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["ssm.amazonaws.com"]
    }
  }

  statement {
    sid    = "DenyDirectExecutionAndIam"
    effect = "Deny"

    actions = [
      "ssm:SendCommand",
      "ec2:RunInstances",
      "ec2:TerminateInstances",
      # El control plane nunca toca Auto Scaling: sólo inicia el runbook.
      "autoscaling:TerminateInstanceInAutoScalingGroup",
      "autoscaling:SetDesiredCapacity",
      "autoscaling:UpdateAutoScalingGroup",
      "iam:*",
    ]

    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "application" {
  count = local.enabled

  name   = "msr-poc-application-policy"
  role   = aws_iam_role.application[0].id
  policy = data.aws_iam_policy_document.application.json
}
