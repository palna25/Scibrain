import { useEffect, useMemo, useState } from "react";
import {
  BookOpen,
  Check,
  ChevronRight,
  FileText,
  GitBranch,
  HelpCircle,
  Lightbulb,
  Loader2,
  Network,
  Search,
  Send,
  Sparkles,
  Upload,
  X,
  BarChart3,
  FileSearch,
} from "lucide-react";

import AppLayout from "../components/AppLayout";

const API_URL = "http://127.0.0.1:8000";

function ResearchNotebook() {
  const [papers, setPapers] = useState([]);
  const [selectedPaperIds, setSelectedPaperIds] = useState([]);
  const [loadingPapers, setLoadingPapers] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [message, setMessage] = useState("");
  const [activeStudio, setActiveStudio] = useState(null);

  // --------------------------------------------------
  // Load papers
  // --------------------------------------------------

  useEffect(() => {
    const fetchPapers = async () => {
      try {
        setLoadingPapers(true);

        const response = await fetch(`${API_URL}/api/papers/`);

        if (!response.ok) {
          throw new Error("Failed to fetch papers.");
        }

        const data = await response.json();

        const formattedPapers = data.map((paper) => ({
          id: paper.id,
          title: paper.title || paper.filename || "Untitled Paper",
          filename: paper.filename || "",
          pageCount: paper.page_count || 0,
          textLength: paper.text_length || 0,
          status: paper.status || "uploaded",
          uploadedAt: paper.uploaded_at || null,
        }));

        setPapers(formattedPapers);
      } catch (error) {
        console.error("Failed to load papers:", error);
      } finally {
        setLoadingPapers(false);
      }
    };

    fetchPapers();
  }, []);

  // --------------------------------------------------
  // Selected papers
  // --------------------------------------------------

  const selectedPapers = useMemo(
    () =>
      papers.filter((paper) =>
        selectedPaperIds.includes(paper.id)
      ),
    [papers, selectedPaperIds]
  );

  const filteredPapers = papers.filter((paper) => {
    const text =
      `${paper.title} ${paper.filename}`.toLowerCase();

    return text.includes(searchQuery.toLowerCase());
  });

  const togglePaper = (paperId) => {
    setSelectedPaperIds((current) =>
      current.includes(paperId)
        ? current.filter((id) => id !== paperId)
        : [...current, paperId]
    );
  };

  const clearSources = () => {
    setSelectedPaperIds([]);
  };

  // --------------------------------------------------
  // Suggested prompts
  // --------------------------------------------------

  const handlePrompt = (prompt) => {
    setMessage(prompt);
  };

  const handleSend = () => {
    if (!message.trim()) return;

    /*
      UI only for now.

      Later this will call the SciBrain
      research / RAG endpoint.
    */

    console.log("Research question:", message);
    console.log("Selected papers:", selectedPaperIds);

    setMessage("");
  };

  return (
    <AppLayout>
      <div className="flex h-[calc(100vh-6rem)] min-h-[680px] flex-col overflow-hidden rounded-2xl border border-white/[0.07] bg-slate-950/40">

        {/* ------------------------------------------------ */}
        {/* Notebook Header                                  */}
        {/* ------------------------------------------------ */}

        <div className="flex shrink-0 items-center justify-between border-b border-white/[0.06] px-6 py-4">

          <div className="flex items-center gap-3">
            <div className="relative flex h-10 w-10 items-center justify-center rounded-xl border border-indigo-400/15 bg-indigo-500/10">
              <div className="absolute inset-0 rounded-xl bg-indigo-500/10 blur-md" />

              <BookOpen className="relative h-5 w-5 text-indigo-400" />
            </div>

            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-indigo-400">
                Research Workspace
              </p>

              <h1 className="mt-0.5 text-lg font-semibold tracking-tight text-white">
                Research Notebook
              </h1>
            </div>
          </div>

          <div className="flex items-center gap-3">

            <div className="hidden items-center gap-2 rounded-lg border border-white/[0.06] bg-slate-900/60 px-3 py-2 text-[11px] text-slate-500 sm:flex">
              <FileText className="h-3.5 w-3.5" />

              {selectedPapers.length}{" "}
              {selectedPapers.length === 1
                ? "source"
                : "sources"}{" "}
              selected
            </div>

            <button
              type="button"
              className="flex items-center gap-2 rounded-xl bg-indigo-500 px-4 py-2.5 text-xs font-medium text-white shadow-lg shadow-indigo-500/20 transition hover:bg-indigo-400"
            >
              <Upload className="h-4 w-4" />
              Add Papers
            </button>

          </div>
        </div>

        {/* ------------------------------------------------ */}
        {/* Main Notebook                                    */}
        {/* ------------------------------------------------ */}

        <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[270px_minmax(0,1fr)_285px]">

          {/* ================================================= */}
          {/* SOURCES                                           */}
          {/* ================================================= */}

          <aside className="flex min-h-0 flex-col border-b border-white/[0.06] bg-slate-950/50 lg:border-b-0 lg:border-r">

            <div className="shrink-0 border-b border-white/[0.06] px-5 py-4">

              <div className="flex items-center justify-between">

                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-indigo-400">
                    Sources
                  </p>

                  <p className="mt-1 text-xs text-slate-500">
                    Select papers for this notebook
                  </p>
                </div>

                {selectedPapers.length > 0 && (
                  <button
                    type="button"
                    onClick={clearSources}
                    className="text-[10px] text-slate-600 transition hover:text-slate-300"
                  >
                    Clear
                  </button>
                )}

              </div>

              {/* Search */}
              <div className="relative mt-4">
                <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-600" />

                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) =>
                    setSearchQuery(e.target.value)
                  }
                  placeholder="Search papers..."
                  className="h-9 w-full rounded-xl border border-white/[0.07] bg-slate-900/70 pl-9 pr-3 text-xs text-slate-200 outline-none placeholder:text-slate-600 transition focus:border-indigo-400/20 focus:ring-1 focus:ring-indigo-400/10"
                />
              </div>

            </div>

            {/* Paper list */}
            <div className="min-h-0 flex-1 overflow-y-auto p-3">

              {loadingPapers ? (
                <div className="flex h-40 flex-col items-center justify-center text-center">

                  <Loader2 className="h-5 w-5 animate-spin text-indigo-400" />

                  <p className="mt-3 text-xs text-slate-500">
                    Loading papers...
                  </p>

                </div>
              ) : filteredPapers.length === 0 ? (
                <div className="flex h-40 flex-col items-center justify-center px-4 text-center">

                  <FileSearch className="h-6 w-6 text-slate-700" />

                  <p className="mt-3 text-xs text-slate-500">
                    No papers found
                  </p>

                </div>
              ) : (
                <div className="space-y-1.5">

                  {filteredPapers.map((paper) => {
                    const selected =
                      selectedPaperIds.includes(paper.id);

                    return (
                      <button
                        key={paper.id}
                        type="button"
                        onClick={() =>
                          togglePaper(paper.id)
                        }
                        className={`group flex w-full items-start gap-3 rounded-xl border p-3 text-left transition ${
                          selected
                            ? "border-indigo-400/20 bg-indigo-500/[0.08]"
                            : "border-transparent hover:border-white/[0.06] hover:bg-white/[0.025]"
                        }`}
                      >

                        {/* Checkbox */}
                        <div
                          className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border transition ${
                            selected
                              ? "border-indigo-400 bg-indigo-500 text-white"
                              : "border-slate-700 bg-slate-900 text-transparent group-hover:border-slate-500"
                          }`}
                        >
                          <Check className="h-3 w-3" />
                        </div>

                        {/* Icon */}
                        <div
                          className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border ${
                            selected
                              ? "border-indigo-400/15 bg-indigo-500/10"
                              : "border-white/[0.06] bg-slate-900"
                          }`}
                        >
                          <FileText
                            className={`h-4 w-4 ${
                              selected
                                ? "text-indigo-400"
                                : "text-slate-600"
                            }`}
                          />
                        </div>

                        {/* Info */}
                        <div className="min-w-0 flex-1">

                          <p
                            className={`truncate text-xs font-medium ${
                              selected
                                ? "text-indigo-200"
                                : "text-slate-300"
                            }`}
                          >
                            {paper.title}
                          </p>

                          <p className="mt-1 truncate text-[10px] text-slate-600">
                            {paper.pageCount > 0
                              ? `${paper.pageCount} pages`
                              : "Research paper"}
                          </p>

                        </div>

                      </button>
                    );
                  })}

                </div>
              )}

            </div>

            {/* Source footer */}
            <div className="shrink-0 border-t border-white/[0.06] p-4">

              <div className="rounded-xl border border-white/[0.05] bg-slate-900/50 p-3">

                <div className="flex items-center gap-2">

                  <Sparkles className="h-3.5 w-3.5 text-indigo-400" />

                  <span className="text-[10px] font-medium text-slate-400">
                    Notebook sources
                  </span>

                </div>

                <p className="mt-2 text-[10px] leading-4 text-slate-600">
                  Select multiple papers to investigate
                  relationships, findings and research gaps
                  across the literature.
                </p>

              </div>

            </div>

          </aside>

          {/* ================================================= */}
          {/* RESEARCH CHAT                                     */}
          {/* ================================================= */}

          <section className="flex min-h-0 flex-col bg-slate-950/20">

            {/* Chat header */}
            <div className="shrink-0 border-b border-white/[0.06] px-6 py-4">

              <div className="flex items-center gap-3">

                <div className="flex h-9 w-9 items-center justify-center rounded-xl border border-cyan-400/10 bg-cyan-400/[0.05]">
                  <Sparkles className="h-4 w-4 text-cyan-400" />
                </div>

                <div>
                  <p className="text-sm font-medium text-slate-200">
                    SciBrain Research Assistant
                  </p>

                  <p className="mt-0.5 text-[10px] text-slate-600">
                    Ask questions across your selected papers
                  </p>
                </div>

              </div>

            </div>

            {/* Chat content */}
            <div className="min-h-0 flex-1 overflow-y-auto px-6 py-8">

              {selectedPapers.length === 0 ? (
                <EmptyNotebook
                  onPrompt={handlePrompt}
                />
              ) : (
                <ActiveNotebook
                  selectedPapers={selectedPapers}
                  onPrompt={handlePrompt}
                />
              )}

            </div>

            {/* Composer */}
            <div className="shrink-0 border-t border-white/[0.06] p-5">

              {selectedPapers.length === 0 && (
                <p className="mb-3 text-center text-[10px] text-slate-600">
                  Select at least one paper to begin your
                  research session.
                </p>
              )}

              <div
                className={`mx-auto flex max-w-3xl items-end gap-2 rounded-2xl border bg-slate-900/70 p-2 transition ${
                  selectedPapers.length > 0
                    ? "border-white/[0.08] focus-within:border-indigo-400/20"
                    : "border-white/[0.05] opacity-60"
                }`}
              >

                <textarea
                  value={message}
                  onChange={(e) =>
                    setMessage(e.target.value)
                  }
                  onKeyDown={(e) => {
                    if (
                      e.key === "Enter" &&
                      !e.shiftKey
                    ) {
                      e.preventDefault();

                      if (selectedPapers.length > 0) {
                        handleSend();
                      }
                    }
                  }}
                  disabled={selectedPapers.length === 0}
                  rows={2}
                  placeholder={
                    selectedPapers.length > 0
                      ? "Ask about your research papers..."
                      : "Select papers to start asking questions..."
                  }
                  className="max-h-32 min-h-[42px] flex-1 resize-none bg-transparent px-3 py-2 text-sm text-slate-200 outline-none placeholder:text-slate-600 disabled:cursor-not-allowed"
                />

                <button
                  type="button"
                  disabled={
                    !message.trim() ||
                    selectedPapers.length === 0
                  }
                  onClick={handleSend}
                  className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-indigo-500 text-white shadow-lg shadow-indigo-500/20 transition hover:bg-indigo-400 disabled:cursor-not-allowed disabled:opacity-30"
                >
                  <Send className="h-4 w-4" />
                </button>

              </div>

              <p className="mt-2 text-center text-[9px] text-slate-700">
                SciBrain uses your selected research sources
                to provide evidence-backed responses.
              </p>

            </div>

          </section>

          {/* ================================================= */}
          {/* RESEARCH STUDIO                                   */}
          {/* ================================================= */}

          <aside className="hidden min-h-0 flex-col border-l border-white/[0.06] bg-slate-950/50 xl:flex">

            <div className="shrink-0 border-b border-white/[0.06] px-5 py-4">

              <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-indigo-400">
                Research Studio
              </p>

              <p className="mt-1 text-xs text-slate-500">
                Investigate your literature
              </p>

            </div>

            <div className="min-h-0 flex-1 overflow-y-auto p-4">

              <div className="space-y-2.5">

                <StudioCard
                  icon={BookOpen}
                  title="Research Summary"
                  description="Synthesize the selected papers"
                  onClick={() =>
                    setActiveStudio("summary")
                  }
                />

                <StudioCard
                  icon={BarChart3}
                  title="Compare Papers"
                  description="Compare methods, datasets and findings"
                  onClick={() =>
                    setActiveStudio("compare")
                  }
                />

                <StudioCard
                  icon={Lightbulb}
                  title="Research Gaps"
                  description="Discover unexplored research areas"
                  onClick={() =>
                    setActiveStudio("gaps")
                  }
                />

                <StudioCard
                  icon={GitBranch}
                  title="Conflicting Findings"
                  description="Identify disagreements across studies"
                  onClick={() =>
                    setActiveStudio("conflicts")
                  }
                />

                <StudioCard
                  icon={Network}
                  title="Knowledge Graph"
                  description="Explore entities and relationships"
                  onClick={() =>
                    setActiveStudio("graph")
                  }
                />

                <StudioCard
                  icon={FileSearch}
                  title="Evidence Map"
                  description="Trace insights back to sources"
                  onClick={() =>
                    setActiveStudio("evidence")
                  }
                />

              </div>

              {/* Selected sources */}
              <div className="mt-6">

                <div className="mb-3 flex items-center justify-between">

                  <p className="text-[10px] font-medium uppercase tracking-[0.15em] text-slate-600">
                    Active Sources
                  </p>

                  <span className="text-[10px] text-slate-700">
                    {selectedPapers.length}
                  </span>

                </div>

                {selectedPapers.length === 0 ? (
                  <div className="rounded-xl border border-dashed border-white/[0.06] p-4 text-center">

                    <p className="text-[10px] leading-4 text-slate-600">
                      Selected papers will appear here.
                    </p>

                  </div>
                ) : (
                  <div className="space-y-1.5">

                    {selectedPapers.map((paper) => (
                      <div
                        key={paper.id}
                        className="flex items-center gap-2 rounded-lg border border-white/[0.05] bg-slate-900/40 px-2.5 py-2"
                      >

                        <FileText className="h-3.5 w-3.5 shrink-0 text-indigo-400" />

                        <span className="min-w-0 flex-1 truncate text-[10px] text-slate-500">
                          {paper.title}
                        </span>

                        <button
                          type="button"
                          onClick={() =>
                            togglePaper(paper.id)
                          }
                          className="text-slate-700 transition hover:text-slate-300"
                        >
                          <X className="h-3 w-3" />
                        </button>

                      </div>
                    ))}

                  </div>
                )}

              </div>

            </div>

            {/* Studio footer */}
            <div className="shrink-0 border-t border-white/[0.06] p-4">

              <div className="flex items-start gap-2">

                <HelpCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-700" />

                <p className="text-[9px] leading-4 text-slate-600">
                  Studio tools analyze the papers selected
                  in this notebook.
                </p>

              </div>

            </div>

          </aside>

        </div>

        {/* Studio modal / panel */}
        {activeStudio && (
          <StudioPreview
            type={activeStudio}
            selectedPapers={selectedPapers}
            onClose={() => setActiveStudio(null)}
          />
        )}

      </div>
    </AppLayout>
  );
}

