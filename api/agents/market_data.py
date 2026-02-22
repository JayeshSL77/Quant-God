
from typing import Dict, Any, List
from .base import BaseAgent
from api.database.database import get_stock_context_from_db

class MarketDataAgent(BaseAgent):
    """
    Agent responsible for fetching quantitative market data (Price, PE, Trends).
    """
    
    def __init__(self):
        super().__init__(name="MarketDataAgent")
        
    def process(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fetches structured financial data for the requested stock.
        """
        symbol = context.get("formatted_tickers", [])[0] if context.get("formatted_tickers") else None
        
        if not symbol:
            return {
                "has_data": False,
                "data": {},
                "source": "MarketDataAgent",
                "relevance_score": 0
            }
            
        self._log_activity(f"Fetching market context for {symbol}")
        
        # 1. LIVE FETCH (Primary) - As requested by user to "activate everytime"
        try:
            from api.core.utils.fetch_indian_data import fetch_indian_data
            live_data = fetch_indian_data(symbol)
            
            # Sync to DB for future reference and 10-year context
            if live_data and "price" in live_data:
                from api.database.database import save_stock_snapshot
                save_stock_snapshot(live_data)
                self._log_activity(f"Synced live data for {symbol} to DB")
        except Exception as e:
            self._log_activity(f"Live fetch failed: {e}")
            live_data = {}

        # 2. DB FETCH (Historical/Supplementary)
        db_data = get_stock_context_from_db(symbol)
        
        # 3. Merge Strategies (Live takes precedence for snapshot metrics)
        snapshots = db_data.get("snapshots", [])
        
        if live_data and "price" in live_data:
            # Prepend live data as the latest snapshot
            snapshots.insert(0, live_data)
            
        # Refined merged data structure
        market_data = {
            "snapshots": snapshots,
            "history": db_data.get("history", []),
            "peers": live_data.get("peers") or db_data.get("peers", []),
            "long_term_trend": db_data.get("long_term_trend", {})
        }
        
        has_data = bool(snapshots or market_data.get("history"))
        
        # Determine relevance
        query_lower = query.lower()
        is_price_focused = any(term in query_lower for term in 
            ['price', 'limit', 'trading', 'value', 'market cap', 'pe ratio'])
            
        return {
            "has_data": has_data,
            "data": market_data,
            "source": "MarketDataAgent",
            "relevance_score": 0.9 if is_price_focused else 0.6
        }
