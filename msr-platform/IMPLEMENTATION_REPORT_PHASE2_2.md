# Fase 2.2 — Advisory vigente y releasever explícito

Corrección previa al primer `terraform plan`. No se ha ejecutado `plan` ni `apply`,
no se ha llamado a AWS y no se ha creado ningún recurso: `enable_real_resources = false`,
`MSR_PATCH_PROVIDER=mock`, `MSR_RESTORE_PROVIDER=mock` y `MSR_DRY_RUN=true` siguen siendo
los valores por defecto.

## 1. Causa del cambio de advisory

El advisory configurado hasta la fase 2.1, `ALAS2023-2026-1651`, se corrigió en la release
`2023.11.20260505` de Amazon Linux 2023. La AMI base de la PoC
(`ami-0b2ab3a97a77bd35e`, `al2023-ami-2023.11.20260509.0-kernel-6.1-x86_64`) se publicó
después, así que con toda probabilidad ya incorpora el kernel corregido: el precheck no
encontraría el advisory como aplicable y la PoC no podría demostrar un parcheo real.

### Comparación temporal

| Elemento | Release | Orden |
| --- | --- | --- |
| Corrección del advisory retirado `ALAS2023-2026-1651` | `2023.11.20260505` | anterior a la AMI ❌ |
| AMI base `ami-0b2ab3a97a77bd35e` | `2023.11.20260509.0` | base de la PoC |
| Corrección del advisory vigente `ALAS2023-2026-1924` | `2023.12.20260706` | posterior a la AMI ✅ |

La condición «AMI base anterior a la corrección» deja de ser una convención documentada y
pasa a ser un `precondition` de `aws_autoscaling_group.lab`
(`substr(var.source_ami_release, 0, 16) < var.candidate_releasever`; ambos formatos son de
anchura fija `YYYY.NN.YYYYMMDD`, así que la comparación de cadenas equivale a la
cronológica).

## 2. Valores controlados

| Valor | Variable Terraform | Variable de entorno |
| --- | --- | --- |
| `ALAS2023-2026-1924` | `candidate_advisory_id` | `MSR_PATCH_ADVISORY_ID` |
| `kernel` | `candidate_package_family` | `MSR_PATCH_PACKAGE_FAMILY` |
| `2023.12.20260706` | `candidate_releasever` | `MSR_PATCH_RELEASEVER` |
| `6.1.176-220.358.amzn2023.x86_64` | `expected_fixed_kernel` | `MSR_PATCH_EXPECTED_FIXED_KERNEL` |
| `ami-0b2ab3a97a77bd35e` | `source_ami_id` | — |
| `2023.11.20260509.0` | `source_ami_release` | — |

`candidate_releasever` se valida con `^[0-9]{4}\.[0-9]{2}\.[0-9]{8}$` (YYYY.NN.YYYYMMDD),
`expected_fixed_kernel` con el formato de kernel de Amazon Linux 2023 y `source_ami_release`
con `YYYY.NN.YYYYMMDD.N`.

Propagación: `variables.tf` → `locals.tf` (`required_backend_environment`) →
`automation-documents.tf` (`document_vars`) → runbooks → `ec2.tf` (`user_data`) →
`user-data.sh.tftpl` (`/var/lib/msr-poc/baseline.json`) → `outputs.tf`
(`candidate_advisory_id`, `candidate_releasever`, `expected_fixed_kernel`) →
`.env.example` → `Settings` → `LabTarget` → `GET /api/labs/{id}` → tipos y `LabPanel` del
frontend.

## 3. Precheck

El precheck ya no consulta el repositorio implícito de la AMI, que está fijado en su propia
release y nunca ofrecería la corrección. Ejecuta el equivalente exacto de:

```bash
dnf updateinfo list --available --advisory ALAS2023-2026-1924 --releasever 2023.12.20260706
```

