import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import fitz
import requests

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.database.mongodb import papers_collection
from app.services.external_sources import (
    get_crossref_work,
    get_semantic_scholar_paper,
    search_external_sources,
)
from app.services.vector_store import index_paper_chunks


router = APIRouter(
    prefix="/api/sources",
    tags=["External Sources"],
)


# ============================================================
# CONFIGURATION
# ============================================================

UPLOAD_DIR = "uploads/papers"

MAX_PDF_SIZE = 20 * 1024 * 1024

PDF_DOWNLOAD_TIMEOUT = 60

os.makedirs(
    UPLOAD_DIR,
    exist_ok=True,
)


# ============================================================
# SEARCH REQUEST
# ============================================================

class SourceSearchRequest(BaseModel):
    query: str = Field(
        min_length=2,
        max_length=300,
    )

    sources: Optional[List[str]] = None

    limit: int = Field(
        default=10,
        ge=1,
        le=50,
    )


# ============================================================
# IMPORT REQUEST
# ============================================================

class SourceImportRequest(BaseModel):
    """
    External paper selected by the researcher for import.

    The frontend can send the complete normalized result
    returned by /api/sources/search.
    """

    title: str = Field(
        min_length=1,
        max_length=1000,
    )

    pdf_url: Optional[str] = None

    url: Optional[str] = None

    doi: Optional[str] = None

    source: Optional[str] = None

    source_id: Optional[str] = None

    authors: Optional[List[Dict[str, Any]]] = None

    year: Optional[int] = None

    venue: Optional[str] = None

    abstract: Optional[str] = None

    external_ids: Optional[Dict[str, Any]] = None

    id: Optional[str] = None


# ============================================================
# HELPERS
# ============================================================

def _normalize_text(value: Optional[str]) -> str:
    """
    Normalize text for duplicate comparison.
    """

    if not value:
        return ""

    return re.sub(
        r"\s+",
        " ",
        value.strip().lower(),
    )


def _normalize_doi(doi: Optional[str]) -> str:
    """
    Normalize DOI values so that different representations
    compare consistently.

    Examples:
        https://doi.org/10.1234/example
        doi:10.1234/example
        10.1234/example

    all become:

        10.1234/example
    """

    if not doi:
        return ""

    value = doi.strip()

    value = re.sub(
        r"^https?://doi\.org/",
        "",
        value,
        flags=re.IGNORECASE,
    )

    value = re.sub(
        r"^doi:",
        "",
        value,
        flags=re.IGNORECASE,
    )

    return value.strip().lower()


def _safe_filename(paper_id: str) -> str:
    return f"{paper_id}.pdf"


def _paper_title_from_filename(filename: str) -> str:
    return os.path.splitext(
        os.path.basename(filename)
    )[0]


def _build_author_names(
    authors: Optional[List[Dict[str, Any]]],
) -> List[str]:
    """
    Convert normalized external author objects into
    simple author-name strings for storage.
    """

    if not authors:
        return []

    names = []

    for author in authors:

        if not isinstance(author, dict):
            continue

        name = author.get("name")

        if name and str(name).strip():
            names.append(
                str(name).strip()
            )

    return names


# ============================================================
# DUPLICATE CHECK
# ============================================================

def _find_existing_paper(
    title: str,
    doi: Optional[str],
) -> Optional[Dict[str, Any]]:
    """
    Check whether the external paper already exists
    in SciBrain.

    DOI is the strongest identifier.

    Title is used as a fallback when DOI is unavailable.
    """

    normalized_doi = _normalize_doi(
        doi
    )

    # --------------------------------------------------------
    # DOI duplicate check
    # --------------------------------------------------------

    if normalized_doi:

        existing = papers_collection.find_one(
            {
                "doi": {
                    "$regex": (
                        "^"
                        + re.escape(normalized_doi)
                        + "$"
                    ),
                    "$options": "i",
                }
            },
            {
                "_id": 1,
                "title": 1,
                "doi": 1,
                "status": 1,
            },
        )

        if existing:
            return existing

    # --------------------------------------------------------
    # Title duplicate check
    # --------------------------------------------------------

    normalized_title = _normalize_text(
        title
    )

    if normalized_title:

        existing = papers_collection.find_one(
            {
                "title": {
                    "$regex": (
                        "^"
                        + re.escape(normalized_title)
                        + "$"
                    ),
                    "$options": "i",
                }
            },
            {
                "_id": 1,
                "title": 1,
                "doi": 1,
                "status": 1,
            },
        )

        if existing:
            return existing

    return None


