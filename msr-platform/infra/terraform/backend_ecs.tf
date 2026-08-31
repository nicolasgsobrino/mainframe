# SUPERSEDED / NO OBJETIVO (fase 2.9): la aplicación MSR ya no se aloja en AWS.
# Se conserva por valor histórico, desactivado por defecto, y ningún despliegue
# objetivo depende de él. Arquitectura vigente: ARCHITECTURE_REPORT_PHASE2_9.md.
#
# Runtime del backend: task de ECS Fargate.
#
# Internet/usuario → frontend (SPA servida por el propio backend)
#   → backend como task de ECS Fargate
#   → ECS Task Role (credenciales temporales del endpoint de metadatos)
#   → Systems Manager Automation
#   → runbooks MSR de patch/reset
#   → EC2 del laboratorio
#
# El backend NO se despliega en la EC2 del laboratorio: esa instancia se termina
# a propósito en cada reset, así que alojar ahí la aplicación la destruiría.
#
# Los recursos sólo existen con `enable_backend_service = true` (además del
# interruptor maestro): con los valores predeterminados el plan del laboratorio
# sigue siendo exactamente el mismo.

locals {
  backend_enabled = (var.enable_real_resources && var.enable_backend_service) ? 1 : 0

  backend_cluster_name   = "${local.name_prefix}-backend"
  backend_service_name   = "${local.name_prefix}-backend-svc"
  backend_container_name = "backend"

  # Entorno de la task. Providers AWS activados y `MSR_DRY_RUN=true` hasta que se
  # autorice la validación real; la reconciliación destructiva NO se ejecuta en el
  # arranque de cada réplica (la lanza el hook de release).
  backend_task_environment = merge(local.backend_environment, {
    MSR_PATCH_PROVIDER           = "aws-automation"
    MSR_RESTORE_PROVIDER         = "aws-automation"
    MSR_DRY_RUN                  = tostring(var.backend_dry_run)
    MSR_LAB_RECONCILE_ON_STARTUP = "false"
    # Lock distribuido: en ejecución real el backend serializa las mutaciones del
    # laboratorio contra esta tabla, no contra su filesystem efímero.
    MSR_LAB_LOCK_TABLE_NAME = var.backend_lock_table_name
    # Vacíos a propósito: boto3 usa exclusivamente el Task Role. Sin perfiles,
    # sin claves estáticas, sin sts:AssumeRole.
    MSR_AWS_PROFILE  = ""
    MSR_AWS_ROLE_ARN = ""
  })

  backend_container_definition = {
    name      = local.backend_container_name
    image     = var.backend_image
    essential = true
    portMappings = [{
      containerPort = 8080
      protocol      = "tcp"
    }]
    environment = [
      for key in sort(keys(local.backend_task_environment)) :
      { name = key, value = local.backend_task_environment[key] }
    ]
    # Sin `secrets`: no hay ninguna credencial que inyectar.
    healthCheck = {
      command     = ["CMD-SHELL", "python -c \"import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=4).status == 200 else 1)\""]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 15
    }
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = local.backend_log_group_name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "backend"
      }
    }
  }

  backend_log_group_name = "/aws/ecs/${local.name_prefix}-backend"
}

resource "aws_cloudwatch_log_group" "backend" {
  count = local.backend_enabled

  name              = local.backend_log_group_name
  retention_in_days = var.backend_log_retention_days

  tags = merge(local.common_tags, { Name = local.backend_log_group_name })
}

# Red: la task sale por HTTPS hacia los endpoints de SSM/EC2/Auto Scaling/DynamoDB
# y su única entrada permitida es el security group del ALB (ver backend_alb.tf).
resource "aws_security_group" "backend" {
  count = local.backend_enabled

  name        = "${local.name_prefix}-backend-sg"
  description = "MSR PoC backend: ingress solo desde el ALB; egress HTTPS/DNS hacia las APIs de AWS"
  vpc_id      = var.vpc_id

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-backend-sg" })
}

resource "aws_vpc_security_group_egress_rule" "backend_https" {
  count = local.backend_enabled

  security_group_id = aws_security_group.backend[0].id
  description       = "HTTPS hacia las APIs de AWS (SSM, EC2, Auto Scaling, DynamoDB, ECR, Logs)"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
}

