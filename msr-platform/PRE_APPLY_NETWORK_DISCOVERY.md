# Informe pre-apply: descubrimiento de red e IAM (fase 2.8, sin mutaciones)

Rama `devin/1785917443-msr-aws-phase1-1`, PR [#6](https://github.com/nicolasgsobrino/mainframe/pull/6).

**Ninguna operación mutativa se ha ejecutado**: sin `terraform apply`, sin plan real, sin
ECR, sin push de imagen, sin ECS, sin ALB, sin DynamoDB, sin endpoints, sin NAT, sin cambios
de IAM, sin patch y sin reset. Todas las banderas de recursos reales siguen en `false`.

## 0. Cómo se obtuvo este informe

Descubrimiento ejecutado el 2026-08-07 con una credencial **temporal de sesión** de la
cuenta `133789123239` (`arn:aws:sts::133789123239:assumed-role/AWS_133789123239_Admin/a-jmariscalalonso@deloitte.es`,
caducada a las 17:53 UTC). Aviso: la credencial entregada es de **administrador**, no
`ReadOnlyAccess`; aun así **sólo** se invocaron operaciones de lectura —
`sts:GetCallerIdentity`, `ec2:Describe*`, `elasticloadbalancing:DescribeLoadBalancers`,
`ecs:ListClusters`, `ecr:DescribeRepositories`, `dynamodb:ListTables`, `iam:GetRole`,
`iam:ListRoles` e `iam:SimulatePrincipalPolicy`. Nada se creó, modificó ni borró.

```bash
cd msr-platform/backend
MSR_AWS_REGION=eu-north-1 .venv/bin/python -m app.net_discovery \
  --vpc-id vpc-023864c0ca3c82eab            # Markdown
MSR_AWS_REGION=eu-north-1 .venv/bin/python -m app.net_discovery \
  --vpc-id vpc-023864c0ca3c82eab --json     # JSON
```

`backend/app/net_discovery.py` sólo emite `Describe*` (`DescribeVpcs`,
`DescribeVpcAttribute`, `DescribeSubnets`, `DescribeRouteTables`, `DescribeVpcEndpoints`,
`DescribeNatGateways`, `DescribeInternetGateways`); un test comprueba que todas las llamadas
empiezan por `describe_` y el doble de cliente falla ante cualquier otra operación.

## 1. VPC elegida

| Dato | Valor |
|---|---|
| VPC | `vpc-023864c0ca3c82eab` (la de la EC2 `i-02f5f4778a9c67865` del laboratorio) |
| CIDR | `172.31.0.0/16` (sin CIDRs adicionales) |
| `IsDefault` | **`true`** — es la VPC por defecto de la región, sin etiquetas |
| DNS support / hostnames | `true` / `true` |
| Internet Gateway | `igw-0904bc0fd030da725` |
| NAT Gateways | **ninguno** |
| VGW / VPN / Transit Gateway / peering | **ninguno** (`DescribeVpnGateways`, `DescribeVpnConnections`, `DescribeTransitGatewayAttachments`, `DescribeVpcPeeringConnections` vacíos) |
| Otras VPCs en la cuenta | ninguna |

## 2. Subnets: todas públicas, ninguna apta

| Subnet | AZ | CIDR | IPs libres | Route table | Salida por defecto | `DefaultForAz` | `MapPublicIpOnLaunch` | ALB interno | Fargate |
|---|---|---|---|---|---|---|---|---|---|
| `subnet-0bb97e6254e4f83e9` | `eu-north-1a` | `172.31.16.0/20` | 4090 | `rtb-09e3e2813fced31ff` | Internet Gateway | sí | sí | **no** | **no** |
| `subnet-0c14b617316ff3efa` | `eu-north-1b` | `172.31.32.0/20` | 4091 | `rtb-09e3e2813fced31ff` | Internet Gateway | sí | sí | **no** | **no** |
| `subnet-09e94d9e3b0e20b8e` | `eu-north-1c` | `172.31.0.0/20` | 4091 | `rtb-09e3e2813fced31ff` | Internet Gateway | sí | sí | **no** | **no** |

Existe **una sola route table**, la principal `rtb-09e3e2813fced31ff`, sin ninguna
asociación explícita de subnet, con exactamente dos rutas: `172.31.0.0/16 → local` y
`0.0.0.0/0 → igw-0904bc0fd030da725`.

Consecuencia: **no hay ninguna subnet privada en la cuenta**. Las tres son públicas por
definición (ruta por defecto a un IGW) y no superan el criterio del ALB interno. Las tres se
descartan también para las tasks: su única salida es el IGW, que con
`assign_public_ip = false` **no da salida ninguna** a una ENI de Fargate, y no hay ni NAT ni
endpoints que la sustituyan.

## 3. Subnets candidatas del ALB

**Ninguna.** No propongo ninguna: no hay subnets privadas y las tres públicas sólo servirían
para un ALB *internet-facing*, que no está autorizado. `backend_alb_subnet_ids` sigue vacío y
el precondition de `aws_lb.backend` detiene el apply.

## 4. Subnets candidatas de las tasks

**Ninguna** con la topología actual y `assign_public_ip = false`. `backend_subnet_ids` sigue
vacío y el precondition de `aws_ecs_task_definition.backend` detiene el apply.

## 5. Análisis de routing

Las tres subnets comparten la tabla principal y salen por el IGW. No existe ningún
attachment corporativo (VPN, Transit Gateway, Direct Connect o peering) que conecte esta VPC
con la red de Deloitte. Los nueve endpoints de VPC evaluados están **ausentes**:

| Servicio | Presente |
|---|---|
| `com.amazonaws.eu-north-1.ecr.api` | no |
| `com.amazonaws.eu-north-1.ecr.dkr` | no |
| `com.amazonaws.eu-north-1.s3` | no |
| `com.amazonaws.eu-north-1.logs` | no |
| `com.amazonaws.eu-north-1.ssm` | no |
| `com.amazonaws.eu-north-1.ssmmessages` | no |
| `com.amazonaws.eu-north-1.ec2` | no |
| `com.amazonaws.eu-north-1.autoscaling` | no |
| `com.amazonaws.eu-north-1.dynamodb` | no |

La EC2 del laboratorio alcanza SSM porque **es** una instancia en subnet pública con IP
pública saliendo por el IGW. Ese mecanismo no es trasladable a una task de Fargate sin IP
pública.

## 6. Origen corporativo de entrada

**Sigue pendiente y es una dependencia externa.** El descubrimiento no propone ningún CIDR
(`alb_ingress_cidrs = []`, estado `pending-network-team`) y no se usa `0.0.0.0/0` ni
`172.31.0.0/16` como sucedáneo. Preguntas exactas para el equipo de red/cloud:

> Cuenta `133789123239`, región `eu-north-1`. Hoy sólo existe la **VPC por defecto**
> `vpc-023864c0ca3c82eab` (`172.31.0.0/16`) con tres subnets públicas, un IGW, sin NAT, sin
> endpoints de VPC y sin VPN/Transit Gateway/peering.
>
> 1. ¿Autorizáis crear en esta cuenta dos subnets **privadas** (AZs `eu-north-1a`/`b`) para
>    las ENIs del ALB interno y las tasks de Fargate, o debemos desplegar en otra VPC ya
>    conectada a la red corporativa? En ese caso, ¿qué VPC y qué subnets?
> 2. ¿Existe (o se puede habilitar) una conexión de la red corporativa a esta cuenta — VPN
>    Site-to-Site, Transit Gateway o Direct Connect? Sin ella, un ALB interno **no es
>    alcanzable** desde un portátil corporativo.
> 3. ¿Qué CIDR(s) representan la red de origen real de los usuarios (VPN/oficina/bastión)?
>    Necesitamos el rango de origen, no el CIDR de la VPC.
> 4. ¿La resolución DNS del nombre del ALB (`*.elb.amazonaws.com`) funciona desde esa red o
>    hace falta un registro en el DNS corporativo?
> 5. Para la salida de las tasks: ¿preferís un **NAT Gateway** en una subnet pública (coste
>    por hora y por GB) o los **nueve endpoints de VPC** del punto 5? ¿Existen endpoints
>    centralizados que debamos consumir en su lugar?
> 6. Si nada de lo anterior es viable a corto plazo, ¿autorizáis excepcionalmente un ALB
>    *internet-facing* restringido a un CIDR corporativo concreto y con HTTPS/ACM?

## 7. Camino de alcance propuesto: NO demostrado

```text
portátil corporativo
  → red/VPN corporativa
  → routing de la VPC            ← NO EXISTE: sin VPN, sin TGW, sin Direct Connect, sin peering
  → ALB interno                  ← NO EXISTE subnet privada donde colocarlo
  → ECS Fargate :8080
```

**La topología actual demuestra que este camino no existe.** Un ALB interno creado hoy en
las subnets públicas sólo sería alcanzable desde dentro de la propia VPC (por ejemplo desde
la EC2 del laboratorio, que el reset destruye). Esto es el bloqueo de red que impide el
apply, y no lo resuelvo con atajos: no propongo `0.0.0.0/0`, ni el CIDR de la VPC, ni
`assign_public_ip = true`.

## 8. NAT y endpoints de VPC: ninguna de las dos alternativas se cumple hoy

- **A. NAT existente** → no hay ningún NAT Gateway en la cuenta.
- **B. Endpoints completos** → los nueve están ausentes.

Con `assign_public_ip = false` (que se mantiene) las tasks **no tendrían salida**: no podrían
descargar la imagen de ECR, ni escribir en CloudWatch Logs, ni llamar a SSM, EC2, Auto
Scaling o DynamoDB. Hay que resolverlo antes del apply, con una de estas opciones y con
autorización explícita (ninguna se ejecuta ahora):

| Opción | Recursos nuevos | Nota |
|---|---|---|
| NAT Gateway | 1 NAT + 1 EIP + 1 route table privada + 2 subnets privadas | coste fijo por hora; salida a Internet controlada |
| Endpoints de VPC | 7 interface (`ecr.api`, `ecr.dkr`, `logs`, `ssm`, `ssmmessages`, `ec2`, `autoscaling`) + 2 gateway (`s3`, `dynamodb`) + SG de endpoints + 2 subnets privadas | sin salida a Internet; coste por endpoint/hora |
| IP pública en la task | ninguno | **descartado**: expondría el backend y contradice `assign_public_ip = false` |

El Terraform de la opción elegida se entregaría en un plan aparte antes de crear nada.

## 9. Escenario IAM: el A no es viable, hay que usar el B

`iam:SimulatePrincipalPolicy` sobre `arn:aws:iam::133789123239:role/AWS_133789123239_Admin`:

| Acción | Decisión |
|---|---|
| `iam:CreateRole` | allowed |
| `iam:TagRole` | allowed |
| `iam:CreatePolicy` | allowed |
| `iam:PassRole` | allowed |
| **`iam:PutRolePolicy`** | **explicitDeny** |
| **`iam:AttachRolePolicy`** | **explicitDeny** |
| `ecr:CreateRepository`, `dynamodb:CreateTable`, `ecs:CreateCluster`, `ecs:RegisterTaskDefinition`, `ecs:CreateService`, `elasticloadbalancing:CreateLoadBalancer`, `elasticloadbalancing:CreateTargetGroup`, `ec2:CreateSecurityGroup`, `ec2:CreateVpcEndpoint`, `ec2:CreateNatGateway`, `logs:CreateLogGroup` | allowed |

Conclusión: **se puede crear un rol pero no darle ningún permiso** — hay un deny explícito
tanto para políticas inline (`aws_iam_role_policy`) como para adjuntar políticas gestionadas
(`aws_iam_role_policy_attachment`). El escenario A produciría un Task Role vacío e inútil, y
además el execution role de ECS necesita `AmazonECSTaskExecutionRolePolicy` adjunta, que
también está denegada.

Por tanto el despliegue debe ir por el **escenario B**: `create_backend_task_role = false`,
`backend_task_role_arn` (y el execution role) **preaprovisionados por el equipo de cloud**
con los documentos exactos que publica Terraform en
`backend_task_role_trust_policy_json` y `backend_task_role_permission_policy_json` (incluye
ya el statement de DynamoDB acotado a `msr-poc-lab-locks`). Ambos caminos siguen soportados
en el código; sólo B es aplicable en esta cuenta. Sin un ARN válido, el precondition de la
task definition detiene el despliegue.

No existe hoy ningún rol `msr*` en la cuenta (`iam:ListRoles`), ni el rol
`msr-poc-linux-patching-01-backend-task` (`NoSuchEntity`).

## 10. Esquema del ALB y flujo de security groups propuesto (sin cambios)

ALB `internal = true`.

| Origen | Destino | Puerto | Implementación |
|---|---|---|---|
| CIDR corporativo (**pendiente**) | SG del ALB | 80 | `aws_vpc_security_group_ingress_rule.backend_alb`, uno por CIDR; sin CIDR no se crea ninguno |
| SG del ALB | SG del backend | 8080 | `aws_vpc_security_group_egress_rule.backend_alb_to_backend` |
| SG del backend | — | 8080 | `aws_vpc_security_group_ingress_rule.backend_from_alb`, por `referenced_security_group_id`, nunca por CIDR |
| SG del backend | APIs de AWS | 443 | `aws_vpc_security_group_egress_rule.backend_https` |
| SG del backend | resolver de la VPC | 53/udp | `aws_vpc_security_group_egress_rule.backend_dns_udp` |

## 11. Salida propuesta de las tasks

```text
ECS Fargate (awsvpc, assign_public_ip = false)
  → subnets privadas (por crear/autorizar)
  → NAT Gateway o endpoints de VPC del punto 8
  → SSM, EC2, Auto Scaling, DynamoDB, ECR, CloudWatch Logs, S3
```

## 12. Recursos que crearía el primer apply

Estado de partida confirmado: **no existe nada** del runtime — `DescribeLoadBalancers`,
`ListClusters`, `DescribeRepositories` y `ListTables` están vacíos.

| Bloque | Bandera | Recursos |
|---|---|---|
| Laboratorio (ya existente) | `enable_real_resources` | 10 recursos, sin cambios |
| ECR | `enable_backend_ecr` | `aws_ecr_repository.backend`, `aws_ecr_lifecycle_policy.backend` |
| Lock | `enable_backend_lock_table` | `aws_dynamodb_table.lab_locks` |
| Runtime | `enable_backend_service` | `aws_cloudwatch_log_group.backend`, `aws_security_group.backend` + 2 reglas de egress, `aws_ecs_cluster.backend`, `aws_ecs_task_definition.backend`, `aws_ecs_service.backend` |
| Runtime + IAM (escenario A) | `create_backend_task_role` | `aws_iam_role.backend_task`, `aws_iam_role_policy.backend_task`, `aws_iam_role.backend_execution`, `aws_iam_role_policy_attachment.backend_execution` — **no aplicable en esta cuenta** (§9) |
| ALB | `enable_backend_alb` | `aws_security_group.backend_alb`, `aws_vpc_security_group_ingress_rule.backend_alb` (uno por CIDR), `aws_vpc_security_group_egress_rule.backend_alb_to_backend`, `aws_vpc_security_group_ingress_rule.backend_from_alb`, `aws_lb.backend`, `aws_lb_target_group.backend`, `aws_lb_listener.backend` |
| Red (no implementado, requeriría autorización) | — | subnets privadas + route table + NAT/EIP **o** 9 endpoints de VPC (§8) |

Todas las banderas están en `false`.

## 13. Dependencias externas pendientes

1. **Subnets privadas o VPC alternativa** para ALB y tasks (§6.1). Bloqueante.
2. **Conectividad corporativa** a la cuenta (§6.2): sin VPN/TGW/DX el ALB interno es
   inalcanzable. Bloqueante.
3. **CIDR(s) de origen** de los usuarios (§6.3) y **DNS** del ALB (§6.4).
4. **Decisión NAT vs. endpoints** para la salida de las tasks (§8). Bloqueante.
5. **Preaprovisionamiento del Task Role y del execution role** por el equipo de cloud: en
   esta cuenta `iam:PutRolePolicy` e `iam:AttachRolePolicy` están explícitamente denegados
   (§9). Bloqueante.
6. **Autorización explícita del `apply`**, que no se solicita en este informe.
