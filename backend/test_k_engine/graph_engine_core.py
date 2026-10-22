
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable


# ---------------------------------------------------------
# INPUT CONTRACT
# ---------------------------------------------------------

@dataclass(frozen=True)
class EvidenceChunk:
    chunk_id: str
    paper_id: str
    paper_title: str
    text: str


@dataclass(frozen=True)
class EntityCandidate:
    name: str
    entity_type: str
    chunk_id: str
    evidence_quote: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class RelationshipCandidate:
    source_name: str
    source_type: str
    relation: str
    target_name: str
    target_type: str
    chunk_id: str
    evidence_quote: str


# ---------------------------------------------------------
# OUTPUT CONTRACT
# ---------------------------------------------------------

@dataclass
class GraphEvidence:
    paper_id: str
    paper_title: str
    chunk_id: str
    quote: str


@dataclass
class GraphNode:
    id: str
    name: str
    entity_type: str
    aliases: list[str] = field(default_factory=list)
    evidence: list[GraphEvidence] = field(default_factory=list)


@dataclass
class GraphEdge:
    id: str
    source: str
    target: str
    relation: str
    evidence: list[GraphEvidence] = field(default_factory=list)


@dataclass
class GraphResult:
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    diagnostics: dict


# ---------------------------------------------------------
# NORMALIZATION
# ---------------------------------------------------------

