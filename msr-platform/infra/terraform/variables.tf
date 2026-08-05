variable "aws_account_id" {
  description = "Cuenta AWS de la PoC. Cualquier otra cuenta es rechazada."
  type        = string
  default     = "133789123239"

  validation {
    condition     = can(regex("^[0-9]{12}$", var.aws_account_id))
    error_message = "aws_account_id debe ser un identificador de cuenta de 12 dígitos."
  }
}

variable "aws_region" {
  description = "Región de la PoC."
  type        = string
  default     = "eu-north-1"
}

variable "vpc_id" {
  description = "VPC del laboratorio."
  type        = string
  default     = "vpc-023864c0ca3c82eab"
}

variable "subnet_id" {
  description = "Subnet del laboratorio (debe pertenecer a vpc_id)."
  type        = string
  default     = "subnet-0bb97e6254e4f83e9"
}

variable "operator_role_arn" {
  description = "Rol humano/operador que podrá asumir el rol de aplicación."
  type        = string
  default     = "arn:aws:iam::133789123239:role/AWS_133789123239_Admin"
}

variable "lab_id" {
  description = "Identificador lógico del laboratorio (tag msr-lab-id)."
  type        = string
  default     = "linux-patching-01"
}

variable "source_ami_id" {
  description = "AMI base vulnerable del laboratorio (Amazon Linux 2023, x86_64)."
  type        = string
  default     = "ami-0b2ab3a97a77bd35e"
}

variable "instance_type" {
  description = "Tipo de instancia del laboratorio."
  type        = string
  default     = "t3.micro"
}

variable "candidate_advisory_id" {
  description = "Advisory candidato de Amazon Linux aprobado por el patch baseline."
  type        = string
  default     = "ALAS2023-2026-1924"

  validation {
    condition     = can(regex("^ALAS2023-[0-9]{4}-[0-9]+$", var.candidate_advisory_id))
    error_message = "candidate_advisory_id debe tener el formato ALAS2023-AAAA-NNNN."
  }
}

# La AMI base fija el repositorio de Amazon Linux 2023 en su propia release, por
# lo que un advisory posterior no se ve sin consultar explícitamente el
# releasever donde se publicó la corrección.
variable "candidate_releasever" {
  description = "Release de Amazon Linux 2023 que contiene la corrección del advisory candidato."
  type        = string
  default     = "2023.12.20260706"

  validation {
    condition     = can(regex("^[0-9]{4}\\.[0-9]{2}\\.[0-9]{8}$", var.candidate_releasever))
    error_message = "candidate_releasever debe tener el formato YYYY.NN.YYYYMMDD."
  }
}

variable "expected_fixed_kernel" {
  description = "Versión mínima del kernel que debe quedar en ejecución tras el parcheo."
  type        = string
  default     = "6.1.176-220.358.amzn2023.x86_64"

  validation {
    condition     = can(regex("^[0-9]+\\.[0-9]+\\.[0-9]+-[0-9.]+\\.amzn2023\\.[a-z0-9_]+$", var.expected_fixed_kernel))
    error_message = "expected_fixed_kernel debe ser una versión de kernel de Amazon Linux 2023."
  }
}

variable "source_ami_release" {
  description = "Release de Amazon Linux 2023 de la AMI base; debe ser anterior a candidate_releasever."
  type        = string
  default     = "2023.11.20260509.0"

  validation {
    condition     = can(regex("^[0-9]{4}\\.[0-9]{2}\\.[0-9]{8}\\.[0-9]+$", var.source_ami_release))
    error_message = "source_ami_release debe tener el formato YYYY.NN.YYYYMMDD.N."
  }
}

variable "candidate_package_family" {
  description = "Familia de paquetes afectada por el advisory candidato."
  type        = string
  default     = "kernel"
}

variable "allowed_ui_cidr" {
  description = <<-EOT
    CIDR autorizado a alcanzar la instancia desde fuera. La PoC no abre ningún
    puerto de entrada, pero el valor se valida para impedir que una futura regla
    de ingress se cree abierta a Internet.
  EOT
  type        = string
  default     = "10.0.0.0/8"

  validation {
    condition     = var.allowed_ui_cidr != "0.0.0.0/0" && can(cidrhost(var.allowed_ui_cidr, 0))
    error_message = "allowed_ui_cidr debe ser un CIDR válido y no puede ser 0.0.0.0/0."
  }
}

variable "enable_real_resources" {
  description = <<-EOT
    Interruptor maestro. Con `false` (valor predeterminado) Terraform no crea
    ningún recurso mutativo: el plan queda vacío y sirve como revisión estática.
  EOT
  type        = bool
  default     = false
}

variable "root_volume_size_gib" {
  description = "Tamaño del volumen raíz (gp3, cifrado)."
  type        = number
  default     = 8

  validation {
    condition     = var.root_volume_size_gib >= 8
    error_message = "El volumen raíz debe tener al menos 8 GiB."
  }
}

variable "asg_health_check_grace_period_seconds" {
  description = "Margen antes de que el ASG evalúe la salud de una instancia nueva."
  type        = number
  default     = 300

  validation {
    condition     = var.asg_health_check_grace_period_seconds >= 60
    error_message = "El periodo de gracia debe permitir el bootstrap (>= 60 s)."
  }
}

variable "patch_group" {
  description = "Valor del tag `Patch Group` que asocia la instancia al baseline."
  type        = string
  default     = "msr-poc-linux"
}

variable "environment_tag" {
  description = "Valor del tag msr-environment."
  type        = string
  default     = "sandbox"
}

variable "cost_center" {
  description = "Centro de coste (tag de coste configurable)."
  type        = string
  default     = "msr-poc"
}

variable "owner" {
  description = "Propietario responsable del laboratorio (tag configurable)."
  type        = string
  default     = "msr-poc-team"
}

variable "extra_tags" {
  description = "Tags adicionales aplicados a todos los recursos."
  type        = map(string)
  default     = {}
}

variable "patch_runbook_name" {
  description = "Nombre del runbook Automation de parcheo."
  type        = string
  default     = "MSR-PatchLinuxInstance"
}

variable "reset_runbook_name" {
  description = "Nombre del runbook Automation de reset del laboratorio."
  type        = string
  default     = "MSR-ResetLabInstance"
}