y publica un contrato de pares `clave=valor` (`MSR_OS_ID`, `MSR_ADVISORY`, `MSR_RELEASEVER`,
`MSR_REPO_REACHABLE`, `MSR_ADVISORY_APPLICABLE`, `MSR_KERNEL_RUNNING`,
`MSR_KERNEL_INSTALLED`, `MSR_KERNEL_ORDER`, `MSR_HTTPD`, `MSR_HEALTH`). El paso de
verificación aborta la Automation cuando:

| Comprobación | Error |
| --- | --- |
| El sistema no es Amazon Linux 2023 | `UNSUPPORTED_OPERATING_SYSTEM` |
| El advisory/releasever no coinciden con los renderizados por Terraform | `PRECHECK_CONTRACT_MISMATCH` |
| `dnf` no puede consultar el repositorio (código de salida ≠ 0) | `PATCH_REPOSITORY_UNREACHABLE` |
| El advisory no aparece disponible | `ADVISORY_NOT_APPLICABLE` |
| El kernel en ejecución no es anterior al corregido | `KERNEL_ALREADY_FIXED` |
| `httpd` inactivo o `/health` distinto de `MSR_POC_HEALTHY` | `PRE_PATCH_HEALTH_FAILED` |

Un repositorio inaccesible produce `MSR_REPO_REACHABLE=false` y
`MSR_ADVISORY_APPLICABLE=unknown`: nunca se degrada a «advisory no aplicable».

## 4. Postcheck

Repite la misma consulta con el mismo `--releasever`. El éxito exige advisory ausente,
kernel en ejecución distinto del anterior, kernel en ejecución igual al último instalado y
kernel igual o posterior a `6.1.176-220.358.amzn2023.x86_64`, más el health check. Errores:
`PATCH_REPOSITORY_UNREACHABLE`, `ADVISORY_STILL_APPLICABLE`, `KERNEL_NOT_UPDATED`,
`KERNEL_NOT_RUNNING_LATEST`, `KERNEL_OLDER_THAN_FIXED`, `POST_PATCH_HEALTH_FAILED`.

La comparación de kernels **no es lexicográfica**: la instancia calcula
`MSR_KERNEL_ORDER ∈ {older, equal, newer}` con `sort -V`, y el runbook sólo interpreta ese
resultado. El runbook mantiene una única acción `aws:runCommand` sin outputs, que se limita
a invocar `AWS-RunPatchBaseline` con `Operation=Install` y `RebootOption=RebootIfNeeded`.

## 5. Patch baseline

`aws_ssm_patch_baseline.lab` sigue aprobando exclusivamente
`approved_patches = [var.candidate_advisory_id]` (ahora `ALAS2023-2026-1924`), sin
`approval_rules` ni comodines, con `approved_patches_enable_non_security = false` y
`rejected_patches_action = "ALLOW_AS_DEPENDENCY"`.

## 6. Reset

Tras sustituir la instancia dentro del ASG
(`TerminateInstanceInAutoScalingGroup`, `ShouldDecrementDesiredCapacity=false`), la nueva
instancia sólo se considera vulnerable cuando se cumplen **todas** estas condiciones —ya no
basta el ID ni la fecha de la AMI:

| Comprobación | Error |
| --- | --- |
| AMI no verificable desde IMDS | `RESET_AMI_UNVERIFIABLE` |
| AMI distinta de `ami-0b2ab3a97a77bd35e` | `RESET_AMI_MISMATCH` |
| Release base distinta de `2023.11.20260509.0` (leída del `baseline.json` del bootstrap) | `RESET_AMI_RELEASE_MISMATCH` |
| Repositorio no consultable con el releasever | `PATCH_REPOSITORY_UNREACHABLE` |
| `ALAS2023-2026-1924` no disponible con `--releasever 2023.12.20260706` | `RESET_TARGET_NOT_VULNERABLE` |
| Kernel no anterior al corregido (`sort -V`) | `RESET_KERNEL_NOT_VULNERABLE` |
| SSM no operativo / health check KO | pasos de espera y `RESET_HEALTH_FAILED` |

