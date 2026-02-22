"""
Inwezt AI - Production Middleware
Request ID tracking, rate limiting, and error handling.
"""
import uuid
import time
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from api.endpoints.logging_config import get_logger

logger = get_logger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Adds a unique request ID to each request for tracing.
    The ID is available in request.state.request_id and returned in X-Request-ID header.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate or use existing request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        
        # Process request
        response = await call_next(request)
        
        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Logs request/response details with timing information.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        request_id = getattr(request.state, 'request_id', 'unknown')
        
        # Log request
        logger.info(
            f"Request started: {request.method} {request.url.path}",
            extra={"extra_data": {
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "client_ip": request.client.host if request.client else "unknown"
            }}
        )
        
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000
        
        # Log response
        logger.info(
            f"Request completed: {request.method} {request.url.path} - {response.status_code} ({duration_ms:.2f}ms)",
            extra={"extra_data": {
                "request_id": request_id,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2)
            }}
        )
        
        return response


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """
    Global error handler that catches unhandled exceptions and returns structured errors.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            return await call_next(request)
        except Exception as exc:
            request_id = getattr(request.state, 'request_id', 'unknown')
            
            # Log the error
            logger.error(
                f"Unhandled exception: {str(exc)}",
                exc_info=True,
                extra={"extra_data": {
                    "request_id": request_id,
                    "path": request.url.path,
                    "method": request.method
                }}
            )
            
            # Return structured error response
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal server error",
                    "message": "An unexpected error occurred. Please try again.",
                    "request_id": request_id
                },
                headers={"X-Request-ID": request_id}
            )
