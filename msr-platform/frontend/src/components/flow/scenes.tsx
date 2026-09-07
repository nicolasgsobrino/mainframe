import { useState, type ReactNode } from "react";
import ImpactGraphView from "../ImpactGraphView";
import type { HitlGate, Ring, TaskDetail } from "../../types";
import { CI_CLASS_META } from "../../ui";
import { AutomationBadge } from "./hitl";
import { CountUp, useProgressiveReveal } from "./reveal";

/**
 * Las escenas del recorrido guiado: una por fase del journey, con el material
 * que el backend ya publica para esa fase. No calculan estado ni disparan
 * acciones — eso vive en el panel del presentador.
 */
export interface SceneProps {
  detail: TaskDetail;
  /** Puertas humanas de la fase, para señalar dónde se detiene el recorrido. */
  gates: HitlGate[];
  /** Revierte un anillo ya desplegado; sin ella el control se ve inhabilitado. */
  onRollback?: (ring: number) => void;
  /** Hay un job en vuelo o una reproducción en curso: no se encadenan acciones. */
  busy?: boolean;
}

/** Dato suelto con etiqueta: el ladrillo con el que se arman las escenas. */
function Fact({ label, value, hint, accent }: {
  label: string; value: ReactNode; hint?: string; accent?: string;
}) {
  return (
    <div className="rounded-lg border border-line bg-ink p-3">
      <div className="text-[10px] uppercase tracking-wide text-gray-500">{label}</div>
      <div className="text-lg font-bold leading-tight mt-0.5" style={{ color: accent ?? "#e5e7eb" }}>
        {value}
      </div>
      {hint && <div className="text-[11px] text-gray-500 leading-snug mt-1">{hint}</div>}
    </div>
  );
}

function Facts({ children }: { children: ReactNode }) {
  return <div className="grid grid-cols-2 lg:grid-cols-4 gap-2.5">{children}</div>;
}

/** Lista que se completa sola en Modo Demo, un elemento cada vez. */
function Revealed<T>({ items, render, empty }: {
  items: T[]; render: (item: T, i: number) => ReactNode; empty?: string;
}) {
  const shown = useProgressiveReveal(items, 220);
  if (items.length === 0) return <div className="text-[11px] text-gray-600">{empty ?? "No items."}</div>;
  return (
    <div className="space-y-1.5">
      {shown.map((item, i) => (
        <div key={i} className="animate-fade-in">{render(item, i)}</div>
      ))}
      {shown.length < items.length && (
        <div className="text-[11px] text-gray-600">
          <span className="animate-pulse">▍</span> {items.length - shown.length} to confirm…
        </div>
      )}
    </div>
  );
}

function Block({ title, sub, children }: { title: string; sub?: string; children: ReactNode }) {
  return (
    <div className="rounded-xl border border-line bg-ink-panel/40 p-3">
      <div className="text-xs font-semibold text-gray-200">{title}</div>
      {sub && <div className="text-[11px] text-gray-500 leading-snug mb-2">{sub}</div>}
      <div className={sub ? "" : "mt-2"}>{children}</div>
    </div>
  );
}

function ClassTag({ ciClass }: { ciClass: string }) {
  const meta = CI_CLASS_META[ciClass] ?? { label: ciClass, color: "#64748b" };
  return (
    <span className="chip border" style={{ borderColor: meta.color + "55", color: meta.color }}>
      {meta.label}
    </span>
  );
}

// --- 1 · Disparador de ciberseguridad ---------------------------------------

function CyberTrigger({ detail }: SceneProps) {
  const vi = detail.vulnerable_item;
  return (
    <div className="space-y-3">
      <Facts>
        <Fact label="CVSS" value={vi.cvss.toFixed(1)} accent="#ef4444" hint="Technical severity" />
        <Fact label="EPSS" value={`${Math.round(vi.epss * 100)}%`} accent="#f59e0b"
              hint="Probability of exploitation within 30 days" />
        <Fact label="Exploitation" value={vi.kev ? "KEV · active" : vi.exploit_available ? "Public exploit" : "Not observed"}
              accent={vi.kev ? "#ef4444" : "#f59e0b"} hint="CISA KEV and threat telemetry" />
        <Fact label="Exposure" value={vi.exposed ? "Internet" : "Internal"}
              hint={`${vi.environment} · ${vi.criticality}`} />
      </Facts>
      <Block title="Signal received from Cyber / Security"
             sub="The finding arrives already correlated; the platform normalises it and opens the Vulnerable Item.">
        <Revealed
          items={[
            `Correlated sources: ${vi.sources.join(" · ")}`,
            `Finding ${vi.cve} on ${vi.component} ${vi.vulnerable_version}`,
            `Vulnerable Item ${vi.id} created and linked to ${vi.ci_name} (${vi.ci_id})`,
            `Composite risk ${vi.risk_score}/100 · ${detail.lane_meta.label} lane · SLA ${detail.lane_meta.sla}`,
          ]}
          render={(line) => (
            <div className="flex items-start gap-2 text-[11px] text-gray-300">
              <span className="text-brand">▸</span>{line}
            </div>
          )}
        />
      </Block>
    </div>
  );
}

