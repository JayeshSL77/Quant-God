"""
ESG Scoring Engine
Environmental, Social, and Governance scoring from annual reports.
"""

import os
import re
import logging
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None
import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ESGScoring")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

INDIA_DB = os.getenv("DATABASE_URL", 
    "postgresql://postgres:analyezdb77**@analyezdb.cbimec0sg2ch.ap-south-1.rds.amazonaws.com:5432/analyezdb")
US_DB = os.getenv("US_DATABASE_URL",
    "postgresql://postgres:analyezdb77**@analyezdb.cbimec0sg2ch.ap-south-1.rds.amazonaws.com:5432/usmarkets")


@dataclass
class ESGScore:
    """ESG scores for a company."""
    symbol: str
    environmental: int  # 0-100
    social: int  # 0-100
    governance: int  # 0-100
    overall: int  # Weighted average
    
    # Sub-metrics
    carbon_initiatives: int
    renewable_energy: int
    waste_management: int
    
    diversity_inclusion: int
    employee_safety: int
    community_impact: int
    
    board_independence: int
    executive_compensation: int
    transparency: int
    
    # Analysis
    highlights: List[str]
    risks: List[str]
    data_quality: str  # high, medium, low


class ESGAnalyzer:
    """
    Analyzes ESG factors from annual reports.
    Uses AI to extract and score sustainability metrics.
    """
    
    ESG_PROMPT = """Analyze this annual report excerpt for ESG (Environmental, Social, Governance) factors.
Score each dimension 0-100 based on evidence in the text.

Environmental factors: carbon reduction, renewable energy, waste management, conservation
Social factors: diversity, employee safety, community programs, human rights
Governance factors: board independence, exec compensation, transparency, ethics

Report excerpt:
{text}

Return JSON:
{{
    "environmental": {{
        "score": 0-100,
        "carbon_initiatives": 0-100,
        "renewable_energy": 0-100,
        "waste_management": 0-100,
        "evidence": ["quote1", "quote2"]
    }},
    "social": {{
        "score": 0-100,
        "diversity_inclusion": 0-100,
        "employee_safety": 0-100,
        "community_impact": 0-100,
        "evidence": ["quote1", "quote2"]
    }},
    "governance": {{
        "score": 0-100,
        "board_independence": 0-100,
        "executive_compensation": 0-100,
        "transparency": 0-100,
        "evidence": ["quote1", "quote2"]
    }},
    "highlights": ["positive point 1", "positive point 2"],
    "risks": ["concern 1", "concern 2"]
}}"""

    def __init__(self, market: str = "india"):
        self.market = market
        self.db_url = INDIA_DB if market == "india" else US_DB
        self.client = OpenAI(api_key=OPENAI_API_KEY) if (OpenAI and OPENAI_API_KEY) else None
    
    def analyze_report(self, text: str) -> Dict[str, Any]:
        """Analyze annual report for ESG factors."""
        if self.client:
            return self._analyze_with_ai(text)
        else:
            return self._analyze_with_keywords(text)
    
    def _analyze_with_ai(self, text: str) -> Dict[str, Any]:
        """Use AI for ESG analysis."""
        try:
            # Focus on relevant sections (sustainability, risk, governance)
            text = text[:20000]
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Analyze ESG factors in corporate reports. Return JSON only."},
                    {"role": "user", "content": self.ESG_PROMPT.format(text=text)}
                ],
                temperature=0.2,
                max_tokens=800
            )
            
            content = response.choices[0].message.content.strip()
            if content.startswith("```"):
                content = re.sub(r'^```json?\n?', '', content)
                content = re.sub(r'\n?```$', '', content)
            
            return json.loads(content)
            
        except Exception as e:
            logger.error(f"AI ESG analysis error: {e}")
            return self._analyze_with_keywords(text)
    
    def _analyze_with_keywords(self, text: str) -> Dict[str, Any]:
        """Keyword-based ESG scoring fallback."""
        text_lower = text.lower()
        
        # Environmental keywords
        env_keywords = ['carbon', 'emission', 'renewable', 'solar', 'wind', 'sustainability', 
                       'climate', 'green', 'environment', 'recycl', 'conservation']
        env_score = min(100, sum(10 for kw in env_keywords if kw in text_lower))
        
        # Social keywords
        soc_keywords = ['diversity', 'inclusion', 'employee', 'safety', 'community', 
                       'training', 'health', 'welfare', 'women', 'minority']
        soc_score = min(100, sum(10 for kw in soc_keywords if kw in text_lower))
        
        # Governance keywords
        gov_keywords = ['independent', 'board', 'ethics', 'compliance', 'audit', 
                       'transparency', 'disclosure', 'governance', 'stakeholder']
        gov_score = min(100, sum(11 for kw in gov_keywords if kw in text_lower))
        
        return {
            "environmental": {"score": env_score, "carbon_initiatives": env_score, 
                            "renewable_energy": env_score, "waste_management": env_score, "evidence": []},
            "social": {"score": soc_score, "diversity_inclusion": soc_score, 
                      "employee_safety": soc_score, "community_impact": soc_score, "evidence": []},
            "governance": {"score": gov_score, "board_independence": gov_score, 
                          "executive_compensation": 50, "transparency": gov_score, "evidence": []},
            "highlights": [],
            "risks": []
        }
    
    def score_company(self, symbol: str) -> ESGScore:
        """Get ESG score for a company from latest annual report."""
        try:
            conn = psycopg2.connect(self.db_url)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            if self.market == "india":
                cur.execute("""
                    SELECT symbol, fiscal_year, content
                    FROM annual_reports
                    WHERE symbol = %s AND content IS NOT NULL
                    ORDER BY fiscal_year DESC LIMIT 1
                """, (symbol,))
            else:
                cur.execute("""
                    SELECT symbol, fiscal_year, full_text
                    FROM annual_reports_10k
                    WHERE symbol = %s AND full_text IS NOT NULL
                    ORDER BY fiscal_year DESC LIMIT 1
                """, (symbol,))
            
            row = cur.fetchone()
            cur.close()
            conn.close()
            
            if not row:
                return self._default_score(symbol)
            
            text = row.get('content') or row.get('full_text', '')
            analysis = self.analyze_report(text)
            
            env = analysis.get('environmental', {})
            soc = analysis.get('social', {})
            gov = analysis.get('governance', {})
            
            overall = int((env.get('score', 50) * 0.33 + 
                          soc.get('score', 50) * 0.33 + 
                          gov.get('score', 50) * 0.34))
            
            return ESGScore(
                symbol=symbol,
                environmental=env.get('score', 50),
                social=soc.get('score', 50),
                governance=gov.get('score', 50),
                overall=overall,
                carbon_initiatives=env.get('carbon_initiatives', 50),
                renewable_energy=env.get('renewable_energy', 50),
                waste_management=env.get('waste_management', 50),
                diversity_inclusion=soc.get('diversity_inclusion', 50),
                employee_safety=soc.get('employee_safety', 50),
                community_impact=soc.get('community_impact', 50),
                board_independence=gov.get('board_independence', 50),
                executive_compensation=gov.get('executive_compensation', 50),
                transparency=gov.get('transparency', 50),
                highlights=analysis.get('highlights', []),
                risks=analysis.get('risks', []),
                data_quality="high" if self.client else "medium"
            )
            
        except Exception as e:
            logger.error(f"Error scoring {symbol}: {e}")
            return self._default_score(symbol)
    
    def _default_score(self, symbol: str) -> ESGScore:
        """Default score when data unavailable."""
        return ESGScore(
            symbol=symbol,
            environmental=50, social=50, governance=50, overall=50,
            carbon_initiatives=50, renewable_energy=50, waste_management=50,
            diversity_inclusion=50, employee_safety=50, community_impact=50,
            board_independence=50, executive_compensation=50, transparency=50,
            highlights=[], risks=[], data_quality="low"
        )


