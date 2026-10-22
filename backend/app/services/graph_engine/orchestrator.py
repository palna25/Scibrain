"""LangGraph orchestration for the independent graph engine."""
from __future__ import annotations
from typing import Any, TypedDict
from app.services.graph_engine.config import GraphEngineSettings
from app.services.graph_engine.retrieval import retrieve_graph_evidence
from app.services.graph_engine.extraction import extract_graph_candidates
from app.services.graph_engine.resolution import resolve_entities
from app.services.graph_engine.validation import validate_relationships
from app.services.graph_engine.finalization import finalize_graph
from app.services.graph_engine.schemas import KnowledgeGraph

class GraphEngineState(TypedDict, total=False):
    resource_ids:list[str]; evidence:dict[str,Any]; candidate_entities:list[dict[str,Any]]; candidate_relationships:list[dict[str,Any]]; resolved_entities:list[dict[str,Any]]; resolved_relationships:list[dict[str,Any]]; validated_relationships:list[dict[str,Any]]; rejected_relationships:list[dict[str,Any]]; indeterminate_relationships:list[dict[str,Any]]; graph:dict[str,Any]; stats:dict[str,Any]; stage_events:list[dict[str,Any]]

def _ids(values):
    result=list(dict.fromkeys(str(x).strip() for x in (values or []) if str(x).strip()))
    if not result: raise ValueError("At least one resource ID is required")
    return result

def _event(state,stage,details=None): return list(state.get("stage_events",[]))+[{"stage":stage,"status":"completed","details":details or {}}]

def build_default_handlers(settings=None,*,paper_collection=None,search_fn=None,generator=None,semantic_verifier=None):
    settings=settings or GraphEngineSettings.from_env()
    def retrieve(s):
        result=retrieve_graph_evidence(s["resource_ids"],paper_collection=paper_collection,search_fn=search_fn,settings=settings)
        return {"evidence":result,"stats":{"retrieval":result["stats"]},"stage_events":_event(s,"retrieve_evidence",result["stats"])}
    def extract(s):
        result=extract_graph_candidates(s["evidence"]["chunks"],generator=generator,batch_size=settings.extraction_batch_size,max_chunk_chars=settings.max_chunk_chars)
        return {"candidate_entities":result["entities"],"candidate_relationships":result["relationships"],"stats":{**s.get("stats",{}),"extraction":result["stats"]},"stage_events":_event(s,"extract_candidates",result["stats"])}
    def resolve(s):
        result=resolve_entities(s.get("candidate_entities",[]),s.get("candidate_relationships",[]))
        return {"resolved_entities":result["entities"],"resolved_relationships":result["relationships"],"rejected_relationships":result["rejected_relationships"],"stats":{**s.get("stats",{}),"resolution":result["stats"]},"stage_events":_event(s,"resolve_entities",result["stats"])}
    def discover(s):
        nodes={n["entity_id"]:n for n in s.get("resolved_entities",[])}; retained=[]; rejected=list(s.get("rejected_relationships",[]))
        for edge in s.get("resolved_relationships",[]):
            a=nodes.get(edge.get("source")); b=nodes.get(edge.get("target"))
            if not a or not b: rejected.append({**edge,"rejection_reason":"missing_endpoint"}); continue
            shared=set(a.get("paper_ids",[]))&set(b.get("paper_ids",[])); evidence=[e for e in edge.get("evidence",[]) if e.get("paper_id") in shared]
            if evidence: retained.append({**edge,"evidence":evidence,"paper_ids":sorted({e["paper_id"] for e in evidence})})
            else: rejected.append({**edge,"rejection_reason":"no_shared_paper_evidence"})
        details={"retained":len(retained),"rejected":len(rejected),"cross_paper_discovery":False}
        return {"resolved_relationships":retained,"rejected_relationships":rejected,"stats":{**s.get("stats",{}),"relationship_discovery":details},"stage_events":_event(s,"discover_relationships",details)}
    def validate(s):
        result=validate_relationships(s.get("resolved_entities",[]),s.get("resolved_relationships",[]),s["evidence"]["chunks"],semantic_verifier=semantic_verifier,minimum_confidence=settings.minimum_relationship_confidence,fail_on_verifier_error=False)
        return {"validated_relationships":result["relationships"],"rejected_relationships":list(s.get("rejected_relationships",[]))+result["rejected_relationships"],"indeterminate_relationships":result.get("indeterminate_relationships",[]),"stats":{**s.get("stats",{}),"validation":result["stats"]},"stage_events":_event(s,"validate_relationships",result["stats"])}
    def finalize(s):
        graph=finalize_graph(s["resource_ids"],s.get("resolved_entities",[]),s.get("validated_relationships",[]),s["evidence"]["chunks"],rejected_relationships=s.get("rejected_relationships",[]),indeterminate_relationships=s.get("indeterminate_relationships",[]),stage_stats=s.get("stats",{}))
        rejected_final=graph.get("audit",{}).get("rejected_relationships",[])
        reason_counts={}
        for item in rejected_final:
            reason=str(item.get("reason") or "unknown")
            reason_counts[reason]=reason_counts.get(reason,0)+1
        details={"nodes":len(graph["nodes"]),"edges":len(graph["edges"]),"validated_edges_dropped":len(rejected_final),"drop_reasons":reason_counts,"rejected_entities":len(graph.get("audit",{}).get("rejected_nodes",[]))}
        final_stats={"final_nodes":len(graph["nodes"]),"final_edges":len(graph["edges"]),"validated_edges_dropped":len(rejected_final),"drop_reasons":reason_counts,"rejected_entities":len(graph.get("audit",{}).get("rejected_nodes",[]))}
        return {"graph":graph,"stats":{**s.get("stats",{}),"finalization":final_stats},"stage_events":_event(s,"finalize_graph",details)}
    return {"retrieve_evidence":retrieve,"extract_candidates":extract,"resolve_entities":resolve,"discover_relationships":discover,"validate_relationships":validate,"finalize_graph":finalize}

def build_graph_workflow(handlers=None):
    try: from langgraph.graph import END,START,StateGraph
    except Exception as exc: raise RuntimeError("langgraph is required for the isolated graph workflow") from exc
    handlers=handlers or build_default_handlers(); stages=["retrieve_evidence","extract_candidates","resolve_entities","discover_relationships","validate_relationships","finalize_graph"]
    missing=[name for name in stages if not callable(handlers.get(name))]
    if missing: raise ValueError("Missing workflow handlers: "+", ".join(missing))
    graph=StateGraph(GraphEngineState)
    for name in stages: graph.add_node(name,handlers[name])
    graph.add_edge(START,stages[0])
    for left,right in zip(stages,stages[1:]): graph.add_edge(left,right)
    graph.add_edge(stages[-1],END)
    return graph.compile()

def run_graph_workflow(resource_ids,*,handlers=None):
    state=build_graph_workflow(handlers).invoke({"resource_ids":_ids(resource_ids),"stage_events":[],"stats":{}})
    if not state.get("graph"): raise RuntimeError("Workflow finished without a graph")
    raw=state["graph"]
    validated=KnowledgeGraph.model_validate({"graph_id":raw["graph_id"],"resource_ids":raw["resource_ids"],"nodes":raw["nodes"],"edges":raw["edges"],"quality":raw["quality"],"metadata":{**raw.get("metadata",{}),"stage_events":state.get("stage_events",[]),"stage_stats":state.get("stats",{}),"audit":raw.get("audit",{})}})
    return validated.model_dump(mode="json")
