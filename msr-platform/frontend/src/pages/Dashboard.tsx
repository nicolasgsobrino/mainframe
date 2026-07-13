import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Cell, PieChart, Pie,
} from "recharts";
import { api } from "../api";
import type { Overview, Task, LogEntry } from "../types";
import { PHASE_META, Priority, Track, Risk, TRACK_META } from "../ui";

const CRIT_COLOR: Record<string, string> = { critical: "#ef4444", high: "#f97316", medium: "#f59e0b", low: "#0ea5e9" };

function Kpi({ label, value, accent }: { label: string; value: string | number; accent?: string }) {
  return (
    <div className="card p-4">
      <div className="text-2xl font-extrabold" style={{ color: accent }}>{value}</div>
      <div className="text-xs text-gray-400 mt-1">{label}</div>
    </div>
  );
}

const PHASE_ORDER = ["detection", "prioritization", "pre_implementation", "lab_testing", "prototype", "deployment"];

export default function Dashboard() {
  const [ov, setOv] = useState<Overview | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [activity, setActivity] = useState<LogEntry[]>([]);
  const nav = useNavigate();

  useEffect(() => {
    api.overview().then(setOv);
    api.tasks().then(setTasks);
    api.activity().then(setActivity);
  }, []);

  if (!ov) return <div className="p-8 text-gray-500">Cargando…</div>;

  const funnelMax = ov.funnel[0].value;
  const phaseData = PHASE_ORDER.map((p) => ({ name: PHASE_META[p].label, value: ov.by_phase[p] || 0, color: PHASE_META[p].color }));
  const priData = Object.entries(ov.by_priority).map(([k, v]) => ({ name: k, value: v }));
  const PRI_COLOR: Record<string, string> = { critical: "#ef4444", high: "#f97316", medium: "#f59e0b", low: "#0ea5e9" };

  return (
    <div className="p-6 space-y-6 max-w-[1400px]">
      <header>
        <div className="text-xs font-bold text-brand tracking-wider">MACHINE SPEED REMEDIATION · CENTRO DE MANDO</div>
        <h1 className="text-2xl font-extrabold mt-1">Gestión de vulnerabilidades impulsada por IA</h1>
        <p className="text-sm text-gray-400 mt-1">
          ServiceNow gobierna el ciclo · <span className="text-brand font-semibold">Devin</span> ejecuta el trabajo técnico de cada fase · 3 carriles (infra · aplicación · contenedores) sobre CMDB estandarizada.
        </p>
      </header>

      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-7 gap-3">
        <Kpi label="Hallazgos abiertos" value={ov.kpis.open_findings.toLocaleString()} />
        <Kpi label="Vulnerable Items" value={ov.kpis.vulnerable_items} />
        <Kpi label="Remediation Tasks" value={ov.kpis.remediation_tasks} accent="#86BC25" />
        <Kpi label="KEV (explotadas)" value={ov.kpis.kev_count} accent="#ef4444" />
        <Kpi label="En curso" value={ov.kpis.in_flight} accent="#0ea5e9" />
        <Kpi label="Remediadas" value={ov.kpis.remediated} accent="#22c55e" />
        <Kpi label="CIs en CMDB" value={ov.kpis.cis} />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Funnel */}
        <div className="card p-5 xl:col-span-1">
          <div className="text-sm font-semibold mb-1">Priorización basada en riesgo</div>
          <div className="text-xs text-gray-500 mb-4">De ruido a señal accionable (contexto + explotabilidad + impacto)</div>
          <div className="space-y-2">
            {ov.funnel.map((f, i) => {
              const pct = Math.max(6, (f.value / funnelMax) * 100);
              const colors = ["#334155", "#475569", "#f59e0b", "#f97316", "#86BC25"];
              return (
                <div key={i}>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-gray-300">{f.label}</span>
                    <span className="font-mono font-bold" style={{ color: colors[i] }}>{f.value.toLocaleString()}</span>
                  </div>
                  <div className="h-6 rounded-md bg-ink" >
                    <div className="h-6 rounded-md flex items-center justify-end pr-2" style={{ width: `${pct}%`, background: colors[i] }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Phase distribution */}
        <div className="card p-5">
          <div className="text-sm font-semibold mb-1">Tareas por fase del ciclo</div>
          <div className="text-xs text-gray-500 mb-3">Pipeline de remediación (6 fases)</div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={phaseData} margin={{ left: -20 }}>
              <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 11 }} interval={0} angle={-15} textAnchor="end" height={50} />
              <YAxis allowDecimals={false} tick={{ fill: "#94a3b8", fontSize: 11 }} />
              <Tooltip contentStyle={{ background: "#1b1f27", border: "1px solid #2b313d", borderRadius: 8, fontSize: 12 }} />
              <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                {phaseData.map((e, i) => <Cell key={i} fill={e.color} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Priority */}
        <div className="card p-5">
          <div className="text-sm font-semibold mb-1">Prioridad de las tareas</div>
          <div className="text-xs text-gray-500 mb-3">Riesgo contextual (no solo CVSS)</div>
          <div className="flex items-center gap-4">
            <ResponsiveContainer width="55%" height={180}>
              <PieChart>
                <Pie data={priData} dataKey="value" nameKey="name" innerRadius={40} outerRadius={70} paddingAngle={3}>
                  {priData.map((e, i) => <Cell key={i} fill={PRI_COLOR[e.name]} />)}
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

      {/* 3 carriles + criticidad + despliegue/rollback */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* 3 carriles */}
        <div className="card p-5 xl:col-span-2">
          <div className="text-sm font-semibold mb-1">3 carriles de remediación</div>
          <div className="text-xs text-gray-500 mb-4">Cada carril tiene su ejecución y su rollback · reparto de CIs desde la CMDB estandarizada</div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {(["A", "B", "C"] as const).map((k) => {
              const cis = ov.cmdb.by_track[k] || 0;
              const cisPct = Math.round((cis / ov.cmdb.total) * 100);
              return (
                <div key={k} className="rounded-lg border border-line p-3">
                  <Track t={k} />
                  <div className="text-xs text-gray-400 mt-2 leading-snug">{TRACK_META[k].label.split("· ")[1]}</div>
                  <div className="mt-3 flex items-baseline gap-2">
                    <span className="text-2xl font-extrabold">{ov.by_track[k] || 0}</span>
                    <span className="text-xs text-gray-500">tareas</span>
                  </div>
                  <div className="mt-2 text-xs text-gray-400">
                    <span className="font-mono font-bold text-gray-200">{cis.toLocaleString()}</span> CIs ({cisPct}%)
                  </div>
                  <div className="text-[11px] text-gray-500 mt-1">
                    {k === "A" ? "SCCM · BigFix · Ansible" : k === "B" ? "CI/CD (GitHub Actions)" : "Argo CD · Helm · Registry"}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Despliegue y rollback */}
        <div className="card p-5">
          <div className="text-sm font-semibold mb-1">Despliegue & Rollback</div>
          <div className="text-xs text-gray-500 mb-4">Ejecución por anillos con evidencia y reversión</div>
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-lg bg-ink p-3">
              <div className="text-2xl font-extrabold text-sky-400">{ov.deployment.in_deployment}</div>
              <div className="text-[11px] text-gray-400 mt-1">En despliegue</div>
            </div>
            <div className="rounded-lg bg-ink p-3">
              <div className="text-2xl font-extrabold text-emerald-400">{ov.deployment.rings_deployed}</div>
              <div className="text-[11px] text-gray-400 mt-1">Anillos desplegados</div>
            </div>
            <div className="rounded-lg bg-ink p-3">
              <div className="text-2xl font-extrabold" style={{ color: ov.deployment.rollbacks ? "#f97316" : "#64748b" }}>{ov.deployment.rollbacks}</div>
              <div className="text-[11px] text-gray-400 mt-1">Rollbacks ejecutados</div>
            </div>
            <div className="rounded-lg bg-ink p-3">
              <div className="text-2xl font-extrabold text-brand">{ov.kpis.remediated}</div>
              <div className="text-[11px] text-gray-400 mt-1">Remediadas</div>
            </div>
          </div>
          <div className="mt-3 text-[11px] text-gray-500 leading-snug">
            Rollback armado y probado en lab desde el inicio; disparo manual (owner) o automático por fallo de post-checks.
          </div>
        </div>
      </div>

      {/* Criticidad + CMDB estandarizada */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <div className="card p-5">
          <div className="text-sm font-semibold mb-1">Criticidad de las tareas</div>
          <div className="text-xs text-gray-500 mb-4">Tier de negocio (CSDM)</div>
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
        </div>

        <div className="card p-5 xl:col-span-2">
          <div className="flex items-center justify-between mb-1">
            <div className="text-sm font-semibold">CMDB estandarizada</div>
            <button className="text-xs text-brand font-semibold" onClick={() => nav("/cmdb")}>Ver CMDB →</button>
          </div>
          <div className="text-xs text-gray-500 mb-4">
            Fuente: <span className="text-gray-300">{ov.cmdb.source}</span> · <b className="text-gray-200">{ov.cmdb.total.toLocaleString()}</b> CIs · {ov.cmdb.edges.toLocaleString()} relaciones
          </div>
          <div className="flex flex-wrap gap-2">
            {Object.entries(ov.cmdb.by_class).sort((a, b) => b[1] - a[1]).map(([k, v]) => (
              <div key={k} className="chip border border-line text-gray-300">
                {k.replace("_", " ")}: <b className="ml-1 text-gray-100">{v.toLocaleString()}</b>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Top tasks */}
        <div className="card xl:col-span-2 overflow-hidden">
          <div className="px-4 py-3 border-b border-line flex items-center justify-between">
            <div className="text-sm font-semibold">Remediation Tasks prioritarias</div>
            <button className="text-xs text-brand font-semibold" onClick={() => nav("/tasks")}>Ver todas →</button>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-500 border-b border-line">
                <th className="px-4 py-2 font-medium">Riesgo</th>
                <th className="px-2 py-2 font-medium">CVE</th>
                <th className="px-2 py-2 font-medium">Activo</th>
                <th className="px-2 py-2 font-medium">Track</th>
                <th className="px-2 py-2 font-medium">Fase</th>
                <th className="px-2 py-2 font-medium">Prioridad</th>
              </tr>
            </thead>
            <tbody>
              {tasks.slice(0, 7).map((t) => (
                <tr key={t.id} className="border-b border-line/50 hover:bg-ink-panel cursor-pointer" onClick={() => nav(`/tasks/${t.id}`)}>
                  <td className="px-4 py-2.5"><Risk score={t.risk_score} /></td>
                  <td className="px-2 py-2.5 font-mono text-xs text-gray-300">{t.cve}</td>
                  <td className="px-2 py-2.5 text-gray-300">{t.ci_name}</td>
                  <td className="px-2 py-2.5"><Track t={t.track} /></td>
                  <td className="px-2 py-2.5">
                    <span className="chip" style={{ background: PHASE_META[t.phase].color + "22", color: PHASE_META[t.phase].color }}>
                      {t.phase_label}
                    </span>
                  </td>
                  <td className="px-2 py-2.5"><Priority p={t.priority} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Activity feed */}
        <div className="card overflow-hidden flex flex-col">
          <div className="px-4 py-3 border-b border-line flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-brand animate-pulse" />
            <div className="text-sm font-semibold">Actividad del agente</div>
          </div>
          <div className="p-3 space-y-2 overflow-y-auto max-h-[340px]">
            {activity.slice(0, 16).map((a, i) => (
              <div key={i} className="text-xs flex gap-2">
                <span className={`chip shrink-0 ${a.actor === "Devin" ? "bg-brand/15 text-brand" : a.actor.includes("HITL") || a.actor.includes("Owner") ? "bg-amber-500/15 text-amber-300" : "bg-sky-500/15 text-sky-300"}`}>
                  {a.actor}
                </span>
                <span className="text-gray-400 leading-relaxed">{a.msg}</span>
              </div>
            ))}
            {activity.length === 0 && <div className="text-xs text-gray-600">Sin actividad todavía. Aprueba una fase en una tarea para ver al agente trabajar.</div>}
          </div>
        </div>
      </div>
    </div>
  );
}
