# Infraestructura del laboratorio MSR (Terraform)

Define el laboratorio de la PoC: **una** instancia EC2 Amazon Linux 2023
deliberadamente vulnerable, su Launch Template, el patch baseline restringido a
un único advisory y los dos runbooks de Systems Manager Automation. **No gestiona
IAM**: la cuenta deniega `iam:AttachRolePolicy`, `iam:PutRolePolicy` e
`iam:UpdateAssumeRolePolicy`, así que la instancia reutiliza el instance profile
corporativo existente (`existing_instance_profile_name`) como data source de sólo
lectura, el backend usa las credenciales de su entorno y Automation las de la
identidad que la inicia.

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
| `data.tf` | Consultas de sólo lectura (incluido el instance profile corporativo) y `check` de cuenta/región/VPC/AMI |
| `networking.tf` | Security group **sin ingress** y egress DNS/HTTPS |
| `ec2.tf` | Launch Template + Auto Scaling Group (1/1/1) del laboratorio |
| `patching.tf` | Patch baseline y patch group |
| `automation-documents.tf` | Registro de los runbooks Automation |
| `backend_ecs.tf` | Runtime del backend: cluster, task definition y servicio de ECS Fargate |
| `backend_iam.tf` | Documentos exactos de los dos roles externos (no crea ningún recurso IAM) |
| `backend_ecr.tf` | Repositorio ECR privado de la imagen (escaneo, cifrado, lifecycle policy) |
| `backend_alb.tf` | Application Load Balancer, target group `ip`, listener y reglas de security group |
| `backend_locks.tf` | Tabla DynamoDB del lock distribuido de operación del laboratorio |
| `documents/*.yaml` | Cuerpo de los runbooks (plantillas `templatefile`) |
| `outputs.tf` | Salidas, incluida `required_backend_environment` |
| `user-data.sh.tftpl` | Bootstrap: httpd, `/health`, `baseline.json` |

## Guardrails

- `allowed_account_ids` en el provider: credenciales de otra cuenta → error.
- Preconditions en `aws_autoscaling_group.lab` y `aws_launch_template.lab`: cuenta,
  región, pertenencia de la subnet a la VPC, arquitectura `x86_64`, propietario
  Amazon de la AMI y presencia de todos los valores obligatorios.
- Validaciones de variable: formato de la cuenta y del advisory, volumen ≥ 8 GiB
  y `allowed_ui_cidr != 0.0.0.0/0`.
- `check` de cuenta, región, red, AMI e instance profile para que un `plan` avise
  antes del apply.
- El Launch Template exige que `existing_instance_profile_name` y
  `existing_instance_profile_role_name` estén fijados, que el profile contenga ese
  rol y que su ARN pertenezca a `aws_account_id`.

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

# Tests nativos: evalúan la configuración (incluida enable_real_resources = true)
# con `mock_provider "aws"`, sin credenciales y sin crear ningún recurso.
terraform test

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

## Advisory candidato y releasever

`candidate_advisory_id` (`ALAS2023-2026-1924`) se corrigió en la release
`candidate_releasever` (`2023.12.20260706`), posterior a la release de la AMI
base `source_ami_release` (`2023.11.20260509.0`) — un precondition de
`aws_autoscaling_group.lab` lo exige. Como el repositorio de la AMI está fijado en
su propia release, precheck, postcheck y reset consultan siempre
`dnf updateinfo list --available --advisory <advisory> --releasever <releasever>`
y comparan el kernel con `expected_fixed_kernel`
(`6.1.176-220.358.amzn2023.x86_64`) mediante `sort -V`.

## Patch group

Patch Manager reconoce dos claves equivalentes, `Patch Group` y `PatchGroup`. La
instancia usa la variante **sin espacio** porque el Launch Template expone los
tags por IMDS (`instance_metadata_tags = "enabled"`) y EC2 rechaza las claves con
espacio al lanzar. `aws_ssm_patch_group.lab` registra el valor `msr-poc-linux`
contra el baseline personalizado, de modo que `AWS-RunPatchBaseline` selecciona
ese baseline y no el predeterminado del sistema operativo.

## Etiquetas corporativas externas

Un sistema corporativo añade a los recursos etiquetas propias (`APPID`,
`BILLINGCODE`, `BUSINESSAREA`, `ENVIRONMENT`…). Terraform no las conoce, así que
al actualizar un recurso intentaría eliminarlas. Para evitarlo, el provider
declara:

```hcl
ignore_tags {
  keys = var.externally_managed_tag_keys
}
```

