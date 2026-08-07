# Lock distribuido de operación del laboratorio.
#
# patch desde la UI + reset + reconciliación de release
#   → lock en DynamoDB (escritura condicional)
#   → exactamente una mutación del laboratorio a la vez
#
# El lock local en SQLite no basta en Fargate: la task del servicio y el RunTask
# del hook tienen filesystems efímeros independientes. La tabla es el único punto
# de serialización compartido; `desired_count = 1` no es un mecanismo de lock.
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
