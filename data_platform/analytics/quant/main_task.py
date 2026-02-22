from api_client import RapidAPIClient
from data_migrator import DataMigrator
import time

def main():
    # 1. Setup
    api = RapidAPIClient()
    db = DataMigrator()
    
    # 2. Define the Universe (List of stocks to track)
    # You can move this to a config file or database table later.
    symbols_to_track = ["RELIANCE", "TCS", "INFY"]
    
    fetched_data = []

    # 3. Fetch Loop
    print(f"🚀 Starting batch fetch for {len(symbols_to_track)} symbols...")
    for symbol in symbols_to_track:
        try:
            # The fetch_stock_price method has built-in retries (Robustness)
            stock_data = api.fetch_stock_price(symbol)
            fetched_data.append(stock_data)
        except Exception as e:
            print(f"⚠️ Skipped {symbol} after retries failed.")
    
    # 4. Save (Atomic Batch Insert)
    if fetched_data:
        print(f"💾 Saving {len(fetched_data)} records to Database...")
        db.save_prices(fetched_data)
    else:
        print("⚠️ No data was fetched successfully.")

if __name__ == "__main__":
    main()
