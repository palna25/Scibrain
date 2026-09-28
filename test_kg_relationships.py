from app.routes import knowledge_graph
import requests
import os

paper_id = "5679161b-084a-4df5-b794-77f3c4f30052"

chunks = knowledge_graph.search_paper_chunks(
    "Alan Turing Turing Test Imitation Game Computing Machinery Intelligence proposed based",
    paper_ids=[paper_id],
    limit=6,
)

print("CHUNKS:", len(chunks))

context = "\n\n".join(
    f'CHUNK {c["chunk_index"]}:\n{c["text"]}'
    for c in chunks
)

prompt = """
Extract only relationships that are explicitly supported by the supplied text.

Return ONLY valid JSON in exactly this format:

{
  "relationships": [
    {
      "source": "entity name",
      "target": "entity name",
      "relationship": "authored_by|uses|evaluated_on|discusses|reports|related_to",
      "evidence": "short exact quote from the supplied text"
    }
  ]
}

Rules:
- Only use entities explicitly present in the supplied text.
- Only create a relationship when the text explicitly supports it.
- Do not use outside knowledge.
- Evidence MUST be copied exactly from the supplied text.
- The evidence must contain enough information to support the relationship.
- Do not invent relationships.
- Do not include explanations or markdown.
"""

r = requests.post(
    os.getenv("OLLAMA_URL") + "/api/chat",
    json={
        "model": os.getenv("OLLAMA_MODEL"),
        "messages": [
            {
                "role": "system",
                "content": prompt,
            },
            {
                "role": "user",
                "content": context,
            },
        ],
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0,
        },
    },
    timeout=240,
)

print("\n--- OLLAMA RESPONSE ---")
print("STATUS:", r.status_code)
print(r.text)
