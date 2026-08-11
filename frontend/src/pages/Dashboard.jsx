
import {
  FileText,
  Network,
  GitBranch,
  Lightbulb,
  Activity,
  ArrowUpRight,
} from "lucide-react";


function StatCard({ icon: Icon, label, value, description }) {
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


function Dashboard() {
  return (
    <div>

      {/* ================= PAGE HEADER ================= */}

      <div className="mb-8">

        <div className="flex items-end justify-between">

          <div>

            <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.25em] text-indigo-400">
              Research Intelligence
            </p>

            <h1 className="text-3xl font-semibold tracking-tight text-white">
              Research Dashboard
            </h1>

            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
              Explore literature, discover relationships, and identify
              unexplored research opportunities.
            </p>

          </div>


          {/* System status */}

          <div className="hidden items-center gap-2 rounded-full border border-emerald-400/10 bg-emerald-400/[0.05] px-3 py-1.5 sm:flex">

            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]" />

            <span className="text-xs text-emerald-300">
              System Online
            </span>

          </div>

        </div>

      </div>


      {/* ================= STATISTICS ================= */}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">

        <StatCard
          icon={FileText}
          label="Research Papers"
          value="0"
          description="Papers analyzed"
        />

        <StatCard
          icon={Network}
          label="Knowledge Nodes"
          value="0"
          description="Entities discovered"
        />

        <StatCard
          icon={GitBranch}
          label="Contradictions"
          value="0"
          description="Potential conflicts"
        />

        <StatCard
          icon={Lightbulb}
          label="Research Gaps"
          value="0"
          description="Opportunities detected"
        />

      </div>


      {/* ================= MAIN CONTENT ================= */}

      <div className="mt-6 grid gap-6 xl:grid-cols-[1fr_360px]">


        {/* ================= KNOWLEDGE GRAPH ================= */}

        <section className="relative min-h-[420px] overflow-hidden rounded-2xl border border-white/[0.07] bg-slate-900/50 p-6">

          {/* Subtle glow */}

          <div className="pointer-events-none absolute -right-24 -top-24 h-48 w-48 rounded-full bg-indigo-500/10 blur-3xl" />


          <div className="relative flex items-center justify-between">

            <div>

              <p className="text-[10px] font-medium uppercase tracking-[0.2em] text-indigo-400">
                Knowledge Graph
              </p>

              <h2 className="mt-2 text-base font-semibold text-white">
                Research Intelligence
              </h2>

              <p className="mt-1 text-xs text-slate-500">
                Your research landscape will appear here.
              </p>

            </div>


            <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-indigo-400/10 bg-indigo-500/[0.06]">
              <Activity className="h-4 w-4 text-indigo-400" />
            </div>

          </div>


          <div className="relative flex h-[320px] items-center justify-center">

            <div className="text-center">

              <div className="relative mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-2xl border border-indigo-400/15 bg-indigo-500/10">

                <div className="absolute inset-0 rounded-2xl bg-indigo-500/10 blur-xl" />

                <Network className="relative h-7 w-7 text-indigo-400" />

              </div>


              <h3 className="text-sm font-medium text-slate-300">
                No research data yet
              </h3>

              <p className="mx-auto mt-2 max-w-sm text-xs leading-5 text-slate-500">
                Upload academic papers to begin building your research
                knowledge graph and discovering meaningful connections.
              </p>

            </div>

          </div>

        </section>


        {/* ================= SYSTEM STATUS ================= */}

        <section className="rounded-2xl border border-white/[0.07] bg-slate-900/50 p-6">

          <div className="mb-6">

            <p className="text-[10px] font-medium uppercase tracking-[0.2em] text-indigo-400">
              Infrastructure
            </p>

            <h2 className="mt-2 text-base font-semibold text-white">
              System Status
            </h2>

            <p className="mt-1 text-xs text-slate-500">
              SciBrain infrastructure
            </p>

          </div>


          <div className="space-y-3">

            {[
              ["FastAPI Backend", "Online"],
              ["PostgreSQL", "Online"],
              ["Neo4j", "Online"],
              ["Qdrant", "Online"],
            ].map(([name, status]) => (

              <div
                key={name}
                className="flex items-center justify-between rounded-xl border border-white/[0.06] bg-slate-950/70 px-4 py-3 transition hover:border-indigo-400/15 hover:bg-slate-950"
              >

                <span className="text-sm text-slate-400">
                  {name}
                </span>


                <div className="flex items-center gap-2">

                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-[0_0_7px_rgba(52,211,153,0.8)]" />

                  <span className="text-xs text-emerald-300">
                    {status}
                  </span>

                </div>

              </div>

            ))}

          </div>

        </section>

      </div>

    </div>
  );
}


export default Dashboard;
