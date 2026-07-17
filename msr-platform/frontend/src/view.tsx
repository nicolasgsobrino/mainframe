import { createContext, useContext, useState, type ReactNode } from "react";

export type ViewRole = "manager" | "tech";

interface ViewCtx {
  role: ViewRole;
  setRole: (r: ViewRole) => void;
}

const Ctx = createContext<ViewCtx>({ role: "manager", setRole: () => {} });

export function ViewProvider({ children }: { children: ReactNode }) {
  const [role, setRoleState] = useState<ViewRole>(
    () => (localStorage.getItem("msr_role") as ViewRole) || "manager",
  );
  const setRole = (r: ViewRole) => {
    setRoleState(r);
    localStorage.setItem("msr_role", r);
  };
  return <Ctx.Provider value={{ role, setRole }}>{children}</Ctx.Provider>;
}

export const useView = () => useContext(Ctx);

export const ROLE_META: Record<ViewRole, { label: string; icon: string; hint: string }> = {
  manager: {
    label: "Gestor",
    icon: "◱",
    hint: "Visión de negocio: riesgo, SLA, servicios afectados y estado a alto nivel.",
  },
  tech: {
    label: "Técnico",
    icon: "⌘",
    hint: "Detalle operativo: comandos, anillos, CIs impactados, dependencias y rollback.",
  },
};

export function RoleToggle() {
  const { role, setRole } = useView();
  return (
    <div className="flex rounded-lg border border-line overflow-hidden text-xs">
      {(["manager", "tech"] as ViewRole[]).map((r) => (
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
