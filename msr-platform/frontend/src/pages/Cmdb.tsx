import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { CI, Edge } from "../types";
import { CI_CLASS_META } from "../ui";
import ImpactGraphView from "../components/ImpactGraphView";

export default function Cmdb() {
  const [cis, setCis] = useState<CI[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [svc, setSvc] = useState<string>("");
  const [cls, setCls] = useState<string>("all");

  useEffect(() => {
    api.cmdb().then((r) => {
      setCis(r.cis); setEdges(r.edges);
      const bs = r.cis.find((c) => c.ci_class === "business_service");
      if (bs) setSvc(bs.id);
    });
  }, []);

  const services = cis.filter((c) => c.ci_class === "business_service");

  // subgrafo del servicio seleccionado
  const sub = useMemo(() => {
    if (!svc) return { nodes: [], edges: [] };
    const byId = Object.fromEntries(cis.map((c) => [c.id, c]));
    const seen = new Set<string>([svc]);
    let frontier = [svc];
    for (let d = 0; d < 4 && frontier.length; d++) {
      const nxt: string[] = [];
      for (const id of frontier)
        for (const e of edges) {
          if (e.source === id && !seen.has(e.target)) { seen.add(e.target); nxt.push(e.target); }
          if (e.target === id && !seen.has(e.source)) { seen.add(e.source); nxt.push(e.source); }
        }
      frontier = nxt;
    }
    const nodes = [...seen].map((id) => ({ ...byId[id], is_root: id === svc } as any)).filter((n) => n.id);
    const subEdges = edges.filter((e) => seen.has(e.source) && seen.has(e.target));
    return { nodes, edges: subEdges };
  }, [svc, cis, edges]);

  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    cis.forEach((x) => (c[x.ci_class] = (c[x.ci_class] || 0) + 1));
    return c;
  }, [cis]);

  const filteredCis = cls === "all" ? cis : cis.filter((c) => c.ci_class === cls);

  return (
    <div className="p-6 space-y-5 max-w-[1400px]">
      <header>
        <div className="text-xs font-bold text-brand tracking-wider">SERVICENOW · CMDB / CSDM</div>
        <h1 className="text-2xl font-extrabold mt-1">Patrimonio tecnológico e Impact Graph</h1>
        <p className="text-sm text-gray-400 mt-1">Modelo de dependencias que traduce "servidor vulnerable" → "servicio de negocio crítico". Base del blast radius.</p>
      </header>

      <div className="flex flex-wrap gap-2">
        {Object.entries(counts).map(([k, v]) => (
          <div key={k} className="chip border border-line" style={{ color: CI_CLASS_META[k]?.color }}>
            {CI_CLASS_META[k]?.label || k}: <b className="ml-1">{v}</b>
          </div>
        ))}
      </div>

      <div className="card p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="text-sm font-semibold">Impact Graph por servicio de negocio</div>
          <select value={svc} onChange={(e) => setSvc(e.target.value)}
            className="bg-ink border border-line rounded-lg px-3 py-1.5 text-sm outline-none focus:border-brand">
            {services.map((s) => <option key={s.id} value={s.id}>{s.name} ({s.criticality})</option>)}
          </select>
        </div>
        {sub.nodes.length > 0 && <ImpactGraphView nodes={sub.nodes} edges={sub.edges} height={440} />}
        <div className="text-xs text-gray-500 mt-2">{sub.nodes.length} CIs conectados a este servicio.</div>
      </div>

      <div className="card overflow-hidden">
        <div className="px-4 py-3 border-b border-line flex items-center gap-2">
          <div className="text-sm font-semibold">Configuration Items</div>
          <select value={cls} onChange={(e) => setCls(e.target.value)}
            className="ml-auto bg-ink border border-line rounded-lg px-2 py-1 text-xs outline-none">
            <option value="all">Todas las clases</option>
            {Object.keys(counts).map((k) => <option key={k} value={k}>{CI_CLASS_META[k]?.label || k}</option>)}
          </select>
        </div>
        <div className="max-h-[420px] overflow-y-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-ink">
              <tr className="text-left text-xs text-gray-500 border-b border-line">
                <th className="px-4 py-2 font-medium">ID</th>
                <th className="px-2 py-2 font-medium">Nombre</th>
                <th className="px-2 py-2 font-medium">Clase</th>
                <th className="px-2 py-2 font-medium">Criticidad</th>
                <th className="px-2 py-2 font-medium">Entorno</th>
                <th className="px-2 py-2 font-medium">Owner</th>
              </tr>
            </thead>
            <tbody>
              {filteredCis.slice(0, 200).map((c) => (
                <tr key={c.id} className="border-b border-line/40">
                  <td className="px-4 py-2 font-mono text-xs text-gray-500">{c.id}</td>
                  <td className="px-2 py-2 text-gray-200">{c.name}</td>
                  <td className="px-2 py-2"><span className="chip" style={{ color: CI_CLASS_META[c.ci_class]?.color, background: (CI_CLASS_META[c.ci_class]?.color || "#666") + "1a" }}>{CI_CLASS_META[c.ci_class]?.label || c.ci_class}</span></td>
                  <td className="px-2 py-2 text-gray-400 capitalize">{c.criticality}</td>
                  <td className="px-2 py-2 text-gray-400">{c.environment}</td>
                  <td className="px-2 py-2 text-gray-500 text-xs">{c.owner}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
