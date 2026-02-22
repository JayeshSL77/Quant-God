import os
import sys

# Add the parent directory to sys.path so we can import from backend
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from database.database import get_connection

def check_coverage():
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT COUNT(*), COUNT(DISTINCT symbol) FROM annual_reports")
        ar_stats = cur.fetchone()
        ar_count = ar_stats[0]
        ar_symbols = ar_stats[1]
        
        cur.execute("SELECT COUNT(*), COUNT(DISTINCT symbol) FROM concalls")
        concall_stats = cur.fetchone()
        concall_count = concall_stats[0]
        concall_symbols = concall_stats[1]
        
        print(f"Annual Reports: {ar_count} reports across {ar_symbols} stocks")
        print(f"Concalls: {concall_count} calls across {concall_symbols} stocks")
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_coverage()
