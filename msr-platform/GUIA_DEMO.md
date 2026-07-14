# Guía total · Machine Speed Remediation Platform

> Guía completa para **entender, ejecutar y presentar** la plataforma en una demo de cliente
> (sector banca). Incluye: qué es, arquitectura, cada pantalla, el guion de demo paso a paso,
> los mensajes clave y las preguntas frecuentes.

---

## 0. El pitch en 30 segundos

> "Deloitte no solo ha diseñado el **modelo operativo de patching** sobre ServiceNow: ha
> construido la **herramienta que lo ejecuta**. Esta plataforma demuestra, extremo a extremo,
> cómo un agente de IA (**Devin**) hace el trabajo técnico de cada fase —analizar el impacto,
> proponer las pruebas mínimas, ejecutarlas, levantar entornos y generar la evidencia— mientras
> **ServiceNow gobierna** y **un humano aprueba** cada paso. Resultado: remediar en **minutos/horas**
> lo que hoy tarda **días/semanas**, con trazabilidad audit-ready para DORA."

**Idea de oro:** ServiceNow decide y audita · **Devin razona y ejecuta** · las herramientas del
cliente (SCCM/BigFix/Ansible/CI-CD) despliegan. Devin es el **acelerador** en las fases tempranas,
donde la velocidad es crítica frente a atacantes que ya usan IA.

---

## 1. Qué es (y qué no es)

- **Es** un mockup **funcional y navegable** que reproduce el ciclo de 6 fases del documento
  *"Bajada a nivel Patching Ops"* con datos sintéticos **realistas** y un flujo interactivo
  (aprobar fases, ver al agente trabajar, recorrer el blast radius).
- **No es** un ServiceNow real ni usa datos reales del cliente: todo se genera en el backend y
  las integraciones (ServiceNow, escáneres, ejecutores) están **emuladas**. El diseño refleja
  fielmente cómo se conectaría con los sistemas reales.

**Para qué sirve en la demo:** transmitir que el modelo operativo es tangible y ejecutable, y que
la herramienta se integraría con los sistemas concretos del cliente.

---

## 2. Arquitectura de 3 capas

```
   Fuentes            PLANO DE CONTROL         CAPA AGENTE            EJECUCIÓN
 (escáneres)   →      ServiceNow         →      Devin        →     herramientas cliente
 Qualys/Tenable    Vuln Response · CMDB      Blast radius, MVT,    Ansible/BigFix/SCCM (A)
 Snyk (SCA/SBOM)   Change Mgmt · Flow        tests, IaC, PR,       CI/CD GitHub (B)
 Wiz/Trivy (cont.) (decide/prioriza/audita)  informe (razona)      Argo CD/Helm/Registry (C)
                                                                   Terraform (labs)
                                    ↑ HITL: humano aprueba cada transición ↑
```

- **ServiceNow (control):** ingesta, Vulnerable Items, Remediation Tasks, CMDB/Impact Graph,
  Change Management, estado y auditoría. **No parchea.**
- **Devin (agente):** el trabajo técnico manual de cada fase. **Propone, no decide.**
- **Ejecutores:** aplican el cambio (parche infra o deploy del artefacto).
- **HITL (human-in-the-loop):** en cada transición de fase hay una aprobación humana.

**Stack técnico:** Backend **FastAPI** (Python) con datos mock en memoria + motor de simulación;
Frontend **React + TypeScript + Vite + Tailwind** con React Flow (grafo) y Recharts (KPIs).

---

## 3. Cómo ejecutarla

```bash
# Opción A · desarrollo (2 puertos)
cd msr-platform
./scripts/dev.sh            # backend http://localhost:8080  ·  frontend http://localhost:5173
# abre http://localhost:5173

# Opción B · todo-en-uno (FastAPI sirve el frontend compilado)
cd msr-platform
./scripts/build.sh
cd backend && source .venv/bin/activate && uvicorn app.main:app --port 8080
# abre http://localhost:8080
```

