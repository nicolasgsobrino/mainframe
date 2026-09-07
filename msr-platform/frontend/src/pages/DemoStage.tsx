import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { HitlGate, JourneyDetail, LogEntry, Task, TaskDetail } from "../types";
import { LaneTag, Priority, Risk } from "../ui";
import {
  ExecutionTheatre, HitlCounter, HitlRail, LogConsole, NextActionBar, nextDemoStep, stepTone,
  type DemoStep, type ExecLine,
} from "../components/flow";
import { SCENES } from "../components/flow/scenes";
import { useDemo, useReportExecution } from "../demo";
import { useView, ROLE_META } from "../view";
import { JOURNEY_BAND_COLOR } from "../components/journey/JourneyBoard";

type Phase = JourneyDetail["phases"][number];

/** Guion de la presentación: qué se cuenta en cada escena y quién la ejecuta. */
const SCRIPT: Record<string, { pitch: string; automation: string }> = {
  cyber_trigger: {
    pitch: "Cyber envía el hallazgo ya correlacionado; la plataforma lo normaliza, lo puntúa y abre el Vulnerable Item.",
    automation: "Ingesta y scoring automáticos",
  },
  asset_identification: {
    pitch: "No confiamos en la lista recibida: cada activo se contrasta contra la CMDB antes de tocar nada.",
    automation: "Correlación automática · confirmación humana",
  },
  applicability_assessment: {
    pitch: "Se decide el tipo de remediación y el conjunto mínimo de pruebas que da confianza sin frenar el despliegue.",
    automation: "Propuesta de IA · validada por una persona",
  },
  blast_radius: {
    pitch: "Qué se rompe si esto sale mal: alcance real del cambio siguiendo las dependencias del grafo.",
    automation: "Cálculo automático sobre la CMDB",
  },
  change_planning: {
    pitch: "El cambio ITSM, su ventana, sus tareas y la secuencia de anillos quedan armados antes de ejecutar.",
    automation: "Plan automático · aprobación del cambio",
  },
  ring_execution: {
    pitch: "Despliegue por anillos: cada lote se pre-aprueba, se ejecuta y publica su evidencia antes de promocionar.",
    automation: "Ejecución del agente · una aprobación por anillo",
  },
  gate_validation: {
    pitch: "Post-checks, salud del servicio y rollback armado: la promoción sólo se propone si el anillo está sano.",
    automation: "Verificación automática · validación humana",
  },
  evidence_closure: {
    pitch: "Trazabilidad completa de hallazgo a cierre; el Vulnerable Item se cierra al aceptar las evidencias.",
    automation: "Informe automático · aceptación humana",
  },
};

/**
 * Lo que la acción acaba de provocar por detrás, en el orden en que ocurrió:
 * los comandos del anillo que se ha desplegado y las entradas de log que el
 * backend ha escrito con esta acción. Nada de esto es inventado por la UI.
 */
function playbackLines(step: DemoStep, before: LogEntry[], next: TaskDetail): ExecLine[] {
  const seen = new Set(before.map((l) => `${l.ts ?? ""}|${l.actor}|${l.msg}`));
  const lines: ExecLine[] = [];

  if (step.kind === "deploy" && step.ring !== null) {
    const ring = next.artifacts.deployment.rings.find((r) => r.ring === step.ring);
    ring?.actions?.steps.forEach((s) => {
      lines.push({ actor: s.actor, text: s.why ?? s.tool, detail: `$ ${s.command}` });
      if (s.output) {
        lines.push({
          actor: s.tool, text: s.output,
          detail: `${s.status} · ${s.duration_s}s`,
          status: s.status === "ok" || s.status === "success" ? "ok" : "warn",
        });
      }
    });
    ring?.post_checks.forEach((c) => lines.push({ actor: "Post-check", text: c }));
  }

  next.logs
    .filter((l) => !seen.has(`${l.ts ?? ""}|${l.actor}|${l.msg}`))
    .forEach((l) => lines.push({ actor: l.actor, text: l.msg, detail: l.phase }));

  return lines;
}

