# HANDOFF TÉCNICO · Integración de parcheo real en AWS (EC2)

> Documento de handoff de la PoC **Machine Speed Remediation (MSR) Platform** (`msr-platform/`)
> antes de sustituir los mocks por operaciones reales sobre instancias EC2.
> **Estado del código:** no se ha modificado ninguna línea funcional; este documento es el único
> fichero añadido. Los mocks siguen intactos y no se han introducido credenciales.

---

## 1. Executive summary

1. La PoC es una aplicación **FastAPI + React** aislada en el subdirectorio `msr-platform/` de un
   repositorio cuyo contenido principal es el mainframe CardDemo (COBOL). No comparte código con
   el resto del repo.
2. **Todo es simulación determinista en memoria**: no hay base de datos, ni cola, ni worker, ni
   scheduler, ni llamadas de red salientes. `seed.py` genera CMDB/CVEs/tareas, `engine.py`
   fabrica los artefactos de las 6 fases y `store.py` mantiene el estado en un singleton
   (`STORE = Store()`).
3. El "parcheo" **no ejecuta nada**: `engine.build_ring_actions()` construye una lista de
   diccionarios con `command`/`output` de texto (`deploy patch ...`, `systemctl restart ...`).
   Nunca se invoca un proceso, SSH, SSM ni SDK.
4. **No existe asincronía**: `POST /api/tasks/{id}/approve` calcula el nuevo estado y responde
   síncronamente. No hay `sleep`, ni temporizadores, ni polling en el frontend; la UI se refresca
   con el `TaskDetail` que devuelve el propio POST.
5. **No hay persistencia**: reiniciar el backend recrea todo desde cero (fases iniciales fijas
   `[5, 2, 5, 3, 4]`). Lo único versionado en disco es la CMDB sintética (`data/cmdb/*.json`).
6. **No hay configuración**: cero variables de entorno, cero ficheros de config por entorno, cero
   gestión de secretos y **ninguna dependencia del AWS SDK** (`requirements.txt` = fastapi,
   uvicorn, pydantic).
7. El modelo de datos ya es razonablemente cercano a AWS: `track` (A infra / B dependencias /
   C contenedores) determina el ejecutor y la mecánica de rollback; `RING_STAGES` define la
   promoción por entornos; `RingAsset` ya tiene identidad de activo (`id`, `ci_class`, `environment`).
   **Falta el identificador real de instancia** (`instance_id`, ARN, región, cuenta, tags).
8. La superficie de integración es pequeña y localizada: **3 funciones** de `engine.py`
   (`build_ring_actions`, `build_rollback_plan`, `build_lab_results`) y **2 métodos** de `store.py`
   (`approve_phase`, `rollback`) concentran el 100% de la ejecución simulada.
9. **No hay tests, ni lint de backend, ni CI**. Frontend: `oxlint` (8 warnings, 0 errores) y
   `tsc -b` (limpio); `vite build` OK. `npm run lint` falla en un entorno recién instalado por un
   binding nativo de `oxlint` que npm no instala (bug de optional deps), no por el código.
10. **Riesgo principal si se conecta AWS con la arquitectura actual**: los comandos se construyen
    interpolando datos de la tarea y el backend no valida nada, no tiene allowlist de instancias,
    no tiene autenticación/autorización y no impide dos operaciones concurrentes sobre el mismo
    activo. Todo eso debe existir **antes** de la primera llamada real a AWS.

---

## 2. Arquitectura actual

| Capa | Tecnología | Detalle |
|------|------------|---------|
| Frontend | React 19 + TypeScript + Vite 5 + Tailwind 3, `react-router-dom` 7, `reactflow` 11, `recharts` 3 | SPA, 6 vistas; lint con `oxlint` |
| Backend | Python 3.10+, FastAPI 0.115.6, Uvicorn 0.34, Pydantic 2.10.4 | API REST `/api/*`, CORS `allow_origins=["*"]` |
| Lógica de negocio | Módulos puros Python (`seed`, `engine`, `store`) | Simulación determinista (`random.Random` con semilla) |
| Persistencia | **Ninguna (memoria)** + JSON versionado de CMDB | `STORE` singleton; `data/cmdb/*.json` |
| Despliegue | Sin despliegue automatizado | `scripts/dev.sh` (dev) y `scripts/build.sh` (SPA servida por FastAPI en `backend/static`) |
| CI/CD | **No existe** (`.github/workflows` ausente) | Tampoco hay Dockerfile ni IaC para la PoC |

### Puntos de entrada

- **Backend:** `msr-platform/backend/app/main.py` → `app = FastAPI(...)`; se arranca con
  `uvicorn app.main:app --port 8080`. El estado se crea al importar `store.py` (`STORE = Store()`).
- **Frontend:** `msr-platform/frontend/index.html` → `src/main.tsx` → `src/App.tsx` (router).
- **Todo en uno:** si existe `backend/static/`, `main.py` monta `/assets` y sirve la SPA con un
  catch-all `GET /{full_path:path}`.

### Comandos

| Objetivo | Comando |
|----------|---------|
| Dependencias backend | `cd msr-platform/backend && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt` |
| Dependencias frontend | `cd msr-platform/frontend && npm install` |
| Ejecutar (dev, ambos) | `cd msr-platform && ./scripts/dev.sh` (backend :8080, frontend :5173 con proxy `/api`) |
| Ejecutar backend solo | `uvicorn app.main:app --reload --port 8080` (desde `backend/`) |
| Build producción | `cd msr-platform && ./scripts/build.sh` → copia `frontend/dist` a `backend/static` |
| Lint frontend | `cd msr-platform/frontend && npm run lint` (`oxlint`) |
| Type checking | `cd msr-platform/frontend && npx tsc -b` |
| Tests | **No existen** (ni pytest, ni vitest, ni jest) |
| Lint/format backend | **No configurado** (ni ruff, ni flake8, ni black, ni mypy) |

### Forma actual de despliegue

No hay despliegue. La demo se ejecuta en local (o en el escritorio remoto de una sesión Devin, de
ahí `allowedHosts: true` en `vite.config.ts`). No hay Dockerfile, Helm chart, Terraform, workflow de
GitHub Actions ni referencia a ningún entorno cloud para esta PoC.

---

## 3. Árbol de archivos relevantes

```
msr-platform/
├── README.md                       # arquitectura, comandos, tabla de API
├── GUIA_DEMO.md                    # guion de demo (contexto de negocio)
├── HANDOFF_AWS_PATCHING.md         # este documento
├── backend/
│   ├── requirements.txt            # fastapi / uvicorn / pydantic  ← sin boto3
│   └── app/
│       ├── main.py    (185 l.)     # API FastAPI: 17 rutas /api/*
│       ├── store.py   (503 l.)     # estado en memoria + orquestación HITL de fases
│       ├── engine.py  (791 l.)     # ⚠ simulador: impacto, MVT, lab, prototipo, anillos, rollback
│       └── seed.py    (764 l.)     # ⚠ datos mock: CMDB, CVEs, findings, VI, tasks, catálogo
├── data/cmdb/                      # CMDB sintética versionada (formato ServiceNow Table API)
│   ├── _manifest.json              # tablas + conteos + field map
│   ├── normalized_cis.json         # 180 CIs (fuente que recarga el backend)
│   ├── normalized_edges.json       # 138 relaciones
│   └── cmdb_ci_*.json / cmdb_rel_ci.json
├── frontend/
│   ├── vite.config.ts              # proxy /api → localhost:8080
│   ├── .oxlintrc.json
│   └── src/
│       ├── api.ts                  # ⚠ único cliente HTTP (fetch)
│       ├── types.ts                # modelos TS espejo del backend
│       ├── App.tsx / view.tsx / ui.tsx
│       ├── pages/TaskDetail.tsx    # ⚠ dispara aprobar / rollback / simular incidente
│       ├── pages/{Dashboard,Tasks,Cmdb,Catalog,Integrations}.tsx
│       └── components/{ImpactGraphView,CmdbRecordModal}.tsx
└── scripts/{dev.sh,build.sh}
```

---

## 4. Flujo completo del mock (de la selección de la vulnerabilidad al "parche aplicado")

