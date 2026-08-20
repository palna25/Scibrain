import { useEffect, useState } from "react";
import {
  FileText,
  Network,
  GitBranch,
  Lightbulb,
  Activity,
  ArrowUpRight,
} from "lucide-react";

const API_BASE_URL = "http://127.0.0.1:8000";

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
  const [stats, setStats] = useState({
    total_papers: null,
    analyzed_papers: null,
    knowledge_nodes: null,
    contradictions: null,
    research_gaps: null,
  });

  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchDashboardData = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/papers/`);

        if (!response.ok) {
          throw new Error("Failed to fetch papers");
        }

        const papers = await response.json();

        // --------------------------------------------------
        // PAPER STATISTICS
        // --------------------------------------------------

        const totalPapers = papers.length;

        const analyzedPapers = papers.filter(
          (paper) => paper.status === "analyzed"
        ).length;

        // --------------------------------------------------
        // FUTURE ANALYSIS STATISTICS
        //
        // These are intentionally null when the backend does
        // not provide them yet.
        //
        // Once your analysis pipeline stores:
        //
        // analysis.knowledge_nodes
        // analysis.contradictions
        // analysis.research_gaps
        //
        // the dashboard will automatically display them.
        // --------------------------------------------------

        let knowledgeNodes = null;
        let contradictions = null;
        let researchGaps = null;

        const analyzedData = papers
          .filter((paper) => paper.analysis)
          .map((paper) => paper.analysis);

        // --------------------------------------------------
        // KNOWLEDGE NODES
        // --------------------------------------------------

        const papersWithKnowledgeNodes = analyzedData.filter(
          (analysis) =>
            typeof analysis.knowledge_nodes === "number"
        );

        if (papersWithKnowledgeNodes.length > 0) {
          knowledgeNodes = papersWithKnowledgeNodes.reduce(
            (total, analysis) =>
              total + analysis.knowledge_nodes,
            0
          );
        }

        // --------------------------------------------------
        // CONTRADICTIONS
        // --------------------------------------------------

        const papersWithContradictions = analyzedData.filter(
          (analysis) =>
            typeof analysis.contradictions === "number"
        );

        if (papersWithContradictions.length > 0) {
          contradictions = papersWithContradictions.reduce(
            (total, analysis) =>
              total + analysis.contradictions,
            0
          );
        }

        // --------------------------------------------------
        // RESEARCH GAPS
        // --------------------------------------------------

        const papersWithResearchGaps = analyzedData.filter(
          (analysis) =>
            typeof analysis.research_gaps === "number"
        );

        if (papersWithResearchGaps.length > 0) {
          researchGaps = papersWithResearchGaps.reduce(
            (total, analysis) =>
              total + analysis.research_gaps,
            0
          );
        }

        setStats({
          total_papers: totalPapers,
          analyzed_papers: analyzedPapers,
          knowledge_nodes: knowledgeNodes,
          contradictions: contradictions,
          research_gaps: researchGaps,
        });
      } catch (error) {
        console.error("Dashboard error:", error);

        setStats({
          total_papers: null,
          analyzed_papers: null,
          knowledge_nodes: null,
          contradictions: null,
          research_gaps: null,
        });
      } finally {
        setLoading(false);
      }
    };

    fetchDashboardData();
  }, []);

  // ------------------------------------------------------
  // DISPLAY HELPER
  // ------------------------------------------------------

  const displayValue = (value) => {
    if (loading) {
      return "—";
    }

    if (value === null || value === undefined) {
      return "—";
    }

    return value;
  };

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

          <div className="hidden items-center gap-2 rounded-full border border-emerald-400/10 bg-emerald-400/[0.05] px-3 py-1.5 sm:flex">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]" />

            <span className="text-xs text-emerald-300">
              Dashboard Active
            </span>
          </div>
        </div>
      </div>

      {/* ================= STATISTICS ================= */}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard
          icon={FileText}
          label="Research Papers"
          value={displayValue(stats.total_papers)}
          description={
            stats.analyzed_papers !== null
              ? `${stats.analyzed_papers} paper${
                  stats.analyzed_papers === 1 ? "" : "s"
                } analyzed`
              : "Analysis information unavailable"
          }
        />

        <StatCard
          icon={Network}
          label="Knowledge Nodes"
          value={displayValue(stats.knowledge_nodes)}
          description={
            stats.knowledge_nodes !== null
              ? "Research entities discovered"
              : "Knowledge graph data not available yet"
          }
        />

        <StatCard
          icon={GitBranch}
          label="Contradictions"
          value={displayValue(stats.contradictions)}
          description={
            stats.contradictions !== null
              ? "Contradictions detected"
              : "Contradiction detection not available yet"
          }
        />

        <StatCard
          icon={Lightbulb}
          label="Research Gaps"
          value={displayValue(stats.research_gaps)}
          description={
            stats.research_gaps !== null
              ? "Research opportunities detected"
              : "Research-gap detection not available yet"
          }
        />
      </div>

      {/* ================= MAIN CONTENT ================= */}

      <div className="mt-6 grid gap-6 xl:grid-cols-[1fr_360px]">
        {/* ================= KNOWLEDGE GRAPH ================= */}

        <section className="relative min-h-[420px] overflow-hidden rounded-2xl border border-white/[0.07] bg-slate-900/50 p-6">
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
                Research relationships will appear here when the
                knowledge graph is populated.
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
                {stats.knowledge_nodes !== null
                  ? `${stats.knowledge_nodes} research nodes available`
                  : "Knowledge graph not populated yet"}
              </h3>

              <p className="mx-auto mt-2 max-w-sm text-xs leading-5 text-slate-500">
                {stats.knowledge_nodes !== null
                  ? "Research entities are available for knowledge graph visualization."
                  : "Upload and analyze academic papers to build the research knowledge graph."}
              </p>
            </div>
          </div>
        </section>

        {/* ================= ANALYSIS STATUS ================= */}

        <section className="rounded-2xl border border-white/[0.07] bg-slate-900/50 p-6">
          <div className="mb-6">
            <p className="text-[10px] font-medium uppercase tracking-[0.2em] text-indigo-400">
              Analysis
            </p>

            <h2 className="mt-2 text-base font-semibold text-white">
              Processing Status
            </h2>

            <p className="mt-1 text-xs text-slate-500">
              Current paper analysis state
            </p>
          </div>

          <div className="space-y-3">
            {/* Total Papers */}

            <div className="flex items-center justify-between rounded-xl border border-white/[0.06] bg-slate-950/70 px-4 py-3">
              <span className="text-sm text-slate-400">
                Total Papers
              </span>

              <span className="text-sm font-medium text-white">
                {displayValue(stats.total_papers)}
              </span>
            </div>

            {/* Analyzed Papers */}

            <div className="flex items-center justify-between rounded-xl border border-white/[0.06] bg-slate-950/70 px-4 py-3">
              <span className="text-sm text-slate-400">
                Analyzed Papers
              </span>

              <span className="text-sm font-medium text-indigo-300">
                {displayValue(stats.analyzed_papers)}
              </span>
            </div>

            {/* Pending Analysis */}

            <div className="flex items-center justify-between rounded-xl border border-white/[0.06] bg-slate-950/70 px-4 py-3">
              <span className="text-sm text-slate-400">
                Pending Analysis
              </span>

              <span className="text-sm font-medium text-slate-300">
                {loading
                  ? "—"
                  : stats.total_papers !== null &&
                    stats.analyzed_papers !== null
                  ? Math.max(
                      stats.total_papers -
                        stats.analyzed_papers,
                      0
                    )
                  : "—"}
              </span>
            </div>

            {/* Analysis Engine */}

            <div className="flex items-center justify-between rounded-xl border border-white/[0.06] bg-slate-950/70 px-4 py-3">
              <span className="text-sm text-slate-400">
                Analysis Engine
              </span>

              <div className="flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-[0_0_7px_rgba(52,211,153,0.8)]" />

                <span className="text-xs text-emerald-300">
                  Available
                </span>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

export default Dashboard;