def normalize_text(value: str) -> str:
    """Normalize formatting without removing meaningful characters."""
    value = unicodedata.normalize("NFKC", value or "")
    value = value.casefold()
    value = re.sub(r"[\u2010-\u2015]", "-", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def normalize_name(value: str) -> str:
    """Normalize superficial punctuation and whitespace differences."""
    value = normalize_text(value)
    value = re.sub(r"[^\w\s-]", "", value, flags=re.UNICODE)
    value = re.sub(r"[\s_-]+", " ", value)
    return value.strip()


def contains_phrase(text: str, phrase: str) -> bool:
    """
    Match a phrase at word boundaries rather than by substring.

    This avoids matching 'BERT' inside 'ColBERT'.
    """
    phrase = normalize_text(phrase)
    text = normalize_text(text)

    if not phrase:
        return False

    pattern = (
        r"(?<!\w)"
        + re.escape(phrase)
        + r"(?!\w)"
    )
    return re.search(pattern, text, flags=re.UNICODE) is not None


# ---------------------------------------------------------
# GRAPH BUILDER
# ---------------------------------------------------------

class EvidenceGraphBuilder:
    """
    Deterministic graph assembly and evidence validation.

    The LLM proposes facts. This component checks provenance,
    quoted text, endpoint identity and duplicate graph facts.

    It deliberately does not claim to prove scientific meaning
    from string matching alone.
    """

    def build(
        self,
        chunks: Iterable[EvidenceChunk],
        entity_candidates: Iterable[EntityCandidate],
        relationship_candidates: Iterable[RelationshipCandidate],
    ) -> GraphResult:

        chunk_map = {
            chunk.chunk_id: chunk
            for chunk in chunks
            if chunk.chunk_id and chunk.paper_id and chunk.text.strip()
        }

        nodes_by_key: dict[tuple[str, str], GraphNode] = {}
        entity_lookup: dict[tuple[str, str], str] = {}
        aliases_by_node: dict[str, set[str]] = {}

        rejected_entities = Counter()
        rejected_edges = Counter()
        edge_evidence: dict[tuple[str, str, str], list[GraphEvidence]] = {}

        def valid_quote(chunk: EvidenceChunk, quote: str) -> bool:
            """
            Require the evidence quote to be present in the
            referenced chunk, ignoring harmless whitespace and
            Unicode formatting differences.
            """
            if not quote or not quote.strip():
                return False

            return normalize_text(quote) in normalize_text(chunk.text)

        def evidence_for(
            chunk: EvidenceChunk,
            quote: str,
        ) -> GraphEvidence:
            return GraphEvidence(
                paper_id=chunk.paper_id,
                paper_title=chunk.paper_title,
                chunk_id=chunk.chunk_id,
                quote=quote.strip(),
            )

        def entity_key(name: str, entity_type: str) -> tuple[str, str]:
            return (
                normalize_name(entity_type),
                normalize_name(name),
            )

        def add_entity(
            name: str,
            entity_type: str,
            aliases: Iterable[str],
            evidence: GraphEvidence,
        ) -> str:
            key = entity_key(name, entity_type)

            if key not in nodes_by_key:
                # Stable for the same normalized type and name.
                node_id = f"entity:{key[0]}:{key[1]}"
                node = GraphNode(
                    id=node_id,
                    name=name.strip(),
                    entity_type=entity_type.strip(),
                )
                nodes_by_key[key] = node
                aliases_by_node[node_id] = set()
            else:
                node = nodes_by_key[key]

            for alias in aliases:
                alias = alias.strip()
                if alias and normalize_name(alias) != key[1]:
                    aliases_by_node[node.id].add(alias)

            if evidence not in node.evidence:
                node.evidence.append(evidence)

            entity_lookup[key] = node.id
            return node.id

        # -------------------------------------------------
        # STAGE 1: validate and register entities
        # -------------------------------------------------

        for candidate in entity_candidates:
            name = candidate.name.strip()
            entity_type = candidate.entity_type.strip()
            chunk = chunk_map.get(candidate.chunk_id)

            if not name or not entity_type:
                rejected_entities["missing_name_or_type"] += 1
                continue

            if chunk is None:
                rejected_entities["unknown_chunk"] += 1
                continue

            if not valid_quote(chunk, candidate.evidence_quote):
                rejected_entities["quote_not_in_source"] += 1
                continue

            possible_names = [name, *candidate.aliases]

            if not any(
                contains_phrase(candidate.evidence_quote, item)
                for item in possible_names
                if item.strip()
            ):
                rejected_entities["entity_not_mentioned_in_quote"] += 1
                continue

            add_entity(
                name=name,
                entity_type=entity_type,
                aliases=candidate.aliases,
                evidence=evidence_for(chunk, candidate.evidence_quote),
            )

        # Build alias lookup after all accepted entity candidates
        # have been registered.
        for node in nodes_by_key.values():
            for alias in aliases_by_node[node.id]:
                alias_key = entity_key(alias, node.entity_type)

                # Never silently overwrite a conflicting alias.
                existing = entity_lookup.get(alias_key)
                if existing is None or existing == node.id:
                    entity_lookup[alias_key] = node.id

            node.aliases = sorted(aliases_by_node[node.id])

        # -------------------------------------------------
        # STAGE 2: validate and assemble relationships
        # -------------------------------------------------

        for candidate in relationship_candidates:
            chunk = chunk_map.get(candidate.chunk_id)

            if chunk is None:
                rejected_edges["unknown_chunk"] += 1
                continue

            quote = candidate.evidence_quote.strip()

            if not valid_quote(chunk, quote):
                rejected_edges["quote_not_in_source"] += 1
                continue

            if not candidate.relation.strip():
                rejected_edges["missing_relation"] += 1
                continue

            source_key = entity_key(
                candidate.source_name,
                candidate.source_type,
            )
            target_key = entity_key(
                candidate.target_name,
                candidate.target_type,
            )

            source_id = entity_lookup.get(source_key)
            target_id = entity_lookup.get(target_key)

            if source_id is None:
                rejected_edges["unresolved_source"] += 1
                continue

            if target_id is None:
                rejected_edges["unresolved_target"] += 1
                continue

            if source_id == target_id:
                rejected_edges["self_relationship"] += 1
                continue

            source_node = next(
                node for node in nodes_by_key.values()
                if node.id == source_id
            )
            target_node = next(
                node for node in nodes_by_key.values()
                if node.id == target_id
            )

            # Both endpoints must be explicitly identifiable in
            # the quoted evidence. Aliases are allowed, but matching
            # is boundary-aware to avoid substring collisions.
            def mentioned(node: GraphNode) -> bool:
                return any(
                    contains_phrase(quote, term)
                    for term in [node.name, *node.aliases]
                    if term.strip()
                )

            if not mentioned(source_node):
                rejected_edges["source_not_in_evidence"] += 1
                continue

            if not mentioned(target_node):
                rejected_edges["target_not_in_evidence"] += 1
                continue

            relation = normalize_name(candidate.relation)
            key = (source_id, relation, target_id)

            evidence = evidence_for(chunk, quote)
            evidence_list = edge_evidence.setdefault(key, [])

            if evidence not in evidence_list:
                evidence_list.append(evidence)

        # -------------------------------------------------
        # STAGE 3: deterministic IDs and deduplication
        # -------------------------------------------------

        edges: list[GraphEdge] = []

        for (source_id, relation, target_id), evidence in sorted(
            edge_evidence.items()
        ):
            edges.append(
                GraphEdge(
                    id=f"edge:{source_id}:{relation}:{target_id}",
                    source=source_id,
                    target=target_id,
                    relation=relation,
                    evidence=evidence,
                )
            )

        nodes = sorted(
            nodes_by_key.values(),
            key=lambda node: (node.entity_type.casefold(), node.name.casefold()),
        )

        node_ids = {node.id for node in nodes}
        assert all(
            edge.source in node_ids and edge.target in node_ids
            for edge in edges
        )

        return GraphResult(
            nodes=nodes,
            edges=edges,
            diagnostics={
                "input_chunks": len(chunk_map),
                "entity_candidates": sum(1 for _ in entity_candidates)
                    if not isinstance(entity_candidates, (list, tuple))
                    else len(entity_candidates),
                "accepted_entities": len(nodes),
                "accepted_relationships": len(edges),
                "rejected_entity_candidates": dict(rejected_entities),
                "rejected_relationship_candidates": dict(rejected_edges),
                "isolated_nodes": sum(
                    1 for node in nodes
                    if not any(
                        edge.source == node.id or edge.target == node.id
                        for edge in edges
                    )
                ),
                "evidence_items_on_edges": sum(
                    len(edge.evidence) for edge in edges
                ),
            },
        )