1. **Selección.** `pages/Tasks.tsx` lista las Remediation Tasks (`GET /api/tasks`, ordenadas por
   `risk_score` descendente) y navega a `/tasks/{id}`. No se "introduce" una vulnerabilidad: el
   conjunto está fijado en `seed.build_records()` (5 escenarios, constante `scenarios`).
2. **Carga del detalle.** `pages/TaskDetail.tsx` → `load()` → `api.task(id)` → `GET /api/tasks/{id}`
   → `main.task_detail()` → `STORE.task_detail(tid)`, que devuelve tarea + Vulnerable Item + las 6
   fases con su estado + **todos los artefactos ya precalculados** + logs.
3. **Gate previo (solo fase 6).** Para desplegar un anillo el usuario debe pre-aprobar su informe:
   `POST /api/tasks/{id}/rings/{ring}/preapprove` → `STORE.preapprove_ring()`. Opcionalmente puede
   excluir activos: `POST /api/tasks/{id}/rings/{ring}/assets` → `STORE.update_ring_assets()`
   (editar invalida la pre-aprobación previa).
4. **Acción del usuario ("aplicar el parche").** Botón *"Aprobar y desplegar anillo"* →
   `approve()` → `api.approve(id)` → `POST /api/tasks/{id}/approve` → `main.approve()` →
   **`STORE.approve_phase(tid)`**.
5. **Servicio de negocio.** `Store.approve_phase()`:
   - Fases 1-5: marca la fase `approved`, avanza `phase_index`, pone la siguiente en
     `awaiting_approval` y añade los logs "del agente" (`Store._phase_logs()`).
   - Fase 6 (`deployment`): comprueba la pre-aprobación del siguiente anillo; si falta, escribe un
     log de bloqueo y devuelve el estado sin avanzar. Si existe, `rings_done += 1` y llama a
     `Store._rebuild_deploy()` → `engine.build_deployment()`.
6. **Simulación del parcheo.** `engine.build_deployment()` recalcula los 5 anillos y, para los
   anillos ya completados, invoca **`engine.build_ring_actions()`**, que devuelve la lista de pasos
   (`actor`, `tool`, `command`, `output`, `why`, `duration_s`) según el `track`:
   - **A (infra):** `snapshot create` → `deploy patch <comp> <prev> → <fixed>` → `install` →
     `systemctl restart affected-services`.
   - **B (dependencias):** rama git → bump de versión → merge PR → `docker build` → `helm upgrade`.
   - **C (contenedores):** rama git → nueva imagen base → `docker build` → `trivy` → `argocd sync`.
   - En cualquier caso: 4 post-checks (`version-assert`, `health-check`, `smoke-test`,
     `synthetic-probe`) y, en Lab/Pre-prod, `terraform apply/destroy` de la réplica + suite de tests.
   **Ninguno de esos comandos se ejecuta**: solo se almacenan como texto junto a su salida ficticia.
7. **Cierre.** Cuando `rings_done >= len(RING_DEFS)` (5): `task["status"] = "remediated"` y
   `vulnerable_item["status"] = "fixed"`, más el log de "reescaneo verificado".
8. **Persistencia del estado.** Solo en memoria: `Store.pipelines[tid]` (fase, estados por fase,
   `rings_done`, `rolled_back_rings`, pre-aprobaciones, exclusiones, `rollback`, `artifacts`, `logs`)
   y mutación in-place de `Store.tasks` / `Store.vulnerable_items`.
9. **Refresco del frontend.** El POST devuelve el `TaskDetail` completo y el componente hace
   `setD(r)`. **No hay polling, ni WebSocket, ni SSE, ni revalidación**; el resto de vistas solo
   cargan en el `useEffect` de montaje.
10. **Rollback.** `POST /api/tasks/{id}/rollback` (manual) o
    `POST /api/tasks/{id}/simulate-incident` (que loguea una anomalía y llama al mismo
    `Store.rollback(trigger="auto")`): decrementa `rings_done`, marca el anillo en
    `rolled_back_rings`, escribe los pasos de `engine.build_rollback_plan()` como logs, devuelve el
    VI a `in_progress` y la tarea a `in_flight`.

### Estados posibles

| Dimensión | Valores | Dónde |
|-----------|---------|-------|
| Fase (`phase_index` 0-5) | `detection`, `prioritization`, `pre_implementation`, `lab_testing`, `prototype`, `deployment` | `engine.PHASES` |
| Estado de fase | `pending`, `awaiting_approval`, `approved` | `Store._init_pipeline` / `approve_phase` |
| Anillo | `pending`, `in_progress`, `completed`, `rolled_back` | `engine.build_deployment` |
| Tarea | `remediated`, `in_flight` (ausente = abierta) | `Store.approve_phase` / `rollback` |
| Vulnerable Item | `open`, `in_progress`, `fixed` | `seed` / `Store` |
| Rollback | `armed` → `completed` (`triggered`, `trigger_type` = `manual`/`auto`) | `Store.rollback` |
| Veredictos | lab `pass`/`fail`; prototipo `pass` (fijo) | `engine.build_lab_results` / `build_prototype` |
| Carril operativo (lane) | `critical`, `accelerated`, `standard` | `seed.assign_lane` |
| Dominio técnico (track) | `A`, `B`, `C` | `seed.CVE_CATALOG` / CMDB |
| Tipo de cambio ITSM | `standard`, `normal`, `emergency` | `seed.build_records` |

### Gestión de errores (actual)

- Backend: única gestión = `HTTPException(404, "task not found")` en `main.py` cuando el `STORE`
  devuelve `None` (y 404 "CI no encontrado" en `cmdb_ci_raw`). **No hay try/except, ni códigos 4xx
  de validación de estado, ni 409 de conflicto, ni 5xx controlado, ni logging estructurado.**
- Un fallo funcional (p. ej. anillo sin pre-aprobar) se comunica como **log dentro de la respuesta
  200**, no como error HTTP.
- Frontend: `api.ts` lanza `new Error(await r.text())` si `!r.ok`, pero **ningún componente captura
  la promesa** → un fallo del backend se convierte en un unhandled rejection y la UI se queda
  con el estado anterior (los botones sí se rehabilitan solo si la promesa resuelve; si rechaza,
  `busy` queda en `true`).

---

## 5. Inventario de código mock

Rutas relativas a `msr-platform/`. **Todo el fichero `seed.py` y todo `engine.py` son mock.**

### 5.1 Instancias / activos (CMDB)

| Elemento | Ruta | Responsabilidad | Entrada | Salida | Dependencias | Qué sustituir para AWS |
|---|---|---|---|---|---|---|
| `build_cmdb()` | `backend/app/seed.py` | Construye el patrimonio sintético (servicios, apps, servidores, BBDD, middleware, runtime) | — | `(cis, edges)` | `RNG`, catálogos constantes | Reemplazar por ingesta real (ServiceNow Table API o `ec2:DescribeInstances` + `ssm:DescribeInstanceInformation`) |
| `_scale_estate()` | `backend/app/seed.py` | Rellena hasta 180 CIs (servidores, contenedores, endpoints, cloud, red) | `cis, edges, target` | `(cis, edges)` | `RNG` | Eliminar; el inventario real viene del descubrimiento |
| `export_cmdb()` / `load_cmdb()` / `has_cmdb_export()` | `backend/app/seed.py` | Persiste/recarga la CMDB en `data/cmdb/*.json` | listas de CIs/edges | ficheros JSON | `json`, FS | Sustituir por caché de inventario real (o dejar como fixture de test) |
| `servicenow_record()` / `servicenow_rel()` / `CMDB_FIELD_MAP` | `backend/app/seed.py` | Fabrica el payload "nativo" de ServiceNow y el mapeo de campos | CI normalizado | dict estilo Table API | `hashlib` | Sustituir por la respuesta real de ServiceNow; añadir campos AWS (`instance_id`, `account`, `region`, `tags`) |
| `Store.cmdb_cis/cmdb_summary/cmdb_graph/cmdb_ci_raw` | `backend/app/store.py` | Consulta del inventario en memoria | filtros | dicts | `seed` | Cambiar la fuente, mantener la firma |
| `GET /api/cmdb*` (5 rutas) | `backend/app/main.py` | Exponen el inventario | query params | JSON | `STORE` | Sin cambios de contrato |
| `pages/Cmdb.tsx`, `components/CmdbRecordModal.tsx` | `frontend/src/` | UI de inventario e Impact Graph | — | — | `api.ts` | Añadir columnas `instance_id`/región/cuenta |

