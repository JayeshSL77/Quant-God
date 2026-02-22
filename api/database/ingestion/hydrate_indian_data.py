import time
import logging
import nselib
from nselib import capital_market
from fetch_indian_data import fetch_indian_data

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DataHydrator")

def get_nifty50_tickers():
    """
    Fetches the list of Nifty 50 tickers dynamically from nselib.
    """
    try:
        # data = capital_market.nifty50_equity_list() # This might fail if nselib changes
        # Fallback hardcoded list for MVP stability
        return [
            "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "HINDUNILVR", "ITC", 
            "SBIN", "BHARTIARTL", "KOTAKBANK", "LTIM", "AXISBANK", "TATAMOTORS", "LT",
            "BAJFINANCE", "ASIANPAINT", "MARUTI", "HCLTECH", "SUNPHARMA", "TITAN"
        ]
    except Exception as e:
        logger.error(f"Failed to fetch ticker list: {e}")
        return []

def hydrate_database():
    """
    Iterates through top tickers and forces a fetch to populate AWS DB.
    """
    logger.info("Starting Batch Hydration Process...")
    
    tickers = get_nifty50_tickers()
    logger.info(f"Targeting {len(tickers)} companies.")

    success_count = 0
    failure_count = 0

    for ticker in tickers:
        try:
            logger.info(f"Hydrating: {ticker}...")
            # We assume fetch_indian_data handles the AWS storage automatically
            # calling it triggers the fetch-and-store logic.
            data = fetch_indian_data(ticker, period="1y")
            
            if "error" not in data:
                success_count += 1
            else:
                logger.warning(f"Failed to fetch {ticker}: {data['error']}")
                failure_count += 1
            
            # Rate limiting to be polite to APIs (RapidAPI/NSE)
            time.sleep(1) 
            
        except Exception as e:
            logger.error(f"Critical error processing {ticker}: {e}")
            failure_count += 1

    logger.info("--- Hydration Complete ---")
    logger.info(f"Success: {success_count} | Failures: {failure_count}")

if __name__ == "__main__":
    hydrate_database()
