import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  FileText,
  Clock3,
  CheckCircle2,
  AlertCircle,
  BookOpen,
  Database,
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
        console.error(
          "Failed to load paper:",
          error
        );

        setError(
          error.message ||
            "Failed to load paper."
        );
      } finally {
        setLoading(false);
      }
    };

    fetchPaper();
  }, [paperId]);

  // --------------------------------------------------
  // Format extracted text
  // --------------------------------------------------

  const formattedSections = useMemo(() => {
    if (!paper?.text) {
      return [];
    }

    return formatPaperText(paper.text);
  }, [paper?.text]);

  const uploadedDate = paper?.uploaded_at
    ? new Date(
        paper.uploaded_at
      ).toLocaleDateString("en-IN", {
        day: "2-digit",
        month: "short",
        year: "numeric",
      })
    : "Unknown";

  const status =
    paper?.status?.toLowerCase();

  const isReady = status === "ready";
  const isProcessing =
    status === "processing";
  const isError = status === "error";

  // --------------------------------------------------
  // Loading
  // --------------------------------------------------

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

  // --------------------------------------------------
  // Error
  // --------------------------------------------------

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
            onClick={() =>
              navigate("/papers")
            }
            className="mt-6 rounded-xl bg-indigo-500 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-indigo-400"
          >
            Back to Papers
          </button>
        </div>
      </AppLayout>
    );
  }

  if (!paper) {
    return null;
  }

  return (
    <AppLayout>
      {/* Back */}

      <button
        onClick={() =>
          navigate("/papers")
        }
        className="mb-6 flex items-center gap-2 text-sm text-slate-500 transition hover:text-slate-200"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Papers
      </button>

      {/* Header */}

      <div className="mb-8">
        <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.25em] text-indigo-400">
          Research Resource
        </p>

        <div className="flex items-start gap-4">
          <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl border border-indigo-400/15 bg-indigo-500/10">
            <FileText className="h-6 w-6 text-indigo-400" />
          </div>

          <div className="min-w-0">
            <h1 className="text-3xl font-semibold tracking-tight text-white">
              {paper.title ||
                paper.filename}
            </h1>

            <p className="mt-2 text-sm text-slate-500">
              {paper.filename}
            </p>
          </div>
        </div>
      </div>

      {/* Metadata */}

      <div className="grid gap-4 md:grid-cols-4">
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

        <InfoCard
          label="Indexed Chunks"
          value={paper.indexed_chunks || 0}
          icon={Database}
        />

        <StatusCard
          status={status}
          uploadedDate={uploadedDate}
          isReady={isReady}
          isProcessing={isProcessing}
          isError={isError}
        />
      </div>

      {/* Research readiness */}

      {isReady && (
        <div className="mt-6 flex items-start gap-3 rounded-2xl border border-emerald-400/10 bg-emerald-400/[0.04] px-5 py-4">
          <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-400" />

          <div>
            <p className="text-sm font-medium text-emerald-300">
              Ready for research
            </p>

            <p className="mt-1 text-xs leading-5 text-slate-500">
              This resource has been extracted,
              chunked, embedded, and indexed in
              Qdrant. It can now be selected in
              Research Notebook, Knowledge Graph,
              and Research Gaps.
            </p>
          </div>
        </div>
      )}

      {isProcessing && (
        <div className="mt-6 flex items-start gap-3 rounded-2xl border border-amber-400/10 bg-amber-400/[0.04] px-5 py-4">
          <Clock3 className="mt-0.5 h-5 w-5 shrink-0 text-amber-400" />

          <div>
            <p className="text-sm font-medium text-amber-300">
              Indexing resource
            </p>

            <p className="mt-1 text-xs leading-5 text-slate-500">
              The paper text has been extracted and
              is currently being prepared for semantic
              search.
            </p>
          </div>
        </div>
      )}

      {isError && (
        <div className="mt-6 flex items-start gap-3 rounded-2xl border border-red-400/10 bg-red-400/[0.04] px-5 py-4">
          <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-red-400" />

          <div>
            <p className="text-sm font-medium text-red-300">
              Resource indexing failed
            </p>

            <p className="mt-1 text-xs leading-5 text-slate-500">
              {paper.processing_error ||
                "An error occurred while preparing this paper for research."}
            </p>
          </div>
        </div>
      )}

      {/* Paper Text */}

      <section className="mt-6 overflow-hidden rounded-2xl border border-white/[0.07] bg-slate-900/50">
        <div className="border-b border-white/[0.06] px-6 py-5">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-indigo-400/10 bg-indigo-500/[0.06]">
              <BookOpen className="h-4 w-4 text-indigo-400" />
            </div>

            <div>
              <p className="text-[10px] font-medium uppercase tracking-[0.2em] text-indigo-400">
                Extracted Content
              </p>

              <h2 className="mt-1 text-base font-semibold text-white">
                Paper Text
              </h2>
            </div>
          </div>

          <p className="mt-3 text-xs leading-5 text-slate-500">
            Text extracted from the original
            research paper. The content is stored
            as a research resource and retrieved
            contextually when you ask questions.
          </p>
        </div>

        <div className="max-h-[750px] overflow-y-auto">
          {formattedSections.length > 0 ? (
            <div className="divide-y divide-white/[0.05]">
              {formattedSections.map(
                (section, index) => (
                  <article
                    key={`${section.title}-${index}`}
                    className="px-6 py-7"
                  >
                    {section.title ? (
                      <h3 className="mb-4 text-lg font-semibold tracking-tight text-white">
                        {section.title}
                      </h3>
                    ) : null}

                    <div className="space-y-4">
                      {section.paragraphs.map(
                        (
                          paragraph,
                          paragraphIndex
                        ) => (
                          <p
                            key={
                              paragraphIndex
                            }
                            className="text-sm leading-7 text-slate-400"
                          >
                            {paragraph}
                          </p>
                        )
                      )}
                    </div>
                  </article>
                )
              )}
            </div>
          ) : (
            <div className="flex min-h-[250px] items-center justify-center px-6 text-center">
              <div>
                <FileText className="mx-auto h-8 w-8 text-slate-700" />

                <p className="mt-4 text-sm text-slate-600">
                  No text could be extracted
                  from this paper.
                </p>
              </div>
            </div>
          )}
        </div>
      </section>
    </AppLayout>
  );
}


