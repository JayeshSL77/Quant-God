import sys
import os
import json

# Add project root to path
sys.path.append('/Users/brainx/Desktop/Create/inwezt_app')

from api.core.charting.generator import ChartGenerator

def test_chart_gen():
    gen = ChartGenerator()
    
    # Test Revenue Trend
    print("--- Testing Revenue Trend ---")
    data = [
        {"period": "2023", "value": 100},
        {"period": "2024", "value": 120}
    ]
    chart = gen.revenue_trend(data, "TEST")
    print(f"Keys: {chart.keys()}")
    if "dataPoints" in chart:
        print(f"Has dataPoints: {len(chart['dataPoints'])} points")
        print(json.dumps(chart['dataPoints'][0], indent=2))
        if "color" in chart['dataPoints'][0]:
             print("Color present verified.")
    else:
        print("FAIL: No dataPoints")

    # Test Margin Trend
    print("\n--- Testing Margin Trend ---")
    data = [
        {"period": "2023", "net_margin": 10.5},
        {"period": "2024", "net_margin": 12.0}
    ]
    chart = gen.margin_trend(data, "TEST")
    if "dataPoints" in chart:
        print(f"Has dataPoints: {len(chart['dataPoints'])} points")
    else:
        print("FAIL: No dataPoints")

if __name__ == "__main__":
    test_chart_gen()
