
import json
import os
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

from graph_engine import EvidenceChunk, GeminiGraphModel, generate_graph


HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent

load_dotenv(BACKEND / ".env")

PAPER_IDS = [
    "646fc26c-04ed-406c-9669-15a6a75b3d77",
    "81670699-a813-424c-a4af-b8e51929238b",
]

MAX_CHUNKS_PER_PAPER = 6
SCROLL_PAGE_SIZE = 256


def get_local_qdrant_url():
    """Make Docker service URLs usable from a local Windows process."""
    url = os.getenv("QDRANT_URL", "http://localhost:6333").strip()
    parsed = urlparse(url)

    if parsed.hostname in {"qdrant", "mongodb", "backend"}:
        netloc = f"localhost:{parsed.port or 6333}"
        if parsed.username:
            credentials = parsed.username
            if parsed.password:
                credentials += f":{parsed.password}"
            netloc = f"{credentials}@{netloc}"

        parsed = parsed._replace(netloc=netloc)

    return urlunparse(parsed)


def create_qdrant_client():
    url = get_local_qdrant_url()
    api_key = os.getenv("QDRANT_API_KEY")

    print(f"Connecting to Qdrant at: {url}")

    options = {"url": url, "timeout": 15}
    if api_key:
        options["api_key"] = api_key

    return QdrantClient(**options)


def load_paper_chunks(client, collection, paper_id):
    """Read stored evidence directly, filtered to the selected paper."""
    records = []
    offset = None

    while True:
        points, next_offset = client.scroll(
            collection_name=collection,
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="paper_id",
                        match=MatchValue(value=paper_id),
                    )
                ]
            ),
            limit=SCROLL_PAGE_SIZE,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )

        for point in points:
            payload = point.payload or {}

            # Verify ownership even though the Qdrant filter is applied.
            if str(payload.get("paper_id", "")) != paper_id:
                continue

            text = payload.get("text")
            if not isinstance(text, str) or len(text.strip()) < 35:
                continue

            try:
                chunk_index = int(payload.get("chunk_index", 0))
            except (TypeError, ValueError):
                chunk_index = 0

            records.append({
                "chunk_index": chunk_index,
                "text": text.strip(),
                "title": payload.get("title"),
            })

        if next_offset is None or not points:
            break

        offset = next_offset

    records.sort(key=lambda record: record["chunk_index"])

    unique = []
    seen = set()

    for record in records:
        fingerprint = " ".join(record["text"].casefold().split())
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        unique.append(record)

    return unique


def sample_across_paper(records, limit):
    """Choose chunks spread across the paper's indexed content."""
    if len(records) <= limit:
        return records

    if limit <= 1:
        return [records[len(records) // 2]]

    indexes = [
        round(i * (len(records) - 1) / (limit - 1))
        for i in range(limit)
    ]

    return [records[index] for index in indexes]


def main():
    if not os.getenv("GEMINI_API_KEY", "").strip():
        raise RuntimeError(
            "GEMINI_API_KEY is missing. Check backend/.env without "
            "printing or sharing the key."
        )

    # Use the model previously reported as available in your account.
    os.environ["GEMINI_MODEL"] = "gemini-3.8-flash"

    collection = os.getenv("QDRANT_COLLECTION", "scibrain_papers")
    client = create_qdrant_client()

    try:
        collections = {
            item.name for item in client.get_collections().collections
        }

        if collection not in collections:
            raise RuntimeError(
                f"Qdrant collection '{collection}' was not found. "
                f"Available collections: {sorted(collections)}"
            )

        chunks = []
        input_report = []

        for paper_id in PAPER_IDS:
            records = load_paper_chunks(client, collection, paper_id)

            if not records:
                input_report.append({
                    "paper_id": paper_id,
                    "indexed_chunks_found": 0,
                    "sampled_chunks": 0,
                    "title": None,
                    "warning": (
                        "No indexed chunks matched this exact paper ID. "
                        "Verify the selected IDs and Qdrant collection."
                    ),
                })
                continue

            title = next(
                (
                    str(record["title"])
                    for record in records
                    if record.get("title")
                ),
                f"Paper {paper_id}",
            )

            sampled = sample_across_paper(
                records, MAX_CHUNKS_PER_PAPER
            )

            input_report.append({
                "paper_id": paper_id,
                "title": title,
                "indexed_chunks_found": len(records),
                "sampled_chunks": len(sampled),
                "chunk_indexes_sampled": [
                    record["chunk_index"] for record in sampled
                ],
            })

            for record in sampled:
                chunks.append(
                    EvidenceChunk(
                        chunk_id=(
                            f"{paper_id}-chunk-{record['chunk_index']}"
                        ),
                        paper_id=paper_id,
                        paper_title=title,
                        text=record["text"],
                    )
                )

        print("\nInput coverage:")
        print(json.dumps(input_report, indent=2, ensure_ascii=False))

        if not chunks:
            raise RuntimeError(
                "No evidence chunks were loaded. Check the IDs, "
                "collection, and Qdrant connection."
            )

        print(f"\nLoaded {len(chunks)} evidence chunks.")
        print("Starting independent graph extraction...")

        model = GeminiGraphModel()
        result = generate_graph(chunks, model)
        graph = result.to_dict()

        report = {
            "test": "SciBrain independent engine real-paper regression",
            "model": os.environ["GEMINI_MODEL"],
            "collection": collection,
            "input_coverage": input_report,
            "graph": graph,
        }

        output_path = HERE / "real_paper_graph_report.json"
        output_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

        print("\nGraph statistics:")
        print(json.dumps(
            graph.get("statistics", {}),
            indent=2,
            ensure_ascii=False,
        ))
        print(f"\nAccepted nodes: {len(graph.get('nodes', []))}")
        print(f"Accepted edges: {len(graph.get('edges', []))}")
        print(f"Report saved to: {output_path}")

    finally:
        client.close()


if __name__ == "__main__":
    main()
