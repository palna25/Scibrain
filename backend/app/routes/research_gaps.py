import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.core.dependencies import get_current_user_id
from app.database.mongodb import (
    papers_collection,
    notebooks_collection,
    research_gap_analyses_collection,
    research_gap_source_selections_collection,
)
from app.services.vector_store import search_paper_chunks
from app.services.gemini import call_gemini_json


router = APIRouter(
    prefix="/api/research-gaps",
    tags=["Research Gaps"],
)


# ============================================================
# CONFIGURATION
# ============================================================

# Retrieval
QUERIES = [
    "research problem unanswered question objective research question",
    "limitations weaknesses constraints challenges existing approaches",
    "future work recommendation unexplored research direction open problem",
    "missing comparison evaluation methodology dataset experiment results",
]

CHUNKS_PER_QUERY = 4
MAX_CHUNKS_PER_PAPER = 30
MAX_CHUNK_CHARS = 1800

# Evidence classification
MAX_GAP_EVIDENCE_PER_PAPER = 8

# Candidate extraction
MAX_CANDIDATE_GAPS_PER_PAPER = 3

# Final synthesis
MAX_FINAL_GAPS = 3


# ============================================================
# REQUEST MODEL
# ============================================================

class ResearchGapRequest(BaseModel):
    resource_ids: List[str]
    notebook_id: str = ""
class ResearchGapSourceSelectionRequest(BaseModel):
    notebook_id: str
    resource_ids: List[str]
def serialize_saved_analysis(analysis: dict) -> dict:
    """Return a saved analysis in a frontend-safe format."""
    return {
        "analysis_id": analysis.get("analysis_id"),
        "notebook_id": analysis.get("notebook_id"),
        "title": analysis.get("title", "Research Gap Analysis"),
        "resource_ids": analysis.get("resource_ids", []),
        "gaps": analysis.get("gaps", []),
        "meta": analysis.get("meta", {}),
        "created_at": analysis.get("created_at"),
        "updated_at": analysis.get("updated_at"),
    }


def persist_analysis_response(
    response: dict,
    user_id: str,
    notebook_id: str,
    resource_ids: List[str],
    notebook_title: str,
) -> dict:
    """
    Save a completed analysis as a new snapshot.

    Every analysis receives its own ID, so earlier results
    are preserved when a new analysis is run.
    """
    if not notebook_id:
        response["saved"] = False
        return response

    now = datetime.now(timezone.utc)
    analysis_id = str(uuid.uuid4())

    document = {
        "analysis_id": analysis_id,
        "user_id": str(user_id),
        "notebook_id": notebook_id,
        "title": f"{notebook_title} — Research Gaps",
        "resource_ids": resource_ids,
        "gaps": response.get("gaps", []),
        "meta": response.get("meta", {}),
        "created_at": now,
        "updated_at": now,
    }

    try:
        research_gap_analyses_collection.insert_one(document)

        response["analysis_id"] = analysis_id
        response["saved"] = True

    except Exception as exc:
        # Preserve the generated result even if saving fails.
        print(
            "[Research Gaps] Failed to save analysis "
            f"for notebook {notebook_id}: {exc}"
        )
        response["saved"] = False

    return response
