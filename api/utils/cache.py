"""
Caching Layer
Redis-like in-memory cache with TTL support for API responses.
Reduces load on external APIs (Yahoo Finance, OpenAI).
"""

import time
import json
import hashlib
import logging
import threading
from typing import Any, Optional, Callable
from functools import wraps
from datetime import datetime
from collections import OrderedDict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Cache")


class CacheEntry:
    """A single cache entry with TTL."""
    def __init__(self, value: Any, ttl_seconds: int):
        self.value = value
        self.created_at = time.time()
        self.ttl = ttl_seconds
    
    def is_expired(self) -> bool:
        return time.time() - self.created_at > self.ttl


class InMemoryCache:
    """
    Thread-safe in-memory cache with TTL and LRU eviction.
    """
    
    def __init__(self, max_size: int = 10000, default_ttl: int = 300):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        self._stats = {"hits": 0, "misses": 0, "evictions": 0}
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        with self._lock:
            if key not in self._cache:
                self._stats["misses"] += 1
                return None
            
            entry = self._cache[key]
            
            if entry.is_expired():
                del self._cache[key]
                self._stats["misses"] += 1
                return None
            
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            self._stats["hits"] += 1
            return entry.value
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache."""
        with self._lock:
            # Evict if at max size
            while len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)
                self._stats["evictions"] += 1
            
            self._cache[key] = CacheEntry(value, ttl or self.default_ttl)
    
    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
    
    def get_stats(self) -> dict:
        """Get cache statistics."""
        with self._lock:
            total = self._stats["hits"] + self._stats["misses"]
            hit_rate = self._stats["hits"] / total if total > 0 else 0
            return {
                **self._stats,
                "size": len(self._cache),
                "hit_rate": round(hit_rate * 100, 2)
            }
    
    def cleanup_expired(self) -> int:
        """Remove expired entries."""
        removed = 0
        with self._lock:
            expired_keys = [k for k, v in self._cache.items() if v.is_expired()]
            for key in expired_keys:
                del self._cache[key]
                removed += 1
        return removed


# Global cache instances
_caches = {
    "default": InMemoryCache(max_size=10000, default_ttl=300),  # 5 min
    "prices": InMemoryCache(max_size=5000, default_ttl=60),     # 1 min for stock prices
    "fundamentals": InMemoryCache(max_size=2000, default_ttl=3600),  # 1 hour
    "ai_responses": InMemoryCache(max_size=1000, default_ttl=600),  # 10 min
}


def get_cache(name: str = "default") -> InMemoryCache:
    """Get a cache instance by name."""
    if name not in _caches:
        _caches[name] = InMemoryCache()
    return _caches[name]


def cache_key(*args, **kwargs) -> str:
    """Generate cache key from arguments."""
    key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
    return hashlib.md5(key_data.encode()).hexdigest()


def cached(cache_name: str = "default", ttl: Optional[int] = None, key_prefix: str = ""):
    """
    Decorator to cache function results.
    
    Usage:
        @cached(cache_name="prices", ttl=60)
        def get_stock_price(symbol):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache = get_cache(cache_name)
            key = f"{key_prefix}{func.__name__}:{cache_key(*args, **kwargs)}"
            
            # Try cache first
            result = cache.get(key)
            if result is not None:
                logger.debug(f"Cache hit: {key}")
                return result
            
            # Call function
            result = func(*args, **kwargs)
            
            # Cache result
            cache.set(key, result, ttl)
            logger.debug(f"Cache set: {key}")
            
            return result
        
        # Add cache control methods
        wrapper.cache_clear = lambda: get_cache(cache_name).clear()
        wrapper.cache_stats = lambda: get_cache(cache_name).get_stats()
        
        return wrapper
    return decorator


# Specialized caching decorators
def cache_prices(ttl: int = 60):
    """Cache stock price data for 1 minute."""
    return cached(cache_name="prices", ttl=ttl)


def cache_fundamentals(ttl: int = 3600):
    """Cache fundamental data for 1 hour."""
    return cached(cache_name="fundamentals", ttl=ttl)


def cache_ai(ttl: int = 600):
    """Cache AI responses for 10 minutes."""
    return cached(cache_name="ai_responses", ttl=ttl)


if __name__ == "__main__":
    # Test caching
    call_count = 0
    
    @cached(ttl=2)
    def expensive_function(x):
        global call_count
        call_count += 1
        return x * 2
    
    print(f"Call 1: {expensive_function(5)}, count={call_count}")
    print(f"Call 2: {expensive_function(5)}, count={call_count}")  # Should be cached
    print(f"Call 3: {expensive_function(10)}, count={call_count}")  # Different arg
    
    time.sleep(3)  # Wait for expiry
    print(f"Call 4: {expensive_function(5)}, count={call_count}")  # Expired, recalculated
    
    print(f"\nStats: {expensive_function.cache_stats()}")
