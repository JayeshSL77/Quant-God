"""
Inwezt AI Interface - Agent Orchestrator
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
from api.endpoints.config import config, AGENT_SYSTEM_PROMPT, TAX_CONTEXT_PROMPT
from api.endpoints.models import QueryIntent, StockData
from api.core.utils.guardrails import ScopeGuardrail, ResponseGuardrail, ResponseFactChecker
from api.core.utils.indian_utils import (
    format_indian_number,
    IndianTaxCalculator,
    is_indian_market_open,
    get_circuit_warning
)
from api.core.utils.fetch_indian_data import fetch_indian_data

# User Personalization Engine
try:
    from api.endpoints.personalization import personalization_engine, UserProfile
    PERSONALIZATION_AVAILABLE = True
except ImportError:
    PERSONALIZATION_AVAILABLE = False
    personalization_engine = None

# Database integration for RAG
try:
    from api.database.database import (
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
logger = logging.getLogger("InweztAgent")



from api.agents.orchestrator import OrchestratorV2

class InweztAgent:
    """
    Wrapper for the new Agentic RAG Orchestrator.
    Maintains backward compatibility for main.py.
    Now includes self-learning personalization.
    """
    
    def __init__(self):
        self.orchestrator = OrchestratorV2()  # Switched to V2 for institutional-grade responses
        # Initialize guardrails
        self.scope_guard = ScopeGuardrail()
        self.response_guard = ResponseGuardrail()
        self.fact_checker = ResponseFactChecker()
        # Personalization engine
        self.personalization = personalization_engine if PERSONALIZATION_AVAILABLE else None
        if self.personalization:
            logger.info("User personalization engine initialized")
        
    @property
    def llm_client(self):
        """Pass-through for any direct access."""
        return self.orchestrator.openai_client or self.orchestrator.gemini_client or self.orchestrator.mistral_client
    
    def _detect_follow_up(self, query: str) -> bool:
        """Detect if query is a follow-up to previous conversation."""
        follow_up_patterns = [
            r'^(what about|how about|and|also|its|their|the same)',
            r'^(tell me more|more on|expand on|elaborate)',
            r'^(compare|vs|versus)(?!\s+\w+\s+(and|vs|versus))',  # "compare" without new ticker
            r'^(why|when|how)(?!\s+(is|are|does|do)\s+\w+)'  # Questions without explicit subject
        ]
        query_lower = query.lower().strip()
        return any(re.match(pattern, query_lower) for pattern in follow_up_patterns)
    
    def _extract_ticker_from_history(self, history: List[Dict]) -> Optional[str]:
        """Extract the most recent ticker mentioned in conversation history."""
        # Known ticker pattern
        ticker_pattern = r'\b([A-Z]{2,10}(?:BANK)?)\b'
        
        for msg in reversed(history):
            if msg.get('role') == 'user':
                matches = re.findall(ticker_pattern, msg.get('content', '').upper())
                # Filter to known tickers
                for match in matches:
                    if match in self.orchestrator.KNOWN_TICKERS.values():
                        return match
        return None
    
    def process_query(self, query: str, include_tax_context: bool = True, 
                      selected_sources: Optional[List[str]] = None,
                      conversation_history: Optional[List[Dict]] = None,
                      user_id: Optional[str] = None,
                      analysis_mode: str = "deep_research") -> Dict:
        """
        Delegates processing to the Multi-Agent Orchestrator.
        Applies guardrails for security and compliance.
        P2: Now supports conversation context for follow-up queries.
        """
        start_time = time.time()
        
        # ========== P2: CONVERSATION CONTEXT ==========
        context_prefix = ""
        if conversation_history and len(conversation_history) > 0:
            # Check if this is a follow-up query
            if self._detect_follow_up(query):
                inferred_ticker = self._extract_ticker_from_history(conversation_history)
                if inferred_ticker:
                    logger.info(f"[P2] Detected follow-up query, inferred ticker: {inferred_ticker}")
                    # Augment query with context
                    query = f"[Context: Discussing {inferred_ticker}] {query}"
            
            # Build conversation context for LLM
            recent_msgs = conversation_history[-3:]  # Last 3 messages
            context_lines = []
            for msg in recent_msgs:
                role = "User" if msg.get('role') == 'user' else "AI"
                content = msg.get('content', '')[:150]  # Truncate for efficiency
                context_lines.append(f"{role}: {content}")
            context_prefix = "Previous conversation:\n" + "\n".join(context_lines) + "\n\n"
            logger.info(f"[P2] Added conversation context with {len(recent_msgs)} messages")
        
        # ========== PERSONALIZATION: Learn from user ==========
        user_context = ""
        user_profile = None
        if self.personalization and user_id:
            user_profile = self.personalization.get_or_create_profile(user_id)
            user_context = self.personalization.generate_personalized_context(user_profile)
            if user_context:
                logger.info(f"[PERSONALIZATION] Loaded profile for user (queries: {user_profile.query_count})")
        
        # ========== PRE-CHECK: Scope Guardrail ==========
        # DEMO MODE: Intercept specific questions for video recording
        query_lower = query.lower().strip()
        
        # ========== MAIN PROCESSING ==========
        # Check Knowledge Base for Inwezt-specific queries
        if "inwezt" in query_lower:
            yield {"status": "thinking", "message": "Searching internal knowledge base..."}
            time.sleep(1) # Visual pause
            knowledge_items = get_knowledge(query)
            
            if knowledge_items:
                yield {"status": "thinking", "message": "Found relevant information about Inwezt."}
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
        context = {
            "include_tax": include_tax_context,
            "selected_sources": selected_sources,
            "conversation_context": context_prefix if context_prefix else None,  # P2: Pass to orchestrator
            "user_context": user_context if user_context else None,  # PERSONALIZATION: Inject user persona
            "analysis_mode": analysis_mode  # Analysis depth mode: summary, business, deep_research
        }

        
        try:
            # The orchestrator is now a generator that yields thinking states, chunks, and final result
            final_result = None
            for event in self.orchestrator.process(query, context):
                if event.get("status") == "thinking":
                    yield event
                elif event.get("status") == "success":
                    if event.get("is_partial"):
                        # Forward partial chunk for real-time streaming
                        yield {
                            "status": "success",
                            "response": event.get("response"),
                            "chunk": event.get("chunk"),
                            "is_partial": True
                        }
                    else:
                        final_result = event
            
            if not final_result:
                raise Exception("Orchestrator failed to return a final result.")
                
            response_text = final_result.get("response", "")
            
            # ========== POST-CHECK: Response Sanitization ==========
            # Only sanitize at the end for performance, or we can sanitize chunks
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
                "data_used": final_result.get("data") or final_result.get("data_used"),
                "chart": final_result.get("chart"),
                "comparison": final_result.get("comparison"),
                "processing_time_ms": processing_time,
                "disclaimer": "AI-generated. Not investment advice. Verify before acting.",
                "is_partial": False
            }
            
            # ========== PERSONALIZATION: Learn from this interaction ==========
            if self.personalization and user_id:
                self.personalization.learn_from_interaction(
                    user_id=user_id,
                    query=query,
                    response=response_text,
                    conversation_history=conversation_history
                )
                logger.info(f"[PERSONALIZATION] Updated user profile after interaction")
        except Exception as e:
            logger.error(f"Agent processing error: {str(e)}", exc_info=True)
            yield {
                "status": "error",
                "response": f"I encountered an error while analyzing your request: {str(e)}",
                "intent": "unknown",
                "processing_time_ms": int((time.time() - start_time) * 1000)
            }

# Singleton instance
agent = InweztAgent()
