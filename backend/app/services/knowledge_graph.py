import re
import time
from typing import Any, Dict, List, Tuple

from fastapi import HTTPException

from app.database.mongodb import papers_collection
from app.services.gemini import call_gemini_json
from app.services.vector_store import search_paper_chunks


# ============================================================
# CONFIGURATION
# ============================================================

RETRIEVAL_LIMIT = 4
MAX_RETRIEVED_CHUNKS = 30
MAX_GRAPH_CHUNKS = 10
MAX_CHUNK_CHARS = 2200

MAX_GRAPH_ENTITIES = 20
MAX_GRAPH_RELATIONSHIPS = 15

MAX_EVIDENCE_PER_NODE = 8
MAX_EVIDENCE_PER_EDGE = 8


# ============================================================
# GRAPH TYPES
# ============================================================

SUPPORTED_ENTITY_TYPES = {
    "paper",
    "author",
    "method",
    "dataset",
    "metric",
    "concept",
    "finding",
    "limitation",
    "future_work",
    "problem",
    "organization",
    "tool",
    "model",
}


SUPPORTED_RELATION_TYPES = {
    "authored_by",
    "uses",
    "proposed",
    "evaluated_on",
    "discusses",
    "reports",
    "based_on",
    "addresses",
    "measures",
    "implements",
    "extends",
    "improves",
    "compares_with",
    "has_finding",
    "has_limitation",
    "has_future_work",
}


RELATION_ALIASES = {
    "authored by": "authored_by",
    "authored_by": "authored_by",

    "uses": "uses",
    "use": "uses",
    "using": "uses",
    "used": "uses",

    "proposed": "proposed",
    "proposes": "proposed",
    "propose": "proposed",
    "introduces": "proposed",
    "introduced": "proposed",
    "introduce": "proposed",
    "develops": "proposed",
    "developed": "proposed",

    "evaluated on": "evaluated_on",
    "evaluated_on": "evaluated_on",
    "tested on": "evaluated_on",
    "test on": "evaluated_on",
    "benchmarked on": "evaluated_on",
    "benchmarked_on": "evaluated_on",

    "discusses": "discusses",
    "discuss": "discusses",
    "describes": "discusses",
    "describe": "discusses",

    "reports": "reports",
    "report": "reports",
    "reported": "reports",
    "reports result": "reports",

    "based on": "based_on",
    "based_on": "based_on",
    "builds on": "based_on",
    "built on": "based_on",
    "derived from": "based_on",

    "addresses": "addresses",
    "address": "addresses",

    "measures": "measures",
    "measure": "measures",
    "measured": "measures",

    "implements": "implements",
    "implement": "implements",
    "implemented": "implements",

    "extends": "extends",
    "extend": "extends",
    "extended": "extends",

    "improves": "improves",
    "improve": "improves",
    "improved": "improves",

    "compares with": "compares_with",
    "compared with": "compares_with",
    "compares to": "compares_with",
    "compared to": "compares_with",
    "compares_with": "compares_with",
    "compares": "compares_with",

    "has finding": "has_finding",
    "has_finding": "has_finding",

    "has limitation": "has_limitation",
    "has_limitation": "has_limitation",

    "has future work": "has_future_work",
    "has_future_work": "has_future_work",
}


# ============================================================
# GEMINI RESPONSE SCHEMA
# ============================================================

GRAPH_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                    },
                    "type": {
                        "type": "string",
                        "enum": sorted(
                            SUPPORTED_ENTITY_TYPES - {"paper"}
                        ),
                    },
                    "description": {
                        "type": "string",
                    },
                    "evidence": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "chunk_index": {
                                    "type": "integer",
                                },
                                "statement": {
                                    "type": "string",
                                },
                            },
                            "required": [
                                "chunk_index",
                                "statement",
                            ],
                        },
                    },
                },
                "required": [
                    "name",
                    "type",
                    "description",
                    "evidence",
                ],
            },
        },
        "relationships": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source": {
                        "type": "string",
                    },
                    "target": {
                        "type": "string",
                    },
                    "relation": {
                        "type": "string",
                        "enum": sorted(
                            SUPPORTED_RELATION_TYPES
                        ),
                    },
                    "evidence": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "chunk_index": {
                                    "type": "integer",
                                },
                                "statement": {
                                    "type": "string",
                                },
                            },
                            "required": [
                                "chunk_index",
                                "statement",
                            ],
                        },
                    },
                },
                "required": [
                    "source",
                    "target",
                    "relation",
                    "evidence",
                ],
            },
        },
    },
    "required": [
        "entities",
        "relationships",
    ],
}


SEMANTIC_VALIDATION_SCHEMA = {
    "type": "object",
    "properties": {
        "accepted_relationships": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source_id": {
                        "type": "string",
                    },
                    "target_id": {
                        "type": "string",
                    },
                    "relationship": {
                        "type": "string",
                    },
                },
                "required": [
                    "source_id",
                    "target_id",
                    "relationship",
                ],
            },
        },
    },
    "required": [
        "accepted_relationships",
    ],
}


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def normalize_text_for_matching(text: Any) -> str:
    value = str(text or "")

    value = value.replace("\u00a0", " ")
    value = value.replace("\u2013", "-")
    value = value.replace("\u2014", "-")
    value = value.replace("\u2212", "-")

    value = re.sub(r"\s+", " ", value)

    return value.strip().lower()


