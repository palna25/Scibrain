"""
SciBrain - Research Paper Analysis Engine

Production-oriented research paper analysis service.

Pipeline:

    MongoDB
       ↓
    Extracted PDF text
       ↓
    PDF text cleaning
       ↓
    Academic section detection
       ↓
    Evidence-focused context construction
       ↓
    Ollama / llama3.2
       ↓
    Structured JSON
       ↓
    Normalization
       ↓
    Evidence-aware cleanup
       ↓
    Deterministic recovery for missing fields
       ↓
    MongoDB
       ↓
    API

Important design rules:

1. Empty optional fields are VALID.
2. A paper must never fail only because limitations/future_work/etc.
   are empty.
3. The LLM must not invent information.
4. Datasets and metrics must come from actual evaluation evidence.
5. Methodology must describe the proposed method, not related work.
6. Techniques must contain actual technical concepts.
7. Baseline methods must not automatically become proposed techniques.
"""

import json
import os
import re
from typing import Any, Dict, List

import requests

from app.database.mongodb import papers_collection


# ============================================================
# CONFIGURATION
# ============================================================

OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://127.0.0.1:11434",
)

OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "llama3.2",
)

OLLAMA_TIMEOUT = int(
    os.getenv("OLLAMA_TIMEOUT", "180")
)

MAX_TOTAL_CONTEXT_CHARS = 50000
MAX_SECTION_CHARS = 10000


# ============================================================
# EXPECTED OUTPUT SCHEMA
# ============================================================

STRING_FIELDS = {
    "summary",
    "problem",
}

LIST_FIELDS = {
    "methodology",
    "datasets",
    "metrics",
    "findings",
    "limitations",
    "future_work",
    "contributions",
    "techniques",
}

EXPECTED_FIELDS = STRING_FIELDS | LIST_FIELDS


# ============================================================
# SECTION ALIASES
# ============================================================

SECTION_ALIASES = {
    "abstract": {
        "abstract",
        "summary",
    },

    "introduction": {
        "introduction",
        "background",
        "motivation",
    },

    "related_work": {
        "related work",
        "related works",
        "literature review",
        "literature survey",
        "prior work",
        "previous work",
    },

    "methodology": {
        "methodology",
        "method",
        "methods",
        "approach",
        "proposed method",
        "proposed approach",
        "proposed model",
        "proposed framework",
        "model",
        "framework",
        "architecture",
        "system architecture",
        "technical approach",
    },

    "experiments": {
        "experiments",
        "experimental setup",
        "experimental evaluation",
        "experimental methodology",
        "experimental design",
        "evaluation",
        "evaluation setup",
    },

    "results": {
        "results",
        "experimental results",
        "results and discussion",
        "findings",
        "performance evaluation",
    },

    "discussion": {
        "discussion",
        "analysis",
        "interpretation",
    },

    "limitations": {
        "limitations",
        "limitations of the study",
        "limitations and future work",
        "limitations and discussion",
    },

    "future_work": {
        "future work",
        "future research",
        "future directions",
        "future studies",
        "conclusion and future work",
    },

    "conclusion": {
        "conclusion",
        "conclusions",
        "concluding remarks",
        "concluding discussion",
    },

    "references": {
        "references",
        "bibliography",
        "reference",
    },
}


# ============================================================
# TEXT CLEANING
# ============================================================

def clean_text(text: str) -> str:
    """
    Clean PDF extraction artifacts while preserving enough structure
    for academic section detection.
    """

    if not text:
        return ""

    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    replacements = {
        "ﬁ": "fi",
        "ﬂ": "fl",
        "ﬀ": "ff",
        "ﬃ": "ffi",
        "ﬄ": "ffl",
        "\u00ad": "",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    # Repair words broken across lines.
    text = re.sub(
        r"([A-Za-z])-\s*\n\s*([a-z])",
        r"\1\2",
        text,
    )

    # Normalize spaces but preserve newlines.
    text = re.sub(
        r"[ \t]+",
        " ",
        text,
    )

    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text,
    )

    return text.strip()


def remove_pdf_noise(text: str) -> str:
    """
    Remove obvious PDF extraction noise.
    """

    if not text:
        return ""

    # URLs.
    text = re.sub(
        r"https?://\S+",
        " ",
        text,
        flags=re.IGNORECASE,
    )

    # Emails.
    text = re.sub(
        r"\b[\w.+-]+@[\w.-]+\.\w+\b",
        " ",
        text,
    )

    # Page-number-only lines.
    text = re.sub(
        r"(?m)^\s*\d+\s*$",
        "",
        text,
    )

    # Normalize excessive spaces.
    text = re.sub(
        r"[ \t]+",
        " ",
        text,
    )

    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text,
    )

    return text.strip()


# ============================================================
# SECTION DETECTION
# ============================================================

