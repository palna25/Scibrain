
import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import AppLayout from "../components/AppLayout";

import {
  BookOpen,
  FileText,
  Loader2,
  MessageSquare,
  MoreVertical,
  Plus,
  Search,
  Sparkles,
  Trash2,
  X,
  RefreshCw,
} from "lucide-react";

const API_URL = "http://127.0.0.1:8000";

function ResearchNotebook() {
  const navigate = useNavigate();

  const [notebooks, setNotebooks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");

  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");

  const [openMenu, setOpenMenu] = useState(null);
  const [deletingId, setDeletingId] = useState(null);

  const getAuthHeaders = useCallback(() => {
    const token = localStorage.getItem("scibrain_token");

    return token
      ? { Authorization: `Bearer ${token}` }
      : {};
  }, []);

  const readResponse = async (response) => {
    try {
      return await response.json();
    } catch {
      return null;
    }
  };

  const loadNotebooks = useCallback(async () => {
    try {
      setLoading(true);
      setError("");

      const response = await fetch(`${API_URL}/api/notebook`, {
        headers: getAuthHeaders(),
      });

      if (response.status === 401) {
        throw new Error("Your session has expired. Please log in again.");
      }

      const data = await readResponse(response);

      if (!response.ok) {
        throw new Error(
          data?.detail || "Unable to load your research notebooks."
        );
      }

      setNotebooks(
        Array.isArray(data?.notebooks) ? data.notebooks : []
      );
    } catch (err) {
      console.error("Research notebook loading error:", err);
      setError(err.message || "Unable to load your research notebooks.");
    } finally {
      setLoading(false);
    }
  }, [getAuthHeaders]);

  useEffect(() => {
    loadNotebooks();
  }, [loadNotebooks]);

  const filteredNotebooks = notebooks.filter((notebook) => {
    const query = search.trim().toLowerCase();

    if (!query) return true;

    return (
      String(notebook.title || "").toLowerCase().includes(query) ||
      String(notebook.description || "").toLowerCase().includes(query)
    );
  });

  const openCreateModal = () => {
    setNewTitle("");
    setNewDescription("");
    setCreateError("");
    setShowCreateModal(true);
  };

  const closeCreateModal = () => {
    if (creating) return;

    setShowCreateModal(false);
    setNewTitle("");
    setNewDescription("");
    setCreateError("");
  };

  const createNotebook = async (event) => {
    event.preventDefault();

    const title = newTitle.trim();
    const description = newDescription.trim();

    if (!title) {
      setCreateError("Enter a name for your notebook.");
      return;
    }

    if (creating) return;

    try {
      setCreating(true);
      setCreateError("");

      const response = await fetch(`${API_URL}/api/notebook`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...getAuthHeaders(),
        },
        body: JSON.stringify({
          title,
          description,
          resource_ids: [],
        }),
      });

      const data = await readResponse(response);

      if (response.status === 401) {
        throw new Error("Your session has expired. Please log in again.");
      }

      if (!response.ok) {
        throw new Error(data?.detail || "Unable to create the notebook.");
      }

      const notebook = data?.notebook;

      if (!notebook?.notebook_id) {
        throw new Error(
          "The server did not return the ID of the created notebook."
        );
      }

      setShowCreateModal(false);
      setNewTitle("");
      setNewDescription("");

      // Sources and chats belong to the individual notebook workspace.
      navigate(`/notebook/${encodeURIComponent(notebook.notebook_id)}`);
    } catch (err) {
      console.error("Create notebook error:", err);
      setCreateError(err.message || "Unable to create the notebook.");
    } finally {
      setCreating(false);
    }
  };

  const openNotebook = (notebookId) => {
    if (!notebookId) return;

    navigate(`/notebook/${encodeURIComponent(notebookId)}`);
  };

  const deleteNotebook = async (notebook) => {
    if (!notebook?.notebook_id || deletingId) return;

    const confirmed = window.confirm(
      `Delete "${notebook.title || "this notebook"}"?\n\nThis will also delete all chats belonging to this notebook.`
    );

    if (!confirmed) return;

    try {
      setDeletingId(notebook.notebook_id);
      setError("");
      setOpenMenu(null);

      const response = await fetch(
        `${API_URL}/api/notebook/${encodeURIComponent(notebook.notebook_id)}`,
        {
          method: "DELETE",
          headers: getAuthHeaders(),
        }
      );

      const data = await readResponse(response);

      if (response.status === 401) {
        throw new Error("Your session has expired. Please log in again.");
      }

      if (!response.ok) {
        throw new Error(data?.detail || "Unable to delete the notebook.");
      }

      setNotebooks((current) =>
        current.filter(
          (item) => item.notebook_id !== notebook.notebook_id
        )
      );
    } catch (err) {
      console.error("Delete notebook error:", err);
      setError(err.message || "Unable to delete the notebook.");
    } finally {
      setDeletingId(null);
    }
  };

  const formatDate = (value) => {
    if (!value) return "Recently created";

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
      return "Recently updated";
    }

    return date.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  };

  return (
    <AppLayout>
      <div className="mx-auto flex max-w-[1500px] flex-col gap-8">
        {/* Header */}
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="mb-2 flex items-center gap-2 text-xs font-medium uppercase tracking-[0.18em] text-indigo-400">
              <Sparkles className="h-3.5 w-3.5" />
              Research Workspace
            </div>

            <h1 className="text-3xl font-semibold tracking-tight text-slate-100">
              Research Notebooks
            </h1>

            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
              Create separate workspaces for your research papers, sources,
              and conversations. Each notebook keeps its research context
              organized independently.
            </p>
          </div>

          <button
            type="button"
            onClick={openCreateModal}
            className="inline-flex items-center justify-center gap-2 rounded-xl border border-indigo-400/20 bg-indigo-500/10 px-4 py-2.5 text-sm font-medium text-indigo-300 transition hover:border-indigo-400/30 hover:bg-indigo-500/15"
          >
            <Plus className="h-4 w-4" />
            New Notebook
          </button>
        </div>

        {/* Error */}
        {error && (
          <div className="flex items-center justify-between gap-4 rounded-xl border border-red-400/15 bg-red-400/[0.04] px-4 py-3 text-sm text-red-300">
            <span>{error}</span>

            <button
              type="button"
              onClick={loadNotebooks}
              disabled={loading}
              className="inline-flex shrink-0 items-center gap-1.5 text-xs font-medium text-red-200 hover:text-white disabled:opacity-50"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              Retry
            </button>
          </div>
        )}

        {/* Search */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex w-full max-w-xl items-center gap-2 rounded-xl border border-white/[0.07] bg-slate-950/60 px-3 py-2.5">
            <Search className="h-4 w-4 shrink-0 text-slate-500" />

            <input
              type="text"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search notebooks..."
              aria-label="Search notebooks"
              className="w-full bg-transparent text-sm text-slate-200 outline-none placeholder:text-slate-600"
            />
          </div>

          {!loading && (
            <div className="text-xs text-slate-600">
              {filteredNotebooks.length}{" "}
              {filteredNotebooks.length === 1 ? "notebook" : "notebooks"}
            </div>
          )}
        </div>

        {/* Notebook library */}
        {loading ? (
          <div className="flex min-h-[360px] items-center justify-center rounded-2xl border border-white/[0.07] bg-slate-950/40">
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading your research notebooks...
            </div>
          </div>
        ) : filteredNotebooks.length === 0 ? (
          <EmptyNotebookState
            hasSearch={Boolean(search.trim())}
            onCreate={openCreateModal}
            onClearSearch={() => setSearch("")}
          />
        ) : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {filteredNotebooks.map((notebook) => (
              <NotebookCard
                key={notebook.notebook_id}
                notebook={notebook}
                deleting={deletingId === notebook.notebook_id}
                menuOpen={openMenu === notebook.notebook_id}
                onOpen={() => openNotebook(notebook.notebook_id)}
                onMenu={() =>
                  setOpenMenu((current) =>
                    current === notebook.notebook_id
                      ? null
                      : notebook.notebook_id
                  )
                }
                onDelete={() => deleteNotebook(notebook)}
                formatDate={formatDate}
              />
            ))}
          </div>
        )}
      </div>

      {/* Create notebook modal */}
      {showCreateModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4 backdrop-blur-sm"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              closeCreateModal();
            }
          }}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="create-notebook-title"
            className="w-full max-w-lg rounded-2xl border border-white/[0.08] bg-slate-950 shadow-2xl shadow-black/40"
          >
            <div className="flex items-center justify-between border-b border-white/[0.06] px-5 py-4">
              <div>
                <div
                  id="create-notebook-title"
                  className="flex items-center gap-2 text-sm font-semibold text-slate-100"
                >
                  <BookOpen className="h-4 w-4 text-indigo-400" />
                  New Research Notebook
                </div>

                <p className="mt-1 text-xs text-slate-500">
                  Create your workspace, then add sources inside it.
                </p>
              </div>

              <button
                type="button"
                onClick={closeCreateModal}
                disabled={creating}
                aria-label="Close create notebook dialog"
                className="rounded-lg p-2 text-slate-500 transition hover:bg-white/[0.05] hover:text-slate-200 disabled:opacity-40"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <form onSubmit={createNotebook} className="space-y-5 p-5">
              <div>
                <label
                  htmlFor="notebook-title"
                  className="mb-2 block text-xs font-medium uppercase tracking-wider text-slate-500"
                >
                  Notebook name
                </label>

                <input
                  id="notebook-title"
                  autoFocus
                  required
                  type="text"
                  value={newTitle}
                  onChange={(event) => setNewTitle(event.target.value)}
                  placeholder="e.g. RAG Research"
                  maxLength={150}
                  className="w-full rounded-xl border border-white/[0.08] bg-slate-900/70 px-4 py-3 text-sm text-slate-200 outline-none transition placeholder:text-slate-600 focus:border-indigo-400/30"
                />
              </div>

              <div>
                <label
                  htmlFor="notebook-description"
                  className="mb-2 block text-xs font-medium uppercase tracking-wider text-slate-500"
                >
                  Description
                  <span className="ml-1 normal-case tracking-normal text-slate-700">
                    optional
                  </span>
                </label>

                <textarea
                  id="notebook-description"
                  value={newDescription}
                  onChange={(event) =>
                    setNewDescription(event.target.value)
                  }
                  placeholder="What are you researching in this notebook?"
                  maxLength={500}
                  rows={4}
                  className="w-full resize-none rounded-xl border border-white/[0.08] bg-slate-900/70 px-4 py-3 text-sm leading-6 text-slate-200 outline-none transition placeholder:text-slate-600 focus:border-indigo-400/30"
                />
              </div>

              {createError && (
                <div
                  role="alert"
                  className="rounded-xl border border-red-400/15 bg-red-400/[0.04] px-3 py-2.5 text-xs text-red-300"
                >
                  {createError}
                </div>
              )}

              <div className="flex justify-end gap-3">
                <button
                  type="button"
                  onClick={closeCreateModal}
                  disabled={creating}
                  className="rounded-xl border border-white/[0.08] bg-slate-900/60 px-4 py-2.5 text-sm font-medium text-slate-400 transition hover:bg-slate-800 hover:text-slate-200 disabled:opacity-40"
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  disabled={creating || !newTitle.trim()}
                  className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {creating ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Creating...
                    </>
                  ) : (
                    <>
                      <Plus className="h-4 w-4" />
                      Create Notebook
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </AppLayout>
  );
}

