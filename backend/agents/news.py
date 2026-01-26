from typing import Dict, Any
from .base import BaseAgent

# Try to import database functions for RAG
try:
    from backend.database.database import get_recent_news
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False

class NewsAgent(BaseAgent):
    """
    Agent responsible for fetching recent news and headlines for a stock.
    Primary: RAG database (pre-indexed news)
    Fallback: yfinance ticker.news
    """
    
    def __init__(self):
        super().__init__(name="NewsAgent")
        
    def _get_stock_news(self, symbol: str) -> list:
        """Fetch recent news - prioritize RAG database, fallback to yfinance."""
        
        # PRIMARY: Try RAG database first (faster, pre-embedded)
        if DB_AVAILABLE:
            try:
                db_news = get_recent_news(symbol, limit=5)
                if db_news:
                    self._log_activity(f"Got {len(db_news)} news from RAG database")
                    return db_news
            except Exception as e:
                self._log_activity(f"Database news failed: {e}")
        
        # FALLBACK: yfinance API
        try:
            import yfinance as yf
            ticker = yf.Ticker(f"{symbol}.NS")
            news = ticker.news
            
            if not news:
                return []
            
            # Extract key info from top 5 news items
            headlines = []
            for item in news[:5]:
                headlines.append({
                    "headline": item.get("title", ""),
                    "summary": item.get("summary", ""),
                    "source": item.get("publisher", ""),
                    "url": item.get("link", ""),
                    "published_at": item.get("providerPublishTime", "")
                })
            
            self._log_activity(f"Got {len(headlines)} news from yfinance API")
            return headlines
            
        except Exception as e:
            self._log_activity(f"Failed to fetch news: {e}")
            return []
        
    def process(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fetches recent news headlines for the stock.
        Returns has_data=True only if relevant news is found.
        """
        symbol = context.get("formatted_tickers", [])[0] if context.get("formatted_tickers") else None
        
        if not symbol:
            return {
                "has_data": False,
                "data": {},
                "source": "NewsAgent",
                "relevance_score": 0
            }
            
        self._log_activity(f"Fetching news for {symbol}")
        news = self._get_stock_news(symbol)
        
        if not news:
            return {
                "has_data": False,
                "data": {},
                "source": "NewsAgent",
                "relevance_score": 0
            }
        
        # Determine relevance based on query
        query_lower = query.lower()
        is_news_focused = any(term in query_lower for term in 
            ['news', 'headline', 'announcement', 'update', 'latest', 'recent'])
        
        return {
            "has_data": True,
            "data": {"news": news, "symbol": symbol},
            "source": "NewsAgent",
            "relevance_score": 0.9 if is_news_focused else 0.4
        }
