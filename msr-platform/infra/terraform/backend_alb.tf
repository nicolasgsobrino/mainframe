# Exposición de la UI/API a través de un Application Load Balancer.
#
# cliente → ALB → ECS Fargate :8080
#
# El backend sirve la SPA compilada y `/api` desde el mismo contenedor, así que
# basta un target group con targets `ip` (obligatorio con `awsvpc`) y un listener.
# Sin CloudFront y sin túneles: la exposición es un recurso gestionado.
#
# El valor predeterminado es un ALB interno. No se asume que la red corporativa
# permita un ALB público: publicarlo exige `backend_alb_internal = false`,
# subnets públicas y orígenes autorizados explícitos.

locals {
  backend_alb_enabled = (local.backend_enabled == 1 && var.enable_backend_alb) ? 1 : 0

  backend_alb_name       = "${local.name_prefix}-alb"
  backend_alb_tg_name    = "${local.name_prefix}-tg"
  backend_health_path    = "/api/health"
  backend_container_port = 8080
}

resource "aws_security_group" "backend_alb" {
  count = local.backend_alb_enabled

  name        = "${local.name_prefix}-alb-sg"
  description = "MSR PoC ALB: ingress solo desde los origenes autorizados"
  vpc_id      = var.vpc_id

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-alb-sg" })
}

# Sin `backend_alb_ingress_cidrs` no se crea ninguna regla: el ALB queda sin
# entrada permitida en lugar de abrirse por omisión.
resource "aws_vpc_security_group_ingress_rule" "backend_alb" {
  count = local.backend_alb_enabled == 1 ? length(var.backend_alb_ingress_cidrs) : 0

  security_group_id = aws_security_group.backend_alb[0].id
  description       = "Acceso a la UI/API de la PoC"
  cidr_ipv4         = var.backend_alb_ingress_cidrs[count.index]
  ip_protocol       = "tcp"
  from_port         = var.backend_alb_port
  to_port           = var.backend_alb_port
}

resource "aws_vpc_security_group_egress_rule" "backend_alb_to_backend" {
  count = local.backend_alb_enabled

  security_group_id            = aws_security_group.backend_alb[0].id
  description                  = "Reenvio al contenedor del backend"
  referenced_security_group_id = aws_security_group.backend[0].id
  ip_protocol                  = "tcp"
  from_port                    = local.backend_container_port
  to_port                      = local.backend_container_port
}

# Única entrada del backend: el propio ALB. Ni CIDR abiertos ni acceso directo.
resource "aws_vpc_security_group_ingress_rule" "backend_from_alb" {
  count = local.backend_alb_enabled

  security_group_id            = aws_security_group.backend[0].id
  description                  = "Trafico de la UI/API unicamente desde el ALB"
  referenced_security_group_id = aws_security_group.backend_alb[0].id
  ip_protocol                  = "tcp"
  from_port                    = local.backend_container_port
  to_port                      = local.backend_container_port
}

resource "aws_lb" "backend" {
  count = local.backend_alb_enabled

  name               = local.backend_alb_name
  internal           = var.backend_alb_internal
  load_balancer_type = "application"
  security_groups    = [aws_security_group.backend_alb[0].id]
  subnets            = var.backend_alb_subnet_ids

  drop_invalid_header_fields = true
  enable_deletion_protection = false

  tags = merge(local.common_tags, { Name = local.backend_alb_name })

  lifecycle {
    precondition {
      condition     = length(var.backend_alb_subnet_ids) >= 2
      error_message = "backend_alb_subnet_ids necesita al menos dos subnets en zonas distintas."
    }

    # Un ALB público sólo puede existir si se declara explícitamente.
    precondition {
      condition = var.backend_alb_internal || !contains(var.backend_alb_ingress_cidrs, "0.0.0.0/0")
      error_message = join(" ", [
        "Un ALB publico abierto a 0.0.0.0/0 requiere aprobacion de red:",
        "mantén backend_alb_internal = true o restringe backend_alb_ingress_cidrs.",
      ])
    }
  }
}

resource "aws_lb_target_group" "backend" {
  count = local.backend_alb_enabled

  name        = local.backend_alb_tg_name
  port        = local.backend_container_port
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip" # Fargate/awsvpc: los targets son ENIs, no instancias.

  deregistration_delay = 30

  health_check {
    enabled             = true
    path                = local.backend_health_path
    protocol            = "HTTP"
    matcher             = "200"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  tags = merge(local.common_tags, { Name = local.backend_alb_tg_name })
}

resource "aws_lb_listener" "backend" {
  count = local.backend_alb_enabled

  load_balancer_arn = aws_lb.backend[0].arn
  port              = var.backend_alb_port
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.backend[0].arn
  }

  tags = merge(local.common_tags, { Name = "${local.backend_alb_name}-listener" })
}
