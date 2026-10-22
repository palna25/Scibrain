"""Deterministic graph finalization and final provenance audit."""
from __future__ import annotations
import hashlib, math, re
from datetime import datetime, timezone
from app.services.graph_engine.schemas import ENTITY_TYPES
class GraphFinalizationError(RuntimeError): pass
def _norm(s): return re.sub(r"\s+"," ",str(s or "")).strip().casefold()
def _name_norm(s): return re.sub(r"[^a-z0-9]+", " ", _norm(s)).strip()
def _id(prefix,*parts): return prefix+"_"+hashlib.sha256("|".join(_norm(p) for p in parts).encode()).hexdigest()[:20]
def _chunks_index(chunks):
    result={}
    for chunk in chunks or []:
        if not isinstance(chunk,dict): continue
        cid=str(chunk.get("chunk_id") or ""); pid=str(chunk.get("paper_id") or ""); text=str(chunk.get("text") or "")
        if not cid or not pid or not text.strip(): continue
        if cid in result and (result[cid]["paper_id"]!=pid or _norm(result[cid]["text"])!=_norm(text)): raise GraphFinalizationError(f"Conflicting chunk identity {cid!r}")
        result[cid]={"paper_id":pid,"text":text,"chunk_index":chunk.get("chunk_index")}
    return result
def _verify(ev,index,selected):
    if not isinstance(ev,dict): return None
    pid=str(ev.get("paper_id") or ""); cid=str(ev.get("chunk_id") or ""); quote=str(ev.get("quote") or "").strip(); chunk=index.get(cid)
    if not pid or pid not in selected or not cid or not quote or not chunk or chunk["paper_id"]!=pid or _norm(quote) not in _norm(chunk["text"]): return None
    return {**ev,"paper_id":pid,"chunk_id":cid,"quote":quote,"chunk_index":chunk["chunk_index"]}