function NotebookCard({
  notebook,
  deleting,
  menuOpen,
  onOpen,
  onMenu,
  onDelete,
  formatDate,
}) {
  const resourceCount = Array.isArray(notebook.resource_ids)
    ? notebook.resource_ids.length
    : 0;

  return (
    <article
      className={`group relative rounded-2xl border bg-slate-950/50 transition ${
        menuOpen
          ? "border-indigo-400/25"
          : "border-white/[0.07] hover:border-indigo-400/20"
      }`}
    >
      <div className="flex items-start justify-between px-5 pt-5">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-indigo-400/15 bg-indigo-500/10 text-indigo-400 transition group-hover:bg-indigo-500/15">
          <BookOpen className="h-5 w-5" />
        </div>

        <div className="relative">
          <button
            type="button"
            onClick={onMenu}
            disabled={deleting}
            aria-label={`Options for ${notebook.title || "notebook"}`}
            aria-expanded={menuOpen}
            className="rounded-lg p-2 text-slate-600 transition hover:bg-white/[0.05] hover:text-slate-300 disabled:opacity-40"
          >
            <MoreVertical className="h-4 w-4" />
          </button>

          {menuOpen && (
            <div className="absolute right-0 top-10 z-20 w-40 rounded-xl border border-white/[0.08] bg-slate-900 p-1.5 shadow-2xl shadow-black/30">
              <button
                type="button"
                onClick={onDelete}
                disabled={deleting}
                className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-xs text-red-300 transition hover:bg-red-400/10 disabled:opacity-50"
              >
                <Trash2 className="h-3.5 w-3.5" />
                Delete notebook
              </button>
            </div>
          )}
        </div>
      </div>

      <button
        type="button"
        onClick={onOpen}
        disabled={deleting}
        className="block w-full rounded-b-2xl px-5 pb-5 pt-4 text-left disabled:cursor-wait"
      >
        <h2 className="truncate text-base font-semibold text-slate-100">
          {notebook.title || "Untitled Notebook"}
        </h2>

        <p className="mt-2 min-h-[42px] text-sm leading-5 text-slate-500">
          {notebook.description ||
            "A research workspace for organizing papers and conversations."}
        </p>

        <div className="mt-5 flex items-center gap-4 border-t border-white/[0.05] pt-4">
          <div className="flex items-center gap-1.5 text-xs text-slate-500">
            <FileText className="h-3.5 w-3.5 text-indigo-400" />
            {resourceCount} {resourceCount === 1 ? "source" : "sources"}
          </div>

          <div className="flex items-center gap-1.5 text-xs text-slate-500">
            <MessageSquare className="h-3.5 w-3.5 text-cyan-400" />
            Research chats
          </div>
        </div>

        <div className="mt-3 text-[11px] text-slate-700">
          Updated {formatDate(notebook.updated_at || notebook.created_at)}
        </div>
      </button>

      {deleting && (
        <div className="absolute inset-0 z-30 flex items-center justify-center rounded-2xl bg-slate-950/80 backdrop-blur-sm">
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            Deleting notebook...
          </div>
        </div>
      )}
    </article>
  );
}

