import { NavLink, useNavigate } from "react-router-dom";
import {
  BrainCircuit,
  LayoutDashboard,
  Users,
  FileText,
  LogOut,
  ShieldCheck,
  Settings,

} from "lucide-react";

import AdminTopbar from "./AdminTopbar";

function AdminLayout({ children }) {
  const navigate = useNavigate();

  const handleLogout = () => {
    localStorage.removeItem("scibrain_token");
    localStorage.removeItem("scibrain_user");

    navigate("/login");
  };

  const navigation = [
    {
      name: "Dashboard",
      path: "/admin",
      icon: LayoutDashboard,
    },
    {
      name: "Users",
      path: "/admin/users",
      icon: Users,
    },
    {
      name: "Papers",
      path: "/admin/papers",
      icon: FileText,
    },
    {
  name: "Settings",
  path: "/admin/settings",
  icon: Settings,
},
  ];

  return (
    <div className="min-h-screen bg-background text-foreground">

      {/* ================= AMBIENT BACKGROUND ================= */}

      <div className="pointer-events-none fixed inset-0 overflow-hidden">

        <div className="absolute left-[20%] top-[-20%] h-[500px] w-[500px] rounded-full bg-cyan-500/[0.025] blur-[120px]" />

        <div className="absolute bottom-[-20%] right-[-10%] h-[500px] w-[500px] rounded-full bg-indigo-500/[0.02] blur-[120px]" />

      </div>


      {/* ================= ADMIN SIDEBAR ================= */}

      <aside className="fixed inset-y-0 left-0 z-40 w-[250px] border-r border-border bg-background/80 backdrop-blur-xl">

        <div className="flex h-full flex-col">

          {/* Logo */}

          <div className="flex h-[72px] items-center border-b border-border px-6">

            <div className="flex items-center gap-3">

              <div className="flex h-9 w-9 items-center justify-center rounded-xl border border-indigo-400/20 bg-indigo-500/10">

                <BrainCircuit className="h-5 w-5 text-indigo-400" />

              </div>

              <div>

                <p className="font-semibold">
                  Sci<span className="text-indigo-400">Brain</span>
                </p>

                <p className="text-[10px] uppercase tracking-widest text-muted-foreground">
                  Administration
                </p>

              </div>

            </div>

          </div>


          {/* Navigation */}

          <nav className="flex-1 space-y-1 px-4 py-6">

            <p className="mb-3 px-3 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
              Management
            </p>

            {navigation.map((item) => {

              const Icon = item.icon;

              return (
                <NavLink
                  key={item.path}
                  to={item.path}
                  end={item.path === "/admin"}
                  className={({ isActive }) =>
                    `flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition ${
                      isActive
                        ? "bg-indigo-500/10 text-indigo-400"
                        : "text-muted-foreground hover:bg-white/[0.03] hover:text-foreground"
                    }`
                  }
                >

                  <Icon className="h-4 w-4" />

                  <span>
                    {item.name}
                  </span>

                </NavLink>
              );
            })}

          </nav>


          {/* ================= ADMIN ACCOUNT ================= */}

          <div className="border-t border-border p-4">

            <div className="mb-3 flex items-center gap-3 rounded-xl bg-white/[0.02] p-3">

              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-500/10">

                <ShieldCheck className="h-4 w-4 text-indigo-400" />

              </div>

              <div className="min-w-0">

                <p className="truncate text-xs font-medium">
                  Administrator
                </p>

                <p className="text-[10px] text-muted-foreground">
                  System Access
                </p>

              </div>

            </div>


            <button
              type="button"
              onClick={handleLogout}
              className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-muted-foreground transition hover:bg-red-500/5 hover:text-red-400"
            >

              <LogOut className="h-4 w-4" />

              <span>
                Logout
              </span>

            </button>

          </div>

        </div>

      </aside>


      {/* ================= MAIN CONTENT ================= */}

      <div className="relative ml-[250px] min-h-screen">

        {/* Shared SciBrain Topbar */}

        <AdminTopbar />


        {/* Page Content */}

        <main className="p-8">
          {children}
        </main>

      </div>

    </div>
  );
}


export default AdminLayout;