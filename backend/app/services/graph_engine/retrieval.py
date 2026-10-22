"""Coverage-aware retrieval with paper ownership and duplicate-identity checks."""
from __future__ import annotations
import hashlib, math, re
from collections import defaultdict
from typing import Callable, Any
from app.services.graph_engine.config import GraphEngineSettings

class EvidenceRetrievalError(RuntimeError): pass

# Chunks containing only bibliographic records or front-matter metadata are not
# useful evidence for a scientific concept graph. Keep this conservative: normal
# in-body mentions of prior work must remain eligible.
_REFERENCE_HEADING = re.compile(r"(?im)^\s*(?:references|bibliography|works cited)\s*$")
_AFFILIATION_ONLY = re.compile(
    r"(?is)^.{0,180}\b(?:department|school of|faculty of|university|institute|college)\b.{0,260}$"
)
_BIBLIOGRAPHY_ENTRY = re.compile(
    r"(?is)^\s*[A-Z][\w’'\-]+(?:\s+[A-Z][\w’'\-]+)?"
    r"(?:,\s*[^.\n]{2,80}){2,}\.\s*(?:19|20)\d{2}\.\s+[A-Z]"
)


def _is_nonresearch_chunk(text, source_section=None):
    section = _norm(source_section).casefold()
    if section in {"references", "bibliography", "works cited", "reference"}:
        return "bibliography_section"
    normalized = _norm(text)
    if _REFERENCE_HEADING.search(normalized):
        return "bibliography_heading"
    # Author affiliations often occupy their own first PDF chunk and otherwise
    # become false Organization/author-affiliation graph nodes.
    if _AFFILIATION_ONLY.match(normalized) and re.search(r"\b(?:university|department|school of|faculty of|institute)\b", normalized, re.I):
        if not re.search(r"\b(?:we propose|we present|this paper|abstract|our method|our approach|we introduce)\b", normalized, re.I):
            return "front_matter_affiliation"
    # Reference-list entries usually begin with a multi-author string followed
    # by a publication year and title. Do not apply this to ordinary prose.
    if _BIBLIOGRAPHY_ENTRY.match(normalized):
        return "bibliography_entry"
    return None


COVERAGE_QUERIES = {
    "problem": "research problem question motivation objective",
    "contribution": "main contribution novelty proposed approach",
    "method": "method methodology algorithm architecture approach",
    "model": "model network framework system implementation",
    "dataset": "dataset corpus benchmark data collection",
    "evaluation": "experimental setup evaluation protocol",
    "metrics": "evaluation metrics performance measures",
    "results": "results quantitative findings performance",
    "findings": "key findings observations conclusions",
    "concepts": "important concepts definitions theory",
    "tools": "tools libraries software platform",
    "limitations": "limitations threats to validity weaknesses",
    "future_work": "future work open problems directions",
    "comparison": "comparison baselines competing approaches",
    "conclusion": "conclusion summary implications",
}

def _norm(s): return re.sub(r"\s+", " ", str(s or "")).strip()
def _fingerprint(pid, text, idx): return hashlib.sha256(f"{pid}|{idx}|{_norm(text)}".encode()).hexdigest()

def _integrations():
    failures=[]; papers=None; search=None
    for module_name in ("app.database.mongodb", "app.db.mongodb"):
        try:
            module=__import__(module_name, fromlist=["papers_collection"]); papers=getattr(module,"papers_collection"); break
        except Exception as exc: failures.append(f"{module_name}: {exc}")
    try:
        module=__import__("app.services.vector_store", fromlist=["search_paper_chunks"]); search=getattr(module,"search_paper_chunks")
    except Exception as exc: failures.append(f"app.services.vector_store: {exc}")
    if papers is None or search is None: raise EvidenceRetrievalError("Unable to load integrations: " + " | ".join(failures))
    return papers, search

