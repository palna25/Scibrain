import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  BookOpen,
  ChevronRight,
  FileText,
  Lightbulb,
  Loader2,
  RefreshCw,
  Search,
  Sparkles,
  X,
} from "lucide-react";

import AppLayout from "../components/AppLayout";
import { useResearchContext } from "../context/ResearchContext";

const API_URL = "http://127.0.0.1:8000";

function ResearchGaps() {
  const navigate = useNavigate();

  const {
    selectedResourceIds,
    clearResources,
  } = useResearchContext();

  const [papers, setPapers] = useState([]);
  const [gaps, setGaps] = useState([]);
  const [selectedGap, setSelectedGap] = useState(null);

  const [loadingPapers, setLoadingPapers] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState("");

  const [searchQuery, setSearchQuery] = useState("");

  // --------------------------------------------------
  // Load paper metadata
  // --------------------------------------------------

  useEffect(() => {
    const loadPapers = async () => {
      try {
        setLoadingPapers(true);

        const response = await fetch(`${API_URL}/api/papers/`);

        if (!response.ok) {
          throw new Error("Failed to load research sources.");
        }

        const data = await response.json();

        setPapers(
          data.map((paper) => ({
            id: paper.id,
            title:
              paper.title ||
              paper.filename ||
              "Untitled Research Paper",
            filename: paper.filename || "",
            pageCount: paper.page_count || 0,
          }))
        );
      } catch (err) {
        console.error(err);
        setError(err.message);
      } finally {
        setLoadingPapers(false);
      }
    };

    loadPapers();
  }, []);

  // --------------------------------------------------
  // Selected resources
  // --------------------------------------------------

  const selectedPapers = useMemo(
    () =>
      papers.filter((paper) =>
        selectedResourceIds.includes(String(paper.id))
      ),
    [papers, selectedResourceIds]
  );

  const filteredGaps = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();

    if (!query) {
      return gaps;
    }

    return gaps.filter((gap) => {
      const text = [
        gap.title,
        gap.description,
        gap.why_gap,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();

      return text.includes(query);
    });
  }, [gaps, searchQuery]);

  // --------------------------------------------------
  // Analyze gaps
  // --------------------------------------------------

  const analyzeGaps = async () => {
    if (selectedResourceIds.length === 0) {
      setError(
        "Select at least one research source in the Research Notebook."
      );
      return;
    }

    try {
      setAnalyzing(true);
      setError("");
      setSelectedGap(null);

      const response = await fetch(
        `${API_URL}/api/research-gaps/analyze`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            resource_ids: selectedResourceIds,
          }),
        }
      );

      if (!response.ok) {
        const message = await response.text();
        throw new Error(
          message || "Research gap analysis failed."
        );
      }

      const data = await response.json();

      setGaps(Array.isArray(data.gaps) ? data.gaps : []);
    } catch (err) {
      console.error(err);
      setError(err.message || "Research gap analysis failed.");
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <AppLayout>
      <div className="min-h-[calc(100vh-6rem)]">

        {/* Header */}

        <div className="flex flex-col gap-5 border-b border-white/[0.06] pb-6 lg:flex-row lg:items-center lg:justify-between">

          <div className="flex items-start gap-3">

            <button
              type="button"
              onClick={() => navigate("/research-notebook")}
              className="mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-white/[0.07] bg-slate-900/60 text-slate-500 transition hover:bg-white/[0.04] hover:text-slate-200"
            >
              <ArrowLeft className="h-4 w-4" />
            </button>

            <div>
              <div className="flex items-center gap-2">
                <Lightbulb className="h-4 w-4 text-indigo-400" />

                <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-indigo-400">
                  Research Intelligence
                </p>
              </div>

              <h1 className="mt-2 text-2xl font-semibold tracking-tight text-white">
                Research Gaps
              </h1>

              <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
                Identify potential unexplored research areas from
                the sources selected in your research notebook.
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={analyzeGaps}
            disabled={
              analyzing ||
              selectedResourceIds.length === 0
            }
            className="flex shrink-0 items-center justify-center gap-2 rounded-xl bg-indigo-500 px-4 py-2.5 text-xs font-medium text-white shadow-lg shadow-indigo-500/20 transition hover:bg-indigo-400 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {analyzing ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Analyzing...
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4" />
                Analyze Research Gaps
              </>
            )}
          </button>
        </div>

        {/* Main */}

        <div className="mt-6 grid gap-6 xl:grid-cols-[330px_minmax(0,1fr)]">

          {/* Research Context */}

          <aside className="h-fit rounded-2xl border border-white/[0.07] bg-slate-950/40">

            <div className="border-b border-white/[0.06] p-5">

              <div className="flex items-center gap-2">
                <BookOpen className="h-4 w-4 text-indigo-400" />

                <p className="text-xs font-medium text-slate-300">
                  Research Context
                </p>
              </div>

              <p className="mt-1 text-[10px] leading-4 text-slate-600">
                Sources currently selected in your notebook.
              </p>

            </div>

            <div className="p-4">

              <div className="mb-4 flex items-center justify-between">

                <span className="text-[10px] uppercase tracking-[0.15em] text-slate-600">
                  Selected Sources
                </span>

                <span className="text-xs text-indigo-400">
                  {selectedResourceIds.length}
                </span>

              </div>

              {loadingPapers ? (
                <div className="flex justify-center py-8">
                  <Loader2 className="h-5 w-5 animate-spin text-indigo-400" />
                </div>
              ) : selectedPapers.length === 0 ? (
                <div className="rounded-xl border border-dashed border-white/[0.07] p-5 text-center">

                  <FileText className="mx-auto h-5 w-5 text-slate-700" />

                  <p className="mt-3 text-xs text-slate-500">
                    No sources selected.
                  </p>

                  <button
                    type="button"
                    onClick={() =>
                      navigate("/research-notebook")
                    }
                    className="mt-3 text-[10px] font-medium text-indigo-400 hover:text-indigo-300"
                  >
                    Return to notebook
                  </button>

                </div>
              ) : (
                <div className="space-y-2">

                  {selectedPapers.map((paper) => (
                    <div
                      key={paper.id}
                      className="flex items-center gap-2 rounded-xl border border-white/[0.05] bg-slate-900/50 p-2.5"
                    >
                      <FileText className="h-3.5 w-3.5 shrink-0 text-indigo-400" />

                      <span className="min-w-0 flex-1 truncate text-[10px] text-slate-400">
                        {paper.title}
                      </span>
                    </div>
                  ))}

                </div>
              )}

              {selectedPapers.length > 0 && (
                <button
                  type="button"
                  onClick={clearResources}
                  className="mt-4 flex items-center gap-1.5 text-[10px] text-slate-600 transition hover:text-slate-300"
                >
                  <X className="h-3 w-3" />
                  Clear selected sources
                </button>
              )}

            </div>

          </aside>

          {/* Gap Results */}

          <section className="min-w-0">

            {error && (
              <div className="mb-5 rounded-xl border border-red-400/10 bg-red-500/[0.04] px-4 py-3 text-xs text-red-300">
                {error}
              </div>
            )}

            <div className="mb-4 flex items-center justify-between gap-4">

              <div>
                <p className="text-sm font-medium text-slate-200">
                  Potential Research Gaps
                </p>

                <p className="mt-1 text-[10px] text-slate-600">
                  {gaps.length}{" "}
                  {gaps.length === 1 ? "potential gap" : "potential gaps"}{" "}
                  identified
                </p>
              </div>

              {gaps.length > 0 && (
                <div className="relative w-52">
                  <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-600" />

                  <input
                    value={searchQuery}
                    onChange={(e) =>
                      setSearchQuery(e.target.value)
                    }
                    placeholder="Search gaps..."
                    className="h-9 w-full rounded-xl border border-white/[0.07] bg-slate-900/60 pl-9 pr-3 text-xs text-slate-300 outline-none placeholder:text-slate-600 focus:border-indigo-400/20"
                  />
                </div>
              )}
            </div>

            {analyzing ? (
              <LoadingState />
            ) : gaps.length === 0 ? (
              <EmptyState
                hasSources={selectedResourceIds.length > 0}
                onAnalyze={analyzeGaps}
              />
            ) : filteredGaps.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-white/[0.07] p-12 text-center">

                <Search className="mx-auto h-6 w-6 text-slate-700" />

                <p className="mt-3 text-sm text-slate-400">
                  No matching research gaps
                </p>

              </div>
            ) : (
              <div className="grid gap-3">

                {filteredGaps.map((gap, index) => (
                  <GapCard
                    key={gap.id || index}
                    gap={gap}
                    index={index}
                    onClick={() => setSelectedGap(gap)}
                  />
                ))}

              </div>
            )}

          </section>
        </div>

        {selectedGap && (
          <GapDetails
            gap={selectedGap}
            onClose={() => setSelectedGap(null)}
          />
        )}

      </div>
    </AppLayout>
  );
}

