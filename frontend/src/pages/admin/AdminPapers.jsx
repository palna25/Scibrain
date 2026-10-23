
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import AdminLayout from "../../components/AdminLayout";
import {
  AlertCircle,
  BookOpen,
  CheckCircle2,
  Clock3,
  FileText,
  Loader2,
  RefreshCw,
  Search,
  Trash2,
  X,
} from "lucide-react";

const API_URL = "http://127.0.0.1:8000";

function formatDate(value) {
  if (!value) return "—";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return "—";

  return date.toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function getStatus(status) {
  const value = String(status || "uploaded").toLowerCase();

  if (value === "ready" || value === "analyzed") {
    return {
      label: value === "ready" ? "Ready" : "Analyzed",
      className: "border-emerald-500/20 bg-emerald-500/10 text-emerald-400",
    };
  }

  if (value === "processing") {
    return {
      label: "Processing",
      className: "border-amber-500/20 bg-amber-500/10 text-amber-400",
    };
  }

  if (value === "error" || value === "failed") {
    return {
      label: "Failed",
      className: "border-red-500/20 bg-red-500/10 text-red-400",
    };
  }

  return {
    label: value.charAt(0).toUpperCase() + value.slice(1),
    className: "border-slate-500/20 bg-slate-500/10 text-slate-400",
  };
}

export default function AdminPapers() {
  const navigate = useNavigate();

  const [papers, setPapers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [deletingId, setDeletingId] = useState(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [confirmPaper, setConfirmPaper] = useState(null);

  const getHeaders = useCallback(() => {
    const token = localStorage.getItem("scibrain_token");

    return {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    };
  }, []);

  const loadPapers = useCallback(async (isRefresh = false) => {
    if (isRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }

    setError("");

    try {
      const response = await fetch(`${API_URL}/api/admin/papers`, {
        method: "GET",
        headers: getHeaders(),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));

        if (response.status === 401 || response.status === 403) {
          throw new Error(
            data.detail || "You are not authorized to view administration data."
          );
        }

        throw new Error(data.detail || "Failed to load papers.");
      }

      const data = await response.json();
      setPapers(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err.message || "Unable to load papers. Check the backend connection.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [getHeaders]);

  useEffect(() => {
    loadPapers();
  }, [loadPapers]);

  const filteredPapers = useMemo(() => {
    const query = search.trim().toLowerCase();

    return papers.filter((paper) => {
      const matchesSearch =
        !query ||
        String(paper.title || "").toLowerCase().includes(query) ||
        String(paper.filename || "").toLowerCase().includes(query) ||
        String(paper.id || "").toLowerCase().includes(query);

      const status = String(paper.status || "uploaded").toLowerCase();
      const matchesStatus =
        statusFilter === "all" ||
        (statusFilter === "ready" && status === "ready") ||
        (statusFilter === "processing" && status === "processing") ||
        (statusFilter === "error" && ["error", "failed"].includes(status)) ||
        (statusFilter === "other" &&
          !["ready", "analyzed", "processing", "error", "failed"].includes(status));

      return matchesSearch && matchesStatus;
    });
  }, [papers, search, statusFilter]);

  const stats = useMemo(() => ({
    total: papers.length,
    ready: papers.filter((paper) =>
      ["ready", "analyzed"].includes(
        String(paper.status || "").toLowerCase()
      )
    ).length,
    processing: papers.filter(
      (paper) => String(paper.status || "").toLowerCase() === "processing"
    ).length,
    failed: papers.filter((paper) =>
      ["error", "failed"].includes(String(paper.status || "").toLowerCase())
    ).length,
  }), [papers]);

  async function deletePaper() {
    if (!confirmPaper) return;

    const paper = confirmPaper;
    setDeletingId(paper.id);
    setError("");
    setNotice("");

    try {
      const response = await fetch(
        `${API_URL}/api/admin/papers/${encodeURIComponent(paper.id)}`,
        {
          method: "DELETE",
          headers: getHeaders(),
        }
      );

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(data.detail || "Failed to delete paper.");
      }

      setPapers((current) =>
        current.filter((item) => item.id !== paper.id)
      );
      setNotice(`"${paper.title || paper.filename || "Paper"}" was deleted.`);
      setConfirmPaper(null);
    } catch (err) {
      setError(err.message || "Unable to delete this paper.");
      setConfirmPaper(null);
    } finally {
      setDeletingId(null);
    }
  }

  const statCards = [
    {
      label: "Total Papers",
      value: stats.total,
      icon: BookOpen,
      color: "text-indigo-400",
      background: "bg-indigo-500/10",
    },
    {
      label: "Ready",
      value: stats.ready,
      icon: CheckCircle2,
      color: "text-emerald-400",
      background: "bg-emerald-500/10",
    },
    {
      label: "Processing",
      value: stats.processing,
      icon: Clock3,
      color: "text-amber-400",
      background: "bg-amber-500/10",
    },
    {
      label: "Failed",
      value: stats.failed,
      icon: AlertCircle,
      color: "text-red-400",
      background: "bg-red-500/10",
    },
  ];

  return (
    <AdminLayout>
      <div className="min-h-screen space-y-6 p-4 text-slate-100 sm:p-6 lg:p-8">
        <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-indigo-400">
              Administration / Papers
            </p>
            <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
              Paper Management
            </h1>
            <p className="mt-2 text-sm text-slate-400">
              Review research papers stored in the SciBrain workspace.
            </p>
          </div>

          <button
            type="button"
            onClick={() => loadPapers(true)}
            disabled={refreshing || loading}
            className="inline-flex items-center justify-center gap-2 self-start rounded-xl border border-slate-700 bg-slate-900 px-4 py-2.5 text-sm font-medium text-slate-200 transition hover:border-indigo-500/50 hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50 sm:self-auto"
          >
            <RefreshCw
              size={16}
              className={refreshing ? "animate-spin" : ""}
            />
            Refresh
          </button>
        </div>

        {notice && (
          <div className="flex items-start justify-between gap-3 rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-300">
            <div className="flex items-center gap-2">
              <CheckCircle2 size={18} />
              {notice}
            </div>
            <button
              type="button"
              onClick={() => setNotice("")}
              aria-label="Dismiss success message"
            >
              <X size={16} />
            </button>
          </div>
        )}

        {error && (
          <div className="flex items-start justify-between gap-3 rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-300">
            <div className="flex items-start gap-2">
              <AlertCircle size={18} className="mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
            <button
              type="button"
              onClick={() => setError("")}
              aria-label="Dismiss error message"
            >
              <X size={16} />
            </button>
          </div>
        )}

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {statCards.map((stat) => {
            const Icon = stat.icon;

            return (
              <div
                key={stat.label}
                className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm text-slate-400">{stat.label}</span>
                  <span className={`rounded-xl p-2.5 ${stat.background}`}>
                    <Icon size={19} className={stat.color} />
                  </span>
                </div>
                <p className="mt-4 text-3xl font-semibold tracking-tight">
                  {loading ? "—" : stat.value}
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  {stat.label === "Total Papers"
                    ? "Records in the paper collection"
                    : `${stat.label} paper records`}
                </p>
              </div>
            );
          })}
        </div>

        <section className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/60">
          <div className="flex flex-col gap-4 border-b border-slate-800 p-4 sm:p-5 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <h2 className="font-semibold">Research Paper Library</h2>
              <p className="mt-1 text-sm text-slate-400">
                {filteredPapers.length} of {papers.length} papers displayed
              </p>
            </div>

            <div className="flex flex-col gap-3 sm:flex-row">
              <div className="relative min-w-0 sm:w-72">
                <Search
                  size={17}
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500"
                />
                <input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search title, filename, or ID..."
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 py-2.5 pl-10 pr-3 text-sm text-slate-200 outline-none placeholder:text-slate-500 focus:border-indigo-500"
                />
              </div>

              <select
                value={statusFilter}
                onChange={(event) => setStatusFilter(event.target.value)}
                className="rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm text-slate-200 outline-none focus:border-indigo-500"
                aria-label="Filter papers by status"
              >
                <option value="all">All statuses</option>
                <option value="ready">Ready</option>
                <option value="processing">Processing</option>
                <option value="error">Failed</option>
                <option value="other">Other</option>
              </select>
            </div>
          </div>

          {loading ? (
            <div className="flex min-h-64 items-center justify-center gap-3 text-sm text-slate-400">
              <Loader2 size={20} className="animate-spin text-indigo-400" />
              Loading research papers...
            </div>
          ) : error && papers.length === 0 ? (
            <div className="flex min-h-64 flex-col items-center justify-center px-6 text-center">
              <AlertCircle size={28} className="mb-3 text-red-400" />
              <p className="font-medium text-slate-200">
                Could not load papers
              </p>
              <p className="mt-2 max-w-md text-sm text-slate-400">
                Check the backend connection and your administrator session, then try again.
              </p>
              <button
                type="button"
                onClick={() => loadPapers(true)}
                className="mt-4 rounded-xl border border-slate-700 px-4 py-2 text-sm hover:bg-slate-800"
              >
                Try again
              </button>
            </div>
          ) : filteredPapers.length === 0 ? (
            <div className="flex min-h-64 flex-col items-center justify-center px-6 text-center">
              <FileText size={30} className="mb-3 text-slate-600" />
              <p className="font-medium text-slate-200">No papers found</p>
              <p className="mt-2 text-sm text-slate-400">
                {papers.length
                  ? "Try changing your search or status filter."
                  : "No paper records are currently available."}
              </p>
              {(search || statusFilter !== "all") && (
                <button
                  type="button"
                  onClick={() => {
                    setSearch("");
                    setStatusFilter("all");
                  }}
                  className="mt-4 text-sm text-indigo-400 hover:text-indigo-300"
                >
                  Clear filters
                </button>
              )}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[850px] text-left text-sm">
                <thead className="border-b border-slate-800 bg-slate-950/60 text-xs uppercase tracking-wider text-slate-500">
                  <tr>
                    <th className="px-5 py-4 font-medium">Paper</th>
                    <th className="px-5 py-4 font-medium">Pages</th>
                    <th className="px-5 py-4 font-medium">Status</th>
                    <th className="px-5 py-4 font-medium">Analysis</th>
                    <th className="px-5 py-4 font-medium">Uploaded</th>
                    <th className="px-5 py-4 text-right font-medium">Actions</th>
                  </tr>
                </thead>

                <tbody className="divide-y divide-slate-800/80">
                  {filteredPapers.map((paper) => {
                    const status = getStatus(paper.status);
                    const isDeleting = deletingId === paper.id;

                    return (
                      <tr
                        key={paper.id}
                        className="transition hover:bg-slate-800/30"
                      >
                        <td className="max-w-md px-5 py-4">
                          <div className="flex items-start gap-3">
                            <span className="mt-0.5 rounded-lg border border-indigo-500/20 bg-indigo-500/10 p-2">
                              <FileText size={18} className="text-indigo-400" />
                            </span>
                            <div className="min-w-0">
                              <p className="break-words font-medium text-slate-200">
                                {paper.title || "Untitled Paper"}
                              </p>
                              <p className="mt-1 break-all text-xs text-slate-500">
                                {paper.filename || "No filename"}
                              </p>
                              <p className="mt-1 text-xs text-slate-600">
                                ID: {paper.id}
                              </p>
                            </div>
                          </div>
                        </td>

                        <td className="px-5 py-4 text-slate-300">
                          {Number(paper.page_count) || "—"}
                        </td>

                        <td className="px-5 py-4">
                          <span
                            className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-medium ${status.className}`}
                          >
                            {status.label}
                          </span>
                        </td>

                        <td className="px-5 py-4">
                          {paper.has_analysis ? (
                            <span className="text-emerald-400">Available</span>
                          ) : (
                            <span className="text-slate-500">—</span>
                          )}
                        </td>

                        <td className="whitespace-nowrap px-5 py-4 text-slate-400">
                          {formatDate(paper.uploaded_at)}
                        </td>

                        <td className="px-5 py-4 text-right">
                          <button
                            type="button"
                            disabled={Boolean(deletingId)}
                            onClick={() => setConfirmPaper(paper)}
                            className="inline-flex items-center gap-2 rounded-lg border border-red-500/20 px-3 py-2 text-xs font-medium text-red-400 transition hover:border-red-500/40 hover:bg-red-500/10 disabled:cursor-not-allowed disabled:opacity-50"
                            aria-label={`Delete ${paper.title || paper.filename || "paper"}`}
                          >
                            {isDeleting ? (
                              <Loader2 size={15} className="animate-spin" />
                            ) : (
                              <Trash2 size={15} />
                            )}
                            Delete
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          <div className="flex flex-col gap-2 border-t border-slate-800 px-5 py-4 text-xs text-slate-500 sm:flex-row sm:items-center sm:justify-between">
            <span>Paper records from the SciBrain administration API.</span>
            <span>{filteredPapers.length} displayed</span>
          </div>
        </section>
      </div>

      {confirmPaper && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget && !deletingId) {
              setConfirmPaper(null);
            }
          }}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-paper-title"
            className="w-full max-w-md rounded-2xl border border-slate-700 bg-slate-900 p-6 shadow-2xl"
          >
            <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-red-500/10">
              <Trash2 size={22} className="text-red-400" />
            </div>

            <h2 id="delete-paper-title" className="text-lg font-semibold">
              Delete this paper?
            </h2>

            <p className="mt-3 break-words text-sm leading-6 text-slate-400">
              You are about to delete{" "}
              <span className="font-medium text-slate-200">
                {confirmPaper.title || confirmPaper.filename || "this paper"}
              </span>
              . This action may remove the paper and its associated research data.
              It cannot be undone.
            </p>

            <div className="mt-6 flex justify-end gap-3">
              <button
                type="button"
                disabled={Boolean(deletingId)}
                onClick={() => setConfirmPaper(null)}
                className="rounded-xl border border-slate-700 px-4 py-2.5 text-sm text-slate-300 hover:bg-slate-800 disabled:opacity-50"
              >
                Cancel
              </button>

              <button
                type="button"
                disabled={Boolean(deletingId)}
                onClick={deletePaper}
                className="inline-flex items-center gap-2 rounded-xl bg-red-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-red-500 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {deletingId ? (
                  <>
                    <Loader2 size={16} className="animate-spin" />
                    Deleting...
                  </>
                ) : (
                  <>
                    <Trash2 size={16} />
                    Delete paper
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </AdminLayout>
  );
}
