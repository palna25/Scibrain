import os
import uuid
from collections import OrderedDict
from datetime import datetime, timezone

import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

from app.core.dependencies import get_current_user_id
from app.database.mongodb import notebook_chats_collection
from app.services.vector_store import search_paper_chunks


router = APIRouter(
    prefix="/api/notebook",
    tags=["Research Notebook"]
)


# ============================================================
# CONFIGURATION
# ============================================================

OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://host.docker.internal:11434"
)

OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "llama3.2:latest"
)

OLLAMA_CHAT_TIMEOUT = int(
    os.getenv("OLLAMA_CHAT_TIMEOUT", "180")
)


# ============================================================
# REQUEST SCHEMA
# ============================================================

class NotebookChatRequest(BaseModel):
    resource_ids: list[str] = Field(default_factory=list)
    message: str = Field(min_length=1)
    chat_id: str | None = None
    notebook_id: str | None = None


# ============================================================
# CHAT TITLE
# ============================================================

def generate_chat_title(message: str) -> str:
    """
    Creates a readable title from the first user message.
    """

    title = " ".join(message.strip().split())

    if len(title) > 60:
        title = title[:57].rstrip() + "..."

    return title or "New Research Chat"


# ============================================================
# MESSAGE SERIALIZATION
# ============================================================

def serialize_message(
    role: str,
    content: str,
    citations: list | None = None
):
    return {
        "role": role,
        "content": content,
        "citations": citations or [],
        "created_at": datetime.now(timezone.utc)
    }


# ============================================================
# GROUP RETRIEVED RESULTS BY PAPER
# ============================================================

def group_results_by_paper(
    results: list[dict]
) -> OrderedDict:

    grouped = OrderedDict()

    for result in results:
        paper_id = str(
            result.get("paper_id", "")
        )

        if paper_id not in grouped:
            grouped[paper_id] = []

        grouped[paper_id].append(result)

    return grouped


# ============================================================
# BUILD LLM CONTEXT
# ============================================================

def build_context(
    results: list[dict]
) -> str:
    """
    Builds context grouped by actual paper.

    Each PAPER represents one research paper.
    Each PASSAGE represents a retrieved chunk
    belonging to that paper.
    """

    grouped = group_results_by_paper(results)

    if not grouped:
        return (
            "No relevant research passages were retrieved."
        )

    sections = []

    for paper_id, chunks in grouped.items():

        title = (
            chunks[0].get("title")
            or "Untitled Research Paper"
        )

        paper_section = [
            f"PAPER: {title}",
            f"PAPER_ID: {paper_id}"
        ]

        passage_number = 0

        for chunk in chunks:

            text = chunk.get("text", "").strip()

            if not text:
                continue

            passage_number += 1

            paper_section.append(
                f"PASSAGE {passage_number}:\n{text}"
            )

        if passage_number > 0:
            sections.append(
                "\n\n".join(paper_section)
            )

    if not sections:
        return (
            "No relevant research passages were retrieved."
        )

    return "\n\n==============================\n\n".join(
        sections
    )


# ============================================================
# BUILD CITATIONS
# ============================================================

def build_citations(
    results: list[dict]
) -> list[dict]:
    """
    Creates citation metadata for the frontend.

    Multiple passages from the same paper remain
    separate internally so the frontend can group
    them into one source card.
    """

    citations = []

    for result in results:

        citations.append({
            "paper_id": result.get("paper_id"),
            "title": (
                result.get("title")
                or "Untitled Research Paper"
            ),
            "chunk_index": result.get("chunk_index"),
            "score": result.get("score")
        })

    return citations


# ============================================================
# OLLAMA
# ============================================================

