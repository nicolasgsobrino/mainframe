import type { ReactNode } from "react";

export const PRIORITY_COLORS: Record<string, string> = {
  critical: "bg-red-500/15 text-red-400 border border-red-500/30",
  high: "bg-orange-500/15 text-orange-400 border border-orange-500/30",
  medium: "bg-amber-500/15 text-amber-300 border border-amber-500/30",
  low: "bg-sky-500/15 text-sky-300 border border-sky-500/30",
};

export const PHASE_META: Record<string, { label: string; color: string }> = {
  detection: { label: "Detección", color: "#64748b" },
  prioritization: { label: "Priorización", color: "#f59e0b" },
  pre_implementation: { label: "MVT", color: "#86BC25" },
  lab_testing: { label: "Lab", color: "#22c55e" },
  prototype: { label: "Prototipo", color: "#14b8a6" },
  deployment: { label: "Despliegue", color: "#0ea5e9" },
};

export function Badge({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <span className={`chip ${className}`}>{children}</span>;
}

export function Priority({ p }: { p: string }) {
  return <span className={`chip ${PRIORITY_COLORS[p] || ""}`}>{p.toUpperCase()}</span>;
}

export const TRACK_META: Record<string, { label: string; cls: string }> = {
  A: { label: "A · Infraestructura", cls: "bg-indigo-500/15 text-indigo-300 border border-indigo-500/30" },
  B: { label: "B · Aplicaciones y dependencias", cls: "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30" },
  C: { label: "C · Contenedores & Cloud-native", cls: "bg-sky-500/15 text-sky-300 border border-sky-500/30" },
};

export function Track({ t }: { t: string }) {
  const m = TRACK_META[t] || TRACK_META.A;
  return (
    <span className={`chip ${m.cls}`} title={`Carril ${m.label}`}>
      Carril {t}
    </span>
  );
}

export function Risk({ score }: { score: number }) {
  const color = score >= 80 ? "text-red-400" : score >= 60 ? "text-orange-400" : score >= 40 ? "text-amber-300" : "text-sky-300";
  return <span className={`font-mono font-bold ${color}`}>{score}</span>;
}

export function KevTag() {
  return <span className="chip bg-red-500/20 text-red-300 border border-red-500/40" title="Known Exploited Vulnerability (CISA KEV)">KEV</span>;
}

export function StatusDot({ status }: { status: string }) {
  const map: Record<string, string> = {
    connected: "bg-brand", active: "bg-brand animate-pulse", pending: "bg-gray-500",
  };
  return <span className={`inline-block w-2.5 h-2.5 rounded-full ${map[status] || "bg-gray-500"}`} />;
}

export function CardTitle({ children, sub }: { children: ReactNode; sub?: string }) {
  return (
    <div className="px-4 pt-3 pb-2 border-b border-line">
      <div className="text-sm font-semibold text-gray-100">{children}</div>
      {sub && <div className="text-xs text-gray-500 mt-0.5">{sub}</div>}
    </div>
  );
}

export const CI_CLASS_META: Record<string, { label: string; color: string }> = {
  business_service: { label: "Business Service", color: "#a855f7" },
  application: { label: "Application", color: "#22c55e" },
  database: { label: "Database", color: "#0ea5e9" },
  server: { label: "Server", color: "#f59e0b" },
  middleware: { label: "Middleware", color: "#ec4899" },
  runtime: { label: "Runtime", color: "#14b8a6" },
  container: { label: "Container", color: "#38bdf8" },
  network_device: { label: "Network Device", color: "#fb7185" },
  endpoint: { label: "Endpoint", color: "#a3a3a3" },
  cloud_resource: { label: "Cloud Resource", color: "#818cf8" },
};
