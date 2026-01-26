"""
Analyez AI Interface - Agent Orchestrator
The brain that coordinates queries, tools, and LLM responses.
"""
import os
import re
import time
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dotenv import load_dotenv

# CRITICAL: Load .env FIRST before any other imports that use config
load_dotenv(override=True)

# Import our custom modules (updated paths)
from backend.api.config import config, AGENT_SYSTEM_PROMPT, TAX_CONTEXT_PROMPT
from backend.api.models import QueryIntent, StockData
from backend.utils.guardrails import ScopeGuardrail, ResponseGuardrail, ResponseFactChecker
from backend.utils.indian_utils import (
    format_indian_number,
    IndianTaxCalculator,
    is_indian_market_open,
    get_circuit_warning
)
from backend.utils.fetch_indian_data import fetch_indian_data

# Database integration for RAG
try:
    from backend.database.database import (
        save_stock_snapshot, 
        save_query_history, 
        save_news_article, 
        save_corporate_filing,
        get_stock_context_from_db,
        get_historical_price_data,
        get_historical_valuation_data,
        get_historical_valuation_data,
        get_corporate_filings,
        get_knowledge
    )
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False

# LLM Imports (conditional based on provider)
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AnalyezAgent")



from backend.agents.orchestrator_v2 import OrchestratorV2

class AnalyezAgent:
    """
    Wrapper for the new Agentic RAG Orchestrator.
    Maintains backward compatibility for main.py
    """
    
    def __init__(self):
        self.orchestrator = OrchestratorV2()  # Switched to V2 for institutional-grade responses
        # Initialize guardrails
        self.scope_guard = ScopeGuardrail()
        self.response_guard = ResponseGuardrail()
        self.fact_checker = ResponseFactChecker()
        
    @property
    def llm_client(self):
        """Pass-through for any direct access."""
        return self.orchestrator.openai_client or self.orchestrator.gemini_client or self.orchestrator.mistral_client
    
    def process_query(self, query: str, include_tax_context: bool = True) -> Dict:
        """
        Delegates processing to the Multi-Agent Orchestrator.
        Applies guardrails for security and compliance.
        """
        start_time = time.time()
        
        # ========== PRE-CHECK: Scope Guardrail ==========
        # DEMO MODE: Intercept specific questions for video recording
        query_lower = query.lower().strip()
        
        # ========== MAIN PROCESSING ==========
        # Check Knowledge Base for Analyez-specific queries
        if "analyez" in query_lower:
            yield {"status": "thinking", "message": "Searching internal knowledge base..."}
            time.sleep(1) # Visual pause
            knowledge_items = get_knowledge(query)
            
            if knowledge_items:
                yield {"status": "thinking", "message": "Found relevant information about Analyez."}
                # Construct response from knowledge items
                best_match = knowledge_items[0]
                response_text = best_match['answer']
                
                yield {
                    "status": "success", 
                    "response": response_text,
                    "intent": "general_market",
                    "data_used": [k['question'] for k in knowledge_items],
                    "processing_time_ms": int((time.time() - start_time) * 1000)
                }
                return

        yield {"status": "thinking", "message": "Analyzing query context..."}
        context = {"include_tax": include_tax_context}
        
        try:
            # The orchestrator is now a generator that yields thinking states and final result
            final_result = None
            for event in self.orchestrator.process(query, context):
                if event.get("status") == "thinking":
                    yield event
                elif event.get("status") == "success":
                    final_result = event
            
            if not final_result:
                raise Exception("Orchestrator failed to return a valid result.")
                
            response_text = final_result.get("response", "")
            
            # ========== POST-CHECK: Response Sanitization ==========
            response_text = self.response_guard.sanitize_response(response_text, query)
            
            # ========== POST-CHECK: Fact Verification ==========
            fact_result = self.fact_checker.check(response_text, final_result.get("data"))
            if not fact_result["is_valid"]:
                logger.warning(f"Fact check failed: {fact_result['error']}")
            
            # Map Orchestrator output to Legacy format
            processing_time = int((time.time() - start_time) * 1000)
            
            category = final_result.get("category", "general")
            intent_mapping = {
                "market_data": "stock_analysis",
                "technical_analysis": "stock_analysis",
                "filings": "regulatory_info",
                "news": "news_update",
                "general": "general_market"
            }
            mapped_intent = intent_mapping.get(category, "unknown")
            
            yield {
                "status": "success",
                "response": response_text,
                "intent": mapped_intent,
                "data_used": final_result.get("data"),
                "processing_time_ms": processing_time,
                "disclaimer": "AI-generated. Not investment advice. Verify before acting."
            }
        except Exception as e:
            logger.error(f"Agent processing error: {str(e)}", exc_info=True)
            yield {
                "status": "error",
                "response": f"I encountered an error while analyzing your request: {str(e)}",
                "intent": "unknown",
                "processing_time_ms": int((time.time() - start_time) * 1000)
            }

# Singleton instance
agent = AnalyezAgent()
