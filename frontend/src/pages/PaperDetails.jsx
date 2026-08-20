import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  FileText,
  Clock3,
  CheckCircle2,
  AlertCircle,
  BookOpen,
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

  /*
   * IMPORTANT:
   * This hook must remain BEFORE all early returns.
   */
  const formattedSections = useMemo(() => {
    if (!paper?.text) {
      return [];
    }

    return formatPaperText(paper.text);
  }, [paper?.text]);

  const uploadedDate = paper?.uploaded_at
    ? new Date(paper.uploaded_at).toLocaleDateString(
        "en-IN",
        {
          day: "2-digit",
          month: "short",
          year: "numeric",
        }
      )
    : "Unknown";

  const isProcessed =
    paper?.status?.toLowerCase() === "processed" ||
    paper?.status?.toLowerCase() === "analyzed";

  /* ================= LOADING ================= */

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

  /* ================= ERROR ================= */

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

  if (!paper) {
    return null;
  }

  return (
    <AppLayout>
      {/* ================= BACK ================= */}

      <button
        onClick={() => navigate("/papers")}
        className="mb-6 flex items-center gap-2 text-sm text-slate-500 transition hover:text-slate-200"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Papers
      </button>

      {/* ================= HEADER ================= */}

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

      {/* ================= METADATA ================= */}

      <div className="grid gap-4 md:grid-cols-3">
        <InfoCard
          label="Pages"
          value={paper.page_count || 0}
        />

        <InfoCard
          label="Extracted Text"
          value={formatTextLength(paper.text_length)}
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

      {/* ================= PAPER TEXT ================= */}

      <section className="mt-6 overflow-hidden rounded-2xl border border-white/[0.07] bg-slate-900/50">
        {/* Section header */}

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
            Structured text extracted from the uploaded research paper.
          </p>
        </div>

        {/* Text */}

        <div className="max-h-[750px] overflow-y-auto">
          {formattedSections.length > 0 ? (
            <div className="divide-y divide-white/[0.05]">
              {formattedSections.map((section, index) => (
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
                      (paragraph, paragraphIndex) => (
                        <p
                          key={paragraphIndex}
                          className="text-sm leading-7 text-slate-400"
                        >
                          {paragraph}
                        </p>
                      )
                    )}
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="flex min-h-[250px] items-center justify-center px-6 text-center">
              <div>
                <FileText className="mx-auto h-8 w-8 text-slate-700" />

                <p className="mt-4 text-sm text-slate-600">
                  No text could be extracted from this paper.
                </p>
              </div>
            </div>
          )}
        </div>
      </section>
    </AppLayout>
  );
}

/* =========================================================
   FORMAT PAPER TEXT
   ========================================================= */

function formatPaperText(text) {
  if (!text || typeof text !== "string") {
    return [];
  }

  /*
   * Normalize PDF extraction artifacts.
   */

  let cleaned = text
    .replace(/\r\n/g, "\n")
    .replace(/\r/g, "\n")
    .replace(/[ \t]+/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();

  if (!cleaned) {
    return [];
  }

  /*
   * Common academic-paper section headings.
   *
   * We only format headings that are actually present
   * in the extracted text.
   *
   * We are NOT inventing content.
   */

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

    const paragraph = paragraphBuffer.join(" ").trim();

    if (paragraph) {
      currentSection.paragraphs.push(paragraph);
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

    /*
     * Detect actual section headings.
     */

    if (headingPattern.test(normalizedLine)) {
      flushSection();

      currentSection.title = normalizedLine;

      return;
    }

    /*
     * Detect numbered headings such as:
     *
     * 1 Introduction
     * 2. Methodology
     * 3 Results
     */

    const numberedHeading =
      normalizedLine.match(
        /^\d+(?:\.\d+)*\.?\s+([A-Z][A-Za-z &-]{2,60})$/
      );

    if (numberedHeading) {
      const possibleTitle =
        numberedHeading[1].trim();

      if (
        possibleTitle.length < 60 &&
        !/[.!?]$/.test(possibleTitle)
      ) {
        flushSection();

        currentSection.title = possibleTitle;

        return;
      }
    }

    /*
     * If the PDF extractor already separated paragraphs,
     * preserve those paragraph boundaries.
     */

    if (paragraphBuffer.length > 0) {
      const previousLine =
        paragraphBuffer[paragraphBuffer.length - 1];

      /*
       * A new line beginning with a capitalized sentence
       * after a reasonably long line is usually a new
       * extracted paragraph.
       */

      if (
        previousLine.length > 120 &&
        /^[A-Z]/.test(normalizedLine)
      ) {
        flushParagraph();
      }
    }

    paragraphBuffer.push(normalizedLine);
  });

  flushSection();

  /*
   * If the PDF had no recognizable headings, still display
   * readable paragraphs rather than one giant text block.
   */

  if (sections.length === 1 && !sections[0].title) {
    const fullText = sections[0].paragraphs.join(" ");

    const paragraphs = fullText
      .split(/(?<=[.!?])\s+(?=[A-Z])/)
      .map((paragraph) => paragraph.trim())
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

/* =========================================================
   INFO CARD
   ========================================================= */

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

/* =========================================================
   TEXT LENGTH
   ========================================================= */

function formatTextLength(length) {
  if (!length) {
    return "0 characters";
  }

  if (length >= 1000) {
    return `${(length / 1000).toFixed(1)}k`;
  }

  return `${length} characters`;
}

export default PaperDetails;