import html
import os
import re
from typing import Any, Dict, List, Optional

import requests


SEMANTIC_SCHOLAR_URL = (
    "https://api.semanticscholar.org/graph/v1"
)

CROSSREF_URL = "https://api.crossref.org/v1"

REQUEST_TIMEOUT = 20

SEMANTIC_SCHOLAR_API_KEY = os.getenv(
    "SEMANTIC_SCHOLAR_API_KEY"
)

CROSSREF_EMAIL = os.getenv(
    "CROSSREF_EMAIL",
    ""
)


# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_SOURCES = [
    "semantic_scholar",
    "crossref",
]

SUPPORTED_SOURCES = {
    "semantic_scholar",
    "crossref",
}


# ============================================================
# HELPERS
# ============================================================

def _clean(value: Any) -> Optional[str]:
    """
    Convert a value to a clean optional string.
    """
    if value is None:
        return None

    value = str(value).strip()

    return value if value else None


def _normalize_text(value: Any) -> str:
    """
    Normalize text for comparison/deduplication.
    """
    value = _clean(value) or ""

    value = html.unescape(value)

    value = value.lower()

    value = re.sub(
        r"[^a-z0-9\s]",
        " ",
        value,
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


def _clean_abstract(value: Any) -> Optional[str]:
    """
    Clean Crossref JATS/XML or HTML-like abstracts.
    """
    value = _clean(value)

    if not value:
        return None

    value = html.unescape(value)

    # Remove XML/HTML tags.
    value = re.sub(
        r"<[^>]+>",
        " ",
        value,
    )

    # Remove common JATS entities.
    value = value.replace(
        "&nbsp;",
        " ",
    )

    value = html.unescape(value)

    # Normalize whitespace.
    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip() or None


def _normalize_year(value: Any) -> Optional[int]:
    """
    Normalize publication year.
    """
    if value is None:
        return None

    try:
        year = int(value)

        if 1000 <= year <= 2100:
            return year

    except (TypeError, ValueError):
        pass

    return None


def _normalize_authors(
    authors: Optional[List[Dict[str, Any]]]
) -> List[Dict[str, Any]]:
    """
    Normalize Semantic Scholar-style authors.
    """
    normalized = []

    for author in authors or []:

        if not isinstance(author, dict):
            continue

        name = _clean(
            author.get("name")
        )

        if not name:
            continue

        normalized.append(
            {
                "name": name,
                "id": _clean(
                    author.get("authorId")
                    or author.get("id")
                ),
            }
        )

    return normalized


def _normalize_crossref_authors(
    authors: Optional[List[Dict[str, Any]]]
) -> List[Dict[str, Any]]:
    """
    Normalize Crossref authors.
    """
    normalized = []

    for author in authors or []:

        if not isinstance(author, dict):
            continue

        given = _clean(
            author.get("given")
        )

        family = _clean(
            author.get("family")
        )

        name = " ".join(
            part
            for part in [given, family]
            if part
        )

        if not name:
            name = _clean(
                author.get("name")
            )

        if not name:
            continue

        normalized.append(
            {
                "name": name,
                "id": _clean(
                    author.get("ORCID")
                ),
            }
        )

    return normalized


def _select_crossref_pdf(
    item: Dict[str, Any],
) -> Optional[str]:
    """
    Select the most likely PDF URL from Crossref links.

    Crossref's first link is not necessarily a PDF, so we
    prefer links explicitly marked as application/pdf or
    links whose URL ends in .pdf.
    """

    links = item.get("link") or []

    candidates = []

    for link in links:

        if not isinstance(link, dict):
            continue

        url = _clean(
            link.get("URL")
        )

        if not url:
            continue

        content_type = (
            _clean(
                link.get("content-type")
            )
            or ""
        ).lower()

        score = 0

        if "application/pdf" in content_type:
            score += 10

        if url.lower().split("?")[0].endswith(
            ".pdf"
        ):
            score += 5

        candidates.append(
            (
                score,
                url,
            )
        )

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    best_score, best_url = candidates[0]

    if best_score <= 0:
        return None

    return best_url


def _build_result_id(
    paper: Dict[str, Any],
) -> str:
    """
    Build a stable identifier for frontend operations.
    DOI is preferred because it is generally stable across
    scholarly metadata providers.
    """

    doi = _clean(
        paper.get("doi")
    )

    if doi:
        return f"doi:{doi.lower()}"

    source = _clean(
        paper.get("source")
    ) or "unknown"

    source_id = _clean(
        paper.get("source_id")
    ) or ""

    return (
        f"{source}:{source_id}"
        .lower()
    )


def _paper_identity_keys(
    paper: Dict[str, Any],
) -> List[str]:
    """
    Generate keys used for cross-source deduplication.
    """

    keys = []

    doi = _clean(
        paper.get("doi")
    )

    if doi:
        keys.append(
            f"doi:{_normalize_text(doi)}"
        )

    title = _normalize_text(
        paper.get("title")
    )

    if title:
        keys.append(
            f"title:{title}"
        )

    return keys


# ============================================================
# RELEVANCE
# ============================================================

def _calculate_relevance(
    query: str,
    paper: Dict[str, Any],
) -> float:
    """
    Lightweight deterministic relevance score.

    This is intentionally not an LLM score. It is only used
    for ordering external discovery results.
    """

    query_tokens = set(
        _normalize_text(query).split()
    )

    if not query_tokens:
        return 0.0

    title_tokens = set(
        _normalize_text(
            paper.get("title")
        ).split()
    )

    abstract_tokens = set(
        _normalize_text(
            paper.get("abstract")
        ).split()
    )

    title_overlap = (
        len(query_tokens & title_tokens)
        / len(query_tokens)
    )

    abstract_overlap = (
        len(query_tokens & abstract_tokens)
        / len(query_tokens)
        if abstract_tokens
        else 0.0
    )

    score = (
        title_overlap * 0.70
        + abstract_overlap * 0.30
    )

    # Small metadata quality bonuses.
    if paper.get("abstract"):
        score += 0.03

    if paper.get("authors"):
        score += 0.02

    if paper.get("doi"):
        score += 0.02

    if paper.get("pdf_url"):
        score += 0.03

    # Citation signal, deliberately kept small so popular
    # papers do not dominate relevance.
    try:
        citations = int(
            paper.get("citation_count") or 0
        )

        if citations >= 100:
            score += 0.05

        elif citations >= 25:
            score += 0.03

        elif citations >= 5:
            score += 0.01

    except (TypeError, ValueError):
        pass

    return round(
        min(score, 1.0),
        4,
    )


# ============================================================
# SEMANTIC SCHOLAR NORMALIZATION
# ============================================================

def _normalize_semantic_scholar_paper(
    paper: Dict[str, Any],
) -> Dict[str, Any]:

    external_ids = (
        paper.get("externalIds")
        or {}
    )

    result = {
        "source": "semantic_scholar",

        "source_id": _clean(
            paper.get("paperId")
        ),

        "title": _clean(
            paper.get("title")
        ),

        "abstract": _clean_abstract(
            paper.get("abstract")
        ),

        "year": _normalize_year(
            paper.get("year")
        ),

        "authors": _normalize_authors(
            paper.get("authors")
        ),

        "venue": _clean(
            paper.get("venue")
        ),

        "citation_count": (
            paper.get("citationCount")
            or 0
        ),

        "reference_count": (
            paper.get("referenceCount")
            or 0
        ),

        "url": _clean(
            paper.get("url")
        ),

        "pdf_url": _clean(
            (
                paper.get("openAccessPdf")
                or {}
            ).get("url")
        ),

        "doi": _clean(
            external_ids.get("DOI")
        ),

        "arxiv_id": _clean(
            external_ids.get("ArXiv")
        ),

        "external_ids": external_ids,
    }

    result["id"] = _build_result_id(
        result
    )

    return result


# ============================================================
# CROSSREF NORMALIZATION
# ============================================================

def _normalize_crossref_paper(
    item: Dict[str, Any],
) -> Dict[str, Any]:

    title_list = (
        item.get("title")
        or []
    )

    title = (
        _clean(title_list[0])
        if title_list
        else None
    )

    container_list = (
        item.get("container-title")
        or []
    )

    venue = (
        _clean(container_list[0])
        if container_list
        else None
    )

    published = (
        item.get("published-print")
        or item.get("published-online")
        or item.get("issued")
        or {}
    )

    date_parts = (
        published.get("date-parts")
        or [[]]
    )

    year = None

    if (
        date_parts
        and date_parts[0]
    ):
        year = _normalize_year(
            date_parts[0][0]
        )

    doi = _clean(
        item.get("DOI")
    )

    url = _clean(
        item.get("URL")
    )

    result = {
        "source": "crossref",

        "source_id": doi,

        "title": title,

        "abstract": _clean_abstract(
            item.get("abstract")
        ),

        "year": year,

        "authors": _normalize_crossref_authors(
            item.get("author")
        ),

        "venue": venue,

        "citation_count": (
            item.get(
                "is-referenced-by-count"
            )
            or 0
        ),

        "reference_count": (
            item.get(
                "reference-count"
            )
            or 0
        ),

        "url": url,

        "pdf_url": _select_crossref_pdf(
            item
        ),

        "doi": doi,

        "arxiv_id": None,

        "external_ids": {
            "DOI": doi
            if doi
            else None,
        },
    }

    result["id"] = _build_result_id(
        result
    )

    return result


# ============================================================
# SEMANTIC SCHOLAR REQUEST
# ============================================================

def _semantic_scholar_headers() -> Dict[str, str]:
    headers = {}

    if SEMANTIC_SCHOLAR_API_KEY:
        headers["x-api-key"] = (
            SEMANTIC_SCHOLAR_API_KEY
        )

    return headers


def search_semantic_scholar(
    query: str,
    limit: int = 10,
) -> List[Dict[str, Any]]:

    query = query.strip()

    if not query:
        return []

    limit = max(
        1,
        min(int(limit), 100),
    )

    fields = ",".join(
        [
            "title",
            "abstract",
            "year",
            "authors",
            "venue",
            "citationCount",
            "referenceCount",
            "url",
            "openAccessPdf",
            "externalIds",
        ]
    )

    params = {
        "query": query,
        "limit": limit,
        "fields": fields,
    }

    response = requests.get(
        f"{SEMANTIC_SCHOLAR_URL}/paper/search",
        params=params,
        headers=_semantic_scholar_headers(),
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    payload = response.json()

    return [
        _normalize_semantic_scholar_paper(
            paper
        )
        for paper in payload.get(
            "data",
            [],
        )
        if isinstance(paper, dict)
    ]


def get_semantic_scholar_paper(
    paper_id: str,
) -> Optional[Dict[str, Any]]:

    paper_id = paper_id.strip()

    if not paper_id:
        return None

    fields = ",".join(
        [
            "title",
            "abstract",
            "year",
            "authors",
            "venue",
            "citationCount",
            "referenceCount",
            "url",
            "openAccessPdf",
            "externalIds",
            "citations",
            "references",
        ]
    )

    response = requests.get(
        f"{SEMANTIC_SCHOLAR_URL}/paper/{paper_id}",
        params={
            "fields": fields,
        },
        headers=_semantic_scholar_headers(),
        timeout=REQUEST_TIMEOUT,
    )

    if response.status_code == 404:
        return None

    response.raise_for_status()

    paper = response.json()

    if not isinstance(paper, dict):
        return None

    return _normalize_semantic_scholar_paper(
        paper
    )


# ============================================================
# CROSSREF REQUEST
# ============================================================

def _crossref_headers() -> Dict[str, str]:
    return {
        "User-Agent": (
            "SciBrain/1.0 "
            "(academic research assistant)"
        )
    }


def _crossref_params() -> Dict[str, str]:
    params = {}

    if CROSSREF_EMAIL:
        params["mailto"] = CROSSREF_EMAIL

    return params


def search_crossref(
    query: str,
    limit: int = 10,
) -> List[Dict[str, Any]]:

    query = query.strip()

    if not query:
        return []

    limit = max(
        1,
        min(int(limit), 50),
    )

    params = {
        "query": query,
        "rows": limit,
        **_crossref_params(),
    }

    response = requests.get(
        f"{CROSSREF_URL}/works",
        params=params,
        headers=_crossref_headers(),
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    payload = response.json()

    message = payload.get(
        "message",
        {},
    )

    items = message.get(
        "items",
        [],
    )

    return [
        _normalize_crossref_paper(item)
        for item in items
        if isinstance(item, dict)
    ]


def get_crossref_work(
    doi: str,
) -> Optional[Dict[str, Any]]:

    doi = doi.strip()

    if not doi:
        return None

    doi = re.sub(
        r"^https?://doi\.org/",
        "",
        doi,
        flags=re.IGNORECASE,
    )

    doi = doi.strip()

    params = _crossref_params()

    response = requests.get(
        f"{CROSSREF_URL}/works/{doi}",
        params=params,
        headers=_crossref_headers(),
        timeout=REQUEST_TIMEOUT,
    )

    if response.status_code == 404:
        return None

    response.raise_for_status()

    payload = response.json()

    item = payload.get(
        "message"
    )

    if not isinstance(item, dict):
        return None

    return _normalize_crossref_paper(
        item
    )


# ============================================================
# RESULT DEDUPLICATION
# ============================================================

def _deduplicate_results(
    results: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Deduplicate papers returned by multiple providers.

    DOI is the strongest identity signal. Title is used as
    a fallback.
    """

    seen = {}

    for paper in results:

        if not isinstance(paper, dict):
            continue

        keys = _paper_identity_keys(
            paper
        )

        if not keys:
            continue

        existing = None

        for key in keys:

            if key in seen:
                existing = seen[key]
                break

        if existing is None:

            seen[
                keys[0]
            ] = paper

            for key in keys[1:]:
                seen[key] = paper

            continue

        # Merge missing metadata from the newer result.
        for field in [
            "abstract",
            "venue",
            "url",
            "pdf_url",
            "doi",
            "arxiv_id",
        ]:

            if not existing.get(field):
                if paper.get(field):
                    existing[field] = paper[field]

        if not existing.get("authors"):
            if paper.get("authors"):
                existing["authors"] = (
                    paper["authors"]
                )

        # Prefer the larger citation/reference counts.
        try:
            existing["citation_count"] = max(
                int(
                    existing.get(
                        "citation_count"
                    )
                    or 0
                ),
                int(
                    paper.get(
                        "citation_count"
                    )
                    or 0
                ),
            )
        except (TypeError, ValueError):
            pass

        try:
            existing["reference_count"] = max(
                int(
                    existing.get(
                        "reference_count"
                    )
                    or 0
                ),
                int(
                    paper.get(
                        "reference_count"
                    )
                    or 0
                ),
            )
        except (TypeError, ValueError):
            pass

        # Preserve source information when a paper exists
        # in more than one provider.
        sources = existing.get(
            "sources"
        )

        if not isinstance(sources, list):
            sources = [
                existing.get("source")
            ]

        current_source = paper.get(
            "source"
        )

        if (
            current_source
            and current_source not in sources
        ):
            sources.append(
                current_source
            )

        existing["sources"] = sources

    unique_results = []

    added_ids = set()

    for paper in seen.values():

        paper_id = id(paper)

        if paper_id in added_ids:
            continue

        added_ids.add(
            paper_id
        )

        if not paper.get("sources"):
            paper["sources"] = [
                paper.get("source")
            ]

        unique_results.append(
            paper
        )

    return unique_results


# ============================================================
# SOURCE STATUS
# ============================================================

def _error_status(
    source: str,
    exc: Exception,
) -> Dict[str, Any]:

    status = "error"

    if (
        isinstance(exc, requests.HTTPError)
        and exc.response is not None
    ):

        if exc.response.status_code == 429:
            status = "rate_limited"

        elif 400 <= exc.response.status_code < 500:
            status = "request_failed"

        elif exc.response.status_code >= 500:
            status = "provider_error"

    return {
        "status": status,
        "error": str(exc),
    }


# ============================================================
# UNIFIED SEARCH
# ============================================================

def search_external_sources(
    query: str,
    sources: Optional[List[str]] = None,
    limit: int = 10,
) -> Dict[str, Any]:

    query = query.strip()

    if not query:
        return {
            "query": query,
            "results": [],
            "errors": [],
            "sources": [],
            "source_status": {},
            "count": 0,
        }

    requested_sources = sources or DEFAULT_SOURCES

    # Normalize and remove duplicates.
    normalized_sources = []

    for source in requested_sources:

        source = source.strip().lower()

        if source and source not in normalized_sources:
            normalized_sources.append(
                source
            )

    results = []

    errors = []

    source_status = {}

    for source in normalized_sources:

        if source not in SUPPORTED_SOURCES:

            error = {
                "source": source,
                "error": "Unsupported source",
            }

            errors.append(
                error
            )

            source_status[source] = {
                "status": "unsupported",
                "error": "Unsupported source",
            }

            continue

        try:

            if source == "semantic_scholar":

                source_results = (
                    search_semantic_scholar(
                        query=query,
                        limit=limit,
                    )
                )

            elif source == "crossref":

                source_results = (
                    search_crossref(
                        query=query,
                        limit=limit,
                    )
                )

            else:
                source_results = []

            results.extend(
                source_results
            )

            source_status[source] = {
                "status": "success",
                "count": len(
                    source_results
                ),
            }

        except requests.RequestException as exc:

            error = {
                "source": source,
                "error": str(exc),
            }

            errors.append(
                error
            )

            source_status[source] = (
                _error_status(
                    source,
                    exc,
                )
            )

        except Exception as exc:

            error = {
                "source": source,
                "error": str(exc),
            }

            errors.append(
                error
            )

            source_status[source] = {
                "status": "error",
                "error": str(exc),
            }

    # Remove duplicate records.
    results = _deduplicate_results(
        results
    )

    # Calculate relevance after merging.
    for paper in results:

        paper["relevance_score"] = (
            _calculate_relevance(
                query=query,
                paper=paper,
            )
        )

    # Highest relevance first.
    # Citation count is only a secondary tie-breaker.
    results.sort(
        key=lambda paper: (
            paper.get(
                "relevance_score",
                0,
            ),
            paper.get(
                "citation_count",
                0,
            ) or 0,
            paper.get(
                "year",
                0,
            ) or 0,
        ),
        reverse=True,
    )

    # Return only the requested number of final results.
    final_results = results[
        : max(
            1,
            min(
                int(limit),
                50,
            ),
        )
    ]

    return {
        "query": query,

        "results": final_results,

        "errors": errors,

        "sources": normalized_sources,

        "source_status": source_status,

        "count": len(
            final_results
        ),
    }