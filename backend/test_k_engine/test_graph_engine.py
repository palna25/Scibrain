# test_graph_engine.py
import unittest

from graph_engine import (
    EvidenceChunk,
    EntityCandidate,
    RelationshipCandidate,
    EvidenceGraphBuilder,
    QuotaExhausted,
    generate_graph,
    normalize_name,
    quote_in_source,
)


class FakeVerifier:
    def __init__(self, supported=True):
        self.supported = supported
        self.calls = 0

    def verify_relationships(self, items):
        self.calls += 1
        return {
            item["candidate_id"]: {
                "supported": self.supported,
                "reason": "Test verifier verdict",
            }
            for item in items
        }


class FakeModel(FakeVerifier):
    def __init__(self, extraction_results, supported=True):
        super().__init__(supported=supported)
        self.extraction_results = extraction_results
        self.extraction_calls = 0
        self.request_count = 0
        self.retry_count = 0
        self.quota_exhausted = False
        self.model_name = "FakeModel"

    def extract_many(self, chunks):
        self.extraction_calls += 1
        self.request_count += 1
        return {
            chunk.chunk_id: self.extraction_results.get(
                chunk.chunk_id,
                {"entities": [], "relationships": []},
            )
            for chunk in chunks
        }


def sample_chunk(
    chunk_id="c1",
    paper_id="p1",
    text="RAGLAB uses dense retrieval to retrieve relevant passages.",
):
    return EvidenceChunk(
        chunk_id=chunk_id,
        paper_id=paper_id,
        paper_title=f"Paper {paper_id}",
        text=text,
    )


def sample_candidates(chunk):
    quote = "RAGLAB uses dense retrieval to retrieve relevant passages."
    entities = [
        EntityCandidate(chunk.chunk_id, "RAGLAB", "method", quote),
        EntityCandidate(chunk.chunk_id, "dense retrieval", "method", quote),
    ]
    relations = [
        RelationshipCandidate(
            chunk.chunk_id, "RAGLAB", "uses", "dense retrieval", quote
        )
    ]
    return entities, relations


