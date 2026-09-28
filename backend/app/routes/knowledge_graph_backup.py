import json
import os
import re
import time
from typing import Any, Dict, List, Tuple

import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.database.mongodb import papers_collection
from app.services.vector_store import search_paper_chunks


router = APIRouter(
    prefix="/api/knowledge-graph",
    tags=["Knowledge Graph"],
)


# ============================================================
# CONFIGURATION
# ============================================================

OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://host.docker.internal:11434",
)

OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "llama3.2:latest",
)

OLLAMA_TIMEOUT = 90

# Keep retrieval broad enough to cover different sections,
# but reduce the number of chunks returned per query.
RETRIEVAL_LIMIT = 2

# Maximum number of unique chunks sent to the extraction LLM.
MAX_GRAPH_CHUNKS = 6

# Maximum number of graph entities accepted from one paper.
MAX_GRAPH_ENTITIES = 12

# Maximum number of relationships accepted from one paper.
MAX_GRAPH_RELATIONSHIPS = 8
MAX_CHUNK_CHARS = 2000
OLLAMA_EXTRACTION_MAX_TOKENS = 1200
OLLAMA_VALIDATION_MAX_TOKENS = 400

# ============================================================
# SUPPORTED ENTITY TYPES
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


# ============================================================
# SUPPORTED RELATION TYPES
# ============================================================

RELATION_ALIASES = {
    "authored": "authored_by",
    "written_by": "authored_by",
    "authored_by": "authored_by",
    "paper_by": "authored_by",
    "published_by": "authored_by",

    "uses": "uses",
    "use": "uses",
    "utilizes": "uses",
    "utilize": "uses",
    "employs": "uses",
    "employ": "uses",
    "applies": "uses",
    "apply": "uses",

    "proposed": "proposed",
    "proposes": "proposed",
    "introduced": "proposed",
    "introduces": "proposed",

    "evaluated_on": "evaluated_on",
    "evaluated": "evaluated_on",
    "evaluates": "evaluated_on",
    "evaluating": "evaluated_on",
    "tested_on": "evaluated_on",
    "tested": "evaluated_on",
    "tests": "evaluated_on",
    "benchmarked_on": "evaluated_on",
    "benchmarked": "evaluated_on",
    "benchmarks": "evaluated_on",

    "discusses": "discusses",
    "discuss": "discusses",
    "describes": "discusses",
    "describe": "discusses",

    "reports": "reports",
    "report": "reports",
    "reported": "reports",
    "finds": "reports",
    "found": "reports",

    "based_on": "based_on",
    "builds_on": "based_on",
    "built_on": "based_on",
}


SUPPORTED_RELATIONS = set(
    RELATION_ALIASES.values()
)


# ============================================================
# NOISE FILTERING
# ============================================================

# Generic words that should not become standalone concept nodes.
GENERIC_CONCEPT_NAMES = {
    "paper",
    "article",
    "study",
    "research",
    "research paper",
    "method",
    "methods",
    "approach",
    "approaches",
    "technique",
    "techniques",
    "algorithm",
    "algorithms",
    "model",
    "models",
    "system",
    "systems",
    "framework",
    "frameworks",
    "data",
    "dataset",
    "datasets",
    "experiment",
    "experiments",
    "result",
    "results",
    "finding",
    "findings",
    "performance",
    "evaluation",
    "conclusion",
    "conclusions",
    "problem",
    "objective",
    "objectives",
    "future work",
    "limitation",
    "limitations",
}

# Concepts should normally be research-specific rather than
# ordinary scientific nouns.
CONCEPT_RELEVANCE_TERMS = {
    "technique",
    "method",
    "approach",
    "framework",
    "architecture",
    "algorithm",
    "model",
    "system",
    "detector",
    "reconstruction",
    "classification",
    "regression",
    "simulation",
    "representation",
    "learning",
    "network",
    "calorimeter",
    "particle",
    "physics",
    "computer",
    "machine",
    "neural",
    "deep",
    "energy",
    "resolution",
    "readout",
    "shower",
    "flow",
    "tracking",
    "inference",
    "training",
    "embedding",
    "retrieval",
}


# ============================================================
# REQUEST MODEL
# ============================================================

class KnowledgeGraphRequest(BaseModel):
    resource_ids: List[str]


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_name(value: Any) -> str:
    """
    Normalize an entity name for reliable comparison.
    """

    if value is None:
        return ""

    text = str(value).strip().lower()

    text = text.replace("“", '"')
    text = text.replace("”", '"')
    text = text.replace("’", "'")

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text


def normalize_paper_name(value: Any) -> str:
    """
    Normalize paper titles while allowing a leading
    article such as The, A, or An to be omitted.
    """

    normalized = normalize_name(value)

    normalized = re.sub(
        r"^(the|a|an)\s+",
        "",
        normalized,
    )

    return normalized


def normalize_relation(value: Any) -> str:
    """
    Convert an allowed relation alias into canonical form.
    """

    if value is None:
        return ""

    normalized = normalize_name(value)

    normalized = normalized.replace(
        "-",
        "_",
    )

    normalized = normalized.replace(
        " ",
        "_",
    )

    return RELATION_ALIASES.get(
        normalized,
        normalized,
    )


def normalize_text_for_matching(value: Any) -> str:
    """
    Normalize text for conservative lexical matching.
    """

    if value is None:
        return ""

    text = str(value).lower()

    text = text.replace("“", '"')
    text = text.replace("”", '"')
    text = text.replace("’", "'")

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