def normalize_entity_name(name: Any) -> str:
    value = normalize_text_for_matching(name)

    value = re.sub(
        r"[^a-z0-9]+",
        " ",
        value,
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


def normalize_relation(relation: Any) -> str:
    value = normalize_text_for_matching(relation)

    value = value.replace("-", "_")

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return RELATION_ALIASES.get(
        value,
        value,
    )


# ============================================================
# CANONICAL NODE IDS
# ============================================================

def build_entity_id(
    entity_type: str,
    entity_name: str,
) -> str:
    return (
        f"{entity_type}:"
        f"{normalize_entity_name(entity_name)}"
    )


def build_paper_node_id(
    resource_id: str,
) -> str:
    return f"paper:{str(resource_id).strip()}"


# ============================================================
# REFERENCE / METADATA FILTERING
# ============================================================

def looks_like_reference_or_bibliography(
    text: str,
) -> bool:
    normalized = normalize_text_for_matching(text)

    if not normalized:
        return True

    if re.match(
        r"^\s*(references|bibliography|references and bibliography)\s*$",
        normalized,
        flags=re.IGNORECASE,
    ):
        return True

    bibliographic_patterns = [
        r"\barxiv\s*:\s*\d{4}\.\d+",
        r"\bdoi\s*:",
        r"\bvol\.\s*\d+",
        r"\bpp?\.\s*\d+\s*-\s*\d+",
        r"\bpages?\s+\d+\s*-\s*\d+",
        r"\bproc\.\s+",
        r"\bproceedings\b",
        r"\binternational conference\b",
        r"\btechnical report\b",
        r"\bjournal\b.*\b\d{4}\b",
    ]

    signal_count = 0

    for pattern in bibliographic_patterns:
        if re.search(
            pattern,
            normalized,
            flags=re.IGNORECASE,
        ):
            signal_count += 1

    if signal_count >= 2:
        return True

    if (
        re.search(
            r"\(\s*\d{4}\s*\)",
            normalized,
        )
        and (
            "doi" in normalized
            or "arxiv" in normalized
            or "proc." in normalized
            or "proceedings" in normalized
        )
    ):
        return True

    return False


def looks_like_metadata_only_chunk(
    text: str,
) -> bool:
    normalized = normalize_text_for_matching(text)

    if not normalized:
        return True

    word_count = len(
        re.findall(
            r"\b[\w'-]+\b",
            normalized,
        )
    )

    if word_count <= 5:
        return True

    metadata_prefixes = (
        "keywords:",
        "key words:",
        "contents:",
        "references:",
        "bibliography:",
        "acknowledgements:",
        "acknowledgments:",
    )

    return normalized.startswith(
        metadata_prefixes
    )


# ============================================================
# AUTHOR-LIST DETECTION
# ============================================================

def looks_like_author_list(
    text: str,
) -> bool:
    """
    Detects likely author-list passages.

    This is deliberately conservative. A bibliography entry such as:

        Aoran Gan et al. Retrieval Augmented Generation Evaluation...

    must NOT be treated as the current paper's author list.
    """

    if not text:
        return False

    if looks_like_reference_or_bibliography(text):
        return False

    normalized = normalize_text_for_matching(text)

    # Strong author-list indicators.
    author_markers = [
        "authors:",
        "author:",
        "written by",
        "by ",
        "corresponding author",
        "et al.",
    ]

    # "et al." is intentionally NOT sufficient by itself.
    # It frequently occurs in bibliography/reference text.
    if "et al." in normalized:
        if not any(
            marker in normalized
            for marker in (
                "authors:",
                "author:",
                "written by",
                "corresponding author",
            )
        ):
            return False

    if any(
        marker in normalized
        for marker in author_markers
    ):
        return True

    # Typical paper author-list pattern:
    #
    # First Last, First Last, First Last
    #
    # Avoid treating long prose sentences as author lists.
    words = re.findall(
        r"\b[A-Z][a-zA-Z'-]+\b",
        text,
    )

    comma_count = text.count(",")

    if (
        comma_count >= 2
        and 2 <= len(words) <= 25
        and len(text) <= 500
    ):
        lower = normalized

        prose_signals = [
            "the ",
            "this ",
            "we ",
            "our ",
            "is ",
            "are ",
            "was ",
            "were ",
            "propose ",
            "proposed ",
            "method ",
            "model ",
            "dataset ",
            "results ",
        ]

        prose_signal_count = sum(
            1
            for signal in prose_signals
            if signal in lower
        )

        if prose_signal_count <= 1:
            return True

    return False


# ============================================================
# CHUNK QUALITY
# ============================================================

def evidence_chunk_quality(
    chunk: Dict[str, Any],
) -> Tuple[int, str]:
    text = str(
        chunk.get(
            "text",
            "",
        )
    ).strip()

    if not text:
        return 0, "empty"

    if looks_like_reference_or_bibliography(text):
        return 0, "reference_or_bibliography"

    if looks_like_metadata_only_chunk(text):
        return 1, "metadata_or_fragment"

    score = 10

    word_count = len(
        re.findall(
            r"\b[\w'-]+\b",
            text,
        )
    )

    if word_count >= 40:
        score += 2

    if word_count >= 80:
        score += 1

    sentence_count = len(
        re.findall(
            r"[.!?](?:\s|$)",
            text,
        )
    )

    if sentence_count >= 2:
        score += 2

    if re.search(
        r"\b(method|methodology|approach|"
        r"experiment|evaluation|results|"
        r"findings|discussion|conclusion|"
        r"training|testing|dataset|model|"
        r"architecture|authors?)\b",
        text,
        flags=re.IGNORECASE,
    ):
        score += 2

    citation_count = len(
        re.findall(
            r"\[\d+(?:,\s*\d+)*\]",
            text,
        )
    )

    if citation_count >= 4:
        score -= 2

    return score, "research_prose"


def select_high_quality_graph_chunks(
    chunks: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    scored_chunks = []

    for chunk in chunks:
        quality_score, quality_reason = (
            evidence_chunk_quality(chunk)
        )

        if quality_score <= 1:
            print(
                "[KG] Chunk filtered: "
                f"reason={quality_reason}, "
                f"chunk_index={chunk.get('chunk_index')}"
            )
            continue

        qdrant_score = float(
            chunk.get(
                "score",
                0.0,
            )
            or 0.0
        )

        scored_chunks.append(
            (
                quality_score + qdrant_score,
                chunk,
            )
        )

    scored_chunks.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    selected = [
        item[1]
        for item in scored_chunks[:MAX_GRAPH_CHUNKS]
    ]

    selected.sort(
        key=lambda chunk: int(
            chunk.get(
                "chunk_index",
                0,
            )
            or 0
        )
    )

    return selected


# ============================================================
# RETRIEVAL
# ============================================================

GRAPH_RETRIEVAL_QUERIES = [
    "authors author list researchers contributors",
    "paper authors names affiliation corresponding author",
    "method methodology approach algorithm architecture",
    "model models proposed developed trained",
    "dataset benchmark evaluation test experiments",
    "WikiEval MTEB benchmark evaluation dataset",
    "metrics results accuracy precision recall score performance",
    "findings results observations conclusions",
    "problem task challenge research question",
    "concept terminology topic research problem",
    "tool framework library implementation training",
    "limitations weaknesses constraints",
    "future work future research recommendations",
]


def retrieve_graph_chunks(
    resource_id: str,
) -> List[Dict[str, Any]]:
    all_chunks: Dict[
        Tuple[str, str],
        Dict[str, Any],
    ] = {}

    print(
        "[KG] Starting Gemini KG retrieval "
        f"with {len(GRAPH_RETRIEVAL_QUERIES)} focused queries."
    )

    for query_index, query in enumerate(
        GRAPH_RETRIEVAL_QUERIES,
        start=1,
    ):
        print(
            "[KG] Retrieval query "
            f"{query_index}/{len(GRAPH_RETRIEVAL_QUERIES)}: "
            f"{query}"
        )

        try:
            results = search_paper_chunks(
                query=query,
                paper_ids=[resource_id],
                limit=RETRIEVAL_LIMIT,
            )
        except Exception as exc:
            print(
                "[KG] Retrieval query failed: "
                f"{exc}"
            )
            continue

        for result in results:
            text = str(
                result.get(
                    "text",
                    "",
                )
            ).strip()

            if not text:
                continue

            chunk_index = result.get(
                "chunk_index"
            )

            key = (
                str(resource_id),
                str(chunk_index),
            )

            if key not in all_chunks:
                all_chunks[key] = result

    chunks = list(
        all_chunks.values()
    )

    print(
        "[KG] Unique chunks before quality "
        f"filtering: {len(chunks)}"
    )

    if len(chunks) > MAX_RETRIEVED_CHUNKS:
        chunks = sorted(
            chunks,
            key=lambda chunk: float(
                chunk.get(
                    "score",
                    0.0,
                )
                or 0.0
            ),
            reverse=True,
        )[:MAX_RETRIEVED_CHUNKS]

    selected = select_high_quality_graph_chunks(
        chunks
    )

    print(
        "[KG] High-quality chunks selected: "
        f"{len(selected)}"
    )

    print(
        "[KG] Selected chunk indexes: "
        f"{[chunk.get('chunk_index') for chunk in selected]}"
    )

    return selected


# ============================================================
# EVIDENCE CONTEXT
# ============================================================

def build_evidence_context(
    chunks: List[Dict[str, Any]],
) -> str:
    parts = []

    for chunk in chunks:
        chunk_index = chunk.get(
            "chunk_index"
        )

        text = str(
            chunk.get(
                "text",
                "",
            )
        ).strip()

        if not text:
            continue

        text = text[:MAX_CHUNK_CHARS]

        parts.append(
            f"[CHUNK {chunk_index}]\n{text}"
        )

    return "\n\n".join(parts)


# ============================================================
# GEMINI EXTRACTION
# ============================================================

def extract_graph_candidates(
    paper: Dict[str, Any],
    chunks: List[Dict[str, Any]],
) -> Dict[str, Any]:
    resource_id = str(
        paper.get(
            "_id",
            "",
        )
    )

    paper_title = str(
        paper.get(
            "title",
            "Untitled Paper",
        )
    ).strip()

    context = build_evidence_context(
        chunks
    )

    prompt = f"""
You are extracting a high-precision research knowledge graph
from ONE research paper.

PAPER RESOURCE ID:
{resource_id}

PAPER TITLE:
{paper_title}

SOURCE PASSAGES:
{context}

Your job is to identify useful research entities and explicit
relationships supported by the supplied passages.

Use ONLY the supplied passages.

Never use outside knowledge.

Never guess.

Never invent facts.

Every evidence statement MUST be an exact contiguous substring
of one supplied source passage.

============================================================
IMPORTANT EXTRACTION PRIORITY
============================================================

The goal is NOT to extract every noun.

Extract meaningful entities that can participate in a useful
research knowledge graph.

Prefer entities that have a relationship with the current paper
or another extracted entity.

However, do NOT invent relationships simply to make the graph
dense.

The graph must remain evidence-grounded.

============================================================
REFERENCE AND BIBLIOGRAPHY RULE
============================================================

NEVER extract entities or relationships from bibliography or
reference entries.

NEVER extract authors of cited papers.

NEVER extract cited paper titles.

NEVER treat "Author et al. Title..." as the author list of the
current paper.

If a passage clearly describes another paper, citation, reference,
DOI, proceedings, or bibliography entry, ignore it.

============================================================
ALLOWED ENTITY TYPES
============================================================

author
method
dataset
metric
concept
finding
limitation
future_work
problem
organization
tool
model

Do NOT output paper.

The backend creates the current paper node.

============================================================
AUTHOR RULE
============================================================

Extract authors ONLY when the supplied passage represents the
author list of the CURRENT paper.

For example:

"Hao Yu, Aoran Gan, Kai Zhang, Shiwei Tong†, Qi Liu, and
Zhaofeng Liu"

supports these current-paper authors:

Hao Yu
Aoran Gan
Kai Zhang
Shiwei Tong
Qi Liu
Zhaofeng Liu

Ignore:

daggers
asterisks
superscripts
affiliation numbers
contribution symbols
commas
"and"

Do NOT extract authors from a reference.

============================================================
METHOD RULE
============================================================

Extract meaningful methods, approaches, algorithms, architectures,
or techniques when the passage explicitly describes them in the
context of the current work.

Do not extract generic words such as:

method
approach
technique

unless the word is part of a meaningful named method.

============================================================
MODEL RULE
============================================================

Extract models explicitly used, developed, trained, evaluated,
or compared by the current paper.

============================================================
DATASET RULE
============================================================

Extract datasets or benchmarks when the passage explicitly
connects them to the current paper's training, testing,
experimentation, benchmarking, or evaluation.

A dataset description by itself is not enough to create an
evaluated_on relationship.

============================================================
METRIC RULE
============================================================

Extract metrics when the paper actually measures or reports
results using them.

============================================================
FINDING RULE
============================================================

Extract explicit findings or results.

============================================================
LIMITATION RULE
============================================================

Extract explicitly stated limitations, weaknesses, constraints,
or shortcomings.

============================================================
FUTURE WORK RULE
============================================================

Extract explicitly stated future work or recommendations.

============================================================
PROBLEM RULE
============================================================

Extract explicit research problems, challenges, tasks,
research questions, or unresolved problems.

============================================================
CONCEPT RULE
============================================================

Extract meaningful concepts actually discussed by the paper.

Do not extract every technical noun.

============================================================
TOOL RULE
============================================================

Extract software, libraries, frameworks, tools, or training
systems explicitly used by the current work.

============================================================
ORGANIZATION RULE
============================================================

Extract organizations only when the supplied text explicitly
connects the organization to the current paper or its authors.

============================================================
RELATIONSHIPS
============================================================

Allowed relationships:

authored_by
uses
proposed
evaluated_on
discusses
reports
based_on
addresses
measures
implements
extends
improves
compares_with
has_finding
has_limitation
has_future_work

A relationship must be explicitly supported by one evidence
statement.

Do NOT infer relationships merely because two entities appear
in the same passage.

============================================================
CURRENT PAPER
============================================================

The backend creates the current paper node.

You may represent the current paper using its exact title:

"{paper_title}"

For relationships involving the current paper, the paper title
does NOT need to occur in the evidence because the backend knows
which paper supplied the passage.

The non-paper endpoint MUST occur in the evidence.

Examples:

Current Paper -> uses -> LoRA

Current Paper -> evaluated_on -> MTEB benchmark

Current Paper -> measures -> Error detection rate

Current Paper -> addresses -> hallucination

============================================================
AUTHOR RELATIONSHIPS
============================================================

If the source passage is the current paper's author list, create:

Current Paper -> authored_by -> Author

for every explicitly listed current-paper author.

The author-list passage itself is sufficient evidence.

Do NOT create authored_by from a bibliography sentence.

============================================================
EVALUATION RELATIONSHIPS
============================================================

Create:

Current Paper -> evaluated_on -> Dataset

ONLY when the evidence explicitly says that the current paper,
model, method, system, or approach was evaluated, tested,
benchmarked, experimented on, or assessed using that dataset
or benchmark.

Valid:

"We evaluate the trained model on the MTEB benchmark."

Valid:

"Experiments are conducted on WikiEval."

Invalid:

"WikiEval Post-2022 Wikipedia Manually labeled"

Invalid:

"WikiEval is a dataset containing..."

A dataset description alone does NOT establish evaluated_on.

============================================================
ENTITY-TO-ENTITY RELATIONSHIPS
============================================================

For entity-to-entity relationships, BOTH endpoints must occur
in the SAME evidence statement.

Example:

"our method extends BERT"

supports:

Method -> extends -> BERT

============================================================
EVIDENCE
============================================================

Every entity needs at least one evidence item.

Every relationship needs at least one evidence item.

Each evidence item must contain:

chunk_index
statement

The statement must be copied exactly and contiguously from the
source passage.

Do not paraphrase.

Do not use ellipses.

Do not combine multiple passages.

============================================================
PRECISION
============================================================

When uncertain, do not create the entity.

When uncertain, do not create the relationship.

Do not create edges just to make the graph connected.

Maximum entities: {MAX_GRAPH_ENTITIES}

Maximum relationships: {MAX_GRAPH_RELATIONSHIPS}

============================================================
FINAL CHECK
============================================================

Before returning JSON verify:

1. Every entity has an allowed type.
2. Every entity has evidence.
3. Every entity name occurs in its evidence.
4. Every evidence statement exists exactly in the supplied text.
5. Every relationship has evidence.
6. Current-paper relationships contain the non-paper endpoint
   in the evidence.
7. Entity-to-entity relationships contain both endpoints in
   the same evidence.
8. authored_by comes only from the current paper's author list.
9. evaluated_on requires explicit evaluation/testing/benchmarking.
10. Dataset descriptions alone do not create evaluated_on.
11. Bibliography entries are ignored.
12. Cited paper authors are ignored.
13. Prefer useful connected entities over isolated nouns.
14. Do not invent edges.

Return JSON only.
"""

    print(
        "[KG] Calling Gemini for graph extraction..."
    )

    start_time = time.time()

    try:
        result = call_gemini_json(
            prompt,
            GRAPH_EXTRACTION_SCHEMA,
        )
    except Exception as exc:
        elapsed = time.time() - start_time

        print(
            "[KG] Gemini graph extraction failed "
            f"after {elapsed:.2f}s: {exc}"
        )

        raise HTTPException(
            status_code=502,
            detail=(
                "Gemini knowledge graph extraction failed: "
                f"{exc}"
            ),
        )

    elapsed = time.time() - start_time

    print(
        "[KG] Gemini graph extraction completed "
        f"in {elapsed:.2f}s."
    )

    if not isinstance(result, dict):
        print(
            "[KG] Gemini returned a non-object response."
        )
        result = {}

    entities = result.get(
        "entities",
        [],
    )

    relationships = result.get(
        "relationships",
        [],
    )

    if not isinstance(
        entities,
        list,
    ):
        entities = []

    if not isinstance(
        relationships,
        list,
    ):
        relationships = []

    result["entities"] = entities[
        :MAX_GRAPH_ENTITIES
    ]

    result["relationships"] = relationships[
        :MAX_GRAPH_RELATIONSHIPS
    ]

    print(
        "[KG DEBUG] Gemini proposed "
        f"{len(result['entities'])} entities and "
        f"{len(result['relationships'])} relationships."
    )

    if result["entities"]:
        print(
            "[KG DEBUG] Gemini entities:"
        )

        for entity in result["entities"]:
            print(
                "   -",
                entity.get("type"),
                ":",
                entity.get("name"),
            )
    else:
        print(
            "[KG WARNING] Gemini returned ZERO entities."
        )

    for relationship in result["relationships"]:
        print(
            "[KG DEBUG] Gemini relationship candidate:",
            relationship.get("source"),
            "->",
            relationship.get("relation"),
            "->",
            relationship.get("target"),
        )

    return result


# ============================================================
# CHUNK LOOKUP
# ============================================================

def find_chunk_text(
    chunks: List[Dict[str, Any]],
    chunk_index: Any,
) -> str:
    target = str(chunk_index)

    for chunk in chunks:
        if str(
            chunk.get(
                "chunk_index"
            )
        ) == target:
            return str(
                chunk.get(
                    "text",
                    "",
                )
            )

    return ""


# ============================================================
# EVIDENCE VALIDATION
# ============================================================

def statement_is_supported_by_chunk(
    statement: str,
    chunk_text: str,
) -> bool:
    if not statement:
        return False

    statement_normalized = (
        normalize_text_for_matching(
            statement
        )
    )

    chunk_normalized = (
        normalize_text_for_matching(
            chunk_text
        )
    )

    if not statement_normalized:
        return False

    if not chunk_normalized:
        return False

    return statement_normalized in chunk_normalized


def get_valid_evidence(
    evidence: Any,
    chunks: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not isinstance(
        evidence,
        list,
    ):
        return []

    valid = []
    seen = set()

    for item in evidence:
        if not isinstance(
            item,
            dict,
        ):
            continue

        chunk_index = item.get(
            "chunk_index"
        )

        statement = str(
            item.get(
                "statement",
                "",
            )
        ).strip()

        if chunk_index is None:
            continue

        chunk_text = find_chunk_text(
            chunks,
            chunk_index,
        )

        if not statement_is_supported_by_chunk(
            statement,
            chunk_text,
        ):
            continue

        key = (
            str(chunk_index),
            statement,
        )

        if key in seen:
            continue

        seen.add(key)

        valid.append(
            {
                "chunk_index": chunk_index,
                "statement": statement,
            }
        )

    return valid[
        :MAX_EVIDENCE_PER_EDGE
    ]


# ============================================================
# ENTITY VALIDATION
# ============================================================

def validate_entity_candidates(
    candidates: Dict[str, Any],
    chunks: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    raw_entities = candidates.get(
        "entities",
        [],
    )

    if not isinstance(
        raw_entities,
        list,
    ):
        return []

    validated = []
    seen_entity_keys = set()

    for entity in raw_entities:
        if not isinstance(
            entity,
            dict,
        ):
            continue

        name = str(
            entity.get(
                "name",
                "",
            )
        ).strip()

        entity_type = str(
            entity.get(
                "type",
                "",
            )
        ).strip().lower()

        description = str(
            entity.get(
                "description",
                "",
            )
        ).strip()

        if not name:
            continue

        if "|" in entity_type:
            continue

        if "/" in entity_type:
            continue

        if entity_type not in (
            SUPPORTED_ENTITY_TYPES - {"paper"}
        ):
            continue

        normalized_name = normalize_entity_name(
            name
        )

        if not normalized_name:
            continue

        entity_key = (
            entity_type,
            normalized_name,
        )

        if entity_key in seen_entity_keys:
            continue

        valid_evidence = get_valid_evidence(
            entity.get(
                "evidence",
                [],
            ),
            chunks,
        )

        if not valid_evidence:
            print(
                "[KG] Entity rejected: invalid evidence | "
                f"{name}"
            )
            continue

        name_supported = False

        for evidence_item in valid_evidence:
            statement_normalized = (
                normalize_text_for_matching(
                    evidence_item["statement"]
                )
            )

            name_normalized = (
                normalize_text_for_matching(
                    name
                )
            )

            if name_normalized in statement_normalized:
                name_supported = True
                break

        if not name_supported:
            print(
                "[KG] Entity rejected: name not present "
                f"in evidence | {name}"
            )
            continue

        # ----------------------------------------------------
        # Authors must not come from bibliography/reference text.
        # ----------------------------------------------------

        if entity_type == "author":
            if not any(
                looks_like_author_list(
                    evidence_item["statement"]
                )
                for evidence_item in valid_evidence
            ):
                print(
                    "[KG] Author rejected: evidence does not "
                    f"look like current-paper author list | {name}"
                )
                continue

        entity_id = build_entity_id(
            entity_type,
            name,
        )

        validated.append(
            {
                "id": entity_id,
                "name": name,
                "type": entity_type,
                "description": description,
                "evidence": valid_evidence,
            }
        )

        seen_entity_keys.add(
            entity_key
        )

    print(
        "[KG] Deterministically validated "
        f"{len(validated)} entities."
    )

    return validated


# ============================================================
# RELATIONSHIP LANGUAGE
# ============================================================

def explicit_relation_language_exists(
    relation: str,
    statement: str,
) -> bool:
    text = normalize_text_for_matching(
        statement
    )

    patterns = {
        "authored_by": [
            r"\bauthors?\b",
            r"\bauthored\b",
            r"\bwritten\s+by\b",
        ],

        "uses": [
            r"\buse(?:s|d)?\b",
            r"\butiliz(?:e|es|ed|ing)\b",
            r"\bapply(?:ing|ies|ied)?\b",
            r"\bemploy(?:s|ed|ing)?\b",
        ],

        "proposed": [
            r"\bpropose(?:s|d)?\b",
            r"\bintroduce(?:s|d)?\b",
            r"\bpresent(?:s|ed)?\b",
            r"\bdevelop(?:s|ed|ing)?\b",
        ],

        "evaluated_on": [
            r"\bevaluat(?:e|es|ed|ing)\b",
            r"\btest(?:s|ed|ing)?\b",
            r"\bbenchmark(?:ed|ing)?\b",
            r"\bassess(?:es|ed|ing)\b",
            r"\bexperiment(?:s|ed|ing)?\b",
            r"\bexperiment(?:s)?\s+are\s+conducted\b",
        ],

        "discusses": [
            r"\bdiscuss(?:es|ed|ing)?\b",
            r"\bexplor(?:e|es|ed|ing)\b",
            r"\bexamin(?:e|es|ed|ing)\b",
            r"\bfocus(?:es|ed|ing)?\s+on\b",
        ],

        "reports": [
            r"\breport(?:s|ed|ing)?\b",
            r"\bachiev(?:e|es|ed|ing)\b",
            r"\bobtain(?:s|ed|ing)?\b",
        ],

        "based_on": [
            r"\bbased\s+on\b",
            r"\bfollow(?:s|ed|ing)?\b",
            r"\binspired\s+by\b",
            r"\bbuild(?:s|ing)?\s+on\b",
        ],

        "addresses": [
            r"\baddress(?:es|ed|ing)?\b",
            r"\btackle(?:s|d|ing)?\b",
            r"\bsolve(?:s|d|ing)?\b",
            r"\bmitigat(?:e|es|ed|ing)\b",
        ],

        "measures": [
            r"\bmeasure(?:s|d|ing)?\b",
            r"\bmetric\b",
            r"\bquantif(?:y|ies|ied|ying)\b",
        ],

        "implements": [
            r"\bimplement(?:s|ed|ing)?\b",
            r"\bimplementation\b",
            r"\brealiz(?:e|es|ed|ing)\b",
        ],

        "extends": [
            r"\bextend(?:s|ed|ing)?\b",
            r"\bextension\b",
            r"\bbuild(?:s|ing)?\s+upon\b",
        ],

        "improves": [
            r"\bimprov(?:e|es|ed|ing)\b",
            r"\benhanc(?:e|es|ed|ing)\b",
            r"\bboost(?:s|ed|ing)?\b",
        ],

        "compares_with": [
            r"\bcompar(?:e|es|ed|ing)\b",
            r"\bversus\b",
            r"\bvs\.?\b",
            r"\bagainst\b",
        ],

        "has_finding": [
            r"\bfind(?:s|ing|ings)?\b",
            r"\bshow(?:s|ed|ing)?\b",
            r"\bdemonstrat(?:e|es|ed|ing)\b",
            r"\bresult(?:s|ed|ing)?\b",
        ],

        "has_limitation": [
            r"\blimitation(?:s)?\b",
            r"\blimit(?:s|ed|ing)?\b",
            r"\bconstraint(?:s)?\b",
            r"\bshortcoming(?:s)?\b",
        ],

        "has_future_work": [
            r"\bfuture\s+work\b",
            r"\bfuture\s+research\b",
            r"\bwe\s+plan\b",
            r"\bwill\s+explore\b",
            r"\bnext\s+step(?:s)?\b",
        ],
    }

    relation_patterns = patterns.get(
        relation,
        [],
    )

    return any(
        re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )
        for pattern in relation_patterns
    )


# ============================================================
# EVALUATION EVIDENCE
# ============================================================

def explicit_evaluation_language_exists(
    statement: str,
) -> bool:
    text = normalize_text_for_matching(
        statement
    )

    patterns = [
        r"\bevaluat(?:e|es|ed|ing)\b",
        r"\btest(?:s|ed|ing)?\b",
        r"\bbenchmark(?:ed|ing)?\b",
        r"\bassess(?:es|ed|ing)\b",
        r"\bexperiment(?:s|ed|ing)?\b",
        r"\bexperiments?\s+are\s+conducted\b",
        r"\bwe\s+evaluate\b",
        r"\bwe\s+test\b",
        r"\bwe\s+benchmark\b",
        r"\bwe\s+experiment\b",
    ]

    return any(
        re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )
        for pattern in patterns
    )


# ============================================================
# ENTITY RESOLUTION
# ============================================================

def resolve_entity_id(
    name: str,
    entity_map: Dict[str, Dict[str, Any]],
    paper_id: str,
    paper_name: str,
) -> str | None:
    normalized_name = normalize_entity_name(
        name
    )

    if not normalized_name:
        return None

    paper_names = {
        normalize_entity_name(paper_name),
        normalize_entity_name(
            paper_name.replace("_", " ")
        ),
    }

    if normalized_name in paper_names:
        return paper_id

    for entity_id, entity in entity_map.items():
        entity_name = str(
            entity.get(
                "name",
                "",
            )
        )

        if (
            normalize_entity_name(
                entity_name
            )
            == normalized_name
        ):
            return entity_id

    return None


# ============================================================
# RELATIONSHIP VALIDATION
# ============================================================

def validate_relationship_candidates(
    candidates: Dict[str, Any],
    entities: List[Dict[str, Any]],
    paper: Dict[str, Any],
    chunks: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:

    raw_relationships = candidates.get(
        "relationships",
        [],
    )

    if not isinstance(
        raw_relationships,
        list,
    ):
        return []

    entity_map: Dict[
        str,
        Dict[str, Any],
    ] = {}

    for entity in entities:
        entity_id = entity.get("id")

        if entity_id:
            entity_map[entity_id] = entity

    paper_id = build_paper_node_id(
        str(paper["_id"])
    )

    paper_name = str(
        paper.get("title")
        or paper.get("name")
        or paper.get("filename")
        or paper["_id"]
    ).strip()

    entity_map[paper_id] = {
        "id": paper_id,
        "name": paper_name,
        "type": "paper",
        "description": "",
        "evidence": [],
    }

    validated = []

    print(
        "[KG DEBUG] Starting deterministic relationship "
        f"validation for {len(raw_relationships)} candidates."
    )

    for candidate_index, candidate in enumerate(
        raw_relationships,
        start=1,
    ):
        if not isinstance(
            candidate,
            dict,
        ):
            continue

        relation = normalize_relation(
            candidate.get(
                "relation",
                candidate.get(
                    "relationship",
                    "",
                ),
            )
        )

        if relation not in SUPPORTED_RELATION_TYPES:
            print(
                "[KG DEBUG] Relationship rejected: "
                f"unsupported relation | {relation}"
            )
            continue

        source_name = str(
            candidate.get(
                "source",
                "",
            )
        ).strip()

        target_name = str(
            candidate.get(
                "target",
                "",
            )
        ).strip()

        if not source_name or not target_name:
            continue

        print(
            "[KG DEBUG] Checking relationship "
            f"{candidate_index}: "
            f"{source_name} -> {relation} -> {target_name}"
        )

        source_id = resolve_entity_id(
            source_name,
            entity_map,
            paper_id,
            paper_name,
        )

        target_id = resolve_entity_id(
            target_name,
            entity_map,
            paper_id,
            paper_name,
        )

        if not source_id:
            print(
                "[KG DEBUG] Relationship rejected: "
                f"source not found | {source_name}"
            )
            continue

        if not target_id:
            print(
                "[KG DEBUG] Relationship rejected: "
                f"target not found | {target_name}"
            )
            continue

        if source_id == target_id:
            continue

        raw_evidence = candidate.get(
            "evidence",
            [],
        )

        valid_evidence = get_valid_evidence(
            raw_evidence,
            chunks,
        )

        if not valid_evidence:
            print(
                "[KG DEBUG] Relationship rejected: "
                "no valid evidence."
            )
            continue

        source_entity = entity_map[
            source_id
        ]

        target_entity = entity_map[
            target_id
        ]

        source_is_paper = (
            source_id == paper_id
        )

        target_is_paper = (
            target_id == paper_id
        )

        relationship_accepted = False
        accepted_evidence = []

        for evidence_item in valid_evidence:
            statement = evidence_item[
                "statement"
            ]

            statement_normalized = (
                normalize_text_for_matching(
                    statement
                )
            )

            source_normalized = (
                normalize_text_for_matching(
                    str(
                        source_entity.get(
                            "name",
                            "",
                        )
                    )
                )
            )

            target_normalized = (
                normalize_text_for_matching(
                    str(
                        target_entity.get(
                            "name",
                            "",
                        )
                    )
                )
            )

            source_present = (
                bool(source_normalized)
                and source_normalized
                in statement_normalized
            )

            target_present = (
                bool(target_normalized)
                and target_normalized
                in statement_normalized
            )

            # ------------------------------------------------
            # Endpoint validation
            # ------------------------------------------------

            if source_is_paper and not target_is_paper:
                if not target_present:
                    continue

            elif target_is_paper and not source_is_paper:
                if not source_present:
                    continue

            else:
                if not source_present:
                    continue

                if not target_present:
                    continue

            # ------------------------------------------------
            # Authored-by validation
            # ------------------------------------------------

            if relation == "authored_by":
                if not source_is_paper:
                    if not explicit_relation_language_exists(
                        relation,
                        statement,
                    ):
                        continue

                if not looks_like_author_list(
                    statement
                ):
                    print(
                        "[KG DEBUG] authored_by rejected: "
                        "evidence does not look like current "
                        f"paper author list | {statement[:150]}"
                    )
                    continue

            # ------------------------------------------------
            # Evaluation validation
            # ------------------------------------------------

            elif relation == "evaluated_on":
                if not explicit_evaluation_language_exists(
                    statement
                ):
                    print(
                        "[KG DEBUG] evaluated_on rejected: "
                        "no explicit evaluation language."
                    )
                    continue

            # ------------------------------------------------
            # All other relationship validation
            # ------------------------------------------------

            else:
                if not explicit_relation_language_exists(
                    relation,
                    statement,
                ):
                    continue

            relationship_accepted = True
            accepted_evidence.append(
                evidence_item
            )
            break

        if not relationship_accepted:
            print(
                "[KG DEBUG] Relationship rejected after "
                "endpoint/language validation: "
                f"{source_name} -> {relation} -> {target_name}"
            )
            continue

        validated_relationship = {
            "id": (
                f"{source_id}"
                f"__{relation}"
                f"__{target_id}"
            ),
            "source": source_id,
            "target": target_id,
            "relationship": relation,
            "resource_ids": [
                str(paper["_id"])
            ],
            "evidence": (
                accepted_evidence
                or valid_evidence[:MAX_EVIDENCE_PER_EDGE]
            ),
        }

        validated.append(
            validated_relationship
        )

        print(
            "[KG DEBUG] Relationship accepted: "
            f"{source_name} -> {relation} -> {target_name}"
        )

    # --------------------------------------------------------
    # Deduplicate
    # --------------------------------------------------------

    unique: Dict[
        Tuple[str, str, str],
        Dict[str, Any],
    ] = {}

    for relationship in validated:
        key = (
            relationship["source"],
            relationship["target"],
            relationship["relationship"],
        )

        if key not in unique:
            unique[key] = relationship
            continue

        existing = unique[key]

        for resource_id in relationship.get(
            "resource_ids",
            [],
        ):
            if resource_id not in existing[
                "resource_ids"
            ]:
                existing[
                    "resource_ids"
                ].append(
                    resource_id
                )

        existing_evidence_keys = {
            (
                str(
                    item.get(
                        "chunk_index"
                    )
                ),
                item.get(
                    "statement",
                    "",
                ),
            )
            for item in existing.get(
                "evidence",
                [],
            )
        }

        for evidence in relationship.get(
            "evidence",
            [],
        ):
            if len(
                existing["evidence"]
            ) >= MAX_EVIDENCE_PER_EDGE:
                break

            evidence_key = (
                str(
                    evidence.get(
                        "chunk_index"
                    )
                ),
                evidence.get(
                    "statement",
                    "",
                ),
            )

            if evidence_key not in existing_evidence_keys:
                existing[
                    "evidence"
                ].append(
                    evidence
                )

                existing_evidence_keys.add(
                    evidence_key
                )

    final = list(
        unique.values()
    )

    print(
        "[KG DEBUG] Deterministic relationship validation "
        f"completed: {len(final)} valid relationships."
    )

    return final


# ============================================================
# SEMANTIC RELATIONSHIP VALIDATION
# ============================================================

def semantic_validate_relationships(
    entities: List[Dict[str, Any]],
    relationships: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:

    if not relationships:
        return []

    entity_map = {
        entity["id"]: entity
        for entity in entities
    }

    compact_relationships = []

    for relationship in relationships:
        source = entity_map.get(
            relationship["source"]
        )

        target = entity_map.get(
            relationship["target"]
        )

        if not source or not target:
            continue

        compact_relationships.append(
            {
                "source_id": source["id"],
                "source": source["name"],
                "source_type": source["type"],
                "target_id": target["id"],
                "target": target["name"],
                "target_type": target["type"],
                "relationship": relationship[
                    "relationship"
                ],
            }
        )

    if not compact_relationships:
        return relationships

    compact_entities = [
        {
            "id": entity["id"],
            "name": entity["name"],
            "type": entity["type"],
        }
        for entity in entities
    ]

    prompt = f"""
You are performing a semantic sanity check on relationships
in an evidence-grounded research knowledge graph.

All supplied relationships have ALREADY passed deterministic
evidence validation.

You may ONLY accept or reject the supplied relationships.

You MUST NOT:

- create new relationships
- reverse relationships
- rename entities
- modify relationship types
- infer additional relationships

ENTITIES:

{compact_entities}

RELATIONSHIPS:

{compact_relationships}

Accept a relationship when its direction and type are reasonable.

Examples:

paper -> authored_by -> author
paper -> uses -> method
paper -> proposed -> method
paper -> evaluated_on -> dataset
paper -> reports -> finding
paper -> discusses -> concept
paper -> addresses -> problem
paper -> has_limitation -> limitation
paper -> has_future_work -> future_work

method -> based_on -> model
method -> extends -> method
method -> improves -> method
method -> compares_with -> model

IMPORTANT:

Deterministic validation has already established explicit evidence.

Do not reject a relationship simply because the paper identity is
implicit in the evidence.

When uncertain, ACCEPT rather than destroying a relationship that
has already passed evidence validation.

Return ONLY JSON matching the supplied schema.
"""

    print(
        "[KG] Calling Gemini for semantic "
        "relationship validation..."
    )

    start_time = time.time()

    try:
        result = call_gemini_json(
            prompt,
            SEMANTIC_VALIDATION_SCHEMA,
        )
    except Exception as exc:
        elapsed = time.time() - start_time

        print(
            "[KG] Semantic validation failed "
            f"after {elapsed:.2f}s: {exc}"
        )

        print(
            "[KG] Keeping deterministic relationships."
        )

        return relationships

    elapsed = time.time() - start_time

    print(
        "[KG] Gemini semantic validation completed "
        f"in {elapsed:.2f}s."
    )

    print(
        "[KG DEBUG] Gemini semantic validation response:",
        result,
    )

    accepted = result.get(
        "accepted_relationships",
        [],
    )

    if not isinstance(
        accepted,
        list,
    ):
        return relationships

    if not accepted:
        print(
            "[KG] Gemini returned zero accepted relationships."
        )

        print(
            "[KG] Preserving deterministic evidence-backed "
            "relationships."
        )

        return relationships

    valid_keys = {
        (
            item["source_id"],
            item["target_id"],
            normalize_relation(
                item["relationship"]
            ),
        )
        for item in compact_relationships
    }

    accepted_keys = set()

    for item in accepted:
        if not isinstance(
            item,
            dict,
        ):
            continue

        source_id = str(
            item.get(
                "source_id",
                "",
            )
        ).strip()

        target_id = str(
            item.get(
                "target_id",
                "",
            )
        ).strip()

        relationship = normalize_relation(
            item.get(
                "relationship",
                "",
            )
        )

        key = (
            source_id,
            target_id,
            relationship,
        )

        if key in valid_keys:
            accepted_keys.add(
                key
            )

    if not accepted_keys:
        print(
            "[KG] Gemini returned no matching "
            "relationship keys."
        )

        print(
            "[KG] Preserving deterministic relationships."
        )

        return relationships

    final_relationships = []

    for relationship in relationships:
        key = (
            relationship["source"],
            relationship["target"],
            normalize_relation(
                relationship["relationship"]
            ),
        )

        if key in accepted_keys:
            final_relationships.append(
                relationship
            )

    if not final_relationships:
        return relationships

    print(
        "[KG] Semantically accepted "
        f"{len(final_relationships)} relationships "
        f"out of {len(relationships)}."
    )

    return final_relationships


# ============================================================
# NODE MERGING
# ============================================================

def merge_entity_into_graph(
    graph_nodes: Dict[str, Dict[str, Any]],
    entity: Dict[str, Any],
    resource_id: str,
) -> None:
    entity_id = entity["id"]

    existing = graph_nodes.get(
        entity_id
    )

    if existing is None:
        graph_nodes[entity_id] = {
            "id": entity_id,
            "name": entity["name"],
            "type": entity["type"],
            "description": entity.get(
                "description",
                "",
            ),
            "resource_ids": [
                resource_id
            ],
            "evidence": list(
                entity.get(
                    "evidence",
                    [],
                )
            )[:MAX_EVIDENCE_PER_NODE],
        }

        return

    if resource_id not in existing[
        "resource_ids"
    ]:
        existing[
            "resource_ids"
        ].append(
            resource_id
        )

    existing_evidence_keys = {
        (
            str(
                item.get(
                    "chunk_index"
                )
            ),
            item.get(
                "statement",
                "",
            ),
        )
        for item in existing[
            "evidence"
        ]
        if isinstance(
            item,
            dict,
        )
    }

    for evidence_item in entity.get(
        "evidence",
        [],
    ):
        if len(
            existing["evidence"]
        ) >= MAX_EVIDENCE_PER_NODE:
            break

        if not isinstance(
            evidence_item,
            dict,
        ):
            continue

        evidence_key = (
            str(
                evidence_item.get(
                    "chunk_index"
                )
            ),
            evidence_item.get(
                "statement",
                "",
            ),
        )

        if evidence_key not in existing_evidence_keys:
            existing[
                "evidence"
            ].append(
                evidence_item
            )

            existing_evidence_keys.add(
                evidence_key
            )

    if (
        not existing.get(
            "description"
        )
        and entity.get(
            "description"
        )
    ):
        existing[
            "description"
        ] = entity[
            "description"
        ]


# ============================================================
# PAPER NODE
# ============================================================

def build_paper_node(
    paper: Dict[str, Any],
) -> Dict[str, Any]:
    resource_id = str(
        paper.get(
            "_id",
            "",
        )
    )

    title = str(
        paper.get(
            "title",
            "Untitled Paper",
        )
    ).strip()

    return {
        "id": build_paper_node_id(
            resource_id
        ),
        "name": title,
        "type": "paper",
        "description": "",
        "resource_ids": [
            resource_id
        ],
        "evidence": [],
    }


# ============================================================
# EDGE MERGING
# ============================================================

def merge_relationship_into_graph(
    graph_edges: Dict[
        Tuple[str, str, str],
        Dict[str, Any],
    ],
    relationship: Dict[str, Any],
) -> None:
    key = (
        relationship["source"],
        relationship["target"],
        relationship["relationship"],
    )

    existing = graph_edges.get(
        key
    )

    if existing is None:
        graph_edges[key] = {
            "id": (
                f"{relationship['source']}"
                f"__{relationship['relationship']}"
                f"__{relationship['target']}"
            ),
            "source": relationship[
                "source"
            ],
            "target": relationship[
                "target"
            ],
            "relationship": relationship[
                "relationship"
            ],
            "resource_ids": list(
                relationship.get(
                    "resource_ids",
                    [],
                )
            ),
            "evidence": list(
                relationship.get(
                    "evidence",
                    [],
                )
            )[:MAX_EVIDENCE_PER_EDGE],
        }

        return

    for resource_id in relationship.get(
        "resource_ids",
        [],
    ):
        if resource_id not in existing[
            "resource_ids"
        ]:
            existing[
                "resource_ids"
            ].append(
                resource_id
            )

    existing_evidence_keys = {
        (
            str(
                item.get(
                    "chunk_index"
                )
            ),
            item.get(
                "statement",
                "",
            ),
        )
        for item in existing[
            "evidence"
        ]
        if isinstance(
            item,
            dict,
        )
    }

    for evidence_item in relationship.get(
        "evidence",
        [],
    ):
        if len(
            existing["evidence"]
        ) >= MAX_EVIDENCE_PER_EDGE:
            break

        if not isinstance(
            evidence_item,
            dict,
        ):
            continue

        evidence_key = (
            str(
                evidence_item.get(
                    "chunk_index"
                )
            ),
            evidence_item.get(
                "statement",
                "",
            ),
        )

        if evidence_key not in existing_evidence_keys:
            existing[
                "evidence"
            ].append(
                evidence_item
            )

            existing_evidence_keys.add(
                evidence_key
            )


# ============================================================
# PAPER LOOKUP
# ============================================================

def get_paper_by_resource_id(
    resource_id: str,
) -> Dict[str, Any] | None:
    try:
        paper = papers_collection.find_one(
            {
                "_id": str(
                    resource_id
                )
            }
        )

        return paper

    except Exception as exc:
        print(
            "[KG] MongoDB lookup failed: "
            f"{exc}"
        )

        return None


# ============================================================
# REMOVE ORPHAN ENTITIES
# ============================================================

def remove_orphan_entities(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Keep:

    - every paper node
    - every entity participating in at least one valid edge

    This prevents isolated extracted nouns from polluting the
    final research knowledge graph.
    """

    connected_ids = set()

    for edge in edges:
        source = edge.get(
            "source"
        )

        target = edge.get(
            "target"
        )

        if source:
            connected_ids.add(
                source
            )

        if target:
            connected_ids.add(
                target
            )

    filtered = []

    removed = 0

    for node in nodes:
        node_id = node.get(
            "id"
        )

        node_type = node.get(
            "type"
        )

        if node_type == "paper":
            filtered.append(
                node
            )
            continue

        if node_id in connected_ids:
            filtered.append(
                node
            )
        else:
            removed += 1

    print(
        "[KG] Removed orphan entities: "
        f"{removed}"
    )

    return filtered


# ============================================================
# SINGLE PAPER PROCESSING
# ============================================================

def process_single_paper(
    resource_id: str,
) -> Dict[str, Any]:
    print(
        "[KG] ----------------------------------------"
    )

    print(
        "[KG] Processing paper: "
        f"{resource_id}"
    )

    paper = get_paper_by_resource_id(
        resource_id
    )

    if not paper:
        return {
            "processed": False,
            "resource_id": resource_id,
            "reason": "Paper not found in MongoDB.",
            "nodes": [],
            "edges": [],
        }

    title = str(
        paper.get(
            "title",
            resource_id,
        )
    ).strip()

    print(
        "[KG] Paper: "
        f"{title}"
    )

    chunks = retrieve_graph_chunks(
        resource_id
    )

    if not chunks:
        return {
            "processed": True,
            "resource_id": resource_id,
            "reason": "No usable evidence chunks found.",
            "nodes": [
                build_paper_node(
                    paper
                )
            ],
            "edges": [],
        }

    candidates = extract_graph_candidates(
        paper,
        chunks,
    )

    validated_entities = (
        validate_entity_candidates(
            candidates,
            chunks,
        )
    )

    validated_relationships = (
        validate_relationship_candidates(
            candidates,
            validated_entities,
            paper,
            chunks,
        )
    )

    print(
        "[KG DEBUG] Deterministic relationships before "
        f"semantic validation: {len(validated_relationships)}"
    )

    semantic_entities = list(
        validated_entities
    )

    semantic_entities.append(
        {
            "id": build_paper_node_id(
                resource_id
            ),
            "name": title,
            "type": "paper",
            "description": "",
            "evidence": [],
        }
    )

    final_relationships = (
        semantic_validate_relationships(
            semantic_entities,
            validated_relationships,
        )
    )

    print(
        "[KG DEBUG] Final relationships after semantic "
        f"validation: {len(final_relationships)}"
    )

    nodes = [
        build_paper_node(
            paper
        )
    ]

    for entity in validated_entities:
        nodes.append(
            {
                "id": entity["id"],
                "name": entity["name"],
                "type": entity["type"],
                "description": entity.get(
                    "description",
                    "",
                ),
                "resource_ids": [
                    resource_id
                ],
                "evidence": entity.get(
                    "evidence",
                    [],
                ),
            }
        )

    # Important:
    # Only keep entities which actually participate in a
    # validated relationship.
    nodes = remove_orphan_entities(
        nodes,
        final_relationships,
    )

    edges = list(
        final_relationships
    )

    print(
        "[KG] Paper graph result: "
        f"{len(nodes)} nodes, "
        f"{len(edges)} edges."
    )

    return {
        "processed": True,
        "resource_id": resource_id,
        "reason": "",
        "nodes": nodes,
        "edges": edges,
    }


# ============================================================
# GRAPH STATISTICS
# ============================================================

def build_graph_statistics(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
) -> Dict[str, Any]:
    node_type_counts: Dict[
        str,
        int,
    ] = {}

    edge_type_counts: Dict[
        str,
        int,
    ] = {}

    for node in nodes:
        node_type = str(
            node.get(
                "type",
                "unknown",
            )
        )

        node_type_counts[
            node_type
        ] = (
            node_type_counts.get(
                node_type,
                0,
            )
            + 1
        )

    for edge in edges:
        relationship = str(
            edge.get(
                "relationship",
                "unknown",
            )
        )

        edge_type_counts[
            relationship
        ] = (
            edge_type_counts.get(
                relationship,
                0,
            )
            + 1
        )

    return {
        "node_types": node_type_counts,
        "relationship_types": edge_type_counts,
    }


# ============================================================
# GRAPH NODE METADATA
# ============================================================

def enrich_graph_nodes(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
) -> None:
    degree_map: Dict[str, int] = {}
    in_degree_map: Dict[str, int] = {}
    out_degree_map: Dict[str, int] = {}

    # Actual papers represented by an entity through edges.
    entity_papers: Dict[
        str,
        set,
    ] = {}

    for edge in edges:
        source = edge.get(
            "source"
        )

        target = edge.get(
            "target"
        )

        resource_ids = edge.get(
            "resource_ids",
            [],
        )

        if not isinstance(
            resource_ids,
            list,
        ):
            resource_ids = []

        if source:
            degree_map[source] = (
                degree_map.get(
                    source,
                    0,
                )
                + 1
            )

            out_degree_map[source] = (
                out_degree_map.get(
                    source,
                    0,
                )
                + 1
            )

            entity_papers.setdefault(
                source,
                set(),
            ).update(
                str(resource_id)
                for resource_id in resource_ids
                if resource_id
            )

        if target:
            degree_map[target] = (
                degree_map.get(
                    target,
                    0,
                )
                + 1
            )

            in_degree_map[target] = (
                in_degree_map.get(
                    target,
                    0,
                )
                + 1
            )

            entity_papers.setdefault(
                target,
                set(),
            ).update(
                str(resource_id)
                for resource_id in resource_ids
                if resource_id
            )

    for node in nodes:
        node_id = node.get(
            "id"
        )

        resource_ids = node.get(
            "resource_ids",
            [],
        )

        if not isinstance(
            resource_ids,
            list,
        ):
            resource_ids = []

        degree = degree_map.get(
            node_id,
            0,
        )

        in_degree = in_degree_map.get(
            node_id,
            0,
        )

        out_degree = out_degree_map.get(
            node_id,
            0,
        )

        if node.get(
            "type"
        ) != "paper":
            actual_papers = entity_papers.get(
                node_id,
                set(),
            )

            paper_count = len(
                actual_papers
            )

            # Include merged evidence resources as a fallback.
            if paper_count == 0:
                paper_count = len(
                    set(
                        str(resource_id)
                        for resource_id in resource_ids
                        if resource_id
                    )
                )
        else:
            paper_count = len(
                set(
                    str(resource_id)
                    for resource_id in resource_ids
                    if resource_id
                )
            )

        node["degree"] = degree
        node["in_degree"] = in_degree
        node["out_degree"] = out_degree
        node["paper_count"] = paper_count

        node["shared"] = (
            node.get("type") != "paper"
            and paper_count > 1
        )


# ============================================================
# FINAL GRAPH VALIDATION
# ============================================================

def remove_invalid_graph_edges(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    valid_node_ids = {
        node["id"]
        for node in nodes
        if node.get("id")
    }

    valid_edges = []
    seen = set()

    for edge in edges:
        source = edge.get(
            "source"
        )

        target = edge.get(
            "target"
        )

        relationship = edge.get(
            "relationship"
        )

        if not source or not target:
            continue

        if source not in valid_node_ids:
            continue

        if target not in valid_node_ids:
            continue

        if source == target:
            continue

        if relationship not in SUPPORTED_RELATION_TYPES:
            continue

        key = (
            source,
            target,
            relationship,
        )

        if key in seen:
            continue

        seen.add(key)

        valid_edges.append(
            edge
        )

    return valid_edges


# ============================================================
# MAIN GRAPH GENERATION
# ============================================================

def generate_knowledge_graph(
    resource_ids: List[str],
) -> Dict[str, Any]:

    print(
        "[KG] ========================================"
    )

    print(
        "[KG] Gemini Knowledge Graph generation started."
    )

    # --------------------------------------------------------
    # IMPORTANT:
    # The route passes a list directly.
    # Do NOT expect request.resource_ids here.
    # --------------------------------------------------------

    if not isinstance(
        resource_ids,
        list,
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "resource_ids must be a list."
            ),
        )

    normalized_resource_ids = []

    for resource_id in resource_ids:
        value = str(
            resource_id
        ).strip()

        if not value:
            continue

        if value not in normalized_resource_ids:
            normalized_resource_ids.append(
                value
            )

    if not normalized_resource_ids:
        raise HTTPException(
            status_code=400,
            detail=(
                "At least one valid resource_id is required."
            ),
        )

    graph_nodes: Dict[
        str,
        Dict[str, Any],
    ] = {}

    graph_edges: Dict[
        Tuple[str, str, str],
        Dict[str, Any],
    ] = {}

    processed_papers = []
    skipped_papers = []

    for resource_id in normalized_resource_ids:
        try:
            result = process_single_paper(
                resource_id
            )

            if not result[
                "processed"
            ]:
                skipped_papers.append(
                    {
                        "resource_id": resource_id,
                        "reason": result.get(
                            "reason",
                            "Unknown reason",
                        ),
                    }
                )

                continue

            processed_papers.append(
                resource_id
            )

            for node in result.get(
                "nodes",
                [],
            ):
                if node.get(
                    "type"
                ) == "paper":

                    node_id = node[
                        "id"
                    ]

                    if node_id not in graph_nodes:
                        graph_nodes[
                            node_id
                        ] = node

                    continue

                merge_entity_into_graph(
                    graph_nodes,
                    node,
                    resource_id,
                )

            for edge in result.get(
                "edges",
                [],
            ):
                merge_relationship_into_graph(
                    graph_edges,
                    edge,
                )

        except HTTPException:
            raise

        except Exception as exc:
            print(
                "[KG] Unexpected error while "
                f"processing {resource_id}: {exc}"
            )

            skipped_papers.append(
                {
                    "resource_id": resource_id,
                    "reason": str(exc),
                }
            )

    unique_nodes = list(
        graph_nodes.values()
    )

    unique_edges = list(
        graph_edges.values()
    )

    unique_edges = remove_invalid_graph_edges(
        unique_nodes,
        unique_edges,
    )

    # --------------------------------------------------------
    # Remove entities that ended up disconnected after
    # cross-paper merging / edge validation.
    # --------------------------------------------------------

    unique_nodes = remove_orphan_entities(
        unique_nodes,
        unique_edges,
    )

    unique_edges = remove_invalid_graph_edges(
        unique_nodes,
        unique_edges,
    )

    enrich_graph_nodes(
        unique_nodes,
        unique_edges,
    )

    unique_nodes.sort(
        key=lambda node: (
            0
            if node.get("type") == "paper"
            else 1,
            -int(
                node.get(
                    "paper_count",
                    0,
                )
                or 0
            ),
            -int(
                node.get(
                    "degree",
                    0,
                )
                or 0
            ),
            str(
                node.get(
                    "name",
                    "",
                )
            ).lower(),
        )
    )

    unique_edges.sort(
        key=lambda edge: (
            str(
                edge.get(
                    "relationship",
                    "",
                )
            ),
            str(
                edge.get(
                    "source",
                    "",
                )
            ),
            str(
                edge.get(
                    "target",
                    "",
                )
            ),
        )
    )

    statistics = build_graph_statistics(
        unique_nodes,
        unique_edges,
    )

    shared_entity_count = sum(
        1
        for node in unique_nodes
        if (
            node.get("type") != "paper"
            and node.get("shared") is True
        )
    )

    paper_node_count = sum(
        1
        for node in unique_nodes
        if node.get("type") == "paper"
    )

    entity_node_count = (
        len(unique_nodes)
        - paper_node_count
    )

    response = {
        "nodes": unique_nodes,
        "edges": unique_edges,
        "meta": {
            "requested_resources": len(
                normalized_resource_ids
            ),
            "processed_papers": len(
                processed_papers
            ),
            "processed_resource_ids": processed_papers,
            "skipped_papers": skipped_papers,
            "node_count": len(
                unique_nodes
            ),
            "edge_count": len(
                unique_edges
            ),
            "paper_node_count": paper_node_count,
            "entity_node_count": entity_node_count,
            "shared_entity_count": shared_entity_count,
            "statistics": statistics,
            "architecture": (
                "gemini_qdrant_evidence_grounded"
            ),
        },
    }

    print(
        "[KG] ========================================"
    )

    print(
        "[KG] Knowledge graph completed."
    )

    print(
        "[KG] Papers: "
        f"{len(processed_papers)}"
    )

    print(
        "[KG] Nodes: "
        f"{len(unique_nodes)}"
    )

    print(
        "[KG] Edges: "
        f"{len(unique_edges)}"
    )

    print(
        "[KG] Shared entities: "
        f"{shared_entity_count}"
    )

    print(
        "[KG] Node types: "
        f"{statistics['node_types']}"
    )

    print(
        "[KG] Relationship types: "
        f"{statistics['relationship_types']}"
    )

    return response