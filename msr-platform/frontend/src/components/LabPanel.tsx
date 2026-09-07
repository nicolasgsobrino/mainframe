import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, api, releaseIdempotencyKey } from "../api";
import type { LabCheck, LabReconcileResult, LabSnapshot, LabValidation, PatchJob } from "../types";

/** Modo de ejecución: mock, dry-run o AWS real. Nunca se confunden en la UI. */
const MODE_META: Record<string, { label: string; cls: string }> = {
  "mock": { label: "Simulation (mock)", cls: "bg-gray-500/15 text-gray-300" },
  "aws-dry-run": { label: "AWS · dry-run (no real changes)", cls: "bg-sky-500/15 text-sky-300" },
  "aws-real": { label: "AWS Systems Manager · live execution", cls: "bg-red-500/15 text-red-300" },
};

/** Estado del laboratorio según la evidencia persistida, nunca supuesto. */
const STATE_META: Record<string, { label: string; cls: string }> = {
  unknown: { label: "State not evidenced", cls: "bg-gray-500/15 text-gray-300" },
  vulnerable: { label: "VULNERABLE", cls: "bg-amber-500/15 text-amber-300" },
  patched: { label: "PATCHED", cls: "bg-green-500/15 text-green-400" },
};

/** Estado del reconciliador (`ensure_lab_ready`). */
const RECONCILE_META: Record<string, { label: string; cls: string }> = {
  idle: { label: "Reconciliation: not run", cls: "bg-gray-500/15 text-gray-300" },
  running: { label: "Reconciling…", cls: "bg-sky-500/15 text-sky-300" },
  ready: { label: "READY", cls: "bg-green-500/15 text-green-400" },
  resetting: { label: "Recreating the instance…", cls: "bg-sky-500/15 text-sky-300" },
  failed: { label: "Reconciliation failed", cls: "bg-red-500/15 text-red-300" },
  skipped: { label: "Reconciliation skipped", cls: "bg-amber-500/15 text-amber-300" },
};

const ts = (value: string | null) => (value ? new Date(value).toLocaleString("en-GB") : "—");
const tri = (value: boolean | null | undefined) =>
  value === null || value === undefined ? "no evidence" : value ? "yes" : "no";

const toError = (e: unknown) =>
  e instanceof ApiError
    ? { code: e.code, message: e.message }
    : { code: "NETWORK_ERROR", message: e instanceof Error ? e.message : String(e) };

/** Una comprobación: verde si cumple, roja si falla, gris si no es concluyente. */
function Check({ c }: { c: LabCheck }) {
  const [icon, cls] = c.ok === null ? ["?", "text-gray-400"]
    : c.ok ? ["\u2713", "text-green-400"] : ["\u2717", "text-red-400"];
  return (
    <div className="text-xs flex gap-2">
      <span className={cls}>{icon}</span>
      <span className="text-gray-300">{c.check}</span>
      <span className="text-gray-500">{c.detail}</span>
    </div>
  );
}

function Field({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-wide text-gray-500 font-semibold">{label}</div>
      <div className={`text-sm text-gray-200 ${mono ? "font-mono" : ""}`}>{value}</div>
    </div>
  );
}

/** Panel del laboratorio EC2 reutilizable.
 *
 * No acepta Instance IDs, comandos, documentos ni parámetros: sólo dispara
 * las tres operaciones cerradas del backend sobre el identificador lógico. */
