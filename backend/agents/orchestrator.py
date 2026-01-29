"""
Inwezt V3 - Institutional-Grade Deep RAG Orchestrator

This is the PRODUCTION-READY V3 orchestrator that replaces the MVP.
It leverages deep data from concall transcripts and annual reports.

V3 Enhancements:
1. Nuanced summarization of large transcripts/reports
2. Integrated management guidance synthesis
3. Dynamic weighting of corporate signals over news
4. Visual RAG with chart generation (V3.1)
"""

import logging
import json
import os
from typing import Dict, Any, List, Optional
from datetime import datetime, date
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor, as_completed

# LLM clients
import google.generativeai as genai
from openai import OpenAI
from mistralai import Mistral

from .base import BaseAgent
from .market_data import MarketDataAgent
from .filings import FilingsAgent
from .news import NewsAgent
from .technical import TechnicalAgent

# Visual RAG imports
try:
    from backend.core.charting.generator import detect_chart_intent, generate_relevant_chart, ChartGenerator
    VISUAL_RAG_AVAILABLE = True
except ImportError:
    # Fallback to local import if backend prefix fails in certain environments
    try:
        from core.charting.generator import detect_chart_intent, generate_relevant_chart, ChartGenerator
        VISUAL_RAG_AVAILABLE = True
    except ImportError:
        VISUAL_RAG_AVAILABLE = False

logger = logging.getLogger("OrchestratorV2")


class DateEncoder(json.JSONEncoder):
    """Custom JSON encoder for dates and decimals."""
    def default(self, obj):
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        if hasattr(obj, 'item'):
            return obj.item()
        return super().default(obj)


# =============================================================================
# INSTITUTIONAL PROMPT TEMPLATE
# =============================================================================

INSTITUTIONAL_PROMPT = """
You are a senior equity research analyst at a top-tier institutional asset manager. Your analysis is read by portfolio managers making substantial allocation decisions.

ANALYTICAL FRAMEWORK (ONLY comment on aspects where you have ACTUAL DATA):

1. VALUATION CONTEXT
   - Compare current multiple to historical range (IF historical data is provided)
   - Justify premium/discount vs sector (IF sector PE is provided)
   - Note 52-week range position (IF high/low is provided)

2. EARNINGS QUALITY
   - ONLY comment on margin trajectory if you have actual margin data
   - ONLY mention one-offs/special items if explicitly stated in earnings context
   - DO NOT make generic statements like "no evidence of one-offs" - simply skip if no data

3. MANAGEMENT SIGNALS
   - ONLY comment if actual earnings call transcripts or management quotes are provided
   - Reference specific statements, not generic "tone" assessments
   - If no management commentary exists, skip this section entirely

4. RISK FRAMEWORK
   - Identify 2-3 key risks based on business model and sector
   - Quantify where possible using provided data
   - Focus on material risks, not hypothetical scenarios

5. THESIS ARTICULATION
   - State a clear view: Overweight / Neutral / Underweight
   - Provide fair value range based on available valuation metrics
   - Define catalysts based on actual upcoming events (earnings dates, regulatory decisions)

OUTPUT FORMAT RULES (CRITICAL):
- NO markdown formatting: no #, no **
- Use section names in CAPS followed by a colon
- Use bullet points (simple dashes -) for key points within each section
- Each bullet should be a clear, standalone insight
- No emojis, no casual language
- Use precise financial terminology
- Length: 300-450 words, dense with insight

HANDLING DATA GAPS:
- For qualitative context (e.g., business model, sector dynamics), use your internal knowledge.
- For NUMERICAL data (CAGR, PE ratios, prices), use ONLY the verified numbers provided in the context below.
- DO NOT invent or estimate numerical values. If a number is not provided, do not mention it.
- DO NOT make negative assertions ("no evidence of X", "no one-offs detected") when you simply lack data.
- If a prompt framework section has no data, SKIP IT ENTIRELY rather than writing filler.

CRITICAL: The 10-Year CAGR and other numbers marked as "VERIFIED DATA" must be cited EXACTLY as provided. Do not round, estimate, or change them.

REMEMBER: A portfolio manager wants insights based on ACTUAL DATA, not placeholder statements about missing data.

EXAMPLE OUTPUT FORMAT:

VALUATION CONTEXT:
- Current P/E of 22x sits 15% below its 5-year average of 26x
- Trading at a modest premium to sector peers (18x) justified by superior ROE of 18% vs sector 12%
- 52-week range position suggests contrarian entry point if fundamentals intact

EARNINGS QUALITY:
- Operating margins expanded 120bps to 14.2% in Q3, driven by cost optimization
- Free cash flow conversion remains strong at 85% of net income
- No significant one-offs distorting reported earnings

MANAGEMENT SIGNALS:
- Full-year guidance raised by 5% citing strong order book visibility
- Capital allocation remains disciplined with Rs 2,500 Cr buyback announced
- Management tone constructive on margin sustainability

RISKS:
- Commodity price volatility could compress margins by 200bps if crude rises above $90/bbl
- Execution delays in new capacity could defer revenue recognition by 1-2 quarters
- Currency depreciation exposure on imports (~15% of costs)

THESIS:
- Rating: Overweight
- Fair value range: Rs 1,800-2,000 based on 25x forward P/E
- Key catalyst: Q4 order inflows expected in March
- Timeline: 6-9 months for re-rating

---

STOCK: {symbol}

CURRENT MARKET DATA:
{market_data}

EARNINGS CALL / MANAGEMENT COMMENTARY:
{earnings_context}

RECENT NEWS & DEVELOPMENTS:
{news_context}

PEER COMPARISON:
{peer_context}

ANALYST QUESTION: {query}

---

ANALYSIS:
"""


