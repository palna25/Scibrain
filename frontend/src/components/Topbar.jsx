import { Bell, Search, User } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import PaperSearch from "./PaperSearch";

function Topbar() {
  const navigate = useNavigate();

  const [user, setUser] = useState({
  full_name: "Researcher",
  role: "Scibrain Workspace",
});

  useEffect(() => {
    const storedUser = localStorage.getItem("scibrain_user");

    if (storedUser) {
      try {
        const parsedUser = JSON.parse(storedUser);

        setUser({
  full_name: parsedUser.full_name || "Researcher",
  role: parsedUser.role || "Scibrain Workspace",
});
      } catch (error) {
        console.error("Unable to read user information:", error);
      }
    }
  }, []);

  const handleProfileClick = () => {
    navigate("/settings");
  };

  return (
    <header className="flex h-20 items-center justify-between border-b border-white/[0.06] px-8">
      {/* Search */}
      <div className="relative w-[360px]">
        <PaperSearch />
      
       
      </div>

      {/* Right side */}
      <div className="flex items-center gap-4">
        {/* Notifications */}
        <button
          type="button"
          aria-label="Notifications"
          className="relative flex h-10 w-10 items-center justify-center rounded-xl border border-white/[0.07] bg-slate-900/60 text-slate-500 transition-all hover:border-indigo-400/15 hover:bg-slate-900/80 hover:text-slate-200"
        >
          <Bell className="h-4 w-4" />

          <span className="absolute right-2 top-2 h-1.5 w-1.5 rounded-full bg-indigo-400 shadow-[0_0_8px_rgba(129,140,248,0.8)]" />
        </button>

        {/* Divider */}
        <div className="h-7 w-px bg-white/[0.06]" />

        {/* User Profile */}
        <button
          type="button"
          onClick={handleProfileClick}
          className="group flex items-center gap-3 rounded-xl px-2 py-1.5 text-left transition-all hover:bg-white/[0.03]"
          title="Open profile settings"
        >
          {/* Avatar */}
          <div className="relative flex h-9 w-9 items-center justify-center rounded-full border border-indigo-400/20 bg-indigo-500/10">
            <div className="absolute inset-0 rounded-full bg-indigo-500/10 blur-md" />

            <User className="relative h-4 w-4 text-indigo-400 transition group-hover:text-indigo-300" />
          </div>

          {/* User details */}
          <div className="hidden sm:block">
            <p className="max-w-[180px] truncate text-sm font-medium text-slate-200 transition group-hover:text-white">
              {user.full_name}
            </p>

            <p className="max-w-[180px] truncate text-[10px] capitalize text-slate-500">
  {user.role || "researcher"}
</p>
          </div>
        </button>
      </div>
    </header>
  );
}

export default Topbar;