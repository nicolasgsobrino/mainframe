# Runtime del backend en ECS Fargate y su identidad de workload.
#
# Sin credenciales ni llamadas a AWS: `mock_provider` cubre los data sources y
# todas las comprobaciones se hacen sobre el plan.

mock_provider "aws" {
  mock_data "aws_caller_identity" {
    defaults = {
      account_id = "133789123239"
    }
  }

  mock_data "aws_region" {
    defaults = {
      name = "eu-north-1"
    }
  }

  mock_data "aws_vpc" {
    defaults = {
      id         = "vpc-023864c0ca3c82eab"
      cidr_block = "10.0.0.0/16"
    }
  }

  mock_data "aws_subnet" {
    defaults = {
      id                = "subnet-0bb97e6254e4f83e9"
      vpc_id            = "vpc-023864c0ca3c82eab"
      availability_zone = "eu-north-1a"
      cidr_block        = "10.0.1.0/24"
    }
  }

  mock_data "aws_ami" {
    defaults = {
      id           = "ami-0b2ab3a97a77bd35e"
      architecture = "x86_64"
      owner_id     = "amazon"
      name         = "al2023-ami-2023.11.20260509.0-kernel-6.1-x86_64"
    }
  }

  mock_data "aws_instances" {
    defaults = {
      ids = []
    }
  }

  mock_data "aws_iam_instance_profile" {
    defaults = {
      arn       = "arn:aws:iam::133789123239:instance-profile/EC2SSMAgentProfileL0"
      role_name = "EC2SSMAgentProfile"
      role_arn  = "arn:aws:iam::133789123239:role/EC2SSMAgentProfile"
    }
  }
}

variables {
  enable_real_resources               = true
  existing_instance_profile_name      = "EC2SSMAgentProfileL0"
  existing_instance_profile_role_name = "EC2SSMAgentProfile"
  backend_image                       = "133789123239.dkr.ecr.eu-north-1.amazonaws.com/msr-platform:0.1.0"
  backend_subnet_ids                  = ["subnet-0bb97e6254e4f83e9"]
  backend_task_role_arn               = "arn:aws:iam::133789123239:role/CorpMsrBackendTask"
  backend_execution_role_arn          = "arn:aws:iam::133789123239:role/CorpMsrBackendExec"
}

run "the_lab_plan_does_not_change_when_the_backend_is_disabled" {
  command = plan

  assert {
    condition = (
      length(aws_ecs_cluster.backend) == 0 &&
      length(aws_ecs_service.backend) == 0 &&
      length(aws_ecs_task_definition.backend) == 0
    )
    error_message = "Sin enable_backend_service no puede planificarse ningún recurso del runtime."
  }

  assert {
    condition     = output.backend_resource_summary.enabled == false
    error_message = "El resumen debe reflejar que el runtime está desactivado."
  }

  assert {
    condition     = length(aws_autoscaling_group.lab) == 1 && aws_autoscaling_group.lab[0].desired_capacity == 1
    error_message = "El laboratorio debe seguir siendo un ASG 1/1/1 intacto."
  }
}

