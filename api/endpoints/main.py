"""
Inwezt AI Interface - FastAPI Application
Main entry point for the AI Interface API.
Production-hardened with rate limiting, error tracking, and observability.
"""
import os
import time
from typing import Optional
from datetime import datetime, date
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
import uvicorn
import numpy as np
from decimal import Decimal

# Production imports
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    RATE_LIMIT_AVAILABLE = True
except ImportError:
    RATE_LIMIT_AVAILABLE = False

try:
    import sentry_sdk
    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False

try:
    from prometheus_fastapi_instrumentator import Instrumentator
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

# Import our modules
from api.endpoints.config import config
from api.endpoints.models import (
    QueryRequest, QueryResponse, TaxCalculationRequest, TaxCalculationResponse,
    HealthResponse, ErrorResponse, ResponseStatus
)
from api.endpoints.agent import agent
from api.endpoints.logging_config import setup_logging, get_logger
from api.endpoints.middleware import RequestIDMiddleware, RequestLoggingMiddleware, ErrorHandlingMiddleware
from api.core.utils.indian_utils import IndianTaxCalculator, is_indian_market_open

# Initialize logging
logger = setup_logging(
    level=config.LOG_LEVEL,
    json_format=os.getenv("ENVIRONMENT", "development") == "production"
)
log = get_logger(__name__)

# Initialize Sentry for error tracking
if SENTRY_AVAILABLE and os.getenv("SENTRY_DSN"):
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        environment=os.getenv("ENVIRONMENT", "development"),
        traces_sample_rate=0.1,  # 10% of transactions for performance monitoring
    )
    log.info("Sentry error tracking initialized")

# Initialize rate limiter
if RATE_LIMIT_AVAILABLE:
    limiter = Limiter(key_func=get_remote_address)
else:
    limiter = None

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

# Add rate limit exception handler
if RATE_LIMIT_AVAILABLE:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add production middleware (order matters - first added = last executed)
app.add_middleware(ErrorHandlingMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RequestIDMiddleware)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Initialize Prometheus metrics
if PROMETHEUS_AVAILABLE:
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")
    log.info("Prometheus metrics available at /metrics")

log.info(f"Inwezt AI {config.APP_VERSION} initialized (Rate Limit: {RATE_LIMIT_AVAILABLE}, Sentry: {SENTRY_AVAILABLE})")


# =============================================================================
# API ENDPOINTS
# =============================================================================

# Path configuration
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main chat interface or API status."""
    static_index = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(static_index):
        return FileResponse(static_index)
    
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


@app.get("/waitlist/{full_path:path}", response_class=HTMLResponse)
async def serve_spa_waitlist(full_path: str):
    """Serve the SPA for waitlist routes to support client-side routing."""
    static_index = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(static_index):
        return FileResponse(static_index)
    return HTMLResponse("Frontend not found", status_code=404)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Basic health check endpoint."""
    market_info = is_indian_market_open()
    return HealthResponse(
        status="healthy",
        version=config.APP_VERSION,
        timestamp=datetime.now().isoformat(),
        market_status=market_info
    )


