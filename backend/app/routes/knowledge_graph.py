# routes/knowledge_graph.py
from typing import List
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends
from pydantic import BaseModel, Field

from app.core.dependencies import get_current_user_id
from app.database.mongodb import (
    knowledge_graphs_collection,
    notebooks_collection,
)
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# 🔴 REMOVE OR COMMENT OUT THIS FAULTY LINE:
# from app.models.knowledge_graph import KNOWLEDGE_GRAPH_SCHEMA  

# 🟢 KEEP ONLY THE ACTUAL SERVICE IMPLEMENTATION:
from app.services.knowledge_graph import generate_knowledge_graph

router = APIRouter(
    prefix="/api/knowledge-graph",
    tags=["Knowledge Graph"],
)

class KnowledgeGraphRequest(BaseModel):
    resource_ids: List[str]

@router.post("")
def create_knowledge_graph(
    request: KnowledgeGraphRequest,
):
    resource_ids = [
        str(resource_id).strip()
        for resource_id in request.resource_ids
        if str(resource_id).strip()
    ]

    # Remove duplicate resource IDs while preserving order.
    resource_ids = list(dict.fromkeys(resource_ids))

    if not resource_ids:
        raise HTTPException(
            status_code=400,
            detail="At least one resource_id is required.",
        )

    return generate_knowledge_graph(resource_ids)

class SaveKnowledgeGraphRequest(BaseModel):
    notebook_id: str = Field(min_length=1)
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]


def serialize_saved_graph(graph: dict) -> dict:
    """Return a frontend-safe saved graph."""
    return {
        "graph_id": graph.get("graph_id"),
        "notebook_id": graph.get("notebook_id"),
        "title": graph.get("title", "Knowledge Graph"),
        "resource_ids": graph.get("resource_ids", []),
        "nodes": graph.get("nodes", []),
        "edges": graph.get("edges", []),
        "created_at": graph.get("created_at"),
        "updated_at": graph.get("updated_at"),
    }


@router.post("/saved")
def save_knowledge_graph(
    request: SaveKnowledgeGraphRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Save or update the current graph snapshot for a notebook."""

    notebook_id = request.notebook_id.strip()
    owner_id = str(user_id)

    notebook = notebooks_collection.find_one(
        {
            "notebook_id": notebook_id,
            "user_id": owner_id,
        },
        {
            "_id": 0,
            "title": 1,
            "resource_ids": 1,
        },
    )

    if not notebook:
        raise HTTPException(
            status_code=404,
            detail="Notebook not found.",
        )

    if not request.nodes:
        raise HTTPException(
            status_code=400,
            detail="Cannot save an empty knowledge graph.",
        )

    now = datetime.now(timezone.utc)

    existing = knowledge_graphs_collection.find_one(
        {
            "notebook_id": notebook_id,
            "user_id": owner_id,
        },
        {
            "_id": 0,
            "graph_id": 1,
            "created_at": 1,
        },
    )

    graph_id = (
        existing["graph_id"]
        if existing
        else str(uuid.uuid4())
    )

    graph = {
        "graph_id": graph_id,
        "notebook_id": notebook_id,
        "user_id": owner_id,
        "title": (
            notebook.get("title", "Untitled Notebook")
            + " — Knowledge Graph"
        ),
        "resource_ids": notebook.get("resource_ids", []),
        "nodes": request.nodes,
        "edges": request.edges,
        "created_at": (
            existing.get("created_at", now)
            if existing
            else now
        ),
        "updated_at": now,
    }

    knowledge_graphs_collection.update_one(
        {
            "notebook_id": notebook_id,
            "user_id": owner_id,
        },
        {
            "$set": graph,
        },
        upsert=True,
    )

    return {
        "message": "Knowledge graph saved successfully.",
        "graph": serialize_saved_graph(graph),
    }


@router.get("/saved")
def get_saved_knowledge_graphs(
    user_id: str = Depends(get_current_user_id),
):
    """List saved graphs belonging to the current researcher."""

    cursor = knowledge_graphs_collection.find(
        {
            "user_id": str(user_id),
        },
        {
            "_id": 0,
            "graph_id": 1,
            "notebook_id": 1,
            "title": 1,
            "resource_ids": 1,
            "created_at": 1,
            "updated_at": 1,
        },
    ).sort("updated_at", -1)

    return {
        "graphs": list(cursor),
    }


@router.get("/saved/{graph_id}")
def get_saved_knowledge_graph(
    graph_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Load a saved graph without running Gemini again."""

    graph = knowledge_graphs_collection.find_one(
        {
            "graph_id": graph_id,
            "user_id": str(user_id),
        },
        {
            "_id": 0,
        },
    )

    if not graph:
        raise HTTPException(
            status_code=404,
            detail="Saved knowledge graph not found.",
        )

    return {
        "graph": serialize_saved_graph(graph),
    }


@router.delete("/saved/{graph_id}")
def delete_saved_knowledge_graph(
    graph_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Delete a saved graph owned by the current researcher."""

    result = knowledge_graphs_collection.delete_one(
        {
            "graph_id": graph_id,
            "user_id": str(user_id),
        }
    )

    if result.deleted_count == 0:
        raise HTTPException(
            status_code=404,
            detail="Saved knowledge graph not found.",
        )

    return {
        "message": "Saved knowledge graph deleted successfully.",
        "graph_id": graph_id,
    }
