"""
Analyez AI Interface - FastAPI Application
Main entry point for the AI Interface API.
"""
import os
import time
from datetime import datetime, date
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
import uvicorn
import numpy as np
from decimal import Decimal

# Import our modules (updated paths)
from backend.api.config import config
from backend.api.models import (
    QueryRequest, QueryResponse, TaxCalculationRequest, TaxCalculationResponse,
    HealthResponse, ErrorResponse, ResponseStatus
)
from backend.api.agent import agent
from backend.utils.indian_utils import IndianTaxCalculator, is_indian_market_open

# A/B Testing for V2 experimental orchestrator
from backend.api.ab_test import router as ab_test_router

# =============================================================================
# APP INITIALIZATION
# =============================================================================

def sanitize_data(data):
    """Recursively convert numpy types to native Python types for JSON serialization."""
    if isinstance(data, dict):
        return {k: sanitize_data(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_data(x) for x in data]
    elif isinstance(data, (np.integer, np.floating)):
        return data.item()
    elif isinstance(data, np.ndarray):
        return sanitize_data(data.tolist())
    elif isinstance(data, np.bool_):
        return bool(data)
    elif isinstance(data, (datetime, date)):
        return data.isoformat()
    elif isinstance(data, Decimal):
        return float(data)
    return data

app = FastAPI(
    title=config.APP_NAME,
    description="AI-powered financial assistant for Indian Stock Market",
    version=config.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register A/B test router
app.include_router(ab_test_router, prefix="/api/v2", tags=["A/B Testing"])


# =============================================================================
# API ENDPOINTS
# =============================================================================

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main chat interface or API status."""
    static_path = "static/index.html"
    if os.path.exists(static_path):
        return FileResponse(static_path)
    
    return HTMLResponse(content=f"""
    <html>
        <head>
            <title>{config.APP_NAME}</title>
            <style>
                body {{ font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background: #0f172a; color: white; }}
                .container {{ text-align: center; padding: 2rem; border-radius: 1rem; background: #1e293b; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1); }}
                a {{ color: #38bdf8; text-decoration: none; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🚀 {config.APP_NAME} Backend</h1>
                <p>Status: Healthy | Version: {config.APP_VERSION}</p>
                <p>API documentation: <a href="/docs">/docs</a></p>
                <p style="font-size: 0.8rem; color: #94a3b8;">Frontend assets not detected in /static</p>
            </div>
        </body>
    </html>
    """)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    market_info = is_indian_market_open()
    return HealthResponse(
        status="healthy",
        version=config.APP_VERSION,
        timestamp=datetime.now().isoformat(),
        market_status=market_info
    )


@app.post("/api/query", response_model=QueryResponse)
async def process_query(request: QueryRequest):
    """
    Main endpoint: Process a user query about Indian stocks (Synchronous).
    Consumes the agent generator and returns the final result.
    """
    try:
        final_result = None
        # Iterate through the generator to get the final success/error yield
        for event in agent.process_query(
            query=request.query,
            include_tax_context=request.include_tax_context
        ):
            if event.get("status") in ["success", "error"]:
                final_result = event
        
        if not final_result:
            raise HTTPException(status_code=500, detail="Agent failed to produce a final response")

        if final_result["status"] == "error":
            raise HTTPException(status_code=500, detail=final_result["response"])
        
        return QueryResponse(
            status=ResponseStatus.SUCCESS,
            response=final_result["response"],
            intent=final_result["intent"],
            data_used=sanitize_data(final_result.get("data_used")),
            processing_time_ms=final_result["processing_time_ms"],
            session_id=request.session_id,
            disclaimer=final_result.get("disclaimer")
        )
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.getLogger("uvicorn.error").error(f"Error in process_query: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred processing your request")


@app.post("/api/chat/stream")
async def chat_stream(request: QueryRequest):
    """
    Streaming endpoint: Process a user query and stream "thinking" steps and final response.
    """
    from fastapi.responses import StreamingResponse
    import json

    def event_generator():
        """Synchronous generator that yields agent events as NDJSON."""
        try:
            for event in agent.process_query(
                query=request.query,
                include_tax_context=request.include_tax_context
            ):
                yield json.dumps(sanitize_data(event)) + "\n"
        except Exception as e:
            import logging
            logging.getLogger("uvicorn.error").error(f"Streaming error: {str(e)}", exc_info=True)
            yield json.dumps({"status": "error", "response": str(e)}) + "\n"

    return StreamingResponse(
        event_generator(), 
        media_type="application/x-ndjson",
        headers={
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "application/x-ndjson"
        }
    )


@app.post("/api/tax/calculate", response_model=TaxCalculationResponse)
async def calculate_tax(request: TaxCalculationRequest):
    """
    Calculate capital gains tax for a stock transaction.
    """
    result = IndianTaxCalculator.calculate_tax(
        buy_price=request.buy_price,
        sell_price=request.sell_price,
        quantity=request.quantity,
        holding_days=request.holding_days
    )
    
    return TaxCalculationResponse(**result)


@app.get("/api/market/status")
async def market_status():
    """Get current market status."""
    return is_indian_market_open()


# =============================================================================
# STATIC FILES (Mount after routes)
# =============================================================================

try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except:
    pass  # Static directory may not exist yet


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=config.DEBUG
    )
