import { ApiError } from "../../api";

/** Modo de ejecución: mock, dry-run o AWS real. Nunca se confunden en la UI. */
export const MODE_META: Record<string, { label: string; cls: string }> = {
  "mock": { label: "Simulation (mock)", cls: "bg-gray-500/15 text-gray-300" },
  "aws-dry-run": { label: "AWS · dry-run (no real changes)", cls: "bg-sky-500/15 text-sky-300" },
  "aws-real": { label: "AWS Systems Manager · live execution", cls: "bg-red-500/15 text-red-300" },
};

/** Estado del laboratorio según la evidencia persistida, nunca supuesto. */
export const STATE_META: Record<string, { label: string; cls: string }> = {
  unknown: { label: "State not evidenced", cls: "bg-gray-500/15 text-gray-300" },
  vulnerable: { label: "VULNERABLE", cls: "bg-amber-500/15 text-amber-300" },
  patched: { label: "PATCHED", cls: "bg-green-500/15 text-green-400" },
};

/** Estado del reconciliador (`ensure_lab_ready`). */
export const RECONCILE_META: Record<string, { label: string; cls: string }> = {
  idle: { label: "Reconciliation: not run", cls: "bg-gray-500/15 text-gray-300" },
  running: { label: "Reconciling…", cls: "bg-sky-500/15 text-sky-300" },
  ready: { label: "READY", cls: "bg-green-500/15 text-green-400" },
  resetting: { label: "Recreating the instance…", cls: "bg-sky-500/15 text-sky-300" },
  failed: { label: "Reconciliation failed", cls: "bg-red-500/15 text-red-300" },
  skipped: { label: "Reconciliation skipped", cls: "bg-amber-500/15 text-amber-300" },
};

/** Estado del job tal y como lo publica el backend, en lenguaje de operación. */
export const JOB_STATE_META: Record<string, { label: string; cls: string }> = {
  queued: { label: "Queued", cls: "bg-gray-500/15 text-gray-300" },
  validating: { label: "Running prechecks", cls: "bg-sky-500/15 text-sky-300" },
  dry_run: { label: "Dry-run: no changes applied", cls: "bg-sky-500/15 text-sky-300" },
  starting: { label: "Starting the Automation", cls: "bg-sky-500/15 text-sky-300" },
  running: { label: "Patching in progress", cls: "bg-sky-500/15 text-sky-300" },
  verifying: { label: "Verifying the result", cls: "bg-sky-500/15 text-sky-300" },
  succeeded: { label: "Succeeded", cls: "bg-green-500/15 text-green-400" },
  failed: { label: "Failed", cls: "bg-red-500/15 text-red-300" },
  cancelling: { label: "Cancelling", cls: "bg-amber-500/15 text-amber-300" },
  cancelled: { label: "Cancelled", cls: "bg-amber-500/15 text-amber-300" },
  restore_queued: { label: "Reset queued", cls: "bg-gray-500/15 text-gray-300" },
  restoring: { label: "Recreating the instance", cls: "bg-sky-500/15 text-sky-300" },
  restored: { label: "Instance recreated", cls: "bg-green-500/15 text-green-400" },
  restore_failed: { label: "Reset failed", cls: "bg-red-500/15 text-red-300" },
  timed_out: { label: "Timed out", cls: "bg-red-500/15 text-red-300" },
  timeout_pending_confirmation: {
    label: "Timed out · awaiting confirmation from AWS", cls: "bg-amber-500/15 text-amber-300",
  },
  remote_status_unknown: {
    label: "Remote state unknown", cls: "bg-amber-500/15 text-amber-300",
  },
  stop_requested: { label: "Stop requested", cls: "bg-amber-500/15 text-amber-300" },
};

export const ts = (value: string | null | undefined) =>
  (value ? new Date(value).toLocaleString("en-GB") : "—");

export const tri = (value: boolean | null | undefined) =>
  (value === null || value === undefined ? "no evidence" : value ? "yes" : "no");

export const toError = (e: unknown) =>
  (e instanceof ApiError
    ? { code: e.code, message: e.message }
    : { code: "NETWORK_ERROR", message: e instanceof Error ? e.message : String(e) });
