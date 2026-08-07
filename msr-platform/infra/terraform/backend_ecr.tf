# Repositorio ECR privado de la imagen MSR.
#
# El workflow de despliegue construye, etiqueta y publica la imagen con
# credenciales temporales de OIDC (sin claves estáticas), y la task de ECS la
# descarga a través de su task execution role.
#
# Privado siempre: no se declara ninguna política de repositorio público ni
# `aws_ecrpublic_*`.

locals {
  backend_ecr_enabled = (var.enable_real_resources && var.enable_backend_ecr) ? 1 : 0

  backend_ecr_repository_url = (
    "${var.aws_account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${var.backend_ecr_repository_name}"
  )
  backend_ecr_repository_arn = (
    "arn:aws:ecr:${var.aws_region}:${var.aws_account_id}:repository/${var.backend_ecr_repository_name}"
  )

  # Sólo se conservan las últimas imágenes de la PoC; el resto caduca.
  backend_ecr_lifecycle_policy = {
    rules = [{
      rulePriority = 1
      description  = "Conserva únicamente las ${var.backend_ecr_retained_images} imágenes más recientes"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = var.backend_ecr_retained_images
      }
      action = { type = "expire" }
    }]
  }
}

resource "aws_ecr_repository" "backend" {
  count = local.backend_ecr_enabled

  name = var.backend_ecr_repository_name
  # Cada release publica un tag nuevo (SHA del commit): los tags no se reescriben.
  image_tag_mutability = "IMMUTABLE"
  force_delete         = false

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = merge(local.common_tags, { Name = var.backend_ecr_repository_name })
}

resource "aws_ecr_lifecycle_policy" "backend" {
  count = local.backend_ecr_enabled

  repository = aws_ecr_repository.backend[0].name
  policy     = jsonencode(local.backend_ecr_lifecycle_policy)
}
