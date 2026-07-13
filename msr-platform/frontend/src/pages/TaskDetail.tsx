import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "../api";
import type { TaskDetail as TD } from "../types";
import { Priority, Track, Risk, KevTag, PHASE_META } from "../ui";
import ImpactGraphView from "../components/ImpactGraphView";

const PHASE_IDS = ["detection", "prioritization", "pre_implementation", "lab_testing", "prototype", "deployment"];

function Verdict({ v }: { v: string }) {
  const ok = v === "pass";
  return <span className={`chip ${ok ? "bg-green-500/15 text-green-400" : "bg-red-500/15 text-red-400"}`}>{ok ? "PASS" : "FAIL"}</span>;
}

export default function TaskDetail() {
  const { id } = useParams();
  const [d, setD] = useState<TD | null>(null);
  const [sel, setSel] = useState<number>(0);
  const [busy, setBusy] = useState(false);

  const load = () => api.task(id!).then((r) => { setD(r); setSel(r.phase_index); });
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [id]);

  if (!d) return <div className="p-8 text-gray-500">Cargando…</div>;
  const { task, vulnerable_item: vi, artifacts: a } = d;
  const done = task.status === "remediated";
  const currentPhaseId = PHASE_IDS[d.phase_index];
  const selPhaseId = PHASE_IDS[sel];
  const phaseLogs = d.logs.filter((l) => l.phase === selPhaseId);

  const approve = async () => {
    setBusy(true);
    const r = await api.approve(id!);
    setD(r); setSel(r.phase_index); setBusy(false);
  };
  const rollback = async () => {
    setBusy(true);
    const r = await api.rollback(id!);
    setD(r); setSel(r.phase_index); setBusy(false);
  };
  const simulate = async () => {
    setBusy(true);
    const r = await api.simulateIncident(id!);
    setD(r); setSel(r.phase_index); setBusy(false);
  };

  const canApprove = !done && (
    currentPhaseId !== "lab_testing" || a.lab.verdict === "pass"
  );

  return (
    <div className="p-6 space-y-5 max-w-[1400px]">
      <Link to="/tasks" className="text-xs text-gray-500 hover:text-brand">← Remediation Tasks</Link>

      {/* Header */}
      <div className="card p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-mono text-sm text-gray-300">{task.cve}</span>
              <Track t={task.track} />
              <Priority p={task.priority} />
              {vi.kev && <KevTag />}
              {vi.exploit_available && <span className="chip bg-red-500/10 text-red-300 border border-red-500/20">exploit disponible</span>}
              {done && <span className="chip bg-green-500/15 text-green-400">REMEDIADA</span>}
            </div>
            <h1 className="text-xl font-extrabold mt-2">{task.title}</h1>
            <div className="text-sm text-gray-400 mt-1">
              Activo <span className="text-gray-200">{task.ci_name}</span> · {task.environment} · owner {task.owner}
            </div>
          </div>
          <div className="text-right shrink-0">
            <div className="text-xs text-gray-500">Risk score</div>
            <div className="text-4xl font-extrabold"><Risk score={task.risk_score} /><span className="text-lg text-gray-600">/100</span></div>
            <div className="text-xs text-gray-500 mt-1">Change: <span className="text-gray-300">{task.change_type}</span></div>
          </div>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-6 gap-3 mt-4 text-xs">
          <Meta k="CVSS" v={vi.cvss.toFixed(1)} />
          <Meta k="EPSS" v={`${(vi.epss * 100).toFixed(0)}%`} />
          <Meta k="Componente" v={`${vi.component} ${vi.vulnerable_version}`} />
          <Meta k="Expuesto" v={task.exposed ? "Sí (internet)" : "No"} />
          <Meta k="SLA" v={task.sla_due.slice(0, 10)} />
          <Meta k="Fuentes" v={vi.sources.length + " scanners"} />
        </div>
      </div>

      {/* Phase stepper */}
      <div className="card p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="text-sm font-semibold">Ciclo de remediación · 6 fases</div>
          <div className="text-xs text-gray-500">ServiceNow gobierna · Devin ejecuta · HITL en cada transición</div>
        </div>
        <div className="flex items-center">
          {d.phases.map((p, i) => {
            const isCur = i === d.phase_index;
            const st = p.status;
            const color = st === "approved" ? "#22c55e" : isCur ? PHASE_META[p.id].color : "#3f4756";
            return (
              <div key={p.id} className="flex items-center flex-1 last:flex-none">
                <button onClick={() => setSel(i)}
                  className={`flex flex-col items-center gap-1 ${sel === i ? "" : "opacity-80 hover:opacity-100"}`}>
                  <div className="w-9 h-9 rounded-full flex items-center justify-center text-sm font-bold border-2"
                    style={{ borderColor: color, background: sel === i ? color + "22" : "transparent", color }}>
                    {st === "approved" ? "✓" : i + 1}
                  </div>
                  <span className="text-[11px] font-medium" style={{ color: sel === i ? color : "#94a3b8" }}>{p.label}</span>
                </button>
                {i < d.phases.length - 1 && (
                  <div className="flex-1 h-0.5 mx-1 mb-4" style={{ background: st === "approved" ? "#22c55e" : "#2b313d" }} />
                )}
              </div>
            );
          })}
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
        {/* Artifact panel */}
        <div className="xl:col-span-2 space-y-5">
          <PhaseArtifacts phaseId={selPhaseId} d={d} />
        </div>

        {/* Agent + HITL column */}
        <div className="space-y-5">
          <div className="card overflow-hidden">
            <div className="px-4 py-3 border-b border-line flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-brand animate-pulse" />
              <div className="text-sm font-semibold">Devin · {PHASE_META[selPhaseId].label}</div>
            </div>
            <div className="p-3 space-y-2 max-h-[300px] overflow-y-auto">
              {phaseLogs.map((l, i) => (
                <div key={i} className="text-xs flex gap-2">
                  <span className={`chip shrink-0 h-fit ${l.actor === "Devin" ? "bg-brand/15 text-brand" : l.actor.includes("Owner") || l.actor.includes("HITL") ? "bg-amber-500/15 text-amber-300" : "bg-sky-500/15 text-sky-300"}`}>
                    {l.actor}
                  </span>
                  <span className="text-gray-400 leading-relaxed">{l.msg}</span>
                </div>
              ))}
              {phaseLogs.length === 0 && <div className="text-xs text-gray-600">Fase pendiente. El agente trabajará al llegar aquí.</div>}
            </div>
          </div>

          {/* HITL control */}
          <div className="card p-4">
            <div className="text-sm font-semibold mb-1">Aprobación humana (HITL)</div>
            {done ? (
              <div className="space-y-3">
                <div className="text-xs text-green-400">Tarea remediada. Vulnerable Item cerrado con evidencia de auditoría.</div>
                <div className="text-xs text-gray-400">¿Anomalía detectada en producción tras el despliegue? Puedes ejecutar un rollback.</div>
                <button disabled={busy} onClick={rollback}
                  className="btn w-full justify-center btn-ghost border border-amber-500/40 text-amber-300 hover:bg-amber-500/10">
                  {busy ? "Procesando…" : "⟲ Ejecutar rollback del último anillo"}
                </button>
              </div>
            ) : (
              <>
                <div className="text-xs text-gray-400 mb-3">
                  Fase actual: <span className="font-semibold" style={{ color: PHASE_META[currentPhaseId].color }}>{PHASE_META[currentPhaseId].label}</span>.
                  {currentPhaseId === "deployment"
                    ? ` Aprobar despliega el siguiente anillo (${d.rings_done}/5 completados).`
                    : " Devin propone; el owner aprueba para avanzar."}
                </div>
                {!canApprove && currentPhaseId === "lab_testing" && (
                  <div className="text-xs text-red-400 mb-2">⚠ El MVT ha fallado en laboratorio. ServiceNow bloquea el avance (rollback / análisis).</div>
                )}
                <button disabled={busy || !canApprove} onClick={approve}
                  className={`btn w-full justify-center ${canApprove ? "btn-brand" : "btn-ghost opacity-50 cursor-not-allowed"}`}>
                  {busy ? "Procesando…" : currentPhaseId === "deployment" ? "Aprobar y desplegar anillo" : "Aprobar fase y avanzar"}
                </button>
                {currentPhaseId === "deployment" && d.rings_done > 0 && (
                  <div className="mt-3 pt-3 border-t border-line space-y-2">
                    <div className="text-[11px] text-gray-500">Gestión de rollback (anillo {d.rings_done} desplegado)</div>
                    <button disabled={busy} onClick={rollback}
                      className="btn w-full justify-center btn-ghost border border-amber-500/40 text-amber-300 hover:bg-amber-500/10 text-xs">
                      ⟲ Rollback manual del anillo
                    </button>
                    <button disabled={busy} onClick={simulate}
                      className="btn w-full justify-center btn-ghost border border-red-500/40 text-red-300 hover:bg-red-500/10 text-xs">
                      ⚠ Simular incidente → rollback automático
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function Meta({ k, v }: { k: string; v: string }) {
  return (
    <div className="bg-ink rounded-lg px-3 py-2 border border-line">
      <div className="text-[10px] text-gray-500 uppercase tracking-wide">{k}</div>
      <div className="text-gray-200 font-medium mt-0.5">{v}</div>
    </div>
  );
}

// -------------------- per-phase artifacts --------------------
function PhaseArtifacts({ phaseId, d }: { phaseId: string; d: TD }) {
  const { artifacts: a, task, vulnerable_item: vi } = d;

  if (phaseId === "detection")
    return (
      <Panel title="Fase 1 · Detección e ingesta" sub="ServiceNow Vulnerability Response — normalización y correlación con CMDB">
        <div className="grid grid-cols-2 gap-3 text-sm">
          <Meta k="Vulnerable Item" v={vi.id} />
          <Meta k="Detectado" v={vi.detected_at.slice(0, 10)} />
          <Meta k="Identificador" v={vi.cve} />
          <Meta k="CI asociado" v={`${vi.ci_id} (${vi.ci_class})`} />
        </div>
        <div className="mt-3">
          <div className="text-xs text-gray-500 mb-1">Fuentes correlacionadas (deduplicadas)</div>
          <div className="flex flex-wrap gap-2">
            {vi.sources.map((s) => <span key={s} className="chip bg-ink-panel text-gray-300 border border-line">{s}</span>)}
          </div>
        </div>
      </Panel>
    );

  if (phaseId === "prioritization")
    return (
      <Panel title="Fase 2 · Priorización" sub="Prioridad = riesgo técnico + negocio + operativo + SLA (no solo CVSS)">
        <div className="space-y-2">
          {[
            ["Riesgo técnico (CVSS)", vi.cvss * 4, 40, `CVSS ${vi.cvss}`],
            ["Explotabilidad (EPSS/KEV)", vi.epss * 20 + (vi.kev ? 12 : 0), 32, `EPSS ${(vi.epss * 100).toFixed(0)}% ${vi.kev ? "· KEV" : ""}`],
            ["Contexto de negocio", { critical: 18, high: 12, medium: 6, low: 2 }[task.criticality] || 6, 18, `${task.criticality}`],
            ["Exposición", task.exposed ? 10 : 0, 10, task.exposed ? "Internet-facing" : "Interno"],
          ].map(([label, val, max, note]: any) => (
            <div key={label}>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-gray-300">{label} <span className="text-gray-600">· {note}</span></span>
                <span className="font-mono text-gray-400">{Math.round(val)}/{max}</span>
              </div>
              <div className="h-2 rounded bg-ink"><div className="h-2 rounded bg-brand" style={{ width: `${(val / max) * 100}%` }} /></div>
            </div>
          ))}
        </div>
        <div className="mt-4 p-3 rounded-lg bg-ink border border-line text-sm">
          <div className="text-xs text-brand font-semibold mb-1">Reachability analysis (Devin)</div>
          {task.track === "B"
            ? <span className="text-gray-300">Devin analizó el repositorio <span className="font-mono text-xs">{task.ci_name}</span>: el componente <span className="font-mono text-xs">{vi.component}</span> {task.exposed ? "ES alcanzable en runtime → mantiene prioridad alta." : "no es alcanzable directamente → candidato a excepción documentada."}</span>
            : task.track === "C"
            ? <span className="text-gray-300">Devin analizó la imagen/manifiestos de <span className="font-mono text-xs">{task.ci_name}</span>: <span className="font-mono text-xs">{vi.component}</span> presente en la imagen base {task.exposed ? "y expuesto vía ingress → prioridad alta; requiere rebuild de imagen." : "sin exposición directa → rebuild programado en ventana."}</span>
            : <span className="text-gray-300">Activo de infraestructura {task.exposed ? "expuesto a internet" : "interno"}; prioridad ajustada por ventana de mantenimiento y criticidad del servicio.</span>}
        </div>
      </Panel>
    );

  if (phaseId === "pre_implementation")
    return (
      <>
        <Panel title="Fase 3 · Impact Graph (blast radius)" sub={`Devin enriqueció el grafo desde CMDB + repos/SBOM · ${a.impact.affected_count} CIs, capas: ${a.impact.affected_layers.join(", ")}`}>
          <ImpactGraphView nodes={a.impact.nodes} edges={a.impact.edges} height={360} />
          {a.impact.business_services.length > 0 && (
            <div className="mt-2 text-xs text-gray-400">Servicios de negocio impactados: <span className="text-purple-300">{a.impact.business_services.join(", ")}</span></div>
          )}
        </Panel>
        <Panel title="Minimum Viable Test Plan (MVT)" sub={a.mvt.rationale}>
          <div className="flex items-center gap-3 mb-3">
            <div className="chip bg-brand/15 text-brand">Confianza {a.mvt.confidence}%</div>
            <div className="chip bg-green-500/15 text-green-400">{a.mvt.selected.length} incluidas</div>
            <div className="chip bg-gray-500/15 text-gray-400">{a.mvt.excluded.length} excluidas</div>
          </div>
          <TestTable rows={a.mvt.selected} included />
          <details className="mt-3">
            <summary className="text-xs text-gray-500 cursor-pointer">Ver pruebas excluidas y justificación</summary>
            <div className="mt-2"><TestTable rows={a.mvt.excluded} /></div>
          </details>
        </Panel>
      </>
    );

  if (phaseId === "lab_testing")
    return (
      <Panel title="Fase 4 · Ejecución de pruebas en laboratorio" sub="Devin genera y ejecuta el MVT vía CI/CD y frameworks de test">
        <div className="flex items-center gap-3 mb-4">
          <span className="text-sm">Veredicto agregado:</span> <Verdict v={a.lab.verdict} />
          <span className="text-xs text-gray-400 ml-auto">{a.lab.passed}/{a.lab.total} pruebas OK</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <ResultGroup title="Pruebas de parche" rows={a.lab.patch_tests} />
          <ResultGroup title="Pruebas de aplicación" rows={a.lab.app_tests} />
        </div>
      </Panel>
    );

  if (phaseId === "prototype")
    return (
      <Panel title="Fase 5 · Validación en entorno de prototipo" sub={`Devin aprovisiona un lab (${a.prototype.approach}) con IaC derivado del Impact Graph`}>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          <Meta k="Enfoque" v={a.prototype.approach} />
          <Meta k="Provisión" v={a.prototype.provision_tool} />
          <Meta k="Teardown" v={a.prototype.teardown} />
          <Meta k="Veredicto" v={a.prototype.verdict.toUpperCase()} />
        </div>
        <div className="text-xs text-gray-500 mb-1">Lab Blueprint (componentes aprovisionados)</div>
        <div className="space-y-1 mb-4">
          {a.prototype.lab_blueprint.map((c, i) => (
            <div key={i} className="flex items-center gap-2 text-sm bg-ink rounded-lg px-3 py-1.5 border border-line">
              <span className="chip bg-teal-500/15 text-teal-300">{c.tool}</span>
              <span className="text-gray-300">{c.type}</span>
              <span className="text-gray-500 text-xs ml-auto font-mono">{c.spec}</span>
            </div>
          ))}
        </div>
        <div className="grid grid-cols-4 gap-3">
          {Object.entries(a.prototype.metrics).map(([k, v]) => (
            <Meta key={k} k={k.replace(/_/g, " ")} v={String(v)} />
          ))}
        </div>
      </Panel>
    );

  // deployment
  const rb = a.deployment.rollback;
  return (
    <>
      <Panel title="Fase 6 · Despliegue por anillos" sub={`Estrategia ${a.deployment.strategy} · ejecutor: ${a.deployment.executor} · ${a.deployment.total_assets} activos`}>
        {a.deployment.pr_url && (
          <a href={a.deployment.pr_url} target="_blank" className="chip bg-emerald-500/15 text-emerald-300 mb-3 inline-flex">PR de remediación: {a.deployment.pr_url.split("/").slice(-2).join("/")}</a>
        )}
        <div className="space-y-2">
          {a.deployment.rings.map((r) => (
            <RingRow key={r.ring} r={r} />
          ))}
        </div>
        {a.deployment.exceptions.length > 0 && (
          <div className="mt-4">
            <div className="text-xs text-gray-500 mb-1">Excepciones trazables</div>
            {a.deployment.exceptions.map((e, i) => (
              <div key={i} className="text-xs bg-amber-500/10 border border-amber-500/20 rounded-lg px-3 py-2 text-amber-200">
                <span className="font-mono">{e.asset}</span> — {e.reason}. Control compensatorio: {e.compensating_control}. Expira {e.expires.slice(0, 10)}.
              </div>
            ))}
          </div>
        )}
      </Panel>

      <Panel title="Gestión de Rollback" sub={`Plan armado desde el inicio y probado en lab · estrategia: ${a.deployment.rollback_plan.strategy}`}>
        {rb.triggered && (
          <div className="mb-4 rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3">
            <div className="flex items-center gap-2 mb-1">
              <span className="chip bg-amber-500/20 text-amber-300">ROLLBACK EJECUTADO</span>
              <span className="chip bg-ink-panel text-gray-400">{rb.trigger_type === "auto" ? "automático" : "manual"}</span>
              <span className="text-xs text-gray-500 ml-auto">anillo {rb.ring}</span>
            </div>
            <div className="text-xs text-amber-200">{rb.reason}</div>
            <div className="text-xs text-gray-400 mt-1">Versión restaurada: <span className="font-mono text-gray-200">{rb.restored_version}</span> · {rb.verdict}</div>
          </div>
        )}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          <Meta k="Estrategia" v={a.deployment.rollback_plan.strategy} />
          <Meta k="RTO objetivo" v={`${a.deployment.rollback_plan.rto_minutes} min`} />
          <Meta k="Versión estable" v={a.deployment.rollback_plan.target_version} />
          <Meta k="Probado en lab" v={a.deployment.rollback_plan.tested_in_lab ? "Sí" : "No"} />
        </div>
        <div className="text-xs text-gray-500 mb-1">Disparo automático: {a.deployment.rollback_plan.auto_trigger}</div>
        <div className="text-xs text-gray-500 mb-1 mt-3">Pasos del plan de rollback</div>
        <div className="space-y-1">
          {a.deployment.rollback_plan.steps.map((s, i) => (
            <div key={i} className="flex items-start gap-2 text-xs bg-ink rounded-lg px-3 py-2 border border-line">
              <span className="chip bg-amber-500/15 text-amber-300 shrink-0">{i + 1}</span>
              <span className={`chip shrink-0 ${s.actor === "Devin" ? "bg-brand/15 text-brand" : "bg-sky-500/15 text-sky-300"}`}>{s.actor}</span>
              <div className="flex-1">
                <code className="text-gray-200">{s.command}</code>
                <div className="text-gray-500 mt-0.5">{s.desc}</div>
              </div>
            </div>
          ))}
        </div>
      </Panel>

      <Panel title="Informe de auditoría (audit-ready)" sub={`Devin genera el informe automáticamente · ${a.audit.report_id} · ${a.audit.evidences_count} evidencias${a.audit.dora_relevant ? " · DORA relevante" : ""}`}>
        <div className="space-y-1">
          {a.audit.trace.map((t, i) => (
            <div key={i} className="flex items-center gap-3 text-sm">
              <span className="w-2 h-2 rounded-full bg-brand shrink-0" />
              <span className="text-gray-300 w-40 shrink-0">{t.step}</span>
              <span className="font-mono text-xs text-gray-500 w-40 shrink-0 truncate">{t.ref}</span>
              <span className="text-gray-400 text-xs">{t.detail}</span>
            </div>
          ))}
        </div>
      </Panel>
    </>
  );
}

function RingRow({ r }: { r: any }) {
  const [open, setOpen] = useState(false);
  const hasActions = r.actions && r.actions.steps.length > 0;
  const statusChip =
    r.status === "completed" ? "bg-green-500/15 text-green-400"
    : r.status === "rolled_back" ? "bg-amber-500/15 text-amber-300"
    : r.status === "in_progress" ? "bg-sky-500/15 text-sky-300"
    : "bg-gray-500/15 text-gray-400";
  const icon =
    r.status === "completed" ? "✓" : r.status === "rolled_back" ? "⟲" : r.status === "in_progress" ? "▶" : "·";
  return (
    <div className="bg-ink rounded-lg border border-line">
      <button onClick={() => hasActions && setOpen(!open)}
        className={`w-full flex items-center gap-3 px-3 py-2 text-left ${hasActions ? "cursor-pointer" : "cursor-default"}`}>
        <span className={`chip ${statusChip}`}>{icon}</span>
        <div className="flex-1">
          <div className="text-sm text-gray-200">{r.label}</div>
          {r.health && (
            <div className="text-[11px] text-gray-500">
              err {r.health.error_rate_pct}% · p95 {r.health.p95_latency_ms}ms · avail {r.health.availability_pct}%
            </div>
          )}
        </div>
        <span className="text-xs text-gray-400">{r.assets} activos</span>
        {r.result !== "-" && (
          <span className={`chip ${r.status === "rolled_back" ? "bg-amber-500/10 text-amber-300" : "bg-green-500/10 text-green-400"}`}>{r.result}</span>
        )}
        {hasActions && <span className="text-gray-500 text-xs w-4">{open ? "▾" : "▸"}</span>}
      </button>
      {open && hasActions && (
        <div className="border-t border-line px-3 py-2 space-y-1 font-mono text-[11px]">
          <div className="text-gray-500 mb-1">Acciones ejecutadas · {r.actions.from_version} → {r.actions.to_version}</div>
          {r.actions.steps.map((s: any) => (
            <div key={s.seq} className="flex items-start gap-2">
              <span className={`chip shrink-0 ${s.actor === "Devin" ? "bg-brand/15 text-brand" : s.tool === "post-check" ? "bg-purple-500/15 text-purple-300" : "bg-sky-500/15 text-sky-300"}`}>{s.actor}</span>
              <div className="flex-1 min-w-0">
                <div className="text-gray-300 truncate">$ {s.command}</div>
                <div className="text-gray-500 truncate">→ {s.output}</div>
              </div>
              <span className="text-green-400 shrink-0">ok</span>
              <span className="text-gray-600 shrink-0">{s.duration_s}s</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Panel({ title, sub, children }: { title: string; sub?: string; children: React.ReactNode }) {
  return (
    <div className="card p-5">
      <div className="mb-3">
        <div className="text-sm font-semibold text-gray-100">{title}</div>
        {sub && <div className="text-xs text-gray-500 mt-0.5 leading-relaxed">{sub}</div>}
      </div>
      {children}
    </div>
  );
}

function TestTable({ rows, included }: { rows: any[]; included?: boolean }) {
  return (
    <div className="overflow-hidden rounded-lg border border-line">
      <table className="w-full text-xs">
        <tbody>
          {rows.map((t) => (
            <tr key={t.id} className="border-b border-line/40 last:border-0">
              <td className="px-3 py-2 font-mono text-gray-500 w-24">{t.id}</td>
              <td className="px-2 py-2 text-gray-200">{t.name}</td>
              <td className="px-2 py-2"><span className="chip bg-ink-panel text-gray-400">{t.layer}</span></td>
              <td className="px-2 py-2 text-gray-500">{t.tool}</td>
              {!included && <td className="px-3 py-2 text-gray-600 max-w-[220px]">{t.reason}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ResultGroup({ title, rows }: { title: string; rows: any[] }) {
  return (
    <div>
      <div className="text-xs text-gray-500 mb-2">{title}</div>
      <div className="space-y-1">
        {rows.length === 0 && <div className="text-xs text-gray-600">—</div>}
        {rows.map((r) => (
          <div key={r.test_id} className="flex items-center gap-2 text-xs bg-ink rounded-lg px-3 py-1.5 border border-line">
            <span className={`w-2 h-2 rounded-full ${r.status === "pass" ? "bg-green-400" : "bg-red-400"}`} />
            <span className="text-gray-200">{r.name}</span>
            <span className="text-gray-600 ml-auto">{r.duration_s}s</span>
          </div>
        ))}
      </div>
    </div>
  );
}
