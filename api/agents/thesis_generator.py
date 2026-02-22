"""
Investment Thesis Generator
Generates comprehensive investment thesis documents with AI analysis.
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
logger = logging.getLogger("ThesisGenerator")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

INDIA_DB = os.getenv("DATABASE_URL", 
    "postgresql://postgres:analyezdb77**@analyezdb.cbimec0sg2ch.ap-south-1.rds.amazonaws.com:5432/analyezdb")
US_DB = os.getenv("US_DATABASE_URL",
    "postgresql://postgres:analyezdb77**@analyezdb.cbimec0sg2ch.ap-south-1.rds.amazonaws.com:5432/usmarkets")


@dataclass
class InvestmentThesis:
    """Complete investment thesis."""
    symbol: str
    company_name: str
    recommendation: str  # Buy, Hold, Sell
    conviction: str  # High, Medium, Low
    target_return: str
    time_horizon: str
    
    executive_summary: str
    bull_case: str
    bear_case: str
    
    competitive_moat: str
    growth_drivers: List[str]
    risk_factors: List[str]
    
    valuation_summary: str
    key_metrics: Dict[str, Any]
    
    catalysts: List[Dict[str, str]]  # {event, timeline, impact}
    
    generated_at: str


class ThesisGenerator:
    """
    Generates professional investment thesis documents.
    """
    
    THESIS_PROMPT = """You are a senior equity research analyst. Generate a complete investment thesis for this company.

Company: {symbol}
Industry: {industry}

Data:
- Annual Report Summary: {ar_summary}
- Recent Earnings: {earnings_summary}
- Key Metrics: {metrics}

