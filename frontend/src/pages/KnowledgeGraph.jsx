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
  ExternalLink,
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
  },
  author: {
    fill: "fill-cyan-500/15",
    stroke: "stroke-cyan-400",
    dot: "fill-cyan-400",
    text: "text-cyan-300",
  },
  method: {
    fill: "fill-violet-500/15",
    stroke: "stroke-violet-400",
    dot: "fill-violet-400",
    text: "text-violet-300",
  },
  dataset: {
    fill: "fill-emerald-500/15",
    stroke: "stroke-emerald-400",
    dot: "fill-emerald-400",
    text: "text-emerald-300",
  },
  metric: {
    fill: "fill-amber-500/15",
    stroke: "stroke-amber-400",
    dot: "fill-amber-400",
    text: "text-amber-300",
  },
  concept: {
    fill: "fill-sky-500/15",
    stroke: "stroke-sky-400",
    dot: "fill-sky-400",
    text: "text-sky-300",
  },
  finding: {
    fill: "fill-green-500/15",
    stroke: "stroke-green-400",
    dot: "fill-green-400",
    text: "text-green-300",
  },
  limitation: {
    fill: "fill-red-500/15",
    stroke: "stroke-red-400",
    dot: "fill-red-400",
    text: "text-red-300",
  },
  future_work: {
    fill: "fill-orange-500/15",
    stroke: "stroke-orange-400",
    dot: "fill-orange-400",
    text: "text-orange-300",
  },
  problem: {
    fill: "fill-pink-500/15",
    stroke: "stroke-pink-400",
    dot: "fill-pink-400",
    text: "text-pink-300",
  },
  organization: {
    fill: "fill-blue-500/15",
    stroke: "stroke-blue-400",
    dot: "fill-blue-400",
    text: "text-blue-300",
  },
  tool: {
    fill: "fill-teal-500/15",
    stroke: "stroke-teal-400",
    dot: "fill-teal-400",
    text: "text-teal-300",
  },
  model: {
    fill: "fill-purple-500/15",
    stroke: "stroke-purple-400",
    dot: "fill-purple-400",
    text: "text-purple-300",
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

        const response = await fetch(`${API_URL}/api/papers/`);

        if (!response.ok) {
          throw new Error("Failed to load research sources.");
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
          err.message || "Failed to load research sources."
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
        selectedResourceIds.includes(String(paper.id))
      ),
    [papers, selectedResourceIds]
  );

  // --------------------------------------------------
  // Filter nodes
  // --------------------------------------------------

  const filteredNodes = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();

    return nodes.filter((node) => {
      const name = String(node.name || "").toLowerCase();
      const type = String(node.type || "").toLowerCase();

      const matchesType =
        nodeType === "all" || type === nodeType;

      const matchesSearch =
        !query || name.includes(query);

      return matchesType && matchesSearch;
    });
  }, [nodes, nodeType, searchQuery]);

  // --------------------------------------------------
  // Visible edges
  // --------------------------------------------------

  const visibleEdges = useMemo(() => {
    const visibleIds = new Set(
      filteredNodes.map((node) => String(node.id))
    );

    return edges.filter(
      (edge) =>
        visibleIds.has(String(edge.source)) &&
        visibleIds.has(String(edge.target))
    );
  }, [edges, filteredNodes]);

  // --------------------------------------------------
  // Generate graph
  // --------------------------------------------------

  const generateGraph = async () => {
    if (selectedResourceIds.length === 0) {
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
          message || "Knowledge graph generation failed."
        );
      }

      const data = await response.json();

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
      Math.min(1.8, Number((current + 0.15).toFixed(2)))
    );
  };

  const zoomOut = () => {
    setZoom((current) =>
      Math.max(0.65, Number((current - 0.15).toFixed(2)))
    );
  };

  const resetZoom = () => {
    setZoom(1);
  };

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
                navigate("/research-notebook")
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
                Explore entities and relationships identified
                across the research sources selected in your notebook.
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
                  {selectedResourceIds.length} selected{" "}
                  {selectedResourceIds.length === 1
                    ? "source"
                    : "sources"}
                </p>

              </div>

            </div>

            <button
              type="button"
              onClick={() =>
                navigate("/research-notebook")
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

                {selectedPapers.map((paper) => (
                  <div
                    key={paper.id}
                    className="flex max-w-xs items-center gap-2 rounded-lg border border-white/[0.05] bg-slate-900/50 px-2.5 py-1.5"
                  >
                    <FileText className="h-3 w-3 shrink-0 text-indigo-400" />

                    <span className="truncate text-[10px] text-slate-500">
                      {paper.title}
                    </span>
                  </div>
                ))}

              </div>

            </div>
          )}

        </div>

        {/* ==================================================
            ERROR
        ================================================== */}

        {error && (
          <div className="mt-5 flex items-start justify-between gap-4 rounded-xl border border-red-400/10 bg-red-500/[0.04] px-4 py-3 text-xs text-red-300">

            <span>{error}</span>

            <button
              type="button"
              onClick={() => setError("")}
              className="shrink-0 text-red-400/70 hover:text-red-300"
            >
              <X className="h-4 w-4" />
            </button>

          </div>
        )}

        {/* ==================================================
            GRAPH WORKSPACE
        ================================================== */}

        <div className="mt-5 grid min-h-[620px] gap-5 xl:grid-cols-[minmax(0,1fr)_320px]">

          {/* ==================================================
              GRAPH CANVAS
          ================================================== */}

          <section className="relative min-h-[620px] overflow-hidden rounded-2xl border border-white/[0.07] bg-slate-950/50">

            {/* Toolbar */}

            <div className="absolute left-4 right-4 top-4 z-30 flex items-center justify-between gap-3">

              <div className="flex items-center gap-2 rounded-xl border border-white/[0.07] bg-slate-900/85 p-1.5 shadow-xl backdrop-blur">

                <div className="relative">

                  <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-600" />

                  <input
                    value={searchQuery}
                    onChange={(event) =>
                      setSearchQuery(event.target.value)
                    }
                    placeholder="Search entities..."
                    className="h-8 w-52 bg-transparent pl-8 pr-3 text-xs text-slate-300 outline-none placeholder:text-slate-600"
                  />

                </div>

              </div>

              <div className="flex items-center gap-1 rounded-xl border border-white/[0.07] bg-slate-900/85 p-1 shadow-xl backdrop-blur">

                <button
                  type="button"
                  onClick={zoomOut}
                  disabled={zoom <= 0.65}
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
                  {Math.round(zoom * 100)}%
                </button>

                <button
                  type="button"
                  onClick={zoomIn}
                  disabled={zoom >= 1.8}
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
                      generating ? "animate-spin" : ""
                    }`}
                  />
                </button>

              </div>

            </div>

            {/* Type filter */}

            <div className="absolute bottom-4 left-4 right-4 z-30">

              <div className="flex max-w-full gap-1 overflow-x-auto rounded-xl border border-white/[0.07] bg-slate-900/85 p-1.5 shadow-xl backdrop-blur">

                {NODE_TYPES.map((type) => (
                  <button
                    key={type}
                    type="button"
                    onClick={() => setNodeType(type)}
                    className={`whitespace-nowrap rounded-lg px-2.5 py-1.5 text-[9px] font-medium capitalize transition ${
                      nodeType === type
                        ? "bg-indigo-500/15 text-indigo-300"
                        : "text-slate-600 hover:bg-white/[0.03] hover:text-slate-400"
                    }`}
                  >
                    {formatNodeType(type)}
                  </button>
                ))}

              </div>

            </div>

            {/* Graph */}

            {generating ? (
              <GraphLoading />
            ) : filteredNodes.length === 0 ? (
              <GraphEmpty
                hasSources={selectedResourceIds.length > 0}
                hasGraph={nodes.length > 0}
                onGenerate={generateGraph}
              />
            ) : (
              <GraphCanvas
                nodes={filteredNodes}
                edges={visibleEdges}
                selectedNode={selectedNode}
                onSelect={setSelectedNode}
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
                      setSelectedNode(null)
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
                  Select a node to inspect its description,
                  relationships, evidence, and source reference.
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
              value={filteredNodes.length}
            />

            {searchQuery && (
              <span className="text-[10px] text-slate-700">
                Filtered by "{searchQuery}"
              </span>
            )}

          </div>
        )}

      </div>
    </AppLayout>
  );
}

// ======================================================
// Graph Canvas
// ======================================================

function GraphCanvas({
  nodes,
  edges,
  selectedNode,
  onSelect,
  zoom,
}) {
  const width = 1000;
  const height = 620;

  const [pan, setPan] = useState({
    x: 0,
    y: 0,
  });

  const [dragging, setDragging] = useState(false);
  const dragStart = useRef(null);

  const positionedNodes = useMemo(() => {
    const count = nodes.length;

    if (count === 1) {
      return [
        {
          ...nodes[0],
          x: width / 2,
          y: height / 2,
        },
      ];
    }

    const radius = Math.min(
      250,
      140 + count * 14
    );

    return nodes.map((node, index) => {
      const angle =
        (index / count) * Math.PI * 2 -
        Math.PI / 2;

      return {
        ...node,
        x:
          width / 2 +
          Math.cos(angle) * radius,
        y:
          height / 2 +
          Math.sin(angle) * radius,
      };
    });
  }, [nodes]);

  const nodeMap = useMemo(
    () =>
      Object.fromEntries(
        positionedNodes.map((node) => [
          String(node.id),
          node,
        ])
      ),
    [positionedNodes]
  );

  const handlePointerDown = (event) => {
    if (event.target.closest("[data-graph-node]")) {
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

  const handlePointerMove = (event) => {
    if (!dragging || !dragStart.current) {
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
      className={`absolute inset-0 overflow-hidden ${
        dragging ? "cursor-grabbing" : "cursor-grab"
      }`}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={stopDragging}
      onPointerLeave={stopDragging}
    >

      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="h-full w-full select-none"
        style={{
          transform: `translate(${pan.x / 2}px, ${
            pan.y / 2
          }px) scale(${zoom})`,
          transformOrigin: "center",
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
            markerWidth="7"
            markerHeight="7"
            refX="6"
            refY="3.5"
            orient="auto"
          >
            <path
              d="M0,0 L7,3.5 L0,7 Z"
              className="fill-indigo-300/50"
            />
          </marker>

        </defs>

        <rect
          width="100%"
          height="100%"
          fill="url(#graph-grid)"
          className="text-white"
        />

        {/* Edges */}

        {edges.map((edge, index) => {
          const source =
            nodeMap[String(edge.source)];

          const target =
            nodeMap[String(edge.target)];

          if (!source || !target) {
            return null;
          }

          const midpointX =
            (source.x + target.x) / 2;

          const midpointY =
            (source.y + target.y) / 2;

          return (
            <g
              key={`${edge.source}-${edge.target}-${index}`}
              pointerEvents="none"
            >

              <line
                x1={source.x}
                y1={source.y}
                x2={target.x}
                y2={target.y}
                stroke="currentColor"
                strokeOpacity="0.22"
                strokeWidth="1.5"
                markerEnd="url(#graph-arrow)"
                className="text-indigo-300"
              />

              {edge.relationship && (
                <g>

                  <rect
                    x={midpointX - 45}
                    y={midpointY - 9}
                    width="90"
                    height="18"
                    rx="5"
                    className="fill-slate-950/90"
                  />

                  <text
                    x={midpointX}
                    y={midpointY + 3}
                    textAnchor="middle"
                    className="fill-slate-500 text-[8px]"
                  >
                    {formatRelationship(
                      edge.relationship
                    )}
                  </text>

                </g>
              )}

            </g>
          );
        })}

        {/* Nodes */}

        {positionedNodes.map((node) => {
          const selected =
            String(selectedNode?.id) ===
            String(node.id);

          const style =
            NODE_STYLES[node.type] ||
            NODE_STYLES.concept;

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
            >

              {selected && (
                <circle
                  r="30"
                  className="fill-indigo-400/[0.04] stroke-indigo-400/30"
                  strokeWidth="1"
                />
              )}

              <circle
                r={selected ? 23 : 20}
                className={`${style.fill} ${style.stroke}`}
                strokeWidth={selected ? 2 : 1}
              />

              <circle
                r="5"
                className={style.dot}
              />

              <text
                y="36"
                textAnchor="middle"
                className="fill-slate-300 text-[9px]"
              >
                {truncate(
                  node.name,
                  26
                )}
              </text>

              <text
                y="49"
                textAnchor="middle"
                className={`${style.text} text-[7px]`}
              >
                {formatNodeType(node.type)}
              </text>

            </g>
          );
        })}

      </svg>

      {/* Canvas hint */}

      <div className="pointer-events-none absolute left-5 top-[4.7rem] rounded-lg border border-white/[0.05] bg-slate-950/60 px-2.5 py-1.5 backdrop-blur">
        <p className="text-[9px] text-slate-700">
          Drag to explore · Click an entity for details
        </p>
      </div>

    </div>
  );
}

// ======================================================
// Entity Details
// ======================================================

function EntityDetails({
  node,
  edges,
  nodes,
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
    .filter((item) => item.other);

  const style =
    NODE_STYLES[node.type] ||
    NODE_STYLES.concept;

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
            {formatNodeType(node.type)}
          </p>

        </div>

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
              No validated relationships are associated
              with this entity.
            </p>

          </div>
        ) : (
          <div className="space-y-2">

            {related.map((item, index) => (
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

              </div>
            ))}

          </div>
        )}

      </DetailSection>

      {/* Evidence */}

      {Array.isArray(node.evidence) &&
        node.evidence.length > 0 && (
          <DetailSection title="Evidence">

            <div className="space-y-2">

              {node.evidence.map(
                (item, index) => (
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

      {/* Source */}

      {node.resource_id && (
        <DetailSection title="Source">

          <div className="rounded-xl border border-white/[0.05] bg-slate-900/40 p-3">

            <div className="flex items-start gap-2">

              <FileText className="mt-0.5 h-3.5 w-3.5 shrink-0 text-indigo-400" />

              <div className="min-w-0">

                <p className="text-[9px] uppercase tracking-wide text-slate-700">
                  Research resource
                </p>

                <p className="mt-1 break-all text-[9px] leading-4 text-slate-600">
                  {node.resource_id}
                </p>

              </div>

            </div>

          </div>

        </DetailSection>
      )}

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
        Retrieving relevant research content and
        validating entities and relationships.
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
          : "Generate a graph to explore validated entities and relationships found across the selected research sources."}

      </p>

      {hasSources && !hasGraph && (
        <button
          type="button"
          onClick={onGenerate}
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
// Helpers
// ======================================================

function truncate(value = "", max = 24) {
  const text = String(value);

  if (text.length <= max) {
    return text;
  }

  return `${text.slice(0, max)}…`;
}

function formatNodeType(type = "") {
  if (!type || type === "all") {
    return type === "all" ? "All" : "Entity";
  }

  return String(type)
    .replaceAll("_", " ")
    .replace(/\b\w/g, (char) =>
      char.toUpperCase()
    );
}

function formatRelationship(
  relationship = ""
) {
  if (!relationship) {
    return "Related";
  }

  return String(relationship)
    .replaceAll("_", " ")
    .replace(/\b\w/g, (char) =>
      char.toUpperCase()
    );
}

export default KnowledgeGraph;