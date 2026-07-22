import { BrowserRouter, Routes, Route, NavLink, Navigate } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import Tasks from "./pages/Tasks";
import TaskDetail from "./pages/TaskDetail";
import Cmdb from "./pages/Cmdb";
import Catalog from "./pages/Catalog";
import Integrations from "./pages/Integrations";
import { ViewProvider, RoleToggle, useView, ROLE_META } from "./view";

const NAV = [
  { to: "/dashboard", label: "Dashboard", icon: "▦" },
  { to: "/tasks", label: "Remediation Tasks", icon: "◈" },
  { to: "/cmdb", label: "CMDB · Impact Graph", icon: "⧉" },
  { to: "/catalog", label: "Catálogo de pruebas", icon: "☰" },
  { to: "/integrations", label: "Integraciones", icon: "⇄" },
];

function Sidebar() {
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
        {NAV.map((n) => (
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
        <div className="text-[11px] text-gray-600 leading-relaxed pt-1">
          Demo · datos sintéticos<br />
          ServiceNow (control) + Devin (agente)
        </div>
      </div>
    </aside>
  );
}

function RoleHint() {
  const { role } = useView();
  return <div className="text-[11px] text-gray-500 leading-relaxed">{ROLE_META[role].hint}</div>;
}

export default function App() {
  return (
    <ViewProvider>
    <BrowserRouter>
      <div className="flex h-screen overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto">
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/tasks" element={<Tasks />} />
            <Route path="/tasks/:id" element={<TaskDetail />} />
            <Route path="/cmdb" element={<Cmdb />} />
            <Route path="/catalog" element={<Catalog />} />
            <Route path="/integrations" element={<Integrations />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
    </ViewProvider>
  );
}