// --- 2 · Confirmación de activos afectados ----------------------------------

function AssetConfirmation({ detail }: SceneProps) {
  const impact = detail.artifacts.impact;
  const byClass = impact.nodes.reduce<Record<string, number>>((acc, n) => {
    acc[n.ci_class] = (acc[n.ci_class] ?? 0) + 1;
    return acc;
  }, {});
  return (
    <div className="space-y-3">
      <Facts>
        <Fact label="Confirmed assets" value={<CountUp value={impact.affected_count} />} accent="#86BC25"
              hint="Cross-checked against the CMDB, not just declared by Cyber" />
        <Fact label="Business services" value={<CountUp value={impact.business_services.length} />}
              hint={impact.business_services.join(", ") || "—"} />
        <Fact label="Layers involved" value={<CountUp value={impact.affected_layers.length} />}
              hint={impact.affected_layers.join(", ")} />
        <Fact label="CI→CI relationships" value={<CountUp value={impact.edges.length} />}
              hint="Edges traversed in the CMDB" />
      </Facts>
      <Block title="Confirmation against the CMDB"
             sub="Each CI is resolved by relationship, not from a list: they appear as they are confirmed.">
        <Revealed
          items={impact.nodes}
          render={(n) => (
            <div className="flex items-center gap-2 text-[11px]">
              <ClassTag ciClass={n.ci_class} />
              <span className={n.is_root ? "text-red-300 font-semibold" : "text-gray-300"}>{n.name}</span>
              <span className="text-gray-600">{n.environment}</span>
              {n.is_root && <span className="chip border border-red-500/40 text-red-300">vulnerable root</span>}
            </div>
          )}
        />
      </Block>
      <div className="flex flex-wrap gap-1.5">
        {Object.entries(byClass).map(([cls, n]) => (
          <span key={cls} className="chip border border-line text-gray-400">{n} × {CI_CLASS_META[cls]?.label ?? cls}</span>
        ))}
      </div>
    </div>
  );
}

// --- 3 · Aplicabilidad y remediación ----------------------------------------

function Applicability({ detail }: SceneProps) {
  const mvt = detail.artifacts.mvt;
  const impact = detail.artifacts.impact;
  return (
    <div className="space-y-3">
      <Facts>
        <Fact label="Remediation type" value={mvt.remediation_type} accent="#86BC25"
              hint={`Restart: ${impact.restart_scope} · ${impact.downtime_required ? "with downtime" : "no downtime"}`} />
        <Fact label="Plan confidence" value={`${mvt.confidence}%`} accent="#22c55e"
              hint="Estimated coverage of the minimum viable test set" />
        <Fact label="Selected tests" value={<CountUp value={mvt.selected.length} />}
              hint={`${mvt.excluded.length} discarded as not applicable`} />
        <Fact label="Executor" value={detail.artifacts.deployment.executor} hint={detail.artifacts.deployment.strategy} />
      </Facts>
      <Block title="Minimum viable test set (MVT)" sub={mvt.rationale}>
        <Revealed
          items={mvt.selected}
          render={(t) => (
            <div className="flex items-center gap-2 text-[11px]">
              <span className="font-mono text-gray-600">{t.id}</span>
              <span className="text-gray-300">{t.name}</span>
              <span className="chip border border-line text-gray-500">{t.layer}</span>
              <span className="text-gray-600">{t.tool}</span>
            </div>
          )}
        />
      </Block>
    </div>
  );
}

// --- 4 · Blast radius --------------------------------------------------------

