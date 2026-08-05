# Plan completo con `enable_real_resources = true` sobre un provider simulado.
#
# Llega más allá del precondition del Auto Scaling Group que rompió el primer
# plan real, sin credenciales ni llamadas a AWS: `mock_provider` devuelve los
# valores declarados aquí para caller identity, región, VPC, subnet y AMI.

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

  mock_data "aws_iam_policy_document" {
    defaults = {
      json = "{}"
    }
  }
}

variables {
  enable_real_resources = true
}

run "the_default_configuration_plans_nothing" {
  command = plan

  variables {
    enable_real_resources = false
  }

  assert {
    condition     = length(aws_autoscaling_group.lab) == 0
    error_message = "Con enable_real_resources = false no puede planificarse ningún recurso."
  }

  assert {
    condition     = output.estimated_resource_summary.enabled == false
    error_message = "El interruptor maestro debe seguir desactivado por defecto."
  }
}

run "the_enabled_configuration_plans_every_resource" {
  command = plan

  # Supera el precondition que rompió el primer plan real.
  assert {
    condition     = length(aws_autoscaling_group.lab) == 1
    error_message = "El Auto Scaling Group debe planificarse con la configuración habilitada."
  }

  assert {
    condition = (
      aws_autoscaling_group.lab[0].min_size == 1 &&
      aws_autoscaling_group.lab[0].max_size == 1 &&
      aws_autoscaling_group.lab[0].desired_capacity == 1
    )
    error_message = "El ASG del laboratorio es de capacidad fija 1/1/1."
  }

  assert {
    condition     = length(aws_launch_template.lab) == 1 && length(aws_ssm_document.patch) == 1
    error_message = "Launch Template y runbooks deben planificarse."
  }

  assert {
    condition     = aws_ssm_patch_baseline.lab[0].approved_patches == toset(["ALAS2023-2026-1924"])
    error_message = "El baseline sólo puede aprobar el advisory candidato."
  }

  assert {
    # Depende del ARN del ASG: si el ASG no se planifica, esta política tampoco.
    condition     = length(aws_iam_role_policy.automation) == 1
    error_message = "La política del rol de Automation debe planificarse con el ASG."
  }

  # 18 recursos: los 16 del plan fallido más `aws_autoscaling_group.lab` (que
  # abortó por el operando inválido) y `aws_iam_role_policy.automation`, que
  # depende de su ARN.
  assert {
    condition     = length(output.estimated_resource_summary.resources) == 18
    error_message = "El resumen debe enumerar exactamente los recursos planificados."
  }
}

# Reproduce el escenario del plan fallido: el precondition del ASG detiene el
# plan y deja fuera el propio ASG y la política que depende de su ARN (16 de 18).
run "a_newer_ami_stops_the_enabled_plan" {
  command = plan

  variables {
    source_ami_release = "2023.12.20260801.0"
  }

  expect_failures = [aws_autoscaling_group.lab]
}
