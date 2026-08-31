# Fase 1.1 — Corrección de los bloqueos de la revisión técnica

Continuación de [`IMPLEMENTATION_REPORT_PHASE1.md`](IMPLEMENTATION_REPORT_PHASE1.md). Todo el
cambio queda dentro de `msr-platform/`. **No se ha ejecutado ninguna operación mutativa en
AWS**: `MSR_PATCH_PROVIDER=mock` y `MSR_DRY_RUN=true` siguen siendo los valores por defecto y
los tests inyectan clientes `botocore.stub.Stubber` (nunca una cuenta real).

## 1. Correcciones realizadas

| # | Bloqueo de la revisión | Corrección |
|---|------------------------|------------|
| 1 | El provider aceptaba `AWS-RunPatchBaseline` (documento `Command`) en `StartAutomationExecution` | Contrato explícito de runbooks (`backend/app/runbooks.py`), `describe_document` obligatorio y rechazo de documentos `Command` conocidos antes de cualquier llamada |
| 2 | Cualquier track podía ir a AWS | Sólo track A; B y C fallan con `UNSUPPORTED_REMEDIATION_TRACK` sin tocar AWS y sin inventar versión corregida |
| 3 | Un job AWS podía representar varios activos del anillo | Resolución previa de los activos del anillo y exigencia de **exactamente una** instancia real (`422 RING_TARGET_COUNT_UNSUPPORTED`); la evidencia sólo registra la instancia ejecutada |
| 4 | El timeout local liberaba el lock y marcaba `cancelled` | Estados no confirmados, re-consulta de `GetAutomationExecution`, `StopAutomationExecution` y lock retenido |
| 5 | El pipeline funcional vivía sólo en memoria | `Store.rehydrate_pipeline_state()` reconstruye el estado desde SQLite al arrancar |
| 6 | Los jobs sólo avanzaban si el frontend hacía polling | Reconciliador periódico en proceso, gobernado por el *lifespan* de FastAPI |
| 7 | `MSR_AWS_ROLE_ARN` estaba en el contrato pero no se usaba | STS `AssumeRole` real con credenciales temporales y clientes inyectables |
| 8 | Una allowlist vacía equivalía a «permitir todo» | Política *fail-closed* en modo real (`MSR_DRY_RUN=false`) |
| 9 | No existía modelo del laboratorio reutilizable | `LabTarget` persistente y distinción `rollback` / `reset_lab` |
| 10 | `DescribeAutomationStepExecutions` fallaba en silencio | Aviso sanitizado y clasificado, conservando el estado de `GetAutomationExecution` |

## 2. Nuevo contrato de runbooks

`backend/app/runbooks.py` define un `RunbookContract` por operación:

| Operación | Runbook por defecto (configurable) | Tipo | Parámetros obligatorios | Opcionales | Prohibidos | Tracks | SO |
|-----------|-----------------------------------|------|-------------------------|-----------|-----------|--------|----|
| `patch` | `MSR-PatchLinuxInstance` (`MSR_PATCH_RUNBOOK_NAME`) | `Automation` | `InstanceId` | `AutomationAssumeRole`, `RebootOption` | los comunes + `TargetVersion`, `SnapshotId` | `A` | `linux` |
| `rollback` | `MSR-RollbackLinuxInstance` (`MSR_ROLLBACK_RUNBOOK_NAME`) | `Automation` | `InstanceId` | `AutomationAssumeRole`, `TargetVersion`, `SnapshotId` | los comunes | `A` | `linux` |
| `reset_lab` | `MSR-ResetLabInstance` (`MSR_RESET_RUNBOOK_NAME`) | `Automation` | `LogicalLabId` | `AutomationAssumeRole`, `LaunchTemplateId`, `LaunchTemplateVersion`, `VulnerableAmiId` | los comunes | `A` | `linux` |

Parámetros prohibidos comunes a todos los contratos (vías habituales de inyección de comandos):
`Commands`, `Command`, `Script`, `SourceInfo`, `Parameters`, `DocumentName`, `Operation`,
`InstallOverrideList`. El contrato de `reset_lab` está declarado pero marcado como no
implementado (`implemented=False`).

Reglas aplicadas:

- `resolve_runbook()` rechaza los documentos `Command` conocidos (`AWS-RunPatchBaseline`,
  `AWS-RunShellScript`, …) **antes** de cualquier llamada a AWS;
- antes de arrancar (también en dry-run) se llama a `ssm.describe_document(Name=...)` y se
  exige `DocumentType == "Automation"`, allowlist de política y correspondencia con la
  operación solicitada;
- `validate_parameters()` rechaza parámetros prohibidos, no declarados y obligatorios ausentes;
- los parámetros se derivan del contrato: **no** se envía `Operation=Install` automáticamente y
  `TargetVersion`/`SnapshotId` sólo se envían si el runbook los declara;
