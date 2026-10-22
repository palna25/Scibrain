import { useEffect, useRef, useState } from "react";
import {
  BookOpen,
  Check,
  ExternalLink,
  FileText,
  Loader2,
  Search,
  Upload,
  X,
} from "lucide-react";

const API_URL = "http://127.0.0.1:8000";

const getAuthHeaders = () => {
  const token = localStorage.getItem("scibrain_token");

  return token
    ? {
        Authorization: `Bearer ${token}`,
      }
    : {};
};

function PaperSearch({ className = "" }) {
  const [query, setQuery] = useState("");

  const [internalResults, setInternalResults] = useState([]);
  const [externalResults, setExternalResults] = useState([]);

  const [sourceStatus, setSourceStatus] = useState({});

  const [loading, setLoading] = useState(false);
  const [importingId, setImportingId] = useState(null);

  // Search errors and import errors are deliberately separate.
  const [searchError, setSearchError] = useState("");
  const [importError, setImportError] = useState(null);

  const [searched, setSearched] = useState(false);
  const [open, setOpen] = useState(false);

  const containerRef = useRef(null);

  // ============================================================
  // CLOSE DROPDOWN WHEN CLICKING OUTSIDE
  // ============================================================

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target)
      ) {
        setOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);

    return () => {
      document.removeEventListener(
        "mousedown",
        handleClickOutside
      );
    };
  }, []);

  // ============================================================
  // SEARCH
  // ============================================================

  const handleSearch = async (event) => {
    event?.preventDefault();

    const trimmedQuery = query.trim();

    if (!trimmedQuery) {
      return;
    }

    console.log(
      "SciBrain paper search submitted:",
      trimmedQuery
    );

    setLoading(true);
    setSearchError("");
    setImportError(null);
    setSearched(true);
    setOpen(true);

    setInternalResults([]);
    setExternalResults([]);
    setSourceStatus({});

    try {
      // --------------------------------------------------------
      // 1. SEARCH SCIBRAIN'S EXISTING PAPERS
      // --------------------------------------------------------

      let papers = [];

      try {
        const papersResponse = await fetch(
          `${API_URL}/api/papers/`,
          {
            method: "GET",
            headers: {
              ...getAuthHeaders(),
            },
          }
        );

        if (papersResponse.ok) {
          const papersData = await papersResponse.json();

          papers = Array.isArray(papersData)
            ? papersData
            : papersData?.papers ||
              papersData?.results ||
              [];
        }
      } catch (internalError) {
        // Internal search failure should not prevent
        // external academic search from working.

        console.error(
          "SciBrain internal paper search failed:",
          internalError
        );
      }

      // Local topic matching against:
      // title
      // filename
      // abstract

      const searchTokens = trimmedQuery
        .toLowerCase()
        .split(/\s+/)
        .filter(Boolean);

      const matchedPapers = papers
        .map((paper) => {
          const title = String(paper.title || "");
          const filename = String(paper.filename || "");
          const abstract = String(paper.abstract || "");

          const searchableText =
            `${title} ${filename} ${abstract}`.toLowerCase();

          const matchedTokens = searchTokens.filter((token) =>
            searchableText.includes(token)
          );

          return {
            ...paper,
            _matchScore:
              matchedTokens.length /
              Math.max(searchTokens.length, 1),
          };
        })
        .filter((paper) => paper._matchScore > 0)
        .sort((a, b) => {
          if (b._matchScore !== a._matchScore) {
            return b._matchScore - a._matchScore;
          }

          return String(a.title || "").localeCompare(
            String(b.title || "")
          );
        })
        .slice(0, 5);

      setInternalResults(matchedPapers);

      // --------------------------------------------------------
      // 2. SEARCH EXTERNAL ACADEMIC SOURCES
      // --------------------------------------------------------

      console.log(
        "Searching external academic sources:",
        `${API_URL}/api/sources/search`
      );

      const externalResponse = await fetch(
        `${API_URL}/api/sources/search`,
        {
          method: "POST",

          headers: {
            ...getAuthHeaders(),
            "Content-Type": "application/json",
          },

          body: JSON.stringify({
            query: trimmedQuery,

            sources: [
              "semantic_scholar",
              "crossref",
              "openalex",
            ],

            limit: 50,
          }),
        }
      );

      console.log(
        "External search response:",
        externalResponse.status
      );

      let externalData = {};

      try {
        externalData = await externalResponse.json();
      } catch {
        externalData = {};
      }

      console.log(
        "External search data:",
        externalData
      );

      // A genuine search failure is handled here.

      if (!externalResponse.ok) {
        throw new Error(
          externalData?.detail ||
            externalData?.message ||
            `Search failed with status ${externalResponse.status}`
        );
      }

      // --------------------------------------------------------
      // EXTERNAL RESULTS
      // --------------------------------------------------------

      const results = Array.isArray(externalData?.results)
        ? externalData.results
        : [];

      /*
       * The backend is responsible for determining whether a PDF
       * is actually accessible.
       *
       * Expected fields:
       *
       * pdf_available: boolean
       * pdf_status: string
       * pdf_url: string | null
       *
       * We do not attempt to verify or download PDFs here.
       */

      setExternalResults(results);

      setSourceStatus(
        externalData?.source_status || {}
      );

      // Source-level problems are warnings,
      // not complete search failures.

      if (
        Array.isArray(externalData?.errors) &&
        externalData.errors.length > 0
      ) {
        console.warn(
          "External source warnings:",
          externalData.errors
        );
      }
    } catch (searchErrorValue) {
      console.error(
        "SciBrain paper search failed:",
        searchErrorValue
      );

      setSearchError(
        searchErrorValue?.message ||
          "Unable to search research papers."
      );

      setExternalResults([]);
    } finally {
      setLoading(false);
    }
  };

  // ============================================================
  // IMPORT PAPER
  // ============================================================

  /*
   * IMPORTANT:
   *
   * This is the ONLY place where /api/sources/import
   * is called.
   *
   * Therefore PDF downloading only starts after the
   * researcher explicitly clicks Import.
   */

  const handleImport = async (paper) => {
    const paperKey = paper.id || paper.source_id;

    if (!paperKey || importingId) {
      return;
    }

    /*
     * Defensive check.
     *
     * Even if the UI accidentally receives a paper with a URL,
     * the explicit backend availability flag must be true before
     * allowing import.
     */

    if (paper.pdf_available !== true) {
      setImportError({
        paperId: paperKey,
        message:
          "This paper does not have a verified accessible PDF.",
      });

      return;
    }

    if (!paper.pdf_url) {
      setImportError({
        paperId: paperKey,
        message:
          "This paper does not have a verified PDF URL.",
      });

      return;
    }

    setImportingId(paperKey);

    // Clear only the previous import error.
    setImportError(null);

    try {
      console.log(
        "Importing paper:",
        paper.title
      );

      console.log(
        "Verified PDF URL:",
        paper.pdf_url
      );

      const response = await fetch(
        `${API_URL}/api/sources/import`,
        {
          method: "POST",

          headers: {
            ...getAuthHeaders(),
            "Content-Type": "application/json",
          },

          body: JSON.stringify({
            title: paper.title,

            pdf_url: paper.pdf_url,

            url: paper.url || null,

            doi: paper.doi || null,

            source: paper.source || null,

            source_id: paper.source_id || null,

            authors: paper.authors || [],

            year: paper.year || null,

            venue: paper.venue || null,

            abstract: paper.abstract || null,

            external_ids: paper.external_ids || {},

            id: paper.id || null,
          }),
        }
      );

      let data = {};

      try {
        data = await response.json();
      } catch {
        data = {};
      }

      if (!response.ok) {
        throw new Error(
          data?.detail ||
            data?.message ||
            `Unable to import this paper (HTTP ${response.status}).`
        );
      }

      console.log(
        "Paper import result:",
        data
      );

      /*
       * Mark the paper as imported.
       *
       * This also handles the backend's duplicate response where:
       *
       * already_imported: true
       */

      setExternalResults((current) =>
        current.map((item) =>
          (item.id || item.source_id) === paperKey
            ? {
                ...item,
                _imported: true,
                _importResult: data,
              }
            : item
        )
      );

      setImportError(null);
    } catch (importErrorValue) {
      console.error(
        "Paper import failed:",
        importErrorValue
      );

      /*
       * Do NOT put this in searchError.
       *
       * The search succeeded.
       * Only this paper's import failed.
       */

      setImportError({
        paperId: paperKey,

        message:
          importErrorValue?.message ||
          "Unable to import this paper.",
      });
    } finally {
      setImportingId(null);
    }
  };

  // ============================================================
  // HELPERS
  // ============================================================

  const formatAuthors = (authors) => {
    if (
      !Array.isArray(authors) ||
      authors.length === 0
    ) {
      return "";
    }

    const names = authors
      .map((author) =>
        typeof author === "string"
          ? author
          : author?.name
      )
      .filter(Boolean);

    if (names.length <= 2) {
      return names.join(", ");
    }

    return `${names
      .slice(0, 2)
      .join(", ")} +${names.length - 2}`;
  };

  const getSourceLabel = (source) => {
    if (source === "semantic_scholar") {
      return "Semantic Scholar";
    }

    if (source === "crossref") {
      return "Crossref";
    }

    return source || "External";
  };

  const getPdfStatusLabel = (paper) => {
    if (paper.pdf_available === true) {
      return "PDF verified";
    }

    if (paper.pdf_status === "access_denied") {
      return "PDF access denied";
    }

    if (paper.pdf_status === "not_pdf") {
      return "Not a PDF";
    }

    if (paper.pdf_status === "too_large") {
      return "PDF too large";
    }

    if (paper.pdf_status === "timeout") {
      return "PDF check timed out";
    }

    if (paper.pdf_status === "unavailable") {
      return "PDF unavailable";
    }

    if (paper.pdf_status === "error") {
      return "PDF unavailable";
    }

    return "PDF unavailable";
  };

  const hasResults =
    internalResults.length > 0 ||
    externalResults.length > 0;

  return (
    <div
      ref={containerRef}
      className={`relative ${className}`}
    >
      {/* ======================================================
          SEARCH FORM
          ====================================================== */}

      <form onSubmit={handleSearch}>
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-600" />

          <input
            type="text"
            value={query}
            onChange={(event) => {
              const value = event.target.value;

              setQuery(value);

              /*
               * Clear previous search state
               * only when the search box becomes empty.
               */

              if (!value.trim()) {
                setSearched(false);
                setOpen(false);

                setInternalResults([]);
                setExternalResults([]);

                setSearchError("");
                setImportError(null);
                setSourceStatus({});
              }
            }}
            onFocus={() => {
              if (searched) {
                setOpen(true);
              }
            }}
            onKeyDown={(event) => {
              if (event.key === "Escape") {
                setOpen(false);
              }
            }}
            placeholder="Search research, papers, concepts..."
            className="h-10 w-full rounded-xl border border-white/[0.07] bg-slate-900/60 pl-10 pr-20 text-sm text-slate-200 outline-none placeholder:text-slate-500 transition-all focus:border-indigo-400/20 focus:bg-slate-900/80 focus:ring-1 focus:ring-indigo-400/10"
          />

          {/* Search / loading controls */}

          <div className="absolute right-2 top-1/2 flex -translate-y-1/2 items-center gap-1">
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin text-indigo-400" />
            ) : (
              <>
                {query && (
                  <button
                    type="button"
                    onClick={() => {
                      setQuery("");
                      setSearched(false);
                      setOpen(false);

                      setInternalResults([]);
                      setExternalResults([]);

                      setSearchError("");
                      setImportError(null);
                      setSourceStatus({});
                    }}
                    className="flex h-7 w-7 items-center justify-center rounded-lg text-slate-600 transition hover:bg-white/[0.04] hover:text-slate-300"
                    aria-label="Clear search"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                )}

                <button
                  type="submit"
                  disabled={!query.trim()}
                  className="flex h-7 w-7 items-center justify-center rounded-lg text-slate-500 transition hover:bg-indigo-500/[0.08] hover:text-indigo-300 disabled:cursor-not-allowed disabled:opacity-30"
                  aria-label="Search papers"
                >
                  <Search className="h-3.5 w-3.5" />
                </button>
              </>
            )}
          </div>
        </div>
      </form>

      {/* ======================================================
          RESULTS DROPDOWN
          ====================================================== */}

      {open && searched && (
        <div className="absolute left-0 right-0 top-[calc(100%+10px)] z-[100] overflow-hidden rounded-2xl border border-white/[0.08] bg-slate-950/98 shadow-2xl shadow-black/50 backdrop-blur-xl">

          {/* ==================================================
              LOADING
              ================================================== */}

          {loading && (
            <div className="flex items-center gap-3 px-5 py-6">
              <Loader2 className="h-4 w-4 animate-spin text-indigo-400" />

              <div>
                <p className="text-sm text-slate-300">
                  Searching research papers...
                </p>

                <p className="mt-0.5 text-[10px] text-slate-600">
                  Searching your SciBrain resources and external
                  academic sources
                </p>
              </div>
            </div>
          )}

          {/* ==================================================
              SEARCH ERROR
              ================================================== */}

          {!loading && searchError && (
            <div className="border-b border-red-400/10 bg-red-500/[0.04] px-5 py-4">
              <p className="text-xs font-medium text-red-300">
                Search failed
              </p>

              <p className="mt-1 text-[11px] text-red-300/70">
                {searchError}
              </p>
            </div>
          )}

          {/* ==================================================
              IMPORT ERROR
              ================================================== */}

          {!loading && importError && (
            <div className="border-b border-amber-400/10 bg-amber-500/[0.035] px-5 py-3">
              <div className="flex items-start gap-3">
                <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-amber-500/[0.08]">
                  <FileText className="h-3.5 w-3.5 text-amber-400" />
                </div>

                <div className="min-w-0 flex-1">
                  <p className="text-xs font-medium text-amber-300">
                    Paper could not be imported
                  </p>

                  <p className="mt-1 text-[11px] leading-4 text-amber-300/70">
                    {importError.message}
                  </p>

                  <p className="mt-1 text-[10px] text-slate-600">
                    The search results are still available.
                  </p>
                </div>

                <button
                  type="button"
                  onClick={() => setImportError(null)}
                  className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-slate-600 transition hover:bg-white/[0.04] hover:text-slate-300"
                  aria-label="Dismiss import error"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          )}

          {/* ==================================================
              INTERNAL PAPERS
              ================================================== */}

          {!loading && internalResults.length > 0 && (
            <section>
              <div className="flex items-center gap-2 border-b border-white/[0.05] px-5 py-3">
                <BookOpen className="h-3.5 w-3.5 text-indigo-400" />

                <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                  Your SciBrain Papers
                </span>
              </div>

              <div className="p-2">
                {internalResults.map((paper) => (
                  <button
                    key={paper.id}
                    type="button"
                    onClick={() => {
                      window.location.href =
                        `/papers/${paper.id}`;
                    }}
                    className="group flex w-full items-start gap-3 rounded-xl px-3 py-3 text-left transition hover:bg-white/[0.04]"
                  >
                    <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-indigo-400/10 bg-indigo-500/[0.08]">
                      <FileText className="h-4 w-4 text-indigo-400" />
                    </div>

                    <div className="min-w-0 flex-1">
                      <p className="line-clamp-1 text-sm font-medium text-slate-200 group-hover:text-white">
                        {paper.title ||
                          paper.filename ||
                          "Untitled paper"}
                      </p>

                      <div className="mt-1 flex items-center gap-2 text-[10px] text-slate-500">
                        <span>SciBrain resource</span>

                        {paper.status && (
                          <>
                            <span>•</span>

                            <span className="capitalize">
                              {paper.status}
                            </span>
                          </>
                        )}
                      </div>
                    </div>

                    <ExternalLink className="mt-1 h-3.5 w-3.5 shrink-0 text-slate-700 transition group-hover:text-indigo-400" />
                  </button>
                ))}
              </div>
            </section>
          )}

          {/* ==================================================
              EXTERNAL PAPERS
              ================================================== */}

          {!loading && externalResults.length > 0 && (
            <section>
              <div className="flex items-center gap-2 border-y border-white/[0.05] px-5 py-3">
                <Search className="h-3.5 w-3.5 text-cyan-400" />

                <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                  External Research
                </span>

                <span className="ml-auto text-[9px] text-slate-600">
                  {externalResults.length} results
                </span>
              </div>

              <div className="max-h-[440px] overflow-y-auto p-2">
                {externalResults.map((paper) => {
                  const paperKey =
                    paper.id || paper.source_id;

                  const imported =
                    paper._imported === true;

                  const importing =
                    importingId === paperKey;

                  const thisPaperImportError =
                    importError?.paperId === paperKey;

                  /*
                   * IMPORTANT:
                   *
                   * pdf_available is now the source of truth.
                   *
                   * We intentionally do NOT use:
                   *
                   *     Boolean(paper.pdf_url)
                   *
                   * because a URL can exist while returning 403,
                   * 404, HTML, or another non-PDF response.
                   */

                  const pdfAvailable =
                    paper.pdf_available === true;

                  return (
                    <div
                      key={paperKey}
                      className="rounded-xl px-3 py-3 transition hover:bg-white/[0.035]"
                    >
                      <div className="flex items-start gap-3">
                        <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-cyan-400/10 bg-cyan-500/[0.06]">
                          <FileText className="h-4 w-4 text-cyan-400" />
                        </div>

                        <div className="min-w-0 flex-1">
                          <p className="line-clamp-2 text-sm font-medium leading-5 text-slate-200">
                            {paper.title ||
                              "Untitled paper"}
                          </p>

                          <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-[10px] text-slate-500">
                            {paper.year && (
                              <span>{paper.year}</span>
                            )}

                            {paper.venue && (
                              <>
                                <span>•</span>

                                <span className="max-w-[150px] truncate">
                                  {paper.venue}
                                </span>
                              </>
                            )}

                            <span>•</span>

                            <span className="text-cyan-400/80">
                              {getSourceLabel(
                                paper.source
                              )}
                            </span>

                            {typeof paper.relevance_score ===
                              "number" && (
                              <>
                                <span>•</span>

                                <span>
                                  {Math.round(
                                    paper.relevance_score *
                                      100
                                  )}
                                  % match
                                </span>
                              </>
                            )}
                          </div>

                          {formatAuthors(
                            paper.authors
                          ) && (
                            <p className="mt-1 line-clamp-1 text-[10px] text-slate-600">
                              {formatAuthors(
                                paper.authors
                              )}
                            </p>
                          )}

                          {/* --------------------------------
                              ACTIONS
                              -------------------------------- */}

                          <div className="mt-2 flex items-center gap-2">
                            {paper.url && (
                              <a
                                href={paper.url}
                                target="_blank"
                                rel="noreferrer"
                                onClick={(event) =>
                                  event.stopPropagation()
                                }
                                className="inline-flex items-center gap-1.5 rounded-lg border border-white/[0.06] px-2.5 py-1.5 text-[10px] font-medium text-slate-400 transition hover:border-indigo-400/15 hover:bg-indigo-500/[0.05] hover:text-indigo-300"
                              >
                                <ExternalLink className="h-3 w-3" />

                                Open
                              </a>
                            )}

                            {/* --------------------------------
                                VERIFIED PDF AVAILABLE
                                -------------------------------- */}

                            {pdfAvailable ? (
                              imported ? (
                                <div className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-400/10 bg-emerald-500/[0.05] px-2.5 py-1.5 text-[10px] font-medium text-emerald-300">
                                  <Check className="h-3 w-3" />

                                  In SciBrain
                                </div>
                              ) : (
                                <button
                                  type="button"
                                  disabled={importing}
                                  onClick={() =>
                                    handleImport(
                                      paper
                                    )
                                  }
                                  className="inline-flex items-center gap-1.5 rounded-lg border border-indigo-400/15 bg-indigo-500/[0.08] px-2.5 py-1.5 text-[10px] font-medium text-indigo-300 transition hover:bg-indigo-500/[0.14] disabled:cursor-not-allowed disabled:opacity-60"
                                >
                                  {importing ? (
                                    <>
                                      <Loader2 className="h-3 w-3 animate-spin" />

                                      Importing...
                                    </>
                                  ) : (
                                    <>
                                      <Upload className="h-3 w-3" />

                                      Import
                                    </>
                                  )}
                                </button>
                              )
                            ) : (
                              <span
                                title={
                                  paper.pdf_status ||
                                  "No verified PDF available"
                                }
                                className="rounded-lg border border-white/[0.05] px-2.5 py-1.5 text-[10px] text-slate-600"
                              >
                                {getPdfStatusLabel(
                                  paper
                                )}
                              </span>
                            )}
                          </div>

                          {/* --------------------------------
                              PAPER-SPECIFIC IMPORT ERROR
                              -------------------------------- */}

                          {thisPaperImportError && (
                            <div className="mt-2 rounded-lg border border-amber-400/10 bg-amber-500/[0.035] px-2.5 py-2">
                              <p className="text-[10px] leading-4 text-amber-300/70">
                                Import failed:{" "}
                                {importError.message}
                              </p>

                              <p className="mt-1 text-[9px] text-slate-600">
                                The paper is still available
                                in the search results.
                              </p>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>
          )}

          {/* ==================================================
              NO RESULTS
              ================================================== */}

          {!loading &&
            !searchError &&
            searched &&
            !hasResults && (
              <div className="px-5 py-8 text-center">
                <Search className="mx-auto h-5 w-5 text-slate-700" />

                <p className="mt-2 text-sm text-slate-400">
                  No research papers found
                </p>

                <p className="mt-1 text-xs text-slate-600">
                  Try a broader research topic or
                  keyword.
                </p>
              </div>
            )}

          {/* ==================================================
              SOURCE STATUS
              ================================================== */}

          {!loading &&
            searched &&
            Object.keys(sourceStatus).length > 0 && (
              <div className="border-t border-white/[0.05] px-5 py-2.5">
                <div className="flex flex-wrap items-center gap-3 text-[9px] uppercase tracking-[0.12em] text-slate-600">
                  {Object.entries(sourceStatus).map(
                    ([source, status]) => (
                      <span key={source}>
                        {getSourceLabel(source)}:{" "}
                        <span
                          className={
                            status?.status ===
                            "success"
                              ? "text-emerald-400/70"
                              : status?.status ===
                                "rate_limited"
                              ? "text-amber-400/70"
                              : "text-slate-500"
                          }
                        >
                          {status?.status ||
                            "unknown"}
                        </span>
                      </span>
                    )
                  )}
                </div>
              </div>
            )}
        </div>
      )}
    </div>
  );
}

export default PaperSearch;