// ======================================================
// Gap Card
// ======================================================

function GapCard({ gap, index, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group w-full rounded-2xl border border-white/[0.06] bg-slate-950/40 p-5 text-left transition hover:border-indigo-400/15 hover:bg-indigo-500/[0.025]"
    >
      <div className="flex gap-4">

        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-indigo-400/10 bg-indigo-500/[0.06] text-xs font-semibold text-indigo-400">
          {String(index + 1).padStart(2, "0")}
        </div>

        <div className="min-w-0 flex-1">

          <div className="flex items-start justify-between gap-4">

            <h3 className="text-sm font-medium text-slate-200">
              {gap.title || "Potential Research Gap"}
            </h3>

            <ChevronRight className="mt-0.5 h-4 w-4 shrink-0 text-slate-700 transition group-hover:translate-x-0.5 group-hover:text-indigo-400" />

          </div>

          {gap.description && (
            <p className="mt-2 text-xs leading-5 text-slate-500">
              {gap.description}
            </p>
          )}

          {gap.evidence?.length > 0 && (
            <div className="mt-4 flex items-center gap-2 text-[10px] text-slate-600">
              <FileText className="h-3.5 w-3.5" />
              {gap.evidence.length} evidence{" "}
              {gap.evidence.length === 1
                ? "source"
                : "sources"}
            </div>
          )}

        </div>
      </div>
    </button>
  );
}