@app.get("/health/ready")
async def readiness_check():
    """
    Readiness check with dependency verification.
    Returns 200 if all dependencies are healthy, 503 otherwise.
    """
    checks = {
        "api": True,
        "database": False,
        "llm": False
    }
    
    # Check database connection
    try:
        from api.database.database import get_connection
        conn = get_connection()
        if conn:
            conn.close()
            checks["database"] = True
    except Exception as e:
        log.warning(f"Database health check failed: {e}")
    
    # Check LLM API (lightweight check)
    try:
        if config.MISTRAL_API_KEY or config.OPENAI_API_KEY or config.GEMINI_API_KEY:
            checks["llm"] = True
    except Exception as e:
        log.warning(f"LLM health check failed: {e}")
    
    all_healthy = all(checks.values())
    status_code = 200 if all_healthy else 503
    
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if all_healthy else "degraded",
            "checks": checks,
            "timestamp": datetime.now().isoformat()
        }
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
            include_tax_context=request.include_tax_context,
            selected_sources=request.selected_sources,
            user_id=request.session_id  # PERSONALIZATION: Pass user ID for learning
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
            # P2: Convert conversation history to list of dicts if provided
            conv_history = None
            if request.conversation_history:
                conv_history = [
                    {"role": msg.role, "content": msg.content}
                    for msg in request.conversation_history
                ]
            
            for event in agent.process_query(
                query=request.query,
                include_tax_context=request.include_tax_context,
                selected_sources=request.selected_sources,
                conversation_history=conv_history,  # P2: Pass conversation history
                user_id=request.session_id,  # PERSONALIZATION: Pass user ID for learning
                analysis_mode=request.analysis_mode.value  # Analysis depth mode
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


@app.post("/api/feedback")
async def submit_feedback(request: Request):
    """
    Log user feedback (like/comment) on AI responses for improving quality.
    """
    try:
        data = await request.json()
        message_id = data.get("message_id")
        feedback_type = data.get("type")  # 'like' or 'comment'
        value = data.get("value")
        
        log.info(f"[FEEDBACK] {feedback_type}: message_id={message_id}, value={value}")
        
        # TODO: Store in database for analysis
        # For now, just log to console/file
        
        return {"status": "ok", "message": "Feedback received"}
    except Exception as e:
        log.error(f"Feedback error: {e}")
        return {"status": "error", "message": str(e)}


# =============================================================================
# WAITLIST API (Agentic Assetz)
# =============================================================================

@app.post("/api/waitlist")
async def waitlist_signup(request: Request):
    """
    Sign up for the Agentic Assetz waitlist.
    Captures email, phone (optional), and market (india/us).
    Returns position in waitlist.
    """
    try:
        data = await request.json()
        
        # Validate required fields
        email = data.get("email", "").strip().lower()
        phone = data.get("phone", "").strip() or None
        market = data.get("market", "").strip().lower()
        
        if not email or "@" not in email:
            return {"success": False, "error": "Valid email is required"}
        
        if market not in ["india", "us"]:
            return {"success": False, "error": "Market must be 'india' or 'us'"}
        
        # Get IP and user agent for analytics
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent", "")[:500]  # Truncate
        
        # Save to database
        from api.database.database import save_waitlist_signup
        result = save_waitlist_signup(
            email=email,
            phone=phone,
            market=market,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        if result.get("success"):
            already_registered = result.get("already_registered", False)
            message = "You're already on the waitlist!" if already_registered else "Successfully joined the waitlist!"
            log.info(f"[WAITLIST] {market.upper()}: {email} - Position #{result.get('position')}")
            return {
                "success": True,
                "position": result.get("position"),
                "already_registered": already_registered,
                "message": message
            }
        else:
            log.error(f"[WAITLIST] Failed: {email} - {result.get('error')}")
            return {"success": False, "error": result.get("error", "Failed to join waitlist")}
            
    except Exception as e:
        log.error(f"Waitlist signup error: {e}")
        return {"success": False, "error": "An error occurred. Please try again."}


@app.get("/api/waitlist/count")
async def waitlist_count(market: Optional[str] = None):
    """Get waitlist count (for admin/display purposes)."""
    from api.database.database import get_waitlist_count
    count = get_waitlist_count(market)
    return {"count": count, "market": market or "all"}


# =============================================================================
# STATIC FILES (Mount after routes)
# =============================================================================

try:
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.mount("/assets", StaticFiles(directory=os.path.join(STATIC_DIR, "assets")), name="assets")
    app.mount("/images", StaticFiles(directory=os.path.join(STATIC_DIR, "images")), name="images")
except:
    pass  # Static directory may not exist yet


@app.get("/logo.png")
async def serve_logo():
    """Serve the logo.png file for favicon."""
    logo_path = os.path.join(STATIC_DIR, "logo.png")
    if os.path.exists(logo_path):
        return FileResponse(logo_path)
    return HTMLResponse("Logo not found", status_code=404)


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
