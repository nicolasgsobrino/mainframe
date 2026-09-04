import type { LogEntry } from "../../types";
import { useProgressiveReveal } from "./reveal";

/** Colores por actor: agente, sistema de control y decisión humana. */
function actorClass(actor: string): string {
  if (actor.includes("HITL") || actor.includes("Owner") || actor.includes("CAB")) {
    return "text-amber-300";
  }
  if (actor === "Devin") return "text-brand";
  return "text-sky-300";
}

/**
 * La actividad que ya publica el backend, presentada como consola: misma
 * información, leída línea a línea. En Modo Demo entra de forma progresiva.
 */
export default function LogConsole({ entries, limit = 16, onSelect }: {
  entries: LogEntry[];
  limit?: number;
  onSelect?: (entry: LogEntry) => void;
}) {
  const shown = useProgressiveReveal(entries.slice(0, limit));
  if (entries.length === 0) {
    return (
      <div className="text-xs text-gray-600">
        Sin actividad todavía. Aprueba una fase en una tarea para ver al agente trabajar.
      </div>
    );
  }
  return (
    <div className="font-mono text-[11px] leading-relaxed space-y-0.5">
      {shown.map((e, i) => (
        <button
          key={`${e.task_id ?? "-"}:${i}`}
          type="button"
          disabled={!onSelect || !e.task_id}
          onClick={() => onSelect?.(e)}
          className={`w-full text-left flex gap-2 rounded px-1 py-0.5 ${
            onSelect && e.task_id ? "hover:bg-ink-panel" : "cursor-default"}`}
        >
          <span className="text-gray-700 shrink-0">›</span>
          <span className={`shrink-0 ${actorClass(e.actor)}`}>[{e.actor}]</span>
          <span className="text-gray-400">{e.msg}</span>
        </button>
      ))}
      {shown.length < Math.min(entries.length, limit) && (
        <div className="text-gray-700 px-1">
          <span className="animate-pulse">▍</span>
        </div>
      )}
    </div>
  );
}