`externally_managed_tag_keys` es `[]` por defecto —el módulo sigue siendo
reutilizable fuera de esta cuenta— y **la lista real debe configurarse
explícitamente** en el entorno corporativo (ver `terraform.tfvars.example`). No
se usan `key_prefixes`: las claves corporativas no comparten un prefijo
inequívoco. Los valores de esas etiquetas no se declaran en ningún sitio.

`Name`, `PatchGroup` y las etiquetas `msr-*` **siguen gestionadas por
Terraform**: la variable rechaza esas claves y no se usa
`lifecycle { ignore_changes = [tags] }`, de modo que el drift funcional sigue
apareciendo en el plan.

## Suspensión del proceso `Launch`

`suspended_processes` del ASG es estado deseado explícito, controlado por
`asg_launch_suspended` (nunca se oculta con `ignore_changes`, para que el drift
aparezca en el plan):

```hcl
# Operación normal
asg_launch_suspended = false   # suspended_processes = []

# Recuperación/contención temporal
asg_launch_suspended = true    # suspended_processes = ["Launch"]
```

El valor por defecto es `false`, de modo que una instalación nueva crea la
instancia con normalidad. Sólo `Launch` puede suspenderse: la variable no admite
ningún otro proceso de Auto Scaling. Durante una recuperación se pone a `true` y
**se vuelve a `false` únicamente mediante un plan revisado**, cuando el Launch
Template, el instance profile y las etiquetas ya estén corregidos.

## Runtime del backend y su identidad de workload

```text
Internet/usuario → frontend (SPA servida por el backend)
  → backend como task de ECS Fargate
  → ECS Task Role (credenciales temporales del endpoint de metadatos)
  → Systems Manager Automation → runbooks MSR → EC2 del laboratorio
```

El backend **no** se despliega en la EC2 del laboratorio: esa instancia se termina a
propósito en cada reset. Los runbooks no declaran `assumeRole` y no existe service role
de Automation, así que **todos** los permisos que necesitan sus pasos viven en el Task
Role y no hay `iam:PassRole`.

Este Terraform **no crea ningún rol de aplicación**: el descubrimiento sobre la cuenta
demostró que adjuntar políticas a un rol está explícitamente denegado, así que un rol
creado aquí nacería sin permisos. Los dos roles los aprovisiona el equipo corporativo de
cloud y aquí se consumen por ARN:

```hcl
enable_backend_service     = true
backend_task_role_arn      = "arn:aws:iam::133789123239:role/..."
backend_execution_role_arn = "arn:aws:iam::133789123239:role/..."
```

Sin ambos ARNs (de la cuenta configurada), un precondition de
`aws_ecs_task_definition.backend` **detiene el despliegue**: nunca se arranca una task que
caería en credenciales indeterminadas. Los cuatro documentos exactos que debe crear el
equipo de cloud se publican en los outputs `backend_task_role_trust_policy_json`,
`backend_task_role_permission_policy_json`, `backend_execution_role_trust_policy_json` y
`backend_execution_role_permission_policy_json`. El execution role no usa la política
gestionada `AmazonECSTaskExecutionRolePolicy`: queda acotado al repositorio ECR de la PoC
y a su log group.

La task no lleva `secrets` ni variables de credenciales, y arranca con `MSR_DRY_RUN=true`,
`MSR_LAB_RECONCILE_ON_STARTUP=false`, `MSR_AWS_PROFILE=` y `MSR_AWS_ROLE_ARN=` vacíos:
boto3 usa exclusivamente el Task Role.

## Imagen, exposición y lock distribuido

```text
usuario → ALB → ECS Fargate → Task Role → SSM Automation → EC2 del laboratorio
```

```text
patch/reset desde la UI + reconciliación de release
  → lock distribuido en DynamoDB
  → exactamente una mutación del laboratorio a la vez
```

Los tres bloques están desactivados por defecto (`enable_backend_ecr`,
`enable_backend_alb`, `enable_backend_lock_table` en `false`), igual que el resto del
runtime.

**ECR.** Repositorio privado dedicado con `scan_on_push`, cifrado `AES256`, tags
inmutables y una lifecycle policy que expira todo lo que exceda las
`backend_ecr_retained_images` (5) imágenes más recientes. La URL se publica en
`backend_ecr_repository_url`. El workflow de release obtiene credenciales temporales por
OIDC (`aws-actions/configure-aws-credentials@v4` + `amazon-ecr-login@v2`), construye,
etiqueta y publica la imagen, registra una revisión nueva de la task definition y sólo
después lanza el hook: no hay ninguna clave estática en el pipeline.

