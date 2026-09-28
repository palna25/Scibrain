import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import AppLayout from "../components/AppLayout";
import { useResearchContext } from "../context/ResearchContext";

import {
  ArrowRight,
  BookOpen,
  Bot,
  ChevronDown,
  FileText,
  GitBranch,
  Loader2,
  MessageSquare,
  Network,
  Plus,
  Search,
  Send,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";

const API_URL = "http://127.0.0.1:8000";

function ResearchNotebook() {
  const navigate = useNavigate();

  const {
    selectedResourceIds,
    setSelectedResourceIds,
    toggleResource,
    notebookId,
    setNotebookId,
    chatId,
    setChatId,
  } = useResearchContext();

  const [papers, setPapers] = useState([]);
  const [loadingPapers, setLoadingPapers] = useState(true);
  const [paperError, setPaperError] = useState("");

  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState([]);

  const [chatLoading, setChatLoading] = useState(false);
  const [chatError, setChatError] = useState("");

  const [resourceSearch, setResourceSearch] = useState("");
  const [showResourcePicker, setShowResourcePicker] = useState(false);

  // ---------------------------------------------------------
  // CHAT HISTORY
  // ---------------------------------------------------------

  const [chatHistory, setChatHistory] = useState([]);
  const [loadingChatHistory, setLoadingChatHistory] = useState(true);
  const [loadingChat, setLoadingChat] = useState(false);
  const [historyError, setHistoryError] = useState("");

  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  // ---------------------------------------------------------
  // AUTH
  // ---------------------------------------------------------

  const getAuthHeaders = () => {
    const token = localStorage.getItem("scibrain_token");

    return token
      ? {
          Authorization: `Bearer ${token}`,
        }
      : {};
  };

  // ---------------------------------------------------------
  // LOAD PAPERS
  // ---------------------------------------------------------

  useEffect(() => {
    const loadPapers = async () => {
      try {
        setLoadingPapers(true);
        setPaperError("");

        const response = await fetch(`${API_URL}/api/papers/`, {
          headers: {
            ...getAuthHeaders(),
          },
        });

        if (!response.ok) {
          throw new Error("Unable to load research papers.");
        }

        const data = await response.json();

        setPapers(Array.isArray(data) ? data : []);
      } catch (error) {
        console.error("Notebook paper loading error:", error);

        setPaperError(
          error.message || "Unable to load your research papers."
        );
      } finally {
        setLoadingPapers(false);
      }
    };

    loadPapers();
  }, []);

  // ---------------------------------------------------------
  // SELECTED PAPERS
  // ---------------------------------------------------------

  const selectedPapers = useMemo(() => {
    return papers.filter((paper) =>
      selectedResourceIds.includes(String(paper.id))
    );
  }, [papers, selectedResourceIds]);

  // ---------------------------------------------------------
  // FILTER RESOURCE LIST
  // ---------------------------------------------------------

  const filteredPapers = useMemo(() => {
    const query = resourceSearch.trim().toLowerCase();

    if (!query) return papers;

    return papers.filter((paper) => {
      const title = String(paper.title || "").toLowerCase();
      const filename = String(paper.filename || "").toLowerCase();

      return title.includes(query) || filename.includes(query);
    });
  }, [papers, resourceSearch]);

  // ---------------------------------------------------------
  // AUTO-SCROLL CHAT
  // ---------------------------------------------------------

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messages, chatLoading]);

  // ---------------------------------------------------------
  // LOAD CHAT HISTORY
  // ---------------------------------------------------------

  useEffect(() => {
    const loadChatHistory = async () => {
      try {
        setLoadingChatHistory(true);
        setHistoryError("");

        const response = await fetch(
          `${API_URL}/api/notebook/chats`,
          {
            headers: {
              ...getAuthHeaders(),
            },
          }
        );

        if (!response.ok) {
          if (response.status === 401) {
            throw new Error(
              "Your session has expired. Please log in again."
            );
          }

          throw new Error("Unable to load Notebook chat history.");
        }

        const data = await response.json();

        // Backend returns:
        // { chats: [...] }
        setChatHistory(
          Array.isArray(data?.chats) ? data.chats : []
        );
      } catch (error) {
        console.error("Notebook chat history error:", error);

        setHistoryError(
          error.message || "Unable to load chat history."
        );
      } finally {
        setLoadingChatHistory(false);
      }
    };

    loadChatHistory();
  }, []);

  // ---------------------------------------------------------
  // LOAD CURRENT CHAT
  //
  // If a chat ID exists in ResearchContext, restore that chat.
  // This allows the conversation to survive navigation away
  // from the Notebook page.
  // ---------------------------------------------------------

  useEffect(() => {
    if (!chatId) return;

    const loadCurrentChat = async () => {
      try {
        setLoadingChat(true);
        setChatError("");

        const response = await fetch(
          `${API_URL}/api/notebook/chats/${chatId}`,
          {
            headers: {
              ...getAuthHeaders(),
            },
          }
        );

        if (response.status === 404) {
          // The stored chat no longer exists.
          setChatId(null);
          setNotebookId(null);
          setMessages([]);
          return;
        }

        if (!response.ok) {
          throw new Error(
            "Unable to restore this Notebook conversation."
          );
        }

        const data = await response.json();

        // Restore notebook ID.
        if (data?.notebook_id) {
          setNotebookId(data.notebook_id);
        }

        // Restore selected resources.
        if (Array.isArray(data?.resource_ids)) {
          setSelectedResourceIds(
            data.resource_ids.map((id) => String(id))
          );
        }

        // Restore messages.
        if (Array.isArray(data?.messages)) {
          const restoredMessages = data.messages.map(
            (item, index) => ({
              id:
                item.id ||
                `${data.chat_id}-${index}-${item.role}`,
              role: item.role,
              content: item.content || "",
              citations: item.citations || [],
            })
          );

          setMessages(restoredMessages);
        }
      } catch (error) {
        console.error("Notebook chat restore error:", error);

        setChatError(
          error.message ||
            "Unable to restore the selected Notebook conversation."
        );
      } finally {
        setLoadingChat(false);
      }
    };

    loadCurrentChat();
  }, [chatId]);

  // ---------------------------------------------------------
  // RESOURCE HELPERS
  // ---------------------------------------------------------

  const removeResource = (resourceId) => {
    toggleResource(resourceId);
  };

  const openPaperLibrary = () => {
    navigate("/papers");
  };

  // ---------------------------------------------------------
  // NEW CHAT
  // ---------------------------------------------------------

  const startNewChat = () => {
    if (chatLoading) return;

    setMessages([]);
    setMessage("");
    setChatError("");

    setChatId(null);
    setNotebookId(null);

    /*
     * Keep the currently selected papers.
     *
     * This makes it convenient to start another conversation
     * about the same research collection.
     */
  };

  // ---------------------------------------------------------
  // LOAD A CHAT FROM HISTORY
  // ---------------------------------------------------------

  const openChat = async (historyItem) => {
    if (!historyItem?.chat_id) return;

    if (historyItem.chat_id === chatId && messages.length > 0) {
      return;
    }

    try {
      setLoadingChat(true);
      setChatError("");

      const response = await fetch(
        `${API_URL}/api/notebook/chats/${historyItem.chat_id}`,
        {
          headers: {
            ...getAuthHeaders(),
          },
        }
      );

      if (!response.ok) {
        if (response.status === 404) {
          throw new Error("This conversation no longer exists.");
        }

        throw new Error("Unable to open this conversation.");
      }

      const data = await response.json();

      setChatId(data.chat_id || historyItem.chat_id);

      setNotebookId(
        data.notebook_id ||
          historyItem.notebook_id ||
          null
      );

      setSelectedResourceIds(
        Array.isArray(data.resource_ids)
          ? data.resource_ids.map((id) => String(id))
          : []
      );

      const restoredMessages = Array.isArray(data.messages)
        ? data.messages.map((item, index) => ({
            id:
              item.id ||
              `${data.chat_id}-${index}-${item.role}`,
            role: item.role,
            content: item.content || "",
            citations: item.citations || [],
          }))
        : [];

      setMessages(restoredMessages);
      setMessage("");
    } catch (error) {
      console.error("Open Notebook chat error:", error);

      setChatError(
        error.message || "Unable to open this conversation."
      );
    } finally {
      setLoadingChat(false);
    }
  };

  // ---------------------------------------------------------
  // DELETE CHAT
  // ---------------------------------------------------------

  const deleteChat = async (historyItem) => {
    if (!historyItem?.chat_id) return;

    const confirmed = window.confirm(
      "Delete this Notebook conversation?"
    );

    if (!confirmed) return;

    try {
      setHistoryError("");

      const response = await fetch(
        `${API_URL}/api/notebook/chats/${historyItem.chat_id}`,
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
            data?.message ||
            "Unable to delete this conversation."
        );
      }

      setChatHistory((current) =>
        current.filter(
          (chat) => chat.chat_id !== historyItem.chat_id
        )
      );

      // If deleting the currently open chat, clear it.
      if (historyItem.chat_id === chatId) {
        setMessages([]);
        setMessage("");
        setChatId(null);
        setNotebookId(null);
      }
    } catch (error) {
      console.error("Delete Notebook chat error:", error);

      setHistoryError(
        error.message || "Unable to delete this conversation."
      );
    }
  };

  // ---------------------------------------------------------
  // REFRESH CHAT HISTORY
  // ---------------------------------------------------------

  const refreshChatHistory = async () => {
    try {
      const response = await fetch(
        `${API_URL}/api/notebook/chats`,
        {
          headers: {
            ...getAuthHeaders(),
          },
        }
      );

      if (!response.ok) return;

      const data = await response.json();

      // Backend returns:
      // { chats: [...] }
      setChatHistory(
        Array.isArray(data?.chats) ? data.chats : []
      );
    } catch (error) {
      console.error("Refresh chat history error:", error);
    }
  };

  // ---------------------------------------------------------
  // CHAT
  // ---------------------------------------------------------

  const sendMessage = async (customMessage = null) => {
    const trimmedMessage = String(
      customMessage ?? message
    ).trim();

    if (!trimmedMessage) return;

    if (selectedPapers.length === 0) {
      setChatError(
        "Select at least one research paper before starting a conversation."
      );
      return;
    }

    if (chatLoading) return;

    const userMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: trimmedMessage,
    };

    setMessages((current) => [
      ...current,
      userMessage,
    ]);

    setMessage("");
    setChatError("");
    setChatLoading(true);

    try {
      const response = await fetch(
        `${API_URL}/api/notebook/chat`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...getAuthHeaders(),
          },
          body: JSON.stringify({
            resource_ids: selectedResourceIds,
            message: trimmedMessage,
            chat_id: chatId || null,
            notebook_id: notebookId || null,
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
        const backendMessage =
          data?.detail ||
          data?.message ||
          "The research assistant could not process your question.";

        throw new Error(backendMessage);
      }

      const assistantText =
        data?.answer ||
        data?.response ||
        data?.message ||
        "";

      console.log(
        "NOTEBOOK API RESPONSE:",
        data
      );

      console.log(
        "NOTEBOOK ANSWER:",
        assistantText
      );

      if (!assistantText) {
        throw new Error(
          "The backend returned an empty response. Please check the notebook chat service."
        );
      }

      // -----------------------------------------------------
      // Store generated IDs
      // -----------------------------------------------------

      if (data?.chat_id && data.chat_id !== chatId) {
        setChatId(data.chat_id);
      }

      if (
        data?.notebook_id &&
        data.notebook_id !== notebookId
      ) {
        setNotebookId(data.notebook_id);
      }

      const assistantMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: assistantText,
        citations:
          data?.citations ||
          data?.sources ||
          [],
      };

      setMessages((current) => [
        ...current,
        assistantMessage,
      ]);

      // -----------------------------------------------------
      // Refresh history after successful exchange.
      // -----------------------------------------------------

      await refreshChatHistory();
    } catch (error) {
      console.error(
        "Notebook chat error:",
        error
      );

      setChatError(
        error.message ||
          "Something went wrong while contacting the research assistant."
      );
    } finally {
      setChatLoading(false);
    }
  };

  const handleSubmit = async (event) => {
    event.preventDefault();

    await sendMessage();
  };

  const handleTextareaKeyDown = async (event) => {
    if (
      event.key === "Enter" &&
      !event.shiftKey
    ) {
      event.preventDefault();

      if (!chatLoading) {
        await sendMessage();
      }
    }
  };

  const useSuggestedPrompt = (prompt) => {
    setMessage(prompt);

    requestAnimationFrame(() => {
      textareaRef.current?.focus();
    });
  };

  // ---------------------------------------------------------
  // CITATIONS
  // ---------------------------------------------------------

  const getCitationTitle = (citation) => {
    const resourceId =
      citation?.resource_id ||
      citation?.paper_id ||
      citation?.document_id;

    const paper = papers.find(
      (item) =>
        String(item.id) ===
        String(resourceId)
    );

    return (
      citation?.title ||
      paper?.title ||
      paper?.filename ||
      "Research source"
    );
  };

  const groupCitationsByPaper = (
    citations = []
  ) => {
    const grouped = new Map();

    citations.forEach((citation) => {
      const paperId = String(
        citation?.paper_id ??
          citation?.resource_id ??
          citation?.document_id ??
          citation?.title ??
          "unknown"
      );

      if (!grouped.has(paperId)) {
        grouped.set(paperId, {
          ...citation,
          chunkCount: 1,
        });
      } else {
        grouped.get(paperId).chunkCount += 1;
      }
    });

    return Array.from(
      grouped.values()
    );
  };

  // ---------------------------------------------------------
  // EMPTY CHAT STATE
  // ---------------------------------------------------------

  const renderEmptyState = () => {
    return (
      <div className="flex min-h-[520px] flex-col items-center justify-center px-6 text-center">
        <div className="mb-5 flex h-16 w-16 items-center justify-center rounded-2xl border border-indigo-400/20 bg-indigo-500/10">
          <Sparkles className="h-7 w-7 text-indigo-400" />
        </div>

        <h2 className="text-xl font-semibold text-slate-100">
          Research Notebook
        </h2>

        <p className="mt-2 max-w-xl text-sm leading-6 text-slate-400">
          Ask questions about your selected research papers.
          The assistant will use only the resources attached
          to this notebook conversation.
        </p>

        {selectedPapers.length === 0 ? (
          <div className="mt-6 flex items-center gap-2 rounded-xl border border-amber-400/20 bg-amber-400/5 px-4 py-3 text-sm text-amber-300">
            <FileText className="h-4 w-4" />
            Select a research paper to start chatting.
          </div>
        ) : (
          <div className="mt-8 grid w-full max-w-3xl gap-3 sm:grid-cols-2">
            <SuggestedQuestion
              icon={<BookOpen className="h-4 w-4" />}
              text="Summarize the main contribution of these papers."
              onClick={() =>
                useSuggestedPrompt(
                  "Summarize the main contribution of these papers."
                )
              }
            />

            <SuggestedQuestion
              icon={<GitBranch className="h-4 w-4" />}
              text="Compare the methodologies used in these papers."
              onClick={() =>
                useSuggestedPrompt(
                  "Compare the methodologies used in these papers."
                )
              }
            />

            <SuggestedQuestion
              icon={<Search className="h-4 w-4" />}
              text="What limitations do the authors identify?"
              onClick={() =>
                useSuggestedPrompt(
                  "What limitations do the authors identify?"
                )
              }
            />

            <SuggestedQuestion
              icon={<Network className="h-4 w-4" />}
              text="What research opportunities can be explored from these papers?"
              onClick={() =>
                useSuggestedPrompt(
                  "What research opportunities can be explored from these papers?"
                )
              }
            />
          </div>
        )}
      </div>
    );
  };

  // ---------------------------------------------------------
  // MESSAGE
  // ---------------------------------------------------------

  const renderMessage = (item) => {
    const isUser = item.role === "user";

    const groupedCitations = !isUser
      ? groupCitationsByPaper(
          item.citations || []
        )
      : [];

    return (
      <div
        key={item.id}
        className={`flex w-full ${
          isUser
            ? "justify-end"
            : "justify-start"
        }`}
      >
        <div
          className={`flex max-w-[82%] gap-3 ${
            isUser
              ? "flex-row-reverse"
              : "flex-row"
          }`}
        >
          <div
            className={`mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border ${
              isUser
                ? "border-indigo-400/20 bg-indigo-500/15 text-indigo-300"
                : "border-cyan-400/20 bg-cyan-500/10 text-cyan-300"
            }`}
          >
            {isUser ? (
              <MessageSquare className="h-4 w-4" />
            ) : (
              <Bot className="h-4 w-4" />
            )}
          </div>

          <div>
            <div
              className={`rounded-2xl px-4 py-3 text-sm leading-6 ${
                isUser
                  ? "rounded-tr-md bg-indigo-600 text-white"
                  : "rounded-tl-md border border-white/[0.07] bg-slate-900/70 text-slate-200"
              }`}
            >
              <div className="whitespace-pre-wrap break-words">
                {item.content}
              </div>
            </div>

            {!isUser &&
              groupedCitations.length > 0 && (
                <div className="mt-3 space-y-2">
                  <div className="text-[11px] font-medium uppercase tracking-wider text-slate-500">
                    Sources
                  </div>

                  <div className="flex flex-wrap gap-2">
                    {groupedCitations.map(
                      (
                        citation,
                        index
                      ) => (
                        <div
                          key={`${item.id}-source-${
                            citation?.paper_id ??
                            citation?.resource_id ??
                            citation?.title ??
                            index
                          }`}
                          className="flex max-w-full items-center gap-2 rounded-lg border border-white/[0.06] bg-slate-950/50 px-3 py-2 text-xs text-slate-400"
                        >
                          <FileText className="h-3.5 w-3.5 shrink-0 text-indigo-400" />

                          <span className="truncate">
                            {getCitationTitle(
                              citation
                            )}
                          </span>

                          <span className="shrink-0 text-slate-600">
                            {
                              citation.chunkCount
                            }{" "}
                            {citation.chunkCount ===
                            1
                              ? "passage"
                              : "passages"}
                          </span>
                        </div>
                      )
                    )}
                  </div>
                </div>
              )}
          </div>
        </div>
      </div>
    );
  };

  // ---------------------------------------------------------
  // RENDER
  // ---------------------------------------------------------

  return (
    <AppLayout>
      <div className="mx-auto flex max-w-[1500px] flex-col gap-6">
        {/* -------------------------------------------------- */}
        {/* HEADER */}
        {/* -------------------------------------------------- */}

        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="mb-2 flex items-center gap-2 text-xs font-medium uppercase tracking-[0.18em] text-indigo-400">
              <Sparkles className="h-3.5 w-3.5" />
              Research Workspace
            </div>

            <h1 className="text-3xl font-semibold tracking-tight text-slate-100">
              Research Notebook
            </h1>

            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
              Explore, question, and reason over the
              research papers attached to your notebook.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {/* NEW CHAT */}

            <button
              type="button"
              onClick={startNewChat}
              disabled={chatLoading}
              className="inline-flex items-center gap-2 rounded-xl border border-indigo-400/20 bg-indigo-500/10 px-4 py-2.5 text-sm font-medium text-indigo-300 transition hover:border-indigo-400/30 hover:bg-indigo-500/15 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <Plus className="h-4 w-4" />
              New Chat
            </button>

            <button
              type="button"
              onClick={() =>
                setShowResourcePicker(
                  (current) => !current
                )
              }
              className="inline-flex items-center gap-2 rounded-xl border border-white/[0.08] bg-slate-900/60 px-4 py-2.5 text-sm font-medium text-slate-200 transition hover:border-indigo-400/30 hover:bg-slate-800/70"
            >
              <Plus className="h-4 w-4" />
              Add resources

              <ChevronDown
                className={`h-4 w-4 transition-transform ${
                  showResourcePicker
                    ? "rotate-180"
                    : ""
                }`}
              />
            </button>

            <button
              type="button"
              onClick={() =>
                navigate("/knowledge-graph")
              }
              disabled={
                selectedPapers.length === 0
              }
              className="inline-flex items-center gap-2 rounded-xl border border-white/[0.08] bg-slate-900/60 px-4 py-2.5 text-sm font-medium text-slate-200 transition hover:border-cyan-400/30 hover:bg-slate-800/70 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <Network className="h-4 w-4" />
              Knowledge Graph
            </button>

            <button
              type="button"
              onClick={() =>
                navigate("/research-gaps")
              }
              disabled={
                selectedPapers.length === 0
              }
              className="inline-flex items-center gap-2 rounded-xl border border-white/[0.08] bg-slate-900/60 px-4 py-2.5 text-sm font-medium text-slate-200 transition hover:border-indigo-400/30 hover:bg-slate-800/70 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Research Gaps
              <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* -------------------------------------------------- */}
        {/* CHAT HISTORY */}
        {/* -------------------------------------------------- */}

        <div className="rounded-2xl border border-white/[0.07] bg-slate-950/50 p-4">
          <div className="mb-3 flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2 text-sm font-semibold text-slate-200">
                <MessageSquare className="h-4 w-4 text-indigo-400" />
                Chat History
              </div>

              <div className="mt-1 text-xs text-slate-500">
                Your saved Research Notebook conversations
              </div>
            </div>

            <button
              type="button"
              onClick={startNewChat}
              disabled={chatLoading}
              className="text-xs font-medium text-indigo-400 transition hover:text-indigo-300 disabled:opacity-40"
            >
              + New Chat
            </button>
          </div>

          {historyError && (
            <div className="mb-3 rounded-xl border border-red-400/15 bg-red-400/[0.04] px-3 py-2 text-xs text-red-300">
              {historyError}
            </div>
          )}

          {loadingChatHistory ? (
            <div className="flex items-center gap-2 py-4 text-xs text-slate-500">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Loading conversations...
            </div>
          ) : chatHistory.length === 0 ? (
            <div className="rounded-xl border border-dashed border-white/[0.07] bg-slate-900/30 px-4 py-5 text-center text-xs text-slate-600">
              No saved conversations yet.
              <div className="mt-1 text-slate-700">
                Your first Notebook question will appear here.
              </div>
            </div>
          ) : (
            <div className="flex gap-2 overflow-x-auto pb-1">
              {chatHistory.map((historyItem) => {
                const active =
                  historyItem.chat_id ===
                  chatId;

                return (
                  <div
                    key={historyItem.chat_id}
                    className={`group flex min-w-[240px] max-w-[320px] shrink-0 items-center gap-2 rounded-xl border px-3 py-2.5 transition ${
                      active
                        ? "border-indigo-400/25 bg-indigo-500/10"
                        : "border-white/[0.06] bg-slate-900/40 hover:border-white/[0.12] hover:bg-slate-900/70"
                    }`}
                  >
                    <button
                      type="button"
                      onClick={() =>
                        openChat(historyItem)
                      }
                      className="min-w-0 flex-1 text-left"
                    >
                      <div
                        className={`truncate text-sm font-medium ${
                          active
                            ? "text-indigo-300"
                            : "text-slate-300"
                        }`}
                      >
                        {historyItem.title ||
                          "New Research Chat"}
                      </div>

                      <div className="mt-1 text-[11px] text-slate-600">
                        {Array.isArray(
                          historyItem.resource_ids
                        )
                          ? `${
                              historyItem
                                .resource_ids
                                .length
                            } ${
                              historyItem
                                .resource_ids
                                .length ===
                              1
                                ? "paper"
                                : "papers"
                            }`
                          : "Research chat"}
                      </div>
                    </button>

                    <button
                      type="button"
                      onClick={() =>
                        deleteChat(
                          historyItem
                        )
                      }
                      className="rounded-lg p-1.5 text-slate-600 opacity-0 transition hover:bg-red-400/10 hover:text-red-300 group-hover:opacity-100"
                      title="Delete conversation"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* -------------------------------------------------- */}
        {/* RESOURCE PICKER */}
        {/* -------------------------------------------------- */}

        {showResourcePicker && (
          <div className="rounded-2xl border border-white/[0.07] bg-slate-950/70 p-5 shadow-2xl shadow-black/10">
            <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h2 className="text-sm font-semibold text-slate-200">
                  Add research resources
                </h2>

                <p className="mt-1 text-xs text-slate-500">
                  Only selected resources will be used for
                  this notebook chat.
                </p>
              </div>

              <button
                type="button"
                onClick={() =>
                  setShowResourcePicker(false)
                }
                className="self-start rounded-lg p-2 text-slate-500 transition hover:bg-white/[0.05] hover:text-slate-200"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="mb-4 flex items-center gap-2 rounded-xl border border-white/[0.06] bg-slate-900/60 px-3 py-2.5">
              <Search className="h-4 w-4 text-slate-500" />

              <input
                type="text"
                value={resourceSearch}
                onChange={(event) =>
                  setResourceSearch(
                    event.target.value
                  )
                }
                placeholder="Search papers..."
                className="w-full bg-transparent text-sm text-slate-200 outline-none placeholder:text-slate-600"
              />
            </div>

            {loadingPapers ? (
              <div className="flex items-center justify-center py-8 text-sm text-slate-500">
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Loading papers...
              </div>
            ) : paperError ? (
              <div className="rounded-xl border border-red-400/20 bg-red-400/5 p-4 text-sm text-red-300">
                {paperError}
              </div>
            ) : filteredPapers.length === 0 ? (
              <div className="rounded-xl border border-white/[0.06] bg-slate-900/40 p-6 text-center">
                <FileText className="mx-auto mb-2 h-5 w-5 text-slate-600" />

                <p className="text-sm text-slate-500">
                  No research papers found.
                </p>

                <button
                  type="button"
                  onClick={openPaperLibrary}
                  className="mt-3 text-xs font-medium text-indigo-400 hover:text-indigo-300"
                >
                  Open Paper Library
                </button>
              </div>
            ) : (
              <div className="grid gap-2 md:grid-cols-2">
                {filteredPapers.map((paper) => {
                  const paperId =
                    String(paper.id);

                  const selected =
                    selectedResourceIds.includes(
                      paperId
                    );

                  return (
                    <button
                      type="button"
                      key={paperId}
                      onClick={() =>
                        toggleResource(
                          paperId
                        )
                      }
                      className={`flex items-start gap-3 rounded-xl border p-3 text-left transition ${
                        selected
                          ? "border-indigo-400/30 bg-indigo-500/10"
                          : "border-white/[0.06] bg-slate-900/40 hover:border-white/[0.12] hover:bg-slate-900/70"
                      }`}
                    >
                      <div
                        className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${
                          selected
                            ? "bg-indigo-500/15 text-indigo-300"
                            : "bg-slate-800 text-slate-500"
                        }`}
                      >
                        <FileText className="h-4 w-4" />
                      </div>

                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm font-medium text-slate-200">
                          {paper.title ||
                            paper.filename ||
                            "Untitled paper"}
                        </div>

                        <div className="mt-1 flex items-center gap-2 text-xs text-slate-500">
                          <span>
                            {paper.page_count
                              ? `${paper.page_count} pages`
                              : "Research paper"}
                          </span>

                          {selected && (
                            <span className="text-indigo-400">
                              Selected
                            </span>
                          )}
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* -------------------------------------------------- */}
        {/* ACTIVE CONTEXT */}
        {/* -------------------------------------------------- */}

        <div className="rounded-2xl border border-white/[0.07] bg-slate-950/50 p-5">
          <div className="mb-3 flex items-center justify-between gap-4">
            <div>
              <div className="text-xs font-medium uppercase tracking-wider text-slate-500">
                Active Research Context
              </div>

              <div className="mt-1 text-sm text-slate-300">
                {selectedPapers.length === 0
                  ? "No resources selected"
                  : `${selectedPapers.length} ${
                      selectedPapers.length ===
                      1
                        ? "resource"
                        : "resources"
                    } attached to this notebook`}
              </div>
            </div>

            {selectedPapers.length > 0 && (
              <button
                type="button"
                onClick={() => {
                  selectedResourceIds.forEach(
                    (id) =>
                      toggleResource(id)
                  );
                }}
                className="text-xs text-slate-500 transition hover:text-slate-300"
              >
                Clear all
              </button>
            )}
          </div>

          {selectedPapers.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {selectedPapers.map((paper) => (
                <div
                  key={paper.id}
                  className="flex max-w-full items-center gap-2 rounded-lg border border-indigo-400/15 bg-indigo-500/[0.07] px-3 py-2"
                >
                  <FileText className="h-3.5 w-3.5 shrink-0 text-indigo-400" />

                  <span className="max-w-[260px] truncate text-xs text-slate-300">
                    {paper.title ||
                      paper.filename ||
                      "Untitled paper"}
                  </span>

                  <button
                    type="button"
                    onClick={() =>
                      removeResource(
                        String(paper.id)
                      )
                    }
                    className="rounded p-0.5 text-slate-500 transition hover:bg-white/[0.05] hover:text-slate-200"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <button
              type="button"
              onClick={() =>
                setShowResourcePicker(true)
              }
              className="inline-flex items-center gap-2 rounded-lg border border-dashed border-white/[0.10] px-3 py-2 text-xs text-slate-500 transition hover:border-indigo-400/30 hover:text-indigo-300"
            >
              <Plus className="h-3.5 w-3.5" />
              Attach research papers
            </button>
          )}
        </div>

        {/* -------------------------------------------------- */}
        {/* NOTEBOOK CHAT */}
        {/* -------------------------------------------------- */}

        <div className="overflow-hidden rounded-2xl border border-white/[0.07] bg-slate-950/40">
          {/* Chat header */}

          <div className="flex items-center justify-between border-b border-white/[0.06] px-5 py-4">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-500/10 text-indigo-400">
                <MessageSquare className="h-4 w-4" />
              </div>

              <div>
                <div className="text-sm font-medium text-slate-200">
                  Research Conversation
                </div>

                <div className="text-xs text-slate-500">
                  {selectedPapers.length > 0
                    ? `Grounded in ${
                        selectedPapers.length
                      } selected ${
                        selectedPapers.length ===
                        1
                          ? "resource"
                          : "resources"
                      }`
                    : "Select resources to begin"}
                </div>
              </div>
            </div>

            {loadingChat && (
              <div className="flex items-center gap-2 rounded-lg border border-indigo-400/10 bg-indigo-400/5 px-2.5 py-1.5 text-[11px] text-indigo-300">
                <Loader2 className="h-3 w-3 animate-spin" />
                Restoring
              </div>
            )}

            {!loadingChat &&
              chatId && (
                <div className="hidden rounded-lg border border-emerald-400/10 bg-emerald-400/5 px-2.5 py-1.5 text-[11px] text-emerald-400 sm:block">
                  Conversation active
                </div>
              )}
          </div>

          {/* Messages */}

          <div className="min-h-[520px] max-h-[650px] overflow-y-auto px-5 py-6">
            {messages.length === 0 ? (
              renderEmptyState()
            ) : (
              <div className="mx-auto flex max-w-4xl flex-col gap-6">
                {messages.map(renderMessage)}

                {chatLoading && (
                  <div className="flex justify-start">
                    <div className="flex max-w-[82%] gap-3">
                      <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-cyan-400/20 bg-cyan-500/10 text-cyan-300">
                        <Bot className="h-4 w-4" />
                      </div>

                      <div className="rounded-2xl rounded-tl-md border border-white/[0.07] bg-slate-900/70 px-4 py-3">
                        <div className="flex items-center gap-2 text-sm text-slate-400">
                          <Loader2 className="h-4 w-4 animate-spin text-indigo-400" />

                          <span>
                            Researching your selected
                            papers...
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                <div ref={messagesEndRef} />
              </div>
            )}
          </div>

          {/* Error */}

          {chatError && (
            <div className="border-t border-red-400/10 bg-red-400/[0.03] px-5 py-3">
              <div className="mx-auto max-w-4xl text-sm text-red-300">
                {chatError}
              </div>
            </div>
          )}

          {/* Composer */}

          <div className="border-t border-white/[0.06] bg-slate-950/70 p-4">
            <form
              onSubmit={handleSubmit}
              className="mx-auto max-w-4xl"
            >
              <div
                className={`rounded-2xl border transition ${
                  selectedPapers.length === 0
                    ? "border-white/[0.05] bg-slate-900/30"
                    : "border-white/[0.09] bg-slate-900/70 focus-within:border-indigo-400/30"
                }`}
              >
                <textarea
                  ref={textareaRef}
                  value={message}
                  onChange={(event) =>
                    setMessage(
                      event.target.value
                    )
                  }
                  onKeyDown={
                    handleTextareaKeyDown
                  }
                  disabled={
                    selectedPapers.length ===
                      0 ||
                    chatLoading ||
                    loadingChat
                  }
                  rows={3}
                  placeholder={
                    selectedPapers.length ===
                    0
                      ? "Attach a research paper to start chatting..."
                      : "Ask a question about your selected research..."
                  }
                  className="w-full resize-none bg-transparent px-4 pt-4 text-sm leading-6 text-slate-200 outline-none placeholder:text-slate-600 disabled:cursor-not-allowed"
                />

                <div className="flex items-center justify-between px-3 pb-3">
                  <div className="text-[11px] text-slate-600">
                    Enter to send · Shift + Enter for a new line
                  </div>

                  <button
                    type="submit"
                    disabled={
                      !message.trim() ||
                      selectedPapers.length ===
                        0 ||
                      chatLoading ||
                      loadingChat
                    }
                    className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-600 text-white transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    {chatLoading ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Send className="h-4 w-4" />
                    )}
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}

/* -----------------------------------------------------------
 * SUGGESTED QUESTION
 * -----------------------------------------------------------
 */

function SuggestedQuestion({
  icon,
  text,
  onClick,
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex items-center gap-3 rounded-xl border border-white/[0.07] bg-slate-900/40 p-4 text-left transition hover:border-indigo-400/25 hover:bg-slate-900/70"
    >
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-indigo-500/10 text-indigo-400">
        {icon}
      </div>

      <span className="text-sm leading-5 text-slate-400">
        {text}
      </span>
    </button>
  );
}

export default ResearchNotebook;
