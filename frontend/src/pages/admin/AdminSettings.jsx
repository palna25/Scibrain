
import { useEffect, useState } from "react";
import { useTheme } from "../../context/ThemeContext";
import {
  User,
  Mail,
  Shield,
  Pencil,
  Save,
  Check,
  Settings as SettingsIcon,
  Sun,
  Moon,
} from "lucide-react";

function AdminSettings() {
  const { theme, setTheme } = useTheme();

  const [user, setUser] = useState({
    full_name: "",
    email: "",
    role: "admin",
  });

  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const storedUser = localStorage.getItem("scibrain_user");

    if (!storedUser) return;

    try {
      const parsedUser = JSON.parse(storedUser);

      setUser({
        full_name: parsedUser.full_name || "Administrator",
        email: parsedUser.email || "",
        role: parsedUser.role || "admin",
      });
    } catch (error) {
      console.error("Unable to read admin information:", error);
    }
  }, []);

  const handleSave = () => {
    try {
      const storedUser = localStorage.getItem("scibrain_user");
      const existingUser = storedUser ? JSON.parse(storedUser) : {};

      localStorage.setItem(
        "scibrain_user",
        JSON.stringify({
          ...existingUser,
          full_name: user.full_name.trim(),
        })
      );

      setUser((previous) => ({
        ...previous,
        full_name: previous.full_name.trim(),
      }));

      setSaved(true);
      window.setTimeout(() => setSaved(false), 2500);
    } catch (error) {
      console.error("Unable to save admin settings:", error);
      setSaved(false);
    }
  };

  const isActive = (() => {
    try {
      const storedUser = JSON.parse(
        localStorage.getItem("scibrain_user") || "{}"
      );

      return storedUser.is_active !== false;
    } catch {
      return true;
    }
  })();

  return (
    <div className="relative min-h-[calc(100vh-88px)] overflow-hidden">
      {/* Ambient background */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute left-[15%] top-[-15%] h-[450px] w-[450px] rounded-full bg-indigo-500/[0.035] blur-[130px]" />
        <div className="absolute bottom-[-15%] right-[-5%] h-[450px] w-[450px] rounded-full bg-cyan-500/[0.025] blur-[130px]" />
      </div>

      <div className="relative mx-auto max-w-5xl">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-2">
            <div className="h-5 w-1 rounded-full bg-indigo-400" />
            <p className="text-[10px] font-semibold uppercase tracking-[0.25em] text-indigo-400">
              Administration
            </p>
          </div>

          <h1 className="mt-3 text-2xl font-semibold tracking-tight text-white">
            Profile Settings
          </h1>

          <p className="mt-2 text-sm text-slate-500">
            Manage your administrator profile and workspace preferences.
          </p>
        </div>

        {/* Profile card */}
        <div className="overflow-hidden rounded-2xl border border-white/[0.07] bg-slate-900/40 shadow-2xl shadow-black/20 backdrop-blur-xl">
          <div className="relative h-32 overflow-hidden border-b border-white/[0.06] bg-slate-950/60">
            <div className="absolute inset-0 bg-gradient-to-r from-indigo-500/[0.08] via-transparent to-cyan-500/[0.05]" />
            <div className="absolute -right-20 -top-32 h-72 w-72 rounded-full bg-indigo-500/[0.06] blur-3xl" />
            <div className="absolute -left-20 -bottom-40 h-72 w-72 rounded-full bg-cyan-500/[0.04] blur-3xl" />
          </div>

          <div className="relative px-7 pb-7">
            <div className="-mt-10 flex items-end justify-between">
              <div className="relative flex h-20 w-20 items-center justify-center rounded-2xl border border-indigo-400/20 bg-slate-900 shadow-xl shadow-black/30">
                <div className="absolute inset-1 rounded-xl bg-indigo-500/[0.08]" />
                <Shield className="relative h-8 w-8 text-indigo-400" />
              </div>

              <div
                className={`flex items-center gap-2 rounded-full border px-3 py-1.5 ${
                  isActive
                    ? "border-emerald-400/10 bg-emerald-400/[0.04]"
                    : "border-red-400/10 bg-red-400/[0.04]"
                }`}
              >
                <span
                  className={`h-1.5 w-1.5 rounded-full ${
                    isActive ? "bg-emerald-400" : "bg-red-400"
                  }`}
                />
                <span
                  className={`text-[10px] font-medium uppercase tracking-wider ${
                    isActive ? "text-emerald-400" : "text-red-400"
                  }`}
                >
                  {isActive ? "Active" : "Inactive"}
                </span>
              </div>
            </div>

            <div className="mt-4">
              <h2 className="text-xl font-semibold text-white">
                {user.full_name || "Administrator"}
              </h2>
              <p className="mt-1 text-sm capitalize text-slate-500">
                {user.role}
              </p>
            </div>
          </div>
        </div>

        {/* Account information */}
        <div className="mt-6 rounded-2xl border border-white/[0.07] bg-slate-900/40 p-7 shadow-xl shadow-black/10 backdrop-blur-xl">
          <div className="flex items-center justify-between border-b border-white/[0.06] pb-5">
            <div>
              <h2 className="text-sm font-semibold text-white">
                Account Information
              </h2>
              <p className="mt-1 text-xs text-slate-600">
                Your registered SciBrain administrator account details.
              </p>
            </div>
            <Pencil className="h-4 w-4 text-slate-600" />
          </div>

          <div className="mt-6 grid gap-5 md:grid-cols-2">
            {/* Full name */}
            <div>
              <label
                htmlFor="admin-full-name"
                className="mb-2 block text-[11px] font-medium uppercase tracking-wider text-slate-500"
              >
                Full name
              </label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-600" />
                <input
                  id="admin-full-name"
                  type="text"
                  value={user.full_name}
                  onChange={(event) => {
                    setUser((previous) => ({
                      ...previous,
                      full_name: event.target.value,
                    }));
                    setSaved(false);
                  }}
                  maxLength={100}
                  className="h-11 w-full rounded-xl border border-white/[0.06] bg-slate-950/60 pl-10 pr-4 text-sm text-slate-200 outline-none transition focus:border-indigo-400/20 focus:bg-slate-950/80 focus:ring-1 focus:ring-indigo-400/10"
                />
              </div>
            </div>

            {/* Email */}
            <div>
              <label
                htmlFor="admin-email"
                className="mb-2 block text-[11px] font-medium uppercase tracking-wider text-slate-500"
              >
                Email address
              </label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-600" />
                <input
                  id="admin-email"
                  type="email"
                  value={user.email}
                  disabled
                  className="h-11 w-full cursor-not-allowed rounded-xl border border-white/[0.06] bg-slate-950/40 pl-10 pr-4 text-sm text-slate-500 outline-none"
                />
              </div>
            </div>

            {/* Role */}
            <div>
              <label
                htmlFor="admin-role"
                className="mb-2 block text-[11px] font-medium uppercase tracking-wider text-slate-500"
              >
                Account role
              </label>
              <div className="relative">
                <Shield className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-600" />
                <input
                  id="admin-role"
                  type="text"
                  value={user.role}
                  disabled
                  className="h-11 w-full cursor-not-allowed rounded-xl border border-white/[0.06] bg-slate-950/40 pl-10 pr-4 text-sm capitalize text-slate-500 outline-none"
                />
              </div>
            </div>
          </div>

          <div className="mt-7 flex items-center justify-end border-t border-white/[0.06] pt-6">
            {saved && (
              <div className="mr-4 flex items-center gap-2 text-xs text-emerald-400">
                <Check className="h-3.5 w-3.5" />
                Changes saved locally
              </div>
            )}

            <button
              type="button"
              onClick={handleSave}
              disabled={!user.full_name.trim()}
              className="group flex items-center gap-2 rounded-xl bg-indigo-500 px-5 py-2.5 text-sm font-medium text-white shadow-lg shadow-indigo-500/20 transition hover:bg-indigo-400 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Save className="h-4 w-4 transition group-hover:scale-105" />
              Save changes
            </button>
          </div>
        </div>

        {/* Appearance */}
        <div className="mt-6 rounded-2xl border border-white/[0.07] bg-slate-900/40 p-7 shadow-xl shadow-black/10 backdrop-blur-xl">
          <div className="border-b border-white/[0.06] pb-5">
            <h2 className="text-sm font-semibold text-white">Appearance</h2>
            <p className="mt-1 text-xs text-slate-600">
              Choose how SciBrain looks across your administration workspace.
            </p>
          </div>

          <div className="mt-6 flex flex-col gap-4 sm:flex-row">
            {[
              {
                value: "dark",
                label: "Dark",
                description: "Dark workspace appearance",
                Icon: Moon,
              },
              {
                value: "light",
                label: "Light",
                description: "Light workspace appearance",
                Icon: Sun,
              },
            ].map(({ value, label, description, Icon }) => (
              <button
                key={value}
                type="button"
                onClick={() => setTheme(value)}
                className={`flex flex-1 items-center justify-between rounded-xl border p-4 text-left transition ${
                  theme === value
                    ? "border-indigo-400/30 bg-indigo-500/[0.08]"
                    : "border-white/[0.06] bg-slate-950/40 hover:bg-slate-950/60"
                }`}
              >
                <div className="flex items-center gap-3">
                  <Icon className="h-4 w-4 text-indigo-400" />
                  <div>
                    <p className="text-sm font-medium text-slate-200">
                      {label}
                    </p>
                    <p className="mt-1 text-xs text-slate-500">
                      {description}
                    </p>
                  </div>
                </div>

                <div
                  className={`h-4 w-4 rounded-full border ${
                    theme === value
                      ? "border-indigo-400 bg-indigo-400"
                      : "border-slate-600"
                  }`}
                />
              </button>
            ))}
          </div>
        </div>

        {/* Workspace information */}
        <div className="mt-6 grid gap-6 md:grid-cols-2">
          <div className="rounded-2xl border border-white/[0.06] bg-slate-900/30 p-6">
            <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-600">
              Workspace
            </p>

            <div className="mt-3 flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-500/[0.08]">
                <SettingsIcon className="h-5 w-5 text-indigo-400" />
              </div>
              <div>
                <h3 className="text-sm font-medium text-slate-200">
                  SciBrain Administration
                </h3>
                <p className="mt-1 text-xs text-slate-600">
                  Manage users and the papers.
                </p>
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-white/[0.06] bg-slate-900/30 p-6">
            <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-600">
              Account status
            </p>

            <div className="mt-4 flex items-center gap-3">
              <div
                className={`flex h-9 w-9 items-center justify-center rounded-lg ${
                  isActive ? "bg-emerald-400/[0.06]" : "bg-red-400/[0.06]"
                }`}
              >
                <Check
                  className={`h-4 w-4 ${
                    isActive ? "text-emerald-400" : "text-red-400"
                  }`}
                />
              </div>

              <div>
                <p className="text-sm font-medium text-slate-200">
                  {isActive ? "Account active" : "Account inactive"}
                </p>
                <p className="mt-0.5 text-[11px] text-slate-600">
                  {isActive
                    ? "Administrator workspace access is enabled."
                    : "Administrator account is marked inactive."}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default AdminSettings;
