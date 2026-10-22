import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import AppLayout from "../components/AppLayout";

import {
  ArrowLeft,
  BookOpen,
  Check,
  ChevronRight,
  FileText,
  Loader2,
  MessageSquare,
  Network,
  Plus,
  RefreshCw,
  Lightbulb,
  Search,
  Send,
  Trash2,
  X,
} from "lucide-react";

const API_URL = "http://127.0.0.1:8000";

function ResearchNotebookWorkspace() {
  const navigate = useNavigate();
  const { notebookId } = useParams();

  const [notebook, setNotebook] = useState(null);
  const [papers, setPapers] = useState([]);
  const [chats, setChats] = useState([]);

  const [activeChatId, setActiveChatId] = useState(null);
  const [messages, setMessages] = useState([]);

  const [loadingNotebook, setLoadingNotebook] = useState(true);
  const [loadingPapers, setLoadingPapers] = useState(true);
  const [loadingChats, setLoadingChats] = useState(true);
  const [loadingMessages, setLoadingMessages] = useState(false);

  const [sending, setSending] = useState(false);
  const [savingSources, setSavingSources] = useState(false);

  const [message, setMessage] = useState("");

  const [error, setError] = useState("");
  const [chatError, setChatError] = useState("");

  const [showSources, setShowSources] = useState(false);
  const [sourceSearch, setSourceSearch] = useState("");

  // ============================================================
  // AUTH
  // ============================================================

  const getAuthHeaders = () => {
    const token = localStorage.getItem("scibrain_token");

    return token
      ? {
          Authorization: `Bearer ${token}`,
        }
      : {};
  };

  // ============================================================
  // LOAD NOTEBOOK
  // ============================================================

  const loadNotebook = async () => {
    if (!notebookId) return;

    try {
      setLoadingNotebook(true);
      setError("");

      const response = await fetch(
        `${API_URL}/api/notebook/${notebookId}`,
        {
          headers: {
            ...getAuthHeaders(),
          },
        }
      );

      if (response.status === 401) {
        throw new Error(
          "Your session has expired. Please log in again."
        );
      }

      if (response.status === 404) {
        throw new Error("Notebook not found.");
      }

      if (!response.ok) {
        throw new Error(
          "Unable to load this research notebook."
        );
      }

      const data = await response.json();

      setNotebook(data?.notebook || null);
    } catch (error) {
      console.error("Notebook loading error:", error);

      setError(
        error.message ||
          "Unable to load this research notebook."
      );
    } finally {
      setLoadingNotebook(false);
    }
  };

  // ============================================================
  // LOAD PAPERS
  // ============================================================

  const loadPapers = async () => {
    try {
      setLoadingPapers(true);

      const response = await fetch(
        `${API_URL}/api/papers/`,
        {
          headers: {
            ...getAuthHeaders(),
          },
        }
      );

      if (!response.ok) {
        throw new Error(
          "Unable to load your research papers."
        );
      }

      const data = await response.json();

      /*
       * Existing Papers API may return either:
       *   [...]
       * or
       *   { papers: [...] }
       */
      const paperList = Array.isArray(data)
        ? data
        : Array.isArray(data?.papers)
        ? data.papers
        : [];

      setPapers(paperList);
    } catch (error) {
      console.error("Paper loading error:", error);

      setError(
        error.message ||
          "Unable to load your research papers."
      );
    } finally {
      setLoadingPapers(false);
    }
  };

  // ============================================================
  // LOAD CHATS
  // ============================================================

  const loadChats = async () => {
    if (!notebookId) return;

    try {
      setLoadingChats(true);

      const response = await fetch(
        `${API_URL}/api/notebook/${notebookId}/chats`,
        {
          headers: {
            ...getAuthHeaders(),
          },
        }
      );

      if (!response.ok) {
        throw new Error(
          "Unable to load notebook conversations."
        );
      }

      const data = await response.json();

      setChats(
        Array.isArray(data?.chats)
          ? data.chats
          : []
      );
    } catch (error) {
      console.error("Chat loading error:", error);

      setChatError(
        error.message ||
          "Unable to load notebook conversations."
      );
    } finally {
      setLoadingChats(false);
    }
  };

  // ============================================================
  // INITIAL LOAD
  // ============================================================

  useEffect(() => {
    loadNotebook();
    loadPapers();
    loadChats();
  }, [notebookId]);

  // ============================================================
  // CURRENT SOURCE IDS
  // ============================================================

  const selectedResourceIds = useMemo(() => {
    return Array.isArray(notebook?.resource_ids)
      ? notebook.resource_ids.map(String)
      : [];
  }, [notebook]);

  // ============================================================
  // SELECTED PAPERS
  // ============================================================

  const selectedPapers = useMemo(() => {
    const selected = new Set(
      selectedResourceIds
    );

    return papers.filter((paper) =>
      selected.has(
        String(
          paper.id ??
            paper.paper_id ??
            ""
        )
      )
    );
  }, [papers, selectedResourceIds]);

  // ============================================================
  // FILTER AVAILABLE PAPERS
  // ============================================================

  const filteredPapers = useMemo(() => {
    const query = sourceSearch
      .trim()
      .toLowerCase();

    if (!query) {
      return papers;
    }

    return papers.filter((paper) => {
      const title = String(
        paper.title || ""
      ).toLowerCase();

      const filename = String(
        paper.filename || ""
      ).toLowerCase();

      return (
        title.includes(query) ||
        filename.includes(query)
      );
    });
  }, [papers, sourceSearch]);

  // ============================================================
  // PAPER ID
  // ============================================================

  const getPaperId = (paper) => {
    return String(
      paper?.id ??
        paper?.paper_id ??
        ""
    );
  };

  // ============================================================
  // TOGGLE SOURCE
  // ============================================================

  const toggleSource = async (paper) => {
    if (!notebook || savingSources) {
      return;
    }

    const paperId = getPaperId(paper);

    if (!paperId) {
      return;
    }

    const currentIds = [...selectedResourceIds];

    const exists = currentIds.includes(
      paperId
    );

    const nextIds = exists
      ? currentIds.filter(
          (id) => id !== paperId
        )
      : [...currentIds, paperId];

    await saveNotebookSources(nextIds);
  };

  // ============================================================
  // SAVE NOTEBOOK SOURCES
  // ============================================================

  const saveNotebookSources = async (
    resourceIds
  ) => {
    if (!notebookId) return;

    try {
      setSavingSources(true);
      setError("");

      const response = await fetch(
        `${API_URL}/api/notebook/${notebookId}`,
        {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
            ...getAuthHeaders(),
          },
          body: JSON.stringify({
            resource_ids: resourceIds,
          }),
        }
      );

      let data = null;

      try {
        data = await response.json();
      } catch {
        data = null;
      }

      if (!response.ok) {
        throw new Error(
          data?.detail ||
            "Unable to update notebook sources."
        );
      }

      setNotebook(
        data?.notebook || notebook
      );
    } catch (error) {
      console.error(
        "Notebook source update error:",
        error
      );

      setError(
        error.message ||
          "Unable to update notebook sources."
      );
    } finally {
      setSavingSources(false);
    }
  };

  // ============================================================
  // LOAD CHAT
  // ============================================================

  const openChat = async (chatId) => {
    if (!chatId || loadingMessages) {
      return;
    }

    try {
      setLoadingMessages(true);
      setChatError("");

      const response = await fetch(
        `${API_URL}/api/notebook/${notebookId}/chats/${chatId}`,
        {
          headers: {
            ...getAuthHeaders(),
          },
        }
      );

      let data = null;

      try {
        data = await response.json();
      } catch {
        data = null;
      }

      if (!response.ok) {
        throw new Error(
          data?.detail ||
            "Unable to load this conversation."
        );
      }

      setActiveChatId(chatId);

      setMessages(
        Array.isArray(data?.messages)
          ? data.messages
          : []
      );
    } catch (error) {
      console.error(
        "Chat loading error:",
        error
      );

      setChatError(
        error.message ||
          "Unable to load this conversation."
      );
    } finally {
      setLoadingMessages(false);
    }
  };

  // ============================================================
  // NEW CHAT
  // ============================================================

  const startNewChat = () => {
    setActiveChatId(null);
    setMessages([]);
    setMessage("");
    setChatError("");
  };

  // ============================================================
  // SEND MESSAGE
  // ============================================================

  const sendMessage = async (event) => {
    event?.preventDefault();

    const text = message.trim();

    if (!text || sending) {
      return;
    }

    if (!selectedResourceIds.length) {
      setChatError(
        "Add at least one research paper to this notebook before starting a chat."
      );
      return;
    }

    const optimisticMessage = {
      role: "user",
      content: text,
      citations: [],
      created_at: new Date().toISOString(),
    };

    setMessages((current) => [
      ...current,
      optimisticMessage,
    ]);

    setMessage("");
    setSending(true);
    setChatError("");

    try {
      const response = await fetch(
        `${API_URL}/api/notebook/${notebookId}/chat`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...getAuthHeaders(),
          },
          body: JSON.stringify({
            message: text,
            chat_id: activeChatId,
          }),
        }
      );

      let data = null;

      try {
        data = await response.json();
      } catch {
        data = null;
      }

      if (!response.ok) {
        throw new Error(
          data?.detail ||
            "Unable to generate a research answer."
        );
      }

      const assistantMessage = {
        role: "assistant",
        content: data?.answer || "",
        citations: Array.isArray(
          data?.citations
        )
          ? data.citations
          : [],
        created_at:
          new Date().toISOString(),
      };

      setMessages((current) => [
        ...current,
        assistantMessage,
      ]);

      /*
       * The backend generates the chat ID for the
       * first message. Subsequent messages reuse it.
       */
      if (data?.chat_id) {
        setActiveChatId(data.chat_id);
      }

      /*
       * Refresh chat list so the new conversation
       * appears immediately.
       */
      await loadChats();
    } catch (error) {
      console.error(
        "Notebook chat error:",
        error
      );

      /*
       * Remove the optimistic user message if
       * Gemini/retrieval failed.
       */
      setMessages((current) =>
        current.filter(
          (item) =>
            item !== optimisticMessage
        )
      );

      setChatError(
        error.message ||
          "Unable to generate a research answer."
      );
    } finally {
      setSending(false);
    }
  };

  // ============================================================
  // DELETE CHAT
  // ============================================================

  const deleteChat = async (
    chatId,
    event
  ) => {
    event?.stopPropagation();

    if (!chatId) return;

    const chat = chats.find(
      (item) =>
        item.chat_id === chatId
    );

    const confirmed = window.confirm(
      `Delete "${
        chat?.title ||
        "this research chat"
      }"?`
    );

    if (!confirmed) {
      return;
    }

    try {
      setChatError("");

      const response = await fetch(
        `${API_URL}/api/notebook/${notebookId}/chats/${chatId}`,
        {
          method: "DELETE",
          headers: {
            ...getAuthHeaders(),
          },
        }
      );

      let data = null;

      try {
        data = await response.json();
      } catch {
        data = null;
      }

      if (!response.ok) {
        throw new Error(
          data?.detail ||
            "Unable to delete this chat."
        );
      }

      setChats((current) =>
        current.filter(
          (chatItem) =>
            chatItem.chat_id !== chatId
        )
      );

      if (activeChatId === chatId) {
        startNewChat();
      }
    } catch (error) {
      console.error(
        "Delete chat error:",
        error
      );

      setChatError(
        error.message ||
          "Unable to delete this chat."
      );
    }
  };

  // ============================================================
  // KEYBOARD SEND
  // ============================================================

  const handleMessageKeyDown = (event) => {
    if (
      event.key === "Enter" &&
      !event.shiftKey
    ) {
      event.preventDefault();
      sendMessage(event);
    }
  };

  // ============================================================
  // FORMAT DATE
  // ============================================================

  const formatDate = (value) => {
    if (!value) {
      return "";
    }

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
      return "";
    }

    return date.toLocaleDateString(
      undefined,
      {
        month: "short",
        day: "numeric",
        year: "numeric",
      }
    );
  };

  // ============================================================
  // FORMAT TIME
  // ============================================================

  const formatTime = (value) => {
    if (!value) {
      return "";
    }

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
      return "";
    }

    return date.toLocaleTimeString(
      undefined,
      {
        hour: "numeric",
        minute: "2-digit",
      }
    );
  };

  // ============================================================
  // GET CITATION TITLE
  // ============================================================

  const getCitationTitle = (
    citation
  ) => {
    if (
      citation?.title
    ) {
      return citation.title;
    }

    const paper = papers.find(
      (item) =>
        String(
          item.id ??
            item.paper_id ??
            ""
        ) ===
        String(
          citation?.paper_id ??
            ""
        )
    );

    return (
      paper?.title ||
      "Research paper"
    );
  };

  // ============================================================
  // LOADING / ERROR
  // ============================================================

  if (
    loadingNotebook ||
    !notebook
  ) {
    return (
      <AppLayout>
        <div className="flex min-h-[calc(100vh-8rem)] items-center justify-center">
          {error ? (
            <div className="max-w-md rounded-2xl border border-red-400/15 bg-red-400/[0.04] px-6 py-5 text-center">
              <p className="text-sm text-red-300">
                {error}
              </p>

              <button
                type="button"
                onClick={() =>
                  navigate("/notebook")
                }
                className="mt-4 inline-flex items-center gap-2 rounded-lg border border-white/[0.08] px-3 py-2 text-xs text-slate-400 transition hover:bg-white/[0.05] hover:text-slate-200"
              >
                <ArrowLeft className="h-3.5 w-3.5" />
                Back to Notebooks
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading research notebook...
            </div>
          )}
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <div className="flex h-[calc(100vh-7rem)] min-h-[650px] flex-col gap-4">

        {/* ================================================== */}
        {/* NOTEBOOK HEADER */}
        {/* ================================================== */}

        <div className="flex shrink-0 items-center justify-between gap-4">
          <div className="flex min-w-0 items-center gap-3">
            <button
              type="button"
              onClick={() =>
                navigate("/notebook")
              }
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-white/[0.07] bg-slate-950/50 text-slate-500 transition hover:border-white/[0.12] hover:bg-white/[0.04] hover:text-slate-200"
              title="Back to notebooks"
            >
              <ArrowLeft className="h-4 w-4" />
            </button>

            <div className="min-w-0">
              <div className="flex items-center gap-2 text-[10px] font-medium uppercase tracking-[0.18em] text-indigo-400">
                <BookOpen className="h-3 w-3" />
                Research Notebook
              </div>

              <h1 className="mt-1 truncate text-xl font-semibold tracking-tight text-slate-100">
                {notebook.title}
              </h1>

              {notebook.description && (
                <p className="mt-0.5 max-w-3xl truncate text-xs text-slate-500">
                  {notebook.description}
                </p>
              )}
            </div>
          </div>

          <div className="hidden shrink-0 items-center gap-3 sm:flex">
            <div className="text-xs text-slate-600">
              {selectedResourceIds.length}{" "}
              {selectedResourceIds.length ===
              1
                ? "source"
                : "sources"}
            </div>

            <button
              type="button"
              onClick={() => {
                loadNotebook();
                loadChats();
              }}
              className="flex h-9 w-9 items-center justify-center rounded-xl border border-white/[0.07] bg-slate-950/50 text-slate-500 transition hover:bg-white/[0.04] hover:text-slate-200"
              title="Refresh notebook"
            >
              <RefreshCw className="h-3.5 w-3.5" />
            </button>
            <button
              type="button"
              onClick={() =>
                navigate(
                  `/notebook/${encodeURIComponent(notebookId)}/knowledge-graph`
                )
              }
              className="flex shrink-0 items-center justify-center gap-2 rounded-xl border border-indigo-400/20 bg-indigo-500/[0.08] px-4 py-2.5 text-xs font-medium text-indigo-300 transition hover:border-indigo-400/30 hover:bg-indigo-500/[0.14]"
            >
              <Network className="h-4 w-4" />
              Knowledge Graph
            </button>
            <button
              type="button"
              onClick={() => {
                if (!notebook?.notebook_id) {
                  setError("The research notebook has not finished loading.");
                  return;
                }

                if (!selectedResourceIds.length) {
                  setError("Add at least one research paper to this notebook first.");
                  return;
                }

                sessionStorage.setItem(
                  "scibrain_active_notebook_id",
                  String(notebook.notebook_id)
                );

                navigate("/research-gaps", {
                  state: {
                    notebookId: String(notebook.notebook_id),
                  },
                });
              }}
              disabled={loadingNotebook || !selectedResourceIds.length}
              className="inline-flex items-center gap-2 rounded-xl border border-indigo-400/20 bg-indigo-500/10 px-3 py-2 text-xs font-medium text-indigo-300 transition hover:bg-indigo-500/15 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <Lightbulb className="h-3.5 w-3.5" />
              Research Gaps
              <ChevronRight className="h-3 w-3" />
            </button>
          </div>
        </div>

        {/* ================================================== */}
        {/* GLOBAL ERROR */}
        {/* ================================================== */}

        {error && (
          <div className="flex shrink-0 items-center justify-between rounded-xl border border-red-400/15 bg-red-400/[0.04] px-4 py-2.5 text-xs text-red-300">
            <span>{error}</span>

            <button
              type="button"
              onClick={() => setError("")}
              className="text-red-200 hover:text-white"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        )}

        {/* ================================================== */}
        {/* MAIN WORKSPACE */}
        {/* ================================================== */}

        <div className="grid min-h-0 flex-1 gap-4 lg:grid-cols-[280px_minmax(0,1fr)_240px]">

          {/* ================================================== */}
          {/* SOURCES */}
          {/* ================================================== */}

          <section className="flex min-h-0 flex-col overflow-hidden rounded-2xl border border-white/[0.07] bg-slate-950/45">

            <div className="flex shrink-0 items-center justify-between border-b border-white/[0.06] px-4 py-3">
              <div>
                <div className="flex items-center gap-2 text-sm font-medium text-slate-200">
                  <FileText className="h-4 w-4 text-indigo-400" />
                  Sources
                </div>

                <p className="mt-0.5 text-[11px] text-slate-600">
                  Papers available to this notebook
                </p>
              </div>

              <button
                type="button"
                onClick={() =>
                  setShowSources(true)
                }
                className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 transition hover:bg-white/[0.05] hover:text-slate-200"
                title="Add sources"
              >
                <Plus className="h-4 w-4" />
              </button>
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto p-3">
              {loadingPapers ? (
                <div className="flex items-center justify-center py-10 text-xs text-slate-600">
                  <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
                  Loading papers...
                </div>
              ) : selectedPapers.length ===
                0 ? (
                <div className="flex flex-col items-center justify-center px-4 py-12 text-center">
                  <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-xl border border-white/[0.07] bg-slate-900/60">
                    <FileText className="h-5 w-5 text-slate-600" />
                  </div>

                  <p className="text-xs font-medium text-slate-400">
                    No sources yet
                  </p>

                  <p className="mt-1 text-[11px] leading-5 text-slate-600">
                    Add papers to give this notebook
                    its research context.
                  </p>

                  <button
                    type="button"
                    onClick={() =>
                      setShowSources(true)
                    }
                    className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-indigo-600/90 px-3 py-2 text-[11px] font-medium text-white transition hover:bg-indigo-500"
                  >
                    <Plus className="h-3 w-3" />
                    Add Sources
                  </button>
                </div>
              ) : (
                <div className="space-y-2">
                  {selectedPapers.map(
                    (paper) => {
                      const paperId =
                        getPaperId(
                          paper
                        );

                      return (
                        <div
                          key={paperId}
                          className="group rounded-xl border border-white/[0.06] bg-slate-900/50 p-3 transition hover:border-indigo-400/15"
                        >
                          <div className="flex items-start gap-2.5">
                            <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-indigo-500/10 text-indigo-400">
                              <FileText className="h-3.5 w-3.5" />
                            </div>

                            <div className="min-w-0 flex-1">
                              <p className="line-clamp-3 text-xs font-medium leading-5 text-slate-300">
                                {paper.title ||
                                  paper.filename ||
                                  "Untitled paper"}
                              </p>

                              {paper.filename &&
                                paper.title && (
                                  <p className="mt-1 truncate text-[10px] text-slate-600">
                                    {
                                      paper.filename
                                    }
                                  </p>
                                )}
                            </div>

                            <button
                              type="button"
                              onClick={() =>
                                toggleSource(
                                  paper
                                )
                              }
                              disabled={
                                savingSources
                              }
                              className="shrink-0 rounded-md p-1.5 text-slate-700 opacity-0 transition hover:bg-red-400/10 hover:text-red-300 group-hover:opacity-100 disabled:opacity-40"
                              title="Remove source"
                            >
                              <X className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        </div>
                      );
                    }
                  )}
                </div>
              )}
            </div>

            <div className="shrink-0 border-t border-white/[0.06] p-3">
              <button
                type="button"
                onClick={() =>
                  setShowSources(true)
                }
                disabled={savingSources}
                className="flex w-full items-center justify-center gap-2 rounded-xl border border-white/[0.07] bg-slate-900/60 px-3 py-2.5 text-xs font-medium text-slate-400 transition hover:border-indigo-400/20 hover:bg-white/[0.04] hover:text-slate-200 disabled:opacity-40"
              >
                {savingSources ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Plus className="h-3.5 w-3.5" />
                )}

                Add sources
              </button>
            </div>
          </section>

          {/* ================================================== */}
          {/* CHAT */}
          {/* ================================================== */}

          <section className="flex min-h-0 flex-col overflow-hidden rounded-2xl border border-white/[0.07] bg-slate-950/45">

            <div className="flex shrink-0 items-center justify-between border-b border-white/[0.06] px-5 py-3">
              <div>
                <div className="flex items-center gap-2 text-sm font-medium text-slate-200">
                  <MessageSquare className="h-4 w-4 text-cyan-400" />

                  {activeChatId
                    ? chats.find(
                        (chat) =>
                          chat.chat_id ===
                          activeChatId
                      )?.title ||
                      "Research Chat"
                    : "New Research Chat"}
                </div>

                <p className="mt-0.5 text-[11px] text-slate-600">
                  Answers are grounded in this notebook's sources
                </p>
              </div>

              <button
                type="button"
                onClick={startNewChat}
                className="inline-flex items-center gap-1.5 rounded-lg border border-white/[0.07] bg-slate-900/60 px-3 py-2 text-[11px] font-medium text-slate-400 transition hover:bg-white/[0.05] hover:text-slate-200"
              >
                <Plus className="h-3 w-3" />
                New Chat
              </button>
            </div>

            {/* Messages */}

            <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5">
              {loadingMessages ? (
                <div className="flex h-full items-center justify-center text-xs text-slate-600">
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Loading conversation...
                </div>
              ) : messages.length === 0 ? (
                <EmptyChatState
                  hasSources={
                    selectedResourceIds.length >
                    0
                  }
                  onAddSources={() =>
                    setShowSources(true)
                  }
                />
              ) : (
                <div className="mx-auto max-w-3xl space-y-6">
                  {messages.map(
                    (item, index) => (
                      <ChatMessage
                        key={`${item.created_at || "message"}-${index}`}
                        message={item}
                        formatTime={
                          formatTime
                        }
                        getCitationTitle={
                          getCitationTitle
                        }
                      />
                    )
                  )}

                  {sending && (
                    <div className="flex gap-3">
                      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-cyan-400/10 bg-cyan-400/[0.05] text-cyan-400">
                        <BookOpen className="h-3.5 w-3.5" />
                      </div>

                      <div className="rounded-2xl border border-white/[0.06] bg-slate-900/60 px-4 py-3">
                        <div className="flex items-center gap-2 text-xs text-slate-500">
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          Researching your notebook...
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Chat error */}

            {chatError && (
              <div className="mx-5 mb-3 shrink-0 rounded-xl border border-red-400/15 bg-red-400/[0.04] px-3 py-2.5 text-xs text-red-300">
                {chatError}
              </div>
            )}

            {/* Composer */}

            <div className="shrink-0 border-t border-white/[0.06] p-4">
              <form
                onSubmit={sendMessage}
                className="mx-auto max-w-3xl"
              >
                <div className="rounded-2xl border border-white/[0.08] bg-slate-900/70 transition focus-within:border-indigo-400/25">
                  <textarea
                    value={message}
                    onChange={(event) =>
                      setMessage(
                        event.target.value
                      )
                    }
                    onKeyDown={
                      handleMessageKeyDown
                    }
                    disabled={sending}
                    rows={3}
                    placeholder={
                      selectedResourceIds.length
                        ? "Ask anything about the research in this notebook..."
                        : "Add sources before starting a conversation..."
                    }
                    className="w-full resize-none bg-transparent px-4 py-3 text-sm leading-6 text-slate-200 outline-none placeholder:text-slate-600 disabled:opacity-50"
                  />

                  <div className="flex items-center justify-between px-3 pb-3">
                    <span className="text-[10px] text-slate-700">
                      Enter to send · Shift + Enter for a new line
                    </span>

                    <button
                      type="submit"
                      disabled={
                        sending ||
                        !message.trim() ||
                        !selectedResourceIds.length
                      }
                      className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-white transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-30"
                      title="Send message"
                    >
                      {sending ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Send className="h-3.5 w-3.5" />
                      )}
                    </button>
                  </div>
                </div>
              </form>
            </div>
          </section>

          {/* ================================================== */}
          {/* CHAT HISTORY */}
          {/* ================================================== */}

          <section className="flex min-h-0 flex-col overflow-hidden rounded-2xl border border-white/[0.07] bg-slate-950/45">

            <div className="flex shrink-0 items-center justify-between border-b border-white/[0.06] px-4 py-3">
              <div>
                <div className="flex items-center gap-2 text-sm font-medium text-slate-200">
                  <MessageSquare className="h-4 w-4 text-cyan-400" />
                  Chats
                </div>

                <p className="mt-0.5 text-[11px] text-slate-600">
                  Conversations in this notebook
                </p>
              </div>

              <span className="text-[10px] text-slate-700">
                {chats.length}
              </span>
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto p-2">
              {loadingChats ? (
                <div className="flex items-center justify-center py-10 text-xs text-slate-600">
                  <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
                  Loading chats...
                </div>
              ) : chats.length === 0 ? (
                <div className="px-4 py-10 text-center">
                  <MessageSquare className="mx-auto h-5 w-5 text-slate-700" />

                  <p className="mt-3 text-xs text-slate-600">
                    No conversations yet.
                  </p>
                </div>
              ) : (
                <div className="space-y-1">
                  {chats.map((chat) => (
                    <div
                        key={chat.chat_id}
                        className={`group flex w-full items-start gap-2 rounded-xl px-3 py-3 text-left transition ${
                            activeChatId === chat.chat_id
                            ? "bg-indigo-500/10 text-slate-200"
                            : "text-slate-500 hover:bg-white/[0.035] hover:text-slate-300"
                        }`}
                        >
                        <button
                            type="button"
                            onClick={() =>
                            openChat(chat.chat_id)
                            }
                            className="flex min-w-0 flex-1 items-start gap-2 text-left"
                        >
                            <MessageSquare
                            className={`mt-0.5 h-3.5 w-3.5 shrink-0 ${
                                activeChatId === chat.chat_id
                                ? "text-indigo-400"
                                : "text-slate-700"
                            }`}
                            />

                            <div className="min-w-0 flex-1">
                            <p className="line-clamp-2 text-xs font-medium leading-5">
                                {chat.title || "Research Chat"}
                            </p>

                            <p className="mt-1 text-[10px] text-slate-700">
                                {formatDate(chat.updated_at)}
                            </p>
                            </div>
                        </button>

                        <button
                            type="button"
                            onClick={(event) =>
                            deleteChat(
                                chat.chat_id,
                                event
                            )
                            }
                            className="mt-0.5 shrink-0 rounded-md p-1 text-slate-800 opacity-0 transition hover:bg-red-400/10 hover:text-red-300 group-hover:opacity-100"
                            title="Delete chat"
                        >
                            <Trash2 className="h-3 w-3" />
                        </button>
                        </div>
                  ))}
                </div>
              )}
            </div>

            <div className="shrink-0 border-t border-white/[0.06] p-3">
              <button
                type="button"
                onClick={startNewChat}
                className="flex w-full items-center justify-center gap-2 rounded-xl border border-white/[0.07] bg-slate-900/60 px-3 py-2.5 text-xs font-medium text-slate-400 transition hover:border-cyan-400/15 hover:bg-white/[0.04] hover:text-slate-200"
              >
                <Plus className="h-3.5 w-3.5" />
                New Chat
              </button>
            </div>
          </section>
        </div>
      </div>

      {/* ==================================================== */}
      {/* SOURCE SELECTOR */}
      {/* ==================================================== */}

      {showSources && (
        <SourceSelector
          papers={filteredPapers}
          selectedResourceIds={
            selectedResourceIds
          }
          sourceSearch={sourceSearch}
          setSourceSearch={
            setSourceSearch
          }
          loading={loadingPapers}
          saving={savingSources}
          onToggle={toggleSource}
          onClose={() => {
            setShowSources(false);
            setSourceSearch("");
          }}
          getPaperId={getPaperId}
        />
      )}
    </AppLayout>
  );
}


// ============================================================
// EMPTY CHAT STATE
// ============================================================

function EmptyChatState({
  hasSources,
  onAddSources,
}) {
  return (
    <div className="flex h-full min-h-[300px] flex-col items-center justify-center px-6 text-center">
      <div className="mb-5 flex h-14 w-14 items-center justify-center rounded-2xl border border-cyan-400/10 bg-cyan-400/[0.04]">
        <BookOpen className="h-6 w-6 text-cyan-400/70" />
      </div>

      <h2 className="text-lg font-medium text-slate-200">
        {hasSources
          ? "Ask your research notebook"
          : "Add research sources first"}
      </h2>

      <p className="mt-2 max-w-md text-sm leading-6 text-slate-600">
        {hasSources
          ? "Ask questions, compare papers, explore methods, or investigate limitations using the sources attached to this notebook."
          : "This notebook has no papers yet. Add research sources to give the AI assistant context."}
      </p>

      {!hasSources && (
        <button
          type="button"
          onClick={onAddSources}
          className="mt-5 inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-medium text-white transition hover:bg-indigo-500"
        >
          <Plus className="h-3.5 w-3.5" />
          Add Sources
        </button>
      )}
    </div>
  );
}


// ============================================================
// CHAT MESSAGE
// ============================================================

function ChatMessage({
  message,
  formatTime,
  getCitationTitle,
}) {
  const isUser =
    message.role === "user";

  // Group repeated evidence citations by paper.
  // Backend citations remain unchanged; this only
  // prevents the same paper from being displayed
  // repeatedly in the UI.
  const groupedCitations = [];

  if (
    !isUser &&
    Array.isArray(message.citations)
  ) {
    const seenPapers = new Set();

    message.citations.forEach((citation) => {
      const paperId = String(
        citation?.paper_id ?? ""
      );

      const title = getCitationTitle(
        citation
      );

      const key = paperId || title;

      if (!seenPapers.has(key)) {
        seenPapers.add(key);
        groupedCitations.push(citation);
      }
    });
  }

  return (
    <div
      className={`flex gap-3 ${
        isUser
          ? "justify-end"
          : "justify-start"
      }`}
    >
      {!isUser && (
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-cyan-400/10 bg-cyan-400/[0.05] text-cyan-400">
          <BookOpen className="h-3.5 w-3.5" />
        </div>
      )}

      <div
        className={`max-w-[85%] ${
          isUser
            ? "items-end"
            : "items-start"
        }`}
      >
        <div
          className={`rounded-2xl px-4 py-3 text-sm leading-7 ${
            isUser
              ? "bg-indigo-600/90 text-white"
              : "border border-white/[0.06] bg-slate-900/60 text-slate-300"
          }`}
        >
          <div className="whitespace-pre-wrap">
            {message.content}
          </div>
        </div>

        {!isUser &&
          groupedCitations.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {groupedCitations.map(
                (citation, index) => (
                  <div
                    key={`${citation.paper_id || "citation"}-${index}`}
                    className="max-w-[280px] rounded-lg border border-white/[0.06] bg-slate-950/60 px-2.5 py-1.5 text-[10px] text-slate-500"
                    title={getCitationTitle(
                      citation
                    )}
                  >
                    <span className="text-indigo-400">
                      Evidence
                    </span>{" "}
                    ·{" "}
                    {getCitationTitle(
                      citation
                    )}
                  </div>
                )
              )}
            </div>
          )}

        {message.created_at && (
          <div
            className={`mt-1 text-[10px] text-slate-700 ${
              isUser
                ? "text-right"
                : "text-left"
            }`}
          >
            {formatTime(
              message.created_at
            )}
          </div>
        )}
      </div>
    </div>
  );
}
// ============================================================
// SOURCE SELECTOR
// ============================================================

