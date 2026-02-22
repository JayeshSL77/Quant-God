"""
Inwezt - Historical Data Ingestion from IndianAPI
Ingests 10+ years of historical data for 500 stocks.
"""
import os
import sys
import time
import logging
import requests
from datetime import datetime, date
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv

load_dotenv(override=True)

# Add parent directory to path
# Add parent directory to path (3 levels up: data/ingestion -> data -> app -> root)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from api.database.database import get_connection

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("HistoricalIngestion")

RAPIDAPI_KEY = os.getenv('RAPIDAPI_KEY')
RAPIDAPI_HOST = 'indian-stock-exchange-api2.p.rapidapi.com'

HEADERS = {
    'X-RapidAPI-Key': RAPIDAPI_KEY,
    'X-RapidAPI-Host': RAPIDAPI_HOST
}

# Nifty 500 stocks (expanded list)
NIFTY_500 = [
    # Nifty 50
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "HINDUNILVR", 
    "ITC", "SBIN", "BHARTIARTL", "KOTAKBANK", "LT", "AXISBANK",
    "BAJFINANCE", "ASIANPAINT", "MARUTI", "HCLTECH", "SUNPHARMA",
    "TITAN", "WIPRO", "ULTRACEMCO", "NTPC", "TECHM", "NESTLEIND",
    "POWERGRID", "TATASTEEL", "ONGC", "JSWSTEEL", "COALINDIA",
    "BAJAJFINSV", "GRASIM", "TATAMOTORS", "ADANIPORTS", "HINDALCO",
    "DRREDDY", "BRITANNIA", "CIPLA", "BPCL", "DIVISLAB",
    "EICHERMOT", "APOLLOHOSP", "HDFCLIFE", "SBILIFE", "TATACONSUM",
    "HEROMOTOCO", "UPL", "INDUSINDBK", "BAJAJ-AUTO", "LTIM",
    # Nifty Next 50
    "ADANIGREEN", "ADANIPOWER", "AMBUJACEM", "AUROPHARMA", "BANDHANBNK",
    "BERGEPAINT", "BIOCON", "BOSCHLTD", "CADILAHC", "CHOLAFIN",
    "COLPAL", "CONCOR", "DABUR", "DLF", "GAIL",
    "GODREJCP", "HAVELLS", "ICICIPRULI", "ICICIGI", "INDIGO",
    "IOC", "JUBLFOOD", "LUPIN", "MCDOWELL-N", "MOTHERSON",
    "MUTHOOTFIN", "NAUKRI", "PEL", "PETRONET", "PIDILITIND",
    "PNB", "SRF", "SBICARD", "SHREECEM", "SIEMENS",
    "TATAPOWER", "TORNTPHARM", "TRENT", "VEDL", "ZOMATO",
    # Nifty Midcap 100 (partial)
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
    # Additional prominent stocks
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


def create_historical_tables():
    """Create tables for historical data."""
    conn = get_connection()
    cur = conn.cursor()
    
    # Historical price data (weekly)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS historical_prices (
            id SERIAL PRIMARY KEY,
            symbol VARCHAR(20) NOT NULL,
            trade_date DATE NOT NULL,
            price DECIMAL(12,2),
            dma_50 DECIMAL(12,2),
            dma_200 DECIMAL(12,2),
            volume BIGINT,
            delivery_pct DECIMAL(6,2),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(symbol, trade_date)
        )
    """)
    
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_historical_prices_symbol_date 
        ON historical_prices(symbol, trade_date DESC)
    """)
    
    # Historical valuation data (PE, EPS)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS historical_valuations (
            id SERIAL PRIMARY KEY,
            symbol VARCHAR(20) NOT NULL,
            trade_date DATE NOT NULL,
            pe_ratio DECIMAL(10,2),
            eps DECIMAL(10,2),
            sector_pe DECIMAL(10,2),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(symbol, trade_date)
        )
    """)
    
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_historical_valuations_symbol_date 
        ON historical_valuations(symbol, trade_date DESC)
    """)
    
    conn.commit()
    cur.close()
    conn.close()
    logger.info("Historical tables created successfully")


def fetch_historical_price_data(symbol: str, period: str = "10yr") -> Dict[str, Any]:
    """Fetch historical price data from IndianAPI."""
    url = f'https://{RAPIDAPI_HOST}/historical_data'
    params = {
        'stock_name': symbol,
        'period': period,
        'filter': 'price'
    }
    
    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=30)
        if response.status_code == 200:
            return response.json()
        else:
            logger.warning(f"[{symbol}] Price data failed: {response.status_code}")
            return {}
    except Exception as e:
        logger.error(f"[{symbol}] Price fetch error: {e}")
        return {}


