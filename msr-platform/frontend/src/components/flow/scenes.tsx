import type { ReactNode } from "react";
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
  if (items.length === 0) return <div className="text-[11px] text-gray-600">{empty ?? "Sin elementos."}</div>;
  return (
    <div className="space-y-1.5">
      {shown.map((item, i) => (
        <div key={i} className="animate-fade-in">{render(item, i)}</div>
      ))}
      {shown.length < items.length && (
        <div className="text-[11px] text-gray-600">
          <span className="animate-pulse">▍</span> {items.length - shown.length} por confirmar…
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
        <Fact label="CVSS" value={vi.cvss.toFixed(1)} accent="#ef4444" hint="Severidad técnica" />
        <Fact label="EPSS" value={`${Math.round(vi.epss * 100)}%`} accent="#f59e0b"
              hint="Probabilidad de explotación a 30 días" />
        <Fact label="Explotación" value={vi.kev ? "KEV · activa" : vi.exploit_available ? "Exploit público" : "No observada"}
              accent={vi.kev ? "#ef4444" : "#f59e0b"} hint="CISA KEV y telemetría de amenazas" />
        <Fact label="Exposición" value={vi.exposed ? "Internet" : "Interna"}
              hint={`${vi.environment} · ${vi.criticality}`} />
      </Facts>
      <Block title="Señal recibida desde Cyber / Seguridad"
             sub="El hallazgo llega ya correlacionado; la plataforma lo normaliza y abre el Vulnerable Item.">
        <Revealed
          items={[
            `Fuentes correlacionadas: ${vi.sources.join(" · ")}`,
            `Hallazgo ${vi.cve} sobre ${vi.component} ${vi.vulnerable_version}`,
            `Vulnerable Item ${vi.id} creado y asociado a ${vi.ci_name} (${vi.ci_id})`,
            `Riesgo compuesto ${vi.risk_score}/100 · carril ${detail.lane_meta.label} · SLA ${detail.lane_meta.sla}`,
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
        <Fact label="Activos confirmados" value={<CountUp value={impact.affected_count} />} accent="#86BC25"
              hint="Contrastados contra la CMDB, no sólo declarados por Cyber" />
        <Fact label="Servicios de negocio" value={<CountUp value={impact.business_services.length} />}
              hint={impact.business_services.join(", ") || "—"} />
        <Fact label="Capas implicadas" value={<CountUp value={impact.affected_layers.length} />}
              hint={impact.affected_layers.join(", ")} />
        <Fact label="Relaciones CI→CI" value={<CountUp value={impact.edges.length} />}
              hint="Aristas recorridas en la CMDB" />
      </Facts>
      <Block title="Confirmación contra la CMDB"
             sub="Cada CI se resuelve por relación, no por lista: aparecen a medida que se confirman.">
        <Revealed
          items={impact.nodes}
          render={(n) => (
            <div className="flex items-center gap-2 text-[11px]">
              <ClassTag ciClass={n.ci_class} />
              <span className={n.is_root ? "text-red-300 font-semibold" : "text-gray-300"}>{n.name}</span>
              <span className="text-gray-600">{n.environment}</span>
              {n.is_root && <span className="chip border border-red-500/40 text-red-300">raíz vulnerable</span>}
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
        <Fact label="Tipo de remediación" value={mvt.remediation_type} accent="#86BC25"
              hint={`Reinicio: ${impact.restart_scope} · ${impact.downtime_required ? "con parada" : "sin parada"}`} />
        <Fact label="Confianza del plan" value={`${mvt.confidence}%`} accent="#22c55e"
              hint="Cobertura estimada del conjunto mínimo de pruebas" />
        <Fact label="Pruebas seleccionadas" value={<CountUp value={mvt.selected.length} />}
              hint={`${mvt.excluded.length} descartadas por no aplicables`} />
        <Fact label="Ejecutor" value={detail.artifacts.deployment.executor} hint={detail.artifacts.deployment.strategy} />
      </Facts>
      <Block title="Conjunto mínimo de pruebas (MVT)" sub={mvt.rationale}>
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
        <Fact label="CIs alcanzados" value={`${impact.impacted_count} de ${impact.affected_count}`}
              accent={impact.blast_scope === "propagated" ? "#f97316" : "#22c55e"}
              hint={impact.blast_scope === "propagated" ? "Se propaga a dependientes" : "Impacto local"} />
        <Fact label="Parada de servicio" value={impact.downtime_required ? "Requerida" : "No requerida"}
              hint={`Alcance de reinicio: ${impact.restart_scope}`} />
        <Fact label="Servicios de negocio" value={impact.business_services.join(", ") || "—"} />
        <Fact label="Ventana" value={detail.artifacts.deployment.rings[0]?.plan.window ?? "—"} />
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
        <Fact label="Cambio ITSM" value={itsm?.number ?? detail.journey.change.number} accent="#a855f7"
              hint={itsm?.type_label ?? detail.journey.change.type} />
        <Fact label="Estado" value={itsm?.state ?? detail.journey.change.state} hint={itsm?.approval} />
        <Fact label="Riesgo / impacto" value={itsm?.risk ?? "—"}
              hint={itsm ? `${itsm.impact_level} · ${itsm.affected_cis} CIs` : undefined} />
        <Fact label="Rollback" value={`${rollback.rto_minutes} min RTO`}
              hint={`${rollback.strategy}${rollback.tested_in_lab ? " · probado en laboratorio" : ""}`} />
      </Facts>

      {itsm && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          <Block title="Ciclo del cambio" sub={itsm.detail}>
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
              {itsm.four_eyes && <span className="chip border border-line">doble validación</span>}
              {itsm.gxp && <span className="chip border border-line">GxP</span>}
            </div>
          </Block>
          <Block title="Tareas del cambio (CTASK)" sub="Qué ejecuta el agente y qué queda en manos de una persona.">
            <Revealed
              items={itsm.ctasks}
              render={(c) => (
                <div className="flex items-center gap-2 text-[11px]">
                  <AutomationBadge human={!c.auto} label={c.auto ? "agente" : "persona"} />
                  <span className="text-gray-300">{c.name}</span>
                  <span className="text-gray-600">{c.role}</span>
                </div>
              )}
            />
          </Block>
        </div>
      )}

      <Block title="Secuencia de ejecución planificada"
             sub="Cada anillo tiene su población objetivo, su ventana y su propia aprobación.">
        <Revealed
          items={dep.rings}
          render={(r) => (
            <div className="rounded-lg border border-line bg-ink p-2">
              <div className="flex items-center gap-2 text-[11px]">
                <span className="font-mono text-gray-500">#{r.ring}</span>
                <span className="text-gray-200 font-semibold">{r.label}</span>
                <span className="chip border border-line text-gray-500">{r.plan.assets_count} activos</span>
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
  completed: { label: "completado", color: "#22c55e" },
  in_progress: { label: "en curso", color: "#0ea5e9" },
  rolled_back: { label: "revertido", color: "#f97316" },
  pending: { label: "pendiente", color: "#475569" },
};

function RingCard({ ring }: { ring: Ring }) {
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
        {ring.plan.selected_count}/{ring.plan.assets_count} activos · {ring.plan.window}
      </div>
      <div className="text-[11px]">
        {approval.preapproved
          ? <span className="text-emerald-300">✓ pre-aprobado{approval.approver ? ` · ${approval.approver}` : ""}</span>
          : <span className="text-amber-300">◑ pendiente de pre-aprobación humana</span>}
      </div>
      {ring.simulated && (
        <div className="text-[10px] text-fuchsia-300">simulado · dry-run · sin cambios reales</div>
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
          <span className="chip border border-line">errores {ring.health.error_rate_pct}%</span>
          <span className="chip border border-line">p95 {ring.health.p95_latency_ms} ms</span>
          <span className="chip border border-line">disponibilidad {ring.health.availability_pct}%</span>
        </div>
      )}
    </div>
  );
}

function RingExecution({ detail }: SceneProps) {
  const dep = detail.artifacts.deployment;
  const res = detail.journey.resources;
  return (
    <div className="space-y-3">
      <Facts>
        <Fact label="Anillos desplegados" value={`${detail.rings_done}/${dep.rings.length}`} accent="#0ea5e9" />
        <Fact label="Activos parcheados" value={<CountUp value={res.patched} />} accent="#22c55e"
              hint={`${res.pending} pendientes · ${res.excluded} excluidos`} />
        <Fact label="Ejecutor" value={dep.executor} hint={dep.strategy} />
        <Fact label="Excepciones" value={dep.exceptions.length}
              hint={dep.exceptions[0]?.reason ?? "Sin excepciones registradas"} />
      </Facts>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {dep.rings.map((r) => <RingCard key={r.ring} ring={r} />)}
      </div>
    </div>
  );
}

// --- 7 · Validación de gate y rollback --------------------------------------

function GateValidation({ detail }: SceneProps) {
  const dep = detail.artifacts.deployment;
  const last = [...dep.rings].reverse().find((r) => r.status !== "pending") ?? dep.rings[0];
  const rollback = dep.rollback_plan;
  return (
    <div className="space-y-3">
      <Facts>
        <Fact label="Anillo evaluado" value={last?.label ?? "—"} hint={last?.result} />
        <Fact label="Post-checks" value={last?.post_checks.length ?? 0}
              hint="Comprobaciones ejecutadas antes de promocionar" />
        <Fact label="Rollback" value={dep.rollback.triggered ? "Ejecutado" : dep.rollback.status}
              accent={dep.rollback.triggered ? "#f97316" : "#22c55e"}
              hint={`Disparo automático: ${rollback.auto_trigger}`} />
        <Fact label="Versiones" value={`${rollback.from_version} → ${rollback.target_version}`}
              hint={rollback.snapshot_ref} />
      </Facts>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <Block title="Post-checks del anillo" sub="La promoción sólo se propone si todos pasan.">
          <Revealed
            items={last?.post_checks ?? []}
            render={(c) => <div className="text-[11px] text-gray-300">✓ {c}</div>}
            empty="El anillo todavía no ha publicado post-checks."
          />
        </Block>
        <Block title="Plan de rollback" sub={rollback.strategy}>
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
        <Fact label="Informe" value={audit.report_id} hint={`Generado ${audit.generated_at.slice(0, 10)}`} />
        <Fact label="Evidencias" value={<CountUp value={audit.evidences_count} />} accent="#86BC25" />
        <Fact label="Trazas de auditoría" value={<CountUp value={audit.trace.length} />}
              hint="Cadena hallazgo → cierre" />
        <Fact label="Vulnerable Item" value={closed ? "FIXED" : "abierto"}
              accent={closed ? "#22c55e" : "#f59e0b"}
              hint={closed ? "Cerrado tras aceptar las evidencias" : "Se cierra al aceptar las evidencias"} />
      </Facts>
      <Block title="Cadena de auditoría" sub="Cada paso queda referenciado y es reproducible.">
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