function BlastRadius({ detail }: SceneProps) {
  const impact = detail.artifacts.impact;
  return (
    <div className="space-y-3">
      <Facts>
        <Fact label="CIs reached" value={`${impact.impacted_count} of ${impact.affected_count}`}
              accent={impact.blast_scope === "propagated" ? "#f97316" : "#22c55e"}
              hint={impact.blast_scope === "propagated" ? "Propagates to dependants" : "Local impact"} />
        <Fact label="Service downtime" value={impact.downtime_required ? "Required" : "Not required"}
              hint={`Restart scope: ${impact.restart_scope}`} />
        <Fact label="Business services" value={impact.business_services.join(", ") || "—"} />
        <Fact label="Window" value={detail.artifacts.deployment.rings[0]?.plan.window ?? "—"} />
      </Facts>
      <div className="text-[11px] text-gray-400 leading-snug">{impact.blast_rationale}</div>
      <ImpactGraphView nodes={impact.nodes} edges={impact.edges} height={360} />
    </div>
  );
}

// --- 5 · Marco de cambio y planificación ------------------------------------

function ChangePlanning({ detail }: SceneProps) {
  const dep = detail.artifacts.deployment;
  const itsm = dep.itsm;
  const rollback = dep.rollback_plan;
  return (
    <div className="space-y-3">
      <Facts>
        <Fact label="ITSM change" value={itsm?.number ?? detail.journey.change.number} accent="#a855f7"
              hint={itsm?.type_label ?? detail.journey.change.type} />
        <Fact label="State" value={itsm?.state ?? detail.journey.change.state} hint={itsm?.approval} />
        <Fact label="Risk / impact" value={itsm?.risk ?? "—"}
              hint={itsm ? `${itsm.impact_level} · ${itsm.affected_cis} CIs` : undefined} />
        <Fact label="Rollback" value={`${rollback.rto_minutes} min RTO`}
              hint={`${rollback.strategy}${rollback.tested_in_lab ? " · tested in the lab" : ""}`} />
      </Facts>

      {itsm && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          <Block title="Change lifecycle" sub={itsm.detail}>
            <div className="flex flex-wrap gap-1.5">
              {itsm.phases.filter((p) => p.included).map((p) => (
                <span key={p.key}
                      className={`chip border ${p.approval
                        ? "border-amber-500/40 bg-amber-500/10 text-amber-300"
                        : "border-line text-gray-400"}`}>
                  {p.approval ? "◑ " : ""}{p.label}
                </span>
              ))}
            </div>
            <div className="mt-2 flex flex-wrap gap-1.5 text-[10px] text-gray-500">
              <span className="chip border border-line">{itsm.assignment_group}</span>
              {itsm.four_eyes && <span className="chip border border-line">four-eyes check</span>}
              {itsm.gxp && <span className="chip border border-line">GxP</span>}
            </div>
          </Block>
          <Block title="Change tasks (CTASK)" sub="What the agent runs and what stays in human hands.">
            <Revealed
              items={itsm.ctasks}
              render={(c) => (
                <div className="flex items-center gap-2 text-[11px]">
                  <AutomationBadge human={!c.auto} label={c.auto ? "agent" : "person"} />
                  <span className="text-gray-300">{c.name}</span>
                  <span className="text-gray-600">{c.role}</span>
                </div>
              )}
            />
          </Block>
        </div>
      )}

      <Block title="Planned execution sequence"
             sub="Each ring has its target population, its window and its own approval.">
        <Revealed
          items={dep.rings}
          render={(r) => (
            <div className="rounded-lg border border-line bg-ink p-2">
              <div className="flex items-center gap-2 text-[11px]">
                <span className="font-mono text-gray-500">#{r.ring}</span>
                <span className="text-gray-200 font-semibold">{r.label}</span>
                <span className="chip border border-line text-gray-500">{r.plan.assets_count} assets</span>
                <span className="ml-auto text-gray-500">{r.plan.window}</span>
              </div>
              <div className="text-[10px] text-gray-500 leading-snug mt-1">{r.plan.purpose ?? r.plan.target_population}</div>
            </div>
          )}
        />
      </Block>
    </div>
  );
}

// --- 6 · Ejecución por anillos ----------------------------------------------

const RING_STATUS: Record<string, { label: string; color: string }> = {
  completed: { label: "completed", color: "#22c55e" },
  in_progress: { label: "in progress", color: "#0ea5e9" },
  rolled_back: { label: "rolled back", color: "#f97316" },
  pending: { label: "pending", color: "#475569" },
};

/**
 * Rollback del anillo: la salida de emergencia está a la vista en cada lote,
 * no escondida en una acción global. El motor revierte el último anillo
 * desplegado, así que el resto se muestra inhabilitado explicando por qué.
 */
