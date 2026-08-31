# Fase 2.1 — Corrección de los bloqueos del IaC y de los runbooks

Continuación de la fase 2 en la **misma rama** (`devin/1785917443-msr-aws-phase1-1`) y en
la **misma PR de integración** [#6](https://github.com/nicolasgsobrino/mainframe/pull/6)
contra `main`. Sin merge, sin PR nueva y sin cambiar la base.

Defaults intactos: `MSR_PATCH_PROVIDER=mock`, `MSR_RESTORE_PROVIDER=mock`,
`MSR_DRY_RUN=true`, `enable_real_resources=false`.

## 1. Problemas detectados en la revisión técnica

| # | Bloqueo | Impacto |
|---|---------|---------|
| 1 | El runbook de parcheo usaba **tres** acciones `aws:runCommand` con `outputs` | Automation sólo permite consumir el output de una acción Run Command: el documento habría fallado al registrarse/ejecutarse |
| 2 | `CloudWatchOutputEnabled=true` en `AWS-RunPatchBaseline` | Exige permisos de CloudWatch Logs que el rol de mínimo privilegio no tiene |
| 3 | Verificación de parcheo débil (advisory por texto libre, kernel sin comparar) | Un parche que no cambia el kernel en ejecución se habría dado por bueno |
| 4 | `aws_instance.lab` gestionado por Terraform + reset que hace `TerminateInstances`/`RunInstances` | Tras cada reset el estado de Terraform apunta a una instancia inexistente: **drift garantizado** y `apply` destructivo |
| 5 | `LaunchTemplateId`/`LaunchTemplateVersion` como parámetros públicos del runbook | La identidad del laboratorio dependía de un input, no de la IaC |
| 6 | El rol de Automation tenía `ec2:RunInstances`, `ec2:TerminateInstances`, `ec2:CreateTags` e `iam:PassRole` | Permisos mutativos innecesarios sobre toda la cuenta |
| 7 | Ninguna comprobación de que la instancia resuelta pertenece al laboratorio gestionado | Un reset podría actuar sobre una instancia ajena con los mismos tags |

## 2. Límite de `aws:runCommand`: una sola acción

`MSR-PatchLinuxInstance` tiene ahora **exactamente una** acción `aws:runCommand`
(`InstallPatchBaseline`), sin `outputs` y sin `CloudWatchOutputConfig`, y sólo para invocar
`AWS-RunPatchBaseline` con `Operation=Install` y `RebootOption=RebootIfNeeded`.

## 3. Flujo precheck → patch → postcheck

Precheck y postcheck ya no son `aws:runCommand`, sino el patrón:

1. `aws:executeAwsApi` → `ssm:SendCommand` (`AWS-RunShellScript`);
2. `aws:waitForAwsResourceProperty` → `ssm:GetCommandInvocation` hasta estado terminal;
3. `aws:executeAwsApi` → `ssm:GetCommandInvocation` con output `StandardOutputContent`;
4. `aws:executeScript` que **parsea de forma estructurada** las líneas `MSR_*`.

El precheck consulta el advisory con el comando exacto:

```
dnf updateinfo list --available --advisory ALAS2023-2026-1651
```

Si el advisory no es aplicable, el runbook aborta en `FailAdvisoryNotApplicable` **antes**
de parchear.

## 4. Verificación estricta posterior

`VerifyPatchOutcome` falla con errores explícitos:

| Error | Condición |
|-------|-----------|
| `ADVISORY_STILL_APPLICABLE` | El advisory sigue apareciendo como disponible |
| `KERNEL_NOT_UPDATED` | El kernel en ejecución es el mismo que antes del parche |
| `KERNEL_NOT_RUNNING_LATEST` | El kernel en ejecución no es el último instalado |
| `POST_PATCH_HEALTH_FAILED` | `httpd` no está `active` o `/health` no es exactamente `MSR_POC_HEALTHY` |

`unknown` nunca se considera satisfactorio.

## 5. Migración a Auto Scaling Group

`aws_instance.lab` **desaparece**. La instancia la mantiene `aws_autoscaling_group.lab`:

- `min_size = 1`, `max_size = 1`, `desired_capacity = 1`;
- una sola subnet (`vpc_zone_identifier = [var.subnet_id]`);
- Launch Template existente con **versión fija y explícita** (nunca `$Latest`);
- `health_check_type = "EC2"`, sin scaling policies, sin Spot, sin scale-in protection;
- tags propagados con `propagate_at_launch = true`;
- IMDSv2, volumen gp3 cifrado, instance profile y Security Group vienen del Launch Template.

Outputs nuevos/mantenidos: `autoscaling_group_name`, `autoscaling_group_arn`,
`launch_template_id`, `launch_template_version` y `lab_instance_id`, este último
**documentado como dinámico**: lo mantiene el ASG y cambia con cada reset.

## 6. Nuevo reset

`MSR-ResetLabInstance` expone **sólo** cuatro parámetros públicos: `CurrentInstanceId`,
`AutoScalingGroupName`, `AutomationAssumeRole` y `CorrelationId`. El Launch Template
esperado y su versión ya no son inputs: Terraform los **renderiza dentro del documento** y
el runbook los usa para validar el ASG.

Secuencia: describir la instancia → validar cuenta, región y tags → `DescribeAutoScalingInstances`
(pertenencia exacta) → `DescribeAutoScalingGroups` (capacidad 1/1/1, Launch Template y versión
esperados, exactamente una instancia operativa) → `TerminateInstanceInAutoScalingGroup` con
`ShouldDecrementDesiredCapacity=false` → esperar que la instancia antigua deje de estar
operativa → esperar una instancia **distinta** `InService`/`Healthy`/`running` → esperar que sea
managed node de SSM y que el bootstrap haya terminado → confirmar AMI exacta, tags, advisory
aplicable y health → devolver `OldInstanceId`/`NewInstanceId`.

No se usa `ec2:TerminateInstances` ni `ec2:RunInstances`. Una AMI vacía o `unknown` provoca
`RESET_AMI_UNVERIFIABLE`.

## 7. Eliminación del drift

Terraform ya no administra ninguna instancia EC2 suelta: administra el ASG, que sobrevive a
las sustituciones. Tras un reset, el estado sigue siendo correcto y `lab_instance_id` se lee
mediante un data source por tags, no desde el estado. Esto permite ejecutar dos ciclos
completos de parcheo después de un reset sin `apply` destructivo.

## 8. IAM

Rol de Automation: se retiran `ec2:RunInstances`, `ec2:TerminateInstances`, `ec2:CreateTags`
e `iam:PassRole`; se añaden `autoscaling:DescribeAutoScalingGroups`,
`autoscaling:DescribeAutoScalingInstances` y
`autoscaling:TerminateInstanceInAutoScalingGroup` (esta última limitada al ARN del ASG del
laboratorio). Se mantiene el `Deny` explícito de `ec2:RunInstances`/`ec2:TerminateInstances`.

Rol de aplicación (control plane): sólo inicia y consulta los dos runbooks `MSR-*`; tiene
`Deny` explícito de `ssm:SendCommand`, `ec2:RunInstances`, `ec2:TerminateInstances`,
`autoscaling:TerminateInstanceInAutoScalingGroup`, `autoscaling:SetDesiredCapacity` y
`autoscaling:UpdateAutoScalingGroup`. Conserva únicamente los dos `autoscaling:Describe*`
de **sólo lectura** imprescindibles para comprobar que la instancia resuelta pertenece al
ASG del laboratorio (ver limitación 14.2).

Los `Describe*` de EC2, SSM y Auto Scaling usan `resources = ["*"]` porque esas APIs no
admiten permisos a nivel de recurso ni condiciones por tag; el filtrado efectivo lo hacen
el runbook y el backend comparando con los valores fijados por la IaC.

## 9. Backend y frontend

- Nueva variable `MSR_LAB_AUTOSCALING_GROUP_NAME` (vacía por defecto), renderizada por
  Terraform en `required_backend_environment`.
- `LabTarget` gana `autoscaling_group_name`, persistido en SQLite con **migración**
  `ALTER TABLE` para bases creadas antes de esta fase.
- El ASG se toma **siempre de la configuración**: `register_lab_target()` ignora el valor
  del payload y el provider envía al runbook `settings.lab_autoscaling_group_name`.
- El resolutor AWS valida la pertenencia al ASG (`LAB_TARGET_NOT_IN_AUTOSCALING_GROUP`).
- Política fail-closed: con provider real, reset sin `MSR_LAB_AUTOSCALING_GROUP_NAME` es
  `PROVIDER_MISCONFIGURED`.
- El reset sigue sin tocar `rings_done`, conserva el historial y sustituye
  `current_instance_id` por el nuevo ID.
- Frontend: el ASG se muestra como campo **sólo lectura** en `LabPanel`; no hay controles
  para instancia, ASG, Launch Template, comandos ni runbooks. Se mantienen `Validate lab`,
  `Patch instance` y `Reset lab`.

## 10. Tests

Añadidos o actualizados (todos estáticos o con stubs; **cero llamadas a AWS**):

- Terraform: ausencia de `aws_instance` en cualquier `.tf`, ASG 1/1/1, versión fija del
  Launch Template, health check EC2, ausencia de policies/Spot/scale-in protection,
  outputs del ASG y `lab_instance_id` documentado como dinámico.
- Runbook de parcheo: una sola acción `aws:runCommand` sin `outputs` ni CloudWatch,
  precheck/postcheck con `SendCommand` + `GetCommandInvocation` + `StandardOutputContent`,
  comando exacto del advisory y presencia de los cuatro errores de verificación.
- Runbook de reset: parámetros públicos exactos, orden de validaciones antes de sustituir,
  `TerminateInstanceInAutoScalingGroup` con `ShouldDecrementDesiredCapacity=false`,
  ausencia de `TerminateInstances`/`RunInstances`, validación de LT/versión/capacidad y
  rechazo de AMI `unknown`.
- IAM: el rol de Automation no conserva EC2 mutativo ni `iam:PassRole`; el rol de
  aplicación no puede mutar EC2 ni Auto Scaling.
- Backend: el ASG procede de la configuración y no del payload, pertenencia al ASG exigida
  en la resolución, migración de una base SQLite sin la columna nueva, reset que no cambia
  `rings_done`, sustitución del Instance ID y API que ignora comandos, Instance IDs, ASG y
  Launch Template enviados por el cliente.

## 11. Resultados locales

| Comprobación | Resultado |
|---|---|
| `pytest` | **228 passed** |
| `ruff check app tests` | `All checks passed!` |
| `python -m compileall app tests` | sin errores |
| `npm ci` | OK (Node 22.12.0, `.nvmrc`) |
| `npm run lint` | 0 errores (8 warnings preexistentes de `react-refresh`) |
| `npx tsc -b` | limpio |
| `npm run build` | OK (aviso preexistente de chunk > 500 kB) |
| `terraform fmt -check -recursive` | sin diferencias |
| `terraform init -backend=false` | OK |
| `terraform validate` | `Success! The configuration is valid.` |

No se ejecutó `terraform plan` ni `terraform apply`.

## 12. Checks de CI

`push / backend`, `push / frontend`, `pull_request / backend` y `pull_request / frontend`
del workflow `.github/workflows/msr-platform-ci.yml` sobre el HEAD de la PR #6.

## 13. Recursos Terraform finales (18)

| Fichero | Recursos |
|---|---|
| `networking.tf` | `aws_security_group.lab`, `aws_vpc_security_group_egress_rule.https`, `.dns_udp`, `.dns_tcp` |
| `iam.tf` | `aws_iam_role.instance`, `aws_iam_role_policy_attachment.instance_ssm_core`, `aws_iam_role_policy.instance_boundary`, `aws_iam_instance_profile.instance`, `aws_iam_role.automation`, `aws_iam_role_policy.automation`, `aws_iam_role.application`, `aws_iam_role_policy.application` |
| `ec2.tf` | `aws_launch_template.lab`, `aws_autoscaling_group.lab` |
| `patching.tf` | `aws_ssm_patch_baseline.lab`, `aws_ssm_patch_group.lab` |
| `automation-documents.tf` | `aws_ssm_document.patch`, `aws_ssm_document.reset` |

Todos con `count = local.enabled` y `enable_real_resources = false`: con la configuración
por defecto **no se crea ningún recurso**.

## 14. Limitaciones

1. Todo está validado de forma estática: sin `plan`, sin `apply` y sin cuenta AWS, así que
   la ejecución real de los runbooks sigue sin verificarse contra el servicio.
2. El rol de aplicación conserva `autoscaling:Describe*` de sólo lectura. Es la única forma
   de comprobar desde el backend que la instancia resuelta pertenece al ASG del laboratorio;
   cualquier acción mutativa de Auto Scaling está explícitamente denegada.
3. `WaitForReplacementInstance` usa `aws:executeScript` con `boto3` para esperar la nueva
   instancia; depende del runtime de Automation y de los `Describe*` de Auto Scaling.
4. La AMI y el advisory siguen siendo **candidatos**: la vulnerabilidad debe confirmarse con
   el precheck real antes de dar por buena la PoC.
5. El data source que expone `lab_instance_id` devuelve vacío mientras el ASG no tenga una
   instancia `running`.

## 15. Cero llamadas a AWS y cero recursos creados

No se ha invocado ninguna API de AWS: los tests usan `botocore.stub.Stubber` o dobles en
memoria, y Terraform sólo se ejecutó con `fmt`, `init -backend=false` y `validate`.
`enable_real_resources=false`, `MSR_DRY_RUN=true` y los providers mock siguen siendo el
comportamiento por defecto.
