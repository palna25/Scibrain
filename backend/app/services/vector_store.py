import os
import uuid
from typing import List, Dict, Any

import requests

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchAny,
    MatchValue,
)


# ============================================================
# CONFIGURATION
# ============================================================

QDRANT_URL = os.getenv(
    "QDRANT_URL",
    "http://qdrant:6333",
)

QDRANT_COLLECTION = os.getenv(
    "QDRANT_COLLECTION",
    "scibrain_papers",
)

# Ollama embedding model.
#
# Recommended:
#   nomic-embed-text
#
# You can change this through .env without changing the code.
EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "nomic-embed-text",
)

# Inside Docker Desktop, host.docker.internal points to
# the Windows host where Ollama is normally running.
OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://host.docker.internal:11434",
)

OLLAMA_EMBED_TIMEOUT = int(
    os.getenv("OLLAMA_EMBED_TIMEOUT", "120")
)


# ============================================================
# CLIENTS
# ============================================================

qdrant_client = QdrantClient(
    url=QDRANT_URL
)


# ============================================================
# OLLAMA EMBEDDINGS
# ============================================================

def create_embeddings(
    texts: List[str],
) -> List[List[float]]:
    """
    Generate embeddings using the local Ollama embedding model.

    Ollama returns one embedding vector for each supplied text.
    """

    if not texts:
        return []

    cleaned_texts = [
        text.strip()
        for text in texts
        if text and text.strip()
    ]

    if not cleaned_texts:
        return []

    try:
        response = requests.post(
            f"{OLLAMA_URL.rstrip('/')}/api/embed",
            json={
                "model": EMBEDDING_MODEL,
                "input": cleaned_texts,
            },
            timeout=OLLAMA_EMBED_TIMEOUT,
        )

    except requests.RequestException as error:
        raise RuntimeError(
            f"Could not connect to Ollama at "
            f"{OLLAMA_URL}: {error}"
        )

    if response.status_code != 200:
        raise RuntimeError(
            f"Ollama embedding request failed "
            f"with HTTP {response.status_code}: "
            f"{response.text[:1000]}"
        )

    try:
        data = response.json()
    except ValueError as error:
        raise RuntimeError(
            f"Ollama returned invalid JSON: {error}"
        )

    embeddings = data.get("embeddings")

    if not isinstance(embeddings, list):
        raise RuntimeError(
            "Ollama did not return an 'embeddings' array."
        )

    if len(embeddings) != len(cleaned_texts):
        raise RuntimeError(
            "Ollama returned a different number of embeddings "
            "than the number of input texts."
        )

    return embeddings


# ============================================================
# COLLECTION
# ============================================================

def ensure_collection(
    vector_size: int,
) -> None:
    """
    Create the Qdrant collection if it does not exist.

    The vector size is determined from the actual Ollama
    embedding response rather than being hard-coded.
    """

    existing_collections = qdrant_client.get_collections()

    collection_names = {
        collection.name
        for collection in existing_collections.collections
    }

    if QDRANT_COLLECTION not in collection_names:

        qdrant_client.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=VectorParams(
                size=vector_size,
                distance=Distance.COSINE,
            ),
        )


# ============================================================
# TEXT CHUNKING
# ============================================================

def chunk_text(
    text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 150,
) -> List[str]:
    """
    Split extracted paper text into overlapping chunks.

    Chunking is deterministic so the same paper can be
    consistently indexed and retrieved.
    """

    if not text:
        return []

    text = text.strip()

    if not text:
        return []

    chunks = []

    start = 0
    text_length = len(text)

    while start < text_length:

        end = min(
            start + chunk_size,
            text_length,
        )

        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= text_length:
            break

        start = max(
            end - chunk_overlap,
            start + 1,
        )

    return chunks


# ============================================================
# INDEX PAPER
# ============================================================

