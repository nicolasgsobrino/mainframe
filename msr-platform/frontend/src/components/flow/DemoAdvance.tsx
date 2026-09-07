import { useState } from "react";
import type { HitlGate, TaskDetail } from "../../types";

/**
 * Control de ritmo de la demo: dice cuál es el único paso siguiente de la
 * vulnerabilidad y lo ejecuta. No inventa estado — encadena las acciones que
 * ya expone el backend (verificación humana registrada y aprobación de fase),
 * de forma que el recorrido avanza sobre datos reales.
 */
export interface DemoStep {
  kind: "verify" | "preapprove" | "deploy" | "approve" | "rollback" | "done";
  label: string;
  hint: string;
  gate: HitlGate | null;
  /** Anillo sobre el que actúa el paso, cuando el paso es de despliegue. */
  ring: number | null;
}

export function nextDemoStep(detail: TaskDetail): DemoStep {
  const j = detail.journey;
  // Una puerta pendiente detiene el recorrido: es siempre el siguiente paso.
  const gate = j.gates.find((g) => g.verifiable && g.status === "pending") ?? null;
  if (gate) {
    const ringResult = gate.id === "ring_result";
    return {
      kind: "verify",
      label: ringResult
        ? `Aceptar y promocionar el anillo ${gate.ring}`
        : `Verificar: ${gate.label}${gate.ring !== null ? ` · anillo ${gate.ring}` : ""}`,
      hint: ringResult
        ? `${gate.question} · acepta para promocionar al siguiente anillo o revierte este despliegue.`
        : `${gate.question} · el flujo está detenido hasta esta validación.`,
      gate,
      ring: gate.ring,
    };
  }
  if (j.pipeline_phase === "deployment") {
    const done = detail.rings_done;
    const rings = detail.artifacts.deployment.rings;
    const next = rings[done];
    if (!next) {
      return {
        kind: "done", label: "Recorrido completado", ring: null, gate: null,
        hint: "Todos los anillos desplegados y evidencias cerradas.",
      };
    }
    if (!next.plan.approval.preapproved) {
      return {
        kind: "preapprove", ring: next.ring, gate: null,
        label: `Pre-aprobar el anillo ${next.ring} · ${next.label}`,
        hint: "Puerta que sí bloquea: sin pre-aprobación humana del informe pre-anillo no se despliega.",
      };
    }
    return {
      kind: "deploy", ring: next.ring, gate: null,
      label: `Desplegar el anillo ${next.ring} (${done}/${rings.length})`,
      hint: "Ejecuta el lote del anillo pre-aprobado y publica su evidencia.",
    };
  }
  // Si la fase actual cierra una puerta humana (la aprobación del cambio), la
  // acción se cuenta con el nombre del proceso ITSM que corresponde.
  const phaseGate = j.gates.find(
    (g) => g.status === "pending" && g.closes_with === "phase_approval") ?? null;
  return {
    kind: "approve",
    label: phaseGate ? phaseGate.label : `Avanzar: ${j.phase_label}`,
    hint: phaseGate
      ? `${phaseGate.question} · el flujo está detenido hasta esta aprobación.`
      : "Aprueba la fase actual del pipeline y publica los artefactos de la siguiente.",
    gate: phaseGate,
    ring: null,
  };
}

/** Tarjeta del presentador: siguiente paso, acción y resultado de lo último. */
export function DemoAdvanceControl({ detail, onVerify, onAdvance, onPreapprove, busy = false }: {
  detail: TaskDetail;
  onVerify: (gate: HitlGate) => Promise<unknown>;
  onAdvance: () => Promise<unknown>;
  /** Pre-aprobación del informe pre-anillo, la puerta que sí bloquea. */
  onPreapprove?: (ring: number) => Promise<unknown>;
  busy?: boolean;
}) {
  const [running, setRunning] = useState(false);
  const [outcome, setOutcome] = useState<string | null>(null);
  const step = nextDemoStep(detail);
  const disabled = busy || running || step.kind === "done";

  const act = async () => {
    if (disabled) return;
    setRunning(true);
    try {
      if (step.kind === "verify" && step.gate) {
        await onVerify(step.gate);
        setOutcome(`Validación completada · ${step.gate.label}`);
      } else if (step.kind === "preapprove" && step.ring !== null && onPreapprove) {
        await onPreapprove(step.ring);
        setOutcome(`Anillo ${step.ring} pre-aprobado · listo para desplegar`);
      } else if (step.kind === "deploy") {
        await onAdvance();
        setOutcome(`Anillo ${step.ring} desplegado con su evidencia`);
      } else {
        await onAdvance();
        setOutcome(`Fase completada · ${detail.journey.phase_label}`);
      }
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="rounded-xl border border-fuchsia-500/35 bg-fuchsia-500/[0.06] p-3 space-y-2">
      <div className="flex items-center gap-2">
        <span className="text-[10px] font-semibold tracking-wider text-fuchsia-300">MODO DEMO · RITMO</span>
        <span className="text-[10px] text-fuchsia-200/70">el presentador decide cuándo avanza cada paso</span>
      </div>
      <div className="text-[11px] text-gray-400 leading-snug">{step.hint}</div>
      <button
        type="button"
        onClick={() => void act()}
        disabled={disabled}
        data-testid="demo-advance"
        className={`w-full rounded-lg px-3 py-2 text-xs font-semibold transition ${
          disabled
            ? "border border-line bg-ink text-gray-600 cursor-not-allowed"
            : "border border-fuchsia-500/50 bg-fuchsia-500/20 text-fuchsia-100 hover:bg-fuchsia-500/30"}`}
      >
        {running ? "Ejecutando…" : step.kind === "done" ? step.label : `${step.label} →`}
      </button>
      {outcome && (
        <div className="rounded border border-emerald-500/30 bg-emerald-500/5 px-2 py-1 text-[11px] text-emerald-300">
          ✓ {outcome}
        </div>
      )}
    </div>
  );
}
