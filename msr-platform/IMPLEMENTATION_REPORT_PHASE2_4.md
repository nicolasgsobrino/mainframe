# Fase 2.4 — Espera nativa del reemplazo y trust del rol Automation acotado

Bloqueos detectados en la revisión previa al `apply`. No se ha ejecutado `plan` contra la
cuenta ni `apply`, no se ha llamado a AWS y no se ha creado ningún recurso.

## 1. Punto de partida

El `terraform plan` real del commit `d2d3e0aedfc58c8d307586781ed1b26f684ec19f` terminó
correctamente:

```
Plan: 18 to add, 0 to change, 0 to destroy.
```

Esta fase no cambia los 18 recursos, ni el ASG 1/1/1, ni el Launch Template, ni la AMI, ni
el advisory, ni el releasever, ni el patch baseline, ni la lógica de parcheo, ni la
verificación estricta del reset, ni la ausencia de reglas de ingress; `enable_real_resources`
sigue en `false` y el backend en `mock` con `MSR_DRY_RUN=true`.

## 2. Límite de 600 s en `aws:executeScript`

Systems Manager Automation limita cada acción `aws:executeScript` a **600 segundos** de
ejecución (el paso se aborta al alcanzarlo, sea cual sea el `timeoutSeconds` declarado). El
runbook de reset declaraba 1800 s y hacía el sondeo dentro del script, de modo que la espera
del reemplazo habría fallado por diseño.

### Flujo anterior

```yaml
- name: WaitForReplacementInstance
  action: aws:executeScript
  timeoutSeconds: 1800          # por encima del límite de la acción
  inputs:
    Script: |
      deadline = time.time() + 1500      # bucle interno de 25 minutos
      while time.time() < deadline:
          ... describe_auto_scaling_groups ...
          time.sleep(15)
```

### Flujo corregido

```
TerminateInstanceInAutoScalingGroup   aws:executeAwsApi
WaitForOldInstanceTerminated          aws:waitForAwsResourceProperty   900 s
WaitForReplacementInService           aws:waitForAwsResourceProperty  1800 s   LifecycleState = InService
WaitForReplacementHealthy             aws:waitForAwsResourceProperty   900 s   HealthStatus  = Healthy
DescribeReplacementInstance           aws:executeAwsApi                        DescribeAutoScalingGroups
ValidateReplacementInstance           aws:executeScript                120 s   → NewInstanceId
```

Las dos esperas consultan `autoscaling:DescribeAutoScalingGroups` sobre el ASG fijado por la
IaC (`AutoScalingGroupNames: ['{{ AutoScalingGroupName }}']`, cuyo valor ya se valida contra
`${autoscaling_group_name}` antes de terminar la instancia) con
`PropertySelector: '$.AutoScalingGroups[0].Instances[0].LifecycleState'` y
`... .HealthStatus`. Al ser acciones nativas, `timeoutSeconds: 1800` es legítimo.

`ValidateReplacementInstance` ya no sondea: recibe la lista de instancias del paso anterior y
sólo valida, en menos de un segundo, que

1. hay exactamente una instancia activa (se descartan los estados `Terminating*`/`Terminated`)
   → `RESET_ASG_INSTANCE_COUNT_UNEXPECTED`;
2. su Instance ID **no** es `CurrentInstanceId` → `RESET_REPLACEMENT_NOT_CREATED`;
3. su `LifecycleState` es `InService` → `RESET_REPLACEMENT_NOT_IN_SERVICE`;
4. su `HealthStatus` es `Healthy` → `RESET_REPLACEMENT_NOT_HEALTHY`,

y publica el output `NewInstanceId`. Los siete usos posteriores
(`WaitForNewInstanceRunning`, `WaitForNewManagedNode`, `SendReadinessCommand`,
`WaitForReadinessCommand`, `GetReadinessOutput`, `VerifyNewInstanceTags` y `Report`) consumen
`{{ ValidateReplacementInstance.NewInstanceId }}`; `WaitForReplacementInstance` ya no existe.

Además, **todos** los pasos `aws:executeScript` de los dos runbooks declaran ahora
`timeoutSeconds: 120` (antes heredaban el valor por defecto de Automation, superior al límite
real de la acción) y ninguno contiene `time.sleep` ni bucles de sondeo.

## 3. Trust policy del rol Automation

