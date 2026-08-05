# Fase 2.5 — Adaptación a las restricciones IAM reales de la cuenta

Rama: `devin/1785917443-msr-aws-phase1-1` · PR #6:
<https://github.com/nicolasgsobrino/mainframe/pull/6> (sin merge, base `main`).

Durante esta fase **no se ha realizado ninguna llamada a AWS**: ni `terraform
plan`, ni `apply`, ni `destroy`, ni lectura o escritura del state remoto. Todo lo
que se describe del estado de la cuenta procede del informe aportado por el
propietario.

## 1. Resultado del apply parcial

El `apply` ejecutado por el propietario sobre el commit `6b74819` terminó
parcialmente:

- la red, el patch baseline, el patch group y los dos runbooks se crearon;
- el Launch Template se creó, pero **el ASG no llegó a lanzar ninguna instancia**;
- las políticas y los trusts de los roles IAM propios fallaron.

Dos causas independientes:

1. **Etiqueta inválida**: `'Patch Group' is not a valid tag key`. El Launch
   Template expone los tags de la instancia por IMDS
   (`instance_metadata_tags = "enabled"`) y EC2 rechaza claves con espacio al
   lanzar.
2. **Política corporativa `DenyIAMUser`**, con `Deny` explícito sobre
   `iam:AttachRolePolicy`, `iam:PutRolePolicy` e `iam:UpdateAssumeRolePolicy`:
   los roles propios pueden existir, pero no se les puede adjuntar ninguna
   política ni fijar su trust, de modo que son inservibles.

## 2. Estado actual de la cuenta (según el informe recibido)

Recursos gestionados presentes en el state parcial:

```text
aws_autoscaling_group.lab[0]
aws_iam_instance_profile.instance[0]
aws_iam_role.automation[0]
aws_iam_role.instance[0]
aws_launch_template.lab[0]
aws_security_group.lab[0]
aws_ssm_document.patch[0]
aws_ssm_document.reset[0]
aws_ssm_patch_baseline.lab[0]
aws_ssm_patch_group.lab[0]
aws_vpc_security_group_egress_rule.dns_tcp[0]
aws_vpc_security_group_egress_rule.dns_udp[0]
aws_vpc_security_group_egress_rule.https[0]
```

- **Cero instancias EC2**: el ASG está vacío (`instances: []`).
- El ASG `msr-poc-linux-patching-01-asg` tiene `desired_capacity = 1` y el
  proceso **`Launch` suspendido**. No se ha intentado modificarlo ni reanudarlo.

## 3. Instance profile corporativo reutilizado

```text
instance_profile_name: EC2SSMAgentProfileL0
instance_profile_arn:  arn:aws:iam::133789123239:instance-profile/EC2SSMAgentProfileL0
role_name:             EC2SSMAgentProfile
role_arn:              arn:aws:iam::133789123239:role/EC2SSMAgentProfile
```

Trust: `ec2.amazonaws.com` con `sts:AssumeRole`. Permisos relevantes detectados:
`ssm:UpdateInstanceInformation`, `ssm:GetDeployablePatchSnapshotForInstance`,
`ssm:GetDocument`, `ssm:DescribeDocument`, `ssm:PutInventory`,
`ssm:PutComplianceItems`, `ssm:ListAssociations`, los cuatro canales de
`ssmmessages:*` y `ec2messages:*` — suficientes para que el agente SSM registre
la instancia y ejecute `AWS-RunPatchBaseline`.

Terraform lo consume como **data source de sólo lectura**:

```hcl
data "aws_iam_instance_profile" "existing" {
  count = local.enabled
  name  = var.existing_instance_profile_name
}
```

y el Launch Template usa `data.aws_iam_instance_profile.existing[0].arn`. No se
importa, no se etiqueta y no se modifica. El ARN nunca procede del frontend ni de
una request: sale de la configuración de Terraform.

Preconditions del Launch Template y `check "instance_profile"` de `data.tf`:

- `existing_instance_profile_name` y `existing_instance_profile_role_name` son
  obligatorios con `enable_real_resources = true`;
- el profile debe contener exactamente ese rol (`role_name`);
- su ARN debe ser `arn:aws:iam::<aws_account_id>:instance-profile/<name>`, de
  modo que pertenezca a la cuenta configurada.

