import pytest
from app.services.graph_engine.schemas import KnowledgeGraph
from app.services.graph_engine.retrieval import retrieve_graph_evidence, EvidenceRetrievalError
from app.services.graph_engine.extraction import extract_graph_candidates, ExtractionError
from app.services.graph_engine.resolution import resolve_entities
from app.services.graph_engine.validation import validate_relationships, RelationshipValidationError
from app.services.graph_engine.finalization import finalize_graph, GraphFinalizationError
from app.services.graph_engine.config import GraphEngineSettings

class Collection:
    def __init__(self, docs): self.docs=docs
    def find_one(self, query): return self.docs.get(query["_id"])

def ev(pid="p1", cid="c1", quote="Graph RAG method"):
    return {"paper_id":pid,"chunk_id":cid,"quote":quote}

def test_retrieval_excludes_unready_and_foreign_chunks():
    collection=Collection({"p1":{"_id":"p1","status":"ready","indexed_chunks":1},"p2":{"_id":"p2","status":"processing","indexed_chunks":1}})
    def search_fn(*,query,paper_ids,limit):
        return [{"id":"c1","paper_id":"p1","chunk_index":0,"text":"Graph RAG method","score":0.8},{"id":"foreign","paper_id":"p2","text":"foreign chunk"}]
    settings=GraphEngineSettings(retrieval_limit=1,max_chunks_per_paper=4,max_total_chunks=4,max_chunks_per_category=1)
    result=retrieve_graph_evidence(["p1","p2"],paper_collection=collection,search_fn=search_fn,settings=settings)
    assert {x["paper_id"] for x in result["chunks"]}=={"p1"}
    assert result["stats"]["rejected_papers"]==[{"paper_id":"p2","reason":"not_ready"}]

def test_extraction_keeps_batch_cross_references_until_all_batches_processed():
    chunks=[{"chunk_id":"c1","paper_id":"p1","text":"Graph RAG method proposes retrieval."},{"chunk_id":"c2","paper_id":"p1","text":"Graph RAG method proposes retrieval."}]
    def gen(prompt):
        if '"chunk_id": "c1"' in prompt:
            return {"entities":[{"name":"Graph RAG","type":"method","evidence":[ev(cid="c1")]},{"name":"retrieval","type":"concept","evidence":[ev(cid="c1",quote="retrieval")] }],"relationships":[{"source":"Graph RAG","target":"retrieval","type":"uses","confidence":0.9,"evidence":[ev(cid="c1",quote="Graph RAG method proposes retrieval.")]}]}
        return {"entities":[{"name":"Graph RAG","type":"method","evidence":[ev(cid="c2")]},{"name":"retrieval","type":"concept","evidence":[ev(cid="c2",quote="retrieval")]}],"relationships":[]}
    result=extract_graph_candidates(chunks,generator=gen,batch_size=1)
    assert len(result["entities"])==2
    assert len(result["relationships"])==1

def test_resolution_drops_edge_that_becomes_self_edge():
    result=resolve_entities([{"entity_id":"a","canonical_name":"Graph RAG","type":"method","evidence":[ev()]},{"entity_id":"b","canonical_name":"graph rag","type":"method","evidence":[ev(cid="c2")]}],[{"source":"a","target":"b","type":"uses","confidence":0.9,"evidence":[ev()]}])
    assert len(result["entities"])==1
    assert result["relationships"]==[]

def test_validation_fails_closed_on_semantic_verifier_error():
    entities=[{"entity_id":"a","paper_ids":["p1"],"evidence":[ev()]},{"entity_id":"b","paper_ids":["p1"],"evidence":[ev()]}]
    rel=[{"source":"a","target":"b","type":"uses","confidence":0.9,"evidence":[ev()]}]
    with pytest.raises(RelationshipValidationError, match="Semantic verification failed"):
        validate_relationships(entities,rel,[{"chunk_id":"c1","paper_id":"p1","text":"Graph RAG method"}],semantic_verifier=lambda *args: (_ for _ in ()).throw(RuntimeError("offline")))

def test_validation_rejects_nan_confidence():
    entities=[{"entity_id":"a","paper_ids":["p1"],"evidence":[ev()]},{"entity_id":"b","paper_ids":["p1"],"evidence":[ev()]}]
    result=validate_relationships(entities,[{"source":"a","target":"b","type":"uses","confidence":float("nan"),"evidence":[ev()]}],[{"chunk_id":"c1","paper_id":"p1","text":"Graph RAG method"}],semantic_verifier=lambda *a:{"supported":True,"direction_correct":True,"confidence":0.99})
    assert not result["relationships"]

