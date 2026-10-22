"""SciBrain evidence-grounded knowledge graph service.

Preserves the existing generate_knowledge_graph(resource_ids) API and the
ReactFlow response contract while validating extracted claims against source
sentences and paper ownership. Gemini proposes graph facts; deterministic
checks decide which facts are accepted.
"""
from __future__ import annotations

import hashlib
import logging
import math
import os
import re
import time
from collections import Counter
from typing import Any, Dict, List, Optional, Set, Tuple

from fastapi import HTTPException

from app.database.mongodb import papers_collection
from app.services.vector_store import search_paper_chunks

logger = logging.getLogger(__name__)

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

RETRIEVAL_LIMIT = max(4, int(os.getenv("KG_RETRIEVAL_LIMIT", "6")))
MAX_CHUNKS_PER_PAPER = max(12, int(os.getenv("KG_MAX_CHUNKS_PER_PAPER", "18")))
MAX_CHUNKS_PER_BATCH = max(1, int(os.getenv("KG_MAX_CHUNKS_PER_BATCH", "2")))
MAX_CHUNK_CHARS = max(1200, int(os.getenv("KG_MAX_CHUNK_CHARS", "2800")))
MAX_ENTITIES = 150
MAX_RELATIONSHIPS = 200
MAX_EVIDENCE_PER_NODE = 5
MAX_EVIDENCE_PER_EDGE = 5
REFERENCE_RATIO_LIMIT = 0.45
MIN_RELATION_EVIDENCE_CHARS = 24

NODE_TYPES = {
    "author", "method", "dataset", "metric", "concept", "finding",
    "limitation", "future_work", "problem", "organization", "tool", "model",
}
RELATIONSHIP_TYPES = {
    "authored_by", "developed_by", "introduced_by", "uses", "proposed",
    "evaluated_on", "discusses", "reports", "based_on", "addresses",
    "measures", "implements", "extends", "improves", "compares_with",
    "has_finding", "has_limitation", "has_future_work", "designs",
}

ADDITIONAL_INSTRUCTIONS = """
Extract a scientific knowledge graph from the supplied research text.
Return only entities and relationships explicitly supported by the text.
Preserve entity names and acronyms as written; do not invent expansions.
Do not extract generic terms (paper, approach, research, results) as entities.
Do not treat questions, headings, references, or bibliography entries as claims.
Co-occurrence is not a relationship. A relationship needs an explicit statement.
Preserve direction: 'X was developed by Y' means X -> Y, DEVELOPED_BY.
For 'X uses Y', the direction is X -> Y, USES. Do not reverse relationships.
Do not infer cross-paper relationships because entities appear in multiple papers.
Do not claim a comparison, improvement, dataset use, or causal link without text.
Attach no fabricated evidence. Use the listed node and relationship types only.
Node types: Author, Method, Dataset, Metric, Concept, Finding, Limitation,
FutureWork, Problem, Organization, Tool, Model.
Relationship types: AUTHORED_BY, DEVELOPED_BY, INTRODUCED_BY, USES, PROPOSED,
EVALUATED_ON, DISCUSSES, REPORTS, BASED_ON, ADDRESSES, MEASURES, IMPLEMENTS,
EXTENDS, IMPROVES, COMPARES_WITH, HAS_FINDING, HAS_LIMITATION, HAS_FUTURE_WORK, DESIGNS.
""".strip()

# Cues are necessary but not sufficient: validate grammatical direction below.
RELATION_CUES: Dict[str, Tuple[str, ...]] = {
    "authored_by": (
        "authored by", "written by", "co-authored by", "authors include", "authored",
    ),
    "developed_by": (
        "developed by", "developed", "created by", "created", "built by", "built",
        "implemented by", "designed by", "designed",
    ),
    "introduced_by": (
        "introduced by", "introduced", "proposed by", "first introduced by",
        "first proposed by", "presented by", "presented",
    ),
    "uses": (
        "makes use of", "makes use", "uses", "used", "using", "utilizes",
        "utilises", "employs", "employed", "applies", "applied", "adopts",
        "adopted", "incorporates", "integrates", "integrated", "leverages",
        "leveraged",
    ),
    "proposed": (
        "we propose", "proposes", "proposed", "we introduce", "we present",
        "we develop", "introduces", "presented",
    ),
    "evaluated_on": (
        "evaluated on", "evaluated using", "evaluated against", "tested on",
        "tested using", "assessed on", "assessed using", "experiments on",
        "experimented on", "benchmarked on", "evaluation on",
    ),
    "discusses": (
        "discusses", "examines", "investigates", "analyzes", "analyses",
        "explores", "describes",
    ),
    "reports": (
        "reports", "reported", "findings show", "results show", "results indicate",
        "results demonstrate", "demonstrates", "demonstrated", "shows", "showed",
    ),
    "based_on": (
        "based on", "derived from", "built upon", "builds upon", "grounded in",
        "draws on", "drawn from",
    ),
    "addresses": (
        "addresses", "tackles", "targets", "solves", "mitigates",
        "aims to address", "is designed to address",
    ),
    "measures": (
        "measures", "measured by", "evaluated using", "assessed using",
        "quantified by",
    ),
    "implements": (
        "implements", "implemented in", "realizes", "realises", "realized by",
        "realised by",
    ),
    "extends": (
        "extends", "extension of", "extends the", "builds on", "built on",
        "is an extension of",
    ),
    "improves": (
        "improves", "improved by", "improved over", "outperforms", "outperformed",
        "achieves higher", "increases", "increased", "reduces", "reduced",
        "improvement over", "performs better than",
    ),
    "compares_with": (
        "compared with", "compared to", "compared against", "comparison with",
        "comparison between", "in comparison with", "compares with", "compares to",
        "outperforms", "performs better than", "performs worse than",
    ),
    "has_finding": (
        "findings show", "findings indicate", "the study found", "results show",
        "results indicate", "we found that", "the results suggest",
    ),
    "has_limitation": (
        "limitations include", "is limited by", "are limited by", "limited to",
        "limited computational resources", "limited resources",
        "computational constraints", "suffers from", "the main drawback",
        "is constrained by",
    ),
    "has_future_work": (
        "future work", "future research", "remains future work",
        "we leave for future work", "further investigation", "future directions",
    ),
    "designs": ("designs", "designed", "architects"),
}

QUESTION_PATTERNS = (
    "what advantages", "what do you think", "how does", "how do", "can you",
    "could you", "which is better", "what is the difference", "do you think",
    "would you recommend", "why does", "why do", "is it better", "which method",
    "which approach",
)
NEGATION_PATTERNS = (
    "does not", "do not", "did not", "cannot", "can not", "never", "fails to",
    "failed to", "unable to", "no evidence that", "not shown to", "not demonstrate",
    "not improve", "not outperform", "didn't", "doesn't", "isn't", "wasn't",
)


