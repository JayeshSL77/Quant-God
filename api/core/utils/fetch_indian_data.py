"""
Inwezt - Indian Stock Data Fetcher
Uses IndianAPI by RapidAPI as PRIMARY source for comprehensive data.
"""
import os
import json
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv
import requests


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("IndianStockFetcher")

# Load environment variables
load_dotenv(override=True)

# API Configuration - MUST be set via environment variable
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
RAPIDAPI_HOST = "indian-stock-exchange-api2.p.rapidapi.com"


def fetch_indian_data(ticker: str) -> Dict[str, Any]:
    """
    Fetch comprehensive stock data from IndianAPI.
    Returns fundamentals, price, news, and peer data.
    """
    clean_ticker = ticker.replace(".NS", "").replace(".BO", "").upper()
    
    if not RAPIDAPI_KEY or RAPIDAPI_KEY == "your-rapidapi-key-here":
        logger.warning("No RapidAPI key configured, falling back to yfinance")
        return _fetch_from_yfinance(clean_ticker)
    
    try:
        url = f"https://{RAPIDAPI_HOST}/stock"
        headers = {
            "X-RapidAPI-Key": RAPIDAPI_KEY,
            "X-RapidAPI-Host": RAPIDAPI_HOST
        }
        params = {"name": clean_ticker}
        
        response = requests.get(url, headers=headers, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            return _normalize_indianapi_data(data, clean_ticker)
        else:
            logger.error(f"IndianAPI error: {response.status_code} - {response.text}")
            return _fetch_from_yfinance(clean_ticker)
            
    except Exception as e:
        logger.error(f"IndianAPI failed: {e}")
        return _fetch_from_yfinance(clean_ticker)


def _normalize_indianapi_data(data: Dict, ticker: str) -> Dict[str, Any]:
    """Normalize IndianAPI response to our standard schema."""
    
    result = {
        "source": "IndianAPI",
        "ticker": ticker,
        "exchange": "NSE",
        "last_updated": datetime.now().isoformat()
    }
    
    # Extract from stockDetailsReusableData
    stock_data = data.get("stockDetailsReusableData", {})
    if stock_data:
        result["price"] = _safe_float(stock_data.get("price"))
        result["price_formatted"] = _format_indian_number(result.get("price", 0))
        result["change_pct"] = _safe_float(stock_data.get("percentChange"))
        result["market_cap"] = _safe_float(stock_data.get("marketCap"))  # In Crores
        result["market_cap_formatted"] = _format_market_cap(result.get("market_cap", 0))
        result["pe_ratio"] = _safe_float(stock_data.get("pPerEBasicExcludingExtraordinaryItemsTTM"))
        result["sector_pe"] = _safe_float(stock_data.get("sectorPriceToEarningsValueRatio"))
        result["ytd_change"] = _safe_float(stock_data.get("priceYTDPricePercentChange"))
        result["week_change"] = _safe_float(stock_data.get("price5DayPercentChange"))
    
    # Profitability & Growth Fallback from peerCompanyList
    # The IndianAPI stock endpoint often includes the main stock in its peer list with pre-calculated metrics
    all_peers = stock_data.get("peerCompanyList", [])
    main_stock_data = next((p for p in all_peers if p.get("companyName", "").upper() == ticker or p.get("tickerId", "").endswith(ticker)), None)
    
    if main_stock_data:
        if not result.get("pe_ratio"): result["pe_ratio"] = _safe_float(main_stock_data.get("priceToEarningsValueRatio"))
        if not result.get("roe"): result["roe"] = _safe_float(main_stock_data.get("returnOnAverageEquityTrailing12Month"))
        if not result.get("net_margin"): result["net_margin"] = _safe_float(main_stock_data.get("netProfitMarginPercentTrailing12Month"))
        if not result.get("book_value"): 
             pb = _safe_float(main_stock_data.get("priceToBookValueRatio"))
             if pb and result.get("price"):
                 result["book_value"] = result["price"] / pb

    # Extract key metrics from specific groups
    key_metrics = data.get("keyMetrics", {})
    
    # Map groups to metric extraction
    metric_groups = {
        "mgmtEffectiveness": {
            "returnOnAverageEquityTrailing12Month": "roe",
            "returnOnAverageAssetsTrailing12Month": "roa"
        },
        "margins": {
            "netProfitMarginPercentTrailing12Month": "net_margin",
            "operatingMarginTrailing12Month": "operating_margin"
        },
        "growth": {
            "revenueChangePercentMostRecentQuarter1YearAgo": "revenue_growth",
            "ePSChangePercentTTMOverTTM": "profit_growth"
        }
    }
    
    for group_name, mappings in metric_groups.items():
        group_data = key_metrics.get(group_name, [])
        for item in group_data:
            key = item.get("key")
            if key in mappings:
                result[mappings[key]] = _safe_float(item.get("value"))

    # Extra share data
    per_share = key_metrics.get("persharedata", [])
    for item in per_share:
        key = item.get("key", "")
        if "ePSIncludingExtraOrdinaryItemsTrailing12Month" in key:
            result["eps_ttm"] = _safe_float(item.get("value"))
        elif "bookValuePerShare" in key and "MostRecentFiscalYear" in key:
            result["book_value"] = _safe_float(item.get("value"))
    
    # Analyst recommendation
    recos = data.get("recosBar", {})
    if recos:
        result["analyst_score"] = _safe_float(recos.get("tickerPercentage"))  # 0-100
    
    # Extract news (top 5)
    news_list = data.get("news", [])[:5]
    result["news"] = []
    for article in news_list:
        result["news"].append({
            "headline": _clean_html(article.get("headline", "")),
            "summary": _clean_html(article.get("summary", "")),
            "date": article.get("date"),
            "url": article.get("url")
        })

    # Fetch Corporate Filings (Earnings, Concalls, etc.)
    try:
        filings = fetch_corporate_filings(ticker)
        result["filings"] = filings
    except Exception as e:
        logger.warning(f"Failed to fetch filings for {ticker}: {e}")
        result["filings"] = []
    
    # Peer companies for comparison
    peers = stock_data.get("peerCompanyList", [])[:3]
    result["peers"] = []
    for peer in peers:
        result["peers"].append({
            "name": peer.get("companyName"),
            "pe_ratio": peer.get("priceToEarningsValueRatio"),
            "market_cap": peer.get("marketCap"),
            "rating": peer.get("overallRating")
        })
    
    return result


def fetch_corporate_filings(ticker: str) -> List[Dict]:
    """
    Fetch corporate filings (Board Meetings, Results, Announcements).
    Uses 'stock' endpoint as 'corporate_actions' has validation/quota issues.
    """
    if not RAPIDAPI_KEY:
        return []
        
    try:
        url = f"https://{RAPIDAPI_HOST}/stock"
        
        headers = {
            "X-RapidAPI-Key": RAPIDAPI_KEY,
            "X-RapidAPI-Host": RAPIDAPI_HOST
        }
        # API expects 'name' for this endpoint
        params = {"name": ticker}
        
        response = requests.get(url, headers=headers, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            documents = []
            
            # Extract corporate actions from the nested object
            corp_data = data.get("stockCorporateActionData", {})
            
            # 1. Board Meetings
            # Structure: [{"boardMeetDate": "YYYY-MM-DD", "purpose": "Desc"}, ...]
            meetings = corp_data.get("boardMeetings", [])
            for item in meetings[:10]:
                date_str = item.get("boardMeetDate", "")
                purpose = item.get("purpose", "Board Meeting")
                if date_str:
                    documents.append({
                        "title": purpose,
                        "date": date_str,
                        "type": "Board Meeting",
                        "url": _generate_id(ticker, date_str, "BM")
                    })

            # 2. Dividends
            # Structure: [{"recordDate": "...", "remarks": "...", "percentage": 55}, ...]
            dividends = corp_data.get("dividend", [])
            for item in dividends[:10]:
                date_str = item.get("recordDate", "") or item.get("dateOfAnnouncement", "")
                remarks = item.get("remarks", "")
                pct = item.get("percentage", "")
                if date_str:
                    documents.append({
                        "title": f"Dividend Declared: {remarks} ({pct}%)",
                        "date": date_str,
                        "type": "Dividend",
                        "url": _generate_id(ticker, date_str, "DIV")
                    })

            # 3. Bonus
            # Structure: [{"recordDate": "...", "remarks": "..."}, ...]
            bonus = corp_data.get("bonus", [])
            for item in bonus[:5]:
                date_str = item.get("recordDate", "") or item.get("dateOfAnnouncement", "")
                remarks = item.get("remarks", "Bonus Issue")
                if date_str:
                    documents.append({
                        "title": f"Bonus Issue: {remarks}",
                        "date": date_str,
                        "type": "Bonus",
                        "url": _generate_id(ticker, date_str, "BON")
                    })

            # 4. Splits
            splits = corp_data.get("splits", [])
            for item in splits[:5]:
                date_str = item.get("recordDate", "") or item.get("dateOfAnnouncement", "")
                remarks = item.get("remarks", "Stock Split")
                if date_str:
                    documents.append({
                        "title": f"Stock Split: {remarks}",
                        "date": date_str,
                        "type": "Split",
                        "url": _generate_id(ticker, date_str, "SPLIT")
                    })

            return documents
        else:
            logger.warning(f"Filings API status: {response.status_code}")
            return []
            
    except Exception as e:
        logger.error(f"Filings fetch error: {e}")
        return []

def _generate_id(ticker, date_str, type_code):
    """Generate a unique ID for actions that lack a URL."""
    import hashlib
    unique_str = f"{ticker}-{date_str}-{type_code}"
    return f"action://{hashlib.md5(unique_str.encode()).hexdigest()[:12]}"


def fetch_concalls(ticker: str) -> List[Dict]:
    """
    Fetch earnings call (concall) transcripts from IndianAPI.
    Endpoint: /concalls
    Returns actual management commentary from earnings calls.
    """
    if not RAPIDAPI_KEY:
        return []
    
    try:
        url = f"https://{RAPIDAPI_HOST}/concalls"
        headers = {
            "X-RapidAPI-Key": RAPIDAPI_KEY,
            "X-RapidAPI-Host": RAPIDAPI_HOST
        }
        params = {"stock_name": ticker}
        
        response = requests.get(url, headers=headers, params=params, timeout=20)
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"Concalls data for {ticker}: {type(data)}")
            
            # Handle both list and dict responses
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return data.get("concalls", data.get("data", []))
            return []
        else:
            logger.warning(f"Concalls API status: {response.status_code}")
            return []
            
    except Exception as e:
        logger.error(f"Concalls fetch error: {e}")
        return []


def fetch_annual_reports(ticker: str) -> List[Dict]:
    """
    Fetch annual reports data from IndianAPI.
    Endpoint: /annual_reports
    Returns annual report URLs and summaries.
    """
    if not RAPIDAPI_KEY:
        return []
    
    try:
        url = f"https://{RAPIDAPI_HOST}/annual_reports"
        headers = {
            "X-RapidAPI-Key": RAPIDAPI_KEY,
            "X-RapidAPI-Host": RAPIDAPI_HOST
        }
        params = {"stock_name": ticker}
        
        response = requests.get(url, headers=headers, params=params, timeout=20)
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"Annual reports data for {ticker}: {type(data)}")
            
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return data.get("reports", data.get("data", []))
            return []
        else:
            logger.warning(f"Annual reports API status: {response.status_code}")
            return []
            
    except Exception as e:
        logger.error(f"Annual reports fetch error: {e}")
        return []


