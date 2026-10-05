import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  BookOpen,
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
} from "lucide-react";

import AppLayout from "../components/AppLayout";
import { useResearchContext } from "../context/ResearchContext";

const API_URL = "http://127.0.0.1:8000";

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
  paper: {
    fill: "fill-indigo-500/20",
    stroke: "stroke-indigo-400",
    dot: "fill-indigo-400",
    text: "text-indigo-300",
    hex: "#818cf8",
  },

  author: {
    fill: "fill-cyan-500/15",
    stroke: "stroke-cyan-400",
    dot: "fill-cyan-400",
    text: "text-cyan-300",
    hex: "#22d3ee",
  },

  method: {
    fill: "fill-violet-500/15",
    stroke: "stroke-violet-400",
    dot: "fill-violet-400",
    text: "text-violet-300",
    hex: "#a78bfa",
  },

  dataset: {
    fill: "fill-emerald-500/15",
    stroke: "stroke-emerald-400",
    dot: "fill-emerald-400",
    text: "text-emerald-300",
    hex: "#34d399",
  },

  metric: {
    fill: "fill-amber-500/15",
    stroke: "stroke-amber-400",
    dot: "fill-amber-400",
    text: "text-amber-300",
    hex: "#fbbf24",
  },

  concept: {
    fill: "fill-sky-500/15",
    stroke: "stroke-sky-400",
    dot: "fill-sky-400",
    text: "text-sky-300",
    hex: "#38bdf8",
  },

  finding: {
    fill: "fill-green-500/15",
    stroke: "stroke-green-400",
    dot: "fill-green-400",
    text: "text-green-300",
    hex: "#4ade80",
  },

  limitation: {
    fill: "fill-red-500/15",
    stroke: "stroke-red-400",
    dot: "fill-red-400",
    text: "text-red-300",
    hex: "#f87171",
  },

  future_work: {
    fill: "fill-orange-500/15",
    stroke: "stroke-orange-400",
    dot: "fill-orange-400",
    text: "text-orange-300",
    hex: "#fb923c",
  },

  problem: {
    fill: "fill-pink-500/15",
    stroke: "stroke-pink-400",
    dot: "fill-pink-400",
    text: "text-pink-300",
    hex: "#f472b6",
  },

  organization: {
    fill: "fill-blue-500/15",
    stroke: "stroke-blue-400",
    dot: "fill-blue-400",
    text: "text-blue-300",
    hex: "#60a5fa",
  },

  tool: {
    fill: "fill-teal-500/15",
    stroke: "stroke-teal-400",
    dot: "fill-teal-400",
    text: "text-teal-300",
    hex: "#2dd4bf",
  },

  model: {
    fill: "fill-purple-500/15",
    stroke: "stroke-purple-400",
    dot: "fill-purple-400",
    text: "text-purple-300",
    hex: "#c084fc",
  },
};

