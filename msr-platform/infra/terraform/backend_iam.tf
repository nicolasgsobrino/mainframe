# Identidad de workload del backend desplegado (opción B: contexto del llamante).
#
# Los runbooks no declaran `assumeRole` y no existe service role de Automation:
# por tanto TODOS los permisos que necesitan los pasos de la Automation deben
# estar en el rol de la task de ECS que inicia la ejecución. No hay `iam:PassRole`.
#
# La creación de IAM es opcional porque la cuenta corporativa puede denegarla:
#   create_backend_task_role = true   → Terraform crea el rol y su política.
#   create_backend_task_role = false  → se consume backend_task_role_arn, ya
#                                       aprovisionado por el equipo de cloud con
#                                       las políticas publicadas en los outputs
#                                       backend_task_role_trust_policy_json y
#                                       backend_task_role_permission_policy_json.

locals {
  backend_role_name           = "${local.name_prefix}-backend-task"
  backend_execution_role_name = "${local.name_prefix}-backend-exec"

  # ARN determinista del rol creado por Terraform: permite resolver el ARN
  # efectivo sin depender de un valor conocido sólo después del apply.
  backend_task_role_arn_created = (
    "arn:aws:iam::${var.aws_account_id}:role/${local.backend_role_name}"
  )

  # ARN efectivo: creado por Terraform o preaprovisionado. Nunca ambos.
  backend_task_role_arn = (
    var.create_backend_task_role
    ? local.backend_task_role_arn_created
    : var.backend_task_role_arn
  )
  backend_execution_role_arn = (
    var.create_backend_task_role
    ? "arn:aws:iam::${var.aws_account_id}:role/${local.backend_execution_role_name}"
    : var.backend_execution_role_arn
  )

  backend_iam_enabled = var.create_backend_task_role ? local.backend_enabled : 0

  # --- Trust policy del Task Role -----------------------------------------
  # Sólo ECS puede asumirlo, sólo desde esta cuenta y sólo para tasks de esta
  # cuenta/región: sin comodines de cuenta ni de servicio.
  backend_task_trust_policy = {
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = {
        StringEquals = { "aws:SourceAccount" = var.aws_account_id }
        ArnLike = {
          "aws:SourceArn" = "arn:aws:ecs:${var.aws_region}:${var.aws_account_id}:*"
        }
      }
    }]
  }

  # --- ARNs sobre los que opera el backend --------------------------------
  backend_runbook_arns = [
    "arn:aws:ssm:${var.aws_region}:${var.aws_account_id}:automation-definition/${var.patch_runbook_name}",
    "arn:aws:ssm:${var.aws_region}:${var.aws_account_id}:automation-definition/${var.patch_runbook_name}:*",
    "arn:aws:ssm:${var.aws_region}:${var.aws_account_id}:automation-definition/${var.reset_runbook_name}",
    "arn:aws:ssm:${var.aws_region}:${var.aws_account_id}:automation-definition/${var.reset_runbook_name}:*",
  ]
  backend_automation_execution_arn = (
    "arn:aws:ssm:${var.aws_region}:${var.aws_account_id}:automation-execution/*"
  )
  backend_asg_arn = (
    "arn:aws:autoscaling:${var.aws_region}:${var.aws_account_id}:autoScalingGroup:*:autoScalingGroupName/${local.autoscaling_group_name}"
  )
  backend_command_document_arns = [
    "arn:aws:ssm:${var.aws_region}::document/AWS-RunPatchBaseline",
    "arn:aws:ssm:${var.aws_region}::document/AWS-RunShellScript",
  ]
  backend_instance_arn = "arn:aws:ec2:${var.aws_region}:${var.aws_account_id}:instance/*"

  # --- Política de permisos del Task Role ---------------------------------
  # Mínimo estricto para: iniciar/parar sólo los dos runbooks de la PoC,
  # seguirlos, ejecutar sus pasos (SendCommand sobre la instancia etiquetada y
  # sustitución vía Auto Scaling) y leer la evidencia. Las acciones `Describe*`
  # de EC2/Auto Scaling/SSM no admiten ARN de recurso y se acotan por región.
  backend_task_permission_policy = {
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "StartOnlyTheTwoPocRunbooks"
        Effect   = "Allow"
        Action   = ["ssm:StartAutomationExecution"]
        Resource = local.backend_runbook_arns
      },
      {
        Sid      = "ControlAndReadOwnAutomationExecutions"
        Effect   = "Allow"
        Action   = ["ssm:StopAutomationExecution", "ssm:GetAutomationExecution"]
        Resource = local.backend_automation_execution_arn
      },
      {
        Sid    = "ReadAutomationMetadata"
        Effect = "Allow"
        Action = [
          "ssm:DescribeAutomationExecutions",
          "ssm:DescribeAutomationStepExecutions",
          "ssm:DescribeDocument",
        ]
        Resource = "*"
        Condition = {
          StringEquals = { "aws:RequestedRegion" = var.aws_region }
        }
      },
      {
        # `SendCommand` autoriza documento e instancia por separado: la condición
        # de tags sólo puede aplicarse al recurso que lleva los tags.
        Sid      = "RunOnlyTheTwoAwsOwnedCommandDocuments"
        Effect   = "Allow"
        Action   = ["ssm:SendCommand"]
        Resource = local.backend_command_document_arns
      },
      {
        Sid      = "SendCommandOnlyToTheTaggedLabInstance"
        Effect   = "Allow"
        Action   = ["ssm:SendCommand"]
        Resource = local.backend_instance_arn
        Condition = {
          StringEquals = {
            "ssm:resourceTag/msr-poc"    = "true"
            "ssm:resourceTag/msr-lab-id" = var.lab_id
          }
        }
      },
      {
        Sid      = "ReadCommandResults"
        Effect   = "Allow"
        Action   = ["ssm:GetCommandInvocation", "ssm:ListCommandInvocations", "ssm:ListCommands"]
        Resource = "*"
        Condition = {
          StringEquals = { "aws:RequestedRegion" = var.aws_region }
        }
      },
      {
        Sid    = "ReadPatchAndInventoryEvidence"
        Effect = "Allow"
        Action = [
          "ssm:DescribeInstanceInformation",
          "ssm:DescribeInstancePatchStates",
          "ssm:DescribeInstancePatches",
          "ssm:ListInventoryEntries",
        ]
        Resource = "*"
        Condition = {
          StringEquals = { "aws:RequestedRegion" = var.aws_region }
        }
      },
      {
        Sid    = "DiscoverTheLabByTags"
        Effect = "Allow"
        Action = [
          "ec2:DescribeInstances",
          "ec2:DescribeInstanceStatus",
          "ec2:DescribeTags",
          "autoscaling:DescribeAutoScalingGroups",
          "autoscaling:DescribeAutoScalingInstances",
        ]
        Resource = "*"
        Condition = {
          StringEquals = { "aws:RequestedRegion" = var.aws_region }
        }
      },
      {
        Sid      = "ReplaceTheLabInstanceOnlyThroughItsAutoScalingGroup"
        Effect   = "Allow"
        Action   = ["autoscaling:TerminateInstanceInAutoScalingGroup"]
        Resource = local.backend_asg_arn
      },
      {
        # Lock de operación del laboratorio: sólo las acciones que el backend
        # ejecuta realmente (tomar, leer y liberar) y sólo sobre la tabla de
        # locks. Sin `dynamodb:UpdateItem` —la renovación reescribe el ítem
        # completo con `PutItem` condicional— y nunca `dynamodb:*`.
        Sid    = "SerializeLabMutationsWithTheLockTable"
        Effect = "Allow"
        Action = [
          "dynamodb:DeleteItem",
          "dynamodb:GetItem",
          "dynamodb:PutItem",
        ]
        Resource = local.backend_lock_table_arn
      },
    ]
  }
}

