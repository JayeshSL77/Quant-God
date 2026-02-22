"""
Metric Extraction Agent
Extracts key financial metrics from annual reports for Generated Assets.
Works for both India (Nifty 500) and US (S&P 500).
"""

import os
import re
import json
import logging
from typing import Dict, List, Optional, Any
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MetricExtractor")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


class MetricExtractor:
    """
    Extracts structured financial metrics from annual report text.
    Uses GPT-4o-mini for efficient, cost-effective extraction.
    """
    
    EXTRACTION_PROMPT = """You are a financial analyst. Extract the following metrics from this annual report excerpt.
Return ONLY valid JSON, no explanation.

Metrics to extract:
- revenue (in millions, local currency)
- net_income (in millions)
- operating_cash_flow (in millions)
- eps (earnings per share)
- total_assets (in millions)
- total_debt (in millions)
- shareholders_equity (in millions)
- revenue_growth_yoy (percentage, e.g., 15.2 for 15.2%)
- profit_margin (percentage)
- roe (return on equity, percentage)
- roic (return on invested capital, percentage)

If a metric cannot be found, use null.

Annual Report Excerpt:
{text}

Return JSON only:"""

    THEME_EXTRACTION_PROMPT = """Analyze this annual report excerpt and identify business themes/exposures.
Score each theme 0-100 based on how central it is to the company's strategy.
Return ONLY valid JSON.

Themes to check:
- ai_exposure (AI, machine learning, generative AI)
- cloud_computing (cloud services, SaaS)
- ev_exposure (electric vehicles, batteries)
- renewable_energy (solar, wind, clean energy)
- digital_transformation (digitization, automation)
- international_expansion (global growth)
- ecommerce (online sales, digital commerce)
- healthcare_innovation (biotech, medical devices)

Annual Report Excerpt:
{text}

Return JSON with theme scores (0-100):"""

    def __init__(self):
        self.client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
    
    def extract_metrics(self, text: str, max_chars: int = 15000) -> Dict[str, Any]:
        """Extract financial metrics from annual report text."""
        if not self.client:
            logger.error("OpenAI client not available")
            return {}
        
        # Truncate to relevant portion (usually MD&A and financial highlights)
        text = text[:max_chars]
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You extract financial data from reports. Return only valid JSON."},
                    {"role": "user", "content": self.EXTRACTION_PROMPT.format(text=text)}
                ],
                temperature=0.1,
                max_tokens=500
            )
            
            content = response.choices[0].message.content.strip()
            # Clean up potential markdown formatting
            if content.startswith("```"):
                content = re.sub(r'^```json?\n?', '', content)
                content = re.sub(r'\n?```$', '', content)
            
            return json.loads(content)
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            return {}
        except Exception as e:
            logger.error(f"Extraction error: {e}")
            return {}
    
    def extract_themes(self, text: str, max_chars: int = 20000) -> Dict[str, int]:
        """Extract thematic exposures (AI, Cloud, EV, etc.) from annual report."""
        if not self.client:
            return {}
        
        text = text[:max_chars]
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You analyze business themes in reports. Return only valid JSON."},
                    {"role": "user", "content": self.THEME_EXTRACTION_PROMPT.format(text=text)}
                ],
                temperature=0.1,
                max_tokens=300
            )
            
            content = response.choices[0].message.content.strip()
            if content.startswith("```"):
                content = re.sub(r'^```json?\n?', '', content)
                content = re.sub(r'\n?```$', '', content)
            
            return json.loads(content)
            
        except Exception as e:
            logger.error(f"Theme extraction error: {e}")
            return {}
    
    def compute_derived_metrics(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Compute additional metrics from extracted data."""
        derived = {}
        
        try:
            # ROE if we have net_income and equity
            if metrics.get('net_income') and metrics.get('shareholders_equity'):
                derived['computed_roe'] = round(
                    (metrics['net_income'] / metrics['shareholders_equity']) * 100, 2
                )
            
            # Debt to equity
            if metrics.get('total_debt') and metrics.get('shareholders_equity'):
                derived['debt_to_equity'] = round(
                    metrics['total_debt'] / metrics['shareholders_equity'], 2
                )
            
            # Cash flow to net income ratio
            if metrics.get('operating_cash_flow') and metrics.get('net_income'):
                derived['cash_conversion'] = round(
                    (metrics['operating_cash_flow'] / metrics['net_income']) * 100, 2
                )
        except (ZeroDivisionError, TypeError):
            pass
        
        return {**metrics, **derived}


if __name__ == "__main__":
    # Test with sample text
    extractor = MetricExtractor()
    
    sample_text = """
    Fiscal Year 2024 Highlights:
    - Total Revenue: $394.3 billion, up 8% year-over-year
    - Net Income: $97.0 billion, representing a profit margin of 24.6%
    - Operating Cash Flow: $110.5 billion
    - Earnings Per Share (diluted): $6.13
    - Return on Equity: 147%
    - Total Assets: $352.6 billion
    - Total Debt: $111.1 billion
    - Shareholders' Equity: $66.0 billion
    
    Strategic Focus Areas:
    - Continued investment in artificial intelligence and machine learning
    - Expansion of Apple Intelligence features across all product lines
    - Growing services revenue through cloud-based offerings
    - Commitment to carbon neutrality and renewable energy
    """
    
    print("Testing Metric Extraction...")
    metrics = extractor.extract_metrics(sample_text)
    print(f"Extracted metrics: {json.dumps(metrics, indent=2)}")
    
    print("\nTesting Theme Extraction...")
    themes = extractor.extract_themes(sample_text)
    print(f"Extracted themes: {json.dumps(themes, indent=2)}")
