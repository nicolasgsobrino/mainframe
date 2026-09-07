import { createContext, useContext, useState, type ReactNode } from "react";

export type ViewRole = "service_manager" | "technical";

interface ViewCtx {
  role: ViewRole;
  setRole: (r: ViewRole) => void;
}

const Ctx = createContext<ViewCtx>({ role: "service_manager", setRole: () => {} });

// Compatibilidad con la preferencia guardada por la nomenclatura anterior.
const LEGACY_ROLES: Record<string, ViewRole> = {
  manager: "service_manager",
  tech: "technical",
};

function storedRole(): ViewRole {
  const saved = localStorage.getItem("msr_role") ?? "";
  if (saved in ROLE_META) return saved as ViewRole;
  return LEGACY_ROLES[saved] ?? "service_manager";
}

export function ViewProvider({ children }: { children: ReactNode }) {
  const [role, setRoleState] = useState<ViewRole>(storedRole);
  const setRole = (r: ViewRole) => {
    setRoleState(r);
    localStorage.setItem("msr_role", r);
  };
  return <Ctx.Provider value={{ role, setRole }}>{children}</Ctx.Provider>;
}

export const useView = () => useContext(Ctx);

export const ROLE_META: Record<ViewRole, { label: string; icon: string; hint: string }> = {
  service_manager: {
    label: "Service Manager",
    icon: "◱",
    hint: "Management view: risk, SLA, affected services, automation and pending human decisions.",
  },
  technical: {
    label: "Technical",
    icon: "⌘",
    hint: "Operational detail: commands, rings, impacted CIs, dependencies and rollback.",
  },
};

export function RoleToggle() {
  const { role, setRole } = useView();
  return (
    <div className="flex rounded-lg border border-line overflow-hidden text-xs">
      {(Object.keys(ROLE_META) as ViewRole[]).map((r) => (
        <button
          key={r}
          onClick={() => setRole(r)}
          title={ROLE_META[r].hint}
          className={`flex items-center gap-1.5 px-3 py-1.5 font-semibold transition ${
            role === r ? "bg-brand text-black" : "bg-ink text-gray-400 hover:text-gray-200"
          }`}
        >
          <span>{ROLE_META[r].icon}</span>
          {ROLE_META[r].label}
        </button>
      ))}
    </div>
  );
}
