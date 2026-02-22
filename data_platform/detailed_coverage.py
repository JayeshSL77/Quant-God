import os
import sys

# Add the root directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api.database.database import get_connection

def get_coverage_table():
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        # Get AR data
        cur.execute("SELECT symbol, COUNT(*), MIN(fiscal_year), MAX(fiscal_year) FROM annual_reports GROUP BY symbol")
        ar_data = {row[0]: {'count': row[1], 'min': row[2], 'max': row[3]} for row in cur.fetchall()}
        
        # Get CC data
        cur.execute("SELECT symbol, COUNT(*), MIN(fiscal_year), MAX(fiscal_year) FROM concalls GROUP BY symbol")
        cc_data = {row[0]: {'count': row[1], 'min': row[2], 'max': row[3]} for row in cur.fetchall()}
        
        conn.close()
        
        all_symbols = set(ar_data.keys()) | set(cc_data.keys())
        
        results = []
        for sym in all_symbols:
            ar = ar_data.get(sym, {'count': 0, 'min': None, 'max': None})
            cc = cc_data.get(sym, {'count': 0, 'min': None, 'max': None})
            
            # Clean up years (handle None)
            ar_min = str(ar['min']) if ar['min'] else "-"
            ar_max = str(ar['max']) if ar['max'] else "-"
            cc_min = str(cc['min']) if cc['min'] else "-"
            cc_max = str(cc['max']) if cc['max'] else "-"
            
            ar_range = f"{ar_min} - {ar_max}" if ar['count'] > 0 else "-"
            cc_range = f"{cc_min} - {cc_max}" if cc['count'] > 0 else "-"
            
            results.append({
                'Symbol': sym,
                'AR Count': ar['count'],
                'AR Years': ar_range,
                'Concall Count': cc['count'],
                'Concall Years': cc_range
            })
            
        # Sort by total docs
        results.sort(key=lambda x: (x['AR Count'] + x['Concall Count']), reverse=True)
        
        with open("coverage_report.txt", "w") as f:
            f.write(f"Total Stocks Scanned: {len(results)}\n\n")
            f.write(f"{'Symbol':<15} | {'AR Count':<10} | {'AR Years':<22} | {'Concall Count':<15} | {'Concall Years':<22}\n")
            f.write("-" * 95 + "\n")
            
            for r in results:
                f.write(f"{r['Symbol']:<15} | {str(r['AR Count']):<10} | {r['AR Years']:<22} | {str(r['Concall Count']):<15} | {r['Concall Years']:<22}\n")
                
        print(f"Report saved to coverage_report.txt with {len(results)} stocks")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    get_coverage_table()
