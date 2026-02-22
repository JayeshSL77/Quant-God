import sys
import os
import json
import logging

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from data_platform.scrapers.orchestrator import ScraperOrchestrator

logging.basicConfig(level=logging.INFO)

def test_reliance():
    orchestrator = ScraperOrchestrator()
    symbol = "RELIANCE"
    print(f"Testing {symbol}...")
    stats = orchestrator.ingest_stock_data(symbol)
    print(f"Stats: {stats}")

if __name__ == "__main__":
    test_reliance()
