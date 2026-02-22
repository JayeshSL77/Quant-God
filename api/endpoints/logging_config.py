"""
Inwezt AI - Structured Logging Configuration
Production-grade logging with JSON formatting and request tracing.
"""
import logging
import json
import sys
from datetime import datetime, timezone
from typing import Optional
import os


class JSONFormatter(logging.Formatter):
    """
    Custom formatter that outputs logs as JSON for better parsing in production.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add request_id if present (set by middleware)
        if hasattr(record, 'request_id'):
            log_data["request_id"] = record.request_id
        
        # Add extra fields if present
        if hasattr(record, 'extra_data'):
            log_data["extra"] = record.extra_data
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)


class RequestContextFilter(logging.Filter):
    """
    Logging filter that adds request context to log records.
    """
    
    def __init__(self, name: str = ""):
        super().__init__(name)
        self._request_id: Optional[str] = None
    
    def set_request_id(self, request_id: str):
        self._request_id = request_id
    
    def clear_request_id(self):
        self._request_id = None
    
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = self._request_id
        return True


def setup_logging(
    level: str = "INFO",
    json_format: bool = True,
    log_file: Optional[str] = None
) -> logging.Logger:
    """
    Configure application logging.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_format: If True, output logs as JSON. If False, use standard format.
        log_file: Optional file path to write logs to.
    
    Returns:
        Configured root logger.
    """
    # Get log level
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Create handlers
    handlers: list[logging.Handler] = []
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    
    if json_format:
        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
    
    handlers.append(console_handler)
    
    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)
        file_handler.setFormatter(JSONFormatter())
        handlers.append(file_handler)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add our handlers
    for handler in handlers:
        root_logger.addHandler(handler)
    
    # Set levels for noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the given name.
    
    Usage:
        from api.endpoints.logging_config import get_logger
        logger = get_logger(__name__)
        logger.info("Processing request", extra={"extra_data": {"user_id": 123}})
    """
    return logging.getLogger(name)


# Initialize logging on import if in production
if os.getenv("ENVIRONMENT", "development") == "production":
    setup_logging(
        level=os.getenv("LOG_LEVEL", "INFO"),
        json_format=True,
        log_file=os.getenv("LOG_FILE")
    )
