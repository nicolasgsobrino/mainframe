# Fase 2.7 — Modelo IAM y de identidad del backend desplegado (análisis previo, sin cambios en AWS)

Rama `devin/1785917443-msr-aws-phase1-1` · PR [#6](https://github.com/nicolasgsobrino/mainframe/pull/6).
Documento de decisión: **no ejecuta `apply`, ni patch, ni reset, ni ninguna operación mutante**.

## 1. Comportamiento real de `AutomationAssumeRole` en los documentos desplegados

Evidencia sobre la configuración actual (`infra/terraform/`):

| Hecho | Evidencia |
| --- | --- |
| Ambos runbooks declaran `assumeRole: '{{ AutomationAssumeRole }}'` | `documents/MSR-PatchLinuxInstance.yaml:19`, `documents/MSR-ResetLabInstance.yaml:16` |
| El parámetro `AutomationAssumeRole` tiene default **literalmente vacío** | `default: ''` en ambos documentos (`patch:30`, `reset:34`) |
| Terraform **no** inyecta ningún ARN en ese default | `templatefile()` sólo sustituye advisory, patch group, tags, ASG y versión del Launch Template; no existe ninguna variable ni local `automation_assume_role*` en `infra/terraform/*.tf` |
| No existe ningún rol de Automation gestionado por Terraform | Desde la fase 2.5 la configuración no declara ningún recurso `aws_iam_*` (10 recursos, `EC2SSMAgentProfileL0` es data source) |
| El backend omite el parámetro cuando la variable está vacía | `app/providers/aws_ssm_automation.py:477-478`: sólo añade `AutomationAssumeRole` si `MSR_AUTOMATION_ASSUME_ROLE_ARN` tiene valor |
| Los contratos de runbook declaran `requires_assume_role=False` | `app/runbooks.py:99,106,119` |

**Conclusión inequívoca:** los documentos que Terraform desplegaría **no** tienen un ARN de
service role de Automation como default. Con la configuración actual (`MSR_AUTOMATION_ASSUME_ROLE_ARN`
vacío) la Automation se ejecuta **en el contexto del llamante**: los pasos usan los permisos
de la identidad que invoca `StartAutomationExecution`, no los de un rol de ejecución.

Ese diseño se adoptó en la fase 2.5 por una restricción declarada de la cuenta corporativa:
no se permitía crear un service role propio para la PoC, y por eso se eliminaron los ocho
recursos IAM que gestionaba Terraform. La configuración actual es, por tanto, **híbrida sólo
en apariencia**: mantiene el parámetro como punto de extensión, pero ninguna ruta de código o
IaC lo rellena. Aun así, la fase 2.7 debe eliminar esa ambigüedad de forma explícita, y para
eso hacen falta dos decisiones que dependen de permisos y de infraestructura de la cuenta
(sección 4).

## 2. Opción A — rol de ejecución de Automation dedicado (arquitectura preferida)

Requiere que la cuenta permita crear roles IAM para la PoC, lo que contradice la
restricción sobre la que se construyó la fase 2.5.

```
rol de workload del backend → ssm:StartAutomationExecution + iam:PassRole (acotado)
   → rol de ejecución de Automation (MSR-AutomationExecutionRole)
      → EC2 / SSM / Auto Scaling
```

Cambios en Terraform (recuperaría 2 recursos IAM: rol + política):

- `aws_iam_role.automation` con trust policy exacta:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "ssm.amazonaws.com"},
    "Action": "sts:AssumeRole",
    "Condition": {
      "StringEquals": {"aws:SourceAccount": "133789123239"},
      "ArnLike": {"aws:SourceArn": "arn:aws:ssm:eu-north-1:133789123239:automation-execution/*"}
    }
  }]
}
```

- Política del rol de ejecución (permisos que ejecutan los pasos de los runbooks):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {"Effect": "Allow",
     "Action": ["ec2:DescribeInstances", "ec2:DescribeInstanceStatus",
                "autoscaling:DescribeAutoScalingGroups",
                "autoscaling:DescribeAutoScalingInstances",
                "ssm:DescribeInstanceInformation", "ssm:ListCommands",
                "ssm:ListCommandInvocations", "ssm:GetCommandInvocation"],
     "Resource": "*"},
    {"Effect": "Allow",
     "Action": "ssm:SendCommand",
     "Resource": [
       "arn:aws:ssm:eu-north-1::document/AWS-RunShellScript",
       "arn:aws:ssm:eu-north-1::document/AWS-RunPatchBaseline",
       "arn:aws:ec2:eu-north-1:133789123239:instance/*"],
     "Condition": {"StringEquals": {"ssm:resourceTag/msr-poc": "true"}}},
    {"Effect": "Allow",
     "Action": "autoscaling:TerminateInstanceInAutoScalingGroup",
     "Resource": "arn:aws:autoscaling:eu-north-1:133789123239:autoScalingGroup:*:autoScalingGroupName/msr-poc-linux-patching-01-asg"}
  ]
}
```