### 5.2 Vulnerabilidades y su detección

| Elemento | Ruta | Responsabilidad | Entrada | Salida | Dependencias | Qué sustituir para AWS |
|---|---|---|---|---|---|---|
| `CVE_CATALOG` (27 CVEs reales, datos fijos) | `backend/app/seed.py` | Catálogo de vulnerabilidades | — | tuplas | — | Sustituir por Inspector/Snyk/Qualys o entrada del usuario |
| `SCANNERS` + bucle de 240 `findings` en `build_records()` | `backend/app/seed.py` | Simula hallazgos brutos de escáneres | `cis` | lista de findings | `RNG` | Reemplazar por ingesta (`inspector2:ListFindings`, SCA, SBOM) |
| `scenarios` (5 tuplas) + Vulnerable Items + Remediation Tasks en `build_records()` | `backend/app/seed.py` | Curación de los 5 casos de demo | `cis, edges` | `(findings, vitems, tasks)` | `RNG`, `_risk_score`, `assign_lane` | Punto de entrada real: crear tarea desde un finding recibido (webhook/API) |
| `_risk_score()`, `_priority_label()`, `assign_lane()` | `backend/app/seed.py` | Priorización multifactor y carril | cvss, epss, kev, exposed, criticidad, entorno | score 0-100 / label / lane | — | **Reutilizable tal cual** (lógica de negocio, no mock de ejecución) |
| `build_impact_graph()` | `backend/app/engine.py` | Blast radius por BFS sobre la CMDB (máx. 10 nodos, prof. 3) | task, cis, edges | dict de nodos/aristas | `_build_adjacency` | Reutilizable; alimentarlo con relaciones reales |
| `GET /api/vulnerable-items`, `GET /api/findings` | `backend/app/main.py` | Exponen VI y findings (**no consumidos por el frontend**) | — | JSON | `STORE` | Aquí encajaría el `POST` de ingesta real |

### 5.3 Aplicación de parches, reinicios y validación posterior

| Elemento | Ruta | Responsabilidad | Entrada | Salida | Dependencias | Qué sustituir para AWS |
|---|---|---|---|---|---|---|
| **`build_ring_actions()`** | `backend/app/engine.py:483` | **Corazón del mock de parcheo**: genera los pasos "ejecutados" (incluye `systemctl restart affected-services` y los 4 post-checks) | `task, ring_no, assets, executor, ts_base` | `{steps[], from_version, to_version}` | `_rng`, `RING_STAGES`, `_fixed_version` | **Sustituir por `AwsSsmPatchProvider`**: `ssm:SendCommand` (AWS-RunPatchBaseline / AWS-RunShellScript), `ssm:GetCommandInvocation`, reinicio y post-checks reales |
| `_fixed_version()` / `_prev_version()` | `backend/app/engine.py` | Deriva la versión "parcheada" incrementando el patch | versión | string | — | Sustituir por la versión real del baseline/paquete/imagen |
| `_deploy_executor()` | `backend/app/engine.py` | Elige el ejecutor por track (Ansible/BigFix/SCCM/CI-CD/ArgoCD) | task | string | `_rng` | Punto natural de selección del **provider** (`aws-ssm`, `ci-cd`, `gitops`) |
| `build_deployment()` | `backend/app/engine.py:716` | Compone los 5 anillos, excepciones, ITSM, plan de rollback | task, impact, `progress_rings`, … | dict `Deployment` | `assign_impact_to_rings`, `build_ring_plan`, `build_ring_actions`, `build_itsm_change`, `build_rollback_plan` | Mantener como orquestador; delegar la ejecución al provider |
| `RING_DEFS`, `RING_STAGES`, `CANARY_PCT`, `assign_impact_to_rings()`, `order_by_dependency()`, `_scope_nodes()`, `build_ring_plan()` | `backend/app/engine.py` | Definición de anillos por entorno y selección/orden de activos | impact | planes por anillo | `math`, `_rng` | **Reutilizable**; los `assets` deben pasar a llevar `instance_id`/ARN reales |
| `build_lab_results()` | `backend/app/engine.py:216` | Simula la ejecución del MVT (pass/fail aleatorio con `force_pass`) | task, mvt | resultados, veredicto | `_rng` | Sustituir por ejecución real de la suite (CI/CD) o mantener mockeado en la fase 4 |
| `build_mvt()` | `backend/app/engine.py:151` | Selecciona el plan mínimo de pruebas del catálogo | task, impact, catalog | selected/excluded/confidence | — | Reutilizable (regla determinista, no mock de ejecución) |
| `build_prototype()` | `backend/app/engine.py:242` | Métricas y blueprint del lab efímero (valores aleatorios) | task, impact | dict | `_rng` | Sustituir por CloudFormation/Terraform + métricas de CloudWatch |
| `TEST_CATALOG` (21 pruebas) | `backend/app/seed.py` | Catálogo versionado de pruebas | — | lista | — | Migrar a catálogo real en Git |
| `build_audit()` | `backend/app/engine.py:774` | Traza audit-ready de la remediación | artefactos | dict | — | Reutilizable; añadir IDs reales (`CommandId`, `ExecutionId`) |
| `Store._phase_logs()` | `backend/app/store.py:105` | Textos "del agente" por fase | task + artefactos | lista de logs | `engine` | Sustituir por eventos reales del provider |
| `Store.approve_phase()` | `backend/app/store.py:344` | Gate HITL y avance de fase/anillo | `tid` | `TaskDetail` | `engine` | Debe pasar a **encolar** un job asíncrono en lugar de devolver el resultado ya hecho |

### 5.4 Rollback / restauración

| Elemento | Ruta | Responsabilidad | Entrada | Salida | Dependencias | Qué sustituir para AWS |
|---|---|---|---|---|---|---|
| `build_rollback_plan()` | `backend/app/engine.py:571` | Plan por track: `snapshot-restore` (A), `artifact-redeploy` (B), GitOps rollback (C); RTO aleatorio | task, impact | dict `RollbackPlan` | `_rng` | **`AwsRestoreProvider`**: AMI/snapshot EBS (`ec2:CreateSnapshot`/`RegisterImage`), `ssm` downgrade, o rollback de despliegue |
| `Store.rollback()` | `backend/app/store.py:443` | Ejecuta el rollback (logs), decrementa anillo, reabre VI | `tid, reason, trigger` | `TaskDetail` | `engine`, `_rebuild_deploy` | Invocar al provider real y esperar su resultado asíncrono |
| `Store.simulate_incident()` | `backend/app/store.py:480` | Inyecta una anomalía ficticia (error rate 4.7%) y dispara rollback automático | `tid` | `TaskDetail` | `rollback` | **Mantener solo como herramienta de demo**; el disparo real vendría de CloudWatch Alarms |
| `POST /api/tasks/{id}/rollback`, `/simulate-incident` | `backend/app/main.py` | Endpoints de rollback | `tid` | `TaskDetail` | `STORE` | Mismo contrato; respuesta debe volverse asíncrona |

### 5.5 Estados de ejecución y "temporizadores"

- **No existe ningún temporizador ni retardo simulado** (`sleep`, `setTimeout`, `setInterval`,
  `asyncio.sleep`, `BackgroundTasks`): las duraciones son solo el campo `duration_s` de cada paso,
  generado con `rng.randint(...)` en `build_ring_actions()`, y `rto_minutes` en el plan de rollback.
- El "progreso" inicial es artificial: `Store.reset()` reparte fases con `start_phases = [5, 2, 5, 3, 4]`
  y `rings_done = rng.randint(1, 3)` para tareas en fase 6.
- Los IDs son deterministas (`_rng(task_id + sufijo)`), lo que hace la demo reproducible.

---

## 6. Inventario de modelos de datos

No hay ORM ni esquemas Pydantic de dominio: el backend maneja **dicts** y el contrato real está
tipado en `frontend/src/types.ts`. Los únicos modelos Pydantic son dos bodies de request en
`main.py` (`RingPreapproveBody`, `RingAssetsBody`).