function RingRollback({ ring, enabled, busy, onRollback }: {
  ring: Ring; enabled: boolean; busy: boolean; onRollback?: (ring: number) => void;
}) {
  const [armed, setArmed] = useState(false);
  const reverted = ring.status === "rolled_back";
  const usable = Boolean(onRollback) && enabled && !busy && !reverted;
  const why = reverted
    ? "Ring rolled back: its evidence was invalidated and it returns to the pre-deployment state."
    : ring.status === "pending"
      ? "Nothing to roll back: this ring has not been deployed yet."
      : enabled
        ? `Rolls ring ${ring.ring} back to the stable version and reopens its validation.`
        : "Only the last deployed ring can be rolled back; roll back the later ones first.";
  return (
    <div className="pt-1.5 border-t border-line/70 flex items-center gap-2">
      <button
        type="button"
        disabled={!usable}
        title={why}
        onClick={() => {
          if (!usable || !onRollback) return;
          if (!armed) { setArmed(true); return; }
          setArmed(false);
          onRollback(ring.ring);
        }}
        onBlur={() => setArmed(false)}
        className={`text-[10px] rounded-md border px-2 py-1 transition ${
          armed
            ? "border-orange-500/60 bg-orange-500/20 text-orange-200"
            : "border-orange-500/35 text-orange-300/90 hover:bg-orange-500/10"} ${
          usable ? "" : "opacity-45 cursor-not-allowed hover:bg-transparent"}`}
      >
        {reverted ? "⟲ Rolled back" : armed ? "Confirm rollback" : "⟲ Roll back this ring"}
      </button>
      <span className="text-[10px] text-gray-600 leading-snug">{why}</span>
    </div>
  );
}

function RingCard({ ring, rollbackEnabled = false, busy = false, onRollback }: {
  ring: Ring; rollbackEnabled?: boolean; busy?: boolean; onRollback?: (ring: number) => void;
}) {
  const meta = RING_STATUS[ring.status] ?? RING_STATUS.pending;
  const approval = ring.plan.approval;
  return (
    <div className="rounded-xl border p-3 space-y-2" style={{ borderColor: meta.color + "55" }}>
      <div className="flex items-center gap-2">
        <span className="w-2 h-2 rounded-full" style={{ background: meta.color }} />
        <span className="text-xs font-semibold text-gray-100">{ring.label}</span>
        <span className="chip border ml-auto" style={{ borderColor: meta.color + "55", color: meta.color }}>
          {meta.label}
        </span>
      </div>
      <div className="text-[11px] text-gray-500">
        {ring.plan.selected_count}/{ring.plan.assets_count} assets · {ring.plan.window}
      </div>
      <div className="text-[11px]">
        {approval.preapproved
          ? <span className="text-emerald-300">✓ pre-approved{approval.approver ? ` · ${approval.approver}` : ""}</span>
          : <span className="text-amber-300">◑ awaiting human pre-approval</span>}
      </div>
      {ring.simulated && (
        <div className="text-[10px] text-fuchsia-300">simulated · dry-run · no real changes</div>
      )}
      {ring.actions && (
        <div className="font-mono text-[10px] text-gray-500 space-y-0.5">
          {ring.actions.steps.slice(0, 3).map((s) => (
            <div key={s.seq} className="truncate" title={s.command}>$ {s.command}</div>
          ))}
        </div>
      )}
      {ring.health && (
        <div className="flex flex-wrap gap-1.5 text-[10px] text-gray-400">
          <span className="chip border border-line">errors {ring.health.error_rate_pct}%</span>
          <span className="chip border border-line">p95 {ring.health.p95_latency_ms} ms</span>
          <span className="chip border border-line">availability {ring.health.availability_pct}%</span>
        </div>
      )}
      <RingRollback ring={ring} enabled={rollbackEnabled} busy={busy} onRollback={onRollback} />
    </div>
  );
}

/** Último anillo desplegado: el único que el motor puede revertir ahora. */
function revertibleRing(detail: TaskDetail): number | null {
  const rings = detail.artifacts.deployment.rings;
  return detail.rings_done > 0 ? rings[detail.rings_done - 1]?.ring ?? null : null;
}

