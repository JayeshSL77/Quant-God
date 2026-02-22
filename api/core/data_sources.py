"""
Inwezt - Centralized Data Source Configuration

IMPORTANT: This file defines the SINGLE SOURCE OF TRUTH for all data fetching.
Do NOT fetch data directly in agents or orchestrator - use these functions.
"""

from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import the primary data source
from api.core.utils.fetch_indian_data import (
    fetch_indian_data,
    fetch_concalls,
    fetch_annual_reports,
    fetch_credit_ratings
)


def get_stock_fundamentals(ticker: str) -> Dict[str, Any]:
    """
    Get stock fundamentals (PE, ROE, P/B, Net Margin, etc.)
    
    ⭐ PRIMARY SOURCE: RapidAPI Indian Stock API
    FALLBACK: yfinance
    
    Returns:
        Dict with pe_ratio, roe, net_margin, pb_ratio, market_cap, price,
        PLUS: sector_pe, valuation_status, ytd_change, week_change
    """
    data = fetch_indian_data(ticker)
    
    if data.get("error"):
        return {}
    
    # Calculate P/B if not directly available
    price = data.get("price")
    book_value = data.get("book_value")
    pb_ratio = (price / book_value) if (price and book_value and book_value > 0) else None
    
    # Calculate valuation status vs sector
    pe_ratio = data.get("pe_ratio")
    sector_pe = data.get("sector_pe")
    valuation_status = None
    valuation_discount = None
    
    if pe_ratio and sector_pe and sector_pe > 0:
        discount_pct = ((sector_pe - pe_ratio) / sector_pe) * 100
        valuation_discount = round(discount_pct, 1)
        if discount_pct > 10:
            valuation_status = "Undervalued"
        elif discount_pct < -10:
            valuation_status = "Premium"
        else:
            valuation_status = "Fair Value"
    
    return {
        "pe_ratio": pe_ratio,
        "pb_ratio": pb_ratio,
        "roe": data.get("roe"),
        "net_margin": data.get("net_margin"),
        "revenue_growth": data.get("revenue_growth"),
        "market_cap": data.get("market_cap"),
        "price": price,
        "eps": data.get("eps_ttm"),
        # Premium analysis fields
        "sector_pe": sector_pe,
        "valuation_status": valuation_status,
        "valuation_discount": valuation_discount,  # Positive = undervalued
        "ytd_change": data.get("ytd_change"),
        "week_change": data.get("week_change"),
        "source": data.get("source", "RapidAPI")
    }


def get_fundamentals_batch(tickers: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Get fundamentals for multiple tickers in parallel.
    
    Args:
        tickers: List of stock symbols
        
    Returns:
        Dict mapping ticker -> fundamentals
    """
    results = {}
    
    with ThreadPoolExecutor(max_workers=min(len(tickers), 5)) as executor:
        futures = {executor.submit(get_stock_fundamentals, t): t for t in tickers}
        for future in as_completed(futures):
            ticker = futures[future]
            try:
                results[ticker] = future.result()
            except Exception:
                results[ticker] = {}
    
    return results


# Export all functions
__all__ = [
    "get_stock_fundamentals",
    "get_fundamentals_batch",
    "fetch_concalls",
    "fetch_annual_reports",
    "fetch_credit_ratings"
]
