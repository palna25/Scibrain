import { useEffect, useRef, useState } from "react";
import {
  FileText,
  Upload,
  FolderOpen,
  Clock3,
  CheckCircle2,
  AlertCircle,
  Trash2,
  MoreHorizontal,
  Search,
  X,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import AppLayout from "../components/AppLayout";

const API_URL = "http://127.0.0.1:8000";

function Papers() {
  const fileInputRef = useRef(null);

  const [selectedFile, setSelectedFile] = useState(null);
  const [papers, setPapers] = useState([]);
  const [searchQuery, setSearchQuery] = useState("");

  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [loadingPapers, setLoadingPapers] = useState(true);

  const [error, setError] = useState("");
  // --------------------------------------------------
  // Load papers from FastAPI
  // --------------------------------------------------

  const fetchPapers = async () => {
    try {
      setLoadingPapers(true);
      setError("");

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
      console.error("Failed to fetch papers:", error);
      setError(error.message || "Failed to load papers.");
    } finally {
      setLoadingPapers(false);
    }
  };

  useEffect(() => {
    fetchPapers();
  }, []);

  // --------------------------------------------------
  // File validation
  // --------------------------------------------------

  const handleFileSelect = (file) => {
    setError("");

    if (!file) return;

    if (
      file.type !== "application/pdf" &&
      !file.name.toLowerCase().endsWith(".pdf")
    ) {
      setError("Only PDF files are supported.");
      return;
    }

    const maxSize = 20 * 1024 * 1024;

    if (file.size > maxSize) {
      setError("File size must be less than 20 MB.");
      return;
    }

    setSelectedFile(file);
  };

  const handleInputChange = (e) => {
    const file = e.target.files?.[0];

    if (file) {
      handleFileSelect(file);
    }
  };

  // --------------------------------------------------
  // Drag and Drop
  // --------------------------------------------------

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);

    const file = e.dataTransfer.files?.[0];

    if (file) {
      handleFileSelect(file);
    }
  };

  // --------------------------------------------------
  // Upload PDF
  // --------------------------------------------------

  const handleUpload = async () => {
    if (!selectedFile) return;

    setUploading(true);
    setError("");

    try {
      const formData = new FormData();
      formData.append("file", selectedFile);

      const token = localStorage.getItem("scibrain_token");

      const response = await fetch(`${API_URL}/api/papers/upload`, {
        method: "POST",
        headers: token
          ? {
              Authorization: `Bearer ${token}`,
            }
          : {},
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Failed to upload paper.");
      }

      // Clear selected file
      setSelectedFile(null);

      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }

      // Reload papers from backend
      await fetchPapers();
    } catch (error) {
      console.error("Upload failed:", error);
      setError(error.message || "Failed to upload paper.");
    } finally {
      setUploading(false);
    }
  };

  // --------------------------------------------------
  // Remove selected file
  // --------------------------------------------------

  const removeSelectedFile = () => {
    setSelectedFile(null);
    setError("");

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  // --------------------------------------------------
  // Search
  // --------------------------------------------------

  const filteredPapers = papers.filter((paper) => {
    const searchText = `${paper.title} ${paper.filename}`.toLowerCase();

    return searchText.includes(searchQuery.toLowerCase());
  });

  // --------------------------------------------------
  // Statistics
  // --------------------------------------------------

  const processedCount = papers.filter(
    (paper) => paper.status.toLowerCase() === "processed"
  ).length;

  const uploadedCount = papers.filter(
    (paper) => paper.status.toLowerCase() === "uploaded"
  ).length;

  return (
    <AppLayout>
      {/* Page Header */}
      <div className="mb-8">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.25em] text-indigo-400">
              Research Workspace
            </p>

            <h1 className="text-3xl font-semibold tracking-tight text-white">
              Research Papers
            </h1>

            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
              Upload and manage academic papers to build your
              research intelligence workspace.
            </p>
          </div>

          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="flex items-center justify-center gap-2 rounded-xl bg-indigo-500 px-4 py-2.5 text-sm font-medium text-white shadow-lg shadow-indigo-500/20 transition hover:bg-indigo-400"
          >
            <Upload className="h-4 w-4" />
            Upload Paper
          </button>
        </div>
      </div>

      {/* Statistics */}
      <div className="grid gap-4 md:grid-cols-3">
        <InfoCard
          icon={FileText}
          label="Total Papers"
          value={papers.length}
          description="Papers in workspace"
        />

        <InfoCard
          icon={CheckCircle2}
          label="Processed"
          value={processedCount}
          description="Ready for analysis"
        />

        <InfoCard
          icon={Clock3}
          label="Uploaded"
          value={uploadedCount}
          description="Waiting for analysis"
        />
      </div>

      {/* Upload Section */}
      <section className="mt-6 overflow-hidden rounded-2xl border border-white/[0.07] bg-slate-900/50">
        <div className="border-b border-white/[0.06] px-6 py-5">
          <p className="text-[10px] font-medium uppercase tracking-[0.2em] text-indigo-400">
            Add Research
          </p>

          <h2 className="mt-2 text-base font-semibold text-white">
            Upload a research paper
          </h2>

          <p className="mt-1 text-xs text-slate-500">
            PDF files up to 20 MB are supported.
          </p>
        </div>

        <div className="p-6">
          {!selectedFile ? (
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setIsDragging(true);
              }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`group flex min-h-[230px] cursor-pointer flex-col items-center justify-center rounded-2xl border border-dashed px-6 text-center transition ${
                isDragging
                  ? "border-indigo-400 bg-indigo-500/[0.08]"
                  : "border-white/[0.10] bg-slate-950/40 hover:border-indigo-400/30 hover:bg-indigo-500/[0.03]"
              }`}
            >
              <div className="relative mb-5 flex h-14 w-14 items-center justify-center rounded-2xl border border-indigo-400/15 bg-indigo-500/10">
                <div className="absolute inset-0 rounded-2xl bg-indigo-500/10 blur-xl" />

                <Upload className="relative h-6 w-6 text-indigo-400 transition group-hover:-translate-y-0.5" />
              </div>

              <h3 className="text-sm font-medium text-slate-200">
                Drop your research paper here
              </h3>

              <p className="mt-2 text-xs text-slate-500">
                or click to browse from your computer
              </p>

              <div className="mt-4 rounded-lg border border-white/[0.06] bg-slate-900 px-3 py-1.5 text-[10px] text-slate-500">
                PDF · Maximum 20 MB
              </div>
            </div>
          ) : (
            <SelectedFile
              file={selectedFile}
              uploading={uploading}
              onRemove={removeSelectedFile}
              onUpload={handleUpload}
            />
          )}

          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf,.pdf"
            onChange={handleInputChange}
            className="hidden"
          />

          {error && (
            <div className="mt-4 flex items-center gap-2 rounded-xl border border-red-400/15 bg-red-400/[0.05] px-4 py-3 text-sm text-red-300">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}
        </div>
      </section>

      {/* Papers Section */}
      <section className="mt-6 rounded-2xl border border-white/[0.07] bg-slate-900/50">
        <div className="flex flex-col gap-4 border-b border-white/[0.06] px-6 py-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-[10px] font-medium uppercase tracking-[0.2em] text-indigo-400">
              Your Library
            </p>

            <h2 className="mt-2 text-base font-semibold text-white">
              My Papers
            </h2>
          </div>

          {papers.length > 0 && (
            <div className="relative w-full sm:w-64">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-600" />

              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search papers..."
                className="h-9 w-full rounded-xl border border-white/[0.07] bg-slate-950/70 pl-9 pr-3 text-xs text-slate-200 outline-none transition placeholder:text-slate-600 focus:border-indigo-400/20 focus:ring-1 focus:ring-indigo-400/10"
              />
            </div>
          )}
        </div>

        <div className="p-6">
          {loadingPapers ? (
            <LoadingPapers />
          ) : filteredPapers.length === 0 ? (
            <EmptyPapers />
          ) : (
            <div className="space-y-3">
              {filteredPapers.map((paper) => (
                <PaperItem key={paper.id} paper={paper} />
              ))}
            </div>
          )}
        </div>
      </section>
    </AppLayout>
  );
}

