
"""
Fetch detailed stock list.
Fallback source: NSE India Archives (EQUITY_L.csv) because Screener.in requires login for screens.
This provides the list of all active stocks (~2000+).
"""
import requests
import json
import os
import pandas as pd
import io
import argparse

def fetch_nse_stocks() -> list:
    """Fetch all active equity stocks from NSE."""
    url = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
    print(f"Fetching stocks from {url}...")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }
    
    try:
        s = requests.Session()
        # Visit home page first to get cookies
        s.get("https://www.nseindia.com", headers=headers, timeout=10)
        
        response = s.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        # Read CSV
        df = pd.read_csv(io.StringIO(response.text))
        
        # Column is 'SYMBOL'
        symbols = df['SYMBOL'].dropna().tolist()
        
        # Filter out ETFs/Bonds if needed (usually series EQ is equity)
        if 'SERIES' in df.columns:
            equity_df = df[df['SERIES'] == 'EQ']
            symbols = equity_df['SYMBOL'].tolist()
            
        print(f"  Found {len(symbols)} stocks from NSE.")
        return symbols
        
    except Exception as e:
        print(f"  Error fetching NSE list: {e}")
        return []

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=2000)
    args = parser.parse_args()
    
    stocks = fetch_nse_stocks()
    
    if not stocks:
        # Fallback to Nifty 500 hardcoded if both fail?
        # For now, let's hope NSE works.
        print("Failed to fetch stocks.")
        return

    # Take top N (NSE list is usually alphabetical, but bulk ingest will handle them)
    # Ideally we'd sort by Market Cap, but we don't have that in EQUITY_L.csv.
    # We will just take the list. 
    # To improve quality, we could cross ref, but user asked for coverage. 
    # We'll take all of them up to limit.
    
    stocks = sorted(list(set(stocks)))
    if args.limit:
        stocks = stocks[:args.limit]
    
    print(f"\nCollected {len(stocks)} unique stocks.")
    
    output_path = os.path.join(os.path.dirname(__file__), "all_stocks.json")
    with open(output_path, 'w') as f:
        json.dump(stocks, f, indent=2)
        
    print(f"Saved to {output_path}")

if __name__ == "__main__":
    main()
