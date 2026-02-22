"""
Inwezt Institutional-Grade Multi-Agent Summarizer
Produces nuanced summaries that compete with public.com's Generated Assets.

Uses Mistral (free tier) as primary, OpenAI as fallback.
"""

import os
import json
import logging
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from mistralai import Mistral
from dotenv import load_dotenv

load_dotenv(override=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("InstitutionalSummarizer")

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize clients
_mistral_client = None

def get_mistral_client():
    """Get or create Mistral client."""
    global _mistral_client
    if _mistral_client is None and MISTRAL_API_KEY:
        _mistral_client = Mistral(api_key=MISTRAL_API_KEY)
    return _mistral_client


@dataclass
class AnalystOutput:
    """Output from a specialist agent."""
    agent_name: str
    analysis: str
    key_points: List[str]
    sentiment_score: float  # -1 to 1
    confidence: float  # 0 to 1


class BaseAgent:
    """Base class for all analyst agents."""
    
    def _call_llm(self, prompt: str, document: str, temperature: float = 0.2) -> str:
        """Make a Mistral API call."""
        client = get_mistral_client()
        if not client:
            raise ValueError("Mistral client not configured. Set MISTRAL_API_KEY.")
        
        # Truncate document to fit in context
        max_doc_chars = 30000  # Mistral has smaller context
        doc_truncated = document[:max_doc_chars]
        
        response = client.chat.complete(
            model="mistral-small-latest",  # Free tier model
            messages=[
                {"role": "system", "content": "You are an expert financial analyst. Be concise and data-driven."},
                {"role": "user", "content": prompt.format(document=doc_truncated)}
            ],
            temperature=temperature,
            max_tokens=2000
        )
        return response.choices[0].message.content


class FinancialAnalystAgent(BaseAgent):
    """
    Extracts quantitative financial metrics and trends.
    Focus: Numbers, ratios, growth rates, margins, valuations.
    """
    
    PROMPT = """Analyze this document and extract ONLY quantitative financial data.

DOCUMENT:
{document}

Extract and analyze:
1. **Revenue & Growth**: Current revenue, YoY growth rate, CAGR if available
2. **Profitability**: Net profit, PAT margin, EBITDA margin trends
3. **Key Ratios**: ROE, ROCE, D/E ratio, current ratio
4. **Segment Performance**: Revenue/profit by business segment
5. **Capex & Investments**: Capital expenditure, R&D spend

Format your response as:
## Financial Metrics Summary
[Analysis with specific numbers and % changes]

## Key Quantitative Insights
- [Most important financial takeaways as bullet points]

## Financial Health Score: [1-10]
[One line justification]"""
    
    def analyze(self, document: str) -> AnalystOutput:
        try:
            analysis = self._call_llm(self.PROMPT, document, temperature=0.1)
            
            # Extract key points (lines starting with -)
            key_points = [line.strip('- ').strip() for line in analysis.split('\n') 
                         if line.strip().startswith('-')]
            
            # Extract score
            score = 5.0
            if "Score:" in analysis:
                try:
                    score_text = analysis.split("Score:")[1][:10]
                    score = float(''.join(c for c in score_text if c.isdigit() or c == '.'))
                    score = min(10, max(1, score))
                except:
                    pass
            
            return AnalystOutput(
                agent_name="Financial Analyst",
                analysis=analysis,
                key_points=key_points[:10],
                sentiment_score=(score - 5) / 5,  # Normalize to -1 to 1
                confidence=0.9
            )
        except Exception as e:
            logger.error(f"Financial Analyst failed: {e}")
            return AnalystOutput("Financial Analyst", f"Analysis failed: {e}", [], 0.0, 0.0)


class BusinessStrategistAgent(BaseAgent):
    """
    Analyzes competitive positioning, moats, and strategic risks.
    Focus: Qualitative business analysis, market position, threats.
    """
    
    PROMPT = """Analyze this document for strategic insights.

DOCUMENT:
{document}

Analyze:
1. **Competitive Moat**: What sustainable advantages does this company have?
2. **Market Position**: Market share, industry tailwinds/headwinds
3. **Strategic Initiatives**: New products, market expansion, M&A activity
4. **Risk Factors**: Top 3 strategic risks and their potential impact
5. **Industry Trends**: How is the company positioned for secular trends?

Format your response as:
## Business Moat Analysis
[Your analysis]

## Strategic Position Score: [Strong/Moderate/Weak]
[Justification]

## Key Strategic Risks
1. [Risk 1]
2. [Risk 2]
3. [Risk 3]

## Competitive Advantages
- [Bullet points]"""
    
    def analyze(self, document: str) -> AnalystOutput:
        try:
            analysis = self._call_llm(self.PROMPT, document, temperature=0.2)
            
            key_points = [line.strip('- ').strip() for line in analysis.split('\n') 
                         if line.strip().startswith('-') or line.strip().startswith(('1.', '2.', '3.'))]
            
            # Determine sentiment from position score
            sentiment = 0.3
            if "Strong" in analysis:
                sentiment = 0.8
            elif "Weak" in analysis:
                sentiment = -0.3
            elif "Moderate" in analysis:
                sentiment = 0.3
            
            return AnalystOutput(
                agent_name="Business Strategist",
                analysis=analysis,
                key_points=key_points[:10],
                sentiment_score=sentiment,
                confidence=0.85
            )
        except Exception as e:
            logger.error(f"Business Strategist failed: {e}")
            return AnalystOutput("Business Strategist", f"Analysis failed: {e}", [], 0.0, 0.0)


class ManagementToneAgent(BaseAgent):
    """
    Analyzes management sentiment, confidence, and forward guidance.
    Focus: Tone analysis, promises vs delivery, guidance quality.
    """
    
    PROMPT = """Analyze this document for management tone and sentiment.

DOCUMENT:
{document}

Analyze:
1. **Management Confidence**: Are they bullish, cautious, or defensive?
2. **Guidance Quality**: Specific vs vague, conservative vs aggressive
3. **Red Flags**: Unusual language, blame-shifting, inconsistencies
4. **Green Flags**: Accountability, clear metrics, long-term thinking
5. **Forward Outlook**: What are they explicitly guiding for next period?

Format your response as:
## Management Tone Assessment
[Your analysis]

## Sentiment Score: [Very Bullish / Bullish / Neutral / Cautious / Bearish]
[Justification]

## Forward Guidance Summary
[Key guidance points for next quarter/year]

## Green Flags
- [Positive indicators]

## Red Flags
- [Warning signs, if any]"""
    
    def analyze(self, document: str) -> AnalystOutput:
        try:
            analysis = self._call_llm(self.PROMPT, document, temperature=0.2)
            
            key_points = [line.strip('- ').strip() for line in analysis.split('\n') 
                         if line.strip().startswith('-')]
            
            # Determine sentiment
            sentiment = 0.0
            sentiment_map = {
                "Very Bullish": 0.9,
                "Bullish": 0.5,
                "Neutral": 0.0,
                "Cautious": -0.3,
                "Bearish": -0.7
            }
            for label, score in sentiment_map.items():
                if label in analysis:
                    sentiment = score
                    break
            
            return AnalystOutput(
                agent_name="Management Tone Analyst",
                analysis=analysis,
                key_points=key_points[:10],
                sentiment_score=sentiment,
                confidence=0.8
            )
        except Exception as e:
            logger.error(f"Management Tone Agent failed: {e}")
            return AnalystOutput("Management Tone Analyst", f"Analysis failed: {e}", [], 0.0, 0.0)


class SynthesisAgent(BaseAgent):
    """
    Combines all agent outputs into an institutional-grade summary.
    Produces the final nuanced_summary that competes with public.com.
    """
    
    PROMPT = """Synthesize these research analyses into an institutional-grade investment summary.

FINANCIAL ANALYSIS:
{financial}

STRATEGIC ANALYSIS:
{strategic}

MANAGEMENT TONE ANALYSIS:
{tone}

COMPANY: {symbol}
DOCUMENT TYPE: {doc_type}
PERIOD: {period}

Create a summary in EXACTLY this format:

### Investment Thesis
[One powerful sentence summarizing the investment case]

### Key Metrics
| Metric | Value | Trend |
|--------|-------|-------|
[Top 5 financial metrics in table format]

### Business Quality: [★★★★★ / ★★★★☆ / ★★★☆☆ / ★★☆☆☆ / ★☆☆☆☆]
[One paragraph on competitive moat and strategic position]

### Growth Catalysts
• [Catalyst 1]
• [Catalyst 2]
• [Catalyst 3]

### Risk Factors
• [Risk 1]
• [Risk 2]
• [Risk 3]

### Management Assessment
**Confidence Level**: [High/Medium/Low]
**Guidance Reliability**: [Excellent/Good/Mixed/Poor]
[One paragraph on management quality and forward guidance]

### Sentiment Score: [+2 to -2 scale]
🟢🟢 Strong Buy (+2) | 🟢 Buy (+1) | ⚪ Neutral (0) | 🔴 Sell (-1) | 🔴🔴 Strong Sell (-2)

### Investment Implications
[2-3 sentences on what an investor should do with this information]"""
    
    def synthesize(self, symbol: str, doc_type: str, period: str,
                   financial: AnalystOutput, strategic: AnalystOutput,
                   tone: AnalystOutput) -> str:
        client = get_mistral_client()
        if not client:
            raise ValueError("Mistral client not configured")
        
        try:
            response = client.chat.complete(
                model="mistral-small-latest",
                messages=[
                    {"role": "system", "content": "You are a Chief Investment Officer synthesizing research. Be precise and actionable."},
                    {"role": "user", "content": self.PROMPT.format(
                        financial=financial.analysis,
                        strategic=strategic.analysis,
                        tone=tone.analysis,
                        symbol=symbol,
                        doc_type=doc_type,
                        period=period
                    )}
                ],
                temperature=0.3,
                max_tokens=2500
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            # Fallback: combine key points
            return f"""### {symbol} - {period}

**Financial Highlights:**
{chr(10).join('• ' + p for p in financial.key_points[:5])}

**Strategic Position:**
{chr(10).join('• ' + p for p in strategic.key_points[:5])}

**Management Tone:**
{chr(10).join('• ' + p for p in tone.key_points[:5])}

Overall Sentiment: {(financial.sentiment_score + strategic.sentiment_score + tone.sentiment_score) / 3:.2f}
"""


class InstitutionalSummarizer:
    """
    Main orchestrator for multi-agent document summarization.
    Produces nuanced summaries competitive with public.com's Generated Assets.
    """
    
    def __init__(self):
        self.financial_agent = FinancialAnalystAgent()
        self.strategic_agent = BusinessStrategistAgent()
        self.tone_agent = ManagementToneAgent()
        self.synthesis_agent = SynthesisAgent()
        
        # Rate limiting for OpenAI (very generous limits)
        self.requests_per_minute = 500  # Tier 1 allows 500 RPM
        self.last_request_time = 0
    
    def _rate_limit(self):
        """Ensure we don't exceed API rate limits."""
        elapsed = time.time() - self.last_request_time
        min_interval = 60 / self.requests_per_minute
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self.last_request_time = time.time()
    
    def generate_summary(self, document: str, symbol: str, 
                        doc_type: str = "Annual Report",
                        period: str = "FY2024") -> Dict[str, Any]:
        """
        Generate institutional-grade summary using multi-agent analysis.
        
        Returns:
            {
                "nuanced_summary": str,  # The final synthesis
                "financial_analysis": str,
                "strategic_analysis": str,
                "tone_analysis": str,
                "overall_sentiment": float,  # -1 to 1
                "processing_time": float
            }
        """
        start_time = time.time()
        
        logger.info(f"Starting multi-agent analysis for {symbol} {period}...")
        
        # Run all agents
        self._rate_limit()
        logger.info(f"  → Running Financial Analyst...")
        financial = self.financial_agent.analyze(document)
        
        self._rate_limit()
        logger.info(f"  → Running Business Strategist...")
        strategic = self.strategic_agent.analyze(document)
        
        self._rate_limit()
        logger.info(f"  → Running Management Tone Analyst...")
        tone = self.tone_agent.analyze(document)
        
        # Synthesize all perspectives
        self._rate_limit()
        logger.info(f"  → Running Synthesis Agent...")
        nuanced_summary = self.synthesis_agent.synthesize(
            symbol, doc_type, period,
            financial, strategic, tone
        )
        
        # Calculate overall sentiment
        overall_sentiment = (
            financial.sentiment_score * 0.4 +
            strategic.sentiment_score * 0.35 +
            tone.sentiment_score * 0.25
        )
        
        processing_time = time.time() - start_time
        logger.info(f"✅ Completed {symbol} {period} in {processing_time:.1f}s")
        
        return {
            "nuanced_summary": nuanced_summary,
            "financial_analysis": financial.analysis,
            "strategic_analysis": strategic.analysis,
            "tone_analysis": tone.analysis,
            "overall_sentiment": overall_sentiment,
            "processing_time": processing_time
        }


def test_summarizer():
    """Test the summarizer with a sample document."""
    if not OPENAI_API_KEY:
        print("❌ OPENAI_API_KEY not set. Please add it to .env file.")
        return
    
    sample_doc = """
    Annual Report FY 2024 - Reliance Industries Limited
    
    Chairman's Message:
    Dear Shareholders, I am pleased to report another year of exceptional performance.
    Our consolidated revenue grew 15% YoY to ₹9,74,864 crores. Net profit increased 12%
    to ₹73,670 crores. EBITDA margin improved to 14.2%.
    
    Jio Platforms continues to dominate with 450 million subscribers, adding 15 million
    new users this year. ARPU improved to ₹178.8 from ₹167.6.
    
    Retail business achieved ₹2,60,000 crore revenue with 18,040 stores.
    
    We invested ₹1,50,000 crores in green energy initiatives including solar manufacturing
    and hydrogen projects. This positions us for the energy transition.
    
    Risks: Telecom competition remains intense. Oil & Gas volatility affects O2C segment.
    
    Guidance: We expect 18-20% revenue growth in FY2025 driven by Jio and Retail expansion.
    """
    
    summarizer = InstitutionalSummarizer()
    result = summarizer.generate_summary(
        sample_doc,
        symbol="RELIANCE",
        doc_type="Annual Report",
        period="FY2024"
    )
    
    print("\n" + "="*60)
    print("NUANCED SUMMARY:")
    print("="*60)
    print(result["nuanced_summary"])
    print(f"\nOverall Sentiment: {result['overall_sentiment']:.2f}")
    print(f"Processing Time: {result['processing_time']:.1f}s")


if __name__ == "__main__":
    test_summarizer()