- El default del parámetro pasa a ser el ARN del rol (`default: '${automation_assume_role_arn}'`)
  y el `allowedPattern` deja de aceptar la cadena vacía.
- El rol de workload del backend añade **exclusivamente**:

```json
{"Effect": "Allow", "Action": "iam:PassRole",
 "Resource": "arn:aws:iam::133789123239:role/MSR-AutomationExecutionRole",
 "Condition": {"StringEquals": {"iam:PassedToService": "ssm.amazonaws.com"}}}
```

y conserva sólo `ssm:StartAutomationExecution` / `StopAutomationExecution` sobre los dos
runbooks permitidos más las lecturas de descubrimiento; **no** necesita `ssm:SendCommand`
ni `autoscaling:TerminateInstanceInAutoScalingGroup`.

## 3. Opción B — contexto del llamante (lo que hay hoy), hecho explícito

Se elimina el punto de extensión para que no quede configuración ambigua:

- se retira `assumeRole` y el parámetro `AutomationAssumeRole` de ambos runbooks;
- se retira `MSR_AUTOMATION_ASSUME_ROLE_ARN` de `Settings`, de `.env.example` y de la
  validación por provider;
- el rol de workload del backend concentra **todos** los permisos de los pasos:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {"Sid": "DiscoverAndInspect", "Effect": "Allow",
     "Action": ["ec2:DescribeInstances", "ec2:DescribeInstanceStatus",
                "autoscaling:DescribeAutoScalingGroups",
                "autoscaling:DescribeAutoScalingInstances",
                "ssm:DescribeInstanceInformation", "ssm:ListInventoryEntries",
                "ssm:DescribeInstancePatches", "ssm:DescribeInstancePatchStates",
                "ssm:DescribeDocument", "ssm:ListCommands",
                "ssm:ListCommandInvocations", "ssm:GetCommandInvocation"],
     "Resource": "*"},
    {"Sid": "RunOnlyAllowlistedRunbooks", "Effect": "Allow",
     "Action": ["ssm:StartAutomationExecution", "ssm:StopAutomationExecution"],
     "Resource": ["arn:aws:ssm:eu-north-1:133789123239:automation-definition/MSR-PatchLinuxInstance:*",
                  "arn:aws:ssm:eu-north-1:133789123239:automation-definition/MSR-ResetLabInstance:*"]},
    {"Sid": "TrackExecutions", "Effect": "Allow",
     "Action": ["ssm:GetAutomationExecution", "ssm:DescribeAutomationStepExecutions"],
     "Resource": "arn:aws:ssm:eu-north-1:133789123239:automation-execution/*"},
    {"Sid": "RunbookStepsSendCommand", "Effect": "Allow",
     "Action": "ssm:SendCommand",
     "Resource": ["arn:aws:ssm:eu-north-1::document/AWS-RunShellScript",
                  "arn:aws:ssm:eu-north-1::document/AWS-RunPatchBaseline",
                  "arn:aws:ec2:eu-north-1:133789123239:instance/*"],
     "Condition": {"StringEquals": {"ssm:resourceTag/msr-poc": "true"}}},
    {"Sid": "RunbookStepsReplaceInstance", "Effect": "Allow",
     "Action": "autoscaling:TerminateInstanceInAutoScalingGroup",
     "Resource": "arn:aws:autoscaling:eu-north-1:133789123239:autoScalingGroup:*:autoScalingGroupName/msr-poc-linux-patching-01-asg"}
  ]
}
```

Sin `iam:PassRole` y sin ningún recurso IAM en Terraform: el rol de workload lo crea el
equipo de cloud corporativo con este documento de política.

Nota: los pasos `aws:executeScript` de ambos runbooks no invocan ninguna API de AWS (se
verificó en la fase 2.5), por lo que no añaden permisos a ninguna de las dos opciones.

## 4. Lo que no puedo determinar por mí mismo

1. **¿La cuenta permite ahora crear el rol de ejecución de Automation?** La fase 2.5
   eliminó todo IAM de Terraform precisamente porque no lo permitía. La opción A revierte esa
   decisión y necesita confirmación explícita.
2. **¿Cuál es el runtime de despliegue?** El repositorio no contiene ninguna definición de
   despliegue (no hay Dockerfile, ECS/EKS, Lambda ni unidad systemd; sólo el workflow de CI
   `msr-platform-ci.yml`, que no despliega). Sin el runtime no puedo dar el ARN real del rol de
   workload ni su trust policy: cambia por completo según el caso.

| Runtime | Identidad de workload | Trust policy |
| --- | --- | --- |
| ECS Fargate | Task Role | `ecs-tasks.amazonaws.com` con `aws:SourceAccount` y `aws:SourceArn` del cluster |
| EC2 | Instance Profile | `ec2.amazonaws.com` |
| EKS | IRSA / Pod Identity | OIDC del cluster con `sub` del ServiceAccount |
| Lambda (sólo el hook) | Execution Role | `lambda.amazonaws.com` |

En los cuatro casos el requisito se cumple igual: `MSR_AWS_PROFILE=` vacío, sin claves
estáticas, sin tokens copiados y sin `aws login`; boto3 usa la cadena de credenciales del
runtime (`app/providers/aws_ssm_automation.py` sólo pasa `profile_name` cuando
`MSR_AWS_PROFILE` tiene valor, y sólo llama a `sts:AssumeRole` cuando `MSR_AWS_ROLE_ARN`
está configurado). No hay ninguna clave de acceso en el código ni en la configuración.

## 5. Ciclo de vida del despliegue previsto

```
desplegar backend
  → el backend obtiene su identidad IAM de workload (sin perfil, sin claves)
  → paso de release de ejecución única: python -m app.lab_hook
      · laboratorio vulnerable y sano → action=none → despliegue listo
      · laboratorio parcheado        → error de confirmación (no muta nada)
  → los workers arrancan con MSR_LAB_RECONCILE_ON_STARTUP=false
