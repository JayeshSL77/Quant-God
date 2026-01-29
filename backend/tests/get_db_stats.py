import os
import psycopg2
from dotenv import load_dotenv

load_dotenv(override=True)

DATABASE_URL = os.getenv("DATABASE_URL")

def get_stats():
    if not DATABASE_URL:
        print("DATABASE_URL not configured")
        return

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    # Query for annual reports
    cur.execute("SELECT COUNT(*), COUNT(DISTINCT symbol) FROM annual_reports")
    report_count, stock_count_ar = cur.fetchone()
    
    # Query for concalls for comparison or extra context (optional but good)
    cur.execute("SELECT COUNT(*), COUNT(DISTINCT symbol) FROM concalls")
    concall_count, stock_count_cc = cur.fetchone()
    
    # Query for total stocks in master
    cur.execute("SELECT COUNT(*) FROM stock_master")
    total_stocks = cur.fetchone()[0]

    print(f"Annual Reports: {report_count} for {stock_count_ar} stocks")
    print(f"Concalls: {concall_count} for {stock_count_cc} stocks")
    print(f"Total Stocks in Master: {total_stocks}")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    get_stats()
