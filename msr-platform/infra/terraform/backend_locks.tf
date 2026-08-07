# Lock distribuido de operación del laboratorio.
#
# patch desde la UI + reset + reconciliación de release
#   → lock en DynamoDB (escritura condicional)
#   → exactamente una mutación del laboratorio a la vez
#
# El lock local en SQLite no basta con varios procesos: el servicio web y el hook
# de release no comparten filesystem, y el alojamiento externo puede ejecutar
# varias instancias. La tabla es el único punto de serialización compartido; una
# sola réplica no es un mecanismo de lock. Sigue vigente en la fase 2.9 aunque la
# aplicación se aloje fuera de AWS (ver ARCHITECTURE_REPORT_PHASE2_9.md).
#
# `expires_at` es epoch numérico y actúa como TTL de DynamoDB, pero sólo para
# limpiar locks abandonados: la adquisición vuelve a comparar la caducidad dentro
# de su propia condición y no depende del borrado asíncrono.

locals {
  backend_lock_enabled = (var.enable_real_resources && var.enable_backend_lock_table) ? 1 : 0

  backend_lock_table_arn = (
    "arn:aws:dynamodb:${var.aws_region}:${var.aws_account_id}:table/${var.backend_lock_table_name}"
  )
}

resource "aws_dynamodb_table" "lab_locks" {
  count = local.backend_lock_enabled

  name         = var.backend_lock_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "lab_id"

  attribute {
    name = "lab_id"
    type = "S"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  server_side_encryption {
    enabled = true
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = merge(local.common_tags, { Name = var.backend_lock_table_name })
}