@router.get("/saved")
def get_saved_research_gap_analyses(
    notebook_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """List saved analyses belonging to the current user and notebook."""

    notebook_id = notebook_id.strip()
    owner_id = str(user_id)

    notebook = notebooks_collection.find_one(
        {
            "notebook_id": notebook_id,
            "user_id": owner_id,
        },
        {"_id": 0, "notebook_id": 1},
    )

    if not notebook:
        raise HTTPException(
            status_code=404,
            detail="Research notebook not found.",
        )

    cursor = research_gap_analyses_collection.find(
        {
            "user_id": owner_id,
            "notebook_id": notebook_id,
        },
        {
            "_id": 0,
            "analysis_id": 1,
            "notebook_id": 1,
            "title": 1,
            "resource_ids": 1,
            "meta": 1,
            "created_at": 1,
            "updated_at": 1,
        },
    ).sort("created_at", -1)

    analyses = []

    for item in cursor:
        analyses.append({
            **item,
            "gap_count": item.get("meta", {}).get(
                "validated_gaps",
                0,
            ),
        })

    return {"analyses": analyses}


@router.get("/saved/{analysis_id}")
def get_saved_research_gap_analysis(
    analysis_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Load a saved result without rerunning Gemini."""

    analysis = research_gap_analyses_collection.find_one(
        {
            "analysis_id": analysis_id,
            "user_id": str(user_id),
        },
        {"_id": 0},
    )

    if not analysis:
        raise HTTPException(
            status_code=404,
            detail="Saved research gap analysis not found.",
        )

    return {
        "analysis": serialize_saved_analysis(analysis),
    }


@router.delete("/saved/{analysis_id}")
def delete_saved_research_gap_analysis(
    analysis_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Delete a saved analysis owned by the current user."""

    result = research_gap_analyses_collection.delete_one(
        {
            "analysis_id": analysis_id,
            "user_id": str(user_id),
        }
    )

    if result.deleted_count == 0:
        raise HTTPException(
            status_code=404,
            detail="Saved research gap analysis not found.",
        )

    return {
        "message": "Saved research gap analysis deleted successfully.",
        "analysis_id": analysis_id,
    }
# ============================================================
# BASIC HELPERS
# ============================================================

def normalize_text(value: Any) -> str:
    if value is None:
        return ""

    return str(value).strip()


# ============================================================
# REFERENCE / BIBLIOGRAPHY FILTERING
# ============================================================

def is_reference_chunk(text: str) -> bool:
    """
    Detect chunks that are primarily bibliography/reference
    material rather than scientific evidence.
    """

    text = normalize_text(text)

    if not text:
        return False

    normalized = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    lower_text = normalized.lower()

    # --------------------------------------------------------
    # Strong section-heading signals
    # --------------------------------------------------------

    section_patterns = [
        r"^\s*references\s*$",
        r"^\s*references\s*[:.]?\s*",
        r"^\s*bibliography\s*$",
        r"^\s*bibliography\s*[:.]?\s*",
        r"^\s*works\s+cited\s*$",
        r"^\s*literature\s+cited\s*$",
    ]

    for pattern in section_patterns:
        if re.search(
            pattern,
            lower_text,
            flags=re.IGNORECASE,
        ):
            return True

    # --------------------------------------------------------
    # Numbered bibliography entries
    # --------------------------------------------------------

    numbered_entries = re.findall(
        r"(?:^|\s)\[\d{1,3}\]\s+",
        normalized,
    )

    numbered_entry_count = len(
        numbered_entries
    )

    if numbered_entry_count >= 3:
        return True

    # --------------------------------------------------------
    # DOI / URL / publication-year combinations
    # --------------------------------------------------------

    doi_count = len(
        re.findall(
            r"\bdoi\s*[:/]",
            lower_text,
        )
    )

    url_count = len(
        re.findall(
            r"https?://",
            lower_text,
        )
    )

    year_count = len(
        re.findall(
            r"\b(?:19|20)\d{2}\b",
            normalized,
        )
    )

    if (
        numbered_entry_count >= 2
        and (
            doi_count >= 1
            or url_count >= 1
            or year_count >= 3
        )
    ):
        return True

    # --------------------------------------------------------
    # Author/year bibliography patterns
    # --------------------------------------------------------

    et_al_count = len(
        re.findall(
            r"\bet\s+al\.",
            lower_text,
        )
    )

    citation_year_patterns = len(
        re.findall(
            r"\(\s*(?:19|20)\d{2}[a-z]?\s*\)",
            normalized,
        )
    )

    if (
        et_al_count >= 3
        and citation_year_patterns >= 2
    ):
        return True

    # --------------------------------------------------------
    # DOI / URL-heavy chunks
    # --------------------------------------------------------

    if (
        doi_count + url_count
    ) >= 3:
        return True

    return False


def filter_reference_chunks(
    chunks: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:

    filtered: List[Dict[str, Any]] = []

    removed_count = 0

    for chunk in chunks:

        text = normalize_text(
            chunk.get("text")
            or chunk.get("content")
            or ""
        )

        if not text:
            continue

        if is_reference_chunk(text):

            removed_count += 1

            print(
                "[Research Gaps] Filtered reference chunk "
                f"{chunk.get('chunk_index')}"
            )

            continue

        filtered.append(chunk)

    print(
        "[Research Gaps] Reference filtering: "
        f"{len(chunks)} -> {len(filtered)} chunks "
        f"({removed_count} removed)"
    )

    return filtered


# ============================================================
# PAPER METADATA
# ============================================================

def get_paper_metadata(
    resource_ids: List[str],
) -> Dict[str, Dict[str, str]]:

    metadata: Dict[str, Dict[str, str]] = {}

    for resource_id in resource_ids:

        try:
            paper = papers_collection.find_one(
                {"_id": resource_id}
            )

            if paper:
                metadata[resource_id] = {
                    "title": (
                        paper.get("title")
                        or paper.get("filename")
                        or "Unknown Paper"
                    )
                }

        except Exception:
            continue

    return metadata


# ============================================================
# QDRANT RETRIEVAL
# ============================================================

def retrieve_chunks_for_paper(
    resource_id: str,
) -> List[Dict[str, Any]]:

    retrieved: List[Dict[str, Any]] = []

    for query in QUERIES:

        try:
            chunks = search_paper_chunks(
                query=query,
                resource_ids=[resource_id],
                limit=CHUNKS_PER_QUERY,
            )

        except TypeError:

            try:
                chunks = search_paper_chunks(
                    query,
                    [resource_id],
                    CHUNKS_PER_QUERY,
                )

            except Exception:
                chunks = []

        except Exception:
            chunks = []

        if chunks:
            retrieved.extend(chunks)

    # --------------------------------------------------------
    # Deduplicate
    # --------------------------------------------------------

    unique: Dict[str, Dict[str, Any]] = {}

    for chunk in retrieved:

        chunk_resource_id = str(
            chunk.get("resource_id")
            or chunk.get("paper_id")
            or resource_id
        )

        chunk_index = chunk.get(
            "chunk_index",
            chunk.get("index", -1),
        )

        text = normalize_text(
            chunk.get("text")
            or chunk.get("content")
            or ""
        )

        if not text:
            continue

        key = f"{chunk_resource_id}:{chunk_index}"

        if key not in unique:
            unique[key] = {
                **chunk,
                "resource_id": chunk_resource_id,
                "chunk_index": chunk_index,
                "text": text,
            }

    deduplicated = list(
        unique.values()
    )[:MAX_CHUNKS_PER_PAPER]

    print(
        f"[Research Gaps] Retrieved "
        f"{len(deduplicated)} unique chunks "
        f"for {resource_id}"
    )

    # --------------------------------------------------------
    # Reference filtering
    # --------------------------------------------------------

    filtered = filter_reference_chunks(
        deduplicated
    )

    return filtered


# ============================================================
# EVIDENCE CLASSIFICATION
# ============================================================

EVIDENCE_CLASSIFICATION_SCHEMA = {
    "type": "object",
    "properties": {
        "evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "chunk_index": {
                        "type": "integer",
                    },
                    "category": {
                        "type": "string",
                        "enum": [
                            "future_work",
                            "unresolved_question",
                            "limitation",
                            "missing_evaluation",
                            "missing_comparison",
                            "methodological_constraint",
                            "result",
                            "method",
                            "background",
                            "other",
                        ],
                    },
                    "gap_relevance": {
                        "type": "string",
                        "enum": [
                            "high",
                            "medium",
                            "low",
                            "none",
                        ],
                    },
                    "reason": {
                        "type": "string",
                    },
                },
                "required": [
                    "chunk_index",
                    "category",
                    "gap_relevance",
                    "reason",
                ],
            },
        },
    },
    "required": [
        "evidence",
    ],
}


