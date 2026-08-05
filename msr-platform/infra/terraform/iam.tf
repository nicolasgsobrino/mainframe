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

  # Reinicio y terminación exclusivamente de la instancia del laboratorio.
  statement {
    sid    = "ManageLabInstanceLifecycle"
    effect = "Allow"

    actions = [
      "ec2:RebootInstances",
      "ec2:StopInstances",
      "ec2:StartInstances",
      "ec2:TerminateInstances",
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

  # Creación de la instancia de repuesto: sólo desde el Launch Template y la
  # AMI permitidos, y sólo con los tags del laboratorio.
  statement {
    sid    = "RunInstancesFromLaunchTemplateOnly"
    effect = "Allow"

    actions = ["ec2:RunInstances"]

    resources = [
      "arn:aws:ec2:${var.aws_region}:${var.aws_account_id}:instance/*",
      "arn:aws:ec2:${var.aws_region}:${var.aws_account_id}:volume/*",
      "arn:aws:ec2:${var.aws_region}:${var.aws_account_id}:network-interface/*",
      "arn:aws:ec2:${var.aws_region}:${var.aws_account_id}:security-group/${try(aws_security_group.lab[0].id, "*")}",
      "arn:aws:ec2:${var.aws_region}:${var.aws_account_id}:subnet/${var.subnet_id}",
      "arn:aws:ec2:${var.aws_region}:${var.aws_account_id}:launch-template/${try(aws_launch_template.lab[0].id, "*")}",
      "arn:aws:ec2:${var.aws_region}::image/${var.source_ami_id}",
    ]
  }

  statement {
    sid    = "TagOnlyExpectedTags"
    effect = "Allow"

    actions   = ["ec2:CreateTags"]
    resources = ["arn:aws:ec2:${var.aws_region}:${var.aws_account_id}:*/*"]

    condition {
      test     = "StringEquals"
      variable = "ec2:CreateAction"
      values   = ["RunInstances"]
    }

    condition {
      test     = "ForAllValues:StringEquals"
      variable = "aws:TagKeys"
      values   = concat(keys(local.instance_tags), ["msr-managed-by"])
    }
  }

  # Pasar únicamente el instance profile del laboratorio.
  statement {
    sid    = "PassLabInstanceProfileOnly"
    effect = "Allow"

    actions   = ["iam:PassRole"]
    resources = [try(aws_iam_role.instance[0].arn, "*")]

    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["ec2.amazonaws.com"]
    }
  }

  # Prohibiciones explícitas.
  statement {
    sid    = "DenyIamAndArbitraryDocuments"
    effect = "Deny"

    actions = [
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
