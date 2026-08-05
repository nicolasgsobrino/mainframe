# Todas las consultas son de sólo lectura y sólo se evalúan cuando
# `enable_real_resources = true`: con el valor predeterminado Terraform no
# contacta con la cuenta más allá de la validación del provider.

data "aws_caller_identity" "current" {
  count = local.enabled
}

data "aws_region" "current" {
  count = local.enabled
}

data "aws_vpc" "lab" {
  count = local.enabled
  id    = var.vpc_id
}

data "aws_subnet" "lab" {
  count = local.enabled
  id    = var.subnet_id
}

data "aws_ami" "lab" {
  count  = local.enabled
  owners = ["amazon"]

  filter {
    name   = "image-id"
    values = [var.source_ami_id]
  }
}

# Instance profile corporativo: sólo lectura. Terraform no lo crea, no lo etiqueta
# y no lo modifica; tampoco gestiona el rol que contiene.
data "aws_iam_instance_profile" "existing" {
  count = local.enabled
  name  = var.existing_instance_profile_name
}

# Instancia que el ASG mantiene viva en este momento. Es sólo informativa: el
# Instance ID cambia con cada reset y el backend lo resuelve por tags, nunca desde
# el estado de Terraform.
data "aws_instances" "lab" {
  count = local.enabled

  instance_tags        = local.instance_tags
  instance_state_names = ["running"]

  depends_on = [aws_autoscaling_group.lab]
}

# --- Guardrails: cualquier desviación detiene el apply -----------------------
#
# Las condiciones se escriben como `alltrue([for ... ])` sobre la lista del data
# source: HCL evalúa ambos operandos de `||`, así que un `one(...)` sobre una
# lista vacía (con `enable_real_resources = false`) haría fallar la expresión en
# lugar de darla por buena.

check "account_and_region" {
  assert {
    condition = alltrue([
      for identity in data.aws_caller_identity.current :
      identity.account_id == var.aws_account_id
    ])
    error_message = "Las credenciales apuntan a una cuenta distinta de ${var.aws_account_id}."
  }

  assert {
    condition = alltrue([
      for region in data.aws_region.current : region.name == var.aws_region
    ])
    error_message = "La región efectiva no es ${var.aws_region}."
  }
}

check "network" {
  assert {
    condition = alltrue([
      for subnet in data.aws_subnet.lab : subnet.vpc_id == var.vpc_id
    ])
    error_message = "La subnet ${var.subnet_id} no pertenece a la VPC ${var.vpc_id}."
  }

  assert {
    condition = alltrue([
      for vpc in data.aws_vpc.lab : vpc.id == var.vpc_id
    ])
    error_message = "La VPC resuelta no coincide con vpc_id."
  }
}

check "instance_profile" {
  assert {
    condition = alltrue([
      for profile in data.aws_iam_instance_profile.existing :
      profile.role_name == var.existing_instance_profile_role_name
    ])
    error_message = "El instance profile ${var.existing_instance_profile_name} no contiene el rol ${var.existing_instance_profile_role_name}."
  }

  assert {
    condition = alltrue([
      for profile in data.aws_iam_instance_profile.existing :
      profile.arn == "arn:aws:iam::${var.aws_account_id}:instance-profile/${var.existing_instance_profile_name}"
    ])
    error_message = "El instance profile no pertenece a la cuenta ${var.aws_account_id}."
  }
}

check "ami" {
  assert {
    condition = alltrue([
      for ami in data.aws_ami.lab : ami.architecture == "x86_64"
    ])
    error_message = "La AMI ${var.source_ami_id} no es x86_64."
  }

  assert {
    condition = alltrue([
      for ami in data.aws_ami.lab :
      contains(["amazon", "137112412989"], ami.owner_id)
    ])
    error_message = "La AMI ${var.source_ami_id} no pertenece a Amazon."
  }
}
