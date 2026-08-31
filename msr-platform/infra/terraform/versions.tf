terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Estado local a propósito para la primera PoC. El backend remoto (S3 +
  # DynamoDB) se configurará cuando el laboratorio deje de ser desechable.
  # `terraform.tfstate` NO debe versionarse: puede contener valores sensibles.
}
