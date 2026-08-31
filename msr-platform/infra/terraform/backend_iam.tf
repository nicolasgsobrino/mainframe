# Identidad de workload del backend desplegado (opción B: contexto del llamante).
#
# PARCIALMENTE SUPERSEDED (fase 2.9): la política de permisos sigue vigente —las
# llamadas a AWS no cambian—, pero el consumidor ya no es una task de ECS: la
# aplicación se aloja fuera de AWS y la identidad pasa a ser un rol federado por
# OIDC (`MSRExternalBackendRole`), sin execution role de ECS. Ver
# ARCHITECTURE_REPORT_PHASE2_9.md.
#
# Los runbooks no declaran `assumeRole` y no existe service role de Automation:
# por tanto TODOS los permisos que necesitan los pasos de la Automation deben
# estar en el rol de la task de ECS que inicia la ejecución. No hay `iam:PassRole`.
#
# Este Terraform NO crea roles de aplicación. El descubrimiento sobre la cuenta
# demostró que adjuntar políticas a un rol está explícitamente denegado (ver
# PRE_APPLY_NETWORK_DISCOVERY.md): un rol creado aquí nacería sin permisos y el
# despliegue quedaría roto en tiempo de ejecución. Ambos roles los aprovisiona
# el equipo de cloud y se consumen por ARN (`backend_task_role_arn`,
# `backend_execution_role_arn`); los documentos exactos que deben aplicar se
# publican como outputs y el despliegue falla si falta cualquiera de los dos.

locals {
  backend_role_name           = "${local.name_prefix}-backend-task"
  backend_execution_role_name = "${local.name_prefix}-backend-exec"

  # ARNs efectivos: siempre preaprovisionados, nunca gestionados aquí.
  backend_task_role_arn      = var.backend_task_role_arn
  backend_execution_role_arn = var.backend_execution_role_arn

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

  # --- Trust policy del rol federado (arquitectura vigente) ---------------
  # La aplicación se ejecuta en la VM de la sesión de Devin, fuera de AWS: la
  # identidad es un token OIDC de la sesión intercambiado por credenciales
  # temporales. `sub` es el valor verificado del token de esta organización, así
  # que sólo sus sesiones pueden asumir el rol. Sin comodines y sin claves.
  backend_oidc_provider_arn = (
    "arn:aws:iam::${var.aws_account_id}:oidc-provider/${var.devin_oidc_issuer_host}"
  )
  backend_external_role_trust_policy = {
    Version = "2012-10-17"
    Statement = [{
      Sid       = "OnlyDevinSessionsOfThisOrgMayAssumeThisRole"
      Effect    = "Allow"
      Principal = { Federated = local.backend_oidc_provider_arn }
      Action    = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "${var.devin_oidc_issuer_host}:aud" = var.devin_oidc_audience
          "${var.devin_oidc_issuer_host}:sub" = var.devin_oidc_subject
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
        # `StartAutomationExecution` con `Tags` etiqueta la ejecución que crea,
        # y esa llamada exige además `ssm:AddTagsToResource`.
        Sid    = "ControlAndReadOwnAutomationExecutions"
        Effect = "Allow"
        Action = [
          "ssm:StopAutomationExecution",
          "ssm:GetAutomationExecution",
          "ssm:AddTagsToResource",
        ]
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

  # --- Documentos del task execution role ---------------------------------
  # No es la identidad de la aplicación: lo usa el agente de ECS para descargar la
  # imagen y publicar logs. El código nunca obtiene sus credenciales.
  backend_execution_trust_policy = local.backend_task_trust_policy

  backend_execution_permission_policy = {
    Version = "2012-10-17"
    Statement = [
      {
        # `GetAuthorizationToken` no admite ARN de recurso.
        Sid      = "AuthenticateAgainstEcr"
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken"]
        Resource = "*"
        Condition = {
          StringEquals = { "aws:RequestedRegion" = var.aws_region }
        }
      },
      {
        Sid    = "PullOnlyTheMsrImage"
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer",
        ]
        Resource = local.backend_ecr_repository_arn
      },
      {
        Sid    = "PublishTheContainerLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents",
        ]
        Resource = "arn:aws:logs:${var.aws_region}:${var.aws_account_id}:log-group:${local.backend_log_group_name}:*"
      },
    ]
  }
}