# ============================================================
# PAPER MATCHING
# ============================================================

def is_same_paper_name(
    name_a: str,
    name_b: str,
) -> bool:
    return (
        normalize_paper_name(name_a)
        == normalize_paper_name(name_b)
    )


# ============================================================
# NODE HELPERS
# ============================================================

def make_node_id(
    name: str,
    entity_type: str,
    resource_id: str,
) -> str:
    """
    Generate a stable node ID.
    """

    if entity_type == "paper":
        return resource_id

    return normalize_name(name)


def make_node_reference(
    name: str,
    entity_type: str,
    resource_id: str,
) -> str:
    """
    Generate a normalized reference for endpoint matching.
    """

    if entity_type == "paper":
        return normalize_paper_name(name)

    return normalize_name(name)


# ============================================================
# OLLAMA
# ============================================================

def call_ollama(
    prompt: str,
    max_output_tokens: int,
) -> str:
    """
    Send a bounded request to the local Ollama model.
    """

    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0,
                    "num_predict": max_output_tokens,
                },
                "keep_alive": "10m",
            },
            timeout=OLLAMA_TIMEOUT,
        )

        response.raise_for_status()

        data = response.json()

        return data.get(
            "response",
            "",
        )

    except requests.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Ollama request failed: {exc}",
        )


# ============================================================
# JSON EXTRACTION
# ============================================================

def extract_json(
    text: str,
) -> Dict[str, Any]:
    """
    Safely extract a JSON object from an LLM response.
    """

    if not text:
        return {}

    text = text.strip()

    # Direct JSON.
    try:
        parsed = json.loads(text)

        if isinstance(parsed, dict):
            return parsed

    except json.JSONDecodeError:
        pass

    # JSON inside markdown fences.
    fenced_match = re.search(
        r"```(?:json)?\s*(\{.*?\})\s*```",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )

    if fenced_match:
        try:
            parsed = json.loads(
                fenced_match.group(1)
            )

            if isinstance(parsed, dict):
                return parsed

        except json.JSONDecodeError:
            pass

    # First JSON object.
    object_match = re.search(
        r"(\{.*\})",
        text,
        flags=re.DOTALL,
    )

    if object_match:
        try:
            parsed = json.loads(
                object_match.group(1)
            )

            if isinstance(parsed, dict):
                return parsed

        except json.JSONDecodeError:
            pass

    return {}


# ============================================================
# EVIDENCE HELPERS
# ============================================================

def evidence_statement_is_real(
    statement: str,
    chunks: List[Dict[str, Any]],
) -> bool:
    """
    Verify that the supplied evidence statement actually
    occurs in one of the retrieved chunks.

    This prevents the LLM from inventing evidence.
    """

    normalized_statement = normalize_text_for_matching(
        statement
    )

    if not normalized_statement:
        return False

    for chunk in chunks:
        chunk_text = normalize_text_for_matching(
            chunk.get("text", "")
        )

        if (
            normalized_statement in chunk_text
        ):
            return True

    return False


def get_evidence_chunk(
    evidence_item: Dict[str, Any],
) -> Any:
    return evidence_item.get(
        "chunk_index"
    )


def name_appears_in_statement(
    name: str,
    statement: str,
) -> bool:
    """
    Check whether an entity name explicitly occurs
    in the evidence statement.
    """

    normalized_name = normalize_text_for_matching(
        name
    )

    normalized_statement = normalize_text_for_matching(
        statement
    )

    if not normalized_name:
        return False

    if not normalized_statement:
        return False

    return normalized_name in normalized_statement


def paper_name_appears_in_statement(
    name: str,
    statement: str,
) -> bool:
    """
    Paper-specific name matching.
    """

    normalized_name = normalize_paper_name(
        name
    )

    normalized_statement = normalize_text_for_matching(
        statement
    )

    if normalized_name in normalized_statement:
        return True

    original_name = normalize_text_for_matching(
        name
    )

    return (
        bool(original_name)
        and original_name in normalized_statement
    )


# ============================================================
# ENTITY QUALITY FILTER
# ============================================================

def concept_is_research_relevant(
    name: str,
    statement: str,
) -> bool:
    """
    Reject generic concepts and ordinary nouns.

    Concepts are retained only when they appear to represent
    a meaningful research/domain concept.
    """

    normalized_name = normalize_name(
        name
    )

    if not normalized_name:
        return False

    if normalized_name in GENERIC_CONCEPT_NAMES:
        return False

    words = set(
        re.findall(
            r"[a-zA-Z][a-zA-Z0-9\-]*",
            normalized_name,
        )
    )

    statement_text = normalize_text_for_matching(
        statement
    )

    # Multi-word named concepts are generally more useful.
    if len(words) >= 2:
        return True

    # A single-word concept is accepted only when it is
    # supported by meaningful research terminology nearby.
    for term in CONCEPT_RELEVANCE_TERMS:
        if term in statement_text:
            return True

    return False


def entity_quality_is_supported(
    name: str,
    entity_type: str,
    statement: str,
) -> bool:
    """
    Additional quality filter beyond entity-type validation.
    """

    normalized_name = normalize_name(
        name
    )

    if not normalized_name:
        return False

    # Reject excessively long generated names.
    if len(normalized_name) > 120:
        return False

    # Reject obvious sentence-like entity names.
    if len(normalized_name.split()) > 12:
        return False

    if entity_type == "concept":
        return concept_is_research_relevant(
            name,
            statement,
        )

    return True