# --- Rol de la task (identidad de la aplicación) -----------------------------
resource "aws_iam_role" "backend_task" {
  count = local.backend_iam_enabled

  name                 = local.backend_role_name
  description          = "Identidad de workload del backend MSR en ECS Fargate (inicia la Automation)"
  assume_role_policy   = jsonencode(local.backend_task_trust_policy)
  max_session_duration = 3600

  tags = merge(local.common_tags, { Name = local.backend_role_name })
}

resource "aws_iam_role_policy" "backend_task" {
  count = local.backend_iam_enabled

  name   = "${local.backend_role_name}-policy"
  role   = aws_iam_role.backend_task[0].id
  policy = jsonencode(local.backend_task_permission_policy)
}

# --- Rol de ejecución de la task (agente de ECS: imagen y logs) --------------
# No es la identidad de la aplicación: lo usa el agente para descargar la imagen
# de ECR y escribir en CloudWatch Logs. El código nunca obtiene sus credenciales.
resource "aws_iam_role" "backend_execution" {
  count = local.backend_iam_enabled

  name        = local.backend_execution_role_name
  description = "Task execution role del backend MSR (pull de ECR y CloudWatch Logs)"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = {
        StringEquals = { "aws:SourceAccount" = var.aws_account_id }
        ArnLike = {
          "aws:SourceArn" = "arn:aws:ecs:${var.aws_region}:${var.aws_account_id}:*"
        }
      }
    }]
  })

  tags = merge(local.common_tags, { Name = local.backend_execution_role_name })
}

resource "aws_iam_role_policy_attachment" "backend_execution" {
  count = local.backend_iam_enabled

  role       = aws_iam_role.backend_execution[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}