Requisitos: Python 3.10+ y Node 18+. `POST /api/reset` reinicia el estado de la demo entre pases.

---

## 4. Recorrido por cada pantalla

### 4.1 Dashboard · centro de mando
- **Embudo de priorización** `100.000 → 8.000 → 500 → 80 → 20`: de ruido a señal accionable
  (el mismo mensaje del PPT "Machine Speed Remediation"). *Mensaje:* la IA no solo detecta más,
  **descarta ruido** y deja lo explotable de verdad.
- **KPIs:** hallazgos abiertos, Vulnerable Items, Remediation Tasks, KEV (explotadas en real),
  en curso, remediadas, **CIs en CMDB (~10.000)**.
- **Tareas por fase / prioridad**, panel de **3 carriles operativos** (**Crítico · Acelerado · Estándar**)
  con conteo de tareas, SLA y nivel de automatización, y —como bloque secundario— la **dimensión
  técnica A/B/C** (define ejecutor y rollback) con su reparto de CIs sobre la CMDB.
- Panel **Despliegue & Rollback** (anillos desplegados, rollbacks) y **CMDB estandarizada**
  (fuente CSDM, CIs por clase) + **feed del agente** en vivo.

> **Dos dimensiones, no confundir:** el **carril operativo** (Crítico/Acelerado/Estándar) marca
> *velocidad, riesgo, SLA y nivel de automatización*; el **dominio técnico** (A/B/C) marca *qué
> ejecutor y qué rollback* se usan. El triage —con la CMDB como *risk engine*— asigna el carril
> correlacionando KEV/EPSS, exposición, criticidad del CI/servicio, SLA y ventana operativa.

### 4.2 Remediation Tasks
- Cola **priorizada por riesgo** = técnico (CVSS) + explotabilidad (EPSS/KEV) + negocio
  (criticidad) + exposición + SLA. **No es solo CVSS.**
- CVEs reales de banca: Log4Shell, Spring4Shell, ActiveMQ RCE, regreSSHion, Zerologon, XZ backdoor…
- Filtro principal por **carril operativo**: **Crítico** (>24 h, fuera de ventana) / **Acelerado**
  (7-14 días) / **Estándar** (mensual/trimestral), y columna aparte de **dominio técnico** (A/B/C).

### 4.3 Detalle de tarea · el corazón de la demo
Cabecera con CVE, CVSS/EPSS, KEV, exposición, SLA, tipo de change (standard/normal/emergency) y
**risk score /100**. Debajo, el **stepper de 6 fases** (clicable) y, por fase, el artefacto que
produce Devin + el **panel del agente** + el **botón de aprobación HITL**:

1. **Detección e ingesta** — normalización del hallazgo, correlación con CI de la CMDB, dedupe,
   asignación de track.
2. **Priorización** — desglose del riesgo multifactor + **reachability analysis** (¿la dependencia
   vulnerable es alcanzable en runtime?). *Aquí Devin analiza el nuevo contexto que ServiceNow no ve.*
3. **Pre-implementación (MVT)** — **Impact Graph** (blast radius) interactivo + **Minimum Viable
   Test Plan**: pruebas incluidas/excluidas con justificación y **% de confianza**.
4. **Pruebas en laboratorio** — ejecución del MVT (pruebas de parche + de aplicación), veredicto
   agregado pass/fail. Si falla, ServiceNow **bloquea** el avance.
5. **Validación en prototipo** — **lab efímero con IaC** (Terraform/Ansible) derivado del Impact
   Graph, métricas (error rate, p95) y teardown controlado.
6. **Despliegue por anillos + informe** — oleadas por riesgo (Anillo 0→4), post-checks por anillo,
   excepciones trazables, **PR de remediación** (Track B) e **informe de auditoría audit-ready**
   (cadena finding → VI → Impact Graph → MVT → lab → prototipo → CR → anillos → cierre).

