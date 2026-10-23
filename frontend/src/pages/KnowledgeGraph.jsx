
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  BookOpen,
  Check,
  ChevronRight,
  FileText,
  Loader2,
  Network,
  RefreshCw,
  Search,
  ZoomIn,
  ZoomOut,
  Maximize2,
  X,
  Save,
  RotateCcw,
} from "lucide-react";

import AppLayout from "../components/AppLayout";

const API_URL = "http://127.0.0.1:8000";
const ACTIVE_NOTEBOOK_KEY = "scibrain_active_notebook_id";

const NODE_TYPES = [
  "all",
  "paper",
  "author",
  "method",
  "dataset",
  "metric",
  "concept",
  "finding",
  "limitation",
  "future_work",
  "problem",
  "organization",
  "tool",
  "model",
];

const NODE_STYLES = {
  paper: { hex: "#4f46e5", text: "text-indigo-700", fill: "bg-indigo-50" },
  author: { hex: "#0891b2", text: "text-cyan-700", fill: "bg-cyan-50" },
  method: { hex: "#7c3aed", text: "text-violet-700", fill: "bg-violet-50" },
  dataset: { hex: "#059669", text: "text-emerald-700", fill: "bg-emerald-50" },
  metric: { hex: "#d97706", text: "text-amber-700", fill: "bg-amber-50" },
  concept: { hex: "#0284c7", text: "text-sky-700", fill: "bg-sky-50" },
  finding: { hex: "#16a34a", text: "text-green-700", fill: "bg-green-50" },
  limitation: { hex: "#dc2626", text: "text-red-700", fill: "bg-red-50" },
  future_work: { hex: "#ea580c", text: "text-orange-700", fill: "bg-orange-50" },
  problem: { hex: "#db2777", text: "text-pink-700", fill: "bg-pink-50" },
  organization: { hex: "#2563eb", text: "text-blue-700", fill: "bg-blue-50" },
  tool: { hex: "#0d9488", text: "text-teal-700", fill: "bg-teal-50" },
  model: { hex: "#9333ea", text: "text-purple-700", fill: "bg-purple-50" },
};

function getAuthHeaders() {
  const token = localStorage.getItem("scibrain_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function getPaperId(paper) {
  return String(paper?.id ?? paper?.paper_id ?? paper?._id ?? "");
}

async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      ...getAuthHeaders(),
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(options.headers || {}),
    },
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const message =
      typeof data?.detail === "string"
        ? data.detail
        : typeof data?.message === "string"
          ? data.message
          : `Request failed (${response.status}).`;

    throw new Error(message);
  }

  return data;
}

function getNotebookId(item) {
  return String(item?.notebook_id ?? item?.id ?? item?._id ?? "");
}

