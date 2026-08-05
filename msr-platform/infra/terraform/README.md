# Infraestructura del laboratorio MSR (Terraform)

Define el laboratorio de la PoC: **una** instancia EC2 Amazon Linux 2023
deliberadamente vulnerable, su Launch Template, el patch baseline restringido a
un único advisory, los dos runbooks de Systems Manager Automation y los tres
roles IAM (instancia, Automation y aplicación).

> **Nada se crea por defecto.** `enable_real_resources = false` es el valor
> predeterminado: el plan queda vacío y no se realiza ninguna llamada mutativa a
> AWS. Ni esta fase ni el CI ejecutan `terraform plan`/`apply` contra la cuenta.

## Estado

Estado **local** a propósito (PoC desechable). `terraform.tfstate`,
`terraform.tfvars` y `.terraform/` están en `.gitignore` y **no deben
versionarse**: el estado puede contener atributos sensibles. Cuando el
laboratorio deje de ser desechable habrá que mover el backend a S3 + DynamoDB.

## Estructura

| Fichero | Contenido |
|---|---|
| `versions.tf` | Versiones de Terraform y del provider AWS |
| `providers.tf` | Provider AWS, `allowed_account_ids`, `default_tags` |
| `variables.tf` | Todas las variables (nada hardcodeado en los recursos) |
| `locals.tf` | Tags obligatorios, tags de coste y entorno del backend |
| `data.tf` | Consultas de sólo lectura y `check` de cuenta/región/VPC/AMI |
| `networking.tf` | Security group **sin ingress** y egress DNS/HTTPS |
| `iam.tf` | Roles de instancia, Automation y aplicación |
| `ec2.tf` | Launch Template + instancia del laboratorio |
| `patching.tf` | Patch baseline y patch group |
| `automation-documents.tf` | Registro de los runbooks Automation |
| `documents/*.yaml` | Cuerpo de los runbooks (plantillas `templatefile`) |
| `outputs.tf` | Salidas, incluida `required_backend_environment` |
| `user-data.sh.tftpl` | Bootstrap: httpd, `/health`, `baseline.json` |

## Guardrails

- `allowed_account_ids` en el provider: credenciales de otra cuenta → error.
- Preconditions en `aws_instance.lab` y `aws_launch_template.lab`: cuenta,
  región, pertenencia de la subnet a la VPC, arquitectura `x86_64`, propietario
  Amazon de la AMI y presencia de todos los valores obligatorios.
- Validaciones de variable: formato de la cuenta y del advisory, volumen ≥ 8 GiB
  y `allowed_ui_cidr != 0.0.0.0/0`.
- `check` de cuenta, región, red y AMI para que un `plan` avise antes del apply.

## Seguridad de la instancia

Sin key pair, sin SSH, sin reglas de entrada, IMDSv2 obligatorio, volumen raíz
gp3 cifrado de 8 GiB con `delete_on_termination`, monitorización detallada
desactivada y user data que **no** ejecuta `dnf update` global: sólo instala
`httpd`, publica `/health` con `MSR_POC_HEALTHY` y escribe
`/var/lib/msr-poc/baseline.json` y `/var/lib/msr-poc/bootstrap-complete`.

## Uso (todavía NO ejecutado contra AWS)

```bash
cd msr-platform/infra/terraform
cp terraform.tfvars.example terraform.tfvars

terraform fmt -check -recursive
terraform init -backend=false
terraform validate

# 1) Revisión estática, sin recursos (valor predeterminado):
terraform init
terraform plan -out=tfplan            # enable_real_resources = false → plan vacío

# 2) Sólo cuando el propietario de la cuenta lo autorice explícitamente:
terraform plan -var 'enable_real_resources=true' -out=tfplan
terraform show tfplan                 # revisar recurso a recurso
terraform apply tfplan
```

Tras el apply, `terraform output required_backend_environment` devuelve los
valores del `.env` del backend. `MSR_PATCH_PROVIDER`, `MSR_RESTORE_PROVIDER` y
`MSR_DRY_RUN` conservan sus valores seguros: la ejecución real se habilita en un
paso posterior y explícito.

## Limitaciones conocidas

- Patch Manager no ofrece una API para comprobar que un advisory existe: si
  `candidate_advisory_id` no aplicase, `AWS-RunPatchBaseline` no instalaría nada
  y el runbook termina con `ADVISORY_NOT_APPLICABLE` en el precheck en lugar de
  dar por buena una ejecución vacía.
- `ec2:DescribeInstances` y las APIs `ssm:Describe*` no admiten permisos a nivel
  de recurso ni condiciones por tag: esas acciones de lectura quedan con
  `Resource: *`. Las acciones mutativas sí están restringidas por tag.
- El contenido de los runbooks no puede validarse sin AWS; se comprueba de forma
  estática (render de la plantilla + parseo YAML + contrato de parámetros) en la
  suite de tests del backend.
