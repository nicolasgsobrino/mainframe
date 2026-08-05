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

# --- Guardrails: cualquier desviación detiene el apply -----------------------

check "account_and_region" {
  assert {
    condition = !var.enable_real_resources || (
      one(data.aws_caller_identity.current[*].account_id) == var.aws_account_id
    )
    error_message = "Las credenciales apuntan a una cuenta distinta de ${var.aws_account_id}."
  }

  assert {
    condition = !var.enable_real_resources || (
      one(data.aws_region.current[*].name) == var.aws_region
    )
    error_message = "La región efectiva no es ${var.aws_region}."
  }
}

check "network" {
  assert {
    condition = !var.enable_real_resources || (
      one(data.aws_subnet.lab[*].vpc_id) == var.vpc_id
    )
    error_message = "La subnet ${var.subnet_id} no pertenece a la VPC ${var.vpc_id}."
  }

  assert {
    condition = !var.enable_real_resources || (
      one(data.aws_vpc.lab[*].id) == var.vpc_id
    )
    error_message = "La VPC resuelta no coincide con vpc_id."
  }
}

check "ami" {
  assert {
    condition = !var.enable_real_resources || (
      one(data.aws_ami.lab[*].architecture) == "x86_64"
    )
    error_message = "La AMI ${var.source_ami_id} no es x86_64."
  }

  assert {
    condition = !var.enable_real_resources || (
      contains(["amazon", "137112412989"], one(data.aws_ami.lab[*].owner_id))
    )
    error_message = "La AMI ${var.source_ami_id} no pertenece a Amazon."
  }
}
