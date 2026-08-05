output "lab_instance_id" {
  description = <<-EOT
    Instancia actual del laboratorio. Es un valor DINÁMICO: lo mantiene el Auto
    Scaling Group y cambia con cada reset, así que no debe fijarse en el backend
    (que resuelve la instancia por tags). Vacío con enable_real_resources = false.
  EOT
  value       = try(one(data.aws_instances.lab[*].ids[0]), "")
}

output "autoscaling_group_name" {
  description = "ASG de capacidad fija 1 que mantiene la instancia; valor de MSR_LAB_AUTOSCALING_GROUP_NAME."
  value       = try(aws_autoscaling_group.lab[0].name, "")
}

output "autoscaling_group_arn" {
  description = "ARN del ASG del laboratorio."
  value       = try(aws_autoscaling_group.lab[0].arn, "")
}

output "lab_logical_id" {
  description = "Identificador lógico del laboratorio (tag msr-lab-id)."
  value       = var.lab_id
}

output "lab_public_ip" {
  description = "IPv4 pública dinámica (no hay ingress abierto; sólo diagnóstico)."
  value       = try(one(data.aws_instances.lab[*].public_ips[0]), "")
}

output "lab_private_ip" {
  value       = try(one(data.aws_instances.lab[*].private_ips[0]), "")
  description = "IPv4 privada dinámica de la instancia actual del laboratorio."
}

output "launch_template_id" {
  description = "Launch Template desde el que el runbook de reset recrea la instancia."
  value       = try(aws_launch_template.lab[0].id, "")
}

output "launch_template_version" {
  description = "Versión fija del Launch Template usada por el reset."
  value       = try(tostring(aws_launch_template.lab[0].latest_version), "")
}

output "instance_profile_arn" {
  description = "Instance profile del managed node."
  value       = try(aws_iam_instance_profile.instance[0].arn, "")
}

output "application_role_arn" {
  description = "Rol del control plane; valor de MSR_AWS_ROLE_ARN."
  value       = try(aws_iam_role.application[0].arn, "")
}

output "automation_role_arn" {
  description = "Rol de Automation; valor de MSR_AUTOMATION_ASSUME_ROLE_ARN."
  value       = try(aws_iam_role.automation[0].arn, "")
}

output "patch_runbook_name" {
  description = "Runbook Automation de parcheo; valor de MSR_PATCH_RUNBOOK_NAME."
  value       = var.patch_runbook_name
}

output "patch_runbook_arn" {
  value       = try(aws_ssm_document.patch[0].arn, "")
  description = "ARN del runbook de parcheo."
}

output "reset_runbook_name" {
  description = "Runbook Automation de reset; valor de MSR_RESET_RUNBOOK_NAME."
  value       = var.reset_runbook_name
}

output "reset_runbook_arn" {
  value       = try(aws_ssm_document.reset[0].arn, "")
  description = "ARN del runbook de reset."
}

output "candidate_advisory_id" {
  description = "Advisory que la PoC debe demostrar; valor de MSR_PATCH_ADVISORY_ID."
  value       = var.candidate_advisory_id
}

output "candidate_releasever" {
  description = <<-EOT
    Release de Amazon Linux 2023 que contiene la corrección. Precheck, postcheck
    y reset consultan el advisory con `--releasever` sobre este valor, porque el
    repositorio de la AMI base está fijado en una release anterior.
  EOT
  value       = var.candidate_releasever
}

output "expected_fixed_kernel" {
  description = "Kernel mínimo que debe quedar en ejecución tras el parcheo."
  value       = var.expected_fixed_kernel
}

output "patch_baseline_id" {
  description = "Baseline que aprueba únicamente el advisory candidato."
  value       = try(aws_ssm_patch_baseline.lab[0].id, "")
}

output "patch_group" {
  description = "Patch group asociado al baseline (tag `Patch Group`)."
  value       = var.patch_group
}

output "security_group_id" {
  description = "Security group sin reglas de entrada."
  value       = try(aws_security_group.lab[0].id, "")
}

output "required_backend_environment" {
  description = <<-EOT
    Variables que debe recibir el backend (.env). MSR_PATCH_PROVIDER,
    MSR_RESTORE_PROVIDER y MSR_DRY_RUN mantienen sus valores seguros por
    defecto y no se activan desde aquí.
  EOT
  value = merge(local.backend_environment, {
    MSR_AWS_ROLE_ARN               = try(aws_iam_role.application[0].arn, "")
    MSR_AUTOMATION_ASSUME_ROLE_ARN = try(aws_iam_role.automation[0].arn, "")
  })
}

output "estimated_resource_summary" {
  description = "Recursos que se crearían con enable_real_resources = true."
  value = {
    enabled = var.enable_real_resources
    resources = [
      "aws_security_group.lab",
      "aws_vpc_security_group_egress_rule.https",
      "aws_vpc_security_group_egress_rule.dns_tcp",
      "aws_vpc_security_group_egress_rule.dns_udp",
      "aws_iam_role.instance",
      "aws_iam_role_policy.instance_boundary",
      "aws_iam_role_policy_attachment.instance_ssm_core",
      "aws_iam_instance_profile.instance",
      "aws_iam_role.automation",
      "aws_iam_role_policy.automation",
      "aws_iam_role.application",
      "aws_iam_role_policy.application",
      "aws_launch_template.lab",
      "aws_autoscaling_group.lab",
      "aws_ssm_patch_baseline.lab",
      "aws_ssm_patch_group.lab",
      "aws_ssm_document.patch",
      "aws_ssm_document.reset",
    ]
    ec2_instances = var.enable_real_resources ? 1 : 0
  }
}
