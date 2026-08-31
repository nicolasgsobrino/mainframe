# Security Group del laboratorio: sin reglas de entrada (no hay SSH ni UI
# expuesta; la instancia se administra exclusivamente por SSM) y salida
# suficiente para DNS, HTTPS (Systems Manager) y los repositorios de Amazon
# Linux, que se sirven por HTTPS desde endpoints regionales de S3.

resource "aws_security_group" "lab" {
  count = local.enabled

  name        = "${local.name_prefix}-sg"
  description = "MSR PoC: sin ingress; egress DNS/HTTPS para SSM y repositorios"
  vpc_id      = var.vpc_id

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-sg" })

  lifecycle {
    precondition {
      condition     = data.aws_subnet.lab[0].vpc_id == var.vpc_id
      error_message = "La subnet ${var.subnet_id} no pertenece a la VPC ${var.vpc_id}."
    }

    precondition {
      condition     = var.allowed_ui_cidr != "0.0.0.0/0"
      error_message = "allowed_ui_cidr no puede estar abierto a Internet."
    }
  }
}

# Sin `aws_vpc_security_group_ingress_rule`: la PoC no abre ningún puerto de
# entrada. El health check se ejecuta dentro de la instancia (127.0.0.1).

resource "aws_vpc_security_group_egress_rule" "https" {
  count = local.enabled

  security_group_id = aws_security_group.lab[0].id
  description       = "HTTPS: Systems Manager y repositorios de Amazon Linux"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
}

resource "aws_vpc_security_group_egress_rule" "dns_udp" {
  count = local.enabled

  security_group_id = aws_security_group.lab[0].id
  description       = "DNS (UDP) hacia el resolver de la VPC"
  cidr_ipv4         = data.aws_vpc.lab[0].cidr_block
  ip_protocol       = "udp"
  from_port         = 53
  to_port           = 53
}

resource "aws_vpc_security_group_egress_rule" "dns_tcp" {
  count = local.enabled

  security_group_id = aws_security_group.lab[0].id
  description       = "DNS (TCP) hacia el resolver de la VPC"
  cidr_ipv4         = data.aws_vpc.lab[0].cidr_block
  ip_protocol       = "tcp"
  from_port         = 53
  to_port           = 53
}
