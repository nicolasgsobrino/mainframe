# Fase 2 — Infraestructura, runbooks e integración del laboratorio EC2

Preparación completa de la integración real con AWS Systems Manager Automation **sin
ejecutar nada en AWS**: cero llamadas a la cuenta, cero recursos creados, sin
`terraform plan` ni `terraform apply`, sin credenciales y con los defaults seguros intactos
(`MSR_PATCH_PROVIDER=mock`, `MSR_RESTORE_PROVIDER=mock`, `MSR_DRY_RUN=true`,
`enable_real_resources=false`).

---

## 1. Arquitectura objetivo

```
Frontend (LabPanel)              Backend FastAPI                      AWS (cuando se active)
────────────────────             ─────────────────────                ──────────────────────
Validate lab      ──POST──▶ /api/labs/{id}/validate  ──read-only──▶ DescribeInstances
                                                                     DescribeInstanceInformation
Patch instance    ──POST──▶ /api/tasks/{id}/approve  ──Automation──▶ MSR-PatchLinuxInstance
                                                                       └─ aws:runCommand
                                                                            AWS-RunPatchBaseline
Reset lab         ──POST──▶ /api/labs/{id}/reset     ──Automation──▶ MSR-ResetLabInstance
                                  │                                    └─ Terminate + RunInstances
                                  ▼
                            SQLite (jobs, LabTarget)
                                  ▲
                            reconciler → provider.poll()
```

AWS es el **ejecutor duradero**; el backend nunca ejecuta el parche: crea un job persistido,
inicia la Automation y reconcilia por polling. El frontend sondea el job y se recupera tras
un reload porque `active_job` viene del backend.

## 2. Recursos Terraform (`msr-platform/infra/terraform/`)

18 recursos, **todos** con `count = local.enabled` (`enable_real_resources ? 1 : 0`):

| Fichero | Recursos |
|---|---|
| `networking.tf` | `aws_security_group.lab` (sin ingress), 3 × `aws_vpc_security_group_egress_rule` (HTTPS, DNS TCP/UDP) |
| `iam.tf` | `aws_iam_role.instance` + `aws_iam_role_policy.instance_boundary` + `aws_iam_role_policy_attachment.instance_ssm_core` + `aws_iam_instance_profile.instance`; `aws_iam_role.automation` + policy; `aws_iam_role.application` + policy |
| `ec2.tf` | `aws_launch_template.lab`, `aws_instance.lab` |
| `patching.tf` | `aws_ssm_patch_baseline.lab`, `aws_ssm_patch_group.lab` |
| `automation-documents.tf` | `aws_ssm_document.patch`, `aws_ssm_document.reset` |

Sin backend remoto (estado local de PoC, documentado y excluido de git junto con
`terraform.tfvars`, `.terraform/`, `*.tfstate*` y `crash.log`). La VPC y la subnet son
**existentes**: no se crea red.

Guardrails: `allowed_account_ids` en el provider, `check` de cuenta/región/VPC/subnet/AMI
(arquitectura y propietario), preconditions en `aws_instance.lab` y `aws_launch_template.lab`,
validación de `aws_account_id`, `candidate_advisory_id`, `root_volume_size_gib >= 8` y
rechazo explícito de `allowed_ui_cidr = 0.0.0.0/0`.

## 3. Flujo de parcheo

```
POST /approve → job PATCH (SQLite, lock por target)
  → resolver instancia por tags (exactamente una)
  → validar política (track A, cuenta, región, entorno, tag, runbook Automation)
  → describe_document → DocumentType == Automation
  → StartAutomationExecution(MSR-PatchLinuxInstance)
      1 existe / 2 cuenta+región / 3 running / 4 tags / 5 managed node
      6 precheck read-only (os-release, kernel, dnf updateinfo, http, /health)
      7 ¿no aplica? → ADVISORY_NOT_APPLICABLE y fin sin parchear
      9 aws:runCommand AWS-RunPatchBaseline (Operation=Install, RebootIfNeeded)
     10-11 esperar running + managed node
     12-14 verificar advisory no aplicable, kernel nuevo, HTTP y /health
     15 Report: advisory, previous/current kernel, reboot, patch status, health, instance, correlation
  → reconciler → provider.poll() → SQLite → frontend
```

## 4. Flujo de reset

