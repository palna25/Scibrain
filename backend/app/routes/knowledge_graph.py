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

# Retrieve a small number of candidates per focused query.
RETRIEVAL_LIMIT = 3

# Maximum number of unique chunks sent to the extraction model.
MAX_GRAPH_CHUNKS = 6

# Maximum number of graph entities proposed from one paper.
MAX_GRAPH_ENTITIES = 8

# Maximum number of relationships proposed from one paper.
MAX_GRAPH_RELATIONSHIPS = 5

# Keep the extraction response intentionally small.
OLLAMA_EXTRACTION_MAX_TOKENS = 1800

# Semantic validation receives only compact validated candidates.
OLLAMA_VALIDATION_MAX_TOKENS = 350

# Avoid sending excessively large individual chunks to Ollama.
MAX_CHUNK_CHARS = 1800


# ============================================================
# SUPPORTED GRAPH TYPES
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
}


RELATION_ALIASES = {
    "authored by": "authored_by",
    "authored_by": "authored_by",
    "uses": "uses",
    "use": "uses",
    "used": "uses",
    "proposed": "proposed",
    "proposes": "proposed",
    "evaluated on": "evaluated_on",
    "evaluated_on": "evaluated_on",
    "tested on": "evaluated_on",
    "discusses": "discusses",
    "discuss": "discusses",
    "reports": "reports",
    "reported": "reports",
    "based on": "based_on",
    "based_on": "based_on",
}


# ============================================================
# REQUEST SCHEMA
# ============================================================

class KnowledgeGraphRequest(BaseModel):
    resource_ids: List[str]


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def normalize_text_for_matching(
    text: str,
) -> str:
    """
    Normalize text only for matching/comparison.

    Original evidence text is preserved elsewhere.
    """

    value = str(text or "")

    value = value.replace(
        "\u00a0",
        " ",
    )

    value = value.replace(
        "\u2013",
        "-",
    )

    value = value.replace(
        "\u2014",
        "-",
    )

    value = value.replace(
        "\u2212",
        "-",
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip().lower()


def normalize_entity_name(
    name: str,
) -> str:
    value = normalize_text_for_matching(
        name
    )

    value = re.sub(
        r"[^a-z0-9]+",
        " ",
        value,
    )

    return re.sub(
        r"\s+",
        " ",
        value,
    ).strip()


def normalize_relation(
    relation: str,
) -> str:
    value = normalize_text_for_matching(
        relation
    )

    value = value.replace(
        "-",
        "_",
    )

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
# OLLAMA
# ============================================================

def call_ollama(
    prompt: str,
    max_output_tokens: int,
) -> str:

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

        print(
            "[KG] Ollama HTTP response received: "
            f"status={response.status_code}, "
            f"response_chars={len(response.text)}"
        )

        response.raise_for_status()

        payload = response.json()

        return str(
            payload.get(
                "response",
                "",
            )
        )

    except requests.RequestException as exc:
        print(
            "[KG] Ollama request failed: "
            f"{exc}"
        )

        raise HTTPException(
            status_code=502,
            detail=(
                "Ollama request failed: "
                f"{exc}"
            ),
        )


# ============================================================
# JSON EXTRACTION
# ============================================================

def extract_json(
    text: str,
) -> Dict[str, Any]:

    if not text:
        return {}

    value = text.strip()

    try:
        parsed = json.loads(
            value
        )

        if isinstance(
            parsed,
            dict,
        ):
            return parsed

    except json.JSONDecodeError:
        pass

    # Try extracting the first JSON object.
    start = value.find("{")
    end = value.rfind("}")

    if (
        start >= 0
        and end > start
    ):
        candidate = value[
            start : end + 1
        ]

        try:
            parsed = json.loads(
                candidate
            )

            if isinstance(
                parsed,
                dict,
            ):
                return parsed

        except json.JSONDecodeError:
            pass

    return {}


# ============================================================
# EVIDENCE / REFERENCE FILTERING
# ============================================================

def looks_like_reference_or_bibliography(
    text: str,
) -> bool:
    """
    Detect obvious bibliography/reference chunks.

    PDF extraction is inconsistent, so both:
        [4] Title...
    and:
        4] Title...
    are treated as possible reference entries.
    """

    normalized = normalize_text_for_matching(
        text
    )

    if not normalized:
        return True

    if re.search(
        r"^\s*(references|bibliography|"
        r"references and bibliography)\s*$",
        normalized,
        flags=re.IGNORECASE,
    ):
        return True

    if re.match(
        r"^\s*\[?\d{1,3}\]\s+",
        normalized,
    ):
        return True

    if re.match(
        r"^\s*\d{1,3}\s*\]\s+",
        normalized,
    ):
        return True

    if re.search(
        r"^\s*\[?\d{1,3}\s*\]\s+"
        r".*\b(?:arxiv|doi|technical report|"
        r"tech\.?\s*rep\.?|cern)\b",
        normalized,
        flags=re.IGNORECASE,
    ):
        return True

    if re.search(
        r"\b(?:collaboration|collaborations),\s+"
        r"the\s+phase[- ]?\d",
        normalized,
        flags=re.IGNORECASE,
    ) and re.search(
        r"\b(?:tech\.?\s*rep\.?|technical report|"
        r"cern[- ]lhcc|cern,)",
        normalized,
        flags=re.IGNORECASE,
    ):
        return True

    bibliographic_patterns = [
        r"\barxiv\s*:\s*\d{4}\.\d+",
        r"\bdoi\s*:",
        r"\bvol\.\s*\d+",
        r"\bpp?\.\s*\d+\s*[-–]\s*\d+",
        r"\bpages?\s+\d+\s*[-–]\s*\d+",
        r"\btrans\.\s+[a-z]",
        r"\bproc\.\s+",
        r"\bproceedings\b",
        r"\binternational conference\b",
        r"\btechnical report\b",
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
            r"\(\d{4}\)",
            normalized,
        )
        and (
            "arxiv" in normalized
            or "doi" in normalized
            or "trans." in normalized
            or "proc." in normalized
        )
    ):
        return True

    return False


