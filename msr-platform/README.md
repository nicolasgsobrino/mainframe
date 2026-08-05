# Machine Speed Remediation Platform (demo)

Mockup **funcional** de la plataforma de remediación de vulnerabilidades descrita en
*"Bajada a nivel Patching Ops"*. Demuestra, sobre datos sintéticos realistas, el ciclo
de **6 fases** con **ServiceNow como plano de control**, **Devin como capa agente** y las
herramientas del cliente (Ansible/BigFix/SCCM, CI/CD, Terraform) como ejecutores.

> No requiere un ServiceNow real ni datos reales: todos los datos (CMDB bancaria, CVEs,
> hallazgos de escáneres, SBOM/SCA, Vulnerable Items, Remediation Tasks) se generan de
> forma determinista en el backend y emulan las APIs de ServiceNow y del agente Devin.

## Qué demuestra

- **Dashboard / centro de mando**: embudo de priorización (100k → 8k → 500 → 80 → 20),
  KPIs, distribución por fase / prioridad / track y feed de actividad del agente.
- **Remediation Tasks**: cola priorizada por riesgo (técnico + negocio + operativo + SLA).
- **Ciclo de 6 fases** por tarea con panel del agente **Devin** y **gate HITL** (aprobación
  humana) en cada transición:
  1. **Detección e ingesta** — normalización y correlación con CMDB.
  2. **Priorización** — riesgo multifactor + *reachability analysis*.
  3. **Pre-implementación (MVT)** — Impact Graph (blast radius) + Minimum Viable Test Plan.
  4. **Pruebas en laboratorio** — ejecución del MVT (parche + aplicación) con veredicto.
  5. **Validación en prototipo** — lab efímero con IaC (Terraform/Ansible) + métricas.
  6. **Despliegue por anillos + informe** — oleadas por riesgo, excepciones trazables,
     PR de remediación (Track B) e informe de auditoría *audit-ready* (DORA).
- **CMDB · Impact Graph**: patrimonio bancario e Impact Graph interactivo por servicio.
- **Catálogo de pruebas**: biblioteca versionada de la que Devin selecciona el MVT.
- **Integraciones**: modelo de 3 capas y flujo Flow Designer → Devin API → Table API.

## Stack

- **Backend**: FastAPI (Python), datos mock en memoria + motor de simulación de fases,
  jobs de parcheo persistidos en SQLite.
- **Frontend**: React + TypeScript + Vite + Tailwind, React Flow (grafo) y Recharts.

## Ejecución del parcheo: providers

El despliegue de un anillo ya no es una mutación síncrona del estado en memoria: crea un
**job** persistente que ejecuta un *provider*. Hay dos implementaciones seleccionables por
configuración, y el **mock es el valor por defecto**:

| Provider | Valor | Qué hace |
|----------|-------|----------|
| Mock | `mock` | Simulación determinista, sin AWS ni credenciales. Progresa por tiempo y se consulta con `poll()`. |
| AWS SSM Automation | `aws-automation` | `StartAutomationExecution` sobre un runbook **propio de tipo `Automation`** allowlisted, con validación read-only previa de EC2/SSM y `describe_document`. **Desactivado por defecto.** |

El backend nunca usa workers, colas ni `BackgroundTasks`: reconcilia el estado del job
llamando a `provider.poll()` cuando se consulta la tarea, y el frontend hace polling cada
`MSR_JOB_POLL_INTERVAL_SECONDS`. Además, un **reconciliador periódico** en proceso
(`MSR_RECONCILER_*`, arrancado por el *lifespan* de FastAPI) consulta los jobs activos
persistidos, de modo que el estado avanza aunque nadie tenga la UI abierta. El
reconciliador nunca crea ejecuciones: sólo consulta y persiste.

### Contrato de runbooks

Cada operación tiene un contrato explícito (`backend/app/runbooks.py`) con tipo de
documento, parámetros obligatorios/opcionales/prohibidos, tracks y sistemas operativos
admitidos:

| Operación | Runbook por defecto | Variable |
|-----------|--------------------|----------|
| `patch` | `MSR-PatchLinuxInstance` | `MSR_PATCH_RUNBOOK_NAME` |
| `rollback` | `MSR-RollbackLinuxInstance` | `MSR_ROLLBACK_RUNBOOK_NAME` |
| `reset_lab` | `MSR-ResetLabInstance` | `MSR_RESET_RUNBOOK_NAME` |

Antes de arrancar se llama a `ssm.describe_document` y se exige `DocumentType=Automation`.
Documentos de tipo `Command` como `AWS-RunPatchBaseline` **no pueden** enviarse a
`StartAutomationExecution`: el runbook propio los invoca internamente con `aws:runCommand`.
Los parámetros se derivan del contrato del runbook, nunca de valores genéricos
(`Operation=Install`, `TargetVersion`) ni de datos enviados por el frontend.

### Límites de la ejecución real

- sólo **track A** (infraestructura): B y C devuelven `UNSUPPORTED_REMEDIATION_TRACK` sin llamar a AWS;
- un job AWS representa **exactamente una** instancia: cero o varias devuelven `422 RING_TARGET_COUNT_UNSUPPORTED` (el mock mantiene el comportamiento multiactivo);
- un timeout local **no** libera el objetivo: el job pasa a `timeout_pending_confirmation`, `stop_requested` o `remote_status_unknown` y sólo se cierra con confirmación remota o con `POST /api/patch-jobs/{id}/admin-resolve` (auditado);
- con `MSR_DRY_RUN=false` la política es **fail-closed**: región, allowlists de cuenta/región/entorno, tag obligatorio, runbook permitido, rol de Automation y objetivo de sandbox deben estar configurados. Una lista vacía nunca significa «permitir todo»;
- si `MSR_AWS_ROLE_ARN` está configurado, los clientes EC2/SSM se crean con credenciales temporales de STS `AssumeRole` (`RoleSessionName` con el correlation ID sanitizado, nunca registradas).

