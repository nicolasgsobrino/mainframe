provider "aws" {
  region = var.aws_region

  # Sólo se opera sobre la cuenta declarada: si las credenciales apuntan a otra,
  # cualquier operación falla antes de tocar un recurso.
  allowed_account_ids = [var.aws_account_id]

  default_tags {
    tags = local.common_tags
  }

  # Etiquetas que administra un sistema corporativo externo: Terraform no las
  # crea, no las modifica y, sobre todo, no las elimina al actualizar recursos.
  # Sus valores no se conocen ni se declaran aquí.
  ignore_tags {
    keys = var.externally_managed_tag_keys
  }
}
