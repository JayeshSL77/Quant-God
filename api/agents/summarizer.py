"""
Inwezt V3 - Financial Document Summarizer
Intelligently summarizes large concall transcripts and annual reports using Mistral AI.
"""

import os
import logging
from typing import Optional
from mistralai import Mistral
import google.generativeai as genai
import time
import random
import functools

# Retry Decorator (Duplicated from Orchestrator for standalone robustness)
def retry_with_backoff(retries=5, initial_delay=4, backoff_factor=2):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None
            for i in range(retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    # Check for rate limit errors (429)
                    error_str = str(e).lower()
                    if "429" in error_str or "rate limit" in error_str:
                         if i < retries:
                             time.sleep(delay + random.uniform(0, 0.5))
                             delay *= backoff_factor
                             continue
                    raise e
            raise last_exception
        return wrapper
    return decorator

logger = logging.getLogger("Summarizer")

# SUMMARIZATION PROMPT
FINANCIAL_SUMMARY_PROMPT = """
You are a senior equity research analyst specializing in Indian markets. 
Your task is to provide a high-fidelity, nuanced summary of the following financial document (Concall Transcript or Annual Report).

FOCUS ON EXTRACTING THE FOLLOWING (IF PRESENT):
1. REVENUE & MARGIN GUIDANCE: Specific numbers, percentage ranges, and management's confidence level.
2. STRATEGIC PIVOTS & CAPEX: New business lines, manufacturing expansions, or significant capital allocation changes.
3. SEGMENT PERFORMANCE: Performance across different business verticals or geographies.
4. RISKS & TAILWINDS: Specific industry headwinds, regulatory changes, or competitive pressures mentioned.
5. Q&A HIGHLIGHTS (for concalls): The most critical questions from analysts and management's specific rebuttals or clarifications.

RULES:
- Maintain institutional tone.
- Do NOT round numbers; use the exact figures provided.
- If data is missing for a section, skip it.
- Keep the summary between 400-600 words for maximum context efficiency.
- Format with clear section headers in ALL CAPS.

DOCUMENT CONTENT:
{content}

---
NUANCED FINANCIAL SUMMARY:
"""

def summarize_document(content: str, doc_type: str = "Document") -> str:
    """
    Summarize a large financial document using Mistral AI.
    Handles chunking if necessary (simplistic implementation for now).
    """
    if not content or len(content.strip()) < 100:
        return content

    # Pre-truncation
    max_chars = 60000 
    truncated_content = content[:max_chars]
    if len(content) > max_chars:
        logger.warning(f"Content truncated from {len(content)} to {max_chars} chars for summarization")

    provider = os.getenv("LLM_PROVIDER", "mistral")
    
    # === MISTRAL ===
    if provider == "mistral":
        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
             return "Error: MISTRAL_API_KEY missing."
        
        client = Mistral(api_key=api_key)
        model = os.getenv("LLM_MODEL", "mistral-large-latest")

        try:
            @retry_with_backoff(retries=5, initial_delay=4)
            def generate_summary():
                return client.chat.complete(
                    model=model,
                    messages=[{"role": "user", "content": FINANCIAL_SUMMARY_PROMPT.format(content=truncated_content)}],
                    temperature=0.2
                )
            response = generate_summary()
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Mistral Summarization error: {e}")
            return f"Error during summarization: {str(e)}"

    # === GEMINI ===
    elif provider == "gemini":
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
             return "Error: GEMINI_API_KEY missing."
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(os.getenv("LLM_MODEL", "gemini-2.0-flash-exp"))
        
        try:
            @retry_with_backoff(retries=5, initial_delay=4)
            def generate_summary_gemini():
                return model.generate_content(
                    FINANCIAL_SUMMARY_PROMPT.format(content=truncated_content),
                    generation_config=genai.types.GenerationConfig(temperature=0.2)
                )
            response = generate_summary_gemini()
            return response.text
        except Exception as e:
            logger.error(f"Gemini Summarization error: {e}")
            return f"Error during summarization: {str(e)}"
            
    return "Error: Unsupported LLM_PROVIDER"

if __name__ == "__main__":
    # Quick test
    test_content = "This is a test transcript. Profit grew by 20%. Management guides for 15% margin next year."
    print(summarize_document(test_content))
