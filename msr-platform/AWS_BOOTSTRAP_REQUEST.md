# Petición al equipo de Cloud/IAM — bootstrap único de la PoC de MSR

Cuenta `133789123239`, región `eu-north-1`. **Operación única y atómica**: los tres elementos
deben existir juntos. Una configuración a medias (por ejemplo el rol sin su política, o el rol
sin la tabla de locks) deja la PoC inutilizable o, peor, sin serialización entre sesiones.

Por qué lo pide el equipo de cloud y no este Terraform: el descubrimiento de sólo lectura
demostró que la cuenta tiene un **`explicitDeny` en `iam:PutRolePolicy` y
`iam:AttachRolePolicy`** (`CreateRole` sí está permitido), así que un rol creado desde la PoC
nacería sin permisos. Detalle en `PRE_APPLY_NETWORK_DISCOVERY.md`.

Contexto y arquitectura: `ARCHITECTURE_REPORT_PHASE2_11.md`.

**No se pide nada más.** En particular: ni ECS, ni ECR, ni ALB, ni NAT, ni VPC endpoints, ni
usuarios IAM, ni access keys, ni ningún recurso de red nuevo.

---

## 1. Proveedor OIDC de IAM

La aplicación se ejecuta en la VM de una sesión de Devin, fuera de AWS, y se autentica con un
token OIDC de la sesión. Emisor y JWKS verificados en vivo (RS256).

| Campo | Valor |
|---|---|
| Provider URL | `https://deloitte-es.devinenterprise.com` |
| Audience (client ID) | `sts.amazonaws.com` |
| Thumbprint | El que calcule la consola/CLI del certificado TLS del emisor |
| ARN resultante | `arn:aws:iam::133789123239:oidc-provider/deloitte-es.devinenterprise.com` |

```bash
aws iam create-open-id-connect-provider \
  --url https://deloitte-es.devinenterprise.com \
  --client-id-list sts.amazonaws.com \
  --tags Key=msr-poc,Value=true
```

## 2. Rol `MSRExternalBackendRole`

### 2.1 Trust policy (literal, sin comodines)

El `sub` es el valor **verificado** en el token de esta organización (se decodificó localmente,
sin publicar el JWT). Restringe el rol a las sesiones de Devin de esta organización.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "OnlyDevinSessionsOfThisOrgMayAssumeThisRole",
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::133789123239:oidc-provider/deloitte-es.devinenterprise.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "deloitte-es.devinenterprise.com:aud": "sts.amazonaws.com",
          "deloitte-es.devinenterprise.com:sub": "org_id:org-4793cba689a54a11b8fe70ed031524c4"
        }
      }
    }
  ]
}
```

### 2.2 Política de permisos (mínimo estricto)

Es el output `backend_external_role_bootstrap.role.permission_policy_json` de
`infra/terraform` (idéntica a `backend_task_role_permission_policy_json`: las llamadas a AWS no
dependen de dónde se aloje la aplicación). Sin `iam:PassRole` —los runbooks no declaran
`assumeRole`—, sin `dynamodb:UpdateItem` y sin ningún `Action: "*"`.

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
      "Action": [
        "ssm:StopAutomationExecution",
        "ssm:GetAutomationExecution",
        "ssm:AddTagsToResource"
      ],
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
          "ssm:resourceTag/msr-lab-id": "linux-patching-01",
          "ssm:resourceTag/msr-poc": "true"
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

`sts:GetCallerIdentity` (que usa la verificación de arranque) no necesita permiso: AWS lo
autoriza siempre a cualquier identidad.

```bash
aws iam create-role \
  --role-name MSRExternalBackendRole \
  --assume-role-policy-document file://msr-external-backend-trust.json \
  --max-session-duration 3600 \
  --tags Key=msr-poc,Value=true

aws iam put-role-policy \
  --role-name MSRExternalBackendRole \
  --policy-name MSRExternalBackendPermissions \
  --policy-document file://msr-external-backend-permissions.json
