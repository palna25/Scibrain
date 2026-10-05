import uuid
from collections import OrderedDict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

from app.core.dependencies import get_current_user_id
from app.database.mongodb import notebook_chats_collection
from app.services.gemini import call_gemini
from app.services.vector_store import search_paper_chunks


router = APIRouter(
    prefix="/api/notebook",
    tags=["Research Notebook"],
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
    citations: list | None = None,
):
    return {
        "role": role,
        "content": content,
        "citations": citations or [],
        "created_at": datetime.now(timezone.utc),
    }


# ============================================================
# GROUP RETRIEVED RESULTS BY PAPER
# ============================================================

def group_results_by_paper(
    results: list[dict],
) -> OrderedDict:
    """
    Groups retrieved Qdrant passages by paper.

    This ensures that the Gemini context clearly separates
    one research paper from another.
    """

    grouped = OrderedDict()

    for result in results:
        paper_id = str(
            result.get("paper_id", "")
        )

        if not paper_id:
            continue

        if paper_id not in grouped:
            grouped[paper_id] = []

        grouped[paper_id].append(result)

    return grouped


# ============================================================
# BUILD LLM CONTEXT
# ============================================================

def build_context(
    results: list[dict],
) -> str:
    """
    Builds a grounded research context grouped by paper.

    Each PAPER represents one actual research paper.
    Each PASSAGE belongs to that paper.
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
            f"PAPER_ID: {paper_id}",
        ]

        passage_number = 0

        for chunk in chunks:

            text = (
                chunk.get("text") or ""
            ).strip()

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
    results: list[dict],
) -> list[dict]:
    """
    Creates citation metadata for the frontend.

    Each retrieved passage remains separately identifiable.
    The frontend can group passages by paper if required.
    """

    citations = []

    for result in results:

        paper_id = result.get("paper_id")

        if not paper_id:
            continue

        citations.append({
            "paper_id": paper_id,
            "title": (
                result.get("title")
                or "Untitled Research Paper"
            ),
            "chunk_index": result.get(
                "chunk_index"
            ),
            "score": result.get("score"),
        })

    return citations


# ============================================================
# GEMINI
# ============================================================

def ask_gemini(
    question: str,
    context: str,
) -> str:
    """
    Generates a grounded research answer using Gemini.

    Gemini receives only the retrieved research context
    and the researcher's question.
    """

    system_prompt = """
You are the AI research assistant inside SciBrain's
Research Notebook.

Your task is to answer the researcher's question using
ONLY the research passages provided in the research context.

GROUNDING RULES:

1. Use only information supported by the provided
   research context.

2. Do not use outside knowledge to fill missing information.

3. Do not invent facts, datasets, methods, results,
   authors, limitations, findings, or claims.

4. If the provided research context does not contain
   enough information to answer the question, clearly
   say that the available research context does not
   contain enough information.

5. Treat every PAPER section as one separate research
   paper.

6. Every PASSAGE belongs to the PAPER immediately above it.

7. Identify papers by their actual titles.

8. When comparing papers, clearly identify which paper
   supports each statement.

9. Never treat individual passages as separate papers.

10. Never refer to papers as "Source 1", "Source 2",
    "Source 3", etc.

11. Do not mention Qdrant, embeddings, vector databases,
    retrieval pipelines, prompts, or other internal
    implementation details unless the researcher
    explicitly asks about SciBrain itself.

12. Do not fabricate citations, page numbers, references,
    quotations, or evidence.

13. Do not claim that a paper contains information unless
    that information is supported by the provided passages.

14. When multiple papers discuss the same topic, synthesize
    their information while keeping each paper's claims
    clearly distinguishable.

15. If the question asks for a comparison, structure the
    answer so that the differences and similarities between
    the relevant papers are clear.

16. If the question asks for research gaps, opportunities,
    limitations, or future directions, derive them only from
    the provided research passages. Do not invent gaps that
    are not supported by the papers.

17. Prefer precise research-oriented language over generic
    explanations.

18. Do not mention missing information unless it is relevant
    to the question.

19. Answer naturally and directly.

20. The answer should be useful to a researcher while
    remaining strictly grounded in the supplied evidence.
""".strip()

    user_prompt = f"""
RESEARCH CONTEXT

{context}

============================================================

RESEARCHER QUESTION

{question}

============================================================

Answer the researcher's question using only the research
context above.

