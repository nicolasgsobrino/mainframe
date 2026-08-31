# Patch baseline específico de la PoC: aprueba EXCLUSIVAMENTE el advisory
# candidato, sin comodines y sin actualizaciones que no sean de seguridad.
#
# Limitación documentada de Patch Manager: `approved_patches` acepta advisory
# IDs de Amazon Linux (ALASxxxx) como identificadores literales, pero no existe
# una API para verificar que el advisory existe en el repositorio; si el ID no
# es válido, `AWS-RunPatchBaseline` sencillamente no instalará nada y la
# operación `Scan` lo reflejará como «sin parches aprobados aplicables». Por eso
# el runbook ejecuta un precheck con `dnf updateinfo` y aborta con
# ADVISORY_NOT_APPLICABLE en lugar de dar por buena una ejecución vacía.
#
# `approval_rules` se omite deliberadamente: cualquier regla por severidad o
# antigüedad ampliaría el alcance más allá del advisory aprobado.

resource "aws_ssm_patch_baseline" "lab" {
  count = local.enabled

  name             = "msr-poc-al2023-baseline"
  description      = "MSR PoC: aprueba únicamente ${var.candidate_advisory_id}"
  operating_system = "AMAZON_LINUX_2023"

  approved_patches                     = [var.candidate_advisory_id]
  approved_patches_compliance_level    = "CRITICAL"
  approved_patches_enable_non_security = false
  rejected_patches_action              = "ALLOW_AS_DEPENDENCY"

  tags = merge(local.common_tags, { Name = "msr-poc-al2023-baseline" })
}

# Asociación entre el baseline y el patch group. Patch Manager reconoce las dos
# claves equivalentes `Patch Group` y `PatchGroup`; la instancia usa la variante
# sin espacio porque EC2 rechaza los espacios en las claves de tag cuando el
# Launch Template las expone por IMDS (`instance_metadata_tags = "enabled"`).
# Una instancia con `PatchGroup = msr-poc-linux` resuelve este baseline al
# ejecutar `AWS-RunPatchBaseline`, no el predeterminado del sistema operativo.
resource "aws_ssm_patch_group" "lab" {
  count = local.enabled

  baseline_id = aws_ssm_patch_baseline.lab[0].id
  patch_group = var.patch_group
}
