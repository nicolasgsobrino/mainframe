locals {
  # El advisory, los tags y la cuenta se fijan aquí (IaC), nunca desde el
  # frontend ni desde parámetros de entrada del runbook.
  document_vars = {
    aws_account_id           = var.aws_account_id
    aws_region               = var.aws_region
    lab_id                   = var.lab_id
    candidate_advisory_id    = var.candidate_advisory_id
    candidate_package_family = var.candidate_package_family
    source_ami_id            = var.source_ami_id
    required_tags_json       = jsonencode(local.lab_required_tags)
    instance_tags_json = jsonencode([
      for key, value in local.instance_tags : { Key = key, Value = value }
    ])
    automation_role_arn     = try(aws_iam_role.automation[0].arn, "arn:aws:iam::${var.aws_account_id}:role/${local.name_prefix}-automation-role")
    launch_template_id      = try(aws_launch_template.lab[0].id, "lt-00000000")
    launch_template_version = try(tostring(aws_launch_template.lab[0].latest_version), "1")
  }

  patch_document_content = templatefile("${path.module}/documents/MSR-PatchLinuxInstance.yaml",
  local.document_vars)

  reset_document_content = templatefile("${path.module}/documents/MSR-ResetLabInstance.yaml",
  local.document_vars)
}

resource "aws_ssm_document" "patch" {
  count = local.enabled

  name            = var.patch_runbook_name
  document_type   = "Automation"
  document_format = "YAML"
  content         = local.patch_document_content
  target_type     = "/AWS::EC2::Instance"
  tags            = merge(local.common_tags, { Name = var.patch_runbook_name })
}

resource "aws_ssm_document" "reset" {
  count = local.enabled

  name            = var.reset_runbook_name
  document_type   = "Automation"
  document_format = "YAML"
  content         = local.reset_document_content
  target_type     = "/AWS::EC2::Instance"
  tags            = merge(local.common_tags, { Name = var.reset_runbook_name })
}