**Indicador de SLA / due date:** en la cabecera y en la lista de tareas cada remediación muestra su
estado de SLA — **vencido** (rojo, con los días de retraso), **en riesgo** (≤ 2 días, ámbar) o **en plazo**
(verde). Si la tarea está fuera de plazo aparece un **banner de alerta** en el detalle. El Dashboard añade un
KPI **"SLA vencido"** y un resumen vencido / en riesgo / en plazo.

**Mapa de dependencias y afectados (Impact Graph) en la propia tarea:** el detalle de la Remediation Task
incluye —siempre visible, sin cambiar de fase— el **grafo de impacto** con el CI raíz vulnerable, los CIs
afectados, los servicios de negocio impactados y el nº de afectados. Es el criterio con el que Devin decide
qué activos entran en cada anillo.

**Anillos con contexto, revisión y pre-aprobación Human-Driven (Fase 6):** al abrir un anillo se ve un
**informe pre-anillo** con:
- **por qué Devin ha seleccionado esos activos** (rationale) y los **criterios** (blast radius, criticidad,
  entorno, exposición, ventana);
- la **lista de activos seleccionados** (revisable y **editable** — se pueden excluir activos, lo que invalida
  la pre-aprobación y obliga a re-verificar);
- los **criterios de entrada** del anillo (MVT aprobado, prototipo validado, CR autorizado, rollback probado…);
- el estado de **verificación y pre-aprobación (auditoría Human-Driven)**: hasta que el owner no revisa y
  **pre-aprueba** el informe, **ServiceNow bloquea el despliegue** del anillo;
- las **acciones ejecutadas con el porqué de cada comando** (qué hace, por qué aplica y su salida) + post-checks.

### 4.4 CMDB · Impact Graph
Patrimonio bancario a escala: **~10.000 CIs** en modelo **estandarizado (ServiceNow CSDM 4.0)** —
`sys_class_name`, `business_criticality` (tier), `support_group`, `install_status`— con business
services, apps, BBDD, servidores, middleware, runtime, **contenedores, red, endpoints y cloud**.
Resumen por clase / **dominio técnico** / criticidad, **buscador y filtros paginados**, y **grafo de impacto
por servicio de negocio** (subgrafo calculado en servidor). *Mensaje:* traduce "servidor vulnerable" →
"servicio crítico" y es la base para dimensionar las pruebas.

**Contrato de datos con la CMDB (botón `{ } ver JSON` en cada CI):** muestra el **registro nativo de
ServiceNow** tal como llegaría vía IntegrationHub / MID Server —patrón `GET /api/now/table/<sys_class_name>/<sys_id>?sysparm_display_value=all`—
con `sys_id`, `sys_class_name`, `install_status`/`business_criticality` como **código + etiqueta** y los
campos de referencia (`assignment_group`, `managed_by`, `location`) como objetos `{ value, display_value, link }`.
Una segunda pestaña enseña el **mapeo campo ServiceNow → modelo interno** (p. ej. `business_criticality` → triage,
`u_track` → dominio técnico A/B/C que fija ejecutor/rollback). *Mensaje:* "No es un formato inventado: es el payload
exacto de la Table API; conectar su CMDB real es apuntar el endpoint y aplicar este mapeo."

**CMDB versionada en el repo (formato estándar):** la CMDB no se genera solo en memoria — está exportada al
repositorio en `msr-platform/data/cmdb/` en **formato nativo ServiceNow**: un fichero por tabla (`cmdb_ci_server.json`,
`cmdb_ci_appl.json`, `cmdb_ci_runtime.json`, … `cmdb_ci_service.json`) + relaciones (`cmdb_rel_ci.json`), más un
`_manifest.json` (origen, conteos y mapa de campos) y el modelo normalizado que el backend recarga como **fuente de
verdad**. La pantalla CMDB muestra un panel con el origen, las tablas y sus conteos (10.000 CIs · 6.702 relaciones).
Endpoint: `GET /api/cmdb/tables`.

### 4.5 Catálogo de pruebas
Biblioteca **versionada en Git** de pruebas por capa (OS, DB, middleware, runtime, app, externo).
Devin selecciona de aquí el MVT según el Impact Graph. *Mensaje:* pruebas **proporcionales al
riesgo**, ni de menos ni de más.