def fetch_historical_pe_data(symbol: str, period: str = "10yr") -> Dict[str, Any]:
    """Fetch historical PE/EPS data from IndianAPI."""
    url = f'https://{RAPIDAPI_HOST}/historical_data'
    params = {
        'stock_name': symbol,
        'period': period,
        'filter': 'pe'
    }
    
    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=30)
        if response.status_code == 200:
            return response.json()
        else:
            logger.warning(f"[{symbol}] PE data failed: {response.status_code}")
            return {}
    except Exception as e:
        logger.error(f"[{symbol}] PE fetch error: {e}")
        return {}


def save_historical_prices(symbol: str, data: Dict[str, Any]) -> int:
    """Save historical price data to database."""
    if not data or 'datasets' not in data:
        return 0
    
    conn = get_connection()
    cur = conn.cursor()
    
    # Extract datasets
    prices = {}
    dma50 = {}
    dma200 = {}
    volumes = {}
    
    for dataset in data.get('datasets', []):
        metric = dataset.get('metric', '')
        values = dataset.get('values', [])
        
        if metric == 'Price':
            for v in values:
                if len(v) >= 2:
                    prices[v[0]] = float(v[1])
        elif metric == 'DMA50':
            for v in values:
                if len(v) >= 2:
                    dma50[v[0]] = float(v[1])
        elif metric == 'DMA200':
            for v in values:
                if len(v) >= 2:
                    dma200[v[0]] = float(v[1])
        elif metric == 'Volume':
            for v in values:
                if len(v) >= 2:
                    vol_data = {'volume': int(v[1])}
                    if len(v) >= 3 and isinstance(v[2], dict):
                        vol_data['delivery'] = v[2].get('delivery')
                    volumes[v[0]] = vol_data
    
    # Insert data
    count = 0
    for date_str, price in prices.items():
        try:
            cur.execute("""
                INSERT INTO historical_prices 
                (symbol, trade_date, price, dma_50, dma_200, volume, delivery_pct)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (symbol, trade_date) DO UPDATE SET
                    price = EXCLUDED.price,
                    dma_50 = EXCLUDED.dma_50,
                    dma_200 = EXCLUDED.dma_200,
                    volume = EXCLUDED.volume,
                    delivery_pct = EXCLUDED.delivery_pct
            """, (
                symbol,
                date_str,
                price,
                dma50.get(date_str),
                dma200.get(date_str),
                volumes.get(date_str, {}).get('volume'),
                volumes.get(date_str, {}).get('delivery')
            ))
            count += 1
        except Exception as e:
            logger.error(f"[{symbol}] Insert error for {date_str}: {e}")
    
    conn.commit()
    cur.close()
    conn.close()
    
    return count


def save_historical_valuations(symbol: str, data: Dict[str, Any]) -> int:
    """Save historical PE/EPS data to database."""
    if not data or 'datasets' not in data:
        return 0
    
    conn = get_connection()
    cur = conn.cursor()
    
    # Extract datasets
    pe_data = {}
    eps_data = {}
    
    for dataset in data.get('datasets', []):
        metric = dataset.get('metric', '')
        values = dataset.get('values', [])
        
        if 'Earning' in metric or 'PE' in metric.upper():
            for v in values:
                if len(v) >= 2:
                    try:
                        pe_data[v[0]] = float(v[1])
                    except (ValueError, TypeError):
                        pass
        elif metric == 'EPS':
            for v in values:
                if len(v) >= 2:
                    try:
                        eps_data[v[0]] = float(v[1])
                    except (ValueError, TypeError):
                        pass
    
    # Insert data
    count = 0
    for date_str, pe in pe_data.items():
        try:
            cur.execute("""
                INSERT INTO historical_valuations 
                (symbol, trade_date, pe_ratio, eps)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (symbol, trade_date) DO UPDATE SET
                    pe_ratio = EXCLUDED.pe_ratio,
                    eps = COALESCE(EXCLUDED.eps, historical_valuations.eps)
            """, (
                symbol,
                date_str,
                pe,
                eps_data.get(date_str)
            ))
            count += 1
        except Exception as e:
            logger.error(f"[{symbol}] Valuation insert error for {date_str}: {e}")
    
    conn.commit()
    cur.close()
    conn.close()
    
    return count


def ingest_stock_history(symbol: str, period: str = "10yr") -> Dict[str, int]:
    """Ingest all historical data for a single stock."""
    result = {'symbol': symbol, 'prices': 0, 'valuations': 0}
    
    # Fetch and save price data
    price_data = fetch_historical_price_data(symbol, period)
    if price_data:
        result['prices'] = save_historical_prices(symbol, price_data)
    
    time.sleep(0.3)  # Rate limiting
    
    # Fetch and save PE/EPS data
    pe_data = fetch_historical_pe_data(symbol, period)
    if pe_data:
        result['valuations'] = save_historical_valuations(symbol, pe_data)
    
    logger.info(f"[{symbol}] Ingested: {result['prices']} prices, {result['valuations']} valuations")
    return result


