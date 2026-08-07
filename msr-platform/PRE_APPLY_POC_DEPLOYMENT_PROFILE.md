# Perfil de despliegue PoC — informe pre-apply

Fase 2.9. **No se ha ejecutado ninguna mutación en AWS**: ni `terraform apply`, ni plan
real, ni `destroy`, ni push a ECR, ni despliegue de ECS, ni creación de ALB, ni cambios de
IAM, ni patch, ni reset. Todo lo que aparece aquí sale del código, de los tests nativos de
Terraform con `mock_provider` y del descubrimiento de red de sólo lectura documentado en
`PRE_APPLY_NETWORK_DISCOVERY.md`.

## 1. Topología propuesta

```text
cliente (CIDR corporativo autorizado)
  → ALB internet-facing (msr-poc-linux-patching-01-alb)
  → ECS Fargate :8080 en las subnets públicas de vpc-023864c0ca3c82eab
  → ECS Task Role (preaprovisionado)
  → SSM Automation / EC2 / Auto Scaling / DynamoDB
  → EC2 del laboratorio (i-02f5f4778a9c67865)
```

```text
patch/reset desde la UI + reconciliación de release
  → lock distribuido en DynamoDB (msr-poc-lab-locks)
  → exactamente una mutación del laboratorio a la vez
```

Motivo del cambio de perfil: el descubrimiento demostró que la cuenta sólo tiene la VPC por
defecto (`172.31.0.0/16`) con tres subnets públicas, un Internet Gateway, **cero** NAT
gateways, **cero** endpoints de VPC y ninguna conectividad corporativa (sin VPN, sin
Transit Gateway, sin peering). Un ALB interno no sería alcanzable y una task sin IP pública
no tendría salida.

El perfil corporativo privado sigue soportado en el mismo módulo y es el **valor por
defecto** (`backend_alb_internal = true`, `backend_assign_public_ip = false`):

```text
red corporativa → VPN/TGW/peering → ALB interno → tasks privadas → NAT o endpoints de VPC
```

Este Terraform no crea VPN, Transit Gateway, NAT gateways, subnets privadas ni endpoints de
VPC. Ese perfil requiere una autorización de red aparte.

## 2. Configuración exacta del perfil PoC

```hcl
enable_real_resources     = true
enable_backend_service    = true
enable_backend_ecr        = true
enable_backend_alb        = true
enable_backend_lock_table = true

backend_alb_internal      = false
backend_assign_public_ip  = true
backend_alb_subnet_ids    = ["subnet-0bb97e6254e4f83e9", "subnet-0c14b617316ff3efa"]
backend_subnet_ids        = ["subnet-0bb97e6254e4f83e9", "subnet-0c14b617316ff3efa"]
backend_alb_ingress_cidrs = ["<pendiente del equipo de red>"]

backend_image              = "133789123239.dkr.ecr.eu-north-1.amazonaws.com/msr-poc-platform:<tag>"
backend_task_role_arn      = "arn:aws:iam::133789123239:role/<rol corporativo>"
backend_execution_role_arn = "arn:aws:iam::133789123239:role/<rol exec corporativo>"

backend_dry_run = true
```

Subnets candidatas (`backend_candidate_subnet_ids`, del descubrimiento; ni el ALB ni las
tasks pueden usar ninguna otra):

| Subnet | AZ | CIDR | IPs libres |
| --- | --- | --- | --- |
| `subnet-0bb97e6254e4f83e9` | `eu-north-1a` | `172.31.16.0/20` | 4090 |
| `subnet-0c14b617316ff3efa` | `eu-north-1b` | `172.31.32.0/20` | 4091 |
| `subnet-09e94d9e3b0e20b8e` | `eu-north-1c` | `172.31.0.0/20` | 4091 |

Las dos propuestas están en AZs distintas, es el mínimo que exige un ALB, y las tres
comparten la route table `rtb-09e3e2813fced31ff` (`0.0.0.0/0 → igw-0904bc0fd030da725`).

## 3. Lista exacta de recursos del primer apply

Diez del laboratorio (ya definidos y sin cambios) más diecisiete del runtime: **27**. Cero
recursos IAM. Verificado en el test
`the_full_poc_profile_plans_exactly_the_expected_resources`.

Laboratorio:

1. `aws_security_group.lab`
2. `aws_vpc_security_group_egress_rule.https`
3. `aws_vpc_security_group_egress_rule.dns_tcp`
4. `aws_vpc_security_group_egress_rule.dns_udp`
5. `aws_launch_template.lab`
6. `aws_autoscaling_group.lab`
7. `aws_ssm_patch_baseline.lab`
8. `aws_ssm_patch_group.lab`
9. `aws_ssm_document.patch`
10. `aws_ssm_document.reset`

