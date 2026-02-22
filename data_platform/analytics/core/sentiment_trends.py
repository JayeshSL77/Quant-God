"""
Earnings Sentiment Trends
Tracks management tone across earnings calls over multiple quarters.
Detects sentiment shifts before they hit stock price.
"""

import os
import logging
import re
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None
import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SentimentTrends")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Database URLs
INDIA_DB = os.getenv("DATABASE_URL", 
    "postgresql://postgres:analyezdb77**@analyezdb.cbimec0sg2ch.ap-south-1.rds.amazonaws.com:5432/analyezdb")
US_DB = os.getenv("US_DATABASE_URL",
    "postgresql://postgres:analyezdb77**@analyezdb.cbimec0sg2ch.ap-south-1.rds.amazonaws.com:5432/usmarkets")


@dataclass
class QuarterSentiment:
    """Sentiment for a single quarter."""
    quarter: str  # Q1 FY24
    fiscal_year: str
    sentiment_score: float  # -1 to 1
    confidence_score: float  # How confident the model was
    key_phrases: List[str]
    tone: str  # bullish, cautious, neutral, concerned, bearish
    summary: str


@dataclass  
class SentimentTrend:
    """Multi-quarter sentiment trend analysis."""
    symbol: str
    quarters: List[QuarterSentiment]
    trend_direction: str  # improving, stable, declining
    trend_strength: float  # 0-1
    notable_shift: Optional[str]  # Description of any major tone shift
    latest_tone: str


class SentimentAnalyzer:
    """
    Analyzes management sentiment from earnings calls.
    Tracks changes across quarters.
    """
    
    SENTIMENT_PROMPT = """Analyze the tone and sentiment of this earnings call excerpt.
Focus on management's confidence, forward-looking statements, and word choice.

Rate the sentiment from -1.0 (very bearish/concerned) to +1.0 (very bullish/confident).
Identify the overall tone and key phrases that indicate sentiment.

Excerpt:
{text}

Return JSON only:
{{
    "sentiment_score": 0.X,
    "confidence": 0.X,
    "tone": "bullish|cautious|neutral|concerned|bearish",
    "key_phrases": ["phrase1", "phrase2", "phrase3"],
    "summary": "One sentence summary of management's outlook"
}}"""

    POSITIVE_KEYWORDS = [
        'strong', 'growth', 'momentum', 'confident', 'optimistic', 'exceeded',
        'record', 'robust', 'tailwind', 'accelerating', 'visibility', 'demand'
    ]
    
    NEGATIVE_KEYWORDS = [
        'challenging', 'headwind', 'uncertainty', 'pressure', 'decline', 'cautious',
        'difficult', 'softness', 'weakness', 'concerned', 'slowdown', 'macro'
    ]
    
    def __init__(self, market: str = "india"):
        self.market = market
        self.db_url = INDIA_DB if market == "india" else US_DB
        self.client = OpenAI(api_key=OPENAI_API_KEY) if (OpenAI and OPENAI_API_KEY) else None
    
    def analyze_transcript(self, text: str, use_ai: bool = True) -> Dict[str, Any]:
        """Analyze sentiment of a single transcript."""
        if use_ai and self.client:
            return self._analyze_with_ai(text)
        else:
            return self._analyze_with_keywords(text)
    
    def _analyze_with_ai(self, text: str) -> Dict[str, Any]:
        """Use GPT for sentiment analysis."""
        try:
            # Truncate to first 10k chars (prepared remarks + some Q&A)
            text = text[:10000]
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Analyze earnings call sentiment. Return JSON only."},
                    {"role": "user", "content": self.SENTIMENT_PROMPT.format(text=text)}
                ],
                temperature=0.2,
                max_tokens=300
            )
            
            content = response.choices[0].message.content.strip()
            if content.startswith("```"):
                content = re.sub(r'^```json?\n?', '', content)
                content = re.sub(r'\n?```$', '', content)
            
            return json.loads(content)
            
        except Exception as e:
            logger.error(f"AI analysis error: {e}")
            return self._analyze_with_keywords(text)
    
    def _analyze_with_keywords(self, text: str) -> Dict[str, Any]:
        """Fallback keyword-based analysis."""
        text_lower = text.lower()
        
        pos_count = sum(1 for kw in self.POSITIVE_KEYWORDS if kw in text_lower)
        neg_count = sum(1 for kw in self.NEGATIVE_KEYWORDS if kw in text_lower)
        
        total = pos_count + neg_count
        if total == 0:
            score = 0
        else:
            score = (pos_count - neg_count) / total
        
        if score > 0.3:
            tone = "bullish"
        elif score > 0.1:
            tone = "cautious"
        elif score > -0.1:
            tone = "neutral"
        elif score > -0.3:
            tone = "concerned"
        else:
            tone = "bearish"
        
        return {
            "sentiment_score": round(score, 2),
            "confidence": 0.6,
            "tone": tone,
            "key_phrases": [],
            "summary": f"Keyword analysis: {pos_count} positive, {neg_count} negative signals"
        }
    
    def get_quarterly_sentiments(self, symbol: str, quarters: int = 8) -> List[QuarterSentiment]:
        """Fetch and analyze multiple quarters of earnings calls."""
        results = []
        
        try:
            conn = psycopg2.connect(self.db_url)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            # Fetch transcripts
            if self.market == "india":
                cur.execute("""
                    SELECT symbol, fiscal_year, quarter, content
                    FROM concalls
                    WHERE symbol = %s AND content IS NOT NULL
                    ORDER BY fiscal_year DESC, quarter DESC
                    LIMIT %s
                """, (symbol, quarters))
            else:
                cur.execute("""
                    SELECT symbol, fiscal_year, quarter, transcript
                    FROM earnings_transcripts
                    WHERE symbol = %s AND transcript IS NOT NULL
                    ORDER BY fiscal_year DESC, quarter DESC
                    LIMIT %s
                """, (symbol, quarters))
            
            rows = cur.fetchall()
            cur.close()
            conn.close()
            
            for row in rows:
                text = row.get('content') or row.get('transcript', '')
                if not text or len(text) < 1000:
                    continue
                
                analysis = self.analyze_transcript(text, use_ai=True)
                
                results.append(QuarterSentiment(
                    quarter=row.get('quarter', 'Q?'),
                    fiscal_year=row.get('fiscal_year', ''),
                    sentiment_score=analysis.get('sentiment_score', 0),
                    confidence_score=analysis.get('confidence', 0.5),
                    key_phrases=analysis.get('key_phrases', []),
                    tone=analysis.get('tone', 'neutral'),
                    summary=analysis.get('summary', '')
                ))
            
        except Exception as e:
            logger.error(f"Error fetching transcripts: {e}")
        
        return results
    
    def analyze_trend(self, symbol: str, quarters: int = 8) -> SentimentTrend:
        """Analyze sentiment trend across multiple quarters."""
        quarter_data = self.get_quarterly_sentiments(symbol, quarters)
        
        if not quarter_data:
            return SentimentTrend(
                symbol=symbol,
                quarters=[],
                trend_direction="unknown",
                trend_strength=0,
                notable_shift=None,
                latest_tone="unknown"
            )
        
        # Calculate trend
        if len(quarter_data) >= 3:
            recent = sum(q.sentiment_score for q in quarter_data[:2]) / 2
            older = sum(q.sentiment_score for q in quarter_data[-2:]) / 2
            
            diff = recent - older
            
            if diff > 0.2:
                direction = "improving"
            elif diff < -0.2:
                direction = "declining"
            else:
                direction = "stable"
            
            strength = min(1.0, abs(diff) / 0.5)
        else:
            direction = "insufficient_data"
            strength = 0
        
        # Detect notable shifts
        notable_shift = None
        for i in range(1, len(quarter_data)):
            prev = quarter_data[i].sentiment_score
            curr = quarter_data[i-1].sentiment_score
            if abs(curr - prev) > 0.4:
                notable_shift = f"Major shift from {quarter_data[i].tone} to {quarter_data[i-1].tone} in {quarter_data[i-1].quarter}"
                break
        
        return SentimentTrend(
            symbol=symbol,
            quarters=quarter_data,
            trend_direction=direction,
            trend_strength=round(strength, 2),
            notable_shift=notable_shift,
            latest_tone=quarter_data[0].tone if quarter_data else "unknown"
        )


