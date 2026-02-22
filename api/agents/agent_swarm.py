"""
Multi-Agent Research Swarm
Multiple specialized AI agents analyzing stocks from different angles.
This is the hedge fund-grade analysis approach.
"""

import os
import logging
import json
import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None
from concurrent.futures import ThreadPoolExecutor, as_completed
import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AgentSwarm")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

INDIA_DB = os.getenv("DATABASE_URL", 
    "postgresql://postgres:analyezdb77**@analyezdb.cbimec0sg2ch.ap-south-1.rds.amazonaws.com:5432/analyezdb")
US_DB = os.getenv("US_DATABASE_URL",
    "postgresql://postgres:analyezdb77**@analyezdb.cbimec0sg2ch.ap-south-1.rds.amazonaws.com:5432/usmarkets")


@dataclass
class AgentAnalysis:
    """Output from a single agent."""
    agent_name: str
    agent_role: str
    rating: str  # bullish, neutral, bearish
    confidence: float  # 0-1
    key_points: List[str]
    concerns: List[str]
    summary: str


@dataclass
class SwarmReport:
    """Consolidated report from all agents."""
    symbol: str
    company_name: str
    analyses: List[AgentAnalysis]
    consensus_rating: str
    conviction_score: float  # 0-100
    investment_thesis: str
    key_catalysts: List[str]
    key_risks: List[str]
    generated_at: str


class BaseAgent:
    """Base class for specialized agents."""
    
    def __init__(self, name: str, role: str, prompt_template: str):
        self.name = name
        self.role = role
        self.prompt = prompt_template
        self.client = OpenAI(api_key=OPENAI_API_KEY) if (OpenAI and OPENAI_API_KEY) else None
    
    def analyze(self, context: Dict[str, Any]) -> AgentAnalysis:
        """Run agent analysis."""
        raise NotImplementedError


class QuantitativeAgent(BaseAgent):
    """Analyzes financial metrics and ratios."""
    
    PROMPT = """You are a quantitative analyst evaluating financial metrics.
Analyze the following financial data and provide your assessment.

Company: {symbol}
Metrics:
{metrics}

Evaluate: growth rates, margins, returns on capital, debt levels, valuations.

Return JSON:
{{
    "rating": "bullish|neutral|bearish",
    "confidence": 0.X,
    "key_points": ["strength 1", "strength 2"],
    "concerns": ["weakness 1", "weakness 2"],
    "summary": "One paragraph quantitative assessment"
}}"""
    
    def __init__(self):
        super().__init__(
            name="Quantitative Analyst",
            role="Evaluates financial metrics and valuations",
            prompt_template=self.PROMPT
        )
    
    def analyze(self, context: Dict[str, Any]) -> AgentAnalysis:
        if not self.client:
            return self._default_analysis()
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a quantitative financial analyst. Return JSON only."},
                    {"role": "user", "content": self.PROMPT.format(
                        symbol=context.get('symbol', ''),
                        metrics=json.dumps(context.get('metrics', {}), indent=2)
                    )}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            content = response.choices[0].message.content.strip()
            if content.startswith("```"):
                content = re.sub(r'^```json?\n?', '', content)
                content = re.sub(r'\n?```$', '', content)
            
            data = json.loads(content)
            
            return AgentAnalysis(
                agent_name=self.name,
                agent_role=self.role,
                rating=data.get('rating', 'neutral'),
                confidence=data.get('confidence', 0.5),
                key_points=data.get('key_points', []),
                concerns=data.get('concerns', []),
                summary=data.get('summary', '')
            )
            
        except Exception as e:
            logger.error(f"Quant agent error: {e}")
            return self._default_analysis()
    
    def _default_analysis(self) -> AgentAnalysis:
        return AgentAnalysis(
            agent_name=self.name, agent_role=self.role,
            rating="neutral", confidence=0.3,
            key_points=[], concerns=[],
            summary="Insufficient data for quantitative analysis"
        )


