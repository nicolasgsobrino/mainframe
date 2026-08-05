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
- si `MSR_AWS_ROLE_ARN` está configurado, los clientes EC2/SSM se crean con credenciales temporales de STS `AssumeRole` (`RoleSessionName` con el correlation ID sanitizado, nunca registradas) y **se reconstruyen** en cuanto la sesión se renueva: ninguna operación reutiliza un cliente con credenciales caducadas.

Copia `.env.example` a `.env` para ajustar la configuración (`MSR_*`). Con los valores por
defecto (`MSR_PATCH_PROVIDER=mock`, `MSR_DRY_RUN=true`) la aplicación arranca sin AWS y no
realiza ninguna operación real. Al seleccionar `aws-automation` sin región ni runbook, el
arranque falla con un error explícito en lugar de intentar llamadas a medias.

El estado funcional en memoria no es la fuente de verdad: al arrancar,
`rehydrate_pipeline_state()` reconstruye anillos completados, restauraciones, evidencia y
estado de la tarea/Vulnerable Item desde SQLite.

SQLite se usa con una **conexión por operación** (WAL, `busy_timeout` de 5 s y escrituras con
`BEGIN IMMEDIATE`), de modo que requests, polling del frontend y reconciliador pueden actuar
en paralelo sin compartir una conexión entre hilos.

### Laboratorio EC2 reseteable

La PoC trabaja sobre una **única** instancia de laboratorio identificada por su
identificador lógico (`MSR_LAB_LOGICAL_ID`, tag `msr-lab-id`), no por Instance ID: la
mantiene viva un **Auto Scaling Group de capacidad fija 1** (`MSR_LAB_AUTOSCALING_GROUP_NAME`)
y cada `reset_lab` la sustituye dentro de ese grupo
(`TerminateInstanceInAutoScalingGroup` con `ShouldDecrementDesiredCapacity=false`), nunca
con `ec2:TerminateInstances`/`ec2:RunInstances`. El Instance ID se resuelve en cada
operación por tags (`DescribeInstances`), debe haber **exactamente una** instancia activa
(`LAB_TARGET_NOT_FOUND` / `LAB_TARGET_AMBIGUOUS`) y debe pertenecer al ASG configurado
(`LAB_TARGET_NOT_IN_AUTOSCALING_GROUP`). El nombre del ASG sale siempre de la
configuración: ni la API ni la UI lo aceptan como entrada.

`reset_lab` **no es un rollback**: no deshace un despliegue fallido, sino que recrea la
instancia vulnerable para repetir la PoC. No incrementa `rings_done`, conserva el historial
de jobs y actualiza `LabTarget.current_instance_id` al completarse.

El advisory demostrado es **`ALAS2023-2026-1924`** (familia `kernel`). El repositorio de la
AMI base está fijado en su propia release (`2023.11.20260509.0`), anterior a la corrección,
así que precheck, postcheck y reset consultan el advisory con
`dnf updateinfo list --available --advisory ... --releasever 2023.12.20260706`
(`MSR_PATCH_RELEASEVER`) y exigen que el kernel en ejecución quede en
`6.1.176-220.358.amzn2023.x86_64` o posterior (`MSR_PATCH_EXPECTED_FIXED_KERNEL`, comparado
con `sort -V`, nunca lexicográficamente). Un repositorio inaccesible devuelve
`PATCH_REPOSITORY_UNREACHABLE` y no se confunde con `ADVISORY_NOT_APPLICABLE`. Los tres
valores salen de la IaC: la UI sólo los muestra.

La infraestructura (VPC/subnet existentes, Launch Template, ASG, IAM, patch baseline y los dos
runbooks Automation) está en [`infra/terraform/`](infra/terraform/README.md) con
`enable_real_resources = false` por defecto: con ese valor no se crea ningún recurso.

Detalle completo de arquitectura, esquema SQLite, máquina de estados y variables:
[`IMPLEMENTATION_REPORT_PHASE1.md`](IMPLEMENTATION_REPORT_PHASE1.md), las correcciones de
la revisión técnica en
[`IMPLEMENTATION_REPORT_PHASE1_1.md`](IMPLEMENTATION_REPORT_PHASE1_1.md) y el hardening de
concurrencia y credenciales en
[`IMPLEMENTATION_REPORT_PHASE1_2.md`](IMPLEMENTATION_REPORT_PHASE1_2.md). La
infraestructura, los runbooks y la integración del laboratorio, en
[`IMPLEMENTATION_REPORT_PHASE2.md`](IMPLEMENTATION_REPORT_PHASE2.md); la migración a Auto
Scaling Group y la verificación estricta del parcheo, en
[`IMPLEMENTATION_REPORT_PHASE2_1.md`](IMPLEMENTATION_REPORT_PHASE2_1.md); el cambio de
advisory y el releasever explícito, en
[`IMPLEMENTATION_REPORT_PHASE2_2.md`](IMPLEMENTATION_REPORT_PHASE2_2.md).

## Tests, lint y build

```bash
cd backend && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest                 # tests del flujo de jobs, providers, persistencia y API
ruff check .           # lint

cd ../frontend
npm ci                 # requiere Node >= 22.12 (ver .nvmrc)
npm run lint           # oxlint
npx tsc -b             # type checking
npm run build          # build de producción

cd ../infra/terraform  # validación estática: sin backend, sin credenciales
terraform fmt -check -recursive
terraform init -backend=false
terraform validate     # nunca `plan` ni `apply` desde CI
```

Las mismas comprobaciones se ejecutan en CI para cualquier cambio en `msr-platform/**`
(`.github/workflows/msr-platform-ci.yml`), sin credenciales AWS.

## Ejecutar en local

Necesitas Python 3.10+ y Node >= 22.12 (`frontend/.nvmrc`). Con Node 20.18 npm omite el
binario nativo opcional de oxlint (`engines: ^20.19.0 || >=22.12.0`) y `npm run lint` falla
con `Cannot find native binding`.

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
| GET | `/api/labs/{logical_lab_id}` | Estado del laboratorio: instancia resuelta por tags, AMI, advisory, SSM y vulnerable/parcheado |
| POST | `/api/labs/{logical_lab_id}/validate` | Validación de **sólo lectura** (no inicia ninguna Automation) |
| POST | `/api/labs/{logical_lab_id}/reset` | `202` + job `reset_lab`: recrea la instancia vulnerable |
| GET | `/api/labs/{logical_lab_id}/jobs` | Historial completo de jobs del laboratorio |

Los endpoints `/api/labs/*` no aceptan Instance IDs, comandos, documentos, advisories ni
parámetros del cliente: sólo el identificador lógico de la ruta.

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
  labs.py       # resolución del Instance ID actual por tags (AWS y mock)
  reconciler.py # reconciliador periódico de jobs activos (no ejecuta parches)
  providers/    # contrato + mock_patch / mock_restore / aws_ssm_automation
backend/tests/  # pytest (contratos, estados, persistencia, API, AWS con Stubber)
frontend/src/
  pages/      # Dashboard, Tasks, TaskDetail, Cmdb, Catalog, Integrations
  components/ # ImpactGraphView (React Flow), LabPanel (laboratorio EC2)
infra/terraform/
  *.tf          # red, IAM, Launch Template, ASG 1/1/1, patch baseline, documentos
  documents/    # runbooks Automation MSR-PatchLinuxInstance y MSR-ResetLabInstance
```

> Demo con fines de presentación. Los datos son sintéticos y las integraciones están
> emuladas; el diseño refleja cómo se conectaría con los sistemas reales del cliente.