def looks_like_metadata_only_chunk(
    text: str,
) -> bool:
    """
    Detect short metadata, headings and fragments.
    """

    normalized = normalize_text_for_matching(
        text
    )

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

    for prefix in metadata_prefixes:
        if normalized.startswith(
            prefix
        ):
            return True

    return False


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

    if looks_like_reference_or_bibliography(
        text
    ):
        return (
            0,
            "reference_or_bibliography",
        )

    if looks_like_metadata_only_chunk(
        text
    ):
        return (
            1,
            "metadata_or_fragment",
        )

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
        r"introduction|training|testing)\b",
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

    return (
        score,
        "research_prose",
    )


def select_high_quality_graph_chunks(
    chunks: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Select strongest evidence chunks.

    Reference chunks are discarded before the LLM sees them.
    """

    scored_chunks = []

    for chunk in chunks:

        quality_score, quality_reason = (
            evidence_chunk_quality(
                chunk
            )
        )

        chunk_index = chunk.get(
            "chunk_index"
        )

        if quality_score <= 1:
            print(
                "[KG] Retrieval chunk filtered: "
                f"reason={quality_reason}, "
                f"chunk_index={chunk_index}"
            )
            continue

        qdrant_score = float(
            chunk.get(
                "score",
                0.0,
            )
            or 0.0
        )

        combined_score = (
            quality_score
            + qdrant_score
        )

        scored_chunks.append(
            (
                combined_score,
                chunk,
            )
        )

    scored_chunks.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    selected = [
        item[1]
        for item in scored_chunks[
            :MAX_GRAPH_CHUNKS
        ]
    ]

    selected.sort(
        key=lambda chunk: (
            int(
                chunk.get(
                    "chunk_index",
                    0,
                )
                or 0
            )
        )
    )

    return selected


# ============================================================
# RETRIEVAL
# ============================================================

def retrieve_graph_chunks(
    resource_id: str,
) -> List[Dict[str, Any]]:

    queries = [
        "methods models tools datasets experiments evaluation results",
        "methodology architecture training testing evaluation results",
        "findings limitations future work proposed approach",
        "uses applies develops evaluates measures dataset metric",
    ]

    all_chunks: Dict[
        Tuple[str, str],
        Dict[str, Any],
    ] = {}

    print(
        "[KG] Starting optimized Qdrant retrieval "
        "using 4 query variations."
    )

    for index, query in enumerate(
        queries,
        start=1,
    ):

        print(
            "[KG] Retrieval query "
            f"{index}/{len(queries)}"
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

        for result in results:

            chunk_index = result.get(
                "chunk_index"
            )

            text = str(
                result.get(
                    "text",
                    "",
                )
            ).strip()

            key = (
                str(resource_id),
                str(chunk_index),
            )

            if not text:
                continue

            if key not in all_chunks:
                all_chunks[key] = result

    chunks = list(
        all_chunks.values()
    )

    print(
        "[KG] Unique chunks retrieved before "
        f"quality filtering: {len(chunks)}"
    )

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

    for chunk in selected:

        text = str(
            chunk.get(
                "text",
                "",
            )
        ).strip()

        preview = re.sub(
            r"\s+",
            " ",
            text,
        )[:180]

        print(
            "[KG] Selected chunk "
            f"{chunk.get('chunk_index')}: "
            f"{preview}"
        )

    return selected


# ============================================================
# EVIDENCE CONTEXT
# ============================================================

def build_evidence_context(
    chunks: List[Dict[str, Any]],
) -> str:

    context_parts = []

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

        text = text[
            :MAX_CHUNK_CHARS
        ]

        context_parts.append(
            f"[CHUNK {chunk_index}]\n"
            f"{text}"
        )

    return "\n\n".join(
        context_parts
    )


# ============================================================
# EXTRACTION
# ============================================================

def extract_graph_candidates(
    paper_title: str,
    chunks: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Ask Ollama to propose a small set of graph candidates.

    The LLM proposes facts.
    Python performs final deterministic validation.
    """

    context = build_evidence_context(
        chunks
    )

    prompt = f"""
You are extracting a SMALL knowledge graph from ONE research paper.

PAPER TITLE:
{paper_title}

SOURCE PASSAGES:
{context}

You MUST follow these rules.

SOURCE RESTRICTIONS:
- Use ONLY the supplied source passages.
- Do NOT use outside knowledge.
- Do NOT guess.
- Do NOT infer facts from co-occurrence.
- Do NOT extract information from bibliography/reference entries.
- Do NOT extract citation titles.
- Do NOT extract section headings.
- Do NOT extract figure captions or table captions.
- Do NOT extract keyword lists.
- Do NOT treat a cited paper as something used by the current paper
  unless the current paper explicitly says so.
- Do NOT create facts from a fragment that does not describe the
  current paper's work.

ENTITY TYPE RULE:

"type" MUST be EXACTLY ONE of:

"paper"
"author"
"method"
"dataset"
"metric"
"concept"
"finding"
"limitation"
"future_work"
"problem"
"organization"
"tool"
"model"

NEVER output:
"paper|concept"
"paper|method"
"method|model"
"concept/method"
or ANY combined type.

There must be exactly ONE type string per entity.

RELATION TYPE RULE:

"relation" MUST be EXACTLY ONE of:

"authored_by"
"uses"
"proposed"
"evaluated_on"
"discusses"
"reports"
"based_on"

Never combine relations.

ENTITY SELECTION:

Return at most 8 entities.

Only return entities that are genuinely relevant to the research work.

For each entity:
- Its name must literally occur in its evidence statement.
- Its evidence must be copied exactly from the supplied passage.
- Evidence must be an actual sentence or self-contained clause.
- The evidence must describe the current paper, not a cited work.
- Prefer fewer strong entities over many weak entities.
- Do not duplicate entities.
- Do not create the paper entity because the backend already supplies it.

METHOD / MODEL / TOOL:
Only extract these when the passage shows that the current paper
uses, applies, develops, trains, evaluates, describes, or discusses
the method/model/tool.

DATASET:
Only extract when the passage gives actual data, simulation,
training, testing, benchmark, or evaluation context.

METRIC:
Only extract when the passage actually measures or evaluates something.

FINDING:
Only extract when the passage explicitly reports a result or finding.

LIMITATION:
Only extract when the passage explicitly states a limitation.

FUTURE_WORK:
Only extract when the passage explicitly states future work.

PROBLEM:
Only extract when the passage explicitly identifies a research problem.

AUTHOR:
Only extract current paper authors, never authors mentioned inside
references.

ORGANIZATION:
Only extract an organization when the supplied prose connects it
to the current paper's work.

RELATIONSHIP RULES:

Return at most 5 relationships.

Both source and target MUST appear in the entity list.

The SAME evidence statement must explicitly support the complete
relationship.

Never infer a relationship from two entities simply appearing
together.

USES:
Require explicit wording such as:
uses, use, using, employs, applies, utilizes.

PROPOSED:
Require explicit wording such as:
proposes, proposed, introduces, develops.

EVALUATED_ON:
Require explicit evaluation, testing, benchmarking, or validation
language connecting the source to the target.

BASED_ON:
Require explicit wording such as:
based on, builds on, extends, derived from.

AUTHORED_BY:
Require explicit authorship evidence.

REPORTS:
Require explicit reporting of a result, measurement, or finding.

DISCUSSES:
Require actual discussion of the target.

Do not invent a relationship merely to fill the limit.

OUTPUT FORMAT:

Return JSON only.

Do not return Markdown.
Do not return comments.
Do not explain your answer.

Use exactly this structure:

{{
  "entities": [
    {{
      "name": "exact entity name",
      "type": "method",
      "description": "short factual description",
      "evidence": [
        {{
          "chunk_index": 16,
          "statement": "exact contiguous source text"
        }}
      ]
    }}
  ],
  "relationships": [
    {{
      "source": "exact entity name",
      "target": "exact entity name",
      "relation": "uses",
      "evidence": [
        {{
          "chunk_index": 16,
          "statement": "exact contiguous source text"
        }}
      ]
    }}
  ]
}}

FINAL CHECK:

Before returning JSON:
1. Every entity type is exactly ONE allowed value.
2. No entity type contains "|".
3. No entity type contains "/".
4. Every relation is exactly ONE allowed value.
5. Every entity name appears in its evidence.
6. Every evidence statement exists in the supplied passages.
7. No bibliography/reference candidate remains.
8. No keyword-only candidate remains.
9. Every relationship has explicit evidence.
10. Remove uncertain candidates.

Return JSON only.
"""

    start_time = time.time()

    print(
        "[KG] Calling Ollama for graph extraction..."
    )

    response_text = call_ollama(
        prompt,
        OLLAMA_EXTRACTION_MAX_TOKENS,
    )

    elapsed = (
        time.time()
        - start_time
    )

    print(
        "[KG] Ollama extraction completed in "
        f"{elapsed:.2f} seconds."
    )

    raw_response = str(
        response_text or ""
    ).strip()

    print(
        "[KG] Raw Ollama extraction response "
        f"length: {len(raw_response)} character(s)."
    )

    if raw_response:

        print(
            "[KG] Raw Ollama extraction response:"
        )

        print(
            raw_response[:5000]
        )

        if len(raw_response) > 5000:
            print(
                "[KG] Raw Ollama response truncated "
                "in log; remaining characters: "
                f"{len(raw_response) - 5000}."
            )

    else:

        print(
            "[KG] WARNING: Ollama returned an "
            "empty extraction response."
        )

    candidates = extract_json(
        raw_response
    )

    if not candidates:

        print(
            "[KG] WARNING: Extraction response "
            "could not be parsed as JSON."
        )

        return {
            "entities": [],
            "relationships": [],
        }

    print(
        "[KG] Parsed extraction JSON keys: "
        f"{list(candidates.keys())}"
    )

    if "entities" not in candidates:

        for alias in (
            "entity",
            "nodes",
        ):

            if isinstance(
                candidates.get(alias),
                list,
            ):

                candidates[
                    "entities"
                ] = candidates[
                    alias
                ]

                print(
                    "[KG] Diagnostic schema alias "
                    f"used for entities: '{alias}'."
                )

                break

    if "relationships" not in candidates:

        for alias in (
            "relations",
            "relationship",
            "edges",
        ):

            if isinstance(
                candidates.get(alias),
                list,
            ):

                candidates[
                    "relationships"
                ] = candidates[
                    alias
                ]

                print(
                    "[KG] Diagnostic schema alias "
                    f"used for relationships: '{alias}'."
                )

                break

    entities = candidates.get(
        "entities",
        [],
    )

    relationships = candidates.get(
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

    candidates[
        "entities"
    ] = entities[
        :MAX_GRAPH_ENTITIES
    ]

    candidates[
        "relationships"
    ] = relationships[
        :MAX_GRAPH_RELATIONSHIPS
    ]

    print(
        "[KG] Extraction schema counts "
        "before deterministic validation: "
        f"entities={len(candidates['entities'])}, "
        f"relationships={len(candidates['relationships'])}"
    )

    return candidates


# ============================================================
# EVIDENCE VALIDATION
# ============================================================

def find_chunk_text(
    chunks: List[Dict[str, Any]],
    chunk_index: Any,
) -> str:

    target = str(
        chunk_index
    )

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

    return (
        statement_normalized
        in chunk_normalized
    )


def evidence_is_valid(
    evidence: Any,
    chunks: List[Dict[str, Any]],
) -> bool:

    if not isinstance(
        evidence,
        list,
    ):
        return False

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

        if statement_is_supported_by_chunk(
            statement,
            chunk_text,
        ):
            return True

    return False


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

    seen_names = set()

    print(
        "[KG] Deterministically validating entities..."
    )

    for entity in raw_entities:

        if not isinstance(
            entity,
            dict,
        ):
            print(
                "[KG] Entity rejected: "
                "candidate is not an object."
            )
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

        evidence = entity.get(
            "evidence",
            [],
        )

        if not name:

            print(
                "[KG] Entity rejected: "
                "missing name."
            )

            continue

        if "|" in entity_type:

            print(
                "[KG] Entity rejected: "
                f"combined type | name='{name}' "
                f"type='{entity_type}'"
            )

            continue

        if "/" in entity_type:

            print(
                "[KG] Entity rejected: "
                f"combined type | name='{name}' "
                f"type='{entity_type}'"
            )

            continue

        if entity_type not in SUPPORTED_ENTITY_TYPES:

            print(
                "[KG] Entity rejected: "
                f"unsupported type | name='{name}' "
                f"type='{entity_type}'"
            )

            continue

        normalized_name = (
            normalize_entity_name(
                name
            )
        )

        if not normalized_name:
            continue

        if normalized_name in seen_names:

            print(
                "[KG] Entity rejected: "
                f"duplicate | name='{name}'"
            )

            continue

        if not evidence_is_valid(
            evidence,
            chunks,
        ):

            print(
                "[KG] Entity rejected: "
                "evidence is missing, unsupported, "
                f"or not sufficiently specific | "
                f"name='{name}'"
            )

            continue

        # The entity name must occur in at least one
        # supported evidence statement.
        name_supported = False

        for evidence_item in evidence:

            if not isinstance(
                evidence_item,
                dict,
            ):
                continue

            chunk_index = evidence_item.get(
                "chunk_index"
            )

            statement = str(
                evidence_item.get(
                    "statement",
                    "",
                )
            ).strip()

            chunk_text = find_chunk_text(
                chunks,
                chunk_index,
            )

            if (
                statement_is_supported_by_chunk(
                    statement,
                    chunk_text,
                )
                and normalize_entity_name(
                    name
                )
                in normalize_entity_name(
                    statement
                )
            ):

                name_supported = True
                break

        if not name_supported:

            print(
                "[KG] Entity rejected: "
                "entity name is not explicitly present "
                f"in evidence | name='{name}'"
            )

            continue

        validated_entity = {
            "id": normalized_name,
            "name": name,
            "type": entity_type,
            "description": description,
            "evidence": evidence,
        }

        validated.append(
            validated_entity
        )

        seen_names.add(
            normalized_name
        )

    print(
        "[KG] Deterministically validated entities: "
        f"{len(validated)}"
    )

    return validated


# ============================================================
# RELATIONSHIP VALIDATION
# ============================================================

def explicit_relation_language_exists(
    relation: str,
    statement: str,
) -> bool:

    text = normalize_text_for_matching(
        statement
    )

    if relation == "uses":

        return bool(
            re.search(
                r"\b(?:use|uses|using|used|"
                r"employ|employs|employed|"
                r"apply|applies|applied|"
                r"utilize|utilizes|utilized)\b",
                text,
            )
        )

    if relation == "proposed":

        return bool(
            re.search(
                r"\b(?:propose|proposes|proposed|"
                r"introduce|introduces|introduced|"
                r"develop|develops|developed)\b",
                text,
            )
        )

    if relation == "evaluated_on":

        return bool(
            re.search(
                r"\b(?:evaluate|evaluates|evaluated|"
                r"evaluation|test|tests|tested|testing|"
                r"benchmark|benchmarks|benchmarked|"
                r"validate|validates|validated)\b",
                text,
            )
        )

    if relation == "based_on":

        return bool(
            re.search(
                r"\b(?:based on|builds on|built on|"
                r"build upon|extends|extended from|"
                r"derived from)\b",
                text,
            )
        )

    if relation == "authored_by":

        return bool(
            re.search(
                r"\b(?:authored by|written by|"
                r"authors?|by)\b",
                text,
            )
        )

    if relation == "reports":

        return bool(
            re.search(
                r"\b(?:reports?|reported|finds?|"
                r"found|shows?|showed|demonstrates?|"
                r"demonstrated|measures?|measured)\b",
                text,
            )
        )

    if relation == "discusses":

        return bool(
            re.search(
                r"\b(?:discuss|discusses|discussed|"
                r"describes|described|examines|"
                r"examined|considers|considered)\b",
                text,
            )
        )

    return False


def source_target_explicitly_supported(
    source_name: str,
    target_name: str,
    statement: str,
) -> bool:

    normalized_statement = (
        normalize_text_for_matching(
            statement
        )
    )

    normalized_source = (
        normalize_text_for_matching(
            source_name
        )
    )

    normalized_target = (
        normalize_text_for_matching(
            target_name
        )
    )

    if (
        not normalized_source
        or not normalized_target
    ):
        return False

    return (
        normalized_source
        in normalized_statement
        and normalized_target
        in normalized_statement
    )


def validate_relationship_candidates(
    candidates: Dict[str, Any],
    entities: List[Dict[str, Any]],
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

    entity_map = {}

    for entity in entities:

        entity_map[
            normalize_entity_name(
                entity["name"]
            )
        ] = entity

    validated = []

    seen_edges = set()

    print(
        "[KG] Deterministically validating relationships..."
    )

    for relationship in raw_relationships:

        if not isinstance(
            relationship,
            dict,
        ):
            print(
                "[KG] Relationship rejected: "
                "candidate is not an object."
            )
            continue

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
            str(
                relationship.get(
                    "relation",
                    "",
                )
            )
        )

        evidence = relationship.get(
            "evidence",
            [],
        )

        source_key = normalize_entity_name(
            source
        )

        target_key = normalize_entity_name(
            target
        )

        if (
            source_key not in entity_map
            or target_key not in entity_map
        ):

            print(
                "[KG] Relationship rejected: "
                "unknown endpoint"
            )

            continue

        if relation not in SUPPORTED_RELATION_TYPES:

            print(
                "[KG] Relationship rejected: "
                f"unsupported relation='{relation}'"
            )

            continue

        edge_key = (
            source_key,
            target_key,
            relation,
        )

        if edge_key in seen_edges:

            print(
                "[KG] Relationship rejected: "
                "duplicate"
            )

            continue

        if not isinstance(
            evidence,
            list,
        ):

            print(
                "[KG] Relationship rejected: "
                "invalid evidence"
            )

            continue

        relationship_supported = False

        for evidence_item in evidence:

            if not isinstance(
                evidence_item,
                dict,
            ):
                continue

            chunk_index = evidence_item.get(
                "chunk_index"
            )

            statement = str(
                evidence_item.get(
                    "statement",
                    "",
                )
            ).strip()

            chunk_text = find_chunk_text(
                chunks,
                chunk_index,
            )

            if not statement_is_supported_by_chunk(
                statement,
                chunk_text,
            ):
                continue

            if not source_target_explicitly_supported(
                source,
                target,
                statement,
            ):
                continue

            if not explicit_relation_language_exists(
                relation,
                statement,
            ):
                continue

            relationship_supported = True
            break

        if not relationship_supported:

            print(
                "[KG] Relationship rejected: "
                "source, target, and explicit relation "
                "language were not all present in the "
                "same evidence statement"
            )

            continue

        validated.append(
            {
                "source": entity_map[
                    source_key
                ]["id"],
                "target": entity_map[
                    target_key
                ]["id"],
                "relationship": relation,
                "evidence": evidence,
            }
        )

        seen_edges.add(
            edge_key
        )

    print(
        "[KG] Deterministically validated relationships: "
        f"{len(validated)}"
    )

    return validated


# ============================================================
# SEMANTIC VALIDATION
# ============================================================

def semantic_validate_relationships(
    entities: List[Dict[str, Any]],
    relationships: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:

    if not relationships:

        print(
            "[KG] No deterministically validated "
            "relationships require semantic validation."
        )

        return []

    entity_map = {
        entity["id"]: entity
        for entity in entities
    }

    compact_relationships = []

    for relationship in relationships:

        source_id = relationship[
            "source"
        ]

        target_id = relationship[
            "target"
        ]

        source = entity_map.get(
            source_id
        )

        target = entity_map.get(
            target_id
        )

        if not source or not target:
            continue

        compact_relationships.append(
            {
                "source_id": source_id,
                "source": source["name"],
                "target_id": target_id,
                "target": target["name"],
                "relation": relationship[
                    "relationship"
                ],
            }
        )

    if not compact_relationships:
        return []

    prompt = f"""
You are performing semantic validation of already
deterministically validated relationships.

You are NOT allowed to create new relationships.

You are NOT allowed to:
- rename entities
- rename relationships
- modify IDs
- infer new relationships
- add evidence
- remove evidence
- create entities

You may ONLY decide whether each supplied relationship
is semantically reasonable given the supplied entities.

ENTITIES:
{json.dumps(
    [
        {
            "id": entity["id"],
            "name": entity["name"],
            "type": entity["type"],
        }
        for entity in entities
    ],
    ensure_ascii=False,
)}

RELATIONSHIPS:
{json.dumps(
    compact_relationships,
    ensure_ascii=False,
)}

Return JSON only:

{{
  "accepted_relationship_ids": [
    {{
      "source_id": "existing source id",
      "target_id": "existing target id",
      "relation": "existing relation"
    }}
  ]
}}

IMPORTANT:
- Only use IDs and relations already supplied.
- Do not create anything.
- If uncertain, reject the relationship.
"""

    print(
        "[KG] Calling Ollama for semantic validation..."
    )

    start_time = time.time()

    response_text = call_ollama(
        prompt,
        OLLAMA_VALIDATION_MAX_TOKENS,
    )

    elapsed = (
        time.time()
        - start_time
    )

    print(
        "[KG] Ollama semantic validation "
        f"completed in {elapsed:.2f} seconds."
    )

    parsed = extract_json(
        response_text
    )

    accepted = parsed.get(
        "accepted_relationship_ids",
        [],
    )

    if not isinstance(
        accepted,
        list,
    ):
        return []

    valid_keys = {
        (
            item["source"],
            item["target"],
            item["relation"],
        )
        for item in compact_relationships
    }

    final_relationships = []

    for item in accepted:

        if not isinstance(
            item,
            dict,
        ):
            continue

        key = (
            str(
                item.get(
                    "source_id",
                    "",
                )
            ),
            str(
                item.get(
                    "target_id",
                    "",
                )
            ),
            normalize_relation(
                str(
                    item.get(
                        "relation",
                        "",
                    )
                )
            ),
        )

        if key not in valid_keys:
            continue

        for relationship in relationships:

            relationship_key = (
                relationship[
                    "source"
                ],
                relationship[
                    "target"
                ],
                relationship[
                    "relationship"
                ],
            )

            if (
                relationship_key
                == key
            ):

                final_relationships.append(
                    relationship
                )

                break

    return final_relationships


# ============================================================
# GRAPH NODE CREATION
# ============================================================

def build_graph_nodes(
    paper: Dict[str, Any],
    entities: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:

    paper_id = str(
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

    nodes = [
        {
            "id": paper_id,
            "name": paper_title,
            "type": "paper",
            "description": "",
            "resource_id": paper_id,
        }
    ]

    for entity in entities:

        entity_id = entity[
            "id"
        ]

        if entity_id == normalize_entity_name(
            paper_title
        ):
            continue

        node = {
            "id": entity_id,
            "name": entity[
                "name"
            ],
            "type": entity[
                "type"
            ],
            "description": entity.get(
                "description",
                "",
            ),
            "resource_id": paper_id,
            "evidence": entity.get(
                "evidence",
                [],
            ),
        }

        nodes.append(
            node
        )

    return nodes


# ============================================================
# GRAPH EDGE CREATION
# ============================================================

def build_graph_edges(
    relationships: List[Dict[str, Any]],
    entities: List[Dict[str, Any]],
    paper_id: str,
) -> List[Dict[str, Any]]:

    entity_map = {
        entity["id"]: entity
        for entity in entities
    }

    edges = []

    for relationship in relationships:

        source_id = relationship[
            "source"
        ]

        target_id = relationship[
            "target"
        ]

        source_entity = entity_map.get(
            source_id
        )

        target_entity = entity_map.get(
            target_id
        )

        if not source_entity:
            continue

        if not target_entity:
            continue

        edges.append(
            {
                "source": source_id,
                "target": target_id,
                "relationship": relationship[
                    "relationship"
                ],
                "resource_id": paper_id,
                "evidence": relationship.get(
                    "evidence",
                    [],
                ),
            }
        )

    return edges


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

        if paper:
            return paper

    except Exception as exc:

        print(
            "[KG] MongoDB lookup failed: "
            f"{exc}"
        )

    return None


# ============================================================
# SINGLE PAPER GRAPH
# ============================================================

def process_single_paper(
    resource_id: str,
) -> Dict[str, Any]:

    print(
        "[KG] Processing resource: "
        f"{resource_id}"
    )

    paper = get_paper_by_resource_id(
        resource_id
    )

    if not paper:

        print(
            "[KG] Paper not found in MongoDB: "
            f"{resource_id}"
        )

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
        "[KG] Paper found: "
        f"{title}"
    )

    chunks = retrieve_graph_chunks(
        resource_id
    )

    if not chunks:

        print(
            "[KG] No usable Qdrant chunks "
            f"found for resource: {resource_id}"
        )

        nodes = [
            {
                "id": str(
                    resource_id
                ),
                "name": title,
                "type": "paper",
                "description": "",
                "resource_id": str(
                    resource_id
                ),
            }
        ]

        return {
            "processed": True,
            "resource_id": resource_id,
            "reason": "",
            "nodes": nodes,
            "edges": [],
        }

    print(
        "[KG] Chunks sent to extraction model: "
        f"{len(chunks)}"
    )

    print(
        "[KG] Extracting graph candidates..."
    )

    candidates = extract_graph_candidates(
        paper_title=title,
        chunks=chunks,
    )

    print(
        "[KG] LLM proposed "
        f"{len(candidates.get('entities', []))} "
        "entity candidate(s) and "
        f"{len(candidates.get('relationships', []))} "
        "relationship candidate(s)."
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
            chunks,
        )
    )

    semantically_validated_relationships = (
        semantic_validate_relationships(
            validated_entities,
            validated_relationships,
        )
    )

    print(
        "[KG] Final validated entities: "
        f"{len(validated_entities)}"
    )

    print(
        "[KG] Final validated relationships: "
        f"{len(semantically_validated_relationships)}"
    )

    nodes = build_graph_nodes(
        paper,
        validated_entities,
    )

    edges = build_graph_edges(
        semantically_validated_relationships,
        validated_entities,
        str(resource_id),
    )

    print(
        "[KG] Graph completed: "
        f"{len(nodes)} node(s), "
        f"{len(edges)} edge(s)."
    )

    return {
        "processed": True,
        "resource_id": str(
            resource_id
        ),
        "reason": "",
        "nodes": nodes,
        "edges": edges,
    }


# ============================================================
# API ENDPOINT
# ============================================================

@router.post("")
def generate_knowledge_graph(
    request: KnowledgeGraphRequest,
):

    resource_ids = [
        str(resource_id).strip()
        for resource_id in request.resource_ids
        if str(resource_id).strip()
    ]

    if not resource_ids:

        raise HTTPException(
            status_code=400,
            detail="At least one resource_id is required.",
        )

    print(
        "[KG] Knowledge graph request received "
        f"for {len(resource_ids)} resource(s)."
    )

    all_nodes = []
    all_edges = []

    processed_papers = []
    skipped_papers = []

    for resource_id in resource_ids:

        try:

            result = process_single_paper(
                resource_id
            )

            if result[
                "processed"
            ]:

                processed_papers.append(
                    resource_id
                )

                all_nodes.extend(
                    result.get(
                        "nodes",
                        [],
                    )
                )

                all_edges.extend(
                    result.get(
                        "edges",
                        [],
                    )
                )

            else:

                skipped_papers.append(
                    {
                        "resource_id": resource_id,
                        "reason": result.get(
                            "reason",
                            "Unknown reason",
                        ),
                    }
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
                    "reason": str(
                        exc
                    ),
                }
            )

    # --------------------------------------------------------
    # Deduplicate nodes
    # --------------------------------------------------------

    unique_nodes = []
    node_ids = set()

    for node in all_nodes:

        node_id = str(
            node.get(
                "id",
                "",
            )
        )

        if not node_id:
            continue

        if node_id in node_ids:
            continue

        node_ids.add(
            node_id
        )

        unique_nodes.append(
            node
        )

    # --------------------------------------------------------
    # Deduplicate edges
    # --------------------------------------------------------

    unique_edges = []
    edge_keys = set()

    for edge in all_edges:

        key = (
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
            str(
                edge.get(
                    "relationship",
                    "",
                )
            ),
            str(
                edge.get(
                    "resource_id",
                    "",
                )
            ),
        )

        if key in edge_keys:
            continue

        edge_keys.add(
            key
        )

        unique_edges.append(
            edge
        )

    response = {
        "nodes": unique_nodes,
        "edges": unique_edges,
        "meta": {
            "requested_resources": len(
                resource_ids
            ),
            "processed_papers": len(
                processed_papers
            ),
            "skipped_papers": skipped_papers,
            "node_count": len(
                unique_nodes
            ),
            "edge_count": len(
                unique_edges
            ),
        },
    }

    print(
        "[KG] Request completed: "
        f"{len(processed_papers)} paper(s), "
        f"{len(unique_nodes)} node(s), "
        f"{len(unique_edges)} edge(s)."
    )

    return response