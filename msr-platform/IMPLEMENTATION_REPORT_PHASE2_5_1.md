# Fase 2.5.1 — Corrección de la interpretación de `PatchGroup` y retirada de `operator_role_arn`

Rama: `devin/1785917443-msr-aws-phase1-1` · PR #6:
<https://github.com/nicolasgsobrino/mainframe/pull/6> (sin merge, base `main`).

Corrección limitada previa al nuevo plan sobre el state parcial. **Cero llamadas
a AWS**: sin `plan`, `apply`, `destroy`, importaciones ni lectura/escritura del
state.

## 1. `PatchGroup` no rompe la asociación del baseline

La redacción anterior (`infra/terraform/patching.tf`, `infra/terraform/README.md`
e `IMPLEMENTATION_REPORT_PHASE2_5.md`) afirmaba que, al usar la clave sin
espacio, la resolución del baseline por patch group dejaba de aplicarse. **Es
incorrecto.**

Systems Manager Patch Manager reconoce dos claves **equivalentes** para
determinar el patch group de un nodo:

```text
Patch Group
PatchGroup
```

Se usa la variante sin espacio porque el Launch Template expone los tags de la
instancia por IMDS (`instance_metadata_tags = "enabled"`) y EC2 rechaza las
claves con espacio al lanzar (`'Patch Group' is not a valid tag key`, causa del
apply parcial).

La asociación se mantiene intacta:

```hcl
resource "aws_ssm_patch_group" "lab" {
  baseline_id = aws_ssm_patch_baseline.lab[0].id
  patch_group = var.patch_group        # msr-poc-linux
}
```

Una instancia etiquetada con `PatchGroup = msr-poc-linux` resuelve ese baseline
personalizado al ejecutar `AWS-RunPatchBaseline`, **no** el baseline
predeterminado del sistema operativo.

Documentos corregidos: `infra/terraform/patching.tf`,
`infra/terraform/README.md` (nueva sección «Patch group»), `README.md` y
`IMPLEMENTATION_REPORT_PHASE2_5.md`. La clave funcional **no** vuelve a
`Patch Group`.

## 2. Retirada de `operator_role_arn`

Ya no existe rol de aplicación, ni su trust policy, ni ningún `sts:AssumeRole`
del operador hacia él, así que la variable quedó sin uso. Se elimina de
`variables.tf`, del precondition de valores obligatorios de `ec2.tf` y de
`terraform.tfvars.example`. No se sustituye por ninguna otra variable.

La identidad que ejecuta Terraform y el backend procede de la cadena ambiental de
credenciales de AWS y se valida contra `aws_account_id` mediante
`data.aws_caller_identity.current` (`check "account"`) y `allowed_account_ids`
del provider. El cambio no altera ningún recurso ni genera IAM.

## 3. Recuento de recursos: sigue en diez

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
`Plan: 10 to add, 0 to change, 0 to destroy.`

Intactos: `PatchGroup` como clave, `EC2SSMAgentProfileL0`/`EC2SSMAgentProfile`,
el data source `aws_iam_instance_profile.existing`, el caller context de
Automation, las credenciales ambientales de boto3, advisory/AMI/releasever/kernel,
el ASG 1/1/1, los runbooks, `enable_real_resources = false`, los providers `mock`
y `MSR_DRY_RUN = true`. No se ha introducido ningún recurso IAM.

## 4. Tests

Terraform (`tests/enabled_plan.tftest.hcl`):

- `aws_ssm_patch_group.lab[0].patch_group == var.patch_group` y el tag
  `PatchGroup` del Launch Template valen lo mismo;
- `aws_ssm_patch_group.lab[0].baseline_id == aws_ssm_patch_baseline.lab[0].id`;
- el plan simulado sigue enumerando diez recursos, ninguno `aws_iam_*`.

Python (`backend/tests/test_infra_static.py`):

- `local.instance_tags["PatchGroup"] == var.patch_group` y el valor por defecto
  de `patch_group` sigue siendo `msr-poc-linux`;
- el patch group referencia el baseline del laboratorio;
- la clave funcional con espacio (`"Patch Group"` entrecomillada o como clave
  `Patch Group =`/`Patch Group:`) no reaparece en Terraform, user data, runbooks
  ni en el seed del backend — la documentación sí puede nombrarla, porque es una
  clave equivalente válida;
- ningún documento afirma que `PatchGroup` desactive o impida la asociación del
  baseline.

## 5. Estado de AWS

No se ha consultado ni modificado nada. El estado sigue siendo el reportado:

```yaml
asg: msr-poc-linux-patching-01-asg
desired_capacity: 1
instances: []
launch_process: suspended
```

El apply parcial y su state local se revisarán aparte desde CloudShell.

## 6. Resultados locales

```text
pytest                          261 passed
ruff check app tests            All checks passed!
python -m compileall app tests  OK
npm ci                          OK (Node 22, frontend/.nvmrc)
npm run lint                    0 errores
npx tsc -b                      OK
npm run build                   OK
terraform fmt -check -recursive OK
terraform init -backend=false   OK
terraform validate              Success! The configuration is valid.
terraform test                  Success! 10 passed, 0 failed.
```

## 7. Confirmaciones

- Cero llamadas a AWS y cero cambios adicionales en la cuenta.
- Sin `plan`, `apply`, `destroy`, importaciones ni cambios de state.
- Sin merge, sin PR nueva y sin cambio de base.
