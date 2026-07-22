export interface Kpis {
  open_findings: number; vulnerable_items: number; remediation_tasks: number;
  kev_count: number; remediated: number; in_flight: number; cis: number; avg_risk: number;
}
export interface CmdbSummary {
  total: number; edges: number; source: string;
  by_class: Record<string, number>;
  by_track: Record<string, number>;
  by_criticality: Record<string, number>;
  by_environment: Record<string, number>;
}
export type Lane = "critical" | "accelerated" | "standard";
export interface LaneMeta {
  label: string; sla: string; color: string; automation: string; flow: string;
}
export type Automation = "agentable" | "ai_assisted" | "human";
export interface FlowStep {
  name: string; detail: string; automation: Automation; mode: string; sla: string;
}
export interface LaneFlow { shared: FlowStep[]; steps: FlowStep[]; }

export interface Overview {
  funnel: { label: string; value: number }[];
  kpis: Kpis;
  by_priority: Record<string, number>;
  by_phase: Record<string, number>;
  by_track: Record<string, number>;
  by_lane: Record<string, number>;
  by_criticality: Record<string, number>;
  tracks: Record<string, string>;
  lanes: Record<string, LaneMeta>;
  deployment: { rings_deployed: number; rollbacks: number; in_deployment: number };
  cmdb: CmdbSummary;
  sla: { at_risk: number; on_track: number; overdue: number; due_soon: number };
}

export interface SlaState {
  due: string; days_left: number | null; overdue: boolean;
  days_overdue: number; due_soon?: boolean;
}
export interface CmdbTables {
  source: string; instance?: string; generated_at?: string;
  total_cis: number; total_relationships?: number;
  tables: { table: string; file?: string; records: number }[];
}

export interface Task {
  id: string; vulnerable_item_id: string; cve: string; title: string;
  track: "A" | "B" | "C"; lane: Lane; risk_score: number; priority: string;
  ci_id: string; ci_name: string; owner: string; criticality: string;
  environment: string; sla_due: string; change_type: string; exposed: boolean;
  component: string; vulnerable_version: string; created_at: string; status?: string;
  phase: string; phase_label: string; phase_index: number; phase_status: string;
  affected_count: number; sla?: SlaState;
}

export interface CI {
  id: string; name: string; ci_class: string; criticality: string;
  environment?: string; owner?: string; version?: string; os?: string;
  tech?: string; track?: string; repo?: string; dora_relevant?: boolean;
  engine?: string; maintenance_window?: string;
  sys_class_name?: string; install_status?: string; business_criticality?: string;
  cmdb_source?: string; support_group?: string; image?: string; cloud?: string;
}
export interface Edge { source: string; target: string; type: string; }

export interface CmdbFieldMap {
  servicenow: string; type: string; internal: string; note: string;
}
export interface CmdbCiRaw {
  ci_id: string;
  table: string;
  endpoint: string;
  source: string;
  servicenow_record: Record<string, unknown>;
  normalized: CI;
  field_map: CmdbFieldMap[];
}

export interface ImpactGraph {
  nodes: { id: string; name: string; ci_class: string; criticality: string; environment: string; is_root: boolean }[];
  edges: Edge[];
  affected_layers: string[];
  affected_count: number;
  business_services: string[];
}