// ======================================================
// Gap Details
// ======================================================

function GapDetails({ gap, onClose }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-6 backdrop-blur-sm">

      <div className="max-h-[85vh] w-full max-w-3xl overflow-y-auto rounded-2xl border border-white/[0.08] bg-slate-900 shadow-2xl">

        <div className="sticky top-0 flex items-start justify-between border-b border-white/[0.06] bg-slate-900 p-6">

          <div className="flex gap-3">

            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-indigo-400/15 bg-indigo-500/10">
              <Lightbulb className="h-5 w-5 text-indigo-400" />
            </div>

            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-indigo-400">
                Potential Research Gap
              </p>

              <h2 className="mt-1 text-base font-semibold text-white">
                {gap.title || "Research Gap"}
              </h2>
            </div>

          </div>

          <button
            type="button"
            onClick={onClose}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-600 hover:bg-white/[0.04] hover:text-slate-300"
          >
            <X className="h-4 w-4" />
          </button>

        </div>

        <div className="space-y-6 p-6">

          {gap.description && (
            <DetailSection title="Description">
              <p>{gap.description}</p>
            </DetailSection>
          )}

          {gap.why_gap && (
            <DetailSection title="Why this appears to be a gap">
              <p>{gap.why_gap}</p>
            </DetailSection>
          )}

          {gap.evidence?.length > 0 && (
            <DetailSection title="Evidence from selected sources">

              <div className="space-y-3">

                {gap.evidence.map((item, index) => (
                  <div
                    key={item.resource_id || index}
                    className="rounded-xl border border-white/[0.06] bg-slate-950/40 p-4"
                  >
                    <div className="flex items-center gap-2">

                      <FileText className="h-3.5 w-3.5 text-indigo-400" />

                      <p className="text-xs font-medium text-slate-300">
                        {item.paper_title ||
                          "Selected research source"}
                      </p>

                    </div>

                    {item.statement && (
                      <p className="mt-2 text-xs leading-5 text-slate-500">
                        {item.statement}
                      </p>
                    )}
                  </div>
                ))}

              </div>

            </DetailSection>
          )}

        </div>

      </div>
    </div>
  );
}

// ======================================================
// Detail Section
// ======================================================

function DetailSection({ title, children }) {
  return (
    <section>
      <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.15em] text-slate-600">
        {title}
      </p>

      <div className="text-sm leading-6 text-slate-400">
        {children}
      </div>
    </section>
  );
}

// ======================================================
// Loading
// ======================================================

function LoadingState() {
  return (
    <div className="flex min-h-[400px] flex-col items-center justify-center rounded-2xl border border-white/[0.06] bg-slate-950/30">

      <Loader2 className="h-7 w-7 animate-spin text-indigo-400" />

      <p className="mt-4 text-sm font-medium text-slate-300">
        Analyzing selected literature
      </p>

      <p className="mt-2 text-xs text-slate-600">
        SciBrain is examining the selected research sources.
      </p>

    </div>
  );
}

// ======================================================
// Empty
// ======================================================

function EmptyState({ hasSources, onAnalyze }) {
  return (
    <div className="flex min-h-[400px] flex-col items-center justify-center rounded-2xl border border-dashed border-white/[0.07] bg-slate-950/20 px-6 text-center">

      <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-indigo-400/10 bg-indigo-500/[0.06]">
        <Lightbulb className="h-6 w-6 text-indigo-400" />
      </div>

      <h2 className="mt-5 text-sm font-medium text-slate-300">
        {hasSources
          ? "No research gap analysis yet"
          : "Select research sources first"}
      </h2>

      <p className="mt-2 max-w-md text-xs leading-5 text-slate-600">
        {hasSources
          ? "Analyze the selected literature to identify potential unexplored research areas."
          : "Return to the Research Notebook and select the papers you want SciBrain to investigate."}
      </p>

      <button
        type="button"
        onClick={hasSources ? onAnalyze : undefined}
        className="mt-5 flex items-center gap-2 rounded-xl border border-white/[0.07] bg-slate-900 px-4 py-2.5 text-xs font-medium text-slate-300 transition hover:bg-white/[0.04] disabled:cursor-not-allowed"
        disabled={!hasSources}
      >
        {hasSources ? (
          <>
            <RefreshCw className="h-3.5 w-3.5" />
            Analyze selected sources
          </>
        ) : (
          <>
            <BookOpen className="h-3.5 w-3.5" />
            Select sources
          </>
        )}
      </button>

    </div>
  );
}

export default ResearchGaps;