// --------------------------------------------------
// Information Card
// --------------------------------------------------

function InfoCard({
  icon: Icon,
  label,
  value,
  description,
}) {
  return (
    <div className="group rounded-2xl border border-white/[0.07] bg-slate-900/50 p-5 transition hover:border-indigo-400/20 hover:bg-slate-900/80">
      <div className="flex items-start justify-between">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-indigo-400/15 bg-indigo-500/10">
          <Icon className="h-5 w-5 text-indigo-400" />
        </div>

        <span className="text-xs text-slate-700">
          SciBrain
        </span>
      </div>

      <div className="mt-5">
        <p className="text-2xl font-semibold tracking-tight text-white">
          {value}
        </p>

        <p className="mt-1 text-sm text-slate-400">
          {label}
        </p>

        <p className="mt-2 text-xs text-slate-500">
          {description}
        </p>
      </div>
    </div>
  );
}

// --------------------------------------------------
// Selected File
// --------------------------------------------------

function SelectedFile({
  file,
  uploading,
  onRemove,
  onUpload,
}) {
  return (
    <div className="rounded-2xl border border-indigo-400/15 bg-indigo-500/[0.04] p-5">
      <div className="flex items-center gap-4">
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-red-400/15 bg-red-400/[0.06]">
          <FileText className="h-5 w-5 text-red-300" />
        </div>

        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-slate-200">
            {file.name}
          </p>

          <p className="mt-1 text-xs text-slate-500">
            {formatFileSize(file.size)} · PDF
          </p>
        </div>

        {!uploading && (
          <button
            type="button"
            onClick={onRemove}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-slate-600 transition hover:bg-white/[0.05] hover:text-slate-300"
            aria-label="Remove selected file"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:justify-end">
        <button
          type="button"
          onClick={onRemove}
          disabled={uploading}
          className="rounded-xl border border-white/[0.08] px-4 py-2.5 text-xs font-medium text-slate-400 transition hover:bg-white/[0.03] hover:text-slate-200 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Choose another
        </button>

        <button
          type="button"
          onClick={onUpload}
          disabled={uploading}
          className="flex items-center justify-center gap-2 rounded-xl bg-indigo-500 px-5 py-2.5 text-xs font-medium text-white shadow-lg shadow-indigo-500/20 transition hover:bg-indigo-400 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {uploading ? (
            <>
              <Clock3 className="h-4 w-4 animate-spin" />
              Processing...
            </>
          ) : (
            <>
              <Upload className="h-4 w-4" />
              Upload Paper
            </>
          )}
        </button>
      </div>
    </div>
  );
}

