#!/usr/bin/env python3
"""
RAG Version Comparison Test Script
Tests V1 (MVP) vs V2 (Institutional) orchestrators using Mistral AI.
"""

import os
import sys
from datetime import datetime

# Add parent (inwezt_app) to path so 'backend' module can be found
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

# Load environment
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# Ensure Mistral is used
os.environ['LLM_PROVIDER'] = 'mistral'

def test_v1_orchestrator(query: str) -> dict:
    """Test V1 (MVP) Orchestrator - Simple responses."""
    print("\n" + "="*60)
    print("🔷 V1 ORCHESTRATOR (MVP)")
    print("="*60)
    
    from api.agents.orchestrator import OrchestratorV2
    orch = OrchestratorV2()
    
    result = orch.process(query, {})
    return result


def test_v2_orchestrator(query: str) -> dict:
    """Test V2 (Institutional) Orchestrator - Streaming responses."""
    print("\n" + "="*60)
    print("🔶 V2 ORCHESTRATOR (INSTITUTIONAL)")
    print("="*60)
    
    from api.agents.orchestrator import OrchestratorV2
    orch = OrchestratorV2()
    
    full_response = ""
    final_result = {}
    
    for update in orch.process(query, {}):
        if update.get("status") == "thinking":
            print(f"  ⏳ {update.get('message', '')}")
        elif update.get("status") == "success":
            if update.get("is_partial"):
                # Just accumulate
                full_response = update.get("response", "")
            else:
                # Final result
                final_result = update
                full_response = update.get("response", "")
    
    final_result["response"] = full_response
    return final_result


def save_comparison(query: str, v1_result: dict, v2_result: dict, output_file: str):
    """Save comparison results to file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with open(output_file, 'w') as f:
        f.write(f"# RAG VERSION COMPARISON\n")
        f.write(f"Generated: {timestamp}\n\n")
        f.write(f"## Query\n{query}\n\n")
        
        f.write("="*70 + "\n")
        f.write("## V1 RESPONSE (MVP - Simple, 80-100 words)\n")
        f.write("="*70 + "\n\n")
        f.write(v1_result.get("response", "No response"))
        f.write("\n\n")
        f.write(f"**Agents Used:** {v1_result.get('agents_used', [])}\n")
        f.write(f"**Category:** {v1_result.get('category', 'N/A')}\n")
        
        f.write("\n" + "="*70 + "\n")
        f.write("## V2 RESPONSE (Institutional - Deep Analysis, 300-400 words)\n")
        f.write("="*70 + "\n\n")
        f.write(v2_result.get("response", "No response"))
        f.write("\n\n")
        f.write(f"**Agents Used:** {v2_result.get('agents_used', [])}\n")
        f.write(f"**Version:** {v2_result.get('version', 'N/A')}\n")
    
    print(f"\n✅ Comparison saved to: {output_file}")


def main():
    # Test query about margin guidance
    query = "What is RELIANCE's margin guidance?"
    
    print("\n" + "🚀"*20)
    print("       RAG VERSION COMPARISON TEST")
    print("🚀"*20)
    print(f"\nQuery: {query}")
    print(f"LLM Provider: {os.getenv('LLM_PROVIDER', 'not set')}")
    
    # Run V1
    try:
        v1_result = test_v1_orchestrator(query)
        print("\n📝 V1 Response:")
        print("-"*40)
        print(v1_result.get("response", "No response"))
    except Exception as e:
        print(f"❌ V1 Error: {e}")
        v1_result = {"response": f"Error: {e}", "agents_used": [], "category": "error"}
    
    # Run V2
    try:
        v2_result = test_v2_orchestrator(query)
        print("\n📝 V2 Response:")
        print("-"*40)
        print(v2_result.get("response", "No response"))
    except Exception as e:
        print(f"❌ V2 Error: {e}")
        v2_result = {"response": f"Error: {e}", "agents_used": [], "version": "error"}
    
    # Save comparison
    output_file = os.path.join(os.path.dirname(__file__), 'rag_comparison_output.md')
    save_comparison(query, v1_result, v2_result, output_file)


if __name__ == "__main__":
    main()
