"""Retry with exponential backoff.

Provides decorators for retrying failed function calls with
configurable backoff strategies and jitter.
"""

import asyncio
import functools
import logging
import random
import time
from typing import Any, Callable, Optional, Tuple, Type

from .config import RetryConfig, RetryStrategy

logger = logging.getLogger(__name__)


class MaxRetriesExceeded(Exception):
    """Raised when all retry attempts have been exhausted."""

    def __init__(self, attempts: int, last_exception: Exception):
        self.attempts = attempts
        self.last_exception = last_exception
        super().__init__(
            f"Max retries ({attempts}) exceeded. "
            f"Last error: {last_exception}"
        )


def _compute_delay(attempt: int, config: RetryConfig) -> float:
    """Compute the delay for the given attempt number.

    Args:
        attempt: Zero-based attempt index (0 = first retry).
        config: Retry configuration.

    Returns:
        Delay in seconds, capped at max_delay.
    """
    if config.strategy == RetryStrategy.EXPONENTIAL:
        delay = config.base_delay * (2 ** attempt)
    elif config.strategy == RetryStrategy.LINEAR:
        delay = config.base_delay * (attempt + 1)
    else:  # CONSTANT
        delay = config.base_delay

    # Add jitter
    jitter = random.uniform(0, config.jitter_max)
    delay = delay + jitter

    # Cap at max_delay
    return min(delay, config.max_delay)


def retry(
    max_retries: Optional[int] = None,
    base_delay: Optional[float] = None,
    max_delay: Optional[float] = None,
    jitter_max: Optional[float] = None,
    retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
    strategy: Optional[RetryStrategy] = None,
    config: Optional[RetryConfig] = None,
) -> Callable:
    """Decorator that retries a function on failure with backoff.

    Supports both sync and async functions.

    Args:
        max_retries: Maximum number of retry attempts.
        base_delay: Base delay in seconds.
        max_delay: Maximum delay cap in seconds.
        jitter_max: Maximum random jitter to add.
        retryable_exceptions: Tuple of exception types to retry on.
        strategy: Backoff strategy.
        config: Full RetryConfig (overrides individual params).

    Usage:
        @retry(max_retries=3)
        def flaky_call():
            ...

        @retry(retryable_exceptions=(ConnectionError,))
        async def async_flaky():
            ...
    """
    if config is None:
        cfg = RetryConfig()
    else:
        cfg = config

    # Override with explicit params
    if max_retries is not None:
        cfg = RetryConfig(
            max_retries=max_retries,
            base_delay=base_delay if base_delay is not None else cfg.base_delay,
            max_delay=max_delay if max_delay is not None else cfg.max_delay,
            jitter_max=jitter_max if jitter_max is not None else cfg.jitter_max,
            retryable_exceptions=retryable_exceptions if retryable_exceptions is not None else cfg.retryable_exceptions,
            strategy=strategy if strategy is not None else cfg.strategy,
        )
    else:
        if base_delay is not None:
            cfg = RetryConfig(
                max_retries=cfg.max_retries,
                base_delay=base_delay,
                max_delay=max_delay if max_delay is not None else cfg.max_delay,
                jitter_max=jitter_max if jitter_max is not None else cfg.jitter_max,
                retryable_exceptions=retryable_exceptions if retryable_exceptions is not None else cfg.retryable_exceptions,
                strategy=strategy if strategy is not None else cfg.strategy,
            )
        elif any(p is not None for p in [max_delay, jitter_max, retryable_exceptions, strategy]):
            cfg = RetryConfig(
                max_retries=cfg.max_retries,
                base_delay=cfg.base_delay,
                max_delay=max_delay if max_delay is not None else cfg.max_delay,
                jitter_max=jitter_max if jitter_max is not None else cfg.jitter_max,
                retryable_exceptions=retryable_exceptions if retryable_exceptions is not None else cfg.retryable_exceptions,
                strategy=strategy if strategy is not None else cfg.strategy,
            )

    def decorator(func: Callable) -> Callable:
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                last_exc: Optional[Exception] = None
                for attempt in range(cfg.max_retries + 1):
                    try:
                        return await func(*args, **kwargs)
                    except cfg.retryable_exceptions as exc:
                        last_exc = exc
                        if attempt < cfg.max_retries:
                            delay = _compute_delay(attempt, cfg)
                            logger.warning(
                                "Retry %d/%d for %s after %.2fs: %s",
                                attempt + 1,
                                cfg.max_retries,
                                func.__name__,
                                delay,
                                exc,
                            )
                            await asyncio.sleep(delay)
                        else:
                            logger.error(
                                "All %d retries exhausted for %s: %s",
                                cfg.max_retries,
                                func.__name__,
                                exc,
                            )
                raise MaxRetriesExceeded(cfg.max_retries, last_exc)  # type: ignore[arg-type]

            async_wrapper._retry_config = cfg  # type: ignore[attr-defined]
            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                last_exc: Optional[Exception] = None
                for attempt in range(cfg.max_retries + 1):
                    try:
                        return func(*args, **kwargs)
                    except cfg.retryable_exceptions as exc:
                        last_exc = exc
                        if attempt < cfg.max_retries:
                            delay = _compute_delay(attempt, cfg)
                            logger.warning(
                                "Retry %d/%d for %s after %.2fs: %s",
                                attempt + 1,
                                cfg.max_retries,
                                func.__name__,
                                delay,
                                exc,
                            )
                            time.sleep(delay)
                        else:
                            logger.error(
                                "All %d retries exhausted for %s: %s",
                                cfg.max_retries,
                                func.__name__,
                                exc,
                            )
                raise MaxRetriesExceeded(cfg.max_retries, last_exc)  # type: ignore[arg-type]

            sync_wrapper._retry_config = cfg  # type: ignore[attr-defined]
            return sync_wrapper

    return decorator
