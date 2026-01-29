import base64
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from utils.visual_rag import ChartGenerator
from database.database import get_connection

def generate_honest_chart():
    cg = ChartGenerator()
    symbol = "RELIANCE"
    
    # Fetch real data from DB
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT fiscal_year, key_metrics 
        FROM annual_reports 
        WHERE symbol=%s 
        ORDER BY fiscal_year ASC
    """, (symbol,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    
    if not rows:
        print("No data found in DB for RELIANCE")
        return

    # Extract numerical data
    chart_data = []
    for r in rows:
        metrics = r.get("key_metrics", {})
        # Indian reports often use 'Revenue' or 'Total Revenue'
        # Let's see what's actually there
        rev = metrics.get("Revenue", metrics.get("Total Revenue", metrics.get("revenue", 0)))
        if rev:
            chart_data.append({
                "period": f"FY{str(r['fiscal_year'])[-2:]}",
                "value": float(rev)
            })

    if not chart_data:
        print("Could not extract numerical revenue from key_metrics")
        print("Available keys in latest report:", rows[-1]['key_metrics'].keys())
        return

    # Generate chart
    chart = cg.revenue_trend(chart_data, symbol, title_prefix="Annual")
    
    print(f"Chart Title: {chart['title']}")
    print(f"Chart Insight: {chart['insight']}")
    
    # Save image
    out_path = "honest_annual_trend.png"
    with open(out_path, "wb") as f:
        f.write(base64.b64decode(chart["base64"]))
    print(f"✅ Saved {out_path}")

if __name__ == "__main__":
    generate_honest_chart()