def index_paper_chunks(
    paper_id: str,
    text: str,
    title: str | None = None,
) -> int:
    """
    Chunk a research paper, generate embeddings through Ollama,
    and store the chunks in Qdrant.

    Returns:
        Number of indexed chunks.
    """

    paper_id = str(paper_id)

    chunks = chunk_text(text)

    if not chunks:
        return 0

    # --------------------------------------------------------
    # Generate embeddings first.
    # This allows us to determine the vector dimension
    # dynamically from the configured Ollama model.
    # --------------------------------------------------------

    embeddings = create_embeddings(chunks)

    if not embeddings:
        return 0

    vector_size = len(embeddings[0])

    ensure_collection(vector_size)

    # --------------------------------------------------------
    # Remove existing chunks for this paper before re-indexing.
    #
    # This prevents duplicate/stale chunks when a paper is
    # indexed more than once.
    # --------------------------------------------------------

    delete_paper_chunks(
        paper_id,
        ensure_exists=False,
    )

    # --------------------------------------------------------
    # Build Qdrant points.
    # --------------------------------------------------------

    points = []

    for index, (chunk, embedding) in enumerate(
        zip(chunks, embeddings)
    ):

        payload = {
            "paper_id": paper_id,
            "chunk_index": index,
            "text": chunk,
        }

        if title:
            payload["title"] = title

        points.append(
            PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload=payload,
            )
        )

    # --------------------------------------------------------
    # Store vectors in Qdrant.
    # --------------------------------------------------------

    qdrant_client.upsert(
        collection_name=QDRANT_COLLECTION,
        points=points,
    )

    return len(points)


# ============================================================
# SEARCH
# ============================================================

def search_paper_chunks(
    query: str,
    paper_ids: List[str] | None = None,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """
    Search Qdrant for chunks relevant to a researcher query.

    If paper_ids are provided, retrieval is restricted to those
    selected research resources.

    This is the main retrieval function used by the
    Research Notebook RAG workflow.
    """

    query = query.strip()

    if not query:
        return []

    # --------------------------------------------------------
    # Embed the researcher's question using the SAME embedding
    # model used when indexing papers.
    # --------------------------------------------------------

    embeddings = create_embeddings([query])

    if not embeddings:
        return []

    query_embedding = embeddings[0]

    ensure_collection(
        len(query_embedding)
    )

    # --------------------------------------------------------
    # Restrict retrieval to selected research resources.
    # --------------------------------------------------------

    query_filter = None

    if paper_ids:

        selected_ids = [
            str(paper_id)
            for paper_id in paper_ids
            if paper_id is not None
        ]

        if selected_ids:

            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="paper_id",
                        match=MatchAny(
                            any=selected_ids
                        ),
                    )
                ]
            )

    # --------------------------------------------------------
    # Vector similarity search.
    # --------------------------------------------------------

    results = qdrant_client.query_points(
        collection_name=QDRANT_COLLECTION,
        query=query_embedding,
        query_filter=query_filter,
        limit=limit,
        with_payload=True,
    )

    formatted_results = []

    for result in results.points:

        payload = result.payload or {}

        formatted_results.append(
            {
                "id": str(result.id),
                "score": result.score,
                "paper_id": payload.get("paper_id"),
                "chunk_index": payload.get("chunk_index"),
                "title": payload.get("title"),
                "text": payload.get("text", ""),
            }
        )

    return formatted_results


# ============================================================
# DELETE PAPER
# ============================================================

def delete_paper_chunks(
    paper_id: str,
    ensure_exists: bool = True,
) -> None:
    """
    Remove all Qdrant chunks belonging to a research resource.

    Used when:
        - a paper is deleted
        - a paper is re-indexed
    """

    paper_id = str(paper_id)

    if ensure_exists:

        existing_collections = (
            qdrant_client.get_collections()
        )

        collection_names = {
            collection.name
            for collection in existing_collections.collections
        }

        if QDRANT_COLLECTION not in collection_names:
            return

    qdrant_client.delete(
        collection_name=QDRANT_COLLECTION,
        points_selector=Filter(
            must=[
                FieldCondition(
                    key="paper_id",
                    match=MatchValue(
                        value=paper_id,
                    ),
                )
            ]
        ),
    )
    # ============================================================
# DELETE PAPER CHUNKS
# ============================================================

def delete_paper_chunks(
    paper_id: str,
    ensure_exists: bool = True,
) -> None:
    """
    Remove all Qdrant chunks belonging to a research resource.

    Used when:
        - a paper is deleted
        - a paper is re-indexed
    """

    paper_id = str(paper_id)

    if ensure_exists:

        existing_collections = (
            qdrant_client.get_collections()
        )

        collection_names = {
            collection.name
            for collection in existing_collections.collections
        }

        if QDRANT_COLLECTION not in collection_names:
            return

    qdrant_client.delete(
        collection_name=QDRANT_COLLECTION,
        points_selector=Filter(
            must=[
                FieldCondition(
                    key="paper_id",
                    match=MatchValue(
                        value=paper_id,
                    ),
                )
            ]
        ),
    )