
import {
  LayoutDashboard,
  FileText,
  Network,
  NotebookPen,
  GitBranch,
  Lightbulb,
  Settings,
  LogOut,
  BrainCircuit,
} from "lucide-react";

import { NavLink, useNavigate } from "react-router-dom";

const navigation = [
  {
    name: "Dashboard",
    path: "/dashboard",
    icon: LayoutDashboard,
  },
  {
    name: "Papers",
    path: "/papers",
    icon: FileText,
  },
  {
    name: "Research Notebook",
    path: "/research-notebook",
    icon: NotebookPen,
  },
  {
    name: "Knowledge Graph",
    path: "/knowledge-graph",
    icon: Network,
  },
  {
    name: "Research Gaps",
    path: "/research-gaps",
    icon: Lightbulb,
  },
];

function Sidebar() {
  const navigate = useNavigate();

  const handleLogout = () => {
    localStorage.removeItem("scibrain_token");
    navigate("/login");
  };

  return (
<aside className="fixed left-0 top-0 z-50 flex h-screen w-64 flex-col border-r border-white/[0.06] bg-slate-950">      {/* Logo */}
      <div className="flex h-[88px] items-center border-b border-white/[0.06] px-6">
        <div className="flex items-center gap-3">
          {/* Logo icon */}
          <div className="relative flex h-10 w-10 items-center justify-center rounded-xl border border-indigo-400/20 bg-indigo-500/10">
            <div className="absolute inset-0 rounded-xl bg-indigo-500/10 blur-md" />

            <BrainCircuit className="relative h-5 w-5 text-indigo-400" />
          </div>

          {/* Brand */}
          <div>
            <h1 className="text-lg font-semibold tracking-tight text-white">
              Sci<span className="text-indigo-400">Brain</span>
            </h1>

            <p className="mt-0.5 text-[9px] font-medium tracking-[0.25em] text-slate-500">
              RESEARCH INTELLIGENCE
            </p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-4 py-6">
        <p className="mb-3 px-3 text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-500">
          Workspace
        </p>

        <div className="space-y-1">
          {navigation.map((item) => {
            const Icon = item.icon;

            return (
              <NavLink
                key={item.path}
                to={item.path}
                className={({ isActive }) =>
                  `group flex items-center gap-3 rounded-xl border px-3 py-3 text-sm transition-all duration-200 ${
                    isActive
                      ? "border-indigo-400/15 bg-indigo-500/10 text-indigo-300 shadow-[0_0_25px_rgba(99,102,241,0.06)]"
                      : "border-transparent text-slate-400 hover:bg-white/[0.03] hover:text-slate-200"
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    <Icon
                      className={`h-[18px] w-[18px] transition ${
                        isActive
                          ? "text-indigo-400"
                          : "text-slate-500 group-hover:text-slate-300"
                      }`}
                    />

                    <span>{item.name}</span>

                    {isActive && (
                      <span className="ml-auto h-1.5 w-1.5 rounded-full bg-indigo-400 shadow-[0_0_8px_rgba(129,140,248,0.8)]" />
                    )}
                  </>
                )}
              </NavLink>
            );
          })}
        </div>
      </nav>

      {/* Bottom navigation */}
      <div className="border-t border-white/[0.06] px-4 py-4">
        <NavLink
          to="/settings"
          className={({ isActive }) =>
            `flex items-center gap-3 rounded-xl border px-3 py-3 text-sm transition ${
              isActive
                ? "border-indigo-400/10 bg-indigo-500/[0.06] text-indigo-300"
                : "border-transparent text-slate-400 hover:bg-white/[0.03] hover:text-slate-200"
            }`
          }
        >
          {({ isActive }) => (
            <>
              <Settings
                className={`h-[18px] w-[18px] ${
                  isActive ? "text-indigo-400" : "text-slate-500"
                }`}
              />

              <span>Settings</span>
            </>
          )}
        </NavLink>

        <button
          onClick={handleLogout}
          className="mt-1 flex w-full items-center gap-3 rounded-xl px-3 py-3 text-sm text-slate-400 transition hover:bg-red-500/[0.06] hover:text-red-300"
        >
          <LogOut className="h-[18px] w-[18px] text-slate-500 transition group-hover:text-red-300" />

          <span>Logout</span>
        </button>
      </div>
    </aside>
  );
}

export default Sidebar;

