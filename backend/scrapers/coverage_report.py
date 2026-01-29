import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv(override=True)
DATABASE_URL = os.getenv("DATABASE_URL")

def get_coverage_stats():
    if not DATABASE_URL:
        print("DATABASE_URL not found")
        return

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Get total count of companies in NIFTY 500 list from bulk_ingest.py
    # (Simplified for the report)
    
    # Query for Annual Reports coverage
    cur.execute("""
        SELECT symbol, COUNT(*) as ar_count, STRING_AGG(fiscal_year, ', ' ORDER BY fiscal_year DESC) as ar_years
        FROM annual_reports
        GROUP BY symbol
    """)
    ar_stats = {row['symbol']: row for row in cur.fetchall()}

    # Query for Concalls coverage
    cur.execute("""
        SELECT symbol, COUNT(*) as concall_count, STRING_AGG(DISTINCT fiscal_year, ', ' ORDER BY fiscal_year DESC) as concall_years
        FROM concalls
        GROUP BY symbol
    """)
    concall_stats = {row['symbol']: row for row in cur.fetchall()}

    # Combine stats
    symbols = sorted(set(list(ar_stats.keys()) + list(concall_stats.keys())))
    
    print("| Symbol | Annual Reports | AR Years | Concalls | Concall Years |")
    print("| :--- | :--- | :--- | :--- | :--- |")
    
    for symbol in symbols:
        ar = ar_stats.get(symbol, {'ar_count': 0, 'ar_years': '-'})
        concall = concall_stats.get(symbol, {'concall_count': 0, 'concall_years': '-'})
        print(f"| {symbol} | {ar['ar_count']} | {ar['ar_years']} | {concall['concall_count']} | {concall['concall_years']} |")

    cur.close()
    conn.close()

if __name__ == "__main__":
    get_coverage_stats()
