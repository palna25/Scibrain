import json
from typing import List, Dict, Any
from app.database.mongodb import papers_collection
from app.services.gemini import call_gemini_json

# Strict schema dictionary structured for direct integration with your Gemini JSON utility
GEMINI_ONTOLOGY_SCHEMA = {
    "type": "object",
    "properties": {
        "nodes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Lowercase alphanumeric unique string ID"},
                    "name": {"type": "string", "description": "Canonical text display name matching node.name layout parameters"},
                    "type": {"type": "string", "enum": ["paper", "author", "method", "dataset", "metric", "concept", "finding", "limitation", "future_work", "problem", "organization", "tool", "model"]},
                    "description": {"type": "string", "description": "Short explanation of its role within this work"}
                },
                "required": ["id", "name", "type", "description"]
            }
        },
        "edges": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source": {"type": "string"},
                    "target": {"type": "string"},
                    "relationship": {"type": "string", "enum": ["AUTHORED", "PROPOSES", "UTILIZES", "BENCHMARKS_ON", "EVALUATES_WITH", "ACHIEVES_METRIC", "EXTENDS", "IMPLEMENTED_VIA", "ADDRESSES", "PROVES", "CONTRADICTS"]},
                    "evidence": {"type": "string", "description": "Verbatim short sentence line taken from the source text segment"}
                },
                "required": ["source", "target", "relationship", "evidence"]
            }
        }
    },
    "required": ["nodes", "edges"]
}

def split_source_text(text: str, segment_size: int = 8500, overlap: int = 1200) -> List[str]:
    """Slices academic text strings into overlapping structural context windows."""
    if not text:
        return []
    segments = []
    cursor = 0
    while cursor < len(text):
        end = cursor + segment_size
        segments.append(text[cursor:end])
        if end >= len(text):
            break
        cursor += (segment_size - overlap)
    return segments

def generate_knowledge_graph(resource_ids: List[str]) -> Dict[str, Any]:
    """Queries MongoDB, coordinates atomic parsing via Gemini, and merges structural overlaps."""
    master_nodes: Dict[str, Dict[str, Any]] = {}
    master_edges: List[Dict[str, Any]] = []
    seen_edge_fingerprints = set()

    # 1. Fetch persistent documents from your MongoDB collection schema
    papers_cursor = list(papers_collection.find({"_id": {"$in": resource_ids}}))
    if not papers_cursor:
        return {"nodes": [], "edges": []}

    # 2. Add root "paper" vertices for each selected resource to ground the canvas graph topology
    for paper_meta in papers_cursor:
        p_id = str(paper_meta.get("_id"))
        p_title = paper_meta.get("title") or paper_meta.get("filename") or "Untitled Paper"
        
        master_nodes[p_id] = {
            "id": p_id,
            "name": p_title,
            "type": "paper",
            "description": f"Source Research Paper. Pages: {paper_meta.get('page_count', 'Unknown')}",
            "resource_ids": [p_id]
        }

    # 3. Process structural parsing iterations across each source asset text body
    for paper_meta in papers_cursor:
        current_paper_id = str(paper_meta.get("_id"))
        raw_text = paper_meta.get("text", "")
        text_windows = split_source_text(raw_text)

        for text_window in text_windows:
            prompt = (
                "You are an atomic scientific structural knowledge extraction engine.\n"
                "Analyze the academic text window below and extract clear, explicit entities and links.\n\n"
                "CRITICAL CONSTRAINTS:\n"
                "- Avoid generic thematic overviews or summary text chunks.\n"
                "- Categorize entities into strict types: author, method, model, dataset, metric, tool, concept, problem.\n"
                "- Extract explicit variables (e.g., specific framework name, model size, test set performance values).\n\n"
                f"SOURCE EXCERPT TEXT CONTENT:\n{text_window}"
            )
            
            try:
                # Execute native structural completion over your lazily initialized Gemini module wrapper
                extracted_payload = call_gemini_json(prompt, response_schema=GEMINI_ONTOLOGY_SCHEMA)
                
                # Merge nodes and update spatial context tracking matrices
                for node in extracted_payload.get("nodes", []):
                    node_id = str(node["id"]).strip().lower()
                    
                    # Prevent custom target entity rows from mutating established core paper nodes
                    if node_id in master_nodes and master_nodes[node_id]["type"] == "paper":
                        continue
                        
                    node["id"] = node_id
                    if node_id not in master_nodes:
                        node["resource_ids"] = [current_paper_id]
                        master_nodes[node_id] = node
                    else:
                        # Append source references if the entity appears in multiple papers (cross-linking)
                        if current_paper_id not in master_nodes[node_id]["resource_ids"]:
                            master_nodes[node_id]["resource_ids"].append(current_paper_id)

                # Track unique directional relations across nodes
                for edge in extracted_payload.get("edges", []):
                    s_ref = str(edge["source"]).strip().lower()
                    t_ref = str(edge["target"]).strip().lower()
                    
                    edge["source"] = s_ref
                    edge["target"] = t_ref
                    
                    fingerprint = f"{s_ref}->{edge['relationship']}->{t_ref}"
                    if fingerprint not in seen_edge_fingerprints:
                        seen_edge_fingerprints.add(fingerprint)
                        master_edges.append(edge)
                        
            except Exception:
                # Safeguard iteration loops against individual extraction window pipeline errors
                continue

    return {
        "nodes": list(master_nodes.values()),
        "edges": master_edges
    }