Do not add information from outside the provided context.
""".strip()

    prompt = (
        f"{system_prompt}\n\n"
        f"============================================================\n\n"
        f"{user_prompt}"
    )

    try:
        answer = call_gemini(prompt)

    except Exception as exc:

        raise HTTPException(
            status_code=502,
            detail=(
                f"Unable to generate the research answer: {exc}"
            ),
        )

    if not answer or not answer.strip():

        raise HTTPException(
            status_code=502,
            detail=(
                "The AI model returned an empty answer."
            ),
        )

    return answer.strip()


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
    citations: list[dict],
):
    """
    Saves a complete user + assistant exchange
    into MongoDB.
    """

    now = datetime.now(timezone.utc)

    user_chat_message = serialize_message(
        role="user",
        content=user_message,
    )

    assistant_chat_message = serialize_message(
        role="assistant",
        content=assistant_message,
        citations=citations,
    )

    title = generate_chat_title(
        user_message
    )

    try:

        existing_chat = notebook_chats_collection.find_one(
            {
                "chat_id": chat_id,
                "user_id": str(user_id),
            },
            {
                "_id": 1,
            },
        )

        if existing_chat:

            notebook_chats_collection.update_one(
                {
                    "chat_id": chat_id,
                    "user_id": str(user_id),
                },
                {
                    "$set": {
                        "notebook_id": notebook_id,
                        "resource_ids": resource_ids,
                        "updated_at": now,
                    },
                    "$push": {
                        "messages": {
                            "$each": [
                                user_chat_message,
                                assistant_chat_message,
                            ]
                        }
                    },
                },
            )

        else:

            notebook_chats_collection.insert_one(
                {
                    "chat_id": chat_id,
                    "user_id": str(user_id),
                    "notebook_id": notebook_id,
                    "title": title,
                    "resource_ids": resource_ids,
                    "messages": [
                        user_chat_message,
                        assistant_chat_message,
                    ],
                    "created_at": now,
                    "updated_at": now,
                }
            )

    except DuplicateKeyError:

        raise HTTPException(
            status_code=403,
            detail="Unable to save notebook chat.",
        )


# ============================================================
# NOTEBOOK CHAT
# ============================================================

@router.post("/chat")
def notebook_chat(
    request: NotebookChatRequest,
    user_id: str = Depends(
        get_current_user_id
    ),
):
    """
    Answers a research question using only the
    papers selected in the Research Notebook.
    """

    message = request.message.strip()

    if not message:

        raise HTTPException(
            status_code=400,
            detail="Message cannot be empty.",
        )

    # --------------------------------------------------------
    # Normalize resource IDs
    # --------------------------------------------------------

    resource_ids = list(
        dict.fromkeys(
            str(resource_id)
            for resource_id in request.resource_ids
            if str(resource_id).strip()
        )
    )

    if not resource_ids:

        raise HTTPException(
            status_code=400,
            detail=(
                "Select at least one research "
                "paper first."
            ),
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
                limit=3,
            )

            if paper_chunks:
                retrieved_chunks.extend(
                    paper_chunks
                )

        except Exception as exc:

            raise HTTPException(
                status_code=500,
                detail=(
                    f"Paper retrieval failed for "
                    f"paper {paper_id}: {exc}"
                ),
            )

    # --------------------------------------------------------
    # Build grounded context
    # --------------------------------------------------------

    context = build_context(
        retrieved_chunks
    )

    # --------------------------------------------------------
    # Generate grounded answer
    # --------------------------------------------------------

    answer = ask_gemini(
        question=message,
        context=context,
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
        citations=citations,
    )

    # --------------------------------------------------------
    # Return response
    # --------------------------------------------------------

    return {
        "answer": answer,
        "citations": citations,
        "chat_id": chat_id,
        "notebook_id": notebook_id,
    }


# ============================================================
# GET CHAT HISTORY
# ============================================================

@router.get("/chats")
def get_chat_history(
    user_id: str = Depends(
        get_current_user_id
    ),
):
    """
    Returns the current researcher's previous
    notebook conversations.
    """

    chats = notebook_chats_collection.find(
        {
            "user_id": str(user_id),
        },
        {
            "_id": 0,
            "chat_id": 1,
            "notebook_id": 1,
            "title": 1,
            "resource_ids": 1,
            "created_at": 1,
            "updated_at": 1,
        },
    ).sort(
        "updated_at",
        -1,
    )

    results = []

    for chat in chats:

        results.append({
            "chat_id": chat.get(
                "chat_id"
            ),
            "notebook_id": chat.get(
                "notebook_id"
            ),
            "title": chat.get(
                "title",
                "New Research Chat",
            ),
            "resource_ids": chat.get(
                "resource_ids",
                [],
            ),
            "created_at": chat.get(
                "created_at"
            ),
            "updated_at": chat.get(
                "updated_at"
            ),
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
    ),
):
    """
    Returns one complete notebook conversation.
    """

    chat = notebook_chats_collection.find_one(
        {
            "chat_id": chat_id,
            "user_id": str(user_id),
        },
        {
            "_id": 0,
        },
    )

    if not chat:

        raise HTTPException(
            status_code=404,
            detail="Chat not found.",
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
    ),
):
    """
    Deletes one notebook conversation belonging
    to the current researcher.
    """

    result = notebook_chats_collection.delete_one(
        {
            "chat_id": chat_id,
            "user_id": str(user_id),
        }
    )

    if result.deleted_count == 0:

        raise HTTPException(
            status_code=404,
            detail="Chat not found.",
        )

    return {
        "message": "Chat deleted successfully.",
        "chat_id": chat_id,
    }