# ============================================================
# DOWNLOAD PDF
# ============================================================

def _download_pdf(
    pdf_url: str,
    destination: str,
) -> int:
    """
    Download an external PDF safely.

    Returns:
        Number of downloaded bytes.
    """

    if not pdf_url:
        raise ValueError(
            "This paper does not have an available PDF URL."
        )

    try:

        response = requests.get(
            pdf_url,
            stream=True,
            timeout=PDF_DOWNLOAD_TIMEOUT,
            headers={
                "User-Agent": (
                    "SciBrain/1.0 "
                    "(research paper import)"
                )
            },
            allow_redirects=True,
        )

    except requests.RequestException as error:

        raise ValueError(
            f"Could not download the paper PDF: {error}"
        )

    if response.status_code != 200:

        raise ValueError(
            "The external PDF could not be downloaded "
            f"(HTTP {response.status_code})."
        )

    # --------------------------------------------------------
    # Content-Length check
    # --------------------------------------------------------

    content_length = response.headers.get(
        "Content-Length"
    )

    if content_length:

        try:

            declared_size = int(
                content_length
            )

            if declared_size > MAX_PDF_SIZE:

                raise ValueError(
                    "The PDF exceeds SciBrain's "
                    "20 MB import limit."
                )

        except ValueError as error:

            if "20 MB import limit" in str(error):
                raise

    # --------------------------------------------------------
    # Stream download with hard size limit
    # --------------------------------------------------------

    total_bytes = 0

    try:

        with open(
            destination,
            "wb",
        ) as output:

            for chunk in response.iter_content(
                chunk_size=64 * 1024
            ):

                if not chunk:
                    continue

                total_bytes += len(chunk)

                if total_bytes > MAX_PDF_SIZE:

                    raise ValueError(
                        "The PDF exceeds SciBrain's "
                        "20 MB import limit."
                    )

                output.write(chunk)

    except ValueError:
        raise

    except Exception as error:

        raise ValueError(
            f"Failed while saving the downloaded PDF: {error}"
        )

    # --------------------------------------------------------
    # Basic validation
    # --------------------------------------------------------

    if total_bytes == 0:

        raise ValueError(
            "The downloaded PDF is empty."
        )

    # --------------------------------------------------------
    # PDF magic-byte validation
    # --------------------------------------------------------

    try:

        with open(
            destination,
            "rb",
        ) as file:

            header = file.read(5)

    except Exception as error:

        raise ValueError(
            f"Could not validate downloaded PDF: {error}"
        )

    if header != b"%PDF-":

        # Delete invalid download.
        if os.path.exists(destination):
            os.remove(destination)

        raise ValueError(
            "The external URL did not return a valid PDF. "
            "It may require authentication or provide an "
            "HTML/paywall page instead."
        )

    return total_bytes


# ============================================================
# EXTRACT PDF TEXT
# ============================================================

def _extract_pdf_text(
    file_path: str,
) -> tuple[str, int]:
    """
    Extract readable text from a PDF.

    Returns:
        (text, page_count)
    """

    try:

        document = fitz.open(
            file_path
        )

    except Exception as error:

        raise ValueError(
            f"Failed to open imported PDF: {error}"
        )

    try:

        extracted_text = ""

        for page in document:

            extracted_text += page.get_text()

        page_count = len(
            document
        )

    finally:

        document.close()

    if not extracted_text.strip():

        raise ValueError(
            "No readable text could be extracted "
            "from this PDF. Scanned/image-only PDFs "
            "are not supported yet."
        )

    return (
        extracted_text,
        page_count,
    )


# ============================================================
# SEARCH EXTERNAL SOURCES
# ============================================================

