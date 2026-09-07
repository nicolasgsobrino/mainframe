import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, releaseIdempotencyKey } from "../api";
import type {
  HitlGate, LabSnapshot, LabValidation, PatchJob, TaskDetail,
} from "../types";
import { LogConsole, NextActionBar, type DemoStep } from "../components/flow";
import { Check, Field } from "../components/lab/fields";
import { JOB_STATE_META, MODE_META, STATE_META, toError, ts, tri } from "../components/lab/meta";
import { useReportExecution } from "../demo";
import { useView } from "../view";

/**
 * Live patching: la misma gramática visual del recorrido guiado sobre la
 * ejecución que sí toca AWS. Un único entorno, sin gestión del cambio ITSM y
 * sin escenario sintético — todo lo que se ve viene del laboratorio EC2 que el
 * backend resuelve por tags y del job durable de Systems Manager.
 */

/** Anillo único de la ejecución real: la prueba tiene una sola máquina. */
const RING = 1;

type StageId = "target" | "preflight" | "execution" | "evidence";

const STAGES: { id: StageId; label: string; caption: string }[] = [
  { id: "target", label: "Target", caption: "Instance resolved by tags" },
  { id: "preflight", label: "Preflight", caption: "Read-only checks on AWS" },
  { id: "execution", label: "Execution", caption: "SSM Automation runbook" },
  { id: "evidence", label: "Evidence", caption: "Kernel before and after" },
];

const STAGE_PITCH: Record<StageId, string> = {
  target: "No Instance ID is typed anywhere: the platform resolves the machine from its logical "
    + "identifier and the mandatory tags, so a recreated instance is picked up on its own.",
  preflight: "Nothing is changed yet. The checks confirm the instance is manageable through SSM "
    + "and that the advisory really applies to the kernel currently running.",
  execution: "One authorisation, one execution: the Automation runbook patches the instance and "
    + "the job survives a reload because its state lives in the backend, not in this screen.",
  evidence: "The result is not claimed, it is evidenced: kernel before and after, the Automation "
    + "execution that produced it and the state transition observed on AWS.",
};

type LiveOp = "reconcile" | "validate" | "preapprove" | "patch" | "verify" | "none";

interface LiveStep {
  step: DemoStep;
  action: { verb: string; object: string };
  stage: StageId;
  op: LiveOp;
}

const BASELINE_KEY = "msr_live_baseline";

/** Único paso siguiente de la ejecución real, con la escena donde ocurre. */
function nextLiveStep(
  snapshot: LabSnapshot, detail: TaskDetail | null, validation: LabValidation | null,
): LiveStep {
  const patched = snapshot.vulnerable_state === "patched";
  const instanceId = snapshot.instance?.instance_id ?? "the lab instance";
  const ringPlan = detail?.artifacts.deployment.rings.find((r) => r.ring === RING);
  const preapproved = !!ringPlan?.plan.approval.preapproved;
  const resultGate = detail?.journey.gates.find(
    (g) => g.id === "ring_result" && g.ring === RING && g.status === "pending") ?? null;

  if (snapshot.resolution_error) {
    return {
      stage: "target", op: "reconcile",
      action: { verb: "Resolve", object: "the lab instance" },
      step: {
        kind: "deploy", ring: RING, gate: null, label: "Resolve the lab instance",
        hint: `${snapshot.resolution_error.message} Reconciliation resolves the instance by tags `
          + "and leaves the lab ready.",
      },
    };
  }
  if (!patched && !validation) {
    return {
      stage: "preflight", op: "validate",
      action: { verb: "Run", object: "the preflight checks" },
      step: {
        kind: "deploy", ring: RING, gate: null, label: "Run the preflight checks",
        hint: "Read-only checks on AWS: instance resolved, SSM agent online and advisory "
          + "applicable to the running kernel. Nothing is modified.",
      },
    };
  }
  if (!patched && !preapproved) {
    return {
      stage: "execution", op: "preapprove",
      action: { verb: "Authorise", object: `the patch on ${instanceId}` },
      step: {
        kind: "preapprove", ring: RING, gate: null, label: "Authorise the patch",
        hint: "Blocking gate: nothing runs on AWS until a person authorises this environment.",
      },
    };
  }
  if (!patched) {
    return {
      stage: "execution", op: "patch",
      action: { verb: "Apply", object: "the patch" },
      step: {
        kind: "deploy", ring: RING, gate: null, label: "Apply the patch",
        hint: "Runs the Systems Manager Automation runbook on the resolved instance and waits "
          + "for AWS to confirm the result.",
      },
    };
  }
  if (resultGate) {
    return {
      stage: "evidence", op: "verify",
      action: { verb: "Accept", object: "the patch evidence" },
      step: {
        kind: "verify", ring: RING, gate: resultGate, label: "Accept the patch evidence",
        hint: `${resultGate.question} · accept the evidence, or use the reset to leave the lab `
          + "vulnerable again for another run.",
      },
    };
  }
  return {
    stage: "evidence", op: "none",
    action: { verb: "Live patch evidenced", object: "" },
    step: {
      kind: "done", ring: null, gate: null, label: "Live patch evidenced",
      hint: "The instance is patched and the evidence is accepted.",
    },
  };
}