def classify_gap_evidence(
    resource_id: str,
    paper_title: str,
    chunks: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:

    if not chunks:
        return []

    parts: List[str] = []

    for index, chunk in enumerate(chunks):

        chunk_index = chunk.get(
            "chunk_index",
            index,
        )

        text = normalize_text(
            chunk.get("text")
            or chunk.get("content")
            or ""
        )

        text = text[:MAX_CHUNK_CHARS]

        parts.append(
            f"""
[CHUNK {chunk_index}]
resource_id: {resource_id}
paper_title: {paper_title}
text:
{text}
"""
        )

    context = "\n".join(parts)

    prompt = f"""
You are SciBrain's evidence-classification module.

Your task is NOT to generate research gaps yet.

Instead, classify the supplied paper chunks according to
whether they contain evidence that could support a research-gap
investigation.

Use ONLY the supplied evidence.

Do NOT use outside knowledge.

Do NOT invent information.

For each chunk, assign exactly one category:

future_work
- The paper explicitly proposes something for future research.

unresolved_question
- The paper explicitly identifies a question or issue that
  remains unresolved, unclear, or open.

limitation
- The paper identifies a specific limitation, weakness,
  boundary, constraint, or unresolved problem.

missing_evaluation
- The evidence indicates that a method/system has not been
  evaluated under a specific setting, dataset, condition,
  metric, or experiment.

missing_comparison
- The evidence indicates that an important comparison has
  not been performed.

methodological_constraint
- The method has a specific constraint that may create a
  researchable direction, but the evidence does not itself
  establish a complete research gap.

result
- Experimental findings, numerical results, or observations
  that do not themselves indicate something missing.

method
- Description of an existing method or approach.

background
- General context, motivation, or previously known information.

other
- Content that does not clearly belong to another category.

Then assign gap_relevance:

high:
The chunk directly contains evidence of something unresolved,
missing, limited, untested, or proposed for future investigation.

medium:
The chunk may help explain a potential gap but does not
clearly establish one by itself.

low:
The chunk is useful context but provides weak evidence for a gap.

none:
The chunk should not contribute to research-gap discovery.

IMPORTANT:

A result is NOT automatically a research gap.

A limitation is NOT automatically a research gap.

A general research problem is NOT automatically a research gap.

A statement that "future research is needed" without a specific
direction should not receive high relevance.

A concrete unresolved issue such as:

"performance reaches an upper bound beyond 18 layers"

may receive high relevance if the supplied evidence supports
that interpretation.

Return one classification for every supplied chunk.

Return JSON only.

PAPER:
{paper_title}

RESOURCE ID:
{resource_id}

SUPPLIED CHUNKS:

{context}
"""

    try:
        result = call_gemini_json(
            prompt,
            EVIDENCE_CLASSIFICATION_SCHEMA,
        )

        classifications = result.get(
            "evidence",
            [],
        )

        if not isinstance(
            classifications,
            list,
        ):
            return []

        print(
            f"[Research Gaps] Evidence classifications "
            f"for {resource_id}:"
        )

        for item in classifications:
            print(
                f"[EVIDENCE] "
                f"chunk={item.get('chunk_index')} "
                f"type={item.get('category')} "
                f"relevance={item.get('gap_relevance')} "
                f"reason={item.get('reason')}"
            )

        # ----------------------------------------------------
        # Keep only evidence that is useful for gap discovery.
        # ----------------------------------------------------

        relevant = []

        for item in classifications:

            if not isinstance(item, dict):
                continue

            relevance = normalize_text(
                item.get("gap_relevance")
            ).lower()

            category = normalize_text(
                item.get("category")
            ).lower()

            if relevance not in {
                "high",
                "medium",
            }:
                continue

            if category in {
                "future_work",
                "unresolved_question",
                "limitation",
                "missing_evaluation",
                "missing_comparison",
                "methodological_constraint",
            }:
                relevant.append(item)

        # ----------------------------------------------------
        # Limit evidence supplied to candidate extraction.
        # ----------------------------------------------------

        relevant = relevant[
            :MAX_GAP_EVIDENCE_PER_PAPER
        ]

        print(
            f"[Research Gaps] Gap-bearing evidence: "
            f"{len(relevant)}"
        )

        return relevant

    except Exception as exc:
        print(
            f"[Research Gaps] Evidence classification "
            f"failed for {resource_id}: {exc}"
        )
        return []


def select_gap_evidence_chunks(
    chunks: List[Dict[str, Any]],
    classifications: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:

    classification_map: Dict[int, Dict[str, Any]] = {}

    for item in classifications:

        if not isinstance(item, dict):
            continue

        chunk_index = item.get(
            "chunk_index"
        )

        if chunk_index is None:
            continue

        try:
            chunk_index = int(
                chunk_index
            )
        except (TypeError, ValueError):
            continue

        classification_map[
            chunk_index
        ] = item

    selected: List[Dict[str, Any]] = []

    for chunk in chunks:

        chunk_index = chunk.get(
            "chunk_index",
            -1,
        )

        try:
            chunk_index = int(
                chunk_index
            )
        except (TypeError, ValueError):
            continue

        if chunk_index not in classification_map:
            continue

        selected.append(chunk)

    return selected


# ============================================================
# FORMAT PAPER CONTEXT
# ============================================================

def format_paper_context(
    resource_id: str,
    chunks: List[Dict[str, Any]],
    paper_title: str,
) -> str:

    parts: List[str] = []

    for index, chunk in enumerate(chunks):

        chunk_index = chunk.get(
            "chunk_index",
            index,
        )

        text = normalize_text(
            chunk.get("text")
            or chunk.get("content")
            or ""
        )

        text = text[:MAX_CHUNK_CHARS]

        parts.append(
            f"""
[EVIDENCE {index}]
resource_id: {resource_id}
paper_title: {paper_title}
chunk_index: {chunk_index}
text:
{text}
"""
        )

    return "\n".join(parts)


# ============================================================
# GEMINI SCHEMAS
# ============================================================

CANDIDATE_GAP_SCHEMA = {
    "type": "object",
    "properties": {
        "gaps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                    },
                    "description": {
                        "type": "string",
                    },
                    "why_gap": {
                        "type": "string",
                    },
                    "evidence": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "resource_id": {
                                    "type": "string",
                                },
                                "paper_title": {
                                    "type": "string",
                                },
                                "chunk_index": {
                                    "type": "integer",
                                },
                                "statement": {
                                    "type": "string",
                                },
                            },
                            "required": [
                                "resource_id",
                                "paper_title",
                                "chunk_index",
                                "statement",
                            ],
                        },
                    },
                },
                "required": [
                    "title",
                    "description",
                    "why_gap",
                    "evidence",
                ],
            },
        },
    },
    "required": [
        "gaps",
    ],
}