## 4. Eliminación de los recursos IAM propios

Se ha borrado `infra/terraform/iam.tf` completo y con él:

```text
aws_iam_role.instance
aws_iam_role_policy_attachment.instance_ssm_core
aws_iam_role_policy.instance_boundary
aws_iam_instance_profile.instance
aws_iam_role.automation
aws_iam_role_policy.automation
aws_iam_role.application
aws_iam_role_policy.application
```

junto con los `data "aws_iam_policy_document"` y los locals que sólo construían
esos trusts y permisos (incluido `automation_trust_policy`). No se ha creado
ninguna política, rol, profile o attachment alternativo.

**No se han añadido bloques `removed`**: los recursos IAM que quedaron en el
state parcial deben aparecer como destrucciones en el próximo `plan` real, para
que la limpieza sea explícita y revisable.

## 5. Caller context para backend y Automation

- `requires_assume_role = False` en los contratos de `patch`, `rollback` y
  `reset_lab`: ninguna operación puede exigir un service role que la cuenta no
  permite crear. La comprobación de `Settings.validate_real_execution()` sigue en
  su sitio y volvería a exigir `MSR_AUTOMATION_ASSUME_ROLE_ARN` si un contrato
  futuro lo declarase obligatorio.
- `StartAutomationExecution` **omite por completo** `AutomationAssumeRole` cuando
  `MSR_AUTOMATION_ASSUME_ROLE_ARN` está vacío; nunca se envía como lista con la
  cadena vacía y nunca puede llegar desde el frontend o desde una request.
- Los runbooks conservan `assumeRole: "{{ AutomationAssumeRole }}"` con
  `default: ''` y `allowedPattern` que admite el vacío: sin rol, Automation usa
  las credenciales de la identidad iniciadora.
- `_assume_role_credentials()` devuelve `{}` sin tocar STS cuando
  `MSR_AWS_ROLE_ARN` está vacío: se mantiene la cadena estándar de boto3.
- No se ha añadido ninguna access key, secret key o session token a Terraform,
  `.env.example`, outputs, tests, GitHub Actions ni frontend.

### Limitación de seguridad

Con este modelo, el backend y la Automation heredan los permisos de la identidad
que los ejecuta. En la PoC esa identidad es administrativa, así que **se pierde
el límite de mínimo privilegio** que aportaban el rol de aplicación y el de
Automation: los guardrails que quedan son de aplicación (allowlists de cuenta,
región, entorno, tag obligatorio, runbook permitido y ASG fijado por
configuración), no de IAM. Es aceptable para una PoC en sandbox y **no** debe
trasladarse a un entorno productivo sin roles dedicados.

## 6. Etiqueta `PatchGroup`

`"Patch Group"` se ha sustituido por `"PatchGroup"` (mismo valor,
`msr-poc-linux`) en los tags del Launch Template y los propagados por el ASG,
en la documentación y en el seed del backend. Un test estático recorre todo el
Terraform (`.tf`, `.yaml`, `.tftpl`, `.example`) y `backend/app/seed.py` y falla
si reaparece la clave con espacio; los informes históricos conservan la
explicación del incidente y no son código funcional.

Consecuencia funcional: Patch Manager asocia baselines por el tag `Patch Group`,
así que la asociación automática por tag no se aplicará. El runbook invoca
`AWS-RunPatchBaseline` sobre la instancia y el baseline sigue declarado y
disponible para asociarlo explícitamente.

## 7. Scripts sin APIs AWS

Sin service role de Automation, ningún `aws:executeScript` puede llamar a AWS.
Ambos runbooks se han revisado: los scripts sólo validan y transforman sus
inputs, no importan `boto3` ni `botocore`, no crean clientes y no llaman a EC2,
SSM, IAM ni Auto Scaling. Todas las llamadas AWS usan acciones nativas
(`aws:executeAwsApi`, `aws:waitForAwsResourceProperty`, `aws:runCommand`,
`aws:changeInstanceState`) y todos los scripts mantienen `timeoutSeconds: 120`.

## 8. Recuento de recursos: 10

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

18 − 8 recursos IAM = 10. El instance profile corporativo es un data source y no
cuenta. El plan simulado desde cero (`terraform test`, `mock_provider "aws"`)
muestra `Plan: 10 to add, 0 to change, 0 to destroy.`. No se ha añadido ni
eliminado ningún recurso para cuadrar el número.