- el frontend no puede elegir runbook ni parámetros.

El runbook propio de parcheo es de tipo `Automation` y puede invocar internamente
`AWS-RunPatchBaseline` con `aws:runCommand`; esa composición vive en el documento SSM, no en
la aplicación.

## 3. Estados y reglas de timeout

Estados añadidos a `JobState` (ninguno es terminal):

| Estado | Significado |
|--------|-------------|
| `timeout_pending_confirmation` | Se agotó `MSR_JOB_TIMEOUT_SECONDS` en local; la ejecución remota puede seguir viva |
| `stop_requested` | Se ha pedido `StopAutomationExecution` y se espera confirmación de AWS |
| `remote_status_unknown` | No se pudo obtener el estado remoto; requiere reconciliación administrativa |

Reglas:

1. un timeout local **no** libera el lock del objetivo ni marca el job como `cancelled`;
2. se vuelve a consultar `GetAutomationExecution`;
3. si es posible se solicita `StopAutomationExecution` (`stop_requested`);
4. el job sólo se cierra cuando AWS confirma un estado terminal;
5. mientras el estado no esté confirmado, `active_job_for_target()` sigue devolviendo el job y
   cualquier nueva operación sobre el mismo objetivo responde `409`;
6. `POST /api/patch-jobs/{job_id}/admin-resolve` permite el cierre manual, exige que el job
   esté en un estado no confirmado (`422 JOB_NOT_UNCONFIRMED` en caso contrario) y deja un
   evento de auditoría con actor y nota;
7. el mock, que no tiene ejecución remota, mantiene el `timed_out` terminal de la fase 1.

## 4. Estrategia de rehidratación

`Store.rehydrate_pipeline_state()` se ejecuta al construir el `Store` y en el *lifespan* de
FastAPI. Por cada tarea con jobs persistidos:

- descarta la proyección en memoria (`_reset_projection`) para no depender del `rings_done`
  aleatorio inicial de la demo;
- reproduce en orden cronológico los jobs terminales (`succeeded` → anillo completado,
  `restored` → anillo restaurado) con `persist=False`, sin reescribir el histórico;
- reconstruye evidencia, eventos, artefactos de despliegue, estado de la tarea y del
  Vulnerable Item;
- deja disponible el job activo (incluidos los estados no confirmados) leyéndolo de SQLite.

Se distingue el **resultado persistido** del job (`result_payload`, fuente de verdad) de su
**proyección** en el `Store` (conjunto `_projected`, sólo memoria): `outcome_applied` marca que
el resultado ya se proyectó en la instancia actual, pero la rehidratación limpia el marcador de
proyección, por lo que reiniciar el backend reconstruye el estado. La operación es idempotente:
ejecutarla varias veces no duplica anillos, evidencias ni logs.

## 5. Reconciliador periódico

`backend/app/reconciler.py` (`JobReconciler`):

- tarea `asyncio` cancelable, arrancada y detenida por el *lifespan* de FastAPI;
- cada `MSR_RECONCILER_INTERVAL_SECONDS` (10 s por defecto) lee **de SQLite** los jobs activos
  y llama a `provider.poll()`, persistiendo el resultado;
- no crea ejecuciones nuevas ni ejecuta parches: AWS sigue siendo el ejecutor duradero;
- no depende de estado en memoria, por lo que tolera reinicios del backend;
- un lock por `job_id` en el `Store` evita polling concurrente del mismo job entre el
  reconciliador y el polling del frontend;
- se puede desactivar con `MSR_RECONCILER_ENABLED=false`;
- su estado (`enabled`, `running`, `ticks`, `last_reconciled`, `last_error`) se expone en
  `GET /api/execution` y en la UI.

No se han introducido Celery, RQ, `BackgroundTasks`, WebSocket ni SSE.

## 6. Funcionamiento de `AssumeRole`

Cuando `MSR_AWS_ROLE_ARN` está configurado, el provider AWS:

- llama a `sts.assume_role(RoleArn=..., RoleSessionName=..., DurationSeconds=3600)`;
- construye los clientes EC2 y SSM con las credenciales temporales devueltas;
- usa un `RoleSessionName` derivado del correlation ID y sanitizado (`[^\w+=,.@-] → -`,
  truncado a 64 caracteres);
- **no registra ni persiste** las credenciales temporales (ni en logs ni en eventos);
- crea la sesión por operación, de modo que la expiración no deja clientes inservibles;
- ignora `MSR_AWS_PROFILE` cuando se asume un rol, para no mezclar identidades.

Sin `MSR_AWS_ROLE_ARN` se usa la cadena estándar de credenciales de boto3. Los clientes SSM,
EC2 y STS son inyectables, que es como los tests los sustituyen por `Stubber`.