Copia `.env.example` a `.env` para ajustar la configuración (`MSR_*`). Con los valores por
defecto (`MSR_PATCH_PROVIDER=mock`, `MSR_DRY_RUN=true`) la aplicación arranca sin AWS y no
realiza ninguna operación real. Al seleccionar `aws-automation` sin región ni runbook, el
arranque falla con un error explícito en lugar de intentar llamadas a medias.

El estado funcional en memoria no es la fuente de verdad: al arrancar,
`rehydrate_pipeline_state()` reconstruye anillos completados, restauraciones, evidencia y
estado de la tarea/Vulnerable Item desde SQLite.

Detalle completo de arquitectura, esquema SQLite, máquina de estados y variables:
[`IMPLEMENTATION_REPORT_PHASE1.md`](IMPLEMENTATION_REPORT_PHASE1.md) y las correcciones de
la revisión técnica en
[`IMPLEMENTATION_REPORT_PHASE1_1.md`](IMPLEMENTATION_REPORT_PHASE1_1.md).

## Tests, lint y build

```bash
cd backend && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest                 # tests del flujo de jobs, providers, persistencia y API
ruff check .           # lint

cd ../frontend
npm run lint           # oxlint
npx tsc -b             # type checking
npm run build          # build de producción
```

## Ejecutar en local

Necesitas Python 3.10+ y Node 18+.

```bash
# 1) Backend  (http://localhost:8080)
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt        # o requirements-dev.txt para tests y lint
uvicorn app.main:app --reload --port 8080

# 2) Frontend (http://localhost:5173)  — en otra terminal
cd frontend
npm install
npm run dev
```

Abre <http://localhost:5173>. El frontend hace proxy de `/api` al backend.

### Modo "todo en uno" (backend sirve el frontend compilado)

```bash
./scripts/build.sh      # compila el frontend en backend/static
cd backend && source .venv/bin/activate
uvicorn app.main:app --port 8080
# abre http://localhost:8080
```

## API principal

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/overview` | KPIs, embudo, distribuciones |
| GET | `/api/tasks` | Remediation Tasks (cola priorizada) |
| GET | `/api/tasks/{id}` | Detalle + artefactos de cada fase |
| POST | `/api/tasks/{id}/approve` | Gate HITL: aprueba la fase / despliega anillo |
| GET | `/api/cmdb` | CIs y relaciones |
| GET | `/api/catalog` | Catálogo de pruebas |
| GET | `/api/vulnerable-items` | Vulnerable Items |
| GET | `/api/services` | Estado de integraciones (3 capas) |
| POST | `/api/reset` | Reinicia el estado de la demo |
| GET | `/api/execution` | Providers activos, `dry_run` e intervalo de polling |
| GET | `/api/patch-jobs/{job_id}` | Estado de un job de parcheo/restauración |
| GET | `/api/tasks/{id}/patch-jobs` | Jobs de una tarea (más recientes primero) |
| POST | `/api/patch-jobs/{job_id}/cancel` | Solicita la cancelación de un job activo |
| POST | `/api/patch-jobs/{job_id}/admin-resolve` | Reconciliación manual auditada de un job sin estado remoto confirmado |
| GET | `/api/lab-targets` | Laboratorios reutilizables registrados (`LabTarget`) |
| GET | `/api/lab-targets/{logical_lab_id}` | Detalle de un laboratorio |
| POST | `/api/lab-targets` | Registra o actualiza el laboratorio de la PoC |

`POST /api/tasks/{id}/approve` acepta la cabecera `Idempotency-Key`: repetir la misma clave
devuelve el job original en lugar de lanzar otro. En la fase de despliegue responde `202`
con el `TaskDetail` (incluye `active_job`); las fases 1-5 siguen siendo síncronas (`200`).
Los errores usan un formato uniforme `{"error": {"code", "message", "correlation_id"}}`
con `409` (job activo sobre el mismo objetivo), `422` (objetivo o estado inválido) y `503`
(dependencia o configuración externa).

## Estructura

```
backend/app/
  seed.py       # generación de datos mock (CMDB, CVEs, hallazgos, VIs, tasks)
  engine.py     # Impact Graph, MVT, lab, prototipo, anillos, auditoría
  store.py      # estado en memoria + orquestación de fases (HITL) + jobs
  main.py       # API FastAPI
  config.py     # Settings (MSR_*) y validación por provider
  errors.py     # errores de dominio → HTTP con correlation_id
  jobs.py       # PatchJob, JobEvent y máquina de estados
  repository.py # persistencia SQLite: jobs, targets, eventos, idempotencia
  policy.py     # allowlists, validación de objetivos y sanitización
  runbooks.py   # contrato explícito de SSM Documents por operación
  lab.py        # LabTarget: laboratorio vulnerable reutilizable (reset_lab)
  reconciler.py # reconciliador periódico de jobs activos (no ejecuta parches)
  providers/    # contrato + mock_patch / mock_restore / aws_ssm_automation
backend/tests/  # pytest (contratos, estados, persistencia, API, AWS con Stubber)
frontend/src/
  pages/      # Dashboard, Tasks, TaskDetail, Cmdb, Catalog, Integrations
  components/ # ImpactGraphView (React Flow)
```

> Demo con fines de presentación. Los datos son sintéticos y las integraciones están
> emuladas; el diseño refleja cómo se conectaría con los sistemas reales del cliente.