```
POST /api/labs/{id}/reset → 202 + job RESET_LAB (restore provider)
  → StartAutomationExecution(MSR-ResetLabInstance)
      1 DescribeCurrentInstance
      2 ValidateResettableTarget: msr-poc, msr-lab-id, msr-environment, msr-resettable=true
      3 TerminateCurrentInstance (sólo si TODOS los tags coinciden) + esperar terminación
      4 LaunchReplacement desde LaunchTemplateId + versión FIJA
      5 esperar running → managed node → readiness (/var/lib/msr-poc/bootstrap-complete)
      6 confirmar AMI base, advisory aplicable, HTTP saludable y tags
      7 Report: OldInstanceId, NewInstanceId, LogicalLabId, VulnerableState, HealthState, CorrelationId
  → poll() devuelve new_instance_id → LabTarget.current_instance_id actualizado
```

`reset_lab` ≠ `rollback`: no recorre la rama de rollback del Store, **no** incrementa
`rings_done`, conserva el historial completo de jobs y devuelve la tarea a estado
vulnerable/open.

## 5. Advisory candidato y confirmación

`ALAS2023-2026-1651` (familia `kernel`) es un **candidato**. La AMI
`ami-0b2ab3a97a77bd35e` es antigua, pero la antigüedad **no** prueba vulnerabilidad: la
aplicabilidad sólo se confirma con el precheck (`dnf updateinfo list --security`) dentro del
runbook. Hasta entonces el backend reporta `vulnerable_state = "vulnerable_expected"` con
`advisory_confirmed = false`, y la UI lo indica explícitamente.

## 6. Seguridad de red

Sin SSH, sin key pair, security group **sin ninguna regla de entrada**; egress limitado a
HTTPS (SSM y repositorios de Amazon Linux) y DNS hacia el CIDR de la VPC. IPv4 pública
mientras no haya VPC endpoints privados (limitación documentada). IMDSv2 obligatorio
(`http_tokens = required`, hop limit 1), root volume gp3 cifrado ≥ 8 GiB con
`delete_on_termination`, detailed monitoring desactivado.

## 7. IAM

- **Instancia**: trust sólo `ec2.amazonaws.com`; `AmazonSSMManagedInstanceCore` y una policy
  inline de **Deny** explícito sobre `ssm:StartAutomationExecution`, `ec2:RunInstances`,
  `ec2:TerminateInstances`, `ec2:CreateTags`, `sts:AssumeRole` e `iam:*`.
- **Automation**: trust sólo `ssm.amazonaws.com` con `aws:SourceAccount`; lectura de
  instancias/tags/inventario, `SendCommand` limitado a `AWS-RunPatchBaseline` y
  `AWS-RunShellScript` **y** a instancias con los cuatro tags del laboratorio; reboot/stop/
  terminate condicionados por los mismos tags; `RunInstances` restringido a la subnet, el
  security group, el Launch Template y la AMI del laboratorio; `CreateTags` limitado a las
  claves esperadas con `ec2:CreateAction = RunInstances`; `PassRole` sólo del instance
  profile del laboratorio hacia `ec2.amazonaws.com`; Deny explícito de creación/modificación
  IAM.
- **Aplicación** (`msr-poc-application-role`): trust desde
  `arn:aws:iam::133789123239:role/AWS_133789123239_Admin`; sólo lectura +
  `StartAutomationExecution` sobre los dos runbooks `MSR-*`, `StopAutomationExecution`,
  `PassRole` del rol de Automation hacia `ssm.amazonaws.com`, y Deny de `ssm:SendCommand`,
  `ec2:RunInstances`, `ec2:TerminateInstances` e `iam:*`.

Ninguna policy Allow usa `*` como acción ni comodines de servicio (verificado por test).
`ec2:Describe*` y `ssm:Describe*` usan `resources = ["*"]` porque esas APIs no admiten
permisos a nivel de recurso: limitación de AWS, documentada en el propio fichero.

## 8. Patch baseline

`msr-poc-al2023-baseline` (`AMAZON_LINUX_2023`), asociado al patch group `msr-poc-linux` y
con `approved_patches = [ALAS2023-2026-1651]`, `approved_patches_enable_non_security = false`
y **sin** `approval_rules` (cualquier regla por severidad ampliaría el alcance). La
instalación la hace `AWS-RunPatchBaseline` invocado **desde** el runbook Automation;
`Scan` funciona igual sobre el mismo baseline.

Limitación documentada: Patch Manager acepta el advisory como identificador literal, pero no
existe API para verificar que el ID existe; si fuera inválido la ejecución no instalaría nada
y parecería «correcta». Por eso el runbook aborta con `ADVISORY_NOT_APPLICABLE` en lugar de
dar por buena una ejecución vacía.

## 9-10. Runbooks

Ambos son `Automation` (`schemaVersion 0.3`) y sólo aceptan parámetros cerrados:
`MSR-PatchLinuxInstance` → `InstanceId`, `AutomationAssumeRole`, `CorrelationId`;
`MSR-ResetLabInstance` → `CurrentInstanceId`, `LaunchTemplateId`, `LaunchTemplateVersion`,
`AutomationAssumeRole`, `CorrelationId`. El advisory, los tags, la cuenta, la región y la AMI
los fija Terraform con `templatefile()`: **nunca** llegan desde el frontend. No hay ningún
parámetro que acepte comandos, scripts, documentos, URLs ni `Operation`.

