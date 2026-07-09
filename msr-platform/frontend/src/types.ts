export interface Kpis {
  open_findings: number; vulnerable_items: number; remediation_tasks: number;
  kev_count: number; remediated: number; in_flight: number; cis: number; avg_risk: number;
}
export interface Overview {
  funnel: { label: string; value: number }[];
  kpis: Kpis;
  by_priority: Record<string, number>;
  by_phase: Record<string, number>;
  by_track: Record<string, number>;
  sla: { at_risk: number; on_track: number };
}

export interface Task {
  id: string; vulnerable_item_id: string; cve: string; title: string;
  track: "A" | "B"; risk_score: number; priority: string;
  ci_id: string; ci_name: string; owner: string; criticality: string;
  environment: string; sla_due: string; change_type: string; exposed: boolean;
  component: string; vulnerable_version: string; created_at: string; status?: string;
  phase: string; phase_label: string; phase_index: number; phase_status: string;
  affected_count: number;
}

export interface CI {
  id: string; name: string; ci_class: string; criticality: string;
  environment?: string; owner?: string; version?: string; os?: string;
  tech?: string; track?: string; repo?: string; dora_relevant?: boolean;
  engine?: string; maintenance_window?: string;
}
export interface Edge { source: string; target: string; type: string; }

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
export interface Ring {
  ring: number; label: string; assets: number; status: string; post_checks: string[]; result: string;
}
export interface Deployment {
  executor: string; total_assets: number; rings: Ring[];
  exceptions: { asset: string; reason: string; owner: string; expires: string; compensating_control: string }[];
  pr_url: string | null; strategy: string;
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
  phases: { id: string; label: string; index: number; status: string }[];
  artifacts: { impact: ImpactGraph; mvt: Mvt; lab: LabResults; prototype: Prototype; deployment: Deployment; audit: Audit };
  logs: LogEntry[]; rings_done: number;
}
export interface Service { name: string; role: string; status: string; type: string; detail: string; }
