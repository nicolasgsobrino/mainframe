# Fase 2.7 — Despliegue en ECS Fargate e identidad de workload (opción B explícita)

Rama `devin/1785917443-msr-aws-phase1-1`, PR [#6](https://github.com/nicolasgsobrino/mainframe/pull/6).

**Cero llamadas a AWS y cero cambios en la cuenta**: sin `plan` real, `apply`, `destroy`,
`import`, `untaint` ni cambios de state; sin `StartAutomationExecution`, sin patch y sin
reset. Todo lo verificado aquí es local (`terraform test` con `mock_provider "aws"`, tests
estáticos y build/arranque del contenedor).

## 1. Modelo de identidad cerrado: contexto del llamante, sin ambigüedad

Se elimina por completo la extensión híbrida de `AutomationAssumeRole`:

| Antes | Ahora |
|---|---|
| `assumeRole: '{{ AutomationAssumeRole }}'` en ambos runbooks | ningún `assumeRole` |
| parámetro `AutomationAssumeRole` con `default: ''` | parámetro inexistente y **prohibido** por contrato (`PARAMETER_FORBIDDEN`) |
| `MSR_AUTOMATION_ASSUME_ROLE_ARN` en `.env.example`, `Settings` y outputs | variable inexistente (`automation_assume_role_arn` no está en `model_fields`) |
| `iam:PassRole` acotado al service role | **sin `iam:PassRole`** |
| service role de Automation | ninguno; la Automation corre con la identidad que la inicia |

Consecuencia asumida: el **ECS Task Role** necesita la suma de permisos del backend y de
todos los pasos de los runbooks. Es exactamente lo que implementa la política de §4.

## 2. Arquitectura de despliegue

```text
Internet/usuario
  → frontend (SPA compilada, servida por el propio backend)
  → backend como task de ECS Fargate (awsvpc, sin IP pública, puerto 8080)
  → ECS Task Role (credenciales temporales del endpoint de metadatos del contenedor)
  → AWS Systems Manager Automation
  → runbooks MSR-PatchLinuxInstance / MSR-ResetLabInstance
  → EC2 del laboratorio (descubierta por tags)
```

El backend **no** se despliega en la EC2 del laboratorio: esa instancia se termina a
propósito en cada reset, así que alojar ahí la aplicación la destruiría en cada ciclo.

Separación de responsabilidades:

- **recursos de runtime que Terraform puede crear**: cluster, task definition, servicio,
  security group, reglas de egress y grupo de logs;
- **identidad IAM de workload**: creada por Terraform sólo si la cuenta lo permite; en caso
  contrario la aprovisiona el equipo corporativo y Terraform sólo la consume.

## 3. Contenedor

`msr-platform/Dockerfile` (multi-stage, contexto `msr-platform/`):

1. `node:22-bookworm-slim` → `npm ci` + `npm run build`;
2. `python:3.12-slim-bookworm` → dependencias del backend, `app`, `policy` y la SPA en
   `backend/static` (`app.main` la sirve, mismo origen que `/api`);
3. usuario no root `UID 10001`, `EXPOSE 8080`, `HEALTHCHECK` sobre `/api/health`,
   `MSR_JOBS_DB_PATH=/app/data/msr_jobs.db`;
4. `CMD` = `uvicorn app.main:app --host 0.0.0.0 --port 8080`.

El **mismo artefacto** ejecuta el hook sustituyendo el comando:
`python -m app.lab_hook` / `python -m app.lab_hook --confirm`.

`.dockerignore` excluye `node_modules`, `.venv`, `__pycache__`, `dist`, `data`, `.env*`,
state de Terraform y `terraform.tfvars`: el contexto de build no puede arrastrar secretos.

Verificado localmente (sin AWS):

```text
docker build msr-platform            → sha256:f807ab8a067c…
docker run … python -m app.lab_hook  → ready=true (provider mock, sin AWS)
curl /api/health                     → {"status":"ok"}
curl /                               → 200 (SPA)
docker inspect                       → health=healthy, user=10001
```

CI construye la imagen y ejecuta el hook (`--help`) en un job nuevo, **sin publicarla** y
sin credenciales.

## 4. Identidad de workload

### 4.1 Trust policy exacta del ECS Task Role

```json
{
  "Statement": [
    {
      "Action": "sts:AssumeRole",
      "Condition": {
        "ArnLike": {
          "aws:SourceArn": "arn:aws:ecs:eu-north-1:133789123239:*"
        },
        "StringEquals": {
          "aws:SourceAccount": "133789123239"
        }
      },
      "Effect": "Allow",
      "Principal": {
        "Service": "ecs-tasks.amazonaws.com"
      }
    }
  ],
  "Version": "2012-10-17"
}
```

Sólo el servicio ECS Tasks, sólo desde esta cuenta y sólo para tasks de esta cuenta/región.
Sin comodines de principal.

### 4.2 Política de permisos exacta del ECS Task Role

```json
{
  "Statement": [
    {
      "Action": [
        "ssm:StartAutomationExecution"
      ],
      "Effect": "Allow",
      "Resource": [
        "arn:aws:ssm:eu-north-1:133789123239:automation-definition/MSR-PatchLinuxInstance",
        "arn:aws:ssm:eu-north-1:133789123239:automation-definition/MSR-PatchLinuxInstance:*",
        "arn:aws:ssm:eu-north-1:133789123239:automation-definition/MSR-ResetLabInstance",
        "arn:aws:ssm:eu-north-1:133789123239:automation-definition/MSR-ResetLabInstance:*"
      ],
      "Sid": "StartOnlyTheTwoPocRunbooks"
    },
    {
      "Action": [
        "ssm:StopAutomationExecution",
        "ssm:GetAutomationExecution"
      ],
      "Effect": "Allow",
      "Resource": "arn:aws:ssm:eu-north-1:133789123239:automation-execution/*",
      "Sid": "ControlAndReadOwnAutomationExecutions"
    },
    {
      "Action": [
        "ssm:DescribeAutomationExecutions",
        "ssm:DescribeAutomationStepExecutions",
        "ssm:DescribeDocument"
      ],
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "eu-north-1"
        }
      },
      "Effect": "Allow",
      "Resource": "*",
      "Sid": "ReadAutomationMetadata"
    },
    {
      "Action": [
        "ssm:SendCommand"
      ],
      "Effect": "Allow",
      "Resource": [
        "arn:aws:ssm:eu-north-1::document/AWS-RunPatchBaseline",
        "arn:aws:ssm:eu-north-1::document/AWS-RunShellScript"
      ],
      "Sid": "RunOnlyTheTwoAwsOwnedCommandDocuments"
    },
    {
      "Action": [
        "ssm:SendCommand"
      ],
      "Condition": {
        "StringEquals": {
          "ssm:resourceTag/msr-lab-id": "linux-patching-01",
          "ssm:resourceTag/msr-poc": "true"
        }
      },
      "Effect": "Allow",
      "Resource": "arn:aws:ec2:eu-north-1:133789123239:instance/*",
      "Sid": "SendCommandOnlyToTheTaggedLabInstance"
    },
    {
      "Action": [
        "ssm:GetCommandInvocation",
        "ssm:ListCommandInvocations",
        "ssm:ListCommands"
      ],
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "eu-north-1"
        }
      },
      "Effect": "Allow",
      "Resource": "*",
      "Sid": "ReadCommandResults"
    },
    {
      "Action": [
        "ssm:DescribeInstanceInformation",
        "ssm:DescribeInstancePatchStates",
        "ssm:DescribeInstancePatches",
        "ssm:ListInventoryEntries"
      ],
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "eu-north-1"
        }
      },
      "Effect": "Allow",
      "Resource": "*",
      "Sid": "ReadPatchAndInventoryEvidence"
    },
    {
      "Action": [
        "ec2:DescribeInstances",
        "ec2:DescribeInstanceStatus",
        "ec2:DescribeTags",
        "autoscaling:DescribeAutoScalingGroups",
        "autoscaling:DescribeAutoScalingInstances"
      ],
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "eu-north-1"
        }
      },
      "Effect": "Allow",
      "Resource": "*",
      "Sid": "DiscoverTheLabByTags"
    },
    {
      "Action": [
        "autoscaling:TerminateInstanceInAutoScalingGroup"
      ],
      "Effect": "Allow",
      "Resource": "arn:aws:autoscaling:eu-north-1:133789123239:autoScalingGroup:*:autoScalingGroupName/msr-poc-linux-patching-01-asg",
      "Sid": "ReplaceTheLabInstanceOnlyThroughItsAutoScalingGroup"
    }
  ],
  "Version": "2012-10-17"
}
```

Notas de acotación:

- `ssm:StartAutomationExecution` está limitado a los **dos** runbooks de la PoC (nombre y
  cualquier versión);
- `autoscaling:TerminateInstanceInAutoScalingGroup` está limitado al ASG del laboratorio:
  la sustitución sólo puede ocurrir a través del grupo, y **no** hay
  `ec2:TerminateInstances`, `ec2:RunInstances`, `autoscaling:SetDesiredCapacity` ni
  `autoscaling:UpdateAutoScalingGroup`;
- `ssm:SendCommand` se parte en dos sentencias porque la API autoriza documento e instancia
  por separado: documentos limitados a `AWS-RunPatchBaseline`/`AWS-RunShellScript`, e
  instancia limitada por `ssm:resourceTag/msr-poc = true` y
  `ssm:resourceTag/msr-lab-id = linux-patching-01`;
- las acciones `Describe*`/`List*` de EC2, Auto Scaling y SSM **no admiten ARN de recurso ni
  condición por tag**: quedan con `"Resource": "*"` acotadas por `aws:RequestedRegion`. Es
  una limitación de esas APIs, no una relajación deliberada;
- **no hay `iam:PassRole`** (no existe service role) ni `sts:AssumeRole` (el backend usa
  directamente el Task Role: `MSR_AWS_ROLE_ARN=` vacío);
- no se conceden permisos de escritura sobre documentos SSM (`CreateDocument`,
  `UpdateDocument`, `DeleteDocument`): los runbooks los gestiona Terraform.

### 4.3 Task Role frente a Task Execution Role

| Rol | Quién lo usa | Para qué |
|---|---|---|
| **Task Role** (`task_role_arn`) | el código de la aplicación (boto3) | identidad de workload: inicia y sigue la Automation |
| **Task Execution Role** (`execution_role_arn`) | el agente de ECS, no la aplicación | `docker pull` desde ECR y escritura en CloudWatch Logs (`AmazonECSTaskExecutionRolePolicy`) |

La aplicación nunca obtiene las credenciales del execution role.

### 4.4 Los dos escenarios

```hcl
# A) IAM permitido
enable_backend_service   = true
create_backend_task_role = true    # Terraform crea rol, política y execution role

# B) IAM denegado (supuesto vigente desde la fase 2.5)
enable_backend_service     = true
create_backend_task_role   = false # Terraform NO crea ningún recurso IAM
backend_task_role_arn      = "arn:aws:iam::133789123239:role/<rol-corporativo>"
backend_execution_role_arn = "arn:aws:iam::133789123239:role/<rol-exec-corporativo>"
```

En el escenario B el equipo de cloud debe crear el rol con **exactamente** los documentos de
§4.1 y §4.2; los publica también `terraform output backend_task_role_trust_policy_json` y
`backend_task_role_permission_policy_json`.

**El despliegue falla sin identidad válida**: un `precondition` de
`aws_ecs_task_definition.backend` exige que el ARN efectivo (creado o preaprovisionado)
encaje en `^arn:aws:iam::133789123239:role/…$`, y otros dos exigen `backend_image` y
`backend_subnet_ids`. El test `the_deployment_fails_without_a_workload_role` lo demuestra.

## 5. Recursos Terraform

Laboratorio (sin cambios, **diez** recursos): SG + 3 egress, Launch Template, ASG, patch
baseline, patch group, 2 documentos SSM.

Runtime del backend con `enable_backend_service = true` (**siete** recursos, ninguno IAM):

| Recurso | Requiere permisos IAM |
|---|---|
| `aws_cloudwatch_log_group.backend` | no |
| `aws_security_group.backend` | no |
| `aws_vpc_security_group_egress_rule.backend_https` | no |
| `aws_vpc_security_group_egress_rule.backend_dns_udp` | no |
| `aws_ecs_cluster.backend` | no |
| `aws_ecs_task_definition.backend` | no |
| `aws_ecs_service.backend` | no |

Sólo con `create_backend_task_role = true` se añaden **cuatro** recursos que sí exigen
permisos de IAM: `aws_iam_role.backend_task`, `aws_iam_role_policy.backend_task`,
`aws_iam_role.backend_execution` y `aws_iam_role_policy_attachment.backend_execution`.

Con los valores predeterminados (`enable_backend_service = false`) el plan sigue siendo el
del laboratorio: **diez recursos y ningún `aws_iam_*`**.

Fuera de alcance de esta fase (a decidir con el equipo de red/cloud): repositorio ECR y la
exposición de la UI (ALB/CloudFront/túnel corporativo). El security group del backend no
declara **ninguna** regla de ingress.

## 6. Red

- `awsvpc` sobre `backend_subnet_ids` (subnets **privadas**), `assign_public_ip = false`;
- egress: HTTPS (443) hacia las APIs de AWS y DNS/UDP hacia el resolver de la VPC;
- requiere NAT o endpoints de VPC para `ssm`, `ssmmessages`, `ec2`, `autoscaling`, `ecr.api`,
  `ecr.dkr`, `logs` y `s3` (gateway);
- ingress: ninguno.

## 7. Configuración de la task y ausencia de credenciales estáticas

```bash
MSR_PATCH_PROVIDER=aws-automation
MSR_RESTORE_PROVIDER=aws-automation
MSR_DRY_RUN=true
MSR_LAB_RECONCILE_ON_STARTUP=false
MSR_AWS_PROFILE=
MSR_AWS_ROLE_ARN=
```

Prueba de que no hay credenciales estáticas:

- ninguna variable de la task contiene `ACCESS_KEY`, `SECRET` ni `SESSION_TOKEN`
  (aserción en `terraform test`);
- la task definition **no declara `secrets`** y no se usa Secrets Manager ni Parameter
  Store: no hay nada que inyectar;
- `MSR_AWS_PROFILE` vacío → boto3 no busca perfiles; `MSR_AWS_ROLE_ARN` vacío → no se llama
  a STS: las credenciales salen del endpoint de metadatos del contenedor (Task Role);
- el `Dockerfile`, `backend_ecs.tf` y `backend_iam.tf` no contienen ningún marcador de
  credencial (`test_deployment_runtime.py`);
- el pipeline de release usa **OIDC** (`role-to-assume`), no claves de larga duración.

## 8. Ciclo de release y hook de reconciliación

`.github/workflows/msr-platform-deploy.yml` es **sólo manual** (`workflow_dispatch`),
serializado por `concurrency` y con entorno protegido `msr-poc`:

```text
build+push de la imagen
  → update-service + wait services-stable
  → UNA ejecución de scripts/release_lab_hook.sh (aws ecs run-task, comando sustituido)
      → descubre la EC2 actual por tags
      → vulnerable + sana → action=none, READY, sin reset
      → parcheada         → reset_required, exit ≠ 0, el release no queda listo
  → sólo con el input confirm_reset = true se ejecuta `--confirm`, que sí puede resetear
```

`MSR_LAB_RECONCILE_ON_STARTUP=false` en la task: **ninguna réplica reconcilia al arrancar**,
así que escalar el servicio o reiniciar una task no dispara nada destructivo. El lock
durable de SQLite impide que dos reconciliaciones simultáneas reseteen el laboratorio;
además el hook se lanza como una única task por release y el workflow no admite dos
ejecuciones concurrentes.

Limitación documentada: en Fargate el sistema de ficheros de cada task es efímero, de modo
que el lock y los jobs de SQLite son **locales a la task**. Con `desired_count > 1` no hay
coordinación entre réplicas ni supervivencia de los jobs al reemplazo de una task: para eso
haría falta almacenamiento compartido (EFS) o una base de datos/coordinador externo. La
protección efectiva contra resets concurrentes proviene de que el hook es una invocación
única por release.

## 9. Tests

Nuevos tests de plan (`infra/terraform/tests/backend_service.tftest.hcl`, con
`mock_provider "aws"`):

- el plan del laboratorio no cambia con el runtime desactivado (ASG 1/1/1 intacto);
- con IAM permitido: Task Role planificado, ARN efectivo, trust policy exacta
  (principal, `SourceAccount`, `SourceArn`, sin comodines), política sin `iam:PassRole` ni
  `sts:AssumeRole`, arranque limitado a los dos runbooks, terminación limitada al ASG,
  `SendCommand` limitado por tags y ausencia de atajos destructivos;
- con IAM denegado: **cero** recursos IAM planificados y la task definition usa el rol
  preaprovisionado;
- sin ARN: el plan falla en el `precondition`;
- defaults seguros, ninguna variable con credenciales, sin `secrets`, sin IP pública y hook
  documentado (`app.lab_hook` y `--confirm`).

Nuevos tests estáticos (`backend/tests/test_deployment_runtime.py`, 24 casos): imagen que
sirve la SPA, usuario no root, health check, ausencia de credenciales, hook en la misma
imagen, Fargate/awsvpc, defaults desplegados, precondition de identidad, runtime desactivado
por defecto, trust policy, ausencia de `iam:PassRole`/service role, cobertura completa de
las APIs que usan los runbooks y ausencia de acciones destructivas.

`test_infra_static.py` se ajusta: el laboratorio sigue sin gestionar IAM y el único IAM del
repositorio es el del runtime, opcional y con `count = local.backend_iam_enabled`.

## 10. Resultados locales

```text
pytest                              342 passed
ruff check app tests                All checks passed!
python -m compileall app tests      OK
npm ci / npm run lint               OK (sólo warnings preexistentes de fast-refresh)
npx tsc -b                          OK
npm run build                       built
terraform fmt -check -recursive     limpio
terraform init -backend=false       OK
terraform validate                  Success! The configuration is valid.
terraform test                      Success! 19 passed, 0 failed.
docker build / run                  imagen construida, health=healthy, hook ejecutado (mock)
```

## 11. Qué falta autorizar

Nada de lo siguiente se ha ejecutado y todo requiere autorización explícita:
`terraform plan` real, `terraform apply` (runtime y/o IAM), creación del repositorio ECR,
publicación de la imagen, despliegue del servicio, ejecución del hook contra la cuenta,
patch real y reset real.
