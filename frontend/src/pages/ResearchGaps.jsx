import { useCallback, useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  BookOpen,
  Check,
  ChevronRight,
  Clock,
  FileText,
  Lightbulb,
  Loader2,
  RefreshCw,
  Search,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";

import AppLayout from "../components/AppLayout";

const API_URL = "http://127.0.0.1:8000";
const ACTIVE_NOTEBOOK_KEY = "scibrain_active_notebook_id";

function getAuthHeaders() {
  const token = localStorage.getItem("scibrain_token");

  return token ? { Authorization: `Bearer ${token}` } : {};
}

function getPaperId(paper) {
  return String(paper?.id ?? paper?.paper_id ?? paper?._id ?? "");
}

async function readResponse(response) {
  return response.json().catch(() => null);
}

function getErrorMessage(data, fallback) {
  return typeof data?.detail === "string"
    ? data.detail
    : typeof data?.message === "string"
      ? data.message
      : fallback;
}

function ResearchGaps() {
  const navigate = useNavigate();
  const location = useLocation();
  const { notebookId: routeNotebookId } = useParams();

  // Research Gaps still uses a notebook as its analysis workspace.
  // Its paper selection, however, is managed independently.
  const notebookId = String(
    location.state?.notebookId ||
      routeNotebookId ||
      sessionStorage.getItem(ACTIVE_NOTEBOOK_KEY) ||
      ""
  );

  const [notebook, setNotebook] = useState(null);
  const [papers, setPapers] = useState([]);
  const [gaps, setGaps] = useState([]);
  const [selectedGap, setSelectedGap] = useState(null);

  const [loadingNotebook, setLoadingNotebook] = useState(true);
  const [loadingPapers, setLoadingPapers] = useState(true);
  const [loadingSourceSelection, setLoadingSourceSelection] =
    useState(true);
  const [sourceSelectionLoaded, setSourceSelectionLoaded] =
    useState(false);
  const [analyzing, setAnalyzing] = useState(false);

  const [selectedResourceIds, setSelectedResourceIds] = useState([]);
  const [sourceManagerOpen, setSourceManagerOpen] = useState(false);
  const [savingSourceSelection, setSavingSourceSelection] =
    useState(false);

  const [error, setError] = useState("");
  const [searchQuery, setSearchQuery] = useState("");

  const [savedAnalyses, setSavedAnalyses] = useState([]);
  const [loadingSavedAnalyses, setLoadingSavedAnalyses] =
    useState(false);
  const [activeAnalysisId, setActiveAnalysisId] = useState(null);
  const [deletingAnalysisId, setDeletingAnalysisId] = useState(null);

  // --------------------------------------------------
  // Load notebook
  // --------------------------------------------------

  const loadNotebook = useCallback(async () => {
    if (!notebookId) {
      setNotebook(null);
      setLoadingNotebook(false);
      setError(
        "No active research notebook was found. Open a notebook and launch Research Gaps from there."
      );
      return;
    }

    try {
      setLoadingNotebook(true);
      setError("");

      const response = await fetch(
        `${API_URL}/api/notebook/${encodeURIComponent(notebookId)}`,
        { headers: getAuthHeaders() }
      );
      const data = await readResponse(response);

      if (response.status === 401) {
        throw new Error(
          "Your session has expired. Please log in again."
        );
      }

      if (response.status === 404) {
        throw new Error(
          "This research notebook could not be found."
        );
      }

      if (!response.ok) {
        throw new Error(
          getErrorMessage(data, "Unable to load this research notebook.")
        );
      }

      const loadedNotebook = data?.notebook || null;

      if (!loadedNotebook) {
        throw new Error(
          "The server did not return the requested notebook."
        );
      }

      setNotebook(loadedNotebook);

      sessionStorage.setItem(
        ACTIVE_NOTEBOOK_KEY,
        String(loadedNotebook.notebook_id || notebookId)
      );
    } catch (err) {
      console.error("Research notebook loading error:", err);
      setNotebook(null);
      setError(err.message || "Unable to load this research notebook.");
    } finally {
      setLoadingNotebook(false);
    }
  }, [notebookId]);

  // --------------------------------------------------
  // Load available paper metadata
  // --------------------------------------------------

  const loadPapers = useCallback(async () => {
    try {
      setLoadingPapers(true);

      const response = await fetch(`${API_URL}/api/papers/`, {
        headers: getAuthHeaders(),
      });
      const data = await readResponse(response);

      if (response.status === 401) {
        throw new Error(
          "Your session has expired. Please log in again."
        );
      }

      if (!response.ok) {
        throw new Error(
          getErrorMessage(data, "Failed to load research sources.")
        );
      }

      const paperList = Array.isArray(data)
        ? data
        : Array.isArray(data?.papers)
          ? data.papers
          : [];

      setPapers(
        paperList
          .map((paper) => ({
            ...paper,
            id: getPaperId(paper),
            title:
              paper.title ||
              paper.filename ||
              "Untitled Research Paper",
            filename: paper.filename || "",
            pageCount: paper.page_count || 0,
          }))
          .filter((paper) => paper.id)
      );
    } catch (err) {
      console.error("Research papers loading error:", err);
      setError(err.message || "Failed to load research sources.");
      setPapers([]);
    } finally {
      setLoadingPapers(false);
    }
  }, []);

  // --------------------------------------------------
  // Independent Research Gaps source selection
  // --------------------------------------------------

  const loadResearchGapSources = useCallback(async () => {
    if (!notebookId) {
      setSelectedResourceIds([]);
      setSourceSelectionLoaded(false);
      setLoadingSourceSelection(false);
      return;
    }

    try {
      setLoadingSourceSelection(true);
      setSourceSelectionLoaded(false);

      const response = await fetch(
        `${API_URL}/api/research-gaps/sources?notebook_id=${encodeURIComponent(
          notebookId
        )}`,
        { headers: getAuthHeaders() }
      );
      const data = await readResponse(response);

      if (response.status === 401) {
        throw new Error(
          "Your session has expired. Please log in again."
        );
      }

      if (!response.ok) {
        throw new Error(
          getErrorMessage(
            data,
            "Unable to load Research Gaps sources."
          )
        );
      }

      const ids = Array.isArray(data?.resource_ids)
        ? [
            ...new Set(
              data.resource_ids.map(String).filter(Boolean)
            ),
          ]
        : [];

      setSelectedResourceIds(ids);
      setSourceSelectionLoaded(true);
    } catch (err) {
      console.error("Research Gaps source loading error:", err);
      setSelectedResourceIds([]);
      setSourceSelectionLoaded(false);
      setError(err.message || "Unable to load Research Gaps sources.");
    } finally {
      setLoadingSourceSelection(false);
    }
  }, [notebookId]);

  const saveResearchGapSources = async (nextResourceIds) => {
    if (!notebookId || !notebook) {
      setError("Open a research notebook before managing sources.");
      return false;
    }

    try {
      setSavingSourceSelection(true);
      setError("");

      const uniqueIds = [
        ...new Set(
          nextResourceIds.map(String).filter(Boolean)
        ),
      ];

      const response = await fetch(
        `${API_URL}/api/research-gaps/sources`,
        {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            ...getAuthHeaders(),
          },
          body: JSON.stringify({
            notebook_id: notebookId,
            resource_ids: uniqueIds,
          }),
        }
      );

      const data = await readResponse(response);

      if (response.status === 401) {
        throw new Error(
          "Your session has expired. Please log in again."
        );
      }

      if (!response.ok) {
        throw new Error(
          getErrorMessage(data, "Unable to save Research Gaps sources.")
        );
      }

      const savedIds = Array.isArray(data?.resource_ids)
        ? [
            ...new Set(
              data.resource_ids.map(String).filter(Boolean)
            ),
          ]
        : uniqueIds;

      setSelectedResourceIds(savedIds);
      setSourceSelectionLoaded(true);
      setSourceManagerOpen(false);
      setSelectedGap(null);
      setError("");

      return true;
    } catch (err) {
      console.error("Research Gaps source saving error:", err);
      setError(err.message || "Unable to save Research Gaps sources.");
      return false;
    } finally {
      setSavingSourceSelection(false);
    }
  };

  const openSourceManager = () => {
    if (!notebookId || !notebook) {
      openNotebook();
      return;
    }

    if (!sourceSelectionLoaded) {
      setError("Wait for the Research Gaps source selection to load.");
      return;
    }

    setSourceManagerOpen(true);
  };

  // --------------------------------------------------
  // Saved analysis history
  // --------------------------------------------------

  const loadSavedAnalyses = useCallback(
    async (restoreLatest = true) => {
      if (!notebookId) {
        setSavedAnalyses([]);
        return;
      }

      try {
        setLoadingSavedAnalyses(true);

        const response = await fetch(
          `${API_URL}/api/research-gaps/saved?notebook_id=${encodeURIComponent(
            notebookId
          )}`,
          { headers: getAuthHeaders() }
        );

        const data = await readResponse(response);

        if (response.status === 401) {
          throw new Error(
            "Your session has expired. Please log in again."
          );
        }

        if (!response.ok) {
          throw new Error(
            getErrorMessage(
              data,
              "Unable to load saved research gap analyses."
            )
          );
        }

        const analyses = Array.isArray(data?.analyses)
          ? data.analyses
          : [];

        setSavedAnalyses(analyses);

        if (restoreLatest && analyses.length > 0) {
          const latest = analyses[0];

          const detailResponse = await fetch(
            `${API_URL}/api/research-gaps/saved/${encodeURIComponent(
              latest.analysis_id
            )}`,
            { headers: getAuthHeaders() }
          );

          const detailData = await readResponse(detailResponse);

          if (detailResponse.ok && detailData?.analysis) {
            setGaps(
              Array.isArray(detailData.analysis.gaps)
                ? detailData.analysis.gaps
                : []
            );
            setActiveAnalysisId(detailData.analysis.analysis_id);
            setSelectedGap(null);
          }
        } else if (restoreLatest && analyses.length === 0) {
          setGaps([]);
          setActiveAnalysisId(null);
          setSelectedGap(null);
        }
      } catch (err) {
        console.error("Saved research gap loading error:", err);
        setError(err.message || "Unable to load saved research gaps.");
      } finally {
        setLoadingSavedAnalyses(false);
      }
    },
    [notebookId]
  );

  const loadSavedAnalysis = async (analysisId) => {
    try {
      setError("");

      const response = await fetch(
        `${API_URL}/api/research-gaps/saved/${encodeURIComponent(
          analysisId
        )}`,
        { headers: getAuthHeaders() }
      );

      const data = await readResponse(response);

      if (response.status === 401) {
        throw new Error(
          "Your session has expired. Please log in again."
        );
      }

      if (!response.ok || !data?.analysis) {
        throw new Error(
          getErrorMessage(
            data,
            "Unable to open the saved research gap analysis."
          )
        );
      }

      setGaps(
        Array.isArray(data.analysis.gaps) ? data.analysis.gaps : []
      );
      setActiveAnalysisId(data.analysis.analysis_id);
      setSelectedGap(null);
      setSearchQuery("");
    } catch (err) {
      setError(err.message || "Unable to open the saved analysis.");
    }
  };

  const deleteSavedAnalysis = async (analysisId) => {
    try {
      setDeletingAnalysisId(analysisId);
      setError("");

      const response = await fetch(
        `${API_URL}/api/research-gaps/saved/${encodeURIComponent(
          analysisId
        )}`,
        {
          method: "DELETE",
          headers: getAuthHeaders(),
        }
      );

      const data = await readResponse(response);

      if (response.status === 401) {
        throw new Error(
          "Your session has expired. Please log in again."
        );
      }

      if (!response.ok) {
        throw new Error(
          getErrorMessage(data, "Unable to delete the saved analysis.")
        );
      }

      const remaining = savedAnalyses.filter(
        (item) => item.analysis_id !== analysisId
      );

      setSavedAnalyses(remaining);

      if (activeAnalysisId === analysisId) {
        setActiveAnalysisId(null);
        setGaps([]);
        setSelectedGap(null);

        if (remaining.length > 0) {
          await loadSavedAnalysis(remaining[0].analysis_id);
        }
      }
    } catch (err) {
      setError(err.message || "Unable to delete the saved analysis.");
    } finally {
      setDeletingAnalysisId(null);
    }
  };

  // --------------------------------------------------
  // Initial loading
  // --------------------------------------------------

  useEffect(() => {
    loadNotebook();
    loadPapers();
    loadResearchGapSources();
    loadSavedAnalyses(true);
  }, [
    loadNotebook,
    loadPapers,
    loadResearchGapSources,
    loadSavedAnalyses,
  ]);

  // --------------------------------------------------
  // Derive selected papers from Research Gaps selection
  // --------------------------------------------------

  const selectedIdSet = useMemo(
    () => new Set(selectedResourceIds),
    [selectedResourceIds]
  );

  const selectedPapers = useMemo(
    () =>
      papers.filter((paper) =>
        selectedIdSet.has(String(paper.id))
      ),
    [papers, selectedIdSet]
  );

  const missingSourceCount = Math.max(
    0,
    selectedResourceIds.length - selectedPapers.length
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
        ...(Array.isArray(gap.evidence)
          ? gap.evidence.map(
              (item) =>
                `${item.paper_title || ""} ${item.statement || ""}`
            )
          : []),
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();

      return text.includes(query);
    });
  }, [gaps, searchQuery]);

  // --------------------------------------------------
  // Navigation
  // --------------------------------------------------

  const openNotebook = () => {
    if (notebookId) {
      navigate(`/notebook/${encodeURIComponent(notebookId)}`);
    } else {
      navigate("/notebook");
    }
  };

  // --------------------------------------------------
  // Analyze gaps using independent Research Gaps sources
  // --------------------------------------------------

  const analyzeGaps = async () => {
    if (!notebookId || !notebook) {
      setError(
        "Load a research notebook before analyzing research gaps."
      );
      return;
    }

    if (!sourceSelectionLoaded) {
      setError(
        "Research Gaps sources are still loading. Please try again."
      );
      return;
    }

    if (selectedResourceIds.length === 0) {
      setError(
        "Select at least one research paper in Manage Sources before analyzing research gaps."
      );
      return;
    }

    if (missingSourceCount > 0) {
      setError(
        "Some selected research papers are no longer available. Refresh your papers and update Manage Sources before analyzing."
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
            ...getAuthHeaders(),
          },
          body: JSON.stringify({
            notebook_id: notebookId,
            resource_ids: selectedResourceIds,
          }),
        }
      );

      const data = await readResponse(response);

      if (response.status === 401) {
        throw new Error(
          "Your session has expired. Please log in again."
        );
      }

      if (!response.ok) {
        throw new Error(
          getErrorMessage(data, "Research gap analysis failed.")
        );
      }

      const resultGaps = Array.isArray(data?.gaps) ? data.gaps : [];

      setGaps(resultGaps);
      setActiveAnalysisId(data?.analysis_id || null);
      setSelectedGap(null);
      setSearchQuery("");

      if (data?.saved !== true) {
        setError(
          "Analysis completed, but it could not be confirmed as saved. Your results are still displayed."
        );
      } else {
        setError("");
      }

      await loadSavedAnalyses(false);
    } catch (err) {
      console.error("Research gap analysis error:", err);
      setError(err.message || "Research gap analysis failed.");
    } finally {
      setAnalyzing(false);
    }
  };

  const isPageLoading =
    loadingNotebook || loadingPapers || loadingSourceSelection;

  const canAnalyze =
    !isPageLoading &&
    !analyzing &&
    sourceSelectionLoaded &&
    Boolean(notebook) &&
    selectedResourceIds.length > 0 &&
    missingSourceCount === 0;

  return (
    <AppLayout>
      <div className="min-h-[calc(100vh-6rem)]">
        {/* Header */}

        <div className="flex flex-col gap-5 border-b border-white/[0.06] pb-6 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-start gap-3">
            <button
              type="button"
              onClick={openNotebook}
              aria-label="Return to research notebook"
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
                Discover potential unexplored research areas using
                your independently selected research papers.
              </p>

              {notebook && (
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <BookOpen className="h-3.5 w-3.5 text-slate-600" />

                  <span className="text-xs text-slate-400">
                    {notebook.title || "Research Notebook"}
                  </span>

                  <span className="rounded-md border border-white/[0.07] bg-white/[0.03] px-2 py-0.5 text-[10px] text-slate-500">
                    {selectedResourceIds.length}{" "}
                    {selectedResourceIds.length === 1
                      ? "source"
                      : "sources"}
                  </span>
                </div>
              )}
            </div>
          </div>

          <div className="flex shrink-0 flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={openSourceManager}
              disabled={!notebook || !sourceSelectionLoaded}
              className="flex items-center justify-center gap-2 rounded-xl border border-white/[0.07] bg-slate-900/60 px-4 py-2.5 text-xs font-medium text-slate-300 transition hover:bg-white/[0.04] hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
            >
              <BookOpen className="h-3.5 w-3.5" />
              Manage Sources
            </button>

            <button
              type="button"
              onClick={analyzeGaps}
              disabled={!canAnalyze}
              className="flex items-center justify-center gap-2 rounded-xl bg-indigo-500 px-4 py-2.5 text-xs font-medium text-white shadow-lg shadow-indigo-500/20 transition hover:bg-indigo-400 disabled:cursor-not-allowed disabled:opacity-40"
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
                Manage the papers used for Research Gaps independently
                of notebook and Knowledge Graph selections.
              </p>
            </div>

            <div className="p-4">
              <div className="mb-4 flex items-center justify-between">
                <span className="text-[10px] uppercase tracking-[0.15em] text-slate-600">
                  Research Gap Sources
                </span>

                <span className="text-xs tabular-nums text-indigo-400">
                  {selectedResourceIds.length}
                </span>
              </div>

              {isPageLoading ? (
                <div className="flex justify-center py-8">
                  <Loader2 className="h-5 w-5 animate-spin text-indigo-400" />
                </div>
              ) : selectedPapers.length === 0 ? (
                <div className="rounded-xl border border-dashed border-white/[0.07] p-5 text-center">
                  <FileText className="mx-auto h-5 w-5 text-slate-700" />

                  <p className="mt-3 text-xs leading-5 text-slate-500">
                    {selectedResourceIds.length > 0
                      ? "Some saved source IDs could not be matched to available papers."
                      : "No papers are selected for Research Gaps yet."}
                  </p>

                  <button
                    type="button"
                    onClick={openSourceManager}
                    className="mt-3 text-[10px] font-medium text-indigo-400 hover:text-indigo-300"
                  >
                    Manage Research Gaps sources
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

                      <span
                        title={paper.title}
                        className="min-w-0 flex-1 truncate text-[10px] text-slate-400"
                      >
                        {paper.title}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {missingSourceCount > 0 && (
                <p className="mt-3 text-[10px] leading-4 text-amber-400/80">
                  {missingSourceCount} selected{" "}
                  {missingSourceCount === 1 ? "source is" : "sources are"}{" "}
                  missing from the available paper records. Update your
                  Research Gaps source selection before analyzing.
                </p>
              )}

              <button
                type="button"
                onClick={openSourceManager}
                disabled={!sourceSelectionLoaded || !notebook}
                className="mt-4 flex items-center gap-1.5 text-[10px] text-slate-600 transition hover:text-slate-300 disabled:cursor-not-allowed disabled:opacity-40"
              >
                Manage selected sources
                <ChevronRight className="h-3 w-3" />
              </button>
            </div>

            {/* Saved Analyses */}

            <div className="border-t border-white/[0.06] p-4">
              <div className="mb-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Clock className="h-3.5 w-3.5 text-indigo-400" />

                  <p className="text-xs font-medium text-slate-300">
                    Saved Analyses
                  </p>
                </div>

                <span className="text-[10px] tabular-nums text-slate-500">
                  {savedAnalyses.length}
                </span>
              </div>

              {loadingSavedAnalyses ? (
                <div className="flex justify-center py-4">
                  <Loader2 className="h-4 w-4 animate-spin text-indigo-400" />
                </div>
              ) : savedAnalyses.length === 0 ? (
                <p className="rounded-xl border border-dashed border-white/[0.07] px-3 py-4 text-center text-[10px] leading-4 text-slate-600">
                  Completed analyses will appear here automatically.
                </p>
              ) : (
                <div className="space-y-2">
                  {savedAnalyses.map((analysis) => {
                    const isActive =
                      activeAnalysisId === analysis.analysis_id;
                    const gapCount =
                      analysis.gap_count ??
                      analysis.meta?.validated_gaps ??
                      0;

                    return (
                      <div
                        key={analysis.analysis_id}
                        className={`flex items-start gap-2 rounded-xl border p-2 ${
                          isActive
                            ? "border-indigo-400/20 bg-indigo-500/[0.07]"
                            : "border-white/[0.05] bg-slate-900/40"
                        }`}
                      >
                        <button
                          type="button"
                          onClick={() =>
                            loadSavedAnalysis(analysis.analysis_id)
                          }
                          className="min-w-0 flex-1 text-left"
                          title={
                            analysis.title ||
                            "Saved Research Gap Analysis"
                          }
                        >
                          <p className="truncate text-[10px] font-medium text-slate-300">
                            {analysis.title || "Research Gap Analysis"}
                          </p>

                          <p className="mt-1 text-[10px] text-slate-500">
                            {gapCount} {gapCount === 1 ? "gap" : "gaps"}
                          </p>

                          <p className="mt-1 text-[9px] text-slate-600">
                            {analysis.created_at
                              ? new Date(
                                  analysis.created_at
                                ).toLocaleString()
                              : "Saved analysis"}
                          </p>
                        </button>

                        <button
                          type="button"
                          onClick={() =>
                            deleteSavedAnalysis(analysis.analysis_id)
                          }
                          disabled={
                            deletingAnalysisId === analysis.analysis_id
                          }
                          aria-label="Delete saved analysis"
                          title="Delete saved analysis"
                          className="mt-0.5 shrink-0 rounded-lg p-1 text-slate-600 transition hover:bg-red-500/10 hover:text-red-300 disabled:opacity-40"
                        >
                          {deletingAnalysisId === analysis.analysis_id ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <Trash2 className="h-3.5 w-3.5" />
                          )}
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </aside>

          {/* Gap Results */}

          <section className="min-w-0">
            {error && (
              <div className="mb-5 flex items-start justify-between gap-3 rounded-xl border border-red-400/10 bg-red-500/[0.04] px-4 py-3 text-xs leading-5 text-red-300">
                <span>{error}</span>

                <button
                  type="button"
                  onClick={() => setError("")}
                  aria-label="Dismiss error"
                  className="shrink-0 text-red-300/60 transition hover:text-red-200"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            )}

            <div className="mb-4 flex items-center justify-between gap-4">
              <div>
                <p className="text-sm font-medium text-slate-200">
                  Potential Research Gaps
                </p>

                <p className="mt-1 text-[10px] text-slate-600">
                  {gaps.length}{" "}
                  {gaps.length === 1
                    ? "potential gap"
                    : "potential gaps"}{" "}
                  identified
                </p>
              </div>

              {gaps.length > 0 && (
                <div className="relative w-52 max-w-[50%]">
                  <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-600" />

                  <input
                    value={searchQuery}
                    onChange={(event) =>
                      setSearchQuery(event.target.value)
                    }
                    placeholder="Search gaps..."
                    aria-label="Search research gaps"
                    className="h-9 w-full rounded-xl border border-white/[0.07] bg-slate-900/60 pl-9 pr-3 text-xs text-slate-300 outline-none placeholder:text-slate-600 focus:border-indigo-400/20"
                  />
                </div>
              )}
            </div>

            {isPageLoading ? (
              <LoadingState
                title="Loading research sources"
                description="Retrieving the research workspace, papers, and independent Research Gaps source selection."
              />
            ) : analyzing ? (
              <LoadingState />
            ) : !notebook ? (
              <EmptyState
                hasSources={false}
                onAnalyze={analyzeGaps}
                onManageSources={openNotebook}
                title="Open a research notebook"
                description="Research Gaps uses a notebook as its workspace, but manages its source selection separately."
              />
            ) : !sourceSelectionLoaded ? (
              <EmptyState
                hasSources={false}
                onAnalyze={analyzeGaps}
                onManageSources={openSourceManager}
                title="Research sources could not be loaded"
                description="Retry after checking your connection and the Research Gaps source endpoint."
              />
            ) : selectedResourceIds.length === 0 ? (
              <EmptyState
                hasSources={false}
                onAnalyze={analyzeGaps}
                onManageSources={openSourceManager}
                title="Select research sources first"
                description="Choose the papers that Research Gaps should use. This selection does not change your notebook or Knowledge Graph sources."
              />
            ) : gaps.length === 0 ? (
              <EmptyState
                hasSources={true}
                onAnalyze={analyzeGaps}
                onManageSources={openSourceManager}
                title="No research gap analysis yet"
                description="Analyze your independently selected papers to identify potential unexplored research areas."
              />
            ) : filteredGaps.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-white/[0.07] p-12 text-center">
                <Search className="mx-auto h-6 w-6 text-slate-700" />

                <p className="mt-3 text-sm text-slate-400">
                  No matching research gaps
                </p>

                <p className="mt-1 text-xs text-slate-600">
                  Try another search term.
                </p>
              </div>
            ) : (
              <div className="grid gap-3">
                {filteredGaps.map((gap, index) => (
                  <GapCard
                    key={gap.id || `${gap.title || "gap"}-${index}`}
                    gap={gap}
                    index={index}
                    onClick={() => setSelectedGap(gap)}
                  />
                ))}
              </div>
            )}
          </section>
        </div>

        {/* Source manager */}

        {sourceManagerOpen && notebook && (
          <SourceManagerModal
            papers={papers}
            selectedResourceIds={selectedResourceIds}
            saving={savingSourceSelection}
            onClose={() => setSourceManagerOpen(false)}
            onSave={saveResearchGapSources}
          />
        )}

        {/* Gap details */}

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
// Independent Research Gaps Source Manager
// ======================================================

function SourceManagerModal({
  papers,
  selectedResourceIds,
  saving,
  onClose,
  onSave,
}) {
  const [draftIds, setDraftIds] = useState(selectedResourceIds);
  const [query, setQuery] = useState("");

  const selectedSet = useMemo(
    () => new Set(draftIds.map(String)),
    [draftIds]
  );

  const filteredPapers = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();

    if (!normalizedQuery) {
      return papers;
    }

    return papers.filter((paper) =>
      `${paper.title || ""} ${paper.filename || ""}`
        .toLowerCase()
        .includes(normalizedQuery)
    );
  }, [papers, query]);

  const togglePaper = (paperId) => {
    const id = String(paperId);

    setDraftIds((current) =>
      current.includes(id)
        ? current.filter((item) => item !== id)
        : [...current, id]
    );
  };

  const selectAllVisible = () => {
    setDraftIds((current) => [
      ...new Set([
        ...current,
        ...filteredPapers.map((paper) => String(paper.id)),
      ]),
    ]);
  };

  const clearVisible = () => {
    const visibleIds = new Set(
      filteredPapers.map((paper) => String(paper.id))
    );

    setDraftIds((current) =>
      current.filter((id) => !visibleIds.has(String(id)))
    );
  };

  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.key === "Escape" && !saving) {
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [onClose, saving]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/75 p-4 backdrop-blur-sm"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !saving) {
          onClose();
        }
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="research-gap-sources-title"
        className="flex max-h-[85vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-white/[0.08] bg-slate-900 shadow-2xl"
      >
        <div className="flex items-start justify-between gap-4 border-b border-white/[0.06] p-5">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-indigo-400">
              Research Intelligence
            </p>

            <h2
              id="research-gap-sources-title"
              className="mt-2 text-base font-semibold text-white"
            >
              Manage Research Gap Sources
            </h2>

            <p className="mt-1 text-xs leading-5 text-slate-500">
              Choose which papers Research Gaps should use. This
              selection is independent of your notebook and Knowledge
              Graph source selections.
            </p>
          </div>

          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            aria-label="Close source manager"
            className="rounded-lg p-2 text-slate-500 transition hover:bg-white/[0.05] hover:text-white disabled:opacity-40"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-3 border-b border-white/[0.06] p-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-600" />

            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search your research papers..."
              aria-label="Search research papers"
              className="h-10 w-full rounded-xl border border-white/[0.07] bg-slate-950/60 pl-9 pr-3 text-xs text-slate-200 outline-none placeholder:text-slate-600 focus:border-indigo-400/30"
            />
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-xs text-slate-400">
              <span className="font-semibold text-indigo-300">
                {draftIds.length}
              </span>{" "}
              selected · {papers.length} available
            </p>

            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={selectAllVisible}
                disabled={saving || filteredPapers.length === 0}
                className="text-[10px] font-medium text-indigo-300 hover:text-indigo-200 disabled:opacity-40"
              >
                Select visible
              </button>

              <button
                type="button"
                onClick={clearVisible}
                disabled={saving || filteredPapers.length === 0}
                className="text-[10px] font-medium text-slate-500 hover:text-slate-300 disabled:opacity-40"
              >
                Clear visible
              </button>
            </div>
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-4">
          {filteredPapers.length === 0 ? (
            <div className="rounded-xl border border-dashed border-white/[0.08] p-8 text-center">
              <FileText className="mx-auto h-5 w-5 text-slate-700" />

              <p className="mt-3 text-xs text-slate-400">
                {papers.length === 0
                  ? "No research papers are available."
                  : "No papers match your search."}
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {filteredPapers.map((paper) => {
                const id = String(paper.id);
                const checked = selectedSet.has(id);

                return (
                  <label
                    key={id}
                    className={`flex cursor-pointer items-start gap-3 rounded-xl border p-3 transition ${
                      checked
                        ? "border-indigo-400/25 bg-indigo-500/[0.07]"
                        : "border-white/[0.05] bg-slate-950/30 hover:border-white/[0.10]"
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      disabled={saving}
                      onChange={() => togglePaper(id)}
                      className="mt-1 accent-indigo-500"
                    />

                    <FileText className="mt-0.5 h-4 w-4 shrink-0 text-indigo-400" />

                    <span className="min-w-0 flex-1">
                      <span className="block break-words text-xs font-medium text-slate-300">
                        {paper.title || "Untitled Research Paper"}
                      </span>

                      {paper.filename &&
                        paper.filename !== paper.title && (
                          <span className="mt-1 block break-all text-[10px] text-slate-600">
                            {paper.filename}
                          </span>
                        )}
                    </span>

                    {checked && (
                      <span className="flex shrink-0 items-center gap-1 rounded-md bg-indigo-500/10 px-2 py-1 text-[9px] text-indigo-300">
                        <Check className="h-3 w-3" />
                        Selected
                      </span>
                    )}
                  </label>
                );
              })}
            </div>
          )}
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-white/[0.06] p-4">
          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            className="rounded-xl border border-white/[0.08] px-4 py-2.5 text-xs text-slate-300 transition hover:bg-white/[0.04] disabled:opacity-40"
          >
            Cancel
          </button>

          <button
            type="button"
            onClick={() => onSave(draftIds)}
            disabled={saving}
            className="flex items-center gap-2 rounded-xl bg-indigo-500 px-4 py-2.5 text-xs font-medium text-white transition hover:bg-indigo-400 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {saving ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Saving sources...
              </>
            ) : (
              "Save source selection"
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

// ======================================================
// Gap Card
// ======================================================

function GapCard({ gap, index, onClick }) {
  const evidenceCount = Array.isArray(gap.evidence)
    ? gap.evidence.length
    : 0;

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
            <p className="mt-2 whitespace-pre-line text-xs leading-5 text-slate-500">
              {gap.description}
            </p>
          )}

          {evidenceCount > 0 && (
            <div className="mt-4 flex items-center gap-2 text-[10px] text-slate-600">
              <FileText className="h-3.5 w-3.5" />

              {evidenceCount} evidence{" "}
              {evidenceCount === 1 ? "source" : "sources"}
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
  const evidence = Array.isArray(gap.evidence) ? gap.evidence : [];

  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4 backdrop-blur-sm sm:p-6"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="research-gap-title"
        className="max-h-[85vh] w-full max-w-3xl overflow-y-auto rounded-2xl border border-white/[0.08] bg-slate-900 shadow-2xl"
      >
        <div className="sticky top-0 flex items-start justify-between gap-4 border-b border-white/[0.06] bg-slate-900 p-6">
          <div className="flex min-w-0 gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-indigo-400/15 bg-indigo-500/10">
              <Lightbulb className="h-5 w-5 text-indigo-400" />
            </div>

            <div className="min-w-0">
              <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-indigo-400">
                Potential Research Gap
              </p>

              <h2
                id="research-gap-title"
                className="mt-1 text-base font-semibold text-white"
              >
                {gap.title || "Research Gap"}
              </h2>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            aria-label="Close research gap details"
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-slate-600 hover:bg-white/[0.04] hover:text-slate-300"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-6 p-6">
          {gap.description && (
            <DetailSection title="Description">
              <p className="whitespace-pre-line">{gap.description}</p>
            </DetailSection>
          )}

          {gap.why_gap && (
            <DetailSection title="Why this appears to be a gap">
              <p className="whitespace-pre-line">{gap.why_gap}</p>
            </DetailSection>
          )}

          {evidence.length > 0 && (
            <DetailSection title="Evidence from selected sources">
              <div className="space-y-3">
                {evidence.map((item, index) => (
                  <div
                    key={
                      item.resource_id ||
                      item.paper_id ||
                      `${item.paper_title || "evidence"}-${index}`
                    }
                    className="rounded-xl border border-white/[0.06] bg-slate-950/40 p-4"
                  >
                    <div className="flex items-start gap-2">
                      <FileText className="mt-0.5 h-3.5 w-3.5 shrink-0 text-indigo-400" />

                      <p className="text-xs font-medium text-slate-300">
                        {item.paper_title || "Selected research source"}
                      </p>
                    </div>

                    {item.statement && (
                      <p className="mt-2 whitespace-pre-line text-xs leading-5 text-slate-500">
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

      <div className="text-sm leading-6 text-slate-400">{children}</div>
    </section>
  );
}

// ======================================================
// Loading
// ======================================================

function LoadingState({
  title = "Analyzing selected literature",
  description = "SciBrain is examining the selected research sources.",
}) {
  return (
    <div className="flex min-h-[400px] flex-col items-center justify-center rounded-2xl border border-white/[0.06] bg-slate-950/30">
      <Loader2 className="h-7 w-7 animate-spin text-indigo-400" />

      <p className="mt-4 text-sm font-medium text-slate-300">{title}</p>

      <p className="mt-2 max-w-sm text-center text-xs leading-5 text-slate-600">
        {description}
      </p>
    </div>
  );
}

// ======================================================
// Empty State
// ======================================================

function EmptyState({
  hasSources,
  onAnalyze,
  onManageSources,
  title,
  description,
}) {
  return (
    <div className="flex min-h-[400px] flex-col items-center justify-center rounded-2xl border border-dashed border-white/[0.07] bg-slate-950/20 px-6 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-indigo-400/10 bg-indigo-500/[0.06]">
        <Lightbulb className="h-6 w-6 text-indigo-400" />
      </div>

      <h2 className="mt-5 text-sm font-medium text-slate-300">
        {title ||
          (hasSources
            ? "No research gap analysis yet"
            : "Select research sources first")}
      </h2>

      <p className="mt-2 max-w-md text-xs leading-5 text-slate-600">
        {description ||
          (hasSources
            ? "Analyze the selected literature to identify potential unexplored research areas."
            : "Choose the papers you want SciBrain to investigate.")}
      </p>

      <div className="mt-5 flex flex-wrap items-center justify-center gap-2">
        {hasSources && (
          <button
            type="button"
            onClick={onAnalyze}
            className="flex items-center gap-2 rounded-xl border border-indigo-400/15 bg-indigo-500/10 px-4 py-2.5 text-xs font-medium text-indigo-300 transition hover:bg-indigo-500/15"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Analyze selected sources
          </button>
        )}

        <button
          type="button"
          onClick={onManageSources}
          className="flex items-center gap-2 rounded-xl border border-white/[0.07] bg-slate-900 px-4 py-2.5 text-xs font-medium text-slate-300 transition hover:bg-white/[0.04]"
        >
          <BookOpen className="h-3.5 w-3.5" />
          {hasSources ? "Manage sources" : "Manage sources"}
        </button>
      </div>
    </div>
  );
}

export default ResearchGaps;