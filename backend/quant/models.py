from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

class StockPrice(BaseModel):
    """
    Standardized model for a stock price record.
    Using Pydantic for validation to ensure bad data never hits the DB.
    """
    symbol: str = Field(..., description="Stock Ticker Symbol (e.g., RELIANCE.NS)")
    price: float = Field(..., description="Current trading price")
    currency: str = Field("INR", description="Currency code")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Time of data fetch")
    
    # Optional fields that might not always be available
    daily_change: Optional[float] = None
    daily_change_percent: Optional[float] = None
    volume: Optional[int] = None
    
    class Config:
        frozen = True # Makes instances immutable
