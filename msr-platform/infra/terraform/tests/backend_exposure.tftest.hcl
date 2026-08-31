# ECR privado, ALB interno por defecto y tabla del lock distribuido.
#
# Sin credenciales ni llamadas a AWS: `mock_provider` cubre los data sources y
# todo se comprueba sobre el plan.

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
  backend_image                       = "133789123239.dkr.ecr.eu-north-1.amazonaws.com/msr-poc-platform:0.1.0"
  backend_subnet_ids                  = ["subnet-0bb97e6254e4f83e9"]
  backend_task_role_arn               = "arn:aws:iam::133789123239:role/CorpMsrBackendTask"
  backend_execution_role_arn          = "arn:aws:iam::133789123239:role/CorpMsrBackendExec"
}

run "nothing_new_is_planned_while_the_runtime_stays_disabled" {
  command = plan

  assert {
    condition = (
      length(aws_ecr_repository.backend) == 0 &&
      length(aws_ecr_lifecycle_policy.backend) == 0 &&
      length(aws_lb.backend) == 0 &&
      length(aws_lb_target_group.backend) == 0 &&
      length(aws_lb_listener.backend) == 0 &&
      length(aws_dynamodb_table.lab_locks) == 0
    )
    error_message = "Con los valores predeterminados no puede planificarse ECR, ALB ni la tabla de locks."
  }

  assert {
    condition     = length(aws_autoscaling_group.lab) == 1 && aws_autoscaling_group.lab[0].desired_capacity == 1
    error_message = "El laboratorio debe seguir siendo un ASG 1/1/1 intacto."
  }

  assert {
    condition     = var.backend_alb_internal == true
    error_message = "El valor predeterminado del ALB debe ser interno."
  }
}

run "the_ecr_repository_is_private_scanned_encrypted_and_pruned" {
  command = plan

  variables {
    enable_backend_ecr = true
  }

  assert {
    condition     = aws_ecr_repository.backend[0].name == "msr-poc-platform"
    error_message = "El repositorio debe ser el dedicado a la imagen MSR."
  }

  assert {
    condition     = aws_ecr_repository.backend[0].image_scanning_configuration[0].scan_on_push == true
    error_message = "El escaneo de imágenes debe estar activado."
  }

  assert {
    condition     = aws_ecr_repository.backend[0].encryption_configuration[0].encryption_type == "AES256"
    error_message = "El repositorio debe estar cifrado."
  }

  assert {
    condition = (
      aws_ecr_repository.backend[0].image_tag_mutability == "IMMUTABLE" &&
      aws_ecr_repository.backend[0].force_delete == false
    )
    error_message = "Los tags publicados no pueden reescribirse."
  }

  assert {
    condition = (
      jsondecode(aws_ecr_lifecycle_policy.backend[0].policy).rules[0].selection.countType == "imageCountMoreThan" &&
      jsondecode(aws_ecr_lifecycle_policy.backend[0].policy).rules[0].selection.countNumber == 5 &&
      jsondecode(aws_ecr_lifecycle_policy.backend[0].policy).rules[0].action.type == "expire"
    )
    error_message = "La lifecycle policy debe conservar sólo las últimas imágenes."
  }

  assert {
    condition = output.backend_ecr_repository_url == (
      "133789123239.dkr.ecr.eu-north-1.amazonaws.com/msr-poc-platform"
    )
    error_message = "La URL del repositorio debe publicarse como output."
  }
}

run "the_alb_is_internal_and_reaches_the_backend_only_through_its_target_group" {
  command = plan

  variables {
    enable_backend_service = true
    enable_backend_alb     = true
    backend_alb_subnet_ids = ["subnet-0bb97e6254e4f83e9", "subnet-0c14b617316ff3efa"]
    # Origen corporativo concreto: nunca 0.0.0.0/0 por omisión.
    backend_alb_ingress_cidrs = ["203.0.113.10/32"]
  }

  assert {
    condition     = aws_lb.backend[0].internal == true
    error_message = "El ALB debe planificarse como interno mientras no se apruebe uno público."
  }

  assert {
    condition = (
      aws_lb_target_group.backend[0].target_type == "ip" &&
      aws_lb_target_group.backend[0].port == 8080
    )
    error_message = "Fargate con awsvpc exige targets ip sobre el puerto 8080."
  }

  assert {
    condition = (
      aws_lb_target_group.backend[0].health_check[0].path == "/api/health" &&
      aws_lb_target_group.backend[0].health_check[0].matcher == "200"
    )
    error_message = "El health check debe ser /api/health."
  }

  assert {
    condition = length([
      for attachment in aws_ecs_service.backend[0].load_balancer :
      attachment
      if attachment.container_name == "backend" && attachment.container_port == 8080
    ]) == 1
    error_message = "El servicio de ECS debe registrarse en el target group."
  }

  assert {
    condition = (
      aws_vpc_security_group_ingress_rule.backend_from_alb[0].from_port == 8080 &&
      aws_vpc_security_group_ingress_rule.backend_from_alb[0].to_port == 8080 &&
      aws_vpc_security_group_ingress_rule.backend_from_alb[0].cidr_ipv4 == null
    )
    error_message = "El backend sólo puede aceptar tráfico del security group del ALB."
  }

  assert {
    condition     = length(aws_vpc_security_group_ingress_rule.backend_alb) == 1
    error_message = "El listener debe abrirse únicamente a los orígenes declarados."
  }

  assert {
    condition     = aws_ecs_service.backend[0].network_configuration[0].assign_public_ip == false
    error_message = "La task sigue sin IP pública detrás del ALB."
  }
}