Runtime:

11. `aws_cloudwatch_log_group.backend`
12. `aws_security_group.backend`
13. `aws_vpc_security_group_egress_rule.backend_https`
14. `aws_vpc_security_group_egress_rule.backend_dns_udp`
15. `aws_ecs_cluster.backend`
16. `aws_ecs_task_definition.backend`
17. `aws_ecs_service.backend`
18. `aws_security_group.backend_alb`
19. `aws_vpc_security_group_ingress_rule.backend_alb` (una instancia por CIDR autorizado)
20. `aws_vpc_security_group_egress_rule.backend_alb_to_backend`
21. `aws_vpc_security_group_ingress_rule.backend_from_alb`
22. `aws_lb.backend`
23. `aws_lb_target_group.backend`
24. `aws_lb_listener.backend`
25. `aws_ecr_repository.backend`
26. `aws_ecr_lifecycle_policy.backend`
27. `aws_dynamodb_table.lab_locks`

Con `backend_alb_certificate_arn` se añade `aws_lb_listener.backend_https` y el listener
HTTP pasa a redirigir. Ningún recurso requiere permisos de IAM
(`backend_resource_summary.requires_iam_permissions = false`).

## 4. Reglas de security group

ALB (`msr-poc-linux-patching-01-alb-sg`):

| Dirección | Protocolo/puerto | Origen o destino |
| --- | --- | --- |
| Entrada | `tcp/80` (y `tcp/443` con certificado) | cada CIDR de `backend_alb_ingress_cidrs` |
| Salida | `tcp/8080` | security group del backend |

Backend (`msr-poc-linux-patching-01-backend-sg`):

| Dirección | Protocolo/puerto | Origen o destino |
| --- | --- | --- |
| Entrada | `tcp/8080` | **sólo** el security group del ALB (referencia, no CIDR) |
| Salida | `tcp/443` | `0.0.0.0/0` (ECR, CloudWatch Logs, SSM, EC2, Auto Scaling, DynamoDB) |
| Salida | `udp/53` | CIDR de la VPC (resolver) |

No existe ninguna regla de entrada desde Internet hacia la task, ni con IP pública: la ENI
la recibe para poder salir por el Internet Gateway, no para ser alcanzada. Nunca
`0.0.0.0/0` en entrada: lo rechazan la validación de `backend_alb_ingress_cidrs` y un
precondition de `aws_lb.backend`, incluso con el ALB publicado.

## 5. Red de la task

```hcl
network_configuration {
  subnets          = ["subnet-0bb97e6254e4f83e9", "subnet-0c14b617316ff3efa"]
  security_groups  = [aws_security_group.backend[0].id]
  assign_public_ip = true
}
```

`assign_public_ip = true` es imprescindible en este perfil y **no** es una preferencia: sin
NAT y sin los nueve endpoints de VPC necesarios, una task sin IP pública no puede descargar
la imagen de ECR, escribir en CloudWatch Logs ni llamar a SSM, EC2, Auto Scaling o
DynamoDB, y el despliegue fallaría en el arranque. El valor por defecto del módulo sigue
siendo `false`.

## 6. IAM — escenario B exclusivo

Terraform ya no declara ningún recurso IAM. El descubrimiento con simulación de políticas
mostró `iam:CreateRole` permitido pero `iam:PutRolePolicy` e `iam:AttachRolePolicy` en
**explicitDeny**: un rol creado desde aquí nacería sin permisos. `backend_task_role_arn` y
`backend_execution_role_arn` son obligatorios y, si falta cualquiera de los dos, un
precondition de `aws_ecs_task_definition.backend` detiene el despliegue.