def test_finalization_requires_semantic_validation():
    nodes=[{"entity_id":"a","canonical_name":"Graph RAG","type":"method","paper_ids":["p1"],"evidence":[ev()]},{"entity_id":"b","canonical_name":"method","type":"concept","paper_ids":["p1"],"evidence":[ev()]}]
    edges=[{"source":"a","target":"b","type":"uses","confidence":0.9,"evidence":[ev()]}]
    graph=finalize_graph(["p1"],nodes,edges,[{"chunk_id":"c1","paper_id":"p1","text":"Graph RAG method"}])
    assert graph["edges"]==[]

def test_finalization_rejects_unselected_evidence():
    graph=finalize_graph(["p1"],[{"entity_id":"e","canonical_name":"Method","type":"method","paper_ids":["p2"],"evidence":[{"paper_id":"p2","chunk_id":"c2","quote":"Method"}]}],[],[{"chunk_id":"c2","paper_id":"p2","text":"Method"}])
    assert graph["nodes"]==[]

def test_schema_rejects_duplicate_nodes_and_unknown_endpoints():
    with pytest.raises(Exception):
        KnowledgeGraph.model_validate({"graph_id":"g","resource_ids":["p1"],"nodes":[{"entity_id":"a","canonical_name":"x","type":"method"},{"entity_id":"a","canonical_name":"y","type":"method"}]})


def test_extraction_retries_transient_gemini_failure(monkeypatch):
    import app.services.graph_engine.extraction as extraction
    monkeypatch.setattr(extraction.time, "sleep", lambda _seconds: None)
    calls = {"count": 0}
    chunks = [{"chunk_id": "c1", "paper_id": "p1", "text": "Graph RAG method"}]

    def generator(_prompt):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("503 UNAVAILABLE: temporary overload")
        return {"entities": [{"name": "Graph RAG", "type": "method", "evidence": [ev()]}], "relationships": []}

    result = extract_graph_candidates(chunks, generator=generator)
    assert calls["count"] == 2
    assert result["stats"]["retries"] == 1
    assert result["stats"]["successful_batches"] == 1


def test_validation_retries_transient_semantic_verifier_failure(monkeypatch):
    import app.services.graph_engine.validation as validation
    monkeypatch.setattr(validation.time, "sleep", lambda _seconds: None)
    entities = [
        {"entity_id": "a", "paper_ids": ["p1"], "evidence": [ev()]},
        {"entity_id": "b", "paper_ids": ["p1"], "evidence": [ev()]},
    ]
    relationships = [{"source": "a", "target": "b", "type": "uses", "confidence": 0.9, "evidence": [ev()]}]
    calls = {"count": 0}

    def verifier(*_args):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("503 UNAVAILABLE: temporary overload")
        return {"supported": True, "direction_correct": True, "confidence": 0.95, "reason": "Explicitly supported"}

    result = validate_relationships(entities, relationships, [{"chunk_id": "c1", "paper_id": "p1", "text": "Graph RAG method"}], semantic_verifier=verifier)
    assert calls["count"] == 2
    assert len(result["relationships"]) == 1
    assert result["stats"]["retries"] == 1


def test_validation_rejects_demonstrated_by_mislabelled_as_authored_by():
    quote = "iterative retrieval-generation models, as demonstrated by Shuster"
    entities = [
        {"entity_id": "method", "canonical_name": "iterative retrieval-generation models", "type": "method", "paper_ids": ["p1"], "evidence": [{"paper_id": "p1", "chunk_id": "c1", "quote": quote}]},
        {"entity_id": "person", "canonical_name": "Shuster", "type": "author", "paper_ids": ["p1"], "evidence": [{"paper_id": "p1", "chunk_id": "c1", "quote": quote}]},
    ]
    relationships = [{"source": "method", "target": "person", "type": "authored_by", "confidence": 1.0, "evidence": [{"paper_id": "p1", "chunk_id": "c1", "quote": quote}]}]
    result = validate_relationships(
        entities, relationships, [{"chunk_id": "c1", "paper_id": "p1", "text": quote}],
        semantic_verifier=lambda *_: {"supported": True, "direction_correct": True, "confidence": 1.0},
    )
    assert result["relationships"] == []
    assert result["rejected_relationships"][0]["rejection_reason"] == "authored_by_predicate_mismatch"


