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
                   (decide/prioriza/audita)  informe (razona)      Terraform (labs)
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
  en curso, remediadas, CIs en CMDB.
- **Tareas por fase / prioridad / track** y **feed del agente** en vivo.

### 4.2 Remediation Tasks
- Cola **priorizada por riesgo** = técnico (CVSS) + explotabilidad (EPSS/KEV) + negocio
  (criticidad) + exposición + SLA. **No es solo CVSS.**
- CVEs reales de banca: Log4Shell, Spring4Shell, ActiveMQ RCE, regreSSHion, Zerologon, XZ backdoor…
- Filtros por **Track A (infra)** / **Track B (aplicación/dependencias)**.

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

### 4.4 CMDB · Impact Graph
Patrimonio bancario (132 CIs: business services, apps, BBDD, servidores, middleware, runtime) y
**grafo de impacto por servicio de negocio**. *Mensaje:* traduce "servidor vulnerable" →
"servicio crítico" y es la base para dimensionar las pruebas.

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
   (avanza un anillo cada vez). Enseña el **PR de remediación**, las **excepciones** y el
   **informe audit-ready**. *"Toda la cadena queda trazada para DORA."*
8. **Cierre (30 s).** Vuelve al Dashboard. *"ServiceNow gobierna, Devin ejecuta, el humano aprueba.
   Días → minutos, con evidencia completa."*

**Tarea alternativa Track A:** elige un CVE de infra (regreSSHion / Zerologon / XZ) para mostrar
que ahí Devin es **copiloto** (genera tests, IaC y evidencia) pero **no aplica el parche** —lo hace
SCCM/BigFix/Ansible.

---

## 6. Mensajes clave (para repetir en la demo)

- **Acelerador en fases tempranas:** la velocidad de detección/priorización es donde más se gana.
- **Contexto que ServiceNow no ve:** Devin lee código, SBOM, reachability, exposición.
- **Propone, no decide:** HITL obligatorio → gobierno y control.
- **Track A vs B:** infra = copiloto; aplicación/dependencias = extremo a extremo (incluye el PR).
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
  seed.py     # datos mock: CMDB bancaria, catálogo CVEs, hallazgos, VIs, Remediation Tasks
  engine.py   # Impact Graph (BFS sobre relaciones), MVT (reglas por capa), lab, prototipo,
              # anillos y generación del informe de auditoría
  store.py    # estado en memoria + orquestación de fases y gate HITL (approve_phase)
  main.py     # API FastAPI (/api/*) y servido de la SPA
frontend/src/
  pages/      # Dashboard, Tasks, TaskDetail, Cmdb, Catalog, Integrations
  components/ # ImpactGraphView (React Flow)
```

API principal: `GET /api/overview`, `GET /api/tasks`, `GET /api/tasks/{id}`,
`POST /api/tasks/{id}/approve` (HITL), `GET /api/cmdb`, `GET /api/catalog`, `GET /api/services`,
`POST /api/reset`.

---

## 9. Checklist antes de presentar

- [ ] Backend y frontend arrancados (`./scripts/dev.sh`) y `http://localhost:5173` abre.
- [ ] `POST /api/reset` ejecutado para empezar limpio.
- [ ] Tarea Log4Shell (`payments-api`) localizada para el recorrido principal.
- [ ] Una tarea Track A elegida (regreSSHion/Zerologon) para el contraste infra.
- [ ] Zoom del navegador al 100% para que el Impact Graph se vea completo.
