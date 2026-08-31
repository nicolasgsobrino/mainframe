import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { ApiError, api, releaseIdempotencyKey } from "../api";
import type { TaskDetail as TD, FlowStep, Ring, ItsmChange, Deployment, PatchJob, LabPatchEvidence } from "../types";
import { Priority, Track, Risk, KevTag, PHASE_META, LaneTag, LANE_META, AUTOMATION_META, SlaTag } from "../ui";
import ImpactGraphView from "../components/ImpactGraphView";
import LabPanel from "../components/LabPanel";
import { useView } from "../view";

const PHASE_IDS = ["detection", "prioritization", "pre_implementation", "lab_testing", "prototype", "deployment"];

const JOB_STATE_LABEL: Record<string, string> = {
  queued: "En cola", validating: "Validando objetivo", dry_run: "Dry-run (sin cambios)",
  starting: "Arrancando", running: "En ejecución", verifying: "Verificando",
  succeeded: "Completado", failed: "Fallido", cancelling: "Cancelando",
  cancelled: "Cancelado", restore_queued: "Restauración en cola",
  restoring: "Restaurando", restored: "Restaurado", restore_failed: "Restauración fallida",
  timed_out: "Tiempo agotado",
  timeout_pending_confirmation: "Timeout local · pendiente de confirmar en AWS",
  remote_status_unknown: "Estado remoto desconocido",
  stop_requested: "Parada solicitada a AWS",
};
/** El runbook aborta con este error cuando el objetivo ya estaba parcheado. */
const alreadyFixed = (job: PatchJob) => !!job.error_message?.includes("KERNEL_ALREADY_FIXED");

const JOB_STATE_TONE: Record<string, string> = {
  succeeded: "bg-green-500/15 text-green-400", restored: "bg-green-500/15 text-green-400",
  failed: "bg-red-500/15 text-red-400", restore_failed: "bg-red-500/15 text-red-400",
  timed_out: "bg-red-500/15 text-red-400", cancelled: "bg-gray-500/15 text-gray-300",
  dry_run: "bg-sky-500/15 text-sky-300",
  timeout_pending_confirmation: "bg-orange-500/15 text-orange-300",
  remote_status_unknown: "bg-orange-500/15 text-orange-300",
  stop_requested: "bg-orange-500/15 text-orange-300",
};
const jobTone = (state: string) => JOB_STATE_TONE[state] ?? "bg-amber-500/15 text-amber-300";
/** Etiqueta del modo de ejecución: mock, AWS dry-run o AWS real. */
const executionModeLabel = (job: PatchJob): string => {
  if (job.provider === "mock") return "Simulación (mock)";
  return job.dry_run ? "AWS · dry-run (sin cambios reales)" : "AWS Systems Manager · ejecución real";
};

const toError = (e: unknown) =>
  e instanceof ApiError
    ? { code: e.code, message: e.message, correlationId: e.correlationId }
    : { code: "NETWORK_ERROR", message: e instanceof Error ? e.message : String(e), correlationId: null };

function Verdict({ v }: { v: string }) {
  const ok = v === "pass";
  return <span className={`chip ${ok ? "bg-green-500/15 text-green-400" : "bg-red-500/15 text-red-400"}`}>{ok ? "PASS" : "FAIL"}</span>;
}