// ======================================================
// Empty Notebook
// ======================================================

function EmptyNotebook({ onPrompt }) {
  return (
    <div className="mx-auto flex max-w-2xl flex-col items-center text-center">

      <div className="relative flex h-16 w-16 items-center justify-center rounded-2xl border border-indigo-400/15 bg-indigo-500/10">

        <div className="absolute inset-0 rounded-2xl bg-indigo-500/10 blur-xl" />

        <BookOpen className="relative h-7 w-7 text-indigo-400" />

      </div>

      <p className="mt-6 text-[10px] font-semibold uppercase tracking-[0.25em] text-indigo-400">
        Research Notebook
      </p>

      <h2 className="mt-2 text-2xl font-semibold tracking-tight text-white">
        Explore your research
      </h2>

      <p className="mt-3 max-w-lg text-sm leading-6 text-slate-500">
        Select papers from your research library and use
        SciBrain to investigate findings, methods,
        relationships and potential research gaps.
      </p>

      {/* Suggestions */}

      <div className="mt-8 grid w-full gap-3 sm:grid-cols-2">

        <PromptCard
          icon={Lightbulb}
          title="Find research gaps"
          description="Identify unexplored areas across the selected literature."
          onClick={() =>
            onPrompt(
              "What research gaps can be identified across these papers?"
            )
          }
        />

        <PromptCard
          icon={BarChart3}
          title="Compare methodologies"
          description="Compare methods, datasets and evaluation metrics."
          onClick={() =>
            onPrompt(
              "Compare the methodologies, datasets and evaluation metrics used in these papers."
            )
          }
        />

        <PromptCard
          icon={GitBranch}
          title="Find conflicting findings"
          description="Identify studies that report different conclusions."
          onClick={() =>
            onPrompt(
              "Which papers have conflicting findings, and what may explain the differences?"
            )
          }
        />

        <PromptCard
          icon={Network}
          title="Discover connections"
          description="Explore relationships between concepts and studies."
          onClick={() =>
            onPrompt(
              "What important relationships and connections exist between these studies?"
            )
          }
        />

      </div>

    </div>
  );
}

