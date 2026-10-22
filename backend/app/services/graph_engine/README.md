# Isolated SciBrain graph engine

This package is separate from `app.services.knowledge_graph`. It does not alter the legacy engine, API route, frontend, paper routes, or vector store.

## Integration behavior
- Selects only MongoDB papers with `status == "ready"` and `indexed_chunks > 0`.
- Uses `app.services.vector_store.search_paper_chunks(query=..., paper_ids=[paper_id], limit=...)`.
- Tries `app.database.mongodb.papers_collection` then `app.db.mongodb.papers_collection` to account for the two import paths present in the supplied source.
- Reads `GEMINI_API_KEY` only when calling Gemini; no import-time API-key requirement.
- Retries transient Gemini availability/rate-limit errors up to two times after the initial attempt; non-transient errors still fail closed.
- Keeps exact-quote and endpoint-ownership checks deterministic; retries never bypass validation.
- Cross-paper relationship discovery is disabled; no Neo4j dependency is introduced.

## Dependencies
Requires compatible `pydantic` v2, `langgraph`, and `google-genai` in the backend environment. Confirm against the repository's actual dependency file before integration.

## Environment
`GEMINI_API_KEY`, optional `GRAPH_GEMINI_MODEL`, `GRAPH_RETRIEVAL_LIMIT` (8), `GRAPH_MAX_CHUNKS_PER_PAPER` (30), `GRAPH_MAX_TOTAL_CHUNKS` (100), `GRAPH_MAX_CHUNKS_PER_CATEGORY` (4), `GRAPH_EXTRACTION_BATCH_SIZE` (5), `GRAPH_MAX_CHUNK_CHARS` (5000), `GRAPH_MIN_RELATIONSHIP_CONFIDENCE` (0.70), `GRAPH_ENABLE_CROSS_PAPER_DISCOVERY` (false; cross-paper discovery is not implemented).

Do not point the production route at this engine until tests and live integration checks have passed. The included tests are unit tests with mocked retrieval/LLM responses; they do not establish live Gemini quality.

### Predicate and direction safeguards

The semantic validation stage now applies deterministic checks before the Gemini verifier for several easy-to-confuse predicates. `authored_by` requires explicit authorship wording and an author/organization target; wording such as “demonstrated by” or “developed by” cannot pass as authorship. The engine also supports the more precise `developed_by`, `demonstrated_by`, and `introduced_by` predicates, and catches a common reversed `proposes` edge when the evidence says “X was proposed by Y”. These checks are intentionally narrow: they reject obvious predicate/direction errors without pretending to replace semantic review for all relationship types.


### Revision 3 quality safeguards

- Retrieval filters chunks that are clearly bibliography entries, standalone bibliography sections, or front-matter affiliation-only chunks. Ordinary in-body related-work prose remains eligible. Filter counts are deduplicated by chunk ID.
- Finalization statistics now report validated relationships that were subsequently dropped, with reason counts, making validation-versus-final-graph discrepancies inspectable.
- These safeguards reduce known sources of graph noise; they do not replace live review of model-generated entities and predicates.


## Revision 5 — verifier outage semantics and robust name matching

- Semantic verifier failures are no longer represented as semantic rejections when the workflow is configured to preserve partial results. They are returned as `indeterminate_relationships`, stored in `metadata.audit.indeterminate_relationships`, and counted separately in graph quality. These relationships are never emitted as accepted graph edges.
- `fail_on_verifier_error=True` now has real behavior: it raises `RelationshipValidationError` on verifier failure. The orchestrator explicitly opts for audit-preserving mode so a Gemini quota outage does not destroy the full graph run.
- Deterministic development/introduction/demonstration guards no longer reject a relationship solely because its target was classified under a narrow entity type. Explicit predicate cues, target-name evidence, evidence ownership, and semantic verification still apply. Authorship remains separately guarded.
- Entity name evidence matching normalizes punctuation and hyphen variants while retaining token-boundary checks; it does not enable fuzzy or unsupported-name matching.
- Regression tests cover verifier outage classification, strict failure mode, entity-type tolerance, and punctuation-normalized evidence names.
