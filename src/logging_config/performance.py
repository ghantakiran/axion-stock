"""Performance Logging.

Decorator and utilities for timing function execution
and logging slow operations.
"""

import asyncio
import functools
import logging
import time
from typing import Any, Callable, Optional

from src.logging_config.config import DEFAULT_LOGGING_CONFIG

logger = logging.getLogger(__name__)


def log_performance(
    threshold_ms: Optional[float] = None,
    logger_name: Optional[str] = None,
    include_args: bool = False,
) -> Callable:
    """Decorator that logs function execution time.

    Logs all calls at DEBUG level and slow calls (above threshold) at WARNING.

    Args:
        threshold_ms: Slow operation threshold in milliseconds.
                     Defaults to config.slow_threshold_ms (1000ms).
        logger_name: Custom logger name. Defaults to function's module.
        include_args: Whether to include function arguments in log.

    Example:
        @log_performance(threshold_ms=500)
        def fetch_market_data(symbols):
            ...

        @log_performance()
        async def execute_order(order):
            ...
    """
    if threshold_ms is None:
        threshold_ms = DEFAULT_LOGGING_CONFIG.slow_threshold_ms

    def decorator(func: Callable) -> Callable:
        _logger = logging.getLogger(logger_name or func.__module__)
        func_name = f"{func.__qualname__}"

        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                start = time.perf_counter()
                try:
                    result = await func(*args, **kwargs)
                    return result
                except Exception as exc:
                    duration_ms = (time.perf_counter() - start) * 1000
                    _logger.error(
                        f"{func_name} failed after {duration_ms:.1f}ms: {type(exc).__name__}",
                        extra={"duration_ms": round(duration_ms, 2)},
                    )
                    raise
                finally:
                    duration_ms = (time.perf_counter() - start) * 1000
                    extra = {"duration_ms": round(duration_ms, 2)}

                    if include_args:
                        extra["extra_data"] = _summarize_args(args, kwargs)

                    if duration_ms >= threshold_ms:
                        _logger.warning(
                            f"Slow operation: {func_name} took {duration_ms:.1f}ms",
                            extra=extra,
                        )
                    else:
                        _logger.debug(
                            f"{func_name} completed in {duration_ms:.1f}ms",
                            extra=extra,
                        )
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                start = time.perf_counter()
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as exc:
                    duration_ms = (time.perf_counter() - start) * 1000
                    _logger.error(
                        f"{func_name} failed after {duration_ms:.1f}ms: {type(exc).__name__}",
                        extra={"duration_ms": round(duration_ms, 2)},
                    )
                    raise
                finally:
                    duration_ms = (time.perf_counter() - start) * 1000
                    extra = {"duration_ms": round(duration_ms, 2)}

                    if include_args:
                        extra["extra_data"] = _summarize_args(args, kwargs)

                    if duration_ms >= threshold_ms:
                        _logger.warning(
                            f"Slow operation: {func_name} took {duration_ms:.1f}ms",
                            extra=extra,
                        )
                    else:
                        _logger.debug(
                            f"{func_name} completed in {duration_ms:.1f}ms",
                            extra=extra,
                        )
            return sync_wrapper

    return decorator


def _summarize_args(args: tuple, kwargs: dict, max_len: int = 100) -> str:
    """Create a short summary of function arguments for logging."""
    parts = []
    for i, arg in enumerate(args[:3]):
        rep = repr(arg)
        if len(rep) > max_len:
            rep = rep[:max_len] + "..."
        parts.append(rep)
    if len(args) > 3:
        parts.append(f"... +{len(args) - 3} more args")

    for key, val in list(kwargs.items())[:3]:
        rep = repr(val)
        if len(rep) > max_len:
            rep = rep[:max_len] + "..."
        parts.append(f"{key}={rep}")

    return ", ".join(parts)


class PerformanceTimer:
    """Context manager for timing code blocks.

    Example:
        with PerformanceTimer("db_query") as timer:
            results = db.execute(query)
        print(f"Query took {timer.duration_ms:.1f}ms")
    """

    def __init__(self, operation_name: str, threshold_ms: Optional[float] = None):
        self.operation_name = operation_name
        self.threshold_ms = threshold_ms or DEFAULT_LOGGING_CONFIG.slow_threshold_ms
        self.start_time: float = 0
        self.duration_ms: float = 0

    def __enter__(self) -> "PerformanceTimer":
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.duration_ms = (time.perf_counter() - self.start_time) * 1000

        if exc_type is not None:
            logger.error(
                f"{self.operation_name} failed after {self.duration_ms:.1f}ms: {exc_type.__name__}",
                extra={"duration_ms": round(self.duration_ms, 2)},
            )
        elif self.duration_ms >= self.threshold_ms:
            logger.warning(
                f"Slow operation: {self.operation_name} took {self.duration_ms:.1f}ms",
                extra={"duration_ms": round(self.duration_ms, 2)},
            )
        else:
            logger.debug(
                f"{self.operation_name} completed in {self.duration_ms:.1f}ms",
                extra={"duration_ms": round(self.duration_ms, 2)},
            )