# ============================================================
# GAP QUALIFICATION SCHEMA
# ============================================================

QUALIFIED_GAP_SCHEMA = {
    "type": "object",
    "properties": {
        "qualified_candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "candidate_index": {
                        "type": "integer",
                    },
                    "qualification": {
                        "type": "string",
                        "enum": [
                            "strong",
                            "moderate",
                            "weak",
                            "reject",
                        ],
                    },
                    "gap_type": {
                        "type": "string",
                        "enum": [
                            "cross_paper",
                            "paper_specific",
                            "missing_evaluation",
                            "missing_comparison",
                            "unresolved_question",
                            "future_work",
                            "methodological_gap",
                            "other",
                        ],
                    },
                    "supporting_papers": {
                        "type": "integer",
                    },
                    "researchability": {
                        "type": "string",
                        "enum": [
                            "high",
                            "medium",
                            "low",
                        ],
                    },
                    "reason": {
                        "type": "string",
                    },
                    "keep": {
                        "type": "boolean",
                    },
                },
                "required": [
                    "candidate_index",
                    "qualification",
                    "gap_type",
                    "supporting_papers",
                    "researchability",
                    "reason",
                    "keep",
                ],
            },
        },
    },
    "required": [
        "qualified_candidates",
    ],
}

FINAL_GAP_SCHEMA = {
    "type": "object",
    "properties": {
        "gaps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                    },
                    "description": {
                        "type": "string",
                    },
                    "why_gap": {
                        "type": "string",
                    },
                    "evidence": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "resource_id": {
                                    "type": "string",
                                },
                                "paper_title": {
                                    "type": "string",
                                },
                                "chunk_index": {
                                    "type": "integer",
                                },
                                "statement": {
                                    "type": "string",
                                },
                            },
                            "required": [
                                "resource_id",
                                "paper_title",
                                "chunk_index",
                                "statement",
                            ],
                        },
                    },
                },
                "required": [
                    "title",
                    "description",
                    "why_gap",
                    "evidence",
                ],
            },
        },
    },
    "required": [
        "gaps",
    ],
}


# ============================================================
# STAGE 2
# CANDIDATE GAP EXTRACTION
# ============================================================