Generate a comprehensive investment thesis in this exact JSON format:
{{
    "recommendation": "Buy|Hold|Sell",
    "conviction": "High|Medium|Low",
    "target_return": "X% over Y months",
    "time_horizon": "6-12 months",
    
    "executive_summary": "2-3 sentence summary of the investment case",
    
    "bull_case": "2-3 paragraph bullish scenario",
    "bear_case": "1-2 paragraph bearish scenario",
    
    "competitive_moat": "Description of durable competitive advantages",
    
    "growth_drivers": ["driver 1", "driver 2", "driver 3"],
    "risk_factors": ["risk 1", "risk 2", "risk 3"],
    
    "valuation_summary": "Paragraph on current valuations vs intrinsic value",
    
    "catalysts": [
        {{"event": "Event name", "timeline": "Q1 2026", "impact": "High|Medium|Low"}}
    ]
}}"""

    def __init__(self, market: str = "india"):
        self.market = market
        self.db_url = INDIA_DB if market == "india" else US_DB
        self.client = OpenAI(api_key=OPENAI_API_KEY) if (OpenAI and OPENAI_API_KEY) else None
    
    def gather_data(self, symbol: str) -> Dict[str, Any]:
        """Gather all relevant data for thesis generation."""
        data = {"symbol": symbol, "industry": "Unknown"}
        
        try:
            conn = psycopg2.connect(self.db_url)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            if self.market == "india":
                # Get annual report
                cur.execute("""
                    SELECT symbol, fiscal_year, nuanced_summary, title
                    FROM annual_reports
                    WHERE symbol = %s ORDER BY fiscal_year DESC LIMIT 1
                """, (symbol,))
                ar = cur.fetchone()
                if ar:
                    data['company_name'] = ar.get('title', '').split(' - ')[0] if ar.get('title') else symbol
                    data['ar_summary'] = ar.get('nuanced_summary', '')[:3000]
                
                # Get earnings
                cur.execute("""
                    SELECT quarter, fiscal_year, transcript
                    FROM concalls
                    WHERE symbol = %s ORDER BY fiscal_year DESC, quarter DESC LIMIT 1
                """, (symbol,))
                cc = cur.fetchone()
                if cc:
                    data['earnings_summary'] = cc.get('transcript', '')[:2000]
            else:
                # US market
                cur.execute("""
                    SELECT cm.company_name, cm.sector, cm.industry,
                           ar.fiscal_year, ar.mda_section
                    FROM company_metadata cm
                    LEFT JOIN annual_reports_10k ar ON cm.symbol = ar.symbol
                    WHERE cm.symbol = %s
                    ORDER BY ar.fiscal_year DESC LIMIT 1
                """, (symbol,))
                row = cur.fetchone()
                if row:
                    data['company_name'] = row.get('company_name', symbol)
                    data['industry'] = row.get('industry', 'Unknown')
                    data['ar_summary'] = row.get('mda_section', '')[:3000]
                
                data['earnings_summary'] = "Pending earnings data"
            
            cur.close()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error gathering data: {e}")
            data['company_name'] = symbol
            data['ar_summary'] = ""
            data['earnings_summary'] = ""
        
        # Placeholder metrics
        data['metrics'] = {
            "revenue_growth": "N/A",
            "profit_margin": "N/A",
            "roic": "N/A",
            "pe_ratio": "N/A"
        }
        
        return data
    
    def generate(self, symbol: str) -> InvestmentThesis:
        """Generate complete investment thesis."""
        logger.info(f"Generating thesis for {symbol}...")
        
        data = self.gather_data(symbol)
        
        if not self.client:
            return self._default_thesis(symbol, data)
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a senior equity research analyst. Generate professional investment theses in JSON format."},
                    {"role": "user", "content": self.THESIS_PROMPT.format(
                        symbol=symbol,
                        industry=data.get('industry', 'Unknown'),
                        ar_summary=data.get('ar_summary', 'Not available'),
                        earnings_summary=data.get('earnings_summary', 'Not available'),
                        metrics=json.dumps(data.get('metrics', {}))
                    )}
                ],
                temperature=0.4,
                max_tokens=1500
            )
            
            content = response.choices[0].message.content.strip()
            if content.startswith("```"):
                content = re.sub(r'^```json?\n?', '', content)
                content = re.sub(r'\n?```$', '', content)
            
            thesis_data = json.loads(content)
            
            return InvestmentThesis(
                symbol=symbol,
                company_name=data.get('company_name', symbol),
                recommendation=thesis_data.get('recommendation', 'Hold'),
                conviction=thesis_data.get('conviction', 'Medium'),
                target_return=thesis_data.get('target_return', 'N/A'),
                time_horizon=thesis_data.get('time_horizon', '12 months'),
                executive_summary=thesis_data.get('executive_summary', ''),
                bull_case=thesis_data.get('bull_case', ''),
                bear_case=thesis_data.get('bear_case', ''),
                competitive_moat=thesis_data.get('competitive_moat', ''),
                growth_drivers=thesis_data.get('growth_drivers', []),
                risk_factors=thesis_data.get('risk_factors', []),
                valuation_summary=thesis_data.get('valuation_summary', ''),
                key_metrics=data.get('metrics', {}),
                catalysts=thesis_data.get('catalysts', []),
                generated_at=datetime.now().isoformat()
            )
            
        except Exception as e:
            logger.error(f"Thesis generation error: {e}")
            return self._default_thesis(symbol, data)
    
    def _default_thesis(self, symbol: str, data: Dict) -> InvestmentThesis:
        """Default thesis when AI unavailable."""
        return InvestmentThesis(
            symbol=symbol,
            company_name=data.get('company_name', symbol),
            recommendation="Hold",
            conviction="Low",
            target_return="N/A",
            time_horizon="12 months",
            executive_summary="Insufficient data for thesis generation.",
            bull_case="",
            bear_case="",
            competitive_moat="",
            growth_drivers=[],
            risk_factors=[],
            valuation_summary="",
            key_metrics={},
            catalysts=[],
            generated_at=datetime.now().isoformat()
        )


def format_thesis_for_ui(thesis: InvestmentThesis) -> Dict:
    """Format thesis for optimal UI display."""
    
    rec_colors = {"Buy": "#22c55e", "Hold": "#eab308", "Sell": "#ef4444"}
    conviction_icons = {"High": "🔥", "Medium": "⚡", "Low": "💡"}
    
    return {
        # Header
        "header": {
            "symbol": thesis.symbol,
            "company_name": thesis.company_name,
            "recommendation": thesis.recommendation,
            "rec_color": rec_colors.get(thesis.recommendation, "#94a3b8"),
            "conviction": thesis.conviction,
            "conviction_icon": conviction_icons.get(thesis.conviction, ""),
            "target_return": thesis.target_return,
            "time_horizon": thesis.time_horizon
        },
        
        # Executive summary hero
        "executive_summary": thesis.executive_summary,
        
        # Bull vs Bear
        "bull_bear": {
            "bull": {
                "title": "Bull Case 📈",
                "content": thesis.bull_case
            },
            "bear": {
                "title": "Bear Case 📉",
                "content": thesis.bear_case
            }
        },
        
        # Competitive moat
        "moat": {
            "title": "Competitive Moat 🏰",
            "content": thesis.competitive_moat
        },
        
        # Growth drivers
        "growth_drivers": [
            {"icon": "🚀", "text": driver}
            for driver in thesis.growth_drivers
        ],
        
        # Risk factors
        "risk_factors": [
            {"icon": "⚠️", "text": risk}
            for risk in thesis.risk_factors
        ],
        
        # Valuation
        "valuation": {
            "summary": thesis.valuation_summary,
            "metrics": thesis.key_metrics
        },
        
        # Catalysts timeline
        "catalysts": [
            {
                "event": c.get('event', ''),
                "timeline": c.get('timeline', ''),
                "impact": c.get('impact', 'Medium'),
                "impact_color": {"High": "#ef4444", "Medium": "#eab308", "Low": "#22c55e"}.get(c.get('impact'), "#94a3b8")
            }
            for c in thesis.catalysts
        ],
        
        # Metadata
        "generated_at": thesis.generated_at
    }


if __name__ == "__main__":
    generator = ThesisGenerator(market="india")
    
    print("Generating investment thesis...")
    thesis = generator.generate("RELIANCE")
    
    print(f"\n{'='*60}")
    print(f"INVESTMENT THESIS: {thesis.symbol}")
    print(f"{'='*60}")
    print(f"Recommendation: {thesis.recommendation} ({thesis.conviction} conviction)")
    print(f"Target: {thesis.target_return}")
    print(f"\n{thesis.executive_summary}")