# ============================================================
# ENTITY TYPE VALIDATION
# ============================================================

def entity_type_is_supported(
    entity_type: str,
    evidence_text: str,
) -> bool:
    """
    Check whether the proposed entity type is supported
    by the supplied evidence.
    """

    entity_type = normalize_name(
        entity_type
    )

    text = normalize_text_for_matching(
        evidence_text
    )

    if entity_type not in SUPPORTED_ENTITY_TYPES:
        return False

    if entity_type == "paper":
        return bool(
            re.search(
                r"\bpaper\b|"
                r"\barticle\b|"
                r"\bpublication\b|"
                r"\bstudy\b",
                text,
            )
        )

    if entity_type == "author":
        return bool(
            re.search(
                r"\bauthor\b|"
                r"\bauthored\b|"
                r"\bwrote\b|"
                r"\bwritten by\b|"
                r"\bresearcher\b|"
                r"\bscientist\b|"
                r"\bprofessor\b|"
                r"\bmathematician\b",
                text,
            )
        )

    if entity_type == "dataset":
        return bool(
            re.search(
                r"\bdataset\b|"
                r"\bdatasets\b|"
                r"\bcorpus\b|"
                r"\bbenchmark\b|"
                r"\bdata set\b",
                text,
            )
        )

    if entity_type == "metric":
        return bool(
            re.search(
                r"\bmetric\b|"
                r"\bmetrics\b|"
                r"\baccuracy\b|"
                r"\bprecision\b|"
                r"\brecall\b|"
                r"\bf1\b|"
                r"\bauc\b|"
                r"\bmse\b|"
                r"\bmae\b|"
                r"\bperformance\b|"
                r"\benergy resolution\b|"
                r"\bevaluation measure\b",
                text,
            )
        )

    if entity_type == "method":
        return bool(
            re.search(
                r"\bmethod\b|"
                r"\bmethodology\b|"
                r"\bapproach\b|"
                r"\balgorithm\b|"
                r"\btechnique\b|"
                r"\bframework\b|"
                r"\barchitecture\b",
                text,
            )
        )

    if entity_type == "limitation":
        return bool(
            re.search(
                r"\blimitation\b|"
                r"\blimitations\b|"
                r"\bconstraint\b|"
                r"\bconstraints\b|"
                r"\bshortcoming\b|"
                r"\bshortcomings\b|"
                r"\bchalleng\b|"
                r"\bdoes not\b|"
                r"\bcannot\b",
                text,
            )
        )

    if entity_type == "future_work":
        return bool(
            re.search(
                r"\bfuture work\b|"
                r"\bfuture research\b|"
                r"\bfuture direction\b|"
                r"\bfurther research\b|"
                r"\bfurther work\b|"
                r"\bnext step\b|"
                r"\bdirections\b",
                text,
            )
        )

    if entity_type == "finding":
        return bool(
            re.search(
                r"\bfind\b|"
                r"\bfound\b|"
                r"\bfinding\b|"
                r"\bfindings\b|"
                r"\bresult\b|"
                r"\bresults\b|"
                r"\bimprovement\b|"
                r"\bimproved\b|"
                r"\bachieved\b|"
                r"\bperformance\b",
                text,
            )
        )

    if entity_type == "problem":
        return bool(
            re.search(
                r"\bproblem\b|"
                r"\bchallenge\b|"
                r"\bissue\b|"
                r"\bdifficulty\b|"
                r"\btask\b|"
                r"\bobjective\b|"
                r"\bgoal\b",
                text,
            )
        )

    # These entities still require explicit name evidence,
    # which is checked separately.
    if entity_type in {
        "organization",
        "tool",
        "model",
    }:
        return True

    return False


# ============================================================
# ENTITY VALIDATION
# ============================================================

def validate_entity_candidate(
    candidate: Dict[str, Any],
    chunks: List[Dict[str, Any]],
) -> Tuple[bool, str]:

    """
    Deterministically validate an entity candidate.

    Requirements:

    1. Valid object.
    2. Supported entity type.
    3. Non-empty name.
    4. Evidence exists.
    5. Evidence is actually present in retrieved text.
    6. Evidence contains the entity name.
    7. Entity type is supported by the evidence.
    8. Entity passes quality/noise filtering.
    """

    if not isinstance(
        candidate,
        dict,
    ):
        return False, "candidate is not an object"

    name = str(
        candidate.get(
            "name",
            "",
        )
    ).strip()

    entity_type = normalize_name(
        candidate.get(
            "type",
            "",
        )
    )

    evidence = candidate.get(
        "evidence",
        [],
    )

    if not name:
        return False, "missing entity name"

    if entity_type not in SUPPORTED_ENTITY_TYPES:
        return (
            False,
            f"unsupported type '{entity_type}'",
        )

    if (
        not isinstance(evidence, list)
        or not evidence
    ):
        return False, "missing evidence"

    for evidence_item in evidence:

        if not isinstance(
            evidence_item,
            dict,
        ):
            continue

        statement = str(
            evidence_item.get(
                "statement",
                "",
            )
        ).strip()

        if not statement:
            continue

        # Evidence must genuinely exist in the retrieved text.
        if not evidence_statement_is_real(
            statement,
            chunks,
        ):
            continue

        # Entity name must occur in its evidence.
        if not name_appears_in_statement(
            name,
            statement,
        ):
            continue

        # Entity type must be supported by the evidence.
        if not entity_type_is_supported(
            entity_type,
            statement,
        ):
            continue

        # Additional noise/relevance filtering.
        if not entity_quality_is_supported(
            name,
            entity_type,
            statement,
        ):
            continue

        return True, "valid"

    return (
        False,
        "evidence is missing, unsupported, "
        "or not sufficiently specific",
    )


