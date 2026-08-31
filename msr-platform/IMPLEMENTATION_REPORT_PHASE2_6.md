# Fase 2.6 — Reconciliación automática del laboratorio (`ensure_lab_ready`)

Rama: `devin/1785917443-msr-aws-phase1-1` · PR [#6](https://github.com/nicolasgsobrino/mainframe/pull/6)

Objetivo: que un despliegue deje el laboratorio AWS listo para otra demostración de
parcheo sin pasos manuales de AWS CLI, sin fijar nunca un Instance ID y sin que ninguna
operación mutante ocurra sin configuración y autorización explícitas.

## 1. Arquitectura implementada

| Componente | Responsabilidad |
| --- | --- |
| `backend/app/labs.py` | Descubrimiento del objetivo por tags (`msr-poc=true`, `msr-lab-id=<id>`), validación de tags obligatorios, pertenencia al ASG y estado SSM. Modo mock equivalente sin AWS |
| `backend/app/precheck.py` | Evidencia de **sólo lectura**: kernel de inventario, aplicabilidad del advisory, checks de EC2 y estado `InService`/`Healthy` en el ASG |
| `backend/app/lab_lifecycle.py` | `LabLifecycleManager.ensure_lab_ready()`: contrato central de reconciliación, lock durable, correlation ID, esperas deterministas y política fail-closed |
| `backend/app/lab_hook.py` | Hook de despliegue de **ejecución única**: `python -m app.lab_hook [--confirm]` |
| `backend/app/store.py` | Proyección del estado del laboratorio a SQLite tras patch y reset, redescubrimiento independiente del reemplazo y propagación del correlation ID al job de reset |
| `backend/app/main.py` | `GET /api/labs/{id}/reconciliation`, `POST /api/labs/{id}/reconcile` y confirmación obligatoria del reset real |
| `frontend/src/components/LabPanel.tsx` | Estado `READY`/`VULNERABLE`/`PATCHED`, modo de ejecución, instancia actual y anterior, kernels, advisory, SSM, salud, IDs de ejecución de Automation, marcas de tiempo y errores |

Flujo de `ensure_lab_ready(logical_lab_id)`:

1. Adquiere el lock del laboratorio en SQLite (TTL configurable, `holder` por proceso).
2. Descubre la instancia por tags: exactamente una, `running`, en el ASG de la IaC,
   con cuenta y región permitidas y con todos los tags obligatorios.
3. Obtiene evidencia de sólo lectura y la persiste (`lab_state`, kernel, advisory, SSM,
   salud, origen de la evidencia, `last_reconciled_at`, correlation ID).
4. Si la evidencia dice *vulnerable + sana + `Online`*: **no recrea nada** y marca `READY`.
5. Si dice *parcheada*: en `aws-real` exige confirmación explícita, ejecuta
   `MSR-ResetLabInstance`, espera el estado terminal, **redescubre** el reemplazo en AWS,
   exige un Instance ID distinto, repite el precheck y exige `VULNERABLE` + `HEALTHY`.
6. Libera siempre el lock y deja el resultado consultable en la API y en la UI.

### Eliminación de `MSR_SANDBOX_INSTANCE_ID`

La variable (y `MSR_SANDBOX_LOGICAL_TARGET_ID`) desaparecen de `Settings` y de
`.env.example`. Un test comprueba que **ninguna** variable de entorno puede fijar un
Instance ID: `test_no_environment_variable_can_pin_a_lab_instance_id`. El ID persistido en
SQLite y cualquier valor enviado por el navegador nunca sustituyen al descubrimiento.

### Modos de ejecución

| Modo | Comportamiento |
| --- | --- |
| `mock` (por defecto) | Datos sintéticos, cero llamadas a AWS |
| `aws-dry-run` | Consultas de sólo lectura y validación completa; **nunca** `StartAutomationExecution` |
| `aws-real` | Recreación sólo con confirmación humana explícita y tras superar todas las validaciones |

### Fail-closed

Se falla cerrado (y se persiste el error) ante: cero objetivos, varios objetivos, tags
ausentes, cuenta o región no permitidas, instancia fuera del ASG, EC2 no `running`, SSM
offline, salud no concluyente, Automation fallida, reemplazo que nunca queda listo,
reemplazo con el mismo Instance ID y reemplazo que no vuelve a ser vulnerable. La ausencia
de evidencia de salud del ASG **no** se interpreta como salud.

### Concurrencia y arranque

- Lock durable en SQLite: una segunda reconciliación concurrente recibe `LAB_RECONCILE_LOCKED`.
- `MSR_LAB_RECONCILE_ON_STARTUP=false` por defecto: reiniciar un worker no recrea la instancia.
- Reloj (`sleep`, `monotonic`, `now`) inyectable: los tests de espera y timeout son deterministas.

## 2. Recursos AWS creados o modificados

Ninguno. Esta fase no añade, modifica ni destruye recursos: no se ejecutó `plan` real,
`apply`, `destroy`, `untaint`, importaciones ni modificaciones del state, y no se realizó
ninguna llamada a AWS. Los diez recursos Terraform y los dos runbooks siguen intactos.

## 3. Política IAM mínima del backend desplegado

Sólo lectura para descubrir y validar, más la ejecución de los dos runbooks permitidos:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DiscoverAndInspect",
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeInstances",
        "ec2:DescribeInstanceStatus",
        "autoscaling:DescribeAutoScalingGroups",
        "autoscaling:DescribeAutoScalingInstances",
        "ssm:DescribeInstanceInformation",
        "ssm:ListInventoryEntries",
        "ssm:DescribeInstancePatches",
        "ssm:DescribeInstancePatchStates",
        "ssm:DescribeDocument",
        "ssm:GetAutomationExecution",
        "ssm:DescribeAutomationStepExecutions"
      ],
      "Resource": "*"
    },
    {
      "Sid": "RunOnlyAllowlistedRunbooks",
      "Effect": "Allow",
      "Action": ["ssm:StartAutomationExecution", "ssm:StopAutomationExecution"],
      "Resource": [
        "arn:aws:ssm:eu-north-1:133789123239:automation-definition/MSR-PatchLinuxInstance:*",
        "arn:aws:ssm:eu-north-1:133789123239:automation-definition/MSR-ResetLabInstance:*"
      ]
    },
    {
      "Sid": "TrackExecutions",
      "Effect": "Allow",
      "Action": ["ssm:GetAutomationExecution", "ssm:DescribeAutomationStepExecutions"],
      "Resource": "arn:aws:ssm:eu-north-1:133789123239:automation-execution/*"
    }
  ]
}
```

Notas:

- Las acciones `Describe*` de EC2, Auto Scaling y SSM no admiten ARN de recurso: se acotan
  por cuenta y región mediante la política de confianza del rol y las allowlists del backend
  (`MSR_ALLOWED_ACCOUNT_IDS`, `MSR_ALLOWED_REGIONS`, `MSR_ALLOWED_ENVIRONMENTS`).
- No se requiere `iam:PassRole` mientras `MSR_AUTOMATION_ASSUME_ROLE_ARN` esté vacío: el
  parámetro `AutomationAssumeRole` se omite y la Automation usa el contexto de quien la inicia.
- No se requiere `sts:AssumeRole` salvo que se configure `MSR_AWS_ROLE_ARN`.

## 4. Credenciales del backend desplegado

- `MSR_AWS_ROLE_ARN` vacío → cadena estándar de credenciales de boto3 (rol de instancia,
  rol de tarea, IRSA o variables de entorno del runtime). No se llama a STS.
- `MSR_AWS_PROFILE` sólo para desarrollo local (`msr-poc`); el backend desplegado funciona
  sin `AWS_PROFILE`, sin credenciales copiadas y sin `aws login`.
- No hay claves de acceso, secretos ni tokens de sesión en configuración ni en código.

Tests: `test_deployed_backend_needs_no_aws_profile`, `test_local_development_can_use_a_profile`.

## 5. Configuración de despliegue

```bash
MSR_PATCH_PROVIDER=mock            # aws-automation sólo cuando se autorice
MSR_RESTORE_PROVIDER=mock
MSR_DRY_RUN=true
MSR_LAB_LOGICAL_ID=linux-patching-01
MSR_LAB_AUTOSCALING_GROUP_NAME=msr-poc-linux-patching-01-asg
MSR_LAB_RECONCILE_ON_STARTUP=false
MSR_LAB_RECONCILE_LOCK_TTL_SECONDS=1800
MSR_LAB_RECONCILE_TIMEOUT_SECONDS=1800
MSR_LAB_RECONCILE_POLL_INTERVAL_SECONDS=15
MSR_LAB_REPLACEMENT_TIMEOUT_SECONDS=900
```

Hook de release/despliegue (una sola vez, nunca en cada arranque de worker):

```bash
python -m app.lab_hook              # valida y deja el laboratorio listo si ya es vulnerable
python -m app.lab_hook --confirm    # autoriza la recreación real en aws-real
```

## 6. Resultado de los tests

| Comprobación | Resultado |
| --- | --- |
| `pytest` | **316 passed** |
| `ruff check app tests` | `All checks passed!` |
| `python -m compileall app tests` | sin errores |
| `npm ci` · `npm run lint` · `npx tsc -b` · `npm run build` | correctos (sólo los avisos preexistentes de `only-export-components`) |
| `terraform fmt -check -recursive` | limpio |
| `terraform init -backend=false` · `terraform validate` | `Success! The configuration is valid.` |
| `terraform test` | `Success! 14 passed, 0 failed.` |

Cobertura nueva destacada: instancia vulnerable no se recrea; instancia parcheada se
recrea; el reemplazo tiene otro Instance ID; cero y múltiples instancias; tag ausente; ASG
incorrecto; cuenta y región no permitidas; SSM offline; Automation fallida; reemplazo que
nunca queda listo; reemplazo aún parcheado; reconciliaciones concurrentes con lock durable;
el dry-run no llama a `StartAutomationExecution`; sólo se invoca el runbook permitido; el
report es una allowlist saneada; el report se persiste en el job; redescubrimiento
independiente del reemplazo; salud estricta con evidencia del ASG obligatoria; ausencia de
cualquier variable capaz de fijar un Instance ID.

## 7. Reconciliación en dry-run

Hook ejecutado localmente con los defaults seguros (`mock`, `MSR_DRY_RUN=true`), sin AWS:

```json
{
  "logical_lab_id": "linux-patching-01",
  "state": "ready",
  "action": "none",
  "ready": true,
  "execution_mode": "mock",
  "evidence": {"vulnerable_state": "vulnerable", "health_state": "healthy",
               "ssm_state": "Online", "advisory_applicable": true, "source": "mock"},
  "error_code": null
}
```

`action: none` confirma el comportamiento esperado: con el laboratorio vulnerable y sano no
se recrea nada. El modo `aws-dry-run` recorre el mismo flujo con consultas de sólo lectura y
muestra la acción prevista sin iniciar ninguna Automation.

## 8. Confirmación

- No se ejecutó ningún patch ni reset real: no hubo autorización explícita para ello.
- Cero llamadas a AWS durante la implementación y la validación (dobles de EC2, SSM y Auto
  Scaling en los tests; `mock_provider "aws"` en `terraform test`).
- Cero recursos creados, modificados o destruidos; state intacto.
- Sin merge y sin nueva Pull Request: todo el trabajo continúa en la PR #6.