export default function LabPanel({ labId, onPatch, patchBlockedReason, locked, onLabChange }: {
  labId: string;
  onPatch: () => void;
  patchBlockedReason: string | null;
  locked: boolean;
  /** El recurso ha cambiado (reset → otra instancia, parcheo): quien contiene
   *  el panel debe recargar lo que muestre evidencia de ese recurso. */
  onLabChange?: () => void;
}) {
  const [snapshot, setSnapshot] = useState<LabSnapshot | null>(null);
  const [validation, setValidation] = useState<LabValidation | null>(null);
  const [jobs, setJobs] = useState<PatchJob[]>([]);
  const [busy, setBusy] = useState(false);
  const [reconcile, setReconcile] = useState<LabReconcileResult | null>(null);
  const [confirmReset, setConfirmReset] = useState(false);
  const [error, setError] = useState<{ code: string; message: string } | null>(null);

  const load = useCallback(async () => {
    const [next, history] = await Promise.all([api.lab(labId), api.labJobs(labId)]);
    setSnapshot(next);
    setJobs(history);
  }, [labId]);

  useEffect(() => { load().catch((e) => setError(toError(e))); }, [load]);

  // Polling: el job de reset sobrevive a un reload porque `active_job` viene
  // del backend, y el sondeo se detiene en cuanto AWS confirma un estado final.
  const activeJob = snapshot?.active_job ?? null;
  useEffect(() => {
    if (!activeJob || activeJob.terminal) return;
    const timer = window.setInterval(() => {
      load().catch((e) => setError(toError(e)));
    }, 2000);
    return () => window.clearInterval(timer);
  }, [activeJob, load]);

  // Un reset recrea la instancia y borra la evidencia del parcheo: el resto de
  // la pantalla no puede seguir mostrando el estado anterior hasta que alguien
  // recargue el navegador.
  const labSignature = `${snapshot?.instance?.instance_id ?? ""}:${snapshot?.vulnerable_state ?? ""}`;
  const lastSignature = useRef<string | null>(null);
  useEffect(() => {
    if (!snapshot) return;
    if (lastSignature.current !== null && lastSignature.current !== labSignature) {
      // La validación anterior describe un recurso que ya no existe.
      setValidation(null);
      onLabChange?.();
    }
    lastSignature.current = labSignature;
  }, [snapshot, labSignature, onLabChange]);

  if (!snapshot) {
    return (
      <div className="card p-4 text-sm text-gray-400">
        {error ? `${error.code}: ${error.message}` : "Loading the lab…"}
      </div>
    );
  }

  const instance = snapshot.instance;
  const mode = MODE_META[snapshot.execution_mode] ?? MODE_META.mock;
  const state = STATE_META[snapshot.vulnerable_state] ?? STATE_META.unknown;
  const reconciliation = snapshot.reconciliation;
  const reconcileState = reconciliation.reconciliation_state ?? "idle";
  const reconcileMeta = RECONCILE_META[reconcileState] ?? RECONCILE_META.idle;
  const realMode = snapshot.execution_mode === "aws-real";
  const jobRunning = !!activeJob && !activeJob.terminal;
  const disabled = busy || locked || jobRunning;
  // El parcheo exige una validación previa que confirme el estado vulnerable.
  const validatedVulnerable = !!validation?.allowed && validation.vulnerable_state === "vulnerable";
  const patchBlocked = patchBlockedReason
    ?? (!validatedVulnerable ? "Run “Validate lab” first: patching requires a successful validation "
      + "with the lab in a vulnerable state." : null);

  const run = async (action: () => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    try {
      await action();
      await load();
    } catch (e) {
      setError(toError(e));
    } finally {
      setBusy(false);
    }
  };

  const validate = () => run(async () => setValidation(await api.validateLab(labId)));
  // `ensure_lab_ready`: en modo real la recreación exige la misma confirmación.
  const runReconcile = () => run(async () => setReconcile(await api.reconcileLab(labId, realMode)));
  const reset = () => run(async () => {
    await api.resetLab(labId, realMode);
    releaseIdempotencyKey(`lab-reset:${labId}`);
    setValidation(null);
    setConfirmReset(false);
  });

  const resets = jobs.filter((job) => job.job_type === "reset_lab");
  const lastReset = resets[0];
  const previousInstanceId = lastReset?.targets[0]?.instance_id ?? null;

  return (
    <div className="card p-4 space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm font-bold text-gray-100">EC2 lab · {labId}</div>
          <div className="text-xs text-gray-500">
            The instance is resolved by tags on every operation: a reset recreates it with a different Instance ID.
          </div>
        </div>
        <div className="flex flex-wrap gap-1.5 justify-end">
          <span className={`chip ${mode.cls}`}>{mode.label}</span>
          <span className={`chip ${state.cls}`}>{state.label}</span>
          <span className={`chip ${reconcileMeta.cls}`}>{reconcileMeta.label}</span>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Field label="Instance ID" value={instance?.instance_id ?? "unresolved"} mono />
        <Field label="EC2 state" value={instance?.state ?? "—"} />
        <Field label="AMI" value={instance?.image_id ?? snapshot.lab?.vulnerable_ami_id ?? "—"} mono />
        <Field label="Advisory" value={snapshot.advisory_id} mono />
        <Field label="Previous instance"
          value={snapshot.previous_instance_id ?? "—"} mono />
        <Field label="SSM agent"
          value={snapshot.ssm_state
            ?? (instance ? (instance.ssm_managed ? `Online (${instance.ping_status ?? "—"})` : "Not managed") : "—")} />
        <Field label="Health" value={snapshot.health_state ?? "no evidence"} />
        <Field label="Current kernel" value={snapshot.current_kernel ?? "no evidence"} mono />
        <Field label="Advisory applicable" value={tri(snapshot.advisory_applicable)} />
        <Field label="Account / region"
          value={`${instance?.account_id ?? snapshot.lab?.account_id ?? "—"} · ${instance?.region ?? snapshot.lab?.region ?? "—"}`} />
        <Field label="Resets executed" value={String(resets.length)} />
        {/* Sólo lectura: el grupo lo fija la IaC y el backend; la UI no lo envía nunca. */}
        <Field label="Auto Scaling Group"
          value={snapshot.lab?.autoscaling_group_name ?? "—"} mono />
        {/* Sólo lectura: releasever y kernel corregido también vienen de la IaC. */}
        <Field label="Releasever" value={snapshot.releasever} mono />
        <Field label="Fixed kernel" value={snapshot.expected_fixed_kernel} mono />
        <Field label="Automation · patch" value={snapshot.last_patch_execution_id ?? "—"} mono />
        <Field label="Automation · reset" value={snapshot.last_reset_execution_id ?? "—"} mono />
        <Field label="Evidence" value={snapshot.evidence_source ?? "not observed"} />
        <Field label="Last reconciliation" value={ts(snapshot.last_reconciled_at)} />
      </div>

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

      {!snapshot.advisory_confirmed && (
        <div className="text-[11px] text-gray-500">
          No observed evidence yet: only the read-only precheck confirms whether
          {" "}{snapshot.advisory_id} applies to the resolved instance.
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        <button className="btn btn-ghost disabled:opacity-40" onClick={validate} disabled={disabled}>
          Validate lab
        </button>
        <button className="btn btn-ghost disabled:opacity-40" onClick={runReconcile} disabled={disabled}
          title="ensure_lab_ready: resolves the instance by tags and leaves the lab ready">
          Ensure lab ready
        </button>
        <button className="btn btn-brand disabled:opacity-40" onClick={onPatch} disabled={disabled || !!patchBlocked}
          title={patchBlocked ?? "Applies the advisory through the Automation runbook"}>
          Patch instance
        </button>
        <button className="btn btn-ghost disabled:opacity-40" onClick={() => setConfirmReset(true)} disabled={disabled}>
          Reset lab
        </button>
      </div>
      {patchBlocked && <div className="text-[11px] text-amber-300">{patchBlocked}</div>}

      {confirmReset && (
        <div className="rounded-lg border border-orange-500/40 bg-orange-500/10 px-3 py-2 space-y-2">
          <div className="text-xs text-orange-200">
            A reset <strong>is not a rollback</strong>: it terminates the current instance and creates a new
            one from the Launch Template to leave the lab vulnerable again. The job history is kept and the
            rings already deployed are not undone.
          </div>
          <div className="flex gap-2">
            <button className="btn btn-brand disabled:opacity-40" onClick={reset} disabled={busy}>
              Confirm the lab reset
            </button>
            <button className="btn btn-ghost disabled:opacity-40" onClick={() => setConfirmReset(false)} disabled={busy}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {lastReset && (
        <div className="text-xs text-gray-400">
          Last reset <span className="font-mono">{lastReset.id}</span> · {lastReset.state} ·
          {" "}<span className="font-mono">{previousInstanceId ?? "—"}</span> →{" "}
          <span className="font-mono">{
            lastReset.state === "restored" ? (instance?.instance_id ?? "—") : "pending"
          }</span>
        </div>
      )}

      {reconcile && (
        <div className="space-y-1 rounded-lg border border-gray-700/60 px-3 py-2">
          <div className="text-[11px] uppercase tracking-wide text-gray-500 font-semibold">
            Last reconciliation · {reconcile.correlation_id}
          </div>
          <div className="text-xs text-gray-300">
            {reconcile.state} · action {reconcile.action} ·{" "}
            {reconcile.ready ? "lab READY" : "lab not ready"} ·{" "}
            <span className="font-mono">{reconcile.previous_instance_id ?? "—"}</span> →{" "}
            <span className="font-mono">{reconcile.instance_id ?? "—"}</span>
          </div>
          <div className="text-xs text-gray-500">{reconcile.detail || "—"}</div>
          {reconcile.error && (
            <div className="text-xs text-red-300">{reconcile.error_code}: {reconcile.error}</div>
          )}
          {reconcile.evidence?.checks.map((c) => <Check key={c.check} c={c} />)}
        </div>
      )}

      {validation && (
        <div className="space-y-1">
          <div className="text-[11px] uppercase tracking-wide text-gray-500 font-semibold">
            Read-only validation
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
      )}

      {error && (
        <div className="text-xs text-red-300">{error.code}: {error.message}</div>
      )}
    </div>
  );
}
