# Bootstrap único de la identidad federada del backend externo.
#
# La aplicación se ejecuta en la VM de la sesión de Devin, así que su identidad
# es un rol asumido con OIDC. Este Terraform no crea el proveedor, el rol ni la
# tabla: publica los documentos exactos que aplica el equipo de cloud. Sin
# credenciales y sin llamadas a AWS: todo se comprueba sobre el plan.

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
      cidr_block = "172.31.0.0/16"
    }
  }

  mock_data "aws_subnet" {
    defaults = {
      id                = "subnet-0bb97e6254e4f83e9"
      vpc_id            = "vpc-023864c0ca3c82eab"
      availability_zone = "eu-north-1a"
      cidr_block        = "172.31.0.0/20"
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

  mock_data "aws_iam_instance_profile" {
    defaults = {
      arn       = "arn:aws:iam::133789123239:instance-profile/EC2SSMAgentProfileL0"
      role_name = "EC2SSMAgentProfile"
      role_arn  = "arn:aws:iam::133789123239:role/EC2SSMAgentProfile"
    }
  }
}

run "the_trust_policy_only_admits_the_verified_devin_organization" {
  command = plan

  # --- el sujeto verificado del token, literal y sin comodines ------------
  assert {
    condition = (
      jsondecode(output.backend_external_role_bootstrap.role.trust_policy_json).Statement[0].Condition.StringEquals["deloitte-es.devinenterprise.com:sub"] ==
      "org_id:org-4793cba689a54a11b8fe70ed031524c4"
    )
    error_message = "El sub debe ser el valor verificado del token de la organización."
  }

  assert {
    condition = (
      jsondecode(output.backend_external_role_bootstrap.role.trust_policy_json).Statement[0].Condition.StringEquals["deloitte-es.devinenterprise.com:aud"] ==
      "sts.amazonaws.com"
    )
    error_message = "La audiencia debe ser sts.amazonaws.com."
  }

  assert {
    condition = (
      jsondecode(output.backend_external_role_bootstrap.role.trust_policy_json).Statement[0].Action ==
      "sts:AssumeRoleWithWebIdentity" &&
      jsondecode(output.backend_external_role_bootstrap.role.trust_policy_json).Statement[0].Principal.Federated ==
      "arn:aws:iam::133789123239:oidc-provider/deloitte-es.devinenterprise.com"
    )
    error_message = "El rol se asume por federación web, nunca con claves ni por otro principal."
  }

  # Un sub con comodín aceptaría cualquier organización del despliegue.
  assert {
    condition = !strcontains(
      jsondecode(output.backend_external_role_bootstrap.role.trust_policy_json).Statement[0].Condition.StringEquals["deloitte-es.devinenterprise.com:sub"],
      "*"
    )
    error_message = "El sub no admite comodines."
  }

  assert {
    condition = (
      output.backend_external_role_bootstrap.oidc_provider.url == "https://deloitte-es.devinenterprise.com" &&
      output.backend_external_role_bootstrap.oidc_provider.client_id == "sts.amazonaws.com"
    )
    error_message = "El proveedor OIDC debe declarar el emisor y la audiencia verificados."
  }
}

run "the_permission_policy_of_the_federated_role_stays_least_privilege" {
  command = plan

  # --- misma política que el resto de la PoC: sin PassRole ni comodines ---
  assert {
    condition = (
      output.backend_external_role_bootstrap.role.permission_policy_json ==
      output.backend_task_role_permission_policy_json
    )
    error_message = "Las llamadas a AWS no cambian con el alojamiento: la política es la misma."
  }

  assert {
    condition = !strcontains(
      output.backend_external_role_bootstrap.role.permission_policy_json, "iam:PassRole"
    )
    error_message = "No hay service role de Automation: iam:PassRole nunca es necesario."
  }

  # --- lock: sólo las tres acciones usadas y sólo sobre su tabla ----------
  assert {
    condition = length([
      for statement in jsondecode(output.backend_external_role_bootstrap.role.permission_policy_json).Statement :
      statement if length([for action in statement.Action : action if startswith(action, "dynamodb:")]) > 0 &&
      (statement.Resource != "arn:aws:dynamodb:eu-north-1:133789123239:table/msr-poc-lab-locks" ||
      length(setsubtract(statement.Action, ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:DeleteItem"])) > 0)
    ]) == 0
    error_message = "DynamoDB: sólo Get/Put/DeleteItem y sólo sobre la tabla de locks."
  }

  assert {
    condition = (
      output.backend_external_role_bootstrap.lock_table.partition_key == "lab_id" &&
      output.backend_external_role_bootstrap.lock_table.ttl_attribute == "expires_at" &&
      output.backend_external_role_bootstrap.lock_table.billing_mode == "PAY_PER_REQUEST"
    )
    error_message = "La tabla de locks se define por lab_id con TTL en expires_at y bajo demanda."
  }
}

run "the_bootstrap_creates_nothing_from_this_terraform" {
  command = plan

  assert {
    condition     = length(aws_dynamodb_table.lab_locks) == 0
    error_message = "El bootstrap es una operación del equipo de cloud: aquí no se crea la tabla."
  }

  assert {
    condition     = output.backend_task_role_is_managed_by_terraform == false
    error_message = "Este Terraform nunca gestiona el rol de la aplicación."
  }
}