run "the_role_documents_published_for_the_cloud_team_are_exact" {
  command = plan

  variables {
    enable_backend_service = true
  }

  assert {
    condition = (
      output.backend_task_role_is_managed_by_terraform == false &&
      output.backend_resource_summary.requires_iam_permissions == false
    )
    error_message = "Este Terraform no gestiona roles de aplicación: no exige permisos de IAM."
  }

  # --- trust policy exacta: sólo ECS, sólo esta cuenta, sólo esta región ---
  assert {
    condition = (
      jsondecode(output.backend_task_role_trust_policy_json).Statement[0].Principal.Service ==
      "ecs-tasks.amazonaws.com"
    )
    error_message = "El único principal de servicio debe ser ecs-tasks.amazonaws.com."
  }

  assert {
    condition = (
      jsondecode(output.backend_task_role_trust_policy_json).Statement[0].Condition.StringEquals["aws:SourceAccount"] == "133789123239" &&
      jsondecode(output.backend_task_role_trust_policy_json).Statement[0].Condition.ArnLike["aws:SourceArn"] == "arn:aws:ecs:eu-north-1:133789123239:*"
    )
    error_message = "La trust policy debe exigir SourceAccount y SourceArn de la cuenta y región configuradas."
  }

  assert {
    condition = !strcontains(
      output.backend_task_role_trust_policy_json, "\"*\""
    )
    error_message = "La trust policy no puede usar comodines de principal ni de recurso."
  }

  # --- política de permisos: opción B sin PassRole -------------------------
  assert {
    condition     = !strcontains(output.backend_task_role_permission_policy_json, "iam:PassRole")
    error_message = "Sin service role de Automation no puede existir iam:PassRole."
  }

  assert {
    condition = !strcontains(
      output.backend_task_role_permission_policy_json, "sts:AssumeRole"
    )
    error_message = "El backend no asume ningún rol: usa directamente el Task Role."
  }

  assert {
    condition = (
      contains([
        for statement in jsondecode(output.backend_task_role_permission_policy_json).Statement :
        statement.Sid
      ], "StartOnlyTheTwoPocRunbooks")
    )
    error_message = "Falta el permiso de arranque de los runbooks."
  }

  assert {
    condition = alltrue([
      for statement in jsondecode(output.backend_task_role_permission_policy_json).Statement :
      contains(statement.Resource, "arn:aws:ssm:eu-north-1:133789123239:automation-definition/MSR-PatchLinuxInstance") &&
      contains(statement.Resource, "arn:aws:ssm:eu-north-1:133789123239:automation-definition/MSR-ResetLabInstance")
      if statement.Sid == "StartOnlyTheTwoPocRunbooks"
    ])
    error_message = "StartAutomationExecution debe limitarse a los dos runbooks de la PoC."
  }

  assert {
    condition = alltrue([
      for statement in jsondecode(output.backend_task_role_permission_policy_json).Statement :
      statement.Resource == "arn:aws:autoscaling:eu-north-1:133789123239:autoScalingGroup:*:autoScalingGroupName/msr-poc-linux-patching-01-asg"
      if statement.Sid == "ReplaceTheLabInstanceOnlyThroughItsAutoScalingGroup"
    ])
    error_message = "La terminación sólo puede autorizarse sobre el ASG del laboratorio."
  }

  assert {
    condition = alltrue([
      for statement in jsondecode(output.backend_task_role_permission_policy_json).Statement :
      statement.Condition.StringEquals["ssm:resourceTag/msr-poc"] == "true" &&
      statement.Condition.StringEquals["ssm:resourceTag/msr-lab-id"] == "linux-patching-01"
      if statement.Sid == "SendCommandOnlyToTheTaggedLabInstance"
    ])
    error_message = "SendCommand debe restringirse por tags a la instancia del laboratorio."
  }

  assert {
    condition = length([
      for statement in jsondecode(output.backend_task_role_permission_policy_json).Statement :
      statement if strcontains(jsonencode(statement.Action), "ec2:TerminateInstances") ||
      strcontains(jsonencode(statement.Action), "ec2:RunInstances") ||
      strcontains(jsonencode(statement.Action), "ssm:CreateDocument") ||
      strcontains(jsonencode(statement.Action), "ssm:UpdateDocument")
    ]) == 0
    error_message = "El rol no puede terminar ni lanzar instancias, ni modificar documentos."
  }

  # --- task execution role: sólo la imagen MSR y su log group --------------
  assert {
    condition = (
      jsondecode(output.backend_execution_role_trust_policy_json).Statement[0].Principal.Service ==
      "ecs-tasks.amazonaws.com"
    )
    error_message = "El execution role sólo puede asumirlo ECS."
  }

  assert {
    condition = alltrue([
      for statement in jsondecode(output.backend_execution_role_permission_policy_json).Statement :
      statement.Resource == "arn:aws:ecr:eu-north-1:133789123239:repository/msr-poc-platform"
      if statement.Sid == "PullOnlyTheMsrImage"
    ])
    error_message = "El pull debe limitarse al repositorio ECR de la PoC."
  }

  assert {
    condition = alltrue([
      for statement in jsondecode(output.backend_execution_role_permission_policy_json).Statement :
      statement.Resource == "arn:aws:logs:eu-north-1:133789123239:log-group:/aws/ecs/msr-poc-linux-patching-01-backend:*"
      if statement.Sid == "PublishTheContainerLogs"
    ])
    error_message = "Los logs deben limitarse al log group del backend."
  }

  assert {
    condition = length([
      for statement in jsondecode(output.backend_execution_role_permission_policy_json).Statement :
      statement if strcontains(jsonencode(statement.Action), "ecr:Put") ||
      strcontains(jsonencode(statement.Action), "ecr:*") ||
      strcontains(jsonencode(statement.Action), "logs:CreateLogGroup") ||
      strcontains(jsonencode(statement.Action), "secretsmanager:")
    ]) == 0
    error_message = "El execution role no publica imágenes, no crea log groups y no lee secretos."
  }
}

