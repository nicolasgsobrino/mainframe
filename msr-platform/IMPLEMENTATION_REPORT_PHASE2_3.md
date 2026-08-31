# Fase 2.3 — Comparación numérica de releases y `terraform test` con provider simulado

Corrección del fallo del primer `terraform plan` real sobre
`5157b5d470e3284918bfa94c76d10a705bf5c3f3`. No se ha ejecutado `plan` contra la cuenta ni
`apply`, no se ha llamado a AWS y no se ha creado ningún recurso.

## 1. Error observado

```
Error: Invalid operand
  on ec2.tf line 156, in resource "aws_autoscaling_group" "lab":
 156:       condition     = substr(var.source_ami_release, 0, 16) < var.candidate_releasever
```

## 2. Causa raíz

Terraform sólo admite `<`, `>`, `<=` y `>=` entre números. La expresión comparaba dos
`string`, así que la conversión implícita a número fallaba con `Invalid operand`.

`terraform validate` no lo detectó porque la comprobación de tipos de una expresión que
depende de variables de entrada se difiere a la evaluación: el error sólo aparece cuando el
precondition se evalúa realmente, es decir, durante `plan`. Por eso esta fase añade
`terraform test`, que sí evalúa la configuración (ver §5).

### Expresión anterior

```hcl
condition = substr(var.source_ami_release, 0, 16) < var.candidate_releasever
```

### Expresión corregida

`locals.tf`:

```hcl
source_ami_release_product = join(".", slice(split(".", var.source_ami_release), 0, 2))
candidate_release_product  = join(".", slice(split(".", var.candidate_releasever), 0, 2))
source_ami_release_date    = tonumber(split(".", var.source_ami_release)[2])
candidate_release_date     = tonumber(split(".", var.candidate_releasever)[2])

releases_are_amazon_linux_2023 = (
  startswith(local.source_ami_release_product, "2023.") &&
  startswith(local.candidate_release_product, "2023.")
)
ami_release_precedes_fix = (
  local.releases_are_amazon_linux_2023 &&
  local.source_ami_release_date < local.candidate_release_date
)
```

`ec2.tf`:

```hcl
condition = local.ami_release_precedes_fix
```

Con los valores reales: `20260509 < 20260706` → cierto. La comprobación es integral —ambos
productos deben ser Amazon Linux 2023 y la fecha de la AMI estrictamente anterior—, no se
compara `2023.11` con `2023.12` como texto y las validaciones de formato de
`source_ami_release`, `candidate_releasever` y `expected_fixed_kernel` se mantienen intactas.

El nuevo output `release_order` expone `source_ami_date`, `candidate_date`,
`amazon_linux_2023` y `ami_precedes_fix` para que la relación pueda auditarse y probarse.

## 3. Defecto adicional encontrado por los tests

Los `check` de `data.tf` usaban `!var.enable_real_resources || one(data.X[*].attr) == ...`.
HCL evalúa **ambos** operandos de `||`, así que con `enable_real_resources = false`
(`one(...)` sobre una lista vacía → `null`) el bloque `check "ami"` fallaba con
`Invalid function argument`. Se reescribieron como
`alltrue([for x in data.X : ...])`, que es cierto de forma vacía cuando no hay elementos.

## 4. Tests de orden temporal

`infra/terraform/tests/release_order.tftest.hcl` (provider simulado, `command = plan`):

| Caso | Resultado esperado |
| --- | --- |
| `2023.11.20260509.0` frente a `2023.12.20260706` | válido (`20260509 < 20260706`) |
| Misma fecha (`2023.12.20260706.0`) | rechazado |
| AMI posterior (`2023.12.20260801.0`) | rechazado |
| `2023.09.20261231.0` frente a `2023.10.20270105` | válido (el texto no manda) |
| `candidate_releasever = "2023.12"` | `expect_failures = [var.candidate_releasever]` |
| `source_ami_release = "20260509"` | `expect_failures = [var.source_ami_release]` |

