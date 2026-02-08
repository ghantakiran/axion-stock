"""Configuration for resilience patterns."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Tuple, Type


class CircuitState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class RetryStrategy(str, Enum):
    """Retry backoff strategies."""
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    CONSTANT = "constant"


class BulkheadType(str, Enum):
    """Bulkhead isolation types."""
    SEMAPHORE = "semaphore"
    THREAD_POOL = "thread_pool"


class RateLimitAlgorithm(str, Enum):
    """Rate limiting algorithms."""
    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"


# ── Default Constants ────────────────────────────────────────────────

DEFAULT_FAILURE_THRESHOLD = 5
DEFAULT_RECOVERY_TIMEOUT = 30.0  # seconds
DEFAULT_HALF_OPEN_MAX_CALLS = 1
DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 1.0  # seconds
DEFAULT_MAX_DELAY = 60.0  # seconds
DEFAULT_JITTER_MAX = 0.5  # seconds
DEFAULT_RATE_LIMIT = 100  # requests per second
DEFAULT_RATE_BURST = 20  # burst tokens
DEFAULT_BULKHEAD_MAX_CONCURRENT = 10
DEFAULT_BULKHEAD_TIMEOUT = 5.0  # seconds


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""

    failure_threshold: int = DEFAULT_FAILURE_THRESHOLD
    recovery_timeout: float = DEFAULT_RECOVERY_TIMEOUT
    half_open_max_calls: int = DEFAULT_HALF_OPEN_MAX_CALLS
    excluded_exceptions: List[Type[Exception]] = field(default_factory=list)
    monitored_exceptions: List[Type[Exception]] = field(default_factory=lambda: [Exception])
    success_threshold: int = 1  # successes in HALF_OPEN to transition to CLOSED
    name: str = "default"


@dataclass
class RetryConfig:
    """Configuration for retry logic."""

    max_retries: int = DEFAULT_MAX_RETRIES
    base_delay: float = DEFAULT_BASE_DELAY
    max_delay: float = DEFAULT_MAX_DELAY
    jitter_max: float = DEFAULT_JITTER_MAX
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    retryable_exceptions: Tuple[Type[Exception], ...] = (
        ConnectionError,
        TimeoutError,
        OSError,
    )


@dataclass
class RateLimiterConfig:
    """Configuration for rate limiter."""

    rate: float = DEFAULT_RATE_LIMIT  # tokens per second
    burst: int = DEFAULT_RATE_BURST  # maximum burst size
    algorithm: RateLimitAlgorithm = RateLimitAlgorithm.TOKEN_BUCKET


@dataclass
class BulkheadConfig:
    """Configuration for bulkhead."""

    max_concurrent: int = DEFAULT_BULKHEAD_MAX_CONCURRENT
    timeout: float = DEFAULT_BULKHEAD_TIMEOUT
    bulkhead_type: BulkheadType = BulkheadType.SEMAPHORE
    name: str = "default"


@dataclass
class ResilienceConfig:
    """Top-level resilience configuration."""

    circuit_breaker: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)
    retry: RetryConfig = field(default_factory=RetryConfig)
    rate_limiter: RateLimiterConfig = field(default_factory=RateLimiterConfig)
    bulkhead: BulkheadConfig = field(default_factory=BulkheadConfig)
    enable_metrics: bool = True
    enable_logging: bool = True


@dataclass
class ResilienceMetrics:
    """Metrics snapshot for resilience components."""

    circuit_breaker_name: str = ""
    circuit_state: str = "closed"
    failure_count: int = 0
    success_count: int = 0
    total_calls: int = 0
    rejected_calls: int = 0
    retry_attempts: int = 0
    rate_limited_count: int = 0
    bulkhead_active: int = 0
    bulkhead_queued: int = 0
    last_failure_time: float = 0.0
    last_success_time: float = 0.0
