import os
import json
from dotenv import load_dotenv

# Initialize project environment configurations
load_dotenv(".env")

from app.services.knowledge_graph import generate_knowledge_graph

def run_local_graph_test():
    # Replace with a real paper ID from your MongoDB papers collection
    TEST_RESOURCE_IDS = ["your-paper-uuid-here"]
    
    print(f"🚀 Starting Knowledge Graph Engine test for: {TEST_RESOURCE_IDS}...")
    
    try:
        # Run the extraction engine
        result = generate_knowledge_graph(TEST_RESOURCE_IDS)
        
        print("\n🟢 Execution Successful!")
        print(f"📦 Total Extracted Nodes: {len(result['nodes'])}")
        print(f"📦 Total Extracted Relationships: {len(result['edges'])}")
        
        # Verify Frontend Compatibility Requirements
        if result["nodes"]:
            print("\n🔍 Verifying Frontend Structure Compliance on Node 0:")
            sample_node = result["nodes"][0]
            print(f"  - Has 'id': {'id' in sample_node} -> ({sample_node.get('id')})")
            print(f"  - Has 'name': {'name' in sample_node} -> ({sample_node.get('name')})")
            print(f"  - Has 'type': {'type' in sample_node} -> ({sample_node.get('type')})")
            print(f"  - Has 'resource_ids': {'resource_ids' in sample_node} -> ({sample_node.get('resource_ids')})")
            
        if result["edges"]:
            print("\n🔍 Verifying Frontend Structure Compliance on Edge 0:")
            sample_edge = result["edges"][0]
            print(f"  - Has 'source': {'source' in sample_edge}")
            print(f"  - Has 'target': {'target' in sample_edge}")
            print(f"  - Has 'relationship': {'relationship' in sample_edge} -> ({sample_edge.get('relationship')})")
            print(f"  - Has 'evidence': {'evidence' in sample_edge}")
            
        # Print pretty JSON response slice
        print("\n📋 Raw Payload Output Preview (First 2 nodes & edges):")
        preview = {
            "nodes": result["nodes"][:2],
            "edges": result["edges"][:2]
        }
        print(json.dumps(preview, indent=2))
        
    except Exception as e:
        print(f"\n🔴 Test Failed with Error: {str(e)}")

if __name__ == "__main__":
    run_local_graph_test()