// =========================================================
// STATUS CARD
// =========================================================

function StatusCard({
  status,
  uploadedDate,
  isReady,
  isProcessing,
  isError,
}) {
  return (
    <div className="rounded-2xl border border-white/[0.07] bg-slate-900/50 p-5">
      <p className="text-xs text-slate-500">
        Status
      </p>

      <div className="mt-3">
        {isReady && (
          <span className="inline-flex items-center gap-2 rounded-full border border-emerald-400/10 bg-emerald-400/[0.05] px-3 py-1.5 text-xs text-emerald-300">
            <CheckCircle2 className="h-4 w-4" />
            Ready
          </span>
        )}

        {isProcessing && (
          <span className="inline-flex items-center gap-2 rounded-full border border-amber-400/10 bg-amber-400/[0.05] px-3 py-1.5 text-xs text-amber-300">
            <Clock3 className="h-4 w-4" />
            Indexing
          </span>
        )}

        {isError && (
          <span className="inline-flex items-center gap-2 rounded-full border border-red-400/10 bg-red-400/[0.05] px-3 py-1.5 text-xs text-red-300">
            <AlertCircle className="h-4 w-4" />
            Error
          </span>
        )}

        {!isReady &&
          !isProcessing &&
          !isError && (
            <span className="text-xs text-slate-400">
              {status || "Unknown"}
            </span>
          )}
      </div>

      <p className="mt-3 text-xs text-slate-600">
        Uploaded {uploadedDate}
      </p>
    </div>
  );
}


