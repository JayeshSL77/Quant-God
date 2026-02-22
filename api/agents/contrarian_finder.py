"""
Contrarian Finder
Identifies overlooked opportunities where market sentiment diverges from fundamentals.
"What is everyone missing?"
"""

import os
import logging
import json
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None
import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ContrarianFinder")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

INDIA_DB = os.getenv("DATABASE_URL", 
    "postgresql://postgres:analyezdb77**@analyezdb.cbimec0sg2ch.ap-south-1.rds.amazonaws.com:5432/analyezdb")
US_DB = os.getenv("US_DATABASE_URL",
    "postgresql://postgres:analyezdb77**@analyezdb.cbimec0sg2ch.ap-south-1.rds.amazonaws.com:5432/usmarkets")


@dataclass
class ContrarianOpportunity:
    """A potential contrarian investment opportunity."""
    symbol: str
    company_name: str
    contrarian_score: int  # 0-100: how contrarian the opportunity is
    opportunity_type: str  # undervalued_quality, turnaround, misunderstood
    
    market_view: str  # What the market thinks
    hidden_insight: str  # What we found
    
    catalyst: str  # What could unlock value
    timeline: str  # Expected timeline
    
    evidence: List[str]  # Supporting data points
    risks: List[str]
    
    upside_potential: str
    confidence: float


class ContrarianAnalyzer:
    """
    Finds stocks where market sentiment diverges from fundamental quality.
    """
    
    CONTRARIAN_PROMPT = """You are a contrarian investment analyst looking for overlooked opportunities.
Analyze this company data to identify what the market might be missing.

Company: {symbol}
Industry: {industry}

Recent Performance/Sentiment: {sentiment}
Fundamentals: {fundamentals}
Annual Report Key Points: {ar_highlights}

Look for:
1. Quality companies with negative sentiment (undervalued)
2. Improving fundamentals not yet in price
3. Misunderstood business models
4. Turnaround situations
5. Hidden optionality

Return JSON:
{{
    "contrarian_score": 0-100,
    "opportunity_type": "undervalued_quality|turnaround|misunderstood|hidden_optionality",
    "market_view": "What consensus/market currently thinks",
    "hidden_insight": "What they're missing - be specific",
    "catalyst": "What could change perception",
    "timeline": "When catalyst might play out",
    "evidence": ["data point 1", "data point 2", "data point 3"],
    "risks": ["risk 1", "risk 2"],
    "upside_potential": "X% if thesis plays out",
    "confidence": 0.X
}}"""

    def __init__(self, market: str = "india"):
        self.market = market
        self.db_url = INDIA_DB if market == "india" else US_DB
        self.client = OpenAI(api_key=OPENAI_API_KEY) if (OpenAI and OPENAI_API_KEY) else None
    
    def find_contrarian_opportunities(self, symbols: List[str] = None, limit: int = 10) -> List[ContrarianOpportunity]:
        """Find contrarian opportunities across given symbols or screen the universe."""
        opportunities = []
        
        if symbols is None:
            symbols = self._get_screened_symbols(limit * 3)  # Get 3x to filter
        
        for symbol in symbols:
            try:
                opp = self.analyze_stock(symbol)
                if opp and opp.contrarian_score >= 60:  # Only high-score opportunities
                    opportunities.append(opp)
            except Exception as e:
                logger.debug(f"Error analyzing {symbol}: {e}")
                continue
        
        # Sort by contrarian score
        opportunities.sort(key=lambda x: x.contrarian_score, reverse=True)
        return opportunities[:limit]
    
    def _get_screened_symbols(self, limit: int) -> List[str]:
        """Get symbols to screen based on basic criteria."""
        try:
            conn = psycopg2.connect(self.db_url)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            # Get stocks with recent annual reports
            if self.market == "india":
                cur.execute("""
                    SELECT DISTINCT symbol FROM annual_reports
                    ORDER BY symbol LIMIT %s
                """, (limit,))
            else:
                cur.execute("""
                    SELECT DISTINCT symbol FROM annual_reports_10k
                    ORDER BY symbol LIMIT %s
                """, (limit,))
            
            symbols = [row['symbol'] for row in cur.fetchall()]
            cur.close()
            conn.close()
            return symbols
            
        except Exception as e:
            logger.error(f"Error getting symbols: {e}")
            return []
    
    def analyze_stock(self, symbol: str) -> Optional[ContrarianOpportunity]:
        """Analyze a single stock for contrarian potential."""
        if not self.client:
            return None
        
        # Gather data
        data = self._gather_data(symbol)
        
        if not data.get('ar_highlights'):
            return None
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a contrarian analyst finding overlooked opportunities. Be skeptical but identify genuine mispricings. Return JSON only."},
                    {"role": "user", "content": self.CONTRARIAN_PROMPT.format(
                        symbol=symbol,
                        industry=data.get('industry', 'Unknown'),
                        sentiment=data.get('sentiment', 'Neutral'),
                        fundamentals=json.dumps(data.get('fundamentals', {})),
                        ar_highlights=data.get('ar_highlights', '')[:5000]
                    )}
                ],
                temperature=0.4,
                max_tokens=600
            )
            
            content = response.choices[0].message.content.strip()
            if content.startswith("```"):
                content = re.sub(r'^```json?\n?', '', content)
                content = re.sub(r'\n?```$', '', content)
            
            result = json.loads(content)
            
            return ContrarianOpportunity(
                symbol=symbol,
                company_name=data.get('company_name', symbol),
                contrarian_score=result.get('contrarian_score', 50),
                opportunity_type=result.get('opportunity_type', 'unknown'),
                market_view=result.get('market_view', ''),
                hidden_insight=result.get('hidden_insight', ''),
                catalyst=result.get('catalyst', ''),
                timeline=result.get('timeline', ''),
                evidence=result.get('evidence', []),
                risks=result.get('risks', []),
                upside_potential=result.get('upside_potential', 'N/A'),
                confidence=result.get('confidence', 0.5)
            )
            
        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {e}")
            return None
    
    def _gather_data(self, symbol: str) -> Dict[str, Any]:
        """Gather data for contrarian analysis."""
        data = {"symbol": symbol}
        
        try:
            conn = psycopg2.connect(self.db_url)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            if self.market == "india":
                cur.execute("""
                    SELECT symbol, company_name, nuanced_summary
                    FROM annual_reports
                    WHERE symbol = %s ORDER BY fiscal_year DESC LIMIT 1
                """, (symbol,))
                row = cur.fetchone()
                if row:
                    data['company_name'] = row.get('company_name', symbol)
                    data['ar_highlights'] = row.get('nuanced_summary', '')
            else:
                cur.execute("""
                    SELECT cm.company_name, cm.sector, cm.industry,
                           ar.mda_section, ar.business_section
                    FROM company_metadata cm
                    LEFT JOIN annual_reports_10k ar ON cm.symbol = ar.symbol
                    WHERE cm.symbol = %s
                    ORDER BY ar.fiscal_year DESC LIMIT 1
                """, (symbol,))
                row = cur.fetchone()
                if row:
                    data['company_name'] = row.get('company_name', symbol)
                    data['industry'] = row.get('industry', 'Unknown')
                    data['ar_highlights'] = f"{row.get('business_section', '')}\n{row.get('mda_section', '')}"
            
            cur.close()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error gathering data for {symbol}: {e}")
        
        # Placeholder for sentiment and fundamentals
        data['sentiment'] = "Neutral"
        data['fundamentals'] = {}
        
        return data