function SourceSelector({
  papers,
  selectedResourceIds,
  sourceSearch,
  setSourceSearch,
  loading,
  saving,
  onToggle,
  onClose,
  getPaperId,
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/65 px-4 backdrop-blur-sm">
      <div className="flex max-h-[80vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-white/[0.08] bg-slate-950 shadow-2xl shadow-black/50">

        {/* Header */}

        <div className="flex shrink-0 items-center justify-between border-b border-white/[0.06] px-5 py-4">
          <div>
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-100">
              <FileText className="h-4 w-4 text-indigo-400" />
              Add Research Sources
            </div>

            <p className="mt-1 text-xs text-slate-600">
              Select the papers this notebook should use for research conversations.
            </p>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-2 text-slate-500 transition hover:bg-white/[0.05] hover:text-slate-200"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Search */}

        <div className="shrink-0 border-b border-white/[0.06] p-4">
          <div className="flex items-center gap-2 rounded-xl border border-white/[0.07] bg-slate-900/60 px-3 py-2.5">
            <Search className="h-4 w-4 text-slate-600" />

            <input
              type="text"
              value={sourceSearch}
              onChange={(event) =>
                setSourceSearch(
                  event.target.value
                )
              }
              placeholder="Search your papers..."
              className="w-full bg-transparent text-sm text-slate-200 outline-none placeholder:text-slate-600"
            />
          </div>
        </div>

        {/* Papers */}

        <div className="min-h-0 flex-1 overflow-y-auto p-4">
          {loading ? (
            <div className="flex items-center justify-center py-12 text-xs text-slate-600">
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Loading papers...
            </div>
          ) : papers.length === 0 ? (
            <div className="py-12 text-center">
              <FileText className="mx-auto h-6 w-6 text-slate-700" />

              <p className="mt-3 text-xs text-slate-500">
                No papers match your search.
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {papers.map((paper) => {
                const paperId =
                  getPaperId(paper);

                const selected =
                  selectedResourceIds.includes(
                    paperId
                  );

                return (
                  <button
                    key={paperId}
                    type="button"
                    onClick={() =>
                      onToggle(paper)
                    }
                    disabled={saving}
                    className={`flex w-full items-center gap-3 rounded-xl border p-3 text-left transition ${
                      selected
                        ? "border-indigo-400/20 bg-indigo-500/[0.07]"
                        : "border-white/[0.06] bg-slate-900/40 hover:border-white/[0.1] hover:bg-white/[0.025]"
                    } disabled:opacity-50`}
                  >
                    <div
                      className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border ${
                        selected
                          ? "border-indigo-400/20 bg-indigo-500/15 text-indigo-400"
                          : "border-white/[0.07] bg-slate-900 text-slate-600"
                      }`}
                    >
                      {selected ? (
                        <Check className="h-3.5 w-3.5" />
                      ) : (
                        <FileText className="h-3.5 w-3.5" />
                      )}
                    </div>

                    <div className="min-w-0 flex-1">
                      <p className="line-clamp-2 text-xs font-medium leading-5 text-slate-300">
                        {paper.title ||
                          paper.filename ||
                          "Untitled paper"}
                      </p>

                      {paper.filename &&
                        paper.title && (
                          <p className="mt-1 truncate text-[10px] text-slate-600">
                            {paper.filename}
                          </p>
                        )}
                    </div>

                    <ChevronRight
                      className={`h-3.5 w-3.5 shrink-0 ${
                        selected
                          ? "text-indigo-400"
                          : "text-slate-700"
                      }`}
                    />
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer */}

        <div className="flex shrink-0 items-center justify-between border-t border-white/[0.06] px-5 py-3">
          <span className="text-[11px] text-slate-600">
            {selectedResourceIds.length}{" "}
            {selectedResourceIds.length ===
            1
              ? "source"
              : "sources"}{" "}
            selected
          </span>

          <button
            type="button"
            onClick={onClose}
            className="rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-medium text-white transition hover:bg-indigo-500"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}

export default ResearchNotebookWorkspace;