// ======================================================
// Active Notebook
// ======================================================

function ActiveNotebook({ selectedPapers, onPrompt }) {
  return (
    <div className="mx-auto max-w-3xl">

      <div className="mb-8">

        <div className="flex items-center gap-2 text-[10px] text-slate-600">

          <Sparkles className="h-3.5 w-3.5 text-cyan-400" />

          <span>
            Analyzing {selectedPapers.length} selected{" "}
            {selectedPapers.length === 1
              ? "paper"
              : "papers"}
          </span>

        </div>

        <h2 className="mt-3 text-xl font-semibold text-white">
          What would you like to investigate?
        </h2>

        <p className="mt-2 text-sm leading-6 text-slate-500">
          Ask SciBrain a question or choose an analysis
          below. Responses will be grounded in your selected
          research sources.
        </p>

      </div>

      <div className="grid gap-3 sm:grid-cols-2">

        <PromptCard
          icon={Lightbulb}
          title="Find research gaps"
          description="Identify unexplored research opportunities."
          onClick={() =>
            onPrompt(
              "What research gaps can be identified across these papers?"
            )
          }
        />

        <PromptCard
          icon={BarChart3}
          title="Compare papers"
          description="Compare methods, datasets and findings."
          onClick={() =>
            onPrompt(
              "Compare the methodologies, datasets and findings of these papers."
            )
          }
        />

        <PromptCard
          icon={GitBranch}
          title="Analyze conflicting findings"
          description="Investigate disagreements between studies."
          onClick={() =>
            onPrompt(
              "Identify conflicting findings between these papers and explain the differences."
            )
          }
        />

        <PromptCard
          icon={Network}
          title="Explore relationships"
          description="Find important concepts and connections."
          onClick={() =>
            onPrompt(
              "What important relationships exist between the concepts and findings in these papers?"
            )
          }
        />

      </div>

      <div className="mt-8 rounded-2xl border border-white/[0.06] bg-slate-900/30 p-5">

        <div className="flex items-center gap-2">

          <FileText className="h-4 w-4 text-indigo-400" />

          <p className="text-xs font-medium text-slate-300">
            Selected sources
          </p>

        </div>

        <div className="mt-4 flex flex-wrap gap-2">

          {selectedPapers.map((paper) => (
            <div
              key={paper.id}
              className="flex max-w-full items-center gap-2 rounded-lg border border-white/[0.06] bg-slate-950/60 px-3 py-2"
            >

              <FileText className="h-3.5 w-3.5 shrink-0 text-indigo-400" />

              <span className="truncate text-[10px] text-slate-400">
                {paper.title}
              </span>

            </div>
          ))}

        </div>

      </div>

    </div>
  );
}