// =========================================================
// INFO CARD
// =========================================================

function InfoCard({
  label,
  value,
  icon: Icon,
}) {
  return (
    <div className="rounded-2xl border border-white/[0.07] bg-slate-900/50 p-5">
      <div className="flex items-center justify-between">
        <p className="text-xs text-slate-500">
          {label}
        </p>

        {Icon && (
          <Icon className="h-4 w-4 text-indigo-400" />
        )}
      </div>

      <p className="mt-3 text-2xl font-semibold text-white">
        {value}
      </p>
    </div>
  );
}


// =========================================================
// FORMAT PAPER TEXT
// =========================================================

function formatPaperText(text) {
  if (!text || typeof text !== "string") {
    return [];
  }

  let cleaned = text
    .replace(/\r\n/g, "\n")
    .replace(/\r/g, "\n")
    .replace(/[ \t]+/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();

  if (!cleaned) {
    return [];
  }

  const headingPattern =
    /^(abstract|introduction|background|related work|literature review|methodology|methods|materials and methods|proposed method|proposed methodology|experimental setup|experiments|results|discussion|results and discussion|conclusion|conclusions|limitations|future work|references|acknowledgments|acknowledgements)$/i;

  const lines = cleaned
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

  const sections = [];

  let currentSection = {
    title: "",
    paragraphs: [],
  };

  let paragraphBuffer = [];

  const flushParagraph = () => {
    if (paragraphBuffer.length === 0) {
      return;
    }

    const paragraph =
      paragraphBuffer.join(" ").trim();

    if (paragraph) {
      currentSection.paragraphs.push(
        paragraph
      );
    }

    paragraphBuffer = [];
  };

  const flushSection = () => {
    flushParagraph();

    if (
      currentSection.title ||
      currentSection.paragraphs.length > 0
    ) {
      sections.push(currentSection);
    }

    currentSection = {
      title: "",
      paragraphs: [],
    };
  };

  lines.forEach((line) => {
    const normalizedLine = line
      .replace(/^[0-9]+[.)]\s*/, "")
      .trim();

    if (
      headingPattern.test(
        normalizedLine
      )
    ) {
      flushSection();

      currentSection.title =
        normalizedLine;

      return;
    }

    const numberedHeading =
      normalizedLine.match(
        /^\d+(?:\.\d+)*\.?\s+([A-Z][A-Za-z &-]{2,60})$/
      );

    if (numberedHeading) {
      const possibleTitle =
        numberedHeading[1].trim();

      if (
        possibleTitle.length < 60 &&
        !/[.!?]$/.test(
          possibleTitle
        )
      ) {
        flushSection();

        currentSection.title =
          possibleTitle;

        return;
      }
    }

    if (paragraphBuffer.length > 0) {
      const previousLine =
        paragraphBuffer[
          paragraphBuffer.length - 1
        ];

      if (
        previousLine.length > 120 &&
        /^[A-Z]/.test(
          normalizedLine
        )
      ) {
        flushParagraph();
      }
    }

    paragraphBuffer.push(
      normalizedLine
    );
  });

  flushSection();

  if (
    sections.length === 1 &&
    !sections[0].title
  ) {
    const fullText =
      sections[0].paragraphs.join(
        " "
      );

    const paragraphs = fullText
      .split(
        /(?<=[.!?])\s+(?=[A-Z])/
      )
      .map((paragraph) =>
        paragraph.trim()
      )
      .filter(Boolean);

    return [
      {
        title: "",
        paragraphs:
          paragraphs.length > 0
            ? paragraphs
            : [fullText],
      },
    ];
  }

  return sections;
}


// =========================================================
// TEXT LENGTH
// =========================================================

function formatTextLength(length) {
  if (!length) {
    return "0 characters";
  }

  if (length >= 1000) {
    return `${(
      length / 1000
    ).toFixed(1)}k`;
  }

  return `${length} characters`;
}

export default PaperDetails;