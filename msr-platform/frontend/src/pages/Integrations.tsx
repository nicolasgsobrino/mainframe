import { useEffect, useState } from "react";
import { api } from "../api";
import type { Service } from "../types";
import { StatusDot } from "../ui";

const TYPE_META: Record<string, { label: string; color: string }> = {
  control: { label: "Control plane (ServiceNow)", color: "#0ea5e9" },
  agent: { label: "Agent layer (Devin)", color: "#86BC25" },
  source: { label: "Vulnerability sources", color: "#f59e0b" },
  executor: { label: "Technical execution", color: "#a855f7" },
};

export default function Integrations() {
  const [svc, setSvc] = useState<Service[]>([]);
  useEffect(() => { api.services().then(setSvc); }, []);

  const groups = ["control", "agent", "source", "executor"];

  return (
    <div className="p-6 space-y-5 max-w-[1200px]">
      <header>
        <div className="text-xs font-bold text-brand tracking-wider">INTEGRATION ARCHITECTURE</div>
        <h1 className="text-2xl font-extrabold mt-1">Integrations and data flow</h1>
        <p className="text-sm text-gray-400 mt-1">Three-layer model: ServiceNow governs, Devin reasons/executes, the customer's tools deploy. Connected via Flow Designer → Devin API → Table API.</p>
      </header>

      {/* flow diagram */}
      <div className="card p-5">
        <div className="flex items-center justify-between gap-2 flex-wrap">
          {[
            ["Scanners", "#f59e0b", "Qualys · Tenable · Snyk"],
            ["ServiceNow", "#0ea5e9", "VR · CMDB · Change"],
            ["Devin API", "#86BC25", "Session with context"],
            ["Executors", "#a855f7", "Ansible · CI/CD · IaC"],
            ["Table API", "#0ea5e9", "MVT · results · evidence"],
          ].map(([l, c, s], i, arr) => (
            <div key={l as string} className="flex items-center gap-2 flex-1 min-w-[150px]">
              <div className="flex-1 rounded-lg border p-3 text-center" style={{ borderColor: c as string, background: (c as string) + "12" }}>
                <div className="text-sm font-bold" style={{ color: c as string }}>{l}</div>
                <div className="text-[11px] text-gray-400 mt-1">{s}</div>
              </div>
              {i < arr.length - 1 && <span className="text-gray-600 text-lg">→</span>}
            </div>
          ))}
        </div>
        <div className="text-xs text-gray-500 mt-3 text-center">Human-in-the-loop mandatory at every phase transition · one Devin playbook per phase</div>
      </div>

      {groups.map((g) => (
        <div key={g}>
          <div className="text-sm font-semibold mb-2" style={{ color: TYPE_META[g].color }}>{TYPE_META[g].label}</div>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {svc.filter((s) => s.type === g).map((s) => (
              <div key={s.name} className="card p-4">
                <div className="flex items-center gap-2">
                  <StatusDot status={s.status} />
                  <div className="text-sm font-semibold text-gray-100">{s.name}</div>
                </div>
                <div className="text-xs text-gray-500 mt-1">{s.role}</div>
                <div className="text-xs text-gray-400 mt-2">{s.detail}</div>
                <div className="text-[11px] mt-2 uppercase tracking-wide" style={{ color: s.status === "active" ? "#86BC25" : "#22c55e" }}>{s.status}</div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
