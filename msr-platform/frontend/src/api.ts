import type { Overview, Task, TaskDetail, CI, Edge, TestCase, VulnerableItem, Service, CmdbSummary, CmdbCiRaw, CmdbTables, ApiErrorBody, ExecutionConfig, PatchJob, LabSnapshot, LabValidation, LabResetResponse, LabReconciliation, LabReconcileResult } from "./types";

/** Error de API con el sobre uniforme del backend (`error.code`/`correlation_id`). */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly correlationId: string | null;

  constructor(status: number, code: string, message: string, correlationId: string | null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.correlationId = correlationId;
  }
}

const j = async (r: Response) => {
  if (!r.ok) {
    const raw = await r.text();
    let body: Partial<ApiErrorBody> = {};
    try {
      body = JSON.parse(raw) as ApiErrorBody;
    } catch {
      body = {};
    }
    const err = body.error;
    throw new ApiError(r.status, err?.code ?? `HTTP_${r.status}`,
      err?.message ?? (raw || r.statusText), err?.correlation_id ?? null);
  }
  return r.json();
};

/** Clave de idempotencia estable por (tarea, operación) mientras la pestaña vive. */
const idempotencyKeys = new Map<string, string>();
const idempotencyKey = (scope: string): string => {
  const existing = idempotencyKeys.get(scope);
  if (existing) return existing;
  const key = `${scope}:${crypto.randomUUID()}`;
  idempotencyKeys.set(scope, key);
  return key;
};
/** Se descarta tras una operación terminada para permitir el siguiente anillo. */
export const releaseIdempotencyKey = (scope: string) => idempotencyKeys.delete(scope);

const mutate = (url: string, scope: string, body?: unknown) =>
  fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": idempotencyKey(scope),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  }).then(j);

export const api = {
  overview: (): Promise<Overview> => fetch("/api/overview").then(j),
  tasks: (): Promise<Task[]> => fetch("/api/tasks").then(j),
  task: (id: string): Promise<TaskDetail> => fetch(`/api/tasks/${id}`).then(j),
  execution: (): Promise<ExecutionConfig> => fetch("/api/execution").then(j),
  approve: (id: string, ring: number): Promise<TaskDetail> =>
    mutate(`/api/tasks/${id}/approve`, `approve:${id}:${ring}`),
  rollback: (id: string, ring: number): Promise<TaskDetail> =>
    mutate(`/api/tasks/${id}/rollback`, `rollback:${id}:${ring}`),
  patchJob: (jobId: string): Promise<PatchJob> => fetch(`/api/patch-jobs/${jobId}`).then(j),
  taskPatchJobs: (id: string): Promise<PatchJob[]> => fetch(`/api/tasks/${id}/patch-jobs`).then(j),
  cancelPatchJob: (jobId: string): Promise<PatchJob> =>
    mutate(`/api/patch-jobs/${jobId}/cancel`, `cancel:${jobId}`),
  simulateIncident: (id: string): Promise<TaskDetail> =>
    fetch(`/api/tasks/${id}/simulate-incident`, { method: "POST" }).then(j),
  preapproveRing: (id: string, ring: number, note?: string): Promise<TaskDetail> =>
    fetch(`/api/tasks/${id}/rings/${ring}/preapprove`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ note: note ?? null }),
    }).then(j),
  updateRingAssets: (id: string, ring: number, excluded: string[]): Promise<TaskDetail> =>
    fetch(`/api/tasks/${id}/rings/${ring}/assets`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ excluded }),
    }).then(j),
  // Laboratorio EC2: el backend resuelve la instancia por tags. Ninguna de
  // estas llamadas envía Instance IDs, comandos, documentos ni parámetros.
  lab: (labId: string): Promise<LabSnapshot> => fetch(`/api/labs/${labId}`).then(j),
  validateLab: (labId: string): Promise<LabValidation> =>
    fetch(`/api/labs/${labId}/validate`, { method: "POST" }).then(j),
  // El reset real termina la instancia: el backend exige `confirmed` explícito.
  resetLab: (labId: string, confirmed = false): Promise<LabResetResponse> =>
    mutate(`/api/labs/${labId}/reset`, `lab-reset:${labId}`, { confirmed }),
  labReconciliation: (labId: string): Promise<LabReconciliation> =>
    fetch(`/api/labs/${labId}/reconciliation`).then(j),
  reconcileLab: (labId: string, confirmed = false): Promise<LabReconcileResult> =>
    fetch(`/api/labs/${labId}/reconcile`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirmed }),
    }).then(j),
  labJobs: (labId: string): Promise<PatchJob[]> => fetch(`/api/labs/${labId}/jobs`).then(j),
  cmdb: (): Promise<{ summary: CmdbSummary; services: CI[] }> => fetch("/api/cmdb").then(j),
  cmdbCis: (params: { cls?: string; track?: string; crit?: string; q?: string; limit?: number; offset?: number } = {}): Promise<{ total: number; items: CI[] }> => {
    const qs = new URLSearchParams();
    if (params.cls) qs.set("cls", params.cls);
    if (params.track) qs.set("track", params.track);
    if (params.crit) qs.set("crit", params.crit);
    if (params.q) qs.set("q", params.q);
    qs.set("limit", String(params.limit ?? 100));
    qs.set("offset", String(params.offset ?? 0));
    return fetch(`/api/cmdb/cis?${qs}`).then(j);
  },
  cmdbCiRaw: (ciId: string): Promise<CmdbCiRaw> =>
    fetch(`/api/cmdb/cis/${ciId}/raw`).then(j),
  cmdbGraph: (serviceId: string): Promise<{ nodes: CI[]; edges: Edge[] }> =>
    fetch(`/api/cmdb/graph/${serviceId}`).then(j),
  cmdbTables: (): Promise<CmdbTables> => fetch("/api/cmdb/tables").then(j),
  catalog: (): Promise<TestCase[]> => fetch("/api/catalog").then(j),
  vitems: (): Promise<VulnerableItem[]> => fetch("/api/vulnerable-items").then(j),
  services: (): Promise<Service[]> => fetch("/api/services").then(j),
  activity: () => fetch("/api/activity").then(j),
  reset: () => fetch("/api/reset", { method: "POST" }).then(j),
};