def format_contrarian_for_ui(opportunities: List[ContrarianOpportunity]) -> Dict:
    """Format contrarian opportunities for UI display."""
    
    type_icons = {
        "undervalued_quality": "💎",
        "turnaround": "🔄",
        "misunderstood": "🔍",
        "hidden_optionality": "🎯"
    }
    
    return {
        "header": {
            "title": "Contrarian Opportunities",
            "subtitle": "What the market is missing",
            "count": len(opportunities)
        },
        
        "opportunities": [
            {
                "symbol": o.symbol,
                "company_name": o.company_name,
                "score": o.contrarian_score,
                "type": o.opportunity_type.replace("_", " ").title(),
                "type_icon": type_icons.get(o.opportunity_type, "🔍"),
                
                "market_view": {
                    "label": "Market Thinks",
                    "text": o.market_view,
                    "icon": "👥"
                },
                "hidden_insight": {
                    "label": "We Found",
                    "text": o.hidden_insight,
                    "icon": "💡"
                },
                
                "catalyst": o.catalyst,
                "timeline": o.timeline,
                "upside": o.upside_potential,
                
                "evidence": o.evidence,
                "risks": o.risks,
                
                "confidence_bar": int(o.confidence * 100)
            }
            for o in opportunities
        ]
    }


if __name__ == "__main__":
    analyzer = ContrarianAnalyzer(market="us")
    
    print("Finding contrarian opportunities...")
    # Test with specific symbols
    test_symbols = ["INTC", "DIS", "PYPL"]
    
    for symbol in test_symbols:
        opp = analyzer.analyze_stock(symbol)
        if opp:
            print(f"\n{'='*50}")
            print(f"{opp.symbol} - Score: {opp.contrarian_score}")
            print(f"Type: {opp.opportunity_type}")
            print(f"Market thinks: {opp.market_view[:100]}...")
            print(f"Hidden insight: {opp.hidden_insight[:100]}...")