@router.post("/search")
def search_sources(
    request: SourceSearchRequest,
):
    """
    Search configured external academic sources.
    """

    query = request.query.strip()

    if not query:

        raise HTTPException(
            status_code=400,
            detail="Search query cannot be empty.",
        )

    try:

        return search_external_sources(
            query=query,
            sources=request.sources,
            limit=request.limit,
        )

    except Exception as exc:

        raise HTTPException(
            status_code=502,
            detail=(
                "External research source search failed: "
                f"{exc}"
            ),
        )


# ============================================================
# IMPORT EXTERNAL PAPER
# ============================================================

@router.post("/import")
def import_external_paper(
    request: SourceImportRequest,
):
    """
    Import a researcher-selected external paper into SciBrain.

    The paper becomes a normal SciBrain research resource:

        External PDF
             ↓
        MongoDB
             ↓
        Text extraction
             ↓
        Qdrant indexing
             ↓
        Ready for Notebook / Chat / Gaps / KG
    """

    title = request.title.strip()

    if not title:

        raise HTTPException(
            status_code=400,
            detail="Paper title cannot be empty.",
        )

    normalized_doi = _normalize_doi(
        request.doi
    )

    # --------------------------------------------------------
    # Duplicate detection
    # --------------------------------------------------------

    existing = _find_existing_paper(
        title=title,
        doi=normalized_doi,
    )

    if existing:

        existing_id = str(
            existing.get("_id")
        )

        return {
            "id": existing_id,
            "title": existing.get(
                "title",
                title,
            ),
            "status": existing.get(
                "status",
                "unknown",
            ),
            "already_imported": True,
            "message": (
                "This paper is already available "
                "in your SciBrain research resources."
            ),
        }

    # --------------------------------------------------------
    # Require PDF
    # --------------------------------------------------------

    pdf_url = (
        request.pdf_url.strip()
        if request.pdf_url
        else ""
    )

    if not pdf_url:

        raise HTTPException(
            status_code=400,
            detail=(
                "No downloadable PDF is available "
                "for this paper. Import currently "
                "requires an accessible PDF."
            ),
        )

    # --------------------------------------------------------
    # Generate SciBrain resource ID
    # --------------------------------------------------------

    paper_id = str(
        uuid.uuid4()
    )

    safe_filename = _safe_filename(
        paper_id
    )

    file_path = os.path.join(
        UPLOAD_DIR,
        safe_filename,
    )

    # --------------------------------------------------------
    # Download PDF
    # --------------------------------------------------------

    try:

        downloaded_size = _download_pdf(
            pdf_url=pdf_url,
            destination=file_path,
        )

    except ValueError as error:

        if os.path.exists(file_path):
            os.remove(file_path)

        raise HTTPException(
            status_code=422,
            detail=str(error),
        )

    # --------------------------------------------------------
    # Extract text
    # --------------------------------------------------------

    try:

        extracted_text, page_count = (
            _extract_pdf_text(
                file_path
            )
        )

    except ValueError as error:

        if os.path.exists(file_path):
            os.remove(file_path)

        raise HTTPException(
            status_code=422,
            detail=str(error),
        )

    # --------------------------------------------------------
    # External metadata
    # --------------------------------------------------------

    author_names = _build_author_names(
        request.authors
    )

    source_name = (
        request.source.strip()
        if request.source
        else None
    )

    source_id = (
        request.source_id.strip()
        if request.source_id
        else None
    )

    external_url = (
        request.url.strip()
        if request.url
        else None
    )

    # --------------------------------------------------------
    # MongoDB document
    # --------------------------------------------------------

    paper_document = {
        "_id": paper_id,

        "title": title,

        "filename": title + ".pdf",

        "stored_filename": safe_filename,

        "file_path": file_path,

        "page_count": page_count,

        "text": extracted_text,

        "text_length": len(
            extracted_text
        ),

        "status": "processing",

        "processing_error": None,

        "indexed_chunks": 0,

        "uploaded_at": datetime.now(
            timezone.utc
        ),

        # ----------------------------------------------------
        # External-source provenance
        # ----------------------------------------------------

        "imported_from": "external_source",

        "external_source": source_name,

        "external_source_id": source_id,

        "external_url": external_url,

        "pdf_url": pdf_url,

        "doi": normalized_doi or None,

        "external_ids": (
            request.external_ids
            or {}
        ),

        "authors": author_names,

        "year": request.year,

        "venue": request.venue,

        "abstract": request.abstract,

        "external_metadata": {
            "source": source_name,
            "source_id": source_id,
            "external_url": external_url,
            "pdf_url": pdf_url,
            "doi": normalized_doi or None,
            "authors": request.authors or [],
            "year": request.year,
            "venue": request.venue,
            "abstract": request.abstract,
            "external_ids": (
                request.external_ids
                or {}
            ),
        },
    }

    # --------------------------------------------------------
    # Save MongoDB document
    # --------------------------------------------------------

    try:

        papers_collection.insert_one(
            paper_document
        )

    except Exception as error:

        if os.path.exists(file_path):
            os.remove(file_path)

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to save imported paper "
                f"to MongoDB: {error}"
            ),
        )

    # --------------------------------------------------------
    # Index in Qdrant
    # --------------------------------------------------------

    try:

        indexed_chunks = index_paper_chunks(
            paper_id=paper_id,
            title=title,
            text=extracted_text,
        )

        if indexed_chunks == 0:

            papers_collection.update_one(
                {
                    "_id": paper_id,
                },
                {
                    "$set": {
                        "status": "error",
                        "processing_error": (
                            "No searchable chunks were "
                            "created from the imported PDF."
                        ),
                    }
                },
            )

            raise HTTPException(
                status_code=500,
                detail=(
                    "The paper was imported and its text "
                    "was extracted, but no searchable "
                    "chunks could be created."
                ),
            )

        # ----------------------------------------------------
        # Mark paper ready
        # ----------------------------------------------------

        papers_collection.update_one(
            {
                "_id": paper_id,
            },
            {
                "$set": {
                    "status": "ready",
                    "processing_error": None,
                    "indexed_chunks": indexed_chunks,
                }
            },
        )

    except HTTPException:
        raise

    except Exception as error:

        papers_collection.update_one(
            {
                "_id": paper_id,
            },
            {
                "$set": {
                    "status": "error",
                    "processing_error": str(error),
                }
            },
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Paper was imported, but Qdrant "
                "indexing failed: "
                f"{error}"
            ),
        )

    # --------------------------------------------------------
    # Successful response
    # --------------------------------------------------------

    return {
        "id": paper_id,

        "title": title,

        "filename": title + ".pdf",

        "page_count": page_count,

        "text_length": len(
            extracted_text
        ),

        "downloaded_bytes": downloaded_size,

        "indexed_chunks": indexed_chunks,

        "status": "ready",

        "already_imported": False,

        "source": source_name,

        "doi": normalized_doi or None,

        "message": (
            "Paper imported, indexed, and is ready "
            "for research."
        ),
    }


