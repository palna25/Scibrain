import { useEffect, useState } from "react";
import {
  Users,
  FileText,
  CheckCircle2,
  Loader2,
  UserCheck,
  Activity,
  ShieldCheck,
  ArrowUpRight,
  AlertCircle,
} from "lucide-react";

const API_BASE_URL = "http://127.0.0.1:8000";


function StatCard({
  icon: Icon,
  label,
  value,
  description,
}) {
  return (
    <div className="group rounded-2xl border border-white/[0.07] bg-slate-900/50 p-5 transition hover:border-indigo-400/20 hover:bg-slate-900/80">

      <div className="flex items-start justify-between">

        <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-indigo-400/15 bg-indigo-500/10">
          <Icon className="h-5 w-5 text-indigo-400" />
        </div>

        <ArrowUpRight className="h-4 w-4 text-slate-700 transition group-hover:text-indigo-400" />

      </div>

      <div className="mt-5">

        <p className="text-2xl font-semibold tracking-tight text-white">
          {value}
        </p>

        <p className="mt-1 text-sm text-slate-400">
          {label}
        </p>

        <p className="mt-2 text-xs text-slate-500">
          {description}
        </p>

      </div>

    </div>
  );
}


function AdminDashboard() {

  const [statistics, setStatistics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");


  useEffect(() => {

    const fetchStatistics = async () => {

      try {

        const token = localStorage.getItem(
          "scibrain_token"
        );

        const response = await fetch(
          `${API_BASE_URL}/api/admin/statistics`,
          {
            headers: {
              Authorization: `Bearer ${token}`,
            },
          }
        );

        const data = await response.json();

        if (!response.ok) {
          throw new Error(
            data.detail ||
              "Failed to load admin statistics."
          );
        }

        setStatistics(data);

      } catch (err) {

        console.error(
          "Admin dashboard error:",
          err
        );

        setError(
          err.message ||
            "Failed to load admin statistics."
        );

      } finally {

        setLoading(false);

      }

    };

    fetchStatistics();

  }, []);


  const displayValue = (value) => {

    if (loading) {
      return "—";
    }

    if (
      value === null ||
      value === undefined
    ) {
      return "—";
    }

    return value;

  };


  const totalUsers =
    statistics?.users?.total ?? null;

  const activeUsers =
    statistics?.users?.active ?? null;

  const totalPapers =
    statistics?.papers?.total ?? null;

  const analyzedPapers =
    statistics?.papers?.analyzed ?? null;

  const processingPapers =
    statistics?.papers?.processing ?? null;

  const failedPapers =
    statistics?.papers?.failed ?? null;


  return (
    <div>

      {/* ================= PAGE HEADER ================= */}

      <div className="mb-8">

        <div className="flex items-end justify-between">

          <div>

            <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.25em] text-indigo-400">
              Platform Administration
            </p>

            <h1 className="text-3xl font-semibold tracking-tight text-white">
              Admin Dashboard
            </h1>

            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
              Monitor users, research papers, and the
              overall health of the SciBrain platform.
            </p>

          </div>


          {/* System status */}

          <div className="hidden items-center gap-2 rounded-full border border-emerald-400/10 bg-emerald-400/[0.05] px-3 py-1.5 sm:flex">

            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]" />

            <span className="text-xs text-emerald-300">
              System Active
            </span>

          </div>

        </div>

      </div>


      {/* ================= ERROR ================= */}

      {error && (

        <div className="mb-6 flex items-center gap-3 rounded-xl border border-red-400/15 bg-red-400/[0.05] px-4 py-3 text-sm text-red-300">

          <AlertCircle className="h-4 w-4" />

          {error}

        </div>

      )}


      {/* ================= STATISTICS ================= */}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">

        <StatCard
          icon={Users}
          label="Registered Users"
          value={displayValue(totalUsers)}
          description={
            activeUsers !== null
              ? `${activeUsers} active user${
                  activeUsers === 1 ? "" : "s"
                }`
              : "User information unavailable"
          }
        />


        <StatCard
          icon={FileText}
          label="Research Papers"
          value={displayValue(totalPapers)}
          description={
            analyzedPapers !== null
              ? `${analyzedPapers} paper${
                  analyzedPapers === 1 ? "" : "s"
                } analyzed`
              : "Paper information unavailable"
          }
        />


        <StatCard
          icon={CheckCircle2}
          label="Analyzed Papers"
          value={displayValue(analyzedPapers)}
          description={
            totalPapers !== null &&
            analyzedPapers !== null
              ? `${Math.max(
                  totalPapers - analyzedPapers,
                  0
                )} awaiting analysis`
              : "Analysis information unavailable"
          }
        />


        <StatCard
          icon={Loader2}
          label="Processing Papers"
          value={displayValue(processingPapers)}
          description={
            failedPapers !== null
              ? `${failedPapers} failed analysis`
              : "Processing information unavailable"
          }
        />

      </div>


      {/* ================= MAIN CONTENT ================= */}

      <div className="mt-6 grid gap-6 xl:grid-cols-[1fr_360px]">


        {/* ================= PLATFORM OVERVIEW ================= */}

        <section className="relative min-h-[420px] overflow-hidden rounded-2xl border border-white/[0.07] bg-slate-900/50 p-6">

          <div className="pointer-events-none absolute -right-24 -top-24 h-48 w-48 rounded-full bg-indigo-500/10 blur-3xl" />

          <div className="relative flex items-center justify-between">

            <div>

              <p className="text-[10px] font-medium uppercase tracking-[0.2em] text-indigo-400">
                Platform Overview
              </p>

              <h2 className="mt-2 text-base font-semibold text-white">
                SciBrain System
              </h2>

              <p className="mt-1 text-xs text-slate-500">
                Current platform activity and resource
                overview.
              </p>

            </div>


            <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-indigo-400/10 bg-indigo-500/[0.06]">

              <Activity className="h-4 w-4 text-indigo-400" />

            </div>

          </div>


          {/* Overview content */}

          <div className="relative mt-8 grid gap-4 sm:grid-cols-2">

            {/* Users */}

            <div className="rounded-xl border border-white/[0.06] bg-slate-950/70 p-5">

              <div className="flex items-center gap-3">

                <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-indigo-400/10 bg-indigo-500/[0.06]">

                  <Users className="h-4 w-4 text-indigo-400" />

                </div>

                <div>

                  <p className="text-xs text-slate-500">
                    User Accounts
                  </p>

                  <p className="text-sm font-medium text-white">
                    {displayValue(totalUsers)}
                  </p>

                </div>

              </div>

              <p className="mt-4 text-xs leading-5 text-slate-500">
                Registered researcher accounts
                currently available on the platform.
              </p>

            </div>


            {/* Papers */}

            <div className="rounded-xl border border-white/[0.06] bg-slate-950/70 p-5">

              <div className="flex items-center gap-3">

                <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-indigo-400/10 bg-indigo-500/[0.06]">

                  <FileText className="h-4 w-4 text-indigo-400" />

                </div>

                <div>

                  <p className="text-xs text-slate-500">
                    Research Collection
                  </p>

                  <p className="text-sm font-medium text-white">
                    {displayValue(totalPapers)}
                  </p>

                </div>

              </div>

              <p className="mt-4 text-xs leading-5 text-slate-500">
                Academic papers uploaded to the
                SciBrain research collection.
              </p>

            </div>


            {/* Active users */}

            <div className="rounded-xl border border-white/[0.06] bg-slate-950/70 p-5">

              <div className="flex items-center gap-3">

                <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-indigo-400/10 bg-indigo-500/[0.06]">

                  <UserCheck className="h-4 w-4 text-indigo-400" />

                </div>

                <div>

                  <p className="text-xs text-slate-500">
                    Active Users
                  </p>

                  <p className="text-sm font-medium text-white">
                    {displayValue(activeUsers)}
                  </p>

                </div>

              </div>

              <p className="mt-4 text-xs leading-5 text-slate-500">
                User accounts currently enabled for
                platform access.
              </p>

            </div>


            {/* Security */}

            <div className="rounded-xl border border-white/[0.06] bg-slate-950/70 p-5">

              <div className="flex items-center gap-3">

                <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-indigo-400/10 bg-indigo-500/[0.06]">

                  <ShieldCheck className="h-4 w-4 text-indigo-400" />

                </div>

                <div>

                  <p className="text-xs text-slate-500">
                    Admin Access
                  </p>

                  <p className="text-sm font-medium text-emerald-300">
                    Protected
                  </p>

                </div>

              </div>

              <p className="mt-4 text-xs leading-5 text-slate-500">
                Administrative operations are restricted
                to authorized administrators.
              </p>

            </div>

          </div>

        </section>


        {/* ================= SYSTEM STATUS ================= */}

        <section className="rounded-2xl border border-white/[0.07] bg-slate-900/50 p-6">

          <div className="mb-6">

            <p className="text-[10px] font-medium uppercase tracking-[0.2em] text-indigo-400">
              System
            </p>

            <h2 className="mt-2 text-base font-semibold text-white">
              Processing Status
            </h2>

            <p className="mt-1 text-xs text-slate-500">
              Current platform processing state.
            </p>

          </div>


          <div className="space-y-3">


            {/* Total users */}

            <div className="flex items-center justify-between rounded-xl border border-white/[0.06] bg-slate-950/70 px-4 py-3">

              <span className="text-sm text-slate-400">
                Total Users
              </span>

              <span className="text-sm font-medium text-white">
                {displayValue(totalUsers)}
              </span>

            </div>


            {/* Active users */}

            <div className="flex items-center justify-between rounded-xl border border-white/[0.06] bg-slate-950/70 px-4 py-3">

              <span className="text-sm text-slate-400">
                Active Users
              </span>

              <span className="text-sm font-medium text-indigo-300">
                {displayValue(activeUsers)}
              </span>

            </div>


            {/* Total papers */}

            <div className="flex items-center justify-between rounded-xl border border-white/[0.06] bg-slate-950/70 px-4 py-3">

              <span className="text-sm text-slate-400">
                Total Papers
              </span>

              <span className="text-sm font-medium text-white">
                {displayValue(totalPapers)}
              </span>

            </div>


            {/* Processing */}

            <div className="flex items-center justify-between rounded-xl border border-white/[0.06] bg-slate-950/70 px-4 py-3">

              <span className="text-sm text-slate-400">
                Processing
              </span>

              <span className="text-sm font-medium text-amber-300">
                {displayValue(processingPapers)}
              </span>

            </div>


            {/* Failed */}

            <div className="flex items-center justify-between rounded-xl border border-white/[0.06] bg-slate-950/70 px-4 py-3">

              <span className="text-sm text-slate-400">
                Failed Analysis
              </span>

              <span className="text-sm font-medium text-red-300">
                {displayValue(failedPapers)}
              </span>

            </div>


            {/* System */}

            <div className="flex items-center justify-between rounded-xl border border-white/[0.06] bg-slate-950/70 px-4 py-3">

              <span className="text-sm text-slate-400">
                Platform Status
              </span>

              <div className="flex items-center gap-2">

                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-[0_0_7px_rgba(52,211,153,0.8)]" />

                <span className="text-xs text-emerald-300">
                  Operational
                </span>

              </div>

            </div>

          </div>

        </section>

      </div>

    </div>
  );
}


export default AdminDashboard;