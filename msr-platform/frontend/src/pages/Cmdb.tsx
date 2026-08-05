import { useEffect, useState } from "react";
import { api } from "../api";
import type { CI, Edge, CmdbSummary, CmdbCiRaw, CmdbTables } from "../types";
import { CI_CLASS_META, Track } from "../ui";
import ImpactGraphView from "../components/ImpactGraphView";
import CmdbRecordModal from "../components/CmdbRecordModal";

const PAGE = 50;

/** Resuelve si el CI puede ser objetivo de un parcheo automatizado en AWS. */
function PatchTarget({ ci }: { ci: CI }) {
  if (!ci.instance_id)
    return (
      <span className="chip bg-gray-500/15 text-gray-400" title="La CMDB de demo no expone un Instance ID de EC2; el parcheo real requiere resolverlo antes de ejecutar.">
        sin instancia AWS
      </span>
    );
  return (
    <span className="text-xs text-gray-300">
      <span className="font-mono">{ci.instance_id}</span>
      {ci.region && <span className="text-gray-500"> · {ci.region}</span>}
      <span className={`chip ml-1 ${ci.ssm_managed ? "bg-green-500/15 text-green-400" : "bg-amber-500/15 text-amber-300"}`}>
        {ci.ssm_managed ? "SSM" : "sin SSM"}
      </span>
    </span>
  );
}