def build_dynamic_prompt(
    symbol: str,
    has_sector_pe: bool,
    has_historical_data: bool,
    has_margin_data: bool,
    has_earnings_transcript: bool,
    has_growth_data: bool,
    chart_context: Optional[str] = None
) -> str:
    """
    Build a dynamic prompt that ONLY includes sections where we have actual data.
    This prevents LLM from writing filler for missing data.
    """
    
    sections = []
    
    # VISUAL CONTEXT - Instruct LLM to use the generated chart
    if chart_context:
        sections.append(f"""
0. VISUAL INSIGHTS (IMPORTANT)
   - A chart has been generated: "{chart_context}"
   - You MUST reference this chart in your analysis (e.g., "As shown in the revenue trend chart above...")
   - Use the chart's data to support your thesis
""")
    
    # VALUATION - always include if we have price
    sections.append("""
1. VALUATION CONTEXT
   - Compare current P/E to sector average (data provided)
   - Note 52-week range position and what it implies
   - Use 10-year CAGR to context long-term performance
""")
    
    # EARNINGS QUALITY - only if we have actual margin/growth data
    if has_margin_data or has_growth_data:
        sections.append("""
2. EARNINGS QUALITY
   - Comment on margin trajectory using provided net margin data
   - Analyze revenue/profit growth rates if available
   - Note ROE relative to sector average
""")
    
    # MANAGEMENT SIGNALS - only if we have actual transcripts/quotes
    if has_earnings_transcript:
        sections.append("""
3. MANAGEMENT SIGNALS
   - Reference specific management statements from earnings call
   - Note any guidance changes or strategic pivots
   - Mention capital allocation decisions (dividend/buyback)
""")
    
    # RISKS - always include (based on business model knowledge)
    sections.append("""
4. RISK FRAMEWORK
   - Identify 2-3 material risks based on business model and sector
   - Quantify impact where possible using available data
""")
    
    # THESIS - always include
    sections.append("""
5. THESIS
   - Clear rating: Overweight / Neutral / Underweight
   - Fair value range based on P/E or PB multiples
   - 2-3 key catalysts with timeline
""")
    
    framework = "\n".join(sections)
    
    return f"""
You are a senior equity research analyst. Your analysis must be based ONLY on the data provided below.

ANALYTICAL FRAMEWORK:
{framework}

OUTPUT RULES:
- Use bullet points (dashes -) for clarity
- Section names should use markdown headers (e.g. # 1. VALUATION CONTEXT)
- Use standard markdown bold/headers
- 300-400 words total
- DO NOT mention sections that aren't in the framework above
- DO NOT make statements about data you don't have

CRITICAL: Use ONLY verified numbers from the data below. If a calculation or number isn't provided, don't mention it.

STOCK: {symbol}
"""


# =============================================================================
# COMPARISON INTENT DETECTION
# =============================================================================

def detect_comparison_intent(query: str) -> tuple:
    """
    Detect if query is asking for a comparison between multiple stocks.
    Returns: (is_comparison: bool, comparison_type: str)
    
    Examples:
    - "Compare TCS vs Infosys" -> (True, "versus")
    - "TCS and Infosys comparison" -> (True, "comparison")
    - "Which is better: TCS or Wipro?" -> (True, "which_better")
    """
    q_lower = query.lower()
    
    # Comparison patterns
    patterns = {
        "versus": ["vs", "versus", "vs."],
        "comparison": ["compare", "comparison", "comparing"],
        "which_better": ["which is better", "which one", "should i choose", "better investment"],
        "difference": ["difference between", "how does .* differ"]
    }
    
    for comp_type, keywords in patterns.items():
        for keyword in keywords:
            if keyword in q_lower:
                return (True, comp_type)
    
    # Check for "X and Y" pattern with financial context
    if " and " in q_lower and any(word in q_lower for word in ["stock", "invest", "buy", "compare", "both"]):
        return (True, "and_pattern")
    
    return (False, None)


# =============================================================================
# QUERY DECOMPOSITION
# =============================================================================

