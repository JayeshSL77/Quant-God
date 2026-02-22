"""
Utils Package
Robustness utilities for the analytics platform.
"""

from utils.resilience import (
    retry_with_backoff,
    with_retry,
    with_circuit_breaker,
    CircuitBreaker,
    get_circuit_breaker,
    RetryConfig,
    CircuitBreakerOpenError
)

from utils.cache import (
    cached,
    cache_prices,
    cache_fundamentals,
    cache_ai,
    get_cache,
    InMemoryCache
)

from utils.rate_limiter import (
    rate_limited,
    get_rate_limiter,
    RateLimiter,
    RateLimitExceeded
)

__all__ = [
    # Resilience
    'retry_with_backoff',
    'with_retry', 
    'with_circuit_breaker',
    'CircuitBreaker',
    'get_circuit_breaker',
    'RetryConfig',
    'CircuitBreakerOpenError',
    
    # Caching
    'cached',
    'cache_prices',
    'cache_fundamentals', 
    'cache_ai',
    'get_cache',
    'InMemoryCache',
    
    # Rate Limiting
    'rate_limited',
    'get_rate_limiter',
    'RateLimiter',
    'RateLimitExceeded',
]