def normalize_heading(line: str) -> str:
    """
    Convert academic headings such as:

        1 Introduction
        1. Introduction
        3.2 Proposed Method
        I. INTRODUCTION
        A. Methodology

    into a normalized heading.
    """

    line = line.strip()

    if not line:
        return ""

    # Remove numbered prefixes.
    line = re.sub(
        r"^(?:"
        r"(?:[IVXLCDM]+|[A-Z])"
        r"|"
        r"\d+(?:\.\d+)*"
        r")"
        r"\s*[.)-]?\s+",
        "",
        line,
        flags=re.IGNORECASE,
    )

    line = line.rstrip(" :.-")

    line = re.sub(
        r"\s+",
        " ",
        line,
    )

    return line.lower().strip()


def detect_sections(text: str) -> Dict[str, str]:
    """
    Detect recognized academic sections.

    If headings cannot be detected, the caller still retains the
    complete paper as fallback evidence.
    """

    lines = text.splitlines()

    headings = []

    for index, line in enumerate(lines):

        normalized = normalize_heading(line)

        if not normalized:
            continue

        # Avoid treating long paragraphs as headings.
        if len(normalized) > 80:
            continue

        for section_name, aliases in SECTION_ALIASES.items():

            if normalized in aliases:

                headings.append(
                    (
                        index,
                        section_name,
                    )
                )

                break

    sections: Dict[str, str] = {}

    if not headings:
        return sections

    for position, (start, section_name) in enumerate(headings):

        if position + 1 < len(headings):
            end = headings[position + 1][0]
        else:
            end = len(lines)

        content = "\n".join(
            lines[start + 1:end]
        )

        content = remove_pdf_noise(content)

        if not content:
            continue

        content = content[:MAX_SECTION_CHARS]

        if section_name in sections:
            sections[section_name] += "\n\n" + content
        else:
            sections[section_name] = content

    return sections


def fallback_abstract(text: str) -> str:
    """
    Recover an abstract when heading detection failed.
    """

    if not text:
        return ""

    match = re.search(
        r"\babstract\b",
        text,
        flags=re.IGNORECASE,
    )

    if not match:
        return ""

    remaining = text[match.end():]

    next_heading = re.search(
        r"\b(?:1(?:\.\d*)?\s*)?introduction\b",
        remaining,
        flags=re.IGNORECASE,
    )

    if next_heading:
        abstract = remaining[:next_heading.start()]
    else:
        abstract = remaining[:6000]

    return remove_pdf_noise(
        abstract
    )[:6000]


def build_sections(text: str) -> Dict[str, str]:

    sections = detect_sections(text)

    if not sections.get("abstract"):

        abstract = fallback_abstract(text)

        if abstract:
            sections["abstract"] = abstract

    return sections


# ============================================================
# SECTION TEXT HELPER
# ============================================================

def section_text(
    sections: Dict[str, str],
    names: List[str],
) -> str:

    parts = []

    for name in names:

        value = sections.get(
            name,
            "",
        )

        if value:
            parts.append(value)

    return "\n\n".join(parts)


# ============================================================
# CONTEXT CONSTRUCTION
# ============================================================

def build_context(
    text: str,
    sections: Dict[str, str],
) -> str:
    """
    Build a high-value evidence context.

    The goal is NOT simply to send the first N characters of the PDF.

    Different fields require different evidence.
    """

    blocks = []

    order = [
        "abstract",
        "introduction",
        "methodology",
        "experiments",
        "results",
        "discussion",
        "limitations",
        "future_work",
        "conclusion",
        "related_work",
    ]

    for section_name in order:

        content = sections.get(
            section_name,
            "",
        )

        if not content:
            continue

        content = remove_pdf_noise(content)

        if not content:
            continue

        blocks.append(
            f"\n===== {section_name.upper()} =====\n"
            f"{content[:MAX_SECTION_CHARS]}"
        )

    if blocks:

        context = "\n".join(blocks)

        return context[:MAX_TOTAL_CONTEXT_CHARS]

    # Section detection failed.
    # Preserve the actual paper instead of failing.
    return remove_pdf_noise(text)[
        :MAX_TOTAL_CONTEXT_CHARS
    ]


# ============================================================
# OLLAMA PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are SciBrain, an academic research-paper analysis engine.

Your job is to extract factual research information from a scientific
or technical paper.

The paper may belong to ANY technical domain.

You MUST base every answer on the supplied paper.

NEVER invent a dataset, metric, result, limitation, technique,
contribution, or future-work statement.

============================================================
FIELD DEFINITIONS
============================================================

summary:
Write a concise scientific summary containing:
- research context
- problem
- proposed approach
- evaluation
- major result

problem:
State the specific research problem/gap addressed by the authors.

methodology:
List the meaningful components or steps of the paper's PROPOSED
method.

