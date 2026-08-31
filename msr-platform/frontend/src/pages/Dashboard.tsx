import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api";
import type { ExecutionConfig, Overview, Task, LogEntry } from "../types";
import { Risk } from "../ui";
import JourneyBoard, { BlockerChip, JOURNEY_BAND_COLOR } from "../components/journey/JourneyBoard";
import VulnJourneyPanel from "../components/journey/VulnJourneyPanel";

/** Bloqueos que exigen una intervención humana, en orden de urgencia. */
const ACTIONABLE_BLOCKERS = ["job_failed", "job_unconfirmed", "awaiting_approval"];

function Kpi({ label, value, accent, hint, onClick }: {
  label: string; value: string | number; accent?: string; hint: string; onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={`${label}: ${value}. ${hint}`}
      title={hint}
      className="card p-4 text-left hover:bg-ink-panel transition-colors focus:outline-none focus:ring-2 focus:ring-brand/60"
    >
      <div className="text-2xl font-extrabold" style={{ color: accent }}>{value}</div>
      <div className="text-xs text-gray-400 mt-1">{label}</div>
    </button>
  );
}

/** Modo de ejecución real del backend: mock, AWS en simulación o AWS efectivo. */
function ModeBadge({ execution }: { execution: ExecutionConfig | null }) {
  if (!execution) return null;
  const mock = execution.patch_provider === "mock";
  const label = mock ? "MOCK" : execution.dry_run ? "AWS · DRY-RUN" : "AWS · EJECUCIÓN REAL";
  const cls = mock
    ? "bg-slate-500/15 text-slate-300 border-slate-500/40"
    : execution.dry_run
      ? "bg-sky-500/15 text-sky-300 border-sky-500/40"
      : "bg-red-500/15 text-red-300 border-red-500/50";
  return (
    <span className={`chip border font-semibold ${cls}`}
          title={`patch: ${execution.patch_provider} · restore: ${execution.restore_provider}${
            execution.region ? ` · ${execution.region}` : ""}`}>
      {label}
    </span>
  );
}

