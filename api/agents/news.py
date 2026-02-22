
from typing import Dict, Any
from .base import BaseAgent

# Try to import database functions for RAG
try:
    from api.database.database import get_recent_news
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False

class NewsAgent(BaseAgent):
    """
    Agent responsible for fetching recent news and headlines for a stock.
    Primary: RAG database (pre-indexed news)
    Fallback: yfinance ticker.news
    P4: Now includes sentiment scoring for each headline
    """
    
    # Sentiment keyword lists
    POSITIVE_KEYWORDS = [
        'surge', 'surges', 'soar', 'soars', 'rally', 'rallies', 'gain', 'gains',
        'growth', 'grow', 'grows', 'beat', 'beats', 'exceed', 'exceeds', 'outperform',
        'upgrade', 'upgraded', 'bullish', 'strong', 'record', 'high', 'profit',
        'positive', 'optimistic', 'boost', 'boosts', 'recovery', 'expand', 'expands',
        'breakthrough', 'success', 'win', 'wins', 'award', 'milestone', 'dividend'
    ]
    
    NEGATIVE_KEYWORDS = [
        'fall', 'falls', 'drop', 'drops', 'decline', 'declines', 'plunge', 'plunges',
        'crash', 'crashes', 'loss', 'losses', 'miss', 'misses', 'downgrade', 'downgraded',
        'bearish', 'weak', 'concern', 'concerns', 'risk', 'risks', 'warning', 'warns',
        'cut', 'cuts', 'reduce', 'reduces', 'layoff', 'layoffs', 'lawsuit', 'probe',
        'investigation', 'fraud', 'scandal', 'default', 'debt', 'negative', 'struggle'
    ]
    
    def __init__(self):
        super().__init__(name="NewsAgent")
    
    def _analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """Analyze sentiment of a headline/summary using keyword matching."""
        text_lower = text.lower()
        
        positive_count = sum(1 for word in self.POSITIVE_KEYWORDS if word in text_lower)
        negative_count = sum(1 for word in self.NEGATIVE_KEYWORDS if word in text_lower)
        
        if positive_count > negative_count:
            sentiment = 'positive'
            score = min(1.0, 0.5 + (positive_count - negative_count) * 0.1)
        elif negative_count > positive_count:
            sentiment = 'negative'
            score = max(-1.0, -0.5 - (negative_count - positive_count) * 0.1)
        else:
            sentiment = 'neutral'
            score = 0.0
        
        return {
            'sentiment': sentiment,
            'score': round(score, 2),
            'positive_signals': positive_count,
            'negative_signals': negative_count
        }
        
    def _get_stock_news(self, symbol: str) -> list:
        """Fetch recent news - prioritize RAG database, fallback to yfinance."""
        
        # PRIMARY: Try RAG database first (faster, pre-embedded)
        if DB_AVAILABLE:
            try:
                db_news = get_recent_news(symbol, limit=5)
                if db_news:
                    self._log_activity(f"Got {len(db_news)} news from RAG database")
                    # Add sentiment to database news
                    for item in db_news:
                        headline = item.get('headline', item.get('title', ''))
                        sentiment_data = self._analyze_sentiment(headline)
                        item.update(sentiment_data)
                    return db_news
            except Exception as e:
                self._log_activity(f"Database news failed: {e}")
        
        # SECONDARY: Try News Sentinel (Real-time Google News)
        try:
            from api.database.news_sentinel import NewsSentinel
            sentinel = NewsSentinel()
            
            self._log_activity(f"Fetching real-time news from News Sentinel for {symbol}")
            sentinel_news = sentinel.fetch_news(f"{symbol} stock news", limit=5)
            
            if sentinel_news:
                return sentinel_news
                
        except Exception as e:
            self._log_activity(f"News Sentinel failed: {e}")

        # FALLBACK: yfinance API (if Sentinel fails)
        try:
            import yfinance as yf
            ticker = yf.Ticker(f"{symbol}.NS")
            news = ticker.news
            
            if not news:
                return []
            
            # Extract key info
            headlines = []
            for item in news[:5]:
                headline_text = item.get("title", "")
                
                # Use simplified sentiment logic if available
                sentiment_data = {'sentiment': 'neutral', 'score': 0}
                if hasattr(self, '_analyze_sentiment'):
                    sentiment_data = self._analyze_sentiment(headline_text)
                    
                headlines.append({
                    "headline": headline_text,
                    "summary": item.get("summary", ""),
                    "source": item.get("publisher", ""),
                    "url": item.get("link", ""),
                    "published_at": item.get("providerPublishTime", ""),
                    **sentiment_data
                })
            
            return headlines
            
        except Exception as e:
            self._log_activity(f"Failed to fetch news: {e}")
            return []

        
    def process(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fetches recent news headlines for the stock.
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
        
        return {
            "has_data": True,
            "data": {"news": news, "symbol": symbol},
            "source": "NewsAgent",
            "relevance_score": 0.9
        }
