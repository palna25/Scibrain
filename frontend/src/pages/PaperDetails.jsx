import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  FileText,
  Clock3,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";

import AppLayout from "../components/AppLayout";

const API_URL = "http://127.0.0.1:8000";

function PaperDetails() {
  const { paperId } = useParams();
  const navigate = useNavigate();

  const [paper, setPaper] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const fetchPaper = async () => {
      try {
        setLoading(true);
        setError("");

        const response = await fetch(
          `${API_URL}/api/papers/${paperId}`
        );

        const data = await response.json();

        if (!response.ok) {
          throw new Error(
            data.detail || "Failed to load paper."
          );
        }

        setPaper(data);
      } catch (error) {
        console.error("Failed to load paper:", error);
        setError(
          error.message || "Failed to load paper."
        );
      } finally {
        setLoading(false);
      }
    };

    fetchPaper();
  }, [paperId]);

  if (loading) {
    return (
      <AppLayout>
        <div className="flex min-h-[70vh] flex-col items-center justify-center">
          <Clock3 className="h-7 w-7 animate-spin text-indigo-400" />

          <p className="mt-4 text-sm text-slate-400">
            Loading paper...
          </p>
        </div>
      </AppLayout>
    );
  }

  if (error) {
    return (
      <AppLayout>
        <div className="flex min-h-[70vh] flex-col items-center justify-center text-center">
          <AlertCircle className="h-8 w-8 text-red-400" />

          <h2 className="mt-4 text-lg font-semibold text-white">
            Unable to load paper
          </h2>

          <p className="mt-2 text-sm text-slate-500">
            {error}
          </p>

          <button
            onClick={() => navigate("/papers")}
            className="mt-6 rounded-xl bg-indigo-500 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-indigo-400"
          >
            Back to Papers
          </button>
        </div>
      </AppLayout>
    );
  }

  if (!paper) return null;

  const isProcessed =
    paper.status?.toLowerCase() === "processed";

  const uploadedDate = paper.uploaded_at
    ? new Date(paper.uploaded_at).toLocaleDateString(
        "en-IN",
        {
          day: "2-digit",
          month: "short",
          year: "numeric",
        }
      )
    : "Unknown";

  return (
    <AppLayout>
      {/* Back */}
      <button
        onClick={() => navigate("/papers")}
        className="mb-6 flex items-center gap-2 text-sm text-slate-500 transition hover:text-slate-200"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Papers
      </button>

      {/* Header */}
      <div className="mb-8">
        <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.25em] text-indigo-400">
          Research Paper
        </p>

        <div className="flex items-start gap-4">
          <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl border border-indigo-400/15 bg-indigo-500/10">
            <FileText className="h-6 w-6 text-indigo-400" />
          </div>

          <div className="min-w-0">
            <h1 className="text-3xl font-semibold tracking-tight text-white">
              {paper.title || paper.filename}
            </h1>

            <p className="mt-2 text-sm text-slate-500">
              {paper.filename}
            </p>
          </div>
        </div>
      </div>

      {/* Metadata */}
      <div className="grid gap-4 md:grid-cols-3">
        <InfoCard
          label="Pages"
          value={paper.page_count || 0}
        />

        <InfoCard
          label="Extracted Text"
          value={formatTextLength(
            paper.text_length
          )}
        />

        <div className="rounded-2xl border border-white/[0.07] bg-slate-900/50 p-5">
          <p className="text-xs text-slate-500">
            Status
          </p>

          <div className="mt-3">
            {isProcessed ? (
              <span className="inline-flex items-center gap-2 rounded-full border border-emerald-400/10 bg-emerald-400/[0.05] px-3 py-1.5 text-xs text-emerald-300">
                <CheckCircle2 className="h-4 w-4" />
                Processed
              </span>
            ) : (
              <span className="inline-flex items-center gap-2 rounded-full border border-amber-400/10 bg-amber-400/[0.05] px-3 py-1.5 text-xs text-amber-300">
                <Clock3 className="h-4 w-4" />
                Uploaded
              </span>
            )}
          </div>

          <p className="mt-3 text-xs text-slate-600">
            Uploaded {uploadedDate}
          </p>
        </div>
      </div>

      {/* Paper Text */}
      <section className="mt-6 overflow-hidden rounded-2xl border border-white/[0.07] bg-slate-900/50">
        <div className="border-b border-white/[0.06] px-6 py-5">
          <p className="text-[10px] font-medium uppercase tracking-[0.2em] text-indigo-400">
            Extracted Content
          </p>

          <h2 className="mt-2 text-base font-semibold text-white">
            Paper Text
          </h2>

          <p className="mt-1 text-xs text-slate-500">
            Text extracted from the uploaded PDF.
          </p>
        </div>

        <div className="max-h-[650px] overflow-y-auto p-6">
          {paper.text ? (
            <pre className="whitespace-pre-wrap font-sans text-sm leading-7 text-slate-400">
              {paper.text}
            </pre>
          ) : (
            <div className="flex min-h-[200px] items-center justify-center text-center">
              <p className="text-sm text-slate-600">
                No text could be extracted from this paper.
              </p>
            </div>
          )}
        </div>
      </section>
    </AppLayout>
  );
}

function InfoCard({ label, value }) {
  return (
    <div className="rounded-2xl border border-white/[0.07] bg-slate-900/50 p-5">
      <p className="text-xs text-slate-500">
        {label}
      </p>

      <p className="mt-3 text-2xl font-semibold text-white">
        {value}
      </p>
    </div>
  );
}

function formatTextLength(length) {
  if (!length) return "0 characters";

  if (length >= 1000) {
    return `${(length / 1000).toFixed(1)}k`;
  }

  return `${length}`;
}

export default PaperDetails;