def ask_ollama(
    question: str,
    context: str
) -> str:

    system_prompt = """
You are the AI research assistant inside SciBrain's
Research Notebook.

Your job is to answer the researcher's question using
ONLY the research context provided to you.

IMPORTANT RULES:

1. Use only information supported by the provided
   research context.

2. Do not use outside knowledge to fill missing
   information.

3. Do not invent facts, datasets, methods, results,
   authors, limitations, or claims.

4. If the answer is not present in the provided
   context, clearly state that the available research
   context does not contain enough information.

5. Treat every PAPER as one separate research paper.

6. Every PASSAGE belongs to the PAPER immediately
   above it.

7. Identify papers by their actual paper titles.

8. When comparing papers, explicitly identify which
   paper supports each statement.

9. Never treat individual passages as separate papers.

10. Do not refer to papers as "Source 1", "Source 2",
    "Source 3", etc.

11. Do not mention Qdrant, embeddings, vector databases,
    retrieval pipelines, prompts, or other internal
    implementation details unless the researcher
    explicitly asks about SciBrain itself.

12. Give a clear, useful, research-oriented answer.

13. Do not fabricate citations, page numbers,
    references, or evidence.

14. If multiple papers discuss the same topic, synthesize
    their information while keeping each paper's claims
    clearly distinguishable.

15. Do not create categories or group papers unless the
    provided context supports those groupings.

Answer naturally and directly.
""".strip()

    user_prompt = f"""
RESEARCH CONTEXT

{context}

============================================================

RESEARCHER QUESTION

{question}

============================================================

Answer the researcher's question using only the
research context above.
""".strip()

    try:

        response = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ],
                "stream": False,
                "options": {
                    "temperature": 0.2
                }
            },
            timeout=OLLAMA_CHAT_TIMEOUT
        )

        response.raise_for_status()

    except requests.RequestException as exc:

        raise HTTPException(
            status_code=502,
            detail=(
                f"Unable to reach the AI model: {exc}"
            )
        )

    try:

        data = response.json()

    except ValueError:

        raise HTTPException(
            status_code=502,
            detail=(
                "The AI model returned an invalid "
                "JSON response."
            )
        )

    answer = (
        data.get("message", {})
        .get("content", "")
        .strip()
    )

    if not answer:

        raise HTTPException(
            status_code=502,
            detail=(
                "The AI model returned an empty answer."
            )
        )

    return answer


# ============================================================
# SAVE CHAT EXCHANGE
# ============================================================
def save_chat_exchange(
    *,
    chat_id: str,
    notebook_id: str,
    user_id: str,
    resource_ids: list[str],
    user_message: str,
    assistant_message: str,
    citations: list[dict]
):
    """
    Saves the complete user + assistant exchange
    into MongoDB.
    """

    now = datetime.now(timezone.utc)

    user_chat_message = serialize_message(
        role="user",
        content=user_message
    )

    assistant_chat_message = serialize_message(
        role="assistant",
        content=assistant_message,
        citations=citations
    )

    title = generate_chat_title(user_message)

    try:
        # First, check whether this chat already exists.
        existing_chat = notebook_chats_collection.find_one(
            {
                "chat_id": chat_id,
                "user_id": str(user_id)
            },
            {
                "_id": 1
            }
        )

        if existing_chat:
            # Existing chat: append the new exchange.
            notebook_chats_collection.update_one(
                {
                    "chat_id": chat_id,
                    "user_id": str(user_id)
                },
                {
                    "$set": {
                        "notebook_id": notebook_id,
                        "resource_ids": resource_ids,
                        "updated_at": now
                    },
                    "$push": {
                        "messages": {
                            "$each": [
                                user_chat_message,
                                assistant_chat_message
                            ]
                        }
                    }
                }
            )

        else:
            # New chat: create the document with the first exchange.
            notebook_chats_collection.insert_one(
                {
                    "chat_id": chat_id,
                    "user_id": str(user_id),
                    "notebook_id": notebook_id,
                    "title": title,
                    "resource_ids": resource_ids,
                    "messages": [
                        user_chat_message,
                        assistant_chat_message
                    ],
                    "created_at": now,
                    "updated_at": now
                }
            )

    except DuplicateKeyError:
        raise HTTPException(
            status_code=403,
            detail="Unable to save notebook chat."
        )

# ============================================================
# NOTEBOOK CHAT
# ============================================================

