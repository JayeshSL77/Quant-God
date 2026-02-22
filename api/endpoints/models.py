"""
Inwezt AI Interface - Data Models
Pydantic models for request/response validation.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# =============================================================================
# ENUMS
# =============================================================================

class QueryIntent(str, Enum):
    """Detected intent of user query."""
    STOCK_ANALYSIS = "stock_analysis"
    PRICE_CHECK = "price_check"
    PORTFOLIO_ADVICE = "portfolio_advice"
    TAX_CALCULATION = "tax_calculation"
    REGULATORY_INFO = "regulatory_info"
    GENERAL_MARKET = "general_market"
    UNKNOWN = "unknown"


class ResponseStatus(str, Enum):
    """Status of API response."""
    SUCCESS = "success"
    ERROR = "error"
    BLOCKED = "blocked"  # Query blocked by guardrails


# =============================================================================
# REQUEST MODELS
# =============================================================================

class ConversationMessage(BaseModel):
    """A single message in conversation history for context."""
    role: str = Field(..., description="Either 'user' or 'bot'")
    content: str = Field(..., description="Message content")


class AnalysisMode(str, Enum):
    """Analysis depth mode for responses."""
    SUMMARY = "summary"  # Thesis + final view only
    BUSINESS = "business"  # Excludes valuation context
    DEEP_RESEARCH = "deep_research"  # Full comprehensive analysis


class QueryRequest(BaseModel):
    """User query request."""
    query: str = Field(..., min_length=1, max_length=2000, description="User's question")
    session_id: Optional[str] = Field(None, description="Optional session ID for context")
    include_tax_context: bool = Field(True, description="Include LTCG/STCG context")
    selected_sources: Optional[List[str]] = Field(None, description="List of sources to use (e.g., ['market_data', 'filings', 'news', 'technical'])")
    conversation_history: Optional[List[ConversationMessage]] = Field(None, description="Recent conversation messages for context (P2)")
    analysis_mode: AnalysisMode = Field(AnalysisMode.DEEP_RESEARCH, description="Analysis depth: summary, business, or deep_research")
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "Should I buy Reliance at current levels?",
                "session_id": "user-123",
                "include_tax_context": True,
                "selected_sources": ["market_data", "filings"],
                "analysis_mode": "deep_research",
                "conversation_history": [
                    {"role": "user", "content": "Tell me about TCS"},
                    {"role": "bot", "content": "TCS is trading at ₹3,500..."}
                ]
            }
        }


class TaxCalculationRequest(BaseModel):
    """Request for tax calculation."""
    buy_price: float = Field(..., gt=0)
    sell_price: float = Field(..., gt=0)
    quantity: int = Field(..., gt=0)
    holding_days: int = Field(..., ge=0)
    
    class Config:
        json_schema_extra = {
            "example": {
                "buy_price": 100.0,
                "sell_price": 150.0,
                "quantity": 1000,
                "holding_days": 400
            }
        }


# =============================================================================
# RESPONSE MODELS
# =============================================================================

class StockData(BaseModel):
    """Stock data returned from fetch_indian_data."""
    ticker: str
    exchange: str = "NSE"
    source: str = "unknown"
    
    # Price Data
    price: Optional[float] = None
    price_formatted: Optional[str] = None
    change_pct: Optional[float] = None
    ytd_change: Optional[float] = None
    week_change: Optional[float] = None
    
    # Valuation
    pe_ratio: Optional[float] = None
    sector_pe: Optional[float] = None
    market_cap: Optional[float] = None
    market_cap_formatted: Optional[str] = None
    
    # Fundamentals
    eps_ttm: Optional[float] = None
    book_value: Optional[float] = None
    dividend_per_share: Optional[float] = None
    revenue_per_share: Optional[float] = None
    revenue_growth: Optional[float] = None
    profit_growth: Optional[float] = None
    net_margin: Optional[float] = None
    roe: Optional[float] = None
    
    # Technical
    high_52w: Optional[float] = None
    low_52w: Optional[float] = None
    beta: Optional[float] = None
    
    # Analyst
    analyst_score: Optional[float] = None  # 0-100
    
    # News (top 5)
    news: Optional[List[Dict[str, Any]]] = None
    
    # Peers
    peers: Optional[List[Dict[str, Any]]] = None
    
    # Legacy fields (for backwards compatibility)
    volume: Optional[int] = None
    delivery_pct: Optional[float] = None
    circuit_status: str = "NORMAL"
    circuit_warning: Optional[str] = None
    market_status: str = "UNKNOWN"
    market_message: Optional[str] = None
    last_updated: Optional[str] = None


class ChartData(BaseModel):
    """Chart data returned from visual RAG."""
    base64: str = Field(..., description="Base64 encoded PNG image")
    type: str = Field(..., description="Chart type: revenue_trend, margin_trend, etc.")
    title: str = Field(..., description="Chart title")
    symbol: str = Field(..., description="Stock symbol")


class QueryResponse(BaseModel):
    """Response to user query."""
    status: ResponseStatus
    response: str = Field(..., description="AI-generated response")
    intent: QueryIntent = QueryIntent.UNKNOWN
    data_used: Optional[Any] = Field(None, description="Detailed data fetched for this query")
    chart: Optional[ChartData] = Field(None, description="Optional visual chart for the response")
    processing_time_ms: int = 0
    session_id: Optional[str] = None
    disclaimer: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "response": "Reliance is trading at ₹2,450 with PE of 25.4...",
                "intent": "stock_analysis",
                "processing_time_ms": 1250,
                "disclaimer": "This is informational analysis, not investment advice."
            }
        }


class TaxCalculationResponse(BaseModel):
    """Response for tax calculation."""
    gross_gain: float
    gross_gain_formatted: str
    tax_type: str
    tax_rate: str
    tax_amount: float
    tax_amount_formatted: str
    net_gain: float
    net_gain_formatted: str
    holding_period: str


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "healthy"
    version: str
    timestamp: str
    market_status: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    """Error response."""
    status: ResponseStatus = ResponseStatus.ERROR
    error: str
    error_code: Optional[str] = None
    details: Optional[str] = None


# =============================================================================
# WAITLIST MODELS (Agentic Assetz)
# =============================================================================

class WaitlistSignupRequest(BaseModel):
    """Waitlist signup request."""
    email: str = Field(..., min_length=5, max_length=255, description="Email address")
    phone: Optional[str] = Field(None, max_length=20, description="Phone number (optional)")
    market: str = Field(..., pattern="^(india|us)$", description="Market: 'india' or 'us'")
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "investor@example.com",
                "phone": "+919876543210",
                "market": "india"
            }
        }


class WaitlistSignupResponse(BaseModel):
    """Waitlist signup response."""
    success: bool
    position: Optional[int] = None
    already_registered: bool = False
    message: str = "Successfully joined the waitlist!"
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "position": 42,
                "already_registered": False,
                "message": "Successfully joined the waitlist!"
            }
        }

