"""
Inwezt AI Interface - Configuration
Central configuration for API keys, environment variables, and settings.
"""
import os
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

# Load .env file BEFORE reading environment variables
load_dotenv()

@dataclass
class Config:
    """Application configuration loaded from environment variables."""
    
    # LLM Configuration
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY")
    MISTRAL_API_KEY: Optional[str] = os.getenv("MISTRAL_API_KEY")
    
    # Default LLM Provider: "openai", "anthropic", "gemini", "mistral", "local"
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "mistral")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "mistral-large-latest")
    
    # Data API Keys
    RAPIDAPI_KEY: Optional[str] = os.getenv("RAPIDAPI_KEY")
    
    # AWS Configuration
    AWS_REGION: str = os.getenv("AWS_REGION", "ap-south-1")
    DYNAMODB_TABLE: str = os.getenv("DYNAMODB_TABLE", "StockDataCache")
    
    # Application Settings
    APP_NAME: str = "Inwezt AI"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    # Cache Settings
    CACHE_TTL_MINUTES: int = int(os.getenv("CACHE_TTL_MINUTES", "5"))
    
    # Rate Limiting
    MAX_REQUESTS_PER_MINUTE: int = int(os.getenv("MAX_REQUESTS_PER_MINUTE", "30"))
    
    # Security
    ALLOWED_ORIGINS: list[str] = field(default_factory=lambda: os.getenv("ALLOWED_ORIGINS", "*").split(","))
    
    # Monitoring
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")


# Global config instance
config = Config()


# System Prompts
AGENT_SYSTEM_PROMPT = """
You are Inwezt, an elite AI investment analyst for Indian stocks.

MOBILE-FIRST FORMAT (Keep responses SHORT for mobile screens):

**For simple questions (price, PE, single metric):**
Give a 2-3 line answer with the key number + brief context.

**For "should I buy" or analysis questions:**

**TL;DR:** [One sentence - bullish/bearish/neutral stance with key reason]

**Key Facts:**
• Price: ₹X,XXX (X% today)
• PE: Xx vs Sector Xx  
• 52W: ₹X,XXX - ₹X,XXX
[Max 4-5 bullet points]

**Outlook:** [2-3 sentences on what to watch]

*Source: NSE*

RULES:
- Never say "data not available" - skip that field
- **Historical Data Rule:** All data provided for years up to the "Current Date" is FACTUAL HISTORY. Never label it as "Projected".
- Never mention market open/closed status
- Never mention circuit status unless actually hitting limits
- Source line ONLY at the very end, once
- Use ₹ symbol and L Cr for large numbers
- Be direct and specific with numbers
- Max 150 words for simple questions, 250 for analysis
"""

TAX_CONTEXT_PROMPT = """
INDIAN CAPITAL GAINS TAX (Budget 2024):
- LTCG (>1 year): 12.5% on gains above ₹1.25 Lakh/year
- STCG (≤1 year): 20% on all gains
- Mention tax impact when discussing profits or selling.
"""

