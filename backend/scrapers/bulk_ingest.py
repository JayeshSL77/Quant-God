import logging
import time
import sys
import os
from typing import List

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bulk_ingest.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("BulkIngest")

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.scrapers.orchestrator import ScraperOrchestrator

# Full list from ingest_historical.py
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

def run_bulk_ingest(symbols: List[str]):
    orchestrator = ScraperOrchestrator()
    total = len(symbols)
    
    logger.info(f"Starting bulk ingestion for {total} stocks")
    
    for i, symbol in enumerate(symbols):
        try:
            logger.info(f"=== [{i+1}/{total}] Processing {symbol} ===")
            orchestrator.ingest_stock_data(symbol)
            time.sleep(1) # Minor throttle
        except Exception as e:
            logger.error(f"Failed bulk ingest for {symbol}: {e}")
            continue

if __name__ == "__main__":
    run_bulk_ingest(NIFTY_500)