def test_validation_rejects_reversed_proposes_relationship():
    quote = "The GPL method was proposed by Wang Kexin."
    entities = [
        {"entity_id": "gpl", "canonical_name": "GPL method", "type": "method", "paper_ids": ["p1"], "evidence": [{"paper_id": "p1", "chunk_id": "c1", "quote": quote}]},
        {"entity_id": "wang", "canonical_name": "Wang Kexin", "type": "author", "paper_ids": ["p1"], "evidence": [{"paper_id": "p1", "chunk_id": "c1", "quote": quote}]},
    ]
    relationships = [{"source": "gpl", "target": "wang", "type": "proposes", "confidence": 1.0, "evidence": [{"paper_id": "p1", "chunk_id": "c1", "quote": quote}]}]
    result = validate_relationships(
        entities, relationships, [{"chunk_id": "c1", "paper_id": "p1", "text": quote}],
        semantic_verifier=lambda *_: {"supported": True, "direction_correct": True, "confidence": 1.0},
    )
    assert result["relationships"] == []
    assert result["rejected_relationships"][0]["rejection_reason"] == "proposes_direction_reversed"


def test_validation_accepts_explicit_developed_by_relationship():
    quote = "GraphRAG was developed by Microsoft."
    entities = [
        {"entity_id": "graphrag", "canonical_name": "GraphRAG", "type": "tool", "paper_ids": ["p1"], "evidence": [{"paper_id": "p1", "chunk_id": "c1", "quote": quote}]},
        {"entity_id": "microsoft", "canonical_name": "Microsoft", "type": "organization", "paper_ids": ["p1"], "evidence": [{"paper_id": "p1", "chunk_id": "c1", "quote": quote}]},
    ]
    relationships = [{"source": "graphrag", "target": "microsoft", "type": "developed_by", "confidence": 0.95, "evidence": [{"paper_id": "p1", "chunk_id": "c1", "quote": quote}]}]
    result = validate_relationships(
        entities, relationships, [{"chunk_id": "c1", "paper_id": "p1", "text": quote}],
        semantic_verifier=lambda *_: {"supported": True, "direction_correct": True, "confidence": 0.95, "reason": "Explicit development wording"},
    )
    assert len(result["relationships"]) == 1


def test_retrieval_filters_bibliography_and_affiliation_chunks():
    collection = Collection({"p1": {"_id": "p1", "status": "ready", "indexed_chunks": 3}})
    chunks = [
        {"id": "body", "paper_id": "p1", "chunk_index": 2, "text": "We propose a retrieval method that improves answer grounding."},
        {"id": "affiliation", "paper_id": "p1", "chunk_index": 0, "text": "Jiafeng Gu * School of CS and Math, University of Puget Sound, WA, United States"},
        {"id": "reference", "paper_id": "p1", "chunk_index": 30, "text": "Chi-Min Chan, Chunpu Xu, Ruibin Yuan, Hongyin Luo, Wei Xue, Yike Guo, and Jie Fu. 2024. Rq-rag: Learning to refine queries for retrieval augmented generation."},
    ]
    def search_fn(*, query, paper_ids, limit):
        return chunks
    settings = GraphEngineSettings(retrieval_limit=3, max_chunks_per_paper=10, max_total_chunks=10, max_chunks_per_category=3)
    result = retrieve_graph_evidence(["p1"], paper_collection=collection, search_fn=search_fn, settings=settings)
    assert {chunk["chunk_id"] for chunk in result["chunks"]} == {"body"}
    assert result["stats"]["filtered_chunks"]["front_matter_affiliation"] >= 1
    assert result["stats"]["filtered_chunks"]["bibliography_entry"] >= 1


def test_retrieval_does_not_filter_normal_related_work_prose():
    from app.services.graph_engine.retrieval import _is_nonresearch_chunk
    assert _is_nonresearch_chunk("Prior work by Asai et al. introduced Self-RAG, which combines retrieval and generation.") is None


