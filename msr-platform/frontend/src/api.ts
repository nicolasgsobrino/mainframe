import type { Overview, Task, TaskDetail, CI, Edge, TestCase, VulnerableItem, Service, CmdbSummary, CmdbCiRaw, CmdbTables } from "./types";

const j = async (r: Response) => {
  if (!r.ok) throw new Error(await r.text());
  return r.json();
};

export const api = {
  overview: (): Promise<Overview> => fetch("/api/overview").then(j),
  tasks: (): Promise<Task[]> => fetch("/api/tasks").then(j),
  task: (id: string): Promise<TaskDetail> => fetch(`/api/tasks/${id}`).then(j),
  approve: (id: string): Promise<TaskDetail> =>
    fetch(`/api/tasks/${id}/approve`, { method: "POST" }).then(j),
  rollback: (id: string): Promise<TaskDetail> =>
    fetch(`/api/tasks/${id}/rollback`, { method: "POST" }).then(j),
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