### 4.6 Integraciones
Modelo de 3 capas con estado de cada sistema y el flujo **Flow Designer → Devin API → Table API**,
con **HITL** en cada transición y **un playbook de Devin por fase**.

---

## 5. Guion de demo (recomendado · ~8-10 min)

1. **Dashboard (1 min).** Señala el embudo y los KPIs. Frase: *"100.000 hallazgos, pero solo 20
   necesitan acción inmediata. La IA quita el ruido."*
2. **Remediation Tasks (1 min).** Ordena por riesgo. *"No priorizamos por CVSS: metemos negocio,
   exposición y explotabilidad real (KEV/EPSS)."* Abre **Log4Shell en `payments-api`** (riesgo 100).
3. **Fase 2 · Priorización (1 min).** Muestra el desglose del riesgo y el **reachability analysis**.
   *"Devin leyó el repo y confirmó que la librería es alcanzable en runtime → sigue siendo crítico."*
4. **Fase 3 · Impact Graph + MVT (2 min).** El momento estrella. Explora el grafo (root en rojo,
   servicios de negocio impactados). *"Devin construyó el blast radius desde CMDB + SBOM y propone
   8 pruebas —no 40—, justificando qué excluye. Confianza 94%."* Enseña incluidas vs excluidas.
5. **HITL (30 s).** *"Devin propone; el owner aprueba."* Pulsa **Aprobar fase y avanzar**: se ve al
   agente trabajar la siguiente fase en el panel.
6. **Fases 4-5 (1 min).** Resultados de lab (parche + app) y **lab efímero con IaC** + métricas.
7. **Fase 6 · Despliegue + auditoría (2 min).** Anillos 0→4, pulsa **Aprobar y desplegar anillo**
   (avanza un anillo cada vez). **Despliega un anillo (Anillo 0) y haz clic en la fila del anillo
   para desplegar las acciones ejecutadas**: comandos concretos por actor (Devin, ejecutor,
   post-checks), salida y duración, más las métricas de salud (error rate / p95 / disponibilidad).
   *"No solo se aprueba: se ve exactamente qué acción se ejecutó y su evidencia."* Enseña el
   **PR de remediación**, las **excepciones** y el **informe audit-ready**. *"Toda la cadena queda
   trazada para DORA."*
8. **Rollback (1 min).** En el panel de **Gestión de Rollback** enseña que el plan está **armado y
   probado en lab desde el inicio** (estrategia, RTO, versión estable, pasos). Luego pulsa
   **"⚠ Simular incidente → rollback automático"**: aparece la anomalía (error rate 4.7% > SLO),
   el rollback se dispara solo, ejecuta sus pasos y **restaura la versión estable**; el anillo queda
   marcado como *revertido* y el Vulnerable Item vuelve a abrirse para re-análisis. También existe
   **"⟲ Rollback manual"** para el owner. *"El rollback no es un plan en un PDF: es ejecutable,
   automático ante fallo de post-checks y trazado."*
9. **Cierre (30 s).** Vuelve al Dashboard. *"ServiceNow gobierna, Devin ejecuta, el humano aprueba.
   Días → minutos, con evidencia completa y rollback seguro."*

**Carril operativo (lo que decides mostrar por urgencia):** abre una tarea **Crítica** para ver el flujo
express (emergency change pre-aprobado → ejecución inmediata fuera de ventana → validación reforzada →
RCA → cierre Cyber-IT), casi 100% agentable; contrástalo con una **Estándar** (ordinary change →
pre-validación completa → ventana planificada → rollback closed-loop → reporting), semiauto/manual.
Cada paso del flujo lleva su chip **Fully agentable / AI-assisted / Human driven**.