### 6.1 Trust policy (idéntica para los dos roles)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": "ecs-tasks.amazonaws.com" },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": { "aws:SourceAccount": "133789123239" },
        "ArnLike": { "aws:SourceArn": "arn:aws:ecs:eu-north-1:133789123239:*" }
      }
    }
  ]
}
```

### 6.2 Política de permisos del Task Role

Sin `iam:PassRole` (la Automation corre en el contexto del llamante) y sin
`dynamodb:UpdateItem` (la adquisición y la renovación usan `PutItem` condicional y la
liberación `DeleteItem` condicional).

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "StartOnlyTheTwoPocRunbooks",
      "Effect": "Allow",
      "Action": ["ssm:StartAutomationExecution"],
      "Resource": [
        "arn:aws:ssm:eu-north-1:133789123239:automation-definition/MSR-PatchLinuxInstance",
        "arn:aws:ssm:eu-north-1:133789123239:automation-definition/MSR-PatchLinuxInstance:*",
        "arn:aws:ssm:eu-north-1:133789123239:automation-definition/MSR-ResetLabInstance",
        "arn:aws:ssm:eu-north-1:133789123239:automation-definition/MSR-ResetLabInstance:*"
      ]
    },
    {
      "Sid": "ControlAndReadOwnAutomationExecutions",
      "Effect": "Allow",
      "Action": ["ssm:StopAutomationExecution", "ssm:GetAutomationExecution"],
      "Resource": "arn:aws:ssm:eu-north-1:133789123239:automation-execution/*"
    },
    {
      "Sid": "ReadAutomationMetadata",
      "Effect": "Allow",
      "Action": [
        "ssm:DescribeAutomationExecutions",
        "ssm:DescribeAutomationStepExecutions",
        "ssm:DescribeDocument"
      ],
      "Resource": "*",
      "Condition": { "StringEquals": { "aws:RequestedRegion": "eu-north-1" } }
    },
    {
      "Sid": "RunOnlyTheTwoAwsOwnedCommandDocuments",
      "Effect": "Allow",
      "Action": ["ssm:SendCommand"],
      "Resource": [
        "arn:aws:ssm:eu-north-1::document/AWS-RunPatchBaseline",
        "arn:aws:ssm:eu-north-1::document/AWS-RunShellScript"
      ]
    },
    {
      "Sid": "SendCommandOnlyToTheTaggedLabInstance",
      "Effect": "Allow",
      "Action": ["ssm:SendCommand"],
      "Resource": "arn:aws:ec2:eu-north-1:133789123239:instance/*",
      "Condition": {
        "StringEquals": {
          "ssm:resourceTag/msr-poc": "true",
          "ssm:resourceTag/msr-lab-id": "linux-patching-01"
        }
      }
    },
    {
      "Sid": "ReadCommandResults",
      "Effect": "Allow",
      "Action": [
        "ssm:GetCommandInvocation",
        "ssm:ListCommandInvocations",
        "ssm:ListCommands"
      ],
      "Resource": "*",
      "Condition": { "StringEquals": { "aws:RequestedRegion": "eu-north-1" } }
    },
    {
      "Sid": "ReadPatchAndInventoryEvidence",
      "Effect": "Allow",
      "Action": [
        "ssm:DescribeInstanceInformation",
        "ssm:DescribeInstancePatchStates",
        "ssm:DescribeInstancePatches",
        "ssm:ListInventoryEntries"
      ],
      "Resource": "*",
      "Condition": { "StringEquals": { "aws:RequestedRegion": "eu-north-1" } }
    },
    {
      "Sid": "DiscoverTheLabByTags",
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeInstances",
        "ec2:DescribeInstanceStatus",
        "ec2:DescribeTags",
        "autoscaling:DescribeAutoScalingGroups",
        "autoscaling:DescribeAutoScalingInstances"
      ],
      "Resource": "*",
      "Condition": { "StringEquals": { "aws:RequestedRegion": "eu-north-1" } }
    },
    {
      "Sid": "ReplaceTheLabInstanceOnlyThroughItsAutoScalingGroup",
      "Effect": "Allow",
      "Action": ["autoscaling:TerminateInstanceInAutoScalingGroup"],
      "Resource": "arn:aws:autoscaling:eu-north-1:133789123239:autoScalingGroup:*:autoScalingGroupName/msr-poc-linux-patching-01-asg"
    },
    {
      "Sid": "SerializeLabMutationsWithTheLockTable",
      "Effect": "Allow",
      "Action": ["dynamodb:DeleteItem", "dynamodb:GetItem", "dynamodb:PutItem"],
      "Resource": "arn:aws:dynamodb:eu-north-1:133789123239:table/msr-poc-lab-locks"
    }
  ]
}
```

### 6.3 Política de permisos del ECS execution role