function StageRibbon({ current, actionStage, accent, onSelect }: {
  current: StageId; actionStage: StageId; accent: string; onSelect: (id: StageId) => void;
}) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
      {STAGES.map((s, i) => {
        const active = s.id === current;
        const isAction = s.id === actionStage;
        return (
          <button
            key={s.id}
            type="button"
            onClick={() => onSelect(s.id)}
            aria-pressed={active}
            className={`relative rounded-lg border-2 p-2 text-left transition-colors ${
              active ? "bg-ink-panel" : "bg-ink hover:bg-ink-panel"}`}
            style={{
              borderColor: isAction ? accent : active ? "#38bdf8" : "#2b313d",
              background: isAction ? accent + "14" : undefined,
              boxShadow: isAction ? `0 0 0 3px ${accent}26, 0 0 18px ${accent}40` : undefined,
            }}
          >
            {isAction && (
              <span className="absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full animate-pulse"
                    style={{ background: accent }} aria-hidden />
            )}
            <div className="text-[9px] font-mono text-gray-600">STAGE {i + 1}/4</div>
            <div className={`text-[11px] leading-snug font-semibold ${
              active ? "text-gray-100" : "text-gray-400"}`}>
              {s.label}
            </div>
            <div className="text-[10px] text-gray-600 leading-tight">{s.caption}</div>
          </button>
        );
      })}
    </div>
  );
}