# ============================================================
# GET SEMANTIC SCHOLAR PAPER
# ============================================================

@router.get(
    "/semantic-scholar/paper/{paper_id}"
)
def semantic_scholar_paper(
    paper_id: str,
):
    try:

        result = get_semantic_scholar_paper(
            paper_id
        )

        if result is None:

            raise HTTPException(
                status_code=404,
                detail="Paper not found.",
            )

        return result

    except HTTPException:
        raise

    except Exception as exc:

        raise HTTPException(
            status_code=502,
            detail=(
                "Semantic Scholar request failed: "
                f"{exc}"
            ),
        )


# ============================================================
# GET CROSSREF WORK
# ============================================================

@router.get("/crossref/doi")
def crossref_doi(
    doi: str,
):
    """
    Fetch a Crossref work using its DOI.
    """

    if not doi or len(doi.strip()) < 3:

        raise HTTPException(
            status_code=400,
            detail="A valid DOI is required.",
        )

    try:

        result = get_crossref_work(
            doi.strip()
        )

        if result is None:

            raise HTTPException(
                status_code=404,
                detail="DOI not found.",
            )

        return result

    except HTTPException:
        raise

    except Exception as exc:

        raise HTTPException(
            status_code=502,
            detail=(
                "Crossref request failed: "
                f"{exc}"
            ),
        )