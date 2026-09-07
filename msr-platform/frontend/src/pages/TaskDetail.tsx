import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { ApiError, api, releaseIdempotencyKey } from "../api";
import type { TaskDetail as TD, FlowStep, HitlGate, Ring, ItsmChange, Deployment, PatchJob, LabPatchEvidence,
  ExecutionMode } from "../types";
import { Priority, Track, Risk, KevTag, PHASE_META, LaneTag, LANE_META, AUTOMATION_META, SlaTag } from "../ui";
import ImpactGraphView from "../components/ImpactGraphView";
import LabPanel from "../components/LabPanel";
import { DemoAdvanceControl, HitlRail } from "../components/flow";
import { useDemo } from "../demo";
import { useView } from "../view";

const PHASE_IDS = ["detection", "prioritization", "pre_implementation", "lab_testing", "prototype", "deployment"];

const JOB_STATE_LABEL: Record<string, string> = {
  queued: "Queued", validating: "Validating the target", dry_run: "Dry-run (no changes)",
  starting: "Starting", running: "Running", verifying: "Verifying",
  succeeded: "Completed", failed: "Failed", cancelling: "Cancelling",
  cancelled: "Cancelled", restore_queued: "Restore queued",
  restoring: "Restoring", restored: "Restored", restore_failed: "Restore failed",
  timed_out: "Timed out",
  timeout_pending_confirmation: "Local timeout · pending confirmation in AWS",
  remote_status_unknown: "Remote status unknown",
  stop_requested: "Stop requested from AWS",
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
  if (job.provider === "mock") return "Simulation (mock)";
  return job.dry_run ? "AWS · dry-run (no real changes)" : "AWS Systems Manager · live execution";
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
  const { active: demo } = useDemo();
  const isTech = role === "technical";
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

  // Recarga sin perder la fase seleccionada: la usa el panel del laboratorio
  // cuando el recurso cambia (reset → otra instancia, parcheo confirmado).
  const refresh = useCallback(() => {
    keepSelection.current = true;
    api.task(id!).then(apply).catch((e) => setError(toError(e)));
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

  if (!d) return <div className="p-8 text-gray-500">Loading…</div>;
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
  // Verificación humana registrada de un punto de control no bloqueante.
  const verifyGate = (gate: HitlGate) =>
    run(() => api.verifyGate(id!, gate.id, { ring: gate.ring, role }));
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
              {vi.exploit_available && <span className="chip bg-red-500/10 text-red-300 border border-red-500/20">exploit available</span>}
              {!done && <SlaTag sla={d.sla} />}
              {done && <span className="chip bg-green-500/15 text-green-400">REMEDIATED</span>}
            </div>
            <h1 className="text-xl font-extrabold mt-2">{task.title}</h1>
            <div className="text-sm text-gray-400 mt-1">
              Asset <span className="text-gray-200">{task.ci_name}</span> · {task.environment} · owner {task.owner}
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
          <Meta k="Component" v={`${vi.component} ${vi.vulnerable_version}`} />
          <Meta k="Exposed" v={task.exposed ? "Yes (internet)" : "No"} />
          <Meta k="SLA" v={task.sla_due.slice(0, 10)} />
          <Meta k="Sources" v={vi.sources.length + " scanners"} />
        </div>
      </div>

      {/* Laboratorio EC2 real: sólo en la tarea de la PoC de parcheo. */}
      {task.logical_lab_id && (
        <LabPanel
          labId={task.logical_lab_id}
          onPatch={approve}
          patchBlockedReason={labPatch
            ? `Patching already confirmed (kernel ${labPatch.kernel ?? "—"}, execution ${labPatch.execution_id}). `
              + "To repeat it the lab must be reset first."
            : canApprove ? null
              : done ? "The task is already remediated."
                : jobRunning ? "There is an active job on the lab."
                  : "The current phase does not allow patching yet."}
          locked={locked}
          onLabChange={refresh}
        />
      )}

      {labPatch && <PatchConfirmed evidence={labPatch} mode={d.execution?.mode ?? "mock"} />}

      {d.sla?.overdue && !done && (
        <div className="rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-2.5 text-sm text-red-300 flex items-center gap-2">
          <span className="text-lg">⚠</span>
          <span>
            <b>SLA breached</b> — due date {d.sla.due.slice(0, 10)}, overdue by <b>{d.sla.days_overdue} day(s)</b>.
            This remediation is past due; prioritise its execution.
          </span>
        </div>
      )}

      {/* Resumen ejecutivo — vista Gestor */}
      {!isTech && (
        <div className="card p-5">
          <div className="text-sm font-semibold text-gray-100 mb-1">Executive summary</div>
          <div className="text-xs text-gray-500 mb-3">
            Management view — risk, deadline, business impact and status. Switch to <b>Technical</b> (side bar) for the operational detail.
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Meta k="Lane / SLA" v={`${d.lane_meta.label} · ${d.lane_meta.sla}`} />
            <Meta k="Risk" v={`${task.risk_score}/100 · ${task.priority}`} />
            <Meta k="Current phase" v={PHASE_META[currentPhaseId].label} />
            <Meta k="Rings deployed" v={`${d.rings_done}/${a.deployment.rings.length}`} />
            <Meta k="CIs impacted" v={String(a.impact.affected_count)} />
            <Meta k="Business services" v={a.impact.business_services.length ? a.impact.business_services.join(", ") : "—"} />
            <Meta k="Due date" v={task.sla_due.slice(0, 10)} />
            <Meta k="Rollback" v={a.deployment.rollback.triggered ? "Executed" : "Armed"} />
          </div>
        </div>
      )}

      {/* Phase stepper */}
      <div className="card p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="text-sm font-semibold">Remediation cycle · 6 phases</div>
          <div className="text-xs text-gray-500">ServiceNow governs · Devin executes · HITL at every transition</div>
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
            Operational lane · <LaneTag lane={d.lane} />
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
          Assigned by triage (CMDB as risk engine) · {d.lane_meta.automation}
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
          <div className="text-sm font-semibold text-gray-100">Dependency and impact map (Impact Graph)</div>
          <div className="text-xs text-gray-500 mt-0.5 leading-relaxed">
            Blast radius of the vulnerability computed from the CMDB (CI→CI relationships). Root: <span className="font-mono text-gray-300">{task.ci_name}</span> ·
            {" "}{a.impact.affected_count} affected CIs · layers: {a.impact.affected_layers.join(", ")}.
          </div>
        </div>
        <div className="flex flex-wrap gap-2 mb-3 text-xs">
          <span className="chip bg-red-500/15 text-red-300 border border-red-500/30">Vulnerable root: {task.ci_name}</span>
          <span className="chip bg-ink-panel text-gray-300 border border-line">{a.impact.affected_count} affected CIs</span>
          {a.impact.business_services.map((s) => (
            <span key={s} className="chip bg-purple-500/15 text-purple-300 border border-purple-500/30">svc: {s}</span>
          ))}
        </div>
        <ImpactGraphView nodes={a.impact.nodes} edges={a.impact.edges} height={340} />
        <div className="mt-2 text-[11px] text-gray-500 leading-relaxed">
          Devin selects the assets to remediate from this graph: the CIs depending on the root node are the ones exposed by
          the vulnerability and they determine the scope of the deployment rings.
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-2.5 text-sm text-red-300 flex items-start justify-between gap-3">
          <span>
            <b>{error.code}</b> — {error.message}
            {error.correlationId && <span className="text-red-400/70 font-mono text-xs"> · {error.correlationId}</span>}
          </span>
          <button className="text-xs text-red-200/70 hover:text-red-100" onClick={() => setError(null)}>close</button>
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
              {phaseLogs.length === 0 && <div className="text-xs text-gray-600">Phase pending. The agent will work once it gets here.</div>}
            </div>
          </div>

          {(activeJob || (d.jobs?.length ?? 0) > 0) && (
            <JobCard job={activeJob ?? d.jobs![0]} execution={d.execution}
              busy={busy} onCancel={cancelJob} />
          )}

          {/* HITL control */}
          <div className="card p-4 space-y-3">
            <div className="text-sm font-semibold">Human approval (HITL)</div>

            {demo && (
              <DemoAdvanceControl detail={d} busy={locked}
                onVerify={verifyGate}
                onPreapprove={async (ring) => { await preapproveRing(ring); }}
                onAdvance={async () => { await approve(); }} />
            )}

            <HitlRail gates={d.journey.gates.filter((g) => g.status !== "upcoming")}
                      onVerify={verifyGate} stacked />

            {done ? (
              <div className="space-y-3">
                <div className="text-xs text-green-400">Task remediated. Vulnerable Item closed with audit evidence.</div>
                <div className="text-xs text-gray-400">Anomaly spotted in production after the rollout? You can run a rollback.</div>
                <button disabled={locked} onClick={rollback}
                  className="btn w-full justify-center btn-ghost border border-amber-500/40 text-amber-300 hover:bg-amber-500/10">
                  {locked ? "Processing…" : "⟲ Roll back the last ring"}
                </button>
              </div>
            ) : (
              <>
                <div className="text-xs text-gray-400 mb-3">
                  Current phase: <span className="font-semibold" style={{ color: PHASE_META[currentPhaseId].color }}>{PHASE_META[currentPhaseId].label}</span>.
                  {currentPhaseId === "deployment"
                    ? ` Approving deploys the next ring (${d.rings_done}/5 completed).`
                    : " Devin proposes; the owner approves to move on."}
                </div>
                {!canApprove && currentPhaseId === "lab_testing" && (
                  <div className="text-xs text-red-400 mb-2">⚠ The MVT failed in the lab. ServiceNow blocks progress (rollback / analysis).</div>
                )}
                {labPatch && currentPhaseId === "deployment" && !done && (
                  <div className="text-xs text-green-400 mb-2">
                    ✓ The instance is already patched and verified: the remaining rings are
                    approved and closed with that evidence, without re-running the Automation.
                  </div>
                )}
                {!nextRingPreapproved && currentPhaseId === "deployment" && nextRing && (
                  <div className="text-xs text-amber-300 mb-2">⚠ Ring {nextRing.ring} needs review and <b>Human-Driven pre-approval</b> of its pre-ring report (above, in Phase 6) before deploying.</div>
                )}
                {jobRunning && (
                  <div className="text-xs text-amber-300 mb-2">⏳ Job {activeJob!.id} in progress ({JOB_STATE_LABEL[activeJob!.state] ?? activeJob!.state}). Mutating actions are blocked until it finishes.</div>
                )}
                {lastJob?.terminal && lastJob.dry_run && (
                  <div className="text-xs text-sky-300 mb-2">
                    ⓘ Job {lastJob.id} finished in <b>dry-run</b>: the target was validated and the
                    Automation planned, but nothing was applied. The ring advances as a rehearsal of
                    the journey and is marked «simulated». The detail is above, in
                    «Patch execution».
                  </div>
                )}
                <button disabled={locked || !canApprove} onClick={approve}
                  className={`btn w-full justify-center ${canApprove && !locked ? "btn-brand" : "btn-ghost opacity-50 cursor-not-allowed"}`}>
                  {locked ? "Processing…" : currentPhaseId === "deployment" ? "Approve and deploy the ring" : "Approve the phase and move on"}
                </button>
                {currentPhaseId === "deployment" && d.rings_done > 0 && (
                  <div className="mt-3 pt-3 border-t border-line space-y-2">
                    <div className="text-[11px] text-gray-500">Rollback management (ring {d.rings_done} deployed)</div>
                    <button disabled={locked} onClick={rollback}
                      className="btn w-full justify-center btn-ghost border border-amber-500/40 text-amber-300 hover:bg-amber-500/10 text-xs">
                      ⟲ Manual rollback of the ring
                    </button>
                    <button disabled={locked} onClick={simulate}
                      className="btn w-full justify-center btn-ghost border border-red-500/40 text-red-300 hover:bg-red-500/10 text-xs">
                      ⚠ Simulate an incident → automatic rollback
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

/** Parcheo ya confirmado sobre el objetivo: estado del recurso, no de un intento. */
function PatchConfirmed({ evidence, mode }: { evidence: LabPatchEvidence; mode: ExecutionMode }) {
  const source = mode === "mock" ? "the simulation (mock)" : "AWS Systems Manager";
  return (
    <div className="rounded-lg border border-green-500/40 bg-green-500/10 px-4 py-3 text-sm text-green-300">
      <div className="font-semibold flex items-center gap-2">
        <span className="text-lg">✓</span> Patching confirmed by {source}
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-2 text-xs text-gray-300">
        <Meta k="Current kernel" v={evidence.kernel ?? "—"} />
        <Meta k="Instance" v={evidence.instance_id ?? "—"} />
        <Meta k="Automation" v={evidence.execution_id} />
        <Meta k="Confirmed" v={evidence.patched_at ? new Date(evidence.patched_at).toLocaleString("en-GB") : "—"} />
      </div>
      <div className="text-[11px] text-green-200/80 mt-2">
        The instance is on the fixed version: the rings still awaiting approval resolve it as their
        target and close with this evidence, without re-running the Automation. To repeat the
        patching the lab must be reset, which recreates the instance from the vulnerable AMI.
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
        <div className="text-sm font-semibold">Patch execution</div>
        <span className={`chip ${jobTone(job.state)}`}>{JOB_STATE_LABEL[job.state] ?? job.state}</span>
      </div>
      <div className="p-4 space-y-2 text-xs">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="chip bg-ink border border-line text-gray-300">{executionModeLabel(job)}</span>
          {job.dry_run && <span className="chip bg-sky-500/15 text-sky-300">dry-run · the patch was NOT applied</span>}
          {job.unconfirmed && (
            <span className="chip bg-orange-500/15 text-orange-300">remote state unconfirmed · the target stays locked</span>
          )}
          <span className="text-gray-500">{job.job_type === "patch" ? "patching" : job.job_type === "rollback" ? "rollback" : "lab reset"}</span>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <Meta k="Job" v={job.id} />
          <Meta k="Provider" v={job.provider} />
          <Meta k="Ring" v={job.ring_number ? String(job.ring_number) : "—"} />
          <Meta k="Reference" v={job.provider_reference ?? "—"} />
        </div>
        {target && (
          <div className="grid grid-cols-2 gap-2">
            <Meta k="Target" v={target.name || target.logical_target_id} />
            <Meta k="Instance ID" v={target.instance_id ?? "unresolved"} />
            <Meta k="Region" v={target.region ?? "—"} />
            <Meta k="SSM" v={target.ssm_managed ? "managed" : "not managed"} />
          </div>
        )}
        {execution && (
          <div className="text-[11px] text-gray-600">
            Mode {execution.mode}{execution.strict_policy ? " · fail-closed policy" : " · relaxed policy (mock/dry-run)"} · refresh every {execution.poll_interval_seconds}s · restore provider {execution.restore_provider}{execution.reconciler?.running ? " · reconciler active in the backend" : ""}
          </div>
        )}
        {job.error_code && (
          <div className="rounded border border-red-500/40 bg-red-500/10 px-3 py-2 text-red-300">
            <b>{job.error_code}</b> — {job.error_message}
            <div className="font-mono text-[10px] text-red-400/70">{job.correlation_id}</div>
            {alreadyFixed(job) && (
              <div className="text-[11px] text-amber-200 mt-1">
                The runbook aborted because the instance <b>already had the fixed kernel</b>: it is a
                rejected attempt on an already patched target, not a failed patch.
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
            Last event: {job.events[job.events.length - 1].message}
          </div>
        )}
        {running && (
          <button disabled={busy} onClick={() => onCancel(job.id)}
            className="btn w-full justify-center btn-ghost border border-line text-gray-300 text-xs">
            Cancel job
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
      <Panel title="Phase 1 · Detection and ingestion" sub="ServiceNow Vulnerability Response — normalisation and correlation with the CMDB">
        <div className="grid grid-cols-2 gap-3 text-sm">
          <Meta k="Vulnerable Item" v={vi.id} />
          <Meta k="Detected" v={vi.detected_at.slice(0, 10)} />
          <Meta k="Identifier" v={vi.cve} />
          <Meta k="Linked CI" v={`${vi.ci_id} (${vi.ci_class})`} />
        </div>
        <div className="mt-3">
          <div className="text-xs text-gray-500 mb-1">Correlated sources (deduplicated)</div>
          <div className="flex flex-wrap gap-2">
            {vi.sources.map((s) => <span key={s} className="chip bg-ink-panel text-gray-300 border border-line">{s}</span>)}
          </div>
        </div>
      </Panel>
    );

  if (phaseId === "prioritization")
    return (
      <Panel title="Phase 2 · Prioritisation" sub="Priority = technical + business + operational risk + SLA (not just CVSS)">
        <div className="space-y-2">
          {[
            ["Technical risk (CVSS)", vi.cvss * 4, 40, `CVSS ${vi.cvss}`],
            ["Exploitability (EPSS/KEV)", vi.epss * 20 + (vi.kev ? 12 : 0), 32, `EPSS ${(vi.epss * 100).toFixed(0)}% ${vi.kev ? "· KEV" : ""}`],
            ["Business context", { critical: 18, high: 12, medium: 6, low: 2 }[task.criticality] || 6, 18, `${task.criticality}`],
            ["Exposure", task.exposed ? 10 : 0, 10, task.exposed ? "Internet-facing" : "Internal"],
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
            ? <span className="text-gray-300">Devin analysed the repository <span className="font-mono text-xs">{task.ci_name}</span>: the component <span className="font-mono text-xs">{vi.component}</span> {task.exposed ? "IS reachable at runtime → keeps high priority." : "is not directly reachable → candidate for a documented exception."}</span>
            : task.track === "C"
            ? <span className="text-gray-300">Devin analysed the image/manifests of <span className="font-mono text-xs">{task.ci_name}</span>: <span className="font-mono text-xs">{vi.component}</span> present in the base image {task.exposed ? "and exposed via ingress → high priority; requires an image rebuild." : "with no direct exposure → rebuild scheduled in a window."}</span>
            : <span className="text-gray-300">Infrastructure asset {task.exposed ? "exposed to the internet" : "internal"}; priority adjusted by maintenance window and service criticality.</span>}
        </div>
      </Panel>
    );

  if (phaseId === "pre_implementation")
    return (
      <>
        <Panel title="Phase 3 · Impact Graph (blast radius)" sub={`Devin enriched the graph from CMDB + repos/SBOM · ${a.impact.affected_count} CIs, layers: ${a.impact.affected_layers.join(", ")}`}>
          <ImpactGraphView nodes={a.impact.nodes} edges={a.impact.edges} height={360} />
          {a.impact.business_services.length > 0 && (
            <div className="mt-2 text-xs text-gray-400">Business services impacted: <span className="text-purple-300">{a.impact.business_services.join(", ")}</span></div>
          )}
        </Panel>
        <Panel title="Minimum Viable Test Plan (MVT)" sub={a.mvt.rationale}>
          <div className="flex items-center gap-3 mb-3">
            <div className="chip bg-brand/15 text-brand">Confidence {a.mvt.confidence}%</div>
            <div className="chip bg-green-500/15 text-green-400">{a.mvt.selected.length} included</div>
            <div className="chip bg-gray-500/15 text-gray-400">{a.mvt.excluded.length} excluded</div>
          </div>
          <TestTable rows={a.mvt.selected} included />
          <details className="mt-3">
            <summary className="text-xs text-gray-500 cursor-pointer">See excluded tests and rationale</summary>
            <div className="mt-2"><TestTable rows={a.mvt.excluded} /></div>
          </details>
        </Panel>
      </>
    );

  if (phaseId === "lab_testing")
    return (
      <Panel title="Phase 4 · Test execution in the lab" sub="Devin generates and runs the MVT via CI/CD and test frameworks">
        <div className="flex items-center gap-3 mb-4">
          <span className="text-sm">Aggregate verdict:</span> <Verdict v={a.lab.verdict} />
          <span className="text-xs text-gray-400 ml-auto">{a.lab.passed}/{a.lab.total} tests OK</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <ResultGroup title="Patch tests" rows={a.lab.patch_tests} />
          <ResultGroup title="Application tests" rows={a.lab.app_tests} />
        </div>
      </Panel>
    );

  if (phaseId === "prototype")
    return (
      <Panel title="Phase 5 · Validation in the prototype environment" sub={`Devin provisions a lab (${a.prototype.approach}) with IaC derived from the Impact Graph`}>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          <Meta k="Approach" v={a.prototype.approach} />
          <Meta k="Provisioning" v={a.prototype.provision_tool} />
          <Meta k="Teardown" v={a.prototype.teardown} />
          <Meta k="Verdict" v={a.prototype.verdict.toUpperCase()} />
        </div>
        <div className="text-xs text-gray-500 mb-1">Lab Blueprint (provisioned components)</div>
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
      <Panel title="Phase 6 · Ring-based rollout (technical detail)" sub={`${a.deployment.strategy} · executor: ${a.deployment.executor} · ${a.deployment.total_assets} assets`}>
        {a.deployment.pr_url && (
          <a href={a.deployment.pr_url} target="_blank" className="chip bg-emerald-500/15 text-emerald-300 mb-3 inline-flex">Remediation PR: {a.deployment.pr_url.split("/").slice(-2).join("/")}</a>
        )}
        <div className="text-xs text-gray-500 mb-2 leading-relaxed">
          Every ring carries a <b>pre-ring report</b> with the asset selection Devin made and its rationale.
          The owner reviews it, edits the selection if needed and <b>verifies and pre-approves (Human-Driven)</b> before it can be deployed.
        </div>
        <div className="space-y-2">
          {a.deployment.rings.map((r) => (
            <RingRow key={r.ring} r={r} busy={busy} isTech={isTech}
              onPreapprove={onPreapprove} onSaveAssets={onSaveAssets} />
          ))}
        </div>
        {a.deployment.exceptions.length > 0 && (
          <div className="mt-4">
            <div className="text-xs text-gray-500 mb-1">Traceable exceptions</div>
            {a.deployment.exceptions.map((e, i) => (
              <div key={i} className="text-xs bg-amber-500/10 border border-amber-500/20 rounded-lg px-3 py-2 text-amber-200">
                <span className="font-mono">{e.asset}</span> — {e.reason}. Compensating control: {e.compensating_control}. Expires {e.expires.slice(0, 10)}.
              </div>
            ))}
          </div>
        )}
      </Panel>
      )}

      <Panel title="Rollback management" sub={`Plan armed from the start and tested in the lab · strategy: ${a.deployment.rollback_plan.strategy}`}>
        {rb.triggered && (
          <div className="mb-4 rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3">
            <div className="flex items-center gap-2 mb-1">
              <span className="chip bg-amber-500/20 text-amber-300">ROLLBACK EXECUTED</span>
              <span className="chip bg-ink-panel text-gray-400">{rb.trigger_type === "auto" ? "automatic" : "manual"}</span>
              <span className="text-xs text-gray-500 ml-auto">ring {rb.ring}</span>
            </div>
            <div className="text-xs text-amber-200">{rb.reason}</div>
            <div className="text-xs text-gray-400 mt-1">Restored version: <span className="font-mono text-gray-200">{rb.restored_version}</span> · {rb.verdict}</div>
          </div>
        )}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          <Meta k="Strategy" v={a.deployment.rollback_plan.strategy} />
          <Meta k="Target RTO" v={`${a.deployment.rollback_plan.rto_minutes} min`} />
          <Meta k="Stable version" v={a.deployment.rollback_plan.target_version} />
          <Meta k="Tested in the lab" v={a.deployment.rollback_plan.tested_in_lab ? "Yes" : "No"} />
        </div>
        <div className="text-xs text-gray-500 mb-1">Automatic trigger: {a.deployment.rollback_plan.auto_trigger}</div>
        <div className="text-xs text-gray-500 mb-1 mt-3">Rollback plan steps</div>
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

      <Panel title="Audit report (audit-ready)" sub={`Devin generates the report automatically · ${a.audit.report_id} · ${a.audit.evidences_count} evidence items${a.audit.dora_relevant ? " · DORA relevant" : ""}`}>
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
              {r.plan.is_replica ? "infra replica" : `real ${r.plan.pct}%`}
              {r.plan.runs_tests ? " · tests ✓" : ""} · {r.plan.window}
            </div>
          )}
        </div>
        {pa.preapproved
          ? <span className="chip bg-brand/15 text-brand" title={pa.note || ""}>pre-approved 👤</span>
          : r.status === "pending" || r.status === "in_progress"
          ? <span className="chip bg-amber-500/15 text-amber-300">needs pre-approval</span>
          : null}
        <span className="text-xs text-gray-400">{r.plan.assets_count} CIs impacted</span>
        {r.result !== "-" && (
          <span className={`chip ${r.status === "rolled_back" ? "bg-amber-500/10 text-amber-300" : "bg-green-500/10 text-green-400"}`}>{r.result}</span>
        )}
        <span className="text-gray-500 text-xs w-4">{open ? "▾" : "▸"}</span>
      </button>

      {open && (
        <div className="border-t border-line px-3 py-3 space-y-3">
          {/* Informe pre-anillo */}
          <div className="rounded-lg bg-ink-panel border border-line p-3">
            <div className="text-[11px] font-bold text-brand tracking-wider mb-1">PRE-RING REPORT · Devin's selection</div>
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
                CIs impacted by this ring and their dependencies (Impact Graph subgraph)
              </div>
              <ImpactGraphView nodes={r.plan.graph.nodes} edges={r.plan.graph.edges} height={200} />
            </div>
          )}

          {/* CIs impactados del anillo (revisables / editables) */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <div className="text-[11px] text-gray-500">
                CIs impacted in the ring ({r.plan.selected_count}/{r.plan.assets_count})
              </div>
              {isTech && (r.status === "pending" || r.status === "in_progress") && (
                <button onClick={() => setEditing((v) => !v)} className="btn btn-ghost text-[11px]">
                  {editing ? "Cancel editing" : "✎ Edit the selection"}
                </button>
              )}
            </div>
            {r.plan.assets.length === 0 && (
              <div className="text-[11px] text-gray-600">No impacted CIs in this ring's band.</div>
            )}
            <div className="space-y-1">
              {r.plan.assets.map((as) => {
                const isExcl = excluded.includes(as.id);
                return (
                  <div key={as.id} className={`flex items-start gap-2 text-[11px] rounded-lg px-2 py-1.5 border ${isExcl ? "border-red-500/30 bg-red-500/5 opacity-70" : "border-line bg-ink"}`}>
                    {editing && (
                      <input type="checkbox" checked={!isExcl} onChange={() => toggle(as.id)} className="mt-0.5" title="Include in the ring" />
                    )}
                    <span className={`chip shrink-0 ${isExcl ? "bg-red-500/15 text-red-300" : "bg-sky-500/15 text-sky-300"}`}>{as.ci_class}</span>
                    <div className="flex-1 min-w-0">
                      <div className="font-mono text-gray-300 truncate">
                        {as.name} {as.is_root && <span className="chip bg-red-500/15 text-red-300">root</span>}
                        <span className="text-gray-600"> · {as.criticality} · {as.environment}</span>
                      </div>
                      <div className="text-gray-500 truncate">{as.reason}</div>
                    </div>
                    {isExcl && <span className="chip bg-red-500/15 text-red-300 shrink-0">excluded</span>}
                  </div>
                );
              })}
            </div>
            {editing && (
              <button disabled={busy} onClick={() => { onSaveAssets(r.ring, excluded); setEditing(false); }}
                className="btn btn-ghost border border-brand/40 text-brand text-[11px] mt-2">
                Save the edited selection ({excluded.length} excluded)
              </button>
            )}
          </div>

          {/* Dependencias de los CIs impactados del anillo */}
          {r.plan.dependencies.length > 0 && (
            <div>
              <div className="text-[11px] text-gray-500 mb-1">
                Affected dependencies ({r.plan.dependencies.length}) — CIs linked to the impacted ones
              </div>
              <div className="space-y-1">
                {r.plan.dependencies.map((dep) => (
                  <div key={dep.id} className="flex items-start gap-2 text-[11px] rounded-lg px-2 py-1.5 border border-line bg-ink">
                    <span className="chip shrink-0 bg-purple-500/15 text-purple-300">{dep.ci_class}</span>
                    <div className="flex-1 min-w-0">
                      <div className="font-mono text-gray-300 truncate">{dep.name} <span className="text-gray-600">· {dep.criticality}</span></div>
                      <div className="text-gray-500 truncate">{dep.relation} · linked to {dep.of}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Revisión / pre-aprobación Human-Driven */}
          {pa.preapproved ? (
            <div className="rounded-lg border border-brand/30 bg-brand/5 px-3 py-2 text-[11px] text-gray-300">
              <span className="text-brand font-semibold">✓ Report verified and pre-approved (Human-Driven)</span>
              {pa.approver && <> · by <span className="font-mono">{pa.approver}</span></>}
              {pa.ts && <> · {pa.ts.slice(0, 16).replace("T", " ")}</>}
              {pa.note && <div className="text-gray-500 mt-0.5">{pa.note}</div>}
            </div>
          ) : (r.status === "pending" || r.status === "in_progress") ? (
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 px-3 py-2 flex items-center gap-3">
              <div className="text-[11px] text-amber-200 flex-1">
                Human-Driven audit required: review the report and the assets, edit them if needed and verify before deploying.
              </div>
              <button disabled={busy} onClick={() => onPreapprove(r.ring)}
                className="btn btn-brand text-[11px]">✓ Verify and pre-approve</button>
            </div>
          ) : null}

          {/* Acciones ejecutadas con el por qué de cada comando */}
          {isTech && hasActions && r.actions && (
            <div className="border-t border-line pt-2 space-y-1.5 font-mono text-[11px]">
              <div className="text-gray-500 mb-1">Actions executed · {r.actions.from_version} → {r.actions.to_version}</div>
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
  standard: { label: "Standard change", cls: "bg-green-500/15 text-green-300 border-green-500/30", dot: "#22c55e" },
  normal: { label: "Normal change", cls: "bg-sky-500/15 text-sky-300 border-sky-500/30", dot: "#38bdf8" },
  emergency: { label: "Emergency change", cls: "bg-red-500/15 text-red-300 border-red-500/30", dot: "#ef4444" },
};

function ItsmChangePanel({ itsm }: { itsm: ItsmChange }) {
  const st = CHANGE_STYLE[itsm.type] || CHANGE_STYLE.normal;
  return (
    <Panel title="Change Management (ITSM · ServiceNow Change Management)"
      sub="Every patch is backed by a change recorded in the customer's ITSM tool: traceability, authorisation and evidence.">
      <div className="flex items-center gap-2 flex-wrap mb-3">
        <span className={`chip border ${st.cls}`}>{itsm.type_label}</span>
        <span className="chip bg-ink text-gray-300 border border-line font-mono">{itsm.number}</span>
        <span className="chip bg-ink text-gray-400 border border-line">State: {itsm.state}</span>
        <span className="chip bg-ink text-gray-400 border border-line">Risk: {itsm.risk}</span>
        <span className="chip bg-ink text-gray-400 border border-line">Impact: {itsm.impact_level}</span>
        {itsm.four_eyes && <span className="chip bg-purple-500/15 text-purple-300 border border-purple-500/30" title="Implementation reviewed by a second engineer">four-eyes principle 👀</span>}
        {itsm.gxp && <span className="chip bg-amber-500/15 text-amber-300 border border-amber-500/30">GxP relevant</span>}
      </div>

      {/* Change Transaction Phases by Change Type */}
      <div className="text-[11px] text-gray-500 mb-1">Change transaction phases · {itsm.type_label}</div>
      <div className="flex items-stretch gap-1 flex-wrap mb-3">
        {itsm.phases.map((p, i) => (
          <div key={p.key} className="flex items-center">
            <div className={`rounded-md border px-2.5 py-1.5 min-w-[92px] ${p.included ? "border-line bg-ink" : "border-dashed border-line/50 bg-transparent opacity-40"}`}
              style={p.included ? { borderLeft: `3px solid ${st.dot}` } : {}}>
              <div className="text-[10px] font-semibold text-gray-200 leading-tight">{p.label}</div>
              {p.approval
                ? <div className={`text-[9px] mt-0.5 ${p.included ? "text-amber-300" : "text-gray-600"}`}>● approval</div>
                : <div className="text-[9px] mt-0.5 text-gray-600">{p.included ? "phase" : "not applicable"}</div>}
            </div>
            {i < itsm.phases.length - 1 && <span className="text-gray-700 px-0.5">›</span>}
          </div>
        ))}
      </div>
      <div className="text-[11px] text-gray-500 leading-relaxed mb-3">{itsm.detail}</div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-3">
        <Meta k="Approval" v={itsm.approval} />
        <Meta k="Environment" v={itsm.environment} />
        <Meta k="Patch" v={itsm.patch} />
        <Meta k="Affected CIs" v={String(itsm.affected_cis)} />
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
            {c.auto && <span className="chip bg-green-500/10 text-green-400 shrink-0">automatable</span>}
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
    <Panel title="Implementation control panel"
      sub="Promotion across environments matching the customer's reality: Lab → Canary → Pre-production → Controlled production → Full production. In Lab and Pre-production an infrastructure replica is stood up and all tests are run.">
      <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
        {dep.rings.map((r, i) => {
          const stCol =
            r.status === "completed" ? "#22c55e"
            : r.status === "rolled_back" ? "#f59e0b"
            : r.status === "in_progress" ? "#38bdf8" : "#3f4756";
          const stLabel =
            r.status === "completed" ? (r.simulated ? "Simulated" : "Deployed")
            : r.status === "rolled_back" ? "Rolled back"
            : r.status === "in_progress" ? "In progress" : "Pending";
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
                    {r.plan.is_replica ? "replica" : `real ${r.plan.pct}%`}
                  </span>
                </div>
                <div>{r.plan.runs_tests
                  ? <span className="text-green-400">✓ tests in the environment</span>
                  : <span className="text-gray-500">validation by telemetry</span>}</div>
                {r.simulated && (
                  <div className="text-amber-300" title="Dry-run rehearsal: no patch was applied">
                    ⚑ dry-run · no real changes
                  </div>
                )}
                {r.status === "completed" && r.health && (
                  <div className="text-gray-500">health: {r.health.availability_pct}% avail · err {r.health.error_rate_pct}%</div>
                )}
                <div>{r.plan.approval.preapproved
                  ? <span className="text-brand">👤 pre-approved</span>
                  : (r.status === "pending" || r.status === "in_progress")
                  ? <span className="text-amber-300">needs approval</span>
                  : <span className="text-gray-600">—</span>}</div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Progreso + acción de aprobación de alto nivel (sin scripts) */}
      <div className="mt-3 flex items-center gap-3 flex-wrap">
        <div className="text-xs text-gray-400">Progress: <b className="text-gray-200">{ringsDone}/{dep.rings.length}</b> environments deployed</div>
        <div className="flex-1 h-2 rounded bg-ink min-w-[120px]">
          <div className="h-2 rounded bg-brand" style={{ width: `${(ringsDone / dep.rings.length) * 100}%` }} />
        </div>
        {dep.rollback.triggered
          ? <span className="chip bg-amber-500/15 text-amber-300">rollback executed (ring {dep.rollback.ring})</span>
          : <span className="chip bg-green-500/10 text-green-400">rollback armed</span>}
      </div>
      {next && !next.plan.approval.preapproved && (
        <div className="mt-3 rounded-lg border border-amber-500/30 bg-amber-500/5 px-3 py-2 flex items-center gap-3 flex-wrap">
          <div className="text-[11px] text-amber-200 flex-1">
            Next environment: <b>{next.plan.environment || next.label}</b>. Review the report and verify the asset selection before promoting (Human-Driven audit).
          </div>
          <button disabled={busy} onClick={() => onPreapprove(next.ring)} className="btn btn-brand text-[11px]">
            ✓ Verify and pre-approve {next.plan.environment}
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