## 11. Resolución por identificador lógico

`app/labs.py`: `AwsLabResolver` filtra por los tags obligatorios y por estados activos
(`pending`, `running`, `stopping`, `stopped` — se excluyen `shutting-down` y `terminated`),
exige **exactamente una** instancia (`LAB_TARGET_NOT_FOUND` / `LAB_TARGET_AMBIGUOUS`),
valida el formato del Instance ID y los tags (`LAB_TARGET_TAGS_INVALID`) y confirma el
managed node. `MockLabResolver` no llama a AWS: lee el `LabTarget` de SQLite. El seed no fija
ningún Instance ID; en modo mock se genera uno sintético determinista.

## 12. Backend

Tarea track A del laboratorio (`RTASK900900`, advisory `ALAS2023-2026-1651`, componente
`kernel`, `logical_target_id = linux-patching-01`, entorno `sandbox`) y cuatro endpoints:
`GET /api/labs/{id}`, `POST /api/labs/{id}/validate` (read-only), `POST /api/labs/{id}/reset`
(`202`) y `GET /api/labs/{id}/jobs`. Ninguno acepta Instance IDs, comandos, documentos,
advisories ni parámetros del cliente: sólo el identificador lógico de la ruta y la cabecera
`Idempotency-Key`.

## 13. Frontend

`components/LabPanel.tsx`, integrado en `TaskDetail` sólo para la tarea del laboratorio:
estado, Instance ID, AMI, advisory, estado del agente SSM, vulnerable/parcheado, health
check, cuenta/región y número de resets; botones **Validate lab**, **Patch instance**
(deshabilitado hasta que una validación correcta confirme el estado vulnerable) y
**Reset lab** (con confirmación explícita que aclara que no es un rollback). Muestra
old → new Instance ID del último reset, distingue mock / dry-run / AWS real y mantiene el
polling con recuperación tras reload.

## 14-15. Variables y outputs

`.env.example` documenta `MSR_AWS_REGION=eu-north-1`, `MSR_ALLOWED_ACCOUNT_IDS`,
`MSR_ALLOWED_REGIONS`, `MSR_ALLOWED_ENVIRONMENTS=sandbox`, `MSR_LAB_LOGICAL_ID`,
`MSR_LAB_TAG_KEY`, `MSR_LAB_ENVIRONMENT`, `MSR_PATCH_ADVISORY_ID`,
`MSR_PATCH_PACKAGE_FAMILY`, `MSR_PATCH_RUNBOOK_NAME`, `MSR_RESET_RUNBOOK_NAME`,
`MSR_REQUIRED_TARGET_TAG_KEY/VALUE`, `MSR_LAB_LAUNCH_TEMPLATE_ID/VERSION` y `MSR_DRY_RUN=true`.
Los ARNs (`MSR_AWS_ROLE_ARN`, `MSR_AUTOMATION_ASSUME_ROLE_ARN`) quedan **vacíos**: todavía no
existen. Terraform los publica en `required_backend_environment` junto con
`lab_instance_id`, `lab_logical_id`, `lab_public_ip`, `lab_private_ip`, `launch_template_id`,
`launch_template_version`, `instance_profile_arn`, `application_role_arn`,
`automation_role_arn`, `patch_runbook_name/arn`, `reset_runbook_name/arn`,
`patch_baseline_id`, `patch_group`, `security_group_id` y `estimated_resource_summary`.
Ningún output expone secretos.

## 16. Tests

**207 tests** en total (154 en la fase 1.2, **+53** en esta fase), ninguno llama a AWS:

- `tests/test_lab_resolution.py` (8): una instancia, cero, ambigua, tags inválidos, estados
  excluidos, helpers de tags, resolutor mock, target inicial sin Instance ID.
- `tests/test_lab_api.py` (9): snapshot, 404, validación read-only, job `reset_lab`,
  actualización del Instance ID, `logical_lab_id` conservado, `rings_done` sin incrementar,
  historial y rechazo de Instance IDs/comandos enviados en el cuerpo.
- `tests/test_aws_reset_contract.py` (14, `botocore.stub.Stubber`): parámetros exactos del
  reset, exigencia de versión fija del Launch Template, `NewInstanceId` sanitizado, output
  no válido descartado y parámetros prohibidos/obligatorios del contrato.