def fetch_credit_ratings(ticker: str) -> List[Dict]:
    """
    Fetch credit ratings from IndianAPI.
    Endpoint: /credit_ratings
    """
    if not RAPIDAPI_KEY:
        return []
    
    try:
        url = f"https://{RAPIDAPI_HOST}/credit_ratings"
        headers = {
            "X-RapidAPI-Key": RAPIDAPI_KEY,
            "X-RapidAPI-Host": RAPIDAPI_HOST
        }
        params = {"stock_name": ticker}
        
        response = requests.get(url, headers=headers, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return data.get("ratings", data.get("data", []))
            return []
        else:
            return []
            
    except Exception as e:
        logger.error(f"Credit ratings fetch error: {e}")
        return []


def _fetch_from_yfinance(ticker: str) -> Dict[str, Any]:
    """Fallback to yfinance if IndianAPI is unavailable."""
    try:
        import yfinance as yf
        ns_ticker = f"{ticker}.NS"
        stock = yf.Ticker(ns_ticker)
        info = stock.info
        
        return {
            "source": "yfinance",
            "ticker": ticker,
            "exchange": "NSE",
            "price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "price_formatted": _format_indian_number(info.get("currentPrice", 0)),
            "change_pct": info.get("regularMarketChangePercent") or info.get("morningstarRisk"), # minor fallback
            "pe_ratio": info.get("trailingPE") or info.get("forwardPE"),
            "market_cap": info.get("marketCap", 0) / 10000000 if info.get("marketCap") else None,  # Convert to Cr
            "market_cap_formatted": _format_market_cap(info.get("marketCap", 0) / 10000000),
            "eps_ttm": info.get("trailingEps"),
            "roe": info.get("returnOnEquity"),
            "net_margin": info.get("profitMargins"),
            "revenue_growth": info.get("revenueGrowth"),
            "profit_growth": info.get("earningsGrowth"),
            "book_value": info.get("bookValue"),
            "high_52w": info.get("fiftyTwoWeekHigh"),
            "low_52w": info.get("fiftyTwoWeekLow"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "last_updated": datetime.now().isoformat(),
            "news": [],
            "peers": []
        }
    except Exception as e:
        logger.error(f"yfinance fallback failed: {e}")
        return {"error": f"Failed to fetch data for {ticker}", "ticker": ticker}


def _safe_float(value) -> Optional[float]:
    """Safely convert a value to float."""
    if value is None or value == "-" or value == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _format_indian_number(amount: float) -> str:
    """Format number in Indian style (₹X,XX,XXX)."""
    if not amount:
        return "₹0"
    try:
        amount = float(amount)
        if amount >= 10000000:  # 1 Cr+
            return f"₹{amount/10000000:.2f} Cr"
        elif amount >= 100000:  # 1 Lakh+
            return f"₹{amount/100000:.2f} L"
        else:
            return f"₹{amount:,.0f}"
    except:
        return f"₹{amount}"


def _format_market_cap(crores: float) -> str:
    """Format market cap (input in Crores)."""
    if not crores:
        return "N/A"
    try:
        crores = float(crores)
        if crores >= 100000:  # 1 Lakh Cr+
            return f"₹{crores/100000:.2f} L Cr"
        elif crores >= 1000:
            return f"₹{crores/1000:.2f}K Cr"
        else:
            return f"₹{crores:.0f} Cr"
    except:
        return f"₹{crores} Cr"


def _clean_html(text: str) -> str:
    """Remove HTML tags from text."""
    if not text:
        return ""
    return re.sub(r'<[^>]+>', '', text).strip()


# Test function
if __name__ == "__main__":
    result = fetch_indian_data("RELIANCE")
    print(json.dumps(result, indent=2, default=str))