def retrieve_graph_evidence(resource_ids, *, paper_collection=None, search_fn: Callable | None=None, settings=None):
    settings=settings or GraphEngineSettings.from_env()
    ids=list(dict.fromkeys(str(x).strip() for x in (resource_ids or []) if str(x).strip()))
    if not ids: raise EvidenceRetrievalError("At least one resource ID is required")
    if paper_collection is None or search_fn is None:
        default_papers, default_search=_integrations()
        paper_collection=paper_collection or default_papers; search_fn=search_fn or default_search
    eligible=[]; rejected=[]
    for pid in ids:
        try: doc=paper_collection.find_one({"_id":pid})
        except Exception as exc: raise EvidenceRetrievalError(f"MongoDB lookup failed for {pid}: {exc}") from exc
        if not doc: rejected.append({"paper_id":pid,"reason":"not_found"}); continue
        if str(doc.get("status", "")).lower() != "ready": rejected.append({"paper_id":pid,"reason":"not_ready"}); continue
        try: count=int(doc.get("indexed_chunks",0) or 0)
        except (TypeError,ValueError): count=0
        if count <= 0: rejected.append({"paper_id":pid,"reason":"not_indexed"}); continue
        eligible.append({"paper_id":pid,"title":str(doc.get("title") or doc.get("filename") or pid)})
    if not eligible: raise EvidenceRetrievalError("None of the selected papers are ready and indexed")

    all_chunks={}; per_paper={}; successes=failures=0; warnings=[]; filtered_chunks=defaultdict(set)
    for paper in eligible:
        pid=paper["paper_id"]; local={}; ps={"successful_queries":0,"failed_queries":0,"candidate_chunks":0,"selected_chunks":0}
        for category, query in COVERAGE_QUERIES.items():
            try:
                result=search_fn(query=query, paper_ids=[pid], limit=settings.retrieval_limit)
                if not isinstance(result,list): raise TypeError("search_paper_chunks must return a list")
                successes+=1; ps["successful_queries"]+=1
            except Exception as exc:
                failures+=1; ps["failed_queries"]+=1; warnings.append(f"{pid}/{category}: {type(exc).__name__}: {exc}"); continue
            for raw in result:
                if not isinstance(raw,dict): continue
                raw_pid=str(raw.get("paper_id") or "").strip(); text=_norm(raw.get("text"))
                if raw_pid != pid or not text: continue
                try: idx=int(raw["chunk_index"]) if raw.get("chunk_index") is not None else None
                except (TypeError,ValueError): idx=None
                raw_id=str(raw.get("id") or raw.get("chunk_id") or "").strip()
                cid=raw_id or _fingerprint(pid,text,idx)
                filter_reason = _is_nonresearch_chunk(text, raw.get("source_section"))
                if filter_reason:
                    filtered_chunks[filter_reason].add(cid)
                    continue
                try: score=float(raw.get("score",0) or 0); score=score if math.isfinite(score) else 0.0
                except (TypeError,ValueError): score=0.0
                item={"chunk_id":cid,"qdrant_id":raw_id or None,"paper_id":pid,"paper_title":str(raw.get("title") or paper["title"]),"chunk_index":idx,"text":text,"score":score,"coverage_categories":[category],"retrieval_queries":[query]}
                previous=all_chunks.get(cid)
                if previous:
                    if previous["paper_id"] != pid or previous["text"] != text:
                        raise EvidenceRetrievalError(f"Conflicting content for duplicate chunk ID {cid!r}")
                    previous["score"]=max(previous["score"],score)
                    previous["coverage_categories"]=sorted(set(previous["coverage_categories"]+[category]))
                    previous["retrieval_queries"]=list(dict.fromkeys(previous["retrieval_queries"]+[query]))
                    item=previous
                else: all_chunks[cid]=item
                local[cid]=item
        ps["candidate_chunks"]=len(local)
        by_category=defaultdict(list)
        for chunk in local.values():
            for category in chunk["coverage_categories"]: by_category[category].append(chunk)
        selected=[]; used=set()
        for category in COVERAGE_QUERIES:
            count=0
            for chunk in sorted(by_category.get(category,[]),key=lambda c:(-c["score"],c["chunk_index"] if c["chunk_index"] is not None else 10**9,c["chunk_id"])):
                if chunk["chunk_id"] in used: continue
                if count >= settings.max_chunks_per_category or len(selected)>=settings.max_chunks_per_paper: break
                selected.append(chunk); used.add(chunk["chunk_id"]); count+=1
        for chunk in sorted(local.values(),key=lambda c:(-c["score"],c["chunk_id"])):
            if len(selected)>=settings.max_chunks_per_paper: break
            if chunk["chunk_id"] not in used: selected.append(chunk); used.add(chunk["chunk_id"])
        paper["_selected"]=selected; per_paper[pid]=ps
    chunks=[]
    for paper in eligible:
        for chunk in paper.pop("_selected"):
            if len(chunks)>=settings.max_total_chunks: break
            chunks.append(chunk)
        if len(chunks)>=settings.max_total_chunks: break
    for ps in per_paper.values(): ps["selected_chunks"]=0
    for chunk in chunks: per_paper[chunk["paper_id"]]["selected_chunks"]+=1
    if not chunks: raise EvidenceRetrievalError("No usable evidence chunks retrieved")
    if successes == 0: raise EvidenceRetrievalError("All evidence retrieval queries failed")
    return {"resource_ids":ids,"papers":[{"paper_id":p["paper_id"],"title":p["title"]} for p in eligible],"chunks":chunks,
            "stats":{"requested_papers":len(ids),"eligible_papers":len(eligible),"rejected_papers":rejected,"successful_queries":successes,"failed_queries":failures,"candidate_chunks":len(all_chunks),"selected_chunks":len(chunks),"filtered_chunks":{reason:len(chunk_ids) for reason,chunk_ids in filtered_chunks.items()},"per_paper":per_paper},"warnings":warnings}
