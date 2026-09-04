import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api";
import type { HitlGate, JourneyResources, JourneyRing, TaskDetail } from "../../types";
import { LaneTag, Priority, Risk } from "../../ui";
import { BlockerChip, JOURNEY_BAND_COLOR } from "./JourneyBoard";
import { DemoAdvanceControl, HitlCounter, HitlRail } from "../flow";
import { useDemo } from "../../demo";
import { useView } from "../../view";

const RING_STATUS_COLOR: Record<string, string> = {
  completed: "#22c55e",
  in_progress: "#0ea5e9",
  rolled_back: "#f97316",
  pending: "#475569",
};

const RESOURCE_SEGMENTS: { key: keyof JourneyResources; label: string; color: string }[] = [
  { key: "patched", label: "parcheados", color: "#22c55e" },
  { key: "failed", label: "fallidos", color: "#ef4444" },
  { key: "excluded", label: "excluidos", color: "#a855f7" },
  { key: "pending", label: "pendientes", color: "#475569" },
];

function ResourceProgress({ resources }: { resources: JourneyResources }) {
  const total = Math.max(1, resources.total);
  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span className="text-gray-400">Recursos afectados</span>
        <span className="font-mono font-bold text-gray-200">
          {resources.patched}/{resources.total} parcheados
        </span>
      </div>
      <div className="h-3 rounded bg-ink flex overflow-hidden">
        {RESOURCE_SEGMENTS.map(({ key, color }) => {
          const value = Number(resources[key] ?? 0);
          if (!value) return null;
          return <div key={key} style={{ width: `${(value / total) * 100}%`, background: color }} />;
        })}
      </div>
      <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-gray-400">
        {RESOURCE_SEGMENTS.map(({ key, label, color }) => (
          <span key={key} className="inline-flex items-center gap-1">
            <span className="w-2 h-2 rounded-sm" style={{ background: color }} />
            {Number(resources[key] ?? 0)} {label}
          </span>
        ))}
      </div>
    </div>
  );
}

