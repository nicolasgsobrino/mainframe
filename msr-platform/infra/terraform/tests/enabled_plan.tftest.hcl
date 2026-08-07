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

  # Instance profile corporativo existente: sólo lectura, nunca gestionado.
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

  # Operación normal: el grupo debe poder lanzar la instancia.
  assert {
    condition     = length(aws_autoscaling_group.lab[0].suspended_processes) == 0
    error_message = "Con asg_launch_suspended = false no puede suspenderse ningún proceso."
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
    # El instance profile es un data source: se consume su ARN, no se crea.
    condition = (
      aws_launch_template.lab[0].iam_instance_profile[0].arn
      == "arn:aws:iam::133789123239:instance-profile/EC2SSMAgentProfileL0"
    )
    error_message = "El Launch Template debe usar el instance profile corporativo existente."
  }

  assert {
    condition     = aws_launch_template.lab[0].tag_specifications[0].tags["PatchGroup"] == "msr-poc-linux"
    error_message = "El tag del patch group debe ser `PatchGroup`, sin espacio."
  }

  # Patch Manager reconoce `PatchGroup` igual que `Patch Group`: el baseline
  # personalizado sigue asociado al mismo valor que lleva la instancia.
  assert {
    condition = (
      aws_ssm_patch_group.lab[0].patch_group == var.patch_group &&
      aws_launch_template.lab[0].tag_specifications[0].tags["PatchGroup"] == var.patch_group
    )
    error_message = "El tag de la instancia y el patch group registrado deben coincidir."
  }

  # 10 recursos: los 18 anteriores menos los ocho recursos IAM propios, que la
  # cuenta no permite crear (DenyIAMUser).
  assert {
    condition     = length(output.estimated_resource_summary.resources) == 10
    error_message = "El resumen debe enumerar exactamente los recursos planificados."
  }

  assert {
    condition = length([
      for name in output.estimated_resource_summary.resources :
      name if startswith(name, "aws_iam_")
    ]) == 0
    error_message = "Terraform no puede gestionar ningún recurso IAM."
  }

  assert {
    condition     = output.instance_profile_arn == "arn:aws:iam::133789123239:instance-profile/EC2SSMAgentProfileL0"
    error_message = "instance_profile_arn debe devolver el ARN del profile existente."
  }

  assert {
    condition = (
      output.backend_credential_mode == "ambient-caller" &&
      output.automation_credential_mode == "caller-context"
    )
    error_message = "Backend y Automation usan credenciales del contexto, sin roles propios."
  }

  assert {
    condition = (
      output.required_backend_environment.MSR_AWS_ROLE_ARN == "" &&
      !contains(keys(output.required_backend_environment), "MSR_AUTOMATION_ASSUME_ROLE_ARN")
    )
    error_message = "El entorno del backend no puede exigir ningún role ARN."
  }
}

run "the_enabled_plan_requires_the_existing_instance_profile" {
  command = plan

  variables {
    existing_instance_profile_name      = ""
    existing_instance_profile_role_name = ""
  }

  expect_failures = [aws_launch_template.lab, check.instance_profile]
}

# Las claves corporativas se ignoran por configuración; las funcionales de la
# PoC nunca pueden excluirse de la gestión de Terraform.
run "the_ignored_tag_keys_reject_duplicates" {
  command = plan

  variables {
    externally_managed_tag_keys = ["APPID", "APPID"]
  }

  expect_failures = [var.externally_managed_tag_keys]
}

run "the_ignored_tag_keys_reject_the_functional_tags" {
  command = plan

  variables {
    externally_managed_tag_keys = ["Name", "PatchGroup", "msr-lab-id"]
  }

  expect_failures = [var.externally_managed_tag_keys]
}

run "the_corporate_tag_keys_can_be_ignored" {
  command = plan

  variables {
    externally_managed_tag_keys = [
      "APPID", "BILLINGCODE", "BILLINGCONTACT", "BUSINESSAREA", "CMS",
      "COUNTRY", "CSCLASS", "CSQUAL", "CSTYPE", "ENVIRONMENT", "FUNCTION",
      "GROUPCONTACT", "MEMBERFIRM", "PRIMARYCONTACT", "SECONDARYCONTACT",
    ]
  }

  # Ignorar etiquetas externas no altera las de la PoC ni el número de recursos.
  assert {
    condition = (
      aws_launch_template.lab[0].tag_specifications[0].tags["PatchGroup"] == var.patch_group &&
      aws_launch_template.lab[0].tag_specifications[0].tags["msr-lab-id"] == var.lab_id
    )
    error_message = "Las etiquetas funcionales siguen gestionadas por Terraform."
  }

  assert {
    condition     = length(output.estimated_resource_summary.resources) == 10
    error_message = "El resumen debe seguir enumerando diez recursos."
  }
}

# Recuperación controlada: el grupo conserva `Launch` suspendido mientras se
# corrigen Launch Template, instance profile y etiquetas.
run "the_recovery_mode_keeps_launch_suspended" {
  command = plan

  variables {
    asg_launch_suspended = true
  }

  assert {
    condition     = aws_autoscaling_group.lab[0].suspended_processes == toset(["Launch"])
    error_message = "La recuperación sólo puede suspender el proceso Launch."
  }

  assert {
    condition = (
      aws_autoscaling_group.lab[0].min_size == 1 &&
      aws_autoscaling_group.lab[0].max_size == 1 &&
      aws_autoscaling_group.lab[0].desired_capacity == 1
    )
    error_message = "La contención no altera la capacidad fija del laboratorio."
  }
}

# Reproduce el escenario del plan fallido: el precondition del ASG detiene el
# plan y deja fuera el propio ASG (9 de 10 recursos).
run "a_newer_ami_stops_the_enabled_plan" {
  command = plan

  variables {
    source_ami_release = "2023.12.20260801.0"
  }

  expect_failures = [aws_autoscaling_group.lab]
}
