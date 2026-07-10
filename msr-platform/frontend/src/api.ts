import type { Overview, Task, TaskDetail, CI, Edge, TestCase, VulnerableItem, Service } from "./types";

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
  cmdb: (): Promise<{ cis: CI[]; edges: Edge[] }> => fetch("/api/cmdb").then(j),
  catalog: (): Promise<TestCase[]> => fetch("/api/catalog").then(j),
  vitems: (): Promise<VulnerableItem[]> => fetch("/api/vulnerable-items").then(j),
  services: (): Promise<Service[]> => fetch("/api/services").then(j),
  activity: () => fetch("/api/activity").then(j),
  reset: () => fetch("/api/reset", { method: "POST" }).then(j),
};