class FundamentalAgent(BaseAgent):
    """Analyzes business quality from annual reports."""
    
    PROMPT = """You are a fundamental analyst evaluating business quality.
Read this annual report excerpt and assess the company's competitive position.

Company: {symbol}
Report excerpt:
{text}

Evaluate: competitive moat, market position, management quality, growth drivers.

Return JSON:
{{
    "rating": "bullish|neutral|bearish",
    "confidence": 0.X,
    "key_points": ["strength 1", "strength 2"],
    "concerns": ["weakness 1", "weakness 2"],
    "summary": "One paragraph fundamental assessment"
}}"""
    
    def __init__(self):
        super().__init__(
            name="Fundamental Analyst",
            role="Evaluates business quality and competitive moat",
            prompt_template=self.PROMPT
        )
    
    def analyze(self, context: Dict[str, Any]) -> AgentAnalysis:
        if not self.client:
            return AgentAnalysis(
                agent_name=self.name, agent_role=self.role,
                rating="neutral", confidence=0.3,
                key_points=[], concerns=[],
                summary="Insufficient data"
            )
        
        try:
            text = context.get('annual_report', '')[:15000]
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a fundamental business analyst. Return JSON only."},
                    {"role": "user", "content": self.PROMPT.format(
                        symbol=context.get('symbol', ''),
                        text=text
                    )}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            content = response.choices[0].message.content.strip()
            if content.startswith("```"):
                content = re.sub(r'^```json?\n?', '', content)
                content = re.sub(r'\n?```$', '', content)
            
            data = json.loads(content)
            
            return AgentAnalysis(
                agent_name=self.name, agent_role=self.role,
                rating=data.get('rating', 'neutral'),
                confidence=data.get('confidence', 0.5),
                key_points=data.get('key_points', []),
                concerns=data.get('concerns', []),
                summary=data.get('summary', '')
            )
            
        except Exception as e:
            logger.error(f"Fundamental agent error: {e}")
            return AgentAnalysis(
                agent_name=self.name, agent_role=self.role,
                rating="neutral", confidence=0.3,
                key_points=[], concerns=[], summary="Analysis failed"
            )


class SentimentAgent(BaseAgent):
    """Analyzes market sentiment and news."""
    
    PROMPT = """You are a sentiment analyst tracking market mood.
Analyze the following news and sentiment data.

Company: {symbol}
Recent sentiment data:
{sentiment_data}

Evaluate: news flow, social sentiment, analyst opinions.

Return JSON:
{{
    "rating": "bullish|neutral|bearish",
    "confidence": 0.X,
    "key_points": ["positive 1", "positive 2"],
    "concerns": ["negative 1", "negative 2"],
    "summary": "One paragraph sentiment assessment"
}}"""
    
    def __init__(self):
        super().__init__(
            name="Sentiment Analyst",
            role="Tracks market mood and news flow",
            prompt_template=self.PROMPT
        )
    
    def analyze(self, context: Dict[str, Any]) -> AgentAnalysis:
        sentiment = context.get('sentiment', {})
        
        # Simple rule-based if no AI or sentiment data
        score = sentiment.get('score', 0)
        
        if score > 0.3:
            rating = "bullish"
        elif score < -0.3:
            rating = "bearish"
        else:
            rating = "neutral"
        
        return AgentAnalysis(
            agent_name=self.name,
            agent_role=self.role,
            rating=rating,
            confidence=0.6,
            key_points=sentiment.get('positive_headlines', [])[:2],
            concerns=sentiment.get('negative_headlines', [])[:2],
            summary=f"Current sentiment: {sentiment.get('status', 'neutral')}"
        )


