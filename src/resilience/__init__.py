"""PRD-102: Resilience Patterns.

Provides circuit breaker, retry, rate limiter, and bulkhead patterns
for building fault-tolerant services in the Axion platform.
"""

from .config import (
    CircuitState,
    RetryStrategy,
    BulkheadType,
    RateLimitAlgorithm,
    CircuitBreakerConfig,
    RetryConfig,
    RateLimiterConfig,
    BulkheadConfig,
    ResilienceConfig,
    ResilienceMetrics,
)
from .circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpen,
    CircuitBreakerRegistry,
    circuit_breaker,
    get_registry,
)
from .retry import (
    MaxRetriesExceeded,
    retry,
)
from .rate_limiter import (
    RateLimiter,
    RateLimitExceeded,
    RateLimiterRegistry,
    create_rate_limit_middleware,
)
from .bulkhead import (
    Bulkhead,
    BulkheadFull,
    BulkheadRegistry,
    bulkhead,
    get_bulkhead_registry,
)

__all__ = [
    # Config / Enums
    "CircuitState",
    "RetryStrategy",
    "BulkheadType",
    "RateLimitAlgorithm",
    "CircuitBreakerConfig",
    "RetryConfig",
    "RateLimiterConfig",
    "BulkheadConfig",
    "ResilienceConfig",
    "ResilienceMetrics",
    # Circuit Breaker
    "CircuitBreaker",
    "CircuitBreakerOpen",
    "CircuitBreakerRegistry",
    "circuit_breaker",
    "get_registry",
    # Retry
    "MaxRetriesExceeded",
    "retry",
    # Rate Limiter
    "RateLimiter",
    "RateLimitExceeded",
    "RateLimiterRegistry",
    "create_rate_limit_middleware",
    # Bulkhead
    "Bulkhead",
    "BulkheadFull",
    "BulkheadRegistry",
    "bulkhead",
    "get_bulkhead_registry",
]
