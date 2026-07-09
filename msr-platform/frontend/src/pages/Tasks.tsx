import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import type { Task } from "../types";
import { PHASE_META, Priority, Track, Risk } from "../ui";

export default function Tasks() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [track, setTrack] = useState<string>("all");
  const [q, setQ] = useState("");
  const nav = useNavigate();

  useEffect(() => { api.tasks().then(setTasks); }, []);

  const filtered = useMemo(() => tasks.filter((t) =>
    (track === "all" || t.track === track) &&
    (q === "" || (t.cve + t.ci_name + t.title).toLowerCase().includes(q.toLowerCase()))
  ), [tasks, track, q]);

  return (
    <div className="p-6 space-y-4 max-w-[1400px]">
      <header>
        <div className="text-xs font-bold text-brand tracking-wider">SERVICENOW · VULNERABILITY RESPONSE</div>
        <h1 className="text-2xl font-extrabold mt-1">Remediation Tasks</h1>
        <p className="text-sm text-gray-400 mt-1">Cola priorizada por riesgo (técnico + negocio + operativo + SLA). Cada tarea recorre el ciclo de 6 fases.</p>
      </header>

      <div className="flex items-center gap-3">
        <input
          value={q} onChange={(e) => setQ(e.target.value)}
          placeholder="Buscar por CVE, activo…"
          className="bg-ink-soft border border-line rounded-lg px-3 py-2 text-sm w-72 outline-none focus:border-brand"
        />
        <div className="flex gap-1">
          {["all", "A", "B"].map((t) => (
            <button key={t} onClick={() => setTrack(t)}
              className={`btn text-xs ${track === t ? "btn-brand" : "btn-ghost"}`}>
              {t === "all" ? "Todos" : `Track ${t}`}
            </button>
          ))}
        </div>
        <span className="text-xs text-gray-500 ml-auto">{filtered.length} tareas</span>
      </div>

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-gray-500 border-b border-line bg-ink">
              <th className="px-4 py-2.5 font-medium">Riesgo</th>
              <th className="px-2 py-2.5 font-medium">CVE / Vulnerabilidad</th>
              <th className="px-2 py-2.5 font-medium">Activo afectado</th>
              <th className="px-2 py-2.5 font-medium">Track</th>
              <th className="px-2 py-2.5 font-medium">Impacto</th>
              <th className="px-2 py-2.5 font-medium">Fase actual</th>
              <th className="px-2 py-2.5 font-medium">Prioridad</th>
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
                <td className="px-2 py-3 text-xs text-gray-400">{t.sla_due.slice(0, 10)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