function RingStrip({ rings }: { rings: JourneyRing[] }) {
  return (
    <div>
      <div className="text-xs text-gray-400 mb-1.5">Anillos de despliegue</div>
      <div className="flex gap-2">
        {rings.map((r) => {
          const color = RING_STATUS_COLOR[r.status] || "#475569";
          return (
            <div key={r.ring} className="flex-1 min-w-0" title={`${r.label} · ${r.status} · ${r.assets} activos`}>
              <div className="h-1.5 rounded" style={{ background: color }} />
              <div className="text-[11px] mt-1 leading-tight" style={{ color }}>{r.label}</div>
              <div className="text-[10px] text-gray-500">{r.assets} activos</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** Acción natural según lo que bloquea o toca hacer ahora en la tarea. */
function nextAction(blockers: string[], ringLabel: string | null): string {
  if (blockers.includes("awaiting_approval")) return `Aprobar ${ringLabel ?? "el anillo"}`;
  if (blockers.includes("job_failed")) return "Revisar la ejecución fallida";
  if (blockers.includes("job_unconfirmed")) return "Confirmar el estado del job";
  if (blockers.includes("rollback")) return "Revisar el rollback";
  return "Abrir la Remediation Task completa";
}

/** Vista detallada: el journey de una vulnerabilidad con las mismas 8 fases. */
export default function VulnJourneyPanel({ taskId, onClose }: { taskId: string; onClose: () => void }) {
  const [detail, setDetail] = useState<TaskDetail | null>(null);
  const { active: demo } = useDemo();
  const { role } = useView();

  useEffect(() => {
    let active = true;
    setDetail(null);
    api.task(taskId).then((d) => { if (active) setDetail(d); });
    return () => { active = false; };
  }, [taskId]);

  if (!detail) return <div className="card p-5 text-xs text-gray-500">Cargando journey…</div>;

  // Las verificaciones humanas y el avance de fase operan sobre el estado real
  // del backend: la respuesta ya trae el detalle actualizado.
  const verifyGate = (gate: HitlGate) =>
    api.verifyGate(taskId, gate.id, { ring: gate.ring, role }).then(setDetail);
  const advancePhase = () =>
    api.approve(taskId, detail.rings_done + 1).then(setDetail);
  const preapproveRing = (ring: number) =>
    api.preapproveRing(taskId, ring).then(setDetail);

  const j = detail.journey;
  const impact = detail.artifacts.impact;

  return (
    <div className="card p-5 space-y-4 xl:sticky xl:top-6">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="font-mono text-xs text-gray-400">{j.cve}</div>
          <div className="text-sm font-semibold text-gray-100 leading-snug">{j.title}</div>
          <div className="text-xs text-gray-500 mt-0.5">{j.ci_name}</div>
        </div>
        <button type="button" className="text-xs text-gray-500 hover:text-gray-300" onClick={onClose}>✕</button>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Risk score={j.risk_score} />
        <Priority p={j.priority} />
        <LaneTag lane={j.lane} />
        {j.blockers.map((b) => <BlockerChip key={b} id={b} />)}
      </div>

      <Link to={`/tasks/${j.task_id}`}
            className="btn btn-brand w-full justify-center text-xs">
        {nextAction(j.blockers, j.ring_label)} →
      </Link>

      <HitlCounter hitl={j.hitl} />

      {demo && (
        <DemoAdvanceControl detail={detail} onVerify={verifyGate} onAdvance={advancePhase}
                            onPreapprove={preapproveRing} />
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <ol className="space-y-1.5">
          {j.phases.map((p) => {
            const color = JOURNEY_BAND_COLOR[p.band];
            const done = p.status === "completed";
            const current = p.status === "current";
            return (
              <li key={p.id} className="flex items-start gap-2">
                <span
                  className="mt-0.5 w-4 h-4 shrink-0 rounded-full flex items-center justify-center text-[9px] font-bold"
                  style={{
                    background: done ? color : current ? color + "33" : "#1b1f27",
                    color: done ? "#0b0d11" : current ? color : "#64748b",
                    border: `1px solid ${done || current ? color : "#2b313d"}`,
                  }}
                >
                  {done ? "✓" : p.index}
                </span>
                <div className="min-w-0">
                  <div className={`text-xs leading-snug ${current ? "text-gray-100 font-semibold" : done ? "text-gray-300" : "text-gray-500"}`}>
                    {p.label}
                    {current && p.ring !== null && (
                      <span className="ml-2 text-[10px] text-gray-400">· {j.ring_label}</span>
                    )}
                  </div>
                  {current && <div className="text-[10px] text-gray-500">en curso</div>}
                  {p.gates_pending > 0 && (
                    <div className="text-[10px] text-amber-300">
                      ◑ {p.gates_pending === 1
                        ? "1 decisión humana pendiente"
                        : `${p.gates_pending} decisiones humanas pendientes`}
                    </div>
                  )}
                </div>
              </li>
            );
          })}
        </ol>

        <div className="space-y-4">
          <ResourceProgress resources={j.resources} />
          <RingStrip rings={j.rings} />
        </div>
      </div>

      <HitlRail gates={j.gates.filter((g) => g.status !== "upcoming")} onVerify={verifyGate} />

      <details className="group">
        <summary className="text-xs text-gray-400 cursor-pointer hover:text-gray-200 select-none">
          Contexto · blast radius, cambio, evidencias y rollback
        </summary>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 text-[11px] mt-3">
          <div className="rounded-lg bg-ink p-2.5">
            <div className="text-gray-500">Blast radius</div>
            <div className="text-gray-200 font-semibold mt-0.5">
              {impact.impacted_count} de {impact.affected_count} CIs
            </div>
            <div className="text-gray-500 mt-1 leading-snug">
              {impact.downtime_required ? "Con parada → se propaga a dependientes" : "Sin parada → no se propaga"}
            </div>
          </div>
          <div className="rounded-lg bg-ink p-2.5">
            <div className="text-gray-500">Cambio {j.change.number}</div>
            <div className="text-gray-200 font-semibold mt-0.5">{j.change.type}</div>
            <div className="text-gray-500 mt-1 leading-snug">{j.change.state}</div>
          </div>
          <div className="rounded-lg bg-ink p-2.5">
            <div className="text-gray-500">Evidencias</div>
            <div className="text-gray-200 font-semibold mt-0.5">{j.evidence.evidences_count}</div>
            <div className="text-gray-500 mt-1">{j.evidence.report_id}</div>
          </div>
          <div className="rounded-lg bg-ink p-2.5">
            <div className="text-gray-500">Rollback</div>
            <div className="text-gray-200 font-semibold mt-0.5">
              {j.rollback.triggered ? "Ejecutado" : j.rollback.status || "armado"}
            </div>
            <div className="text-gray-500 mt-1">
              {j.resources.rings_done}/{j.resources.rings_total} anillos
            </div>
          </div>
        </div>
      </details>
    </div>
  );
}