// --------------------------------------------------
// Paper Item
// --------------------------------------------------

function PaperItem({ paper }) {
  const navigate = useNavigate();

  const isProcessed =
    paper.status?.toLowerCase() === "processed";

  const uploadedDate = paper.uploadedAt
    ? new Date(paper.uploadedAt).toLocaleDateString(
        "en-IN",
        {
          day: "2-digit",
          month: "short",
          year: "numeric",
        }
      )
    : "Unknown";

  return (
    <div
      onClick={() => navigate(`/papers/${paper.id}`)}
      className="group flex cursor-pointer items-center gap-4 rounded-xl border border-white/[0.06] bg-slate-950/50 px-4 py-4 transition hover:border-indigo-400/20 hover:bg-slate-950/80"
    >
      <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-indigo-400/10 bg-indigo-500/[0.06]">
        <FileText className="h-5 w-5 text-indigo-400 transition group-hover:scale-105" />
      </div>

      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-slate-200 transition group-hover:text-indigo-300">
          {paper.title || paper.filename}
        </p>

        <div className="mt-1 flex flex-wrap items-center gap-2 text-[10px] text-slate-600">
          {paper.pageCount > 0 && (
            <>
              <span>
                {paper.pageCount}{" "}
                {paper.pageCount === 1 ? "page" : "pages"}
              </span>

              <span className="h-1 w-1 rounded-full bg-slate-700" />
            </>
          )}

          <span>
            {formatTextLength(paper.textLength)}
          </span>

          <span className="h-1 w-1 rounded-full bg-slate-700" />

          <span>
            Uploaded {uploadedDate}
          </span>
        </div>
      </div>

      <div className="hidden items-center gap-2 sm:flex">
        {isProcessed ? (
          <span className="flex items-center gap-1.5 rounded-full border border-emerald-400/10 bg-emerald-400/[0.05] px-2.5 py-1 text-[10px] text-emerald-300">
            <CheckCircle2 className="h-3 w-3" />
            Processed
          </span>
        ) : (
          <span className="flex items-center gap-1.5 rounded-full border border-amber-400/10 bg-amber-400/[0.05] px-2.5 py-1 text-[10px] text-amber-300">
            <Clock3 className="h-3 w-3" />
            Uploaded
          </span>
        )}
      </div>

      <button
        type="button"
        disabled
        onClick={(e) => e.stopPropagation()}
        className="flex h-8 w-8 shrink-0 cursor-not-allowed items-center justify-center rounded-lg text-slate-800"
        title="Delete will be added later"
      >
        <Trash2 className="h-4 w-4" />
      </button>

      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
        }}
        className="hidden h-8 w-8 shrink-0 items-center justify-center rounded-lg text-slate-700 transition hover:bg-white/[0.04] hover:text-slate-300 sm:flex"
        title="More options"
      >
        <MoreHorizontal className="h-4 w-4" />
      </button>
    </div>
  );
}

