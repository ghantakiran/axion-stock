"""PRD-103: Observability & Metrics Export — Metric Decorators."""

import asyncio
import functools
import logging
import time
from typing import Optional

from .registry import MetricsRegistry

logger = logging.getLogger(__name__)


def track_latency(metric_name: str, buckets: Optional[list] = None):
    """Decorator to record function execution time to a histogram metric.

    Supports both sync and async functions.

    Usage:
        @track_latency("my_function_duration_seconds")
        def do_work():
            ...
    """

    def decorator(func):
        registry = MetricsRegistry()
        histogram = registry.histogram(
            name=metric_name,
            description=f"Latency of {func.__qualname__}",
            buckets=buckets,
        )

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                elapsed = time.perf_counter() - start
                histogram.observe(elapsed)

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                return await func(*args, **kwargs)
            finally:
                elapsed = time.perf_counter() - start
                histogram.observe(elapsed)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def count_calls(metric_name: str):
    """Decorator to increment a counter on each function call.

    Supports both sync and async functions.

    Usage:
        @count_calls("my_function_calls_total")
        def do_work():
            ...
    """

    def decorator(func):
        registry = MetricsRegistry()
        counter = registry.counter(
            name=metric_name,
            description=f"Call count for {func.__qualname__}",
        )

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            counter.increment()
            return func(*args, **kwargs)

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            counter.increment()
            return await func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def track_errors(metric_name: str):
    """Decorator to count exceptions by type.

    Supports both sync and async functions. Re-raises the exception
    after incrementing the counter.

    Usage:
        @track_errors("my_function_errors_total")
        def do_work():
            ...
    """

    def decorator(func):
        registry = MetricsRegistry()
        counter = registry.counter(
            name=metric_name,
            description=f"Error count for {func.__qualname__}",
            label_names=("exception_type",),
        )

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                counter.increment(labels={"exception_type": type(e).__name__})
                raise

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                counter.increment(labels={"exception_type": type(e).__name__})
                raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
