# Trust policy del rol de Automation, evaluada sobre el JSON real.

mock_provider "aws" {}

variables {
  enable_real_resources = false
}

run "the_trust_policy_requires_source_account_and_source_arn" {
  command = plan

  assert {
    condition = (
      jsondecode(output.automation_trust_policy).Statement[0].Principal.Service
      == "ssm.amazonaws.com"
    )
    error_message = "El único principal de servicio debe ser ssm.amazonaws.com."
  }

  assert {
    condition     = length(jsondecode(output.automation_trust_policy).Statement) == 1
    error_message = "El trust no puede ampliarse con statements adicionales."
  }

  assert {
    condition = (
      jsondecode(output.automation_trust_policy).Statement[0].Condition.StringEquals["aws:SourceAccount"]
      == "133789123239"
    )
    error_message = "aws:SourceAccount debe ser la cuenta configurada."
  }

  assert {
    condition = (
      jsondecode(output.automation_trust_policy).Statement[0].Condition.ArnLike["aws:SourceArn"]
      == "arn:aws:ssm:eu-north-1:133789123239:automation-execution/*"
    )
    error_message = "aws:SourceArn debe acotarse a automation-execution/* de la cuenta y región."
  }
}

run "the_source_arn_follows_the_configured_account_and_region" {
  command = plan

  variables {
    aws_region     = "eu-west-1"
    aws_account_id = "210987654321"
  }

  assert {
    condition = (
      jsondecode(output.automation_trust_policy).Statement[0].Condition.ArnLike["aws:SourceArn"]
      == "arn:aws:ssm:eu-west-1:210987654321:automation-execution/*"
    )
    error_message = "El ARN debe derivarse de aws_region y aws_account_id, no estar fijado."
  }
}