function KnowledgeGraph() {
  const navigate = useNavigate();
  const { selectedResourceIds } = useResearchContext();

  const [papers, setPapers] = useState([]);
  const [nodes, setNodes] = useState([]);
  const [edges, setEdges] = useState([]);

  const [selectedNode, setSelectedNode] = useState(null);

  const [loadingPapers, setLoadingPapers] = useState(true);
  const [generating, setGenerating] = useState(false);

  const [error, setError] = useState("");

  const [searchQuery, setSearchQuery] = useState("");
  const [nodeType, setNodeType] = useState("all");

  const [zoom, setZoom] = useState(1);

  // --------------------------------------------------
  // Load research sources
  // --------------------------------------------------

  useEffect(() => {
    const loadPapers = async () => {
      try {
        setLoadingPapers(true);
        setError("");

        const response = await fetch(
          `${API_URL}/api/papers/`
        );

        if (!response.ok) {
          throw new Error(
            "Failed to load research sources."
          );
        }

        const data = await response.json();

        setPapers(
          Array.isArray(data)
            ? data.map((paper) => ({
                id: paper.id || paper._id,
                title:
                  paper.title ||
                  paper.filename ||
                  "Untitled Research Paper",
              }))
            : []
        );
      } catch (err) {
        console.error(err);

        setError(
          err.message ||
            "Failed to load research sources."
        );
      } finally {
        setLoadingPapers(false);
      }
    };

    loadPapers();
  }, []);

  // --------------------------------------------------
  // Selected research sources
  // --------------------------------------------------

  const selectedPapers = useMemo(
    () =>
      papers.filter((paper) =>
        selectedResourceIds.includes(
          String(paper.id)
        )
      ),
    [papers, selectedResourceIds]
  );

  // --------------------------------------------------
  // Filter nodes
  // --------------------------------------------------

  const filteredNodes = useMemo(() => {
    const query =
      searchQuery.trim().toLowerCase();

    return nodes.filter((node) => {
      const name = String(
        node.name || ""
      ).toLowerCase();

      const type = String(
        node.type || ""
      ).toLowerCase();

      const description = String(
        node.description || ""
      ).toLowerCase();

      const matchesType =
        nodeType === "all" ||
        type === nodeType;

      const matchesSearch =
        !query ||
        name.includes(query) ||
        description.includes(query);

      return (
        matchesType &&
        matchesSearch
      );
    });
  }, [
    nodes,
    nodeType,
    searchQuery,
  ]);

  // --------------------------------------------------
  // Visible edges
  // --------------------------------------------------

  const visibleEdges = useMemo(() => {
    const visibleIds = new Set(
      filteredNodes.map((node) =>
        String(node.id)
      )
    );

    return edges.filter(
      (edge) =>
        visibleIds.has(
          String(edge.source)
        ) &&
        visibleIds.has(
          String(edge.target)
        )
    );
  }, [
    edges,
    filteredNodes,
  ]);

  // --------------------------------------------------
  // Generate graph
  // --------------------------------------------------

  const generateGraph = async () => {
    if (
      selectedResourceIds.length === 0
    ) {
      setError(
        "Select at least one research source in the Research Notebook."
      );
      return;
    }

    try {
      setGenerating(true);
      setError("");
      setSelectedNode(null);
      setZoom(1);

      const response = await fetch(
        `${API_URL}/api/knowledge-graph`,
        {
          method: "POST",
          headers: {
            "Content-Type":
              "application/json",
          },
          body: JSON.stringify({
            resource_ids:
              selectedResourceIds,
          }),
        }
      );

      if (!response.ok) {
        const message =
          await response.text();

        throw new Error(
          message ||
            "Knowledge graph generation failed."
        );
      }

      const data =
        await response.json();

      setNodes(
        Array.isArray(data.nodes)
          ? data.nodes
          : []
      );

      setEdges(
        Array.isArray(data.edges)
          ? data.edges
          : []
      );
    } catch (err) {
      console.error(err);

      setError(
        err.message ||
          "Knowledge graph generation failed."
      );
    } finally {
      setGenerating(false);
    }
  };

  // --------------------------------------------------
  // Zoom
  // --------------------------------------------------

  const zoomIn = () => {
    setZoom((current) =>
      Math.min(
        1.8,
        Number(
          (current + 0.15).toFixed(2)
        )
      )
    );
  };

  const zoomOut = () => {
    setZoom((current) =>
      Math.max(
        0.65,
        Number(
          (current - 0.15).toFixed(2)
        )
      )
    );
  };

  const resetZoom = () => {
    setZoom(1);
  };

  // --------------------------------------------------
  // Selection neighborhood
  // --------------------------------------------------

  const selectedNeighborhood = useMemo(() => {
    if (!selectedNode) {
      return null;
    }

    const connected = new Set([
      String(selectedNode.id),
    ]);

    edges.forEach((edge) => {
      if (
        String(edge.source) ===
        String(selectedNode.id)
      ) {
        connected.add(
          String(edge.target)
        );
      }

      if (
        String(edge.target) ===
        String(selectedNode.id)
      ) {
        connected.add(
          String(edge.source)
        );
      }
    });

    return connected;
  }, [selectedNode, edges]);

  return (
    <AppLayout>
      <div className="min-h-[calc(100vh-6rem)]">

        {/* ==================================================
            HEADER
        ================================================== */}

        <div className="flex flex-col gap-5 border-b border-white/[0.06] pb-6 lg:flex-row lg:items-center lg:justify-between">

          <div className="flex items-start gap-3">

            <button
              type="button"
              onClick={() =>
                navigate(
                  "/research-notebook"
                )
              }
              className="mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-white/[0.07] bg-slate-900/60 text-slate-500 transition hover:bg-white/[0.04] hover:text-slate-200"
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

              <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
                Explore evidence-grounded entities
                and relationships discovered across
                your selected research sources.
              </p>

            </div>
          </div>

          <button
            type="button"
            onClick={generateGraph}
            disabled={
              generating ||
              selectedResourceIds.length === 0
            }
            className="flex shrink-0 items-center justify-center gap-2 rounded-xl bg-indigo-500 px-4 py-2.5 text-xs font-medium text-white shadow-lg shadow-indigo-500/20 transition hover:bg-indigo-400 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {generating ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Building graph...
              </>
            ) : (
              <>
                <Network className="h-4 w-4" />
                Generate Graph
              </>
            )}
          </button>

        </div>

        {/* ==================================================
            ACTIVE CONTEXT
        ================================================== */}

        <div className="mt-5 rounded-2xl border border-white/[0.06] bg-slate-950/40">

          <div className="flex flex-col gap-4 p-5 lg:flex-row lg:items-center lg:justify-between">

            <div className="flex items-center gap-3">

              <div className="flex h-9 w-9 items-center justify-center rounded-xl border border-indigo-400/10 bg-indigo-500/[0.06]">
                <BookOpen className="h-4 w-4 text-indigo-400" />
              </div>

              <div>

                <p className="text-xs font-medium text-slate-300">
                  Active Research Context
                </p>

                <p className="mt-1 text-[10px] text-slate-600">
                  {selectedResourceIds.length}{" "}
                  selected{" "}
                  {selectedResourceIds.length ===
                  1
                    ? "source"
                    : "sources"}
                </p>

              </div>

            </div>

            <button
              type="button"
              onClick={() =>
                navigate(
                  "/research-notebook"
                )
              }
              className="flex items-center gap-1.5 text-[10px] text-indigo-400 transition hover:text-indigo-300"
            >
              Change sources
              <ChevronRight className="h-3 w-3" />
            </button>

          </div>

          {selectedPapers.length > 0 && (
            <div className="border-t border-white/[0.06] px-5 py-3">

              <div className="flex flex-wrap gap-2">

                {selectedPapers.map(
                  (paper) => (
                    <div
                      key={paper.id}
                      className="flex max-w-xs items-center gap-2 rounded-lg border border-white/[0.05] bg-slate-900/50 px-2.5 py-1.5"
                    >
                      <FileText className="h-3 w-3 shrink-0 text-indigo-400" />

                      <span className="truncate text-[10px] text-slate-500">
                        {paper.title}
                      </span>
                    </div>
                  )
                )}

              </div>

            </div>
          )}

        </div>

        {/* ==================================================
            ERROR
        ================================================== */}

        {error && (
          <div className="mt-5 flex items-start justify-between gap-4 rounded-xl border border-red-400/10 bg-red-500/[0.04] px-4 py-3 text-xs text-red-300">

            <span>
              {error}
            </span>

            <button
              type="button"
              onClick={() =>
                setError("")
              }
              className="shrink-0 text-red-400/70 hover:text-red-300"
            >
              <X className="h-4 w-4" />
            </button>

          </div>
        )}

        {/* ==================================================
            GRAPH WORKSPACE
        ================================================== */}

        <div className="mt-5 grid min-h-[620px] gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">

          {/* ==================================================
              GRAPH CANVAS
          ================================================== */}

          <section className="relative min-h-[620px] overflow-hidden rounded-2xl border border-white/[0.07] bg-slate-950/50">

            {/* Top toolbar */}

            <div className="absolute left-4 right-4 top-4 z-30 flex items-center justify-between gap-3">

              <div className="flex items-center gap-2 rounded-xl border border-white/[0.07] bg-slate-900/90 p-1.5 shadow-xl backdrop-blur">

                <div className="relative">

                  <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-600" />

                  <input
                    value={searchQuery}
                    onChange={(event) =>
                      setSearchQuery(
                        event.target.value
                      )
                    }
                    placeholder="Search entities..."
                    className="h-8 w-52 bg-transparent pl-8 pr-3 text-xs text-slate-300 outline-none placeholder:text-slate-600"
                  />

                </div>

              </div>

              <div className="flex items-center gap-1 rounded-xl border border-white/[0.07] bg-slate-900/90 p-1 shadow-xl backdrop-blur">

                <button
                  type="button"
                  onClick={zoomOut}
                  disabled={
                    zoom <= 0.65
                  }
                  className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 transition hover:bg-white/[0.04] hover:text-slate-300 disabled:opacity-30"
                  title="Zoom out"
                >
                  <ZoomOut className="h-3.5 w-3.5" />
                </button>

                <button
                  type="button"
                  onClick={resetZoom}
                  className="flex h-8 min-w-10 items-center justify-center rounded-lg px-2 text-[9px] text-slate-500 transition hover:bg-white/[0.04] hover:text-slate-300"
                  title="Reset zoom"
                >
                  {Math.round(
                    zoom * 100
                  )}
                  %
                </button>

                <button
                  type="button"
                  onClick={zoomIn}
                  disabled={
                    zoom >= 1.8
                  }
                  className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 transition hover:bg-white/[0.04] hover:text-slate-300 disabled:opacity-30"
                  title="Zoom in"
                >
                  <ZoomIn className="h-3.5 w-3.5" />
                </button>

                <div className="mx-1 h-4 w-px bg-white/[0.06]" />

                <button
                  type="button"
                  onClick={generateGraph}
                  disabled={generating}
                  className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 transition hover:bg-white/[0.04] hover:text-indigo-400 disabled:opacity-40"
                  title="Regenerate graph"
                >
                  <RefreshCw
                    className={`h-3.5 w-3.5 ${
                      generating
                        ? "animate-spin"
                        : ""
                    }`}
                  />
                </button>

                <button
                  type="button"
                  onClick={() =>
                    document
                      .querySelector(
                        "[data-kg-canvas]"
                      )
                      ?.requestFullscreen?.()
                  }
                  className="hidden h-8 w-8 items-center justify-center rounded-lg text-slate-500 transition hover:bg-white/[0.04] hover:text-slate-300 sm:flex"
                  title="Fullscreen graph"
                >
                  <Maximize2 className="h-3.5 w-3.5" />
                </button>

              </div>

            </div>

            {/* Legend */}

            {nodes.length > 0 && (
              <GraphLegend />
            )}

            {/* Type filter */}

            <div className="absolute bottom-4 left-4 right-4 z-30">

              <div className="flex max-w-full gap-1 overflow-x-auto rounded-xl border border-white/[0.07] bg-slate-900/90 p-1.5 shadow-xl backdrop-blur">

                {NODE_TYPES.map(
                  (type) => (
                    <button
                      key={type}
                      type="button"
                      onClick={() =>
                        setNodeType(
                          type
                        )
                      }
                      className={`whitespace-nowrap rounded-lg px-2.5 py-1.5 text-[9px] font-medium capitalize transition ${
                        nodeType ===
                        type
                          ? "bg-indigo-500/15 text-indigo-300"
                          : "text-slate-600 hover:bg-white/[0.03] hover:text-slate-400"
                      }`}
                    >
                      {formatNodeType(
                        type
                      )}
                    </button>
                  )
                )}

              </div>

            </div>

            {/* Graph */}

            {generating ? (
              <GraphLoading />
            ) : filteredNodes.length ===
              0 ? (
              <GraphEmpty
                hasSources={
                  selectedResourceIds.length >
                  0
                }
                hasGraph={
                  nodes.length > 0
                }
                onGenerate={
                  generateGraph
                }
              />
            ) : (
              <GraphCanvas
                nodes={filteredNodes}
                edges={visibleEdges}
                selectedNode={
                  selectedNode
                }
                selectedNeighborhood={
                  selectedNeighborhood
                }
                onSelect={
                  setSelectedNode
                }
                zoom={zoom}
              />
            )}

          </section>

          {/* ==================================================
              ENTITY DETAILS
          ================================================== */}

          <aside className="min-h-[620px] overflow-hidden rounded-2xl border border-white/[0.07] bg-slate-950/40">

            <div className="border-b border-white/[0.06] p-5">

              <div className="flex items-center justify-between">

                <div>

                  <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-indigo-400">
                    Entity Details
                  </p>

                  <p className="mt-1 text-xs text-slate-600">
                    Select an entity from the graph.
                  </p>

                </div>

                {selectedNode && (
                  <button
                    type="button"
                    onClick={() =>
                      setSelectedNode(
                        null
                      )
                    }
                    className="flex h-7 w-7 items-center justify-center rounded-lg text-slate-600 transition hover:bg-white/[0.04] hover:text-slate-300"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                )}

              </div>

            </div>

            {selectedNode ? (
              <EntityDetails
                node={selectedNode}
                edges={edges}
                nodes={nodes}
                papers={papers}
              />
            ) : (
              <div className="flex h-[500px] flex-col items-center justify-center px-6 text-center">

                <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-white/[0.06] bg-slate-900/50">
                  <Network className="h-5 w-5 text-slate-700" />
                </div>

                <p className="mt-4 text-xs font-medium text-slate-500">
                  No entity selected
                </p>

                <p className="mt-2 text-[10px] leading-4 text-slate-700">
                  Select a node to inspect its
                  relationships, evidence, and
                  source papers.
                </p>

              </div>
            )}

          </aside>

        </div>

        {/* ==================================================
            GRAPH STATISTICS
        ================================================== */}

        {nodes.length > 0 && (
          <div className="mt-4 flex flex-wrap items-center gap-3">

            <Stat
              label="Nodes"
              value={nodes.length}
            />

            <Stat
              label="Relationships"
              value={edges.length}
            />

            <Stat
              label="Visible"
              value={
                filteredNodes.length
              }
            />

            <Stat
              label="Sources"
              value={
                new Set(
                  nodes.flatMap(
                    (node) =>
                      Array.isArray(
                        node.resource_ids
                      )
                        ? node.resource_ids
                        : []
                  )
                ).size
              }
            />

            {searchQuery && (
              <span className="text-[10px] text-slate-700">
                Filtered by "
                {searchQuery}"
              </span>
            )}

          </div>
        )}

      </div>
    </AppLayout>
  );
}