## 7. Política fail-closed

`Settings.validate_real_execution()` se ejecuta al arrancar cuando
`MSR_PATCH_PROVIDER=aws-automation` (o el de restauración) y `MSR_DRY_RUN=false`, y exige:

`MSR_AWS_REGION`, `MSR_ALLOWED_ACCOUNT_IDS`, `MSR_ALLOWED_REGIONS`,
`MSR_ALLOWED_ENVIRONMENTS`, `MSR_REQUIRED_TARGET_TAG_KEY`, `MSR_REQUIRED_TARGET_TAG_VALUE`,
`MSR_ALLOWED_RUNBOOKS`, el nombre del runbook de la operación,
`MSR_AUTOMATION_ASSUME_ROLE_ARN` cuando el contrato del runbook lo requiere, y
`MSR_SANDBOX_INSTANCE_ID` o `MSR_SANDBOX_LOGICAL_TARGET_ID` resoluble.

En ejecución se exige además track A y exactamente un target real. Una lista vacía nunca
significa «permitir todo» en modo real. El modo relajado sólo existe para `mock` y dry-run y se
identifica explícitamente: `GET /api/execution` devuelve `mode` (`mock` | `aws-dry-run` |
`aws-real`) y `strict_policy`, y la UI muestra el modo y el aviso de que en dry-run el parche
no se ha aplicado.

## 8. Modelo `LabTarget`

`backend/app/lab.py` + tabla `lab_targets` en SQLite, con
`logical_lab_id`, `current_instance_id`, `account_id`, `region`, `vulnerable_ami_id`,
`launch_template_id`, `launch_template_version`, `expected_vulnerable_package`,
`expected_vulnerable_version`, `required_tags`, `last_reset_job_id`, `updated_at`.

- `rollback`: recuperación de una ejecución de parcheo fallida sobre la instancia existente;
- `reset_lab`: recreación deliberada de la instancia vulnerable para repetir la PoC. Registra
  el job y actualiza `last_reset_job_id`, pero **no destruye ni recrea ninguna EC2** en esta
  fase;
- `lab_targets` es configuración, no histórico: sobrevive a `POST /api/reset`;
- endpoints `GET/POST /api/lab-targets` y `GET /api/lab-targets/{logical_lab_id}`;
  los `instance_id` sintéticos de la CMDB se rechazan con `LAB_TARGET_INVALID`.

## 9. Observabilidad y errores

- `classify_error()` distingue `PERMISSION_DENIED`, `THROTTLED` y `TRANSIENT_FAILURE` a partir
  del código de `botocore`;
- si falla `describe_automation_step_executions`, la excepción no se oculta: se conserva el
  estado obtenido con `GetAutomationExecution` y se añade un aviso sanitizado
  (`warning_code`/`warning_message`) que queda como evento del job;
- los outputs de los pasos se sanitizan y truncan a `MSR_MAX_OUTPUT_CHARS` antes de
  persistirse; no se persiste ningún output completo sin sanitizar;
- todos los eventos conservan el correlation ID del job.

## 10. Tests añadidos

136 tests en total (fase 1: 80). Nuevos o reescritos:

| Archivo | Tests | Cubre |
|---------|-------|-------|
| `tests/test_aws_provider.py` | 30 | `describe_document`, rechazo de documentos `Command`, aceptación de `Automation`, parámetro no declarado, obligatorio ausente, `AWS-RunPatchBaseline` no puede iniciar `StartAutomationExecution`, `AssumeRole` con `Stubber`, avisos de steps, ausencia del comodín de `botocore.stub` para parámetros críticos |
| `tests/test_aws_target_semantics.py` | 8 | cero / varios / exactamente un target real, rechazo de tracks B, C, vacío y `None`, no se invoca el provider en tracks no permitidos, no se inventa versión corregida |
| `tests/test_timeout_safety.py` | 6 | el lock sigue tomado tras el timeout, se re-consulta la ejecución, `stop` no produce `cancelled` inmediato, estado remoto desconocido bloquea el target, cierre con estado terminal remoto, reconciliación administrativa auditada |
| `tests/test_rehydration.py` | 5 | el pipeline sobrevive a destruir y recrear el `Store` sobre la misma SQLite, idempotencia, `outcome_applied` no impide el replay, el reconciliador avanza jobs y se detiene limpiamente, el reconciliador desactivado no corre |
| `tests/test_fail_closed_policy.py` | 12 | defaults mock/dry-run, política real completa aceptada, allowlist vacía rechazada, cada requisito ausente bloquea la ejecución real, dry-run relajado pero identificado |
| `tests/test_lab_targets.py` | 7 | persistencia del `LabTarget`, rechazo de instancia sintética, `reset_lab` ≠ `rollback`, la configuración sobrevive al reset del histórico |
| `tests/test_api.py` | 13 | contrato de `/api/execution` (`mode`, `strict_policy`, `reconciler`), endpoints de `LabTarget`, `admin-resolve` sobre job confirmado |
| `tests/test_policy.py` | 14 | `AWS-RunPatchBaseline` fuera de la allowlist de Automation |
| `tests/fakes.py` | — | provider falso con el nombre del adaptador AWS para ejercitar el plano de control sin boto3 |