def test_extraction_rejects_affiliation_and_bibliography_quote_entities():
    chunks = [{"chunk_id": "c1", "paper_id": "p1", "text": "Jiafeng Gu * School of CS and Math, University of Puget Sound, WA, United States. We propose a method for retrieval."}]
    def gen(_prompt):
        return {"entities": [
            {"name": "University of Puget Sound", "type": "organization", "evidence": [ev(quote="Jiafeng Gu * School of CS and Math, University of Puget Sound, WA, United States")]},
            {"name": "retrieval method", "type": "method", "evidence": [ev(quote="We propose a method for retrieval.")]},
        ], "relationships": []}
    result = extract_graph_candidates(chunks, generator=gen)
    assert [e["canonical_name"] for e in result["entities"]] == ["retrieval method"]


def test_finalization_exposes_missing_endpoint_details_and_rejection_counts():
    quote = "Graph RAG method uses retrieval"
    nodes = [{"entity_id": "a", "canonical_name": "Graph RAG", "type": "method", "paper_ids": ["p1"], "evidence": [ev(quote=quote)]}]
    edges = [{"relationship_id": "r1", "source": "a", "target": "missing", "type": "uses", "confidence": 0.9, "evidence": [ev(quote=quote)], "validation": {"status": "accepted", "semantic_support": True, "direction_correct": True}}]
    graph = finalize_graph(["p1"], nodes, edges, [{"chunk_id": "c1", "paper_id": "p1", "text": quote}])
    rejected = graph["audit"]["rejected_relationships"][0]
    assert rejected["missing_target"] is True
    assert rejected["target"] == "missing"
    assert graph["quality"]["rejected_relationship_reasons"]["missing_or_invalid_endpoint"] == 1


def test_verifier_quota_error_is_indeterminate_not_semantic_rejection(monkeypatch):
    import app.services.graph_engine.validation as validation
    monkeypatch.setattr(validation.time, "sleep", lambda _seconds: None)
    entities = [
        {"entity_id": "a", "canonical_name": "Graph", "type": "method", "paper_ids": ["p1"], "evidence": [ev()]},
        {"entity_id": "b", "canonical_name": "RAG", "type": "concept", "paper_ids": ["p1"], "evidence": [ev()]},
    ]
    relationships = [{"relationship_id": "r1", "source": "a", "target": "b", "type": "uses", "confidence": 0.9, "evidence": [ev()]}]
    result = validate_relationships(
        entities, relationships, [{"chunk_id": "c1", "paper_id": "p1", "text": "Graph RAG method"}],
        semantic_verifier=lambda *_: (_ for _ in ()).throw(RuntimeError("429 RESOURCE_EXHAUSTED quota exceeded")),
        fail_on_verifier_error=False,
    )
    assert result["relationships"] == []
    assert result["rejected_relationships"] == []
    assert len(result["indeterminate_relationships"]) == 1
    assert result["stats"]["indeterminate_relationships"] == 1


def test_developed_by_guard_does_not_reject_valid_target_only_due_to_entity_type():
    quote = "The 2018 Wikipedia dataset was developed by the DPR project."
    entities = [
        {"entity_id": "data", "canonical_name": "2018 Wikipedia dataset", "type": "dataset", "paper_ids": ["p1"], "evidence": [{"paper_id": "p1", "chunk_id": "c1", "quote": quote}]},
        {"entity_id": "dpr", "canonical_name": "DPR project", "type": "tool", "paper_ids": ["p1"], "evidence": [{"paper_id": "p1", "chunk_id": "c1", "quote": quote}]},
    ]
    rel = [{"source": "data", "target": "dpr", "type": "developed_by", "confidence": 0.95, "evidence": [{"paper_id": "p1", "chunk_id": "c1", "quote": quote}]}]
    result = validate_relationships(entities, rel, [{"chunk_id": "c1", "paper_id": "p1", "text": quote}], semantic_verifier=lambda *_: {"supported": True, "direction_correct": True, "confidence": 0.95})
    assert len(result["relationships"]) == 1


def test_finalization_name_support_accepts_punctuation_variants():
    quote = "We evaluate Llama3-70B-baseline on the benchmark."
    graph = finalize_graph(
        ["p1"],
        [{"entity_id": "m", "canonical_name": "Llama3 70B baseline", "type": "model", "paper_ids": ["p1"], "evidence": [{"paper_id": "p1", "chunk_id": "c1", "quote": quote}]}],
        [], [{"chunk_id": "c1", "paper_id": "p1", "text": quote}],
    )
    assert len(graph["nodes"]) == 1
    assert graph["audit"]["rejected_nodes"] == []
