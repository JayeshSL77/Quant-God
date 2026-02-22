#!/usr/bin/env python3
"""
Bulk Ingest Script - Optimized for EC2 c7i.large overnight runs
Run with: python3 bulk_ingest.py --instance 1 --total 10
"""
import logging
import time
import sys
import os
import argparse
import signal
import json
from datetime import datetime
from typing import List

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from data_platform.scrapers.orchestrator import ScraperOrchestrator

# Default NIFTY 500 list (fallback)
NIFTY_500 = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "HINDUNILVR", 
    "ITC", "SBIN", "BHARTIARTL", "KOTAKBANK", "LT", "AXISBANK",
    "BAJFINANCE", "ASIANPAINT", "MARUTI", "HCLTECH", "SUNPHARMA",
    "TITAN", "WIPRO", "ULTRACEMCO", "NTPC", "TECHM", "NESTLEIND",
    "POWERGRID", "TATASTEEL", "ONGC", "JSWSTEEL", "COALINDIA"
]

def load_stock_list(custom_path: str = None) -> List[str]:
    """Load stock list from JSON file or fallback to NIFTY_500."""
    json_path = custom_path if custom_path else os.path.abspath(os.path.join(os.path.dirname(__file__), "all_stocks.json"))
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r') as f:
                stocks = json.load(f)
                # Filter out numeric IDs and duplicates
                stocks = [s for s in stocks if not isinstance(s, str) or not s.isdigit()]
                return sorted(list(set(stocks)))
        except Exception as e:
            print(f"Error loading {json_path}: {e}")
    
    return sorted(list(set(NIFTY_500)))

STOCKS_LIST = load_stock_list()


# Graceful shutdown handling
shutdown_requested = False

def signal_handler(signum, frame):
    global shutdown_requested
    print(f"\n[SIGNAL] Shutdown requested. Finishing current stock...")
    shutdown_requested = True

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


def setup_logging(instance_id: int):
    """Setup logging with instance-specific log file."""
    log_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, f"instance_{instance_id}.log")
    
    # Clear existing handlers
    root_logger = logging.getLogger()
    root_logger.handlers = []
    
    logging.basicConfig(
        level=logging.INFO,
        format=f'%(asctime)s [I{instance_id}] %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, mode='a'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(f"BulkIngest-{instance_id}")


def run_bulk_ingest(symbols: List[str], instance_id: int, concalls_only: bool = False):
    """Run bulk ingestion for a subset of stocks."""
    global shutdown_requested
    
    logger = setup_logging(instance_id)
    
    # Use instance-specific orchestrator
    orchestrator = ScraperOrchestrator(instance_id=instance_id, concalls_only=concalls_only)
    
    if not orchestrator._acquire_lock():
        logger.error(f"Could not acquire lock for instance {instance_id}. Exiting.")
        return

    start_time = datetime.now()
    total = len(symbols)
    processed = 0
    total_ar = 0
    total_concalls = 0
    total_errors = 0
    
    try:
        logger.info(f"=" * 60)
        logger.info(f"Instance {instance_id}: Starting ingestion for {total} stocks")
        logger.info(f"Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"=" * 60)
        
        for i, symbol in enumerate(symbols):
            if shutdown_requested:
                logger.info(f"Shutdown requested. Stopping after {i} stocks.")
                break
                
            try:
                logger.info(f"\n{'='*40}")
                logger.info(f"[{i+1}/{total}] Processing {symbol}")
                logger.info(f"{'='*40}")
                
                stats = orchestrator.ingest_stock_data(symbol)
                
                total_ar += stats.get("ar_saved", 0)
                total_concalls += stats.get("concall_saved", 0)
                total_errors += stats.get("errors", 0)
                processed += 1
                
                # Progress update every 10 stocks
                if (i + 1) % 10 == 0:
                    elapsed = (datetime.now() - start_time).total_seconds() / 60
                    rate = processed / elapsed if elapsed > 0 else 0
                    remaining = (total - processed) / rate if rate > 0 else 0
                    logger.info(f"\n[PROGRESS] {processed}/{total} stocks | {total_ar} ARs | {total_concalls} Concalls | ETA: {remaining:.0f} min\n")
                
                # Brief pause between stocks to be respectful
                time.sleep(1.0)
                
            except Exception as e:
                logger.error(f"Failed bulk ingest for {symbol}: {e}")
                total_errors += 1
                continue
                
    finally:
        orchestrator._release_lock()
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds() / 60
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Instance {instance_id}: COMPLETED")
        logger.info(f"Duration: {duration:.1f} minutes")
        logger.info(f"Stocks processed: {processed}/{total}")
        logger.info(f"Annual Reports saved: {total_ar}")
        logger.info(f"Concalls saved: {total_concalls}")
        logger.info(f"Errors: {total_errors}")
        logger.info(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="Parallel bulk ingestion script for EC2")
    parser.add_argument("--instance", type=int, required=True, help="Instance number (1-10)")
    parser.add_argument("--total", type=int, default=10, help="Total number of instances")
    parser.add_argument("--concalls-only", action="store_true", help="Skip Annual Reports and only scrape Concalls")
    parser.add_argument("--list-file", type=str, help="Path to custom stock list JSON")
    args = parser.parse_args()
    
    stocks_list = load_stock_list(args.list_file)
    
    if args.instance < 1 or args.instance > args.total:
        print(f"Error: Instance must be between 1 and {args.total}")
        sys.exit(1)
    
    total_stocks = len(stocks_list)
    chunk_size = max(1, total_stocks // args.total)
    
    start_idx = (args.instance - 1) * chunk_size
    # Last instance takes all remaining stocks
    end_idx = start_idx + chunk_size if args.instance < args.total else total_stocks
    
    stock_slice = stocks_list[start_idx:end_idx]
    
    print(f"\n{'='*50}")
    print(f"INWEZT SCRAPER - Instance {args.instance}/{args.total}")
    print(f"{'='*50}")
    print(f"Total NIFTY 500 stocks: {total_stocks}")
    print(f"This instance: stocks {start_idx+1} to {end_idx} ({len(stock_slice)} stocks)")
    print(f"First 5: {stock_slice[:5]}")
    print(f"Last 5: {stock_slice[-5:]}")
    print(f"{'='*50}\n")
    
    run_bulk_ingest(stock_slice, args.instance, concalls_only=args.concalls_only)


if __name__ == "__main__":
    main()