La salida del reset incluye `Advisory`, `Releasever`, `ExpectedFixedKernel` y
`RunningKernel`, además de los Instance ID antiguo y nuevo.

## 7. Backend, API y frontend

- `Settings.patch_advisory_id` → `ALAS2023-2026-1924`; nuevos `patch_releasever` y
  `patch_expected_fixed_kernel`.
- `LabTarget` persiste `candidate_releasever` y `expected_fixed_kernel` (columnas nuevas con
  migración `ALTER TABLE` para bases anteriores).
- `register_lab_target()` los toma **siempre** de la configuración: igual que el ASG, el
  payload no puede sobreescribirlos.
- `seed.build_all()` recibe advisory, releasever y kernel esperado desde `Settings`, de modo
  que la tarea track A demostrativa (`RTASK900900`, `linux-patching-01`, `sandbox`) queda
  alineada con la IaC.
- `GET /api/labs/{id}` y `POST /api/labs/{id}/validate` exponen `releasever` y
  `expected_fixed_kernel` como sólo lectura; `LabPanel` los muestra junto al advisory y al
  ASG y no ofrece ningún control para modificarlos.

## 8. Tests añadidos o actualizados

`backend/tests/test_infra_static.py`:

- `test_the_retired_advisory_is_gone_from_code_terraform_and_seeds`
- `test_the_candidate_advisory_is_the_only_one_approved`
- `test_candidate_releasever_exists_and_is_validated`
- `test_the_base_ami_release_is_older_than_the_fix`
- `test_the_releasever_reaches_the_backend_and_the_documents`
- `test_advisory_queries_always_pin_the_releasever` (ambos runbooks)
- `test_an_unreachable_repository_is_not_an_inapplicable_advisory` (ambos runbooks)
- `test_kernel_versions_are_compared_with_sort_v_not_lexicographically` (ambos runbooks)
- `test_the_postcheck_requires_the_fixed_kernel`
- `test_the_precheck_requires_amazon_linux_and_a_vulnerable_kernel`
- `test_the_reset_checks_advisory_and_kernel_not_only_the_ami`

`backend/tests/test_lab_api.py`: advisory/releasever/kernel en el snapshot,
`test_the_frontend_cannot_change_the_advisory_or_the_releasever` y payload hostil ampliado
con `advisory_id`, `releasever` y `expected_fixed_kernel`.

`backend/tests/test_lab_targets.py`: migración de bases sin las columnas nuevas y
`test_the_releasever_and_fixed_kernel_come_from_configuration`.

`backend/tests/test_aws_provider.py`:
`test_default_advisory_releasever_and_fixed_kernel_match_the_iac`, que además vuelve a
comprobar `MSR_DRY_RUN=true` y provider `mock` por defecto.

## 9. Resultados locales

| Comando | Resultado |
| --- | --- |
| `pytest` | **245 passed** |
| `ruff check app tests` | `All checks passed!` |
| `python -m compileall app tests` | sin errores |
| `npm ci` | OK (Node 22, `.nvmrc`) |
| `npm run lint` | 0 errores (8 warnings preexistentes) |
| `npx tsc -b` | sin errores |
| `npm run build` | OK (aviso preexistente de chunk > 500 kB) |
| `terraform fmt -check -recursive` | sin diferencias |
| `terraform init -backend=false` | OK |
| `terraform validate` | `Success! The configuration is valid.` |

No se ejecutó `terraform plan` ni `terraform apply`.

## 10. CI y PR

Los checks reales del nuevo HEAD (`push / backend`, `push / frontend`,
`pull_request / backend`, `pull_request / frontend`) se verifican sobre el commit de esta
fase en la PR de integración #6: <https://github.com/nicolasgsobrino/mainframe/pull/6>.

## 11. Confirmación

- Cero llamadas a AWS (los tests usan `botocore.stub.Stubber` y el laboratorio simulado).
- Cero recursos creados: `enable_real_resources = false`.
- Sin `plan`, sin `apply`, sin merge y sin cambiar la base de la PR #6.