class RiskAgent(BaseAgent):
    """Analyzes risk factors and downside."""
    
    PROMPT = """You are a risk analyst identifying potential problems.
Review the following risk factors from the annual report.

Company: {symbol}
Risk factors:
{risks}

Identify: key risks, severity, likelihood, mitigation.

Return JSON:
{{
    "rating": "bullish|neutral|bearish",
    "confidence": 0.X,
    "key_points": ["mitigating factor 1", "mitigating factor 2"],
    "concerns": ["risk 1", "risk 2", "risk 3"],
    "summary": "One paragraph risk assessment"
}}"""
    
    def __init__(self):
        super().__init__(
            name="Risk Analyst",
            role="Identifies downside risks and concerns",
            prompt_template=self.PROMPT
        )
    
    def analyze(self, context: Dict[str, Any]) -> AgentAnalysis:
        if not self.client:
            return AgentAnalysis(
                agent_name=self.name, agent_role=self.role,
                rating="neutral", confidence=0.3,
                key_points=[], concerns=[], summary="Risk analysis unavailable"
            )
        
        try:
            risks = context.get('risk_factors', '')[:10000]
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a risk analyst. Be skeptical. Return JSON only."},
                    {"role": "user", "content": self.PROMPT.format(
                        symbol=context.get('symbol', ''),
                        risks=risks
                    )}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            content = response.choices[0].message.content.strip()
            if content.startswith("```"):
                content = re.sub(r'^```json?\n?', '', content)
                content = re.sub(r'\n?```$', '', content)
            
            data = json.loads(content)
            
            return AgentAnalysis(
                agent_name=self.name, agent_role=self.role,
                rating=data.get('rating', 'neutral'),
                confidence=data.get('confidence', 0.5),
                key_points=data.get('key_points', []),
                concerns=data.get('concerns', []),
                summary=data.get('summary', '')
            )
            
        except Exception as e:
            logger.error(f"Risk agent error: {e}")
            return AgentAnalysis(
                agent_name=self.name, agent_role=self.role,
                rating="neutral", confidence=0.3,
                key_points=[], concerns=[], summary="Analysis failed"
            )


class AgentSwarm:
    """
    Orchestrates multiple specialized agents for comprehensive analysis.
    """
    
    def __init__(self, market: str = "india"):
        self.market = market
        self.db_url = INDIA_DB if market == "india" else US_DB
        self.client = OpenAI(api_key=OPENAI_API_KEY) if (OpenAI and OPENAI_API_KEY) else None
        
        # Initialize agents
        self.agents = [
            QuantitativeAgent(),
            FundamentalAgent(),
            SentimentAgent(),
            RiskAgent()
        ]
    
    def gather_context(self, symbol: str) -> Dict[str, Any]:
        """Gather all data needed for analysis."""
        context = {"symbol": symbol}
        
        try:
            conn = psycopg2.connect(self.db_url)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            # Get annual report
            if self.market == "india":
                cur.execute("""
                    SELECT nuanced_summary FROM annual_reports
                    WHERE symbol = %s ORDER BY fiscal_year DESC LIMIT 1
                """, (symbol,))
                row = cur.fetchone()
                if row:
                    context['annual_report'] = row.get('nuanced_summary', '')
            else:
                cur.execute("""
                    SELECT full_text, risk_factors, mda_section 
                    FROM annual_reports_10k
                    WHERE symbol = %s ORDER BY fiscal_year DESC LIMIT 1
                """, (symbol,))
                row = cur.fetchone()
                if row:
                    context['annual_report'] = row.get('full_text', '')
                    context['risk_factors'] = row.get('risk_factors', '')
            
            cur.close()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error gathering context: {e}")
        
        # Add placeholder metrics (would come from fundamentals table)
        context['metrics'] = {
            "revenue_growth": "15%",
            "profit_margin": "12%",
            "roic": "18%",
            "debt_to_equity": "0.5"
        }
        
        context['sentiment'] = {"score": 0.2, "status": "Neutral"}
        
        return context
    
    def run_analysis(self, symbol: str) -> SwarmReport:
        """Run all agents in parallel and synthesize results."""
        logger.info(f"Running agent swarm for {symbol}...")
        
        # Gather context
        context = self.gather_context(symbol)
        
        # Run agents in parallel
        analyses = []
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(agent.analyze, context): agent for agent in self.agents}
            
            for future in as_completed(futures):
                try:
                    result = future.result()
                    analyses.append(result)
                except Exception as e:
                    logger.error(f"Agent error: {e}")
        
        # Calculate consensus
        rating_scores = {"bullish": 1, "neutral": 0, "bearish": -1}
        total_score = sum(rating_scores.get(a.rating, 0) * a.confidence for a in analyses)
        total_confidence = sum(a.confidence for a in analyses)
        
        if total_confidence > 0:
            avg_score = total_score / total_confidence
            if avg_score > 0.3:
                consensus = "bullish"
            elif avg_score < -0.3:
                consensus = "bearish"
            else:
                consensus = "neutral"
            conviction = int(abs(avg_score) * 100)
        else:
            consensus = "neutral"
            conviction = 0
        
        # Synthesize thesis
        thesis = self._synthesize_thesis(symbol, analyses, consensus)
        
        # Collect catalysts and risks
        catalysts = []
        risks = []
        for a in analyses:
            catalysts.extend(a.key_points[:2])
            risks.extend(a.concerns[:2])
        
        return SwarmReport(
            symbol=symbol,
            company_name=symbol,  # Would fetch from metadata
            analyses=analyses,
            consensus_rating=consensus,
            conviction_score=conviction,
            investment_thesis=thesis,
            key_catalysts=catalysts[:5],
            key_risks=risks[:5],
            generated_at=datetime.now().isoformat()
        )
    
    def _synthesize_thesis(self, symbol: str, analyses: List[AgentAnalysis], consensus: str) -> str:
        """Generate investment thesis from agent analyses."""
        if not self.client:
            return f"Based on multi-agent analysis, {symbol} is rated {consensus}."
        
        try:
            agent_summaries = "\n".join([
                f"- {a.agent_name}: {a.rating.upper()} - {a.summary}"
                for a in analyses
            ])
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Synthesize agent analyses into a cohesive investment thesis."},
                    {"role": "user", "content": f"""Based on these agent analyses for {symbol}:

{agent_summaries}

Write a 2-3 sentence investment thesis that synthesizes all perspectives."""}
                ],
                temperature=0.4,
                max_tokens=200
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Synthesis error: {e}")
            return f"Based on multi-agent analysis, {symbol} is rated {consensus}."


