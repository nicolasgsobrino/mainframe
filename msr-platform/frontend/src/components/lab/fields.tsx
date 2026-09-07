import type { LabCheck } from "../../types";

/** Una comprobación: verde si cumple, roja si falla, gris si no es concluyente. */
export function Check({ c }: { c: LabCheck }) {
  const [icon, cls] = c.ok === null ? ["?", "text-gray-400"]
    : c.ok ? ["\u2713", "text-green-400"] : ["\u2717", "text-red-400"];
  return (
    <div className="text-xs flex gap-2">
      <span className={cls}>{icon}</span>
      <span className="text-gray-300">{c.check}</span>
      <span className="text-gray-500">{c.detail}</span>
    </div>
  );
}

export function Field({ label, value, mono = false }: {
  label: string; value: string; mono?: boolean;
}) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-wide text-gray-500 font-semibold">{label}</div>
      <div className={`text-sm text-gray-200 ${mono ? "font-mono" : ""}`}>{value}</div>
    </div>
  );
}
