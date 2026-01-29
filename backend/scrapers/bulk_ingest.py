#!/usr/bin/env python3
"""
Bulk Ingest Script with Parallel Instance Support
Run with: python3 bulk_ingest.py --instance 1 --total 6
"""
import logging
import time
import sys
import os
import argparse
from typing import List

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.scrapers.orchestrator import ScraperOrchestrator

# Full NIFTY 500 list
NIFTY_500 = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "HINDUNILVR", 
    "ITC", "SBIN", "BHARTIARTL", "KOTAKBANK", "LT", "AXISBANK",
    "BAJFINANCE", "ASIANPAINT", "MARUTI", "HCLTECH", "SUNPHARMA",
    "TITAN", "WIPRO", "ULTRACEMCO", "NTPC", "TECHM", "NESTLEIND",
    "POWERGRID", "TATASTEEL", "ONGC", "JSWSTEEL", "COALINDIA",
    "BAJAJFINSV", "GRASIM", "TATAMOTORS", "ADANIPORTS", "HINDALCO",
    "DRREDDY", "BRITANNIA", "CIPLA", "BPCL", "DIVISLAB",
    "EICHERMOT", "APOLLOHOSP", "HDFCLIFE", "SBILIFE", "TATACONSUM",
    "HEROMOTOCO", "UPL", "INDUSINDBK", "BAJAJ-AUTO", "LTIM",
    "ADANIGREEN", "ADANIPOWER", "AMBUJACEM", "AUROPHARMA", "BANDHANBNK",
    "BERGEPAINT", "BIOCON", "BOSCHLTD", "CADILAHC", "CHOLAFIN",
    "COLPAL", "CONCOR", "DABUR", "DLF", "GAIL",
    "GODREJCP", "HAVELLS", "ICICIPRULI", "ICICIGI", "INDIGO",
    "IOC", "JUBLFOOD", "LUPIN", "MCDOWELL-N", "MOTHERSON",
    "MUTHOOTFIN", "NAUKRI", "PEL", "PETRONET", "PIDILITIND",
    "PNB", "SRF", "SBICARD", "SHREECEM", "SIEMENS",
    "TATAPOWER", "TORNTPHARM", "TRENT", "VEDL", "ZOMATO",
    "ABB", "ACC", "ALKEM", "ASHOKLEY", "BANKBARODA",
    "BHEL", "CANBK", "CUMMINSIND", "DEEPAKNTR", "ESCORTS",
    "EXIDEIND", "FEDERALBNK", "FORTIS", "GMRINFRA", "GSPL",
    "HINDPETRO", "IDFCFIRSTB", "INDHOTEL", "IRCTC", "JINDALSTEL",
    "LICHSGFIN", "LICI", "LTTS", "MANAPPURAM", "MARICO",
    "MINDTREE", "MPHASIS", "MRF", "NAM-INDIA", "NATIONALUM",
    "NHPC", "NMDC", "OBEROIRLTY", "OFSS", "PAGEIND",
    "PERSISTENT", "PFC", "PIIND", "POLYCAB", "PRESTIGE",
    "RAMCOCEM", "RBLBANK", "RECLTD", "SAIL", "SOLARINDS",
    "STAR", "TATACHEM", "TATAELXSI", "TATAMTRDVR", "TTML",
    "UNIONBANK", "UBL", "VOLTAS", "WHIRLPOOL", "ZEEL",
    "3MINDIA", "AARTIIND", "ABFRL", "AFFLE", "AJANTPHARM",
    "ALKYLAMINE", "AMARAJABAT", "AMBER", "APLLTD", "APOLLOTYRE",
    "ATUL", "AUBANK", "AUROPHARMA", "AVANTIFEED", "BAJAJELEC",
    "BALRAMCHIN", "BASF", "BATA", "BEL", "BEML",
    "BHARATFORG", "BLUEDART", "CAPLIPOINT", "CARBORUNIV", "CASTROLIND",
    "CDSL", "CENTRALBK", "CENTURYTEX", "CERA", "CHAMBLFERT",
    "COFORGE", "COROMANDEL", "CRISIL", "CROMPTON", "CSBBANK",
    "CUB", "CYIENT", "DCAL", "DCMSHRIRAM", "DEEPAKFERT",
    "DELTACORP", "DEVYANI", "DIXON", "DMART", "EIDPARRY",
    "ELGIEQUIP", "EMAMILTD", "ENDURANCE", "ENGINERSIN", "EQUITAS",
    "FLUOROCHEM", "GICRE", "GLAXO", "GLENMARK", "GNFC",
    "GODFRYPHLP", "GODREJIND", "GODREJPROP", "GRAPHITE", "GRINDWELL",
    "GRSE", "GSFC", "GUJGASLTD", "HAL", "HAPPSTMNDS",
    "HATSUN", "HDFCAMC", "HEIDELBERG", "HEMIPROP", "HGS",
    "HINDZINC", "HONAUT", "IBREALEST", "IEX", "IIFL",
    "INDIACEM", "INDIAMART", "INDIANB", "INTELLECT", "IOB",
    "IPCALAB", "IRB", "ISEC", "ITI", "J&KBANK",
    "JBCHEPHARM", "JKCEMENT", "JKLAKSHMI", "JKTYRE", "JMFINANCIL",
    "JSL", "JSWENERGY", "JTEKTINDIA", "KAJARIACER", "KALPATPOWR",
    "KANSAINER", "KARURVYSYA", "KEC", "KEI", "KIRLOSBAR",
    "KJSB", "KPITTECH", "KRBL", "KSB", "LALPATHLAB",
    "LATENTVIEW", "LAURUSLABS", "LEMONTREE", "LINDEINDIA", "LUXIND",
    "MANYAVAR", "MAPMYINDIA", "MASTEK", "MAXHEALTH", "MAZDOCK",
    "MCX", "METROPOLIS", "MIDHANI", "MINDACORP", "MISHRA",
    "MMTC", "MOIL", "MOTILALOFS", "MSTCLTD", "NATCOPHARM",
    "NAUKRI", "NAVINFLUOR", "NBCC", "NCC", "NESCO",
    "NFL", "NLCINDIA", "NOCIL", "NUVOCO", "OFSS",
    "OIL", "OLECTRA", "ORIENTELEC", "ORIENTCEM", "PGHH",
    "PHOENIXLTD", "POLY", "POONAWALLA", "PRINCEPIPE", "PRSMJOHNSN",
    "QUESS", "RADICO", "RAIN", "RAJESHEXPO", "RALLIS",
    "RKFORGE", "ROUTE", "RTNINDIA", "SAREGAMA", "SCHAEFFLER",
    "SEQUENT", "SHARDACROP", "SHILPAMED", "SHOPERSTOP", "SHREDIGCEM",
    "SHYAMMETL", "SKFINDIA", "SOBHA", "SONACOMS", "SPARC",
    "SRTRANSFIN", "STARHEALTH", "SUNDRMFAST", "SUNFLAG", "SUPRAJIT",
    "SUPREMEIND", "SUVENPHAR", "SWANENERGY", "SYMPHONY", "TANLA",
    "TASTYBITE", "TCI", "TEAMLEASE", "THERMAX", "THYROCARE",
    "TIMKEN", "TINPLATE", "TITAGARH", "TMB", "TORNTPOWER",
    "TRENT", "TRIDENT", "TRITURBINE", "TRIVENI", "TTKLALITHA",
    "TV18BRDCST", "TVSMOTOR", "UJJIVAN", "UJJIVANSFB", "UNIONBK",
    "UTIAMC", "UTIBANK", "VAINDUSTRI", "VARROC", "VBL",
    "VGUARD", "VINATIORGA", "VIPIND", "VMART", "VSTIND",
    "VTL", "WABCOINDIA", "WELCORP", "WELSPUNIND", "WESTLIFE",
    "WOCKPHARMA", "XPROINDIA", "YESBANK", "ZENSARTECH", "ZFCVINDIA",
]

