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
  description = "Instance profile corporativo reutilizado por la instancia (no gestionado por Terraform)."
  value       = try(data.aws_iam_instance_profile.existing[0].arn, "")
}

output "instance_profile_name" {
  description = "Nombre del instance profile corporativo reutilizado."
  value       = var.existing_instance_profile_name
}

output "instance_profile_role_name" {
  description = "Rol contenido en el instance profile corporativo."
  value       = var.existing_instance_profile_role_name
}

output "backend_credential_mode" {
  description = "El backend usa las credenciales del entorno donde se ejecuta (sin sts:AssumeRole)."
  value       = "ambient-caller"
}

output "automation_credential_mode" {
  description = "Automation se ejecuta con las credenciales de quien la inicia (sin service role)."
  value       = "caller-context"
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

output "release_order" {
  description = <<-EOT
    Orden temporal entre la AMI base y la release que corrige el advisory. La
    comparación es numérica sobre la fecha YYYYMMDD; `ami_precedes_fix = false`
    detiene el plan en el precondition del Auto Scaling Group.
  EOT
  value = {
    source_ami_product = local.source_ami_release_product
    candidate_product  = local.candidate_release_product
    source_ami_date    = local.source_ami_release_date
    candidate_date     = local.candidate_release_date
    amazon_linux_2023  = local.releases_are_amazon_linux_2023
    ami_precedes_fix   = local.ami_release_precedes_fix
  }
}

output "patch_baseline_id" {
  description = "Baseline que aprueba únicamente el advisory candidato."
  value       = try(aws_ssm_patch_baseline.lab[0].id, "")
}

output "patch_group" {
  description = "Patch group asociado al baseline (tag `PatchGroup` en la instancia)."
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
  # El ARN queda vacío a propósito: el backend usa la identidad de workload de su
  # runtime (ECS Task Role) y la Automation se ejecuta con esa misma identidad.
  value = merge(local.backend_environment, {
    MSR_AWS_ROLE_ARN = ""
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

# --- Runtime del backend y su identidad de workload --------------------------

output "backend_deployment_runtime" {
  description = "Runtime de despliegue del backend."
  value       = "ecs-fargate"
}

output "backend_task_role_arn" {
  description = <<-EOT
    ARN efectivo del ECS Task Role: el creado por Terraform o el preaprovisionado
    por el equipo corporativo. Vacío significa despliegue no configurado.
  EOT
  value       = local.backend_task_role_arn
}

output "backend_execution_role_arn" {
  description = "ARN efectivo del task execution role (agente de ECS)."
  value       = local.backend_execution_role_arn
}

output "backend_task_role_is_managed_by_terraform" {
  description = "true si Terraform crea el Task Role; false si se consume uno existente."
  value       = var.create_backend_task_role
}

output "backend_task_role_trust_policy_json" {
  description = <<-EOT
    Trust policy exacta del Task Role. Si IAM no puede crearse desde aquí, es el
    documento que debe aplicar el equipo de cloud, sin ampliaciones.
  EOT
  value       = jsonencode(local.backend_task_trust_policy)
}

output "backend_task_role_permission_policy_json" {
  description = <<-EOT
    Política de permisos exacta del Task Role: mínimo necesario para iniciar los
    dos runbooks y para todos los pasos que ejecutan en el contexto del llamante.
    No incluye iam:PassRole porque no existe service role de Automation.
  EOT
  value       = jsonencode(local.backend_task_permission_policy)
}

output "backend_task_environment" {
  description = "Variables MSR_* de la task (sin secretos: no hay credenciales que inyectar)."
  value       = local.backend_task_environment
}

output "backend_reconciliation_hook" {
  description = <<-EOT
    Invocación única del hook de reconciliación por release (RunTask con override
    del comando), nunca en el arranque de cada réplica.
  EOT
  value = {
    normal             = ["python", "-m", "app.lab_hook"]
    authorized_restore = ["python", "-m", "app.lab_hook", "--confirm"]
  }
}

output "backend_resource_summary" {
  description = "Recursos del runtime que se crearían con enable_backend_service = true."
  value = {
    enabled = var.enable_backend_service
    resources = concat([
      "aws_cloudwatch_log_group.backend",
      "aws_security_group.backend",
      "aws_vpc_security_group_egress_rule.backend_https",
      "aws_vpc_security_group_egress_rule.backend_dns_udp",
      "aws_ecs_cluster.backend",
      "aws_ecs_task_definition.backend",
      "aws_ecs_service.backend",
      ], var.enable_backend_alb ? [
      "aws_security_group.backend_alb",
      "aws_vpc_security_group_ingress_rule.backend_alb",
      "aws_vpc_security_group_egress_rule.backend_alb_to_backend",
      "aws_vpc_security_group_ingress_rule.backend_from_alb",
      "aws_lb.backend",
      "aws_lb_target_group.backend",
      "aws_lb_listener.backend",
      ] : [], var.enable_backend_ecr ? [
      "aws_ecr_repository.backend",
      "aws_ecr_lifecycle_policy.backend",
      ] : [], var.enable_backend_lock_table ? [
      "aws_dynamodb_table.lab_locks",
      ] : [], var.create_backend_task_role ? [
      "aws_iam_role.backend_task",
      "aws_iam_role_policy.backend_task",
      "aws_iam_role.backend_execution",
      "aws_iam_role_policy_attachment.backend_execution",
    ] : [])
    requires_iam_permissions = var.create_backend_task_role
  }
}

# --- Registro de imágenes, exposición y lock ---------------------------------

output "backend_ecr_repository_url" {
  description = "URL del repositorio ECR privado donde se publica la imagen del backend."
  value       = local.backend_ecr_repository_url
}

output "backend_alb_dns_name" {
  description = <<-EOT
    DNS del Application Load Balancer. Vacío mientras `enable_backend_alb = false`;
    con un ALB interno sólo resuelve dentro de la red corporativa/VPC.
  EOT
  value       = try(aws_lb.backend[0].dns_name, "")
}

output "backend_alb_is_internal" {
  description = "true si el ALB no está publicado en Internet."
  value       = var.backend_alb_internal
}

output "backend_lock_table" {
  description = "Tabla DynamoDB del lock de operación del laboratorio y su ARN exacto."
  value = {
    name          = var.backend_lock_table_name
    arn           = local.backend_lock_table_arn
    partition_key = "lab_id"
    ttl_attribute = "expires_at"
    managed       = var.enable_backend_lock_table
  }
}