resource "aws_vpc_security_group_egress_rule" "backend_dns_udp" {
  count = local.backend_enabled

  security_group_id = aws_security_group.backend[0].id
  description       = "DNS (UDP) hacia el resolver de la VPC"
  cidr_ipv4         = data.aws_vpc.lab[0].cidr_block
  ip_protocol       = "udp"
  from_port         = 53
  to_port           = 53
}

resource "aws_ecs_cluster" "backend" {
  count = local.backend_enabled

  name = local.backend_cluster_name

  setting {
    name  = "containerInsights"
    value = "disabled"
  }

  tags = merge(local.common_tags, { Name = local.backend_cluster_name })
}

resource "aws_ecs_task_definition" "backend" {
  count = local.backend_enabled

  family                   = "${local.name_prefix}-backend"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.backend_task_cpu
  memory                   = var.backend_task_memory
  # Identidad de la aplicación: creada por Terraform o preaprovisionada.
  task_role_arn      = local.backend_task_role_arn
  execution_role_arn = local.backend_execution_role_arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  container_definitions = jsonencode([local.backend_container_definition])

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-backend" })

  lifecycle {
    # Sin identidad de workload válida el despliegue falla: nunca se arranca una
    # task que caería en credenciales ambientales indeterminadas.
    precondition {
      condition = can(regex(
        "^arn:aws:iam::${var.aws_account_id}:role/[\\w+=,.@/-]+$",
        local.backend_task_role_arn
      ))
      error_message = "Sin Task Role: define backend_task_role_arn con el rol preaprovisionado de la cuenta ${var.aws_account_id}."
    }

    precondition {
      condition = can(regex(
        "^arn:aws:iam::${var.aws_account_id}:role/[\\w+=,.@/-]+$",
        local.backend_execution_role_arn
      ))
      error_message = "Sin task execution role: define backend_execution_role_arn con el rol preaprovisionado."
    }

    precondition {
      condition     = var.backend_image != ""
      error_message = "backend_image debe apuntar a la imagen publicada en ECR."
    }

    precondition {
      condition     = length(var.backend_subnet_ids) > 0
      error_message = "backend_subnet_ids no puede estar vacío."
    }

    # Ninguna subnet ajena al descubrimiento de red autorizado.
    precondition {
      condition = length(setsubtract(
        var.backend_subnet_ids, var.backend_candidate_subnet_ids
      )) == 0
      error_message = "backend_subnet_ids sólo admite subnets de backend_candidate_subnet_ids."
    }
  }
}

resource "aws_ecs_service" "backend" {
  count = local.backend_enabled

  name            = local.backend_service_name
  cluster         = aws_ecs_cluster.backend[0].id
  task_definition = aws_ecs_task_definition.backend[0].arn
  desired_count   = var.backend_desired_count
  launch_type     = "FARGATE"
  # El hook de reconciliación se ejecuta una sola vez por release (RunTask), no
  # en cada réplica: el servicio puede escalar sin resetear el laboratorio.
  enable_execute_command = false
  propagate_tags         = "SERVICE"

  # La IP pública no expone el backend: la única entrada de su security group es el
  # security group del ALB. En el perfil PoC es imprescindible porque la VPC por
  # defecto no tiene NAT ni endpoints de VPC y, sin ella, la task no podría
  # descargar la imagen de ECR, escribir logs ni llamar a las APIs de AWS.
  network_configuration {
    subnets          = var.backend_subnet_ids
    security_groups  = [aws_security_group.backend[0].id]
    assign_public_ip = var.backend_assign_public_ip
  }

  dynamic "load_balancer" {
    for_each = local.backend_alb_enabled == 1 ? [1] : []

    content {
      target_group_arn = aws_lb_target_group.backend[0].arn
      container_name   = local.backend_container_name
      container_port   = local.backend_container_port
    }
  }

  # El target group debe existir con su listener antes de registrar la task.
  depends_on = [aws_lb_listener.backend]

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  tags = merge(local.common_tags, { Name = local.backend_service_name })
}