def normalize_source_text(value: Any) -> str:
    """Normalize OCR whitespace while preserving line boundaries for reference filtering."""
    if value is None:
        return ""
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"(?<=\w)-\s*\n\s*(?=\w)", "", text)
    text = re.sub(r"[‐‑‒–—−]", "-", text)
    lines = [re.sub(r"[\t\f\v ]+", " ", line).strip() for line in text.split("\n")]
    # Collapse repeated blank lines, but do not flatten distinct source lines.
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", normalize_source_text(value)).strip()


def normalized_match_text(value: Any) -> str:
    """Build a comparison key without discarding scientific Unicode characters.

    Keep acronyms, parenthetical expansions, model versions, Greek letters, and
    official punctuation-bearing names semantically distinct where possible.
    This key is for matching only; the original display name is never rewritten.
    """
    text = normalize_text(value).casefold()
    text = re.sub(r"[‐‑‒–—−]", "-", text)
    text = text.replace("_", " ")
    text = re.sub(r"[^\w]+", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def canonical_name(value: Any) -> str:
    """Normalize spacing/case/punctuation, but never strip a scientific acronym.

    In particular, ``Long Method Name (LMN)`` is not silently collapsed to
    ``Long Method Name``. That earlier shortcut could merge distinct labels and
    conceal whether an acronym was explicitly part of the source name.
    """
    return normalized_match_text(value)


def stable_id(prefix: str, value: str) -> str:
    return f"{prefix}_{hashlib.sha256(value.encode('utf-8')).hexdigest()[:16]}"


def clean_entity_name(value: Any) -> str:
    name = normalize_text(value).strip(" \t\r\n.,;:()[]{}\"'")
    if not name:
        return ""
    # Truncated parentheticals are usually malformed model/OCR output.
    if name.count("(") > name.count(")"):
        name = name[:name.rfind("(")].strip()
    name = re.sub(r"\s+", " ", name).strip(" .,;:")
    if not name or len(name) > 160 or len(name.split()) > 18:
        return ""
    if len(re.sub(r"[^A-Za-z0-9]", "", name)) < 2 or name.count("(") != name.count(")"):
        return ""
    if normalized_match_text(name) in {
        "paper", "research", "research paper", "methodology", "approach", "results",
        "result", "study", "work", "authors", "the authors", "this paper", "this study",
        "the method", "the model", "the system", "figure", "table", "section",
        "conclusion", "introduction", "abstract", "references",
    }:
        return ""
    return name


def normalize_node_type(value: Any) -> str:
    raw = normalized_match_text(value).replace(" ", "_")
    aliases = {
        "person": "author", "researcher": "author", "scientist": "author",
        "algorithm": "method", "technique": "method", "approach": "method",
        "benchmark": "dataset", "corpus": "dataset", "evaluation_metric": "metric",
        "performance_metric": "metric", "issue": "problem", "challenge": "problem",
        "research_gap": "problem", "software": "tool", "library": "tool",
        "framework": "tool", "platform": "tool", "application": "tool",
        "model_architecture": "model", "futurework": "future_work", "future": "future_work",
        "company": "organization", "institution": "organization", "result": "finding",
    }
    candidate = aliases.get(raw, raw)
    return candidate if candidate in NODE_TYPES else "concept"


def infer_entity_type(name: str, proposed_type: Any) -> str:
    """Correct common taxonomy mistakes without trying to infer arbitrary types."""
    key = normalized_match_text(name)
    proposed = normalize_node_type(proposed_type)
    # A general RAG system/domain is a concept, not a named ML model.
    if key in {
        "rag system", "rag systems", "retrieval augmented generation systems",
        "retrieval augmented generation rag systems", "retrieval augmented generation system",
    }:
        return "concept"
    # Named RAG algorithms/approaches are methods; avoid labelling them as generic models.
    if key in {"self rag", "graphrag", "graph rag", "corrective rag", "adaptive rag", "r rag"}:
        return "method"
    # Preserve well-established broad model families as models.
    if key in {"large language model", "large language models", "llm", "llms", "large language model llms"}:
        return "model"
    return proposed


def normalize_relation_type(value: Any) -> str:
    raw = normalized_match_text(value).replace(" ", "_").replace("-", "_")
    aliases = {
        "author_of": "authored_by", "created_by": "developed_by", "introduced": "introduced_by",
        "evaluated_using": "evaluated_on", "tested_on": "evaluated_on", "based_upon": "based_on",
        "addresses_problem": "addresses", "compared_to": "compares_with", "compared_with": "compares_with",
    }
    candidate = aliases.get(raw, raw)
    return candidate if candidate in RELATIONSHIP_TYPES else ""


def get_properties(obj: Any) -> Dict[str, Any]:
    value = getattr(obj, "properties", None)
    return value if isinstance(value, dict) else {}


def property_value(properties: Dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = properties.get(key)
        if value is not None and str(value).strip():
            return normalize_text(value)
    return ""


def is_question_or_heading(text: str) -> bool:
    value = normalize_text(text)
    if not value or value.endswith("?"):
        return True
    lowered = value.casefold()
    if any(pattern in lowered for pattern in QUESTION_PATTERNS):
        return True
    if len(value) < 100 and not re.search(r"[.!?]", value):
        if lowered.startswith(("keywords:", "abstract", "introduction", "references", "bibliography", "table ", "figure ", "fig. ")):
            return True
    return False


def is_reference_heavy(text: str) -> bool:
    value = normalize_source_text(text)
    if not value:
        return True
    lines = [line.strip() for line in value.splitlines() if line.strip()] or [normalize_text(value)]
    patterns = (r"\bdoi\s*:", r"\barxiv\s*:", r"\bvol\.\s*\d+", r"\bpp\.\s*\d+", r"\bet al\.\s*,?\s*\d{4}", r"https?://")
    hits = 0
    for line in lines:
        reference_marker = bool(re.match(r"^(?:\[\d+\]|\(\d{4}\)|\d+\.\s+[A-Z])", line))
        metadata_hits = sum(bool(re.search(pattern, line, re.I)) for pattern in patterns)
        if reference_marker or metadata_hits >= 2:
            hits += 1
    # Also reject a short bibliography chunk consisting almost entirely of citation lines.
    return len(lines) >= 3 and hits / len(lines) >= REFERENCE_RATIO_LIMIT
def split_sentences(text: str) -> List[str]:
    """Split on sentence punctuation without splitting common academic abbreviations."""
    value = normalize_source_text(text)
    if not value:
        return []
    value = re.sub(
        r"\b(et al|e\.g|i\.e|fig|eq|dr|prof|vs)\.",
        lambda m: m.group(0).replace(".", "<DOT>"),
        value,
        flags=re.I,
    )
    value = re.sub(r"\b([A-Z])\.", r"\1<DOT>", value)
    parts = re.split(r"(?<=[.!?])\s+", value)
    return [part.replace("<DOT>", ".").strip() for part in parts if part.strip()]


def name_is_mentioned(name: str, text: str) -> bool:
    """Conservative mention matching with a boundary-safe BERT OCR exception."""
    target = canonical_name(name)
    source = normalized_match_text(text)
    if not target or not source:
        return False
    if f" {target} " in f" {source} ":
        return True
    # Accept BERT-based and OCR-flattened BERTbased, but never ColBERT.
    if target == "bert":
        return bool(
            re.search(
                r"(?<![\w])bert(?:[-‐‑‒–— ]?based)?(?![\w])",
                str(text),
                re.I,
            )
        )
    return False


def is_probable_metadata_sentence(sentence: str) -> bool:
    """Reject bibliography/front-matter fragments as claim evidence."""
    s = normalize_text(sentence)
    low = s.casefold()
    if re.match(r"^\s*(references|bibliography|keywords|doi|arxiv|abstract\s*[:.]?$)\b", low):
        return True
    if re.match(r"^\s*\[\d+\]", s):
        return True

    metadata_markers = (
        "corresponding author", "author email", "email:", "all rights reserved",
        "highlights in science", "volume ", "school of ", "department of ",
        "submitted on", "accepted on", "published online", "copyright",
    )
    if any(marker in low for marker in metadata_markers):
        return True

    if re.search(r"\b(19|20)\d{2}\b", s) and re.search(
        r"\b(in proceedings|journal of|arxiv|doi:|vol\.|pp\.)\b", low
    ):
        if not re.search(
            r"\b(proposes|develops|evaluates|shows|demonstrates|reports|uses|introduces|implements)\b",
            low,
        ):
            return True
    return False


def is_truncated_final_sentence(
    source_text: str,
    sentence: str,
    index: int,
    sentences: List[str],
) -> bool:
    return (
        len(source_text) >= MAX_CHUNK_CHARS
        and index == len(sentences) - 1
        and sentence == sentences[-1]
        and not re.search(r"[.!?][\"')\]]?$", sentence)
    )


def find_entity_evidence(
    name: str,
    chunks: List[Dict[str, Any]],
    entity_type: str = "concept",
) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Choose strong local evidence instead of the first incidental mention.

    Front matter may be used only as a fallback for author/institution nodes.
    For research concepts and technical entities, prefer explanatory body text.
    """
    candidates: List[Tuple[int, int, str, Dict[str, Any]]] = []
    metadata_fallbacks: List[Tuple[int, int, str, Dict[str, Any]]] = []

    for chunk_order, chunk in enumerate(chunks):
        source_text = chunk["text"]
        sentences = split_sentences(source_text)

        for index, sentence in enumerate(sentences):
            if len(sentence) < 25 or not name_is_mentioned(name, sentence):
                continue
            if is_question_or_heading(sentence):
                continue
            if is_truncated_final_sentence(source_text, sentence, index, sentences):
                continue

            if is_probable_metadata_sentence(sentence):
                if entity_type in {"author", "organization"}:
                    score = min(len(sentence), 360) // 40
                    metadata_fallbacks.append((score, -chunk_order, sentence, chunk))
                continue

            score = 0
            if 55 <= len(sentence) <= 360:
                score += 3
            elif len(sentence) > 600:
                score -= 2

            if re.search(
                r"\b(is|are|was|were|uses|used|proposes|proposed|develops|developed|"
                r"implements|implemented|evaluates|evaluated|consists|integrates|"
                r"enables|provides|addresses|demonstrates|shows|reports)\b",
                sentence,
                re.I,
            ):
                score += 2
            if re.search(r"[.!?]$", sentence):
                score += 1
            if re.match(r"^(this paper|in this paper|the authors|keywords|abstract)\b", sentence, re.I):
                score -= 2

            candidates.append((score, -chunk_order, sentence, chunk))

    if candidates:
        _, _, quote, chunk = max(
            candidates,
            key=lambda item: (item[0], item[1], -len(item[2])),
        )
        return quote[:700], chunk

    if metadata_fallbacks:
        _, _, quote, chunk = max(
            metadata_fallbacks,
            key=lambda item: (item[0], item[1]),
        )
        match = re.search(re.escape(normalize_text(name)), quote, flags=re.I)
        if match:
            start = match.start()
            end = min(len(quote), start + 260)
            compact = quote[start:end].strip()
            email_pos = re.search(
                r"\b(?:corresponding author|author email|email:)\b",
                compact,
                flags=re.I,
            )
            if email_pos and email_pos.start() > 20:
                compact = compact[:email_pos.start()].rstrip(" ,;:*")
            quote = compact
        return quote[:300], chunk

    return None


def _mention_span(name: str, sentence: str) -> Optional[Tuple[int, int]]:
    """Return a real span in source text; never fabricate normalized offsets."""
    name = normalize_text(name)
    if not name:
        return None

    pattern = re.escape(name).replace(r"\ ", r"\s+")
    match = re.search(r"(?<!\w)" + pattern + r"(?!\w)", sentence, flags=re.I)
    if match:
        return match.span()

    if canonical_name(name) == "bert":
        match = re.search(
            r"(?<![\w])bert(?:[-‐‑‒–— ]?based)?(?![\w])",
            sentence,
            flags=re.I,
        )
        if match:
            return match.span()

    return None


def _cue_match(sentence: str, relation: str) -> Optional[re.Match[str]]:
    cues = sorted(RELATION_CUES.get(relation, ()), key=len, reverse=True)
    if not cues:
        return None
    pattern = r"(?<!\w)(?:" + "|".join(re.escape(c) for c in cues) + r")(?!\w)"
    return re.search(pattern, sentence, flags=re.I)


def _is_negated_near(sentence: str, cue_start: int, cue_end: int) -> bool:
    low = sentence.casefold()
    window = low[max(0, cue_start - 65):min(len(low), cue_end + 65)]

    for neg in NEGATION_PATTERNS:
        if neg in window:
            if "not only" in window and neg in {"does not", "do not", "did not"}:
                continue
            return True
    return False


def _direction_supported(
    sentence: str,
    source_name: str,
    target_name: str,
    relation: str,
    cue: re.Match[str],
) -> bool:
    """Validate edge orientation for common active/passive constructions.

    Edge semantics are source -> target. For *_by relationships, target is the
    agent/creator and source is the artifact or method being described.
    """
    sm_span = _mention_span(source_name, sentence)
    tm_span = _mention_span(target_name, sentence)
    if not sm_span or not tm_span:
        return False

    s0, s1 = sm_span
    t0, t1 = tm_span
    c0, c1 = cue.span()

    if relation == "compares_with":
        return True

    if relation in {"authored_by", "developed_by", "introduced_by"}:
        passive = re.search(
            r"\b(?:authored|written|co-authored|developed|created|built|implemented|"
            r"designed|introduced|proposed|presented)\s+by\b",
            sentence,
            re.I,
        )
        if passive and s0 < passive.start() and t0 > passive.end():
            return True

        active_verb = re.search(
            r"\b(?:authored|wrote|co-authored|developed|created|built|implemented|"
            r"designed|introduced|proposed|presented)\b",
            sentence,
            re.I,
        )
        if active_verb and t0 < active_verb.start() and s0 >= active_verb.end():
            return True

        if relation == "authored_by" and re.search(r"\bauthors include\b", sentence, re.I):
            return t0 > cue.start()
        return False

    if relation in {
        "uses", "evaluated_on", "discusses", "reports", "based_on", "addresses",
        "measures", "implements", "extends", "improves", "proposed", "designs",
    }:
        if s0 < c0 and t0 >= c1:
            return True

        passive_by = re.search(
            r"\b(?:improved|implemented|measured|reported|evaluated|assessed|"
            r"addressed|extended|proposed|used|leveraged|employed|adopted|applied)\s+by\b",
            sentence,
            re.I,
        )
        if passive_by and relation in {
            "uses", "improves", "implements", "measures", "reports",
            "evaluated_on", "addresses", "extends", "proposed",
        }:
            return t0 < passive_by.start() and s0 > passive_by.end()

        if relation == "evaluated_on":
            eval_phrase = re.search(
                r"\b(?:used|employed|adopted)\s+to\s+(?:evaluate|test|assess|benchmark)\b",
                sentence,
                re.I,
            )
            if eval_phrase:
                return s0 > eval_phrase.end() and t0 < eval_phrase.start()
        return False

    # Explicit construction: "Due to limited resources, X ..." means X has
    # the stated limitation. Do not allow arbitrary reverse-order endpoint pairs.
    if relation == "has_limitation":
        due_to = re.search(r"\bdue to\s+", sentence, re.I)
        if due_to and t0 >= due_to.end() and s0 > t1:
            return True

    if relation in {"has_finding", "has_limitation", "has_future_work"}:
        return s0 < c0 and t0 >= c1

    return s0 < c0 and t0 >= c1


def find_supporting_sentence(
    source_name: str,
    target_name: str,
    relation: str,
    chunks: List[Dict[str, Any]],
) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Require endpoints and predicate to be supported in one sentence.

    Two-sentence windows caused predicate leakage: a verb about one target in
    sentence N could incorrectly validate a different target in sentence N+1.
    Quotes are copied directly from the owning retrieved chunk.
    """
    for chunk in chunks:
        source_text = chunk["text"]
        sentences = split_sentences(source_text)

        for index, sentence in enumerate(sentences):
            if is_question_or_heading(sentence) or is_probable_metadata_sentence(sentence):
                continue
            if is_truncated_final_sentence(source_text, sentence, index, sentences):
                continue
            if len(sentence) < MIN_RELATION_EVIDENCE_CHARS or len(sentence) > 900:
                continue
            if not name_is_mentioned(source_name, sentence) or not name_is_mentioned(target_name, sentence):
                continue

            cue = _cue_match(sentence, relation)
            if not cue or _is_negated_near(sentence, *cue.span()):
                continue
            if not _direction_supported(sentence, source_name, target_name, relation, cue):
                continue

            return sentence, chunk

    return None


def diagnose_relationship_candidate(
    source_name: str,
    target_name: str,
    relation: str,
    chunks: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Explain a rejection without changing the acceptance validator."""
    partial_passage = ""
    partial_chunk: Optional[Dict[str, Any]] = None
    partial_score = -1
    saw_both_endpoints = False
    saw_cue = False
    saw_negation = False
    saw_direction_failure = False
    saw_question_or_metadata = False
    saw_short_or_truncated = False

    for chunk in chunks:
        source_text = chunk.get("text", "")
        sentences = split_sentences(source_text)

        for index, sentence in enumerate(sentences):
            if is_question_or_heading(sentence) or is_probable_metadata_sentence(sentence):
                saw_question_or_metadata = True
                continue
            if is_truncated_final_sentence(source_text, sentence, index, sentences):
                saw_short_or_truncated = True
                continue
            if not sentence or len(sentence) > 900 or len(sentence) < MIN_RELATION_EVIDENCE_CHARS:
                saw_short_or_truncated = True
                continue

            src_present = name_is_mentioned(source_name, sentence)
            tgt_present = name_is_mentioned(target_name, sentence)
            if not (src_present and tgt_present):
                score = int(src_present) + int(tgt_present)
                if score > partial_score:
                    partial_passage, partial_chunk, partial_score = sentence, chunk, score
                continue

            saw_both_endpoints = True
            cue = _cue_match(sentence, relation)
            if not cue:
                return {
                    "reason": "explicit_relationship_cue_not_found_in_same_sentence",
                    "evidence": normalize_text(sentence)[:900],
                    "chunk_index": chunk.get("chunk_index"),
                    "chunk_id": chunk.get("id"),
                }

            saw_cue = True
            if _is_negated_near(sentence, *cue.span()):
                saw_negation = True
                return {
                    "reason": "negated_relationship_claim",
                    "evidence": normalize_text(sentence)[:900],
                    "chunk_index": chunk.get("chunk_index"),
                    "chunk_id": chunk.get("id"),
                }

            if not _direction_supported(sentence, source_name, target_name, relation, cue):
                saw_direction_failure = True
                return {
                    "reason": "relationship_direction_not_supported",
                    "evidence": normalize_text(sentence)[:900],
                    "chunk_index": chunk.get("chunk_index"),
                    "chunk_id": chunk.get("id"),
                }

    if not saw_both_endpoints:
        reason = "endpoint_missing_from_same_sentence"
    elif saw_direction_failure:
        reason = "relationship_direction_not_supported"
    elif saw_negation:
        reason = "negated_relationship_claim"
    elif not saw_cue:
        reason = "explicit_relationship_cue_not_found_in_same_sentence"
    elif saw_question_or_metadata:
        reason = "only_question_heading_or_metadata_evidence_found"
    elif saw_short_or_truncated:
        reason = "insufficient_or_truncated_evidence"
    else:
        reason = "evidence_did_not_pass_all_validation_checks"

    return {
        "reason": reason,
        "evidence": normalize_text(partial_passage)[:900],
        "chunk_index": (partial_chunk or {}).get("chunk_index"),
        "chunk_id": (partial_chunk or {}).get("id"),
    }


def is_quota_exhausted(exc: Exception) -> bool:
    message = str(exc).casefold()
    return any(
        x in message
        for x in (
            "resource_exhausted", "quota exceeded", "quota_exceeded",
            "rate limit", "429", "too many requests",
        )
    )


def get_paper_metadata(resource_id: str) -> Optional[Dict[str, Any]]:
    resource_id = str(resource_id)
    for query in (
        {"_id": resource_id},
        {"resource_id": resource_id},
        {"paper_id": resource_id},
        {"id": resource_id},
    ):
        try:
            paper = papers_collection.find_one(query)
        except Exception:
            paper = None
        if paper:
            return _paper_record(resource_id, paper)

    try:
        from bson import ObjectId
        if ObjectId.is_valid(resource_id):
            paper = papers_collection.find_one({"_id": ObjectId(resource_id)})
            if paper:
                return _paper_record(resource_id, paper)
    except Exception:
        logger.debug("ObjectId paper lookup failed", exc_info=True)

    return None


def _paper_record(resource_id: str, paper: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "resource_id": resource_id,
        "title": normalize_text(
            paper.get("title")
            or paper.get("filename")
            or paper.get("original_filename")
            or "Untitled paper"
        ),
        "status": normalize_text(paper.get("status") or "ready").lower(),
        "metadata": paper,
    }


RETRIEVAL_CATEGORIES = [
    ("abstract", "abstract introduction research objective"),
    ("problem", "research problem challenge motivation gap"),
    ("method", "method methodology algorithm approach architecture"),
    ("model", "model framework proposed system technique"),
    ("dataset", "dataset corpus benchmark data source"),
    ("evaluation", "experimental setup evaluation protocol"),
    ("metrics", "evaluation metrics performance measures"),
    ("results", "experimental results findings outcomes"),
    ("concepts", "key concepts definitions theoretical background"),
    ("tools", "software tools libraries implementation"),
    ("limitations", "limitations weaknesses threats to validity"),
    ("future_work", "future work open problems further research"),
    ("comparison", "comparison baseline competing methods"),
    ("conclusion", "conclusion main contributions"),
]


def extract_chunk_text(chunk: Dict[str, Any]) -> str:
    for key in ("text", "content", "chunk_text", "page_content", "document"):
        value = chunk.get(key)
        if isinstance(value, str) and value.strip():
            return normalize_source_text(value)

    for container_key in ("metadata", "payload"):
        container = chunk.get(container_key)
        if isinstance(container, dict):
            for key in ("text", "content", "chunk_text", "page_content"):
                value = container.get(key)
                if isinstance(value, str) and value.strip():
                    return normalize_source_text(value)

    return ""
def extract_chunk_owner(chunk: Dict[str, Any]) -> str:
    for container in (chunk, chunk.get("metadata"), chunk.get("payload")):
        if isinstance(container, dict):
            for key in ("resource_id", "paper_id", "document_id", "source_id"):
                value = container.get(key)
                if value is not None and str(value).strip():
                    return str(value)
    return ""


def extract_chunk_index(chunk: Dict[str, Any], fallback: int) -> int:
    for container in (chunk, chunk.get("metadata"), chunk.get("payload")):
        if isinstance(container, dict):
            for key in ("chunk_index", "index", "chunk_id"):
                value = container.get(key)
                try:
                    if value is not None:
                        return int(value)
                except (TypeError, ValueError):
                    pass
    return fallback


def retrieve_paper_chunks(
    resource_id: str,
    title: str,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Retrieve evidence only from the requested paper and diversify coverage."""
    collected: List[Dict[str, Any]] = []
    errors: List[str] = []
    seen: Set[str] = set()

    for category, query in RETRIEVAL_CATEGORIES:
        try:
            results = search_paper_chunks(
                query=f"{title} {query}",
                paper_ids=[str(resource_id)],
                limit=RETRIEVAL_LIMIT,
            ) or []
        except Exception as exc:
            errors.append(f"{category}: {type(exc).__name__}: {str(exc)[:240]}")
            continue

        for raw in results:
            if not isinstance(raw, dict):
                continue

            owner = extract_chunk_owner(raw)
            if owner and owner != str(resource_id):
                continue

            text = extract_chunk_text(raw)
            if len(text) < 35 or is_reference_heavy(text):
                continue

            fingerprint = hashlib.sha256(
                normalized_match_text(text).encode()
            ).hexdigest()
            if fingerprint in seen:
                continue

            seen.add(fingerprint)
            collected.append({
                "resource_id": str(resource_id),
                "paper_title": title,
                "chunk_index": extract_chunk_index(raw, len(collected)),
                "text": text[:MAX_CHUNK_CHARS],
                "category": category,
                "retrieval_score": raw.get("score"),
            })

    # First try to include one chunk per retrieval category. Then fill any
    # remaining capacity with additional unique chunks from the same paper.
    selected: List[Dict[str, Any]] = []
    selected_fingerprints: Set[str] = set()

    for category, _ in RETRIEVAL_CATEGORIES:
        chunk = next(
            (
                c for c in collected
                if c["category"] == category
                and hashlib.sha256(
                    normalized_match_text(c["text"]).encode()
                ).hexdigest() not in selected_fingerprints
            ),
            None,
        )
        if chunk:
            selected.append(chunk)
            selected_fingerprints.add(
                hashlib.sha256(
                    normalized_match_text(chunk["text"]).encode()
                ).hexdigest()
            )
        if len(selected) >= MAX_CHUNKS_PER_PAPER:
            break

    for chunk in collected:
        fingerprint = hashlib.sha256(
            normalized_match_text(chunk["text"]).encode()
        ).hexdigest()
        if fingerprint not in selected_fingerprints:
            selected.append(chunk)
            selected_fingerprints.add(fingerprint)
        if len(selected) >= MAX_CHUNKS_PER_PAPER:
            break

    return selected, errors


def create_graph_transformer():
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is missing. Configure it in the backend environment."
        )

    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_experimental.graph_transformers import LLMGraphTransformer
    except ImportError as exc:
        raise RuntimeError(
            "Knowledge graph dependencies are missing. Install langchain-core, "
            "langchain-experimental, and langchain-google-genai."
        ) from exc

    llm = ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        google_api_key=GEMINI_API_KEY,
        temperature=0,
        max_retries=0,
    )

    return LLMGraphTransformer(
        llm=llm,
        allowed_nodes=[
            "Author", "Method", "Dataset", "Metric", "Concept", "Finding",
            "Limitation", "FutureWork", "Problem", "Organization", "Tool", "Model",
        ],
        allowed_relationships=[x.upper() for x in RELATIONSHIP_TYPES],
        strict_mode=False,
        node_properties=True,
        relationship_properties=True,
        additional_instructions=ADDITIONAL_INSTRUCTIONS,
    )


def make_batches(
    chunks: List[Dict[str, Any]],
    batch_size: int = MAX_CHUNKS_PER_BATCH,
) -> List[List[Dict[str, Any]]]:
    return [
        chunks[i:i + batch_size]
        for i in range(0, len(chunks), batch_size)
    ]


def batch_to_document_text(batch: List[Dict[str, Any]]) -> str:
    return "\n\n".join(
        f"[SOURCE CHUNK {chunk['chunk_index']}]\n{chunk['text']}"
        for chunk in batch
    )


def extract_graph_for_chunks(
    transformer: Any,
    chunks: List[Dict[str, Any]],
    paper: Dict[str, Any],
) -> Dict[str, Any]:
    try:
        from langchain_core.documents import Document
    except ImportError as exc:
        raise RuntimeError(
            "langchain-core is required for graph extraction."
        ) from exc

    result: Dict[str, Any] = {
        "entities": [],
        "relationships": [],
        "entity_candidates": 0,
        "relationship_candidates": 0,
        "extraction_errors": [],
        "quota_exhausted": False,
        "rejected_relationships": Counter(),
        "rejected_entities": Counter(),
        "rejected_candidate_report": [],
    }

    batches = make_batches(chunks)

    for batch_number, batch in enumerate(batches, start=1):
        document = Document(
            page_content=batch_to_document_text(batch),
            metadata={
                "resource_id": paper["resource_id"],
                "paper_title": paper["title"],
                "batch_number": batch_number,
            },
        )

        try:
            graph_documents = transformer.convert_to_graph_documents([document])
        except Exception as exc:
            result["extraction_errors"].append(
                f"Batch {batch_number}: {type(exc).__name__}: {str(exc)[:500]}"
            )
            if is_quota_exhausted(exc):
                result["quota_exhausted"] = True
                result["extraction_errors"].append(
                    "Extraction stopped to avoid repeated quota failures."
                )
                break
            continue

        for graph_document in graph_documents or []:
            nodes = getattr(graph_document, "nodes", []) or []
            relationships = getattr(graph_document, "relationships", []) or []

            result["entity_candidates"] += len(nodes)
            result["relationship_candidates"] += len(relationships)

            for node in nodes:
                props = get_properties(node)
                name = clean_entity_name(
                    getattr(node, "id", None)
                    or property_value(props, "name", "label")
                )
                if not name:
                    result["rejected_entities"]["invalid_name"] += 1
                    continue

                entity_type = infer_entity_type(name, getattr(node, "type", None))
                evidence = find_entity_evidence(name, batch, entity_type)
                if evidence is None:
                    result["rejected_entities"]["entity_without_evidence"] += 1
                    continue

                quote, chunk = evidence
                result["entities"].append({
                    "name": name,
                    "canonical_name": canonical_name(name),
                    "type": entity_type,
                    "resource_id": paper["resource_id"],
                    "paper_title": paper["title"],
                    "chunk_index": chunk["chunk_index"],
                    "quote": quote,
                })

            for relationship in relationships:
                source_obj = getattr(relationship, "source", None)
                target_obj = getattr(relationship, "target", None)
                source_name = clean_entity_name(getattr(source_obj, "id", ""))
                target_name = clean_entity_name(getattr(target_obj, "id", ""))
                relation_type = normalize_relation_type(
                    getattr(relationship, "type", "")
                )

                if not source_name or not target_name or not relation_type:
                    reason = "relationship_missing_endpoint_or_type"
                    result["rejected_relationships"][reason] += 1
                    result["rejected_candidate_report"].append({
                        "source_entity": source_name or None,
                        "proposed_relation": (
                            relation_type
                            or normalize_text(getattr(relationship, "type", ""))
                            or None
                        ),
                        "target_entity": target_name or None,
                        "evidence_passage": "",
                        "rejection_reason": reason,
                        "resource_id": paper["resource_id"],
                        "paper_title": paper["title"],
                        "batch_number": batch_number,
                    })
                    continue

                if canonical_name(source_name) == canonical_name(target_name):
                    reason = "self_relationship_after_normalization"
                    result["rejected_relationships"][reason] += 1
                    result["rejected_candidate_report"].append({
                        "source_entity": source_name,
                        "proposed_relation": relation_type,
                        "target_entity": target_name,
                        "evidence_passage": "",
                        "rejection_reason": reason,
                        "resource_id": paper["resource_id"],
                        "paper_title": paper["title"],
                        "batch_number": batch_number,
                    })
                    continue

                support = find_supporting_sentence(
                    source_name,
                    target_name,
                    relation_type,
                    batch,
                )

                if support is None:
                    diagnostic = diagnose_relationship_candidate(
                        source_name,
                        target_name,
                        relation_type,
                        batch,
                    )
                    reason = diagnostic["reason"]
                    result["rejected_relationships"][reason] += 1
                    result["rejected_candidate_report"].append({
                        "source_entity": source_name,
                        "proposed_relation": relation_type,
                        "target_entity": target_name,
                        "evidence_passage": diagnostic["evidence"],
                        "rejection_reason": reason,
                        "resource_id": paper["resource_id"],
                        "paper_title": paper["title"],
                        "chunk_index": diagnostic["chunk_index"],
                        "chunk_id": diagnostic["chunk_id"],
                        "batch_number": batch_number,
                    })
                    continue

                quote, chunk = support
                result["relationships"].append({
                    "source_name": source_name,
                    "source_canonical": canonical_name(source_name),
                    "target_name": target_name,
                    "target_canonical": canonical_name(target_name),
                    "relationship": relation_type,
                    "resource_id": paper["resource_id"],
                    "paper_title": paper["title"],
                    "chunk_index": chunk["chunk_index"],
                    "quote": quote,
                })

        if batch_number < len(batches):
            time.sleep(0.15)

    return result


TYPE_PRIORITY = {
    "author": 12,
    "organization": 11,
    "dataset": 10,
    "metric": 9,
    "tool": 8,
    "model": 7,
    "method": 6,
    "problem": 5,
    "limitation": 4,
    "future_work": 4,
    "finding": 3,
    "concept": 2,
}


def merge_evidence(
    existing: List[Dict[str, Any]],
    incoming: Dict[str, Any],
    limit: int,
) -> List[Dict[str, Any]]:
    signature = (
        incoming.get("resource_id"),
        incoming.get("chunk_index"),
        normalized_match_text(incoming.get("quote", "")),
    )
    if any(
        (
            item.get("resource_id"),
            item.get("chunk_index"),
            normalized_match_text(item.get("quote", "")),
        ) == signature
        for item in existing
    ):
        return existing
    if len(existing) < limit:
        existing.append(incoming)
    return existing
def build_graph(
    extracted_entities: List[Dict[str, Any]],
    extracted_relationships: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    """Merge verified entities and edges without inventing cross-paper relations."""
    groups: Dict[str, Dict[str, Any]] = {}
    type_votes: Dict[str, Counter] = {}
    display_votes: Dict[str, Counter] = {}

    for entity in extracted_entities:
        key = entity.get("canonical_name") or canonical_name(entity.get("name", ""))
        if not key:
            continue

        if key not in groups:
            groups[key] = {
                "names": [],
                "evidence": [],
                "resource_ids": set(),
                "paper_titles": set(),
            }
            type_votes[key] = Counter()
            display_votes[key] = Counter()

        group = groups[key]
        name = entity["name"]
        display_votes[key][name] += 1
        type_votes[key][entity["type"]] += 1

        if name not in group["names"]:
            group["names"].append(name)

        group["resource_ids"].add(entity["resource_id"])
        group["paper_titles"].add(entity["paper_title"])
        group["evidence"] = merge_evidence(
            group["evidence"],
            {
                "resource_id": entity["resource_id"],
                "paper_title": entity["paper_title"],
                "chunk_index": entity["chunk_index"],
                "quote": entity["quote"],
            },
            MAX_EVIDENCE_PER_NODE,
        )

    key_to_id: Dict[str, str] = {}
    nodes: List[Dict[str, Any]] = []

    for key, group in groups.items():
        if not group["evidence"]:
            continue

        selected_type = sorted(
            type_votes[key].items(),
            key=lambda item: (
                item[1],
                TYPE_PRIORITY.get(item[0], 0),
            ),
            reverse=True,
        )[0][0]

        display_name = sorted(
            display_votes[key].items(),
            key=lambda item: (item[1], len(item[0])),
            reverse=True,
        )[0][0]

        node_id = stable_id("entity", key)
        key_to_id[key] = node_id

        nodes.append({
            "id": node_id,
            "type": "default",
            "position": {"x": 0, "y": 0},
            "data": {
                "label": display_name,
                "name": display_name,
                "type": selected_type,
                "source_resource_ids": sorted(group["resource_ids"]),
                "source_papers": sorted(group["paper_titles"]),
                "evidence": group["evidence"],
                "aliases": sorted(
                    name for name in group["names"] if name != display_name
                ),
            },
        })

    edge_groups: Dict[Tuple[str, str, str], Dict[str, Any]] = {}

    for relationship in extracted_relationships:
        source_key = relationship["source_canonical"]
        target_key = relationship["target_canonical"]
        relation_type = relationship["relationship"]

        source_id = key_to_id.get(source_key)
        target_id = key_to_id.get(target_key)

        if not source_id or not target_id or source_id == target_id:
            continue

        edge_key = (source_key, relation_type, target_key)

        if edge_key not in edge_groups:
            edge_groups[edge_key] = {
                "source": source_id,
                "target": target_id,
                "relationship": relation_type,
                "resource_ids": set(),
                "paper_titles": set(),
                "evidence": [],
            }

        group = edge_groups[edge_key]
        group["resource_ids"].add(relationship["resource_id"])
        group["paper_titles"].add(relationship["paper_title"])
        group["evidence"] = merge_evidence(
            group["evidence"],
            {
                "resource_id": relationship["resource_id"],
                "paper_title": relationship["paper_title"],
                "chunk_index": relationship["chunk_index"],
                "quote": relationship["quote"],
            },
            MAX_EVIDENCE_PER_EDGE,
        )

    labels = {
        "authored_by": "authored by",
        "developed_by": "developed by",
        "introduced_by": "introduced by",
        "uses": "uses",
        "proposed": "proposed",
        "evaluated_on": "evaluated on",
        "discusses": "discusses",
        "reports": "reports",
        "based_on": "based on",
        "addresses": "addresses",
        "measures": "measures",
        "implements": "implements",
        "extends": "extends",
        "improves": "improves",
        "compares_with": "compares with",
        "has_finding": "has finding",
        "has_limitation": "has limitation",
        "has_future_work": "has future work",
        "designs": "designs",
    }

    edges: List[Dict[str, Any]] = []

    for key, group in edge_groups.items():
        if not group["evidence"]:
            continue

        relation_type = group["relationship"]
        edges.append({
            "id": stable_id("edge", "|".join(key)),
            "source": group["source"],
            "target": group["target"],
            "label": labels.get(relation_type, relation_type.replace("_", " ")),
            "type": "default",
            "data": {
                "relationship": relation_type,
                "source_papers": sorted(group["paper_titles"]),
                "source_resource_ids": sorted(group["resource_ids"]),
                "evidence": group["evidence"],
            },
            "animated": False,
        })

    if len(nodes) > MAX_ENTITIES:
        nodes.sort(
            key=lambda node: (
                len(node["data"]["source_resource_ids"]),
                len(node["data"]["evidence"]),
            ),
            reverse=True,
        )
        nodes = nodes[:MAX_ENTITIES]

    retained_ids = {node["id"] for node in nodes}
    edges = [
        edge for edge in edges
        if edge["source"] in retained_ids and edge["target"] in retained_ids
    ][:MAX_RELATIONSHIPS]

    assign_layout(nodes, edges)

    return nodes, edges, {
        "merged_entity_groups": len(groups),
        "accepted_entity_groups": len(nodes),
        "accepted_relationship_groups": len(edges),
    }


def assign_layout(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
) -> None:
    """Assign deterministic initial positions; preserve the existing UI contract."""
    count = len(nodes)
    if not count:
        return

    radius = max(320, int(count * 12))
    for index, node in enumerate(nodes):
        angle = (2 * math.pi * index / count) - (math.pi / 2)
        node["position"] = {
            "x": int(radius * math.cos(angle)),
            "y": int(radius * math.sin(angle)),
        }


def _empty_statistics(selected: int, rejected: int = 0) -> Dict[str, Any]:
    return {
        "selected_papers": selected,
        "available_papers": 0,
        "rejected_papers": rejected,
        "retrieved_chunks": 0,
        "entity_candidates": 0,
        "relationship_candidates": 0,
        "entities": 0,
        "relationships": 0,
        "semantic_relationships": 0,
        "evidence_validated_relationships": 0,
        "cross_paper_relationships": 0,
        "repeated_relationships_across_papers": 0,
        "entity_types": {},
        "relationship_types": {},
        "rejected_relationships": {},
        "rejected_entities": {},
        "extraction_error_count": 0,
        "retrieval_error_count": 0,
        "quota_exhausted": False,
    }


def generate_knowledge_graph(resource_ids: List[str]) -> Dict[str, Any]:
    """Generate a graph for selected workspace papers, preserving the API contract."""
    if not resource_ids:
        raise HTTPException(
            status_code=400,
            detail="Select at least one paper to generate a knowledge graph.",
        )

    requested_ids = list(dict.fromkeys(
        str(value) for value in resource_ids if str(value).strip()
    ))

    selected_papers: List[Dict[str, Any]] = []
    rejected_papers: List[Dict[str, Any]] = []

    for resource_id in requested_ids:
        paper = get_paper_metadata(resource_id)

        if not paper:
            rejected_papers.append({
                "resource_id": resource_id,
                "reason": "Paper not found in the current workspace.",
            })
            continue

        status = paper["status"]
        if status in {
            "deleted", "unavailable", "missing", "error", "failed",
            "processing", "removed",
        }:
            rejected_papers.append({
                "resource_id": resource_id,
                "title": paper["title"],
                "reason": (
                    "Paper is not available for graph extraction "
                    f"(status: {status})."
                ),
            })
            continue

        selected_papers.append(paper)

    if not selected_papers:
        return {
            "nodes": [],
            "edges": [],
            "statistics": _empty_statistics(
                len(requested_ids),
                len(rejected_papers),
            ),
            "papers": [],
            "meta": {
                "rejected_papers": rejected_papers,
                "rejected_candidate_report": [],
                "rejected_candidate_report_total": 0,
                "rejected_candidate_report_truncated": False,
                "validation": {
                    "evidence_required": True,
                    "cross_paper_inference_enabled": False,
                },
            },
        }

    paper_chunks: Dict[str, List[Dict[str, Any]]] = {}
    paper_retrieval_errors: Dict[str, List[str]] = {}

    for paper in selected_papers:
        chunks, errors = retrieve_paper_chunks(
            paper["resource_id"],
            paper["title"],
        )
        paper_chunks[paper["resource_id"]] = chunks
        paper_retrieval_errors[paper["resource_id"]] = errors

    papers_with_chunks = [
        paper for paper in selected_papers
        if paper_chunks.get(paper["resource_id"])
    ]

    transformer = None
    if papers_with_chunks:
        try:
            transformer = create_graph_transformer()
        except Exception as exc:
            logger.exception("Could not initialize SciBrain graph transformer")
            raise HTTPException(
                status_code=503,
                detail=(
                    "Knowledge graph engine could not be initialized. "
                    f"{type(exc).__name__}: {str(exc)[:300]}"
                ),
            ) from exc

    all_entities: List[Dict[str, Any]] = []
    all_relationships: List[Dict[str, Any]] = []
    paper_diagnostics: List[Dict[str, Any]] = []

    entity_candidates = 0
    relationship_candidates = 0
    rejected_relationships: Counter = Counter()
    rejected_entities: Counter = Counter()
    rejected_candidate_report: List[Dict[str, Any]] = []

    extraction_error_count = 0
    retrieval_error_count = sum(
        len(errors) for errors in paper_retrieval_errors.values()
    )
    quota_exhausted = False

    for paper in selected_papers:
        resource_id = paper["resource_id"]
        chunks = paper_chunks.get(resource_id, [])
        retrieval_errors = paper_retrieval_errors.get(resource_id, [])

        if not chunks:
            extraction = {
                "entities": [],
                "relationships": [],
                "entity_candidates": 0,
                "relationship_candidates": 0,
                "extraction_errors": [],
                "quota_exhausted": False,
                "rejected_relationships": Counter(),
                "rejected_entities": Counter(),
                "rejected_candidate_report": [],
            }
            availability_note = (
                "No usable indexed text chunks were retrieved for this selected paper."
            )
        elif quota_exhausted:
            extraction = {
                "entities": [],
                "relationships": [],
                "entity_candidates": 0,
                "relationship_candidates": 0,
                "extraction_errors": [
                    "Skipped because a previous paper exhausted the Gemini quota."
                ],
                "quota_exhausted": True,
                "rejected_relationships": Counter(),
                "rejected_entities": Counter(),
                "rejected_candidate_report": [],
            }
            availability_note = None
        else:
            extraction = extract_graph_for_chunks(transformer, chunks, paper)
            availability_note = None

        quota_exhausted = quota_exhausted or extraction["quota_exhausted"]
        all_entities.extend(extraction["entities"])
        all_relationships.extend(extraction["relationships"])

        entity_candidates += extraction["entity_candidates"]
        relationship_candidates += extraction["relationship_candidates"]

        rejected_relationships.update(extraction["rejected_relationships"])
        rejected_entities.update(extraction["rejected_entities"])
        rejected_candidate_report.extend(
            extraction.get("rejected_candidate_report", [])
        )
        extraction_error_count += len(extraction["extraction_errors"])

        diagnostic = {
            "resource_id": resource_id,
            "title": paper["title"],
            "retrieved_chunks": len(chunks),
            "selected_chunks": len(chunks),
            "entities_extracted": len(extraction["entities"]),
            "relationships_extracted": len(extraction["relationships"]),
            "extraction_errors": extraction["extraction_errors"],
            "retrieval_errors": retrieval_errors,
            "quota_exhausted": extraction["quota_exhausted"],
            "relationship_diagnostics": {
                "candidate_relationships": extraction["relationship_candidates"],
                "accepted_relationship_candidates": len(extraction["relationships"]),
                "accepted_relationships_in_final_graph": 0,
                "evidence_required": True,
                "cross_paper_inference_enabled": False,
                "rejected_candidates": dict(extraction["rejected_relationships"]),
                "rejected_candidate_report": extraction.get(
                    "rejected_candidate_report", []
                ),
            },
        }

        if availability_note:
            diagnostic["availability_note"] = availability_note

        paper_diagnostics.append(diagnostic)

    nodes, edges, graph_diagnostics = build_graph(
        all_entities,
        all_relationships,
    )
    accepted_relationship_candidates = len(all_relationships)

    for diagnostic in paper_diagnostics:
        resource_id = diagnostic["resource_id"]
        diagnostic["relationship_diagnostics"][
            "accepted_relationships_in_final_graph"
        ] = sum(
            1
            for edge in edges
            if resource_id in edge.get("data", {}).get("source_resource_ids", [])
        )

    entity_type_counts = Counter(node["data"]["type"] for node in nodes)
    relation_type_counts = Counter(
        edge["data"]["relationship"] for edge in edges
    )
    repeated_relationships = sum(
        1 for edge in edges
        if len(edge["data"]["source_resource_ids"]) > 1
    )

    statistics = {
        "selected_papers": len(requested_ids),
        "available_papers": len(papers_with_chunks),
        "rejected_papers": len(rejected_papers),
        "retrieved_chunks": sum(len(chunks) for chunks in paper_chunks.values()),
        "entity_candidates": entity_candidates,
        "relationship_candidates": relationship_candidates,
        "accepted_relationship_candidates": accepted_relationship_candidates,
        "entities": len(nodes),
        "relationships": len(edges),
        "semantic_relationships": len(edges),
        "evidence_validated_relationships": len(edges),
        "unique_relationship_groups": len(edges),
        "cross_paper_relationships": 0,
        "repeated_relationships_across_papers": repeated_relationships,
        "entity_types": dict(entity_type_counts),
        "relationship_types": dict(relation_type_counts),
        "rejected_relationships": dict(rejected_relationships),
        "rejected_entities": dict(rejected_entities),
        "extraction_error_count": extraction_error_count,
        "retrieval_error_count": retrieval_error_count,
        "quota_exhausted": quota_exhausted,
    }

    return {
        "nodes": nodes,
        "edges": edges,
        "statistics": statistics,
        "papers": paper_diagnostics,
        "meta": {
            "engine": (
                "SciBrain Revision 2.2 — sentence-local validation + rejection diagnostics"
            ),
            "model": GEMINI_MODEL,
            "graph_diagnostics": graph_diagnostics,
            "rejected_papers": rejected_papers,
            "rejected_candidate_report": rejected_candidate_report[:200],
            "rejected_candidate_report_total": len(rejected_candidate_report),
            "rejected_candidate_report_truncated": len(rejected_candidate_report) > 200,
            "validation": {
                "evidence_required": True,
                "entity_mentions_required": True,
                "relationship_endpoints_required": True,
                "explicit_relationship_cue_required": True,
                "relationship_direction_checked": True,
                "negated_relationships_rejected": True,
                "question_based_relationships_rejected": True,
                "reference_only_evidence_rejected": True,
                "cross_paper_inference_enabled": False,
                "shared_entities_merge_across_papers": True,
                "semantic_validation_method": (
                    "Deterministic single-sentence evidence, relation cue, "
                    "active/passive direction and negation checks; not an "
                    "independent semantic reviewer."
                ),
                "diagnostic_policy": (
                    "Rejected candidates are reported with proposed endpoints, "
                    "relation, local evidence, owning paper, and the first "
                    "actionable validation reason. Reporting does not relax "
                    "acceptance rules."
                ),
                "normalization_policy": (
                    "Case/spacing/punctuation normalization preserves parenthetical "
                    "acronyms, Unicode scientific symbols, and official display names. "
                    "BERT-based OCR matching is boundary-safe and does not match "
                    "ColBERT. No acronym expansion or speculative alias merge."
                ),
                "evidence_quote_policy": (
                    "Quotes are selected from the owning retrieved chunk; no fallback "
                    "chunk attribution is permitted."
                ),
                "quota_exhausted": quota_exhausted,
                "partial_results_possible": quota_exhausted,
            },
        },
    }