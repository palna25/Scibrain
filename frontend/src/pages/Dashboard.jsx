import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  FileText,
  Network,
  Lightbulb,
  BookOpen,
  ArrowUpRight,
  RefreshCw,
  Loader2,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";

const API_BASE_URL = "http://127.0.0.1:8000";

function StatCard({
  icon: Icon,
  label,
  value,
  description,
  onClick,
  accent = "indigo",
}) {
  const accents = {
    indigo: "border-indigo-400/15 bg-indigo-500/10 text-indigo-400",
    cyan: "border-cyan-400/15 bg-cyan-500/10 text-cyan-400",
    violet: "border-violet-400/15 bg-violet-500/10 text-violet-400",
    emerald: "border-emerald-400/15 bg-emerald-500/10 text-emerald-400",
  };

  return (
    <button
      type="button"
      onClick={onClick}
      className="group w-full rounded-2xl border border-white/[0.07] bg-slate-900/50 p-5 text-left transition hover:border-indigo-400/25 hover:bg-slate-900/80 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400/60"
    >
      <div className="flex items-start justify-between">
        <div
          className={`flex h-10 w-10 items-center justify-center rounded-xl border ${
            accents[accent] || accents.indigo
          }`}
        >
          <Icon className="h-5 w-5" />
        </div>

        <ArrowUpRight className="h-4 w-4 text-slate-700 transition group-hover:text-indigo-400" />
      </div>

      <div className="mt-5">
        <p className="text-2xl font-semibold tracking-tight text-white">
          {value}
        </p>

        <p className="mt-1 text-sm text-slate-400">{label}</p>

        <p className="mt-2 text-xs leading-5 text-slate-500">
          {description}
        </p>
      </div>
    </button>
  );
}