export default function Dashboard() {
  const [ov, setOv] = useState<Overview | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [activity, setActivity] = useState<LogEntry[]>([]);
  const [execution, setExecution] = useState<ExecutionConfig | null>(null);
  const [error, setError] = useState<string | null>(null);
  const nav = useNavigate();
  const [params, setParams] = useSearchParams();
  const phaseFilter = params.get("phase");
  const selectedTask = params.get("vuln");

  const selectJourney = (next: { phase?: string | null; vuln?: string | null }) => {
    const updated = new URLSearchParams(params);
    for (const [key, value] of Object.entries(next)) {
      if (value) updated.set(key, value);
      else updated.delete(key);
    }
    setParams(updated, { replace: true });
  };

  useEffect(() => {
    const load = () => Promise.all([api.overview(), api.tasks(), api.activity(), api.execution()])
      .then(([o, t, a, e]) => {
        setOv(o);
        setTasks(t);
        setActivity(a);
        setExecution(e);
        setError(null);
      })
      .catch((e: Error) => setError(e.message));
    load();
    const timer = setInterval(load, 15000);
    return () => clearInterval(timer);
  }, []);

  if (error && !ov) {
    return (
      <div className="p-8 text-sm text-red-300">
        No se pudo cargar el estado: {error}. Reintentando cada 15 s…
      </div>
    );
  }
  if (!ov) return <div className="p-8 text-gray-500">Cargando…</div>;

  const journeyTasks = tasks.filter((t) => !phaseFilter || t.journey.phase === phaseFilter);
  const phaseMeta = ov.journey.phases.find((p) => p.id === phaseFilter);
  const needsAction = tasks
    .map((t) => ({ task: t, blockers: t.journey.blockers.filter((b) => ACTIONABLE_BLOCKERS.includes(b)) }))
    .filter((x) => x.blockers.length > 0)
    .sort((a, b) => ACTIONABLE_BLOCKERS.indexOf(a.blockers[0]) - ACTIONABLE_BLOCKERS.indexOf(b.blockers[0]));

  return (
    <div className="p-6 space-y-6 max-w-[1600px]">
      <header className="flex items-start justify-between gap-4">
        <div>
          <div className="text-xs font-bold text-brand tracking-wider">MACHINE SPEED REMEDIATION · CENTRO DE MANDO</div>
          <h1 className="text-2xl font-extrabold mt-1">Gestión de vulnerabilidades impulsada por IA</h1>
          <p className="text-sm text-gray-400 mt-1">
            {ov.kpis.open_findings.toLocaleString()} hallazgos de los escáneres →{" "}
            <b className="text-gray-200">{ov.kpis.vulnerable_items}</b> Vulnerable Items curados sobre{" "}
            {ov.cmdb.total.toLocaleString()} CIs ·{" "}
            <button type="button" className="text-brand font-semibold" onClick={() => nav("/analytics")}>
              ver el embudo de priorización →
            </button>
          </p>
        </div>
        <ModeBadge execution={execution} />
      </header>

      {error && (
        <div className="chip bg-amber-500/15 text-amber-300 border border-amber-500/40">
          Datos posiblemente desactualizados: {error}
        </div>
      )}

      {/* ¿Qué tengo? — cada indicador entra al detalle que representa */}
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
        <Kpi label="Vulnerabilidades abiertas" value={ov.kpis.vulnerable_items}
             hint="Ver todas las Remediation Tasks" onClick={() => nav("/tasks")} />
        <Kpi label="Requieren mi acción" value={needsAction.length}
             accent={needsAction.length > 0 ? "#f59e0b" : "#22c55e"}
             hint="Aprobaciones pendientes, jobs fallidos o sin confirmar"
             onClick={() => document.getElementById("needs-action")?.scrollIntoView({ behavior: "smooth" })} />
        <Kpi label="KEV (explotadas)" value={ov.kpis.kev_count} accent="#ef4444"
             hint="Ver las tareas de vulnerabilidades explotadas activamente"
             onClick={() => nav("/tasks?kev=1")} />
        <Kpi label="En curso" value={ov.kpis.in_flight} accent="#0ea5e9"
             hint="Ver las tareas todavía no remediadas" onClick={() => nav("/tasks?status=in_flight")} />
        <Kpi label="Fuera de SLA" value={ov.sla.overdue}
             accent={ov.sla.overdue > 0 ? "#ef4444" : "#22c55e"}
             hint="Ver las tareas que han superado su fecha de vencimiento"
             onClick={() => nav("/tasks?sla=overdue")} />
        <Kpi label="Remediadas" value={ov.kpis.remediated} accent="#22c55e"
             hint="Ver las tareas cerradas" onClick={() => nav("/tasks?status=remediated")} />
      </div>

      <div className="flex flex-wrap gap-2 text-xs">
        <button type="button" onClick={() => nav("/tasks?sla=overdue")}
                className="chip bg-red-500/15 text-red-300 border border-red-500/40">
          {ov.sla.overdue} fuera de plazo
        </button>
        <button type="button" onClick={() => nav("/tasks?sla=due_soon")}
                className="chip bg-amber-500/15 text-amber-300 border border-amber-500/40">
          {ov.sla.due_soon} en riesgo (vence ≤ 2 días)
        </button>
        <span className="chip bg-emerald-500/10 text-emerald-300 border border-emerald-500/30">
          {ov.sla.on_track} en plazo
        </span>
        <span className="text-gray-500 self-center">
          El SLA se cuenta desde la detección: 3 días para KEV/CVSS≥9, 15 para altas y 30 para el resto.
        </span>
      </div>

      {/* ¿Qué requiere atención ahora? */}
      {needsAction.length > 0 && (
        <section id="needs-action" className="card p-4 space-y-2">
          <div className="text-sm font-semibold">Requieren mi acción</div>
          <div className="text-xs text-gray-500">
            Bloqueos operativos: aprobaciones pendientes, ejecuciones fallidas y jobs sin confirmar.
          </div>
          <div className="divide-y divide-line/50">
            {needsAction.map(({ task, blockers }) => (
              <button key={task.id} type="button" onClick={() => selectJourney({ vuln: task.id })}
                      className="w-full text-left py-2 flex items-center gap-3 hover:bg-ink-panel">
                <span className="font-mono text-xs text-gray-300 w-36 shrink-0">{task.cve}</span>
                <span className="text-sm text-gray-300 truncate flex-1">{task.ci_name}</span>
                {blockers.map((b) => <BlockerChip key={b} id={b} />)}
              </button>
            ))}
          </div>
        </section>
      )}

      {/* ¿Dónde están dentro del proceso? + ¿qué hago con esta? */}
      <section className="space-y-3">
        <div className="flex items-baseline justify-between gap-3">
          <div>
            <div className="text-sm font-semibold">Patching Journey</div>
            <div className="text-xs text-gray-500">
              Distribución de las {ov.journey.total} vulnerabilidades a lo largo de las 8 fases del modelo ·
              las fases 4-7 se repiten en cada anillo de despliegue
            </div>
          </div>
          {phaseFilter && (
            <button className="text-xs text-brand font-semibold"
                    onClick={() => selectJourney({ phase: null, vuln: null })}>
              Quitar filtro ✕
            </button>
          )}
        </div>

        <JourneyBoard
          journey={ov.journey}
          selected={phaseFilter}
          onSelect={(id) => selectJourney({ phase: id, vuln: null })}
        />

        <div className={`grid grid-cols-1 gap-6 ${selectedTask ? "xl:grid-cols-12" : ""}`}>
          <div className={`card overflow-hidden ${selectedTask ? "xl:col-span-5" : ""}`}>
            <div className="px-4 py-3 border-b border-line text-sm font-semibold">
              {phaseMeta
                ? <>Fase {phaseMeta.index} · {phaseMeta.label} <span className="text-gray-500 font-normal">({journeyTasks.length})</span></>
                : <>Todas las vulnerabilidades <span className="text-gray-500 font-normal">({journeyTasks.length})</span></>}
              <div className="text-xs text-gray-500 font-normal mt-0.5">
                {phaseMeta ? phaseMeta.label_en : "Selecciona una fase para filtrar, y una vulnerabilidad para ver su journey"}
              </div>
            </div>
            <div className="divide-y divide-line/50">
              {journeyTasks.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => selectJourney({ vuln: t.id })}
                  aria-pressed={selectedTask === t.id}
                  className={`w-full text-left px-4 py-2.5 flex items-start gap-3 hover:bg-ink-panel ${
                    selectedTask === t.id ? "bg-ink-panel" : ""}`}
                >
                  <Risk score={t.risk_score} />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-baseline gap-2">
                      <span className="font-mono text-xs text-gray-300 shrink-0">{t.cve}</span>
                      <span className="text-sm text-gray-400 truncate">{t.ci_name}</span>
                    </div>
                    <div className="flex flex-wrap items-center gap-2 mt-1">
                      <span className="chip"
                            style={{ background: JOURNEY_BAND_COLOR[t.journey.band] + "22",
                                     color: JOURNEY_BAND_COLOR[t.journey.band] }}>
                        {t.journey.phase_index} · {t.journey.phase_label}
                        {t.journey.ring !== null && ` · A${t.journey.ring}`}
                      </span>
                      <span className="text-[11px] text-gray-500 font-mono">
                        {t.journey.resources.patched}/{t.journey.resources.total} parcheados
                      </span>
                      {t.journey.blockers.slice(0, 1).map((b) => <BlockerChip key={b} id={b} />)}
                    </div>
                  </div>
                </button>
              ))}
              {journeyTasks.length === 0 && (
                <div className="px-4 py-6 text-xs text-gray-600">Ninguna vulnerabilidad en esta fase ahora mismo.</div>
              )}
            </div>
          </div>

          {selectedTask && (
            <div className="xl:col-span-7">
              <VulnJourneyPanel taskId={selectedTask} onClose={() => selectJourney({ vuln: null })} />
            </div>
          )}
        </div>
      </section>

      {/* ¿Qué ha pasado? */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <div className="card overflow-hidden flex flex-col xl:col-span-2">
          <div className="px-4 py-3 border-b border-line flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-brand animate-pulse" />
            <div className="text-sm font-semibold">Actividad del agente</div>
          </div>
          <div className="p-3 space-y-1 overflow-y-auto max-h-[340px]">
            {activity.slice(0, 16).map((a, i) => (
              <button key={i} type="button" disabled={!a.task_id}
                      onClick={() => a.task_id && nav(`/tasks/${a.task_id}`)}
                      className={`w-full text-left text-xs flex gap-2 rounded px-1 py-1 ${
                        a.task_id ? "hover:bg-ink-panel" : "cursor-default"}`}>
                <span className={`chip shrink-0 ${a.actor === "Devin" ? "bg-brand/15 text-brand" : a.actor.includes("HITL") || a.actor.includes("Owner") ? "bg-amber-500/15 text-amber-300" : "bg-sky-500/15 text-sky-300"}`}>
                  {a.actor}
                </span>
                <span className="text-gray-400 leading-relaxed">{a.msg}</span>
              </button>
            ))}
            {activity.length === 0 && <div className="text-xs text-gray-600">Sin actividad todavía. Aprueba una fase en una tarea para ver al agente trabajar.</div>}
          </div>
        </div>

        <div className="card p-5">
          <div className="text-sm font-semibold mb-1">Despliegue & Rollback</div>
          <div className="text-xs text-gray-500 mb-4">Ejecución por anillos con evidencia y reversión</div>
          <div className="grid grid-cols-2 gap-3">
            <button type="button" onClick={() => nav("/tasks?status=in_flight")}
                    className="rounded-lg bg-ink p-3 text-left hover:bg-ink-panel">
              <div className="text-2xl font-extrabold text-sky-400">{ov.deployment.in_deployment}</div>
              <div className="text-[11px] text-gray-400 mt-1">En despliegue</div>
            </button>
            <div className="rounded-lg bg-ink p-3">
              <div className="text-2xl font-extrabold text-emerald-400">{ov.deployment.rings_deployed}</div>
              <div className="text-[11px] text-gray-400 mt-1">Anillos desplegados</div>
            </div>
            <div className="rounded-lg bg-ink p-3">
              <div className="text-2xl font-extrabold" style={{ color: ov.deployment.rollbacks ? "#f97316" : "#64748b" }}>{ov.deployment.rollbacks}</div>
              <div className="text-[11px] text-gray-400 mt-1">Rollbacks ejecutados</div>
            </div>
            <button type="button" onClick={() => nav("/cmdb")}
                    className="rounded-lg bg-ink p-3 text-left hover:bg-ink-panel">
              <div className="text-2xl font-extrabold text-brand">{ov.cmdb.total.toLocaleString()}</div>
              <div className="text-[11px] text-gray-400 mt-1">CIs en la CMDB</div>
            </button>
          </div>
          <div className="mt-3 text-[11px] text-gray-500 leading-snug">
            Rollback armado y probado en lab desde el inicio; disparo manual (owner) o automático por fallo de post-checks.
          </div>
        </div>
      </div>
    </div>
  );
}
