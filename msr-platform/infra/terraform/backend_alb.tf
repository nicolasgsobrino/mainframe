# Exposición de la UI/API a través de un Application Load Balancer.
#
# cliente → ALB → ECS Fargate :8080
#
# El backend sirve la SPA compilada y `/api` desde el mismo contenedor, así que
# basta un target group con targets `ip` (obligatorio con `awsvpc`) y un listener.
# Sin CloudFront y sin túneles: la exposición es un recurso gestionado.
#
# El valor predeterminado es un ALB interno (perfil corporativo futuro). El perfil
# PoC lo publica con `backend_alb_internal = false` porque la cuenta no tiene
# subnets privadas ni conectividad corporativa; a cambio, la lista de orígenes
# autorizados es obligatoria y ningún prefijo `/0` es admisible.

locals {
  backend_alb_enabled = (local.backend_enabled == 1 && var.enable_backend_alb) ? 1 : 0

  backend_alb_name       = "${local.name_prefix}-alb"
  backend_alb_tg_name    = "${local.name_prefix}-tg"
  backend_health_path    = "/api/health"
  backend_container_port = 8080

  # Con certificado el tráfico entra por 443 y el listener HTTP sólo redirige.
  backend_alb_https_enabled = var.backend_alb_certificate_arn != "" ? 1 : 0
  backend_alb_ingress_ports = (
    var.backend_alb_certificate_arn != "" ? [var.backend_alb_port, 443] : [var.backend_alb_port]
  )
  backend_alb_ingress_rules = {
    for pair in setproduct(var.backend_alb_ingress_cidrs, local.backend_alb_ingress_ports) :
    "${pair[0]}-${pair[1]}" => { cidr = pair[0], port = pair[1] }
  }
}

resource "aws_security_group" "backend_alb" {
  count = local.backend_alb_enabled

  name        = "${local.name_prefix}-alb-sg"
  description = "MSR PoC ALB: ingress solo desde los origenes autorizados"
  vpc_id      = var.vpc_id

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-alb-sg" })
}

# Una regla por origen autorizado y puerto expuesto. Sin orígenes no se crea
# ninguna: el ALB nunca se abre por omisión (y su precondition detiene el apply).
resource "aws_vpc_security_group_ingress_rule" "backend_alb" {
  for_each = local.backend_alb_enabled == 1 ? local.backend_alb_ingress_rules : {}

  security_group_id = aws_security_group.backend_alb[0].id
  description       = "Acceso a la UI/API de la PoC"
  cidr_ipv4         = each.value.cidr
  ip_protocol       = "tcp"
  from_port         = each.value.port
  to_port           = each.value.port
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

    # Ninguna subnet ajena al descubrimiento de red autorizado.
    precondition {
      condition = length(setsubtract(
        var.backend_alb_subnet_ids, var.backend_candidate_subnet_ids
      )) == 0
      error_message = "backend_alb_subnet_ids sólo admite subnets de backend_candidate_subnet_ids."
    }

    # Exponer el ALB sin orígenes autorizados dejaría un balanceador inalcanzable
    # o, peor, invitaría a abrirlo después a mano.
    precondition {
      condition     = length(var.backend_alb_ingress_cidrs) > 0
      error_message = "backend_alb_ingress_cidrs es obligatoria: declara los orígenes autorizados de la red corporativa."
    }

    # Ni siquiera un ALB público admite un prefijo /0.
    precondition {
      condition = alltrue([
        for cidr in var.backend_alb_ingress_cidrs : tonumber(split("/", cidr)[1]) > 0
      ])
      error_message = "Ningún origen puede ser 0.0.0.0/0: restringe backend_alb_ingress_cidrs a la red corporativa."
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

  # Con certificado, el listener HTTP deja de servir tráfico y sólo redirige.
  dynamic "default_action" {
    for_each = local.backend_alb_https_enabled == 1 ? [] : [1]

    content {
      type             = "forward"
      target_group_arn = aws_lb_target_group.backend[0].arn
    }
  }

  dynamic "default_action" {
    for_each = local.backend_alb_https_enabled == 1 ? [1] : []

    content {
      type = "redirect"

      redirect {
        port        = "443"
        protocol    = "HTTPS"
        status_code = "HTTP_301"
      }
    }
  }

  tags = merge(local.common_tags, { Name = "${local.backend_alb_name}-listener" })
}

# HTTPS sólo cuando existe un certificado de ACM: no se inventa ni nombre DNS ni
# certificado. Sin él, la PoC queda en HTTP con los orígenes restringidos.
resource "aws_lb_listener" "backend_https" {
  count = local.backend_alb_enabled * local.backend_alb_https_enabled

  load_balancer_arn = aws_lb.backend[0].arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.backend_alb_certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.backend[0].arn
  }

  tags = merge(local.common_tags, { Name = "${local.backend_alb_name}-listener-https" })
}