Antes exigía sólo `aws:SourceAccount`. Ahora exige simultáneamente el principal
`ssm.amazonaws.com`, la cuenta y el ARN de origen:

```json
{
  "Effect": "Allow",
  "Action": "sts:AssumeRole",
  "Principal": { "Service": "ssm.amazonaws.com" },
  "Condition": {
    "StringEquals": { "aws:SourceAccount": "133789123239" },
    "ArnLike": { "aws:SourceArn": "arn:aws:ssm:eu-north-1:133789123239:automation-execution/*" }
  }
}
```

El ARN se deriva de `var.aws_region` y `var.aws_account_id` (nunca `arn:aws:ssm:*:*:*`) y el
principal no se amplía. El documento se construye con `jsonencode` en `locals.tf` en lugar de
`data "aws_iam_policy_document"`, de modo que `terraform test` puede comprobar el JSON exacto
con el provider simulado; el nuevo output `automation_trust_policy` lo expone. El recuento de
recursos no cambia (un `data source` no es un recurso).

## 4. Tests

`backend/tests/test_infra_static.py`:

- `test_no_execute_script_step_exceeds_the_aws_limit` (los dos runbooks): falla si algún
  `aws:executeScript` supera 600 s, si un script contiene `time.sleep`, si declara un
  `deadline`/`time.time() + N` mayor que 600 o si reaparece un `while time.time()`.
- `test_the_replacement_wait_is_native_and_validates_a_new_instance`: la espera de 1800 s es
  `aws:waitForAwsResourceProperty` sobre `DescribeAutoScalingGroups`, existe la espera de
  `HealthStatus = Healthy`, el nuevo Instance ID sale de un `aws:executeAwsApi` con
  `DescribeAutoScalingGroups`, el script de validación es ≤ 120 s y exige una única instancia
  distinta de la anterior, `InService` y `Healthy`, y ningún paso usa ya el output antiguo.
- `test_the_automation_trust_policy_is_scoped_to_the_account_and_region` y
  `test_the_terraform_tests_cover_the_trust_policy_json`.
- `test_reset_replaces_the_instance_only_through_auto_scaling` (existente) sigue exigiendo
  `TerminateInstanceInAutoScalingGroup` con `ShouldDecrementDesiredCapacity: false`.

`infra/terraform/tests/automation_trust.tftest.hcl` (nuevo, `mock_provider "aws"`): decodifica
`output.automation_trust_policy` y comprueba el principal único, `aws:SourceAccount`,
`aws:SourceArn` limitado a `automation-execution/*`, un solo statement y que el ARN sigue a
`aws_region`/`aws_account_id` cuando cambian.

`infra/terraform/tests/enabled_plan.tftest.hcl` (fase 2.3) sigue verificando que la
configuración habilitada planifica los 18 recursos con provider simulado
(`Plan: 18 to add, 0 to change, 0 to destroy.`).

## 5. Resultados locales

| Comando | Resultado |
| --- | --- |
| `pytest` | **252 passed** |
| `ruff check app tests` | `All checks passed!` |
| `python -m compileall app tests` | sin errores |
| `npm ci` | OK (Node 22) |
| `npm run lint` | 0 errores (8 warnings preexistentes) |
| `npx tsc -b` | sin errores |
| `npm run build` | OK (aviso preexistente de chunk > 500 kB) |
| `terraform fmt -check -recursive` | sin diferencias |
| `terraform init -backend=false` | OK |
| `terraform validate` | `Success! The configuration is valid.` |
| `terraform test` | `Success! 11 passed, 0 failed.` |

No se ejecutó `terraform plan` contra la cuenta ni `terraform apply`.

## 6. CI y PR

Los checks del nuevo HEAD (`backend`, `frontend` y `terraform` en `push` y `pull_request`) se
verifican sobre el commit de esta fase en la PR de integración #6:
<https://github.com/nicolasgsobrino/mainframe/pull/6>.

## 7. Confirmación

- Cero llamadas a AWS: `mock_provider` en los tests de Terraform y `botocore.stub.Stubber` en
  los de Python.
- Cero recursos creados: `enable_real_resources = false`, `MSR_DRY_RUN=true` y providers
  `mock` por defecto.
- Sin `plan` real, sin `apply`, sin merge y sin cambiar la base de la PR #6.
