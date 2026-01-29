import sys
import os
import asyncio
import json

# Add project root to path
# Add project root (the directory containing 'backend') to path for absolute imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.agents.orchestrator import OrchestratorV2

async def main():
    print("Initializing OrchestratorV2...")
    orch = OrchestratorV2()
    
    query = "What is the revenue trend for RELIANCE?"
    print(f"\nQuery: {query}\n" + "="*50)
    
    # Process query
    chart_found = False
    full_text = ""
    
    print("Streaming response...")
    chart_info_printed = False
    
    for event in orch.process(query, context={"include_tax_context": False}):
        status = event.get("status")
        
        if status == "success":
            # Accumulate text
            if "chunk" in event:
                print(event["chunk"], end="", flush=True)
                full_text += event["chunk"]
            
            # Check for chart
            if "chart" in event and event["chart"] and not chart_info_printed:
                chart = event["chart"]
                print(f"\n\n[CHART GENERATED]")
                print(f"Type: {chart.get('type')}")
                print(f"Title: {chart.get('title')}")
                print(f"Insight: {chart.get('insight')}")
                
                # Save image to artifacts folder
                import base64
                output_dir = os.path.join(os.path.dirname(__file__), "artifacts")
                os.makedirs(output_dir, exist_ok=True)
                output_path = os.path.join(output_dir, "latest_verification_chart.png")
                
                with open(output_path, "wb") as f:
                    f.write(base64.b64decode(chart.get("base64")))
                print(f"✅ Chart saved to {output_path}")
                
                chart_info_printed = True

    print("\n" + "="*50)
    if chart_found:
        print("\n✅ Visual RAG integration successful: Chart + Insight received.")
    else:
        print("\n❌ No chart generated.")

if __name__ == "__main__":
    asyncio.run(main())
