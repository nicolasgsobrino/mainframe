locals {
  user_data = templatefile("${path.module}/user-data.sh.tftpl", {
    source_ami_id            = var.source_ami_id
    candidate_advisory_id    = var.candidate_advisory_id
    candidate_package_family = var.candidate_package_family
    lab_id                   = var.lab_id
  })
}

# Launch Template: única definición de la instancia del laboratorio. El runbook
# de reset recrea la instancia SIEMPRE desde aquí, con una versión fija.
resource "aws_launch_template" "lab" {
  count = local.enabled

  name        = "${local.name_prefix}-lt"
  description = "MSR PoC: instancia vulnerable reutilizable (${var.lab_id})"

  image_id      = var.source_ami_id
  instance_type = var.instance_type
  # Sin key pair: el acceso es exclusivamente por Systems Manager.
  key_name  = null
  user_data = base64encode(local.user_data)

  iam_instance_profile {
    arn = aws_iam_instance_profile.instance[0].arn
  }

  network_interfaces {
    device_index                = 0
    subnet_id                   = var.subnet_id
    associate_public_ip_address = true
    security_groups             = [aws_security_group.lab[0].id]
    delete_on_termination       = true
  }

  block_device_mappings {
    device_name = "/dev/xvda"

    ebs {
      volume_type           = "gp3"
      volume_size           = var.root_volume_size_gib
      encrypted             = true
      delete_on_termination = true
    }
  }

  metadata_options {
    http_tokens                 = "required" # IMDSv2 obligatorio
    http_endpoint               = "enabled"
    http_put_response_hop_limit = 1
    instance_metadata_tags      = "enabled"
  }

  monitoring {
    enabled = false
  }

  tag_specifications {
    resource_type = "instance"
    tags          = local.instance_tags
  }

  tag_specifications {
    resource_type = "volume"
    tags          = local.instance_tags
  }

  tags = local.common_tags

  lifecycle {
    precondition {
      condition     = data.aws_ami.lab[0].architecture == "x86_64"
      error_message = "La AMI ${var.source_ami_id} no es x86_64."
    }

    precondition {
      condition     = contains(["amazon", "137112412989"], data.aws_ami.lab[0].owner_id)
      error_message = "La AMI ${var.source_ami_id} no pertenece a Amazon."
    }
  }
}

resource "aws_instance" "lab" {
  count = local.enabled

  launch_template {
    id      = aws_launch_template.lab[0].id
    version = aws_launch_template.lab[0].latest_version
  }

  tags        = local.instance_tags
  volume_tags = local.instance_tags

  lifecycle {
    # El reset del laboratorio se hace por runbook, no recreando desde Terraform.
    ignore_changes = [launch_template, tags, volume_tags]

    precondition {
      condition     = data.aws_caller_identity.current[0].account_id == var.aws_account_id
      error_message = "Las credenciales pertenecen a una cuenta distinta de ${var.aws_account_id}."
    }

    precondition {
      condition     = data.aws_region.current[0].name == var.aws_region
      error_message = "La región efectiva no es ${var.aws_region}."
    }

    precondition {
      condition     = data.aws_subnet.lab[0].vpc_id == var.vpc_id
      error_message = "La subnet ${var.subnet_id} no pertenece a la VPC ${var.vpc_id}."
    }

    precondition {
      condition = alltrue([
        var.lab_id != "",
        var.source_ami_id != "",
        var.subnet_id != "",
        var.vpc_id != "",
        var.candidate_advisory_id != "",
        var.operator_role_arn != "",
      ])
      error_message = "Faltan valores obligatorios para una ejecución real."
    }
  }
}
