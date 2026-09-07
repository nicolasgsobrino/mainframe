/**
 * Biblioteca de presentación del recorrido de remediación.
 *
 * Los componentes no saben si están dentro del dashboard funcional o de una
 * demo: reciben lo que devuelve la API y lo pintan. El Modo Demo sólo cambia
 * el ritmo (ver `demo.tsx`), nunca los datos.
 */
export { HitlRail, HitlGateCard, HitlCounter, AutomationBadge, HITL_COLOR } from "./hitl";
export { CountUp, useProgressiveReveal } from "./reveal";
export { default as LogConsole } from "./LogConsole";
export { DemoAdvanceControl, nextDemoStep } from "./DemoAdvance";
export type { DemoStep } from "./DemoAdvance";
export { NextActionBar, stepTone, stepAction } from "./NextAction";
export { ExecutionTheatre } from "./ExecutionTheatre";
export type { ExecLine } from "./ExecutionTheatre";
