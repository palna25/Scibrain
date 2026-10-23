import json
import logging
from typing import List, Dict, Any
from app.database.mongodb import papers_collection
from app.services.gemini import call_gemini_json
logger = logging.getLogger(__name__)
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
    """ Slices academic text strings into overlapping structural context windows. """
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
    """ Queries MongoDB, coordinates atomic parsing via Gemini, and merges structural overlaps. """
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
        if not isinstance(raw_text, str) or not raw_text.strip():
            logger.warning(
                "No extracted text available for paper %s",
                current_paper_id,
            )
            continue
        text_windows = split_source_text(raw_text)

        for text_window in text_windows:
            
            prompt = (
                "You are an academic knowledge graph extraction engine.\n"
                "Extract explicit, evidence-grounded entities and directed "
                "relationships from the supplied research text.\n\n"

                "ENTITY COVERAGE:\n"
                "- paper: the source research paper, when explicitly identifiable\n"
                "- author: named researchers\n"
                "- method: algorithms, methodologies, frameworks, approaches\n"
                "- model: named machine-learning or statistical models\n"
                "- dataset: named datasets, benchmarks, and evaluation corpora\n"
                "- metric: evaluation metrics and measured quantities\n"
                "- tool: software, libraries, platforms, and implementations\n"
                "- concept: explicitly discussed technical concepts\n"
                "- problem: research problems and challenges\n"
                "- finding: explicit results, observations, conclusions, "
                "and experimentally supported outcomes\n"
                "- limitation: explicitly acknowledged weaknesses, constraints, "
                "failure cases, assumptions, or threats to validity\n"
                "- future_work: explicitly proposed future studies, extensions, "
                "improvements, and directions for further research\n"
                "- organization: explicitly named institutions or organizations\n\n"

                "REQUIRED EXTRACTION PROCEDURE:\n"
                "1. Examine the entire supplied excerpt, not only its opening.\n"
                "2. Pay particular attention to results, discussion, conclusion, "
                "limitations, threats to validity, and future-work sections.\n"
                "3. Extract findings when the excerpt states a result or conclusion; "
                "do not require a numerical metric for every finding.\n"
                "4. Extract limitations and future work only when the text supports "
                "them. Never invent missing limitations or proposals.\n"
                "5. Prefer specific canonical entity names over vague generic nodes.\n"
                "6. Merge repeated mentions of the same entity within this excerpt.\n"
                "7. Create relationships only when the text explicitly supports them.\n"
                "8. Each relationship's source and target must match IDs of nodes "
                "returned in this same response.\n"
                "9. Relationship evidence must be a short verbatim excerpt from "
                "the supplied text, not an invented paraphrase.\n"
                "10. Return empty arrays when the excerpt genuinely supports no "
                "entities or relationships.\n\n"

                "SOURCE EXCERPT:\n"
                f"{text_window}"
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
                logger.exception(
                    "Knowledge graph extraction failed for paper %s",
                    current_paper_id,
                )
                continue
            valid_node_ids = set(master_nodes)

            master_edges = [
                edge
                for edge in master_edges
                if edge.get("source") in valid_node_ids
                and edge.get("target") in valid_node_ids
                and edge.get("source") != edge.get("target")
            ]
    return {
        "nodes": list(master_nodes.values()),
        "edges": master_edges
    } 


""" import json
import logging
import hashlib
from typing import List, Dict, Any
from difflib import SequenceMatcher
from app.database.mongodb import papers_collection
from app.services.gemini import call_gemini_json

logger = logging.getLogger(__name__)

GEMINI_ONTOLOGY_SCHEMA = {
    "type": "object",
    "properties": {
        "nodes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "type": {"type": "string", "enum": ["paper", "author", "method", "dataset", "metric", "concept", "finding", "limitation", "future_work", "problem", "organization", "tool", "model"]},
                    "description": {"type": "string"}
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
                    "evidence": {"type": "string"}
                },
                "required": ["source", "target", "relationship", "evidence"]
            }
        }
    },
    "required": ["nodes", "edges"]
}
def split_source_text(text: str, segment_size: int = 8500, overlap: int = 1200) -> List[str]:
    Slices academic text strings into overlapping structural context windows.
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

def normalize_text(text: str) -> str:
    Normalize text for comparison.
    return ''.join(e for e in text.lower() if e.isalnum())

def similar(a: str, b: str) -> float:
    Compute similarity between two strings.
    return SequenceMatcher(None, a, b).ratio()

def nodes_are_similar(n1: Dict[str, Any], n2: Dict[str, Any], threshold=0.85) -> bool:
    Decide if two nodes should be merged based on name and type similarity.
    if n1['type'] != n2['type']:
        return False
    name_sim = similar(normalize_text(n1['name']), normalize_text(n2['name']))
    desc_sim = similar(normalize_text(n1.get('description', '')), normalize_text(n2.get('description', '')))
    return (name_sim > threshold) and (desc_sim > 0.6)

def hash_evidence(evidence: str) -> str:
   Create a hash for an evidence string.
    return hashlib.md5(evidence.strip().encode('utf-8')).hexdigest()

def validate_edge(edge: Dict[str, Any], master_nodes: Dict[str, Any]) -> bool:
    Validate edge relationship logically according to node types.
    valid_relationships = {
        ("author", "paper"): ["AUTHORED"],
        ("paper", "method"): ["PROPOSES", "UTILIZES"],
        ("paper", "dataset"): ["BENCHMARKS_ON"],
        ("paper", "metric"): ["EVALUATES_WITH", "ACHIEVES_METRIC"],
        ("method", "model"): ["EXTENDS", "IMPLEMENTED_VIA"],
        ("paper", "finding"): ["ADDRESSES", "PROVES", "CONTRADICTS"],
        ("paper", "limitation"): ["ADDRESSES"],
        # Add more as needed
    }
    src = master_nodes.get(edge["source"])
    tgt = master_nodes.get(edge["target"])
    if not src or not tgt:
        return False
    allowed = valid_relationships.get((src["type"], tgt["type"]), [])
    return edge["relationship"] in allowed

def generate_knowledge_graph(resource_ids: List[str]) -> Dict[str, Any]:
    master_nodes: Dict[str, Dict[str, Any]] = {}
    master_edges: List[Dict[str, Any]] = []
    seen_edge_fingerprints = set()
    
    papers_cursor = list(papers_collection.find({"_id": {"$in": resource_ids}}))
    if not papers_cursor:
        return {"nodes": [], "edges": []}

    # Add root paper nodes
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

    # Process text segments via Gemini
    for paper_meta in papers_cursor:
        current_paper_id = str(paper_meta.get("_id"))
        raw_text = paper_meta.get("text", "")
        if not isinstance(raw_text, str) or not raw_text.strip():
            logger.warning("No extracted text for paper %s", current_paper_id)
            continue
        text_windows = split_source_text(raw_text)

        for text_window in text_windows:
            prompt = (
                # (same prompt as original, omitted here for brevity)
                "You are an academic knowledge graph extraction engine.\n"
                "Extract explicit, evidence-grounded entities and directed relationships...\n"
                f"{text_window}"
            )
            
            try:
                extracted_payload = call_gemini_json(prompt, response_schema=GEMINI_ONTOLOGY_SCHEMA)
                
                for node in extracted_payload.get("nodes", []):
                    node_id = normalize_text(node["id"])
                    node["id"] = node_id

                    # Disallow empty or generic vague descriptions
                    if not node.get("description") or len(node["description"].strip()) < 10:
                        logger.debug(f"Skipping node {node_id} due to short/empty description.")
                        continue                    
                    
                    # Prevent overriding core paper nodes
                    if node_id in master_nodes and master_nodes[node_id]["type"] == "paper":
                        continue
                    
                    # Check for similar existing node to merge
                    merged = False
                    for existing_id, existing_node in list(master_nodes.items()):
                        if nodes_are_similar(node, existing_node):
                            # Merge resource IDs & descriptions (optional)
                            for rid in (node.get("resource_ids") or [current_paper_id]):
                                if rid not in existing_node["resource_ids"]:
                                    existing_node["resource_ids"].append(rid)
                            merged = True
                            break
                    
                    if not merged:
                        node["resource_ids"] = [current_paper_id]
                        master_nodes[node_id] = node

                for edge in extracted_payload.get("edges", []):
                    # Validate edge evidence
                    evidence = edge.get("evidence", "").strip()
                    if not evidence:
                        logger.debug(f"Skipping edge due to empty evidence: {edge}")
                        continue
                    
                    s_ref = normalize_text(edge["source"])
                    t_ref = normalize_text(edge["target"])
                    edge["source"] = s_ref
                    edge["target"] = t_ref

                    # Validate nodes existence and relationship type
                    if s_ref not in master_nodes or t_ref not in master_nodes:
                        continue
                    
                    if not validate_edge(edge, master_nodes):
                        logger.debug(f"Skipping edge due to invalid relationship: {edge}")
                        continue
                    
                    fingerprint = f"{s_ref}->{edge['relationship']}->{t_ref}@{hash_evidence(evidence)}"
                    if fingerprint in seen_edge_fingerprints:
                        continue
                    seen_edge_fingerprints.add(fingerprint)
                    master_edges.append(edge)
                
            except Exception:
                logger.exception(f"Knowledge graph extraction failed for paper {current_paper_id}")
                continue

    # Final cleanup: remove edges referencing missing nodes or self loops
    valid_node_ids = set(master_nodes.keys())
    filtered_edges = [
        edge for edge in master_edges
        if edge["source"] in valid_node_ids
        and edge["target"] in valid_node_ids
        and edge["source"] != edge["target"]
    ]

    # Optionally filter out generic/vague nodes here

    return {
        "nodes": list(master_nodes.values()),
        "edges": filtered_edges
    }
 """