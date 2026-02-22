import os
import sys

# Add the parent directory to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from database.database import get_connection

def check_tenure():
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        # Annual Reports Tenure
        cur.execute("SELECT MIN(fiscal_year), MAX(fiscal_year) FROM annual_reports")
        ar_tenure = cur.fetchone()
        print(f"Annual Reports Tenure: {ar_tenure[0]} to {ar_tenure[1]}")
        
        # Concalls Tenure
        cur.execute("SELECT MIN(call_date), MAX(call_date) FROM concalls")
        cc_tenure = cur.fetchone()
        print(f"Concalls Tenure: {cc_tenure[0]} to {cc_tenure[1]}")
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_tenure()
