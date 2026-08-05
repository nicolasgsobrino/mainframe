# Fase 1 — Base técnica para el parcheo real en AWS

## 1. Resumen

Esta fase sustituye la mutación síncrona en memoria del despliegue por un **job durable,
idempotente y auditable**, y extrae la ejecución del parcheo detrás de un **contrato de
provider** con dos implementaciones: el mock existente (por defecto) y un adaptador real de
**AWS Systems Manager Automation** (desactivado por defecto).

Lo que **no** cambia: las fases 1–5 siguen siendo síncronas y devuelven `200`; el mock sigue
siendo el provider por defecto y no se ha eliminado; los artefactos que consume el frontend
mantienen su estructura; no se ejecuta ninguna operación mutativa real en AWS sin
configuración explícita.

Lo que sí cambia:

- La aprobación del anillo (fase 6) crea un job persistido en SQLite y responde `202`.
- El progreso (`rings_done`) se incrementa **una sola vez**, y sólo cuando el job alcanza
  `succeeded`. Un dry-run o un fallo nunca cuentan como parche aplicado.
- Un objetivo no puede tener dos jobs mutativos simultáneos (lock en base de datos).
- El estado se reconcilia con `provider.poll()`; el frontend hace polling y se recupera tras
  un reload o un reinicio del backend.

## 2. Diagrama

```
Frontend (TaskDetail)                Backend (FastAPI)                    Provider
──────────────────────               ─────────────────────                ────────────────
POST /approve  ────────────────────▶  store.approve_phase
  Idempotency-Key                      ├─ repo.get_job_by_idempotency_key ─┐ (replay)
                                       ├─ policy/provider.validate_target ─▶ validate_target()
                                       ├─ repo.create_job (BEGIN IMMEDIATE, lock por target)
                                       └─ provider.start(request, key) ────▶ start()
   ◀──── 202 TaskDetail(active_job)                                          │
                                                                             │
GET /tasks/{id}  (cada 2 s) ───────▶  store.task_detail
                                       └─ reconcile_job ──────────────────▶ poll()
                                            ├─ pasos + estado + eventos
                                            └─ succeeded ⇒ rings_done += 1 (una vez)
   ◀──── TaskDetail(active_job|jobs)
POST /patch-jobs/{id}/cancel ──────▶  store.cancel_job ───────────────────▶ cancel()
```

No hay colas, workers, `BackgroundTasks`, WebSocket ni SSE: el avance se produce en las
consultas de lectura, y la duración real de la operación AWS vive en Systems Manager.

## 3. Ficheros creados

| Fichero | Contenido |
|---------|-----------|
| `backend/app/config.py` | `Settings` (`pydantic-settings`, prefijo `MSR_`), validación por provider, `effective_dry_run`, ruta absoluta de la BD |
| `backend/app/errors.py` | `DomainError` y subclases (`NotFound`, `Conflict`, `Validation`, `TargetNotAllowed`, `DependencyUnavailable`) con `correlation_id` |
| `backend/app/jobs.py` | `JobType`, `JobState`, transiciones permitidas, `PatchJob`, `JobEvent` |
| `backend/app/repository.py` | Persistencia SQLite: jobs, targets con lock, eventos e idempotencia |
| `backend/app/policy.py` | Allowlists, validación de objetivo, `redact`/`sanitize_text`, validación de runbooks y parámetros |
| `backend/app/providers/base.py` | `Target`, `PatchRequest`, `RestoreRequest`, `ExecutionStep`, `PatchExecution`, `RestoreExecution`, `TargetPolicyResult`, `ProviderError`, protocolos `PatchProvider`/`RestoreProvider` |
| `backend/app/providers/mock_patch.py` | Simulación determinista del parcheo (incluye `build_ring_actions`) |
| `backend/app/providers/mock_restore.py` | Simulación determinista de la restauración (incluye `build_rollback_plan`) |
| `backend/app/providers/aws_ssm_automation.py` | Adaptador real de SSM Automation (patch y restore) |
| `backend/app/providers/__init__.py` | Factoría única: `get_patch_provider` / `get_restore_provider` |
| `backend/pyproject.toml` | Configuración de Ruff y pytest |
| `backend/requirements-dev.txt` | pytest, httpx, ruff |
| `backend/policy/allowlist.example.yaml` | Ejemplo documentado de allowlist de cuentas, regiones y runbooks |
| `backend/tests/*` | 80 tests: contratos, estados, persistencia, política, store, API y AWS con `Stubber` |
| `.env.example` | Todas las variables `MSR_*`, sin valores reales |
| `IMPLEMENTATION_REPORT_PHASE1.md` | Este documento |