# ============================================================
# RELATION LANGUAGE VALIDATION
# ============================================================

def relation_appears_in_statement(
    relation: str,
    statement: str,
) -> bool:
    """
    Check whether explicit language supports the requested
    canonical relationship.
    """

    canonical_relation = normalize_relation(
        relation
    )

    statement_text = normalize_text_for_matching(
        statement
    )

    patterns = {
        "authored_by": [
            r"\bauthored\b",
            r"\bauthor(?:ed|s)?\b",
            r"\bwritten by\b",
            r"\bwritten\b",
        ],

        "uses": [
            r"\buses\b",
            r"\buse\b",
            r"\bused\b",
            r"\butilizes\b",
            r"\butilize\b",
            r"\bemploys\b",
            r"\bemploy\b",
            r"\bapplies\b",
            r"\bapply\b",
        ],

        "proposed": [
            r"\bproposed\b",
            r"\bproposes\b",
            r"\bintroduced\b",
            r"\bintroduces\b",
        ],

        "evaluated_on": [
            r"\bevaluated\b",
            r"\bevaluated on\b",
            r"\bevaluates\b",
            r"\bevaluating\b",
            r"\bevaluated using\b",
            r"\btested\b",
            r"\btested on\b",
            r"\btests\b",
            r"\bbenchmarked\b",
            r"\bbenchmarked on\b",
            r"\bbenchmarks\b",
        ],

        "discusses": [
            r"\bdiscusses\b",
            r"\bdiscuss\b",
            r"\bdescribes\b",
            r"\bdescribe\b",
        ],

        "reports": [
            r"\breports\b",
            r"\breport\b",
            r"\breported\b",
            r"\bfinds\b",
            r"\bfound\b",
        ],

        "based_on": [
            r"\bbased on\b",
            r"\bbased upon\b",
            r"\bbuilds on\b",
            r"\bbuilt on\b",
        ],
    }

    relation_patterns = patterns.get(
        canonical_relation,
        [],
    )

    for pattern in relation_patterns:
        if re.search(
            pattern,
            statement_text,
        ):
            return True

    return False


# ============================================================
# RELATIONSHIP VALIDATION
# ============================================================

def validate_relationship_candidate(
    candidate: Dict[str, Any],
    valid_entities: List[Dict[str, Any]],
    paper_title: str,
    chunks: List[Dict[str, Any]],
) -> Tuple[bool, str]:

    """
    Deterministically validate a relationship.

    A relationship is accepted only when:

    1. Source exists.
    2. Target exists.
    3. Relation is supported.
    4. Evidence exists.
    5. Evidence is genuinely present in retrieved text.
    6. Source and target occur in the SAME statement.
    7. Explicit relation language occurs in that statement.

    No relationship is inferred merely from co-occurrence.
    """

    if not isinstance(
        candidate,
        dict,
    ):
        return False, "candidate is not an object"

    source = str(
        candidate.get(
            "source",
            "",
        )
    ).strip()

    target = str(
        candidate.get(
            "target",
            "",
        )
    ).strip()

    raw_relation = str(
        candidate.get(
            "relation",
            "",
        )
    ).strip()

    relation = normalize_relation(
        raw_relation
    )

    evidence = candidate.get(
        "evidence",
        [],
    )

    if not source:
        return False, "missing source"

    if not target:
        return False, "missing target"

    if not raw_relation:
        return False, "missing relation"

    if relation not in SUPPORTED_RELATIONS:
        return (
            False,
            f"unsupported relation '{raw_relation}'",
        )

    if (
        not isinstance(evidence, list)
        or not evidence
    ):
        return False, "missing evidence"

    # Build known entity references.
    known_references = set()

    for entity in valid_entities:

        entity_name = str(
            entity.get(
                "name",
                "",
            )
        ).strip()

        entity_type = normalize_name(
            entity.get(
                "type",
                "",
            )
        )

        if not entity_name:
            continue

        known_references.add(
            make_node_reference(
                entity_name,
                entity_type,
                entity.get(
                    "resource_id",
                    "",
                ),
            )
        )

    source_known = (
        normalize_name(source)
        in known_references
    )

    target_known = (
        normalize_name(target)
        in known_references
    )

    # Selected paper is always a valid endpoint.
    if is_same_paper_name(
        source,
        paper_title,
    ):
        source_known = True

    if is_same_paper_name(
        target,
        paper_title,
    ):
        target_known = True

    if not source_known or not target_known:
        return (
            False,
            "unknown endpoint",
        )

    # --------------------------------------------------------
    # SAME-STATEMENT VALIDATION
    # --------------------------------------------------------

    for evidence_item in evidence:

        if not isinstance(
            evidence_item,
            dict,
        ):
            continue

        statement = str(
            evidence_item.get(
                "statement",
                "",
            )
        ).strip()

        if not statement:
            continue

        # Evidence must exist in retrieved text.
        if not evidence_statement_is_real(
            statement,
            chunks,
        ):
            continue

        # Source occurrence.
        if is_same_paper_name(
            source,
            paper_title,
        ):
            source_present = (
                paper_name_appears_in_statement(
                    source,
                    statement,
                )
                or paper_name_appears_in_statement(
                    paper_title,
                    statement,
                )
            )
        else:
            source_present = (
                name_appears_in_statement(
                    source,
                    statement,
                )
            )

        # Target occurrence.
        if is_same_paper_name(
            target,
            paper_title,
        ):
            target_present = (
                paper_name_appears_in_statement(
                    target,
                    statement,
                )
                or paper_name_appears_in_statement(
                    paper_title,
                    statement,
                )
            )
        else:
            target_present = (
                name_appears_in_statement(
                    target,
                    statement,
                )
            )

        if not source_present:
            continue

        if not target_present:
            continue

        # Explicit relationship language.
        if not relation_appears_in_statement(
            relation,
            statement,
        ):
            continue

        return True, "valid"

    return (
        False,
        "source, target, and explicit relation language "
        "were not all present in the same evidence statement",
    )


