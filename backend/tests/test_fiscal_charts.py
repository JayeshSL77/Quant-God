#!/usr/bin/env python3
"""Test fiscal.ai-style chart generation"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.visual_rag import ChartGenerator
import base64

def test_fiscal_charts():
    gen = ChartGenerator()
    
    # 1. Test Revenue Trend (fiscal.ai style)
    print("Testing Revenue Trend...")
    revenue_data = [
        {"quarter": "Dec'19", "value": 15000},
        {"quarter": "Dec'20", "value": 18500},
        {"quarter": "Dec'21", "value": 21200},
        {"quarter": "Dec'22", "value": 24800},
        {"quarter": "Dec'23", "value": 31500},
        {"quarter": "Dec'24", "value": 42000},
    ]
    
    revenue_chart = gen.revenue_trend(revenue_data, "RELIANCE", "Reliance Industries")
    with open("fiscal_revenue_chart.png", "wb") as f:
        f.write(base64.b64decode(revenue_chart["base64"]))
    print(f"  ✅ Revenue chart: {len(revenue_chart['base64'])} chars")
    print(f"     CAGR: {revenue_chart['metrics']['cagr']:.1f}%")
    
    # 2. Test Margin Trend (fiscal.ai style)
    print("\nTesting Margin Trend...")
    margin_data = [
        {"quarter": 1, "fiscal_year": 2024, "net_margin": 12.5},
        {"quarter": 2, "fiscal_year": 2024, "net_margin": 13.2},
        {"quarter": 3, "fiscal_year": 2024, "net_margin": 11.8},
        {"quarter": 4, "fiscal_year": 2024, "net_margin": 14.1},
    ]
    
    margin_chart = gen.margin_trend(margin_data, "RELIANCE")
    with open("fiscal_margin_chart.png", "wb") as f:
        f.write(base64.b64decode(margin_chart["base64"]))
    print(f"  ✅ Margin chart: {len(margin_chart['base64'])} chars")
    
    # 3. Test Valuation Gauge (fiscal.ai style)
    print("\nTesting Valuation Gauge...")
    gauge = gen.valuation_gauge(
        current_pe=25.5,
        sector_pe=13.0,
        historical_low=8.0,
        historical_high=35.0,
        symbol="RELIANCE"
    )
    with open("fiscal_gauge_chart.png", "wb") as f:
        f.write(base64.b64decode(gauge["base64"]))
    print(f"  ✅ Gauge chart: {len(gauge['base64'])} chars")
    
    print("\n✅ All fiscal.ai-style charts generated!")
    print("   Check: fiscal_revenue_chart.png, fiscal_margin_chart.png, fiscal_gauge_chart.png")

if __name__ == "__main__":
    test_fiscal_charts()