## 4. Ficheros modificados

| Fichero | Cambio |
|---------|--------|
| `backend/app/store.py` | Recibe settings, repositorio y providers; crea y reconcilia jobs; expone `active_job`, `jobs` y `execution`; rollback diferido al éxito del restore |
| `backend/app/engine.py` | `build_ring_actions` / `build_rollback_plan` pasan a ser wrappers de compatibilidad sobre los mocks; `build_deployment` preserva evidencia previa y refleja el job activo |
| `backend/app/seed.py` | Los activos incorporan campos de objetivo (`logical_target_id`, `instance_id`, `account_id`, `region`, `tags`, `ssm_managed`, `os`) |
| `backend/app/main.py` | Manejador uniforme de `DomainError`, CORS sin comodín, `202` en despliegue, `Idempotency-Key` y endpoints de jobs |
| `backend/requirements.txt` | `pydantic-settings` y `boto3` (import perezoso) |
| `frontend/src/types.ts` | `PatchJob`, `JobEvent`, `JobStep`, `JobTarget`, `ExecutionConfig`, `ApiErrorBody`, campos de objetivo en `CI` |
| `frontend/src/api.ts` | `ApiError` con `code`/`correlation_id`, claves de idempotencia por acción y cliente de jobs |
| `frontend/src/pages/TaskDetail.tsx` | Polling del job, panel de ejecución, bloqueo de acciones mutativas, `try/catch/finally` y banner de error |
| `frontend/src/pages/Cmdb.tsx` | Columna "Objetivo de parcheo": instancia, región y si el nodo está gestionado por SSM |
| `.gitignore` | Excluye `.env`, la BD de jobs y cachés |

## 5. Esquema SQLite

```sql
jobs(id PK, job_type, task_id, ring_number, provider, provider_reference, state,
     dry_run, correlation_id, created_at, updated_at, started_at, completed_at,
     error_code, error_message, idempotency_key, request_payload, result_payload)

job_targets(id PK, job_id → jobs.id, logical_target_id, instance_id, payload, active)
  UNIQUE(logical_target_id) WHERE active = 1
  UNIQUE(instance_id)       WHERE active = 1 AND instance_id IS NOT NULL

job_events(id PK, job_id → jobs.id, state, message, actor, created_at)

idempotency_keys(key PK, job_id → jobs.id, scope, created_at)
```

- El `id` del job es interno (`job-…`); el identificador de AWS vive en
  `provider_reference` (`AutomationExecutionId`).
- Los índices parciales son el lock: mientras un job siga activo su fila `job_targets`
  mantiene `active = 1`, y cualquier segundo intento sobre el mismo objetivo falla en la
  transacción (`BEGIN IMMEDIATE`) y se traduce a `409`.
- El lock se libera **sólo** al alcanzar un estado terminal.
- `request_payload` / `result_payload` guardan datos controlados y saneados; no se
  persisten credenciales ni salidas de comandos sin truncar.

## 6. Máquina de estados

```
queued ─▶ validating ─┬─▶ dry_run ─▶ succeeded
                      ├─▶ starting ─▶ running ─▶ verifying ─▶ succeeded
                      ├─▶ failed | timed_out | cancelling ─▶ cancelled
restore_queued ─▶ restoring ─▶ restored | restore_failed
```

