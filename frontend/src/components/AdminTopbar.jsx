
import { User } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

function AdminTopbar() {
  const navigate = useNavigate();

  const [user, setUser] = useState({
    full_name: "Administrator",
    role: "admin",
  });

  useEffect(() => {
    const storedUser = localStorage.getItem("scibrain_user");

    if (storedUser) {
      try {
        const parsedUser = JSON.parse(storedUser);

        setUser({
          full_name: parsedUser.full_name || "Administrator",
          role: parsedUser.role || "admin",
        });
      } catch (error) {
        console.error("Unable to read admin information:", error);
      }
    }
  }, []);

  const handleProfileClick = () => {
    navigate("/admin/settings");
  };

  return (
    <header className="flex h-20 items-center justify-end border-b border-white/[0.06] px-8">
      <div className="flex items-center gap-4">
        
        {/* Divider */}
        <div className="h-7 w-px bg-white/[0.06]" />

        {/* Admin Profile */}
        <button
          type="button"
          onClick={handleProfileClick}
          title="Open admin settings"
          className="group flex items-center gap-3 rounded-xl px-2 py-1.5 text-left transition-all hover:bg-white/[0.03]"
        >
          <div className="relative flex h-9 w-9 items-center justify-center rounded-full border border-indigo-400/20 bg-indigo-500/10">
            <div className="absolute inset-0 rounded-full bg-indigo-500/10 blur-md" />

            <User className="relative h-4 w-4 text-indigo-400 transition group-hover:text-indigo-300" />
          </div>

          <div className="hidden sm:block">
            <p className="max-w-[180px] truncate text-sm font-medium text-slate-200 transition group-hover:text-white">
              {user.full_name}
            </p>

            <p className="max-w-[180px] truncate text-[10px] capitalize text-slate-500">
              {user.role}
            </p>
          </div>
        </button>
      </div>
    </header>
  );
}

export default AdminTopbar;
