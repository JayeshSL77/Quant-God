import os
import requests
from typing import List
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from models import StockPrice
from dotenv import load_dotenv

load_dotenv()

class RapidAPIClient:
    """
    Robust client for fetching stock data from RapidAPI.
    Includes automatic retries and error handling.
    """
    
    def __init__(self):
        self.api_key = os.getenv("RAPIDAPI_KEY")
        # Using 'Indian Stock Exchange API' per research, but this host is configurable
        self.api_host = os.getenv("RAPIDAPI_HOST", "indian-stock-exchange-api2.p.rapidapi.com")
        self.base_url = f"https://{self.api_host}"
        
        if not self.api_key:
            print("⚠️ Warning: RAPIDAPI_KEY not found in environment variables")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(requests.exceptions.RequestException)
    )
    def fetch_stock_price(self, symbol: str) -> StockPrice:
        """
        Fetches real-time price for a single stock symbol.
        Retries up to 3 times with exponential backoff if the API fails.
        """
        url = f"{self.base_url}/stock"
        # API expects 'stock_name', not 'symbol'
        querystring = {"name": symbol} # Some versions use 'name', let's check screenshot again or try 'stock_name'
        # User said "parameter is stock name like infosys"
        # Based on screenshot it was stock_name for corporate actions.
        # Let's try 'stock_name' first, but standard for this API's /stock endpoint is often just 'name' or 'stock_name'
        # I will trust the user explicitly said "parameter is stock name"
        querystring = {"name": symbol}
        headers = {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": self.api_host
        }

        try:
            print(f"Fetching data for {symbol}...")
            response = requests.get(url, headers=headers, params=querystring, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # Parsing logic adjusted for actual API response structure
            # API returns price as a dict: {'BSE': '1,406.85', 'NSE': '1,406.30'}
            raw_price = data.get("currentPrice", {})
            price_value = 0.0
            
            if isinstance(raw_price, dict):
                # Prefer NSE, fallback to BSE
                price_str = raw_price.get("NSE", raw_price.get("BSE", "0"))
            else:
                price_str = str(raw_price)
                
            # Clean up price string (remove commas)
            try:
                price_value = float(str(price_str).replace(",", ""))
            except ValueError:
                price_value = 0.0

            return StockPrice(
                symbol=symbol,
                price=price_value,
                daily_change=float(str(data.get("change", 0)).replace(",", "")),
                daily_change_percent=float(str(data.get("pChange", 0)).replace("%", "").replace(",", "")),
                # If API doesn't send timestamp, Pydantic defaults to now()
            )
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Network error fetching {symbol}: {e}")
            raise  # Trigger retry
        except Exception as e:
            print(f"❌ Logic error parsing {symbol}: {e}")
            raise
