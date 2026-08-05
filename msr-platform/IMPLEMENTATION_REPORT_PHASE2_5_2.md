# Fase 2.5.2 — Suspensión explícita del proceso `Launch` del ASG

Rama: `devin/1785917443-msr-aws-phase1-1` · PR #6:
<https://github.com/nicolasgsobrino/mainframe/pull/6> (sin merge, base `main`).

**Cero llamadas a AWS**: sin plan real, `apply`, `destroy`, `untaint`,
importaciones ni modificaciones del state.

## 1. Plan de recuperación observado

Sobre el state parcial, en el commit `2bab76e`:

```text
Plan: 1 to add, 4 to change, 4 to destroy.

delete,create aws_autoscaling_group.lab[0]
delete        aws_iam_instance_profile.instance[0]
delete        aws_iam_role.automation[0]
delete        aws_iam_role.instance[0]
update        aws_launch_template.lab[0]
update        aws_security_group.lab[0]
update        aws_ssm_document.patch[0]
update        aws_ssm_document.reset[0]
```

Las tres destrucciones IAM son las esperadas tras retirar el IAM propio en la
fase 2.5. Los cuatro `update` son los deseados: Launch Template con el instance
profile corporativo y el tag `PatchGroup`, y los runbooks en su versión actual.

## 2. Taint del ASG y riesgo de la sustitución

El ASG figura como **tainted**: el primer apply falló al no poder satisfacer la
capacidad (la instancia no llegó a lanzarse por la clave de tag inválida), así
que Terraform marcó el recurso como no fiable. Un recurso tainted se planifica
siempre como `delete,create`.

Esa sustitución es el riesgo principal de este plan:

- destruiría y recrearía un ASG que ya existe y es correcto salvo por la versión
  del Launch Template;
- durante la recreación el grupo intentaría lanzar una instancia inmediatamente,
  antes de cualquier verificación manual;
- la contención actual (`Launch` suspendido) se perdería, porque un grupo nuevo
  nace con todos los procesos activos.

Lo deseable es un **update in-place**, no una sustitución.

## 3. Pérdida observada de `Launch`

El estado remoto es:

```yaml
name: msr-poc-linux-patching-01-asg
desired_capacity: 1
instances: []
suspended_processes:
  - Launch
```

y el plan mostraba:

```text
suspended_processes before: ["Launch"]
suspended_processes after:  null
```

Terraform no gestionaba el atributo, así que lo interpretaba como «sin
suspensiones» y reanudaría `Launch` al aplicar. Con el grupo aún sin verificar,
el plan no podía aplicarse.

## 4. Nueva variable `asg_launch_suspended`

```hcl
variable "asg_launch_suspended" {
  type        = bool
  description = "Mantiene suspendido el proceso Launch del ASG durante una recuperación controlada."
  default     = false
}
```

y en `aws_autoscaling_group.lab`:

```hcl
suspended_processes = var.asg_launch_suspended ? ["Launch"] : []
```

Comportamiento:

| Valor | `suspended_processes` | Uso |
| --- | --- | --- |
| `false` (por defecto) | `[]` | Operación normal: el grupo lanza la instancia. |
| `true` | `["Launch"]` | Recuperación/contención temporal: no lanza nada. |

No es una lista genérica de procesos: `Launch` es el único que la variable puede
suspender, y un test lo comprueba. El valor vuelve a `false` **únicamente
mediante un plan revisado**, cuando el Launch Template, el instance profile y las
etiquetas ya estén corregidos.

## 5. Sin ocultación de drift

No se ha añadido `lifecycle { ignore_changes = [suspended_processes] }` ni
`create_before_destroy`. La suspensión forma parte del estado deseado y cualquier
divergencia aparece explícitamente en el plan. Un test estático falla si
reaparece cualquiera de las dos construcciones en el bloque del ASG.

## 6. Taint: se resuelve fuera del código

No se han añadido bloques `removed`, recursos alternativos, cambios de nombre del
ASG, importaciones, scripts de `terraform untaint` ni manipulación del state.

Estrategia posterior, manual y revisada:

1. Copia de seguridad del fichero de state.
2. `terraform untaint aws_autoscaling_group.lab[0]`.
3. Nuevo `plan` con `asg_launch_suspended = true`, verificando que el ASG pasa a
   `update` in-place (no `delete,create`), que `suspended_processes` se mantiene
   en `["Launch"]` y que las tres destrucciones IAM siguen siendo las esperadas.
4. Apply sólo tras revisar ese plan recurso a recurso.
5. Cuando Launch Template, instance profile y etiquetas estén confirmados, un
   plan posterior con `asg_launch_suspended = false` reanuda `Launch` y deja que
   el grupo lance la instancia del laboratorio.

## 7. Arquitectura intacta y recuento de diez recursos

```text
aws_security_group.lab
aws_vpc_security_group_egress_rule.https
aws_vpc_security_group_egress_rule.dns_tcp
aws_vpc_security_group_egress_rule.dns_udp
aws_launch_template.lab
aws_autoscaling_group.lab
aws_ssm_patch_baseline.lab
aws_ssm_patch_group.lab
aws_ssm_document.patch
aws_ssm_document.reset
```

Plan simulado desde cero (`terraform test`, `mock_provider "aws"`):
`Plan: 10 to add, 0 to change, 0 to destroy.` Sin recursos `aws_iam_*`.

Sin cambios en el nombre del ASG, la capacidad 1/1/1, la versión fija del Launch
Template, `PatchGroup`, `EC2SSMAgentProfileL0`, el caller context, los runbooks,
el baseline, el advisory, la AMI, el releasever, el kernel esperado, la red ni los
defaults seguros (`enable_real_resources = false`, providers `mock`,
`MSR_DRY_RUN = true`).

## 8. Tests

Terraform (`tests/enabled_plan.tftest.hcl`):

- con el valor por defecto, `suspended_processes` está vacío;
- nuevo `run "the_recovery_mode_keeps_launch_suspended"` con
  `asg_launch_suspended = true`: `suspended_processes == toset(["Launch"])` y el
  grupo sigue siendo 1/1/1;
- el plan simulado sigue enumerando diez recursos, ninguno `aws_iam_*`.

Python (`backend/tests/test_infra_static.py`):

- `asg_launch_suspended` es `bool` con `default = false`;
- el ASG usa exactamente
  `suspended_processes = var.asg_launch_suspended ? ["Launch"] : []`, y ningún
  otro proceso de Auto Scaling aparece en el bloque;
- el ASG conserva `min_size`/`max_size`/`desired_capacity` a 1 y una versión
  numérica fija del Launch Template (`latest_version`, nunca `$Latest`);
- el bloque del ASG no contiene `ignore_changes` ni `create_before_destroy`.

Nota: las aserciones sobre `launch_template[0].version`/`id` no pueden evaluarse
en `terraform test` con `command = plan` (son valores desconocidos hasta el
apply), así que la versión fija se verifica de forma estática sobre el HCL.

## 9. Resultados locales

```text
pytest                          263 passed
ruff check app tests            All checks passed!
python -m compileall app tests  OK
npm ci                          OK (Node 22, frontend/.nvmrc)
npm run lint                    0 errores
npx tsc -b                      OK
npm run build                   OK
terraform fmt -check -recursive OK
terraform init -backend=false   OK
terraform validate              Success! The configuration is valid.
terraform test                  Success! 11 passed, 0 failed.
```

## 10. Confirmaciones

- Cero llamadas a AWS y cero cambios en la cuenta o en el state.
- Sin plan real, `apply`, `destroy`, `untaint` ni importaciones.
- Sin merge, sin PR nueva y sin cambio de base.
