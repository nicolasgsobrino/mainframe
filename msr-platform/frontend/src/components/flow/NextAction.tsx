import { useState } from "react";
import type { DemoStep } from "./DemoAdvance";

/**
 * Único punto focal de la pantalla guiada: qué hay que hacer ahora y quién lo
 * hace. La distinción importante para la audiencia no es el nombre del botón
 * sino de quién es el turno — decisión humana (ámbar) frente a ejecución
 * automática (verde de marca).
 */
export type StepTone = "human" | "auto" | "done";

export function stepTone(step: DemoStep): StepTone {
  if (step.kind === "done") return "done";
  return step.kind === "verify" || step.kind === "preapprove" || step.kind === "rollback"
    ? "human"
    : "auto";
}

/** Verbo corto y objeto de la acción, para no obligar a leer el botón entero. */
export function stepAction(step: DemoStep): { verb: string; object: string } {
  switch (step.kind) {
    case "verify":
      return step.gate?.id === "ring_result"
        ? { verb: "Accept and promote", object: `ring ${step.ring}` }
        : { verb: "Verify", object: step.gate?.label ?? "control point" };
    case "preapprove":
      return { verb: "Pre-approve", object: `ring ${step.ring}` };
    case "deploy":
      return { verb: "Deploy", object: `ring ${step.ring}` };
    case "approve":
      return { verb: "Approve", object: step.gate?.label ?? "the current phase" };
    case "rollback":
      return { verb: "Roll back", object: `ring ${step.ring}` };
    default:
      return { verb: "Completed", object: "" };
  }
}

const TONE = {
  human: {
    accent: "#f59e0b",
    kicker: "YOUR TURN · HUMAN DECISION",
    who: "Nothing automates this: the flow is stopped until a person approves it.",
    icon: "✋",
  },
  auto: {
    accent: "#8ef04a",
    kicker: "PLATFORM'S TURN · AUTOMATED EXECUTION",
    who: "Authorised by a human; the agent now runs and publishes its evidence.",
    icon: "⚙",
  },
  done: {
    accent: "#34d399",
    kicker: "JOURNEY COMPLETED",
    who: "All rings deployed and evidence accepted.",
    icon: "✓",
  },
} as const;

export function NextActionBar({ step, running, onAct, onGoToScene, onRollback }: {
  step: DemoStep;
  running: boolean;
  onAct: () => void;
  /** Cuando el paso vive en otra escena, saltar a ella antes de actuar. */
  onGoToScene?: () => void;
  /** Segunda salida de la validación del anillo: revertir en vez de aceptar. */
  onRollback?: (ring: number) => void;
}) {
  const [armed, setArmed] = useState(false);
  const tone = stepTone(step);
  const meta = TONE[tone];
  const { verb, object } = stepAction(step);
  const disabled = running || tone === "done";
  const rollbackRing = onRollback && step.kind === "verify"
    && step.gate?.id === "ring_result" && step.ring !== null
    ? step.ring
    : null;

  return (
    <div className="rounded-xl border-2 p-4 flex flex-wrap items-center gap-4"
         style={{ borderColor: meta.accent + "66", background: meta.accent + "0f" }}>
      <span className="w-11 h-11 rounded-xl flex items-center justify-center text-xl shrink-0"
            style={{ background: meta.accent + "22", color: meta.accent }}>
        {meta.icon}
      </span>
      <div className="flex-1 min-w-[16rem]">
        <div className="text-[10px] font-bold tracking-[0.16em]" style={{ color: meta.accent }}>
          {meta.kicker}
        </div>
        <div className="text-lg font-bold text-gray-100 leading-tight">
          {tone === "done" ? "Journey completed" : <>{verb} <span className="text-gray-400 font-semibold">· {object}</span></>}
        </div>
        <div className="text-[11px] text-gray-400 mt-0.5">{tone === "done" ? meta.who : step.hint}</div>
      </div>
      <div className="flex items-center gap-2">
        {onGoToScene && (
          <button type="button" onClick={onGoToScene}
                  className="text-[11px] rounded-lg border border-line px-3 py-2 text-gray-400 hover:text-gray-200">
            Go to its scene
          </button>
        )}
        {rollbackRing !== null && (
          <button
            type="button"
            disabled={disabled}
            onClick={() => {
              if (disabled) return;
              if (!armed) { setArmed(true); return; }
              setArmed(false);
              onRollback?.(rollbackRing);
            }}
            onBlur={() => setArmed(false)}
            data-testid="demo-next-rollback"
            title={`Rolls ring ${rollbackRing} back to its pre-deployment state`}
            className={`rounded-lg border px-4 py-2.5 text-sm font-bold transition disabled:opacity-50 disabled:cursor-not-allowed ${
              armed
                ? "border-orange-500/70 bg-orange-500/25 text-orange-100"
                : "border-orange-500/50 bg-orange-500/10 text-orange-300 hover:bg-orange-500/20"}`}
          >
            {armed ? "Confirm rollback" : "⟲ Rollback"}
          </button>
        )}
        <span className="relative inline-flex">
          {!disabled && (
            <span className="absolute inset-0 rounded-lg animate-ping opacity-40"
                  style={{ background: meta.accent + "44" }} aria-hidden />
          )}
          <button
            type="button"
            onClick={onAct}
            disabled={disabled}
            data-testid="demo-next-action"
            className="relative rounded-lg px-5 py-2.5 text-sm font-bold transition disabled:cursor-not-allowed"
            style={{
              background: disabled ? "#1b1f27" : meta.accent,
              color: disabled ? "#64748b" : "#0b0d11",
              border: `1px solid ${disabled ? "#2b313d" : meta.accent}`,
            }}
          >
            {running ? "Running…" : tone === "done" ? "No steps pending" : `${verb} →`}
          </button>
        </span>
      </div>
    </div>
  );
}
