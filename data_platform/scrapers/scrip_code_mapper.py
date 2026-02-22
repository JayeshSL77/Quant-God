"""
BSE Scrip Code Mapper
Maps stock ticker symbols to BSE scrip codes (e.g., DLF → 532868).

Uses BSE's stock search API to resolve codes.
"""

import os
import json
import time
import logging
import requests
import psycopg2
from typing import Dict, Optional, List
from dotenv import load_dotenv

load_dotenv(override=True)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ScripMapper")

DATABASE_URL = os.getenv("DATABASE_URL",
    "postgresql://postgres:analyezdb77**@analyezdb.cbimec0sg2ch.ap-south-1.rds.amazonaws.com:5432/analyezdb")

BSE_SEARCH_URL = "https://api.bseindia.com/BseIndiaAPI/api/Suggest/w?flag=0&Group=&Ession_id=&Type=&text="
BSE_STOCK_LIST_URL = "https://api.bseindia.com/BseIndiaAPI/api/ListofScripData/w?Group=&Atea=&segment=Equity&status=Active"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.bseindia.com/",
    "Origin": "https://www.bseindia.com",
}

# Cache file for offline use
CACHE_FILE = os.path.join(os.path.dirname(__file__), "scrip_code_cache.json")


class ScripCodeMapper:
    """Maps ticker symbols to BSE scrip codes."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self._cookies_initialized = False
        self.cache: Dict[str, Dict] = {}
        self._load_cache()

    def _init_cookies(self):
        """Visit BSE main page to get session cookies."""
        if self._cookies_initialized:
            return
        try:
            self.session.get("https://www.bseindia.com/", timeout=10)
            self._cookies_initialized = True
        except Exception:
            pass

    def _load_cache(self):
        """Load cached mappings from file."""
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r') as f:
                self.cache = json.load(f)
            logger.info(f"Loaded {len(self.cache)} cached scrip codes")

    def _save_cache(self):
        """Save mappings to cache file."""
        with open(CACHE_FILE, 'w') as f:
            json.dump(self.cache, f, indent=2)

    def search_scrip_code(self, symbol: str) -> Optional[Dict]:
        """
        Search BSE API for a stock's scrip code.
        Returns dict with scrip_code, company_name, isin, group, industry.
        """
        if symbol in self.cache:
            return self.cache[symbol]

        self._init_cookies()

        try:
            time.sleep(1.5)  # Rate limit
            url = BSE_SEARCH_URL + symbol
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            if not data:
                logger.warning(f"No BSE data for {symbol}")
                return None

            # BSE returns array of matches like "532868/DLF Ltd/DLF/A /Active"
            for item in data:
                parts = str(item).split("/")
                if len(parts) >= 3:
                    code = parts[0].strip()
                    name = parts[1].strip()
                    sym = parts[2].strip()

                    # Match exact symbol or close match
                    if sym.upper() == symbol.upper() or symbol.upper() in sym.upper():
                        result = {
                            "scrip_code": code,
                            "company_name": name,
                            "symbol": sym,
                            "group": parts[3].strip() if len(parts) > 3 else "",
                            "status": parts[4].strip() if len(parts) > 4 else "",
                        }
                        self.cache[symbol] = result
                        return result

            # Try first result as fallback
            if data:
                parts = str(data[0]).split("/")
                if len(parts) >= 3:
                    result = {
                        "scrip_code": parts[0].strip(),
                        "company_name": parts[1].strip(),
                        "symbol": parts[2].strip(),
                        "group": parts[3].strip() if len(parts) > 3 else "",
                        "status": parts[4].strip() if len(parts) > 4 else "",
                    }
                    self.cache[symbol] = result
                    return result

        except Exception as e:
            logger.error(f"Error searching {symbol}: {e}")

        return None

    def bulk_resolve(self, symbols: List[str]) -> Dict[str, str]:
        """
        Resolve scrip codes for a list of symbols.
        Returns mapping of symbol → scrip_code.
        """
        results = {}
        total = len(symbols)
        resolved = 0
        failed = 0

        for i, symbol in enumerate(symbols):
            info = self.search_scrip_code(symbol)
            if info:
                results[symbol] = info["scrip_code"]
                resolved += 1
            else:
                failed += 1

            if (i + 1) % 50 == 0 or (i + 1) == total:
                logger.info(f"  [{i+1}/{total}] Resolved: {resolved}, Failed: {failed}")
                self._save_cache()

        self._save_cache()
        logger.info(f"✅ Resolved {resolved}/{total} scrip codes ({failed} failed)")
        return results

    def save_to_db(self):
        """Save cached mappings to bse_scrip_codes table."""
        if not self.cache:
            logger.warning("No cached data to save")
            return

        conn = psycopg2.connect(DATABASE_URL, sslmode='require', connect_timeout=15)
        cur = conn.cursor()
        saved = 0

        for symbol, info in self.cache.items():
            try:
                cur.execute("""
                    INSERT INTO bse_scrip_codes (symbol, scrip_code, company_name, group_name)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (symbol) DO UPDATE SET
                        scrip_code = EXCLUDED.scrip_code,
                        company_name = EXCLUDED.company_name,
                        group_name = EXCLUDED.group_name
                """, (
                    symbol,
                    info.get("scrip_code"),
                    info.get("company_name"),
                    info.get("group"),
                ))
                saved += 1
            except Exception as e:
                logger.error(f"Error saving {symbol}: {e}")

        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"✅ Saved {saved} scrip codes to database")

    def get_code(self, symbol: str) -> Optional[str]:
        """Get scrip code for a symbol (from cache or DB)."""
        if symbol in self.cache:
            return self.cache[symbol].get("scrip_code")

        # Try DB
        try:
            conn = psycopg2.connect(DATABASE_URL, sslmode='require', connect_timeout=15)
            cur = conn.cursor()
            cur.execute("SELECT scrip_code FROM bse_scrip_codes WHERE symbol = %s", (symbol,))
            row = cur.fetchone()
            cur.close()
            conn.close()
            if row:
                self.cache[symbol] = {"scrip_code": row[0]}
                return row[0]
        except Exception:
            pass

        # Try BSE API
        info = self.search_scrip_code(symbol)
        return info.get("scrip_code") if info else None


def main():
    """Resolve scrip codes for all 1000 stocks."""
    import argparse
    parser = argparse.ArgumentParser(description="BSE Scrip Code Mapper")
    parser.add_argument("--test", action="store_true", help="Test with 5 stocks")
    parser.add_argument("--symbol", type=str, help="Resolve single symbol")
    args = parser.parse_args()

    mapper = ScripCodeMapper()

    if args.symbol:
        info = mapper.search_scrip_code(args.symbol)
        print(f"{args.symbol} → {info}")
        return

    # Load all symbols
    stocks_file = os.path.join(os.path.dirname(__file__), "all_stocks.json")
    with open(stocks_file, 'r') as f:
        symbols = json.load(f)

    if args.test:
        symbols = symbols[:5]
        logger.info("🧪 TEST MODE — 5 stocks only")

    logger.info(f"Resolving {len(symbols)} symbols to BSE scrip codes...")
    mapper.bulk_resolve(symbols)
    mapper.save_to_db()


if __name__ == "__main__":
    main()