// ======================================================
// Prompt Card
// ======================================================

function PromptCard({
  icon: Icon,
  title,
  description,
  onClick,
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group rounded-2xl border border-white/[0.06] bg-slate-900/40 p-4 text-left transition hover:border-indigo-400/20 hover:bg-indigo-500/[0.04]"
    >

      <div className="flex items-start justify-between">

        <div className="flex h-9 w-9 items-center justify-center rounded-xl border border-indigo-400/10 bg-indigo-500/[0.06]">

          <Icon className="h-4 w-4 text-indigo-400 transition group-hover:text-indigo-300" />

        </div>

        <ChevronRight className="h-4 w-4 text-slate-700 transition group-hover:translate-x-0.5 group-hover:text-indigo-400" />

      </div>

      <p className="mt-4 text-xs font-medium text-slate-300">
        {title}
      </p>

      <p className="mt-1.5 text-[10px] leading-4 text-slate-600">
        {description}
      </p>

    </button>
  );
}

// ======================================================
// Studio Card
// ======================================================

function StudioCard({
  icon: Icon,
  title,
  description,
  onClick,
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group flex w-full items-center gap-3 rounded-xl border border-white/[0.05] bg-slate-900/40 p-3 text-left transition hover:border-indigo-400/15 hover:bg-indigo-500/[0.04]"
    >

      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-indigo-400/10 bg-indigo-500/[0.06]">

        <Icon className="h-4 w-4 text-indigo-400 transition group-hover:text-indigo-300" />

      </div>

      <div className="min-w-0 flex-1">

        <p className="text-[11px] font-medium text-slate-300">
          {title}
        </p>

        <p className="mt-0.5 truncate text-[9px] text-slate-600">
          {description}
        </p>

      </div>

      <ChevronRight className="h-3.5 w-3.5 shrink-0 text-slate-700 transition group-hover:text-indigo-400" />

    </button>
  );
}

