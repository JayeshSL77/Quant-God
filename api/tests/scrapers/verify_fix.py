import logging
import sys
import os

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VerifyScraper")

# Add paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from data_platform.scrapers.bulk_ingest import run_bulk_ingest

if __name__ == "__main__":
    test_symbol = ["TECHM"] # Using TECHM as it was the one being processed
    logger.info(f"Starting verification for {test_symbol}")
    run_bulk_ingest(test_symbol)
    logger.info("Verification run completed.")