| Concepto | Definición backend (productor) | Tipo TS |
|---|---|---|
| Vulnerability (CVE) | `seed.CVE_CATALOG` (tupla: cve, título, cvss, epss, kev, exploit, track, componente, versión) | dentro de `VulnerableItem` |
| Vulnerable Item | `seed.build_records()` | `VulnerableItem` (`types.ts:173`) |
| Instance / CI | `seed.build_cmdb()` + `_std_fields()` | `CI` (`types.ts:57`), `Edge`, `CmdbCiRaw`, `CmdbFieldMap` |
| Patch job / execution | `Store.pipelines[tid]` (dict interno, **no expuesto tal cual**) | proyectado en `TaskDetail` (`types.ts:180`) |
| Remediation Task | `seed.build_records()` + campos añadidos en `Store.list_tasks()` | `Task` (`types.ts:47`) |
| Patch (acciones/anillo) | `engine.build_ring_actions()` / `build_deployment()` | `RingAction`, `Ring`, `RingPlan`, `RingAsset`, `RingDependency`, `RingApproval`, `Deployment` |
| Patch result | `engine.build_lab_results()`, `ring.health`, `build_audit()` | `LabResults`, `Audit` |
| Rollback / restore | `engine.build_rollback_plan()` + `Store.rollback()` | `RollbackPlan`, `RollbackState` |
| Error | **No hay modelo de error**; solo `HTTPException(404)` de FastAPI (`{"detail": "..."}`) | — |
| Impacto / MVT / prototipo | `engine.build_impact_graph/build_mvt/build_prototype` | `ImpactGraph`, `Mvt`, `TestCase`, `Prototype` |
| ITSM Change | `engine.build_itsm_change()` | `ItsmChange`, `ItsmPhase`, `ItsmCtask` |
| Log / actividad | `Store._log()` | `LogEntry` |
| Integraciones | lista hardcodeada en `main.services()` | `Service` |

### Ejemplos reales de JSON que circulan hoy

`GET /api/tasks/RTASK900001` → `task`:

```json
{
  "id": "RTASK900001",
  "vulnerable_item_id": "VIT700001",
  "cve": "CVE-2021-44228",
  "title": "Apache Log4j2 JNDI RCE (Log4Shell)",
  "track": "B",
  "lane": "critical",
  "risk_score": 100,
  "priority": "critical",
  "ci_id": "APP-1001",
  "ci_name": "payments-api",
  "owner": "infra-linux@bank.example",
  "criticality": "critical",
  "environment": "production",
  "sla_due": "2026-06-30T09:00:00Z",
  "change_type": "emergency",
  "exposed": true,
  "component": "log4j-core",
  "vulnerable_version": "2.14.1",
  "created_at": "2026-06-28T09:00:00Z"
}
```

> Nótese que **no hay ningún identificador de instancia real**: `ci_id` es un ID sintético
> (`APP-1001`, `SRV-3001`), no un `i-0123456789abcdef0`.

`artifacts.deployment.rings[0].actions` (mock de parcheo, dominio B):

```json
{
  "from_version": "2.14.1",
  "to_version": "2.14.2",
  "steps": [
    {
      "seq": 1,
      "actor": "Devin",
      "tool": "Terraform + Ansible",
      "command": "terraform apply -target=replica.lab (10 CIs)",
      "output": "Réplica de 10 CIs aprovisionada en «Laboratorio»",
      "status": "ok",
      "why": "Se levanta una réplica efímera (IaC) ...",
      "duration_s": 4
    }
  ]
}
```

`artifacts.deployment.rollback_plan`:

```json
{
  "strategy": "artifact-redeploy (imagen previa)",
  "snapshot_ref": "registry/payments-api:2.14.1",
  "target_version": "2.14.1",
  "from_version": "2.14.2",
  "rto_minutes": 10,
  "auto_trigger": "fallo de post-checks / breach de health-check tras un anillo",
  "tested_in_lab": true,
  "steps": [
    { "actor": "Devin", "tool": "Helm", "command": "helm rollback payments-api <previous-revision>", "desc": "..." }
  ]
}
```

Request bodies existentes:

```json
POST /api/tasks/{id}/rings/{ring}/preapprove   {"approver": null, "note": null}
POST /api/tasks/{id}/rings/{ring}/assets       {"excluded": ["SRV-3001", "MW-3002"]}
```

---

## 7. Inventario de endpoints (API actual)

Todos bajo el prefijo `/api`; `main.py` es el único router. Datos: **100% simulados**.

| Método | Ruta | Handler (`main.py`) | Servicio | Request | Response | HTTP | Datos | Consumidor |
|---|---|---|---|---|---|---|---|---|
| GET | `/api/health` | `health` | — | — | `{"status":"ok"}` | 200 | mock | — (operativa) |
| GET | `/api/overview` | `overview` | `STORE.overview()` | — | KPIs, funnel, distribuciones, SLA, CMDB | 200 | mock | `Dashboard.tsx` |
| GET | `/api/tasks` | `tasks` | `STORE.list_tasks()` | — | `Task[]` (orden por riesgo) | 200 | mock | `Tasks.tsx`, `Dashboard.tsx` |
| GET | `/api/tasks/{tid}` | `task_detail` | `STORE.task_detail()` | path | `TaskDetail` | 200 / 404 | mock | `TaskDetail.tsx` |
| POST | `/api/tasks/{tid}/approve` | `approve` | `STORE.approve_phase()` | path, **sin body** | `TaskDetail` | 200 / 404 | mock | `TaskDetail.tsx` |
| POST | `/api/tasks/{tid}/rings/{ring_no}/preapprove` | `preapprove_ring` | `STORE.preapprove_ring()` | `RingPreapproveBody` (opcional) | `TaskDetail` | 200 / 404 / 422 | mock | `TaskDetail.tsx` |
| POST | `/api/tasks/{tid}/rings/{ring_no}/assets` | `update_ring_assets` | `STORE.update_ring_assets()` | `RingAssetsBody` | `TaskDetail` | 200 / 404 / 422 | mock | `TaskDetail.tsx` |
| POST | `/api/tasks/{tid}/rollback` | `rollback` | `STORE.rollback(trigger="manual")` | path | `TaskDetail` | 200 / 404 | mock | `TaskDetail.tsx` |
| POST | `/api/tasks/{tid}/simulate-incident` | `simulate_incident` | `STORE.simulate_incident()` | path | `TaskDetail` | 200 / 404 | mock | `TaskDetail.tsx` |
| GET | `/api/cmdb` | `cmdb` | `STORE.cmdb_summary()` + servicios | — | `{summary, services}` | 200 | mock | `Cmdb.tsx` |
| GET | `/api/cmdb/summary` | `cmdb_summary` | idem | — | `CmdbSummary` | 200 | mock | — |
| GET | `/api/cmdb/cis` | `cmdb_cis` | `STORE.cmdb_cis()` | query `cls, track, crit, q, limit, offset` | `{total, items}` | 200 | mock | `Cmdb.tsx` |
| GET | `/api/cmdb/cis/{ci_id}/raw` | `cmdb_ci_raw` | `STORE.cmdb_ci_raw()` | path | `CmdbCiRaw` | 200 / 404 | mock | `CmdbRecordModal.tsx` |
| GET | `/api/cmdb/tables` | `cmdb_tables` | `seed.cmdb_manifest()` | — | `CmdbTables` | 200 | mock (fichero) | `Cmdb.tsx` |
| GET | `/api/cmdb/graph/{service_id}` | `cmdb_graph` | `STORE.cmdb_graph()` | path | `{nodes, edges}` | 200 (vacío si no existe) | mock | `Cmdb.tsx` |
| GET | `/api/catalog` | `catalog` | `STORE.catalog` | — | `TestCase[]` | 200 | mock | `Catalog.tsx` |
| GET | `/api/vulnerable-items` | `vitems` | `STORE.vulnerable_items` | — | `VulnerableItem[]` | 200 | mock | **ninguno** |
| GET | `/api/findings` | `findings` | `STORE.findings` | — | findings | 200 | mock | **ninguno** |
| GET | `/api/activity` | `activity` | `STORE.activity` | — | `LogEntry[]` | 200 | mock | `Dashboard.tsx` |
| GET | `/api/services` | `services` | lista hardcodeada | — | `Service[]` | 200 | **hardcoded** | `Integrations.tsx` |
| POST | `/api/reset` | `reset` | `STORE.reset()` | — | `{"status":"reset"}` | 200 | mock | **ninguno** (útil en demo) |
| GET | `/{full_path:path}` | `spa` | FS | — | `index.html` / fichero | 200 | — | navegador |