def finalize_graph(resource_ids,entities,relationships,chunks,*,rejected_relationships=None,indeterminate_relationships=None,stage_stats=None):
    ids=list(dict.fromkeys(str(x).strip() for x in (resource_ids or []) if str(x).strip()))
    if not ids: raise GraphFinalizationError("At least one selected resource ID is required")
    selected=set(ids); index=_chunks_index(chunks); input_nodes=list(entities or []); input_edges=list(relationships or []); rejected_nodes=[]; groups={}
    for raw in input_nodes:
        if not isinstance(raw,dict): rejected_nodes.append({"reason":"not_an_object"}); continue
        eid=str(raw.get("entity_id") or "").strip(); name=str(raw.get("canonical_name") or raw.get("name") or "").strip(); typ=str(raw.get("type") or "other").strip().lower()
        evidence=[_verify(e,index,selected) for e in (raw.get("evidence") or [])]; evidence=[e for e in evidence if e]
        if not eid or not name or typ not in ENTITY_TYPES or not evidence: rejected_nodes.append({"entity_id":eid,"reason":"missing_identity_or_grounded_evidence"}); continue
        papers=sorted({e["paper_id"] for e in evidence}); declared={str(x) for x in raw.get("paper_ids",[])}
        if not declared.issubset(selected) or not declared.issubset(set(papers)): rejected_nodes.append({"entity_id":eid,"reason":"paper_ownership_mismatch"}); continue
        aliases=[str(x).strip() for x in raw.get("aliases",[]) if str(x).strip()]
        evidence_texts=[_name_norm(e["quote"]) for e in evidence]
        supported_names=[_name_norm(value) for value in [name, *aliases] if _name_norm(value)]
        if not any((" " + candidate + " ") in (" " + quote + " ") for candidate in supported_names for quote in evidence_texts): rejected_nodes.append({"entity_id":eid,"reason":"name_not_supported_by_evidence"}); continue
        item={"entity_id":eid,"canonical_name":name,"type":typ,"description":str(raw.get("description") or ""),"aliases":list(dict.fromkeys(aliases),),"paper_ids":papers,"evidence":evidence,"properties":raw.get("properties") if isinstance(raw.get("properties"),dict) else {}}
        groups.setdefault(eid,[]).append(item)
    nodes=[]; duplicate_nodes_merged=0
    for eid,group in sorted(groups.items()):
        if len({(x["canonical_name"],x["type"]) for x in group})!=1: rejected_nodes.append({"entity_id":eid,"reason":"conflicting_identity_for_same_id"}); continue
        duplicate_nodes_merged+=max(0,len(group)-1); base=dict(group[0]); evmap={}; aliases=set(); papers=set()
        for item in group:
            aliases.update(item["aliases"]); papers.update(item["paper_ids"])
            for ev in item["evidence"]: evmap[(ev["paper_id"],ev["chunk_id"],_norm(ev["quote"]))]=ev
        base.update(aliases=sorted(aliases,key=str.casefold),paper_ids=sorted(papers),evidence=list(evmap.values())); nodes.append(base)
    node_index={n["entity_id"]:n for n in nodes}; edge_groups={}; rejected_edges=[]
    for raw in input_edges:
        if not isinstance(raw,dict): rejected_edges.append({"reason":"not_an_object"}); continue
        source=str(raw.get("source") or ""); target=str(raw.get("target") or "")
        if source not in node_index or target not in node_index or source==target:
            rejected_edges.append({"relationship_id":raw.get("relationship_id"),"source":source,"target":target,"reason":"missing_or_invalid_endpoint","missing_source":source not in node_index,"missing_target":target not in node_index,"self_relationship":source==target}); continue
        typ=str(raw.get("type") or "other").strip().lower()
        if typ not in {"authored_by","developed_by","demonstrated_by","introduced_by","uses","proposes","evaluated_on","measures","addresses","reports","based_on","implements","extends","improves","compares_with","has_finding","has_limitation","has_future_work","related_to","other"}: rejected_edges.append({"relationship_id":raw.get("relationship_id"),"reason":"invalid_relation_type"}); continue
        evidence=[_verify(e,index,selected) for e in (raw.get("evidence") or [])]; evidence=[e for e in evidence if e]
        shared=set(node_index[source]["paper_ids"])&set(node_index[target]["paper_ids"])
        if not evidence or any(e["paper_id"] not in shared for e in evidence): rejected_edges.append({"relationship_id":raw.get("relationship_id"),"reason":"edge_evidence_not_shared_by_endpoints"}); continue
        try: confidence=float(raw.get("confidence"))
        except (TypeError,ValueError): confidence=float("nan")
        validation=raw.get("validation") if isinstance(raw.get("validation"),dict) else {}
        if not math.isfinite(confidence) or not 0<=confidence<=1: rejected_edges.append({"relationship_id":raw.get("relationship_id"),"reason":"invalid_confidence"}); continue
        if validation.get("status")!="accepted" or validation.get("semantic_support") is not True or validation.get("direction_correct") is not True: rejected_edges.append({"relationship_id":raw.get("relationship_id"),"reason":"semantic_validation_missing"}); continue
        key=(source,typ,target); item={"relationship_id":_id("rel",source,typ,target),"source":source,"target":target,"type":typ,"description":str(raw.get("description") or ""),"confidence":confidence,"paper_ids":sorted({e["paper_id"] for e in evidence}),"evidence":evidence,"properties":raw.get("properties") if isinstance(raw.get("properties"),dict) else {}}
        if key not in edge_groups: edge_groups[key]=item
        else:
            old=edge_groups[key]; evmap={(e["paper_id"],e["chunk_id"],_norm(e["quote"])):e for e in old["evidence"]}
            evmap.update({(e["paper_id"],e["chunk_id"],_norm(e["quote"])):e for e in evidence}); old["evidence"]=list(evmap.values()); old["paper_ids"]=sorted({e["paper_id"] for e in old["evidence"]}); old["confidence"]=max(old["confidence"],confidence)
    edges=sorted(edge_groups.values(),key=lambda e:(e["source"],e["type"],e["target"])); nodes=sorted(nodes,key=lambda n:(n["type"],n["canonical_name"].casefold(),n["entity_id"]))
    prior=list(rejected_relationships or []); indeterminate=list(indeterminate_relationships or []); graph_id=_id("graph",*sorted(ids)); processed={c["paper_id"] for c in index.values() if c["paper_id"] in selected}
    entity_reason_counts={}; edge_reason_counts={}
    for item in rejected_nodes:
        reason=str(item.get("reason") or "unknown"); entity_reason_counts[reason]=entity_reason_counts.get(reason,0)+1
    for item in [*rejected_edges,*prior]:
        reason=str(item.get("reason") or item.get("rejection_reason") or "unknown"); edge_reason_counts[reason]=edge_reason_counts.get(reason,0)+1
    quality={"input_papers":len(ids),"processed_papers":len(processed),"retrieved_chunks":len(index),"candidate_entities":len(input_nodes),"accepted_entities":len(nodes),"rejected_entities":len(rejected_nodes),"candidate_relationships":len(input_edges)+len(prior),"accepted_relationships":len(edges),"rejected_relationships":len(rejected_edges)+len(prior),"indeterminate_relationships":len(indeterminate),"validation_errors":[],"rejected_entity_reasons":entity_reason_counts,"rejected_relationship_reasons":edge_reason_counts}
    return {"graph_id":graph_id,"resource_ids":ids,"nodes":nodes,"edges":edges,"quality":quality,"audit":{"rejected_nodes":rejected_nodes,"rejected_relationships":rejected_edges,"prior_rejected_relationships":prior,"indeterminate_relationships":indeterminate,"duplicate_nodes_merged":duplicate_nodes_merged,"stage_stats":stage_stats or {}},"metadata":{"engine":"scibrain_isolated_graph_engine","finalized_at":datetime.now(timezone.utc).isoformat(),"semantic_validation_required":True,"cross_paper_discovery_enabled":False}}