run "the_alb_cannot_be_deployed_without_declared_origins" {
  command = plan

  variables {
    enable_backend_service = true
    enable_backend_alb     = true
    backend_alb_subnet_ids = ["subnet-0bb97e6254e4f83e9", "subnet-0c14b617316ff3efa"]
  }

  expect_failures = [aws_lb.backend]
}

run "an_alb_open_to_the_internet_is_rejected" {
  command = plan

  variables {
    enable_backend_service    = true
    enable_backend_alb        = true
    backend_alb_internal      = false
    backend_alb_subnet_ids    = ["subnet-0bb97e6254e4f83e9", "subnet-0c14b617316ff3efa"]
    backend_alb_ingress_cidrs = ["0.0.0.0/0"]
  }

  expect_failures = [var.backend_alb_ingress_cidrs]
}

run "the_alb_requires_two_availability_zones" {
  command = plan

  variables {
    enable_backend_service    = true
    enable_backend_alb        = true
    backend_alb_subnet_ids    = ["subnet-0bb97e6254e4f83e9"]
    backend_alb_ingress_cidrs = ["203.0.113.10/32"]
  }

  expect_failures = [aws_lb.backend]
}

run "the_alb_cannot_use_a_subnet_outside_the_discovered_candidates" {
  command = plan

  variables {
    enable_backend_service    = true
    enable_backend_alb        = true
    backend_alb_subnet_ids    = ["subnet-0bb97e6254e4f83e9", "subnet-0aa97e6254e4f83e0"]
    backend_alb_ingress_cidrs = ["203.0.113.10/32"]
  }

  expect_failures = [aws_lb.backend]
}

run "the_poc_profile_publishes_the_alb_only_to_the_allowlisted_origins" {
  command = plan

  variables {
    enable_backend_service    = true
    enable_backend_alb        = true
    backend_alb_internal      = false
    backend_assign_public_ip  = true
    backend_alb_subnet_ids    = ["subnet-0bb97e6254e4f83e9", "subnet-0c14b617316ff3efa"]
    backend_alb_ingress_cidrs = ["203.0.113.10/32", "198.51.100.0/28"]
  }

  assert {
    condition     = aws_lb.backend[0].internal == false
    error_message = "El perfil PoC publica el ALB porque no existe conectividad corporativa."
  }

  assert {
    condition = length(aws_vpc_security_group_ingress_rule.backend_alb) == 2 && alltrue([
      for rule in values(aws_vpc_security_group_ingress_rule.backend_alb) :
      contains(["203.0.113.10/32", "198.51.100.0/28"], rule.cidr_ipv4) && rule.from_port == 80
    ])
    error_message = "El listener sólo puede abrirse a los orígenes autorizados."
  }

  assert {
    condition = (
      output.backend_network_profile.profile == "poc-public" &&
      output.backend_network_profile.listener_protocol == "HTTP" &&
      output.backend_network_profile.assign_public_ip == true
    )
    error_message = "El perfil de red publicado debe describir la exposición real."
  }
}

run "the_full_poc_profile_plans_exactly_the_expected_resources" {
  command = plan

  variables {
    enable_backend_service    = true
    enable_backend_ecr        = true
    enable_backend_lock_table = true
    enable_backend_alb        = true
    backend_alb_internal      = false
    backend_assign_public_ip  = true
    backend_alb_subnet_ids    = ["subnet-0bb97e6254e4f83e9", "subnet-0c14b617316ff3efa"]
    backend_subnet_ids        = ["subnet-0bb97e6254e4f83e9", "subnet-0c14b617316ff3efa"]
    backend_alb_ingress_cidrs = ["203.0.113.10/32"]
  }

  # Diecisiete recursos del runtime sobre los diez del laboratorio, ninguno IAM.
  assert {
    condition = (
      length(output.backend_resource_summary.resources) == 17 &&
      length(output.estimated_resource_summary.resources) == 10
    )
    error_message = "El primer apply del perfil PoC debe crear exactamente 27 recursos."
  }

  assert {
    condition = !anytrue([
      for resource in output.backend_resource_summary.resources :
      startswith(resource, "aws_iam_")
    ])
    error_message = "Ningún recurso IAM puede formar parte del plan."
  }
}