def format_esg_for_ui(score: ESGScore) -> Dict:
    """Format ESG score for optimal UI display."""
    
    def score_color(s: int) -> str:
        if s >= 70: return "#22c55e"
        if s >= 50: return "#eab308"
        if s >= 30: return "#f97316"
        return "#ef4444"
    
    def score_label(s: int) -> str:
        if s >= 80: return "Excellent"
        if s >= 60: return "Good"
        if s >= 40: return "Average"
        if s >= 20: return "Below Average"
        return "Poor"
    
    return {
        # Overall gauge
        "overall": {
            "score": score.overall,
            "label": score_label(score.overall),
            "color": score_color(score.overall)
        },
        
        # Three pillars
        "pillars": [
            {
                "name": "Environmental",
                "icon": "🌿",
                "score": score.environmental,
                "color": score_color(score.environmental),
                "breakdown": [
                    {"label": "Carbon Initiatives", "score": score.carbon_initiatives},
                    {"label": "Renewable Energy", "score": score.renewable_energy},
                    {"label": "Waste Management", "score": score.waste_management}
                ]
            },
            {
                "name": "Social",
                "icon": "👥",
                "score": score.social,
                "color": score_color(score.social),
                "breakdown": [
                    {"label": "Diversity & Inclusion", "score": score.diversity_inclusion},
                    {"label": "Employee Safety", "score": score.employee_safety},
                    {"label": "Community Impact", "score": score.community_impact}
                ]
            },
            {
                "name": "Governance",
                "icon": "⚖️",
                "score": score.governance,
                "color": score_color(score.governance),
                "breakdown": [
                    {"label": "Board Independence", "score": score.board_independence},
                    {"label": "Executive Pay", "score": score.executive_compensation},
                    {"label": "Transparency", "score": score.transparency}
                ]
            }
        ],
        
        # Radar chart data
        "radar": {
            "labels": ["Environmental", "Social", "Governance"],
            "data": [score.environmental, score.social, score.governance]
        },
        
        # Highlights and risks
        "insights": {
            "highlights": [{"type": "positive", "text": h} for h in score.highlights],
            "risks": [{"type": "warning", "text": r} for r in score.risks]
        },
        
        # Data quality indicator
        "data_quality": {
            "level": score.data_quality,
            "message": "Based on AI analysis of annual report" if score.data_quality == "high" 
                      else "Based on keyword analysis"
        }
    }


if __name__ == "__main__":
    analyzer = ESGAnalyzer(market="us")
    
    # Test with sample text
    sample = """
    Our commitment to sustainability remains strong. We achieved carbon neutrality 
    in 2024 and are on track for 100% renewable energy by 2030. Our diversity 
    initiatives have increased female representation to 45%. The board maintains 
    75% independence with regular governance reviews.
    """
    
    result = analyzer.analyze_report(sample)
    print(f"Environmental: {result['environmental']['score']}")
    print(f"Social: {result['social']['score']}")
    print(f"Governance: {result['governance']['score']}")