def ingest_all_historical(symbols: List[str] = None, period: str = "10yr", delay: float = 0.5):
    """Ingest historical data for all stocks."""
    if symbols is None:
        symbols = NIFTY_500[:500]  # Limit to 500
    
    # Create tables first
    create_historical_tables()
    
    logger.info(f"Starting historical ingestion for {len(symbols)} stocks ({period} period)...")
    start_time = datetime.now()
    
    results = {
        'total': len(symbols),
        'success': 0,
        'failed': 0,
        'total_prices': 0,
        'total_valuations': 0
    }
    
    for i, symbol in enumerate(symbols, 1):
        logger.info(f"[{i}/{len(symbols)}] Processing {symbol}...")
        
        try:
            result = ingest_stock_history(symbol, period)
            results['total_prices'] += result['prices']
            results['total_valuations'] += result['valuations']
            results['success'] += 1
        except Exception as e:
            logger.error(f"[{symbol}] Failed: {e}")
            results['failed'] += 1
        
        # Rate limiting
        if i < len(symbols):
            time.sleep(delay)
    
    elapsed = (datetime.now() - start_time).total_seconds()
    
    logger.info("=" * 60)
    logger.info("HISTORICAL INGESTION COMPLETE")
    logger.info(f"Total stocks: {results['total']}")
    logger.info(f"Successful: {results['success']}")
    logger.info(f"Failed: {results['failed']}")
    logger.info(f"Total price records: {results['total_prices']}")
    logger.info(f"Total valuation records: {results['total_valuations']}")
    logger.info(f"Time elapsed: {elapsed:.1f}s ({elapsed/60:.1f} minutes)")
    logger.info("=" * 60)
    
    return results


def get_historical_stats():
    """Get statistics on historical data."""
    conn = get_connection()
    cur = conn.cursor()
    
    stats = {}
    
    # Price data stats
    cur.execute("""
        SELECT 
            COUNT(*) as total_records,
            COUNT(DISTINCT symbol) as unique_stocks,
            MIN(trade_date) as earliest_date,
            MAX(trade_date) as latest_date
        FROM historical_prices
    """)
    row = cur.fetchone()
    stats['prices'] = {
        'total_records': row[0],
        'unique_stocks': row[1],
        'earliest_date': str(row[2]) if row[2] else None,
        'latest_date': str(row[3]) if row[3] else None
    }
    
    # Valuation data stats
    cur.execute("""
        SELECT 
            COUNT(*) as total_records,
            COUNT(DISTINCT symbol) as unique_stocks,
            MIN(trade_date) as earliest_date,
            MAX(trade_date) as latest_date
        FROM historical_valuations
    """)
    row = cur.fetchone()
    stats['valuations'] = {
        'total_records': row[0],
        'unique_stocks': row[1],
        'earliest_date': str(row[2]) if row[2] else None,
        'latest_date': str(row[3]) if row[3] else None
    }
    
    cur.close()
    conn.close()
    
    return stats


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Historical Data Ingestion")
    parser.add_argument("--init", action="store_true", help="Initialize tables")
    parser.add_argument("--ingest", action="store_true", help="Ingest historical data")
    parser.add_argument("--count", type=int, default=50, help="Number of stocks to ingest")
    parser.add_argument("--period", type=str, default="10yr", help="Period: 1m, 6m, 1yr, 3yr, 5yr, 10yr, max")
    parser.add_argument("--stats", action="store_true", help="Show historical data stats")
    
    args = parser.parse_args()
    
    if args.init:
        create_historical_tables()
    
    if args.stats:
        stats = get_historical_stats()
        print("\n📊 HISTORICAL DATA STATISTICS")
        print("=" * 40)
        print(f"Price Data:")
        print(f"  Records: {stats['prices']['total_records']:,}")
        print(f"  Stocks: {stats['prices']['unique_stocks']}")
        print(f"  Range: {stats['prices']['earliest_date']} to {stats['prices']['latest_date']}")
        print(f"\nValuation Data:")
        print(f"  Records: {stats['valuations']['total_records']:,}")
        print(f"  Stocks: {stats['valuations']['unique_stocks']}")
        print(f"  Range: {stats['valuations']['earliest_date']} to {stats['valuations']['latest_date']}")
    
    if args.ingest:
        symbols = NIFTY_500[:args.count]
        ingest_all_historical(symbols, args.period)
        
        # Show final stats
        stats = get_historical_stats()
        print("\n📊 Final Statistics:")
        print(f"  Price records: {stats['prices']['total_records']:,}")
        print(f"  Valuation records: {stats['valuations']['total_records']:,}")
