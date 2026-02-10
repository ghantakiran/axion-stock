"""Tests for PRD-102: Resilience Patterns."""

import asyncio
import time
from unittest.mock import MagicMock, patch

import pytest

from src.resilience.config import (
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
from src.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpen,
    CircuitBreakerRegistry,
    circuit_breaker,
)
from src.resilience.retry import (
    MaxRetriesExceeded,
    retry,
    _compute_delay,
)
from src.resilience.rate_limiter import (
    RateLimiter,
    RateLimitExceeded,
    RateLimiterRegistry,
)
from src.resilience.bulkhead import (
    Bulkhead,
    BulkheadFull,
    BulkheadRegistry,
    bulkhead,
)


# ── Helpers ──────────────────────────────────────────────────────────

def _run_async(coro):
    """Run an async coroutine synchronously."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── Config Tests ─────────────────────────────────────────────────────


class TestResilienceEnums:
    def test_circuit_states(self):
        assert len(CircuitState) == 3
        assert CircuitState.CLOSED.value == "closed"
        assert CircuitState.OPEN.value == "open"
        assert CircuitState.HALF_OPEN.value == "half_open"

    def test_retry_strategies(self):
        assert len(RetryStrategy) == 3
        assert RetryStrategy.EXPONENTIAL.value == "exponential"
        assert RetryStrategy.LINEAR.value == "linear"
        assert RetryStrategy.CONSTANT.value == "constant"

    def test_bulkhead_types(self):
        assert len(BulkheadType) == 2
        assert BulkheadType.SEMAPHORE.value == "semaphore"

    def test_rate_limit_algorithms(self):
        assert len(RateLimitAlgorithm) == 3
        assert RateLimitAlgorithm.TOKEN_BUCKET.value == "token_bucket"

    def test_circuit_state_string_enum(self):
        assert str(CircuitState.CLOSED) == "CircuitState.CLOSED"
        assert CircuitState("closed") == CircuitState.CLOSED

    def test_retry_strategy_string_enum(self):
        assert RetryStrategy("exponential") == RetryStrategy.EXPONENTIAL

    def test_rate_limit_algorithm_values(self):
        assert RateLimitAlgorithm.SLIDING_WINDOW.value == "sliding_window"
        assert RateLimitAlgorithm.FIXED_WINDOW.value == "fixed_window"

    def test_bulkhead_type_thread_pool(self):
        assert BulkheadType.THREAD_POOL.value == "thread_pool"


class TestResilienceConfigs:
    def test_circuit_breaker_config_defaults(self):
        cfg = CircuitBreakerConfig()
        assert cfg.failure_threshold == 5
        assert cfg.recovery_timeout == 30.0
        assert cfg.half_open_max_calls == 1
        assert cfg.name == "default"
        assert cfg.excluded_exceptions == []

    def test_retry_config_defaults(self):
        cfg = RetryConfig()
        assert cfg.max_retries == 3
        assert cfg.base_delay == 1.0
        assert cfg.max_delay == 60.0
        assert cfg.jitter_max == 0.5
        assert cfg.strategy == RetryStrategy.EXPONENTIAL
        assert ConnectionError in cfg.retryable_exceptions
        assert TimeoutError in cfg.retryable_exceptions
        assert OSError in cfg.retryable_exceptions

    def test_rate_limiter_config_defaults(self):
        cfg = RateLimiterConfig()
        assert cfg.rate == 100
        assert cfg.burst == 20
        assert cfg.algorithm == RateLimitAlgorithm.TOKEN_BUCKET

    def test_bulkhead_config_defaults(self):
        cfg = BulkheadConfig()
        assert cfg.max_concurrent == 10
        assert cfg.timeout == 5.0
        assert cfg.bulkhead_type == BulkheadType.SEMAPHORE

    def test_resilience_config_composite(self):
        cfg = ResilienceConfig()
        assert isinstance(cfg.circuit_breaker, CircuitBreakerConfig)
        assert isinstance(cfg.retry, RetryConfig)
        assert isinstance(cfg.rate_limiter, RateLimiterConfig)
        assert isinstance(cfg.bulkhead, BulkheadConfig)
        assert cfg.enable_metrics is True

    def test_resilience_metrics_defaults(self):
        m = ResilienceMetrics()
        assert m.circuit_breaker_name == ""
        assert m.circuit_state == "closed"
        assert m.failure_count == 0
        assert m.total_calls == 0

    def test_custom_circuit_breaker_config(self):
        cfg = CircuitBreakerConfig(
            failure_threshold=10,
            recovery_timeout=60.0,
            name="custom",
        )
        assert cfg.failure_threshold == 10
        assert cfg.recovery_timeout == 60.0
        assert cfg.name == "custom"

    def test_custom_retry_config(self):
        cfg = RetryConfig(
            max_retries=5,
            base_delay=2.0,
            strategy=RetryStrategy.LINEAR,
        )
        assert cfg.max_retries == 5
        assert cfg.strategy == RetryStrategy.LINEAR


# ── Circuit Breaker Tests ────────────────────────────────────────────


class TestCircuitBreaker:
    def test_initial_state_is_closed(self):
        cb = CircuitBreaker()
        assert cb.state == CircuitState.CLOSED
        assert cb.is_closed
        assert not cb.is_open

    def test_successful_call(self):
        cb = CircuitBreaker()
        result = cb.call(lambda: 42)
        assert result == 42
        assert cb.success_count == 1
        assert cb.total_calls == 1

    def test_failure_increments_count(self):
        cb = CircuitBreaker()
        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))
        assert cb.failure_count == 1

    def test_opens_after_threshold(self):
        cfg = CircuitBreakerConfig(failure_threshold=3)
        cb = CircuitBreaker(cfg)

        def failing():
            raise ConnectionError("down")

        for _ in range(3):
            with pytest.raises(ConnectionError):
                cb.call(failing)

        assert cb.state == CircuitState.OPEN

    def test_open_rejects_calls(self):
        cfg = CircuitBreakerConfig(failure_threshold=2)
        cb = CircuitBreaker(cfg)

        def failing():
            raise ConnectionError("down")

        for _ in range(2):
            with pytest.raises(ConnectionError):
                cb.call(failing)

        with pytest.raises(CircuitBreakerOpen) as exc_info:
            cb.call(lambda: 42)

        assert "OPEN" in str(exc_info.value)
        assert cb.rejected_calls == 1

    def test_transitions_to_half_open(self):
        cfg = CircuitBreakerConfig(failure_threshold=2, recovery_timeout=0.1)
        cb = CircuitBreaker(cfg)

        def failing():
            raise ConnectionError("down")

        for _ in range(2):
            with pytest.raises(ConnectionError):
                cb.call(failing)

        assert cb.state == CircuitState.OPEN
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_success_closes(self):
        cfg = CircuitBreakerConfig(failure_threshold=2, recovery_timeout=0.1)
        cb = CircuitBreaker(cfg)

        def failing():
            raise ConnectionError("down")

        for _ in range(2):
            with pytest.raises(ConnectionError):
                cb.call(failing)

        time.sleep(0.15)
        result = cb.call(lambda: "recovered")
        assert result == "recovered"
        assert cb.state == CircuitState.CLOSED

    def test_half_open_failure_reopens(self):
        cfg = CircuitBreakerConfig(failure_threshold=2, recovery_timeout=0.1)
        cb = CircuitBreaker(cfg)

        def failing():
            raise ConnectionError("down")

        for _ in range(2):
            with pytest.raises(ConnectionError):
                cb.call(failing)

        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

        with pytest.raises(ConnectionError):
            cb.call(failing)
        assert cb.state == CircuitState.OPEN

    def test_reset(self):
        cfg = CircuitBreakerConfig(failure_threshold=2)
        cb = CircuitBreaker(cfg)

        def failing():
            raise ConnectionError("down")

        for _ in range(2):
            with pytest.raises(ConnectionError):
                cb.call(failing)

        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_excluded_exceptions_not_counted(self):
        cfg = CircuitBreakerConfig(
            failure_threshold=3,
            excluded_exceptions=[ValueError],
        )
        cb = CircuitBreaker(cfg)

        for _ in range(5):
            with pytest.raises(ValueError):
                cb.call(lambda: (_ for _ in ()).throw(ValueError("ignore")))

        # Should still be closed because ValueError is excluded
        assert cb.state == CircuitState.CLOSED

    def test_get_metrics(self):
        cb = CircuitBreaker(CircuitBreakerConfig(name="test_cb"))
        cb.call(lambda: 1)
        metrics = cb.get_metrics()
        assert metrics["name"] == "test_cb"
        assert metrics["state"] == "closed"
        assert metrics["success_count"] == 1
        assert metrics["failure_threshold"] == 5

    def test_async_call(self):
        cb = CircuitBreaker()

        async def async_work():
            return "async_result"

        result = _run_async(cb.call_async(async_work))
        assert result == "async_result"
        assert cb.success_count == 1


class TestCircuitBreakerOpen:
    def test_exception_message(self):
        exc = CircuitBreakerOpen("test_svc", 15.3)
        assert exc.name == "test_svc"
        assert exc.remaining == 15.3
        assert "test_svc" in str(exc)
        assert "OPEN" in str(exc)

    def test_default_remaining(self):
        exc = CircuitBreakerOpen("svc")
        assert exc.remaining == 0.0


class TestCircuitBreakerRegistry:
    def test_get_or_create(self):
        reg = CircuitBreakerRegistry()
        cb1 = reg.get_or_create("service_a")
        cb2 = reg.get_or_create("service_a")
        assert cb1 is cb2
        assert cb1.name == "service_a"

    def test_get_returns_none_for_missing(self):
        reg = CircuitBreakerRegistry()
        assert reg.get("nonexistent") is None

    def test_remove(self):
        reg = CircuitBreakerRegistry()
        reg.get_or_create("temp")
        assert reg.remove("temp") is True
        assert reg.remove("temp") is False

    def test_reset_all(self):
        reg = CircuitBreakerRegistry()
        cb = reg.get_or_create(
            "svc", CircuitBreakerConfig(failure_threshold=2)
        )

        def failing():
            raise ConnectionError("down")

        for _ in range(2):
            with pytest.raises(ConnectionError):
                cb.call(failing)

        assert cb.state == CircuitState.OPEN
        reg.reset_all()
        assert cb.state == CircuitState.CLOSED

    def test_get_all_metrics(self):
        reg = CircuitBreakerRegistry()
        reg.get_or_create("svc_a")
        reg.get_or_create("svc_b")
        metrics = reg.get_all_metrics()
        assert "svc_a" in metrics
        assert "svc_b" in metrics

    def test_names(self):
        reg = CircuitBreakerRegistry()
        reg.get_or_create("x")
        reg.get_or_create("y")
        assert set(reg.names) == {"x", "y"}

    def test_len(self):
        reg = CircuitBreakerRegistry()
        assert len(reg) == 0
        reg.get_or_create("a")
        assert len(reg) == 1

    def test_create_with_custom_config(self):
        reg = CircuitBreakerRegistry()
        cfg = CircuitBreakerConfig(failure_threshold=10, name="custom")
        cb = reg.get_or_create("custom", cfg)
        assert cb._config.failure_threshold == 10


class TestCircuitBreakerDecorator:
    def test_sync_decorator(self):
        registry = CircuitBreakerRegistry()

        @circuit_breaker("my_sync_svc", registry=registry)
        def my_func():
            return "ok"

        assert my_func() == "ok"
        cb = registry.get("my_sync_svc")
        assert cb is not None
        assert cb.success_count == 1

    def test_async_decorator(self):
        registry = CircuitBreakerRegistry()

        @circuit_breaker("my_async_svc", registry=registry)
        async def my_async_func():
            return "async_ok"

        result = _run_async(my_async_func())
        assert result == "async_ok"
        cb = registry.get("my_async_svc")
        assert cb.success_count == 1

    def test_decorator_opens_on_failures(self):
        registry = CircuitBreakerRegistry()
        cfg = CircuitBreakerConfig(failure_threshold=2)

        @circuit_breaker("fail_svc", config=cfg, registry=registry)
        def failing_func():
            raise ConnectionError("down")

        for _ in range(2):
            with pytest.raises(ConnectionError):
                failing_func()

        with pytest.raises(CircuitBreakerOpen):
            failing_func()

    def test_decorator_preserves_function_name(self):
        registry = CircuitBreakerRegistry()

        @circuit_breaker("svc", registry=registry)
        def original_name():
            pass

        assert original_name.__name__ == "original_name"

    def test_decorator_exposes_breaker(self):
        registry = CircuitBreakerRegistry()

        @circuit_breaker("svc", registry=registry)
        def my_func():
            pass

        assert hasattr(my_func, "_circuit_breaker")
        assert isinstance(my_func._circuit_breaker, CircuitBreaker)

    def test_async_decorator_opens_on_failures(self):
        registry = CircuitBreakerRegistry()
        cfg = CircuitBreakerConfig(failure_threshold=2)

        @circuit_breaker("async_fail", config=cfg, registry=registry)
        async def async_failing():
            raise ConnectionError("down")

        for _ in range(2):
            with pytest.raises(ConnectionError):
                _run_async(async_failing())

        with pytest.raises(CircuitBreakerOpen):
            _run_async(async_failing())

    def test_sync_decorator_with_args(self):
        registry = CircuitBreakerRegistry()

        @circuit_breaker("arg_svc", registry=registry)
        def add(a, b):
            return a + b

        assert add(3, 4) == 7

    def test_async_decorator_with_kwargs(self):
        registry = CircuitBreakerRegistry()

        @circuit_breaker("kwarg_svc", registry=registry)
        async def greet(name="world"):
            return f"hello {name}"

        assert _run_async(greet(name="axion")) == "hello axion"


# ── Retry Tests ──────────────────────────────────────────────────────


class TestComputeDelay:
    def test_exponential_backoff(self):
        cfg = RetryConfig(base_delay=1.0, jitter_max=0.0)
        assert _compute_delay(0, cfg) == 1.0
        assert _compute_delay(1, cfg) == 2.0
        assert _compute_delay(2, cfg) == 4.0
        assert _compute_delay(3, cfg) == 8.0

    def test_linear_backoff(self):
        cfg = RetryConfig(
            base_delay=1.0, jitter_max=0.0, strategy=RetryStrategy.LINEAR
        )
        assert _compute_delay(0, cfg) == 1.0
        assert _compute_delay(1, cfg) == 2.0
        assert _compute_delay(2, cfg) == 3.0

    def test_constant_backoff(self):
        cfg = RetryConfig(
            base_delay=2.0, jitter_max=0.0, strategy=RetryStrategy.CONSTANT
        )
        assert _compute_delay(0, cfg) == 2.0
        assert _compute_delay(5, cfg) == 2.0

    def test_max_delay_cap(self):
        cfg = RetryConfig(base_delay=10.0, max_delay=30.0, jitter_max=0.0)
        delay = _compute_delay(5, cfg)  # 10 * 32 = 320, capped at 30
        assert delay == 30.0

    def test_jitter_adds_randomness(self):
        cfg = RetryConfig(base_delay=1.0, jitter_max=0.5)
        delays = {_compute_delay(0, cfg) for _ in range(20)}
        # With jitter there should be variation
        assert len(delays) > 1

    def test_zero_jitter(self):
        cfg = RetryConfig(base_delay=1.0, jitter_max=0.0)
        delays = {_compute_delay(0, cfg) for _ in range(10)}
        assert len(delays) == 1
        assert 1.0 in delays

    def test_jitter_bounded(self):
        cfg = RetryConfig(base_delay=1.0, jitter_max=0.5)
        for _ in range(50):
            d = _compute_delay(0, cfg)
            assert 1.0 <= d <= 1.5

    def test_large_attempt_number(self):
        cfg = RetryConfig(base_delay=1.0, max_delay=60.0, jitter_max=0.0)
        delay = _compute_delay(20, cfg)
        assert delay == 60.0


class TestRetryLogic:
    def test_succeeds_without_retry(self):
        call_count = 0

        @retry(max_retries=3, base_delay=0.01, jitter_max=0.0)
        def succeeding():
            nonlocal call_count
            call_count += 1
            return "ok"

        assert succeeding() == "ok"
        assert call_count == 1

    def test_retries_on_connection_error(self):
        call_count = 0

        @retry(max_retries=3, base_delay=0.01, jitter_max=0.0)
        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("fail")
            return "recovered"

        assert flaky() == "recovered"
        assert call_count == 3

    def test_max_retries_exceeded(self):
        @retry(max_retries=2, base_delay=0.01, jitter_max=0.0)
        def always_fail():
            raise ConnectionError("fail")

        with pytest.raises(MaxRetriesExceeded) as exc_info:
            always_fail()
        assert exc_info.value.attempts == 2
        assert isinstance(exc_info.value.last_exception, ConnectionError)

    def test_non_retryable_exception_not_retried(self):
        call_count = 0

        @retry(
            max_retries=3,
            retryable_exceptions=(ConnectionError,),
            base_delay=0.01,
            jitter_max=0.0,
        )
        def raises_value_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("not retryable")

        with pytest.raises(ValueError):
            raises_value_error()
        assert call_count == 1  # No retries

    def test_async_retry(self):
        call_count = 0

        @retry(max_retries=3, base_delay=0.01, jitter_max=0.0)
        async def async_flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("fail")
            return "async_ok"

        result = _run_async(async_flaky())
        assert result == "async_ok"
        assert call_count == 2

    def test_async_max_retries_exceeded(self):
        @retry(max_retries=2, base_delay=0.01, jitter_max=0.0)
        async def async_always_fail():
            raise TimeoutError("timeout")

        with pytest.raises(MaxRetriesExceeded):
            _run_async(async_always_fail())

    def test_retries_timeout_error(self):
        call_count = 0

        @retry(max_retries=2, base_delay=0.01, jitter_max=0.0)
        def timeout_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise TimeoutError("timeout")
            return "ok"

        assert timeout_func() == "ok"
        assert call_count == 3

    def test_retries_os_error(self):
        call_count = 0

        @retry(max_retries=1, base_delay=0.01, jitter_max=0.0)
        def os_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise OSError("os fail")
            return "ok"

        assert os_func() == "ok"
        assert call_count == 2

    def test_preserves_function_name(self):
        @retry(max_retries=1)
        def my_function():
            pass

        assert my_function.__name__ == "my_function"

    def test_retry_config_attached(self):
        @retry(max_retries=5, base_delay=2.0)
        def func():
            pass

        assert hasattr(func, "_retry_config")
        assert func._retry_config.max_retries == 5

    def test_with_retry_config_object(self):
        cfg = RetryConfig(max_retries=4, base_delay=0.01, jitter_max=0.0)
        call_count = 0

        @retry(config=cfg)
        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("fail")
            return "ok"

        assert flaky() == "ok"

    def test_retry_with_args_and_kwargs(self):
        @retry(max_retries=1, base_delay=0.01, jitter_max=0.0)
        def add(a, b, extra=0):
            return a + b + extra

        assert add(1, 2, extra=3) == 6


class TestMaxRetriesExceeded:
    def test_exception_message(self):
        inner = ConnectionError("original")
        exc = MaxRetriesExceeded(3, inner)
        assert exc.attempts == 3
        assert exc.last_exception is inner
        assert "3" in str(exc)
        assert "original" in str(exc)

    def test_inherits_from_exception(self):
        exc = MaxRetriesExceeded(1, ValueError("x"))
        assert isinstance(exc, Exception)


# ── Rate Limiter Tests ───────────────────────────────────────────────


class TestRateLimiter:
    def test_allows_within_burst(self):
        cfg = RateLimiterConfig(rate=10, burst=5)
        rl = RateLimiter(cfg)
        for _ in range(5):
            assert rl.consume() is True

    def test_rejects_over_burst(self):
        cfg = RateLimiterConfig(rate=10, burst=3)
        rl = RateLimiter(cfg)
        for _ in range(3):
            rl.consume()
        assert rl.consume() is False

    def test_refills_over_time(self):
        cfg = RateLimiterConfig(rate=100, burst=2)
        rl = RateLimiter(cfg)
        assert rl.consume()
        assert rl.consume()
        assert not rl.consume()
        time.sleep(0.05)  # at 100/s, 0.05s = 5 tokens
        assert rl.consume()

    def test_available_tokens(self):
        cfg = RateLimiterConfig(rate=10, burst=5)
        rl = RateLimiter(cfg)
        assert rl.available_tokens == 5.0
        rl.consume()
        assert rl.available_tokens < 5.0

    def test_retry_after(self):
        cfg = RateLimiterConfig(rate=10, burst=1)
        rl = RateLimiter(cfg)
        rl.consume()
        wait = rl.retry_after()
        assert wait > 0

    def test_retry_after_when_available(self):
        cfg = RateLimiterConfig(rate=10, burst=5)
        rl = RateLimiter(cfg)
        assert rl.retry_after() == 0.0

    def test_reset(self):
        cfg = RateLimiterConfig(rate=10, burst=3)
        rl = RateLimiter(cfg)
        for _ in range(3):
            rl.consume()
        assert not rl.consume()
        rl.reset()
        assert rl.consume()

    def test_metrics(self):
        cfg = RateLimiterConfig(rate=10, burst=5)
        rl = RateLimiter(cfg)
        rl.consume()
        rl.consume()
        metrics = rl.get_metrics()
        assert metrics["total_allowed"] == 2
        assert metrics["total_rejected"] == 0
        assert metrics["max_tokens"] == 5.0
        assert metrics["rate_per_second"] == 10

    def test_total_rejected_count(self):
        cfg = RateLimiterConfig(rate=10, burst=1)
        rl = RateLimiter(cfg)
        rl.consume()
        rl.consume()  # rejected
        assert rl.total_rejected == 1
        assert rl.total_allowed == 1

    def test_multi_token_consume(self):
        cfg = RateLimiterConfig(rate=10, burst=5)
        rl = RateLimiter(cfg)
        assert rl.consume(3) is True
        assert rl.consume(3) is False  # only 2 left

    def test_consume_zero_tokens(self):
        cfg = RateLimiterConfig(rate=10, burst=5)
        rl = RateLimiter(cfg)
        assert rl.consume(0) is True


class TestRateLimiterRegistry:
    def test_get_or_create(self):
        reg = RateLimiterRegistry()
        rl1 = reg.get_or_create("client_a")
        rl2 = reg.get_or_create("client_a")
        assert rl1 is rl2

    def test_different_keys(self):
        reg = RateLimiterRegistry()
        rl1 = reg.get_or_create("client_a")
        rl2 = reg.get_or_create("client_b")
        assert rl1 is not rl2

    def test_remove(self):
        reg = RateLimiterRegistry()
        reg.get_or_create("temp")
        assert reg.remove("temp") is True
        assert reg.remove("temp") is False

    def test_get_all_metrics(self):
        reg = RateLimiterRegistry()
        reg.get_or_create("a")
        reg.get_or_create("b")
        metrics = reg.get_all_metrics()
        assert "a" in metrics
        assert "b" in metrics

    def test_len(self):
        reg = RateLimiterRegistry()
        assert len(reg) == 0
        reg.get_or_create("x")
        assert len(reg) == 1

    def test_custom_default_config(self):
        cfg = RateLimiterConfig(rate=50, burst=10)
        reg = RateLimiterRegistry(cfg)
        rl = reg.get_or_create("client")
        metrics = rl.get_metrics()
        assert metrics["rate_per_second"] == 50
        assert metrics["max_tokens"] == 10

    def test_multiple_removes(self):
        reg = RateLimiterRegistry()
        reg.get_or_create("a")
        reg.get_or_create("b")
        assert len(reg) == 2
        reg.remove("a")
        assert len(reg) == 1

    def test_isolated_limiters(self):
        reg = RateLimiterRegistry(RateLimiterConfig(rate=10, burst=2))
        rl_a = reg.get_or_create("a")
        rl_b = reg.get_or_create("b")
        rl_a.consume()
        rl_a.consume()
        assert not rl_a.consume()
        assert rl_b.consume()  # b is independent


class TestRateLimitExceeded:
    def test_exception_message(self):
        exc = RateLimitExceeded(5.0)
        assert exc.retry_after == 5.0
        assert "5.0" in str(exc)

    def test_default_retry_after(self):
        exc = RateLimitExceeded()
        assert exc.retry_after == 0.0


# ── Bulkhead Tests ───────────────────────────────────────────────────


class TestBulkhead:
    def test_allows_within_limit(self):
        bh = Bulkhead(BulkheadConfig(max_concurrent=2, timeout=1.0))

        async def work():
            return "done"

        result = _run_async(bh.execute(work))
        assert result == "done"
        assert bh.total_accepted == 1

    def test_tracks_active_count(self):
        bh = Bulkhead(BulkheadConfig(max_concurrent=5))

        async def check_active():
            assert bh.active_count == 1
            return "ok"

        _run_async(bh.execute(check_active))
        assert bh.active_count == 0  # released after completion

    def test_rejects_when_full(self):
        bh = Bulkhead(BulkheadConfig(max_concurrent=1, timeout=0.1))

        async def blocking():
            await asyncio.sleep(1.0)

        async def run_test():
            task = asyncio.create_task(bh.execute(blocking))
            await asyncio.sleep(0.05)  # Let the first task acquire
            with pytest.raises(BulkheadFull):
                await bh.execute(blocking)
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, BulkheadFull):
                pass

        _run_async(run_test())
        assert bh.total_rejected >= 1

    def test_concurrent_execution(self):
        bh = Bulkhead(BulkheadConfig(max_concurrent=3, timeout=2.0))
        results = []

        async def work(n):
            results.append(n)
            await asyncio.sleep(0.01)
            return n

        async def run_all():
            tasks = [bh.execute(work, i) for i in range(3)]
            return await asyncio.gather(*tasks)

        outcomes = _run_async(run_all())
        assert set(outcomes) == {0, 1, 2}
        assert bh.total_accepted == 3

    def test_releases_on_exception(self):
        bh = Bulkhead(BulkheadConfig(max_concurrent=1, timeout=1.0))

        async def failing():
            raise ValueError("boom")

        with pytest.raises(ValueError):
            _run_async(bh.execute(failing))

        assert bh.active_count == 0  # slot released

        # Should be able to execute again
        async def ok():
            return "fine"

        assert _run_async(bh.execute(ok)) == "fine"

    def test_get_metrics(self):
        bh = Bulkhead(BulkheadConfig(max_concurrent=5, name="test_bh"))
        metrics = bh.get_metrics()
        assert metrics["name"] == "test_bh"
        assert metrics["max_concurrent"] == 5
        assert metrics["available_slots"] == 5
        assert metrics["active_count"] == 0

    def test_reset(self):
        bh = Bulkhead(BulkheadConfig(max_concurrent=2))

        async def work():
            return 1

        _run_async(bh.execute(work))
        assert bh.total_accepted == 1
        bh.reset()
        assert bh.total_accepted == 0

    def test_available_slots(self):
        bh = Bulkhead(BulkheadConfig(max_concurrent=10))
        assert bh.available_slots == 10
        assert bh.max_concurrent == 10

    def test_name_property(self):
        bh = Bulkhead(BulkheadConfig(name="my_bh"))
        assert bh.name == "my_bh"

    def test_default_config(self):
        bh = Bulkhead()
        assert bh.max_concurrent == 10

    def test_execute_with_args(self):
        bh = Bulkhead(BulkheadConfig(max_concurrent=5))

        async def add(a, b):
            return a + b

        result = _run_async(bh.execute(add, 3, 4))
        assert result == 7

    def test_execute_with_kwargs(self):
        bh = Bulkhead(BulkheadConfig(max_concurrent=5))

        async def greet(name="world"):
            return f"hello {name}"

        result = _run_async(bh.execute(greet, name="axion"))
        assert result == "hello axion"


class TestBulkheadFull:
    def test_exception_message(self):
        exc = BulkheadFull("my_bh", 5)
        assert exc.name == "my_bh"
        assert exc.max_concurrent == 5
        assert "my_bh" in str(exc)
        assert "5" in str(exc)


class TestBulkheadRegistry:
    def test_get_or_create(self):
        reg = BulkheadRegistry()
        bh1 = reg.get_or_create("svc_a")
        bh2 = reg.get_or_create("svc_a")
        assert bh1 is bh2

    def test_get_returns_none(self):
        reg = BulkheadRegistry()
        assert reg.get("missing") is None

    def test_remove(self):
        reg = BulkheadRegistry()
        reg.get_or_create("temp")
        assert reg.remove("temp") is True
        assert reg.remove("temp") is False

    def test_get_all_metrics(self):
        reg = BulkheadRegistry()
        reg.get_or_create("a")
        reg.get_or_create("b")
        metrics = reg.get_all_metrics()
        assert "a" in metrics
        assert "b" in metrics

    def test_len(self):
        reg = BulkheadRegistry()
        assert len(reg) == 0
        reg.get_or_create("x")
        assert len(reg) == 1

    def test_custom_config(self):
        reg = BulkheadRegistry()
        cfg = BulkheadConfig(max_concurrent=3, name="custom")
        bh = reg.get_or_create("custom", cfg)
        assert bh.max_concurrent == 3

    def test_names_assigned(self):
        reg = BulkheadRegistry()
        bh = reg.get_or_create("my_svc")
        assert bh.name == "my_svc"

    def test_independent_bulkheads(self):
        reg = BulkheadRegistry()
        bh_a = reg.get_or_create("a", BulkheadConfig(max_concurrent=2))
        bh_b = reg.get_or_create("b", BulkheadConfig(max_concurrent=5))
        assert bh_a.max_concurrent == 2
        assert bh_b.max_concurrent == 5


class TestBulkheadDecorator:
    def test_basic_decorator(self):
        reg = BulkheadRegistry()

        @bulkhead("svc", config=BulkheadConfig(max_concurrent=5), registry=reg)
        async def work():
            return "done"

        result = _run_async(work())
        assert result == "done"
        bh = reg.get("svc")
        assert bh.total_accepted == 1

    def test_decorator_preserves_name(self):
        reg = BulkheadRegistry()

        @bulkhead("svc", registry=reg)
        async def my_function():
            pass

        assert my_function.__name__ == "my_function"

    def test_decorator_exposes_bulkhead(self):
        reg = BulkheadRegistry()

        @bulkhead("svc", registry=reg)
        async def func():
            pass

        assert hasattr(func, "_bulkhead")
        assert isinstance(func._bulkhead, Bulkhead)

    def test_decorator_with_args(self):
        reg = BulkheadRegistry()

        @bulkhead("svc", registry=reg)
        async def add(a, b):
            return a + b

        assert _run_async(add(2, 3)) == 5

    def test_decorator_with_kwargs(self):
        reg = BulkheadRegistry()

        @bulkhead("svc", registry=reg)
        async def greet(name="world"):
            return f"hi {name}"

        assert _run_async(greet(name="test")) == "hi test"

    def test_decorator_rejection(self):
        reg = BulkheadRegistry()

        @bulkhead(
            "tight_svc",
            config=BulkheadConfig(max_concurrent=1, timeout=0.1),
            registry=reg,
        )
        async def slow_work():
            await asyncio.sleep(1.0)

        async def run_test():
            task = asyncio.create_task(slow_work())
            await asyncio.sleep(0.05)
            with pytest.raises(BulkheadFull):
                await slow_work()
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, BulkheadFull):
                pass

        _run_async(run_test())

    def test_decorator_multiple_calls(self):
        reg = BulkheadRegistry()

        @bulkhead("multi", config=BulkheadConfig(max_concurrent=10), registry=reg)
        async def work(n):
            return n * 2

        async def run():
            results = await asyncio.gather(*[work(i) for i in range(5)])
            return results

        results = _run_async(run())
        assert results == [0, 2, 4, 6, 8]

    def test_decorator_error_handling(self):
        reg = BulkheadRegistry()

        @bulkhead("err_svc", registry=reg)
        async def failing():
            raise RuntimeError("fail")

        with pytest.raises(RuntimeError):
            _run_async(failing())

        bh = reg.get("err_svc")
        assert bh.active_count == 0


# ── Integration Tests ────────────────────────────────────────────────


class TestResilienceIntegration:
    def test_circuit_breaker_with_retry(self):
        """Circuit breaker wrapping a retried function."""
        registry = CircuitBreakerRegistry()
        call_count = 0

        @circuit_breaker("integrated", config=CircuitBreakerConfig(failure_threshold=10), registry=registry)
        @retry(max_retries=2, base_delay=0.01, jitter_max=0.0)
        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("fail")
            return "ok"

        result = flaky()
        assert result == "ok"
        assert call_count == 3

    def test_rate_limiter_with_circuit_breaker(self):
        """Rate limiter protecting a circuit breaker."""
        rl = RateLimiter(RateLimiterConfig(rate=100, burst=5))
        cb = CircuitBreaker(CircuitBreakerConfig(failure_threshold=3, name="rl_cb"))

        for _ in range(5):
            if rl.consume():
                cb.call(lambda: "ok")

        assert cb.success_count == 5

    def test_full_stack(self):
        """All patterns working together."""
        rl = RateLimiter(RateLimiterConfig(rate=100, burst=10))
        call_count = 0

        @retry(max_retries=2, base_delay=0.01, jitter_max=0.0)
        def resilient_call():
            nonlocal call_count
            call_count += 1
            if not rl.consume():
                raise ConnectionError("rate limited")
            return "success"

        result = resilient_call()
        assert result == "success"

    def test_module_imports(self):
        """Verify all public API imports work."""
        from src.resilience import (
            CircuitBreaker,
            CircuitBreakerOpen,
            CircuitBreakerRegistry,
            circuit_breaker,
            get_registry,
            MaxRetriesExceeded,
            retry,
            RateLimiter,
            RateLimitExceeded,
            RateLimiterRegistry,
            Bulkhead,
            BulkheadFull,
            BulkheadRegistry,
            bulkhead,
            get_bulkhead_registry,
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
        assert CircuitState.CLOSED.value == "closed"

    def test_global_registry(self):
        from src.resilience import get_registry
        reg = get_registry()
        assert isinstance(reg, CircuitBreakerRegistry)

    def test_global_bulkhead_registry(self):
        from src.resilience import get_bulkhead_registry
        reg = get_bulkhead_registry()
        assert isinstance(reg, BulkheadRegistry)

    def test_async_bulkhead_with_retry(self):
        """Bulkhead wrapping a retried async function."""
        reg = BulkheadRegistry()
        call_count = 0

        @bulkhead("bh_retry", config=BulkheadConfig(max_concurrent=5), registry=reg)
        @retry(max_retries=2, base_delay=0.01, jitter_max=0.0)
        async def flaky_async():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("fail")
            return "recovered"

        result = _run_async(flaky_async())
        assert result == "recovered"

    def test_create_rate_limit_middleware_import(self):
        """Verify middleware factory is importable."""
        from src.resilience import create_rate_limit_middleware
        assert callable(create_rate_limit_middleware)
