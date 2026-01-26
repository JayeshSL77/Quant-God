"""
Inwezt V3 - Financial Document Summarizer
Intelligently summarizes large concall transcripts and annual reports using Mistral AI.
"""

import os
import logging
from typing import Optional
from mistralai import Mistral

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

    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        logger.error("MISTRAL_API_KEY not found")
        return "Error: Summarization failed due to missing API key."

    client = Mistral(api_key=api_key)
    model = os.getenv("LLM_MODEL", "mistral-large-latest")

    # Simple truncation for now to stay within context limits
    # Most models handle 32k-128k, but let's be safe and target ~20k chars
    max_chars = 60000 
    truncated_content = content[:max_chars]
    if len(content) > max_chars:
        logger.warning(f"Content truncated from {len(content)} to {max_chars} chars for summarization")

    try:
        response = client.chat.complete(
            model=model,
            messages=[
                {"role": "user", "content": FINANCIAL_SUMMARY_PROMPT.format(content=truncated_content)}
            ],
            temperature=0.2 # Lower temperature for factual accuracy
        )
        
        summary = response.choices[0].message.content
        return summary
    except Exception as e:
        logger.error(f"Summarization error: {e}")
        return f"Error during summarization: {str(e)}"

if __name__ == "__main__":
    # Quick test
    test_content = "This is a test transcript. Profit grew by 20%. Management guides for 15% margin next year."
    print(summarize_document(test_content))
