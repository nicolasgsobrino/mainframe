import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api";
import type { Task } from "../types";
import { PHASE_META, Priority, Track, Risk, LaneTag, LANE_META, SlaTag } from "../ui";

const LANE_KEYS = ["all", "critical", "accelerated", "standard"] as const;

/** Filtros de drill-down: los KPIs del Overview enlazan aquí con estos parámetros. */
const FILTER_LABELS: Record<string, Record<string, string>> = {
  status: { in_flight: "In flight", remediated: "Remediated" },
  sla: { overdue: "SLA breached", due_soon: "SLA at risk" },
  kev: { "1": "KEV (exploited)" },
};

function matchesStatus(task: Task, status: string | null) {
  if (status === "remediated") return task.status === "remediated";
  if (status === "in_flight") return task.status !== "remediated";
  return true;
}

function matchesSla(task: Task, sla: string | null) {
  if (sla === "overdue") return Boolean(task.sla?.overdue);
  if (sla === "due_soon") return Boolean(task.sla?.due_soon);
  return true;
}

export default function Tasks() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [params, setParams] = useSearchParams();
  const nav = useNavigate();

  const lane = params.get("lane") ?? "all";
  const q = params.get("q") ?? "";
  const status = params.get("status");
  const sla = params.get("sla");
  const kev = params.get("kev") === "1";

  const setFilter = (key: string, value: string | null) => {
    const updated = new URLSearchParams(params);
    if (value && value !== "all") updated.set(key, value);
    else updated.delete(key);
    setParams(updated, { replace: true });
  };

  useEffect(() => { api.tasks().then(setTasks); }, []);

  const filtered = useMemo(() => tasks.filter((t) =>
    (lane === "all" || t.lane === lane) &&
    matchesStatus(t, status) && matchesSla(t, sla) && (!kev || t.kev) &&
    (q === "" || (t.cve + t.ci_name + t.title).toLowerCase().includes(q.toLowerCase()))
  ), [tasks, lane, q, status, sla, kev]);

  const chips = (["status", "sla", "kev"] as const)
    .map((key) => ({ key, value: params.get(key) ?? "" }))
    .filter((f) => f.value !== "");

  return (
    <div className="p-6 space-y-4 max-w-[1400px]">
      <header>
        <div className="text-xs font-bold text-brand tracking-wider">SERVICENOW · VULNERABILITY RESPONSE</div>
        <h1 className="text-2xl font-extrabold mt-1">Remediation Tasks</h1>
        <p className="text-sm text-gray-400 mt-1">Queue prioritised by risk (technical + business + operational + SLA). Every task runs through the 6-phase cycle.</p>
      </header>

      <div className="flex items-center gap-3">
        <input
          value={q} onChange={(e) => setFilter("q", e.target.value)}
          placeholder="Search by CVE, asset…"
          className="bg-ink-soft border border-line rounded-lg px-3 py-2 text-sm w-72 outline-none focus:border-brand"
        />
        <div className="flex gap-1">
          {LANE_KEYS.map((t) => (
            <button key={t} onClick={() => setFilter("lane", t)}
              className={`btn text-xs ${lane === t ? "btn-brand" : "btn-ghost"}`}>
              {t === "all" ? "All" : `${LANE_META[t].label} lane`}
            </button>
          ))}
        </div>
        <span className="text-xs text-gray-500 ml-auto">{filtered.length} tasks</span>
      </div>

      {chips.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="text-gray-500">Filters:</span>
          {chips.map((f) => (
            <button key={f.key} type="button" onClick={() => setFilter(f.key, null)}
              className="chip border border-brand/40 bg-brand/10 text-brand">
              {FILTER_LABELS[f.key]?.[f.value] ?? f.value} ✕
            </button>
          ))}
        </div>
      )}

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-gray-500 border-b border-line bg-ink">
              <th className="px-4 py-2.5 font-medium">Risk</th>
              <th className="px-2 py-2.5 font-medium">CVE / Vulnerability</th>
              <th className="px-2 py-2.5 font-medium">Affected asset</th>
              <th className="px-2 py-2.5 font-medium">Lane</th>
              <th className="px-2 py-2.5 font-medium">Domain</th>
              <th className="px-2 py-2.5 font-medium">Impact</th>
              <th className="px-2 py-2.5 font-medium">Current phase</th>
              <th className="px-2 py-2.5 font-medium">Priority</th>
              <th className="px-2 py-2.5 font-medium">SLA</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((t) => (
              <tr key={t.id} className="border-b border-line/40 hover:bg-ink-panel cursor-pointer" onClick={() => nav(`/tasks/${t.id}`)}>
                <td className="px-4 py-3"><Risk score={t.risk_score} /></td>
                <td className="px-2 py-3">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs text-gray-300">{t.cve}</span>
                    {t.status === "remediated" && <span className="chip bg-green-500/15 text-green-400">fixed</span>}
                  </div>
                  <div className="text-xs text-gray-500 truncate max-w-[240px]">{t.title}</div>
                </td>
                <td className="px-2 py-3">
                  <div className="text-gray-200">{t.ci_name}</div>
                  <div className="text-xs text-gray-500">{t.environment} · {t.criticality}</div>
                </td>
                <td className="px-2 py-3"><LaneTag lane={t.lane} /></td>
                <td className="px-2 py-3"><Track t={t.track} /></td>
                <td className="px-2 py-3 text-gray-400 text-xs">{t.affected_count} CIs</td>
                <td className="px-2 py-3">
                  <div className="flex items-center gap-1.5">
                    <span className="chip" style={{ background: PHASE_META[t.phase].color + "22", color: PHASE_META[t.phase].color }}>
                      {t.phase_index + 1}/6 · {t.phase_label}
                    </span>
                  </div>
                </td>
                <td className="px-2 py-3"><Priority p={t.priority} /></td>
                <td className="px-2 py-3">
                  <SlaTag sla={t.sla} />
                  <div className="text-[10px] text-gray-500 mt-0.5">due {t.sla_due.slice(0, 10)}</div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