Outputs: se eliminan `application_role_arn`, `automation_role_arn` y
`automation_trust_policy`; `instance_profile_arn` devuelve el ARN del profile
existente; se añaden `instance_profile_name`, `instance_profile_role_name`,
`backend_credential_mode = "ambient-caller"` y
`automation_credential_mode = "caller-context"`; `required_backend_environment`
fija `MSR_AWS_ROLE_ARN = ""` y `MSR_AUTOMATION_ASSUME_ROLE_ARN = ""`. Ningún
output devuelve credenciales ni tokens.

## 9. Recuperación del apply parcial (documentada, no ejecutada)

El próximo `plan` real sobre el state parcial **debería** contener:

- destrucción de `aws_iam_instance_profile.instance`;
- destrucción de `aws_iam_role.instance`;
- destrucción de `aws_iam_role.automation`;
- actualización del Launch Template para usar `EC2SSMAgentProfileL0`;
- actualización de los tags a `PatchGroup`;
- actualización del ASG a la nueva versión fija del Launch Template;
- conservación de red, patch baseline, patch group y runbooks;
- **cero** instancias EC2 que destruir.

No debe asumirse que el plan real será exactamente ése: hay que revisarlo recurso
a recurso antes de aplicarlo.

> **Advertencia**: el fallo parcial pudo dejar un rol `msr-poc-application-role`
> creado **fuera** del state (sin política ni trust utilizables). No se gestiona
> ni se borra desde código; debe inspeccionarse aparte antes del siguiente apply.

## 10. Tests

Nuevos o actualizados (`backend/tests/test_infra_static.py`,
`test_fail_closed_policy.py`, `test_aws_provider.py`,
`infra/terraform/tests/enabled_plan.tftest.hcl`):

- `PatchGroup` es la clave del tag y `"Patch Group"` no aparece en Terraform,
  user data, runbooks ni código funcional;
- Terraform no declara ningún `resource "aws_iam_*"` ni ningún
  `data "aws_iam_policy_document"`, y `iam.tf` no existe;
- Terraform usa `data.aws_iam_instance_profile.existing` y el Launch Template
  consume su ARN; el data source no lleva `tags` ni ningún atributo gestionado;
- profile y rol son obligatorios en modo real (precondition + `expect_failures`);
- el plan simulado desde cero enumera 10 recursos y ninguno `aws_iam_*`;
- `patch`, `rollback` y `reset_lab` permiten caller context;
- `MSR_AUTOMATION_ASSUME_ROLE_ARN` vacío es válido en modo real y el parámetro
  `AutomationAssumeRole` se omite de `StartAutomationExecution`;
- `MSR_AWS_ROLE_ARN` vacío no llama a STS (Stubber sin respuestas registradas);
- ningún `aws:executeScript` importa `boto3`/`botocore` ni crea clientes;
- las allowlists de cuenta, región, entorno, runbook, tag y ASG siguen siendo
  obligatorias en modo real;
- `enable_real_resources = false`, providers `mock` y `MSR_DRY_RUN = true` siguen
  siendo los valores por defecto;
- no se introducen credenciales estáticas en la infraestructura.

Los tests de la trust policy del rol de Automation (`automation_trust.tftest.hcl`
y sus dos tests estáticos) se eliminan porque el rol ya no existe.

## 11. Resultados locales

```text
pytest                          254 passed
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

No se han ejecutado `terraform plan`, `terraform apply` ni `terraform destroy`.

## 12. CI y commit

- Commit: ver la sección final de esta PR (`git log -1` de la rama).
- CI del nuevo HEAD: `push`/`pull_request` × `backend`, `frontend`, `terraform`.

## 13. Confirmaciones

- **Cero llamadas a AWS** durante toda la fase.
- **Cero cambios adicionales** en la cuenta: no se ha tocado el ASG, ni el
  proceso `Launch` suspendido, ni el instance profile corporativo, ni el state.
- Se mantienen `MSR_PATCH_PROVIDER=mock`, `MSR_RESTORE_PROVIDER=mock`,
  `MSR_DRY_RUN=true` y `enable_real_resources=false`.
- Sin merge, sin PR nueva y sin cambio de base.