/** Título de la reproducción según lo que se acaba de ejecutar. */
const PLAYBACK_TITLE: Record<DemoStep["kind"], (s: DemoStep) => string> = {
  verify: (s) => `Validación humana registrada · ${s.gate?.label ?? ""}`,
  preapprove: (s) => `Anillo ${s.ring} pre-aprobado · informe pre-anillo aceptado`,
  deploy: (s) => `Desplegando el anillo ${s.ring}`,
  rollback: (s) => `Rollback del anillo ${s.ring} · restaurando la versión estable`,
  approve: (s) => s.gate?.verdict
    ? `${s.gate.verdict} · la plataforma prepara los artefactos siguientes`
    : "Fase aprobada · la plataforma prepara los artefactos siguientes",
  done: () => "Recorrido completado",
};

/** Escena donde vive la acción pendiente, para señalarla en el stepper. */
function actionPhaseOf(step: DemoStep, j: JourneyDetail): string | null {
  if (step.kind === "done") return null;
  if (step.kind === "verify") return step.gate?.phase ?? null;
  if (step.kind === "approve") return j.phase;
  if (step.kind === "rollback") return "gate_validation";
  return "ring_execution";
}

function SceneStepper({ phases, current, actionPhase, actionAccent, onSelect }: {
  phases: Phase[];
  current: string;
  /** Escena donde vive la acción pendiente: se resalta sin etiquetas. */
  actionPhase: string | null;
  actionAccent: string;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 xl:grid-cols-8 gap-2">
      {phases.map((p) => {
        const color = JOURNEY_BAND_COLOR[p.band];
        const active = p.id === current;
        const done = p.status === "completed";
        const isAction = p.id === actionPhase;
        return (
          <button
            key={p.id}
            type="button"
            onClick={() => onSelect(p.id)}
            aria-pressed={active}
            title={`${p.label_en} · ${p.status}`}
            className={`relative rounded-lg border-2 p-2 text-left transition-colors ${
              active ? "bg-ink-panel" : "bg-ink hover:bg-ink-panel"} ${
              isAction ? "scale-[1.03]" : ""}`}
            style={{
              borderColor: isAction ? actionAccent : active ? color : done ? color + "55" : "#2b313d",
              background: isAction ? actionAccent + "14" : undefined,
              boxShadow: isAction ? `0 0 0 3px ${actionAccent}26, 0 0 18px ${actionAccent}40` : undefined,
            }}
          >
            {isAction && (
              <span className="absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full animate-pulse"
                    style={{ background: actionAccent }} aria-hidden />
            )}
            <div className="flex items-center gap-1.5">
              <span className="w-4 h-4 rounded-full text-[9px] font-bold flex items-center justify-center"
                    style={{
                      background: done ? color : active ? color + "33" : "#1b1f27",
                      color: done ? "#0b0d11" : active ? color : "#64748b",
                      border: `1px solid ${done || active ? color : "#2b313d"}`,
                    }}>
                {done ? "✓" : p.index + 1}
              </span>
              {p.gates.length > 0 && (
                <span className={`ml-auto text-[10px] ${p.gates_pending > 0 ? "text-amber-300" : "text-gray-600"}`}
                      title={p.gates.map((g) => g.label).join(" · ")}>
                  ◑{p.gates_pending > 0 ? ` ${p.gates_pending}` : ""}
                </span>
              )}
            </div>
            <div className={`text-[11px] leading-snug mt-1 ${active ? "text-gray-100 font-semibold" : "text-gray-400"}`}>
              {p.label}
            </div>
            {p.status === "current" && <div className="text-[10px]" style={{ color }}>en curso</div>}
          </button>
        );
      })}
    </div>
  );
}