Good:
- Constructs a multi-behavior user-item interaction graph.
- Learns behavior-specific representations.
- Applies cross-layer mutual relation learning.
- Aggregates high-order behavior representations.

Bad:
- "This section explains the methodology."
- "Technical details."
- copied paragraphs.

datasets:
ONLY datasets/data sources actually used for experiments, training,
validation or testing.

Do NOT include datasets merely mentioned in related work.

metrics:
ONLY evaluation metrics actually reported or used by the paper.

Do NOT include generic words such as "performance" unless it is
explicitly an evaluation metric.

findings:
Report actual experimental or analytical findings.

Good:
- MBRec outperforms the compared baselines.
- The method improves recommendation performance on the evaluated
  datasets.

Do NOT turn research questions, table headings, baseline descriptions,
or section descriptions into findings.

limitations:
ONLY limitations explicitly acknowledged by the authors.

If none are stated:
[]

future_work:
ONLY future work explicitly stated or clearly proposed by the authors.

If none:
[]

contributions:
Extract the paper's claimed contributions.

These normally come from:
- abstract
- introduction
- contribution statements
- conclusion

techniques:
Extract specific technical techniques, algorithms, architectures,
mechanisms, or computational methods actually used by the proposed
approach.

Good:
- Graph Neural Network
- Multi-Behavior Graph Learning
- Attention Mechanism
- Mutual Relation Encoder
- Message Passing
- Graph Sampling

Bad:
- "this framework"
- "this module"
- "technical details"
- "our proposed model"

============================================================
IMPORTANT DISTINCTIONS
============================================================

PROPOSED METHOD:

Identify what THIS PAPER actually proposes.

RELATED WORK:

Do not confuse cited or previous methods with the proposed method.

BASELINES:

A baseline is not automatically a technique of the proposed system.

DATASETS:

A dataset mentioned in background is not necessarily a dataset used
in experiments.

METRICS:

A metric mentioned theoretically is not necessarily an evaluation
metric.

FINDINGS:

Research questions are NOT findings.

============================================================
OUTPUT
============================================================

Return ONLY valid JSON.

Use exactly this structure:

{
  "summary": "",
  "problem": "",
  "methodology": [],
  "datasets": [],
  "metrics": [],
  "findings": [],
  "limitations": [],
  "future_work": [],
  "contributions": [],
  "techniques": []
}

No Markdown.
No code fences.
No explanation outside JSON.
"""


# ============================================================
# OLLAMA CALL
# ============================================================

def call_ollama(
    context: str,
) -> Dict[str, Any]:

    if not context.strip():

        raise ValueError(
            "No meaningful paper text was available for analysis."
        )

    user_prompt = f"""
Analyze the following academic paper for SciBrain.

IMPORTANT:

Use the actual evidence supplied below.

For methodology, focus primarily on the PROPOSED METHOD section.

For datasets and metrics, focus primarily on EXPERIMENTS,
EVALUATION and RESULTS.

For findings, use actual RESULTS, DISCUSSION and CONCLUSION statements.

For limitations and future work, only extract explicit statements.

For contributions, use the paper's contribution statements and
abstract/conclusion.

Do not return research questions as findings.

Do not return baseline models as proposed techniques.

Do not copy large paragraphs.

Be concise but informative.

PAPER EVIDENCE:

