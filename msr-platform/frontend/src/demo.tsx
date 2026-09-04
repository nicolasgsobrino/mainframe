import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api } from "./api";
import type { ExecutionConfig } from "./types";

/**
 * Modo Demo: capa de presentación, ortogonal al modo de ejecución.
 *
 * `mock | aws-dry-run | aws-real` dice qué se ejecuta de verdad; el Modo Demo
 * sólo cambia el ritmo y el foco con el que se cuenta lo que el backend ya
 * devuelve. No introduce datos ficticios ni altera ninguna llamada, y por eso
 * sólo puede activarse cuando no hay mutaciones reales en juego.
 */
interface DemoCtx {
  /** Preferencia del presentador. */
  enabled: boolean;
  /** Activo de verdad: la preferencia sólo cuenta si el modo lo permite. */
  active: boolean;
  allowed: boolean;
  /** El modo de ejecución ya se conoce: hasta entonces `allowed` no decide nada. */
  resolved: boolean;
  reason: string | null;
  setEnabled: (on: boolean) => void;
  setExecution: (execution: ExecutionConfig | null) => void;
}

const Ctx = createContext<DemoCtx>({
  enabled: false, active: false, allowed: false, resolved: false, reason: null,
  setEnabled: () => {}, setExecution: () => {},
});

const STORAGE_KEY = "msr_demo_mode";

/** El Modo Demo no se ofrece sobre ejecución real: allí nada es narrativa. */
function allowance(execution: ExecutionConfig | null): { allowed: boolean; reason: string | null } {
  if (!execution) return { allowed: false, reason: "Modo de ejecución todavía desconocido." };
  if (execution.patch_provider === "mock" || execution.dry_run) return { allowed: true, reason: null };
  return { allowed: false, reason: "No disponible en ejecución real de AWS: las acciones mutan recursos." };
}

export function DemoProvider({ children }: { children: ReactNode }) {
  const [enabled, setEnabledState] = useState(() => localStorage.getItem(STORAGE_KEY) === "1");
  const [execution, setExecution] = useState<ExecutionConfig | null>(null);
  const { allowed, reason } = allowance(execution);

  // El modo de ejecución se resuelve una vez para toda la app: las páginas que
  // ya lo consultan sólo lo refrescan (`useReportExecution`).
  useEffect(() => {
    let active = true;
    api.execution().then((e) => { if (active) setExecution(e); }).catch(() => {});
    return () => { active = false; };
  }, []);

  const setEnabled = (on: boolean) => {
    setEnabledState(on);
    localStorage.setItem(STORAGE_KEY, on ? "1" : "0");
  };

  return (
    <Ctx.Provider value={{
      enabled, active: enabled && allowed, allowed, resolved: execution !== null, reason,
      setEnabled, setExecution,
    }}>
      {children}
    </Ctx.Provider>
  );
}

export const useDemo = () => useContext(Ctx);

/** Registra el modo de ejecución observado por la página que ya lo consulta. */
export function useReportExecution(execution: ExecutionConfig | null) {
  const { setExecution } = useDemo();
  useEffect(() => {
    if (execution) setExecution(execution);
  }, [execution, setExecution]);
}

export function DemoToggle() {
  const { enabled, allowed, reason, setEnabled } = useDemo();
  return (
    <button
      type="button"
      disabled={!allowed}
      onClick={() => setEnabled(!enabled)}
      title={reason ?? "Presentación guiada sobre los mismos datos: sin cambios reales"}
      className={`w-full rounded-lg border px-3 py-1.5 text-xs font-semibold transition ${
        !allowed
          ? "border-line bg-ink text-gray-600 cursor-not-allowed"
          : enabled
            ? "border-fuchsia-500/50 bg-fuchsia-500/15 text-fuchsia-300"
            : "border-line bg-ink text-gray-400 hover:text-gray-200"}`}
    >
      ◉ Modo Demo · {enabled && allowed ? "activo" : "apagado"}
    </button>
  );
}

/** Aviso permanente mientras la narrativa está activa. */
export function DemoBanner() {
  const { active } = useDemo();
  if (!active) return null;
  return (
    <div className="border-b border-fuchsia-500/30 bg-fuchsia-500/10 px-6 py-2 text-xs text-fuchsia-200 flex items-center gap-2">
      <span className="w-2 h-2 rounded-full bg-fuchsia-400 animate-pulse" />
      <b>Modo Demo</b>
      <span className="text-fuchsia-200/80">
        presentación guiada sobre datos reales del backend · ninguna acción muta recursos en AWS
      </span>
    </div>
  );
}
