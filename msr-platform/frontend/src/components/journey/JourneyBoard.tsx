import type { JourneyOverview, JourneyPhaseAggregate } from "../../types";
import { LANE_META } from "../../ui";

// Colores por banda del modelo: cualificación → planificación → ejecución y cierre.
export const JOURNEY_BAND_COLOR: Record<string, string> = {
  demand_risk: "#f59e0b",
  change_planning: "#a855f7",
  execution_closure: "#0ea5e9",
};

export const BLOCKER_META: Record<string, { label: string; cls: string }> = {
  awaiting_approval: { label: "pdte. aprobación", cls: "bg-amber-500/15 text-amber-300 border border-amber-500/30" },
  job_failed: { label: "ejecución fallida", cls: "bg-red-500/15 text-red-300 border border-red-500/40" },
  job_unconfirmed: { label: "estado sin confirmar", cls: "bg-orange-500/15 text-orange-300 border border-orange-500/40" },
  rollback: { label: "rollback", cls: "bg-orange-500/15 text-orange-300 border border-orange-500/40" },
  sla_overdue: { label: "SLA vencido", cls: "bg-red-500/15 text-red-300 border border-red-500/40" },
  sla_due_soon: { label: "SLA en riesgo", cls: "bg-amber-500/15 text-amber-300 border border-amber-500/30" },
};

export function BlockerChip({ id, count }: { id: string; count?: number }) {
  const meta = BLOCKER_META[id] || { label: id, cls: "chip border border-line text-gray-300" };
  return (
    <span className={`chip ${meta.cls}`}>
      {count === undefined ? meta.label : `${count} ${meta.label}`}
    </span>
  );
}

function PhaseCard({ phase, selected, onSelect }: {
  phase: JourneyPhaseAggregate; selected: boolean; onSelect: () => void;
}) {
  const color = JOURNEY_BAND_COLOR[phase.band];
  const empty = phase.count === 0;
  const lanes = (["critical", "accelerated", "standard"] as const)
    .map((lane) => ({ lane, n: phase.by_lane[lane] || 0 }))
    .filter((l) => l.n > 0);
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      title={`${phase.label_en} · ${phase.count} vulnerabilidad(es)`}
      className={`text-left rounded-lg border p-3 transition-colors w-full h-full ${
        selected ? "bg-ink-panel" : "bg-ink hover:bg-ink-panel"}`}
      style={{ borderColor: selected ? color : "#2b313d" }}
    >
      <div className="flex items-center gap-2">
        <span className="font-mono text-[10px] px-1.5 py-0.5 rounded"
              style={{ background: color + "22", color }}>{phase.index}</span>
        {phase.per_ring && (
          <span className="text-[10px] text-gray-500" title="Se repite en cada anillo de despliegue">× anillo</span>
        )}
        {phase.gates.length > 0 && (
          <span
            className={`ml-auto text-[10px] ${phase.gates_pending > 0 ? "text-amber-300" : "text-gray-600"}`}
            title={phase.gates.map((g) => g.label).join(" · ")}
          >
            ◑ {phase.gates_pending > 0 ? `${phase.gates_pending} pdte.` : "HITL"}
          </span>
        )}
      </div>
      <div className="text-xs font-semibold text-gray-200 mt-2 leading-snug">{phase.label}</div>
      <div className="text-[10px] text-gray-500 leading-snug">{phase.label_en}</div>
      <div className="mt-2 flex items-baseline gap-1.5">
        <span className="text-2xl font-extrabold" style={{ color: empty ? "#475569" : color }}>{phase.count}</span>
        <span className="text-[10px] text-gray-500">vuln.</span>
      </div>
      <div className="mt-2 flex flex-wrap gap-1">
        {lanes.map(({ lane, n }) => (
          <span key={lane} className="inline-flex items-center gap-1 text-[10px] text-gray-400">
            <span className="w-2 h-2 rounded-full" style={{ background: LANE_META[lane].dot }} />
            {n}
          </span>
        ))}
        {phase.rings.length > 0 && (
          <span className="text-[10px] text-gray-500">· anillo {phase.rings.join(", ")}</span>
        )}
      </div>
      {Object.keys(phase.blockers).length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {Object.entries(phase.blockers).map(([id, n]) => <BlockerChip key={id} id={id} count={n} />)}
        </div>
      )}
    </button>
  );
}

/** Vista global: las 8 fases del journey agrupadas en sus 3 bandas. */
export default function JourneyBoard({ journey, selected, onSelect }: {
  journey: JourneyOverview;
  selected: string | null;
  onSelect: (phaseId: string | null) => void;
}) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-[repeat(8,minmax(0,1fr))] gap-3">
      {journey.bands.map((band) => {
        const phases = journey.phases.filter((p) => p.band === band.id);
        return (
          <div key={band.id} className="rounded-xl border border-line p-2"
               style={{ gridColumn: `span ${phases.length}` }}>
            <div className="text-[10px] font-semibold tracking-wider mb-2 px-1"
                 style={{ color: JOURNEY_BAND_COLOR[band.id] }}>
              {band.label.toUpperCase()}
            </div>
            <div className="grid gap-2" style={{ gridTemplateColumns: `repeat(${phases.length}, minmax(0, 1fr))` }}>
              {phases.map((p) => (
                <PhaseCard
                  key={p.id}
                  phase={p}
                  selected={selected === p.id}
                  onSelect={() => onSelect(selected === p.id ? null : p.id)}
                />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
