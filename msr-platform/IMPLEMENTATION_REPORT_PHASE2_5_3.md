# Fase 2.5.3 — Preservación de las etiquetas corporativas externas

Rama: `devin/1785917443-msr-aws-phase1-1` · PR #6:
<https://github.com/nicolasgsobrino/mainframe/pull/6> (sin merge, base `main`).

**Cero llamadas a AWS**: sin plan real, `apply`, `destroy`, `untaint`,
importaciones ni modificaciones del state. Todo lo que se describe del plan de
recuperación procede del informe aportado por el propietario.

## 1. Plan real de recuperación

Tras retirar de forma controlada el taint del ASG:

```text
Plan: 0 to add, 5 to change, 3 to destroy.
```

- **Cero reemplazos** y ninguna destrucción fuera de los tres recursos IAM
  retirados en la fase 2.5.
- El ASG queda contenido y se actualiza in-place:

```yaml
actions: [update]
desired_capacity: {before: 1, after: 1}
suspended_processes:
  before: ["Launch"]
  after:  ["Launch"]
instances: []
```

`Launch` **permanece suspendido**, que es exactamente lo que habilitó
`asg_launch_suspended` en la fase 2.5.2.

### Contenido «unknown» del runbook de reset

`aws_ssm_document.reset` muestra `content` como *unknown* porque la plantilla
interpola la nueva versión numérica del Launch Template, que no se conoce hasta
el apply. No significa que el documento quede vacío: el render local completo
tiene 541 líneas y conserva `schemaVersion: '0.3'`,
`assumeRole: '{{ AutomationAssumeRole }}'` con `default: ''`,
`EXPECTED_LT_VERSION = "<nueva versión>"` y
`TerminateInstanceInAutoScalingGroup`.

## 2. Bloqueo: etiquetas corporativas del Security Group

El único cambio inaceptable era `aws_security_group.lab[0]: update`, que
eliminaba quince etiquetas añadidas por un sistema corporativo externo:

```text
APPID              BILLINGCODE        BILLINGCONTACT
BUSINESSAREA       CMS                COUNTRY
CSCLASS            CSQUAL             CSTYPE
ENVIRONMENT        FUNCTION           GROUPCONTACT
MEMBERFIRM         PRIMARYCONTACT     SECONDARYCONTACT
```

Riesgo de eliminarlas: se pierden la imputación de costes, la titularidad y la
clasificación corporativa del recurso, el sistema externo detectaría el recurso
como no conforme y podría re-etiquetarlo o marcarlo para remediación, y cada plan
posterior volvería a intentar borrarlas.

## 3. `ignore_tags` en el provider

```hcl
provider "aws" {
  region              = var.aws_region
  allowed_account_ids = [var.aws_account_id]

  default_tags {
    tags = local.common_tags
  }

  ignore_tags {
    keys = var.externally_managed_tag_keys
  }
}
```

Se aplica globalmente a todos los recursos gestionados por el provider. No se
usan `key_prefixes` (las claves corporativas no comparten un prefijo inequívoco)
y no se ha añadido ningún recurso `aws_ec2_tag`.

Nueva variable:

```hcl
variable "externally_managed_tag_keys" {
  type    = list(string)
  default = []
  # rechaza duplicados
  # rechaza Name, PatchGroup y cualquier clave msr-*
}
```

El default vacío mantiene el módulo reutilizable fuera de esta cuenta; la lista
real se configura explícitamente en el entorno corporativo. Los **valores** de
esas etiquetas no aparecen en Terraform, ni en `local.common_tags`, ni en los
tags de recursos o del Launch Template, ni en outputs, backend o frontend.

Lista que usará el plan real de recuperación (sólo claves):

```hcl
externally_managed_tag_keys = [
  "APPID", "BILLINGCODE", "BILLINGCONTACT", "BUSINESSAREA", "CMS",
  "COUNTRY", "CSCLASS", "CSQUAL", "CSTYPE", "ENVIRONMENT", "FUNCTION",
  "GROUPCONTACT", "MEMBERFIRM", "PRIMARYCONTACT", "SECONDARYCONTACT",
]
```

## 4. Etiquetas que siguen gestionadas

```text
Name           PatchGroup        msr-poc
msr-managed-by msr-owner         msr-cost-center
msr-environment msr-lab-id       msr-resettable
```

No se ha añadido `lifecycle { ignore_changes = [tags] }` ni ninguna variante
sobre `tags`, `tags_all` o `tag_specifications`: el drift de las etiquetas
funcionales de la PoC sigue apareciendo en el plan.

## 5. Tests

Terraform (`tests/enabled_plan.tftest.hcl`):

- `["APPID", "APPID"]` falla por duplicados;
- `["Name", "PatchGroup", "msr-lab-id"]` falla por proteger las etiquetas
  funcionales;
- con las quince claves corporativas configuradas, el Launch Template conserva
  `PatchGroup` y `msr-lab-id`, y el plan sigue enumerando diez recursos.

Python (`backend/tests/test_infra_static.py`):

- el provider declara `ignore_tags { keys = var.externally_managed_tag_keys }` y
  no usa `key_prefixes`;
- la variable es `list(string)`, `default = []`, valida `distinct(...)` y rechaza
  `Name`, `PatchGroup` y `msr-*`;
- ninguna de las quince claves corporativas se declara con valor en Terraform;
- las etiquetas funcionales siguen declaradas en `locals.tf`;
- ningún fichero declara `aws_ec2_tag`;
- ningún recurso usa `ignore_changes` sobre `tags`, `tags_all` o
  `tag_specifications`;
- se mantienen los tests previos: diez recursos, ningún `aws_iam_*`,
  `asg_launch_suspended = true` → exactamente `["Launch"]`, ASG 1/1/1 y versión
  numérica fija del Launch Template.

## 6. Diez recursos, arquitectura intacta

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

Plan simulado desde cero: `Plan: 10 to add, 0 to change, 0 to destroy.`, sin
recursos `aws_iam_*`. Sin cambios en `PatchGroup`, `EC2SSMAgentProfileL0`/
`EC2SSMAgentProfile`, el caller context de Automation, las credenciales
ambientales, `asg_launch_suspended`, la capacidad 1/1/1, la versión fija del
Launch Template, los runbooks, el advisory, la AMI, el releasever, el kernel
esperado, la red ni el baseline.

## 7. Resultados locales

```text
pytest                          283 passed
ruff check app tests            All checks passed!
python -m compileall app tests  OK
npm ci                          OK (Node 22, frontend/.nvmrc)
npm run lint                    0 errores
npx tsc -b                      OK
npm run build                   OK
terraform fmt -check -recursive OK
terraform init -backend=false   OK
terraform validate              Success! The configuration is valid.
terraform test                  Success! 14 passed, 0 failed.
```

No existe ningún `terraform.tfvars` en el directorio del módulo, así que
`terraform test` se ejecuta sobre los defaults del módulo y sobre las variables
declaradas en los propios ficheros de test.

## 8. Confirmaciones

- Cero llamadas a AWS y cero cambios en la cuenta o en el state.
- Sin plan real, `apply`, `destroy`, `untaint` ni importaciones.
- Sin merge, sin PR nueva y sin cambio de base.