def extract_candidate_gaps(
    resource_id: str,
    paper_title: str,
    chunks: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:

    if not chunks:
        return []

    context = format_paper_context(
        resource_id,
        chunks,
        paper_title,
    )

    print(
        f"[Research Gaps] Gap-bearing evidence for "
        f"{resource_id}:"
    )

    for chunk in chunks:
        print(
            f"[CHUNK {chunk.get('chunk_index')}]\n"
            f"{normalize_text(chunk.get('text'))[:1000]}\n"
            f"----------------------------------------"
        )

    prompt = f"""
You are SciBrain's research-gap extraction module.

You are given evidence that has already been classified as
potentially relevant to research-gap discovery.

Your task is to identify POTENTIAL research gaps.

You are not required to find a sentence that literally says
"research gap".

Infer a research gap only when the evidence supports something
that remains:

- unexplored,
- not evaluated,
- not compared,
- not tested,
- unresolved,
- insufficiently investigated,
- limited by a specific condition,
- proposed as future work,
- or left as an open research question.

IMPORTANT:

A limitation is NOT automatically a research gap.

For example:

BAD:
"The method has limitations."

GOOD:
"The method has only been evaluated under condition A,
leaving its effectiveness under condition B untested."

BAD:
"Future research is needed."

GOOD:
"The paper identifies evaluation on dataset B as future work,
leaving the method's performance on that dataset untested."

BAD:
"Translation quality reaches an upper bound."

BETTER:
"The evidence indicates that translation quality saturates
beyond a specific model depth, leaving the problem of obtaining
further performance improvements under that depth constraint
unresolved."

However, the final wording MUST remain faithful to the evidence.

You MUST use only the supplied evidence.

Do NOT use outside knowledge.

Do NOT invent datasets, methods, experiments, results,
comparisons, or research questions.

Do NOT turn a known result into a research gap unless the
evidence also indicates what remains unresolved.

For every candidate, explain:

1. WHAT is missing.
2. WHY the supplied evidence indicates that it remains missing.
3. WHAT could reasonably be investigated, without inventing
   unsupported details.

A candidate does not need to be cross-paper.
Paper-specific gaps are acceptable.

Return at most {MAX_CANDIDATE_GAPS_PER_PAPER} candidates.

Each candidate MUST contain:

title
description
why_gap
evidence

Each evidence item MUST contain:

resource_id
paper_title
chunk_index
statement

The evidence statement must be faithful to the supplied chunk.
It may be a concise paraphrase, but must not introduce facts
that are absent from the chunk.

The resource_id MUST be:

{resource_id}

The paper_title MUST be:

{paper_title}

If the evidence genuinely does not support any potential gap,
return an empty gaps array.

Return JSON only.

Required structure:

{{
  "gaps": [
    {{
      "title": "Specific missing research area",
      "description": "What remains unexplored or insufficiently investigated",
      "why_gap": "Why the supplied evidence indicates that this is missing",
      "evidence": [
        {{
          "resource_id": "{resource_id}",
          "paper_title": "{paper_title}",
          "chunk_index": 0,
          "statement": "Evidence-supported statement"
        }}
      ]
    }}
  ]
}}

PAPER:
{paper_title}

RESOURCE ID:
{resource_id}

GAP-BEARING EVIDENCE:

{context}
"""

    try:
        result = call_gemini_json(
            prompt,
            CANDIDATE_GAP_SCHEMA,
        )

        print(
            f"[Research Gaps] Gemini candidate response "
            f"for {resource_id}: {result}"
        )

        gaps = result.get(
            "gaps",
            [],
        )

        if not isinstance(gaps, list):
            print(
                "[Research Gaps] Gemini returned a "
                "non-list gaps value:",
                gaps,
            )
            return []

        print(
            "[Research Gaps] Gemini candidate gaps:",
            gaps,
        )

        return gaps[
            :MAX_CANDIDATE_GAPS_PER_PAPER
        ]

    except Exception as exc:
        print(
            f"[Research Gaps] Gemini candidate extraction "
            f"failed for {resource_id}: {exc}"
        )
        return []


# ============================================================
# STAGE 3
# CROSS-PAPER SYNTHESIS
# ============================================================

def build_candidate_context(
    candidates: List[Dict[str, Any]],
) -> str:

    parts: List[str] = []

    for index, candidate in enumerate(
        candidates,
        start=1,
    ):

        parts.append(
            f"""
[CANDIDATE {index}]

title:
{normalize_text(candidate.get("title"))}

description:
{normalize_text(candidate.get("description"))}

why_gap:
{normalize_text(candidate.get("why_gap"))}

evidence:
"""
        )

        evidence = candidate.get(
            "evidence",
            [],
        )

        if isinstance(evidence, list):

            for item in evidence[:3]:

                if not isinstance(item, dict):
                    continue

                parts.append(
                    f"""
resource_id: {normalize_text(item.get("resource_id"))}
paper_title: {normalize_text(item.get("paper_title"))}
chunk_index: {item.get("chunk_index")}
statement: {normalize_text(item.get("statement"))}
"""
                )

    return "\n".join(parts)

# ============================================================
# GAP QUALIFICATION / CROSS-PAPER VERIFICATION
# ============================================================

def qualify_candidate_gaps(
    candidates: List[Dict[str, Any]],
    resource_count: int,
) -> List[Dict[str, Any]]:

    if not candidates:
        return []

    candidate_context = build_candidate_context(
        candidates
    )

    prompt = f"""
You are SciBrain's Gap Qualification module.

Your task is to critically evaluate candidate research gaps
before they are presented as potential research gaps.

There are {resource_count} selected research papers.

The candidates were generated from evidence extracted from
those papers.

You MUST NOT create new research gaps.

You may ONLY evaluate the supplied candidates.

For every candidate, determine whether it represents a
meaningful research opportunity.

============================================================
IMPORTANT DISTINCTIONS
============================================================

A paper limitation is NOT automatically a research gap.

A future-work statement is NOT automatically a broader
research gap.

A research result is NOT automatically a research gap.

A general statement such as "more research is needed" is
NOT sufficient.

A candidate should be considered stronger when the evidence
indicates a specific unresolved or insufficiently investigated
problem.

============================================================
CROSS-PAPER VERIFICATION
============================================================

For each candidate, examine ALL supplied candidates and their
evidence.

Determine whether the candidate:

1. Appears in more than one selected paper.
2. Represents a common limitation across papers.
3. Represents a missing evaluation or comparison across
   the selected literature.
4. Represents an unresolved question shared across papers.
5. Is addressed or substantially investigated by another
   selected paper.
6. Is merely a future-work statement from one paper.

IMPORTANT:

Do NOT assume that two papers support the same gap simply
because they contain similar words.

There must be a meaningful scientific connection.

If a candidate is supported by only one paper but still
represents a specific and legitimate unresolved research
direction, it may be classified as:

paper_specific

That is acceptable.

However, do NOT call it cross_paper unless evidence from
multiple selected papers genuinely supports the same issue.

============================================================
RESEARCHABILITY
============================================================

Determine whether a researcher could formulate a concrete
research study from the candidate.

HIGH:
The missing area is specific enough to investigate.

MEDIUM:
The direction is meaningful but requires further
specification.

LOW:
The candidate is too broad, vague, or merely repeats
a generic limitation.

============================================================
REJECTION CONDITIONS
============================================================

Reject a candidate if:

- it merely repeats an existing result;
- it is only a generic limitation;
- it says only that future work is needed;
- it is not supported by the supplied evidence;
- another selected paper already addresses the supposed gap;
- it combines unrelated findings from different papers;
- it is too vague to form a researchable question;
- it introduces information not present in the evidence.

============================================================
QUALIFICATION LEVELS
============================================================

strong:
Clear evidence of a specific researchable missing area.

moderate:
Potentially meaningful research gap, but evidence or
specificity is limited.

weak:
Mostly a paper-specific limitation/future-work statement
with limited evidence of a broader research opportunity.

reject:
Should not be presented as a research gap.

============================================================
IMPORTANT EXAMPLE
============================================================

If one paper says:

"Future work should estimate test-set contamination."

That alone should NOT automatically become a strong
cross-paper research gap.

It should normally be:

gap_type = future_work
qualification = weak or moderate

unless other selected papers independently establish the
same unresolved problem.

============================================================

Return one qualification for EVERY candidate.

Do NOT generate additional candidates.

Return JSON only.

CANDIDATES:

{candidate_context}
"""

    try:

        result = call_gemini_json(
            prompt,
            QUALIFIED_GAP_SCHEMA,
        )

        qualified = result.get(
            "qualified_candidates",
            [],
        )

        if not isinstance(
            qualified,
            list,
        ):
            return []

        print(
            "[Research Gaps] Candidate qualification:"
        )

        for item in qualified:

            print(
                f"[QUALIFICATION] "
                f"candidate={item.get('candidate_index')} "
                f"qualification={item.get('qualification')} "
                f"type={item.get('gap_type')} "
                f"papers={item.get('supporting_papers')} "
                f"researchability={item.get('researchability')} "
                f"keep={item.get('keep')} "
                f"reason={item.get('reason')}"
            )

        # ----------------------------------------------------
        # Keep only candidates that survived qualification.
        # ----------------------------------------------------

        qualified_candidates = []

        for item in qualified:

            if not isinstance(item, dict):
                continue

            keep = item.get(
                "keep",
                False,
            )

            qualification = normalize_text(
                item.get("qualification")
            ).lower()

            if (
                keep is True
                and qualification in {
                    "strong",
                    "moderate",
                }
            ):
                qualified_candidates.append(
                    item
                )

        print(
            "[Research Gaps] Qualified candidates: "
            f"{len(qualified_candidates)}"
        )

        # ----------------------------------------------------
        # Attach qualification metadata to original candidate.
        # ----------------------------------------------------

        final_candidates = []

        for item in qualified_candidates:

            candidate_index = item.get(
                "candidate_index"
            )

            if candidate_index is None:
                continue

            try:
                index = int(
                    candidate_index
                ) - 1
            except (
                TypeError,
                ValueError,
            ):
                continue

            if (
                index < 0
                or index >= len(candidates)
            ):
                continue

            original = dict(
                candidates[index]
            )

            original[
                "qualification"
            ] = item.get(
                "qualification"
            )

            original[
                "gap_type"
            ] = item.get(
                "gap_type"
            )

            original[
                "supporting_papers"
            ] = item.get(
                "supporting_papers",
                1,
            )

            original[
                "researchability"
            ] = item.get(
                "researchability"
            )

            original[
                "qualification_reason"
            ] = item.get(
                "reason"
            )

            final_candidates.append(
                original
            )

        return final_candidates

    except Exception as exc:

        print(
            "[Research Gaps] Candidate qualification "
            f"failed: {exc}"
        )

        return [] 
    

def synthesize_research_gaps(
    candidates: List[Dict[str, Any]],
    resource_count: int,
) -> List[Dict[str, Any]]:

    if not candidates:
        return []

    candidate_context = build_candidate_context(
        candidates
    )

    prompt = f"""
You are SciBrain's final research-gap synthesis module.

You are given candidate research gaps extracted independently
from selected research papers.

Your task is to produce the strongest final research gaps.

There are {resource_count} selected research papers.

IMPORTANT:

- Do not invent information.
- Do not create unsupported research gaps.
- Do not use information outside the supplied candidates.
- Do not simply repeat paper limitations.
- Do not treat an existing relationship as a missing research area.
- Do not treat an existing finding as a research gap.
- Do not use bibliography/reference entries as evidence.
- Every final gap MUST be supported by the supplied evidence.
- Evidence must come ONLY from the candidate evidence.
- Avoid duplicate or nearly identical gaps.

A strong research gap must identify a specific and researchable
missing area.

Prefer gaps involving one or more of the following:

1. A method that has not been evaluated on another relevant setting.
2. A comparison between approaches that has not been performed.
3. A dataset, domain, or condition that has not been investigated.
4. An unresolved research question explicitly indicated by the literature.
5. A limitation that clearly creates a specific direction for further
   investigation.
6. A relationship between concepts, methods, datasets, or findings
   that remains insufficiently investigated.

Avoid gaps that are merely:

- a paper title,
- a general limitation,
- an objection,
- a broad research topic,
- "more research is needed",
- a restatement of an existing finding,
- or a relationship that the paper already established.

The final gap should describe:

WHAT is missing

and, where possible:

WHAT should be investigated to address that missing area.

For multiple selected papers:

- Prefer a cross-paper gap only when the evidence genuinely
  supports the comparison or common unresolved issue.
- Do NOT force unrelated papers into one research gap.
- A strong paper-specific gap is preferable to a weak
  cross-paper gap.

Before including a candidate, ask:

"Could a researcher formulate a concrete research study from this gap?"

If the answer is no, reject it.

Return at most {MAX_FINAL_GAPS} final gaps.

Every final gap MUST contain:

- title
- description
- why_gap
- evidence

Every evidence item MUST contain:

- resource_id
- paper_title
- chunk_index
- statement

Use ONLY evidence already present in the candidates.

Return ONLY the required JSON structure.

CANDIDATE RESEARCH GAPS:

{candidate_context}
"""

    try:
        result = call_gemini_json(
            prompt,
            FINAL_GAP_SCHEMA,
        )

        gaps = result.get(
            "gaps",
            [],
        )

        if not isinstance(gaps, list):
            return []

        return gaps[
            :MAX_FINAL_GAPS
        ]

    except Exception as exc:
        print(
            f"[Research Gaps] Gemini synthesis failed: {exc}"
        )
        return []


# ============================================================
# EVIDENCE VALIDATION
# ============================================================

def validate_evidence(
    statement: str,
    source_text: str,
) -> bool:

    statement_words = {
        word.lower()
        for word in re.findall(
            r"[A-Za-z]{4,}",
            statement,
        )
    }

    source_words = {
        word.lower()
        for word in re.findall(
            r"[A-Za-z]{4,}",
            source_text,
        )
    }

    if not statement_words:
        return False

    overlap = statement_words.intersection(
        source_words
    )

    # Evidence statements may be paraphrased.
    # Require modest lexical overlap rather than
    # exact string matching.
    return len(overlap) >= min(
        4,
        max(
            3,
            len(statement_words) // 6,
        ),
    )


def validate_final_gaps(
    gaps: List[Dict[str, Any]],
    all_chunks: List[Dict[str, Any]],
    metadata: Dict[str, Dict[str, str]],
) -> List[Dict[str, Any]]:

    # --------------------------------------------------------
    # Build exact chunk lookup
    # --------------------------------------------------------

    chunk_map: Dict[str, Dict[str, Any]] = {}

    for chunk in all_chunks:

        resource_id = str(
            chunk.get("resource_id")
            or chunk.get("paper_id")
            or ""
        )

        chunk_index = chunk.get(
            "chunk_index",
            chunk.get("index", -1),
        )

        key = f"{resource_id}:{chunk_index}"

        chunk_map[key] = chunk

    validated: List[Dict[str, Any]] = []

    for gap_number, gap in enumerate(
        gaps[:MAX_FINAL_GAPS],
        start=1,
    ):

        if not isinstance(gap, dict):
            continue

        title = normalize_text(
            gap.get("title")
        )

        description = normalize_text(
            gap.get("description")
        )

        why_gap = normalize_text(
            gap.get("why_gap")
        )

        if not title or not description or not why_gap:
            continue

        evidence_output: List[Dict[str, Any]] = []

        evidence = gap.get(
            "evidence",
            [],
        )

        if not isinstance(evidence, list):
            continue

        # ----------------------------------------------------
        # Validate evidence
        # ----------------------------------------------------

        for item in evidence[:3]:

            if not isinstance(item, dict):
                continue

            resource_id = normalize_text(
                item.get("resource_id")
            )

            chunk_index = item.get(
                "chunk_index"
            )

            statement = normalize_text(
                item.get("statement")
            )

            if (
                not resource_id
                or chunk_index is None
                or not statement
            ):
                continue

            key = f"{resource_id}:{chunk_index}"

            source_chunk = chunk_map.get(key)

            if not source_chunk:
                continue

            source_text = normalize_text(
                source_chunk.get("text")
                or source_chunk.get("content")
                or ""
            )

            if not validate_evidence(
                statement,
                source_text,
            ):
                continue

            paper_title = (
                metadata.get(
                    resource_id,
                    {},
                ).get(
                    "title",
                    normalize_text(
                        item.get("paper_title")
                    )
                    or "Unknown Paper",
                )
            )

            evidence_output.append(
                {
                    "resource_id": resource_id,
                    "paper_title": paper_title,
                    "chunk_index": chunk_index,
                    "statement": statement,
                }
            )

        if not evidence_output:
            continue

        # ----------------------------------------------------
        # Remove duplicate evidence
        # ----------------------------------------------------

        unique_evidence = []
        seen = set()

        for item in evidence_output:

            key = (
                item["resource_id"],
                item["chunk_index"],
                item["statement"],
            )

            if key in seen:
                continue

            seen.add(key)
            unique_evidence.append(item)

        validated.append(
            {
                "id": f"gap-{gap_number}",
                "title": title,
                "description": description,
                "why_gap": why_gap,
                "evidence": unique_evidence,
            }
        )

    return validated

@router.get("/sources")
def get_research_gap_sources(
    notebook_id: str,
    user_id: str = Depends(get_current_user_id),
):
    owner_id = str(user_id)
    notebook_id = notebook_id.strip()

    notebook = notebooks_collection.find_one(
        {
            "notebook_id": notebook_id,
            "user_id": owner_id,
        },
        {
            "_id": 0,
            "notebook_id": 1,
            "resource_ids": 1,
        },
    )

    if not notebook:
        raise HTTPException(
            status_code=404,
            detail="Research notebook not found.",
        )

    saved = research_gap_source_selections_collection.find_one(
        {
            "user_id": owner_id,
            "notebook_id": notebook_id,
        },
        {
            "_id": 0,
            "resource_ids": 1,
        },
    )

    # Use the notebook selection only as the initial default.
    # Do not modify the notebook itself.
    if saved is not None:
        resource_ids = saved.get("resource_ids", [])
    else:
        resource_ids = notebook.get("resource_ids", [])

    resource_ids = list(
        dict.fromkeys(
            str(item).strip()
            for item in resource_ids
            if str(item).strip()
        )
    )

    return {
        "notebook_id": notebook_id,
        "resource_ids": resource_ids,
    }


@router.put("/sources")
def save_research_gap_sources(
    request: ResearchGapSourceSelectionRequest,
    user_id: str = Depends(get_current_user_id),
):
    owner_id = str(user_id)
    notebook_id = request.notebook_id.strip()

    notebook = notebooks_collection.find_one(
        {
            "notebook_id": notebook_id,
            "user_id": owner_id,
        },
        {
            "_id": 0,
            "notebook_id": 1,
        },
    )

    if not notebook:
        raise HTTPException(
            status_code=404,
            detail="Research notebook not found.",
        )

    resource_ids = list(
        dict.fromkeys(
            str(item).strip()
            for item in request.resource_ids
            if str(item).strip()
        )
    )

    if resource_ids:
        existing_ids = {
            str(paper["_id"])
            for paper in papers_collection.find(
                {"_id": {"$in": resource_ids}},
                {"_id": 1},
            )
        }

        missing_ids = [
            resource_id
            for resource_id in resource_ids
            if resource_id not in existing_ids
        ]

        if missing_ids:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Some selected research sources no longer exist. "
                    "Refresh the paper list and try again."
                ),
            )

    now = datetime.now(timezone.utc)

    research_gap_source_selections_collection.update_one(
        {
            "user_id": owner_id,
            "notebook_id": notebook_id,
        },
        {
            "$set": {
                "resource_ids": resource_ids,
                "updated_at": now,
            },
            "$setOnInsert": {
                "user_id": owner_id,
                "notebook_id": notebook_id,
                "created_at": now,
            },
        },
        upsert=True,
    )

    return {
        "message": "Research Gaps sources saved.",
        "notebook_id": notebook_id,
        "resource_ids": resource_ids,
    }
