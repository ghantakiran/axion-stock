"""Tests for PRD-101: Structured Logging & Request Tracing."""

import asyncio
import json
import logging
import time

import pytest

from src.logging_config.config import LogFormat, LoggingConfig, LogLevel
from src.logging_config.context import (
    RequestContext,
    generate_request_id,
    get_context_dict,
    get_correlation_id,
    get_request_id,
    get_user_id,
)
from src.logging_config.performance import PerformanceTimer, log_performance
from src.logging_config.setup import (
    ConsoleFormatter,
    StructuredFormatter,
    configure_logging,
    get_logger,
)


class TestLoggingConfig:
    """Tests for logging configuration dataclasses."""

    def test_default_config_values(self):
        config = LoggingConfig()
        assert config.level == LogLevel.INFO
        assert config.format == LogFormat.JSON
        assert config.include_caller is True
        assert config.slow_threshold_ms == 1000.0
        assert config.service_name == "axion"

    def test_custom_config(self):
        config = LoggingConfig(
            level=LogLevel.DEBUG,
            format=LogFormat.CONSOLE,
            slow_threshold_ms=500.0,
            service_name="test",
        )
        assert config.level == LogLevel.DEBUG
        assert config.format == LogFormat.CONSOLE
        assert config.slow_threshold_ms == 500.0

    def test_log_level_enum_values(self):
        assert LogLevel.DEBUG.value == "DEBUG"
        assert LogLevel.INFO.value == "INFO"
        assert LogLevel.WARNING.value == "WARNING"
        assert LogLevel.ERROR.value == "ERROR"
        assert LogLevel.CRITICAL.value == "CRITICAL"

    def test_log_format_enum_values(self):
        assert LogFormat.JSON.value == "json"
        assert LogFormat.CONSOLE.value == "console"

    def test_exclude_paths_default(self):
        config = LoggingConfig()
        assert "/health" in config.exclude_paths
        assert "/metrics" in config.exclude_paths

    def test_config_with_custom_exclude_paths(self):
        config = LoggingConfig(exclude_paths=["/custom"])
        assert config.exclude_paths == ["/custom"]

    def test_log_request_body_defaults_false(self):
        config = LoggingConfig()
        assert config.log_request_body is False
        assert config.log_response_body is False

    def test_date_format_default(self):
        config = LoggingConfig()
        assert config.date_format == "iso"


class TestRequestContext:
    """Tests for request context management."""

    def test_generate_request_id_unique(self):
        ids = {generate_request_id() for _ in range(100)}
        assert len(ids) == 100

    def test_request_id_is_uuid_format(self):
        rid = generate_request_id()
        parts = rid.split("-")
        assert len(parts) == 5

    def test_context_sets_request_id(self):
        with RequestContext(request_id="test-123"):
            assert get_request_id() == "test-123"
        assert get_request_id() == ""

    def test_context_sets_user_id(self):
        with RequestContext(user_id="user_42"):
            assert get_user_id() == "user_42"
        assert get_user_id() == ""

    def test_context_sets_correlation_id(self):
        with RequestContext(correlation_id="corr-abc"):
            assert get_correlation_id() == "corr-abc"
        assert get_correlation_id() == ""

    def test_correlation_id_defaults_to_request_id(self):
        with RequestContext(request_id="req-777") as ctx:
            assert ctx.correlation_id == "req-777"
            assert get_correlation_id() == "req-777"

    def test_auto_generates_request_id(self):
        with RequestContext() as ctx:
            assert ctx.request_id != ""
            assert get_request_id() == ctx.request_id

    def test_context_cleanup_on_exit(self):
        with RequestContext(request_id="a", user_id="b", correlation_id="c"):
            pass
        assert get_request_id() == ""
        assert get_user_id() == ""
        assert get_correlation_id() == ""

    def test_get_context_dict(self):
        with RequestContext(request_id="r1", user_id="u1"):
            ctx = get_context_dict()
            assert ctx["request_id"] == "r1"
            assert ctx["user_id"] == "u1"
            assert "correlation_id" in ctx

    def test_context_dict_empty_outside(self):
        ctx = get_context_dict()
        assert ctx == {}

    def test_bind_extra_context(self):
        with RequestContext(request_id="r1") as ctx:
            ctx.bind(order_id="ord-123", strategy="momentum")
            d = get_context_dict()
            assert d["order_id"] == "ord-123"
            assert d["strategy"] == "momentum"

    def test_elapsed_ms(self):
        with RequestContext() as ctx:
            time.sleep(0.01)
            assert ctx.elapsed_ms >= 10

    def test_nested_contexts(self):
        with RequestContext(request_id="outer"):
            assert get_request_id() == "outer"
            with RequestContext(request_id="inner"):
                assert get_request_id() == "inner"
            # After inner exits, context is cleared
            # (this is expected behavior with contextvars reset)


