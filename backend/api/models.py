"""
Analyez AI Interface - Data Models
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

class QueryRequest(BaseModel):
    """User query request."""
    query: str = Field(..., min_length=1, max_length=2000, description="User's question")
    session_id: Optional[str] = Field(None, description="Optional session ID for context")
    include_tax_context: bool = Field(True, description="Include LTCG/STCG context")
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "Should I buy Reliance at current levels?",
                "session_id": "user-123",
                "include_tax_context": True
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


class QueryResponse(BaseModel):
    """Response to user query."""
    status: ResponseStatus
    response: str = Field(..., description="AI-generated response")
    intent: QueryIntent = QueryIntent.UNKNOWN
    data_used: Optional[Any] = Field(None, description="Detailed data fetched for this query")
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
