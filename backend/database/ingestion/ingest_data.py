"""
Inwezt - Data Ingestion Script
Fetches and stores data for all Nifty stocks to build comprehensive RAG database.
"""
import os
import sys
import time
import logging
from datetime import datetime
from typing import List
from dotenv import load_dotenv

load_dotenv(override=True)

# Add parent directory to path (3 levels up: data/ingestion -> data -> app -> root)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from utils.fetch_indian_data import fetch_indian_data
from backend.database.database import (
    init_database, save_stock_snapshot, save_news_article, 
    get_connection, NIFTY_50
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("DataIngestion")


def ingest_stock(symbol: str) -> dict:
    """Ingest data for a single stock."""
    result = {"symbol": symbol, "success": False, "news_count": 0}
    
    try:
        # Fetch from IndianAPI
        data = fetch_indian_data(symbol)
        
        if "error" in data:
            logger.warning(f"[{symbol}] Fetch failed: {data.get('error')}")
            return result
        
        # Save snapshot
        if save_stock_snapshot(data):
            result["success"] = True
            logger.info(f"[{symbol}] Snapshot saved: PE={data.get('pe_ratio')}, Price={data.get('price')}")
        
        # Save news articles
        news_items = data.get("news", [])
        for article in news_items:
            if save_news_article(symbol, article):
                result["news_count"] += 1
        
        if news_items:
            logger.info(f"[{symbol}] Saved {result['news_count']} news articles")
        
        return result
        
    except Exception as e:
        logger.error(f"[{symbol}] Error: {e}")
        return result


def ingest_all_stocks(symbols: List[str] = None, delay_seconds: float = 1.0):
    """Ingest data for all specified stocks."""
    if symbols is None:
        symbols = NIFTY_50
    
    logger.info(f"Starting ingestion for {len(symbols)} stocks...")
    start_time = datetime.now()
    
    results = {
        "total": len(symbols),
        "success": 0,
        "failed": 0,
        "news_total": 0
    }
    
    for i, symbol in enumerate(symbols, 1):
        logger.info(f"[{i}/{len(symbols)}] Processing {symbol}...")
        
        result = ingest_stock(symbol)
        
        if result["success"]:
            results["success"] += 1
        else:
            results["failed"] += 1
        
        results["news_total"] += result["news_count"]
        
        # Rate limiting
        if i < len(symbols):
            time.sleep(delay_seconds)
    
    elapsed = (datetime.now() - start_time).total_seconds()
    
    logger.info("=" * 50)
    logger.info(f"INGESTION COMPLETE")
    logger.info(f"Total stocks: {results['total']}")
    logger.info(f"Successful: {results['success']}")
    logger.info(f"Failed: {results['failed']}")
    logger.info(f"News articles: {results['news_total']}")
    logger.info(f"Time elapsed: {elapsed:.1f}s")
    logger.info("=" * 50)
    
    return results


def get_db_stats():
    """Get current database statistics."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        stats = {}
        
        # Count snapshots
        cur.execute("SELECT COUNT(*) FROM stock_snapshots")
        stats["snapshots"] = cur.fetchone()[0]
        
        # Count unique symbols
        cur.execute("SELECT COUNT(DISTINCT symbol) FROM stock_snapshots")
        stats["unique_stocks"] = cur.fetchone()[0]
        
        # Count news
        cur.execute("SELECT COUNT(*) FROM news_articles")
        stats["news_articles"] = cur.fetchone()[0]
        
        # Count queries
        cur.execute("SELECT COUNT(*) FROM query_history")
        stats["queries"] = cur.fetchone()[0]
        
        cur.close()
        conn.close()
        
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        return {}


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Inwezt Data Ingestion")
    parser.add_argument("--init", action="store_true", help="Initialize database tables")
    parser.add_argument("--ingest", action="store_true", help="Ingest all Nifty 50 stocks")
    parser.add_argument("--symbols", nargs="+", help="Specific symbols to ingest")
    parser.add_argument("--stats", action="store_true", help="Show database statistics")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between API calls (seconds)")
    
    args = parser.parse_args()
    
    if args.init:
        init_database()
    
    if args.stats:
        stats = get_db_stats()
        print("\n📊 DATABASE STATISTICS")
        print("=" * 30)
        for key, value in stats.items():
            print(f"  {key}: {value}")
        print()
    
    if args.ingest:
        symbols = args.symbols if args.symbols else NIFTY_50
        ingest_all_stocks(symbols, args.delay)
    
    if not any([args.init, args.ingest, args.stats]):
        # Default: show stats and ingest top 10
        print("Running quick ingestion (top 10 stocks)...")
        init_database()
        ingest_all_stocks(NIFTY_50[:10], delay_seconds=1.0)
        
        print("\n📊 Final Statistics:")
        stats = get_db_stats()
        for key, value in stats.items():
            print(f"  {key}: {value}")