# ============================================================
# BROADER QDRANT RETRIEVAL
# ============================================================

def retrieve_graph_chunks(
    paper_title: str,
    resource_id: str,
) -> List[Dict[str, Any]]:
    """
    Retrieve representative paper chunks.

    Multiple focused queries are used to cover different
    sections of a research paper.

    Retrieval only is performed here.
    No paper analysis is performed.
    """

    retrieval_queries = [
        paper_title,
        "authors researchers introduction research problem objective",
        "method methodology approach algorithm framework architecture technique model",
        "dataset data corpus benchmark evaluation experiment metric accuracy performance results findings conclusion limitations future work",
    ]

    unique_chunks: List[Dict[str, Any]] = []
    seen_chunks = set()

    print(
        "[KG] Starting optimized Qdrant retrieval "
        f"using {len(retrieval_queries)} query variations."
    )

    for query_index, query in enumerate(
        retrieval_queries,
        start=1,
    ):

        print(
            f"[KG] Retrieval query {query_index}/"
            f"{len(retrieval_queries)}"
        )

        try:
            results = search_paper_chunks(
                query=query,
                paper_ids=[
                    resource_id
                ],
                limit=RETRIEVAL_LIMIT,
            )

        except Exception as exc:

            print(
                "[KG] Retrieval query failed: "
                f"{exc}"
            )

            continue

        for chunk in results:

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

            chunk_key = (
                resource_id,
                chunk_index,
                normalize_text_for_matching(
                    text
                ),
            )

            if chunk_key in seen_chunks:
                continue

            seen_chunks.add(
                chunk_key
            )

            unique_chunks.append(
                chunk
            )

    # Sort document-order chunks first.
    unique_chunks.sort(
        key=lambda chunk: (
            chunk.get(
                "chunk_index"
            )
            if isinstance(
                chunk.get(
                    "chunk_index"
                ),
                int,
            )
            else 999999
        )
    )

    selected_chunks = unique_chunks[
        :MAX_GRAPH_CHUNKS
    ]

    print(
        "[KG] Unique chunks retrieved: "
        f"{len(unique_chunks)}"
    )

    print(
        "[KG] Chunks sent to extraction model: "
        f"{len(selected_chunks)}"
    )

    return selected_chunks


# ============================================================
# COMPACT EVIDENCE CONTEXT
# ============================================================

def build_evidence_context(
    chunks: List[Dict[str, Any]],
) -> str:
    """
    Build compact context for the extraction model.
    """

    evidence_blocks = []

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
        if len(text) > MAX_CHUNK_CHARS:
            text = text[:MAX_CHUNK_CHARS]
        if not text:
            continue

        evidence_blocks.append(
            f"[CHUNK {chunk_index}]\n{text}"
        )

    return "\n\n".join(
        evidence_blocks
    )


# ============================================================
# GRAPH EXTRACTION
# ============================================================