def format_sentiment_for_ui(trend: SentimentTrend) -> Dict:
    """Format sentiment trend for optimal UI display."""
    
    # Direction colors
    direction_colors = {
        "improving": "#22c55e",
        "stable": "#eab308", 
        "declining": "#ef4444",
        "unknown": "#94a3b8"
    }
    
    # Create chart data
    chart_data = [
        {
            "quarter": f"{q.quarter} {q.fiscal_year}",
            "score": q.sentiment_score,
            "tone": q.tone
        }
        for q in reversed(trend.quarters)  # Chronological order for chart
    ]
    
    return {
        # Header
        "header": {
            "symbol": trend.symbol,
            "current_tone": trend.latest_tone.upper(),
            "trend": trend.trend_direction,
            "trend_color": direction_colors.get(trend.trend_direction, "#94a3b8")
        },
        
        # Trend indicator
        "trend_indicator": {
            "direction": trend.trend_direction,
            "strength": trend.trend_strength,
            "icon": "📈" if trend.trend_direction == "improving" else "📉" if trend.trend_direction == "declining" else "➡️"
        },
        
        # Alert for notable shifts
        "alert": {
            "show": trend.notable_shift is not None,
            "message": trend.notable_shift,
            "type": "warning"
        } if trend.notable_shift else None,
        
        # Line chart data
        "chart": {
            "type": "line",
            "data": chart_data,
            "yAxis": {"min": -1, "max": 1}
        },
        
        # Quarter cards with visual bars
        "quarters": [
            {
                "label": f"{q.quarter} {q.fiscal_year}",
                "score": q.sentiment_score,
                "tone": q.tone,
                "bar_width": int((q.sentiment_score + 1) / 2 * 100),  # 0-100 scale
                "summary": q.summary,
                "key_phrases": q.key_phrases[:3]
            }
            for q in trend.quarters
        ]
    }


if __name__ == "__main__":
    analyzer = SentimentAnalyzer(market="india")
    
    # Test text
    sample_text = """
    Good morning everyone. We're pleased to report another strong quarter. 
    Revenue grew 25% year-over-year, exceeding our guidance. We're seeing 
    robust demand across all segments and remain confident in our full-year 
    outlook. While there are some macro headwinds, our diversified business 
    model and strong execution give us visibility into continued growth.
    """
    
    result = analyzer.analyze_transcript(sample_text, use_ai=False)
    print(f"\nSentiment: {result['sentiment_score']} ({result['tone']})")
    print(f"Summary: {result['summary']}")