def decompose_query(query: str, symbol: str) -> List[str]:
    """
    Break a high-level query into analytical sub-questions.
    This enables multi-hop reasoning over different data sources.
    """
    q_lower = query.lower()
    sub_questions = []
    
    # Always include valuation context
    sub_questions.append(f"What is {symbol}'s current PE ratio and how does it compare to its 5-year historical average?")
    
    # Peer comparison for valuation queries
    if any(word in q_lower for word in ['undervalued', 'overvalued', 'cheap', 'expensive', 'valuation', 'pe', 'price']):
        sub_questions.append(f"How does {symbol}'s PE compare to sector peers and what justifies any premium or discount?")
    
    # Management signals for buy/sell queries
    if any(word in q_lower for word in ['buy', 'sell', 'invest', 'hold', 'should']):
        sub_questions.append(f"What did management say in the most recent earnings call about growth outlook and guidance?")
        sub_questions.append(f"What are the 2-3 key risks that could impact {symbol}'s thesis?")
    
    # Catalysts
    sub_questions.append(f"What recent news or developments could act as catalysts for {symbol}?")
    
    return sub_questions


# =============================================================================
# CONTEXT BUILDERS
# =============================================================================

def build_valuation_insight(data: Dict[str, Any]) -> str:
    """
    Transform raw valuation data into analytical insight text.
    This is the "why" behind the numbers.
    """
    insights = []
    
    pe = data.get("pe_ratio")
    sector_pe = data.get("sector_pe")
    hist_avg_pe = data.get("historical_avg_pe", 22)  # Default assumption
    price = data.get("price")
    high_52w = data.get("high_52w")
    low_52w = data.get("low_52w")
    
    if pe and sector_pe:
        premium = ((pe / sector_pe) - 1) * 100
        if premium > 30:
            insights.append(f"PE of {pe:.1f}x represents a {premium:.0f}% premium to sector average ({sector_pe:.1f}x). This premium requires justification through superior growth or returns.")
        elif premium < -20:
            insights.append(f"PE of {pe:.1f}x is at a {abs(premium):.0f}% discount to sector ({sector_pe:.1f}x). Either a value opportunity or reflects structural concerns.")
        else:
            insights.append(f"PE of {pe:.1f}x is broadly in line with sector average ({sector_pe:.1f}x).")
    
    if pe and hist_avg_pe:
        vs_hist = ((pe / hist_avg_pe) - 1) * 100
        if vs_hist < -20:
            insights.append(f"Currently trading below historical average PE of ~{hist_avg_pe}x — potentially attractive entry point if fundamentals intact.")
        elif vs_hist > 20:
            insights.append(f"Trading above historical average PE of ~{hist_avg_pe}x — market pricing in elevated growth expectations.")
    
    if price and high_52w and low_52w:
        range_position = (price - low_52w) / (high_52w - low_52w) * 100 if high_52w != low_52w else 50
        if range_position < 25:
            insights.append(f"Price near 52-week lows (at {range_position:.0f}% of range). Contrarian opportunity if thesis intact.")
        elif range_position > 75:
            insights.append(f"Price near 52-week highs (at {range_position:.0f}% of range). Momentum positive but entry risk elevated.")
    
    return " ".join(insights) if insights else "Valuation data limited."


def build_peer_context(symbol: str, peers: List[Dict]) -> str:
    """Format peer comparison data."""
    if not peers:
        return "Peer comparison data not available."
    
    lines = []
    for peer in peers[:3]:
        name = peer.get("name", "Unknown")
        pe = peer.get("pe_ratio", "N/A")
        mcap = peer.get("market_cap", "N/A")
        lines.append(f"- {name}: PE {pe}x, Mkt Cap {mcap}")
    
    return "\n".join(lines)


def build_earnings_context(data: Dict[str, Any]) -> str:
    """
    Extract and format earnings call / filing context.
    V3: Prioritize nuanced summaries from concalls and annual reports.
    """
    filings = data.get("filings", [])
    concalls = data.get("concalls", [])
    reports = data.get("annual_reports", [])
    
    sections = []
    
    # 1. MANAGEMENT GUIDANCE (from Concalls)
    if concalls:
        sections.append("MANAGEMENT GUIDANCE (Source: Latest Earnings Call):")
        for call in concalls:
            summary = call.get("nuanced_summary", call.get("management_guidance", "Guidance details in transcript."))
            sections.append(f"- {summary}")
            if call.get("quarter") and call.get("fiscal_year"):
                sections.append(f"  [Ref: {call.get('fiscal_year')} Q{call.get('quarter')}]")
    
    # 2. STRATEGIC OUTLOOK (from Annual Reports)
    if reports:
        sections.append("\nSTRATEGIC OUTLOOK (Source: Annual Report):")
        for report in reports:
            summary = report.get("nuanced_summary", report.get("summary", "Summary details in report."))
            sections.append(f"- {summary}")
            sections.append(f"  [Ref: FY{report.get('fiscal_year')}]")
    
    # 3. OTHER FILINGS
    if filings:
        sections.append("\nRECENT CORPORATE ACTIONS:")
        for filing in filings[:5]:
            title = filing.get("title", "")
            doc_date = filing.get("date", filing.get("doc_date", ""))
            doc_type = filing.get("type", filing.get("doc_type", ""))
            sections.append(f"- [{doc_type}] {title} ({doc_date})")
            
    if not sections:
        return "No recent earnings call or deep filing data available. Analysis based on market metrics and news only."
        
    return "\n".join(sections)


# =============================================================================
# EXPERIMENTAL ORCHESTRATOR V2
# =============================================================================

