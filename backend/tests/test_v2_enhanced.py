#!/usr/bin/env python3
"""Test V2 Orchestrator with Enhanced RAG"""
import os
import sys

# Add parent dir for backend module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
os.environ['LLM_PROVIDER'] = 'mistral'

from backend.agents.orchestrator_v2 import OrchestratorV2

print("Testing V2 Orchestrator with ENHANCED RAG (4 concalls, 3 annual reports)...")
orch = OrchestratorV2()

full_response = ""
for update in orch.process("What is RELIANCE's margin guidance?", {}):
    if update.get("status") == "thinking":
        print(f"  ⏳ {update.get('message', '')}")
    elif update.get("status") == "success" and not update.get("is_partial"):
        full_response = update.get("response", "")

print("\n" + "="*60)
print("V2 ENHANCED RESPONSE:")
print("="*60)
print(full_response)

# Save to file
with open('v2_enhanced_response.txt', 'w') as f:
    f.write(full_response)
print("\n✅ Saved to v2_enhanced_response.txt")
