import { useEffect, useState } from "react";
import { api } from "../api";
import type { TestCase } from "../types";

const LAYER_COLOR: Record<string, string> = {
  os: "#f59e0b", database: "#0ea5e9", middleware: "#ec4899", runtime: "#14b8a6",
  application: "#22c55e", external: "#a855f7",
};

export default function Catalog() {
  const [rows, setRows] = useState<TestCase[]>([]);
  useEffect(() => { api.catalog().then(setRows); }, []);

  const layers = [...new Set(rows.map((r) => r.layer))];

  return (
    <div className="p-6 space-y-5 max-w-[1200px]">
      <header>
        <div className="text-xs font-bold text-brand tracking-wider">TEST CATALOGUE · VERSIONED IN GIT</div>
        <h1 className="text-2xl font-extrabold mt-1">Library of reusable tests</h1>
        <p className="text-sm text-gray-400 mt-1">Deterministic test profiles by layer. Devin picks the Minimum Viable Test Plan from here based on the Impact Graph.</p>
      </header>

      {layers.map((layer) => (
        <div key={layer} className="card overflow-hidden">
          <div className="px-4 py-2.5 border-b border-line flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-sm" style={{ background: LAYER_COLOR[layer] }} />
            <span className="text-sm font-semibold capitalize">{layer}</span>
            <span className="text-xs text-gray-500">{rows.filter((r) => r.layer === layer).length} tests</span>
          </div>
          <table className="w-full text-sm">
            <tbody>
              {rows.filter((r) => r.layer === layer).map((t) => (
                <tr key={t.id} className="border-b border-line/40 last:border-0">
                  <td className="px-4 py-2 font-mono text-xs text-gray-500 w-28">{t.id}</td>
                  <td className="px-2 py-2 text-gray-200">{t.name}</td>
                  <td className="px-2 py-2"><span className="chip bg-ink-panel text-gray-400">{t.tool}</span></td>
                  <td className="px-2 py-2 text-xs text-gray-500">type: {t.remediation_type}</td>
                  <td className="px-2 py-2 text-xs text-gray-500">crit: {t.criticality}</td>
                  <td className="px-2 py-2 text-xs text-gray-500">evidence: {t.evidence}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  );
}
