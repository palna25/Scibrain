from app.routes import knowledge_graph
import requests
import os

paper_id = "5679161b-084a-4df5-b794-77f3c4f30052"

chunks = knowledge_graph.search_paper_chunks(
    "Turing Test machine thinking Alan Turing Imitation Game",
    paper_ids=[paper_id],
    limit=5,
)

print("CHUNKS:", len(chunks))

for c in chunks:
    print("\n--- CHUNK", c["chunk_index"], "---")
    print(c["text"][:1200])

context = "\n\n".join(
    f'CHUNK {c["chunk_index"]}:\n{c["text"]}'
    for c in chunks
)

prompt = """
Extract named entities from the supplied text.

Return ONLY JSON in exactly this format:

{
  "entities": [
    {
      "name": "entity name",
      "type": "person|method|concept",
      "evidence": "exact words copied from the text"
    }
  ]
}

Rules:
- Only extract entities explicitly present in the text.
- Do not use outside knowledge.
- Evidence must be copied exactly from the supplied text.
- Include Alan Turing if he appears.
- Include Turing Test if it appears.
- Include Imitation Game if it appears.
- Do not return an empty list if these entities are explicitly present.
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