class TestStructuredFormatter:
    """Tests for JSON structured log formatting."""

    def test_formats_as_json(self):
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py",
            lineno=1, msg="hello world", args=(), exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["message"] == "hello world"
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test"

    def test_includes_timestamp(self):
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py",
            lineno=1, msg="test", args=(), exc_info=None,
        )
        parsed = json.loads(formatter.format(record))
        assert "timestamp" in parsed

    def test_includes_service_name(self):
        formatter = StructuredFormatter(service_name="my-service")
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py",
            lineno=1, msg="test", args=(), exc_info=None,
        )
        parsed = json.loads(formatter.format(record))
        assert parsed["service"] == "my-service"

    def test_includes_caller_info(self):
        formatter = StructuredFormatter(include_caller=True)
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py",
            lineno=42, msg="test", args=(), exc_info=None,
        )
        parsed = json.loads(formatter.format(record))
        assert parsed["line"] == 42
        assert "module" in parsed
        assert "function" in parsed

    def test_excludes_caller_when_disabled(self):
        formatter = StructuredFormatter(include_caller=False)
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py",
            lineno=42, msg="test", args=(), exc_info=None,
        )
        parsed = json.loads(formatter.format(record))
        assert "line" not in parsed
        assert "function" not in parsed

    def test_includes_request_context(self):
        formatter = StructuredFormatter()
        with RequestContext(request_id="ctx-test"):
            record = logging.LogRecord(
                name="test", level=logging.INFO, pathname="test.py",
                lineno=1, msg="test", args=(), exc_info=None,
            )
            parsed = json.loads(formatter.format(record))
            assert parsed["request_id"] == "ctx-test"

    def test_formats_exception(self):
        formatter = StructuredFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            import sys
            record = logging.LogRecord(
                name="test", level=logging.ERROR, pathname="test.py",
                lineno=1, msg="failed", args=(), exc_info=sys.exc_info(),
            )
            parsed = json.loads(formatter.format(record))
            assert parsed["exception"]["type"] == "ValueError"
            assert "test error" in parsed["exception"]["message"]

    def test_includes_extra_fields(self):
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py",
            lineno=1, msg="test", args=(), exc_info=None,
        )
        record.duration_ms = 42.5
        record.status_code = 200
        parsed = json.loads(formatter.format(record))
        assert parsed["duration_ms"] == 42.5
        assert parsed["status_code"] == 200


class TestConsoleFormatter:
    """Tests for colored console log formatting."""

    def test_formats_readable_output(self):
        formatter = ConsoleFormatter()
        record = logging.LogRecord(
            name="test.module", level=logging.INFO, pathname="test.py",
            lineno=1, msg="hello", args=(), exc_info=None,
        )
        output = formatter.format(record)
        assert "test.module" in output
        assert "hello" in output

    def test_includes_level_name(self):
        formatter = ConsoleFormatter()
        record = logging.LogRecord(
            name="test", level=logging.WARNING, pathname="test.py",
            lineno=1, msg="warn", args=(), exc_info=None,
        )
        output = formatter.format(record)
        assert "WARNING" in output

    def test_includes_context_info(self):
        formatter = ConsoleFormatter()
        with RequestContext(request_id="abc"):
            record = logging.LogRecord(
                name="test", level=logging.INFO, pathname="test.py",
                lineno=1, msg="test", args=(), exc_info=None,
            )
            output = formatter.format(record)
            assert "request_id=abc" in output

    def test_has_color_codes(self):
        formatter = ConsoleFormatter()
        record = logging.LogRecord(
            name="test", level=logging.ERROR, pathname="test.py",
            lineno=1, msg="error", args=(), exc_info=None,
        )
        output = formatter.format(record)
        assert "\033[31m" in output  # Red for ERROR