**Dominio técnico (lo que cambia el ejecutor/rollback):** en cualquier carril, el dominio del CI decide
cómo se ejecuta — **A · Infraestructura** (SCCM/BigFix/Ansible; snapshot/downgrade), **B · Aplicaciones y
dependencias** (CI/CD + PR; artifact redeploy), **C · Contenedores & Cloud-native** (rebuild de imagen +
Trivy/cosign + rollout GitOps Argo CD/Helm; `argocd app rollback` + `kubectl rollout undo`).

---

## 6. Mensajes clave (para repetir en la demo)

- **Acelerador en fases tempranas:** la velocidad de detección/priorización es donde más se gana.
- **Contexto que ServiceNow no ve:** Devin lee código, SBOM, reachability, exposición.
- **Propone, no decide:** HITL obligatorio → gobierno y control.
- **3 carriles operativos** (Crítico/Acelerado/Estándar) = velocidad, riesgo, SLA y automatización; el triage los asigna con la CMDB como *risk engine*.
- **Dominio técnico A/B/C** = atributo secundario del CI que elige ejecutor y rollback: A infra (SCCM/BigFix/Ansible), B aplicación con PR (CI/CD), C contenedores/cloud (rebuild + rollout GitOps Argo CD/Helm).
- **Audit-ready:** trazabilidad completa finding→cierre, clave para banca/DORA.
- **Se integra con lo que ya tienen:** ServiceNow, Qualys/Tenable/Snyk, SCCM/BigFix/Ansible, CI/CD.

---

## 7. Preguntas frecuentes (y respuestas)

- **"¿Devin sustituye a ServiceNow?"** No. ServiceNow sigue siendo el plano de control y auditoría;
  Devin es la capa agente que ejecuta el trabajo técnico.
- **"¿Devin parchea producción solo?"** No. Los ejecutores del cliente aplican; y siempre hay
  aprobación humana en cada fase.
- **"¿Los datos son reales?"** No, son sintéticos para la demo; el diseño refleja la integración real.
- **"¿Y si una prueba falla?"** ServiceNow bloquea el avance, avisa al owner y registra la causa
  (se ve en la fase de laboratorio).
- **"¿Qué pasa con activos sin parche/ventana?"** Se registran como **excepciones trazables** con
  control compensatorio y caducidad (visible en la fase de despliegue).

---

## 8. Mapa técnico (para preguntas de arquitectura)

```
backend/app/
  seed.py     # CMDB CSDM ~10k CIs, triage/asignación de carril (LANES) + dominio técnico A/B/C,
              # catálogo CVEs, hallazgos, VIs, Tasks
  engine.py   # flujo por carril (SHARED_FLOW + LANE_FLOWS) y automatización por fase; Impact Graph
              # (BFS), MVT (reglas por capa), lab, prototipo, anillos e informe de auditoría
  store.py    # estado en memoria + orquestación de fases y gate HITL (approve_phase)
  main.py     # API FastAPI (/api/*) y servido de la SPA
frontend/src/
  pages/      # Dashboard, Tasks, TaskDetail, Cmdb, Catalog, Integrations
  components/ # ImpactGraphView (React Flow)
```

API principal: `GET /api/overview`, `GET /api/tasks`, `GET /api/tasks/{id}`,
`POST /api/tasks/{id}/approve` (HITL), `GET /api/cmdb`, `GET /api/cmdb/cis`,
`GET /api/cmdb/cis/{id}/raw` (registro nativo ServiceNow + mapeo), `GET /api/catalog`,
`GET /api/services`, `POST /api/reset`.

---

## 9. Checklist antes de presentar

- [ ] Backend y frontend arrancados (`./scripts/dev.sh`) y `http://localhost:5173` abre.
- [ ] `POST /api/reset` ejecutado para empezar limpio.
- [ ] Tarea Log4Shell (`payments-api`) localizada para el recorrido principal.
- [ ] Una tarea Crítica y una Estándar localizadas para contrastar carril/automatización.
- [ ] Una tarea de dominio A (regreSSHion/Zerologon) y una de dominio C (runc/containerd) para el contraste de ejecutor/rollback.
- [ ] Zoom del navegador al 100% para que el Impact Graph se vea completo.