run "a_certificate_moves_the_traffic_to_https_and_redirects_http" {
  command = plan

  variables {
    enable_backend_service      = true
    enable_backend_alb          = true
    backend_alb_internal        = false
    backend_assign_public_ip    = true
    backend_alb_subnet_ids      = ["subnet-0bb97e6254e4f83e9", "subnet-0c14b617316ff3efa"]
    backend_alb_ingress_cidrs   = ["203.0.113.10/32"]
    backend_alb_certificate_arn = "arn:aws:acm:eu-north-1:133789123239:certificate/11111111-2222-3333-4444-555555555555"
  }

  assert {
    condition = (
      length(aws_lb_listener.backend_https) == 1 &&
      aws_lb_listener.backend_https[0].port == 443 &&
      aws_lb_listener.backend_https[0].protocol == "HTTPS"
    )
    error_message = "Con certificado debe existir el listener HTTPS."
  }

  assert {
    condition     = aws_lb_listener.backend[0].default_action[0].type == "redirect"
    error_message = "El listener HTTP debe redirigir a HTTPS en lugar de servir tráfico."
  }

  assert {
    condition = length(aws_vpc_security_group_ingress_rule.backend_alb) == 2 && anytrue([
      for rule in values(aws_vpc_security_group_ingress_rule.backend_alb) : rule.from_port == 443
    ])
    error_message = "El origen autorizado debe poder alcanzar también el puerto 443."
  }

  assert {
    condition     = output.backend_network_profile.listener_protocol == "HTTPS"
    error_message = "El perfil publicado debe reflejar HTTPS."
  }
}

run "the_lock_table_serializes_lab_mutations" {
  command = plan

  variables {
    enable_backend_lock_table = true
  }

  assert {
    condition = (
      aws_dynamodb_table.lab_locks[0].name == "msr-poc-lab-locks" &&
      aws_dynamodb_table.lab_locks[0].hash_key == "lab_id" &&
      aws_dynamodb_table.lab_locks[0].billing_mode == "PAY_PER_REQUEST"
    )
    error_message = "La tabla del lock debe ser una única tabla con partition key lab_id."
  }

  assert {
    condition = (
      aws_dynamodb_table.lab_locks[0].ttl[0].attribute_name == "expires_at" &&
      aws_dynamodb_table.lab_locks[0].ttl[0].enabled == true
    )
    error_message = "El TTL debe limpiar los locks abandonados sobre expires_at."
  }

  assert {
    condition = (
      aws_dynamodb_table.lab_locks[0].server_side_encryption[0].enabled == true &&
      aws_dynamodb_table.lab_locks[0].point_in_time_recovery[0].enabled == true
    )
    error_message = "La tabla debe estar cifrada y recuperable."
  }

  assert {
    condition = (
      output.backend_lock_table.arn == "arn:aws:dynamodb:eu-north-1:133789123239:table/msr-poc-lab-locks" &&
      output.backend_lock_table.partition_key == "lab_id"
    )
    error_message = "El ARN exacto de la tabla debe publicarse como output."
  }
}

run "the_task_role_can_only_touch_the_lock_table_in_dynamodb" {
  command = plan

  variables {
    enable_backend_service = true
  }

  assert {
    condition = alltrue([
      for statement in jsondecode(output.backend_task_role_permission_policy_json).Statement :
      statement.Resource == "arn:aws:dynamodb:eu-north-1:133789123239:table/msr-poc-lab-locks"
      if statement.Sid == "SerializeLabMutationsWithTheLockTable"
    ])
    error_message = "Los permisos de DynamoDB deben acotarse a la tabla del lock."
  }

  assert {
    condition = alltrue([
      for statement in jsondecode(output.backend_task_role_permission_policy_json).Statement :
      alltrue([
        for action in statement.Action :
        contains(["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:DeleteItem"], action)
      ])
      if statement.Sid == "SerializeLabMutationsWithTheLockTable"
    ])
    error_message = "Sólo se autorizan las acciones que el lock ejecuta realmente."
  }

  assert {
    condition     = !strcontains(output.backend_task_role_permission_policy_json, "dynamodb:*")
    error_message = "Nunca puede concederse dynamodb:*."
  }

  assert {
    condition = !strcontains(
      output.backend_task_role_permission_policy_json, "dynamodb:DeleteTable"
    )
    error_message = "El rol no puede administrar la tabla, sólo sus ítems."
  }

  assert {
    condition     = output.backend_task_environment.MSR_LAB_LOCK_TABLE_NAME == "msr-poc-lab-locks"
    error_message = "La task debe recibir el nombre de la tabla del lock."
  }
}
