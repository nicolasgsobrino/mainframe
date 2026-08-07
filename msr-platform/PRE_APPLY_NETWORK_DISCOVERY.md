# Informe pre-apply: descubrimiento de red e IAM (fase 2.8, sin mutaciones)

Rama `devin/1785917443-msr-aws-phase1-1`, PR [#6](https://github.com/nicolasgsobrino/mainframe/pull/6).

**Ninguna operación se ha ejecutado contra AWS**: sin `terraform apply`, sin ECR, sin push
de imagen, sin ECS, sin ALB, sin DynamoDB, sin cambios de IAM, sin patch y sin reset. Todas
las banderas de recursos reales siguen en `false`.

## 0. Estado del descubrimiento: bloqueado por credenciales

> **Dependencia externa inmediata.** Este entorno **no tiene ninguna credencial de AWS**
> (`aws sts get-caller-identity` → `Unable to locate credentials`; no hay `~/.aws`, ni
> variables `AWS_*`, ni ningún secreto de AWS disponible en la sesión). Por tanto no puedo
> ejecutar el descubrimiento y **no invento** ni subnets, ni AZs, ni rangos de origen.

El procedimiento queda implementado y probado en local, listo para ejecutarse en cuanto
exista una identidad de **sólo lectura** (`ReadOnlyAccess`, o `ec2:Describe*` + los
`iam:Get*`/`iam:Simulate*` del punto 8):

```bash
cd msr-platform/backend
MSR_AWS_REGION=eu-north-1 .venv/bin/python -m app.net_discovery \
  --vpc-id vpc-023864c0ca3c82eab            # informe en Markdown
MSR_AWS_REGION=eu-north-1 .venv/bin/python -m app.net_discovery \
  --vpc-id vpc-023864c0ca3c82eab --json     # el mismo informe en JSON
```

`backend/app/net_discovery.py` sólo emite `Describe*` (`DescribeVpcs`,
`DescribeVpcAttribute`, `DescribeSubnets`, `DescribeRouteTables`, `DescribeVpcEndpoints`,
`DescribeNatGateways`, `DescribeInternetGateways`); un test comprueba que **todas** las
llamadas del descubrimiento empiezan por `describe_` y el doble de cliente falla ante
cualquier otra operación. Lo que reporta, por VPC y por subnet:

| Ámbito | Datos |
|---|---|
| VPC | ID, nombre, CIDR principal y adicionales, `enableDnsSupport`, `enableDnsHostnames` |
| Subnets | ID, AZ, CIDR, IPs disponibles, `MapPublicIpOnLaunch`, route table asociada (o la principal), todas sus rutas y el destino de la ruta por defecto (IGW, NAT, TGW, VGW, peering, Core Network o ninguno), aptitud para ALB interno y para tasks de Fargate, con el motivo exacto de cada descarte |
| Endpoints | presencia, ID, tipo, estado y subnets de `ecr.api`, `ecr.dkr`, `s3`, `logs`, `ssm`, `ssmmessages`, `ec2`, `autoscaling`, `dynamodb` |
| Gateways | NAT gateways (ID, subnet, estado, `ConnectivityType`) e Internet Gateways adjuntos |
| Propuesta | esquema `internal`, subnets candidatas del ALB (una por AZ, ≥2 AZs), subnets candidatas de las tasks, endpoints ausentes y el estado del origen de entrada |

Criterios de aptitud (ninguna subnet se elige por el simple hecho de existir):

- **ALB interno**: la ruta por defecto **no** puede apuntar a un Internet Gateway (eso sería
  una subnet pública, válida sólo para un ALB internet-facing) y necesita ≥ 8 IPs libres.
- **Tasks de Fargate**: salida por NAT/Transit/VPN/Core Network **o** los nueve endpoints de
  VPC completos, y ≥ 4 IPs libres.
- **Origen de entrada**: `alb_ingress_cidrs` se devuelve **vacío** con estado
  `pending-network-team`. La topología no puede demostrar desde qué red acceden los
  usuarios, así que no se propone ningún CIDR; en particular no se usa `0.0.0.0/0` ni el
  CIDR completo de la VPC como sucedáneo (un test lo verifica).

## 1. VPC elegida

`vpc-023864c0ca3c82eab` (`eu-north-1`), la de la EC2 del laboratorio, ya fijada en
`var.vpc_id` y verificada en cada plan por el `check "network"`. CIDR, DNS support y DNS
hostnames: **pendientes de descubrimiento**.

## 2. Subnets candidatas del ALB

**Pendiente.** Única subnet conocida hoy: `subnet-0bb97e6254e4f83e9` (`var.subnet_id`, la
del laboratorio) — una sola subnet y una sola AZ, insuficiente para un ALB, que exige dos
zonas. `backend_alb_subnet_ids` sigue vacío y el precondition de `aws_lb.backend` detiene el
apply mientras no haya al menos dos.

## 3. Subnets candidatas de las tasks

**Pendiente.** `backend_subnet_ids` sigue vacío y el precondition de
`aws_ecs_task_definition.backend` detiene el apply si lo está.

## 4. Análisis de routing

**Pendiente.** El descubrimiento resuelve, por subnet, la route table asociada (o la
principal si no hay asociación explícita) y clasifica el destino de la ruta por defecto.
Hipótesis **no verificada**: la instancia del laboratorio alcanza los endpoints de SSM, así
que su subnet tiene alguna forma de salida (NAT o endpoints). Eso no está probado y no se
extrapola al ALB.

## 5. Origen corporativo de entrada

**Pendiente y externo.** Pregunta exacta para el equipo de red/cloud:

> Para publicar la UI/API de la PoC MSR detrás de un **ALB interno** en
> `vpc-023864c0ca3c82eab` (`eu-north-1`, cuenta `133789123239`):
>
> 1. ¿Qué rango(s) CIDR corresponden a la red desde la que los usuarios accederán
>    realmente (VPN corporativa, red de oficina o bastión)? Necesitamos el rango de
>    **origen**, no el CIDR de la VPC.
> 2. ¿Cómo llega ese origen a la VPC: VPN Site-to-Site, Transit Gateway, Direct Connect o
>    peering? ¿Está ya asociada la ruta correspondiente a las route tables de las subnets
>    que usaría el ALB?
> 3. ¿Qué dos subnets (en AZs distintas) autorizáis para las ENIs del ALB interno, y qué
>    subnets para las tasks de Fargate?
> 4. ¿La resolución DNS del nombre del ALB (`*.elb.amazonaws.com`) funciona desde esa red,
>    o hace falta un registro en el DNS corporativo?
> 5. Si las subnets de las tasks no tienen NAT, ¿autorizáis crear los endpoints de VPC del
>    punto 7 o existen ya endpoints centralizados que debamos consumir?

## 6. Camino de alcance propuesto

```text
portátil corporativo
  → red/VPN corporativa
  → routing de la VPC (VPN Site-to-Site / Transit Gateway / Direct Connect)
  → ALB interno (dos AZs)
  → ECS Fargate :8080
```

**La topología conocida hoy NO demuestra que este camino exista.** Faltan las respuestas 1,
2 y 4 del punto 5; sin ellas el ALB podría crearse y no ser alcanzable, y por eso el
listener nace sin ninguna regla de entrada. Esta es la dependencia de red que bloquea el
apply.

## 7. NAT y endpoints de VPC

**Pendiente.** Dos alternativas, por orden de preferencia:

- **A. NAT existente.** Si las subnets elegidas ya tienen ruta por defecto a un NAT o
  Transit Gateway corporativo, no se crea nada. Es la opción preferida.
- **B. Endpoints de VPC.** Si no hay salida, la lista exacta que habría que proponer es:
  `com.amazonaws.eu-north-1.ecr.api`, `ecr.dkr`, `logs`, `ssm`, `ssmmessages`, `ec2`,
  `autoscaling` (interface) y `s3`, `dynamodb` (gateway). No se crea ninguno en esta fase:
  el Terraform propuesto para ellos se entregaría antes, en un plan aparte.

No se creará ningún NAT Gateway ni ninguna salida amplia a Internet por iniciativa propia.

## 8. Escenario IAM

**No determinable en sólo lectura desde aquí** (sin credenciales). Con una identidad de
lectura se resolvería con llamadas read-only:

```bash
aws iam simulate-principal-policy \
  --policy-source-arn <arn-de-la-identidad> \
  --action-names iam:CreateRole iam:PutRolePolicy iam:AttachRolePolicy
aws iam get-role --role-name msr-poc-linux-patching-01-backend-task   # ¿ya existe?
```

Mientras no esté confirmado se mantienen **ambos** caminos, sin asumir que IAM esté
permitido:

- **A** `create_backend_task_role = true`: Terraform crea Task Role, política (incluido el
  statement de DynamoDB) y execution role.
- **B** `create_backend_task_role = false`: Terraform no gestiona IAM y consume
  `backend_task_role_arn`; los documentos exactos que debe aplicar el equipo de cloud son
  `backend_task_role_trust_policy_json` y `backend_task_role_permission_policy_json`.

Sin un ARN válido de la cuenta `133789123239`, el precondition de la task definition detiene
el despliegue.

## 9. Esquema del ALB y flujo de security groups propuesto

ALB `internal = true` (sin cambios; un ALB público sigue bloqueado por precondition si se
combina con `0.0.0.0/0`).

| Origen | Destino | Puerto | Implementación |
|---|---|---|---|
| CIDR corporativo (**pendiente**) | SG del ALB | 80 | `aws_vpc_security_group_ingress_rule.backend_alb`, un recurso por CIDR; sin CIDR no se crea ninguno |
| SG del ALB | SG del backend | 8080 | `aws_vpc_security_group_egress_rule.backend_alb_to_backend` |
| SG del backend | — | 8080 | `aws_vpc_security_group_ingress_rule.backend_from_alb`, por `referenced_security_group_id`, nunca por CIDR |
| SG del backend | APIs de AWS | 443 | `aws_vpc_security_group_egress_rule.backend_https` |
| SG del backend | resolver de la VPC | 53/udp | `aws_vpc_security_group_egress_rule.backend_dns_udp` |

## 10. Salida propuesta de las tasks

```text
ECS Fargate (awsvpc, sin IP pública)
  → NAT/Transit Gateway existente          (opción A, preferida)
  → o endpoints de VPC del punto 7         (opción B, sólo con autorización)
  → SSM, EC2, Auto Scaling, DynamoDB, ECR, CloudWatch Logs, S3
```

## 11. Recursos que crearía el primer apply

Con `enable_real_resources = true` y las banderas que se activen:

| Bloque | Bandera | Recursos |
|---|---|---|
| Laboratorio (ya existente) | `enable_real_resources` | 10 recursos, sin cambios |
| ECR | `enable_backend_ecr` | `aws_ecr_repository.backend`, `aws_ecr_lifecycle_policy.backend` |
| Lock | `enable_backend_lock_table` | `aws_dynamodb_table.lab_locks` |
| Runtime | `enable_backend_service` | `aws_cloudwatch_log_group.backend`, `aws_security_group.backend`, sus dos reglas de egress, `aws_ecs_cluster.backend`, `aws_ecs_task_definition.backend`, `aws_ecs_service.backend` |
| Runtime + IAM (escenario A) | `create_backend_task_role` | `aws_iam_role.backend_task`, `aws_iam_role_policy.backend_task`, `aws_iam_role.backend_execution`, `aws_iam_role_policy_attachment.backend_execution` |
| ALB | `enable_backend_alb` | `aws_security_group.backend_alb`, `aws_vpc_security_group_ingress_rule.backend_alb` (uno por CIDR autorizado), `aws_vpc_security_group_egress_rule.backend_alb_to_backend`, `aws_vpc_security_group_ingress_rule.backend_from_alb`, `aws_lb.backend`, `aws_lb_target_group.backend`, `aws_lb_listener.backend` |

Todas las banderas están en `false`. `output.backend_resource_summary` enumera lo mismo a
partir de la configuración efectiva.

## 12. Dependencias externas pendientes

1. **Credencial de sólo lectura** en la cuenta `133789123239` para ejecutar el
   descubrimiento (bloqueante para todo lo demás).
2. **Rango(s) de origen corporativo** del punto 5.1 y prueba del routing del punto 5.2.
3. **Autorización de subnets** para ALB y tasks (punto 5.3).
4. **Resolución DNS** del nombre del ALB desde la red corporativa (punto 5.4).
5. **Decisión sobre NAT/endpoints** (punto 5.5 y punto 7).
6. **Escenario IAM** A o B (punto 8).
7. **Autorización explícita del `apply`**, que no se solicita en este informe.