export default function Cmdb() {
  const [summary, setSummary] = useState<CmdbSummary | null>(null);
  const [services, setServices] = useState<CI[]>([]);
  const [svc, setSvc] = useState<string>("");
  const [graph, setGraph] = useState<{ nodes: CI[]; edges: Edge[] }>({ nodes: [], edges: [] });

  // tabla paginada
  const [cls, setCls] = useState("all");
  const [track, setTrack] = useState("all");
  const [crit, setCrit] = useState("all");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(0);
  const [rows, setRows] = useState<CI[]>([]);
  const [total, setTotal] = useState(0);
  const [raw, setRaw] = useState<CmdbCiRaw | null>(null);
  const [tables, setTables] = useState<CmdbTables | null>(null);

  useEffect(() => {
    api.cmdb().then((r) => {
      setSummary(r.summary);
      setServices(r.services);
      if (r.services[0]) setSvc(r.services[0].id);
    });
    api.cmdbTables().then(setTables);
  }, []);

  useEffect(() => {
    if (svc) api.cmdbGraph(svc).then(setGraph);
  }, [svc]);

  useEffect(() => {
    const h = setTimeout(() => {
      api.cmdbCis({ cls, track, crit, q, limit: PAGE, offset: page * PAGE }).then((r) => {
        setRows(r.items);
        setTotal(r.total);
      });
    }, 200);
    return () => clearTimeout(h);
  }, [cls, track, crit, q, page]);

  useEffect(() => { setPage(0); }, [cls, track, crit, q]);

  if (!summary) return <div className="p-8 text-gray-500">Cargando…</div>;

  const graphNodes = graph.nodes.map((n) => ({ ...n, is_root: (n as any).is_root } as any));

  return (
    <div className="p-6 space-y-5 max-w-[1400px]">
      <header>
        <div className="text-xs font-bold text-brand tracking-wider">SERVICENOW · CMDB / CSDM</div>
        <h1 className="text-2xl font-extrabold mt-1">Patrimonio tecnológico e Impact Graph</h1>
        <p className="text-sm text-gray-400 mt-1">
          CMDB estandarizada (<span className="text-gray-300">{summary.source}</span>) · <b className="text-gray-200">{summary.total.toLocaleString()}</b> CIs · {summary.edges.toLocaleString()} relaciones. Traduce "servidor vulnerable" → "servicio de negocio crítico".
        </p>
      </header>

      {/* CMDB versionada en el repo (formato ServiceNow Table API) */}
      {tables && (
        <div className="card p-4">
          <div className="flex items-center justify-between flex-wrap gap-2 mb-2">
            <div>
              <div className="text-sm font-semibold text-gray-100">CMDB versionada en el repositorio</div>
              <div className="text-xs text-gray-500 mt-0.5">
                Origen: <span className="text-gray-300">{tables.source}</span> · export en formato nativo ServiceNow (una tabla por <span className="font-mono">cmdb_ci_*</span> + relaciones <span className="font-mono">cmdb_rel_ci</span>) en <span className="font-mono text-gray-300">msr-platform/data/cmdb/</span>. El backend la carga como fuente de verdad.
              </div>
            </div>
            <div className="text-right">
              <div className="text-2xl font-extrabold text-brand">{tables.total_cis.toLocaleString()}</div>
              <div className="text-[11px] text-gray-500">CIs · {tables.total_relationships?.toLocaleString()} relaciones</div>
            </div>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {tables.tables.map((t) => (
              <span key={t.table} className="chip border border-line bg-ink text-gray-300 font-mono text-[11px]" title={t.file}>
                {t.table} · {t.records.toLocaleString()}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* resumen por clase y carril */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="card p-4">
          <div className="text-xs text-gray-500 mb-2">CIs por clase</div>
          <div className="flex flex-wrap gap-2">
            {Object.entries(summary.by_class).sort((a, b) => b[1] - a[1]).map(([k, v]) => (
              <div key={k} className="chip border border-line" style={{ color: CI_CLASS_META[k]?.color }}>
                {CI_CLASS_META[k]?.label || k}: <b className="ml-1">{v.toLocaleString()}</b>
              </div>
            ))}
          </div>
        </div>
        <div className="card p-4">
          <div className="text-xs text-gray-500 mb-2">CIs por dominio técnico</div>
          <div className="flex flex-wrap gap-2 items-center">
            {(["A", "B", "C"] as const).map((k) => (
              <div key={k} className="flex items-center gap-2">
                <Track t={k} /><b className="font-mono">{(summary.by_track[k] || 0).toLocaleString()}</b>
              </div>
            ))}
          </div>
        </div>
        <div className="card p-4">
          <div className="text-xs text-gray-500 mb-2">CIs por criticidad</div>
          <div className="flex flex-wrap gap-2">
            {Object.entries(summary.by_criticality).map(([k, v]) => (
              <div key={k} className="chip border border-line capitalize">{k}: <b className="ml-1">{v.toLocaleString()}</b></div>
            ))}
          </div>
        </div>
      </div>

      <div className="card p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="text-sm font-semibold">Impact Graph por servicio de negocio</div>
          <select value={svc} onChange={(e) => setSvc(e.target.value)}
            className="bg-ink border border-line rounded-lg px-3 py-1.5 text-sm outline-none focus:border-brand">
            {services.map((s) => <option key={s.id} value={s.id}>{s.name} ({s.criticality})</option>)}
          </select>
        </div>
        {graphNodes.length > 0 && <ImpactGraphView nodes={graphNodes} edges={graph.edges} height={440} />}
        <div className="text-xs text-gray-500 mt-2">{graphNodes.length} CIs conectados a este servicio (blast radius, prof. 4).</div>
      </div>

      <div className="card overflow-hidden">
        <div className="px-4 pt-3 text-xs text-gray-500">
          Cada CI llega desde ServiceNow vía IntegrationHub / MID Server (Table API). Pulsa <span className="text-brand font-mono">{"{ } ver JSON"}</span> para ver el <b className="text-gray-300">registro nativo</b> y su mapeo al modelo interno — el contrato de integración.
        </div>
        <div className="px-4 py-3 border-b border-line flex flex-wrap items-center gap-2">
          <div className="text-sm font-semibold">Configuration Items</div>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar por nombre / ID…"
            className="ml-auto bg-ink border border-line rounded-lg px-3 py-1 text-xs outline-none focus:border-brand w-48" />
          <select value={cls} onChange={(e) => setCls(e.target.value)} className="bg-ink border border-line rounded-lg px-2 py-1 text-xs outline-none">
            <option value="all">Todas las clases</option>
            {Object.keys(summary.by_class).map((k) => <option key={k} value={k}>{CI_CLASS_META[k]?.label || k}</option>)}
          </select>
          <select value={track} onChange={(e) => setTrack(e.target.value)} className="bg-ink border border-line rounded-lg px-2 py-1 text-xs outline-none">
            <option value="all">Todos los dominios</option>
            <option value="A">Dominio A</option><option value="B">Dominio B</option><option value="C">Dominio C</option>
          </select>
          <select value={crit} onChange={(e) => setCrit(e.target.value)} className="bg-ink border border-line rounded-lg px-2 py-1 text-xs outline-none">
            <option value="all">Toda criticidad</option>
            <option value="critical">Critical</option><option value="high">High</option>
            <option value="medium">Medium</option><option value="low">Low</option>
          </select>
        </div>
        <div className="max-h-[460px] overflow-y-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-ink">
              <tr className="text-left text-xs text-gray-500 border-b border-line">
                <th className="px-4 py-2 font-medium">ID</th>
                <th className="px-2 py-2 font-medium">Nombre</th>
                <th className="px-2 py-2 font-medium">Clase (sys_class_name)</th>
                <th className="px-2 py-2 font-medium">Dominio</th>
                <th className="px-2 py-2 font-medium">Criticidad</th>
                <th className="px-2 py-2 font-medium">Entorno</th>
                <th className="px-2 py-2 font-medium">Objetivo de parcheo</th>
                <th className="px-2 py-2 font-medium">Support group</th>
                <th className="px-2 py-2 font-medium text-right">Registro CMDB</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((c) => (
                <tr key={c.id} className="border-b border-line/40">
                  <td className="px-4 py-2 font-mono text-xs text-gray-500">{c.id}</td>
                  <td className="px-2 py-2 text-gray-200">{c.name}</td>
                  <td className="px-2 py-2">
                    <span className="chip" style={{ color: CI_CLASS_META[c.ci_class]?.color, background: (CI_CLASS_META[c.ci_class]?.color || "#666") + "1a" }}>
                      {CI_CLASS_META[c.ci_class]?.label || c.ci_class}
                    </span>
                    <span className="ml-1 font-mono text-[10px] text-gray-600">{c.sys_class_name}</span>
                  </td>
                  <td className="px-2 py-2">{c.track ? <Track t={c.track} /> : <span className="text-gray-600 text-xs">—</span>}</td>
                  <td className="px-2 py-2 text-gray-400 capitalize">{c.criticality}</td>
                  <td className="px-2 py-2 text-gray-400">{c.environment}</td>
                  <td className="px-2 py-2"><PatchTarget ci={c} /></td>
                  <td className="px-2 py-2 text-gray-500 text-xs">{c.support_group}</td>
                  <td className="px-2 py-2 text-right">
                    <button
                      onClick={() => api.cmdbCiRaw(c.id).then(setRaw)}
                      className="px-2 py-1 rounded border border-line text-[11px] text-brand hover:bg-brand/10"
                      title="Ver el registro tal como llega de ServiceNow (Table API) y su mapeo">
                      {"{ }"} ver JSON
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="px-4 py-2 border-t border-line flex items-center justify-between text-xs text-gray-400">
          <span>{total.toLocaleString()} CIs · página {page + 1} de {Math.max(1, Math.ceil(total / PAGE))}</span>
          <div className="flex gap-2">
            <button disabled={page === 0} onClick={() => setPage((p) => Math.max(0, p - 1))}
              className="px-2 py-1 rounded border border-line disabled:opacity-40">← Anterior</button>
            <button disabled={(page + 1) * PAGE >= total} onClick={() => setPage((p) => p + 1)}
              className="px-2 py-1 rounded border border-line disabled:opacity-40">Siguiente →</button>
          </div>
        </div>
      </div>

      {raw && <CmdbRecordModal raw={raw} onClose={() => setRaw(null)} />}
    </div>
  );
}
