import html
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

import requests


# ============================================================
# API CONFIGURATION
# ============================================================

SEMANTIC_SCHOLAR_URL = (
    "https://api.semanticscholar.org/graph/v1"
)

CROSSREF_URL = (
    "https://api.crossref.org/v1"
)

OPENALEX_URL = (
    "https://api.openalex.org"
)

REQUEST_TIMEOUT = 20

PDF_VERIFY_TIMEOUT = 12

MAX_PDF_SIZE = 20 * 1024 * 1024

# Search substantially deeper than the final UI limit.
SEARCH_MULTIPLIER = 5

MAX_PROVIDER_RESULTS = 100

PDF_VERIFY_WORKERS = 8

SEMANTIC_SCHOLAR_API_KEY = os.getenv(
    "SEMANTIC_SCHOLAR_API_KEY"
)

CROSSREF_EMAIL = os.getenv(
    "CROSSREF_EMAIL",
    "",
)

OPENALEX_EMAIL = os.getenv(
    "OPENALEX_EMAIL",
    "",
)


# ============================================================
# SOURCE CONFIGURATION
# ============================================================

DEFAULT_SOURCES = [
    "semantic_scholar",
    "crossref",
    "openalex",
]

SUPPORTED_SOURCES = {
    "semantic_scholar",
    "crossref",
    "openalex",
}

PDF_MAGIC = b"%PDF-"

PDF_USER_AGENT = (
    "SciBrain/1.0 "
    "(academic research assistant)"
)


# ============================================================
# HELPERS
# ============================================================

def _clean(value: Any) -> Optional[str]:
    if value is None:
        return None

    value = str(value).strip()

    return value if value else None


def _normalize_text(value: Any) -> str:
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


def _tokenize(value: Any) -> List[str]:
    normalized = _normalize_text(value)

    if not normalized:
        return []

    return normalized.split()


def _clean_abstract(value: Any) -> Optional[str]:
    value = _clean(value)

    if not value:
        return None

    value = html.unescape(value)

    value = re.sub(
        r"<[^>]+>",
        " ",
        value,
    )

    value = value.replace(
        "&nbsp;",
        " ",
    )

    value = html.unescape(value)

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip() or None