```

## 3. Tabla de locks `msr-poc-lab-locks`

Serializa las mutaciones del laboratorio **entre sesiones de Devin independientes**: cada
sesión es una VM con su propio disco, así que un lock local no impide que dos personas
parcheen o reseteen la misma EC2 a la vez. El backend toma y renueva el lock con `PutItem`
condicional y lo libera con `DeleteItem` condicional por owner; el TTL sólo limpia locks
abandonados.

```bash
aws dynamodb create-table \
  --table-name msr-poc-lab-locks \
  --attribute-definitions AttributeName=lab_id,AttributeType=S \
  --key-schema AttributeName=lab_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region eu-north-1 \
  --tags Key=msr-poc,Value=true

aws dynamodb update-time-to-live \
  --table-name msr-poc-lab-locks \
  --time-to-live-specification "Enabled=true,AttributeName=expires_at" \
  --region eu-north-1
```

`expires_at` es un epoch numérico (atributo de TTL) y el ítem lleva además `expires_at_iso`
legible, `owner`, `holder`, `operation`, `reason` y `acquired_at`.

## 4. Verificación de aceptación (para quien aplique el bootstrap)

```bash
aws iam get-open-id-connect-provider \
  --open-id-connect-provider-arn arn:aws:iam::133789123239:oidc-provider/deloitte-es.devinenterprise.com
aws iam get-role --role-name MSRExternalBackendRole \
  --query 'Role.AssumeRolePolicyDocument'
aws iam list-role-policies --role-name MSRExternalBackendRole
aws iam list-attached-role-policies --role-name MSRExternalBackendRole   # debe estar vacío
aws dynamodb describe-time-to-live --table-name msr-poc-lab-locks --region eu-north-1
```

Criterios: la trust policy contiene el `sub` literal del §2.1; la política en línea es
exactamente la del §2.2 (ninguna política gestionada adjunta); el TTL está `ENABLED` sobre
`expires_at`.

---

## 5. Validación end-to-end en dry-run (Devin, sesión nueva)

Se ejecuta **después** de que el equipo de cloud confirme el bootstrap, en una sesión nueva con
el blueprint aprobado (que ya incluye `setup-aws-oidc`). Es de sólo lectura: no parchea ni
resetea.

```bash
msr-platform/scripts/start_poc.sh          # deps, build, :8080, identidad, preflight
cd msr-platform/backend && .venv/bin/python -m app.preflight
```

| # | Comprobación | Cómo se evidencia |
|---|---|---|
| 1 | `setup-aws-oidc` funciona | `~/.aws/config` con `credential_process`, y el paso 2 responde |
| 2 | La identidad resuelve `MSRExternalBackendRole` | `preflight.checks[identity].role` |
| 3 | Credenciales temporales | `arn` de `assumed-role`, `temporary: true` |
| 4 | Sin claves estáticas | `static_credentials_present: false`, `credentials_source: default-chain` |
| 5 | La aplicación arranca | `/api/health` 200 y SPA 200 en `:8080` |
| 6 | Modo AWS automático | `MSR_PATCH_PROVIDER=aws-automation` sin intervención |
| 7 | Cuenta `133789123239` | `checks[identity].account` |
| 8 | Región `eu-north-1` | `checks[identity].region` y `checks[lab].region` |
| 9 | Instancia descubierta por tags | `checks[lab].instance_id` (nunca configurado) |
| 10 | SSM `Online` | `checks[lab].ssm_state` |
| 11 | Laboratorio vulnerable y sano | `vulnerable_state: vulnerable`, `health_state: healthy` |
| 12 | Tabla de locks alcanzable | `checks[lock_table].reachable` (`GetItem`) |
| 13 | `MSR_DRY_RUN=true` | `checks[safe_defaults].dry_run` |
| 14 | Ningún patch ni reset | `preflight` usa `allow_reset=false`; CloudTrail sin `StartAutomationExecution` |

Un patch o un reset reales siguen exigiendo autorización explícita y separada
(`MSR_DRY_RUN=false`, y `python -m app.lab_hook --confirm` para recrear el laboratorio).
