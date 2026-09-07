import type { ReactNode } from "react";
import type { SlaState } from "./types";

export const PRIORITY_COLORS: Record<string, string> = {
  critical: "bg-red-500/15 text-red-400 border border-red-500/30",
  high: "bg-orange-500/15 text-orange-400 border border-orange-500/30",
  medium: "bg-amber-500/15 text-amber-300 border border-amber-500/30",
  low: "bg-sky-500/15 text-sky-300 border border-sky-500/30",
};

export const PHASE_META: Record<string, { label: string; color: string }> = {
  detection: { label: "Detection", color: "#64748b" },
  prioritization: { label: "Prioritisation", color: "#f59e0b" },
  pre_implementation: { label: "MVT", color: "#86BC25" },
  lab_testing: { label: "Lab", color: "#22c55e" },
  prototype: { label: "Prototype", color: "#14b8a6" },
  deployment: { label: "Deployment", color: "#0ea5e9" },
};

export function Badge({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <span className={`chip ${className}`}>{children}</span>;
}

export function Priority({ p }: { p: string }) {
  return <span className={`chip ${PRIORITY_COLORS[p] || ""}`}>{p.toUpperCase()}</span>;
}

// Dimensión técnica (secundaria) — determina el ejecutor y la mecánica de rollback.
export const TRACK_META: Record<string, { label: string; cls: string; exec: string }> = {
  A: { label: "A · Infrastructure", cls: "bg-indigo-500/15 text-indigo-300 border border-indigo-500/30", exec: "SCCM · BigFix · Ansible" },
  B: { label: "B · Applications and dependencies", cls: "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30", exec: "CI/CD (GitHub Actions)" },
  C: { label: "C · Containers & Cloud-native", cls: "bg-sky-500/15 text-sky-300 border border-sky-500/30", exec: "Argo CD · Helm · Registry" },
};

export function Track({ t }: { t: string }) {
  const m = TRACK_META[t] || TRACK_META.A;
  return (
    <span className={`chip ${m.cls}`} title={`Technical domain ${m.label} · ${m.exec}`}>
      Domain {t}
    </span>
  );
}

// Carril operativo (principal) — velocidad/riesgo. Colores del modelo: rojo/naranja/verde.
export const LANE_META: Record<string, { label: string; cls: string; dot: string }> = {
  critical: { label: "Critical", cls: "bg-red-500/15 text-red-300 border border-red-500/40", dot: "#ef4444" },
  accelerated: { label: "Accelerated", cls: "bg-orange-500/15 text-orange-300 border border-orange-500/40", dot: "#f97316" },
  standard: { label: "Standard", cls: "bg-emerald-500/15 text-emerald-300 border border-emerald-500/40", dot: "#22c55e" },
};

export function LaneTag({ lane, sla }: { lane: string; sla?: string }) {
  const m = LANE_META[lane] || LANE_META.standard;
  return (
    <span className={`chip ${m.cls}`} title={sla ? `${m.label} lane · ${sla}` : `${m.label} lane`}>
      {m.label} lane
    </span>
  );
}

// Nivel de automatización (leyenda del modelo): agentable / AI-assisted / human.
export const AUTOMATION_META: Record<string, { label: string; icon: string; cls: string }> = {
  agentable: { label: "Fully agentable", icon: "🤖", cls: "bg-brand/15 text-brand border border-brand/30" },
  ai_assisted: { label: "AI-assisted", icon: "🤝", cls: "bg-amber-500/15 text-amber-300 border border-amber-500/30" },
  human: { label: "Human driven", icon: "👤", cls: "bg-slate-500/15 text-slate-300 border border-slate-500/30" },
};

export function Automation({ level, compact = false }: { level: string; compact?: boolean }) {
  const m = AUTOMATION_META[level] || AUTOMATION_META.ai_assisted;
  return (
    <span className={`chip ${m.cls}`} title={m.label}>
      {m.icon}{compact ? "" : ` ${m.label}`}
    </span>
  );
}

// Indicador de cumplimiento del SLA / due date.
export function SlaTag({ sla }: { sla?: SlaState }) {
  if (!sla || sla.days_left === null) return <span className="text-gray-500 text-xs">—</span>;
  if (sla.overdue)
    return (
      <span className="chip bg-red-500/20 text-red-300 border border-red-500/50" title={`Overdue by ${sla.days_overdue} day(s) · due ${sla.due?.slice(0, 10)}`}>
        ⚠ SLA breached · +{sla.days_overdue}d
      </span>
    );
  if (sla.due_soon)
    return (
      <span className="chip bg-amber-500/15 text-amber-300 border border-amber-500/40" title={`Due in ${sla.days_left} day(s) · due ${sla.due?.slice(0, 10)}`}>
        ⏳ {sla.days_left}d left
      </span>
    );
  return (
    <span className="chip bg-emerald-500/10 text-emerald-300 border border-emerald-500/30" title={`due ${sla.due?.slice(0, 10)}`}>
      {sla.days_left}d within SLA
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