function KnowledgeGraph() {
  const navigate = useNavigate();
  const location = useLocation();
  const { notebookId: routeNotebookId } = useParams();

  const [activeNotebookId, setActiveNotebookId] = useState(() =>
    String(
      location.state?.notebookId ||
        routeNotebookId ||
        sessionStorage.getItem(ACTIVE_NOTEBOOK_KEY) ||
        ""
    )
  );

  const notebookId = activeNotebookId;

  const [notebook, setNotebook] = useState(null);
  const [notebookLoaded, setNotebookLoaded] = useState(false);
  const [availableNotebooks, setAvailableNotebooks] = useState([]);
  const [loadingNotebooks, setLoadingNotebooks] = useState(true);

  const [papers, setPapers] = useState([]);
  const [nodes, setNodes] = useState([]);
  const [edges, setEdges] = useState([]);
  const [selectedNode, setSelectedNode] = useState(null);

  const [loadingPapers, setLoadingPapers] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [savingGraph, setSavingGraph] = useState(false);
  const [savedGraph, setSavedGraph] = useState(false);
  const [savedGraphId, setSavedGraphId] = useState("");

  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [nodeType, setNodeType] = useState("all");
  const [zoom, setZoom] = useState(1);

  const backToNotebook = useCallback(() => {
    navigate(
      notebookId
        ? `/notebook/${encodeURIComponent(notebookId)}`
        : "/notebook"
    );
  }, [navigate, notebookId]);

  const handleNotebookChange = useCallback((value) => {
    const nextId = String(value || "");

    setActiveNotebookId(nextId);
    setNotebook(null);
    setNodes([]);
    setEdges([]);
    setSelectedNode(null);
    setSavedGraph(false);
    setSavedGraphId("");
    setError("");
    setNotice("");
    setSearchQuery("");
    setNodeType("all");
    setZoom(1);

    if (nextId) {
      sessionStorage.setItem(ACTIVE_NOTEBOOK_KEY, nextId);
    } else {
      sessionStorage.removeItem(ACTIVE_NOTEBOOK_KEY);
    }
  }, []);

  // Keep the selected notebook synchronized with notebook-specific routes.
  useEffect(() => {
    const routeId = String(location.state?.notebookId || routeNotebookId || "");

    if (routeId && routeId !== activeNotebookId) {
      handleNotebookChange(routeId);
    }
  }, [
    routeNotebookId,
    location.state?.notebookId,
    activeNotebookId,
    handleNotebookChange,
  ]);

  // Load the notebook list so the page works when opened directly.
  useEffect(() => {
    let cancelled = false;

    async function loadNotebooks() {
      setLoadingNotebooks(true);

      try {
        const data = await apiRequest("/api/notebook/");
        const list = Array.isArray(data)
          ? data
          : Array.isArray(data?.notebooks)
            ? data.notebooks
            : [];

        if (!cancelled) {
          setAvailableNotebooks(
            list.filter((item) => getNotebookId(item))
          );
        }
      } catch (err) {
        if (!cancelled) {
          setError((current) => current || err.message);
        }
      } finally {
        if (!cancelled) setLoadingNotebooks(false);
      }
    }

    loadNotebooks();

    return () => {
      cancelled = true;
    };
  }, []);

  // Load the active notebook. No notebook is a valid page state.
  useEffect(() => {
    let cancelled = false;

    async function loadNotebook() {
      setNotebookLoaded(false);
      setNotebook(null);
      setNodes([]);
      setEdges([]);
      setSelectedNode(null);
      setSavedGraph(false);
      setSavedGraphId("");
      setError("");
      setNotice("");

      if (!notebookId) {
        setNotebookLoaded(true);
        return;
      }

      try {
        const data = await apiRequest(
          `/api/notebook/${encodeURIComponent(notebookId)}`
        );

        const loadedNotebook = data?.notebook;

        if (!loadedNotebook) {
          throw new Error("The server did not return the requested notebook.");
        }

        if (cancelled) return;

        setNotebook(loadedNotebook);

        const confirmedId = String(
          loadedNotebook.notebook_id || notebookId
        );

        sessionStorage.setItem(ACTIVE_NOTEBOOK_KEY, confirmedId);
      } catch (err) {
        if (!cancelled) {
          setNotebook(null);
          setError(err.message || "Failed to load the research notebook.");
        }
      } finally {
        if (!cancelled) setNotebookLoaded(true);
      }
    }

    loadNotebook();

    return () => {
      cancelled = true;
    };
  }, [notebookId]);

  // Load available paper metadata.
  useEffect(() => {
    let cancelled = false;

    async function loadPapers() {
      setLoadingPapers(true);

      try {
        const data = await apiRequest("/api/papers/");
        const rawPapers = Array.isArray(data)
          ? data
          : Array.isArray(data?.papers)
            ? data.papers
            : [];

        if (!cancelled) {
          setPapers(
            rawPapers
              .map((paper) => ({
                ...paper,
                id: getPaperId(paper),
                title:
                  paper.title ||
                  paper.filename ||
                  "Untitled Research Paper",
              }))
              .filter((paper) => paper.id)
          );
        }
      } catch (err) {
        if (!cancelled) {
          setError((current) => current || err.message);
        }
      } finally {
        if (!cancelled) setLoadingPapers(false);
      }
    }

    loadPapers();

    return () => {
      cancelled = true;
    };
  }, []);

  const selectedResourceIds = useMemo(() => {
    const ids = Array.isArray(notebook?.resource_ids)
      ? notebook.resource_ids
      : [];

    return [...new Set(ids.map(String).filter(Boolean))];
  }, [notebook]);

  const selectedIdSet = useMemo(
    () => new Set(selectedResourceIds),
    [selectedResourceIds]
  );

  const selectedPapers = useMemo(
    () => papers.filter((paper) => selectedIdSet.has(String(paper.id))),
    [papers, selectedIdSet]
  );

  const missingSourceCount = Math.max(
    0,
    selectedResourceIds.length - selectedPapers.length
  );

  // Load the saved snapshot for this notebook, if one exists.
  // These calls require the corresponding backend endpoints.
  useEffect(() => {
    let cancelled = false;

    async function loadSavedGraph() {
      if (!notebookId || !notebookLoaded || !notebook) return;

      try {
        const listData = await apiRequest("/api/knowledge-graph/saved");
        const savedGraphs = Array.isArray(listData?.graphs)
          ? listData.graphs
          : [];

        const match = savedGraphs.find(
          (item) => String(item.notebook_id) === String(notebookId)
        );

        if (!match) {
          if (!cancelled) {
            setSavedGraph(false);
            setSavedGraphId("");
            setNodes([]);
            setEdges([]);
            setSelectedNode(null);
          }
          return;
        }

        const graphId = String(match.graph_id || match.id || "");

        if (!graphId) {
          throw new Error("The saved graph response is missing its graph ID.");
        }

        const graphData = await apiRequest(
          `/api/knowledge-graph/saved/${encodeURIComponent(graphId)}`
        );

        if (cancelled) return;

        const graph = graphData?.graph || graphData || {};

        setNodes(Array.isArray(graph.nodes) ? graph.nodes : []);
        setEdges(Array.isArray(graph.edges) ? graph.edges : []);
        setSavedGraph(true);
        setSavedGraphId(graphId);
        setSelectedNode(null);
        setZoom(1);
      } catch (err) {
        if (cancelled) return;

        // Do not silently label an unsaved graph as saved.
        setSavedGraph(false);
        setSavedGraphId("");

        // A missing save API should not prevent the page from being used.
        console.warn("Could not load a saved knowledge graph:", err.message);
      }
    }

    loadSavedGraph();

    return () => {
      cancelled = true;
    };
  }, [notebookId, notebookLoaded, notebook]);

  const filteredNodes = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();

    return nodes.filter((node) => {
      const matchesType = nodeType === "all" || node.type === nodeType;
      const searchable = [
        node.name,
        node.description,
        node.type,
      ]
        .map((value) => String(value || ""))
        .join(" ")
        .toLowerCase();

      return matchesType && (!query || searchable.includes(query));
    });
  }, [nodes, nodeType, searchQuery]);

  const visibleEdges = useMemo(() => {
    const visibleIds = new Set(filteredNodes.map((node) => String(node.id)));

    return edges.filter(
      (edge) =>
        visibleIds.has(String(edge.source)) &&
        visibleIds.has(String(edge.target))
    );
  }, [edges, filteredNodes]);

  const selectedNeighborhood = useMemo(() => {
    if (!selectedNode) return null;

    const connected = new Set([String(selectedNode.id)]);

    edges.forEach((edge) => {
      if (String(edge.source) === String(selectedNode.id)) {
        connected.add(String(edge.target));
      }

      if (String(edge.target) === String(selectedNode.id)) {
        connected.add(String(edge.source));
      }
    });

    return connected;
  }, [selectedNode, edges]);

  const generateGraph = async () => {
    if (!notebookId || !notebookLoaded || !notebook) {
      setError("Select a valid research notebook before generating its graph.");
      return;
    }

    if (selectedResourceIds.length === 0) {
      setError("Add at least one research paper to this notebook first.");
      return;
    }

    if (missingSourceCount > 0) {
      setError(
        `${missingSourceCount} notebook source(s) could not be matched to available paper records. Resolve these sources before generating the graph.`
      );
      return;
    }

    setGenerating(true);
    setError("");
    setNotice("");
    setSelectedNode(null);

    try {
      const data = await apiRequest("/api/knowledge-graph", {
        method: "POST",
        body: JSON.stringify({ resource_ids: selectedResourceIds }),
      });

      const newNodes = Array.isArray(data?.nodes) ? data.nodes : [];
      const newEdges = Array.isArray(data?.edges) ? data.edges : [];

      setNodes(newNodes);
      setEdges(newEdges);
      setSavedGraph(false);
      setSavedGraphId("");
      setZoom(1);

      if (newNodes.length === 0) {
        setNotice(
          "Graph generation completed, but no entities were returned. Check the paper text and backend extraction logs."
        );
      } else {
        setNotice(
          `Graph generated: ${newNodes.length} entities and ${newEdges.length} relationships. Save it to reopen this snapshot later.`
        );
      }
    } catch (err) {
      setError(err.message || "Knowledge graph generation failed.");
    } finally {
      setGenerating(false);
    }
  };

  const saveGraph = async () => {
    if (!notebookId || !notebook) {
      setError("Select a notebook before saving the graph.");
      return;
    }

    if (nodes.length === 0) {
      setError("There are no graph entities to save.");
      return;
    }

    setSavingGraph(true);
    setError("");
    setNotice("");

    try {
      const data = await apiRequest("/api/knowledge-graph/saved", {
        method: "POST",
        body: JSON.stringify({
          notebook_id: notebookId,
          nodes,
          edges,
        }),
      });

      const graph = data?.graph || data || {};
      const graphId = String(graph.graph_id || graph.id || savedGraphId || "");

      setSavedGraph(true);
      setSavedGraphId(graphId);
      setNotice("Knowledge graph snapshot saved for this notebook.");
    } catch (err) {
      setError(
        `Could not save the graph. ${err.message} Ensure the backend save endpoints are implemented.`
      );
    } finally {
      setSavingGraph(false);
    }
  };

  const clearGraphSelection = () => setSelectedNode(null);

  const zoomIn = () =>
    setZoom((current) => Math.min(1.8, Number((current + 0.15).toFixed(2))));

  const zoomOut = () =>
    setZoom((current) => Math.max(0.65, Number((current - 0.15).toFixed(2))));

  const resetZoom = () => setZoom(1);

  return (
    <AppLayout>
      <div className="min-h-[calc(100vh-6rem)] text-slate-800">
        {/* Header */}
        <div className="flex flex-col gap-5 border-b border-white/[0.06] pb-6 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-start gap-3">
            <button
              type="button"
              onClick={backToNotebook}
              className="mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-white/[0.08] bg-slate-900/60 text-slate-400 transition hover:bg-white/[0.06] hover:text-white"
              aria-label="Back to research notebook"
            >
              <ArrowLeft className="h-4 w-4" />
            </button>

            <div>
              <div className="flex items-center gap-2">
                <Network className="h-4 w-4 text-cyan-400" />
                <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-cyan-400">
                  Research Intelligence
                </p>
              </div>

              <h1 className="mt-2 text-2xl font-semibold tracking-tight text-white">
                Knowledge Graph
              </h1>

              <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
                Explore evidence-grounded entities and relationships across
                your research sources.
              </p>
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={saveGraph}
              disabled={!notebook || nodes.length === 0 || savingGraph || generating}
              className="flex items-center justify-center gap-2 rounded-xl border border-white/[0.12] bg-slate-900 px-4 py-2.5 text-xs font-medium text-slate-200 transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {savingGraph ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : savedGraph ? (
                <Check className="h-4 w-4 text-emerald-400" />
              ) : (
                <Save className="h-4 w-4" />
              )}
              {savingGraph ? "Saving..." : savedGraph ? "Save again" : "Save graph"}
            </button>

            <button
              type="button"
              onClick={generateGraph}
              disabled={
                generating ||
                loadingPapers ||
                !notebookLoaded ||
                !notebook ||
                selectedResourceIds.length === 0 ||
                missingSourceCount > 0
              }
              className="flex items-center justify-center gap-2 rounded-xl bg-indigo-500 px-4 py-2.5 text-xs font-medium text-white shadow-lg shadow-indigo-500/20 transition hover:bg-indigo-400 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {generating ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Building graph...
                </>
              ) : (
                <>
                  <Network className="h-4 w-4" />
                  Generate graph
                </>
              )}
            </button>
          </div>
        </div>

        {/* Notebook selection and active context */}
        <section className="mt-5 rounded-2xl border border-white/[0.08] bg-slate-950/40">
          <div className="flex flex-col gap-4 p-5 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex min-w-0 items-center gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-indigo-400/10 bg-indigo-500/[0.08]">
                <BookOpen className="h-4 w-4 text-indigo-400" />
              </div>

              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-slate-200">
                  {notebook?.title || "Choose a research notebook"}
                </p>
                <p className="mt-1 text-[10px] text-slate-500">
                  {!notebookId
                    ? "Select a notebook to load its sources and saved graph."
                    : !notebookLoaded
                      ? "Loading notebook..."
                      : notebook
                        ? `${selectedResourceIds.length} selected source${selectedResourceIds.length === 1 ? "" : "s"}`
                        : "The selected notebook could not be loaded."}
                </p>
              </div>
            </div>

            <div className="flex flex-wrap items-end gap-3">
              <div className="min-w-[230px]">
                <label
                  htmlFor="kg-notebook-select"
                  className="mb-1.5 block text-[9px] uppercase tracking-wider text-slate-500"
                >
                  Research notebook
                </label>

                <select
                  id="kg-notebook-select"
                  value={notebookId}
                  onChange={(event) => handleNotebookChange(event.target.value)}
                  disabled={loadingNotebooks || generating || savingGraph}
                  className="w-full rounded-lg border border-white/[0.12] bg-slate-900 px-3 py-2.5 text-xs text-slate-200 outline-none focus:border-indigo-400/60"
                >
                  <option value="">
                    {loadingNotebooks ? "Loading notebooks..." : "Select a notebook"}
                  </option>

                  {availableNotebooks.map((item) => {
                    const id = getNotebookId(item);

                    return (
                      <option key={id} value={id}>
                        {item.title || item.name || "Untitled Notebook"}
                      </option>
                    );
                  })}
                </select>
              </div>

              <button
                type="button"
                onClick={backToNotebook}
                disabled={!notebookId}
                className="flex items-center gap-1.5 rounded-lg border border-white/[0.10] px-3 py-2.5 text-[10px] text-slate-300 transition hover:bg-white/[0.05] disabled:opacity-40"
              >
                Open notebook
                <ChevronRight className="h-3 w-3" />
              </button>
            </div>
          </div>

          {notebook && selectedPapers.length > 0 && (
            <div className="border-t border-white/[0.07] px-5 py-3">
              <div className="flex flex-wrap gap-2">
                {selectedPapers.map((paper) => (
                  <div
                    key={paper.id}
                    className="flex max-w-xs items-center gap-2 rounded-lg border border-white/[0.07] bg-slate-900/60 px-2.5 py-1.5"
                  >
                    <FileText className="h-3 w-3 shrink-0 text-indigo-400" />
                    <span className="truncate text-[10px] text-slate-400">
                      {paper.title}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {notebook && missingSourceCount > 0 && !loadingPapers && (
            <div className="border-t border-amber-400/10 px-5 py-3">
              <p className="text-xs leading-5 text-amber-300">
                {missingSourceCount} saved source(s) could not be matched to
                available paper records. Resolve these before generating.
              </p>
            </div>
          )}
        </section>

        {/* Feedback */}
        {error && (
          <div className="mt-5 flex items-start justify-between gap-4 rounded-xl border border-red-400/20 bg-red-500/[0.06] px-4 py-3 text-xs text-red-200">
            <span>{error}</span>
            <button
              type="button"
              onClick={() => setError("")}
              className="shrink-0 text-red-300 hover:text-white"
              aria-label="Dismiss error"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        )}

        {notice && (
          <div className="mt-5 flex items-start justify-between gap-4 rounded-xl border border-emerald-400/20 bg-emerald-500/[0.06] px-4 py-3 text-xs text-emerald-200">
            <span>{notice}</span>
            <button
              type="button"
              onClick={() => setNotice("")}
              className="shrink-0 text-emerald-300 hover:text-white"
              aria-label="Dismiss message"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        )}

        {/* Graph workspace */}
        <div className="mt-5 grid min-h-[620px] gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
          <section
            data-kg-workspace
            className="relative min-h-[620px] overflow-hidden rounded-2xl border border-slate-200 bg-slate-50 shadow-sm"
          >
            {/* Canvas toolbar */}
            <div className="absolute left-4 right-4 top-4 z-30 flex items-center justify-between gap-3">
              <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white/95 p-1.5 shadow-sm backdrop-blur">
                <div className="relative">
                  <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
                  <input
                    value={searchQuery}
                    onChange={(event) => setSearchQuery(event.target.value)}
                    placeholder="Search entities..."
                    className="h-8 w-36 bg-transparent pl-8 pr-3 text-xs text-slate-700 outline-none placeholder:text-slate-400 sm:w-52"
                    aria-label="Search graph entities"
                  />
                </div>
              </div>

              <div className="flex items-center gap-1 rounded-xl border border-slate-200 bg-white/95 p-1 shadow-sm backdrop-blur">
                <button
                  type="button"
                  onClick={zoomOut}
                  disabled={zoom <= 0.65}
                  className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-600 transition hover:bg-slate-100 disabled:opacity-30"
                  title="Zoom out"
                >
                  <ZoomOut className="h-3.5 w-3.5" />
                </button>

                <button
                  type="button"
                  onClick={resetZoom}
                  className="flex h-8 min-w-10 items-center justify-center rounded-lg px-2 text-[9px] text-slate-600 transition hover:bg-slate-100"
                  title="Reset zoom"
                >
                  {Math.round(zoom * 100)}%
                </button>

                <button
                  type="button"
                  onClick={zoomIn}
                  disabled={zoom >= 1.8}
                  className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-600 transition hover:bg-slate-100 disabled:opacity-30"
                  title="Zoom in"
                >
                  <ZoomIn className="h-3.5 w-3.5" />
                </button>

                <div className="mx-1 h-4 w-px bg-slate-200" />

                <button
                  type="button"
                  onClick={generateGraph}
                  disabled={
                    generating ||
                    !notebook ||
                    !notebookLoaded ||
                    selectedResourceIds.length === 0 ||
                    missingSourceCount > 0
                  }
                  className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-600 transition hover:bg-slate-100 hover:text-indigo-600 disabled:opacity-40"
                  title="Regenerate graph"
                  aria-label="Regenerate graph"
                >
                  <RefreshCw className={`h-3.5 w-3.5 ${generating ? "animate-spin" : ""}`} />
                </button>

                <button
                  type="button"
                  onClick={() => {
                    document
                      .querySelector("[data-kg-workspace]")
                      ?.requestFullscreen?.();
                  }}
                  className="hidden h-8 w-8 items-center justify-center rounded-lg text-slate-600 transition hover:bg-slate-100 sm:flex"
                  title="Fullscreen graph"
                  aria-label="Fullscreen graph"
                >
                  <Maximize2 className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>

            {nodes.length > 0 && <GraphLegend />}

            {selectedNode && (
              <button
                type="button"
                onClick={clearGraphSelection}
                className="absolute right-4 top-[4.6rem] z-30 flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-[10px] font-medium text-slate-700 shadow-sm transition hover:bg-slate-100"
              >
                <RotateCcw className="h-3 w-3" />
                Clear selection
              </button>
            )}

            {/* Node type filters */}
            <div className="absolute bottom-4 left-4 right-4 z-30">
              <div className="flex max-w-full gap-1 overflow-x-auto rounded-xl border border-slate-200 bg-white/95 p-1.5 shadow-sm backdrop-blur">
                {NODE_TYPES.map((type) => (
                  <button
                    key={type}
                    type="button"
                    onClick={() => setNodeType(type)}
                    className={`whitespace-nowrap rounded-lg px-2.5 py-1.5 text-[9px] font-medium capitalize transition ${
                      nodeType === type
                        ? "bg-indigo-100 text-indigo-800"
                        : "text-slate-500 hover:bg-slate-100 hover:text-slate-800"
                    }`}
                  >
                    {formatNodeType(type)}
                  </button>
                ))}
              </div>
            </div>

            {!notebookId ? (
              <GraphPrompt
                title="Select a research notebook"
                description="Choose a notebook above to load its research sources and any saved knowledge graph."
              />
            ) : !notebookLoaded || generating || loadingPapers ? (
              <GraphLoading generating={generating} />
            ) : !notebook ? (
              <GraphPrompt
                title="Notebook unavailable"
                description="Choose another notebook from the selector above, or return to your notebook list."
              />
            ) : filteredNodes.length === 0 ? (
              <GraphEmpty
                hasSources={selectedResourceIds.length > 0}
                hasGraph={nodes.length > 0}
                hasSearch={Boolean(searchQuery.trim()) || nodeType !== "all"}
                onGenerate={generateGraph}
              />
            ) : (
              <GraphCanvas
                nodes={filteredNodes}
                edges={visibleEdges}
                selectedNode={selectedNode}
                selectedNeighborhood={selectedNeighborhood}
                onSelect={setSelectedNode}
                onClearSelection={clearGraphSelection}
                zoom={zoom}
              />
            )}
          </section>

          {/* Details panel */}
          <aside className="min-h-[620px] overflow-hidden rounded-2xl border border-white/[0.08] bg-slate-950/40">
            <div className="flex items-center justify-between border-b border-white/[0.08] p-5">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-indigo-400">
                  Entity Details
                </p>
                <p className="mt-1 text-xs text-slate-400">
                  Inspect relationships and supporting evidence.
                </p>
              </div>

              {selectedNode && (
                <button
                  type="button"
                  onClick={clearGraphSelection}
                  className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition hover:bg-white/[0.06] hover:text-white"
                  aria-label="Clear selected entity"
                  title="Clear selection"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>

            {selectedNode ? (
              <EntityDetails
                node={selectedNode}
                edges={edges}
                nodes={nodes}
                papers={papers}
                onSelectNode={setSelectedNode}
              />
            ) : (
              <div className="flex h-[500px] flex-col items-center justify-center px-6 text-center">
                <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-white/[0.08] bg-slate-900/70">
                  <Network className="h-5 w-5 text-slate-500" />
                </div>
                <p className="mt-4 text-xs font-medium text-slate-300">
                  No entity selected
                </p>
                <p className="mt-2 text-[10px] leading-5 text-slate-500">
                  Select a node to inspect its relationships, evidence, and
                  source papers. Use Clear selection to return to the full graph.
                </p>
              </div>
            )}
          </aside>
        </div>

        {/* Graph statistics */}
        {nodes.length > 0 && (
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <Stat label="Nodes" value={nodes.length} />
            <Stat label="Relationships" value={edges.length} />
            <Stat label="Visible nodes" value={filteredNodes.length} />
            <Stat
              label="Sources"
              value={
                new Set(
                  nodes.flatMap((node) =>
                    Array.isArray(node.resource_ids)
                      ? node.resource_ids.map(String)
                      : []
                  )
                ).size
              }
            />
            {savedGraph && (
              <Stat label="Snapshot" value="Saved" />
            )}
            {searchQuery && (
              <span className="text-[10px] text-slate-400">
                Search: "{searchQuery}"
              </span>
            )}
          </div>
        )}
      </div>
    </AppLayout>
  );
}

function GraphLegend() {
  const visibleTypes = [
    "paper",
    "method",
    "model",
    "dataset",
    "metric",
    "concept",
    "finding",
    "limitation",
    "future_work",
  ];

  return (
    <div className="absolute left-4 top-[4.7rem] z-20 hidden max-w-[440px] rounded-xl border border-slate-200 bg-white/95 px-3 py-2.5 shadow-sm backdrop-blur md:block">
      <div className="flex flex-wrap gap-x-3 gap-y-2">
        {visibleTypes.map((type) => (
          <div key={type} className="flex items-center gap-1.5">
            <span
              className="h-2 w-2 rounded-full"
              style={{ backgroundColor: NODE_STYLES[type].hex }}
            />
            <span className="text-[8px] text-slate-600">
              {formatNodeType(type)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}


function GraphCanvas({
  nodes,
  edges,
  selectedNode,
  selectedNeighborhood,
  onSelect,
  onClearSelection,
  zoom,
}) {
  const width = 1200;
  const height = 680;

  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const dragStart = useRef(null);
  const hasDragged = useRef(false);

  const positionedNodes = useMemo(
    () => calculateGraphLayout(nodes, edges, width, height),
    [nodes, edges]
  );

  const nodeMap = useMemo(
    () =>
      Object.fromEntries(
        positionedNodes.map((node) => [String(node.id), node])
      ),
    [positionedNodes]
  );

  useEffect(() => {
    setPan({ x: 0, y: 0 });
    setDragging(false);
    dragStart.current = null;
    hasDragged.current = false;
  }, [nodes, edges]);

  const handlePointerDown = (event) => {
    // Selecting a node should never initiate canvas panning.
    if (event.target.closest("[data-graph-node]")) return;

    // Only start a pan with the primary mouse button.
    if (event.pointerType === "mouse" && event.button !== 0) return;

    hasDragged.current = false;

    dragStart.current = {
      clientX: event.clientX,
      clientY: event.clientY,
      panX: pan.x,
      panY: pan.y,
    };

    setDragging(true);

    try {
      event.currentTarget.setPointerCapture?.(event.pointerId);
    } catch {
      // Pointer capture is optional; ordinary pointer events still work.
    }
  };

  const handlePointerMove = (event) => {
    if (!dragging || !dragStart.current) return;

    const deltaX = event.clientX - dragStart.current.clientX;
    const deltaY = event.clientY - dragStart.current.clientY;

    // Distinguish an actual pan from a normal click on empty canvas.
    if (Math.abs(deltaX) > 4 || Math.abs(deltaY) > 4) {
      hasDragged.current = true;
    }

    setPan({
      x: dragStart.current.panX + deltaX,
      y: dragStart.current.panY + deltaY,
    });
  };

  const stopDragging = () => {
    setDragging(false);
    dragStart.current = null;
  };

  const handleCanvasClick = (event) => {
    // Node clicks are handled by the node itself.
    if (event.target.closest("[data-graph-node]")) return;

    // A pan should not be interpreted as a request to deselect.
    if (hasDragged.current) {
      hasDragged.current = false;
      return;
    }

    onClearSelection();
  };

  return (
    <div
      data-kg-canvas
      className={`absolute inset-0 overflow-hidden ${
        dragging ? "cursor-grabbing" : "cursor-grab"
      }`}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={stopDragging}
      onPointerCancel={stopDragging}
      onLostPointerCapture={stopDragging}
      onClick={handleCanvasClick}
    >
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="h-full w-full select-none"
        style={{
          transform: `translate(${pan.x / 2}px, ${pan.y / 2}px) scale(${zoom})`,
          transformOrigin: "center",
          transition: dragging ? "none" : "transform 180ms ease",
        }}
      >
        <defs>
          <pattern
            id="graph-grid"
            width="32"
            height="32"
            patternUnits="userSpaceOnUse"
          >
            <path
              d="M 32 0 L 0 0 0 32"
              fill="none"
              stroke="#cbd5e1"
              strokeWidth="1"
            />
          </pattern>

          <marker
            id="graph-arrow"
            markerWidth="8"
            markerHeight="8"
            refX="7"
            refY="4"
            orient="auto"
            markerUnits="userSpaceOnUse"
          >
            <path d="M0,0 L8,4 L0,8 Z" fill="#64748b" />
          </marker>

          <marker
            id="graph-arrow-highlight"
            markerWidth="9"
            markerHeight="9"
            refX="8"
            refY="4.5"
            orient="auto"
            markerUnits="userSpaceOnUse"
          >
            <path d="M0,0 L9,4.5 L0,9 Z" fill="#4f46e5" />
          </marker>
        </defs>

        <rect width="100%" height="100%" fill="#f8fafc" />
        <rect
          width="100%"
          height="100%"
          fill="url(#graph-grid)"
          opacity="0.65"
        />

        {/* Relationship edges */}
        {edges.map((edge, index) => {
          const source = nodeMap[String(edge.source)];
          const target = nodeMap[String(edge.target)];

          if (!source || !target) return null;

          const isConnected =
            Boolean(selectedNode) &&
            (String(edge.source) === String(selectedNode.id) ||
              String(edge.target) === String(selectedNode.id));

          const isFocused = !selectedNode || isConnected;

          const midpoint = getEdgeMidpoint(source, target);
          const path = buildCurvedEdgePath(source, target);
          const label = formatRelationship(edge.relationship);
          const labelWidth = Math.min(
            150,
            Math.max(74, label.length * 5.8 + 16)
          );

          return (
            <g
              key={`${edge.source}-${edge.target}-${edge.relationship}-${index}`}
              opacity={isFocused ? 1 : 0.18}
            >
              <path
                d={path}
                fill="none"
                stroke={isConnected ? "#4f46e5" : "#64748b"}
                strokeOpacity={
                  !selectedNode ? 0.72 : isConnected ? 1 : 0.35
                }
                strokeWidth={isConnected ? 2.8 : 1.5}
                markerEnd={
                  isConnected
                    ? "url(#graph-arrow-highlight)"
                    : "url(#graph-arrow)"
                }
                strokeLinecap="round"
              />

              {edge.relationship && (
                <g opacity={!selectedNode ? 1 : isConnected ? 1 : 0.3}>
                  <rect
                    x={midpoint.x - labelWidth / 2}
                    y={midpoint.y - 10}
                    width={labelWidth}
                    height="20"
                    rx="6"
                    fill={isConnected ? "#eef2ff" : "#ffffff"}
                    fillOpacity="0.98"
                    stroke={isConnected ? "#a5b4fc" : "#cbd5e1"}
                    strokeWidth={isConnected ? 1.2 : 0.8}
                  />

                  <text
                    x={midpoint.x}
                    y={midpoint.y + 3}
                    textAnchor="middle"
                    fill={isConnected ? "#3730a3" : "#334155"}
                    fontSize="8.5"
                    fontWeight={isConnected ? 700 : 500}
                  >
                    {truncate(label, 23)}
                  </text>
                </g>
              )}
            </g>
          );
        })}

        {/* Entity nodes */}
        {positionedNodes.map((node) => {
          const nodeId = String(node.id);
          const selected = String(selectedNode?.id) === nodeId;

          const isNeighbor =
            Boolean(selectedNode) &&
            !selected &&
            selectedNeighborhood?.has(nodeId);

          const isFocused = !selectedNode || selected || isNeighbor;

          const style = NODE_STYLES[node.type] || NODE_STYLES.concept;
          const radius = getNodeRadius(node, edges);
          const degree = getNodeDegree(node.id, edges);

          return (
            <g
              key={node.id}
              data-graph-node
              transform={`translate(${node.x}, ${node.y})`}
              onClick={(event) => {
                event.stopPropagation();
                onSelect(node);
              }}
              className="cursor-pointer"
              opacity={isFocused ? 1 : 0.22}
              style={{
                transition: "opacity 160ms ease",
              }}
            >
              {/* Soft halo for entities connected to the selected node */}
              {isNeighbor && (
                <circle
                  r={radius + 8}
                  fill="#4f46e5"
                  fillOpacity="0.08"
                  stroke="#818cf8"
                  strokeOpacity="0.9"
                  strokeWidth="1.8"
                />
              )}

              {/* Existing halo for well-connected entities */}
              {!selected &&
                !isNeighbor &&
                node.type !== "paper" &&
                degree >= 2 && (
                  <circle
                    r={radius + 7}
                    fill={style.hex}
                    fillOpacity="0.07"
                    stroke={style.hex}
                    strokeOpacity="0.25"
                    strokeWidth="1"
                  />
                )}

              {/* Strong selection ring */}
              {selected && (
                <>
                  <circle
                    r={radius + 12}
                    fill="#4f46e5"
                    fillOpacity="0.08"
                    stroke="#818cf8"
                    strokeOpacity="0.4"
                    strokeWidth="5"
                  />

                  <circle
                    r={radius + 8}
                    fill="none"
                    stroke="#4f46e5"
                    strokeWidth="2.5"
                  />
                </>
              )}

              <circle
                r={radius}
                fill="#ffffff"
                stroke={selected ? "#4f46e5" : style.hex}
                strokeOpacity={isFocused ? 1 : 0.6}
                strokeWidth={
                  selected ? 3.5 : isNeighbor ? 2.8 : node.type === "paper" ? 2.5 : 1.8
                }
              />

              <circle
                r={radius - 3}
                fill={style.hex}
                fillOpacity={node.type === "paper" ? 0.12 : 0.06}
              />

              <circle
                r={node.type === "paper" ? 6 : 4.5}
                fill={style.hex}
              />

              {degree > 1 && (
                <text
                  x={radius - 2}
                  y={-radius + 4}
                  textAnchor="end"
                  fill="#475569"
                  fontSize="7"
                  fontWeight={selected || isNeighbor ? 700 : 400}
                >
                  {degree}
                </text>
              )}

              {/* Entity name */}
              <text
                y={radius + 18}
                textAnchor="middle"
                fill={selected ? "#020617" : "#1e293b"}
                stroke="#f8fafc"
                strokeWidth={selected || isNeighbor ? "3.5" : "3"}
                paintOrder="stroke"
                fontSize={node.type === "paper" ? 10 : 9}
                fontWeight={
                  selected || isNeighbor || node.type === "paper" ? 700 : 500
                }
              >
                {truncate(node.name, node.type === "paper" ? 30 : 25)}
              </text>

              {/* Entity type */}
              <text
                y={radius + 31}
                textAnchor="middle"
                fill={style.hex}
                fontSize="7.5"
                fontWeight={selected || isNeighbor ? 700 : 600}
              >
                {formatNodeType(node.type)}
              </text>
            </g>
          );
        })}
      </svg>

      {/* Canvas guidance */}
      <div className="pointer-events-none absolute bottom-[4.7rem] left-5 rounded-lg border border-slate-200 bg-white/95 px-2.5 py-1.5 shadow-sm">
        <p className="text-[9px] text-slate-600">
          Drag to explore · Click an entity to focus · Click empty space to clear
        </p>
      </div>

      {/* Focus status */}
      {selectedNode && (
        <div className="pointer-events-none absolute left-4 top-[7.8rem] z-20 max-w-[230px] rounded-xl border border-indigo-200 bg-white/95 px-3 py-2 shadow-sm backdrop-blur">
          <p className="text-[8px] font-semibold uppercase tracking-[0.14em] text-indigo-600">
            Focused entity
          </p>

          <p className="mt-1 truncate text-xs font-semibold text-slate-800">
            {selectedNode.name}
          </p>

          <p className="mt-1 text-[9px] text-slate-500">
            Direct connections highlighted
          </p>
        </div>
      )}
    </div>
  );
}

function calculateGraphLayout(nodes, edges, width, height) {
  if (!nodes.length) return [];

  if (nodes.length === 1) {
    return [{ ...nodes[0], x: width / 2, y: height / 2 }];
  }

  const degree = Object.fromEntries(nodes.map((node) => [String(node.id), 0]));

  edges.forEach((edge) => {
    if (degree[String(edge.source)] !== undefined) degree[String(edge.source)]++;
    if (degree[String(edge.target)] !== undefined) degree[String(edge.target)]++;
  });

  const papers = nodes.filter((node) => node.type === "paper");
  const entities = nodes.filter((node) => node.type !== "paper");
  const positions = {};

  const paperRadius = Math.min(255, 150 + papers.length * 22);

  papers.forEach((paper, index) => {
    const angle =
      (index / Math.max(papers.length, 1)) * Math.PI * 2 - Math.PI / 2;

    positions[String(paper.id)] = {
      x: width / 2 + Math.cos(angle) * paperRadius,
      y: height / 2 + Math.sin(angle) * paperRadius,
    };
  });

  const maxDegree = Math.max(
    ...entities.map((node) => degree[String(node.id)] || 0),
    1
  );

  entities.forEach((node, index) => {
    const connectivity = (degree[String(node.id)] || 0) / maxDegree;
    const radialDistance = 95 + (1 - connectivity) * 175;
    const angle = stableAngle(node.id, index, entities.length);

    positions[String(node.id)] = {
      x: width / 2 + Math.cos(angle) * radialDistance,
      y: height / 2 + Math.sin(angle) * radialDistance,
    };
  });

  const result = nodes.map((node) => ({
    ...node,
    x: positions[String(node.id)]?.x ?? width / 2,
    y: positions[String(node.id)]?.y ?? height / 2,
  }));

  const nodeIndex = new Map(
    result.map((node, index) => [String(node.id), index])
  );

  const iterations = nodes.length > 45 ? 24 : 36;

  for (let iteration = 0; iteration < iterations; iteration++) {
    const forces = result.map(() => ({ x: 0, y: 0 }));

    // Repulsion between nodes.
    for (let i = 0; i < result.length; i++) {
      for (let j = i + 1; j < result.length; j++) {
        const a = result[i];
        const b = result[j];

        let dx = b.x - a.x;
        let dy = b.y - a.y;
        let distance = Math.sqrt(dx * dx + dy * dy);

        if (distance < 0.01) {
          dx = 1;
          dy = 0;
          distance = 1;
        }

        const minDistance =
          a.type === "paper" || b.type === "paper" ? 110 : 78;

        const strength = Math.max(0, minDistance - distance) * 0.018;
        const nx = dx / distance;
        const ny = dy / distance;

        forces[i].x -= nx * strength;
        forces[i].y -= ny * strength;
        forces[j].x += nx * strength;
        forces[j].y += ny * strength;
      }
    }

    // Attraction along relationships.
    edges.forEach((edge) => {
      const sourceIndex = nodeIndex.get(String(edge.source));
      const targetIndex = nodeIndex.get(String(edge.target));

      if (sourceIndex === undefined || targetIndex === undefined) return;

      const source = result[sourceIndex];
      const target = result[targetIndex];

      let dx = target.x - source.x;
      let dy = target.y - source.y;
      const distance = Math.max(1, Math.sqrt(dx * dx + dy * dy));

      const desired =
        source.type === "paper" || target.type === "paper" ? 165 : 135;

      const strength = (distance - desired) * 0.008;
      dx /= distance;
      dy /= distance;

      forces[sourceIndex].x += dx * strength;
      forces[sourceIndex].y += dy * strength;
      forces[targetIndex].x -= dx * strength;
      forces[targetIndex].y -= dy * strength;
    });

    result.forEach((node, index) => {
      node.x += forces[index].x * 0.82;
      node.y += forces[index].y * 0.82;
      node.x = clamp(node.x, 65, width - 65);
      node.y = clamp(node.y, 75, height - 75);
    });
  }

  return result;
}

function buildCurvedEdgePath(source, target) {
  const dx = target.x - source.x;
  const dy = target.y - source.y;
  const distance = Math.sqrt(dx * dx + dy * dy);

  if (distance < 1) {
    return `M ${source.x} ${source.y} L ${target.x} ${target.y}`;
  }

  const normalX = -dy / distance;
  const normalY = dx / distance;
  const curve = Math.min(45, distance * 0.12);
  const midpointX = (source.x + target.x) / 2;
  const midpointY = (source.y + target.y) / 2;
  const controlX = midpointX + normalX * curve;
  const controlY = midpointY + normalY * curve;

  return `M ${source.x} ${source.y} Q ${controlX} ${controlY} ${target.x} ${target.y}`;
}

function getEdgeMidpoint(source, target) {
  return {
    x: (source.x + target.x) / 2,
    y: (source.y + target.y) / 2,
  };
}

function EntityDetails({ node, edges, nodes, papers, onSelectNode }) {
  const related = edges
    .filter(
      (edge) =>
        String(edge.source) === String(node.id) ||
        String(edge.target) === String(node.id)
    )
    .map((edge) => {
      const outgoing = String(edge.source) === String(node.id);
      const otherId = outgoing ? edge.target : edge.source;
      const other = nodes.find((item) => String(item.id) === String(otherId));

      return {
        ...edge,
        other,
        direction: outgoing ? "outgoing" : "incoming",
      };
    })
    .filter((item) => item.other);

  const style = NODE_STYLES[node.type] || NODE_STYLES.concept;
  const sourceIds = Array.isArray(node.resource_ids) ? node.resource_ids : [];
  const sourcePapers = sourceIds.map(
    (id) =>
      papers.find((paper) => String(paper.id) === String(id)) || {
        id: String(id),
        title: "Research source",
      }
  );

  return (
    <div className="max-h-[calc(100vh-13rem)] overflow-y-auto p-5">
      <div className="flex items-start gap-3">
        <div
          className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-white/[0.10] ${style.fill}`}
        >
          <Network className={`h-5 w-5 ${style.text}`} />
        </div>

        <div className="min-w-0">
          <p className="break-words text-sm font-medium text-slate-100">
            {node.name}
          </p>
          <p className={`mt-1 text-[10px] uppercase tracking-wide ${style.text}`}>
            {formatNodeType(node.type)}
          </p>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2">
        <MiniStat label="Connections" value={related.length} />
        <MiniStat label="Sources" value={sourceIds.length} />
      </div>

      {node.description && (
        <DetailSection title="Description">
          <p className="text-xs leading-5 text-slate-300">{node.description}</p>
        </DetailSection>
      )}

      <DetailSection title="Relationships">
        {related.length === 0 ? (
          <div className="rounded-xl border border-white/[0.08] bg-slate-900/40 p-3">
            <p className="text-xs text-slate-400">
              No relationships are associated with this entity.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {related.map((item, index) => (
              <button
                type="button"
                key={`${item.other.id}-${item.relationship}-${index}`}
                onClick={() => onSelectNode(item.other)}
                className="block w-full rounded-xl border border-white/[0.08] bg-slate-900/50 p-3 text-left transition hover:border-indigo-400/30 hover:bg-slate-900"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[9px] font-semibold uppercase tracking-wide text-indigo-300">
                    {formatRelationship(item.relationship)}
                  </span>
                  <span className="text-[8px] text-slate-500">
                    {item.direction}
                  </span>
                </div>

                <p className="mt-1 break-words text-xs text-slate-200">
                  {item.other.name}
                </p>
                <p className="mt-1 text-[9px] text-slate-400">
                  {formatNodeType(item.other.type)}
                </p>

                {item.evidence && (
                  <p className="mt-2 border-t border-white/[0.06] pt-2 text-[10px] leading-4 text-slate-400">
                    "{item.evidence}"
                  </p>
                )}
              </button>
            ))}
          </div>
        )}
      </DetailSection>

      {Array.isArray(node.evidence) && node.evidence.length > 0 && (
        <DetailSection title="Evidence">
          <div className="space-y-2">
            {node.evidence.map((item, index) => (
              <div
                key={`${item.chunk_index ?? "chunk"}-${index}`}
                className="rounded-xl border border-cyan-400/10 bg-cyan-400/[0.04] p-3"
              >
                <div className="flex items-center gap-2">
                  <FileText className="h-3 w-3 text-cyan-300" />
                  <span className="text-[9px] font-medium uppercase tracking-wide text-cyan-300">
                    Chunk {item.chunk_index ?? "—"}
                  </span>
                </div>
                {item.statement && (
                  <p className="mt-2 text-[10px] leading-5 text-slate-300">
                    "{item.statement}"
                  </p>
                )}
              </div>
            ))}
          </div>
        </DetailSection>
      )}

      <DetailSection title="Source Papers">
        {sourcePapers.length === 0 ? (
          <p className="text-[10px] leading-5 text-slate-400">
            No source paper metadata is available for this entity.
          </p>
        ) : (
          <div className="space-y-2">
            {sourcePapers.map((paper) => (
              <div
                key={paper.id}
                className="rounded-xl border border-white/[0.08] bg-slate-900/50 p-3"
              >
                <div className="flex items-start gap-2">
                  <FileText className="mt-0.5 h-3.5 w-3.5 shrink-0 text-indigo-300" />
                  <p className="break-words text-[10px] leading-4 text-slate-300">
                    {paper.title}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </DetailSection>

      <DetailSection title="Graph Identity">
        <div className="rounded-xl border border-white/[0.08] bg-slate-900/50 p-3">
          <p className="break-all font-mono text-[9px] leading-4 text-slate-300">
            {node.id}
          </p>
        </div>
      </DetailSection>
    </div>
  );
}

function DetailSection({ title, children }) {
  return (
    <div className="mt-6">
      <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-slate-400">
        {title}
      </p>
      <div className="mt-3">{children}</div>
    </div>
  );
}

function MiniStat({ label, value }) {
  return (
    <div className="rounded-xl border border-white/[0.08] bg-slate-900/50 px-3 py-2">
      <p className="text-[8px] uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-1 text-sm font-medium text-slate-100">{value}</p>
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-white/[0.08] bg-slate-950/40 px-3 py-2">
      <span className="text-[9px] uppercase tracking-wide text-slate-400">
        {label}
      </span>
      <span className="text-xs font-medium text-slate-100">{value}</span>
    </div>
  );
}

function GraphLoading({ generating = false }) {
  return (
    <div className="flex min-h-[620px] flex-col items-center justify-center px-6 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-indigo-200 bg-white">
        <Loader2 className="h-6 w-6 animate-spin text-indigo-600" />
      </div>
      <p className="mt-4 text-sm font-semibold text-slate-800">
        {generating ? "Building knowledge graph" : "Loading research context"}
      </p>
      <p className="mt-2 max-w-sm text-xs leading-5 text-slate-500">
        {generating
          ? "Extracting entities and validating relationships from your selected sources."
          : "Loading your notebook, sources, and saved graph."}
      </p>
    </div>
  );
}

function GraphPrompt({ title, description }) {
  return (
    <div className="flex min-h-[620px] flex-col items-center justify-center px-6 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-indigo-200 bg-white shadow-sm">
        <BookOpen className="h-6 w-6 text-indigo-600" />
      </div>
      <h2 className="mt-5 text-sm font-semibold text-slate-800">{title}</h2>
      <p className="mt-2 max-w-md text-xs leading-5 text-slate-500">
        {description}
      </p>
    </div>
  );
}

function GraphEmpty({ hasSources, hasGraph, hasSearch, onGenerate }) {
  const title = hasSearch
    ? "No matching entities"
    : !hasSources
      ? "No research sources selected"
      : hasGraph
        ? "No entities match the current filters"
        : "Knowledge graph not generated";

  const description = hasSearch
    ? "Try another search term or choose a different entity type."
    : !hasSources
      ? "Add research papers to this notebook before generating a graph."
      : hasGraph
        ? "Clear the search or change the entity filter to see more of the graph."
        : "Generate a graph to explore the entities and relationships in your research sources.";

  return (
    <div className="flex min-h-[620px] flex-col items-center justify-center px-6 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-slate-200 bg-white">
        <Network className="h-6 w-6 text-indigo-600" />
      </div>

      <h2 className="mt-5 text-sm font-semibold text-slate-800">{title}</h2>
      <p className="mt-2 max-w-md text-xs leading-5 text-slate-500">
        {description}
      </p>

      {!hasGraph && hasSources && !hasSearch && (
        <button
          type="button"
          onClick={onGenerate}
          className="mt-5 flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-medium text-white transition hover:bg-indigo-500"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Generate graph
        </button>
      )}
    </div>
  );
}

function getNodeDegree(nodeId, edges) {
  return edges.reduce((count, edge) => {
    if (
      String(edge.source) === String(nodeId) ||
      String(edge.target) === String(nodeId)
    ) {
      return count + 1;
    }
    return count;
  }, 0);
}

function getNodeRadius(node, edges) {
  const degree = getNodeDegree(node.id, edges);
  if (node.type === "paper") return Math.min(31, 25 + degree * 1.4);
  return Math.min(24, 18 + degree * 1.1);
}

function stableAngle(id, index, total) {
  const text = String(id);
  let hash = 0;

  for (let i = 0; i < text.length; i++) {
    hash = (hash * 31 + text.charCodeAt(i)) | 0;
  }

  const normalized = Math.abs(hash) / 2147483647;

  return (
    (index / Math.max(total, 1)) * Math.PI * 2 -
    Math.PI / 2 +
    normalized * 0.45
  );
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function truncate(value = "", max = 24) {
  const text = String(value);
  return text.length <= max ? text : `${text.slice(0, max)}…`;
}

function formatNodeType(type = "") {
  if (!type || type === "all") return type === "all" ? "All" : "Entity";

  return String(type)
    .replaceAll("_", " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatRelationship(relationship = "") {
  if (!relationship) return "Related";

  return String(relationship)
    .replaceAll("_", " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

export default KnowledgeGraph;