function EmptyNotebookState({ hasSearch, onCreate, onClearSearch }) {
  if (hasSearch) {
    return (
      <div className="flex min-h-[360px] flex-col items-center justify-center rounded-2xl border border-dashed border-white/[0.08] bg-slate-950/30 px-6 text-center">
        <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl border border-white/[0.07] bg-slate-900/60">
          <Search className="h-6 w-6 text-slate-600" />
        </div>

        <h2 className="text-lg font-medium text-slate-300">
          No notebooks found
        </h2>

        <p className="mt-2 max-w-md text-sm leading-6 text-slate-600">
          No research notebook matches your search.
        </p>

        <button
          type="button"
          onClick={onClearSearch}
          className="mt-5 text-xs font-medium text-indigo-400 transition hover:text-indigo-300"
        >
          Clear search
        </button>
      </div>
    );
  }

  return (
    <div className="flex min-h-[420px] flex-col items-center justify-center rounded-2xl border border-dashed border-white/[0.08] bg-slate-950/30 px-6 text-center">
      <div className="mb-5 flex h-16 w-16 items-center justify-center rounded-2xl border border-indigo-400/15 bg-indigo-500/10">
        <BookOpen className="h-7 w-7 text-indigo-400" />
      </div>

      <h2 className="text-xl font-semibold text-slate-100">
        Create your first research notebook
      </h2>

      <p className="mt-2 max-w-xl text-sm leading-6 text-slate-500">
        Keep papers, sources, and AI conversations organized around a
        specific research topic. Each notebook becomes its own research
        workspace.
      </p>

      <button
        type="button"
        onClick={onCreate}
        className="mt-6 inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-indigo-500"
      >
        <Plus className="h-4 w-4" />
        Create Notebook
      </button>
    </div>
  );
}

export default ResearchNotebook;