// ======================================================
// Studio Preview
// ======================================================

function StudioPreview({
  type,
  selectedPapers,
  onClose,
}) {
  const content = {
    summary: {
      title: "Research Summary",
      description:
        "Generate a synthesis of the selected literature.",
      icon: BookOpen,
    },
    compare: {
      title: "Compare Papers",
      description:
        "Compare methodologies, datasets, metrics and findings.",
      icon: BarChart3,
    },
    gaps: {
      title: "Research Gaps",
      description:
        "Identify potential unexplored areas across the literature.",
      icon: Lightbulb,
    },
    conflicts: {
      title: "Conflicting Findings",
      description:
        "Investigate disagreements between selected studies.",
      icon: GitBranch,
    },
    graph: {
      title: "Knowledge Graph",
      description:
        "Explore relationships between concepts and entities.",
      icon: Network,
    },
    evidence: {
      title: "Evidence Map",
      description:
        "Trace research insights back to their source papers.",
      icon: FileSearch,
    },
  };

  const item = content[type];
  const Icon = item.icon;

  return (
    <div className="absolute inset-0 z-40 flex items-center justify-center bg-slate-950/70 p-6 backdrop-blur-sm">

      <div className="w-full max-w-xl rounded-2xl border border-white/[0.08] bg-slate-900 p-6 shadow-2xl">

        <div className="flex items-start justify-between">

          <div className="flex items-center gap-3">

            <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-indigo-400/15 bg-indigo-500/10">

              <Icon className="h-5 w-5 text-indigo-400" />

            </div>

            <div>

              <p className="text-sm font-semibold text-white">
                {item.title}
              </p>

              <p className="mt-1 text-[10px] text-slate-500">
                {item.description}
              </p>

            </div>

          </div>

          <button
            type="button"
            onClick={onClose}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-600 transition hover:bg-white/[0.04] hover:text-slate-300"
          >
            <X className="h-4 w-4" />
          </button>

        </div>

        <div className="mt-6 rounded-xl border border-dashed border-white/[0.07] bg-slate-950/40 p-8 text-center">

          <Sparkles className="mx-auto h-6 w-6 text-indigo-400" />

          <p className="mt-4 text-sm font-medium text-slate-300">
            Analysis workspace
          </p>

          <p className="mx-auto mt-2 max-w-sm text-xs leading-5 text-slate-600">
            This tool will analyze{" "}
            {selectedPapers.length} selected{" "}
            {selectedPapers.length === 1
              ? "source"
              : "sources"}{" "}
            using SciBrain's research analysis pipeline.
          </p>

        </div>

        <div className="mt-5 flex justify-end">

          <button
            type="button"
            onClick={onClose}
            className="rounded-xl border border-white/[0.07] px-4 py-2.5 text-xs font-medium text-slate-400 transition hover:bg-white/[0.03] hover:text-slate-200"
          >
            Close
          </button>

        </div>

      </div>

    </div>
  );
}

export default ResearchNotebook;