/** Pasos que el runbook ya ha ejecutado, con su salida real. */
function JobSteps({ job }: { job: PatchJob }) {
  if (job.steps.length === 0) {
    return <div className="text-[11px] text-gray-600">The runbook has not published any step yet.</div>;
  }
  return (
    <div className="font-mono text-[11px] leading-relaxed space-y-1">
      {job.steps.map((s) => (
        <div key={s.seq}>
          <div className="flex gap-2">
            <span className="text-gray-700">›</span>
            <span className="text-sky-300">[{s.actor}]</span>
            <span className="text-gray-400">{s.why ?? s.tool}</span>
          </div>
          <div className="pl-4 text-gray-500">$ {s.command}</div>
          {s.output && (
            <div className={`pl-4 ${
              s.status === "ok" || s.status === "success" ? "text-emerald-300/80" : "text-amber-300/80"}`}>
              {s.output}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

export default function LiveStage() {
  const { role } = useView();
  const [labId, setLabId] = useState<string | null>(null);
  const [snapshot, setSnapshot] = useState<LabSnapshot | null>(null);
  const [detail, setDetail] = useState<TaskDetail | null>(null);
  const [jobs, setJobs] = useState<PatchJob[]>([]);
  const [validation, setValidation] = useState<LabValidation | null>(null);
  const [pinned, setPinned] = useState<StageId | null>(null);
  const [running, setRunning] = useState(false);
  const [confirmRollback, setConfirmRollback] = useState(false);
  const [error, setError] = useState<{ code: string; message: string } | null>(null);

  useReportExecution(detail?.execution ?? null);

  // El laboratorio se descubre por la tarea que lo referencia: la pantalla no
  // conoce identificadores de instancia ni los fija en ningún sitio.
  useEffect(() => {
    api.tasks()
      .then((all) => {
        const lab = all.find((t) => t.lab_target && t.logical_lab_id);
        if (!lab?.logical_lab_id) {
          setError({ code: "LAB_NOT_REGISTERED", message: "No lab target is registered in this environment." });
          return;
        }
        setLabId(lab.logical_lab_id);
      })
      .catch((e) => setError(toError(e)));
  }, []);

  const load = useCallback(async (id: string) => {
    const next = await api.lab(id);
    const [task, history] = await Promise.all([api.task(next.task_id), api.labJobs(id)]);
    setSnapshot(next);
    setDetail(task);
    setJobs(history);
  }, []);

  useEffect(() => {
    if (!labId) return;
    load(labId).catch((e) => setError(toError(e)));
  }, [labId, load]);

  // El job vive en el backend: el sondeo sólo refresca lo que AWS ya confirmó.
  const activeJob = snapshot?.active_job ?? null;
  const pollMs = (detail?.execution?.poll_interval_seconds ?? 2) * 1000;
  useEffect(() => {
    if (!labId || !activeJob || activeJob.terminal) return;
    const timer = window.setInterval(() => {
      load(labId).catch((e) => setError(toError(e)));
    }, pollMs);
    return () => window.clearInterval(timer);
  }, [labId, activeJob, pollMs, load]);

  // Kernel observado mientras la instancia seguía vulnerable: es el «antes» de
  // la evidencia y tiene que sobrevivir a una recarga durante la grabación.
  const [baseline, setBaseline] = useState<string | null>(null);
  const instanceId = snapshot?.instance?.instance_id ?? null;
  const baselineKey = labId && instanceId ? `${BASELINE_KEY}:${labId}:${instanceId}` : null;
  useEffect(() => {
    if (!baselineKey) return;
    const stored = localStorage.getItem(baselineKey);
    if (snapshot?.vulnerable_state === "vulnerable" && snapshot.current_kernel) {
      localStorage.setItem(baselineKey, snapshot.current_kernel);
      setBaseline(snapshot.current_kernel);
      return;
    }
    setBaseline(stored);
  }, [baselineKey, snapshot?.vulnerable_state, snapshot?.current_kernel]);

  const lastPatchJob = useMemo(
    () => jobs.find((job) => job.job_type === "patch") ?? null, [jobs]);

  // Una instancia distinta invalida la validación anterior: describe un
  // recurso que ya no existe.
  const lastInstance = useRef<string | null>(null);
  useEffect(() => {
    if (!instanceId) return;
    if (lastInstance.current !== null && lastInstance.current !== instanceId) setValidation(null);
    lastInstance.current = instanceId;
  }, [instanceId]);

  if (!snapshot || !labId) {
    return (
      <div className="p-6 text-sm text-gray-400">
        {error ? `${error.code}: ${error.message}` : "Resolving the lab target…"}
      </div>
    );
  }

  const instance = snapshot.instance;
  const mode = MODE_META[snapshot.execution_mode] ?? MODE_META.mock;
  const state = STATE_META[snapshot.vulnerable_state] ?? STATE_META.unknown;
  const realMode = snapshot.execution_mode === "aws-real";
  const jobRunning = !!activeJob && !activeJob.terminal;
  const live = nextLiveStep(snapshot, detail, validation);
  const busy = running || jobRunning;
  const stage = pinned ?? live.stage;
  const accent = live.step.kind === "deploy" ? "#8ef04a" : "#f59e0b";
  const patchJob = activeJob?.job_type === "patch" ? activeJob : lastPatchJob;

  const run = async (action: () => Promise<unknown>) => {
    if (busy) return;
    setRunning(true);
    setError(null);
    try {
      await action();
      await load(labId);
    } catch (e) {
      setError(toError(e));
    } finally {
      setRunning(false);
    }
  };

  const taskId = detail?.task.id ?? snapshot.task_id;
  const act = () => {
    setPinned(null);
    switch (live.op) {
      case "reconcile":
        return void run(() => api.reconcileLab(labId, realMode));
      case "validate":
        return void run(async () => setValidation(await api.validateLab(labId)));
      case "preapprove":
        return void run(() => api.preapproveRing(taskId, RING));
      case "patch":
        return void run(() => api.approve(taskId, RING));
      case "verify":
        return void run(() => api.verifyGate(taskId, "ring_result", { ring: RING, role }));
      default:
        return undefined;
    }
  };

  // Rollback del anillo desplegado. AWS no ofrece una vuelta atrás del kernel
  // en caliente para este advisory, así que la reversión real es recrear la
  // instancia desde la AMI previa al parcheo: el anillo se reabre, la evidencia
  // se invalida y el laboratorio vuelve al estado anterior a la ejecución.
  const rollback = () => void run(async () => {
    await api.resetLab(labId, realMode);
    releaseIdempotencyKey(`lab-reset:${labId}`);
    setValidation(null);
    setConfirmRollback(false);
  });

  const rollbackTarget = snapshot.vulnerable_state === "patched" || !!lastPatchJob;
  const rollbackPanel = (
    <div className="rounded-lg border border-orange-500/30 bg-orange-500/[0.06] px-3 py-2 space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          disabled={busy || !rollbackTarget}
          onClick={() => setConfirmRollback(true)}
          title={rollbackTarget
            ? `Revert ring ${RING} to the state before the patch`
            : "Nothing to revert: this ring has not been deployed yet"}
          className={`rounded-lg border px-3 py-1.5 text-xs font-bold transition ${
            busy || !rollbackTarget
              ? "border-orange-500/40 bg-orange-500/10 text-orange-300/50 cursor-not-allowed"
              : "border-orange-500/60 bg-orange-500/15 text-orange-200 hover:bg-orange-500/25"}`}
        >
          ⟲ Rollback ring {RING}
        </button>
        <span className="text-[11px] text-orange-200/80">
          {rollbackTarget
            ? "Reverts the environment to the state before the patch and reopens the ring."
            : "Available once the ring has been deployed."}
        </span>
      </div>
      <div className="text-[11px] text-gray-400">
        There is no in-place kernel downgrade for this advisory, so the rollback recreates the
        target: the current instance is terminated and the Auto Scaling Group launches a new one
        from the Launch Template with the pre-patch AMI. The evidence of this run is invalidated,
        the ring returns to its pre-deployment state and the replacement instance is discovered
        by tags.
      </div>
      {confirmRollback && (
        <div className="flex gap-2">
          <button className="btn btn-brand disabled:opacity-40" onClick={rollback} disabled={busy}>
            Confirm the rollback of ring {RING}
          </button>
          <button className="btn btn-ghost disabled:opacity-40"
                  onClick={() => setConfirmRollback(false)} disabled={busy}>
            Cancel
          </button>
        </div>
      )}
    </div>
  );

  const gates: HitlGate[] = detail?.journey.gates.filter(
    (g) => g.ring === RING || g.ring === null) ?? [];
  const decided = gates.filter((g) => g.status === "done").length;

  return (
    <div className="p-6 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-[10px] tracking-[0.2em] text-sky-300">LIVE PATCHING</div>
          <h1 className="text-xl font-bold text-gray-100 leading-tight">
            {snapshot.advisory_id} · Amazon Linux 2023 kernel advisory
          </h1>
          <div className="flex flex-wrap items-center gap-2 mt-1.5">
            <span className={`chip ${mode.cls}`}>{mode.label}</span>
            <span className={`chip ${state.cls}`}>{state.label}</span>
            <span className="text-xs text-gray-500">
              {instance?.account_id ?? snapshot.lab?.account_id ?? "—"} ·{" "}
              {instance?.region ?? snapshot.lab?.region ?? "—"} · single environment
            </span>
          </div>
        </div>
        <div className="text-right space-y-1">
          <div className="text-[11px] text-gray-500">
            {decided}/{gates.length} human decisions recorded
          </div>
          {detail && (
            <Link to={`/tasks/${snapshot.task_id}`} className="text-[11px] text-gray-500 hover:text-gray-300">
              Open the full Remediation Task →
            </Link>
          )}
        </div>
      </div>

      <div className={`rounded-lg border px-3 py-2 text-xs ${
        realMode
          ? "border-red-500/40 bg-red-500/10 text-red-200"
          : snapshot.execution_mode === "aws-dry-run"
            ? "border-sky-500/40 bg-sky-500/10 text-sky-200"
            : "border-line bg-ink-panel text-gray-400"}`}>
        {realMode
          ? "AWS · LIVE EXECUTION — every action on this screen changes real resources in the account above."
          : snapshot.execution_mode === "aws-dry-run"
            ? "AWS · DRY-RUN — AWS is queried for real, but no resource is modified."
            : "Simulation (mock) — no AWS call is made. Point the backend at AWS to run this for real."}
      </div>

      <StageRibbon current={stage} actionStage={live.stage} accent={accent}
                   onSelect={(id) => setPinned(id)} />

      <NextActionBar
        step={live.step}
        running={busy}
        action={live.action}
        kicker={live.step.kind === "deploy" && !jobRunning
          ? "PLATFORM'S TURN · REAL EXECUTION ON AWS"
          : undefined}
        onAct={act}
        onGoToScene={stage !== live.stage ? () => setPinned(null) : undefined}
      />

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_360px] gap-4 items-start">
        <div className="card p-5 space-y-4" key={stage}>
          <div className="animate-fade-in">
            <h2 className="text-lg font-bold text-gray-100">
              {STAGES.find((s) => s.id === stage)?.label}
            </h2>
            <div className="text-xs text-gray-400 leading-relaxed mt-1">{STAGE_PITCH[stage]}</div>
          </div>

          {stage === "target" && (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3 animate-fade-in">
              <Field label="Logical target" value={labId} mono />
              <Field label="Instance ID" value={instance?.instance_id ?? "unresolved"} mono />
              <Field label="EC2 state" value={instance?.state ?? "—"} />
              <Field label="AMI" value={instance?.image_id ?? snapshot.lab?.vulnerable_ami_id ?? "—"} mono />
              <Field label="Auto Scaling Group" value={snapshot.lab?.autoscaling_group_name ?? "—"} mono />
              <Field label="Previous instance" value={snapshot.previous_instance_id ?? "—"} mono />
              <Field label="Advisory" value={snapshot.advisory_id} mono />
              <Field label="Current kernel" value={snapshot.current_kernel ?? "no evidence"} mono />
              <Field label="Fixed kernel" value={snapshot.expected_fixed_kernel} mono />
            </div>
          )}

          {stage === "preflight" && (
            <div className="space-y-3 animate-fade-in">
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                <Field label="SSM agent"
                  value={snapshot.ssm_state
                    ?? (instance ? (instance.ssm_managed ? `Online (${instance.ping_status ?? "—"})` : "Not managed") : "—")} />
                <Field label="Health" value={snapshot.health_state ?? "no evidence"} />
                <Field label="Advisory applicable" value={tri(snapshot.advisory_applicable)} />
                <Field label="Releasever" value={snapshot.releasever} mono />
                <Field label="Evidence" value={snapshot.evidence_source ?? "not observed"} />
                <Field label="Last reconciliation" value={ts(snapshot.last_reconciled_at)} />
              </div>
              {validation ? (
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] uppercase tracking-wide text-gray-500 font-semibold">
                      Read-only validation
                    </span>
                    <span className={`chip ${validation.allowed
                      ? "bg-green-500/15 text-green-400" : "bg-amber-500/15 text-amber-300"}`}>
                      {validation.allowed ? "Ready to patch" : "Blocking checks failed"}
                    </span>
                  </div>
                  {validation.checks.map((c) => <Check key={c.check} c={c} />)}
                  {validation.inconclusive.length > 0 && (
                    <div className="text-[11px] text-gray-400">
                      Inconclusive (non-blocking; the runbook precheck repeats them):{" "}
                      {validation.inconclusive.join(", ")}.
                    </div>
                  )}
                  <div className="text-[11px] text-gray-500">{validation.note}</div>
                </div>
              ) : (
                <div className="text-[11px] text-gray-500">
                  The checks have not been run yet. They only read from AWS: no command reaches the instance.
                </div>
              )}
            </div>
          )}

          {stage === "execution" && (
            <div className="space-y-3 animate-fade-in">
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                <Field label="Job" value={patchJob?.id ?? "not started"} mono />
                <Field label="Job state"
                  value={patchJob ? (JOB_STATE_META[patchJob.state]?.label ?? patchJob.state) : "—"} />
                <Field label="Automation execution"
                  value={patchJob?.provider_reference ?? snapshot.last_patch_execution_id ?? "—"} mono />
                <Field label="Provider" value={patchJob?.provider ?? snapshot.patch_provider} />
                <Field label="Dry-run" value={snapshot.dry_run ? "yes" : "no"} />
                <Field label="Started" value={ts(patchJob?.started_at)} />
              </div>
              {jobRunning && (
                <div className="rounded-lg border border-sky-500/40 bg-sky-500/10 px-3 py-2 text-xs text-sky-200 flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-sky-300 animate-pulse" />
                  {JOB_STATE_META[activeJob.state]?.label ?? activeJob.state} · polling AWS every{" "}
                  {pollMs / 1000}s. The job keeps running even if this screen is closed.
                </div>
              )}
              {patchJob?.error_message && (
                <div className="text-xs text-red-300">
                  {patchJob.error_code}: {patchJob.error_message}
                </div>
              )}
              <div className="rounded-lg border border-line bg-ink p-3">
                <div className="text-[10px] font-semibold tracking-wider text-gray-500 mb-2">
                  RUNBOOK OUTPUT
                </div>
                {patchJob
                  ? <JobSteps job={patchJob} />
                  : <div className="text-[11px] text-gray-600">
                      Nothing has run yet on this instance.
                    </div>}
              </div>
              {rollbackPanel}
            </div>
          )}

          {stage === "evidence" && (
            <div className="space-y-3 animate-fade-in">
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span className={`chip ${baseline ? STATE_META.vulnerable.cls : STATE_META.unknown.cls}`}>
                  {baseline ? "VULNERABLE" : "State before not observed"}
                </span>
                <span className="text-gray-600">→</span>
                <span className={`chip ${state.cls}`}>{state.label}</span>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                <Field label="Kernel before"
                  value={baseline ?? snapshot.lab?.expected_vulnerable_version ?? "not observed"} mono />
                <Field label="Kernel after" value={snapshot.current_kernel ?? "no evidence"} mono />
                <Field label="Expected fixed kernel" value={snapshot.expected_fixed_kernel} mono />
                <Field label="Advisory" value={snapshot.advisory_id} mono />
                <Field label="Advisory applicable" value={tri(snapshot.advisory_applicable)} />
                <Field label="Automation execution"
                  value={snapshot.last_patch_execution_id ?? "—"} mono />
                <Field label="Evidence" value={snapshot.evidence_source ?? "not observed"} />
                <Field label="Health" value={snapshot.health_state ?? "no evidence"} />
                <Field label="Instance ID" value={instance?.instance_id ?? "unresolved"} mono />
              </div>

              {rollbackPanel}
            </div>
          )}

          {snapshot.resolution_error && (
            <div className="text-xs text-red-300 bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2">
              {snapshot.resolution_error.code}: {snapshot.resolution_error.message}
            </div>
          )}
          {snapshot.last_reconciliation_error && (
            <div className="text-xs text-red-300 bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2">
              {snapshot.last_reconciliation_error}
            </div>
          )}
          {error && <div className="text-xs text-red-300">{error.code}: {error.message}</div>}
        </div>

        <div className="space-y-3 xl:sticky xl:top-6">
          <div className="card p-3 space-y-2">
            <div className="text-[10px] font-semibold tracking-wider text-gray-500">
              HUMAN CONTROL POINTS
            </div>
            {gates.length === 0 && <div className="text-[11px] text-gray-600">No gate published yet.</div>}
            {gates.map((g) => (
              <div key={`${g.id}:${g.ring ?? "-"}`} className="flex items-start gap-2 text-[11px]">
                <span className={g.status === "done" ? "text-emerald-400"
                  : g.status === "pending" ? "text-amber-300" : "text-gray-600"}>
                  {g.status === "done" ? "✓" : g.status === "pending" ? "◑" : "○"}
                </span>
                <div>
                  <div className={g.status === "pending" ? "text-amber-200" : "text-gray-300"}>{g.label}</div>
                  <div className="text-gray-600">
                    {g.status === "done"
                      ? `${g.verdict ?? "Verified"}${g.actor ? ` · ${g.actor}` : ""}`
                      : g.status === "pending" ? "awaiting a human decision" : "upcoming"}
                  </div>
                </div>
              </div>
            ))}
          </div>
          <div className="card p-3">
            <div className="text-[10px] font-semibold tracking-wider text-gray-500 mb-2">
              TECHNICAL ACTIVITY
            </div>
            <LogConsole entries={detail ? [...detail.logs].reverse() : []} limit={18} />
          </div>
          <div className="card p-3 space-y-1">
            <div className="text-[10px] font-semibold tracking-wider text-gray-500 mb-1">
              JOB HISTORY
            </div>
            {jobs.length === 0 && <div className="text-[11px] text-gray-600">No job on this lab yet.</div>}
            {jobs.slice(0, 6).map((job) => (
              <div key={job.id} className="text-[11px] flex items-center gap-2">
                <span className="font-mono text-gray-500">{job.id.slice(0, 12)}</span>
                <span className="text-gray-400">{job.job_type}</span>
                <span className="text-gray-600">{JOB_STATE_META[job.state]?.label ?? job.state}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
