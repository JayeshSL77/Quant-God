
from typing import Dict, Any, List
from .base import BaseAgent
from backend.database.database import get_stock_context_from_db

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
        market_data = get_stock_context_from_db(symbol)
        
        has_data = bool(market_data.get("snapshots") or market_data.get("history"))
        
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