@router.post("/chat")
def notebook_chat(
    request: NotebookChatRequest,
    user_id: str = Depends(
        get_current_user_id
    )
):

    message = request.message.strip()

    if not message:

        raise HTTPException(
            status_code=400,
            detail="Message cannot be empty."
        )

    # --------------------------------------------------------
    # Normalize resource IDs
    # --------------------------------------------------------

    resource_ids = list(
        dict.fromkeys(
            str(resource_id)
            for resource_id in request.resource_ids
        )
    )

    if not resource_ids:

        raise HTTPException(
            status_code=400,
            detail=(
                "Select at least one research "
                "paper first."
            )
        )

    # --------------------------------------------------------
    # Chat / Notebook IDs
    # --------------------------------------------------------

    chat_id = (
        str(request.chat_id)
        if request.chat_id
        else str(uuid.uuid4())
    )

    notebook_id = (
        str(request.notebook_id)
        if request.notebook_id
        else str(uuid.uuid4())
    )

    # --------------------------------------------------------
    # Retrieve relevant chunks from every selected paper
    # --------------------------------------------------------

    retrieved_chunks = []

    for paper_id in resource_ids:

        try:

            paper_chunks = search_paper_chunks(
                query=message,
                paper_ids=[paper_id],
                limit=3
            )

            retrieved_chunks.extend(
                paper_chunks
            )

        except Exception as exc:

            raise HTTPException(
                status_code=500,
                detail=(
                    f"Paper retrieval failed: {exc}"
                )
            )

    # --------------------------------------------------------
    # Build grounded context
    # --------------------------------------------------------

    context = build_context(
        retrieved_chunks
    )

    # --------------------------------------------------------
    # Generate answer
    # --------------------------------------------------------

    answer = ask_ollama(
        question=message,
        context=context
    )

    # --------------------------------------------------------
    # Build citations
    # --------------------------------------------------------

    citations = build_citations(
        retrieved_chunks
    )

    # --------------------------------------------------------
    # Persist exchange
    # --------------------------------------------------------

    save_chat_exchange(
        chat_id=chat_id,
        notebook_id=notebook_id,
        user_id=str(user_id),
        resource_ids=resource_ids,
        user_message=message,
        assistant_message=answer,
        citations=citations
    )

    # --------------------------------------------------------
    # Return response
    # --------------------------------------------------------

    return {
        "answer": answer,
        "citations": citations,
        "chat_id": chat_id,
        "notebook_id": notebook_id
    }


# ============================================================
# GET CHAT HISTORY
# ============================================================

@router.get("/chats")
def get_chat_history(
    user_id: str = Depends(
        get_current_user_id
    )
):

    chats = notebook_chats_collection.find(
        {
            "user_id": str(user_id)
        },
        {
            "_id": 0,
            "chat_id": 1,
            "notebook_id": 1,
            "title": 1,
            "resource_ids": 1,
            "created_at": 1,
            "updated_at": 1
        }
    ).sort(
        "updated_at",
        -1
    )

    results = []

    for chat in chats:

        results.append({
            "chat_id": chat.get("chat_id"),
            "notebook_id": chat.get("notebook_id"),
            "title": chat.get(
                "title",
                "New Research Chat"
            ),
            "resource_ids": chat.get(
                "resource_ids",
                []
            ),
            "created_at": chat.get(
                "created_at"
            ),
            "updated_at": chat.get(
                "updated_at"
            )
        })

    return {
        "chats": results
    }


# ============================================================
# GET SINGLE CHAT
# ============================================================

@router.get("/chats/{chat_id}")
def get_chat(
    chat_id: str,
    user_id: str = Depends(
        get_current_user_id
    )
):

    chat = notebook_chats_collection.find_one(
        {
            "chat_id": chat_id,
            "user_id": str(user_id)
        },
        {
            "_id": 0
        }
    )

    if not chat:

        raise HTTPException(
            status_code=404,
            detail="Chat not found."
        )

    return chat


# ============================================================
# DELETE CHAT
# ============================================================

@router.delete("/chats/{chat_id}")
def delete_chat(
    chat_id: str,
    user_id: str = Depends(
        get_current_user_id
    )
):

    result = notebook_chats_collection.delete_one(
        {
            "chat_id": chat_id,
            "user_id": str(user_id)
        }
    )

    if result.deleted_count == 0:

        raise HTTPException(
            status_code=404,
            detail="Chat not found."
        )

    return {
        "message": "Chat deleted successfully.",
        "chat_id": chat_id
    }