function FeatureCard({
  icon: Icon,
  eyebrow,
  title,
  description,
  actionLabel,
  onClick,
  accent = "indigo",
}) {
  const styles = {
    indigo: {
      icon: "border-indigo-400/15 bg-indigo-500/10 text-indigo-400",
      glow: "bg-indigo-500/[0.08]",
    },
    cyan: {
      icon: "border-cyan-400/15 bg-cyan-500/10 text-cyan-400",
      glow: "bg-cyan-500/[0.07]",
    },
    violet: {
      icon: "border-violet-400/15 bg-violet-500/10 text-violet-400",
      glow: "bg-violet-500/[0.07]",
    },
  };

  const style = styles[accent] || styles.indigo;

  return (
    <button
      type="button"
      onClick={onClick}
      className="group relative w-full overflow-hidden rounded-2xl border border-white/[0.07] bg-slate-900/50 p-5 text-left transition hover:border-indigo-400/20 hover:bg-slate-900/80 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400/60 sm:p-6"
    >
      <div
        className={`pointer-events-none absolute -right-12 -top-12 h-36 w-36 rounded-full blur-3xl ${style.glow}`}
      />

      <div className="relative flex items-start justify-between gap-4">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-indigo-400">
            {eyebrow}
          </p>

          <h3 className="mt-2 text-base font-semibold text-white">
            {title}
          </h3>
        </div>

        <div
          className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border ${style.icon}`}
        >
          <Icon className="h-5 w-5" />
        </div>
      </div>

      <p className="relative mt-3 min-h-[60px] text-sm leading-6 text-slate-400">
        {description}
      </p>

      <div className="relative mt-5 flex items-center justify-between border-t border-white/[0.06] pt-4">
        <span className="text-xs font-medium text-slate-300 transition group-hover:text-white">
          {actionLabel}
        </span>

        <ArrowUpRight className="h-4 w-4 text-slate-600 transition group-hover:translate-x-0.5 group-hover:-translate-y-0.5 group-hover:text-indigo-400" />
      </div>
    </button>
  );
}

function Dashboard() {
  const navigate = useNavigate();

  const [stats, setStats] = useState({
    totalPapers: null,
    readyPapers: null,
    totalNotebooks: null,
    totalChats: null,
  });

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [errors, setErrors] = useState([]);

  const fetchDashboardData = useCallback(async (isRefresh = false) => {
    if (isRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }

    setErrors([]);

    const token = localStorage.getItem("scibrain_token");

    const headers = token
      ? { Authorization: `Bearer ${token}` }
      : {};

    const requestJson = async (url) => {
      const response = await fetch(url, { headers });

      if (!response.ok) {
        throw new Error(
          response.status === 401 || response.status === 403
            ? "Your session may have expired. Please sign in again."
            : `Request failed (${response.status}).`
        );
      }

      return response.json();
    };

    const nextStats = {
      totalPapers: null,
      readyPapers: null,
      totalNotebooks: null,
      totalChats: null,
    };

    const nextErrors = [];

    try {
      const papersData = await requestJson(`${API_BASE_URL}/api/papers/`);

      if (!Array.isArray(papersData)) {
        throw new Error("Unexpected papers response.");
      }

      nextStats.totalPapers = papersData.length;
      nextStats.readyPapers = papersData.filter(
        (paper) => paper.status === "ready"
      ).length;
    } catch (error) {
      console.error("Dashboard papers error:", error);
      nextErrors.push(`Papers: ${error.message}`);
    }

    try {
      const notebooksData = await requestJson(
        `${API_BASE_URL}/api/notebook`
      );

      if (!Array.isArray(notebooksData.notebooks)) {
        throw new Error("Unexpected notebooks response.");
      }

      const notebooks = notebooksData.notebooks;

      nextStats.totalNotebooks = notebooks.length;

      // Each saved chat belongs to a notebook.
      // Count chat records, not individual messages.
      if (notebooks.length === 0) {
        nextStats.totalChats = 0;
      } else {
        const chatResults = await Promise.allSettled(
          notebooks.map(async (notebook) => {
            if (!notebook.notebook_id) {
              throw new Error("A notebook is missing its ID.");
            }

            const encodedId = encodeURIComponent(
              notebook.notebook_id
            );

            const chatData = await requestJson(
              `${API_BASE_URL}/api/notebook/${encodedId}/chats`
            );

            if (!Array.isArray(chatData.chats)) {
              throw new Error(
                `Unexpected chat response for notebook ${notebook.notebook_id}.`
              );
            }

            return chatData.chats.length;
          })
        );

        const failedChatRequests = chatResults.filter(
          (result) => result.status === "rejected"
        );

        if (failedChatRequests.length === 0) {
          nextStats.totalChats = chatResults.reduce(
            (total, result) => total + result.value,
            0
          );
        } else {
          // Never show a partial total as if it were complete.
          nextStats.totalChats = null;

          console.error(
            "Some notebook chat counts could not be loaded:",
            failedChatRequests
          );

          nextErrors.push(
            "Chats: Unable to retrieve chats from every notebook."
          );
        }
      }
    } catch (error) {
      console.error("Dashboard notebooks error:", error);
      nextErrors.push(`Notebooks: ${error.message}`);
    }

    setStats(nextStats);
    setErrors(nextErrors);
    setLoading(false);
    setRefreshing(false);
  }, []);

  useEffect(() => {
    fetchDashboardData();
  }, [fetchDashboardData]);

  const displayValue = (value) => {
    if (loading || value === null || value === undefined) {
      return "—";
    }

    return value;
  };

  const openPapers = () => navigate("/papers");
  const openKnowledgeGraph = () => navigate("/knowledge-graph");
  const openResearchGaps = () => navigate("/research-gaps");
  const openNotebook = () => navigate("/notebook");

  return (
    <div className="space-y-7">
      {/* PAGE HEADER */}
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.25em] text-indigo-400">
            Research Intelligence
          </p>

          <h1 className="text-3xl font-semibold tracking-tight text-white">
            Research Dashboard
          </h1>

          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
            Your research workspace for exploring academic literature,
            connecting knowledge, and discovering research opportunities.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="hidden items-center gap-2 rounded-full border border-white/[0.07] bg-slate-900/60 px-3 py-2 sm:flex">
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                errors.length > 0 ? "bg-amber-400" : "bg-emerald-400"
              }`}
            />

            <span className="text-xs text-slate-400">
              {errors.length > 0
                ? "Some data unavailable"
                : "Research workspace"}
            </span>
          </div>

          <button
            type="button"
            onClick={() => fetchDashboardData(true)}
            disabled={loading || refreshing}
            className="inline-flex items-center gap-2 rounded-xl border border-white/[0.08] bg-slate-900/70 px-3 py-2.5 text-xs font-medium text-slate-300 transition hover:border-indigo-400/25 hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
          >
            {refreshing ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            Refresh
          </button>
        </div>
      </div>

      {/* DATA ERRORS */}
      {errors.length > 0 && (
        <div className="flex items-start gap-3 rounded-xl border border-amber-400/15 bg-amber-500/[0.05] p-4">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" />

          <div>
            <p className="text-sm font-medium text-amber-300">
              Some dashboard statistics could not be loaded
            </p>

            <ul className="mt-1 space-y-1">
              {errors.map((error) => (
                <li
                  key={error}
                  className="text-xs leading-5 text-slate-400"
                >
                  {error}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* WORKSPACE STATISTICS */}
      <section>
        <div className="mb-4">
          <h2 className="text-sm font-semibold text-white">
            Workspace Overview
          </h2>

          <p className="mt-1 text-xs text-slate-500">
            Your papers, notebooks, and research conversations
          </p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard
            icon={FileText}
            label="Research Papers"
            value={displayValue(stats.totalPapers)}
            description="Papers in your research library"
            onClick={openPapers}
            accent="indigo"
          />

          <StatCard
            icon={CheckCircle2}
            label="Ready Papers"
            value={displayValue(stats.readyPapers)}
            description="Papers available for retrieval"
            onClick={openPapers}
            accent="emerald"
          />

          <StatCard
            icon={BookOpen}
            label="Notebooks"
            value={displayValue(stats.totalNotebooks)}
            description="Research notebooks created"
            onClick={openNotebook}
            accent="cyan"
          />

          <StatCard
            icon={Lightbulb}
            label="Research Chats"
            value={displayValue(stats.totalChats)}
            description="Saved conversations across your notebooks"
            onClick={openNotebook}
            accent="violet"
          />
        </div>
      </section>

      {/* MAIN CONTENT */}
      <div className="grid gap-6 xl:grid-cols-[1fr_340px]">
        {/* RESEARCH TOOLS */}
        <section className="min-w-0">
          <div className="mb-4">
            <h2 className="text-sm font-semibold text-white">
              Research Tools
            </h2>

            <p className="mt-1 text-xs text-slate-500">
              Continue exploring your papers with SciBrain's research tools.
            </p>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <FeatureCard
              icon={Network}
              eyebrow="Knowledge Graph"
              title="Explore Research Connections"
              description="Explore entities and evidence-backed relationships extracted from your selected research papers."
              actionLabel="Open Knowledge Graph"
              onClick={openKnowledgeGraph}
              accent="indigo"
            />

            <FeatureCard
              icon={Lightbulb}
              eyebrow="Research Gaps"
              title="Discover Research Opportunities"
              description="Investigate potential research gaps grounded in evidence from your selected academic literature."
              actionLabel="Explore Research Gaps"
              onClick={openResearchGaps}
              accent="violet"
            />

            <FeatureCard
              icon={BookOpen}
              eyebrow="Notebook"
              title="Research in Context"
              description="Work with selected papers, ask questions, and revisit saved research conversations."
              actionLabel="Open Notebooks"
              onClick={openNotebook}
              accent="cyan"
            />

            <FeatureCard
              icon={FileText}
              eyebrow="Paper Library"
              title="Manage Your Literature"
              description="Review your uploaded papers and check which papers are ready for research workflows."
              actionLabel="View Research Papers"
              onClick={openPapers}
              accent="indigo"
            />
          </div>
        </section>

        {/* WORKSPACE ACTIVITY */}
        <section className="h-fit rounded-2xl border border-white/[0.07] bg-slate-900/50 p-5 sm:p-6">
          <div className="mb-5">
            <p className="text-[10px] font-medium uppercase tracking-[0.2em] text-indigo-400">
              Workspace
            </p>

            <h2 className="mt-2 text-base font-semibold text-white">
              Research Activity
            </h2>

            <p className="mt-1 text-xs leading-5 text-slate-500">
              A summary of the resources and conversations you have saved.
            </p>
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between rounded-xl border border-white/[0.06] bg-slate-950/70 px-4 py-3">
              <span className="text-sm text-slate-400">
                Research Papers
              </span>

              <span className="text-sm font-medium text-white">
                {displayValue(stats.totalPapers)}
              </span>
            </div>

            <div className="flex items-center justify-between rounded-xl border border-white/[0.06] bg-slate-950/70 px-4 py-3">
              <span className="text-sm text-slate-400">
                Ready Papers
              </span>

              <span className="text-sm font-medium text-emerald-300">
                {displayValue(stats.readyPapers)}
              </span>
            </div>

            <div className="flex items-center justify-between rounded-xl border border-white/[0.06] bg-slate-950/70 px-4 py-3">
              <span className="text-sm text-slate-400">
                Notebooks
              </span>

              <span className="text-sm font-medium text-cyan-300">
                {displayValue(stats.totalNotebooks)}
              </span>
            </div>

            <div className="flex items-center justify-between rounded-xl border border-white/[0.06] bg-slate-950/70 px-4 py-3">
              <span className="text-sm text-slate-400">
                Research Chats
              </span>

              <span className="text-sm font-medium text-violet-300">
                {displayValue(stats.totalChats)}
              </span>
            </div>
          </div>

          {!loading &&
            stats.totalNotebooks === 0 &&
            stats.totalChats === 0 && (
              <div className="mt-5 rounded-xl border border-dashed border-white/[0.1] px-4 py-5 text-center">
                <BookOpen className="mx-auto h-6 w-6 text-slate-600" />

                <p className="mt-3 text-sm font-medium text-slate-300">
                  Start a research notebook
                </p>

                <p className="mt-1 text-xs leading-5 text-slate-500">
                  Create a notebook to organize papers and save research chats.
                </p>

                <button
                  type="button"
                  onClick={openNotebook}
                  className="mt-4 rounded-lg border border-indigo-400/20 bg-indigo-500/10 px-3 py-2 text-xs font-medium text-indigo-300 transition hover:bg-indigo-500/15"
                >
                  Open Notebooks
                </button>
              </div>
            )}
        </section>
      </div>

      {/* FOOTER NOTE */}
      <div className="flex items-start gap-3 rounded-xl border border-white/[0.06] bg-slate-900/30 px-4 py-3">
        <Network className="mt-0.5 h-4 w-4 shrink-0 text-indigo-400" />

        <p className="text-xs leading-5 text-slate-500">
          Knowledge Graph and Research Gaps work with selected research papers.
          Their results depend on the evidence available in your workspace.
        </p>
      </div>
    </div>
  );
}

export default Dashboard;