def extract_graph_candidates(
    paper_title: str,
    chunks: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Ask the local LLM to propose graph candidates.

    The LLM proposes candidates only.
    Python performs final validation.
    """

    context = build_evidence_context(
        chunks
    )

    prompt = f"""
Extract a SMALL, CONSERVATIVE knowledge graph from the
retrieved research-paper text.

PAPER:
{paper_title}

TEXT:
{context}

Return ONLY JSON:
{{
  "entities": [
    {{
      "name": "exact name from text",
      "type": "paper|author|method|dataset|metric|concept|finding|limitation|future_work|problem|organization|tool|model",
      "description": "short factual description",
      "evidence": [{{"chunk_index": 0, "statement": "EXACT sentence copied from text"}}]
    }}
  ],
  "relationships": [
    {{
      "source": "exact entity name",
      "target": "exact entity name",
      "relation": "authored_by|uses|proposed|evaluated_on|discusses|reports|based_on",
      "evidence": [{{"chunk_index": 0, "statement": "EXACT sentence copied from text"}}]
    }}
  ]
}}

RULES:
- At most 12 entities and 8 relationships.
- Extract only research-relevant entities.
- Prefer authors, methods, models, datasets, metrics, tools,
  findings, limitations, future work, problems, organizations,
  and important domain concepts.
- Do not extract generic nodes such as paper, method, result,
  data, system, research, or performance.
- Entity names must occur in their evidence statement.
- Evidence must be copied exactly from the text.
- Do not invent entities, descriptions, evidence, or facts.
- Use only the allowed entity and relationship types.
- Avoid duplicate entities.
- A relationship is valid only when ONE SAME evidence statement
  explicitly contains source, target, and relationship meaning.
- Never infer relationships from co-occurrence.
- Never combine multiple statements.
- Use exact entity names.
- If uncertain, omit the candidate.
- Accuracy is more important than completeness.

The selected paper is "{paper_title}".
Return JSON only.
"""

    start_time = time.time()

    print("[KG] Calling Ollama for graph extraction...")

    response_text = call_ollama(
        prompt,
        OLLAMA_EXTRACTION_MAX_TOKENS,
    )

    print(
        "[KG] Ollama extraction completed in "
        f"{time.time() - start_time:.2f} seconds."
    )

    return extract_json(
        response_text
    )


# ============================================================
# CANDIDATE DEDUPLICATION
# ============================================================

def deduplicate_entities(
    entities: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Remove duplicate entity candidates.
    """

    result = []
    seen = set()

    for entity in entities:

        if not isinstance(
            entity,
            dict,
        ):
            continue

        name = normalize_name(
            entity.get(
                "name",
                "",
            )
        )

        entity_type = normalize_name(
            entity.get(
                "type",
                "",
            )
        )

        key = (
            name,
            entity_type,
        )

        if not name:
            continue

        if key in seen:
            continue

        seen.add(key)

        result.append(
            entity
        )

        if len(result) >= MAX_GRAPH_ENTITIES:
            break

    return result


def deduplicate_relationships(
    relationships: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Remove duplicate relationship candidates.
    """

    result = []
    seen = set()

    for relationship in relationships:

        if not isinstance(
            relationship,
            dict,
        ):
            continue

        source = normalize_name(
            relationship.get(
                "source",
                "",
            )
        )

        target = normalize_name(
            relationship.get(
                "target",
                "",
            )
        )

        relation = normalize_relation(
            relationship.get(
                "relation",
                "",
            )
        )

        key = (
            source,
            relation,
            target,
        )

        if not source or not target or not relation:
            continue

        if key in seen:
            continue

        seen.add(key)

        result.append(
            relationship
        )

        if len(result) >= MAX_GRAPH_RELATIONSHIPS:
            break

    return result


# ============================================================
# SEMANTIC VALIDATION
# ============================================================

def semantic_validate_candidates(
    entities: List[Dict[str, Any]],
    relationships: List[Dict[str, Any]],
    paper_title: str,
) -> Dict[str, Any]:
    """
    Perform second-stage semantic validation.

    The model may only accept or reject existing candidates.
    It cannot modify or create candidates.
    """

    if not entities and not relationships:
        return {
            "accepted_entities": [],
            "accepted_relationships": [],
        }

    # Send compact summaries only. Python retains the full candidates.
    entity_candidates = []
    for index, entity in enumerate(entities):
        evidence = entity.get("evidence", [])
        statement = ""
        if isinstance(evidence, list) and evidence and isinstance(evidence[0], dict):
            statement = str(evidence[0].get("statement", "")).strip()
        entity_candidates.append({
            "candidate_id": f"E{index}",
            "name": str(entity.get("name", "")).strip(),
            "type": normalize_name(entity.get("type", "")),
            "evidence": statement[:500],
        })

    relationship_candidates = []
    for index, relationship in enumerate(relationships):
        evidence = relationship.get("evidence", [])
        statement = ""
        if isinstance(evidence, list) and evidence and isinstance(evidence[0], dict):
            statement = str(evidence[0].get("statement", "")).strip()
        relationship_candidates.append({
            "candidate_id": f"R{index}",
            "source": str(relationship.get("source", "")).strip(),
            "target": str(relationship.get("target", "")).strip(),
            "relation": normalize_relation(relationship.get("relation", "")),
            "evidence": statement[:500],
        })

    prompt = f"""
Semantically validate ONLY the supplied candidates for this paper.

PAPER:
{paper_title}

You are NOT extracting information.
You may ONLY accept or reject supplied candidate IDs.

ENTITY RULES:
- Accept only clearly research-relevant entities.
- Reject generic or irrelevant concepts.
- Reject an entity if its evidence does not support its type.

RELATIONSHIP RULES:
- Accept only when the supplied evidence explicitly supports
  the exact source, target, and relation.
- Do not infer, modify, or create relationships.

ENTITY CANDIDATES:
{json.dumps(entity_candidates, ensure_ascii=False, separators=(",", ":"))}

RELATIONSHIP CANDIDATES:
{json.dumps(relationship_candidates, ensure_ascii=False, separators=(",", ":"))}

Return ONLY:
{{
  "accepted_entities": ["E0"],
  "accepted_relationships": ["R0"]
}}

Only use supplied candidate IDs. Do not create or modify candidates.
"""

    start_time = time.time()

    print("[KG] Calling Ollama for semantic validation...")

    response_text = call_ollama(
        prompt,
        OLLAMA_VALIDATION_MAX_TOKENS,
    )

    print(
        "[KG] Ollama semantic validation completed in "
        f"{time.time() - start_time:.2f} seconds."
    )

    result = extract_json(
        response_text
    )

    if not isinstance(
        result,
        dict,
    ):
        return {
            "accepted_entities": [],
            "accepted_relationships": [],
        }

    accepted_entities = result.get(
        "accepted_entities",
        [],
    )

    accepted_relationships = result.get(
        "accepted_relationships",
        [],
    )

    if not isinstance(
        accepted_entities,
        list,
    ):
        accepted_entities = []

    if not isinstance(
        accepted_relationships,
        list,
    ):
        accepted_relationships = []

    return {
        "accepted_entities": [
            str(value)
            for value in accepted_entities
        ],
        "accepted_relationships": [
            str(value)
            for value in accepted_relationships
        ],
    }


# ============================================================
# APPLY SEMANTIC VALIDATION
# ============================================================

def apply_semantic_validation(
    entities: List[Dict[str, Any]],
    relationships: List[Dict[str, Any]],
    semantic_result: Dict[str, Any],
) -> Tuple[
    List[Dict[str, Any]],
    List[Dict[str, Any]],
]:

    accepted_entity_ids = set(
        semantic_result.get(
            "accepted_entities",
            [],
        )
    )

    accepted_relationship_ids = set(
        semantic_result.get(
            "accepted_relationships",
            [],
        )
    )

    final_entities = []

    for index, entity in enumerate(
        entities
    ):

        candidate_id = f"E{index}"

        if candidate_id in accepted_entity_ids:

            final_entities.append(
                entity
            )

    final_relationships = []

    for index, relationship in enumerate(
        relationships
    ):

        candidate_id = f"R{index}"

        if candidate_id in accepted_relationship_ids:

            final_relationships.append(
                relationship
            )

    return (
        final_entities,
        final_relationships,
    )


# ============================================================
# BUILD GRAPH NODES
# ============================================================

def build_graph_nodes(
    paper_title: str,
    resource_id: str,
    validated_entities: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Build graph nodes.

    The selected paper is always included.
    """

    nodes = [
        {
            "id": resource_id,
            "name": paper_title,
            "type": "paper",
            "description": "",
            "resource_id": resource_id,
        }
    ]

    seen_ids = {
        resource_id
    }

    for entity in validated_entities:

        name = str(
            entity.get(
                "name",
                "",
            )
        ).strip()

        entity_type = normalize_name(
            entity.get(
                "type",
                "",
            )
        )

        if not name:
            continue

        if entity_type == "paper":
            continue

        node_id = make_node_id(
            name,
            entity_type,
            resource_id,
        )

        if node_id in seen_ids:
            continue

        seen_ids.add(
            node_id
        )

        node = {
            "id": node_id,
            "name": name,
            "type": entity_type,
            "description": entity.get(
                "description",
                "",
            ),
            "resource_id": resource_id,
        }

        evidence = entity.get(
            "evidence",
            [],
        )

        if evidence:
            node["evidence"] = evidence

        nodes.append(
            node
        )

    return nodes


# ============================================================
# BUILD GRAPH EDGES
# ============================================================

def build_graph_edges(
    relationships: List[Dict[str, Any]],
    nodes: List[Dict[str, Any]],
    paper_title: str,
    resource_id: str,
) -> List[Dict[str, Any]]:
    """
    Convert validated relationships into graph edges.
    """

    node_lookup = {}

    for node in nodes:

        node_name = str(
            node.get(
                "name",
                "",
            )
        )

        node_type = normalize_name(
            node.get(
                "type",
                "",
            )
        )

        reference = make_node_reference(
            node_name,
            node_type,
            resource_id,
        )

        node_lookup[
            reference
        ] = node.get(
            "id"
        )

    edges = []

    for relationship in relationships:

        source = str(
            relationship.get(
                "source",
                "",
            )
        ).strip()

        target = str(
            relationship.get(
                "target",
                "",
            )
        ).strip()

        relation = normalize_relation(
            relationship.get(
                "relation",
                "",
            )
        )

        if not source or not target:
            continue

        if relation not in SUPPORTED_RELATIONS:
            continue

        # Selected paper always maps to resource ID.
        if is_same_paper_name(
            source,
            paper_title,
        ):
            source_id = resource_id
        else:
            source_id = node_lookup.get(
                normalize_name(source)
            )

        if is_same_paper_name(
            target,
            paper_title,
        ):
            target_id = resource_id
        else:
            target_id = node_lookup.get(
                normalize_name(target)
            )

        if not source_id or not target_id:
            continue

        edge_id = (
            f"{source_id}"
            f"__{relation}__"
            f"{target_id}"
        )

        edges.append(
            {
                "id": edge_id,
                "source": source_id,
                "target": target_id,
                "relation": relation,
                "label": relation,
                "evidence": relationship.get(
                    "evidence",
                    [],
                ),
            }
        )

    return edges


# ============================================================
# MAIN ENDPOINT
# ============================================================

@router.post("")
def generate_knowledge_graph(
    request: KnowledgeGraphRequest,
):
    """
    Generate a knowledge graph for selected papers.

    Pipeline:

        MongoDB
            ↓
        Qdrant retrieval
            ↓
        LLM candidate extraction
            ↓
        Deterministic validation
            ↓
        Semantic validation
            ↓
        Graph construction

    Principle:

        LLM proposes.
        Code decides.
    """

    resource_ids = [
        str(resource_id).strip()
        for resource_id in request.resource_ids
        if resource_id is not None
        and str(resource_id).strip()
    ]

    if not resource_ids:
        raise HTTPException(
            status_code=400,
            detail="At least one resource_id is required.",
        )

    print(
        "[KG] Knowledge graph request received for "
        f"{len(resource_ids)} resource(s)."
    )

    all_nodes = []
    all_edges = []

    processed_papers = 0
    skipped_papers = []

    seen_node_ids = set()
    seen_edge_ids = set()

    for resource_id in resource_ids:

        print(
            "[KG] Processing resource: "
            f"{resource_id}"
        )

        # ====================================================
        # MONGODB
        # ====================================================

        paper = papers_collection.find_one(
            {
                "_id": resource_id
            }
        )

        if not paper:

            print(
                "[KG] Paper not found: "
                f"{resource_id}"
            )

            skipped_papers.append(
                {
                    "resource_id": resource_id,
                    "reason": "Paper not found in MongoDB",
                }
            )

            continue

        paper_title = str(
            paper.get(
                "title",
                paper.get(
                    "filename",
                    "Untitled Paper",
                ),
            )
        ).strip()

        print(
            "[KG] Paper found: "
            f"{paper_title}"
        )

        # ====================================================
        # QDRANT RETRIEVAL
        # ====================================================

        chunks = retrieve_graph_chunks(
            paper_title,
            resource_id,
        )

        if not chunks:

            skipped_papers.append(
                {
                    "resource_id": resource_id,
                    "reason": "No indexed paper chunks found",
                }
            )

            continue

        # ====================================================
        # LLM EXTRACTION
        # ====================================================

        print(
            "[KG] Extracting graph candidates..."
        )

        candidates = extract_graph_candidates(
            paper_title,
            chunks,
        )

        raw_entities = candidates.get(
            "entities",
            [],
        )

        raw_relationships = candidates.get(
            "relationships",
            [],
        )

        if not isinstance(
            raw_entities,
            list,
        ):
            raw_entities = []

        if not isinstance(
            raw_relationships,
            list,
        ):
            raw_relationships = []

        raw_entities = deduplicate_entities(
            raw_entities
        )

        raw_relationships = deduplicate_relationships(
            raw_relationships
        )

        print(
            "[KG] LLM proposed "
            f"{len(raw_entities)} entity candidate(s) "
            "and "
            f"{len(raw_relationships)} relationship candidate(s)."
        )

        # ====================================================
        # DETERMINISTIC ENTITY VALIDATION
        # ====================================================

        deterministic_entities = []

        for entity in raw_entities:

            is_valid, reason = (
                validate_entity_candidate(
                    entity,
                    chunks,
                )
            )

            if is_valid:

                entity = dict(
                    entity
                )

                entity[
                    "resource_id"
                ] = resource_id

                deterministic_entities.append(
                    entity
                )

            else:

                print(
                    "[KG] Entity rejected: "
                    f"{reason} | "
                    f"name='{entity.get('name', '')}'"
                )

        print(
            "[KG] Deterministically validated entities: "
            f"{len(deterministic_entities)}"
        )

        # ====================================================
        # DETERMINISTIC RELATIONSHIP VALIDATION
        # ====================================================

        deterministic_relationships = []

        for relationship in raw_relationships:

            is_valid, reason = (
                validate_relationship_candidate(
                    relationship,
                    deterministic_entities,
                    paper_title,
                    chunks,
                )
            )

            if is_valid:

                deterministic_relationships.append(
                    relationship
                )

            else:

                print(
                    "[KG] Relationship rejected: "
                    f"{reason}"
                )

        print(
            "[KG] Deterministically validated relationships: "
            f"{len(deterministic_relationships)}"
        )

        # ====================================================
        # SEMANTIC VALIDATION
        # ====================================================

        semantic_result = (
            semantic_validate_candidates(
                deterministic_entities,
                deterministic_relationships,
                paper_title,
            )
        )

        (
            final_entities,
            final_relationships,
        ) = apply_semantic_validation(
            deterministic_entities,
            deterministic_relationships,
            semantic_result,
        )

        print(
            "[KG] Final validated entities: "
            f"{len(final_entities)}"
        )

        print(
            "[KG] Final validated relationships: "
            f"{len(final_relationships)}"
        )

        # ====================================================
        # GRAPH CONSTRUCTION
        # ====================================================

        nodes = build_graph_nodes(
            paper_title,
            resource_id,
            final_entities,
        )

        edges = build_graph_edges(
            final_relationships,
            nodes,
            paper_title,
            resource_id,
        )

        # ====================================================
        # MERGE NODES
        # ====================================================

        for node in nodes:

            node_id = node.get(
                "id"
            )

            if node_id in seen_node_ids:
                continue

            seen_node_ids.add(
                node_id
            )

            all_nodes.append(
                node
            )

        # ====================================================
        # MERGE EDGES
        # ====================================================

        for edge in edges:

            edge_id = edge.get(
                "id"
            )

            if edge_id in seen_edge_ids:
                continue

            seen_edge_ids.add(
                edge_id
            )

            all_edges.append(
                edge
            )

        processed_papers += 1

        print(
            "[KG] Graph completed: "
            f"{len(nodes)} node(s), "
            f"{len(edges)} edge(s)."
        )

    # ========================================================
    # FINAL RESPONSE
    # ========================================================

    response = {
        "nodes": all_nodes,
        "edges": all_edges,
        "meta": {
            "requested_resources": len(
                resource_ids
            ),
            "processed_papers": processed_papers,
            "skipped_papers": skipped_papers,
            "node_count": len(
                all_nodes
            ),
            "edge_count": len(
                all_edges
            ),
        },
    }

    print(
        "[KG] Request completed: "
        f"{processed_papers} paper(s), "
        f"{len(all_nodes)} node(s), "
        f"{len(all_edges)} edge(s)."
    )

    return response