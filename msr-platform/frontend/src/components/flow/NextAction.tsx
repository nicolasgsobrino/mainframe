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
      return { verb: "Verificar", object: step.gate?.label ?? "punto de control" };
    case "preapprove":
      return { verb: "Pre-aprobar", object: `anillo ${step.ring}` };
    case "deploy":
      return { verb: "Desplegar", object: `anillo ${step.ring}` };
    case "approve":
      return { verb: "Aprobar", object: step.gate?.label ?? "la fase actual" };
    case "rollback":
      return { verb: "Revertir", object: `anillo ${step.ring}` };
    default:
      return { verb: "Completado", object: "" };
  }
}

const TONE = {
  human: {
    accent: "#f59e0b",
    kicker: "TU TURNO · DECISIÓN HUMANA",
    who: "Nadie automatiza esto: el flujo está detenido hasta que una persona lo apruebe.",
    icon: "✋",
  },
  auto: {
    accent: "#8ef04a",
    kicker: "TURNO DE LA PLATAFORMA · EJECUCIÓN AUTOMÁTICA",
    who: "Autorizado por el humano; ahora ejecuta el agente y publica su evidencia.",
    icon: "⚙",
  },
  done: {
    accent: "#34d399",
    kicker: "RECORRIDO COMPLETADO",
    who: "Todos los anillos desplegados y las evidencias aceptadas.",
    icon: "✓",
  },
} as const;

export function NextActionBar({ step, running, onAct, onGoToScene }: {
  step: DemoStep;
  running: boolean;
  onAct: () => void;
  /** Cuando el paso vive en otra escena, saltar a ella antes de actuar. */
  onGoToScene?: () => void;
}) {
  const tone = stepTone(step);
  const meta = TONE[tone];
  const { verb, object } = stepAction(step);
  const disabled = running || tone === "done";

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
          {tone === "done" ? "Recorrido completado" : <>{verb} <span className="text-gray-400 font-semibold">· {object}</span></>}
        </div>
        <div className="text-[11px] text-gray-400 mt-0.5">{tone === "done" ? meta.who : step.hint}</div>
      </div>
      <div className="flex items-center gap-2">
        {onGoToScene && (
          <button type="button" onClick={onGoToScene}
                  className="text-[11px] rounded-lg border border-line px-3 py-2 text-gray-400 hover:text-gray-200">
            Ver su escena
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
            {running ? "Ejecutando…" : tone === "done" ? "Sin pasos pendientes" : `${verb} →`}
          </button>
        </span>
      </div>
    </div>
  );
}
