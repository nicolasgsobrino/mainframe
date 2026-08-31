locals {
  user_data = templatefile("${path.module}/user-data.sh.tftpl", {
    source_ami_id            = var.source_ami_id
    source_ami_release       = var.source_ami_release
    candidate_advisory_id    = var.candidate_advisory_id
    candidate_releasever     = var.candidate_releasever
    expected_fixed_kernel    = var.expected_fixed_kernel
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

  # Instance profile corporativo preexistente: la cuenta deniega iam:PutRolePolicy,
  # iam:AttachRolePolicy e iam:UpdateAssumeRolePolicy, así que la PoC no gestiona IAM.
  iam_instance_profile {
    arn = data.aws_iam_instance_profile.existing[0].arn
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

    # Sin instance profile corporativo la instancia no sería un managed node y la
    # cuenta no permite que la PoC cree uno propio.
    precondition {
      condition = (
        var.existing_instance_profile_name != "" &&
        var.existing_instance_profile_role_name != ""
      )
      error_message = "existing_instance_profile_name y existing_instance_profile_role_name son obligatorios con enable_real_resources = true."
    }

    precondition {
      condition     = data.aws_iam_instance_profile.existing[0].role_name == var.existing_instance_profile_role_name
      error_message = "El instance profile ${var.existing_instance_profile_name} no contiene el rol ${var.existing_instance_profile_role_name}."
    }

    precondition {
      condition     = data.aws_iam_instance_profile.existing[0].arn == "arn:aws:iam::${var.aws_account_id}:instance-profile/${var.existing_instance_profile_name}"
      error_message = "El instance profile no pertenece a la cuenta ${var.aws_account_id}."
    }
  }
}

# La instancia del laboratorio la mantiene un Auto Scaling Group de capacidad
# fija 1: el reset sustituye la instancia dentro del grupo, de modo que Terraform
# conserva el control del laboratorio y un `plan` posterior no intenta crear una
# segunda instancia independiente (que es lo que ocurría con `aws_instance`).
resource "aws_autoscaling_group" "lab" {
  count = local.enabled

  name                = "${local.name_prefix}-asg"
  min_size            = 1
  max_size            = 1
  desired_capacity    = 1
  vpc_zone_identifier = [var.subnet_id]

  health_check_type         = "EC2"
  health_check_grace_period = var.asg_health_check_grace_period_seconds
  capacity_rebalance        = false
  # El reset debe poder sustituir la instancia: sin protección de scale-in.
  protect_from_scale_in = false

  # Estado deseado explícito, nunca oculto con `ignore_changes`: durante una
  # recuperación controlada el grupo no debe lanzar instancias hasta que el
  # Launch Template, el instance profile y las etiquetas estén corregidos.
  suspended_processes = var.asg_launch_suspended ? ["Launch"] : []

  launch_template {
    id = aws_launch_template.lab[0].id
    # Versión fija y explícita: nunca $Latest ni $Default.
    version = aws_launch_template.lab[0].latest_version
  }

  dynamic "tag" {
    for_each = local.instance_tags

    content {
      key                 = tag.key
      value               = tag.value
      propagate_at_launch = true
    }
  }

  lifecycle {
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
        var.candidate_releasever != "",
        var.expected_fixed_kernel != "",
      ])
      error_message = "Faltan valores obligatorios para una ejecución real."
    }

    precondition {
      # La AMI base debe ser ANTERIOR a la release que corrige el advisory; en
      # caso contrario la imagen ya vendría parcheada y la PoC no demostraría
      # nada. La comparación es numérica sobre la fecha YYYYMMDD: Terraform no
      # admite `<` entre strings y el orden lexicográfico no es cronológico.
      condition     = local.ami_release_precedes_fix
      error_message = "La AMI base (${var.source_ami_release}) no es anterior a ${var.candidate_releasever}: ya contendría la corrección."
    }
  }
}
