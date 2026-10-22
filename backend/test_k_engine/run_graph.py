
import json

from graph_engine import (
    EvidenceChunk,
    GeminiGraphModel,
    generate_graph,
)

chunks = [
    EvidenceChunk(
        chunk_id="paper1-section1",
        paper_id="paper1",
        paper_title="Example Scientific Study",
        text=(
            "The researchers developed CropNet. "
            "CropNet predicts crop yield using satellite imagery."
        ),
    )
]

model = GeminiGraphModel()
result = generate_graph(chunks, model)

print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