```

Despliegue autorizado explícitamente a restaurar un laboratorio parcheado:

```
python -m app.lab_hook --confirm
  → MSR-ResetLabInstance
  → redescubrimiento por tags (Instance ID distinto obligatorio)
  → ASG InService/Healthy · SSM Online · advisory aplicable · salud healthy
  → READY
```

Defaults seguros del entorno desplegado hasta la validación real:

```bash
MSR_PATCH_PROVIDER=aws-automation
MSR_RESTORE_PROVIDER=aws-automation
MSR_DRY_RUN=true
MSR_LAB_RECONCILE_ON_STARTUP=false
MSR_AWS_PROFILE=
MSR_AWS_ROLE_ARN=
```

## 6. Estado de los entregables pedidos

| Entregable | Estado |
| --- | --- |
| Comportamiento real de `AutomationAssumeRole` | **Resuelto**: default vacío, sin ARN; hoy es contexto del llamante (§1) |
| Modelo IAM sin ambigüedad | Especificado en las dos variantes; falta la decisión de §4.1 para implementarlo |
| Políticas y trust policies exactas | §2 y §3 |
| Ámbito exacto de `iam:PassRole` | §2 (sólo aplica a la opción A) |
| Identidad de workload y runtime | **Bloqueado**: el repositorio no define ningún despliegue (§4.2) |
| Prueba de ausencia de credenciales estáticas | §4; tests `test_deployed_backend_needs_no_aws_profile` y `test_local_development_can_use_a_profile` |
| Hook del ciclo de release | §5; implementado en `app/lab_hook.py` desde la fase 2.6 |
| `terraform plan` de los cambios IAM | Opción A: 2 recursos nuevos (`aws_iam_role` + `aws_iam_role_policy`). Opción B: **cero** cambios en AWS. Ningún plan real ejecutado |
| Reconciliación dry-run contra la cuenta real | Pendiente de credenciales y de autorización explícita |
