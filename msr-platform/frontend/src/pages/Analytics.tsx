import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Cell, PieChart, Pie,
} from "recharts";
import { api } from "../api";
import type { Overview } from "../types";
import { PHASE_META, Track, TRACK_META, LANE_META, LaneTag } from "../ui";

const CRIT_COLOR: Record<string, string> = { critical: "#ef4444", high: "#f97316", medium: "#f59e0b", low: "#0ea5e9" };
const PRI_COLOR: Record<string, string> = CRIT_COLOR;
const PHASE_ORDER = ["detection", "prioritization", "pre_implementation", "lab_testing", "prototype", "deployment"];

/** Vista secundaria: el análisis que no necesita estar en el centro de mando. */
export default function Analytics() {
  const [ov, setOv] = useState<Overview | null>(null);
  const nav = useNavigate();

  useEffect(() => { api.overview().then(setOv); }, []);

  if (!ov) return <div className="p-8 text-gray-500">Loading…</div>;

  const funnelMax = ov.funnel[0].value;
  const phaseData = PHASE_ORDER.map((p) => ({ name: PHASE_META[p].label, value: ov.by_phase[p] || 0, color: PHASE_META[p].color }));
  const priData = Object.entries(ov.by_priority).map(([k, v]) => ({ name: k, value: v }));

  return (
    <div className="p-6 space-y-6 max-w-[1400px]">
      <header>
        <div className="text-xs font-bold text-brand tracking-wider">PROGRAMME ANALYTICS</div>
        <h1 className="text-2xl font-extrabold mt-1">Prioritisation, distribution and capacity</h1>
        <p className="text-sm text-gray-400 mt-1">
          Aggregate context of the patching programme. Day-to-day operational status lives in the{" "}
          <button type="button" className="text-brand font-semibold" onClick={() => nav("/dashboard")}>
            command centre →
          </button>
        </p>
      </header>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <div className="card p-5">
          <div className="text-sm font-semibold mb-1">Risk-based prioritisation</div>
          <div className="text-xs text-gray-500 mb-4">From noise to actionable signal (context + exploitability + impact)</div>
          <div className="space-y-2">
            {ov.funnel.map((f, i) => {
              const pct = Math.max(6, (f.value / funnelMax) * 100);
              const colors = ["#334155", "#475569", "#f59e0b", "#f97316", "#86BC25"];
              return (
                <div key={f.label}>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-gray-300">{f.label}</span>
                    <span className="font-mono font-bold" style={{ color: colors[i] }}>{f.value.toLocaleString()}</span>
                  </div>
                  <div className="h-6 rounded-md bg-ink">
                    <div className="h-6 rounded-md" style={{ width: `${pct}%`, background: colors[i] }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="card p-5">
          <div className="text-sm font-semibold mb-1">Tasks by cycle phase</div>
          <div className="text-xs text-gray-500 mb-3">Remediation pipeline (6 phases with HITL approval)</div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={phaseData} margin={{ left: -20 }}>
              <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 11 }} interval={0} angle={-15} textAnchor="end" height={50} />
              <YAxis allowDecimals={false} tick={{ fill: "#94a3b8", fontSize: 11 }} />
              <Tooltip contentStyle={{ background: "#1b1f27", border: "1px solid #2b313d", borderRadius: 8, fontSize: 12 }} />
              <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                {phaseData.map((e) => <Cell key={e.name} fill={e.color} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card p-5">
          <div className="text-sm font-semibold mb-1">Task priority</div>
          <div className="text-xs text-gray-500 mb-3">Contextual risk (not just CVSS)</div>
          <div className="flex items-center gap-4">
            <ResponsiveContainer width="55%" height={180}>
              <PieChart>
                <Pie data={priData} dataKey="value" nameKey="name" innerRadius={40} outerRadius={70} paddingAngle={3}>
                  {priData.map((e) => <Cell key={e.name} fill={PRI_COLOR[e.name]} />)}
                </Pie>
                <Tooltip contentStyle={{ background: "#1b1f27", border: "1px solid #2b313d", borderRadius: 8, fontSize: 12 }} />
              </PieChart>
            </ResponsiveContainer>
            <div className="space-y-2 text-sm">
              {priData.map((p) => (
                <div key={p.name} className="flex items-center gap-2">
                  <span className="w-3 h-3 rounded-sm" style={{ background: PRI_COLOR[p.name] }} />
                  <span className="capitalize text-gray-300">{p.name}</span>
                  <span className="font-mono font-bold ml-auto">{p.value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <div className="card p-5 xl:col-span-2">
          <div className="text-sm font-semibold mb-1">3 operational lanes (speed / risk)</div>
          <div className="text-xs text-gray-500 mb-4">
            AI triage assigns every vulnerability to a lane based on KEV/EPSS, exposure and criticality ·
            each lane has its own SLA and automation level
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {(["critical", "accelerated", "standard"] as const).map((k) => {
              const meta = ov.lanes[k];
              const total = ov.kpis.remediation_tasks || 1;
              const n = ov.by_lane[k] || 0;
              return (
                <button key={k} type="button" onClick={() => nav(`/tasks?lane=${k}`)}
                        className="rounded-lg border p-3 text-left hover:bg-ink-panel"
                        style={{ borderColor: LANE_META[k].dot + "55" }}>
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full" style={{ background: LANE_META[k].dot }} />
                    <LaneTag lane={k} />
                  </div>
                  <div className="mt-3 flex items-baseline gap-2">
                    <span className="text-2xl font-extrabold" style={{ color: LANE_META[k].dot }}>{n}</span>
                    <span className="text-xs text-gray-500">tasks ({Math.round((n / total) * 100)}%)</span>
                  </div>
                  <div className="text-[11px] text-gray-400 mt-2 leading-snug">{meta.sla}</div>
                  <div className="text-[11px] text-gray-500 mt-1 leading-snug">{meta.automation}</div>
                </button>
              );
            })}
          </div>
          <div className="mt-4 pt-3 border-t border-line">
            <div className="text-[11px] text-gray-500 mb-2">
              Technical dimension (defines the executor and the rollback) · CI distribution across the CMDB
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
              {(["A", "B", "C"] as const).map((k) => {
                const cis = ov.cmdb.by_track[k] || 0;
                const cisPct = Math.round((cis / ov.cmdb.total) * 100);
                return (
                  <div key={k} className="rounded-lg bg-ink p-2.5">
                    <Track t={k} />
                    <div className="text-[11px] text-gray-400 mt-1.5">
                      <span className="font-mono font-bold text-gray-200">{cis.toLocaleString()}</span> CIs ({cisPct}%)
                    </div>
                    <div className="text-[11px] text-gray-500 mt-0.5">{TRACK_META[k].exec}</div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        <div className="card p-5">
          <div className="text-sm font-semibold mb-1">Task criticality</div>
          <div className="text-xs text-gray-500 mb-4">Business tier (CSDM)</div>
          <div className="space-y-2">
            {(["critical", "high", "medium", "low"] as const).map((c) => {
              const v = ov.by_criticality[c] || 0;
              const max = Math.max(1, ...Object.values(ov.by_criticality));
              return (
                <div key={c}>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="capitalize text-gray-300">{c}</span>
                    <span className="font-mono font-bold" style={{ color: CRIT_COLOR[c] }}>{v}</span>
                  </div>
                  <div className="h-2.5 rounded bg-ink">
                    <div className="h-2.5 rounded" style={{ width: `${Math.max(4, (v / max) * 100)}%`, background: CRIT_COLOR[c] }} />
                  </div>
                </div>
              );
            })}
          </div>
          <div className="mt-5 pt-4 border-t border-line">
            <div className="flex items-center justify-between mb-1">
              <div className="text-sm font-semibold">Standardised CMDB</div>
              <button className="text-xs text-brand font-semibold" onClick={() => nav("/cmdb")}>View the CMDB →</button>
            </div>
            <div className="text-xs text-gray-500">
              Source: <span className="text-gray-300">{ov.cmdb.source}</span> ·{" "}
              <b className="text-gray-200">{ov.cmdb.total.toLocaleString()}</b> CIs · {ov.cmdb.edges.toLocaleString()} relationships
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
