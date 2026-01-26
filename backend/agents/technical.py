
from typing import Dict, Any
from .base import BaseAgent

class TechnicalAgent(BaseAgent):
    """
    Agent responsible for technical analysis indicators.
    Provides: 50-DMA, 200-DMA, RSI, trend signals.
    """
    
    def __init__(self):
        super().__init__(name="TechnicalAgent")
        
    def _get_technical_indicators(self, symbol: str) -> Dict[str, Any]:
        """Calculate technical indicators from yfinance data."""
        try:
            import yfinance as yf
            import pandas as pd
            
            ticker = yf.Ticker(f"{symbol}.NS")
            # Get 1 year of daily data for indicator calculation
            hist = ticker.history(period="1y")
            
            if hist.empty or len(hist) < 50:
                return {}
            
            close = hist['Close']
            current_price = close.iloc[-1]
            
            # Calculate DMAs
            dma_50 = close.rolling(window=50).mean().iloc[-1]
            dma_200 = close.rolling(window=200).mean().iloc[-1] if len(close) >= 200 else None
            
            # Calculate RSI (14-day)
            delta = close.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            rsi_value = rsi.iloc[-1]
            
            # 52-week high/low
            high_52w = close.max()
            low_52w = close.min()
            
            # Trend signals
            above_50dma = current_price > dma_50
            above_200dma = current_price > dma_200 if dma_200 else None
            
            # Distance from 52w high
            pct_from_high = ((current_price - high_52w) / high_52w) * 100
            
            return {
                "current_price": round(current_price, 2),
                "dma_50": round(dma_50, 2),
                "dma_200": round(dma_200, 2) if dma_200 else None,
                "rsi_14": round(rsi_value, 1),
                "high_52w": round(high_52w, 2),
                "low_52w": round(low_52w, 2),
                "pct_from_52w_high": round(pct_from_high, 1),
                "above_50dma": above_50dma,
                "above_200dma": above_200dma,
                "trend_signal": self._get_trend_signal(above_50dma, above_200dma, rsi_value)
            }
            
        except Exception as e:
            self._log_activity(f"Failed to calculate technicals: {e}")
            return {}
    
    def _get_trend_signal(self, above_50, above_200, rsi) -> str:
        """Generate a simple trend signal."""
        if above_50 and above_200:
            if rsi > 70:
                return "Strong Uptrend (Overbought)"
            return "Strong Uptrend"
        elif not above_50 and above_200:
            return "Short-term Pullback in Uptrend"
        elif above_50 and not above_200:
            return "Recovery Attempt"
        else:
            if rsi < 30:
                return "Downtrend (Oversold)"
            return "Downtrend"
        
    def process(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculates technical indicators for the stock.
        High relevance for 'buy/sell' queries, medium for price queries.
        """
        symbol = context.get("formatted_tickers", [])[0] if context.get("formatted_tickers") else None
        
        if not symbol:
            return {
                "has_data": False,
                "data": {},
                "source": "TechnicalAgent",
                "relevance_score": 0
            }
            
        self._log_activity(f"Calculating technicals for {symbol}")
        technicals = self._get_technical_indicators(symbol)
        
        if not technicals:
            return {
                "has_data": False,
                "data": {},
                "source": "TechnicalAgent",
                "relevance_score": 0
            }
        
        # Determine relevance
        query_lower = query.lower()
        is_decision_query = any(term in query_lower for term in 
            ['buy', 'sell', 'should', 'invest', 'entry', 'exit', 'technical', 'trend', 'dma', 'rsi'])
        
        return {
            "has_data": True,
            "data": {"technicals": technicals, "symbol": symbol},
            "source": "TechnicalAgent",
            "relevance_score": 0.9 if is_decision_query else 0.5
        }
