"""Conservative entity resolution and directed relationship reconciliation."""
from __future__ import annotations
import hashlib,re
from collections import defaultdict
GENERIC={"approach","architecture","baseline","classifier","dataset","framework","method","model","network","system","technique","the model","the method","proposed method","proposed approach","algorithm"}
def _norm(s): return re.sub(r"\s+"," ",str(s or "")).strip().casefold()
def _id(prefix,*parts): return prefix+"_"+hashlib.sha256("|".join(_norm(p) for p in parts).encode()).hexdigest()[:20]

def resolve_entities(entities, relationships=()):
    input_entities=list(entities or []); input_relations=list(relationships or []); valid=[]
    for raw in input_entities:
        if not isinstance(raw,dict): continue
        name=str(raw.get("canonical_name") or raw.get("name") or "").strip(); typ=str(raw.get("type") or "other").strip().lower()
        evidence=[e for e in raw.get("evidence",[]) if isinstance(e,dict) and e.get("paper_id") and e.get("chunk_id") and e.get("quote")]
        if not name or not evidence: continue
        item=dict(raw); item.update(canonical_name=name,type=typ,evidence=evidence,paper_ids=sorted({str(e["paper_id"]) for e in evidence})); item["entity_id"]=str(raw.get("entity_id") or _id("ent",typ,name)); valid.append(item)
    groups=defaultdict(list)
    for item in valid:
        name=_norm(item["canonical_name"]); scope=tuple(sorted(item["paper_ids"])) if name in GENERIC else ()
        groups[(item["type"],name,scope)].append(item)
    nodes=[]; id_map={}
    for (typ,norm_name,scope),group in sorted(groups.items(),key=lambda x:str(x[0])):
        canonical=sorted({e["canonical_name"] for e in group},key=lambda x:(len(x),x.casefold(),x))[0]
        evmap={}; aliases=set(); papers=set(); descriptions=[]; props=defaultdict(list); old_ids=set()
        for item in group:
            old_ids.add(item["entity_id"]); papers.update(item["paper_ids"]); aliases.update(str(a).strip() for a in item.get("aliases",[]) if str(a).strip() and _norm(str(a))!=norm_name)
            if item.get("description"): descriptions.append(str(item["description"]).strip())
            for ev in item["evidence"]: evmap[(str(ev["paper_id"]),str(ev["chunk_id"]),_norm(ev["quote"]))]=ev
            for key,value in (item.get("properties") or {}).items():
                if value not in props[key]: props[key].append(value)
        new_id=_id("ent",typ,canonical,"|".join(scope) if scope else "")
        for old in old_ids: id_map[old]=new_id
        nodes.append({"entity_id":new_id,"canonical_name":canonical,"type":typ,"description":descriptions[0] if descriptions else "","aliases":sorted(aliases,key=str.casefold),"paper_ids":sorted(papers),"evidence":list(evmap.values()),"properties":{k:(v[0] if len(v)==1 else v) for k,v in sorted(props.items())}})
    by_id={n["entity_id"]:n for n in nodes}; edge_groups=defaultdict(list); rejected=[]
    for rel in input_relations:
        if not isinstance(rel,dict): rejected.append({"reason":"not_an_object"}); continue
        source=id_map.get(str(rel.get("source") or ""),str(rel.get("source") or "")); target=id_map.get(str(rel.get("target") or ""),str(rel.get("target") or ""))
        if source not in by_id or target not in by_id or source==target: rejected.append({"relationship_id":rel.get("relationship_id"),"reason":"missing_or_invalid_endpoint"}); continue
        evidence=[e for e in rel.get("evidence",[]) if isinstance(e,dict) and e.get("paper_id") and e.get("chunk_id") and e.get("quote")]
        shared=set(by_id[source]["paper_ids"])&set(by_id[target]["paper_ids"]); evidence=[e for e in evidence if str(e["paper_id"]) in shared]
        if not evidence: rejected.append({"relationship_id":rel.get("relationship_id"),"reason":"no_shared_paper_evidence"}); continue
        typ=str(rel.get("type") or "other").strip().lower()
        try: confidence=float(rel.get("confidence",0))
        except (TypeError,ValueError): confidence=float("nan")
        import math
        if not math.isfinite(confidence) or not 0<=confidence<=1: rejected.append({"relationship_id":rel.get("relationship_id"),"reason":"invalid_confidence"}); continue
        edge_groups[(source,typ,target)].append({**rel,"source":source,"target":target,"type":typ,"confidence":confidence,"evidence":evidence})
    edges=[]
    for (source,typ,target),group in sorted(edge_groups.items()):
        evmap={}; papers=set()
        for rel in group:
            for ev in rel["evidence"]: evmap[(str(ev["paper_id"]),str(ev["chunk_id"]),_norm(ev["quote"]))]=ev; papers.add(str(ev["paper_id"]))
        edges.append({"relationship_id":_id("rel",source,typ,target),"source":source,"target":target,"type":typ,"description":next((str(r.get("description") or "").strip() for r in group if r.get("description")),""),"confidence":max(r["confidence"] for r in group),"paper_ids":sorted(papers),"evidence":list(evmap.values())})
    return {"entities":nodes,"relationships":edges,"stats":{"input_entities":len(input_entities),"resolved_entities":len(nodes),"input_relationships":len(input_relations),"resolved_relationships":len(edges),"rejected_relationships":len(rejected)},"rejected_relationships":rejected}