function RingExecution({ detail, onRollback, busy = false }: SceneProps) {
  const dep = detail.artifacts.deployment;
  const res = detail.journey.resources;
  const revertible = revertibleRing(detail);
  return (
    <div className="space-y-3">
      <Facts>
        <Fact label="Rings deployed" value={`${detail.rings_done}/${dep.rings.length}`} accent="#0ea5e9" />
        <Fact label="Assets patched" value={<CountUp value={res.patched} />} accent="#22c55e"
              hint={`${res.pending} pending · ${res.excluded} excluded`} />
        <Fact label="Executor" value={dep.executor} hint={dep.strategy} />
        <Fact label="Exceptions" value={dep.exceptions.length}
              hint={dep.exceptions[0]?.reason ?? "No exceptions recorded"} />
      </Facts>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {dep.rings.map((r) => (
          <RingCard key={r.ring} ring={r} onRollback={onRollback} busy={busy}
                    rollbackEnabled={r.ring === revertible} />
        ))}
      </div>
      <div className="text-[10px] text-gray-600">
        Every ring carries its own exit: if the validation is not convincing, the batch is rolled
        back to the stable version before promoting to the next one.
      </div>
    </div>
  );
}

// --- 7 · Validation Tests y rollback ----------------------------------------

function GateValidation({ detail, onRollback, busy = false }: SceneProps) {
  const dep = detail.artifacts.deployment;
  const last = [...dep.rings].reverse().find((r) => r.status !== "pending") ?? dep.rings[0];
  const rollback = dep.rollback_plan;
  const revertible = revertibleRing(detail);
  return (
    <div className="space-y-3">
      <Facts>
        <Fact label="Ring under review" value={last?.label ?? "—"} hint={last?.result} />
        <Fact label="Post-checks" value={last?.post_checks.length ?? 0}
              hint="Checks run before promoting" />
        <Fact label="Rollback" value={dep.rollback.triggered ? "Executed" : dep.rollback.status}
              accent={dep.rollback.triggered ? "#f97316" : "#22c55e"}
              hint={`Automatic trigger: ${rollback.auto_trigger}`} />
        <Fact label="Versions" value={`${rollback.from_version} → ${rollback.target_version}`}
              hint={rollback.snapshot_ref} />
      </Facts>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <Block title="Ring post-checks" sub="Promotion is only proposed if they all pass.">
          <Revealed
            items={last?.post_checks ?? []}
            render={(c) => <div className="text-[11px] text-gray-300">✓ {c}</div>}
            empty="This ring has not published post-checks yet."
          />
        </Block>
        <Block title="Rollback plan" sub={rollback.strategy}>
          {last && (
            <div className="mb-2">
              <RingRollback ring={last} enabled={last.ring === revertible} busy={busy}
                            onRollback={onRollback} />
            </div>
          )}
          <Revealed
            items={rollback.steps}
            render={(s) => (
              <div className="text-[11px]">
                <span className="text-gray-500">[{s.actor}]</span>{" "}
                <span className="font-mono text-gray-400">{s.command}</span>
                <div className="text-[10px] text-gray-600">{s.desc}</div>
              </div>
            )}
          />
        </Block>
      </div>
    </div>
  );
}

// --- 8 · Evidencias y cierre -------------------------------------------------

function EvidenceClosure({ detail }: SceneProps) {
  const audit = detail.artifacts.audit;
  const closed = detail.task.status === "remediated";
  return (
    <div className="space-y-3">
      <Facts>
        <Fact label="Report" value={audit.report_id} hint={`Generated ${audit.generated_at.slice(0, 10)}`} />
        <Fact label="Evidence items" value={<CountUp value={audit.evidences_count} />} accent="#86BC25" />
        <Fact label="Audit trail entries" value={<CountUp value={audit.trace.length} />}
              hint="Chain from finding to closure" />
        <Fact label="Vulnerable Item" value={closed ? "FIXED" : "open"}
              accent={closed ? "#22c55e" : "#f59e0b"}
              hint={closed ? "Closed after accepting the evidence" : "Closes once the evidence is accepted"} />
      </Facts>
      <Block title="Audit trail" sub="Every step is referenced and reproducible.">
        <Revealed
          items={audit.trace}
          render={(t) => (
            <div className="flex items-start gap-2 text-[11px]">
              <span className="text-gray-500 w-28 shrink-0">{t.step}</span>
              <span className="font-mono text-brand shrink-0">{t.ref}</span>
              <span className="text-gray-400">{t.detail}</span>
            </div>
          )}
        />
      </Block>
    </div>
  );
}

/** Escena por fase del journey; el resto de fases reutiliza la más cercana. */
export const SCENES: Record<string, (props: SceneProps) => ReactNode> = {
  cyber_trigger: CyberTrigger,
  asset_identification: AssetConfirmation,
  applicability_assessment: Applicability,
  blast_radius: BlastRadius,
  change_planning: ChangePlanning,
  ring_execution: RingExecution,
  gate_validation: GateValidation,
  evidence_closure: EvidenceClosure,
};
