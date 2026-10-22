from typing import List, Literal, Optional
from pydantic import BaseModel, Field

# 🧬 Aligned strictly to your frontend's NODE_TYPES array index mapping rules
EntityType = Literal[
    "paper", "author", "method", "dataset", "metric", 
    "concept", "finding", "limitation", "future_work", 
    "problem", "organization", "tool", "model"
]

# 🔗 Clear semantic predicates binding your academic canvas graph elements
RelationType = Literal[
    "AUTHORED", "PROPOSES", "UTILIZES", "BENCHMARKS_ON",
    "EVALUATES_WITH", "ACHIEVES_METRIC", "EXTENDS", 
    "IMPLEMENTED_VIA", "ADDRESSES", "PROVES", "CONTRADICTS"
]

class GraphNode(BaseModel):
    id: str = Field(..., description="Unique alphanumeric lowercase identifier slug (e.g., 'adam-optimizer')")
    name: str = Field(..., description="The canonical display name matching front-end node.name rules (e.g., 'Adam Optimizer')")
    type: EntityType = Field(..., description="The typed ontological category of this entity")
    description: str = Field(..., description="Specific definition or context statement showing its role in the text")

class GraphEdge(BaseModel):
    source: str = Field(..., description="The 'id' of the source node entity")
    target: str = Field(..., description="The 'id' of the target node entity")
    relationship: RelationType = Field(..., description="The semantic predicate string matching front-end edge.relationship rules")
    evidence: str = Field(..., description="Verbatim sentence excerpt extracted from the source text serving as empirical proof")

class KnowledgeGraphResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