class OrchestratorV2(BaseAgent):
    """
    Experimental institutional-grade RAG orchestrator.
    Runs alongside MVP for A/B testing.
    """
    
    # Known ticker mappings
    KNOWN_TICKERS = {
        "reliance": "RELIANCE", "tcs": "TCS", "infosys": "INFY", "infy": "INFY",
        "hdfc": "HDFCBANK", "hdfc bank": "HDFCBANK", "icici": "ICICIBANK",
        "sbi": "SBIN", "state bank": "SBIN", "bharti": "BHARTIARTL", "airtel": "BHARTIARTL",
        "tata motors": "TATAMOTORS", "maruti": "MARUTI", "wipro": "WIPRO",
        "itc": "ITC", "asian paints": "ASIANPAINT", "hcl": "HCLTECH",
        "sun pharma": "SUNPHARMA", "titan": "TITAN", "bajaj finance": "BAJFINANCE",
        "kotak": "KOTAKBANK", "axis": "AXISBANK", "indusind": "INDUSINDBK",
        "hdfc life": "HDFCLIFE", "adani": "ADANIENT", "vedanta": "VEDL",
        "tata steel": "TATASTEEL", "jsw steel": "JSWSTEEL", "hindalco": "HINDALCO",
        "ongc": "ONGC", "ntpc": "NTPC", "power grid": "POWERGRID",
        "coal india": "COALINDIA", "ultratech": "ULTRACEMCO", "grasim": "GRASIM",
        "divis": "DIVISLAB", "dr reddy": "DRREDDY", "cipla": "CIPLA",
        "britannia": "BRITANNIA", "nestle": "NESTLEIND", "hindustan unilever": "HINDUNILVR",
        "hul": "HINDUNILVR", "bajaj auto": "BAJAJ-AUTO", "hero": "HEROMOTOCO",
        "eicher": "EICHERMOT", "m&m": "M&M", "mahindra": "M&M",
        "tech mahindra": "TECHM", "ltim": "LTIM", "lt": "LT", "larsen": "LT"
    }
    
    def __init__(self):
        super().__init__(name="OrchestratorV2")
        
        # Initialize sub-agents
        self.market_agent = MarketDataAgent()
        self.filings_agent = FilingsAgent()
        self.news_agent = NewsAgent()
        self.technical_agent = TechnicalAgent()
        
        # LLM Setup
        self.provider = os.getenv("LLM_PROVIDER", "gemini")
        self.openai_client = None
        self.gemini_client = None
        self.mistral_client = None
        
        if self.provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                self.openai_client = OpenAI(api_key=api_key)
        elif self.provider == "mistral":
            api_key = os.getenv("MISTRAL_API_KEY")
            if api_key:
                self.mistral_client = Mistral(api_key=api_key)
        
        # Fallback Logic (Disabling per user request for strictly Mistral)
        # if not (self.openai_client or self.mistral_client):
        #     self.provider = "gemini"
        #     api_key = os.getenv("GEMINI_API_KEY")
        #     if api_key:
        #         genai.configure(api_key=api_key)
        #         self.gemini_client = genai.GenerativeModel('gemini-2.0-flash-exp')
    
    def _extract_tickers(self, query: str) -> List[str]:
        """Extract stock tickers from query."""
        import re
        query_lower = query.lower()
        found_tickers = []
        
        for name, ticker in self.KNOWN_TICKERS.items():
            if name in query_lower and ticker not in found_tickers:
                found_tickers.append(ticker)
        
        words = re.findall(r'\b[A-Z]{2,10}\b', query)
        for word in words:
            if word not in found_tickers and len(word) >= 2:
                if word in ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "SBIN", "ITC", "AXISBANK", "WIPRO"]:
                    found_tickers.append(word)
        
        return found_tickers[:5]
    
    def _process_comparison(self, query: str, tickers: List[str], context: Dict[str, Any]):
        """
        Process a multi-company comparison query.
        Enhanced to run full agent pipeline for institutional-grade analysis.
        """
        import time
        start_time = time.time()
        
        # Agent status map for frontend research trace
        agent_status_map = {
            "MarketDataAgent": "Market Dynamics",
            "FilingsAgent": "Deep Filings & Concalls",
            "NewsAgent": "Recent Developments",
            "TechnicalAgent": "Technical Indicators"
        }
        
        # 1. Queue all agents (for frontend research trace)
        for agent_name in agent_status_map.values():
            yield {"status": "thinking", "message": f"Queued {agent_name}..."}
        
        # 2. Run full agent pipeline for all tickers in parallel
        agents = [self.market_agent, self.filings_agent, self.news_agent, self.technical_agent]
        all_ticker_data = {ticker: {} for ticker in tickers}
        comparison_data = {}
        
        # Create tasks for all agents across all tickers
        with ThreadPoolExecutor(max_workers=8) as executor:
            future_to_task = {}
            for ticker in tickers:
                ticker_context = context.copy()
                ticker_context["formatted_tickers"] = [ticker]
                ticker_context["comparison_mode"] = True  # Flag for agents to use lighter processing
                for agent in agents:
                    future = executor.submit(agent.process, query, ticker_context)
                    future_to_task[future] = (ticker, agent.name)
            
            # Track completed agents for status updates
            completed_agents = set()
            
            for future in as_completed(future_to_task):
                ticker, agent_name = future_to_task[future]
                try:
                    result = future.result()
                    if result.get("has_data", False):
                        all_ticker_data[ticker][agent_name] = result["data"]
                        
                        # Emit status update when an agent type finishes for all tickers
                        if agent_name not in completed_agents:
                            # Check if this agent is done for all tickers
                            agent_done_count = sum(
                                1 for t in tickers 
                                if agent_name in all_ticker_data.get(t, {})
                            )
                            if agent_done_count >= len(tickers):
                                completed_agents.add(agent_name)
                                display_name = agent_status_map.get(agent_name, agent_name)
                                yield {"status": "thinking", "message": f"[✓] Processed {display_name}"}
                                self._log_activity(f"[Comparison] {agent_name} completed for all tickers")
                except Exception as e:
                    self._log_activity(f"[Comparison] {agent_name} failed for {ticker}: {e}")
            
            # Emit any remaining agent completions
            for agent_name in agent_status_map.keys():
                if agent_name not in completed_agents:
                    display_name = agent_status_map.get(agent_name, agent_name)
                    yield {"status": "thinking", "message": f"[✓] Processed {display_name}"}
        
        # 3. Fetch comparison metrics from centralized data source (RapidAPI)
        # See ARCHITECTURE.md and backend/core/data_sources.py for data source hierarchy
        from backend.core.data_sources import get_fundamentals_batch
        
        yield {"status": "thinking", "message": "Fetching fundamentals from RapidAPI..."}
        
        # Use centralized batch function (handles parallel fetching internally)
        comparison_data = get_fundamentals_batch(tickers)
        
        for ticker in tickers:
            if ticker in comparison_data and comparison_data[ticker]:
                self._log_activity(f"[Comparison] Fetched fundamentals for {ticker} from RapidAPI")
        
        if not comparison_data:
            yield {
                "status": "error",
                "response": "Could not fetch data for comparison. Please try again."
            }
            return
        
        # 4. Generate comparison chart
        chart_data = None
        if VISUAL_RAG_AVAILABLE:
            try:
                chart_gen = ChartGenerator()
                peers = [
                    {"symbol": t, **comparison_data[t]}
                    for t in tickers if t in comparison_data
                ]
                chart_data = chart_gen.peer_comparison(
                    peers=peers,
                    metric="pe_ratio",
                    highlight_symbol=tickers[0]
                )
                self._log_activity(f"[Comparison] Generated comparison chart")
            except Exception as e:
                self._log_activity(f"[Comparison] Chart error: {e}")
        
        # 5. Build comparison table text
        yield {"status": "thinking", "message": "Synthesizing institutional analysis..."}
        
        # Yield metadata early so table appears immediately
        metadata_yield = {
            "status": "success",
            "response": "",
            "is_partial": True,
            "intent": "comparison",
            "comparison": {
                "symbols": tickers,
                "metrics": comparison_data
            }
        }
        if chart_data:
            metadata_yield["chart"] = chart_data
        yield metadata_yield

        # Build enhanced metrics table with sector context
        def format_pe_with_sector(data: Dict) -> str:
            pe = data.get("pe_ratio")
            sector_pe = data.get("sector_pe")
            if pe and sector_pe:
                discount = data.get("valuation_discount", 0)
                arrow = "↓" if discount > 0 else "↑" if discount < 0 else "→"
                return f"{pe:.1f}x (vs {sector_pe:.1f}x) {arrow}{abs(discount):.0f}%"
            return f"{pe:.1f}x" if pe else "N/A"
        
        def format_metric_with_trend(val, ytd_change=None) -> str:
            if val is None:
                return "N/A"
            if ytd_change is not None:
                arrow = "↗" if ytd_change > 0 else "↘" if ytd_change < 0 else "→"
                return f"{val:.1f}% {arrow}"
            return f"{val:.1f}%"
        
        # Build premium comparison table for LLM context
        comp_table = "📊 COMPARISON DATA:\n"
        comp_table += f"| Metric | {' | '.join(tickers)} |\n"
        comp_table += f"|--------|{'|'.join(['------'] * len(tickers))}|\n"
        
        # P/E with sector context
        pe_row = "| P/E vs Sector |"
        for t in tickers:
            pe_row += f" {format_pe_with_sector(comparison_data.get(t, {}))} |"
        comp_table += pe_row + "\n"
        
        # Valuation status
        val_row = "| Valuation Status |"
        for t in tickers:
            status = comparison_data.get(t, {}).get("valuation_status", "N/A")
            val_row += f" {status} |"
        comp_table += val_row + "\n"
        
        # Other metrics
        metrics_order = [("pb_ratio", "P/B Ratio"), ("roe", "ROE"), ("net_margin", "Net Margin"), 
                        ("revenue_growth", "Rev Growth"), ("market_cap", "Market Cap")]
        
        for metric_key, metric_label in metrics_order:
            row = f"| {metric_label} |"
            for t in tickers:
                val = comparison_data.get(t, {}).get(metric_key, "N/A")
                if isinstance(val, (int, float)):
                    if metric_key == "market_cap":
                        row += f" ₹{val:,.0f}Cr |"
                    else:
                        row += f" {val:.1f}{'%' if 'ratio' not in metric_key else 'x'} |"
                else:
                    row += f" {val} |"
            comp_table += row + "\n"
        
        # 6. Build enriched context from agent data with management QUOTES
        enriched_context = ""
        for ticker in tickers:
            ticker_data = all_ticker_data.get(ticker, {})
            
            # Filings/Concall insights - extract actual quotes
            filings_data = ticker_data.get("FilingsAgent", {})
            concalls = filings_data.get("concalls", [])
            if concalls:
                enriched_context += f"\n💬 {ticker} MANAGEMENT COMMENTARY:\n"
                for call in concalls[:1]:
                    summary = call.get("nuanced_summary", call.get("management_guidance", ""))
                    if summary:
                        # Extract key quote-like statements
                        enriched_context += f'"{summary[:300]}..." - Management, Earnings Call\n'
            
            # News insights
            news_data = ticker_data.get("NewsAgent", {})
            news_items = news_data.get("news", [])
            if news_items:
                enriched_context += f"\n📰 {ticker} RECENT NEWS:\n"
                for item in news_items[:2]:
                    enriched_context += f"- {item.get('headline', '')}\n"
        
        # 7. Generate LLM synthesis with premium prompt
        comparison_prompt = f"""You are a senior equity research analyst at a top investment bank comparing these Indian stocks.

{comp_table}

{enriched_context}

USER QUESTION: {query}

Generate an INSTITUTIONAL-GRADE comparison analysis. Use this EXACT format:

## 📊 Key Differences
| Factor | {tickers[0]} | {tickers[1]} | Investment Implication |
|--------|-------------|-------------|------------------------|
| Scale & Market Position | [data] | [data] | [implication] |
| Business Mix | [data] | [data] | [implication] |
| Competitive Moat | [data] | [data] | [implication] |

## 💰 Valuation Analysis
- **{tickers[0]}**: [PE vs sector, valuation status, justify if premium/discount is warranted]
- **{tickers[1]}**: [PE vs sector, valuation status, justify if premium/discount is warranted]
- **Winner**: [which is more attractively valued and why]

## 📈 Growth & Profitability
- **Revenue Momentum**: [compare with specific numbers and YoY trends]
- **Margin Quality**: [compare net margins, explain sustainability]
- **ROE Efficiency**: [compare capital efficiency]

## 💬 Management Signals
- Quote or paraphrase key management guidance from concalls for each stock

## 🎯 Investment Recommendation
- **Conservative Investors**: [recommendation with rationale]
- **Growth Investors**: [recommendation with rationale]
- **Risk-Adjusted Pick**: [final verdict]

Keep response under 400 words. Be specific with numbers. Use ✓ to mark better metrics.
"""
        
        response_text = ""
        for chunk in self._stream_llm_response_simple(comparison_prompt):
            response_text += chunk
            yield {"status": "success", "response": response_text, "is_partial": True}
        
        # 8. Final response
        processing_time = int((time.time() - start_time) * 1000)
        
        final_response = {
            "status": "success",
            "response": response_text,
            "is_partial": False,
            "intent": "comparison",
            "comparison": {
                "symbols": tickers,
                "metrics": comparison_data
            },
            "processing_time_ms": processing_time,
            "data_used": {"stocks_compared": tickers, "agents_used": list(agent_status_map.keys())}
        }
        
        if chart_data:
            final_response["chart"] = chart_data
        
        yield final_response
    
    def _fetch_stock_metrics(self, ticker: str) -> Dict[str, Any]:
        """Fetch key metrics for a single stock using Live API."""
        try:
            from backend.core.utils.fetch_indian_data import fetch_indian_data
            data = fetch_indian_data(ticker)
            
            if data:
                return {
                    "pe_ratio": data.get("pe_ratio"),
                    "pb_ratio": data.get("book_value") and (data.get("price", 0) / data.get("book_value") if data.get("book_value") else None),
                    "roe": data.get("roe"),
                    "net_margin": data.get("net_margin"),
                    "revenue_growth": data.get("revenue_growth"),
                    "market_cap": data.get("market_cap"),
                    "price": data.get("price"),
                    "eps": data.get("eps_ttm")
                }
        except Exception as e:
            self._log_activity(f"[Comparison] Metrics fetch failed for {ticker}: {e}")
        return {}
    
    def _stream_llm_response_simple(self, prompt: str):
        """Simple LLM streaming for comparison responses."""
        try:
            if self.provider == "mistral" and self.mistral_client:
                stream = self.mistral_client.chat.stream(
                    model=os.getenv("LLM_MODEL", "mistral-large-latest"),
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3
                )
                for chunk in stream:
                    content = chunk.data.choices[0].delta.content
                    if content:
                        yield content
            elif self.provider == "openai" and self.openai_client:
                stream = self.openai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    stream=True
                )
                for chunk in stream:
                    content = chunk.choices[0].delta.content
                    if content:
                        yield content
            elif self.gemini_client:
                response = self.gemini_client.generate_content(prompt, stream=True)
                for chunk in response:
                    yield chunk.text
        except Exception as e:
            self._log_activity(f"[Comparison] LLM error: {e}")
            yield f"Analysis generation failed: {str(e)}"
    
    def process(self, query: str, context: Dict[str, Any]):
        """
        Process query using institutional-grade RAG pipeline (Generator).
        Yields progress updates for research trace and final synthesized response chunks.
        """
        self._log_activity(f"[V2] Processing: {query}")
        
        # 1. Extract tickers
        tickers = self._extract_tickers(query)
        context["formatted_tickers"] = tickers
        symbol = tickers[0] if tickers else "UNKNOWN"
        self._log_activity(f"[V2] Extracted: {tickers}")
        
        # 2. Check for comparison intent (NEW)
        is_comparison, comp_type = detect_comparison_intent(query)
        if is_comparison and len(tickers) >= 2:
            self._log_activity(f"[V2] Comparison detected: {comp_type} with {tickers}")
            yield {"status": "thinking", "message": f"Comparing {', '.join(tickers)}..."}
            
            # Delegate to comparison processing
            for event in self._process_comparison(query, tickers, context):
                yield event
            return
        
        yield {"status": "thinking", "message": f"Identifying signals for {symbol}..."}
        
        # 3. Decompose query (for single-stock analysis)
        sub_questions = decompose_query(query, symbol)
        self._log_activity(f"[V2] Decomposed into {len(sub_questions)} sub-questions")
        
        # 4. Parallel agent execution (Checklist Trigger)
        agents = [self.market_agent, self.filings_agent, self.news_agent, self.technical_agent]
        aggregated_data = {}
        
        agent_status_map = {
            "MarketDataAgent": "Market Dynamics",
            "FilingsAgent": "Deep Filings & Concalls",
            "NewsAgent": "Recent Developments",
            "TechnicalAgent": "Technical Indicators"
        }

        # Send initial queuing statuses
        for agent_name in agent_status_map.values():
            yield {"status": "thinking", "message": f"Queued {agent_name}..."}

        with ThreadPoolExecutor(max_workers=4) as executor:
            future_to_agent = {
                executor.submit(agent.process, query, context.copy()): agent.name
                for agent in agents
            }
            
            for future in as_completed(future_to_agent):
                agent_name = future_to_agent[future]
                try:
                    result = future.result()
                    if result.get("has_data", False):
                        aggregated_data[agent_name] = result["data"]
                        display_name = agent_status_map.get(agent_name, agent_name)
                        yield {"status": "thinking", "message": f"[✓] Processed {display_name}"}
                        self._log_activity(f"[V2] {agent_name} contributed data")
                except Exception as e:
                    self._log_activity(f"[V2] {agent_name} failed: {e}")
        
        # 4. Build rich context
        yield {"status": "thinking", "message": "Synthesizing institutional analysis..."}
        market_data = aggregated_data.get("MarketDataAgent", {})
        
        # Get snapshots for valuation
        snapshots = market_data.get("snapshots", [])
        latest = {}
        latest_for_prompt = {}
        if snapshots:
            latest = snapshots[0] if isinstance(snapshots[0], dict) else {}
            def _round_val(v):
                try: 
                    return round(float(v), 2) if v is not None else "N/A"
                except: 
                    return "N/A"
                    
            market_data.update({
                "pe_ratio": _round_val(latest.get("pe_ratio")),
                "sector_pe": _round_val(latest.get("sector_pe")),
                "price": _round_val(latest.get("price")),
                "high_52w": _round_val(latest.get("high_52w")),
                "low_52w": _round_val(latest.get("low_52w")),
            })
            latest_for_prompt = {k: _round_val(v) for k,v in latest.items()}
        
        valuation_insight = build_valuation_insight(market_data)
        peer_context = build_peer_context(symbol, market_data.get("peers", []))
        
        filings_data = aggregated_data.get("FilingsAgent", {})
        earnings_context = build_earnings_context(filings_data)
        
        news_data = aggregated_data.get("NewsAgent", {})
        news_items = news_data.get("news", [])
        news_context = "\n".join([f"- {n.get('headline', '')}" for n in news_items[:5]]) if news_items else "No recent news available."
        
        long_term = market_data.get("long_term_trend", {})
        cagr_10yr = long_term.get("cagr_10yr", "N/A")
        
        market_data_str = f"""
VALUATION METRICS (Current):
- Price: Rs {latest_for_prompt.get('price', 'N/A')}
- Market Cap: {market_data.get('market_cap_formatted', 'N/A')}
- PE Ratio: {latest_for_prompt.get('pe_ratio', 'N/A')}x
- Sector PE: {latest_for_prompt.get('sector_pe', 'N/A')}x
- PB Ratio: {latest_for_prompt.get('pb_ratio', 'N/A')}x
- Book Value: Rs {latest_for_prompt.get('book_value', 'N/A')}

TRADING METRICS:
- 52W High: Rs {latest_for_prompt.get('high_52w', 'N/A')}
- 52W Low: Rs {latest_for_prompt.get('low_52w', 'N/A')}
- YTD Change: {latest_for_prompt.get('ytd_change', 'N/A')}%
- Beta: {latest_for_prompt.get('beta', 'N/A')}

FUNDAMENTALS (TTM):
- EPS: Rs {latest_for_prompt.get('eps_ttm', 'N/A')}
- Dividend per Share: Rs {latest_for_prompt.get('dividend_per_share', 'N/A')}
- Dividend Yield: {latest_for_prompt.get('dividend_yield', 'N/A')}%

GROW & PROFIT:
- Revenue Growth: {latest_for_prompt.get('revenue_growth', 'N/A')}%
- Profit Growth: {latest_for_prompt.get('profit_growth', 'N/A')}%
- Net Margin: {latest_for_prompt.get('net_margin', 'N/A')}%
- ROE: {latest_for_prompt.get('roe', 'N/A')}%

10-YEAR PERFORMANCE (VERIFIED):
- CAGR: {cagr_10yr}%
- Total Return: {long_term.get('change_pct_total', 'N/A')}%

VALUATION INSIGHT: {valuation_insight}
"""
        
        # 5. Generate relevant chart (MOVED UP for context)
        chart_data = None
        chart_context_str = None
        if VISUAL_RAG_AVAILABLE:
            try:
                chart_data = generate_relevant_chart(
                    query=query,
                    market_data=market_data,
                    filings_data=filings_data,
                    symbol=symbol
                )
                if chart_data:
                    self._log_activity(f"[V2] Generated {chart_data.get('type')} chart")
                    insight = chart_data.get("insight", "showing visual trends.")
                    chart_context_str = f"A {chart_data.get('type').replace('_', ' ')} chart titled '{chart_data.get('title')}' is provided. {insight}"
            except Exception as e:
                self._log_activity(f"[V2] Chart generation failed: {e}")

        # 6. Synthesize response (STREAMING)
        full_response_text = ""
        for chunk in self._stream_institutional(
            query=query,
            symbol=symbol,
            market_data=market_data_str,
            earnings_context=earnings_context,
            news_context=news_context,
            peer_context=peer_context,
            latest_snapshot=latest,
            chart_context=chart_context_str
        ):
            full_response_text += chunk
            yield {
                "status": "success",
                "response": full_response_text, # Frontend accumulates or replaces
                "chunk": chunk,                # For word-by-word effect
                "data": aggregated_data,
                "is_partial": True,
                "chart": chart_data
            }
            
        yield {
            "status": "success",
            "response": full_response_text,
            "data": aggregated_data,
            "chart": chart_data,  # NEW: Chart as base64
            "category": "institutional_analysis",
            "agents_used": list(aggregated_data.keys()),
            "version": "v3_visual",
            "is_partial": False
        }
    
    def _stream_institutional(
        self,
        query: str,
        symbol: str,
        market_data: str,
        earnings_context: str,
        news_context: str,
        peer_context: str,
        latest_snapshot: Dict[str, Any],
        chart_context: Optional[str] = None
    ):
        """
        Generate institutional-grade response via Mistral Stream.
        """
        if not (self.openai_client or self.gemini_client or self.mistral_client):
            yield "Error: AI model not configured."
            return
        
        # Build prompt
        has_sector_pe = latest_snapshot.get('sector_pe') is not None
        has_historical_data = "10-Year CAGR" in market_data
        has_margin_data = latest_snapshot.get('net_margin') is not None
        has_growth_data = latest_snapshot.get('revenue_growth') is not None or latest_snapshot.get('profit_growth') is not None
        has_earnings_transcript = earnings_context and "management" in earnings_context.lower() and len(earnings_context) > 200
        
        dynamic_system_prompt = build_dynamic_prompt(
            symbol=symbol,
            has_sector_pe=has_sector_pe,
            has_historical_data=has_historical_data,
            has_margin_data=has_margin_data,
            has_earnings_transcript=has_earnings_transcript,
            has_growth_data=has_growth_data,
            chart_context=chart_context
        )
        
        prompt = f"""{dynamic_system_prompt}

CURRENT MARKET DATA:
{market_data}

CORPORATE ACTIONS:
{earnings_context}

RECENT NEWS:
{news_context}

PEER COMPARISON:
{peer_context}

ANALYST QUESTION: {query}

---

ANALYSIS:
"""
        
        try:
            if self.provider == "mistral" and self.mistral_client:
                stream_response = self.mistral_client.chat.stream(
                    model=os.getenv("LLM_MODEL", "mistral-large-latest"),
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3
                )
                for chunk in stream_response:
                    content = chunk.data.choices[0].delta.content
                    if content:
                        yield content
            
            elif self.provider == "openai" and self.openai_client:
                stream = self.openai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    stream=True
                )
                for chunk in stream:
                    content = chunk.choices[0].delta.content
                    if content:
                        yield content
            
            elif self.gemini_client:
                # Gemini streaming
                response = self.gemini_client.generate_content(prompt, stream=True)
                for chunk in response:
                    yield chunk.text
                    
        except Exception as e:
            self._log_activity(f"[V2] Stream error: {e}")
            yield f"Analysis generation failed: {str(e)}"