Ningún test contacta con AWS: todo es `Stubber` o dobles inyectados.

## 11. Resultado de las validaciones

Ejecutadas en `msr-platform/` (backend con el venv activado, frontend con `npm`):

| Comando | Resultado |
|---------|-----------|
| `pytest` | `136 passed in 2.39s` |
| `ruff check` | `All checks passed!` |
| `python -m compileall backend/app backend/tests` | sin errores (salida vacía, exit 0) |
| `npm run lint` | 0 errores; 8 warnings preexistentes `react(only-export-components)` en `src/ui.tsx` y `src/view.tsx` |
| `npx tsc -b` | sin errores (exit 0) |
| `npm run build` | `✓ built in 4.40s`; aviso preexistente de chunk > 500 kB (`index-*.js` 831 kB) |

## 12. Limitaciones restantes

- los runbooks `MSR-*` **no existen todavía en la cuenta**: hay que crearlos como documentos
  `Automation` antes de cualquier prueba real (la aplicación fallará en `describe_document`);
- el dry-run valida política, documento y parámetros, pero no ejecuta `StartAutomationExecution`;
- `reset_lab` es sólo modelo y contabilidad: no lanza ni destruye instancias EC2;
- el reconciliador es en proceso y de instancia única: no hay coordinación entre varias réplicas
  del backend (bastaría un lock en SQLite o un scheduler externo);
- un job AWS sigue limitado a una instancia; el multiactivo real requiere otra fase;
- la CMDB continúa siendo sintética: sólo la instancia de sandbox tiene `instance_id` real;
- sigue sin haber autenticación de usuarios en la API;
- la rehidratación reconstruye anillos, evidencia y estado, pero no los artefactos sintéticos de
  las fases 1-5, que se regeneran de forma determinista;
- no hay métricas ni traza distribuida; la observabilidad son eventos de job y logs.

## 13. Información AWS necesaria para la fase 2

Del propietario de la cuenta:

1. **Cuenta y región** de sandbox (`MSR_ALLOWED_ACCOUNT_IDS`, `MSR_AWS_REGION`).
2. **Instance ID** de la EC2 Linux vulnerable (`i-…`), su entorno y su etiquetado
   (`msr-poc=true`), más el `logical_target_id` del CI con el que se corresponde.
3. Confirmación de que la instancia está **gestionada por SSM** (agente activo, rol de
   instancia con `AmazonSSMManagedInstanceCore`, salida a los endpoints de SSM).
4. **Rol de ejecución del control plane** (`MSR_AWS_ROLE_ARN`) y su relación de confianza con la
   identidad que ejecuta el backend, con permisos mínimos:
   `ssm:DescribeDocument`, `ssm:StartAutomationExecution`, `ssm:GetAutomationExecution`,
   `ssm:StopAutomationExecution`, `ssm:DescribeAutomationStepExecutions`,
   `ssm:DescribeInstanceInformation`, `ec2:DescribeInstances`, `ec2:DescribeTags`.
5. **Rol de Automation** (`MSR_AUTOMATION_ASSUME_ROLE_ARN`) que el runbook asume para ejecutar
   `aws:runCommand` sobre la instancia.
6. Los **documentos `Automation`** `MSR-PatchLinuxInstance`, `MSR-RollbackLinuxInstance` y
   `MSR-ResetLabInstance`: quién los crea, su esquema de parámetros definitivo y si se versionan
   en este repositorio o en el de infraestructura.
7. Política de **reinicio** de la instancia y ventana de mantenimiento aceptable.
8. Estrategia de **rollback** real: snapshot EBS previo, AMI, o downgrade de paquete; qué debe
   recibir `SnapshotId`/`TargetVersion`.
9. Para `reset_lab`: **AMI vulnerable** y/o *launch template* (id y versión), y si se autoriza
   terminar y recrear la instancia.
10. Paquete y versión vulnerables esperados, para poder verificar el post-parcheo con evidencia
    real en lugar de la versión sintética.
11. Destino de logs y evidencias (CloudWatch Logs, S3) y periodo de retención exigido.
12. Confirmación explícita del momento en el que se autoriza pasar `MSR_DRY_RUN=false`.
