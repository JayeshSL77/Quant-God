
import logging
from typing import Dict, Any, List, Optional
import os
import json
from datetime import date, datetime
from decimal import Decimal
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor, as_completed

# Lazy imports for LLM clients
import google.generativeai as genai
from openai import OpenAI
from mistralai import Mistral

# Custom JSON encoder to handle date and Decimal objects
class DateEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        if hasattr(obj, 'item'):  # Handle numpy types (int64, float64, bool_)
            return obj.item()
        return super().default(obj)

from .base import BaseAgent
from .router import RouterAgent
from .market_data import MarketDataAgent
from .filings import FilingsAgent
from .news import NewsAgent
from .technical import TechnicalAgent

# Semantic search integration
try:
    from data.embeddings import build_semantic_context
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False

# Guardrail / Fact Checker prompt
FACT_CHECK_PROMPT = """
You are a strict financial fact-checker. 
Review the proposed response against the provided retrieved data.
Key Rules:
1. Every numerical claim (price, PE, percentage) MUST be supported by the 'Data Context'.
2. If the data is missing, the response must admit "I don't have that data".
3. Do not allow hallucinations or made-up numbers.

Data Context:
{data}

Proposed Response:
{response}

Verified Response (rewrite if necessary, otherwise repeat):
"""

class Orchestrator(BaseAgent):
    """
    Main controller for the Agentic RAG system.
    """
    
    def __init__(self):
        super().__init__(name="Orchestrator")
        
        # Initialize Sub-Agents
        self.router = RouterAgent()
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
        
        # Fallback setup for Gemini
        if not (self.openai_client or self.mistral_client):
            self.provider = "gemini"
            api_key = os.getenv("GEMINI_API_KEY")
            if api_key:
                genai.configure(api_key=api_key)
                self.gemini_client = genai.GenerativeModel('gemini-2.0-flash-exp')

    # Known ticker mappings for entity extraction
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

    def _extract_tickers(self, query: str) -> List[str]:
        """Extract stock tickers from the query."""
        import re
        query_lower = query.lower()
        found_tickers = []
        
        for name, ticker in self.KNOWN_TICKERS.items():
            if name in query_lower and ticker not in found_tickers:
                found_tickers.append(ticker)
        
        # Also check for direct ticker mentions (e.g., "RELIANCE", "TCS")
        words = re.findall(r'\b[A-Z]{2,10}\b', query)
        for word in words:
            if word not in found_tickers and len(word) >= 2:
                if word in ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "SBIN", "ITC", "AXISBANK", "WIPRO"]:
                    found_tickers.append(word)
        
        return found_tickers[:5]

    def _quick_classify(self, query: str) -> str:
        """Fast keyword-based classification to skip LLM routing for obvious queries."""
        q = query.lower()
        
        # EXPLICIT TECHNICAL queries - user asks specifically for technical analysis
        if any(w in q for w in ['technical', 'rsi', 'macd', 'moving average', 'dma', 'chart', 'support', 'resistance', 'breakout', 'trend line']):
            return "technical_analysis"
        
        # FUNDAMENTAL / GENERAL queries - default for buy/sell/invest questions
        if any(w in q for w in ['buy', 'sell', 'invest', 'hold', 'should i', 'worth', 'good stock', 'undervalued', 'overvalued']):
            return "fundamental"
        
        if any(w in q for w in ['price', 'pe', 'market cap', 'valuation', 'trading at', 'current', 'eps', 'dividend']):
            return "market_data"
        if any(w in q for w in ['filing', 'annual', 'quarterly', 'result', 'earnings', 'report', 'con call', 'concall']):
            return "filings"
        if any(w in q for w in ['news', 'headline', 'announcement', 'update']):
            return "news"
        
        return "fundamental"  # Default to fundamental analysis

    def process(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Orchestrates the query handling flow:
        1. Ticker Extraction
        2. Fast keyword routing (skip LLM if possible)
        3. Semantic context enrichment
        4. Parallel Sub-agent execution
        5. Context Aggregation & Synthesis
        """
        self._log_activity(f"Processing query: {query}")
        
        # 0. Extract Tickers
        tickers = self._extract_tickers(query)
        context["formatted_tickers"] = tickers
        self._log_activity(f"Extracted tickers: {tickers}")
        
        # 1. Fast Route (skip LLM for obvious queries)
        primary_category = self._quick_classify(query)
        if primary_category:
            self._log_activity(f"Fast-routed to: {primary_category}")
        else:
            # Fall back to LLM routing
            route_result = self.router.process(query, context)
            primary_category = route_result.get("data", {}).get("category", "general")
        
        # 2. Semantic Context Enrichment (RAG)
        if EMBEDDINGS_AVAILABLE and tickers:
            try:
                semantic_ctx = build_semantic_context(query, tickers[0], top_k=3)
                if semantic_ctx:
                    context["semantic_news"] = semantic_ctx
                    self._log_activity(f"Added semantic context for {tickers[0]}")
            except Exception as e:
                self._log_activity(f"Semantic context failed: {e}")
        
        # 3. Parallel Execution of Sub-Agents (Optimized)
        agents = [self.market_agent, self.filings_agent, self.news_agent, self.technical_agent]
        aggregated_data = {}
        active_agents = []
        
        # Use ThreadPoolExecutor defined at module level if possible, or create new
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
                        active_agents.append(agent_name)
                        self._log_activity(f"{agent_name} contributed data (Score: {result.get('relevance_score', 0)})")
                except Exception as e:
                    self._log_activity(f"{agent_name} failed: {e}")

        # 3. Synthesize Final Answer
        # If no specialized agents found data, fallback to general chat
        if not aggregated_data and primary_category != "general":
             self._log_activity("No agents found data. Using general synthesis.")
        
        final_answer = self._synthesize_response(query, aggregated_data, primary_category)
        
        return {
            "response": final_answer,
            "data": aggregated_data,
            "category": primary_category,
            "agents_used": active_agents
        }

    def _synthesize_response(self, query: str, data: Dict[str, Any], category: str) -> str:
        """
        Generate natural language response using LLM and retrieved data.
        Adapts focus based on query category (technical vs fundamental).
        """
        if not (self.openai_client or self.gemini_client or self.mistral_client):
            return "Error: AI model not configured."
        
        # Build category-specific instructions
        if category == "technical_analysis":
            focus_instructions = """
FOCUS: Technical indicators (user explicitly asked for technicals)
Include RSI, moving averages, trend direction.

EXAMPLE:
"On the charts, Reliance is falling right now. 📉

RSI is at 17 — very oversold, meaning too much selling happened. Price is also below its 50-day and 200-day averages, so the trend is down.

Wait for now. If RSI goes above 30 or price crosses ₹1,450, that could be a good time to look again."
"""
        else:
            focus_instructions = """
FOCUS: Business and valuation (NOT technicals)
What does the company do? Is the price fair? Is it growing?
AVOID: RSI, DMA, charts, technical words.

EXAMPLE:
"You see Reliance everywhere — petrol pumps, Jio SIM cards, even the local store. It's India's biggest company.

At ₹1,404, the PE is 23x — a bit higher than other companies (sector PE is 13x). But Jio is growing fast and refining business gives steady cash. They also gave a 1:1 bonus and ₹5.5 dividend recently.

Good for long-term. Strong company, fair price. Not very cheap, but reliable. 💰"
"""

        system_prompt = f"""You are Analyez, a helpful AI for Indian stock market investors.

User asked: "{query}"

Data:
{json.dumps(data, indent=2, cls=DateEncoder)}

# HOW TO RESPOND

LANGUAGE: Simple English only. NOT Hindi. NOT Hinglish. Plain English.
- Short sentences. Everyday words.
- NO American slang (no "beast", "screaming bargain", "fireworks")  
- Use words like: good, strong, fair, expensive, cheap, growing, falling
- Use Indian examples (petrol pumps, Jio, local stores)

FORMAT:
- Plain text only, no ** bold **, no bullet points
- Use ₹ for prices
- One or two emojis max (📈📉💰)
- 80-100 words — short and clear

{focus_instructions}

Write like you're explaining to a friend who is new to stocks. Simple, helpful, friendly. ENGLISH ONLY.
"""
        
        try:
            if self.provider == "openai" and self.openai_client:
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "system", "content": system_prompt}]
                )
                initial_draft = response.choices[0].message.content
            elif self.provider == "mistral" and self.mistral_client:
                 response = self.mistral_client.chat.complete(
                    model="mistral-large-latest",
                    messages=[{"role": "user", "content": system_prompt}]
                )
                 initial_draft = response.choices[0].message.content
            elif self.gemini_client:
                response = self.gemini_client.generate_content(system_prompt)
                initial_draft = response.text
            else:
                 return "Error: configured LLM not available."
            
            return initial_draft
            
        except Exception as e:
            self._log_activity(f"Synthesis error: {e}")
            return "I encountered an error generating your analysis."
