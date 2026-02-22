"""
Resilience Utilities
Retry logic, circuit breakers, and error handling for robust API calls.
"""

import time
import random
import logging
import functools
from typing import Callable, Any, Optional, Type, Tuple
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Resilience")


class RetryConfig:
    """Configuration for retry behavior."""
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions


def retry_with_backoff(config: Optional[RetryConfig] = None):
    """
    Decorator that retries failed function calls with exponential backoff.
    
    Usage:
        @retry_with_backoff(RetryConfig(max_retries=3))
        def my_api_call():
            ...
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(config.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except config.retryable_exceptions as e:
                    last_exception = e
                    
                    if attempt == config.max_retries:
                        logger.error(f"{func.__name__} failed after {config.max_retries + 1} attempts: {e}")
                        raise
                    
                    # Calculate delay with exponential backoff
                    delay = min(
                        config.base_delay * (config.exponential_base ** attempt),
                        config.max_delay
                    )
                    
                    # Add jitter to prevent thundering herd
                    if config.jitter:
                        delay *= (0.5 + random.random())
                    
                    logger.warning(f"{func.__name__} attempt {attempt + 1} failed: {e}. Retrying in {delay:.2f}s...")
                    time.sleep(delay)
            
            raise last_exception
        
        return wrapper
    return decorator


class CircuitBreaker:
    """
    Circuit breaker pattern to prevent cascading failures.
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, requests fail immediately
    - HALF_OPEN: Testing if service recovered
    """
    
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 30,
        half_open_max_calls: int = 3
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        
        self.state = self.CLOSED
        self.failures = 0
        self.last_failure_time: Optional[datetime] = None
        self.half_open_calls = 0
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function through circuit breaker."""
        
        if self.state == self.OPEN:
            if self._should_try_recovery():
                self.state = self.HALF_OPEN
                self.half_open_calls = 0
                logger.info(f"Circuit {self.name}: OPEN -> HALF_OPEN")
            else:
                raise CircuitBreakerOpenError(f"Circuit {self.name} is OPEN")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    def _should_try_recovery(self) -> bool:
        """Check if enough time passed to try recovery."""
        if self.last_failure_time is None:
            return True
        return datetime.now() - self.last_failure_time > timedelta(seconds=self.recovery_timeout)
    
    def _on_success(self):
        """Handle successful call."""
        if self.state == self.HALF_OPEN:
            self.half_open_calls += 1
            if self.half_open_calls >= self.half_open_max_calls:
                self.state = self.CLOSED
                self.failures = 0
                logger.info(f"Circuit {self.name}: HALF_OPEN -> CLOSED")
        else:
            self.failures = 0
    
    def _on_failure(self):
        """Handle failed call."""
        self.failures += 1
        self.last_failure_time = datetime.now()
        
        if self.state == self.HALF_OPEN:
            self.state = self.OPEN
            logger.warning(f"Circuit {self.name}: HALF_OPEN -> OPEN")
        elif self.failures >= self.failure_threshold:
            self.state = self.OPEN
            logger.warning(f"Circuit {self.name}: CLOSED -> OPEN (failures={self.failures})")


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass


# Pre-configured circuit breakers for common services
circuit_breakers = {
    "openai": CircuitBreaker("openai", failure_threshold=3, recovery_timeout=60),
    "sec_edgar": CircuitBreaker("sec_edgar", failure_threshold=5, recovery_timeout=30),
    "yahoo_finance": CircuitBreaker("yahoo_finance", failure_threshold=5, recovery_timeout=30),
    "database": CircuitBreaker("database", failure_threshold=3, recovery_timeout=10),
}


def get_circuit_breaker(name: str) -> CircuitBreaker:
    """Get or create a circuit breaker by name."""
    if name not in circuit_breakers:
        circuit_breakers[name] = CircuitBreaker(name)
    return circuit_breakers[name]


# Convenience decorators
def with_retry(max_retries: int = 3, base_delay: float = 1.0):
    """Simplified retry decorator."""
    return retry_with_backoff(RetryConfig(
        max_retries=max_retries,
        base_delay=base_delay
    ))


def with_circuit_breaker(breaker_name: str):
    """Decorator to wrap function with circuit breaker."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            breaker = get_circuit_breaker(breaker_name)
            return breaker.call(func, *args, **kwargs)
        return wrapper
    return decorator


if __name__ == "__main__":
    # Test retry
    call_count = 0
    
    @with_retry(max_retries=2, base_delay=0.1)
    def flaky_function():
        global call_count
        call_count += 1
        if call_count < 3:
            raise ValueError("Simulated failure")
        return "Success!"
    
    print(f"Result: {flaky_function()}")
    print(f"Took {call_count} attempts")
