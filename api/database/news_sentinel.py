"""
News Sentinel - Real-time Sentiment Scraper
Polls Google News RSS for Indian stocks to provide real-time sentiment analysis without X API costs.
"""

import logging
import requests
import xml.etree.ElementTree as ET
from typing import List, Dict, Any
from datetime import datetime
import time
from urllib.parse import quote

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("NewsSentinel")

class NewsSentinel:
    """
    Scrapes Google News RSS for real-time market sentiment.
    """
    
    RSS_URL = "https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
    
    POSITIVE_KEYWORDS = [
        'surge', 'jump', 'soar', 'rally', 'gain', 'grow', 'profit', 'beat', 'bull', 'bullish',
        'upgrade', 'buy', 'strong', 'record', 'high', 'win', 'deal', 'acquisition', 'positive'
    ]
    
    NEGATIVE_KEYWORDS = [
        'plunge', 'fall', 'drop', 'crash', 'loss', 'miss', 'bear', 'bearish', 'downgrade',
        'sell', 'weak', 'low', 'fraud', 'scam', 'investigation', 'negative', 'debt', 'default'
    ]
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
    
    def _calculate_sentiment(self, text: str) -> float:
        """Simple keyword-based sentiment score (-1.0 to 1.0)."""
        text = text.lower()
        score = 0.0
        
        for word in self.POSITIVE_KEYWORDS:
            if word in text:
                score += 0.2
        
        for word in self.NEGATIVE_KEYWORDS:
            if word in text:
                score -= 0.2
                
        return max(-1.0, min(1.0, score))
    
    def fetch_news(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Fetch news for a query (e.g., 'RELIANCE stock news').
        """
        try:
            encoded_query = quote(query)
            url = self.RSS_URL.format(query=encoded_query)
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            root = ET.fromstring(response.content)
            items = root.findall('.//item')
            
            news_items = []
            for item in items[:limit]:
                title = item.find('title').text if item.find('title') is not None else ""
                link = item.find('link').text if item.find('link') is not None else ""
                pub_date = item.find('pubDate').text if item.find('pubDate') is not None else ""
                
                # Basic cleanup
                source = "Google News"
                if "-" in title:
                    parts = title.rsplit("-", 1)
                    title = parts[0].strip()
                    source = parts[1].strip()
                
                sentiment_score = self._calculate_sentiment(title)
                
                news_items.append({
                    "headline": title,
                    "url": link,
                    "source": source,
                    "published_at": pub_date,
                    "sentiment_score": sentiment_score
                })
            
            return news_items
            
        except Exception as e:
            logger.error(f"Failed to fetch news for '{query}': {e}")
            return []

    def get_market_sentiment(self, symbols: List[str]) -> Dict[str, Any]:
        """
        Get aggregated sentiment for a list of symbols.
        """
        results = {}
        for symbol in symbols:
            news = self.fetch_news(f"{symbol} share price news", limit=5)
            if not news:
                results[symbol] = {"score": 0, "status": "Neutral", "news_count": 0}
                continue
                
            avg_score = sum(n['sentiment_score'] for n in news) / len(news)
            
            status = "Neutral"
            if avg_score > 0.2: status = "Bullish"
            elif avg_score > 0.5: status = "Very Bullish"
            elif avg_score < -0.2: status = "Bearish"
            elif avg_score < -0.5: status = "Very Bearish"
            
            results[symbol] = {
                "score": round(avg_score, 2),
                "status": status,
                "news_count": len(news),
                "top_headline": news[0]['headline']
            }
            time.sleep(0.5)  # Polite delay
            
        return results

if __name__ == "__main__":
    sentinel = NewsSentinel()
    
    # Test with a few stocks
    test_stocks = ["RELIANCE", "TCS", "ADANIENT", "INFY"]
    print(f"Fetching real-time sentiment for: {test_stocks}...")
    
    sentiment = sentinel.get_market_sentiment(test_stocks)
    
    print("\n" + "="*50)
    print("REAL-TIME MARKET SENTIMENT (Source: Google News)")
    print("="*50)
    
    for symbol, data in sentiment.items():
        emoji = "⚪"
        if "Bullish" in data['status']: emoji = "🟢"
        if "Bearish" in data['status']: emoji = "🔴"
        
        print(f"{emoji} {symbol}: {data['status']} (Score: {data['score']})")
        if data['news_count'] > 0:
            print(f"   Latest: {data['top_headline']}")
        print("-" * 30)