- `tests/test_infra_static.py` (21): `enable_real_resources=false` en los 18 recursos,
  IMDSv2, gp3 cifrado ≥ 8 GiB, sin key pair, sin detailed monitoring, SG sin ingress, CIDR
  abierto rechazado, user data sin `dnf update`, baseline restringido al advisory, IAM sin
  comodines administrativos, ambos documentos `Automation`, el runbook de parcheo invoca
  `AWS-RunPatchBaseline` con `Install`/`RebootIfNeeded` tras el precheck, el de reset valida
  los tags **antes** de terminar y usa versión fija (nunca `$Latest`), sin credenciales
  versionadas y `.gitignore` correcto.
- Actualizados: `test_fail_closed_policy.py` (identidad resoluble en lugar de Instance ID
  fijo), `test_lab_targets.py` y `test_api.py` (nueva firma de reset y auto-registro).

## 17. CI

`.github/workflows/msr-platform-ci.yml` añade el job `terraform`:
`terraform fmt -check -recursive`, `terraform init -backend=false` y `terraform validate`.
Sin credenciales AWS, sin `plan` y sin `apply`.

## 18. Resultados exactos

| Validación | Resultado |
|---|---|
| `pytest` | **207 passed** |
| `ruff check app tests` | `All checks passed!` |
| `python -m compileall app tests` | OK |
| `npm ci` | OK (Node 22.12.0, `.nvmrc`) |
| `npm run lint` | 0 errores, 8 warnings preexistentes (`react(only-export-components)` en `ui.tsx`/`view.tsx`) |
| `npx tsc -b` | Sin errores |
| `npm run build` | OK (aviso preexistente de chunk > 500 kB) |
| `terraform fmt -check -recursive` | Sin diferencias |
| `terraform init -backend=false` | OK |
| `terraform validate` | `Success! The configuration is valid.` |
| `terraform plan` / `apply` | **No ejecutados** (prohibidos en esta fase) |

## 19. Limitaciones

1. El advisory sigue siendo candidato: la aplicabilidad sólo se confirma con el precheck.
2. La instancia usa IPv4 pública porque no hay VPC endpoints de SSM; con endpoints privados
   se puede eliminar.
3. `ec2:Describe*` / `ssm:Describe*` no admiten restricción por recurso.
4. Tras un `reset_lab`, la instancia creada por el runbook queda **fuera del estado de
   Terraform** (`aws_instance.lab` ignora cambios). Es intencional en la PoC, pero un
   `terraform apply` posterior intentaría recrear su propia instancia: hay que hacer
   `terraform state rm`/`import` o aceptar el drift.
5. Patch Manager no permite validar que el advisory exista.
6. `MSR-RollbackLinuxInstance` sigue sin materializarse en Terraform (rollback fuera de
   alcance de esta fase).
7. Nada se ha probado contra AWS: la primera ejecución real será dry-run.

## 20. Pasos exactos para activar (fase siguiente)

```bash
cd msr-platform/infra/terraform
cp terraform.tfvars.example terraform.tfvars     # ajustar cuenta/red/AMI
terraform init                                    # con credenciales del operador
terraform plan -var 'enable_real_resources=true'  # REVISIÓN HUMANA del plan
terraform apply -var 'enable_real_resources=true'
terraform output required_backend_environment     # → msr-platform/.env

# Validación SSM (sólo lectura)
aws ssm describe-instance-information --region eu-north-1
aws ssm describe-document --name MSR-PatchLinuxInstance --region eu-north-1
aws ssm describe-document --name MSR-ResetLabInstance  --region eu-north-1

# Primera ejecución: dry-run, sin mutar nada
# .env: MSR_PATCH_PROVIDER=aws-automation, MSR_RESTORE_PROVIDER=aws-automation,
#       MSR_DRY_RUN=true  ← se mantiene en true
curl -X POST http://localhost:8080/api/labs/linux-patching-01/validate
```

Sólo después de un dry-run correcto se evaluará `MSR_DRY_RUN=false`, que exige la política
fail-closed completa.

## 21-23. Confirmaciones

- **Cero llamadas a AWS** en esta fase: ningún test ni comando ha contactado con la cuenta
  (los tests de AWS usan `botocore.stub.Stubber`; los de infraestructura leen ficheros).
- **Cero recursos creados**: no se ha ejecutado `terraform plan` ni `apply`;
  `enable_real_resources` sigue en `false`.
- Defaults seguros intactos: `MSR_PATCH_PROVIDER=mock`, `MSR_RESTORE_PROVIDER=mock`,
  `MSR_DRY_RUN=true`.
- Sin credenciales ni secretos en el repositorio.

## 24-25. Referencias

- PR de integración: <https://github.com/nicolasgsobrino/mainframe/pull/6> (base `main`, sin merge)
- Rama: `devin/1785917443-msr-aws-phase1-1`
