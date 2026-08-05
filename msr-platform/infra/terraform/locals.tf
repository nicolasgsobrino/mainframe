locals {
  name_prefix = "msr-poc-${var.lab_id}"

  # Interruptor maestro: mientras sea 0 no se crea ningún recurso mutativo.
  enabled = var.enable_real_resources ? 1 : 0

  # Nombre determinista del Auto Scaling Group del laboratorio.
  autoscaling_group_name = "${local.name_prefix}-asg"

  # Tags que identifican inequívocamente al laboratorio. El runbook de reset
  # sólo puede terminar una instancia que los tenga todos.
  lab_required_tags = {
    "msr-poc"         = "true"
    "msr-lab-id"      = var.lab_id
    "msr-environment" = var.environment_tag
    "msr-resettable"  = "true"
  }

  cost_tags = {
    "msr-cost-center" = var.cost_center
    "msr-owner"       = var.owner
  }

  common_tags = merge(local.cost_tags, var.extra_tags, {
    "msr-poc"        = "true"
    "msr-managed-by" = "terraform"
  })

  instance_tags = merge(
    local.common_tags,
    local.lab_required_tags,
    {
      "Name"        = "msr-poc-${var.lab_id}"
      "Patch Group" = var.patch_group
    },
  )

  # Orden temporal entre la AMI base y la corrección del advisory. Terraform no
  # admite `<`/`>` entre strings, y comparar `2023.11` con `2023.12` como texto
  # sería lexicográfico: la relación se deriva de la fecha YYYYMMDD como número.
  source_ami_release_product = join(".", slice(split(".", var.source_ami_release), 0, 2))
  candidate_release_product  = join(".", slice(split(".", var.candidate_releasever), 0, 2))
  source_ami_release_date    = tonumber(split(".", var.source_ami_release)[2])
  candidate_release_date     = tonumber(split(".", var.candidate_releasever)[2])

  # Ambos productos deben ser Amazon Linux 2023 y la AMI estrictamente anterior.
  releases_are_amazon_linux_2023 = (
    startswith(local.source_ami_release_product, "2023.") &&
    startswith(local.candidate_release_product, "2023.")
  )
  ami_release_precedes_fix = (
    local.releases_are_amazon_linux_2023 &&
    local.source_ami_release_date < local.candidate_release_date
  )

  # Valores que el backend debe recibir por entorno (ver outputs).
  backend_environment = {
    MSR_AWS_REGION                  = var.aws_region
    MSR_ALLOWED_ACCOUNT_IDS         = var.aws_account_id
    MSR_ALLOWED_REGIONS             = var.aws_region
    MSR_ALLOWED_ENVIRONMENTS        = var.environment_tag
    MSR_REQUIRED_TARGET_TAG_KEY     = "msr-poc"
    MSR_REQUIRED_TARGET_TAG_VALUE   = "true"
    MSR_LAB_LOGICAL_ID              = var.lab_id
    MSR_LAB_AUTOSCALING_GROUP_NAME  = local.autoscaling_group_name
    MSR_PATCH_ADVISORY_ID           = var.candidate_advisory_id
    MSR_PATCH_RELEASEVER            = var.candidate_releasever
    MSR_PATCH_EXPECTED_FIXED_KERNEL = var.expected_fixed_kernel
    MSR_PATCH_RUNBOOK_NAME          = var.patch_runbook_name
    MSR_RESET_RUNBOOK_NAME          = var.reset_runbook_name
  }
}