def _normalize_year(value: Any) -> Optional[int]:
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
    authors: Optional[List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:

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
    authors: Optional[List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:

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


# ============================================================
# OPENALEX ABSTRACT RECONSTRUCTION
# ============================================================

def _reconstruct_openalex_abstract(
    inverted_index: Any,
) -> Optional[str]:
    """
    OpenAlex often stores abstracts as an inverted index.

    Example:

        {
            "retrieval": [0, 5],
            "augmented": [1],
            "generation": [2]
        }

    Reconstruct the original word order.
    """

    if not isinstance(
        inverted_index,
        dict,
    ):
        return None

    positions = []

    for word, indexes in inverted_index.items():
        if not isinstance(indexes, list):
            continue

        for index in indexes:
            try:
                positions.append(
                    (
                        int(index),
                        str(word),
                    )
                )
            except (
                TypeError,
                ValueError,
            ):
                continue

    if not positions:
        return None

    positions.sort(
        key=lambda item: item[0]
    )

    return " ".join(
        word
        for _, word in positions
    ).strip() or None


# ============================================================
# PDF URL NORMALIZATION
# ============================================================

def _add_pdf_candidate(
    candidates: List[str],
    url: Any,
) -> None:

    url = _clean(url)

    if not url:
        return

    if not re.match(
        r"^https?://",
        url,
        flags=re.IGNORECASE,
    ):
        return

    key = url.lower()

    if key not in {
        item.lower()
        for item in candidates
    }:
        candidates.append(url)


# ============================================================
# CROSSREF PDF CANDIDATES
# ============================================================

def _select_crossref_pdf_candidates(
    item: Dict[str, Any],
) -> List[str]:
    """
    Collect possible PDF URLs from Crossref.

    Crossref metadata is not treated as proof of PDF
    availability. Every candidate is verified later.

    We now retain more plausible HTTPS links instead of
    requiring Crossref to explicitly label the link
    application/pdf.
    """

    links = item.get("link") or []

    scored = []

    for link in links:
        if not isinstance(link, dict):
            continue

        url = _clean(
            link.get("URL")
        )

        if not url:
            continue

        if not re.match(
            r"^https?://",
            url,
            flags=re.IGNORECASE,
        ):
            continue

        content_type = (
            _clean(
                link.get("content-type")
            )
            or ""
        ).lower()

        normalized_url = (
            url.lower()
            .split("?")[0]
            .split("#")[0]
        )

        score = 0

        if "application/pdf" in content_type:
            score += 100

        if normalized_url.endswith(".pdf"):
            score += 80

        if "pdf" in normalized_url:
            score += 20

        if "download" in normalized_url:
            score += 10

        if "fulltext" in normalized_url:
            score += 10

        # Do not immediately reject every non-.pdf URL.
        # Some publishers use article/download endpoints
        # which return a PDF after a redirect.
        if score == 0:
            score = 1

        scored.append(
            (
                score,
                url,
            )
        )

    scored.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    candidates = []
    seen = set()

    for _, url in scored:
        key = url.lower()

        if key in seen:
            continue

        seen.add(key)

        candidates.append(url)

    return candidates


def _select_crossref_pdf(
    item: Dict[str, Any],
) -> Optional[str]:

    candidates = (
        _select_crossref_pdf_candidates(
            item
        )
    )

    if not candidates:
        return None

    return candidates[0]


# ============================================================
# PDF URL VERIFICATION
# ============================================================

def _verify_pdf_url(
    url: Optional[str],
) -> Dict[str, Any]:

    url = _clean(url)

    if not url:
        return {
            "pdf_available": False,
            "pdf_status": "no_url",
            "pdf_url": None,
        }

    if not re.match(
        r"^https?://",
        url,
        flags=re.IGNORECASE,
    ):
        return {
            "pdf_available": False,
            "pdf_status": "invalid_url",
            "pdf_url": url,
        }

    response = None

    try:
        response = requests.get(
            url,
            stream=True,
            allow_redirects=True,
            timeout=PDF_VERIFY_TIMEOUT,
            headers={
                "User-Agent": PDF_USER_AGENT,
                "Accept": (
                    "application/pdf,"
                    "application/octet-stream,"
                    "*/*;q=0.8"
                ),
            },
        )

        status_code = response.status_code

        if status_code in (401, 403):
            return {
                "pdf_available": False,
                "pdf_status": "access_denied",
                "pdf_url": url,
                "http_status": status_code,
            }

        if status_code == 404:
            return {
                "pdf_available": False,
                "pdf_status": "not_found",
                "pdf_url": url,
                "http_status": status_code,
            }

        if status_code >= 400:
            return {
                "pdf_available": False,
                "pdf_status": "request_failed",
                "pdf_url": url,
                "http_status": status_code,
            }

        content_length = response.headers.get(
            "Content-Length"
        )

        if content_length:
            try:
                size = int(content_length)

                if size > MAX_PDF_SIZE:
                    return {
                        "pdf_available": False,
                        "pdf_status": "too_large",
                        "pdf_url": url,
                        "size": size,
                    }

            except (
                TypeError,
                ValueError,
            ):
                pass

        content_type = (
            response.headers.get(
                "Content-Type",
                "",
            )
            .lower()
        )

        prefix = b""

        for chunk in response.iter_content(
            chunk_size=8192
        ):
            if not chunk:
                continue

            prefix += chunk

            if len(prefix) >= 8192:
                break

        if not prefix.startswith(
            PDF_MAGIC
        ):
            return {
                "pdf_available": False,
                "pdf_status": "not_pdf",
                "pdf_url": url,
                "content_type": content_type,
            }

        verified_url = (
            response.url
            or url
        )

        return {
            "pdf_available": True,
            "pdf_status": "verified",
            "pdf_url": verified_url,
            "content_type": content_type,
        }

    except requests.exceptions.Timeout:
        return {
            "pdf_available": False,
            "pdf_status": "timeout",
            "pdf_url": url,
        }

    except requests.exceptions.RequestException as exc:
        return {
            "pdf_available": False,
            "pdf_status": "request_error",
            "pdf_url": url,
            "error": str(exc)[:300],
        }

    except Exception as exc:
        return {
            "pdf_available": False,
            "pdf_status": "verification_error",
            "pdf_url": url,
            "error": str(exc)[:300],
        }

    finally:
        if response is not None:
            response.close()


def _verify_pdf_candidates(
    candidates: List[str],
    cache: Optional[
        Dict[str, Dict[str, Any]]
    ] = None,
) -> Dict[str, Any]:

    if cache is None:
        cache = {}

    if not candidates:
        return {
            "pdf_available": False,
            "pdf_status": "no_url",
            "pdf_url": None,
        }

    last_result = {
        "pdf_available": False,
        "pdf_status": "unavailable",
        "pdf_url": None,
    }

    for candidate in candidates:
        candidate = _clean(candidate)

        if not candidate:
            continue

        cache_key = candidate.lower()

        if cache_key in cache:
            result = cache[
                cache_key
            ]

        else:
            result = _verify_pdf_url(
                candidate
            )

            cache[cache_key] = result

        if result.get(
            "pdf_available"
        ):
            return result

        last_result = result

    return last_result


def _verify_all_pdf_candidates(
    papers: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:

    url_candidates: Dict[
        str,
        str,
    ] = {}

    for paper in papers:
        candidates = (
            paper.get(
                "_pdf_candidates"
            )
            or []
        )

        for candidate in candidates:
            candidate = _clean(candidate)

            if not candidate:
                continue

            key = candidate.lower()

            if key not in url_candidates:
                url_candidates[key] = candidate

    if not url_candidates:
        return {}

    verification_cache: Dict[
        str,
        Dict[str, Any],
    ] = {}

    with ThreadPoolExecutor(
        max_workers=PDF_VERIFY_WORKERS
    ) as executor:

        future_map = {
            executor.submit(
                _verify_pdf_url,
                url,
            ): key
            for key, url in url_candidates.items()
        }

        for future in as_completed(
            future_map
        ):
            key = future_map[
                future
            ]

            try:
                verification_cache[
                    key
                ] = future.result()

            except Exception as exc:
                verification_cache[
                    key
                ] = {
                    "pdf_available": False,
                    "pdf_status": (
                        "verification_error"
                    ),
                    "pdf_url": (
                        url_candidates[key]
                    ),
                    "error": str(exc)[:300],
                }

    return verification_cache


# ============================================================
# RESULT ID
# ============================================================

def _build_result_id(
    paper: Dict[str, Any],
) -> str:

    doi = _clean(
        paper.get("doi")
    )

    if doi:
        return (
            f"doi:{doi.lower()}"
        )

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

    query_normalized = _normalize_text(
        query
    )

    if not query_normalized:
        return 0.0

    query_tokens = set(
        _tokenize(query)
    )

    if not query_tokens:
        return 0.0

    title = _normalize_text(
        paper.get("title")
    )

    abstract = _normalize_text(
        paper.get("abstract")
    )

    venue = _normalize_text(
        paper.get("venue")
    )

    title_tokens = set(
        title.split()
    )

    abstract_tokens = set(
        abstract.split()
    )

    venue_tokens = set(
        venue.split()
    )

    title_overlap = (
        len(
            query_tokens
            & title_tokens
        )
        / len(query_tokens)
    )

    abstract_overlap = (
        len(
            query_tokens
            & abstract_tokens
        )
        / len(query_tokens)
        if abstract_tokens
        else 0.0
    )

    venue_overlap = (
        len(
            query_tokens
            & venue_tokens
        )
        / len(query_tokens)
        if venue_tokens
        else 0.0
    )

    exact_title_phrase = (
        query_normalized in title
    )

    exact_abstract_phrase = (
        query_normalized in abstract
    )

    score = (
        title_overlap * 0.60
        + abstract_overlap * 0.35
        + venue_overlap * 0.05
    )

    if exact_title_phrase:
        score += 0.25

    elif exact_abstract_phrase:
        score += 0.10

    if paper.get("abstract"):
        score += 0.02

    if paper.get("authors"):
        score += 0.01

    if paper.get("doi"):
        score += 0.01

    if paper.get("venue"):
        score += 0.01

    if paper.get("pdf_available"):
        score += 0.03

    try:
        citations = int(
            paper.get(
                "citation_count"
            )
            or 0
        )

        if citations >= 100:
            score += 0.04

        elif citations >= 25:
            score += 0.025

        elif citations >= 5:
            score += 0.01

    except (
        TypeError,
        ValueError,
    ):
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

    open_access_pdf = (
        paper.get("openAccessPdf")
        or {}
    )

    pdf_url = _clean(
        open_access_pdf.get("url")
        if isinstance(
            open_access_pdf,
            dict,
        )
        else None
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

        "pdf_url": pdf_url,

        "pdf_available": False,

        "pdf_status": (
            "unverified"
            if pdf_url
            else "no_url"
        ),

        "doi": _clean(
            external_ids.get("DOI")
        ),

        "arxiv_id": _clean(
            external_ids.get("ArXiv")
        ),

        "external_ids": external_ids,

        "_pdf_candidates": (
            [pdf_url]
            if pdf_url
            else []
        ),
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

    pdf_candidates = (
        _select_crossref_pdf_candidates(
            item
        )
    )

    result = {
        "source": "crossref",

        "source_id": doi,

        "title": title,

        "abstract": _clean_abstract(
            item.get("abstract")
        ),

        "year": year,

        "authors": (
            _normalize_crossref_authors(
                item.get("author")
            )
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

        "pdf_url": (
            pdf_candidates[0]
            if pdf_candidates
            else None
        ),

        "pdf_available": False,

        "pdf_status": (
            "unverified"
            if pdf_candidates
            else "no_url"
        ),

        "doi": doi,

        "arxiv_id": None,

        "external_ids": {
            "DOI": doi
            if doi
            else None,
        },

        "_pdf_candidates": pdf_candidates,
    }

    result["id"] = _build_result_id(
        result
    )

    return result


# ============================================================
# OPENALEX NORMALIZATION
# ============================================================

def _select_openalex_pdf_candidates(
    work: Dict[str, Any],
) -> List[str]:

    candidates = []

    open_access = (
        work.get("open_access")
        or {}
    )

    best_oa = (
        work.get("best_oa_location")
        or {}
    )

    primary_location = (
        work.get("primary_location")
        or {}
    )

    locations = (
        work.get("locations")
        or []
    )

    # --------------------------------------------------------
    # Best OA location first.
    # --------------------------------------------------------

    if isinstance(
        best_oa,
        dict,
    ):
        _add_pdf_candidate(
            candidates,
            best_oa.get(
                "pdf_url"
            ),
        )

    # --------------------------------------------------------
    # Primary location.
    # --------------------------------------------------------

    if isinstance(
        primary_location,
        dict,
    ):
        _add_pdf_candidate(
            candidates,
            primary_location.get(
                "pdf_url"
            ),
        )

    # --------------------------------------------------------
    # All OA locations.
    # --------------------------------------------------------

    if isinstance(
        locations,
        list,
    ):
        for location in locations:
            if not isinstance(
                location,
                dict,
            ):
                continue

            _add_pdf_candidate(
                candidates,
                location.get(
                    "pdf_url"
                ),
            )

    return candidates


def _normalize_openalex_paper(
    work: Dict[str, Any],
) -> Dict[str, Any]:

    primary_location = (
        work.get("primary_location")
        or {}
    )

    source_info = (
        primary_location.get(
            "source"
        )
        if isinstance(
            primary_location,
            dict,
        )
        else {}
    )

    if not isinstance(
        source_info,
        dict,
    ):
        source_info = {}

    abstract = (
        _reconstruct_openalex_abstract(
            work.get(
                "abstract_inverted_index"
            )
        )
    )

    authorships = (
        work.get("authorships")
        or []
    )

    authors = []

    for authorship in authorships:
        if not isinstance(
            authorship,
            dict,
        ):
            continue

        author = (
            authorship.get(
                "author"
            )
            or {}
        )

        if not isinstance(
            author,
            dict,
        ):
            continue

        name = _clean(
            author.get("display_name")
        )

        if not name:
            continue

        authors.append(
            {
                "name": name,
                "id": _clean(
                    author.get("id")
                ),
            }
        )

    doi = _clean(
        work.get("doi")
    )

    if doi:
        doi = re.sub(
            r"^https?://doi\.org/",
            "",
            doi,
            flags=re.IGNORECASE,
        )

    pdf_candidates = (
        _select_openalex_pdf_candidates(
            work
        )
    )

    source_id = _clean(
        work.get("id")
    )

    result = {
        "source": "openalex",

        "source_id": source_id,

        "title": _clean(
            work.get("title")
        ),

        "abstract": abstract,

        "year": _normalize_year(
            work.get(
                "publication_year"
            )
        ),

        "authors": authors,

        "venue": _clean(
            source_info.get(
                "display_name"
            )
        ),

        "citation_count": (
            work.get(
                "cited_by_count"
            )
            or 0
        ),

        "reference_count": len(
            work.get(
                "referenced_works"
            )
            or []
        ),

        "url": _clean(
            work.get("doi")
        ) or _clean(
            work.get("id")
        ),

        "pdf_url": (
            pdf_candidates[0]
            if pdf_candidates
            else None
        ),

        "pdf_available": False,

        "pdf_status": (
            "unverified"
            if pdf_candidates
            else "no_url"
        ),

        "doi": doi,

        "arxiv_id": None,

        "external_ids": {
            "DOI": doi
            if doi
            else None,

        },

        "_pdf_candidates": pdf_candidates,
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
        min(
            int(limit),
            MAX_PROVIDER_RESULTS,
        ),
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
        if isinstance(
            paper,
            dict,
        )
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

    if not isinstance(
        paper,
        dict,
    ):
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
        min(
            int(limit),
            MAX_PROVIDER_RESULTS,
        ),
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
        _normalize_crossref_paper(
            item
        )
        for item in items
        if isinstance(
            item,
            dict,
        )
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

    response = requests.get(
        f"{CROSSREF_URL}/works/{doi}",
        params=_crossref_params(),
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

    if not isinstance(
        item,
        dict,
    ):
        return None

    return _normalize_crossref_paper(
        item
    )


# ============================================================
# OPENALEX REQUEST
# ============================================================

def _openalex_params() -> Dict[str, str]:

    params = {}

    if OPENALEX_EMAIL:
        params["mailto"] = OPENALEX_EMAIL

    return params


def _openalex_headers() -> Dict[str, str]:

    return {
        "User-Agent": (
            "SciBrain/1.0 "
            "(academic research assistant)"
        )
    }


def search_openalex(
    query: str,
    limit: int = 10,
) -> List[Dict[str, Any]]:

    query = query.strip()

    if not query:
        return []

    limit = max(
        1,
        min(
            int(limit),
            MAX_PROVIDER_RESULTS,
        ),
    )

    params = {
        "search": query,
        "per-page": limit,
        "select": (
            "id,doi,title,publication_year,"
            "authorships,primary_location,"
            "best_oa_location,locations,"
            "open_access,cited_by_count,"
            "referenced_works,"
            "abstract_inverted_index"
        ),
        **_openalex_params(),
    }

    response = requests.get(
        f"{OPENALEX_URL}/works",
        params=params,
        headers=_openalex_headers(),
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    payload = response.json()

    results = payload.get(
        "results",
        [],
    )

    return [
        _normalize_openalex_paper(
            work
        )
        for work in results
        if isinstance(
            work,
            dict,
        )
    ]


# ============================================================
# RESULT DEDUPLICATION
# ============================================================

def _pdf_quality(
    paper: Dict[str, Any],
) -> int:

    if paper.get(
        "pdf_available"
    ) is True:
        return 3

    if paper.get("pdf_url"):
        return 1

    return 0


def _deduplicate_results(
    results: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:

    seen: Dict[
        str,
        Dict[str, Any],
    ] = {}

    for paper in results:

        if not isinstance(
            paper,
            dict,
        ):
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

            seen[keys[0]] = paper

            for key in keys[1:]:
                seen[key] = paper

            continue

        if (
            _pdf_quality(paper)
            > _pdf_quality(existing)
        ):

            existing["pdf_url"] = (
                paper.get(
                    "pdf_url"
                )
            )

            existing["pdf_available"] = (
                paper.get(
                    "pdf_available"
                )
            )

            existing["pdf_status"] = (
                paper.get(
                    "pdf_status"
                )
            )

        for field in [
            "abstract",
            "venue",
            "url",
            "doi",
            "arxiv_id",
        ]:

            if not existing.get(field):
                if paper.get(field):
                    existing[field] = (
                        paper[field]
                    )

        if not existing.get(
            "authors"
        ):
            if paper.get("authors"):
                existing["authors"] = (
                    paper["authors"]
                )

        if not existing.get("year"):
            if paper.get("year"):
                existing["year"] = (
                    paper["year"]
                )

        try:
            existing[
                "citation_count"
            ] = max(
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

        except (
            TypeError,
            ValueError,
        ):
            pass

        try:
            existing[
                "reference_count"
            ] = max(
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

        except (
            TypeError,
            ValueError,
        ):
            pass

        sources = existing.get(
            "sources"
        )

        if not isinstance(
            sources,
            list,
        ):
            sources = [
                existing.get(
                    "source"
                )
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

        paper_object_id = id(
            paper
        )

        if paper_object_id in added_ids:
            continue

        added_ids.add(
            paper_object_id
        )

        if not paper.get(
            "sources"
        ):
            paper["sources"] = [
                paper.get(
                    "source"
                )
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
        isinstance(
            exc,
            requests.HTTPError,
        )
        and exc.response is not None
    ):

        status_code = (
            exc.response.status_code
        )

        if status_code == 429:
            status = "rate_limited"

        elif 400 <= status_code < 500:
            status = "request_failed"

        elif status_code >= 500:
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

    final_limit = max(
        1,
        min(
            int(limit),
            100,
        ),
    )

    if not query:
        return {
            "query": query,
            "results": [],
            "errors": [],
            "sources": [],
            "source_status": {},
            "count": 0,
            "filtered_count": 0,
        }

    requested_sources = (
        sources
        or DEFAULT_SOURCES
    )

    normalized_sources = []

    for source in requested_sources:

        source = (
            str(source)
            .strip()
            .lower()
        )

        if (
            source
            and source not in normalized_sources
        ):
            normalized_sources.append(
                source
            )

    # --------------------------------------------------------
    # SEARCH DEPTH
    #
    # If frontend asks for 50:
    #
    #     provider_limit = 100
    #
    # We do not make the UI number equal to the provider
    # discovery depth.
    # --------------------------------------------------------

    provider_limit = max(
        final_limit * SEARCH_MULTIPLIER,
        50,
    )

    provider_limit = min(
        provider_limit,
        MAX_PROVIDER_RESULTS,
    )

    results: List[
        Dict[str, Any]
    ] = []

    errors = []

    source_status: Dict[
        str,
        Dict[str, Any],
    ] = {}

    # --------------------------------------------------------
    # QUERY PROVIDERS
    # --------------------------------------------------------

    for source in normalized_sources:

        if source not in SUPPORTED_SOURCES:

            error = {
                "source": source,
                "error": "Unsupported source",
            }

            errors.append(error)

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
                        limit=provider_limit,
                    )
                )

            elif source == "crossref":

                source_results = (
                    search_crossref(
                        query=query,
                        limit=provider_limit,
                    )
                )

            elif source == "openalex":

                source_results = (
                    search_openalex(
                        query=query,
                        limit=provider_limit,
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

            errors.append(
                {
                    "source": source,
                    "error": str(exc),
                }
            )

            source_status[source] = (
                _error_status(
                    source,
                    exc,
                )
            )

        except Exception as exc:

            errors.append(
                {
                    "source": source,
                    "error": str(exc),
                }
            )

            source_status[source] = {
                "status": "error",
                "error": str(exc),
            }

    # --------------------------------------------------------
    # NOTHING FROM PROVIDERS
    # --------------------------------------------------------

    if not results:

        return {
            "query": query,
            "results": [],
            "errors": errors,
            "sources": normalized_sources,
            "source_status": source_status,
            "count": 0,
            "filtered_count": 0,
            "candidate_count": 0,
            "verified_count": 0,
        }

    raw_candidate_count = len(
        results
    )

    # --------------------------------------------------------
    # INITIAL RELEVANCE
    # --------------------------------------------------------

    for paper in results:

        paper[
            "relevance_score"
        ] = _calculate_relevance(
            query=query,
            paper=paper,
        )

    results.sort(
        key=lambda paper: (
            paper.get(
                "relevance_score",
                0,
            ),
            paper.get(
                "citation_count",
                0,
            )
            or 0,
            paper.get(
                "year",
                0,
            )
            or 0,
        ),
        reverse=True,
    )

    # --------------------------------------------------------
    # DEDUPLICATE BEFORE PDF CHECK
    # --------------------------------------------------------

    results = _deduplicate_results(
        results
    )

    deduplicated_candidate_count = (
        len(results)
    )

    # --------------------------------------------------------
    # PDF VERIFICATION
    # --------------------------------------------------------

    verification_cache = (
        _verify_all_pdf_candidates(
            results
        )
    )

    verified_results = []

    filtered_count = 0

    for paper in results:

        candidates = (
            paper.get(
                "_pdf_candidates"
            )
            or []
        )

        verification = {
            "pdf_available": False,
            "pdf_status": "no_url",
            "pdf_url": None,
        }

        for candidate in candidates:

            candidate = _clean(
                candidate
            )

            if not candidate:
                continue

            cache_key = (
                candidate.lower()
            )

            result = (
                verification_cache.get(
                    cache_key
                )
            )

            if result is None:

                result = _verify_pdf_url(
                    candidate
                )

                verification_cache[
                    cache_key
                ] = result

            if result.get(
                "pdf_available"
            ):

                verification = result

                break

            verification = result

        paper[
            "pdf_available"
        ] = (
            verification.get(
                "pdf_available"
            )
            is True
        )

        paper[
            "pdf_status"
        ] = (
            verification.get(
                "pdf_status"
            )
            or "unavailable"
        )

        if paper[
            "pdf_available"
        ]:

            paper[
                "pdf_url"
            ] = verification.get(
                "pdf_url"
            )

            paper[
                "pdf_status"
            ] = "verified"

            verified_results.append(
                paper
            )

        else:

            paper[
                "pdf_url"
            ] = None

            filtered_count += 1

        paper.pop(
            "_pdf_candidates",
            None,
        )

    # --------------------------------------------------------
    # FINAL DEDUPLICATION
    # --------------------------------------------------------

    results = _deduplicate_results(
        verified_results
    )

    # --------------------------------------------------------
    # FINAL RELEVANCE
    # --------------------------------------------------------

    for paper in results:

        paper[
            "relevance_score"
        ] = _calculate_relevance(
            query=query,
            paper=paper,
        )

        paper[
            "pdf_available"
        ] = True

        paper[
            "pdf_status"
        ] = "verified"

    # --------------------------------------------------------
    # FINAL SORT
    # --------------------------------------------------------

    results.sort(
        key=lambda paper: (
            paper.get(
                "relevance_score",
                0,
            ),
            paper.get(
                "citation_count",
                0,
            )
            or 0,
            paper.get(
                "year",
                0,
            )
            or 0,
        ),
        reverse=True,
    )

    total_verified = len(
        results
    )

    # --------------------------------------------------------
    # FINAL LIMIT
    # --------------------------------------------------------

    final_results = results[
        :final_limit
    ]

    # --------------------------------------------------------
    # SOURCE PDF COUNTS
    # --------------------------------------------------------

    for source in normalized_sources:

        status = source_status.get(
            source
        )

        if not status:
            continue

        if status.get(
            "status"
        ) != "success":
            continue

        status[
            "pdf_verified_count"
        ] = sum(
            1
            for paper in results
            if source
            in (
                paper.get(
                    "sources"
                )
                or [
                    paper.get(
                        "source"
                    )
                ]
            )
        )

    return {
        "query": query,

        "results": final_results,

        "errors": errors,

        "sources": normalized_sources,

        "source_status": source_status,

        "count": len(
            final_results
        ),

        "filtered_count": filtered_count,

        "candidate_count": (
            raw_candidate_count
        ),

        "deduplicated_candidate_count": (
            deduplicated_candidate_count
        ),

        "verified_count": (
            total_verified
        ),
    }