def setup_logging(instance_id: int):
    """Setup logging with instance-specific log file."""
    log_file = f"logs/instance_{instance_id}.log"
    os.makedirs("logs", exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format=f'%(asctime)s - [I{instance_id}] %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(f"BulkIngest-{instance_id}")

def run_bulk_ingest(symbols: List[str], instance_id: int):
    """Run bulk ingestion for a subset of stocks."""
    logger = setup_logging(instance_id)
    
    # Use instance-specific lock file
    orchestrator = ScraperOrchestrator()
    orchestrator.lock_file = f".scraper_{instance_id}.lock"
    
    if not orchestrator._acquire_lock():
        logger.error(f"Could not acquire lock for instance {instance_id}. Exiting.")
        return

    try:
        total = len(symbols)
        logger.info(f"Instance {instance_id}: Starting ingestion for {total} stocks")
        
        for i, symbol in enumerate(symbols):
            try:
                logger.info(f"=== [{i+1}/{total}] Processing {symbol} ===")
                orchestrator.ingest_stock_data(symbol)
                time.sleep(0.5)  # Reduced throttle for parallel
            except Exception as e:
                logger.error(f"Failed bulk ingest for {symbol}: {e}")
                continue
    finally:
        orchestrator._release_lock()
        logger.info(f"Instance {instance_id}: Completed and lock released.")

def main():
    parser = argparse.ArgumentParser(description="Parallel bulk ingestion script")
    parser.add_argument("--instance", type=int, required=True, help="Instance number (1-6)")
    parser.add_argument("--total", type=int, default=6, help="Total number of instances")
    args = parser.parse_args()
    
    total_stocks = len(NIFTY_500)
    chunk_size = total_stocks // args.total
    
    start_idx = (args.instance - 1) * chunk_size
    end_idx = start_idx + chunk_size if args.instance < args.total else total_stocks
    
    stock_slice = NIFTY_500[start_idx:end_idx]
    print(f"Instance {args.instance}: Processing stocks {start_idx+1} to {end_idx} ({len(stock_slice)} stocks)")
    
    run_bulk_ingest(stock_slice, args.instance)

if __name__ == "__main__":
    main()