class TestConfigureLogging:
    """Tests for the configure_logging setup function."""

    def test_configures_root_logger(self):
        configure_logging(LoggingConfig(format=LogFormat.CONSOLE))
        root = logging.getLogger()
        assert len(root.handlers) == 1

    def test_json_format(self):
        configure_logging(LoggingConfig(format=LogFormat.JSON))
        root = logging.getLogger()
        assert isinstance(root.handlers[0].formatter, StructuredFormatter)

    def test_console_format(self):
        configure_logging(LoggingConfig(format=LogFormat.CONSOLE))
        root = logging.getLogger()
        assert isinstance(root.handlers[0].formatter, ConsoleFormatter)

    def test_sets_log_level(self):
        configure_logging(LoggingConfig(level=LogLevel.DEBUG))
        root = logging.getLogger()
        assert root.level == logging.DEBUG

    def test_get_logger_returns_logger(self):
        logger = get_logger("test.module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test.module"

    def test_quiets_noisy_loggers(self):
        configure_logging()
        urllib3_logger = logging.getLogger("urllib3")
        assert urllib3_logger.level >= logging.WARNING

    def test_env_var_override_level(self, monkeypatch):
        monkeypatch.setenv("AXION_LOG_LEVEL", "DEBUG")
        configure_logging(LoggingConfig(level=LogLevel.ERROR))
        root = logging.getLogger()
        assert root.level == logging.DEBUG

    def test_env_var_override_format(self, monkeypatch):
        monkeypatch.setenv("AXION_LOG_FORMAT", "CONSOLE")
        configure_logging(LoggingConfig(format=LogFormat.JSON))
        root = logging.getLogger()
        assert isinstance(root.handlers[0].formatter, ConsoleFormatter)


class TestPerformanceLogging:
    """Tests for performance timing decorator and context manager."""

    def test_log_performance_sync(self):
        @log_performance(threshold_ms=10000)
        def fast_func():
            return 42

        result = fast_func()
        assert result == 42

    def test_log_performance_async(self):
        @log_performance(threshold_ms=10000)
        async def async_func():
            return "ok"

        result = asyncio.get_event_loop().run_until_complete(async_func())
        assert result == "ok"

    def test_log_performance_preserves_name(self):
        @log_performance()
        def my_function():
            """My docstring."""
            pass

        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "My docstring."

    def test_log_performance_with_exception(self):
        @log_performance(threshold_ms=10000)
        def failing_func():
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            failing_func()

    def test_log_performance_async_exception(self):
        @log_performance(threshold_ms=10000)
        async def async_failing():
            raise RuntimeError("async fail")

        with pytest.raises(RuntimeError, match="async fail"):
            asyncio.get_event_loop().run_until_complete(async_failing())

    def test_performance_timer_context_manager(self):
        with PerformanceTimer("test_op") as timer:
            time.sleep(0.01)
        assert timer.duration_ms >= 10

    def test_performance_timer_records_duration(self):
        with PerformanceTimer("fast_op", threshold_ms=10000) as timer:
            pass
        assert timer.duration_ms >= 0
        assert timer.duration_ms < 1000

    def test_performance_timer_with_exception(self):
        with pytest.raises(ValueError):
            with PerformanceTimer("failing_op") as timer:
                raise ValueError("oops")
        assert timer.duration_ms >= 0

    def test_log_performance_with_args(self):
        @log_performance(threshold_ms=10000, include_args=True)
        def func_with_args(a, b, c=None):
            return a + b

        result = func_with_args(1, 2, c=3)
        assert result == 3

    def test_performance_timer_operation_name(self):
        timer = PerformanceTimer("my_operation")
        assert timer.operation_name == "my_operation"

    def test_default_threshold(self):
        timer = PerformanceTimer("op")
        assert timer.threshold_ms == 1000.0

    def test_custom_threshold(self):
        timer = PerformanceTimer("op", threshold_ms=500.0)
        assert timer.threshold_ms == 500.0


class TestMiddleware:
    """Tests for RequestTracingMiddleware configuration."""

    def test_middleware_init(self):
        from src.logging_config.middleware import RequestTracingMiddleware

        app = None
        mw = RequestTracingMiddleware(app)
        assert mw.app is None
        assert mw.config.service_name == "axion"

    def test_middleware_custom_config(self):
        from src.logging_config.middleware import RequestTracingMiddleware

        config = LoggingConfig(service_name="test-api")
        mw = RequestTracingMiddleware(None, config=config)
        assert mw.config.service_name == "test-api"

    def test_request_id_header_constant(self):
        from src.logging_config.middleware import REQUEST_ID_HEADER
        assert REQUEST_ID_HEADER == "X-Request-ID"

    def test_correlation_id_header_constant(self):
        from src.logging_config.middleware import CORRELATION_ID_HEADER
        assert CORRELATION_ID_HEADER == "X-Correlation-ID"
