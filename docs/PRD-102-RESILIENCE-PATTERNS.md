# PRD-102: Resilience Patterns

## Overview
Implement circuit breaker, retry with exponential backoff, and rate limiting patterns for all external service calls (brokers, data providers, APIs). Critical for a trading platform where external failures must not cascade.

## Components

### 1. Circuit Breaker (`src/resilience/circuit_breaker.py`)
- **CircuitBreaker** — Three-state circuit breaker (CLOSED, OPEN, HALF_OPEN)
- Configurable failure threshold (default 5), recovery timeout (default 30s)
- Track failure counts per service name
- Automatic state transitions with timing
- Callback hooks for state changes (for alerting)
- @circuit_breaker decorator for wrapping external calls
- CircuitBreakerRegistry for managing multiple breakers

### 2. Retry Logic (`src/resilience/retry.py`)
- **@retry_with_backoff** decorator — Exponential backoff with jitter
- Configurable max_retries (default 3), base_delay (1s), max_delay (60s)
- Retryable exception whitelist (ConnectionError, TimeoutError, etc.)
- Structured logging of retry attempts
- Support for both sync and async functions

### 3. Rate Limiter (`src/resilience/rate_limiter.py`)
- **RateLimiter** — Token bucket rate limiter
- Per-client and global rate limiting
- Configurable tokens_per_second and burst_size
- FastAPI middleware integration
- Return Retry-After header on 429 responses

### 4. Bulkhead (`src/resilience/bulkhead.py`)
- **Bulkhead** — Limit concurrent calls to external services
- Semaphore-based with configurable max_concurrent (default 10)
- Timeout for acquiring semaphore slot
- Prevents thread/connection pool exhaustion

### 5. Configuration (`src/resilience/config.py`)
- ResilienceConfig with per-service overrides
- Default profiles: BROKER (strict), DATA_PROVIDER (moderate), INTERNAL (relaxed)

## Integration Points
- Wrap broker API calls (Alpaca, IB) with circuit breaker + retry
- Wrap data provider calls (Polygon, Yahoo, FRED) with retry + rate limiter
- FastAPI rate limiting middleware on all API routes
