provider "aws" {
  region = var.aws_region

  # Sólo se opera sobre la cuenta declarada: si las credenciales apuntan a otra,
  # cualquier operación falla antes de tocar un recurso.
  allowed_account_ids = [var.aws_account_id]

  default_tags {
    tags = local.common_tags
  }
}