export interface TestCase {
  id: string; name: string; layer: string; applies_to: string;
  remediation_type: string; criticality: string; tool: string; evidence: string;
  reason?: string;
}
export interface Mvt {
  selected: TestCase[]; excluded: TestCase[]; remediation_type: string;
  confidence: number; rationale: string;
}
export interface LabResults {
  results: { test_id: string; name: string; layer: string; tool: string; status: string; duration_s: number; evidence: string }[];
  passed: number; total: number; verdict: string;
  patch_tests: any[]; app_tests: any[];
}
export interface Prototype {
  approach: string; lab_blueprint: { type: string; tool: string; spec: string }[];
  provision_tool: string; metrics: Record<string, number>; verdict: string; teardown: string;
}
export interface RingAction {
  seq: number; actor: string; tool: string; command: string;
  output: string; status: string; duration_s: number; why?: string;
}
export interface RingAsset {
  id: string; name: string; ci_class: string; criticality: string;
  environment: string; reason: string; excluded: boolean; is_root?: boolean;
}
export interface RingDependency {
  id: string; name: string; ci_class: string; criticality: string;
  relation: string; of: string;
}
export interface RingApproval {
  required: string; preapproved: boolean;
  approver: string | null; ts: string | null; note: string | null;
}
export interface RingPlan {
  ring: number; label: string; band: string; target_population: string;
  environment?: string; kind?: string; is_replica?: boolean; runs_tests?: boolean;
  pct?: number; purpose?: string;
  window: string; canary_pct: number; assets_count: number; selected_count: number;
  selection_rationale: string;
  selection_criteria: { factor: string; detail: string }[];
  assets: RingAsset[];
  dependencies: RingDependency[];
  graph: { nodes: ImpactGraph["nodes"]; edges: Edge[] };
  entry_criteria: { check: string; ok: boolean }[];
  approval: RingApproval;
}
export interface Ring {
  ring: number; label: string; assets: number; status: string; post_checks: string[]; result: string;
  actions: { steps: RingAction[]; from_version: string; to_version: string } | null;
  plan: RingPlan;
  health: { error_rate_pct: number; p95_latency_ms: number; availability_pct: number } | null;
}
export interface RollbackPlan {
  strategy: string; snapshot_ref: string; target_version: string; from_version: string;
  rto_minutes: number; auto_trigger: string; tested_in_lab: boolean;
  steps: { actor: string; tool: string; command: string; desc: string }[];
}
export interface RollbackState {
  status: string; triggered: boolean; trigger_type?: string; reason?: string;
  ring?: number; ts?: string; restored_version?: string; verdict?: string;
}
export interface ItsmPhase { key: string; label: string; approval: boolean; included: boolean; }
export interface ItsmCtask { name: string; role: string; auto: boolean; }
export interface ItsmChange {
  system: string; number: string; type: string; type_label: string;
  state: string; risk: string; approval: string; requires_human: boolean;
  detail: string; short_description: string; assignment_group: string;
  phases: ItsmPhase[]; ctasks: ItsmCtask[];
  four_eyes: boolean; gxp: boolean; impact_level: string;
  affected_cis: number; affected_services: string[];
  environment: string; patch: string; vulnerability: string;
}
export interface Deployment {
  executor: string; total_assets: number; rings: Ring[];
  exceptions: { asset: string; reason: string; owner: string; expires: string; compensating_control: string }[];
  pr_url: string | null; strategy: string; itsm?: ItsmChange;
  rollback_plan: RollbackPlan; rollback: RollbackState;
}
export interface Audit {
  report_id: string; generated_at: string;
  trace: { step: string; ref: string; detail: string }[];
  dora_relevant: boolean; evidences_count: number;
}
export interface LogEntry { actor: string; phase: string; msg: string; ts?: string; task_id?: string; }
export interface VulnerableItem {
  id: string; cve: string; title: string; cvss: number; epss: number; kev: boolean;
  exploit_available: boolean; track: string; component: string; vulnerable_version: string;
  ci_id: string; ci_name: string; ci_class: string; exposed: boolean; criticality: string;
  environment: string; owner: string; risk_score: number; sources: string[]; status: string;
  detected_at: string; sla_days: number; sla_due: string;
}
export interface TaskDetail {
  task: Task; vulnerable_item: VulnerableItem; phase_index: number;
  phases: { id: string; label: string; index: number; status: string; automation: Automation }[];
  lane: Lane; lane_meta: LaneMeta; lane_flow: LaneFlow;
  artifacts: { impact: ImpactGraph; mvt: Mvt; lab: LabResults; prototype: Prototype; deployment: Deployment; audit: Audit };
  logs: LogEntry[]; rings_done: number; sla?: SlaState;
}
export interface Service { name: string; role: string; status: string; type: string; detail: string; }