function VulnPicker({ tasks, selected, onSelect }: {
  tasks: Task[]; selected: string; onSelect: (id: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {tasks.map((t) => {
        const active = t.id === selected;
        const closed = t.status === "remediated";
        return (
          <button
            key={t.id}
            type="button"
            onClick={() => onSelect(t.id)}
            aria-pressed={active}
            title={t.title}
            className={`rounded-lg border px-3 py-1.5 text-left transition-colors ${
              active
                ? "border-fuchsia-500/50 bg-fuchsia-500/10"
                : "border-line bg-ink hover:bg-ink-panel"}`}
          >
            <div className="flex items-center gap-2">
              <span className={`font-mono text-[11px] ${active ? "text-fuchsia-200" : "text-gray-300"}`}>{t.cve}</span>
              <span className={`w-1.5 h-1.5 rounded-full ${closed ? "bg-emerald-400" : "bg-amber-400"}`} />
            </div>
            <div className="text-[10px] text-gray-500 leading-tight">
              {closed ? "remediada" : `fase ${t.journey.phase_index + 1}/8 · ${t.journey.phase_label}`}
            </div>
          </button>
        );
      })}
    </div>
  );
}

/** Portada: el Modo Demo es la condición de entrada del recorrido guiado. */
function Curtain() {
  const { allowed, reason, setEnabled } = useDemo();
  return (
    <div className="p-6">
      <div className="card p-8 max-w-2xl mx-auto text-center space-y-4">
        <div className="text-xs tracking-[0.2em] text-fuchsia-300">PRESENTACIÓN GUIADA</div>
        <h1 className="text-2xl font-bold text-gray-100">Del hallazgo de Cyber al cierre con evidencias</h1>
        <p className="text-sm text-gray-400 leading-relaxed">
          Ocho escenas sobre los datos reales del backend, con los puntos de control humano marcados
          y el ritmo en manos del presentador. Ninguna acción muta recursos en AWS.
        </p>
        {allowed ? (
          <button type="button" onClick={() => setEnabled(true)} className="btn btn-brand mx-auto">
            ◉ Activar Modo Demo y empezar
          </button>
        ) : (
          <div className="text-xs text-amber-300">{reason}</div>
        )}
      </div>
    </div>
  );
}

/**
 * Recorrido guiado del Patching Journey: una escena por fase, el carril
 * humano siempre visible y un único siguiente paso. Toda la información sale
 * de `/api/tasks/{id}`; la pantalla no mantiene estado propio del flujo.
 */
export default function DemoStage() {
  const { active } = useDemo();
  const { role } = useView();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [detail, setDetail] = useState<TaskDetail | null>(null);
  const [pinned, setPinned] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [resetting, setResetting] = useState(false);
  const [armed, setArmed] = useState(false);
  const [running, setRunning] = useState(false);
  const [playback, setPlayback] = useState<{ title: string; subtitle: string; lines: ExecLine[] } | null>(null);
  const [replaying, setReplaying] = useState(false);
  // Paso lanzado cuya reproducción todavía no se puede montar: el job del
  // anillo sigue en vuelo y su evidencia aún no está publicada.
  const pending = useRef<{ step: DemoStep; before: LogEntry[] } | null>(null);

  useReportExecution(detail?.execution ?? null);

  useEffect(() => {
    api.tasks().then((all) => {
      setTasks(all);
      setTaskId((current) => current ?? (all.find((t) => t.status !== "remediated") ?? all[0])?.id ?? null);
    }).catch(() => setError("No se pudo cargar la lista de vulnerabilidades."));
  }, []);

  const load = useCallback((id: string) => {
    api.task(id).then(setDetail).catch(() => setError("No se pudo cargar el recorrido."));
  }, []);

  useEffect(() => {
    if (!taskId) return;
    setDetail(null);
    load(taskId);
  }, [taskId, load]);

  // Un job en vuelo mueve el recorrido por su cuenta: se refresca hasta que
  // el backend publica el estado terminal.
  useEffect(() => {
    const job = detail?.active_job;
    if (!taskId || !job || job.terminal) return;
    const timer = setInterval(() => load(taskId), 4000);
    return () => clearInterval(timer);
  }, [detail?.active_job, taskId, load]);

  const phase = detail?.journey.phase;
  // Al avanzar el recorrido la escena vuelve a seguir al flujo real.
  useEffect(() => { setPinned(null); }, [phase]);

  // El detalle no publica la posición del journey en su resumen de tarea, así
  // que el selector se repuebla desde la lista para reflejar la fase nueva.
  const apply = useCallback((next: TaskDetail) => {
    setDetail(next);
    api.tasks().then(setTasks).catch(() => undefined);
  }, []);

  // Rehace el escenario sintético (3 resueltas + 2 pendientes) para volver a
  // presentar desde cero. Sólo toca el store de la demo, nunca AWS.
  const resetDemo = useCallback(() => {
    setResetting(true);
    // La reproducción en curso pertenece al recorrido que se está tirando.
    pending.current = null;
    setPlayback(null);
    setReplaying(false);
    api.resetScenario()
      .then(() => api.tasks())
      .then((all) => {
        setTasks(all);
        setPinned(null);
        const first = all.find((t) => t.status !== "remediated") ?? all[0];
        setTaskId(first?.id ?? null);
        if (first) load(first.id);
      })
      .catch(() => setError("No se pudo reiniciar el escenario de la demo."))
      .finally(() => { setResetting(false); setArmed(false); });
  }, [load]);

  // La reproducción se monta cuando el backend ha terminado: en mock eso es
  // inmediato, pero un anillo real publica su evidencia al cerrar el job.
  useEffect(() => {
    const waiting = pending.current;
    const job = detail?.active_job;
    if (!waiting || !detail || (job && !job.terminal)) return;
    pending.current = null;
    setPlayback({
      title: PLAYBACK_TITLE[waiting.step.kind](waiting.step),
      subtitle: stepTone(waiting.step) === "human"
        ? `Decisión registrada como ${ROLE_META[role].label} · el flujo queda desbloqueado`
        : "Ejecución del agente reproducida paso a paso",
      lines: playbackLines(waiting.step, waiting.before, detail),
    });
  }, [detail, role]);

  const gatesByPhase = useMemo(() => {
    const map = new Map<string, HitlGate[]>();
    detail?.journey.gates.forEach((g) => map.set(g.phase, [...(map.get(g.phase) ?? []), g]));
    return map;
  }, [detail]);

  if (!active) return <Curtain />;
  if (error) return <div className="p-6 text-sm text-red-300">{error}</div>;
  if (!detail || !taskId) return <div className="p-6 text-xs text-gray-500">Preparando la presentación…</div>;

  const j = detail.journey;
  const sceneId = pinned ?? j.phase;
  const scenePhase = j.phases.find((p) => p.id === sceneId) ?? j.phases[0];
  const Scene = SCENES[scenePhase.id];
  const script = SCRIPT[scenePhase.id];
  const gates = gatesByPhase.get(scenePhase.id) ?? [];
  const step = nextDemoStep(detail);
  const job = detail.active_job ?? null;
  // El siguiente paso espera a que termine lo anterior: job real en vuelo o
  // reproducción en curso (el presentador puede saltarla).
  const busy = running || replaying || (job !== null && !job.terminal);
  const actionPhase = actionPhaseOf(step, j);
  const color = JOURNEY_BAND_COLOR[scenePhase.band];

  const verifyGate = (gate: HitlGate) =>
    api.verifyGate(taskId, gate.id, { ring: gate.ring, role }).then(apply);

  const call = (s: DemoStep): Promise<TaskDetail> => {
    if (s.kind === "verify" && s.gate) return api.verifyGate(taskId, s.gate.id, { ring: s.gate.ring, role });
    if (s.kind === "preapprove" && s.ring !== null) return api.preapproveRing(taskId, s.ring);
    return api.approve(taskId, detail.rings_done + 1);
  };

  // Rollback del anillo desplegado: misma mecánica que el resto de acciones
  // (job del backend + reproducción), disparada desde la tarjeta del anillo.
  const rollbackRing = (ring: number) => {
    if (busy) return;
    const label = detail.artifacts.deployment.rings.find((r) => r.ring === ring)?.label ?? "";
    const s: DemoStep = {
      kind: "rollback", ring, gate: null,
      label: `Revertir el anillo ${ring} · ${label}`,
      hint: "Restaura la versión estable del lote y devuelve el anillo al estado previo al despliegue.",
    };
    setRunning(true);
    setPlayback(null);
    setReplaying(true);
    pending.current = { step: s, before: detail.logs };
    api.rollback(taskId, ring)
      .then(apply)
      .catch(() => {
        pending.current = null;
        setReplaying(false);
        setError("El rollback no se pudo completar; el anillo sigue como estaba.");
      })
      .finally(() => setRunning(false));
  };

  // Una sola acción para toda la pantalla: ejecuta el paso y reproduce con
  // ritmo lo que el backend ha hecho, que en mock ocurre en milisegundos.
  const act = () => {
    if (busy || step.kind === "done") return;
    setRunning(true);
    setPlayback(null);
    setReplaying(true);
    pending.current = { step, before: detail.logs };
    call(step)
      .then(apply)
      .catch(() => {
        pending.current = null;
        setReplaying(false);
        setError("La acción no se pudo completar; el flujo sigue detenido.");
      })
      .finally(() => setRunning(false));
  };

  return (
    <div className="p-6 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-[10px] tracking-[0.2em] text-fuchsia-300">PRESENTACIÓN GUIADA</div>
          <h1 className="text-xl font-bold text-gray-100 leading-tight">{j.cve} · {j.title}</h1>
          <div className="flex flex-wrap items-center gap-2 mt-1.5">
            <Risk score={j.risk_score} />
            <Priority p={j.priority} />
            <LaneTag lane={j.lane} />
            <span className="text-xs text-gray-500">{j.ci_name}</span>
            <span className="chip border border-line text-gray-500">{ROLE_META[role].label}</span>
          </div>
        </div>
        <div className="space-y-2">
          <VulnPicker tasks={tasks} selected={taskId} onSelect={setTaskId} />
          <div className="flex items-center justify-end gap-3">
            <button
              type="button"
              disabled={resetting}
              onClick={() => (armed ? resetDemo() : setArmed(true))}
              onBlur={() => setArmed(false)}
              title="Vuelve al escenario inicial: 3 vulnerabilidades resueltas y 2 pendientes"
              className={`text-[11px] rounded-md border px-2 py-1 transition ${
                armed
                  ? "border-amber-500/50 bg-amber-500/15 text-amber-200"
                  : "border-line text-gray-500 hover:text-gray-200"}`}
            >
              {resetting ? "Reiniciando…" : armed ? "Confirmar reinicio" : "↺ Reiniciar la demo"}
            </button>
            <Link to={`/tasks/${taskId}`} className="text-[11px] text-gray-500 hover:text-gray-300">
              Abrir la Remediation Task completa →
            </Link>
          </div>
        </div>
      </div>

      <SceneStepper phases={j.phases} current={scenePhase.id} actionPhase={actionPhase}
                    actionAccent={stepTone(step) === "human" ? "#f59e0b" : "#8ef04a"}
                    onSelect={setPinned} />

      <NextActionBar
        step={step}
        running={busy}
        onAct={act}
        onGoToScene={actionPhase && actionPhase !== scenePhase.id
          ? () => setPinned(actionPhase)
          : undefined}
        onRollback={rollbackRing}
      />

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_360px] gap-4 items-start">
        <div className="space-y-3">
        {playback && (
          <ExecutionTheatre title={playback.title} subtitle={playback.subtitle} lines={playback.lines}
                            onDone={() => setReplaying(false)}
                            onDismiss={() => setPlayback(null)} />
        )}
        <div className="card p-5 space-y-4" key={scenePhase.id}>
          <div className="animate-fade-in">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded"
                    style={{ background: color + "22", color }}>
                ESCENA {scenePhase.index + 1}/{j.phases.length}
              </span>
              <span className="text-[10px] text-gray-500">{scenePhase.band_label}</span>
              {gates.length > 0 && (
                <span className="chip border border-amber-500/40 text-amber-300">
                  ◑ {gates.length === 1 ? "1 punto de control humano" : `${gates.length} puntos de control humanos`}
                </span>
              )}
              {scenePhase.status === "current" && (
                <span className="chip border" style={{ borderColor: color + "66", color }}>escena en curso</span>
              )}
            </div>
            <h2 className="text-lg font-bold text-gray-100 mt-2">{scenePhase.label}</h2>
            <div className="text-xs text-gray-400 leading-relaxed mt-1">{script?.pitch}</div>
            <div className="text-[11px] text-gray-600 mt-1">{script?.automation}</div>
          </div>
          <div className="animate-fade-in">{Scene && <Scene detail={detail} gates={gates} onRollback={rollbackRing} busy={busy} />}</div>
        </div>
        </div>

        <div className="space-y-3 xl:sticky xl:top-6">
          <div className="card p-3 space-y-2">
            <HitlCounter hitl={j.hitl} />
            {step.kind !== "done" && actionPhase && actionPhase !== scenePhase.id && (
              <button type="button" onClick={() => setPinned(actionPhase)}
                      className="text-[11px] text-amber-300 hover:text-amber-200">
                La acción pendiente está en «{j.phases.find((p) => p.id === actionPhase)?.label}» → ir a esa escena
              </button>
            )}
          </div>
          <HitlRail gates={gates.length > 0 ? gates : j.gates.filter((g) => g.status === "pending")} stacked
                    onVerify={verifyGate} onRollback={rollbackRing} />
          <div className="card p-3">
            <div className="text-[10px] font-semibold tracking-wider text-gray-500 mb-2">
              ACTIVIDAD TÉCNICA
            </div>
            <LogConsole entries={[...detail.logs].reverse()} limit={role === "technical" ? 24 : 10} />
          </div>
        </div>
      </div>
    </div>
  );
}