def format_swarm_for_ui(report: SwarmReport) -> Dict:
    """Format swarm report for optimal UI display."""
    
    # Rating colors
    rating_colors = {"bullish": "#22c55e", "neutral": "#eab308", "bearish": "#ef4444"}
    
    return {
        # Header
        "header": {
            "symbol": report.symbol,
            "consensus": report.consensus_rating.upper(),
            "consensus_color": rating_colors.get(report.consensus_rating, "#94a3b8"),
            "conviction": report.conviction_score,
            "generated_at": report.generated_at
        },
        
        # Investment thesis (hero section)
        "thesis": {
            "text": report.investment_thesis,
            "tone": report.consensus_rating
        },
        
        # Agent cards
        "agents": [
            {
                "name": a.agent_name,
                "role": a.agent_role,
                "rating": a.rating,
                "rating_color": rating_colors.get(a.rating, "#94a3b8"),
                "confidence": int(a.confidence * 100),
                "summary": a.summary,
                "key_points": a.key_points,
                "concerns": a.concerns
            }
            for a in report.analyses
        ],
        
        # Summary lists
        "catalysts": [{"text": c, "type": "positive"} for c in report.key_catalysts],
        "risks": [{"text": r, "type": "warning"} for r in report.key_risks]
    }


if __name__ == "__main__":
    swarm = AgentSwarm(market="us")
    
    print("Running agent swarm analysis...")
    report = swarm.run_analysis("AAPL")
    
    print(f"\n{'='*60}")
    print(f"SWARM REPORT: {report.symbol}")
    print(f"{'='*60}")
    print(f"Consensus: {report.consensus_rating.upper()}")
    print(f"Conviction: {report.conviction_score}%")
    print(f"\nThesis: {report.investment_thesis}")
    
    print("\nAgent Ratings:")
    for a in report.analyses:
        print(f"  {a.agent_name}: {a.rating} ({int(a.confidence*100)}% confidence)")
