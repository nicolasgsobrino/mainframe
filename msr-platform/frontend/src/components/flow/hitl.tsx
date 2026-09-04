import type { HitlGate, HitlGateStatus, HitlRollup } from "../../types";

/** Lenguaje visual único del control humano: ámbar en todas las vistas. */
export const HITL_COLOR = "#f59e0b";

const STATUS_META: Record<HitlGateStatus, { label: string; cls: string; dot: string }> = {
  done: {
    label: "decidido",
    cls: "border-emerald-500/40 text-emerald-300 bg-emerald-500/10",
    dot: "#22c55e",
  },
  pending: {
    label: "espera decisión",
    cls: "border-amber-500/50 text-amber-300 bg-amber-500/15",
    dot: HITL_COLOR,
  },
  upcoming: {
    label: "por venir",
    cls: "border-line text-gray-500 bg-ink",
    dot: "#475569",
  },
};

function when(ts: string | null): string {
  if (!ts) return "";
  const d = new Date(ts);
  return Number.isNaN(d.getTime()) ? ts : d.toLocaleString("es-ES", { dateStyle: "short", timeStyle: "short" });
}

/**
 * Una puerta humana, con la misma plantilla en todo el producto: qué se
 * decide, quién decidió y si el motor la aplica o sólo la registra.
 */
export function HitlGateCard({ gate, onSelect }: { gate: HitlGate; onSelect?: () => void }) {
  const meta = STATUS_META[gate.status];
  const body = (
    <>
      <div className="flex items-center gap-2">
        <span className="w-1.5 h-1.5 rounded-full" style={{ background: meta.dot }} />
        <span className="text-xs font-semibold text-gray-200 leading-snug">
          {gate.label}
          {gate.ring !== null && <span className="text-gray-500 font-normal"> · anillo {gate.ring}</span>}
        </span>
        <span className={`chip ml-auto border ${meta.cls}`}>{meta.label}</span>
      </div>
      <div className="text-[11px] text-gray-500 leading-snug mt-1">{gate.question}</div>
      {gate.status === "done" && gate.actor && (
        <div className="text-[11px] text-gray-400 mt-1">
          {gate.actor}
          {gate.ts && <span className="text-gray-600"> · {when(gate.ts)}</span>}
          {gate.note && <span className="text-gray-500"> · «{gate.note}»</span>}
        </div>
      )}
      {!gate.enforced && (
        <div className="text-[10px] text-gray-600 mt-1"
             title="Punto de control registrado: el motor todavía no lo bloquea">
          registro · no bloquea la ejecución
        </div>
      )}
    </>
  );
  const cls = `rounded-lg border p-2.5 w-full text-left ${
    gate.status === "pending" ? "border-amber-500/40 bg-amber-500/5" : "border-line bg-ink"}`;
  return onSelect
    ? <button type="button" onClick={onSelect} className={`${cls} hover:bg-ink-panel transition-colors`}>{body}</button>
    : <div className={cls}>{body}</div>;
}

/**
 * Carril transversal de Human in the Loop: las puertas no son una fase, son un
 * tipo de evento que se repite a lo largo del recorrido.
 */
export function HitlRail({ gates, compact = false }: { gates: HitlGate[]; compact?: boolean }) {
  const shown = compact ? gates.filter((g) => g.status !== "upcoming" || !g.per_ring) : gates;
  if (shown.length === 0) return null;
  return (
    <div className="rounded-xl border border-amber-500/25 bg-amber-500/[0.03] p-3 space-y-2">
      <div className="flex items-center gap-2">
        <span className="text-[10px] font-semibold tracking-wider" style={{ color: HITL_COLOR }}>
          HUMAN IN THE LOOP
        </span>
        <span className="text-[10px] text-gray-500">
          control humano recurrente a lo largo del recorrido, no una fase
        </span>
      </div>
      <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
        {shown.map((g) => <HitlGateCard key={`${g.id}:${g.ring ?? "-"}`} gate={g} />)}
      </div>
    </div>
  );
}

/** Contador de decisiones humanas: tomadas, pendientes y la siguiente. */
export function HitlCounter({ hitl }: { hitl: HitlRollup }) {
  return (
    <div className="flex flex-wrap items-center gap-2 text-xs">
      <span className="chip border border-amber-500/40 bg-amber-500/15 text-amber-300 font-semibold">
        {hitl.pending === 1
          ? "1 decisión humana pendiente"
          : `${hitl.pending} decisiones humanas pendientes`}
      </span>
      <span className="text-gray-500">
        {hitl.done}/{hitl.total} puntos de control superados
        {hitl.pending_enforced > 0 && ` · ${hitl.pending_enforced} bloquean la ejecución`}
      </span>
      {hitl.next && (
        <span className="text-gray-400">
          Siguiente: <b className="text-gray-200">{hitl.next.label}</b>
          {hitl.next.ring !== null && ` (anillo ${hitl.next.ring})`}
        </span>
      )}
    </div>
  );
}

/** Distingue lo que hace la máquina de lo que decide una persona. */
export function AutomationBadge({ human, label }: { human: boolean; label?: string }) {
  return (
    <span
      className={`chip border ${human
        ? "border-amber-500/40 bg-amber-500/15 text-amber-300"
        : "border-brand/40 bg-brand/10 text-brand"}`}
      title={human ? "Requiere decisión humana" : "Ejecutado por el agente sin intervención"}
    >
      {human ? "◑" : "▶"} {label ?? (human ? "Decisión humana" : "Automático")}
    </span>
  );
}
