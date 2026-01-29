import base64
import sys
import os
# Add project root to path
# Add project root (the directory containing 'backend') to path for absolute imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.core.charting.generator import ChartGenerator

def test_annual_chart():
    cg = ChartGenerator()
    
    # Mock data mirroring 2020-2026 reports
    data = [
        {"fiscal_year": "2020", "revenue_cr": 150000, "net_profit_cr": 12000},
        {"fiscal_year": "2021", "revenue_cr": 180000, "net_profit_cr": 15000},
        {"fiscal_year": "2022", "revenue_cr": 210000, "net_profit_cr": 18000},
        {"fiscal_year": "2023", "revenue_cr": 240000, "net_profit_cr": 22000},
        {"fiscal_year": "2024", "revenue_cr": 280000, "net_profit_cr": 25000},
        {"fiscal_year": "2025", "revenue_cr": 310000, "net_profit_cr": 28000},
        {"fiscal_year": "2026", "revenue_cr": 290000, "net_profit_cr": 24000}, # Decline to test logic
    ]
    
    # Format for revenue_trend as done in generate_relevant_chart
    chart_data = [{"period": f"FY{str(a.get('fiscal_year', ''))[-2:]}", 
                 "value": a.get("revenue_cr", 0)} for a in data]
    
    # Generate chart
    chart = cg.revenue_trend(chart_data, "RELIANCE", title_prefix="Annual")
    
    print(f"Chart Type: {chart['type']}")
    print(f"Chart Title: {chart['title']}")
    print(f"Chart Insight: {chart['insight']}")
    
    # Save image
    output_dir = os.path.join(os.path.dirname(__file__), "artifacts")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "annual_trend_test.png")
    
    with open(output_path, "wb") as f:
        f.write(base64.b64decode(chart["base64"]))
    print(f"✅ Saved {output_path}")

if __name__ == "__main__":
    test_annual_chart()
