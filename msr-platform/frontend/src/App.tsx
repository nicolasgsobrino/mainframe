import { BrowserRouter, Routes, Route, NavLink, Navigate } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import Tasks from "./pages/Tasks";
import TaskDetail from "./pages/TaskDetail";
import Analytics from "./pages/Analytics";
import Cmdb from "./pages/Cmdb";
import Catalog from "./pages/Catalog";
import Integrations from "./pages/Integrations";
import DemoStage from "./pages/DemoStage";
import { ViewProvider, RoleToggle, useView, ROLE_META } from "./view";
import { DemoProvider, DemoToggle, DemoBanner, useDemo } from "./demo";

const NAV: { to: string; label: string; icon: string; demoOnly?: boolean }[] = [
  { to: "/dashboard", label: "Dashboard", icon: "▦" },
  // La presentación guiada sólo existe mientras el Modo Demo está activo.
  { to: "/demo", label: "Presentación guiada", icon: "▶", demoOnly: true },
  { to: "/tasks", label: "Remediation Tasks", icon: "◈" },
  { to: "/analytics", label: "Analítica", icon: "◧" },
  { to: "/cmdb", label: "CMDB · Impact Graph", icon: "⧉" },
  { to: "/catalog", label: "Catálogo de pruebas", icon: "☰" },
  { to: "/integrations", label: "Integraciones", icon: "⇄" },
];

function Sidebar() {
  const { active } = useDemo();
  const items = NAV.filter((n) => !n.demoOnly || active);
  return (
    <aside className="w-64 shrink-0 bg-ink border-r border-line flex flex-col">
      <div className="px-5 py-5 border-b border-line">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-brand flex items-center justify-center text-black font-black">M</div>
          <div>
            <div className="text-sm font-extrabold leading-tight">Machine Speed</div>
            <div className="text-xs text-brand font-semibold -mt-0.5">Remediation</div>
          </div>
        </div>
      </div>
      <nav className="flex-1 py-3">
        {items.map((n) => (
          <NavLink
            key={n.to}
            to={n.to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-5 py-2.5 text-sm font-medium transition ${
                isActive ? "text-brand bg-brand/10 border-r-2 border-brand" : "text-gray-400 hover:text-gray-200 hover:bg-ink-soft"
              }`
            }
          >
            <span className="text-base w-4 text-center">{n.icon}</span>
            {n.label}
          </NavLink>
        ))}
      </nav>
      <div className="px-5 py-4 border-t border-line space-y-2">
        <div className="text-[11px] text-gray-500 font-semibold uppercase tracking-wide">Perspectiva</div>
        <RoleToggle />
        <RoleHint />
        <div className="pt-2">
          <div className="text-[11px] text-gray-500 font-semibold uppercase tracking-wide mb-1">Presentación</div>
          <DemoToggle />
        </div>
        <div className="text-[11px] text-gray-600 leading-relaxed pt-1">
          Demo · datos sintéticos<br />
          ServiceNow (control) + Devin (agente)
        </div>
      </div>
    </aside>
  );
}

/** La ruta guiada no existe fuera del Modo Demo: en ejecución real no se ofrece. */
function DemoGuard() {
  const { allowed, resolved } = useDemo();
  if (!resolved) return <div className="p-6 text-xs text-gray-500">Comprobando el modo de ejecución…</div>;
  if (!allowed) return <Navigate to="/dashboard" replace />;
  return <DemoStage />;
}

function RoleHint() {
  const { role } = useView();
  return <div className="text-[11px] text-gray-500 leading-relaxed">{ROLE_META[role].hint}</div>;
}

export default function App() {
  return (
    <ViewProvider>
    <DemoProvider>
    <BrowserRouter>
      <div className="flex h-screen overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto">
          <DemoBanner />
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/demo" element={<DemoGuard />} />
            <Route path="/tasks" element={<Tasks />} />
            <Route path="/tasks/:id" element={<TaskDetail />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/cmdb" element={<Cmdb />} />
            <Route path="/catalog" element={<Catalog />} />
            <Route path="/integrations" element={<Integrations />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
    </DemoProvider>
    </ViewProvider>
  );
}