Terminales: `succeeded`, `failed`, `cancelled`, `restored`, `restore_failed`, `timed_out`.
Las transiciones se validan explícitamente (`assert_transition`); una transición ilegal es
un error de programación, no un estado silencioso. Todos los timestamps son UTC reales
(`datetime.now(timezone.utc)`), nunca la fecha sintética del generador de datos.

## 7. Contrato de providers

```python
class PatchProvider(Protocol):
    name: str
    def validate_target(self, request: PatchRequest) -> TargetPolicyResult: ...
    def start(self, request: PatchRequest, idempotency_key: str) -> PatchExecution: ...
    def poll(self, provider_reference: str) -> PatchExecution: ...
    def cancel(self, provider_reference: str) -> PatchExecution: ...
```

`RestoreProvider` es simétrico sobre `RestoreRequest` / `RestoreExecution`. La selección se
centraliza en `providers.get_patch_provider(settings)` y `get_restore_provider(settings)`:
ni `store.py`, ni `main.py`, ni `engine.py` deciden qué provider se usa.

## 8. Mock asíncrono

- `MockPatchProvider.start()` no bloquea ni duerme: registra un inicio y devuelve una
  referencia `mock-patch:<job-id>:<timestamp>`.
- `poll()` deriva el estado del tiempo transcurrido (`MSR_MOCK_JOB_DURATION_SECONDS`), de
  forma que existe al menos un estado no terminal observable (`running`) antes del éxito.
- Los pasos y salidas son deterministas y conservan la estructura que ya consumía el
  frontend, por lo que la demo se comporta igual que antes salvo por el progreso visible.
- Con `dry_run` el mock ejecuta la simulación completa (no hay recurso real que proteger),
  pero el job se marca como dry-run y **no** incrementa el progreso.

## 9. AWS dry-run

Con `MSR_PATCH_PROVIDER=aws-automation` y `MSR_DRY_RUN=true`:

1. Se resuelve el objetivo y se ejecutan **sólo** llamadas de lectura:
   `DescribeInstances` y `DescribeInstanceInformation`.
2. Se comprueban: formato real de Instance ID (`i-…`, se rechazan IDs sintéticos como
   `SRV-1001`), cuenta y región allowlisted, tag obligatorio
   (`MSR_REQUIRED_TARGET_TAG_KEY`/`VALUE`), estado de la instancia (se rechazan
   `terminated`/`shutting-down`/`stopped`) y que sea un nodo gestionado por SSM.
3. Se valida que el runbook esté configurado y en la allowlist, y que los parámetros no
   contengan shell libre. El frontend nunca envía runbooks ni comandos.
4. **No** se invoca `StartAutomationExecution`: el job termina en `dry_run` con el plan que
   se habría ejecutado, y la UI lo etiqueta como "el parche NO se ha aplicado".

En ejecución real se persiste el `AutomationExecutionId`, se envían tags de correlación, el
`ClientToken` se deriva de la clave de idempotencia, las salidas se sanean y truncan
(`MSR_MAX_OUTPUT_CHARS`), los estados AWS desconocidos se tratan como `running`, y la
cancelación (`StopAutomationExecution`) sólo se refleja localmente cuando AWS lo confirma en
el siguiente `poll()`. `boto3` se importa de forma perezosa y los clientes son inyectables
para poder probarlos con `botocore.stub.Stubber`.

## 10. Variables de entorno

Todas con prefijo `MSR_` (ver `.env.example`). Ninguna contiene credenciales: AWS se resuelve
por la cadena estándar del SDK (perfil, rol o entorno de ejecución).