// ======================================================
// Graph Legend
// ======================================================

function GraphLegend() {
  const visibleTypes = [
    "paper",
    "method",
    "model",
    "dataset",
    "metric",
    "concept",
  ];

  return (
    <div className="absolute left-4 top-[4.7rem] z-20 hidden max-w-[390px] rounded-xl border border-white/[0.06] bg-slate-950/75 px-3 py-2.5 backdrop-blur md:block">

      <div className="flex flex-wrap gap-x-3 gap-y-2">

        {visibleTypes.map(
          (type) => {
            const style =
              NODE_STYLES[type];

            return (
              <div
                key={type}
                className="flex items-center gap-1.5"
              >
                <span
                  className={`h-2 w-2 rounded-full ${style.dot}`}
                />

                <span className="text-[8px] text-slate-600">
                  {formatNodeType(
                    type
                  )}
                </span>
              </div>
            );
          }
        )}

      </div>

    </div>
  );
}

// ======================================================
// Graph Canvas
// ======================================================

function GraphCanvas({
  nodes,
  edges,
  selectedNode,
  selectedNeighborhood,
  onSelect,
  zoom,
}) {
  const width = 1200;
  const height = 680;

  const [pan, setPan] = useState({
    x: 0,
    y: 0,
  });

  const [dragging, setDragging] =
    useState(false);

  const dragStart = useRef(null);

  // --------------------------------------------------
  // Build graph-aware positions
  // --------------------------------------------------

  const positionedNodes = useMemo(
    () =>
      calculateGraphLayout(
        nodes,
        edges,
        width,
        height
      ),
    [nodes, edges]
  );

  const nodeMap = useMemo(
    () =>
      Object.fromEntries(
        positionedNodes.map(
          (node) => [
            String(node.id),
            node,
          ]
        )
      ),
    [positionedNodes]
  );

  // --------------------------------------------------
  // Pointer handling
  // --------------------------------------------------

  const handlePointerDown = (
    event
  ) => {
    if (
      event.target.closest(
        "[data-graph-node]"
      )
    ) {
      return;
    }

    setDragging(true);

    dragStart.current = {
      clientX: event.clientX,
      clientY: event.clientY,
      panX: pan.x,
      panY: pan.y,
    };
  };

  const handlePointerMove = (
    event
  ) => {
    if (
      !dragging ||
      !dragStart.current
    ) {
      return;
    }

    setPan({
      x:
        dragStart.current.panX +
        (event.clientX -
          dragStart.current.clientX),
      y:
        dragStart.current.panY +
        (event.clientY -
          dragStart.current.clientY),
    });
  };

  const stopDragging = () => {
    setDragging(false);
    dragStart.current = null;
  };

  return (
    <div
      data-kg-canvas
      className={`absolute inset-0 overflow-hidden ${
        dragging
          ? "cursor-grabbing"
          : "cursor-grab"
      }`}
      onPointerDown={
        handlePointerDown
      }
      onPointerMove={
        handlePointerMove
      }
      onPointerUp={
        stopDragging
      }
      onPointerLeave={
        stopDragging
      }
    >

      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="h-full w-full select-none"
        style={{
          transform: `translate(${pan.x / 2}px, ${
            pan.y / 2
          }px) scale(${zoom})`,
          transformOrigin:
            "center",
          transition: dragging
            ? "none"
            : "transform 180ms ease",
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
              stroke="currentColor"
              strokeOpacity="0.035"
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
            <path
              d="M0,0 L8,4 L0,8 Z"
              fill="#818cf8"
              fillOpacity="0.55"
            />
          </marker>

          <filter
            id="node-glow"
            x="-100%"
            y="-100%"
            width="300%"
            height="300%"
          >
            <feGaussianBlur
              stdDeviation="4"
              result="blur"
            />

            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>

        </defs>

        <rect
          width="100%"
          height="100%"
          fill="url(#graph-grid)"
          className="text-white"
        />

        {/* ==================================================
            Edges
        ================================================== */}

        {edges.map(
          (edge, index) => {
            const source =
              nodeMap[
                String(
                  edge.source
                )
              ];

            const target =
              nodeMap[
                String(
                  edge.target
                )
              ];

            if (
              !source ||
              !target
            ) {
              return null;
            }

            const edgeConnected =
              selectedNode &&
              (
                String(
                  edge.source
                ) ===
                  String(
                    selectedNode.id
                  ) ||
                String(
                  edge.target
                ) ===
                  String(
                    selectedNode.id
                  )
              );

            const edgeOpacity =
              selectedNode
                ? edgeConnected
                  ? 0.78
                  : 0.08
                : 0.34;

            const path =
              buildCurvedEdgePath(
                source,
                target
              );

            const midpoint =
              getEdgeMidpoint(
                source,
                target
              );

            return (
              <g
                key={`${edge.source}-${edge.target}-${edge.relationship}-${index}`}
                pointerEvents="none"
              >

                <path
                  d={path}
                  fill="none"
                  stroke="#818cf8"
                  strokeOpacity={
                    edgeOpacity
                  }
                  strokeWidth={
                    edgeConnected
                      ? 2
                      : 1.25
                  }
                  markerEnd="url(#graph-arrow)"
                  className="transition-all duration-200"
                />

                {edge.relationship && (
                  <g
                    opacity={
                      selectedNode
                        ? edgeConnected
                          ? 1
                          : 0.15
                        : 0.85
                    }
                  >

                    <rect
                      x={
                        midpoint.x -
                        48
                      }
                      y={
                        midpoint.y -
                        10
                      }
                      width="96"
                      height="20"
                      rx="6"
                      fill="#020617"
                      fillOpacity="0.88"
                      stroke="#ffffff"
                      strokeOpacity="0.05"
                    />

                    <text
                      x={
                        midpoint.x
                      }
                      y={
                        midpoint.y +
                        3
                      }
                      textAnchor="middle"
                      fill="#94a3b8"
                      fontSize="8"
                    >
                      {formatRelationship(
                        edge.relationship
                      )}
                    </text>

                  </g>
                )}

              </g>
            );
          }
        )}

        {/* ==================================================
            Nodes
        ================================================== */}

        {positionedNodes.map(
          (node) => {
            const selected =
              String(
                selectedNode?.id
              ) ===
              String(node.id);

            const highlighted =
              !selectedNode ||
              selected ||
              selectedNeighborhood?.has(
                String(node.id)
              );

            const style =
              NODE_STYLES[
                node.type
              ] ||
              NODE_STYLES.concept;

            const radius =
              getNodeRadius(
                node,
                edges
              );

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
                opacity={
                  highlighted
                    ? 1
                    : 0.18
                }
              >

                {/* Shared-node halo */}

                {node.type !==
                  "paper" &&
                  getNodeDegree(
                    node.id,
                    edges
                  ) >= 2 && (
                    <circle
                      r={
                        radius +
                        8
                      }
                      fill={
                        style.hex
                      }
                      fillOpacity="0.035"
                      stroke={
                        style.hex
                      }
                      strokeOpacity="0.12"
                      strokeWidth="1"
                    />
                  )}

                {/* Selected halo */}

                {selected && (
                  <circle
                    r={
                      radius +
                      10
                    }
                    fill="none"
                    stroke="#818cf8"
                    strokeOpacity="0.45"
                    strokeWidth="1"
                    filter="url(#node-glow)"
                  />
                )}

                {/* Main node */}

                <circle
                  r={radius}
                  fill="#020617"
                  fillOpacity={
                    node.type ===
                    "paper"
                      ? 0.95
                      : 0.88
                  }
                  stroke={
                    style.hex
                  }
                  strokeOpacity={
                    selected
                      ? 1
                      : 0.65
                  }
                  strokeWidth={
                    selected
                      ? 2.4
                      : node.type ===
                        "paper"
                      ? 2
                      : 1.4
                  }
                />

                {/* Inner tint */}

                <circle
                  r={
                    radius -
                    2
                  }
                  fill={
                    style.hex
                  }
                  fillOpacity={
                    node.type ===
                    "paper"
                      ? 0.12
                      : 0.06
                  }
                />

                {/* Node center */}

                <circle
                  r={
                    node.type ===
                    "paper"
                      ? 6
                      : 4.5
                  }
                  fill={
                    style.hex
                  }
                  fillOpacity="0.9"
                />

                {/* Degree indicator */}

                {getNodeDegree(
                  node.id,
                  edges
                ) > 1 && (
                  <text
                    x={
                      radius -
                      2
                    }
                    y={
                      -radius +
                      4
                    }
                    textAnchor="end"
                    fill="#64748b"
                    fontSize="7"
                  >
                    {getNodeDegree(
                      node.id,
                      edges
                    )}
                  </text>
                )}

                {/* Label */}

                <text
                  y={
                    radius +
                    18
                  }
                  textAnchor="middle"
                  fill={
                    selected
                      ? "#e2e8f0"
                      : "#cbd5e1"
                  }
                  fontSize={
                    node.type ===
                    "paper"
                      ? 10
                      : 9
                  }
                  fontWeight={
                    node.type ===
                    "paper"
                      ? 600
                      : 400
                  }
                >
                  {truncate(
                    node.name,
                    node.type ===
                      "paper"
                      ? 30
                      : 25
                  )}
                </text>

                {/* Type */}

                <text
                  y={
                    radius +
                    31
                  }
                  textAnchor="middle"
                  fill={
                    style.hex
                  }
                  fillOpacity="0.85"
                  fontSize="7"
                >
                  {formatNodeType(
                    node.type
                  )}
                </text>

              </g>
            );
          }
        )}

      </svg>

      {/* Canvas hint */}

      <div className="pointer-events-none absolute bottom-[4.7rem] left-5 rounded-lg border border-white/[0.05] bg-slate-950/70 px-2.5 py-1.5 backdrop-blur">

        <p className="text-[9px] text-slate-700">
          Drag to explore · Click an entity
          · Shared nodes connect research sources
        </p>

      </div>

    </div>
  );
}

// ======================================================
// Graph Layout
// ======================================================

function calculateGraphLayout(
  nodes,
  edges,
  width,
  height
) {
  if (nodes.length === 0) {
    return [];
  }

  if (nodes.length === 1) {
    return [
      {
        ...nodes[0],
        x: width / 2,
        y: height / 2,
      },
    ];
  }

  const nodeMap = new Map(
    nodes.map((node) => [
      String(node.id),
      node,
    ])
  );

  const degree = {};

  nodes.forEach((node) => {
    degree[String(node.id)] = 0;
  });

  edges.forEach((edge) => {
    if (
      degree[
        String(edge.source)
      ] !== undefined
    ) {
      degree[
        String(edge.source)
      ] += 1;
    }

    if (
      degree[
        String(edge.target)
      ] !== undefined
    ) {
      degree[
        String(edge.target)
      ] += 1;
    }
  });

  // --------------------------------------------------
  // Initial semantic placement
  //
  // Papers form the outer research context.
  // Highly connected non-paper entities begin closer
  // to the center.
  // --------------------------------------------------

  const papers = nodes.filter(
    (node) =>
      node.type === "paper"
  );

  const entities = nodes.filter(
    (node) =>
      node.type !== "paper"
  );

  const positions = {};

  const paperRadius =
    Math.min(
      255,
      150 +
        papers.length * 22
    );

  papers.forEach(
    (paper, index) => {
      const angle =
        (index /
          Math.max(
            papers.length,
            1
          )) *
          Math.PI *
          2 -
        Math.PI / 2;

      positions[
        String(paper.id)
      ] = {
        x:
          width / 2 +
          Math.cos(angle) *
            paperRadius,
        y:
          height / 2 +
          Math.sin(angle) *
            paperRadius,
      };
    }
  );

  const maxDegree =
    Math.max(
      ...entities.map(
        (node) =>
          degree[
            String(node.id)
          ] || 0
      ),
      1
    );

  entities.forEach(
    (node, index) => {
      const nodeDegree =
        degree[
          String(node.id)
        ] || 0;

      const connectivity =
        nodeDegree /
        maxDegree;

      const radialDistance =
        95 +
        (1 -
          connectivity) *
          175;

      const angle =
        stableAngle(
          node.id,
          index,
          entities.length
        );

      positions[
        String(node.id)
      ] = {
        x:
          width / 2 +
          Math.cos(angle) *
            radialDistance,
        y:
          height / 2 +
          Math.sin(angle) *
            radialDistance,
      };
    }
  );

  // --------------------------------------------------
  // Lightweight force relaxation
  //
  // This makes connected nodes attract one another
  // while unrelated nodes repel each other.
  // --------------------------------------------------

  const result = nodes.map(
    (node) => ({
      ...node,
      x:
        positions[
          String(node.id)
        ]?.x ??
        width / 2,
      y:
        positions[
          String(node.id)
        ]?.y ??
        height / 2,
    })
  );

  const iterations =
    nodes.length > 45
      ? 24
      : 36;

  const nodeIndex = new Map(
    result.map(
      (node, index) => [
        String(node.id),
        index,
      ]
    )
  );

  for (
    let iteration = 0;
    iteration < iterations;
    iteration++
  ) {
    const forces = result.map(
      () => ({
        x: 0,
        y: 0,
      })
    );

    // Repulsion
    for (
      let i = 0;
      i < result.length;
      i++
    ) {
      for (
        let j = i + 1;
        j < result.length;
        j++
      ) {
        const a = result[i];
        const b = result[j];

        let dx = b.x - a.x;
        let dy = b.y - a.y;

        let distance =
          Math.sqrt(
            dx * dx +
              dy * dy
          );

        if (
          distance < 0.01
        ) {
          dx = 1;
          dy = 0;
          distance = 1;
        }

        const minDistance =
          a.type ===
            "paper" ||
          b.type ===
            "paper"
            ? 110
            : 78;

        const strength =
          Math.max(
            0,
            minDistance -
              distance
          ) * 0.018;

        const nx =
          dx / distance;

        const ny =
          dy / distance;

        forces[i].x -=
          nx * strength;

        forces[i].y -=
          ny * strength;

        forces[j].x +=
          nx * strength;

        forces[j].y +=
          ny * strength;
      }
    }

    // Edge attraction
    edges.forEach(
      (edge) => {
        const sourceIndex =
          nodeIndex.get(
            String(
              edge.source
            )
          );

        const targetIndex =
          nodeIndex.get(
            String(
              edge.target
            )
          );

        if (
          sourceIndex ===
            undefined ||
          targetIndex ===
            undefined
        ) {
          return;
        }

        const source =
          result[sourceIndex];

        const target =
          result[targetIndex];

        let dx =
          target.x -
          source.x;

        let dy =
          target.y -
          source.y;

        const distance =
          Math.max(
            1,
            Math.sqrt(
              dx * dx +
                dy * dy
            )
          );

        const desired =
          source.type ===
            "paper" ||
          target.type ===
            "paper"
            ? 165
            : 135;

        const strength =
          (distance -
            desired) *
          0.008;

        dx /= distance;
        dy /= distance;

        forces[
          sourceIndex
        ].x +=
          dx * strength;

        forces[
          sourceIndex
        ].y +=
          dy * strength;

        forces[
          targetIndex
        ].x -=
          dx * strength;

        forces[
          targetIndex
        ].y -=
          dy * strength;
      }
    );

    // Apply forces
    result.forEach(
      (node, index) => {
        const damping =
          0.82;

        node.x +=
          forces[index].x *
          damping;

        node.y +=
          forces[index].y *
          damping;

        // Keep graph inside canvas.
        node.x = clamp(
          node.x,
          65,
          width - 65
        );

        node.y = clamp(
          node.y,
          75,
          height - 75
        );
      }
    );
  }

  // --------------------------------------------------
  // Prevent extreme overlap between labels
  // --------------------------------------------------

  return result;
}

// ======================================================
// Edge Geometry
// ======================================================

function buildCurvedEdgePath(
  source,
  target
) {
  const dx =
    target.x - source.x;

  const dy =
    target.y - source.y;

  const distance =
    Math.sqrt(
      dx * dx +
        dy * dy
    );

  if (distance < 1) {
    return `M ${source.x} ${source.y} L ${target.x} ${target.y}`;
  }

  const normalX =
    -dy / distance;

  const normalY =
    dx / distance;

  const curve =
    Math.min(
      45,
      distance * 0.12
    );

  const midpointX =
    (source.x +
      target.x) /
    2;

  const midpointY =
    (source.y +
      target.y) /
    2;

  const controlX =
    midpointX +
    normalX * curve;

  const controlY =
    midpointY +
    normalY * curve;

  return `
    M ${source.x} ${source.y}
    Q ${controlX} ${controlY}
      ${target.x} ${target.y}
  `;
}

function getEdgeMidpoint(
  source,
  target
) {
  return {
    x:
      (source.x +
        target.x) /
      2,
    y:
      (source.y +
        target.y) /
      2,
  };
}

// ======================================================
// Entity Details
// ======================================================

function EntityDetails({
  node,
  edges,
  nodes,
  papers,
}) {
  const related = edges
    .filter(
      (edge) =>
        String(edge.source) ===
          String(node.id) ||
        String(edge.target) ===
          String(node.id)
    )
    .map((edge) => {
      const outgoing =
        String(edge.source) ===
        String(node.id);

      const otherId = outgoing
        ? edge.target
        : edge.source;

      const other = nodes.find(
        (item) =>
          String(item.id) ===
          String(otherId)
      );

      return {
        ...edge,
        other,
        direction: outgoing
          ? "outgoing"
          : "incoming",
      };
    })
    .filter(
      (item) => item.other
    );

  const style =
    NODE_STYLES[node.type] ||
    NODE_STYLES.concept;

  const sourceIds =
    Array.isArray(
      node.resource_ids
    )
      ? node.resource_ids
      : [];

  const sourcePapers =
    sourceIds.map(
      (resourceId) =>
        papers.find(
          (paper) =>
            String(
              paper.id
            ) ===
            String(
              resourceId
            )
        ) || {
          id: resourceId,
          title:
            "Research source",
        }
    );

  return (
    <div className="max-h-[calc(100vh-13rem)] overflow-y-auto p-5">

      {/* Identity */}

      <div className="flex items-start gap-3">

        <div
          className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border ${style.stroke} ${style.fill}`}
        >
          <Network
            className={`h-5 w-5 ${style.text}`}
          />
        </div>

        <div className="min-w-0">

          <p className="break-words text-sm font-medium text-slate-200">
            {node.name}
          </p>

          <p
            className={`mt-1 text-[10px] uppercase tracking-wide ${style.text}`}
          >
            {formatNodeType(
              node.type
            )}
          </p>

        </div>

      </div>

      {/* Graph role */}

      <div className="mt-4 grid grid-cols-2 gap-2">

        <MiniStat
          label="Connections"
          value={related.length}
        />

        <MiniStat
          label="Sources"
          value={
            sourceIds.length
          }
        />

      </div>

      {/* Description */}

      {node.description && (
        <DetailSection title="Description">

          <p className="text-xs leading-5 text-slate-500">
            {node.description}
          </p>

        </DetailSection>
      )}

      {/* Relationships */}

      <DetailSection title="Relationships">

        {related.length === 0 ? (
          <div className="rounded-xl border border-white/[0.05] bg-slate-900/30 p-3">

            <p className="text-xs text-slate-600">
              No validated relationships
              are associated with this
              entity.
            </p>

          </div>
        ) : (
          <div className="space-y-2">

            {related.map(
              (item, index) => (
                <div
                  key={`${item.other.id}-${index}`}
                  className="rounded-xl border border-white/[0.05] bg-slate-900/40 p-3"
                >

                  <div className="flex items-center justify-between gap-2">

                    <span className="text-[9px] uppercase tracking-wide text-indigo-400">
                      {formatRelationship(
                        item.relationship
                      )}
                    </span>

                    <span className="text-[8px] text-slate-700">
                      {item.direction}
                    </span>

                  </div>

                  <p className="mt-1 break-words text-xs text-slate-400">
                    {item.other.name}
                  </p>

                  <p className="mt-1 text-[9px] capitalize text-slate-700">
                    {formatNodeType(
                      item.other.type
                    )}
                  </p>

                  {Array.isArray(
                    item.resource_ids
                  ) &&
                    item
                      .resource_ids
                      .length >
                      0 && (
                      <p className="mt-2 text-[8px] text-slate-700">
                        Supported by{" "}
                        {
                          item
                            .resource_ids
                            .length
                        }{" "}
                        source
                        {item
                          .resource_ids
                          .length ===
                        1
                          ? ""
                          : "s"}
                      </p>
                    )}

                </div>
              )
            )}

          </div>
        )}

      </DetailSection>

      {/* Evidence */}

      {Array.isArray(
        node.evidence
      ) &&
        node.evidence.length >
          0 && (
          <DetailSection title="Evidence">

            <div className="space-y-2">

              {node.evidence.map(
                (
                  item,
                  index
                ) => (
                  <div
                    key={`${item.chunk_index}-${index}`}
                    className="rounded-xl border border-cyan-400/[0.08] bg-cyan-400/[0.025] p-3"
                  >

                    <div className="flex items-center gap-2">

                      <FileText className="h-3 w-3 text-cyan-400" />

                      <span className="text-[9px] font-medium uppercase tracking-wide text-cyan-400">
                        Chunk{" "}
                        {item.chunk_index ??
                          "—"}
                      </span>

                    </div>

                    {item.statement && (
                      <p className="mt-2 text-[10px] leading-5 text-slate-500">
                        "{item.statement}"
                      </p>
                    )}

                  </div>
                )
              )}

            </div>

          </DetailSection>
        )}

      {/* Source papers */}

      <DetailSection title="Source Papers">

        {sourcePapers.length ===
        0 ? (
          <div className="rounded-xl border border-white/[0.05] bg-slate-900/40 p-3">

            <p className="text-[10px] text-slate-600">
              No source paper metadata
              is available.
            </p>

          </div>
        ) : (
          <div className="space-y-2">

            {sourcePapers.map(
              (paper) => (
                <div
                  key={paper.id}
                  className="rounded-xl border border-white/[0.05] bg-slate-900/40 p-3"
                >

                  <div className="flex items-start gap-2">

                    <FileText className="mt-0.5 h-3.5 w-3.5 shrink-0 text-indigo-400" />

                    <div className="min-w-0">

                      <p className="text-[9px] uppercase tracking-wide text-slate-700">
                        Research source
                      </p>

                      <p className="mt-1 break-words text-[10px] leading-4 text-slate-500">
                        {paper.title}
                      </p>

                    </div>

                  </div>

                </div>
              )
            )}

          </div>
        )}

      </DetailSection>

      {/* Technical ID */}

      <DetailSection title="Graph Identity">

        <div className="rounded-xl border border-white/[0.05] bg-slate-900/40 p-3">

          <p className="break-all font-mono text-[9px] leading-4 text-slate-700">
            {node.id}
          </p>

        </div>

      </DetailSection>

    </div>
  );
}

// ======================================================
// Detail Section
// ======================================================

function DetailSection({
  title,
  children,
}) {
  return (
    <div className="mt-6">

      <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-slate-600">
        {title}
      </p>

      <div className="mt-3">
        {children}
      </div>

    </div>
  );
}

// ======================================================
// Mini Stat
// ======================================================

function MiniStat({
  label,
  value,
}) {
  return (
    <div className="rounded-xl border border-white/[0.05] bg-slate-900/35 px-3 py-2">

      <p className="text-[8px] uppercase tracking-wide text-slate-700">
        {label}
      </p>

      <p className="mt-1 text-sm font-medium text-slate-400">
        {value}
      </p>

    </div>
  );
}

// ======================================================
// Statistics
// ======================================================

function Stat({
  label,
  value,
}) {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-white/[0.05] bg-slate-950/40 px-3 py-2">

      <span className="text-[9px] uppercase tracking-wide text-slate-700">
        {label}
      </span>

      <span className="text-xs font-medium text-slate-400">
        {value}
      </span>

    </div>
  );
}

// ======================================================
// Loading
// ======================================================

function GraphLoading() {
  return (
    <div className="flex h-full min-h-[620px] flex-col items-center justify-center">

      <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-indigo-400/10 bg-indigo-500/[0.05]">

        <Loader2 className="h-6 w-6 animate-spin text-indigo-400" />

      </div>

      <p className="mt-4 text-sm font-medium text-slate-300">
        Building knowledge graph
      </p>

      <p className="mt-2 max-w-sm text-center text-xs leading-5 text-slate-600">
        Retrieving relevant research
        evidence, extracting entities,
        and validating relationships.
      </p>

    </div>
  );
}

// ======================================================
// Empty State
// ======================================================

function GraphEmpty({
  hasSources,
  hasGraph,
  onGenerate,
}) {
  return (
    <div className="flex h-full min-h-[620px] flex-col items-center justify-center px-6 text-center">

      <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-cyan-400/10 bg-cyan-400/[0.05]">

        <Network className="h-6 w-6 text-cyan-400" />

      </div>

      <h2 className="mt-5 text-sm font-medium text-slate-300">

        {!hasSources
          ? "No research sources selected"
          : hasGraph
          ? "No matching entities"
          : "Knowledge graph not generated"}

      </h2>

      <p className="mt-2 max-w-md text-xs leading-5 text-slate-600">

        {!hasSources
          ? "Select research sources in your Research Notebook before generating a knowledge graph."
          : hasGraph
          ? "Try changing the search query or entity type filter."
          : "Generate a graph to explore evidence-grounded entities and relationships discovered across the selected research sources."}

      </p>

      {hasSources &&
        !hasGraph && (
          <button
            type="button"
            onClick={
              onGenerate
            }
            className="mt-5 flex items-center gap-2 rounded-xl bg-indigo-500 px-4 py-2.5 text-xs font-medium text-white transition hover:bg-indigo-400"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Generate graph
          </button>
        )}

    </div>
  );
}

// ======================================================
// Graph Helpers
// ======================================================

function getNodeDegree(
  nodeId,
  edges
) {
  return edges.reduce(
    (count, edge) => {
      if (
        String(
          edge.source
        ) === String(nodeId)
      ) {
        return count + 1;
      }

      if (
        String(
          edge.target
        ) === String(nodeId)
      ) {
        return count + 1;
      }

      return count;
    },
    0
  );
}

function getNodeRadius(
  node,
  edges
) {
  const degree =
    getNodeDegree(
      node.id,
      edges
    );

  if (
    node.type ===
    "paper"
  ) {
    return Math.min(
      31,
      25 + degree * 1.4
    );
  }

  return Math.min(
    24,
    18 + degree * 1.1
  );
}

function stableAngle(
  id,
  index,
  total
) {
  const text = String(id);

  let hash = 0;

  for (
    let i = 0;
    i < text.length;
    i++
  ) {
    hash =
      (hash * 31 +
        text.charCodeAt(i)) |
      0;
  }

  const normalized =
    Math.abs(hash) /
    2147483647;

  return (
    (index / Math.max(total, 1)) *
      Math.PI *
      2 -
    Math.PI / 2 +
    normalized * 0.45
  );
}

function clamp(
  value,
  min,
  max
) {
  return Math.max(
    min,
    Math.min(max, value)
  );
}

// ======================================================
// Text Helpers
// ======================================================

function truncate(
  value = "",
  max = 24
) {
  const text =
    String(value);

  if (
    text.length <= max
  ) {
    return text;
  }

  return `${text.slice(
    0,
    max
  )}…`;
}

function formatNodeType(
  type = ""
) {
  if (
    !type ||
    type === "all"
  ) {
    return type ===
      "all"
      ? "All"
      : "Entity";
  }

  return String(type)
    .replaceAll(
      "_",
      " "
    )
    .replace(
      /\b\w/g,
      (char) =>
        char.toUpperCase()
    );
}

function formatRelationship(
  relationship = ""
) {
  if (!relationship) {
    return "Related";
  }

  return String(
    relationship
  )
    .replaceAll(
      "_",
      " "
    )
    .replace(
      /\b\w/g,
      (char) =>
        char.toUpperCase()
    );
}

export default KnowledgeGraph;