Mínimo real, en lugar de la política gestionada `AmazonECSTaskExecutionRolePolicy` (que
autoriza cualquier repositorio y cualquier log group de la cuenta):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AuthenticateAgainstEcr",
      "Effect": "Allow",
      "Action": ["ecr:GetAuthorizationToken"],
      "Resource": "*",
      "Condition": { "StringEquals": { "aws:RequestedRegion": "eu-north-1" } }
    },
    {
      "Sid": "PullOnlyTheMsrImage",
      "Effect": "Allow",
      "Action": [
        "ecr:BatchCheckLayerAvailability",
        "ecr:BatchGetImage",
        "ecr:GetDownloadUrlForLayer"
      ],
      "Resource": "arn:aws:ecr:eu-north-1:133789123239:repository/msr-poc-platform"
    },
    {
      "Sid": "PublishTheContainerLogs",
      "Effect": "Allow",
      "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
      "Resource": "arn:aws:logs:eu-north-1:133789123239:log-group:/aws/ecs/msr-poc-linux-patching-01-backend:*"
    }
  ]
}
```

`logs:CreateLogGroup` no aparece porque el log group lo crea Terraform.

## 7. Ausencia de credenciales estáticas

- Entorno de la task: `MSR_PATCH_PROVIDER=aws-automation`,
  `MSR_RESTORE_PROVIDER=aws-automation`, `MSR_DRY_RUN=true`,
  `MSR_LAB_RECONCILE_ON_STARTUP=false`, `MSR_AWS_PROFILE=`, `MSR_AWS_ROLE_ARN=`.
- Sin bloque `secrets` en la task definition, sin Secrets Manager, sin Parameter Store.
- boto3 obtiene credenciales temporales exclusivamente del endpoint de metadatos del
  contenedor (ECS Task Role); no hay access keys, session tokens, perfiles ni `aws login`.
- El pipeline de release usa OIDC (`aws-actions/configure-aws-credentials@v4` +
  `amazon-ecr-login@v2`).
- Tests que lo comprueban: `test_no_static_credential_reaches_the_task`,
  `the_task_runs_with_safe_defaults_and_no_credentials`.

## 8. HTTPS

No hay ni nombre DNS ni certificado corporativo que reutilizar y no se inventa
infraestructura de DNS, así que el listener por defecto es HTTP: **limitación temporal de la
PoC**, aceptable únicamente porque la entrada está restringida a los CIDR autorizados. El
soporte de TLS está implementado y se activa sin cambios de código en cuanto exista un
certificado en ACM:

```hcl
backend_alb_certificate_arn = "arn:aws:acm:eu-north-1:133789123239:certificate/<id>"
```

Entonces el ALB escucha en 443 con `ELBSecurityPolicy-TLS13-1-2-2021-06`, el listener HTTP
devuelve `HTTP_301` hacia HTTPS y el security group del ALB añade 443 para los mismos
orígenes.

## 9. Dependencia externa que sigue abierta

`backend_alb_ingress_cidrs` es el **único** valor bloqueante: no se inventa ningún rango.
Pregunta exacta para el equipo de red/cloud:

> ¿Qué rangos CIDR públicos de salida (IPs de NAT/proxy corporativos) usarán los equipos
> desde los que se accederá a la herramienta, para autorizarlos como única entrada del ALB
> `msr-poc-linux-patching-01-alb` en la cuenta 133789123239 / `eu-north-1`? Si el acceso
> fuera a hacerse desde direcciones dinámicas, ¿existe un rango corporativo estable o un
> certificado en ACM y un nombre DNS que podamos usar?

Además, para el perfil corporativo futuro siguen pendientes las seis preguntas de
`PRE_APPLY_NETWORK_DISCOVERY.md` (subnets privadas, conectividad VPN/TGW/DX, resolución DNS
interna y NAT frente a endpoints de VPC).

## 10. Validación local

| Comprobación | Resultado |
| --- | --- |
| `pytest` (backend) | 381 passed |
| `ruff check app tests` | All checks passed |
| `compileall app tests` | sin errores |
| `npm run lint`, `tsc -b`, `npm run build` | correctos |
| `terraform fmt -check -recursive` | limpio |
| `terraform validate` | `Success! The configuration is valid.` |
| `terraform test` | `Success! 33 passed, 0 failed.` |

Los planes son **simulados** con `mock_provider "aws"`: no se ejecutó ningún plan real ni
ninguna llamada a AWS. El descubrimiento previo sólo usó `Describe*`/`Get*`/`Simulate*` con
una credencial temporal ya caducada.

## 11. Pendiente de autorización

Nada de lo siguiente se ha ejecutado ni se ejecutará sin autorización explícita:
`terraform apply`, plan real, creación de ECR, push de imagen, despliegue de ECS, creación
de ALB, creación de DynamoDB, endpoints, NAT, cambios de IAM, patch o reset.