| Variable | Defecto | Propósito |
|----------|---------|-----------|
| `MSR_PATCH_PROVIDER` | `mock` | `mock` o `aws-automation` |
| `MSR_RESTORE_PROVIDER` | `mock` | idem, para restauración |
| `MSR_DRY_RUN` | `true` | Evita cualquier llamada mutativa a AWS |
| `MSR_JOBS_DB_PATH` | `./data/msr_jobs.db` | SQLite de jobs |
| `MSR_AWS_REGION` / `MSR_AWS_PROFILE` / `MSR_AWS_ROLE_ARN` / `MSR_AWS_ENDPOINT_URL` | vacío | Sesión AWS |
| `MSR_PATCH_RUNBOOK_NAME` / `MSR_RESET_RUNBOOK_NAME` | vacío | Runbooks de Automation |
| `MSR_AUTOMATION_ASSUME_ROLE_ARN` | vacío | `AutomationAssumeRole` |
| `MSR_SANDBOX_INSTANCE_ID` / `MSR_SANDBOX_LOGICAL_TARGET_ID` | vacío | Única EC2 de pruebas y su CI |
| `MSR_ALLOWED_ACCOUNT_IDS` / `MSR_ALLOWED_REGIONS` / `MSR_ALLOWED_ENVIRONMENTS` | vacío | Allowlists |
| `MSR_ALLOWED_RUNBOOKS` | dos runbooks de patching | Allowlist de documentos SSM |
| `MSR_REQUIRED_TARGET_TAG_KEY` / `_VALUE` | `msr-poc` / `true` | Tag obligatorio del objetivo |
| `MSR_JOB_POLL_INTERVAL_SECONDS` | `2` | Intervalo de polling (backend y UI) |
| `MSR_JOB_TIMEOUT_SECONDS` | `1800` | Timeout del job (`timed_out`) |
| `MSR_MOCK_JOB_DURATION_SECONDS` / `MSR_MOCK_RESTORE_DURATION_SECONDS` | `6` / `0` | Duración simulada |
| `MSR_MAX_OUTPUT_CHARS` | `2000` | Truncado de salidas |
| `MSR_CORS_ALLOW_ORIGINS` | localhost:5173 | Orígenes permitidos (sin comodín) |

## 11. Requests y responses

```http
POST /api/tasks/RTASK900001/approve
Idempotency-Key: approve:RTASK900001:3:6f0c…

202 Accepted
{
  "task": { "...": "..." },
  "rings_done": 2,
  "active_job": {
    "id": "job-d24a4be376d7401e",
    "job_type": "patch",
    "task_id": "RTASK900001",
    "ring_number": 3,
    "provider": "mock",
    "provider_reference": "mock-patch:job-d24a4be376d7401e:1785914…",
    "state": "running",
    "terminal": false,
    "dry_run": false,
    "correlation_id": "…",
    "targets": [{ "logical_target_id": "SRV-1001", "instance_id": null, "region": null }],
    "steps": [{ "seq": 1, "command": "terraform apply …", "status": "ok", "output": "…" }]
  }
}
```

Repetir la petición con la misma `Idempotency-Key` devuelve el mismo job (no crea otro).
Sin clave, se genera una temporal por petición.

```http
GET  /api/patch-jobs/{job_id}           → 200 PatchJob | 404
GET  /api/tasks/{task_id}/patch-jobs    → 200 [PatchJob]
POST /api/patch-jobs/{job_id}/cancel    → 200 PatchJob (cancelling|cancelled)
GET  /api/execution                     → 200 {patch_provider, restore_provider, dry_run,
                                               poll_interval_seconds, region}
```

Errores (formato uniforme):

```json
{ "error": { "code": "TARGET_NOT_ALLOWED",
             "message": "The selected target is not allowed for automated patching.",
             "correlation_id": "…" } }
```

`409` job activo sobre el mismo objetivo · `422` objetivo o estado inválido ·
`503` configuración o dependencia externa no disponible · `404` recurso inexistente.

## 12. Seguridad

- El frontend no maneja credenciales, runbooks ni comandos: sólo identificadores de tarea,
  anillo y job.
- No hay shell libre: los parámetros de Automation se validan contra una allowlist y se
  rechazan metacaracteres.
