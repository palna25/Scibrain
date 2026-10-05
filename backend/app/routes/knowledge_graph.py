from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

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