**ALB.** `internal = true` por defecto (perfil corporativo). Requiere al menos dos subnets
de zonas distintas y elegidas entre `backend_candidate_subnet_ids`, y el listener sólo se
abre a los orígenes de `backend_alb_ingress_cidrs`: la lista es **obligatoria y no vacía**
y ningún prefijo `/0` es admisible (lo rechazan la validación de la variable y un
precondition de `aws_lb.backend`). El target group usa `target_type = "ip"` (obligatorio
con `awsvpc`) contra el puerto 8080 y comprueba `/api/health`; el security group del
backend sólo admite tráfico del security group del ALB, nunca CIDR. Con
`backend_alb_certificate_arn` el tráfico pasa a HTTPS (443, política TLS 1.2/1.3) y el
listener HTTP redirige; sin certificado la PoC queda en HTTP, una limitación temporal
aceptable sólo con los orígenes restringidos, porque no se inventa DNS ni certificado. Su
DNS se publica en `backend_alb_dns_name`. Sin CloudFront y sin túneles.

**Lock.** Una sola tabla (`msr-poc-lab-locks`) con partition key `lab_id`, TTL sobre
`expires_at`, cifrado y point-in-time recovery. El lock local en SQLite no sirve en
Fargate porque la task del servicio y el `RunTask` del hook tienen filesystems efímeros
independientes; `desired_count = 1` tampoco es un mecanismo de lock. La adquisición es una
escritura condicional que también trata el ítem caducado, así que no depende del borrado
asíncrono del TTL, y sólo el owner puede liberar. El Task Role recibe exactamente
`dynamodb:GetItem`, `dynamodb:PutItem` y `dynamodb:DeleteItem` sobre el ARN de esa tabla
(`backend_lock_table.arn`): nunca `dynamodb:*` ni comodines de recurso. Esos permisos
forman parte del documento que aplica el equipo de cloud.

## Descubrimiento de red previo al primer apply

`backend_alb_subnet_ids` y `backend_alb_ingress_cidrs` **no tienen valor por defecto**: no se
inventan subnets ni rangos de origen. Antes del primer apply se ejecuta un descubrimiento de
sólo lectura que resuelve VPC, subnets, AZs, route tables, salida por defecto (IGW, NAT,
TGW, VPN o ninguna), endpoints de VPC, NAT/Internet Gateways y DNS de la VPC:

```bash
cd ../../backend
MSR_AWS_REGION=eu-north-1 .venv/bin/python -m app.net_discovery --vpc-id <vpc-id>
```

Sólo emite llamadas `Describe*` y no crea nada. El informe pre-apply, con la topología
descubierta y las dependencias del equipo de red que siguen abiertas, está en
`../../PRE_APPLY_NETWORK_DISCOVERY.md`.

## Dos perfiles de red

El descubrimiento demostró que la cuenta sólo tiene la VPC por defecto
(`vpc-023864c0ca3c82eab`, `172.31.0.0/16`) con tres subnets públicas, un Internet Gateway,
cero NAT gateways, cero endpoints de VPC y ninguna conectividad corporativa. De ahí dos
perfiles, y el módulo mantiene los dos:

| | `poc-public` (autorizado para la PoC) | `corporate-private` (valor por defecto, futuro) |
| --- | --- | --- |
| `backend_alb_internal` | `false` | `true` |
| Subnets | las públicas candidatas, dos AZs | privadas, dos AZs |
| `backend_assign_public_ip` | `true` | `false` |
| Salida de la task | Internet Gateway | NAT o endpoints de VPC |
| Entrada | ALB restringido a CIDR corporativos | ALB interno tras VPN/TGW/peering |

```hcl
# Perfil PoC
enable_backend_alb        = true
backend_alb_internal      = false
backend_assign_public_ip  = true
backend_alb_subnet_ids    = ["subnet-0bb97e6254e4f83e9", "subnet-0c14b617316ff3efa"]
backend_subnet_ids        = ["subnet-0bb97e6254e4f83e9", "subnet-0c14b617316ff3efa"]
backend_alb_ingress_cidrs = ["<CIDR corporativo real>"]
```

La IP pública es la **única** salida disponible en esta VPC (sin ella la task no puede
descargar la imagen de ECR, escribir en CloudWatch Logs ni llamar a SSM, EC2, Auto Scaling
o DynamoDB) y no expone el backend: su security group sólo admite `tcp/8080` desde el
security group del ALB, y su salida se limita a `tcp/443` y DNS. Este Terraform **no** crea
VPN, Transit Gateway, NAT gateways, subnets privadas ni endpoints de VPC: el perfil
corporativo depende de una autorización de red aparte. El perfil efectivo se publica en el
output `backend_network_profile`.

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
