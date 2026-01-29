#!/usr/bin/env python3
"""Test new chart types for Phase 2"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.visual_rag import ChartGenerator
import base64

def test_phase2_charts():
    gen = ChartGenerator()
    
    # 1. Test Segment Breakdown (single period)
    print("Testing Segment Breakdown...")
    segments = [
        {"name": "O2C", "value": 150000},
        {"name": "Oil & Gas", "value": 85000},
        {"name": "Retail", "value": 65000},
        {"name": "Digital", "value": 45000},
        {"name": "New Energy", "value": 12000},
    ]
    
    segment_chart = gen.segment_breakdown(segments, "RELIANCE")
    with open("phase2_segment_chart.png", "wb") as f:
        f.write(base64.b64decode(segment_chart["base64"]))
    print(f"  ✅ Segment chart: {len(segment_chart['base64'])} chars")
    
    # 2. Test Quarterly Comparison
    print("\nTesting Quarterly Comparison...")
    current_q = {
        "quarter": 3, "fiscal_year": 2024,
        "revenue_cr": 232000,
        "ebitda_cr": 45000,
        "net_profit_cr": 18000,
        "pat_cr": 17500
    }
    prev_q = {
        "quarter": 2, "fiscal_year": 2024,
        "revenue_cr": 215000,
        "ebitda_cr": 42000,
        "net_profit_cr": 16500,
        "pat_cr": 16000
    }
    
    comparison_chart = gen.quarterly_comparison(current_q, prev_q, "RELIANCE")
    with open("phase2_comparison_chart.png", "wb") as f:
        f.write(base64.b64decode(comparison_chart["base64"]))
    print(f"  ✅ Comparison chart: {len(comparison_chart['base64'])} chars")
    print(f"     QoQ Growth: {comparison_chart['growth']:.1f}%")
    
    print("\n✅ Phase 2 charts generated!")
    print("   Check: phase2_segment_chart.png, phase2_comparison_chart.png")

if __name__ == "__main__":
    test_phase2_charts()