export default function TaskDetail() {
  const { id } = useParams();
  const { role } = useView();
  const isTech = role === "tech";
  const [d, setD] = useState<TD | null>(null);
  const [sel, setSel] = useState<number>(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ code: string; message: string; correlationId: string | null } | null>(null);
  const keepSelection = useRef(false);

  const apply = useCallback((r: TD) => {
    setD(r);
    if (!keepSelection.current) setSel(r.phase_index);
  }, []);

  const load = useCallback(async () => {
    keepSelection.current = false;
    apply(await api.task(id!));
  }, [id, apply]);

  useEffect(() => { load().catch((e) => setError(toError(e))); }, [load]);

  // Polling del job activo: se reanuda tras un reload porque `active_job` viene
  // del backend, y se detiene en cuanto el job alcanza un estado terminal.
  const activeJob = d?.active_job ?? null;
  const pollMs = (d?.execution?.poll_interval_seconds ?? 2) * 1000;
  useEffect(() => {
    if (!activeJob || activeJob.terminal) return;
    const timer = window.setInterval(() => {
      keepSelection.current = true;
      api.task(id!).then(apply).catch((e) => setError(toError(e)));
    }, pollMs);
    return () => window.clearInterval(timer);
  }, [activeJob, id, pollMs, apply]);

  if (!d) return <div className="p-8 text-gray-500">Cargando…</div>;
  const { task, vulnerable_item: vi, artifacts: a } = d;
  const done = task.status === "remediated";
  const currentPhaseId = PHASE_IDS[d.phase_index];
  const selPhaseId = PHASE_IDS[sel];
  const phaseLogs = d.logs.filter((l) => l.phase === selPhaseId);
  const jobRunning = !!activeJob && !activeJob.terminal;
  const lastJob = activeJob ?? d.jobs?.[0] ?? null;
  const locked = busy || jobRunning;

  const run = async (action: () => Promise<TD>) => {
    setBusy(true);
    setError(null);
    try {
      apply(await action());
    } catch (e) {
      setError(toError(e));
    } finally {
      setBusy(false);
    }
  };

  const approve = () => run(() => api.approve(id!, d.rings_done + 1));
  const rollback = () => run(() => api.rollback(id!, d.rings_done));
  const simulate = () => run(() => api.simulateIncident(id!));
  const preapproveRing = (ring: number) => run(() => api.preapproveRing(id!, ring));
  const saveRingAssets = (ring: number, excluded: string[]) =>
    run(() => api.updateRingAssets(id!, ring, excluded));
  const cancelJob = async (jobId: string) => {
    setBusy(true);
    setError(null);
    try {
      await api.cancelPatchJob(jobId);
      releaseIdempotencyKey(`approve:${id}:${d.rings_done + 1}`);
      keepSelection.current = true;
      apply(await api.task(id!));
    } catch (e) {
      setError(toError(e));
    } finally {
      setBusy(false);
    }
  };

  const nextRing = a.deployment.rings[d.rings_done];
  const nextRingPreapproved = !!nextRing?.plan.approval.preapproved;
  // Evidencia del parcheo ya confirmado por AWS sobre la instancia del lab: los
  // anillos siguientes se aprueban igual, pero no relanzan la Automation.
  const labPatch = d.lab_patch ?? null;
  const canApprove = !done && !jobRunning && (
    currentPhaseId === "deployment"
      ? nextRingPreapproved
      : (currentPhaseId !== "lab_testing" || a.lab.verdict === "pass")
  );

  return (
    <div className="p-6 space-y-5 max-w-[1400px]">
      <Link to="/tasks" className="text-xs text-gray-500 hover:text-brand">← Remediation Tasks</Link>

      {/* Header */}
      <div className="card p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-mono text-sm text-gray-300">{task.cve}</span>
              <LaneTag lane={d.lane} sla={d.lane_meta.sla} />
              <Track t={task.track} />
              <Priority p={task.priority} />
              {vi.kev && <KevTag />}
              {vi.exploit_available && <span className="chip bg-red-500/10 text-red-300 border border-red-500/20">exploit disponible</span>}
              {!done && <SlaTag sla={d.sla} />}
              {done && <span className="chip bg-green-500/15 text-green-400">REMEDIADA</span>}
            </div>
            <h1 className="text-xl font-extrabold mt-2">{task.title}</h1>
            <div className="text-sm text-gray-400 mt-1">
              Activo <span className="text-gray-200">{task.ci_name}</span> · {task.environment} · owner {task.owner}
            </div>
          </div>
          <div className="text-right shrink-0">
            <div className="text-xs text-gray-500">Risk score</div>
            <div className="text-4xl font-extrabold"><Risk score={task.risk_score} /><span className="text-lg text-gray-600">/100</span></div>
            <div className="text-xs text-gray-500 mt-1">Change: <span className="text-gray-300">{task.change_type}</span></div>
          </div>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-6 gap-3 mt-4 text-xs">
          <Meta k="CVSS" v={vi.cvss.toFixed(1)} />
          <Meta k="EPSS" v={`${(vi.epss * 100).toFixed(0)}%`} />
          <Meta k="Componente" v={`${vi.component} ${vi.vulnerable_version}`} />
          <Meta k="Expuesto" v={task.exposed ? "Sí (internet)" : "No"} />
          <Meta k="SLA" v={task.sla_due.slice(0, 10)} />
          <Meta k="Fuentes" v={vi.sources.length + " scanners"} />
        </div>
      </div>

      {/* Laboratorio EC2 real: sólo en la tarea de la PoC de parcheo. */}
      {task.logical_lab_id && (
        <LabPanel
          labId={task.logical_lab_id}
          onPatch={approve}
          patchBlockedReason={labPatch
            ? `Parcheo ya confirmado (kernel ${labPatch.kernel ?? "—"}, ejecución ${labPatch.execution_id}). `
              + "Para repetirlo hay que resetear antes el laboratorio."
            : canApprove ? null
              : done ? "La tarea ya está remediada."
                : jobRunning ? "Hay un job activo sobre el laboratorio."
                  : "La fase actual no permite todavía ejecutar el parcheo."}
          locked={locked}
        />
      )}

      {labPatch && <PatchConfirmed evidence={labPatch} />}

      {d.sla?.overdue && !done && (
        <div className="rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-2.5 text-sm text-red-300 flex items-center gap-2">
          <span className="text-lg">⚠</span>
          <span>
            <b>SLA vencido</b> — due date {d.sla.due.slice(0, 10)}, superado hace <b>{d.sla.days_overdue} día(s)</b>.
            Esta remediación está fuera de plazo; prioriza su ejecución.
          </span>
        </div>
      )}

      {/* Resumen ejecutivo — vista Gestor */}
      {!isTech && (
        <div className="card p-5">
          <div className="text-sm font-semibold text-gray-100 mb-1">Resumen ejecutivo</div>
          <div className="text-xs text-gray-500 mb-3">
            Vista de gestión — riesgo, plazo, impacto de negocio y estado. Cambia a <b>Técnico</b> (barra lateral) para el detalle operativo.
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Meta k="Carril / SLA" v={`${d.lane_meta.label} · ${d.lane_meta.sla}`} />
            <Meta k="Riesgo" v={`${task.risk_score}/100 · ${task.priority}`} />
            <Meta k="Fase actual" v={PHASE_META[currentPhaseId].label} />
            <Meta k="Anillos desplegados" v={`${d.rings_done}/${a.deployment.rings.length}`} />
            <Meta k="CIs impactados" v={String(a.impact.affected_count)} />
            <Meta k="Servicios de negocio" v={a.impact.business_services.length ? a.impact.business_services.join(", ") : "—"} />
            <Meta k="Due date" v={task.sla_due.slice(0, 10)} />
            <Meta k="Rollback" v={a.deployment.rollback.triggered ? "Ejecutado" : "Armado"} />
          </div>
        </div>
      )}

      {/* Phase stepper */}
      <div className="card p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="text-sm font-semibold">Ciclo de remediación · 6 fases</div>
          <div className="text-xs text-gray-500">ServiceNow gobierna · Devin ejecuta · HITL en cada transición</div>
        </div>
        <div className="flex items-center">
          {d.phases.map((p, i) => {
            const isCur = i === d.phase_index;
            const st = p.status;
            const color = st === "approved" ? "#22c55e" : isCur ? PHASE_META[p.id].color : "#3f4756";
            return (
              <div key={p.id} className="flex items-center flex-1 last:flex-none">
                <button onClick={() => setSel(i)}
                  className={`flex flex-col items-center gap-1 ${sel === i ? "" : "opacity-80 hover:opacity-100"}`}>
                  <div className="w-9 h-9 rounded-full flex items-center justify-center text-sm font-bold border-2"
                    style={{ borderColor: color, background: sel === i ? color + "22" : "transparent", color }}>
                    {st === "approved" ? "✓" : i + 1}
                  </div>
                  <span className="text-[11px] font-medium" style={{ color: sel === i ? color : "#94a3b8" }}>{p.label}</span>
                  <span className="text-[13px] leading-none" title={AUTOMATION_META[p.automation]?.label}>{AUTOMATION_META[p.automation]?.icon}</span>
                </button>
                {i < d.phases.length - 1 && (
                  <div className="flex-1 h-0.5 mx-1 mb-4" style={{ background: st === "approved" ? "#22c55e" : "#2b313d" }} />
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Carril operativo (velocidad/riesgo) — flujo TO-BE + automatización */}
      {isTech && (
      <div className="card p-4" style={{ borderLeft: `3px solid ${LANE_META[d.lane].dot}` }}>
        <div className="flex items-center justify-between mb-1 flex-wrap gap-2">
          <div className="text-sm font-semibold flex items-center gap-2">
            Carril operativo · <LaneTag lane={d.lane} />
            <span className="text-xs font-normal text-gray-400">{d.lane_meta.sla}</span>
          </div>
          <div className="flex items-center gap-1.5">
            {(["agentable", "ai_assisted", "human"] as const).map((k) => (
              <span key={k} className="text-[11px] text-gray-500 flex items-center gap-1">
                {AUTOMATION_META[k].icon}{AUTOMATION_META[k].label}
              </span>
            ))}
          </div>
        </div>
        <div className="text-xs text-gray-500 mb-3">
          Asignado por el triage (CMDB como risk engine) · {d.lane_meta.automation}
        </div>
        <div className="flex flex-wrap items-stretch gap-2">
          {d.lane_flow.shared.map((s, i) => (
            <FlowCard key={`sh${i}`} s={s} shared />
          ))}
          <div className="flex items-center text-gray-600 px-1">→</div>
          {d.lane_flow.steps.map((s, i) => (
            <FlowCard key={`st${i}`} s={s} />
          ))}
        </div>
      </div>
      )}

      {/* Mapa de dependencias y afectados — visible siempre en la Remediation Task */}
      <div className="card p-5">
        <div className="mb-3">
          <div className="text-sm font-semibold text-gray-100">Mapa de dependencias y afectados (Impact Graph)</div>
          <div className="text-xs text-gray-500 mt-0.5 leading-relaxed">
            Blast radius de la vulnerabilidad calculado desde la CMDB (relaciones CI→CI). Raíz: <span className="font-mono text-gray-300">{task.ci_name}</span> ·
            {" "}{a.impact.affected_count} CIs afectados · capas: {a.impact.affected_layers.join(", ")}.
          </div>
        </div>
        <div className="flex flex-wrap gap-2 mb-3 text-xs">
          <span className="chip bg-red-500/15 text-red-300 border border-red-500/30">Raíz vulnerable: {task.ci_name}</span>
          <span className="chip bg-ink-panel text-gray-300 border border-line">{a.impact.affected_count} CIs afectados</span>
          {a.impact.business_services.map((s) => (
            <span key={s} className="chip bg-purple-500/15 text-purple-300 border border-purple-500/30">svc: {s}</span>
          ))}
        </div>
        <ImpactGraphView nodes={a.impact.nodes} edges={a.impact.edges} height={340} />
        <div className="mt-2 text-[11px] text-gray-500 leading-relaxed">
          Devin selecciona los activos a remediar a partir de este grafo: los CIs dependientes del nodo raíz son los que quedan
          expuestos por la vulnerabilidad y determinan el alcance de los anillos de despliegue.
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-2.5 text-sm text-red-300 flex items-start justify-between gap-3">
          <span>
            <b>{error.code}</b> — {error.message}
            {error.correlationId && <span className="text-red-400/70 font-mono text-xs"> · {error.correlationId}</span>}
          </span>
          <button className="text-xs text-red-200/70 hover:text-red-100" onClick={() => setError(null)}>cerrar</button>
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
        {/* Artifact panel */}
        <div className="xl:col-span-2 space-y-5">
          <PhaseArtifacts phaseId={selPhaseId} d={d} busy={locked} isTech={isTech}
            onPreapprove={preapproveRing} onSaveAssets={saveRingAssets} />
        </div>

        {/* Agent + HITL column */}
        <div className="space-y-5">
          <div className="card overflow-hidden">
            <div className="px-4 py-3 border-b border-line flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-brand animate-pulse" />
              <div className="text-sm font-semibold">Devin · {PHASE_META[selPhaseId].label}</div>
            </div>
            <div className="p-3 space-y-2 max-h-[300px] overflow-y-auto">
              {phaseLogs.map((l, i) => (
                <div key={i} className="text-xs flex gap-2">
                  <span className={`chip shrink-0 h-fit ${l.actor === "Devin" ? "bg-brand/15 text-brand" : l.actor.includes("Owner") || l.actor.includes("HITL") ? "bg-amber-500/15 text-amber-300" : "bg-sky-500/15 text-sky-300"}`}>
                    {l.actor}
                  </span>
                  <span className="text-gray-400 leading-relaxed">{l.msg}</span>
                </div>
              ))}
              {phaseLogs.length === 0 && <div className="text-xs text-gray-600">Fase pendiente. El agente trabajará al llegar aquí.</div>}
            </div>
          </div>

          {(activeJob || (d.jobs?.length ?? 0) > 0) && (
            <JobCard job={activeJob ?? d.jobs![0]} execution={d.execution}
              busy={busy} onCancel={cancelJob} />
          )}

          {/* HITL control */}
          <div className="card p-4">
            <div className="text-sm font-semibold mb-1">Aprobación humana (HITL)</div>
            {done ? (
              <div className="space-y-3">
                <div className="text-xs text-green-400">Tarea remediada. Vulnerable Item cerrado con evidencia de auditoría.</div>
                <div className="text-xs text-gray-400">¿Anomalía detectada en producción tras el despliegue? Puedes ejecutar un rollback.</div>
                <button disabled={locked} onClick={rollback}
                  className="btn w-full justify-center btn-ghost border border-amber-500/40 text-amber-300 hover:bg-amber-500/10">
                  {locked ? "Procesando…" : "⟲ Ejecutar rollback del último anillo"}
                </button>
              </div>
            ) : (
              <>
                <div className="text-xs text-gray-400 mb-3">
                  Fase actual: <span className="font-semibold" style={{ color: PHASE_META[currentPhaseId].color }}>{PHASE_META[currentPhaseId].label}</span>.
                  {currentPhaseId === "deployment"
                    ? ` Aprobar despliega el siguiente anillo (${d.rings_done}/5 completados).`
                    : " Devin propone; el owner aprueba para avanzar."}
                </div>
                {!canApprove && currentPhaseId === "lab_testing" && (
                  <div className="text-xs text-red-400 mb-2">⚠ El MVT ha fallado en laboratorio. ServiceNow bloquea el avance (rollback / análisis).</div>
                )}
                {labPatch && currentPhaseId === "deployment" && !done && (
                  <div className="text-xs text-green-400 mb-2">
                    ✓ La instancia ya está parcheada y verificada: los anillos restantes se
                    aprueban y se cierran con esa evidencia, sin relanzar la Automation.
                  </div>
                )}
                {!nextRingPreapproved && currentPhaseId === "deployment" && nextRing && (
                  <div className="text-xs text-amber-300 mb-2">⚠ El anillo {nextRing.ring} requiere revisión y <b>pre-aprobación Human-Driven</b> de su informe pre-anillo (arriba, en Fase 6) antes de desplegar.</div>
                )}
                {jobRunning && (
                  <div className="text-xs text-amber-300 mb-2">⏳ Job {activeJob!.id} en curso ({JOB_STATE_LABEL[activeJob!.state] ?? activeJob!.state}). Las acciones mutativas están bloqueadas hasta que finalice.</div>
                )}
                {lastJob?.terminal && lastJob.dry_run && (
                  <div className="text-xs text-sky-300 mb-2">
                    ⓘ Job {lastJob.id} terminado en <b>dry-run</b>: se ha validado el objetivo y
                    planificado la Automation, pero no se ha aplicado nada ni ha avanzado el anillo.
                    El detalle está arriba, en «Ejecución del parche».
                  </div>
                )}
                <button disabled={locked || !canApprove} onClick={approve}
                  className={`btn w-full justify-center ${canApprove && !locked ? "btn-brand" : "btn-ghost opacity-50 cursor-not-allowed"}`}>
                  {locked ? "Procesando…" : currentPhaseId === "deployment" ? "Aprobar y desplegar anillo" : "Aprobar fase y avanzar"}
                </button>
                {currentPhaseId === "deployment" && d.rings_done > 0 && (
                  <div className="mt-3 pt-3 border-t border-line space-y-2">
                    <div className="text-[11px] text-gray-500">Gestión de rollback (anillo {d.rings_done} desplegado)</div>
                    <button disabled={locked} onClick={rollback}
                      className="btn w-full justify-center btn-ghost border border-amber-500/40 text-amber-300 hover:bg-amber-500/10 text-xs">
                      ⟲ Rollback manual del anillo
                    </button>
                    <button disabled={locked} onClick={simulate}
                      className="btn w-full justify-center btn-ghost border border-red-500/40 text-red-300 hover:bg-red-500/10 text-xs">
                      ⚠ Simular incidente → rollback automático
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/** Parcheo ya confirmado por AWS: estado del objetivo, no de un intento. */
function PatchConfirmed({ evidence }: { evidence: LabPatchEvidence }) {
  return (
    <div className="rounded-lg border border-green-500/40 bg-green-500/10 px-4 py-3 text-sm text-green-300">
      <div className="font-semibold flex items-center gap-2">
        <span className="text-lg">✓</span> Parcheo confirmado por AWS Systems Manager
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-2 text-xs text-gray-300">
        <Meta k="Kernel actual" v={evidence.kernel ?? "—"} />
        <Meta k="Instancia" v={evidence.instance_id ?? "—"} />
        <Meta k="Automation" v={evidence.execution_id} />
        <Meta k="Confirmado" v={evidence.patched_at ? new Date(evidence.patched_at).toLocaleString("es-ES") : "—"} />
      </div>
      <div className="text-[11px] text-green-200/80 mt-2">
        La instancia está en la versión corregida: los anillos que aún queden por aprobar la
        resuelven como objetivo y se cierran con esta evidencia, sin relanzar la Automation. Para
        repetir el parcheo hay que resetear el laboratorio, que recrea la instancia desde la AMI
        vulnerable.
      </div>
    </div>
  );
}

/** Estado del job de parcheo/restauración: provider, modo, objetivo y pasos. */
function JobCard({ job, execution, busy, onCancel }: {
  job: PatchJob;
  execution?: TD["execution"];
  busy: boolean;
  onCancel: (jobId: string) => void;
}) {
  const target = job.targets[0];
  const running = !job.terminal;
  return (
    <div className="card overflow-hidden">
      <div className="px-4 py-3 border-b border-line flex items-center justify-between gap-2">
        <div className="text-sm font-semibold">Ejecución del parche</div>
        <span className={`chip ${jobTone(job.state)}`}>{JOB_STATE_LABEL[job.state] ?? job.state}</span>
      </div>
      <div className="p-4 space-y-2 text-xs">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="chip bg-ink border border-line text-gray-300">{executionModeLabel(job)}</span>
          {job.dry_run && <span className="chip bg-sky-500/15 text-sky-300">dry-run · el parche NO se ha aplicado</span>}
          {job.unconfirmed && (
            <span className="chip bg-orange-500/15 text-orange-300">estado remoto sin confirmar · el objetivo sigue bloqueado</span>
          )}
          <span className="text-gray-500">{job.job_type === "patch" ? "parcheo" : job.job_type === "rollback" ? "rollback" : "reset de laboratorio"}</span>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <Meta k="Job" v={job.id} />
          <Meta k="Provider" v={job.provider} />
          <Meta k="Anillo" v={job.ring_number ? String(job.ring_number) : "—"} />
          <Meta k="Referencia" v={job.provider_reference ?? "—"} />
        </div>
        {target && (
          <div className="grid grid-cols-2 gap-2">
            <Meta k="Objetivo" v={target.name || target.logical_target_id} />
            <Meta k="Instance ID" v={target.instance_id ?? "sin resolver"} />
            <Meta k="Región" v={target.region ?? "—"} />
            <Meta k="SSM" v={target.ssm_managed ? "gestionado" : "no gestionado"} />
          </div>
        )}
        {execution && (
          <div className="text-[11px] text-gray-600">
            Modo {execution.mode}{execution.strict_policy ? " · política fail-closed" : " · política relajada (mock/dry-run)"} · refresco cada {execution.poll_interval_seconds}s · provider de restauración {execution.restore_provider}{execution.reconciler?.running ? " · reconciliador activo en el backend" : ""}
          </div>
        )}
        {job.error_code && (
          <div className="rounded border border-red-500/40 bg-red-500/10 px-3 py-2 text-red-300">
            <b>{job.error_code}</b> — {job.error_message}
            <div className="font-mono text-[10px] text-red-400/70">{job.correlation_id}</div>
            {alreadyFixed(job) && (
              <div className="text-[11px] text-amber-200 mt-1">
                El runbook abortó porque la instancia <b>ya tenía el kernel corregido</b>: es un
                intento rechazado sobre un objetivo ya parcheado, no un parcheo fallido.
              </div>
            )}
          </div>
        )}
        {job.steps.length > 0 && (
          <div className="space-y-1 max-h-[220px] overflow-y-auto">
            {job.steps.map((s) => (
              <div key={s.seq} className="rounded border border-line bg-ink px-2 py-1.5">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-[11px] text-gray-300 truncate">{s.command}</span>
                  <span className={`chip shrink-0 ${s.status === "ok" ? "bg-green-500/15 text-green-400" : s.status === "planned" ? "bg-sky-500/15 text-sky-300" : s.status === "failed" ? "bg-red-500/15 text-red-400" : "bg-amber-500/15 text-amber-300"}`}>{s.status}</span>
                </div>
                <div className="text-[11px] text-gray-500 mt-0.5 break-words">{s.output}</div>
              </div>
            ))}
          </div>
        )}
        {job.events && job.events.length > 0 && (
          <div className="text-[11px] text-gray-600">
            Último evento: {job.events[job.events.length - 1].message}
          </div>
        )}
        {running && (
          <button disabled={busy} onClick={() => onCancel(job.id)}
            className="btn w-full justify-center btn-ghost border border-line text-gray-300 text-xs">
            Cancelar job
          </button>
        )}
      </div>
    </div>
  );
}

function FlowCard({ s, shared }: { s: FlowStep; shared?: boolean }) {
  return (
    <div className={`rounded-lg border p-2 min-w-[130px] max-w-[160px] ${shared ? "border-line bg-ink/60" : "border-line bg-ink"}`}>
      <div className="flex items-center justify-between gap-1 mb-1">
        <span className="text-[13px] leading-none" title={AUTOMATION_META[s.automation]?.label}>{AUTOMATION_META[s.automation]?.icon}</span>
        <span className="text-[10px] text-gray-500 font-mono">{s.sla}</span>
      </div>
      <div className="text-[11px] font-semibold text-gray-200 leading-tight">{s.name}</div>
      <div className="text-[10px] text-gray-500 mt-0.5 leading-snug">{s.detail}</div>
      <div className="text-[10px] text-gray-600 mt-1">{s.mode}</div>
    </div>
  );
}

function Meta({ k, v }: { k: string; v: string }) {
  return (
    <div className="bg-ink rounded-lg px-3 py-2 border border-line">
      <div className="text-[10px] text-gray-500 uppercase tracking-wide">{k}</div>
      <div className="text-gray-200 font-medium mt-0.5">{v}</div>
    </div>
  );
}

// -------------------- per-phase artifacts --------------------
function PhaseArtifacts({ phaseId, d, busy, isTech, onPreapprove, onSaveAssets }: {
  phaseId: string; d: TD; busy: boolean; isTech: boolean;
  onPreapprove: (ring: number) => void;
  onSaveAssets: (ring: number, excluded: string[]) => void;
}) {
  const { artifacts: a, task, vulnerable_item: vi } = d;

  if (phaseId === "detection")
    return (
      <Panel title="Fase 1 · Detección e ingesta" sub="ServiceNow Vulnerability Response — normalización y correlación con CMDB">
        <div className="grid grid-cols-2 gap-3 text-sm">
          <Meta k="Vulnerable Item" v={vi.id} />
          <Meta k="Detectado" v={vi.detected_at.slice(0, 10)} />
          <Meta k="Identificador" v={vi.cve} />
          <Meta k="CI asociado" v={`${vi.ci_id} (${vi.ci_class})`} />
        </div>
        <div className="mt-3">
          <div className="text-xs text-gray-500 mb-1">Fuentes correlacionadas (deduplicadas)</div>
          <div className="flex flex-wrap gap-2">
            {vi.sources.map((s) => <span key={s} className="chip bg-ink-panel text-gray-300 border border-line">{s}</span>)}
          </div>
        </div>
      </Panel>
    );

  if (phaseId === "prioritization")
    return (
      <Panel title="Fase 2 · Priorización" sub="Prioridad = riesgo técnico + negocio + operativo + SLA (no solo CVSS)">
        <div className="space-y-2">
          {[
            ["Riesgo técnico (CVSS)", vi.cvss * 4, 40, `CVSS ${vi.cvss}`],
            ["Explotabilidad (EPSS/KEV)", vi.epss * 20 + (vi.kev ? 12 : 0), 32, `EPSS ${(vi.epss * 100).toFixed(0)}% ${vi.kev ? "· KEV" : ""}`],
            ["Contexto de negocio", { critical: 18, high: 12, medium: 6, low: 2 }[task.criticality] || 6, 18, `${task.criticality}`],
            ["Exposición", task.exposed ? 10 : 0, 10, task.exposed ? "Internet-facing" : "Interno"],
          ].map(([label, val, max, note]: any) => (
            <div key={label}>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-gray-300">{label} <span className="text-gray-600">· {note}</span></span>
                <span className="font-mono text-gray-400">{Math.round(val)}/{max}</span>
              </div>
              <div className="h-2 rounded bg-ink"><div className="h-2 rounded bg-brand" style={{ width: `${(val / max) * 100}%` }} /></div>
            </div>
          ))}
        </div>
        <div className="mt-4 p-3 rounded-lg bg-ink border border-line text-sm">
          <div className="text-xs text-brand font-semibold mb-1">Reachability analysis (Devin)</div>
          {task.track === "B"
            ? <span className="text-gray-300">Devin analizó el repositorio <span className="font-mono text-xs">{task.ci_name}</span>: el componente <span className="font-mono text-xs">{vi.component}</span> {task.exposed ? "ES alcanzable en runtime → mantiene prioridad alta." : "no es alcanzable directamente → candidato a excepción documentada."}</span>
            : task.track === "C"
            ? <span className="text-gray-300">Devin analizó la imagen/manifiestos de <span className="font-mono text-xs">{task.ci_name}</span>: <span className="font-mono text-xs">{vi.component}</span> presente en la imagen base {task.exposed ? "y expuesto vía ingress → prioridad alta; requiere rebuild de imagen." : "sin exposición directa → rebuild programado en ventana."}</span>
            : <span className="text-gray-300">Activo de infraestructura {task.exposed ? "expuesto a internet" : "interno"}; prioridad ajustada por ventana de mantenimiento y criticidad del servicio.</span>}
        </div>
      </Panel>
    );

  if (phaseId === "pre_implementation")
    return (
      <>
        <Panel title="Fase 3 · Impact Graph (blast radius)" sub={`Devin enriqueció el grafo desde CMDB + repos/SBOM · ${a.impact.affected_count} CIs, capas: ${a.impact.affected_layers.join(", ")}`}>
          <ImpactGraphView nodes={a.impact.nodes} edges={a.impact.edges} height={360} />
          {a.impact.business_services.length > 0 && (
            <div className="mt-2 text-xs text-gray-400">Servicios de negocio impactados: <span className="text-purple-300">{a.impact.business_services.join(", ")}</span></div>
          )}
        </Panel>
        <Panel title="Minimum Viable Test Plan (MVT)" sub={a.mvt.rationale}>
          <div className="flex items-center gap-3 mb-3">
            <div className="chip bg-brand/15 text-brand">Confianza {a.mvt.confidence}%</div>
            <div className="chip bg-green-500/15 text-green-400">{a.mvt.selected.length} incluidas</div>
            <div className="chip bg-gray-500/15 text-gray-400">{a.mvt.excluded.length} excluidas</div>
          </div>
          <TestTable rows={a.mvt.selected} included />
          <details className="mt-3">
            <summary className="text-xs text-gray-500 cursor-pointer">Ver pruebas excluidas y justificación</summary>
            <div className="mt-2"><TestTable rows={a.mvt.excluded} /></div>
          </details>
        </Panel>
      </>
    );

  if (phaseId === "lab_testing")
    return (
      <Panel title="Fase 4 · Ejecución de pruebas en laboratorio" sub="Devin genera y ejecuta el MVT vía CI/CD y frameworks de test">
        <div className="flex items-center gap-3 mb-4">
          <span className="text-sm">Veredicto agregado:</span> <Verdict v={a.lab.verdict} />
          <span className="text-xs text-gray-400 ml-auto">{a.lab.passed}/{a.lab.total} pruebas OK</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <ResultGroup title="Pruebas de parche" rows={a.lab.patch_tests} />
          <ResultGroup title="Pruebas de aplicación" rows={a.lab.app_tests} />
        </div>
      </Panel>
    );

  if (phaseId === "prototype")
    return (
      <Panel title="Fase 5 · Validación en entorno de prototipo" sub={`Devin aprovisiona un lab (${a.prototype.approach}) con IaC derivado del Impact Graph`}>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          <Meta k="Enfoque" v={a.prototype.approach} />
          <Meta k="Provisión" v={a.prototype.provision_tool} />
          <Meta k="Teardown" v={a.prototype.teardown} />
          <Meta k="Veredicto" v={a.prototype.verdict.toUpperCase()} />
        </div>
        <div className="text-xs text-gray-500 mb-1">Lab Blueprint (componentes aprovisionados)</div>
        <div className="space-y-1 mb-4">
          {a.prototype.lab_blueprint.map((c, i) => (
            <div key={i} className="flex items-center gap-2 text-sm bg-ink rounded-lg px-3 py-1.5 border border-line">
              <span className="chip bg-teal-500/15 text-teal-300">{c.tool}</span>
              <span className="text-gray-300">{c.type}</span>
              <span className="text-gray-500 text-xs ml-auto font-mono">{c.spec}</span>
            </div>
          ))}
        </div>
        <div className="grid grid-cols-4 gap-3">
          {Object.entries(a.prototype.metrics).map(([k, v]) => (
            <Meta key={k} k={k.replace(/_/g, " ")} v={String(v)} />
          ))}
        </div>
      </Panel>
    );

  // deployment
  const rb = a.deployment.rollback;
  return (
    <>
      {a.deployment.itsm && <ItsmChangePanel itsm={a.deployment.itsm} />}

      <ImplementationControlPanel dep={a.deployment} ringsDone={d.rings_done} busy={busy}
        onPreapprove={onPreapprove} />

      {isTech && (
      <Panel title="Fase 6 · Despliegue por anillos (detalle técnico)" sub={`${a.deployment.strategy} · ejecutor: ${a.deployment.executor} · ${a.deployment.total_assets} activos`}>
        {a.deployment.pr_url && (
          <a href={a.deployment.pr_url} target="_blank" className="chip bg-emerald-500/15 text-emerald-300 mb-3 inline-flex">PR de remediación: {a.deployment.pr_url.split("/").slice(-2).join("/")}</a>
        )}
        <div className="text-xs text-gray-500 mb-2 leading-relaxed">
          Cada anillo lleva un <b>informe pre-anillo</b> con la selección de activos que ha hecho Devin y su justificación.
          El owner revisa, edita la selección si procede, <b>verifica y pre-aprueba (Human-Driven)</b> antes de que se pueda desplegar.
        </div>
        <div className="space-y-2">
          {a.deployment.rings.map((r) => (
            <RingRow key={r.ring} r={r} busy={busy} isTech={isTech}
              onPreapprove={onPreapprove} onSaveAssets={onSaveAssets} />
          ))}
        </div>
        {a.deployment.exceptions.length > 0 && (
          <div className="mt-4">
            <div className="text-xs text-gray-500 mb-1">Excepciones trazables</div>
            {a.deployment.exceptions.map((e, i) => (
              <div key={i} className="text-xs bg-amber-500/10 border border-amber-500/20 rounded-lg px-3 py-2 text-amber-200">
                <span className="font-mono">{e.asset}</span> — {e.reason}. Control compensatorio: {e.compensating_control}. Expira {e.expires.slice(0, 10)}.
              </div>
            ))}
          </div>
        )}
      </Panel>
      )}

      <Panel title="Gestión de Rollback" sub={`Plan armado desde el inicio y probado en lab · estrategia: ${a.deployment.rollback_plan.strategy}`}>
        {rb.triggered && (
          <div className="mb-4 rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3">
            <div className="flex items-center gap-2 mb-1">
              <span className="chip bg-amber-500/20 text-amber-300">ROLLBACK EJECUTADO</span>
              <span className="chip bg-ink-panel text-gray-400">{rb.trigger_type === "auto" ? "automático" : "manual"}</span>
              <span className="text-xs text-gray-500 ml-auto">anillo {rb.ring}</span>
            </div>
            <div className="text-xs text-amber-200">{rb.reason}</div>
            <div className="text-xs text-gray-400 mt-1">Versión restaurada: <span className="font-mono text-gray-200">{rb.restored_version}</span> · {rb.verdict}</div>
          </div>
        )}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          <Meta k="Estrategia" v={a.deployment.rollback_plan.strategy} />
          <Meta k="RTO objetivo" v={`${a.deployment.rollback_plan.rto_minutes} min`} />
          <Meta k="Versión estable" v={a.deployment.rollback_plan.target_version} />
          <Meta k="Probado en lab" v={a.deployment.rollback_plan.tested_in_lab ? "Sí" : "No"} />
        </div>
        <div className="text-xs text-gray-500 mb-1">Disparo automático: {a.deployment.rollback_plan.auto_trigger}</div>
        <div className="text-xs text-gray-500 mb-1 mt-3">Pasos del plan de rollback</div>
        <div className="space-y-1">
          {a.deployment.rollback_plan.steps.map((s, i) => (
            <div key={i} className="flex items-start gap-2 text-xs bg-ink rounded-lg px-3 py-2 border border-line">
              <span className="chip bg-amber-500/15 text-amber-300 shrink-0">{i + 1}</span>
              <span className={`chip shrink-0 ${s.actor === "Devin" ? "bg-brand/15 text-brand" : "bg-sky-500/15 text-sky-300"}`}>{s.actor}</span>
              <div className="flex-1">
                {isTech && <code className="text-gray-200">{s.command}</code>}
                <div className="text-gray-500 mt-0.5">{s.desc}</div>
              </div>
            </div>
          ))}
        </div>
      </Panel>

      <Panel title="Informe de auditoría (audit-ready)" sub={`Devin genera el informe automáticamente · ${a.audit.report_id} · ${a.audit.evidences_count} evidencias${a.audit.dora_relevant ? " · DORA relevante" : ""}`}>
        <div className="space-y-1">
          {a.audit.trace.map((t, i) => (
            <div key={i} className="flex items-center gap-3 text-sm">
              <span className="w-2 h-2 rounded-full bg-brand shrink-0" />
              <span className="text-gray-300 w-40 shrink-0">{t.step}</span>
              <span className="font-mono text-xs text-gray-500 w-40 shrink-0 truncate">{t.ref}</span>
              <span className="text-gray-400 text-xs">{t.detail}</span>
            </div>
          ))}
        </div>
      </Panel>
    </>
  );
}

function RingRow({ r, busy, isTech, onPreapprove, onSaveAssets }: {
  r: Ring; busy: boolean; isTech: boolean;
  onPreapprove: (ring: number) => void;
  onSaveAssets: (ring: number, excluded: string[]) => void;
}) {
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [excluded, setExcluded] = useState<string[]>(
    r.plan.assets.filter((x) => x.excluded).map((x) => x.id));
  const hasActions = !!r.actions && r.actions.steps.length > 0;
  const pa = r.plan.approval;
  const statusChip =
    r.status === "completed" ? "bg-green-500/15 text-green-400"
    : r.status === "rolled_back" ? "bg-amber-500/15 text-amber-300"
    : r.status === "in_progress" ? "bg-sky-500/15 text-sky-300"
    : "bg-gray-500/15 text-gray-400";
  const icon =
    r.status === "completed" ? "✓" : r.status === "rolled_back" ? "⟲" : r.status === "in_progress" ? "▶" : "·";
  const toggle = (idClicked: string) =>
    setExcluded((e) => e.includes(idClicked) ? e.filter((x) => x !== idClicked) : [...e, idClicked]);

  return (
    <div className="bg-ink rounded-lg border border-line">
      <button onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-3 px-3 py-2 text-left cursor-pointer">
        <span className={`chip ${statusChip}`}>{icon}</span>
        <div className="flex-1">
          <div className="text-sm text-gray-200">{r.label}</div>
          {r.health ? (
            <div className="text-[11px] text-gray-500">
              err {r.health.error_rate_pct}% · p95 {r.health.p95_latency_ms}ms · avail {r.health.availability_pct}%
            </div>
          ) : (
            <div className="text-[11px] text-gray-500">
              {r.plan.is_replica ? "réplica de infra" : `real ${r.plan.pct}%`}
              {r.plan.runs_tests ? " · pruebas ✓" : ""} · {r.plan.window}
            </div>
          )}
        </div>
        {pa.preapproved
          ? <span className="chip bg-brand/15 text-brand" title={pa.note || ""}>pre-aprobado 👤</span>
          : r.status === "pending" || r.status === "in_progress"
          ? <span className="chip bg-amber-500/15 text-amber-300">requiere pre-aprobación</span>
          : null}
        <span className="text-xs text-gray-400">{r.plan.assets_count} CIs impactados</span>
        {r.result !== "-" && (
          <span className={`chip ${r.status === "rolled_back" ? "bg-amber-500/10 text-amber-300" : "bg-green-500/10 text-green-400"}`}>{r.result}</span>
        )}
        <span className="text-gray-500 text-xs w-4">{open ? "▾" : "▸"}</span>
      </button>

      {open && (
        <div className="border-t border-line px-3 py-3 space-y-3">
          {/* Informe pre-anillo */}
          <div className="rounded-lg bg-ink-panel border border-line p-3">
            <div className="text-[11px] font-bold text-brand tracking-wider mb-1">INFORME PRE-ANILLO · selección de Devin</div>
            <div className="text-xs text-gray-400 leading-relaxed">{r.plan.selection_rationale}</div>
            <div className="mt-2 grid grid-cols-1 md:grid-cols-2 gap-1.5">
              {r.plan.selection_criteria.map((c, i) => (
                <div key={i} className="text-[11px] text-gray-500">
                  <span className="text-gray-300 font-medium">{c.factor}:</span> {c.detail}
                </div>
              ))}
            </div>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {r.plan.entry_criteria.map((c, i) => (
                <span key={i} className={`chip text-[10px] ${c.ok ? "bg-green-500/10 text-green-400 border border-green-500/20" : "bg-red-500/10 text-red-300 border border-red-500/30"}`}>
                  {c.ok ? "✓" : "✗"} {c.check}
                </span>
              ))}
            </div>
          </div>

          {/* Subgrafo del anillo: SOLO los CIs impactados de este anillo + sus dependencias */}
          {r.plan.graph.nodes.length > 0 && (
            <div className="rounded-lg bg-ink-panel border border-line p-2">
              <div className="text-[11px] text-gray-500 mb-1">
                CIs impactados de este anillo y sus dependencias (subgrafo del Impact Graph)
              </div>
              <ImpactGraphView nodes={r.plan.graph.nodes} edges={r.plan.graph.edges} height={200} />
            </div>
          )}

          {/* CIs impactados del anillo (revisables / editables) */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <div className="text-[11px] text-gray-500">
                CIs impactados en el anillo ({r.plan.selected_count}/{r.plan.assets_count})
              </div>
              {isTech && (r.status === "pending" || r.status === "in_progress") && (
                <button onClick={() => setEditing((v) => !v)} className="btn btn-ghost text-[11px]">
                  {editing ? "Cancelar edición" : "✎ Editar selección"}
                </button>
              )}
            </div>
            {r.plan.assets.length === 0 && (
              <div className="text-[11px] text-gray-600">Sin CIs impactados en la banda de este anillo.</div>
            )}
            <div className="space-y-1">
              {r.plan.assets.map((as) => {
                const isExcl = excluded.includes(as.id);
                return (
                  <div key={as.id} className={`flex items-start gap-2 text-[11px] rounded-lg px-2 py-1.5 border ${isExcl ? "border-red-500/30 bg-red-500/5 opacity-70" : "border-line bg-ink"}`}>
                    {editing && (
                      <input type="checkbox" checked={!isExcl} onChange={() => toggle(as.id)} className="mt-0.5" title="Incluir en el anillo" />
                    )}
                    <span className={`chip shrink-0 ${isExcl ? "bg-red-500/15 text-red-300" : "bg-sky-500/15 text-sky-300"}`}>{as.ci_class}</span>
                    <div className="flex-1 min-w-0">
                      <div className="font-mono text-gray-300 truncate">
                        {as.name} {as.is_root && <span className="chip bg-red-500/15 text-red-300">raíz</span>}
                        <span className="text-gray-600"> · {as.criticality} · {as.environment}</span>
                      </div>
                      <div className="text-gray-500 truncate">{as.reason}</div>
                    </div>
                    {isExcl && <span className="chip bg-red-500/15 text-red-300 shrink-0">excluido</span>}
                  </div>
                );
              })}
            </div>
            {editing && (
              <button disabled={busy} onClick={() => { onSaveAssets(r.ring, excluded); setEditing(false); }}
                className="btn btn-ghost border border-brand/40 text-brand text-[11px] mt-2">
                Guardar selección editada ({excluded.length} excluido/s)
              </button>
            )}
          </div>

          {/* Dependencias de los CIs impactados del anillo */}
          {r.plan.dependencies.length > 0 && (
            <div>
              <div className="text-[11px] text-gray-500 mb-1">
                Dependencias afectadas ({r.plan.dependencies.length}) — CIs vinculados a los impactados
              </div>
              <div className="space-y-1">
                {r.plan.dependencies.map((dep) => (
                  <div key={dep.id} className="flex items-start gap-2 text-[11px] rounded-lg px-2 py-1.5 border border-line bg-ink">
                    <span className="chip shrink-0 bg-purple-500/15 text-purple-300">{dep.ci_class}</span>
                    <div className="flex-1 min-w-0">
                      <div className="font-mono text-gray-300 truncate">{dep.name} <span className="text-gray-600">· {dep.criticality}</span></div>
                      <div className="text-gray-500 truncate">{dep.relation} · vinculado a {dep.of}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Revisión / pre-aprobación Human-Driven */}
          {pa.preapproved ? (
            <div className="rounded-lg border border-brand/30 bg-brand/5 px-3 py-2 text-[11px] text-gray-300">
              <span className="text-brand font-semibold">✓ Informe verificado y pre-aprobado (Human-Driven)</span>
              {pa.approver && <> · por <span className="font-mono">{pa.approver}</span></>}
              {pa.ts && <> · {pa.ts.slice(0, 16).replace("T", " ")}</>}
              {pa.note && <div className="text-gray-500 mt-0.5">{pa.note}</div>}
            </div>
          ) : (r.status === "pending" || r.status === "in_progress") ? (
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 px-3 py-2 flex items-center gap-3">
              <div className="text-[11px] text-amber-200 flex-1">
                Auditoría Human-Driven requerida: revisa el informe y los activos, edítalos si procede y verifica antes de desplegar.
              </div>
              <button disabled={busy} onClick={() => onPreapprove(r.ring)}
                className="btn btn-brand text-[11px]">✓ Verificar y pre-aprobar</button>
            </div>
          ) : null}

          {/* Acciones ejecutadas con el por qué de cada comando */}
          {isTech && hasActions && r.actions && (
            <div className="border-t border-line pt-2 space-y-1.5 font-mono text-[11px]">
              <div className="text-gray-500 mb-1">Acciones ejecutadas · {r.actions.from_version} → {r.actions.to_version}</div>
              {r.actions.steps.map((s) => (
                <div key={s.seq} className="flex items-start gap-2">
                  <span className={`chip shrink-0 ${s.actor === "Devin" ? "bg-brand/15 text-brand" : s.tool === "post-check" ? "bg-purple-500/15 text-purple-300" : "bg-sky-500/15 text-sky-300"}`}>{s.actor}</span>
                  <div className="flex-1 min-w-0">
                    <div className="text-gray-300 truncate">$ {s.command}</div>
                    <div className="text-gray-500 truncate">→ {s.output}</div>
                    {s.why && <div className="text-gray-600 italic whitespace-normal mt-0.5">↳ {s.why}</div>}
                  </div>
                  <span className="text-green-400 shrink-0">ok</span>
                  <span className="text-gray-600 shrink-0">{s.duration_s}s</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// -------------------- ITSM Change Management (governance) --------------------
const CHANGE_STYLE: Record<string, { label: string; cls: string; dot: string }> = {
  standard: { label: "Cambio estándar", cls: "bg-green-500/15 text-green-300 border-green-500/30", dot: "#22c55e" },
  normal: { label: "Cambio normal", cls: "bg-sky-500/15 text-sky-300 border-sky-500/30", dot: "#38bdf8" },
  emergency: { label: "Cambio de emergencia", cls: "bg-red-500/15 text-red-300 border-red-500/30", dot: "#ef4444" },
};

function ItsmChangePanel({ itsm }: { itsm: ItsmChange }) {
  const st = CHANGE_STYLE[itsm.type] || CHANGE_STYLE.normal;
  return (
    <Panel title="Gestión de Cambios (ITSM · ServiceNow Change Management)"
      sub="Todo parcheado queda respaldado por un cambio registrado en la herramienta ITSM del cliente: trazabilidad, autorización y evidencias.">
      <div className="flex items-center gap-2 flex-wrap mb-3">
        <span className={`chip border ${st.cls}`}>{itsm.type_label}</span>
        <span className="chip bg-ink text-gray-300 border border-line font-mono">{itsm.number}</span>
        <span className="chip bg-ink text-gray-400 border border-line">Estado: {itsm.state}</span>
        <span className="chip bg-ink text-gray-400 border border-line">Riesgo: {itsm.risk}</span>
        <span className="chip bg-ink text-gray-400 border border-line">Impacto: {itsm.impact_level}</span>
        {itsm.four_eyes && <span className="chip bg-purple-500/15 text-purple-300 border border-purple-500/30" title="Implementación revisada por un segundo técnico">principio 4 ojos 👀</span>}
        {itsm.gxp && <span className="chip bg-amber-500/15 text-amber-300 border border-amber-500/30">GxP relevante</span>}
      </div>

      {/* Change Transaction Phases by Change Type */}
      <div className="text-[11px] text-gray-500 mb-1">Fases de la transacción de cambio · {itsm.type_label}</div>
      <div className="flex items-stretch gap-1 flex-wrap mb-3">
        {itsm.phases.map((p, i) => (
          <div key={p.key} className="flex items-center">
            <div className={`rounded-md border px-2.5 py-1.5 min-w-[92px] ${p.included ? "border-line bg-ink" : "border-dashed border-line/50 bg-transparent opacity-40"}`}
              style={p.included ? { borderLeft: `3px solid ${st.dot}` } : {}}>
              <div className="text-[10px] font-semibold text-gray-200 leading-tight">{p.label}</div>
              {p.approval
                ? <div className={`text-[9px] mt-0.5 ${p.included ? "text-amber-300" : "text-gray-600"}`}>● aprobación</div>
                : <div className="text-[9px] mt-0.5 text-gray-600">{p.included ? "fase" : "no aplica"}</div>}
            </div>
            {i < itsm.phases.length - 1 && <span className="text-gray-700 px-0.5">›</span>}
          </div>
        ))}
      </div>
      <div className="text-[11px] text-gray-500 leading-relaxed mb-3">{itsm.detail}</div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-3">
        <Meta k="Aprobación" v={itsm.approval} />
        <Meta k="Entorno" v={itsm.environment} />
        <Meta k="Parche" v={itsm.patch} />
        <Meta k="CIs afectados" v={String(itsm.affected_cis)} />
      </div>

      {/* Change Tasks (CTASK) — mínimo 3: Assessment / Implementation / Review */}
      <div className="text-[11px] text-gray-500 mb-1">Change Tasks (CTASK)</div>
      <div className="space-y-1">
        {itsm.ctasks.map((c, i) => (
          <div key={i} className="flex items-start gap-2 text-[11px] rounded-lg px-2 py-1.5 border border-line bg-ink">
            <span className="chip bg-sky-500/15 text-sky-300 shrink-0">{i + 1}</span>
            <div className="flex-1 min-w-0">
              <span className="text-gray-200 font-medium">{c.name}</span>
              <span className="text-gray-500"> — {c.role}</span>
            </div>
            {c.auto && <span className="chip bg-green-500/10 text-green-400 shrink-0">automatizable</span>}
          </div>
        ))}
      </div>
    </Panel>
  );
}

// -------------------- Panel de control de implementación (alto nivel) --------------------
const ENV_ICON: Record<string, string> = {
  lab: "🧪", canary: "🐤", preprod: "🔧", prod_controlled: "🎯", prod_full: "🌐",
};
function ringEnvKey(idx: number): string {
  return ["lab", "canary", "preprod", "prod_controlled", "prod_full"][idx] || "prod_full";
}

function ImplementationControlPanel({ dep, ringsDone, busy, onPreapprove }: {
  dep: Deployment; ringsDone: number; busy: boolean; onPreapprove: (ring: number) => void;
}) {
  const next = dep.rings[ringsDone];
  return (
    <Panel title="Panel de control de implementación"
      sub="Promoción por entornos según la realidad del cliente: Laboratorio → Canary → Pre-productivo → Productivo controlado → Productivo total. En Lab y Pre-productivo se levanta una réplica de la infraestructura y se ejecutan todas las pruebas.">
      <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
        {dep.rings.map((r, i) => {
          const stCol =
            r.status === "completed" ? "#22c55e"
            : r.status === "rolled_back" ? "#f59e0b"
            : r.status === "in_progress" ? "#38bdf8" : "#3f4756";
          const stLabel =
            r.status === "completed" ? "Desplegado"
            : r.status === "rolled_back" ? "Revertido"
            : r.status === "in_progress" ? "En curso" : "Pendiente";
          const envKey = ringEnvKey(i);
          return (
            <div key={r.ring} className="rounded-lg border p-3 bg-ink" style={{ borderTop: `3px solid ${stCol}` }}>
              <div className="flex items-center gap-1.5 mb-1">
                <span className="text-lg">{ENV_ICON[envKey]}</span>
                <span className="text-xs font-semibold text-gray-100 leading-tight">{r.plan.environment || r.label}</span>
              </div>
              <div className="text-[10px] font-medium mb-2" style={{ color: stCol }}>{stLabel}</div>
              <div className="space-y-1 text-[10px] text-gray-400">
                <div className="flex items-center gap-1">
                  <span className="chip bg-ink-panel border border-line text-gray-300">{r.plan.assets_count} CIs</span>
                  <span className={`chip ${r.plan.is_replica ? "bg-teal-500/15 text-teal-300" : "bg-sky-500/15 text-sky-300"}`}>
                    {r.plan.is_replica ? "réplica" : `real ${r.plan.pct}%`}
                  </span>
                </div>
                <div>{r.plan.runs_tests
                  ? <span className="text-green-400">✓ pruebas en entorno</span>
                  : <span className="text-gray-500">validación por telemetría</span>}</div>
                {r.status === "completed" && r.health && (
                  <div className="text-gray-500">salud: {r.health.availability_pct}% avail · err {r.health.error_rate_pct}%</div>
                )}
                <div>{r.plan.approval.preapproved
                  ? <span className="text-brand">👤 pre-aprobado</span>
                  : (r.status === "pending" || r.status === "in_progress")
                  ? <span className="text-amber-300">requiere aprobación</span>
                  : <span className="text-gray-600">—</span>}</div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Progreso + acción de aprobación de alto nivel (sin scripts) */}
      <div className="mt-3 flex items-center gap-3 flex-wrap">
        <div className="text-xs text-gray-400">Progreso: <b className="text-gray-200">{ringsDone}/{dep.rings.length}</b> entornos desplegados</div>
        <div className="flex-1 h-2 rounded bg-ink min-w-[120px]">
          <div className="h-2 rounded bg-brand" style={{ width: `${(ringsDone / dep.rings.length) * 100}%` }} />
        </div>
        {dep.rollback.triggered
          ? <span className="chip bg-amber-500/15 text-amber-300">rollback ejecutado (anillo {dep.rollback.ring})</span>
          : <span className="chip bg-green-500/10 text-green-400">rollback armado</span>}
      </div>
      {next && !next.plan.approval.preapproved && (
        <div className="mt-3 rounded-lg border border-amber-500/30 bg-amber-500/5 px-3 py-2 flex items-center gap-3 flex-wrap">
          <div className="text-[11px] text-amber-200 flex-1">
            Siguiente entorno: <b>{next.plan.environment || next.label}</b>. Revisa el informe y verifica la selección de activos antes de promover (auditoría Human-Driven).
          </div>
          <button disabled={busy} onClick={() => onPreapprove(next.ring)} className="btn btn-brand text-[11px]">
            ✓ Verificar y pre-aprobar {next.plan.environment}
          </button>
        </div>
      )}
    </Panel>
  );
}

function Panel({ title, sub, children }: { title: string; sub?: string; children: React.ReactNode }) {
  return (
    <div className="card p-5">
      <div className="mb-3">
        <div className="text-sm font-semibold text-gray-100">{title}</div>
        {sub && <div className="text-xs text-gray-500 mt-0.5 leading-relaxed">{sub}</div>}
      </div>
      {children}
    </div>
  );
}

function TestTable({ rows, included }: { rows: any[]; included?: boolean }) {
  return (
    <div className="overflow-hidden rounded-lg border border-line">
      <table className="w-full text-xs">
        <tbody>
          {rows.map((t) => (
            <tr key={t.id} className="border-b border-line/40 last:border-0">
              <td className="px-3 py-2 font-mono text-gray-500 w-24">{t.id}</td>
              <td className="px-2 py-2 text-gray-200">{t.name}</td>
              <td className="px-2 py-2"><span className="chip bg-ink-panel text-gray-400">{t.layer}</span></td>
              <td className="px-2 py-2 text-gray-500">{t.tool}</td>
              {!included && <td className="px-3 py-2 text-gray-600 max-w-[220px]">{t.reason}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ResultGroup({ title, rows }: { title: string; rows: any[] }) {
  return (
    <div>
      <div className="text-xs text-gray-500 mb-2">{title}</div>
      <div className="space-y-1">
        {rows.length === 0 && <div className="text-xs text-gray-600">—</div>}
        {rows.map((r) => (
          <div key={r.test_id} className="flex items-center gap-2 text-xs bg-ink rounded-lg px-3 py-1.5 border border-line">
            <span className={`w-2 h-2 rounded-full ${r.status === "pass" ? "bg-green-400" : "bg-red-400"}`} />
            <span className="text-gray-200">{r.name}</span>
            <span className="text-gray-600 ml-auto">{r.duration_s}s</span>
          </div>
        ))}
      </div>
    </div>
  );
}
