#!/usr/bin/env python3
"""Test Visual RAG Integration - Generates response with chart"""
import os
import sys
import base64

# Add parent dir for backend module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
os.environ['LLM_PROVIDER'] = 'mistral'

from api.agents.orchestrator import OrchestratorV2

print("Testing Visual RAG (V3) - Query with chart intent...")
orch = OrchestratorV2()

# Query that should trigger chart generation
query = "What is RELIANCE's margin guidance?"  # Should trigger margin_trend chart

full_response = ""
chart_data = None

for update in orch.process(query, {}):
    if update.get("status") == "thinking":
        print(f"  ⏳ {update.get('message', '')}")
    elif update.get("status") == "success":
        if not update.get("is_partial"):
            full_response = update.get("response", "")
            chart_data = update.get("chart")

print("\n" + "="*60)
print("V3 VISUAL RAG RESPONSE:")
print("="*60)
print(full_response[:500] + "..." if len(full_response) > 500 else full_response)

print("\n" + "="*60)
print("CHART DATA:")
print("="*60)
if chart_data:
    print(f"✅ Chart Generated!")
    print(f"   Type: {chart_data.get('type')}")
    print(f"   Title: {chart_data.get('title')}")
    print(f"   Base64 Size: {len(chart_data.get('base64', ''))} chars")
    
    # Save chart as PNG for verification
    with open("generated_chart.png", "wb") as f:
        f.write(base64.b64decode(chart_data.get('base64', '')))
    print(f"   Saved to: generated_chart.png")
else:
    print("❌ No chart generated (data may not support chart type)")

print("\n✅ Test complete!")