Observaciones relevantes para AWS:
- **No hay autenticación ni autorización** en ningún endpoint, y CORS es `*`.
- Los POST no tienen idempotencia (ni `Idempotency-Key`), ni versión/ETag para evitar
  aprobaciones dobles por doble clic o dos pestañas.
- Ninguna ruta devuelve 202/`Location` para operaciones largas.

---

## 8. Configuración

| Aspecto | Estado actual |
|---|---|
| Variables de entorno | **Ninguna**. `grep` de `os.environ` / `getenv` / `process.env` / `import.meta.env` en `backend/app`, `frontend/src` y `scripts` → 0 resultados. La única lectura de entorno es `os.path` para localizar `backend/static` y `data/cmdb`. |
| Ficheros de configuración | `frontend/vite.config.ts` (puerto 5173, proxy `/api` → `localhost:8080`, `allowedHosts: true`), `tsconfig*.json`, `.oxlintrc.json`, `tailwind.config.js`, `postcss.config.js`, `backend/requirements.txt`. **No hay `.env`, `.env.example`, `settings.py`, `config.yaml` ni perfiles por entorno.** |
| Gestión de secretos | **No existe** (tampoco hay secretos, porque no hay integraciones reales). |
| Configuración por entorno | **No existe**: la URL del backend está implícita en el proxy de Vite y en rutas relativas `/api/...` de `api.ts`. |
| Credenciales / proveedores externos | Ninguna. Los "sistemas conectados" de `GET /api/services` son una lista de texto. `SN_INSTANCE = "https://bankdev.service-now.com"` en `seed.py` es solo un string para construir enlaces ficticios. |
| AWS SDK | **No hay ninguna dependencia** (`requirements.txt`: fastapi, uvicorn[standard], pydantic; `package.json`: sin `aws-sdk`). |
| Datos con aspecto AWS (solo texto) | `seed.LOCATIONS` (`"AWS eu-west-1"`, `"Azure West Europe"`), `seed.CLOUD_KINDS` (`AWS Lambda`, `EKS Node Group`, `RDS Instance`…), `"EKS eu-west-1"`. Ninguno se usa para llamar a AWS. |

### Dónde debería vivir la configuración AWS

| Necesidad | Lugar propuesto |
|---|---|
| Región, cuenta, rol a asumir, perfil, endpoints | Nuevo `backend/app/config.py` con `pydantic-settings` (`MSR_AWS_REGION`, `MSR_AWS_ROLE_ARN`, `MSR_PATCH_PROVIDER=mock\|aws-ssm`, `MSR_DRY_RUN=true`) + `.env.example` sin valores |
| Selección de provider (mock vs AWS) | Factoría en `backend/app/providers/__init__.py`, inyectada en `Store` |
| Allowlist de instancias / tags permitidos | Fichero versionado `backend/app/policy/allowlist.yaml` (tags obligatorios, `instance_id` permitidos, entornos habilitados) |
| Identificadores de instancia | Nuevos campos en el modelo de CI (`instance_id`, `account_id`, `region`, `tags`) → `data/cmdb` y `types.ts` |
| Documentos/baselines SSM permitidos | Constante allowlist en el provider (`AWS-RunPatchBaseline`, `AWS-RunShellScript` solo si es imprescindible) |
| Credenciales | **Nunca en el repo ni en el frontend**: rol de instancia/IRSA o `AssumeRole` en el backend; en local, perfil de AWS CLI |

---

## 9. Persistencia y ejecución asíncrona

- **Cómo se guardan los trabajos:** en `Store.pipelines` (`dict` en memoria del proceso Uvicorn),
  creado en `Store.reset()` al importar `store.py`. Los artefactos se **recalculan** con
  `_rebuild_deploy()` cada vez que cambia algo, en lugar de acumular un histórico de ejecución.
- **¿Sobreviven a un reinicio?** **No.** Un reinicio (o un `--reload` de uvicorn) vuelve al estado
  inicial sintético. Además, con varios workers de Uvicorn/Gunicorn cada proceso tendría su propio
  `STORE` (estado incoherente).
- **Cola / worker / scheduler / polling:** **nada de eso**. Todo se resuelve dentro del request
  HTTP; el frontend no hace polling.
- **Cómo representar una operación AWS de varios minutos:** el patrón mínimo compatible con la
  arquitectura actual es
  1. `POST /approve` valida, crea un `PatchJob` (`id`, `task_id`, `ring`, `state`,
     `provider_ref` = `CommandId` de SSM, `started_at`, `steps[]`) en estado `queued`, y devuelve
     **202** con el job;
  2. un worker (o `BackgroundTasks`/`asyncio.Task` para la PoC) llama al provider y hace polling de
     `ssm:GetCommandInvocation`, actualizando `state`: `queued → running → succeeded | failed → rolling_back → rolled_back`;
  3. el frontend consulta `GET /api/patch-jobs/{id}` (o SSE/WebSocket) hasta un estado terminal.
     Hoy `TaskDetail.tsx` no tiene ningún mecanismo de refresco: hay que añadirlo.
- **Cómo se evita hoy lanzar dos operaciones sobre la misma instancia:** **no se evita**. No hay
  lock, ni estado `in_progress` bloqueante, ni comprobación de jobs abiertos: dos POST simultáneos
  a `/approve` incrementarían `rings_done` dos veces (el único gate es la pre-aprobación del anillo,
  que no es un lock). Se necesita un lock por `instance_id` (fila `patch_job` con índice único
  parcial sobre instancia + estado activo, o `DynamoDB` conditional write).

---

## 10. Resultados de tests, lint, type checking y build

Ejecutado en Ubuntu 22.04, Python 3.10.12, Node 20.18.1, sobre la rama `devin/1783593359-msr-platform`.

| Comprobación | Comando | Resultado |
|---|---|---|
| Tests | — | **No existen tests** en el repo (ni backend ni frontend). Nada que ejecutar. |
| Backend: import + arranque | `pip install -r requirements.txt` + `python -c "import app.main"` | **OK**. `STORE`: 180 CIs, 138 relaciones, 5 tasks. |
| Backend: smoke de API | `uvicorn app.main:app --port 8080` + `curl` | **OK**: `/api/health` 200, `/api/overview` 200, `/api/tasks` 200, `/api/tasks/RTASK900001` 200, `POST .../approve` 200, `/api/tasks/NOPE` 404. |
| Backend: lint / type check | — | **No configurado** (sin ruff/flake8/black/mypy). |
| Frontend: lint | `npm run lint` (`oxlint`) | **8 warnings, 0 errores**, exit code 0 — todos `react(only-export-components)` en `src/ui.tsx` (6) y `src/view.tsx` (2). **Preexistentes.** |
| Frontend: type checking | `npx tsc -b` | **OK**, sin errores. |
| Frontend: build | `npm run build` (`tsc -b && vite build`) | **OK** en ~4,4 s. 754 módulos; `dist/assets/index-*.js` 823,6 kB (gzip 246,7 kB) con el aviso de Vite de chunk > 500 kB. **Preexistente.** |

### Fallo preexistente encontrado (no corregido)