En `backend/tests/test_infra_static.py`,
`test_no_terraform_expression_compares_strings_with_relational_operators` recorre todos los
`.tf` y prohíbe cualquier `<`/`>`/`<=`/`>=` cuyos operandos sean `var.source_ami_release`,
`var.candidate_releasever` o un `substr(...)`.

## 5. Test Terraform con provider simulado

`infra/terraform/tests/enabled_plan.tftest.hcl` usa `mock_provider "aws"` con valores
simulados para caller identity (`133789123239`), región (`eu-north-1`), VPC, subnet
(`vpc_id` coherente) y AMI (`x86_64`, `owner_id = amazon`), y ejecuta el plan con
`enable_real_resources = true`. Llega más allá del precondition que rompió el plan real y
comprueba el ASG 1/1/1, el Launch Template, los runbooks, el baseline (`approved_patches`
= `{ALAS2023-2026-1924}`) y el conteo del resumen. Un tercer `run` con una AMI posterior
espera el fallo del precondition (`expect_failures = [aws_autoscaling_group.lab]`).

No requiere credenciales: el provider está simulado y no se ejecuta ningún `apply`.

```
Success! 9 passed, 0 failed.
```

## 6. Conteo 16 frente a 18

La configuración declara **18** recursos y todos se planifican. La causa del `16` es el
propio fallo: cuando el precondition del ASG aborta, Terraform excluye ese recurso **y** el
que depende de él.

Reproducido con `terraform test -verbose` (provider simulado, sin AWS):

| Escenario | Salida |
| --- | --- |
| Configuración corregida, `enable_real_resources = true` | `Plan: 18 to add, 0 to change, 0 to destroy.` |
| Precondition del ASG en fallo (AMI posterior) | `Plan: 16 to add, 0 to change, 0 to destroy.` |

Los dos recursos ausentes en el segundo caso son:

1. `aws_autoscaling_group.lab` — el recurso cuyo precondition falla.
2. `aws_iam_role_policy.automation` — su política acota las acciones de Auto Scaling al ARN
   del ASG (`resources = [try(aws_autoscaling_group.lab[0].arn, "*")]`), así que depende de
   él y queda fuera del plan.

Es decir: el fallo interrumpió el cálculo antes de completar el plan; **ningún recurso
definido dejaba de crearse** y no se ha modificado ni añadido ningún recurso para forzar el
número. El resumen `estimated_resource_summary.resources` (18) es correcto y ahora está
verificado por el test.

## 7. CI

El job `terraform` del workflow ejecuta ahora, además de `fmt -check -recursive`,
`init -backend=false` y `validate`, un paso `terraform test`. No se han añadido credenciales
a GitHub Actions: el test usa `mock_provider`.

## 8. Resultados locales

| Comando | Resultado |
| --- | --- |
| `pytest` | **247 passed** |
| `ruff check app tests` | `All checks passed!` |
| `python -m compileall app tests` | sin errores |
| `npm ci` | OK (Node 22) |
| `npm run lint` | 0 errores (8 warnings preexistentes) |
| `npx tsc -b` | sin errores |
| `npm run build` | OK (aviso preexistente de chunk > 500 kB) |
| `terraform fmt -check -recursive` | sin diferencias |
| `terraform init -backend=false` | OK |
| `terraform validate` | `Success! The configuration is valid.` |
| `terraform test` | `Success! 9 passed, 0 failed.` |

No se ejecutó `terraform plan` contra la cuenta ni `terraform apply`.

## 9. CI y PR

Los checks del nuevo HEAD (`backend`, `frontend`, `terraform` en los eventos `push` y
`pull_request`) se verifican sobre el commit de esta fase en la PR de integración #6:
<https://github.com/nicolasgsobrino/mainframe/pull/6>.

## 10. Confirmación

- Cero llamadas a AWS: los tests de Terraform usan `mock_provider` y los de Python
  `botocore.stub.Stubber`.
- Cero recursos creados: `enable_real_resources = false` sigue siendo el valor por defecto
  y `MSR_DRY_RUN=true` con providers `mock` en el backend.
- Sin `plan` real, sin `apply`, sin merge y sin cambiar la base de la PR #6.