run "the_deployment_consumes_the_preprovisioned_roles" {
  command = plan

  variables {
    enable_backend_service = true
  }

  assert {
    condition = (
      output.backend_task_role_arn == "arn:aws:iam::133789123239:role/CorpMsrBackendTask" &&
      output.backend_task_role_is_managed_by_terraform == false &&
      output.backend_resource_summary.requires_iam_permissions == false
    )
    error_message = "El runtime debe consumir el rol preaprovisionado."
  }

  assert {
    condition = (
      aws_ecs_task_definition.backend[0].task_role_arn == "arn:aws:iam::133789123239:role/CorpMsrBackendTask" &&
      aws_ecs_task_definition.backend[0].execution_role_arn == "arn:aws:iam::133789123239:role/CorpMsrBackendExec"
    )
    error_message = "La task definition debe usar el rol preaprovisionado como identidad."
  }
}

run "the_deployment_fails_without_a_workload_role" {
  command = plan

  variables {
    enable_backend_service = true
    backend_task_role_arn  = ""
  }

  expect_failures = [aws_ecs_task_definition.backend]
}

run "the_deployment_fails_without_an_execution_role" {
  command = plan

  variables {
    enable_backend_service     = true
    backend_execution_role_arn = ""
  }

  expect_failures = [aws_ecs_task_definition.backend]
}

run "the_tasks_cannot_use_a_subnet_outside_the_discovered_candidates" {
  command = plan

  variables {
    enable_backend_service = true
    backend_subnet_ids     = ["subnet-0000000000000dead"]
  }

  expect_failures = [aws_ecs_task_definition.backend]
}

run "the_poc_profile_assigns_a_public_ip_without_exposing_the_task" {
  command = plan

  variables {
    enable_backend_service   = true
    backend_assign_public_ip = true
    enable_backend_alb       = true
    backend_alb_internal     = false
    backend_alb_subnet_ids = [
      "subnet-0bb97e6254e4f83e9",
      "subnet-0c14b617316ff3efa",
    ]
    backend_alb_ingress_cidrs = ["203.0.113.10/32"]
  }

  assert {
    condition     = aws_ecs_service.backend[0].network_configuration[0].assign_public_ip == true
    error_message = "El perfil PoC necesita IP pública: la VPC no tiene NAT ni endpoints."
  }

  # La IP pública no abre la task: su única entrada sigue siendo el SG del ALB.
  assert {
    condition = (
      length(aws_vpc_security_group_ingress_rule.backend_from_alb) == 1 &&
      aws_vpc_security_group_ingress_rule.backend_from_alb[0].from_port == 8080 &&
      aws_vpc_security_group_ingress_rule.backend_from_alb[0].cidr_ipv4 == null
    )
    error_message = "La task sólo admite 8080 desde el security group del ALB."
  }

  assert {
    condition     = output.backend_network_profile.profile == "poc-public"
    error_message = "El perfil de red efectivo debe declararse como poc-public."
  }
}

run "the_task_runs_with_safe_defaults_and_no_credentials" {
  command = plan

  variables {
    enable_backend_service = true
  }

  assert {
    condition = (
      output.backend_task_environment.MSR_PATCH_PROVIDER == "aws-automation" &&
      output.backend_task_environment.MSR_RESTORE_PROVIDER == "aws-automation" &&
      output.backend_task_environment.MSR_DRY_RUN == "true" &&
      output.backend_task_environment.MSR_LAB_RECONCILE_ON_STARTUP == "false" &&
      output.backend_task_environment.MSR_AWS_PROFILE == "" &&
      output.backend_task_environment.MSR_AWS_ROLE_ARN == ""
    )
    error_message = "Los defaults desplegados deben ser seguros y sin perfil ni rol que asumir."
  }

  assert {
    condition = !anytrue([
      for key in keys(output.backend_task_environment) :
      strcontains(key, "ACCESS_KEY") || strcontains(key, "SECRET") || strcontains(key, "SESSION_TOKEN")
    ])
    error_message = "Ninguna variable de la task puede transportar credenciales."
  }

  assert {
    condition     = !strcontains(jsonencode(aws_ecs_task_definition.backend[0].container_definitions), "\"secrets\"")
    error_message = "No se inyectan secretos: la identidad viene del Task Role."
  }

  assert {
    condition     = aws_ecs_service.backend[0].network_configuration[0].assign_public_ip == false
    error_message = "El valor predeterminado del perfil corporativo es sin IP pública."
  }

  assert {
    condition = (
      output.backend_reconciliation_hook.normal == ["python", "-m", "app.lab_hook"] &&
      output.backend_reconciliation_hook.authorized_restore == ["python", "-m", "app.lab_hook", "--confirm"]
    )
    error_message = "El hook de release debe documentar la invocación normal y la autorizada."
  }
}
