#!/usr/bin/env python3
"""V1 Orchestrator Test - Simple MVP Response"""
import os
import sys

# Add parent dir for backend module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
os.environ['LLM_PROVIDER'] = 'mistral'

from backend.agents.orchestrator import Orchestrator

print("Testing V1 Orchestrator...")
orch = Orchestrator()
result = orch.process("What is RELIANCE margin guidance?", {})

print("\n" + "="*60)
print("V1 RESPONSE (MVP):")
print("="*60)
print(result.get('response', 'No response'))
print("\nAgents Used:", result.get('agents_used', []))

# Save to file
with open('v1_response.txt', 'w') as f:
    f.write(result.get('response', 'No response'))
print("\nSaved to v1_response.txt")
