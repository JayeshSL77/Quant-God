"""
Rate Limiter
Token bucket rate limiting to protect API quotas.
"""

import time
import threading
import logging
from typing import Dict, Optional
from functools import wraps
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RateLimiter")


class TokenBucket:
    """
    Token bucket rate limiter.
    Allows burst traffic while enforcing average rate.
    """
    
    def __init__(self, rate: float, capacity: int):
        """
        Args:
            rate: Tokens added per second
            capacity: Maximum tokens (burst size)
        """
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_refill = time.time()
        self._lock = threading.Lock()
    
    def _refill(self):
        """Add tokens based on time elapsed."""
        now = time.time()
        elapsed = now - self.last_refill
        tokens_to_add = elapsed * self.rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now
    
    def acquire(self, tokens: int = 1, blocking: bool = True, timeout: float = 30) -> bool:
        """
        Acquire tokens from bucket.
        
        Args:
            tokens: Number of tokens to acquire
            blocking: If True, wait for tokens; if False, return immediately
            timeout: Max seconds to wait when blocking
        
        Returns:
            True if tokens acquired, False otherwise
        """
        deadline = time.time() + timeout
        
        while True:
            with self._lock:
                self._refill()
                
                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return True
                
                if not blocking:
                    return False
                
                # Calculate wait time
                tokens_needed = tokens - self.tokens
                wait_time = tokens_needed / self.rate
            
            if time.time() + wait_time > deadline:
                logger.warning(f"Rate limit timeout after {timeout}s")
                return False
            
            time.sleep(min(wait_time, 0.1))  # Sleep in small increments
    
    @property
    def available_tokens(self) -> float:
        with self._lock:
            self._refill()
            return self.tokens


class RateLimiter:
    """
    Multi-bucket rate limiter for different services.
    """
    
    # Default rate limits
    LIMITS = {
        "openai": (50, 100),      # 50/sec, burst 100
        "openai_embeddings": (100, 200),  # Higher for embeddings
        "sec_edgar": (8, 10),     # SEC limit ~10/sec
        "yahoo_finance": (5, 20), # Conservative for Yahoo
        "database": (100, 200),   # DB queries
        "default": (10, 50),
    }
    
    def __init__(self):
        self._buckets: Dict[str, TokenBucket] = {}
        self._lock = threading.Lock()
    
    def get_bucket(self, name: str) -> TokenBucket:
        """Get or create rate limit bucket."""
        with self._lock:
            if name not in self._buckets:
                rate, capacity = self.LIMITS.get(name, self.LIMITS["default"])
                self._buckets[name] = TokenBucket(rate, capacity)
            return self._buckets[name]
    
    def acquire(self, name: str, tokens: int = 1, blocking: bool = True) -> bool:
        """Acquire tokens from named bucket."""
        bucket = self.get_bucket(name)
        return bucket.acquire(tokens, blocking)
    
    def get_status(self) -> Dict[str, Dict]:
        """Get status of all buckets."""
        status = {}
        for name, bucket in self._buckets.items():
            status[name] = {
                "available": round(bucket.available_tokens, 1),
                "capacity": bucket.capacity,
                "rate_per_sec": bucket.rate
            }
        return status


# Global rate limiter instance
_rate_limiter = RateLimiter()


def get_rate_limiter() -> RateLimiter:
    """Get global rate limiter."""
    return _rate_limiter


def rate_limited(limit_name: str, tokens: int = 1):
    """
    Decorator to rate limit function calls.
    
    Usage:
        @rate_limited("openai")
        def call_openai():
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            limiter = get_rate_limiter()
            if not limiter.acquire(limit_name, tokens):
                raise RateLimitExceeded(f"Rate limit exceeded for {limit_name}")
            return func(*args, **kwargs)
        return wrapper
    return decorator


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded."""
    pass


# Flask middleware for API rate limiting
def create_rate_limit_middleware(limit_name: str = "default", tokens: int = 1):
    """
    Create Flask before_request handler for rate limiting.
    
    Usage:
        from flask import Flask
        app = Flask(__name__)
        
        @app.before_request
        def check_rate_limit():
            return rate_limit_middleware("api")
    """
    def middleware():
        limiter = get_rate_limiter()
        if not limiter.acquire(limit_name, tokens, blocking=False):
            from flask import jsonify
            return jsonify({
                "success": False,
                "error": "Rate limit exceeded. Please try again later.",
                "retry_after": 1
            }), 429
        return None
    return middleware


if __name__ == "__main__":
    # Test rate limiting
    limiter = get_rate_limiter()
    
    print("Testing rate limiter...")
    
    @rate_limited("test", tokens=1)
    def api_call():
        return "OK"
    
    # Should succeed rapidly at first
    for i in range(5):
        print(f"Call {i+1}: {api_call()}")
    
    print(f"\nBucket status: {limiter.get_status()}")
