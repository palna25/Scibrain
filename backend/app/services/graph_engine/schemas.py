"""Strict public schemas for evidence-grounded graph output (Pydantic v2)."""
from __future__ import annotations
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ENTITY_TYPES = {"paper", "author", "method", "model", "dataset", "metric", "concept", "problem", "finding", "limitation", "future_work", "organization", "tool", "task", "other"}
RELATION_TYPES = {"authored_by", "developed_by", "demonstrated_by", "introduced_by", "uses", "proposes", "evaluated_on", "measures", "addresses", "reports", "based_on", "implements", "extends", "improves", "compares_with", "has_finding", "has_limitation", "has_future_work", "related_to", "other"}


def _clean(values):
    result, seen = [], set()
    for item in values or []:
        value = str(item).strip()
        key = value.casefold()
        if value and key not in seen:
            seen.add(key); result.append(value)
    return result


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class EvidenceReference(StrictModel):
    paper_id: str = Field(min_length=1)
    quote: str = Field(min_length=1)
    chunk_id: str | None = None
    chunk_index: int | None = None
    page: int | None = None
    start_offset: int | None = None
    end_offset: int | None = None
    source_section: str | None = None

    @model_validator(mode="after")
    def offsets_valid(self):
        if self.start_offset is not None and self.end_offset is not None and self.end_offset < self.start_offset:
            raise ValueError("end_offset cannot precede start_offset")
        return self


class GraphEntity(StrictModel):
    entity_id: str = Field(min_length=1)
    canonical_name: str = Field(min_length=1)
    type: str
    description: str = ""
    aliases: list[str] = Field(default_factory=list)
    paper_ids: list[str] = Field(default_factory=list)
    evidence: list[EvidenceReference] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)

    @field_validator("entity_id", "canonical_name")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("field must not be blank")
        return value.strip()

    @field_validator("aliases", "paper_ids", mode="before")
    @classmethod
    def clean_lists(cls, value):
        return _clean(value)

    @field_validator("type")
    @classmethod
    def valid_type(cls, value):
        if value not in ENTITY_TYPES:
            raise ValueError(f"Unsupported entity type: {value}")
        return value

    @model_validator(mode="after")
    def evidence_owned(self):
        papers = {item.paper_id for item in self.evidence}
        if not papers.issubset(set(self.paper_ids)):
            raise ValueError("entity paper_ids must include every evidence paper")
        return self


class GraphRelationship(StrictModel):
    relationship_id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    target: str = Field(min_length=1)
    type: str
    description: str = ""
    evidence: list[EvidenceReference] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    paper_ids: list[str] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)

    @field_validator("type")
    @classmethod
    def valid_type(cls, value):
        if value not in RELATION_TYPES:
            raise ValueError(f"Unsupported relationship type: {value}")
        return value

    @field_validator("paper_ids", mode="before")
    @classmethod
    def clean_papers(cls, value):
        return _clean(value)

    @model_validator(mode="after")
    def validate_edge(self):
        if self.source == self.target:
            raise ValueError("self-relationships are not allowed")
        evidence_papers = {item.paper_id for item in self.evidence}
        if self.paper_ids and not evidence_papers.issubset(set(self.paper_ids)):
            raise ValueError("relationship paper_ids must include evidence paper IDs")
        self.paper_ids = _clean([*self.paper_ids, *sorted(evidence_papers)])
        return self


class GraphQualityReport(StrictModel):
    input_papers: int = 0
    processed_papers: int = 0
    retrieved_chunks: int = 0
    candidate_entities: int = 0
    accepted_entities: int = 0
    rejected_entities: int = 0
    candidate_relationships: int = 0
    accepted_relationships: int = 0
    rejected_relationships: int = 0
    indeterminate_relationships: int = 0
    validation_errors: list[str] = Field(default_factory=list)
    rejected_entity_reasons: dict[str, int] = Field(default_factory=dict)
    rejected_relationship_reasons: dict[str, int] = Field(default_factory=dict)


class KnowledgeGraph(StrictModel):
    graph_id: str = Field(min_length=1)
    resource_ids: list[str] = Field(min_length=1)
    nodes: list[GraphEntity] = Field(default_factory=list)
    edges: list[GraphRelationship] = Field(default_factory=list)
    quality: GraphQualityReport = Field(default_factory=GraphQualityReport)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("resource_ids", mode="before")
    @classmethod
    def clean_resource_ids(cls, value):
        return _clean(value)

    @model_validator(mode="after")
    def validate_graph(self):
        selected = set(self.resource_ids)
        if not selected:
            raise ValueError("resource_ids cannot be empty")
        node_ids = [n.entity_id for n in self.nodes]
        edge_ids = [e.relationship_id for e in self.edges]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("duplicate node IDs")
        if len(edge_ids) != len(set(edge_ids)):
            raise ValueError("duplicate relationship IDs")
        node_set = set(node_ids)
        for node in self.nodes:
            if not set(node.paper_ids).issubset(selected):
                raise ValueError(f"node {node.entity_id} references an unselected paper")
        for edge in self.edges:
            if edge.source not in node_set or edge.target not in node_set:
                raise ValueError(f"relationship {edge.relationship_id} has a missing endpoint")
            if not set(edge.paper_ids).issubset(selected):
                raise ValueError(f"relationship {edge.relationship_id} references an unselected paper")
        return self