# ============================================================
# API ENDPOINT
# ============================================================

@router.post("/analyze")
def analyze_research_gaps(
    request: ResearchGapRequest,
    user_id: str = Depends(get_current_user_id),

):

        # --------------------------------------------------------
    # Validate request and ownership
    # --------------------------------------------------------

    owner_id = str(user_id)
    notebook_id = normalize_text(request.notebook_id)

    # Normalize and deduplicate requested resource IDs.
    requested_resource_ids = list(
        dict.fromkeys(
            str(resource_id).strip()
            for resource_id in request.resource_ids
            if str(resource_id).strip()
        )
    )

    if not requested_resource_ids:
        raise HTTPException(
            status_code=400,
            detail="Select at least one research paper before analyzing.",
        )

    notebook_title = "Research Notebook"

    if notebook_id:
        notebook = notebooks_collection.find_one(
            {
                "notebook_id": notebook_id,
                "user_id": owner_id,
            },
            {
                "_id": 0,
                "title": 1,
            },
        )

        if not notebook:
            raise HTTPException(
                status_code=404,
                detail="Research notebook not found.",
            )

        notebook_title = (
            notebook.get("title") or "Research Notebook"
        )

        # Research Gaps has its own source selection.
        # Never use the notebook's current resource_ids here.
        saved_selection = research_gap_source_selections_collection.find_one(
            {
                "user_id": owner_id,
                "notebook_id": notebook_id,
            },
            {
                "_id": 0,
                "resource_ids": 1,
            },
        )

        # A missing saved selection is treated as an empty selection.
        # The GET /sources endpoint provides the notebook's sources
        # as the initial default, and PUT /sources persists the choice.
        if saved_selection is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Research Gaps sources have not been saved yet. "
                    "Open Manage Sources and save your selection first."
                ),
            )

        saved_resource_ids = list(
            dict.fromkeys(
                str(resource_id).strip()
                for resource_id in saved_selection.get(
                    "resource_ids", []
                )
                if str(resource_id).strip()
            )
        )

        # Require the request to match the saved selection exactly,
        # regardless of order.
        if set(requested_resource_ids) != set(saved_resource_ids):
            raise HTTPException(
                status_code=400,
                detail=(
                    "The requested papers do not match the saved "
                    "Research Gaps source selection. Refresh your "
                    "selection and try again."
                ),
            )

        resource_ids = saved_resource_ids

    else:
        # Preserve compatibility with requests that do not belong
        # to a notebook. These requests cannot save notebook analyses.
        resource_ids = requested_resource_ids

    # Validate that every selected paper still exists.
    existing_ids = {
        str(paper["_id"])
        for paper in papers_collection.find(
            {"_id": {"$in": resource_ids}},
            {"_id": 1},
        )
    }

    missing_ids = [
        resource_id
        for resource_id in resource_ids
        if resource_id not in existing_ids
    ]

    if missing_ids:
        raise HTTPException(
            status_code=400,
            detail=(
                "Some selected research sources could not be found. "
                "Refresh your sources and try again."
            ),
        )

    def finish_analysis(response: dict) -> dict:
        return persist_analysis_response(
            response=response,
            user_id=owner_id,
            notebook_id=notebook_id,
            resource_ids=resource_ids,
            notebook_title=notebook_title,
        )

    # --------------------------------------------------------
    # Metadata
    # --------------------------------------------------------

    metadata = get_paper_metadata(
        resource_ids
    )

    # --------------------------------------------------------
    # Stage 1:
    # Retrieve, filter, and classify each paper
    # --------------------------------------------------------

    all_chunks: List[Dict[str, Any]] = []
    all_gap_evidence_chunks: List[Dict[str, Any]] = []
    all_candidates: List[Dict[str, Any]] = []

    paper_results = []

    for resource_id in resource_ids:

        paper_title = (
            metadata.get(
                resource_id,
                {},
            ).get(
                "title",
                "Unknown Paper",
            )
        )

        chunks = retrieve_chunks_for_paper(
            resource_id
        )

        all_chunks.extend(chunks)

        # ----------------------------------------------------
        # Evidence classification
        # ----------------------------------------------------

        classifications = classify_gap_evidence(
            resource_id=resource_id,
            paper_title=paper_title,
            chunks=chunks,
        )

        gap_evidence_chunks = (
            select_gap_evidence_chunks(
                chunks=chunks,
                classifications=classifications,
            )
        )

        all_gap_evidence_chunks.extend(
            gap_evidence_chunks
        )

        print(
            f"[Research Gaps] Gap-bearing chunks for "
            f"{resource_id}: "
            f"{len(gap_evidence_chunks)}"
        )

        # ----------------------------------------------------
        # Candidate gap extraction
        # ----------------------------------------------------

        candidates = extract_candidate_gaps(
            resource_id=resource_id,
            paper_title=paper_title,
            chunks=gap_evidence_chunks,
        )

        for candidate in candidates:

            if not isinstance(candidate, dict):
                continue

            candidate["source_resource_id"] = (
                resource_id
            )

            all_candidates.append(
                candidate
            )

        paper_results.append(
            {
                "resource_id": resource_id,
                "retrieved_chunks": len(chunks),
                "gap_evidence_chunks": len(
                    gap_evidence_chunks
                ),
                "candidate_gaps": len(candidates),
            }
        )

   
    # --------------------------------------------------------
    # No retrieval
    # --------------------------------------------------------

    if not all_chunks:
        return finish_analysis({
            "gaps": [],
            "meta": {
                "requested_resources": len(resource_ids),
                "retrieved_chunks": 0,
                "gap_evidence_chunks": 0,
                "candidate_gaps": 0,
                "validated_gaps": 0,
                "papers_analyzed": 0,
            },
        })

    # --------------------------------------------------------
    # No gap-bearing evidence
    # --------------------------------------------------------

    if not all_gap_evidence_chunks:
        return finish_analysis({
            "gaps": [],
            "meta": {
                "requested_resources": len(resource_ids),
                "retrieved_chunks": len(all_chunks),
                "gap_evidence_chunks": 0,
                "candidate_gaps": 0,
                "validated_gaps": 0,
                "papers_analyzed": len(paper_results),
                "paper_results": paper_results,
            },
        })

    # --------------------------------------------------------
    # No candidate gaps
    # --------------------------------------------------------

    if not all_candidates:
        return finish_analysis({
            "gaps": [],
            "meta": {
                "requested_resources": len(resource_ids),
                "retrieved_chunks": len(all_chunks),
                "gap_evidence_chunks": len(all_gap_evidence_chunks),
                "candidate_gaps": 0,
                "validated_gaps": 0,
                "papers_analyzed": len(paper_results),
                "paper_results": paper_results,
            },
        })

    # --------------------------------------------------------
    # Stage 3: Gap qualification / cross-paper verification
    # --------------------------------------------------------

    qualified_candidates = qualify_candidate_gaps(
        candidates=all_candidates,
        resource_count=len(resource_ids),
    )

    # --------------------------------------------------------
    # No qualified candidates
    # --------------------------------------------------------

    if not qualified_candidates:
        return finish_analysis({
            "gaps": [],
            "meta": {
                "requested_resources": len(resource_ids),
                "papers_analyzed": len(paper_results),
                "retrieved_chunks": len(all_chunks),
                "gap_evidence_chunks": len(all_gap_evidence_chunks),
                "candidate_gaps": len(all_candidates),
                "qualified_gaps": 0,
                "validated_gaps": 0,
                "paper_results": paper_results,
            },
        })

    # --------------------------------------------------------
    # Stage 4: Final synthesis
    # --------------------------------------------------------

    final_gaps = synthesize_research_gaps(
        candidates=qualified_candidates,
        resource_count=len(resource_ids),
    )

    # --------------------------------------------------------
    # Evidence validation
    # --------------------------------------------------------

    validated_gaps = validate_final_gaps(
        gaps=final_gaps,
        all_chunks=all_chunks,
        metadata=metadata,
    )

    # --------------------------------------------------------
    # Final response and persistence
    # --------------------------------------------------------

    return finish_analysis({
        "gaps": validated_gaps,
        "meta": {
            "requested_resources": len(resource_ids),
            "papers_analyzed": len(paper_results),
            "retrieved_chunks": len(all_chunks),
            "gap_evidence_chunks": len(all_gap_evidence_chunks),
            "candidate_gaps": len(all_candidates),
            "qualified_gaps": len(qualified_candidates),
            "validated_gaps": len(validated_gaps),
            "paper_results": paper_results,
        },
    })