{context}
"""

    payload = {
        "model": OLLAMA_MODEL,
        "system": SYSTEM_PROMPT,
        "prompt": user_prompt,
        "format": "json",
        "stream": False,
        "options": {
            "temperature": 0,
            "top_p": 0.1,
        },
    }

    try:

        response = requests.post(
            f"{OLLAMA_URL.rstrip('/')}/api/generate",
            json=payload,
            timeout=OLLAMA_TIMEOUT,
        )

    except requests.RequestException as error:

        raise RuntimeError(
            f"Could not connect to Ollama at "
            f"{OLLAMA_URL}: {error}"
        )

    if response.status_code != 200:

        raise RuntimeError(
            f"Ollama returned HTTP "
            f"{response.status_code}: "
            f"{response.text[:1000]}"
        )

    try:

        data = response.json()

    except ValueError as error:

        raise RuntimeError(
            f"Ollama returned invalid HTTP JSON: {error}"
        )

    raw = data.get(
        "response",
        "",
    )

    if isinstance(raw, dict):
        return raw

    if not isinstance(raw, str):
        return {}

    raw = raw.strip()

    if not raw:
        return {}

    # Remove Markdown fences.
    raw = re.sub(
        r"^```(?:json)?\s*",
        "",
        raw,
        flags=re.IGNORECASE,
    )

    raw = re.sub(
        r"\s*```$",
        "",
        raw,
    )

    # Direct JSON.
    try:

        parsed = json.loads(raw)

        if isinstance(parsed, dict):
            return parsed

    except json.JSONDecodeError:
        pass

    # Recover JSON embedded inside other text.
    start = raw.find("{")
    end = raw.rfind("}")

    if start != -1 and end > start:

        candidate = raw[
            start:end + 1
        ]

        try:

            parsed = json.loads(candidate)

            if isinstance(parsed, dict):
                return parsed

        except json.JSONDecodeError:
            pass

    return {}


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_string(
    value: Any,
) -> str:

    if value is None:
        return ""

    if isinstance(value, list):

        value = " ".join(
            str(item)
            for item in value
        )

    if not isinstance(value, str):
        return ""

    value = re.sub(
        r"\s+",
        " ",
        value,
    ).strip()

    return value[:5000]


def normalize_list(
    value: Any,
) -> List[str]:

    if value is None:
        return []

    if isinstance(value, str):
        value = [value]

    if not isinstance(value, list):
        return []

    result = []

    for item in value:

        if isinstance(item, dict):
            continue

        if not isinstance(item, str):
            continue

        item = re.sub(
            r"\s+",
            " ",
            item,
        ).strip()

        if len(item) < 2:
            continue

        result.append(
            item[:1000]
        )

    # Deduplicate.
    final = []
    seen = set()

    for item in result:

        key = item.lower()

        if key in seen:
            continue

        seen.add(key)
        final.append(item)

    return final


def normalize_analysis(
    raw: Dict[str, Any],
) -> Dict[str, Any]:

    if not isinstance(raw, dict):
        raw = {}

    analysis = {}

    for field in STRING_FIELDS:

        analysis[field] = normalize_string(
            raw.get(field)
        )

    for field in LIST_FIELDS:

        analysis[field] = normalize_list(
            raw.get(field)
        )

    return analysis


# ============================================================
# GENERIC ITEM REMOVAL
# ============================================================

GENERIC_ITEMS = {
    "this module",
    "this framework",
    "this model",
    "this method",
    "the model",
    "the framework",
    "the system",
    "the proposed framework",
    "the proposed model",
    "the proposed method",
    "our model",
    "our framework",
    "our proposed method",
    "our proposed framework",
    "technical details",
    "this section",
    "the proposed system",
}


def remove_generic_items(
    items: List[str],
) -> List[str]:

    result = []

    for item in items:

        normalized = item.lower().strip()

        if normalized in GENERIC_ITEMS:
            continue

        # Obvious PDF section descriptions.
        if normalized.startswith(
            (
                "in this section",
                "this section",
                "figure ",
                "table ",
                "rq1:",
                "rq2:",
                "rq3:",
                "rq4:",
                "rq5:",
                "rq6:",
                "rq7:",
                "rq8:",
            )
        ):
            continue

        # Paragraphs are not useful list items.
        if len(item) > 700:
            continue

        result.append(item)

    return result


# ============================================================
# EVIDENCE MATCHING
# ============================================================

def concept_in_text(
    concept: str,
    text: str,
) -> bool:

    if not concept or not text:
        return False

    concept_words = [
        word.lower()
        for word in re.findall(
            r"[A-Za-z0-9@.+-]+",
            concept,
        )
        if len(word) > 2
    ]

    if not concept_words:
        return False

    text_lower = text.lower()

    # Exact phrase.
    if concept.lower() in text_lower:
        return True

    # For multi-word concepts require most meaningful words.
    matched = sum(
        1
        for word in concept_words
        if word in text_lower
    )

    required = max(
        1,
        int(len(concept_words) * 0.7),
    )

    return matched >= required


def evidence_filter(
    items: List[str],
    evidence: str,
) -> List[str]:

    if not evidence:
        return items

    verified = []

    for item in items:

        if concept_in_text(
            item,
            evidence,
        ):
            verified.append(item)

    return verified


# ============================================================
# DATASET EXTRACTION
# ============================================================

def extract_datasets_from_text(
    text: str,
) -> List[str]:

    if not text:
        return []

    candidates = []

    patterns = [
        r"(?:datasets?|data sets?)\s*(?:used|include|included|are|were)?"
        r"\s*(?:on|from|:)?\s*([A-Z][A-Za-z0-9_-]*(?:\s+dataset)?"
        r"(?:\s*,\s*[A-Z][A-Za-z0-9_-]*(?:\s+dataset)?){0,5})",

        r"(?:evaluated|tested|experiments?)\s+(?:on|using)\s+"
        r"([A-Z][A-Za-z0-9_-]*(?:\s+dataset)?"
        r"(?:\s*,\s*[A-Z][A-Za-z0-9_-]*(?:\s+dataset)?){0,5})",
    ]

    for pattern in patterns:

        matches = re.findall(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        for match in matches:

            parts = re.split(
                r",|\band\b",
                match,
                flags=re.IGNORECASE,
            )

            for part in parts:

                part = part.strip(
                    " .:;()[]"
                )

                if 2 <= len(part) <= 100:

                    if not re.match(
                        r"^(the|following|these|three|four|five)$",
                        part,
                        flags=re.IGNORECASE,
                    ):
                        candidates.append(part)

    # Common dataset naming pattern.
    common_dataset_pattern = (
        r"\b("
        r"Tmall|"
        r"MovieLens(?:-\d+)?|"
        r"Amazon|"
        r"Yelp|"
        r"BeiBei|"
        r"IJCAI[- ]?contest|"
        r"Taobao|"
        r"Douban|"
        r"Last\.fm|"
        r"Netflix"
        r")\b"
    )

    candidates.extend(
        re.findall(
            common_dataset_pattern,
            text,
            flags=re.IGNORECASE,
        )
    )

    final = []
    seen = set()

    for item in candidates:

        item = re.sub(
            r"\s+",
            " ",
            item,
        ).strip()

        key = item.lower()

        if key in seen:
            continue

        seen.add(key)
        final.append(item)

    return final[:15]


# ============================================================
# METRIC EXTRACTION
# ============================================================

KNOWN_METRICS = [
    "NDCG",
    "HR",
    "Hit Ratio",
    "Recall",
    "Precision",
    "F1-score",
    "F1",
    "Accuracy",
    "AUC",
    "MAP",
    "MRR",
    "MAE",
    "RMSE",
    "BLEU",
    "ROUGE",
    "Perplexity",
    "MSE",
    "R2",
    "R²",
]


def extract_metrics_from_text(
    text: str,
) -> List[str]:

    if not text:
        return []

    found = []

    for metric in KNOWN_METRICS:

        pattern = re.escape(metric)

        if re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        ):

            # Capture @K when present.
            match = re.search(
                rf"\b{re.escape(metric)}\s*@\s*\d+\b",
                text,
                flags=re.IGNORECASE,
            )

            if match:
                found.append(
                    match.group(0)
                )
            else:
                found.append(metric)

    # Explicit metric expressions such as Recall@20.
    explicit = re.findall(
        r"\b(?:HR|NDCG|Recall|Precision|Hit\s*Ratio|F1)"
        r"\s*@\s*\d+\b",
        text,
        flags=re.IGNORECASE,
    )

    found.extend(explicit)

    final = []
    seen = set()

    for metric in found:

        metric = re.sub(
            r"\s+",
            " ",
            metric,
        ).strip()

        key = metric.lower()

        if key in seen:
            continue

        seen.add(key)
        final.append(metric)

    return final


# ============================================================
# TECHNIQUE EXTRACTION
# ============================================================

TECHNIQUE_PATTERNS = [
    r"\bgraph neural network\b",
    r"\bgraph convolutional network\b",
    r"\bgraph attention network\b",
    r"\bgraph neural architecture\b",
    r"\bmessage passing\b",
    r"\bself[- ]attention\b",
    r"\battention mechanism\b",
    r"\btransformer(?: encoder)?\b",
    r"\bconvolutional neural network\b",
    r"\bcnn\b",
    r"\brecurrent neural network\b",
    r"\blstm\b",
    r"\bgru\b",
    r"\bautoencoder\b",
    r"\bvariational autoencoder\b",
    r"\bcontrastive learning\b",
    r"\breinforcement learning\b",
    r"\btransfer learning\b",
    r"\bknowledge graph\b",
    r"\bretrieval[- ]augmented generation\b",
    r"\brag\b",
    r"\bmutual relation encoder\b",
    r"\bgraph sampling\b",
    r"\bmessage aggregation\b",
    r"\bmatrix factorization\b",
    r"\bcollaborative filtering\b",
    r"\bhigh[- ]order graph learning\b",
    r"\bmulti[- ]behavior graph\b",
    r"\bmulti[- ]behavior recommendation\b",
]


def extract_techniques_from_text(
    text: str,
) -> List[str]:

    if not text:
        return []

    found = []

    for pattern in TECHNIQUE_PATTERNS:

        matches = re.findall(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        for match in matches:

            if isinstance(match, tuple):
                match = next(
                    (
                        item
                        for item in match
                        if item
                    ),
                    "",
                )

            if not match:
                continue

            # Normalize known names.
            normalized = match.strip()

            found.append(
                normalized
            )

    # Preserve canonical capitalization.
    canonical = {
        "graph neural network":
            "Graph Neural Network",

        "graph convolutional network":
            "Graph Convolutional Network",

        "graph attention network":
            "Graph Attention Network",

        "message passing":
            "Message Passing",

        "self-attention":
            "Self-Attention",

        "attention mechanism":
            "Attention Mechanism",

        "transformer":
            "Transformer",

        "transformer encoder":
            "Transformer Encoder",

        "autoencoder":
            "Autoencoder",

        "contrastive learning":
            "Contrastive Learning",

        "knowledge graph":
            "Knowledge Graph",

        "retrieval-augmented generation":
            "Retrieval-Augmented Generation",

        "mutual relation encoder":
            "Mutual Relation Encoder",

        "graph sampling":
            "Graph Sampling",

        "matrix factorization":
            "Matrix Factorization",

        "collaborative filtering":
            "Collaborative Filtering",

        "high-order graph learning":
            "High-Order Graph Learning",

        "multi-behavior graph":
            "Multi-Behavior Graph",

        "multi-behavior recommendation":
            "Multi-Behavior Recommendation",
    }

    result = []
    seen = set()

    for item in found:

        key = item.lower()

        item = canonical.get(
            key,
            item,
        )

        key = item.lower()

        if key in seen:
            continue

        seen.add(key)
        result.append(item)

    return result[:20]


# ============================================================
# FINDING EXTRACTION
# ============================================================

def extract_findings_from_text(
    text: str,
) -> List[str]:

    if not text:
        return []

    sentences = re.split(
        r"(?<=[.!?])\s+",
        text,
    )

    result = []

    finding_terms = (
        "outperform",
        "outperforms",
        "improve",
        "improves",
        "improved",
        "achieve",
        "achieves",
        "achieved",
        "superior",
        "significantly better",
        "significant improvement",
        "better performance",
        "competitive performance",
        "validated",
        "demonstrate",
        "demonstrates",
        "demonstrated",
        "effective",
        "effectiveness",
    )

    for sentence in sentences:

        sentence = re.sub(
            r"\s+",
            " ",
            sentence,
        ).strip()

        lower = sentence.lower()

        if len(sentence) < 40:
            continue

        # Do not accept research questions.
        if re.match(
            r"^(rq\d+|research question)",
            lower,
        ):
            continue

        if any(
            term in lower
            for term in finding_terms
        ):

            result.append(
                sentence[:1000]
            )

        if len(result) >= 6:
            break

    return result


# ============================================================
# FALLBACK PROBLEM EXTRACTION
# ============================================================

def extract_problem(
    text: str,
) -> str:

    if not text:
        return ""

    sentences = re.split(
        r"(?<=[.!?])\s+",
        text,
    )

    keywords = (
        "however",
        "challenge",
        "problem",
        "limitation",
        "shortcoming",
        "overlook",
        "insufficient",
        "lack of",
        "remain",
        "existing methods",
        "existing models",
    )

    for sentence in sentences:

        sentence = re.sub(
            r"\s+",
            " ",
            sentence,
        ).strip()

        if len(sentence) < 40:
            continue

        lower = sentence.lower()

        if any(
            keyword in lower
            for keyword in keywords
        ):

            return sentence[:2000]

    return ""


# ============================================================
# FALLBACK METHODOLOGY EXTRACTION
# ============================================================

def extract_methodology(
    text: str,
) -> List[str]:

    if not text:
        return []

    sentences = re.split(
        r"(?<=[.!?])\s+",
        text,
    )

    keywords = (
        "propose",
        "proposed",
        "develop",
        "developed",
        "design",
        "designed",
        "construct",
        "constructs",
        "build",
        "builds",
        "introduce",
        "introduces",
        "learn",
        "learning",
        "aggregate",
        "aggregation",
        "message passing",
        "encoder",
        "graph",
        "attention",
        "propagation",
    )

    result = []

    for sentence in sentences:

        sentence = re.sub(
            r"\s+",
            " ",
            sentence,
        ).strip()

        if len(sentence) < 50:
            continue

        lower = sentence.lower()

        if any(
            keyword in lower
            for keyword in keywords
        ):

            result.append(
                sentence[:900]
            )

        if len(result) >= 8:
            break

    return result


# ============================================================
# FALLBACK CONTRIBUTION EXTRACTION
# ============================================================

def extract_contributions(
    text: str,
) -> List[str]:

    if not text:
        return []

    sentences = re.split(
        r"(?<=[.!?])\s+",
        text,
    )

    result = []

    contribution_terms = (
        "we propose",
        "we introduce",
        "we develop",
        "our contributions",
        "our main contribution",
        "contributions are",
        "we design",
        "we present",
        "this paper proposes",
        "this work proposes",
    )

    for sentence in sentences:

        sentence = re.sub(
            r"\s+",
            " ",
            sentence,
        ).strip()

        lower = sentence.lower()

        if len(sentence) < 40:
            continue

        if any(
            term in lower
            for term in contribution_terms
        ):

            result.append(
                sentence[:1000]
            )

        if len(result) >= 6:
            break

    return result


# ============================================================
# EXPLICIT FUTURE WORK EXTRACTION
# ============================================================

def extract_future_work(
    text: str,
) -> List[str]:

    if not text:
        return []

    sentences = re.split(
        r"(?<=[.!?])\s+",
        text,
    )

    result = []

    future_terms = (
        "future work",
        "future research",
        "future direction",
        "future study",
        "in future",
        "we plan to",
        "we would like to",
        "will investigate",
        "will explore",
        "left for future",
    )

    for sentence in sentences:

        sentence = re.sub(
            r"\s+",
            " ",
            sentence,
        ).strip()

        lower = sentence.lower()

        if len(sentence) < 30:
            continue

        if any(
            term in lower
            for term in future_terms
        ):

            result.append(
                sentence[:1000]
            )

        if len(result) >= 5:
            break

    return result


# ============================================================
# EXPLICIT LIMITATION EXTRACTION
# ============================================================

def extract_limitations(
    text: str,
) -> List[str]:

    if not text:
        return []

    sentences = re.split(
        r"(?<=[.!?])\s+",
        text,
    )

    result = []

    limitation_terms = (
        "limitation",
        "limitations",
        "limited by",
        "limited to",
        "cannot",
        "unable to",
        "lack of",
        "drawback",
        "shortcoming",
    )

    for sentence in sentences:

        sentence = re.sub(
            r"\s+",
            " ",
            sentence,
        ).strip()

        lower = sentence.lower()

        if len(sentence) < 30:
            continue

        if any(
            term in lower
            for term in limitation_terms
        ):

            result.append(
                sentence[:1000]
            )

        if len(result) >= 5:
            break

    return result


# ============================================================
# DETERMINISTIC RECOVERY
# ============================================================

def deterministic_recovery(
    analysis: Dict[str, Any],
    text: str,
    sections: Dict[str, str],
) -> Dict[str, Any]:

    abstract = sections.get(
        "abstract",
        "",
    )

    introduction = sections.get(
        "introduction",
        "",
    )

    methodology = section_text(
        sections,
        [
            "methodology",
        ],
    )

    evaluation = section_text(
        sections,
        [
            "experiments",
            "results",
            "discussion",
        ],
    )

    conclusion = sections.get(
        "conclusion",
        "",
    )

    future = section_text(
        sections,
        [
            "future_work",
        ],
    )

    limitations = section_text(
        sections,
        [
            "limitations",
        ],
    )

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    if not analysis["summary"]:

        source = (
            abstract
            or conclusion
            or text[:5000]
        )

        if source:

            analysis["summary"] = re.sub(
                r"\s+",
                " ",
                source,
            ).strip()[:3000]

    # --------------------------------------------------------
    # PROBLEM
    # --------------------------------------------------------

    if not analysis["problem"]:

        analysis["problem"] = extract_problem(
            introduction or abstract
        )

    # --------------------------------------------------------
    # METHODOLOGY
    # --------------------------------------------------------

    if not analysis["methodology"]:

        analysis["methodology"] = (
            extract_methodology(
                methodology
                or abstract
            )
        )

    # --------------------------------------------------------
    # TECHNIQUES
    # --------------------------------------------------------

    if not analysis["techniques"]:

        analysis["techniques"] = (
            extract_techniques_from_text(
                methodology
                or abstract
            )
        )

    # --------------------------------------------------------
    # DATASETS
    # --------------------------------------------------------

    if not analysis["datasets"]:

        analysis["datasets"] = (
            extract_datasets_from_text(
                evaluation
            )
        )

    # --------------------------------------------------------
    # METRICS
    # --------------------------------------------------------

    if not analysis["metrics"]:

        analysis["metrics"] = (
            extract_metrics_from_text(
                evaluation
            )
        )

    # --------------------------------------------------------
    # FINDINGS
    # --------------------------------------------------------

    if not analysis["findings"]:

        analysis["findings"] = (
            extract_findings_from_text(
                evaluation
                or conclusion
                or abstract
            )
        )

    # --------------------------------------------------------
    # CONTRIBUTIONS
    # --------------------------------------------------------

    if not analysis["contributions"]:

        analysis["contributions"] = (
            extract_contributions(
                introduction
                or abstract
                or conclusion
            )
        )

    # --------------------------------------------------------
    # LIMITATIONS
    # --------------------------------------------------------

    if not analysis["limitations"]:

        analysis["limitations"] = (
            extract_limitations(
                limitations
                or conclusion
            )
        )

    # --------------------------------------------------------
    # FUTURE WORK
    # --------------------------------------------------------

    if not analysis["future_work"]:

        analysis["future_work"] = (
            extract_future_work(
                future
                or conclusion
            )
        )

    return analysis


# ============================================================
# FINAL QUALITY CONTROL
# ============================================================

def quality_check(
    analysis: Dict[str, Any],
) -> bool:

    """
    A valid paper analysis needs meaningful core information.

    Optional fields can all be empty.

    We therefore DO NOT require:
        datasets
        metrics
        limitations
        future_work
        contributions

    A summary/problem/methodology/finding combination is sufficient.
    """

    if not analysis:
        return False

    summary = analysis.get(
        "summary",
        "",
    )

    problem = analysis.get(
        "problem",
        "",
    )

    methodology = analysis.get(
        "methodology",
        [],
    )

    findings = analysis.get(
        "findings",
        [],
    )

    contributions = analysis.get(
        "contributions",
        [],
    )

    return bool(
        summary
        or problem
        or methodology
        or findings
        or contributions
    )


# ============================================================
# MAIN ANALYSIS FUNCTION
# ============================================================

def analyze_paper(
    paper_id: str,
) -> Dict[str, Any]:

    """
    Analyze a paper stored in MongoDB.

    Expected caller:

        analysis = analyze_paper(paper_id)

    This matches:

        POST /api/papers/{paper_id}/analyze
    """

    # ========================================================
    # 1. FIND PAPER
    # ========================================================

    paper = papers_collection.find_one(
        {
            "_id": paper_id
        }
    )

    if not paper:

        raise ValueError(
            "Paper not found."
        )

    # ========================================================
    # 2. GET TEXT
    # ========================================================

    raw_text = paper.get(
        "text",
        "",
    )

    if not isinstance(
        raw_text,
        str,
    ):

        raw_text = str(
            raw_text
        )

    text = clean_text(
        raw_text
    )

    if not text.strip():

        raise ValueError(
            "No extracted text is available for analysis."
        )

    # ========================================================
    # 3. BUILD SECTIONS
    # ========================================================

    sections = build_sections(
        text
    )

    # ========================================================
    # 4. BUILD EVIDENCE CONTEXT
    # ========================================================

    context = build_context(
        text,
        sections,
    )

    if not context.strip():

        raise ValueError(
            "Could not build usable paper evidence."
        )

    # ========================================================
    # 5. CALL LOCAL LLM
    # ========================================================

    try:

        raw_analysis = call_ollama(
            context
        )

    except Exception:

        # Do NOT immediately fail.
        #
        # The deterministic extractor can still recover useful
        # information from the paper.

        raw_analysis = {}

    # ========================================================
    # 6. NORMALIZE LLM RESULT
    # ========================================================

    analysis = normalize_analysis(
        raw_analysis
    )

    # ========================================================
    # 7. REMOVE GENERIC JUNK
    # ========================================================

    for field in LIST_FIELDS:

        analysis[field] = (
            remove_generic_items(
                analysis[field]
            )
        )

    # ========================================================
    # 8. EVIDENCE-AWARE VALIDATION
    # ========================================================

    methodology_evidence = section_text(
        sections,
        [
            "methodology",
            "abstract",
        ],
    )

    evaluation_evidence = section_text(
        sections,
        [
            "experiments",
            "results",
            "discussion",
            "conclusion",
        ],
    )

    # Techniques should exist in actual methodology evidence.
    if methodology_evidence:

        verified = evidence_filter(
            analysis["techniques"],
            methodology_evidence,
        )

        # Only replace if we actually found valid evidence.
        if verified:
            analysis["techniques"] = verified

    # Datasets should be connected to evaluation evidence.
    if evaluation_evidence:

        verified = evidence_filter(
            analysis["datasets"],
            evaluation_evidence,
        )

        if verified:
            analysis["datasets"] = verified

    # Metrics should be connected to evaluation evidence.
    if evaluation_evidence:

        verified = evidence_filter(
            analysis["metrics"],
            evaluation_evidence,
        )

        if verified:
            analysis["metrics"] = verified

    # ========================================================
    # 9. DETERMINISTIC RECOVERY
    # ========================================================

    analysis = deterministic_recovery(
        analysis,
        text,
        sections,
    )

    # ========================================================
    # 10. REMOVE GENERIC ITEMS AGAIN
    # ========================================================

    for field in LIST_FIELDS:

        analysis[field] = (
            remove_generic_items(
                analysis[field]
            )
        )

    # ========================================================
    # 11. FINAL NORMALIZATION
    # ========================================================

    analysis = normalize_analysis(
        analysis
    )

    # ========================================================
    # 12. QUALITY CHECK
    # ========================================================

    if not quality_check(
        analysis
    ):

        raise ValueError(
            "SciBrain could not extract usable research information "
            "from the supplied paper text."
        )

    # ========================================================
    # 13. SAVE TO MONGODB
    # ========================================================

    papers_collection.update_one(
        {
            "_id": paper_id
        },
        {
            "$set": {
                "analysis": analysis,
                "status": "analyzed",
                "processing_error": None,
            }
        },
    )

    # ========================================================
    # 14. RETURN
    # ========================================================

    return analysis