- Doble allowlist (cuenta/región/entorno + runbook) y tag obligatorio en el objetivo; los
  IDs sintéticos de la CMDB de demo no pueden usarse como objetivo AWS.
- Lock por objetivo en base de datos: imposible lanzar dos operaciones mutativas
  simultáneas sobre la misma instancia.
- Idempotencia por clave: un doble clic o un reintento no duplican ejecuciones.
- Salidas saneadas y truncadas antes de persistirse o mostrarse; los ARNs y valores
  sensibles se redactan. Ninguna variable de entorno de secretos se registra.
- CORS restringido por configuración (sin `*`).
- Dry-run activado por defecto: seleccionar AWS no basta para mutar nada.

## 13. Resultados de validación

| Comando | Resultado |
|---------|-----------|
| `pytest` (backend) | **80 passed** |
| `ruff check .` (backend) | **All checks passed!** |
| `python -m compileall app` | OK |
| `npm run lint` (oxlint) | exit 0 · 8 warnings preexistentes (`only-export-components` en `ui.tsx`/`view.tsx`) |
| `npx tsc -b` | limpio |
| `npm run build` | OK · aviso preexistente de chunk > 500 kB |

Prueba manual extremo a extremo con el provider mock: aprobar el anillo 3 devuelve `202`,
la UI muestra el job en `running` con sus pasos y bloquea aprobación/rollback/edición,
`rings_done` permanece en 2 durante la ejecución y pasa a 3 exactamente una vez al alcanzar
`succeeded`; tras recargar la página el estado se recupera del backend.

## 14. Limitaciones

- El adaptador AWS está validado con `botocore.stub.Stubber`, no contra una cuenta real.
- La CMDB sintética no contiene Instance IDs reales: hasta configurar
  `MSR_SANDBOX_INSTANCE_ID` no existe ningún objetivo ejecutable en AWS (la UI lo indica
  como "sin instancia AWS").
- El avance del job requiere que alguien consulte la tarea; sin lecturas el job no se
  reconcilia (no hay scheduler).
- No hay autenticación ni autorización en la API; sigue siendo una demo.
- El estado funcional de la demo (fases, logs, artefactos) sigue en memoria; sólo los jobs
  son durables.
- La verificación posterior al parche es simulada: no se consultan métricas reales.

## 15. Información AWS pendiente

1. Cuenta(s) y región de la EC2 de pruebas, e Instance ID concreto.
2. ¿La instancia es un nodo gestionado por SSM (agente activo, rol de instancia con
   `AmazonSSMManagedInstanceCore`, endpoints alcanzables)?
3. Runbook a utilizar: `AWS-RunPatchBaseline` u otro documento propio; nombre exacto y
   parámetros permitidos.
4. Rol IAM para la aplicación (permisos mínimos: `ssm:StartAutomationExecution`,
   `ssm:GetAutomationExecution`, `ssm:DescribeAutomationStepExecutions`,
   `ssm:StopAutomationExecution`, `ssm:DescribeInstanceInformation`,
   `ec2:DescribeInstances`) y `AutomationAssumeRole`.
5. ¿Se permiten reinicios y snapshots previos? ¿Ventana de mantenimiento?
6. Estrategia de rollback aceptada (snapshot/AMI previa vs. redeploy del artefacto).
7. Tag de gobierno definitivo para marcar objetivos parcheables.

## 16. Siguiente incremento

1. Configurar la única EC2 de sandbox y ejecutar el flujo en **dry-run real** contra la
   cuenta (sólo llamadas de lectura) para validar la resolución del objetivo.
2. Primera ejecución real de `StartAutomationExecution` sobre esa instancia, con la
   allowlist restringida a ese Instance ID.
3. Verificación posterior al parche basada en salidas reales del runbook en lugar de la
   simulación.
4. Restauración real (snapshot/AMI) tras validar el patch path.
5. Autenticación de la API y trazas/auditoría exportables antes de cualquier uso más allá
   del sandbox.
