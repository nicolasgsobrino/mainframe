import { useState } from "react";
import type { CmdbCiRaw } from "../types";

type Tab = "record" | "mapping";

export default function CmdbRecordModal({ raw, onClose }: { raw: CmdbCiRaw; onClose: () => void }) {
  const [tab, setTab] = useState<Tab>("record");
  const record = raw.servicenow_record as Record<string, unknown>;
  const rec = record["name"];
  const title = typeof rec === "string" ? rec : raw.ci_id;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={onClose}>
      <div
        className="card w-full max-w-3xl max-h-[85vh] overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-5 py-3 border-b border-line flex items-start justify-between gap-3">
          <div>
            <div className="text-xs font-bold text-brand tracking-wider">CONTRATO DE INGESTA · SERVICENOW CMDB</div>
            <div className="text-sm font-semibold mt-0.5">{title}</div>
            <div className="text-[11px] text-gray-500 font-mono mt-1">{raw.endpoint}</div>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-200 text-lg leading-none">✕</button>
        </div>

        <div className="px-5 pt-3 flex gap-2">
          <button
            onClick={() => setTab("record")}
            className={`px-3 py-1 rounded-lg text-xs border ${tab === "record" ? "border-brand text-brand bg-brand/10" : "border-line text-gray-400"}`}>
            Registro nativo (Table API)
          </button>
          <button
            onClick={() => setTab("mapping")}
            className={`px-3 py-1 rounded-lg text-xs border ${tab === "mapping" ? "border-brand text-brand bg-brand/10" : "border-line text-gray-400"}`}>
            Mapeo → modelo interno
          </button>
        </div>

        <div className="p-5 overflow-y-auto">
          {tab === "record" ? (
            <>
              <div className="text-[11px] text-gray-500 mb-2">
                Respuesta JSON con <span className="font-mono">sysparm_display_value=all</span>: campos de referencia como
                <span className="font-mono"> {"{ value, display_value, link }"}</span>, estados como código + etiqueta.
              </div>
              <pre className="bg-ink rounded-lg border border-line p-3 text-[11px] font-mono text-gray-300 overflow-x-auto whitespace-pre">
{JSON.stringify({ result: record }, null, 2)}
              </pre>
            </>
          ) : (
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-gray-500 border-b border-line">
                  <th className="py-2 pr-3 font-medium">Campo ServiceNow</th>
                  <th className="py-2 pr-3 font-medium">Tipo</th>
                  <th className="py-2 pr-3 font-medium">Modelo interno</th>
                  <th className="py-2 font-medium">Uso</th>
                </tr>
              </thead>
              <tbody>
                {raw.field_map.map((m) => (
                  <tr key={m.servicenow} className="border-b border-line/40 align-top">
                    <td className="py-2 pr-3 font-mono text-brand">{m.servicenow}</td>
                    <td className="py-2 pr-3 text-gray-500">{m.type}</td>
                    <td className="py-2 pr-3 font-mono text-gray-300">{m.internal}</td>
                    <td className="py-2 text-gray-400">{m.note}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="px-5 py-2 border-t border-line text-[11px] text-gray-500">
          Fuente: {raw.source} · tabla <span className="font-mono">{raw.table}</span>. Datos sintéticos y deterministas para la demo.
        </div>
      </div>
    </div>
  );
}