`npm run lint` **falla con `Error: Cannot find native binding`** tras un `npm install` limpio:
npm no instala el paquete opcional `@oxlint/binding-linux-x64-gnu` (bug conocido
[npm/cli#4828](https://github.com/npm/cli/issues/4828)). Workaround usado para poder ejecutar el
lint: `npm i --no-save @oxlint/binding-linux-x64-gnu`. No se ha tocado `package.json` ni el
lockfile. Es un problema de entorno/instalación, no del código.

Otras observaciones no corregidas: `types.ts` usa `any` en `LabResults.patch_tests` / `app_tests`;
`TaskDetail.tsx` desactiva la regla de dependencias del `useEffect`.

---

## 11. Puntos concretos de integración con AWS

Orden recomendado (de menor a mayor esfuerzo), sin rediseñar la aplicación:

1. **Identidad del activo.** Añadir `instance_id`, `account_id`, `region` y `tags` al modelo de CI
   (`seed._std_fields()` / `data/cmdb/normalized_cis.json` / `types.ts:CI`) y propagarlos a
   `RingAsset` (`engine.build_ring_plan()`), que es la lista de activos que llega a la UI y al
   despliegue. Sin esto no hay a qué apuntar.
2. **Frontera de ejecución.** Extraer una interfaz `PatchProvider` y mover el contenido de
   `engine.build_ring_actions()` a `MockPatchProvider`. `engine.build_deployment()` deja de
   fabricar los pasos y pasa a **leer** los pasos que devuelve el provider.
3. **Job asíncrono.** `Store.approve_phase()` (rama `deployment`) crea un `PatchJob` en vez de
   avanzar `rings_done` de inmediato; `rings_done` avanza cuando el job termina en `succeeded`.
4. **Rollback.** Igual con `RestoreProvider` a partir de `engine.build_rollback_plan()` y
   `Store.rollback()`.
5. **Persistencia.** Sustituir `Store.pipelines` por una tabla `patch_job` (SQLite/Postgres o
   DynamoDB) con lock por instancia; el resto del `Store` puede seguir siendo caché en memoria.
6. **Configuración y seguridad.** `config.py` + allowlist + autenticación en los POST + `MSR_DRY_RUN`.

### Ficheros existentes a modificar

| Fichero | Cambio |
|---|---|
| `msr-platform/backend/app/engine.py` | Extraer `build_ring_actions()` y `build_rollback_plan()` a providers; `build_deployment()` acepta los pasos/estado del job en vez de generarlos |
| `msr-platform/backend/app/store.py` | `approve_phase()` y `rollback()` delegan en el provider y crean/consultan `PatchJob`; `_rebuild_deploy()` respeta el estado persistido |
| `msr-platform/backend/app/main.py` | Nuevas rutas de jobs (`GET /api/patch-jobs/{id}`, `GET /api/tasks/{id}/patch-jobs`), respuesta 202 en `approve`, 409 en conflicto, auth en los POST |
| `msr-platform/backend/app/seed.py` | Añadir campos AWS al CI y dejar de ser la única fuente de inventario (mock detrás de un flag) |
| `msr-platform/backend/requirements.txt` | `boto3`, `pydantic-settings` (y `sqlalchemy`/`alembic` si se elige SQL) |
| `msr-platform/frontend/src/types.ts` | `CI.instance_id/region/account_id/tags`, `PatchJob`, estados nuevos |
| `msr-platform/frontend/src/api.ts` | Métodos de jobs + refresco (polling/SSE) |
| `msr-platform/frontend/src/pages/TaskDetail.tsx` | Estado "en ejecución", progreso del job, manejo de errores (`try/catch`), refresco |
| `msr-platform/frontend/src/pages/Cmdb.tsx` | Mostrar `instance_id`/región/cuenta |
| `msr-platform/README.md` | Documentar el flag de provider y la configuración |

### Ficheros nuevos propuestos

```
backend/app/config.py                        # settings (pydantic-settings), sin valores por defecto peligrosos
backend/app/providers/__init__.py            # factoría get_patch_provider() / get_restore_provider()
backend/app/providers/base.py                # PatchProvider, RestoreProvider (Protocol/ABC) + DTOs
backend/app/providers/mock_patch.py          # MockPatchProvider  (mueve build_ring_actions)
backend/app/providers/aws_ssm_patch.py       # AwsSsmPatchProvider (boto3 ssm/ec2)
backend/app/providers/mock_restore.py        # MockRestoreProvider (mueve build_rollback_plan)
backend/app/providers/aws_restore.py         # AwsRestoreProvider  (AMI/snapshot/downgrade)
backend/app/jobs.py                          # PatchJob, máquina de estados, lock por instancia
backend/app/policy/allowlist.yaml            # instancias/tags/entornos permitidos
backend/app/repository.py                    # persistencia de jobs (SQLite/DynamoDB)
backend/tests/…                              # ver sección 13
.env.example                                 # nombres de variables, sin valores
```

### Boceto de la abstracción (no implementado)

```python
# backend/app/providers/base.py
class PatchProvider(Protocol):
    name: str
    def start(self, req: PatchRequest) -> PatchExecution: ...        # devuelve provider_ref (p.ej. SSM CommandId)
    def poll(self, ref: str) -> PatchExecution: ...                  # running | succeeded | failed + steps/output
    def cancel(self, ref: str) -> None: ...

class RestoreProvider(Protocol):
    def plan(self, task, ring) -> RestorePlan: ...
    def start(self, req: RestoreRequest) -> RestoreExecution: ...
    def poll(self, ref: str) -> RestoreExecution: ...

@dataclass(frozen=True)
class PatchRequest:
    task_id: str; ring: int; targets: list[Target]   # Target = instance_id + account + region + tags
    document: str                                    # p.ej. "AWS-RunPatchBaseline" (allowlist)
    parameters: dict[str, list[str]]                 # validado contra el documento, nunca texto libre
    dry_run: bool
```

`AwsSsmPatchProvider` usaría `ssm:SendCommand` con `Targets` por tag o `InstanceIds` de la
allowlist, `ssm:GetCommandInvocation` para el polling, `ec2:DescribeInstances` para verificar
estado/tags antes de actuar y `ec2:CreateSnapshot`/`RegisterImage` (o `ssm` downgrade) para el
`AwsRestoreProvider`. `MSR_DRY_RUN=true` debería ser el valor por defecto.

---

## 12. Riesgos de seguridad

| # | Riesgo | Situación actual | Mitigación antes de conectar AWS |
|---|---|---|---|
| 1 | **Credenciales AWS en el frontend** | No hay credenciales, pero tampoco hay backend "de confianza": cualquiera con acceso a la SPA puede llamar a la API. Riesgo real si alguien decide usar el SDK en el navegador o exponer un `import.meta.env.VITE_AWS_*` | Todas las llamadas AWS solo en el backend con rol de instancia/IRSA/`AssumeRole`; prohibir cualquier `VITE_AWS_*`; regla de lint/CI que lo detecte |
| 2 | **Ejecución de comandos arbitrarios** | Hoy los `command` son texto. Al conectar SSM, el mismo patrón de interpolación (`f"install {comp}-{fixed}"` con `component`/`vulnerable_version` del dato) se convertiría en inyección de comandos si se usa `AWS-RunShellScript` | Usar solo documentos SSM de una allowlist (preferible `AWS-RunPatchBaseline`), parámetros tipados y validados, **nunca** concatenar strings de entrada en un script |
| 3 | **Parámetros proporcionados por el usuario** | `POST .../assets` acepta cualquier `excluded: string[]` sin validar que los IDs pertenezcan al anillo; los `path params` no se validan más allá de "existe la tarea" | Validar pertenencia al anillo, tipos y rangos (`ring_no` 1-5) con Pydantic; 422/409 explícitos |
| 4 | **Selección libre de instancias** | Los activos salen del Impact Graph calculado en servidor (bien), pero no hay allowlist ni verificación de tags/entorno; y `simulate_incident`/`rollback` se pueden invocar sobre cualquier tarea | Allowlist explícita de `instance_id`/tags/cuentas/entornos + comprobación en el provider antes de `SendCommand` |
| 5 | **Escalada de privilegios** | Sin autenticación ni roles: la "pre-aprobación Human-Driven" y la aprobación HITL son botones sin identidad (el `approver` se rellena con `task.owner` por defecto) | Autenticación (SSO/OIDC), rol y separación de funciones (4-ojos real), rol IAM de mínimos privilegios por entorno, sin `ssm:*`/`ec2:*` amplios |
| 6 | **Registro accidental de secretos** | `Store._log()` guarda los `command`/`output` completos en memoria y los devuelve al frontend; si un comando real llevara tokens o parámetros sensibles, quedarían en la UI y en el informe de auditoría | Redacción/allowlist de campos antes de loguear; nunca pasar secretos como parámetro de comando (usar SSM Parameter Store/Secrets Manager por referencia) |
| 7 | **Falta de allowlist de instancias** | No existe | Ver #4; además `MSR_DRY_RUN` por defecto y confirmación adicional para entornos productivos |
| 8 | **Ausencia de validación de estado y de concurrencia** | `approve_phase()` no comprueba si hay una operación en curso; doble clic o dos pestañas avanzan dos anillos; sin idempotencia ni locks; estado en memoria por proceso | Lock por instancia + estado `in_progress` persistido + `Idempotency-Key` + 409 en conflicto + un solo worker o coordinación externa |
| 9 | CORS `allow_origins=["*"]` sin auth | Cualquier web puede invocar los POST del backend local | Restringir orígenes y exigir auth |
| 10 | Sin auditoría fuera de proceso | La traza de auditoría (`build_audit`) se pierde al reiniciar | Persistir evidencia (S3/CloudTrail + tabla de jobs) |

---

## 13. Tests

**Estado actual: no hay ni un test.** No existen `pytest`, `vitest`, `jest`, ni workflows de CI.
Tampoco hay dependencias externas simuladas en tests (porque no hay tests): los "mocks" del repo
son *datos de demo* en producción, no dobles de prueba.

| Categoría | Detalle |
|---|---|
| Tests relacionados con el flujo | Ninguno |
| Cobertura de los mocks | 0% verificada automáticamente |
| Tests que deberían mantenerse al introducir AWS | Los que se escriban ahora sobre la **lógica de negocio pura**: `seed._risk_score`, `seed.assign_lane`, `seed._priority_label`, `engine.build_impact_graph`, `engine.build_mvt`, `engine.order_by_dependency`/`assign_impact_to_rings`, `engine._fixed_version`, `store.sla_state` y la máquina de fases de `Store.approve_phase` (con `MockPatchProvider`) |
| Tests nuevos necesarios | (a) contrato `PatchProvider`/`RestoreProvider` ejecutado contra mock y contra AWS con `moto`/`botocore.stub`; (b) máquina de estados del `PatchJob` (incluido fallo → rollback); (c) allowlist e inyección de parámetros (casos maliciosos); (d) concurrencia: dos aprobaciones simultáneas → 409; (e) persistencia: job sobrevive a reinicio; (f) API: 202/404/409/422; (g) frontend: render de estados de job y manejo de error de `api.ts` |
| Dependencias externas a simular en tests | AWS SSM/EC2 (`moto` o stubs de botocore), reloj (`NOW` está fijado a `datetime(2026,7,6,9,0,0)` en `seed.py` — conviene inyectarlo), aleatoriedad (ya determinista por semilla), y ServiceNow si se integra |

---

## 14. Preguntas pendientes

### A. Deducible del repositorio (ya respondido en este documento)

- ¿Dónde se simula el parcheo? `engine.build_ring_actions()`. ¿Y el rollback? `build_rollback_plan()` + `Store.rollback()`.
- ¿Hay persistencia, cola o temporizadores? No.
- ¿Hay AWS SDK, variables de entorno o secretos? No.
- ¿Qué endpoints existen y quién los consume? Sección 7.
- ¿Qué modelos circulan? Secciones 6 y `frontend/src/types.ts`.

### B. Debe responder el propietario de la cuenta AWS

1. ¿Cuenta(s) y región(es) objetivo de la PoC? ¿Hay una cuenta *sandbox* dedicada?
2. ¿Las instancias EC2 objetivo están **gestionadas por SSM** (agente instalado, perfil IAM,
   endpoints/NAT)? ¿Cuántas y con qué SO?
3. ¿Qué mecanismo de parcheo se autoriza: **Patch Manager con baselines existentes**,
   `AWS-RunPatchBaseline` puntual, o comandos propios? ¿Existen baselines y patch groups ya definidos?
4. ¿Cómo se identifican los activos: `instance_id` explícito, tags (`Environment`, `PatchGroup`,
   `Owner`) o Resource Groups?
5. ¿Qué **rol IAM** puede asumir la aplicación y con qué permisos mínimos? ¿Hay SCPs/permission
   boundaries o ventanas de mantenimiento obligatorias?
6. ¿Se permite crear snapshots/AMI para rollback? ¿Con qué retención y coste asumible?
7. ¿Reinicios permitidos? ¿En qué ventanas y con qué aprobación?
8. ¿Existen CloudWatch Alarms/SLOs que puedan disparar el rollback automático?
9. ¿Dónde debe desplegarse el backend (ECS/EKS/EC2/Lambda) y cómo obtiene credenciales?
10. ¿Requisitos de auditoría/retención de evidencia (CloudTrail, S3, DORA)?

### C. Decisiones de arquitectura pendientes

1. ¿Ejecución vía **SSM Run Command**, **Patch Manager (Maintenance Windows)** o **Automation
   (SSM Documents)**? Determina el `provider_ref` y el modelo de polling.
2. Asincronía: `BackgroundTasks` (suficiente para PoC, se pierde al reiniciar) vs worker externo
   (Celery/RQ/ECS task) vs Step Functions.
3. Persistencia de jobs: SQLite (PoC), Postgres/RDS o DynamoDB (lock condicional nativo).
4. Refresco de la UI: polling simple (más barato) vs SSE/WebSocket.
5. ¿Se mantiene el mock como provider seleccionable por configuración (recomendado) o se sustituye?
6. Granularidad de los anillos con activos reales: ¿los 5 anillos actuales por entorno se mapean a
   *patch groups*/tags reales? ¿Quién define la pertenencia?
7. Autenticación/autorización y trazabilidad del aprobador (¿SSO corporativo?).
8. ¿Sigue ServiceNow siendo el plano de control (y entonces la app consume su Table API), o la app
   es autónoma en la PoC?
9. Multi-cuenta/multi-región: ¿`AssumeRole` por cuenta o una sola cuenta en la PoC?
10. ¿Dónde vive el catálogo de pruebas y quién ejecuta el MVT real (CI/CD del cliente)?

---

## 15. Propuesta mínima de evolución hacia AWS

Sin rediseñar la aplicación, 4 incrementos:

**Paso 0 — preparación (sin AWS).** Añadir `instance_id`/`region`/`account_id`/`tags` al CI y a
`RingAsset`; crear `config.py` con `MSR_PATCH_PROVIDER=mock` y `MSR_DRY_RUN=true`; extraer
`PatchProvider`/`RestoreProvider` y mover el mock a `MockPatchProvider`/`MockRestoreProvider` sin
cambiar el JSON que consume el frontend. Añadir los primeros tests sobre lógica pura.

**Paso 1 — job asíncrono con el mock.** Introducir `PatchJob` persistido + lock por instancia,
`POST /approve` → 202 + `GET /api/patch-jobs/{id}`, y polling en `TaskDetail.tsx`. Todo sigue
siendo mock: se valida la máquina de estados sin tocar AWS.

**Paso 2 — `AwsSsmPatchProvider` en dry-run.** `boto3` + allowlist + un único documento SSM
(`AWS-RunPatchBaseline`), con `MSR_DRY_RUN=true`: se resuelven targets y se validan permisos y
tags, pero no se envía el comando. Sobre una sola instancia de sandbox.

**Paso 3 — ejecución real acotada.** Desactivar `dry_run` solo para el anillo 1 (una instancia
etiquetada `msr-poc=true`), con snapshot previo (`AwsRestoreProvider`), post-checks reales y
rollback probado. El resto de anillos sigue en mock hasta validar.

Lo que **no** hace falta cambiar: el modelo de 6 fases, los gates HITL, el Impact Graph, el MVT, la
selección/orden de activos por anillo, el informe de auditoría y toda la UI salvo el estado de job.

---

## Apéndice estructurado

```yaml
application:
  frontend:
    framework: "React 19 + TypeScript + Vite 5 + Tailwind 3 (react-router-dom 7, reactflow 11, recharts 3)"
    entrypoint: "msr-platform/frontend/index.html → src/main.tsx → src/App.tsx"
    patch_trigger_component: "msr-platform/frontend/src/pages/TaskDetail.tsx (approve() → botón «Aprobar y desplegar anillo»; también rollback() y simulate())"
    api_client: "msr-platform/frontend/src/api.ts (objeto `api`, fetch nativo, rutas relativas /api/*, proxy de Vite a :8080)"
  backend:
    framework: "FastAPI 0.115.6 + Uvicorn 0.34 + Pydantic 2.10.4 (Python 3.10+)"
    entrypoint: "msr-platform/backend/app/main.py (app = FastAPI); uvicorn app.main:app --port 8080"
    patch_endpoint: "POST /api/tasks/{tid}/approve (+ /rings/{ring_no}/preapprove, /rings/{ring_no}/assets, /rollback, /simulate-incident)"
    patch_handler: "main.approve() → store.STORE.approve_phase(tid)"
    patch_service: "store.Store.approve_phase / _rebuild_deploy / rollback / simulate_incident"
    mock_implementation: "engine.build_ring_actions() (pasos y comandos ficticios), engine.build_deployment(), engine.build_rollback_plan(), engine.build_lab_results(), engine.build_prototype(), seed.py (CMDB, CVE_CATALOG, findings, VI, tasks, TEST_CATALOG)"
  persistence:
    technology: "Ninguna base de datos: estado en memoria (singleton store.STORE) + CMDB sintética en JSON versionado (msr-platform/data/cmdb/*.json)"
    patch_job_storage: "store.Store.pipelines[task_id] = {phase_index, statuses, rings_done, rolled_back_rings, ring_preapprovals, ring_exclusions, rollback, artifacts, logs} — volátil, no sobrevive a un reinicio"
  deployment:
    method: "Solo ejecución local; sin CI/CD, sin Docker, sin IaC. Modo todo-en-uno: SPA compilada a backend/static y servida por FastAPI"
    relevant_files:
      - "msr-platform/scripts/dev.sh"
      - "msr-platform/scripts/build.sh"
      - "msr-platform/backend/requirements.txt"
      - "msr-platform/frontend/package.json"
      - "msr-platform/frontend/vite.config.ts"
      - "msr-platform/backend/app/main.py (mount de backend/static + catch-all SPA)"

integration_surface:
  mock_files_to_replace:
    - "msr-platform/backend/app/engine.py::build_ring_actions  (parcheo, reinicio, post-checks)"
    - "msr-platform/backend/app/engine.py::build_rollback_plan (restauración)"
    - "msr-platform/backend/app/engine.py::build_lab_results   (validación posterior)"
    - "msr-platform/backend/app/engine.py::build_prototype     (lab efímero / métricas)"
    - "msr-platform/backend/app/engine.py::_deploy_executor / _fixed_version / _prev_version"
    - "msr-platform/backend/app/seed.py::build_cmdb / _scale_estate / servicenow_record (inventario de instancias)"
    - "msr-platform/backend/app/seed.py::CVE_CATALOG / build_records (detección de vulnerabilidades)"
    - "msr-platform/backend/app/store.py::approve_phase / rollback / simulate_incident / _phase_logs"
    - "msr-platform/backend/app/main.py::services (lista de integraciones hardcodeada)"
  interfaces_already_available:
    - "engine.PHASES / PHASE_IDS (máquina de 6 fases)"
    - "engine.RING_DEFS / RING_STAGES / assign_impact_to_rings / order_by_dependency (anillos y alcance)"
    - "engine.build_impact_graph / build_mvt / build_audit (lógica reutilizable)"
    - "seed._risk_score / assign_lane / _priority_label (priorización)"
    - "store.Store (fachada única de estado y acciones)"
    - "frontend/src/api.ts + types.ts (contrato tipado extremo a extremo)"
  recommended_new_interfaces:
    - "PatchProvider (start/poll/cancel) + PatchRequest/PatchExecution/Target"
    - "MockPatchProvider (mueve build_ring_actions sin cambiar el JSON)"
    - "AwsSsmPatchProvider (ssm:SendCommand AWS-RunPatchBaseline, ssm:GetCommandInvocation, ec2:DescribeInstances)"
    - "RestoreProvider (plan/start/poll)"
    - "MockRestoreProvider (mueve build_rollback_plan)"
    - "AwsRestoreProvider (snapshot EBS / AMI / downgrade vía SSM)"
    - "PatchJob + repositorio persistente con lock por instance_id"
    - "InstanceAllowlist / PolicyGuard (validación previa a cualquier llamada AWS)"
  recommended_new_files:
    - "msr-platform/backend/app/config.py"
    - "msr-platform/backend/app/providers/{__init__,base,mock_patch,aws_ssm_patch,mock_restore,aws_restore}.py"
    - "msr-platform/backend/app/jobs.py"
    - "msr-platform/backend/app/repository.py"
    - "msr-platform/backend/app/policy/allowlist.yaml"
    - "msr-platform/backend/tests/{test_risk,test_impact_graph,test_phases,test_provider_contract,test_jobs,test_allowlist}.py"
    - "msr-platform/.env.example"
  configuration_files:
    existing:
      - "msr-platform/frontend/vite.config.ts (proxy /api → :8080)"
      - "msr-platform/frontend/tsconfig*.json, .oxlintrc.json, tailwind.config.js, postcss.config.js"
      - "msr-platform/backend/requirements.txt"
    missing_and_needed:
      - "config.py + .env.example (MSR_PATCH_PROVIDER, MSR_DRY_RUN, MSR_AWS_REGION, MSR_AWS_ROLE_ARN)"
      - "allowlist de instancias/tags/entornos"
      - "requirements con boto3 / pydantic-settings"
  test_files:
    existing: "ninguno"
    recommended: "msr-platform/backend/tests/** (pytest) y, opcionalmente, vitest para frontend/src/api.ts y TaskDetail"

current_patch_flow:
  request: "POST /api/tasks/{tid}/approve sin body (previa POST /rings/{ring}/preapprove). Disparado por TaskDetail.tsx → api.approve()"
  processing: "main.approve() → Store.approve_phase(): si la fase es `deployment`, verifica la pre-aprobación del siguiente anillo, incrementa rings_done y llama a _rebuild_deploy() → engine.build_deployment() → engine.build_ring_actions() (pasos ficticios: snapshot/patch/install/systemctl restart o bump+build+helm o rebuild imagen+argocd, más 4 post-checks). Al completar los 5 anillos: task.status=remediated y vulnerable_item.status=fixed"
  simulated_delay: "Ninguno. No hay sleep, temporizadores ni tareas en background; solo el campo `duration_s` (rng.randint) de cada paso y `rto_minutes` en el plan de rollback"
  state_updates: "En memoria: Store.pipelines[tid] (phase_index, statuses, rings_done, rolled_back_rings, preaprobaciones, exclusiones, rollback, artifacts, logs) + mutación de Store.tasks y Store.vulnerable_items; feed global Store.activity (máx. 200)"
  response: "200 con el TaskDetail completo (task, vulnerable_item, phases, artifacts, logs, rings_done, sla). 404 si la tarea no existe. Los errores funcionales se devuelven como log dentro de un 200"
  frontend_refresh: "Sin polling ni WebSocket: setD(respuesta del POST). Las demás vistas cargan solo al montar; POST /api/reset reinicia la demo"

open_questions:
  repository:
    - "¿Se conserva el mock como provider seleccionable (recomendado) o se elimina?"
    - "¿Se acepta añadir persistencia (SQLite/Dynamo) al backend de la PoC?"
    - "¿Se añaden tests y CI (hoy no hay ninguno) como parte de la integración?"
    - "¿El handoff/documentación debe vivir en msr-platform/ o en la raíz del repo (hoy raíz = CardDemo COBOL)?"
    - "¿Se corrige el fallo de instalación de oxlint (binding nativo) en package.json/CI?"
  aws:
    - "Cuenta(s), región(es) y sandbox disponible"
    - "Instancias EC2 gestionadas por SSM: cuántas, SO, agente y endpoints"
    - "Mecanismo autorizado: Patch Manager con baselines vs Run Command vs Automation"
    - "Identificación de activos: instance_id explícito o tags/PatchGroup"
    - "Rol IAM y permisos mínimos; SCPs, ventanas de mantenimiento y aprobaciones"
    - "¿Snapshots/AMI permitidos para rollback? retención y coste"
    - "¿Reinicios permitidos y en qué ventanas?"
    - "CloudWatch Alarms/SLOs para rollback automático"
    - "Dónde se despliega el backend y cómo obtiene credenciales"
    - "Requisitos de auditoría y retención de evidencia"
  architecture:
    - "Modelo de asincronía: BackgroundTasks vs worker externo vs Step Functions"
    - "Almacén de jobs y estrategia de lock por instancia"
    - "Polling vs SSE/WebSocket para el refresco de la UI"
    - "Mapeo de los 5 anillos a patch groups/tags reales"
    - "Autenticación, autorización y trazabilidad del aprobador (4-ojos real)"
    - "Multi-cuenta/multi-región (AssumeRole) desde el inicio o después"
    - "¿ServiceNow como plano de control real o app autónoma en la PoC?"
    - "Quién ejecuta el MVT real y dónde vive el catálogo de pruebas"
```