// --------------------------------------------------
// Loading
// --------------------------------------------------

function LoadingPapers() {
  return (
    <div className="flex min-h-[280px] flex-col items-center justify-center text-center">
      <Clock3 className="h-7 w-7 animate-spin text-indigo-400" />

      <p className="mt-4 text-sm text-slate-400">
        Loading your research papers...
      </p>
    </div>
  );
}

// --------------------------------------------------
// Empty State
// --------------------------------------------------

function EmptyPapers() {
  return (
    <div className="flex min-h-[280px] flex-col items-center justify-center text-center">
      <div className="relative mb-5 flex h-16 w-16 items-center justify-center rounded-2xl border border-indigo-400/15 bg-indigo-500/10">
        <div className="absolute inset-0 rounded-2xl bg-indigo-500/10 blur-xl" />

        <FolderOpen className="relative h-7 w-7 text-indigo-400" />
      </div>

      <h3 className="text-sm font-medium text-slate-300">
        No research papers yet
      </h3>

      <p className="mx-auto mt-2 max-w-sm text-xs leading-5 text-slate-500">
        Upload your first academic paper to begin building
        your research library and uncovering meaningful
        connections.
      </p>
    </div>
  );
}

// --------------------------------------------------
// Helpers
// --------------------------------------------------

function formatFileSize(bytes) {
  if (!bytes) return "0 Bytes";

  const units = ["Bytes", "KB", "MB", "GB"];

  const index = Math.min(
    Math.floor(Math.log(bytes) / Math.log(1024)),
    units.length - 1
  );

  return `${(bytes / Math.pow(1024, index)).toFixed(1)} ${
    units[index]
  }`;
}

function formatTextLength(length) {
  if (!length) return "No extracted text";

  if (length >= 1000) {
    return `${(length / 1000).toFixed(1)}k characters`;
  }

  return `${length} characters`;
}

export default Papers;