class GraphEngineTests(unittest.TestCase):
    def test_normalization_preserves_scientific_distinctions(self):
        self.assertEqual(normalize_name("Graph-RAG"), "graph rag")
        self.assertEqual(normalize_name("Graph_RAG"), "graph rag")
        self.assertNotEqual(normalize_name("RAG"), normalize_name("RAGLAB"))
        self.assertNotEqual(
            normalize_name("Llama 3 8B"),
            normalize_name("Llama 3 70B"),
        )

    def test_quote_match_handles_pdf_line_wrapping(self):
        source = "Retrieval-augmented\n generation improves retrieval."
        quote = "Retrieval-augmented generation improves retrieval."
        self.assertTrue(quote_in_source(quote, source))

    def test_fabricated_entity_quote_is_rejected(self):
        chunk = sample_chunk()
        builder = EvidenceGraphBuilder()
        result = builder.build(
            [chunk],
            [
                EntityCandidate(
                    "c1", "RAGLAB", "method",
                    "This fabricated sentence is not in the paper.",
                )
            ],
            [],
        )
        self.assertEqual(result.nodes, [])
        self.assertEqual(
            result.rejected_entities[0]["reason"],
            "quote_not_in_source",
        )

    def test_entity_must_appear_in_its_own_quote(self):
        chunk = sample_chunk()
        builder = EvidenceGraphBuilder()
        result = builder.build(
            [chunk],
            [
                EntityCandidate(
                    "c1", "Llama 3", "model",
                    "RAGLAB uses dense retrieval to retrieve relevant passages.",
                )
            ],
            [],
        )
        self.assertEqual(result.nodes, [])
        self.assertEqual(
            result.rejected_entities[0]["reason"],
            "entity_not_identifiable_in_quote",
        )

    def test_valid_relationship_is_accepted_with_evidence(self):
        chunk = sample_chunk()
        entities, relations = sample_candidates(chunk)
        verifier = FakeVerifier(supported=True)

        result = EvidenceGraphBuilder().build(
            [chunk], entities, relations, verifier=verifier
        )

        self.assertEqual(len(result.nodes), 2)
        self.assertEqual(len(result.edges), 1)
        self.assertEqual(result.edges[0].relation, "uses")
        self.assertEqual(len(result.edges[0].evidence), 1)
        self.assertEqual(result.edges[0].evidence[0].paper_id, "p1")

    def test_semantically_rejected_relationship_is_not_added(self):
        chunk = sample_chunk()
        entities, relations = sample_candidates(chunk)
        result = EvidenceGraphBuilder().build(
            [chunk], entities, relations, verifier=FakeVerifier(False)
        )

        self.assertEqual(result.edges, [])
        self.assertEqual(
            result.rejected_relationships[0]["reason"],
            "semantic_verification_failed",
        )

    def test_both_endpoints_must_appear_in_relationship_quote(self):
        chunk = sample_chunk()
        builder = EvidenceGraphBuilder()
        entities = [
            EntityCandidate("c1", "RAGLAB", "method", chunk.text),
            EntityCandidate("c1", "dense retrieval", "method", chunk.text),
        ]
        relations = [
            RelationshipCandidate(
                "c1",
                "RAGLAB",
                "uses",
                "dense retrieval",
                "RAGLAB is a modular research framework.",
            )
        ]
        result = builder.build(
            [chunk], entities, relations, verifier=FakeVerifier(True)
        )

        self.assertEqual(result.edges, [])
        self.assertIn(
            result.rejected_relationships[0]["reason"],
            {"source_not_in_evidence", "target_not_in_evidence"},
        )

    def test_unknown_chunk_is_rejected(self):
        chunk = sample_chunk()
        result = EvidenceGraphBuilder().build(
            [chunk],
            [],
            [
                RelationshipCandidate(
                    "missing-chunk",
                    "RAGLAB",
                    "uses",
                    "dense retrieval",
                    "RAGLAB uses dense retrieval.",
                )
            ],
            verifier=FakeVerifier(True),
        )
        self.assertEqual(result.edges, [])
        self.assertEqual(
            result.rejected_relationships[0]["reason"],
            "unknown_chunk",
        )

    def test_rejection_diagnostics_keep_candidate_details(self):
        chunk = sample_chunk()
        result = EvidenceGraphBuilder().build(
            [chunk],
            [],
            [
                RelationshipCandidate(
                    "c1", "RAGLAB", "uses", "dense retrieval",
                    "This sentence is not in the source.",
                )
            ],
        )
        rejected = result.rejected_relationships[0]
        self.assertEqual(rejected["source"], "RAGLAB")
        self.assertEqual(rejected["relation"], "uses")
        self.assertEqual(rejected["target"], "dense retrieval")
        self.assertTrue(rejected["evidence"])

    def test_verifier_unavailable_is_not_semantic_rejection(self):
        chunk = sample_chunk()
        entities, relations = sample_candidates(chunk)
        builder = EvidenceGraphBuilder()

        class BrokenVerifier:
            def verify_relationships(self, items):
                raise RuntimeError("provider unavailable")

        result = builder.build(
            [chunk], entities, relations, verifier=BrokenVerifier()
        )
        reasons = {
            item["reason"] for item in result.rejected_relationships
        }
        self.assertIn("verification_unavailable", reasons)
        self.assertNotIn("semantic_verification_failed", reasons)

    def test_batch_verifier_is_called_once_for_small_graph(self):
        chunk = sample_chunk()
        entities, relations = sample_candidates(chunk)
        verifier = FakeVerifier(True)
        result = EvidenceGraphBuilder().build(
            [chunk], entities, relations, verifier=verifier
        )
        self.assertEqual(verifier.calls, 1)
        self.assertEqual(len(result.edges), 1)

    def test_generate_graph_extracts_multiple_chunks_in_one_batch(self):
        chunks = [
            sample_chunk("c1", "p1"),
            sample_chunk("c2", "p2"),
        ]
        results = {
            "c1": {
                "entities": [
                    {"name": "RAGLAB", "type": "method",
                     "quote": chunks[0].text},
                    {"name": "dense retrieval", "type": "method",
                     "quote": chunks[0].text},
                ],
                "relationships": [
                    {"source": "RAGLAB", "relation": "uses",
                     "target": "dense retrieval", "quote": chunks[0].text}
                ],
            },
            "c2": {"entities": [], "relationships": []},
        }
        model = FakeModel(results)
        result = generate_graph(chunks, model=model)

        self.assertEqual(model.extraction_calls, 1)
        self.assertEqual(len(result.nodes), 2)
        self.assertEqual(len(result.edges), 1)

    def test_duplicate_relationship_merges_evidence(self):
        chunk1 = sample_chunk("c1", "p1")
        chunk2 = sample_chunk("c2", "p2")
        chunks = [chunk1, chunk2]
        entities = []
        relations = []

        for chunk in chunks:
            entities.extend([
                EntityCandidate(
                    chunk.chunk_id, "RAGLAB", "method", chunk.text
                ),
                EntityCandidate(
                    chunk.chunk_id, "dense retrieval", "method", chunk.text
                ),
            ])
            relations.append(RelationshipCandidate(
                chunk.chunk_id, "RAGLAB", "uses",
                "dense retrieval", chunk.text
            ))

        result = EvidenceGraphBuilder().build(
            chunks, entities, relations, verifier=FakeVerifier(True)
        )
        self.assertEqual(len(result.edges), 1)
        self.assertEqual(len(result.edges[0].evidence), 2)

    def test_missing_verifier_verdict_fails_closed(self):
        chunk = sample_chunk()
        entities, relations = sample_candidates(chunk)

        class MissingVerdict:
            def verify_relationships(self, items):
                return {}

        result = EvidenceGraphBuilder().build(
            [chunk], entities, relations, verifier=MissingVerdict()
        )
        self.assertEqual(result.edges, [])
        self.assertEqual(
            result.rejected_relationships[0]["reason"],
            "semantic_verification_failed",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)