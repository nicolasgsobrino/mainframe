import { useEffect, useState } from "react";

/**
 * Reproducción con ritmo de lo que el backend acaba de ejecutar.
 *
 * No simula nada: cada línea es un comando del plan del anillo o una entrada
 * del log que la acción ha escrito de verdad. Lo único que añade la demo es el
 * tiempo — en mock todo ocurre en milisegundos y la audiencia no llega a ver
 * qué ha pasado por detrás.
 */
export interface ExecLine {
  actor: string;
  text: string;
  /** Comando, referencia o salida asociada, si el dato existe. */
  detail?: string | null;
  status?: "ok" | "info" | "warn";
}

/** Presupuesto de tiempo de la reproducción y límites por línea. */
const TOTAL_MS = 11000;
const MIN_MS = 170;
const MAX_MS = 550;

const stepMs = (count: number) =>
  Math.min(MAX_MS, Math.max(MIN_MS, Math.round(TOTAL_MS / Math.max(count, 1))));

const reducedMotion = () =>
  typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const ACTOR_COLOR: Record<string, string> = {
  Devin: "text-brand",
  ServiceNow: "text-sky-300",
  AWS: "text-amber-300",
  SSM: "text-amber-300",
  Human: "text-fuchsia-300",
};

const actorClass = (actor: string) =>
  Object.entries(ACTOR_COLOR).find(([k]) => actor.toLowerCase().includes(k.toLowerCase()))?.[1]
  ?? "text-gray-400";

export function ExecutionTheatre({ title, subtitle, lines, onDone, onDismiss }: {
  title: string;
  subtitle: string;
  lines: ExecLine[];
  /** Se dispara una vez cuando termina la reproducción. */
  onDone?: () => void;
  onDismiss?: () => void;
}) {
  const instant = reducedMotion();
  const [shown, setShown] = useState(instant ? lines.length : 0);

  useEffect(() => {
    if (instant) { setShown(lines.length); return; }
    setShown(0);
    const timer = setInterval(() => {
      setShown((c) => (c >= lines.length ? c : c + 1));
    }, stepMs(lines.length));
    return () => clearInterval(timer);
  }, [lines, instant]);

  const finished = shown >= lines.length;
  useEffect(() => { if (finished) onDone?.(); }, [finished, onDone]);

  const pct = lines.length === 0 ? 100 : Math.round((shown / lines.length) * 100);

  return (
    <div className={`rounded-xl border p-4 space-y-3 animate-fade-in ${
      finished ? "border-emerald-500/40 bg-emerald-500/[0.05]" : "border-brand/40 bg-brand/[0.05]"}`}>
      <div className="flex items-start gap-3">
        <span className={`mt-0.5 w-5 h-5 rounded-full flex items-center justify-center text-[11px] font-bold ${
          finished ? "bg-emerald-500/20 text-emerald-300" : "bg-brand/20 text-brand animate-pulse"}`}>
          {finished ? "✓" : "▸"}
        </span>
        <div className="flex-1 min-w-0">
          <div className="text-sm font-bold text-gray-100">{title}</div>
          <div className="text-[11px] text-gray-500">{subtitle}</div>
        </div>
        <div className="text-right">
          <div className={`text-xs font-mono ${finished ? "text-emerald-300" : "text-brand"}`}>
            {shown}/{lines.length}
          </div>
          {finished ? onDismiss && (
            <button type="button" onClick={onDismiss}
                    className="text-[10px] text-gray-500 hover:text-gray-300">cerrar</button>
          ) : (
            <button type="button" onClick={() => setShown(lines.length)}
                    className="text-[10px] text-gray-500 hover:text-gray-300">saltar ⏭</button>
          )}
        </div>
      </div>

      <div className="h-1 rounded bg-ink overflow-hidden">
        <div className={`h-full transition-all duration-500 ${finished ? "bg-emerald-400" : "bg-brand"}`}
             style={{ width: `${pct}%` }} />
      </div>

      <ol className="space-y-1.5">
        {lines.slice(0, shown).map((l, i) => {
          const running = !finished && i === shown - 1;
          return (
            <li key={`${l.text}-${i}`} className="animate-fade-in flex items-start gap-2 text-[11px]">
              <span className={`mt-[3px] w-1.5 h-1.5 rounded-full shrink-0 ${
                running ? "bg-brand animate-pulse" : l.status === "warn" ? "bg-amber-400" : "bg-emerald-400"}`} />
              <div className="min-w-0">
                <span className={`font-mono ${actorClass(l.actor)}`}>[{l.actor}]</span>{" "}
                <span className="text-gray-300">{l.text}</span>
                {l.detail && (
                  <div className="font-mono text-[10px] text-gray-500 break-all leading-snug">{l.detail}</div>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
