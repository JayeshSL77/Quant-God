import logging
import sys
import os

# Add the inwezt_app directory to path
sys.path.append("/Users/brainx/Desktop/Create/inwezt_app")

from data_platform.scrapers.orchestrator import ScraperOrchestrator
from api.database.database import init_database

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def run_test():
    # Initialize DB tables just in case
    init_database()
    
    orchestrator = ScraperOrchestrator()
    symbol = "ZYDUSLIFE"
    
    print(f"--- Starting Test Ingestion for {symbol} ---")
    metadata = orchestrator.screener.fetch_metadata(symbol)
    print(f"Discovered {len(metadata)} document groups on Screener")
    for m in metadata:
        if m.get('links'):
            print(f"  - {m['type']}: {m['title']} links: {m.get('links')}")
        else:
            print(f"  - {m['type']}: {m['title']} url: {m.get('url')}")
    
    orchestrator.ingest_stock_data(symbol)
    print(f"--- Finished Test Ingestion for {symbol} ---")

if __name__ == "__main__":
    run_test()
