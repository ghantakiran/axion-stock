"""Logging Setup.

One-call configuration for structured logging across the Axion platform.
Supports JSON output for production and colored console for development.
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Optional

from src.logging_config.config import DEFAULT_LOGGING_CONFIG, LogFormat, LoggingConfig, LogLevel
from src.logging_config.context import get_context_dict


class StructuredFormatter(logging.Formatter):
    """JSON structured log formatter.

    Produces one JSON object per log line with consistent fields:
    timestamp, level, logger, message, plus any bound context.
    """

    def __init__(self, service_name: str = "axion", include_caller: bool = True):
        super().__init__()
        self.service_name = service_name
        self.include_caller = include_caller

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": self.service_name,
        }

        if self.include_caller:
            log_entry["module"] = record.module
            log_entry["function"] = record.funcName
            log_entry["line"] = record.lineno

        # Merge request context (request_id, user_id, etc.)
        ctx = get_context_dict()
        if ctx:
            log_entry.update(ctx)

        # Include exception info if present
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info),
            }

        # Include any extra fields bound to the record
        for key in ("duration_ms", "status_code", "method", "path", "extra_data"):
            if hasattr(record, key):
                log_entry[key] = getattr(record, key)

        return json.dumps(log_entry, default=str)


class ConsoleFormatter(logging.Formatter):
    """Colored console formatter for development.

    Produces human-readable log lines with color-coded levels.
    """

    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.RESET)
        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]

        ctx = get_context_dict()
        ctx_str = ""
        if ctx:
            parts = [f"{k}={v}" for k, v in ctx.items()]
            ctx_str = f" [{', '.join(parts)}]"

        line = (
            f"{color}{timestamp} {record.levelname:8s}{self.RESET} "
            f"{record.name}: {record.getMessage()}{ctx_str}"
        )

        if record.exc_info and record.exc_info[0] is not None:
            line += "\n" + self.formatException(record.exc_info)

        return line


def configure_logging(config: Optional[LoggingConfig] = None) -> None:
    """Configure structured logging for the Axion platform.

    Call once at application startup. Sets up the root logger with
    the appropriate formatter (JSON or console) and log level.

    Args:
        config: Logging configuration. Uses defaults if not provided.
                Log level can be overridden with AXION_LOG_LEVEL env var.
                Log format can be overridden with AXION_LOG_FORMAT env var.
    """
    config = config or DEFAULT_LOGGING_CONFIG

    # Allow env var overrides
    env_level = os.environ.get("AXION_LOG_LEVEL", "").upper()
    if env_level and env_level in LogLevel.__members__:
        config = LoggingConfig(
            level=LogLevel(env_level),
            format=config.format,
            include_caller=config.include_caller,
            slow_threshold_ms=config.slow_threshold_ms,
            service_name=config.service_name,
        )

    env_format = os.environ.get("AXION_LOG_FORMAT", "").lower()
    if env_format and env_format in [f.value for f in LogFormat]:
        config = LoggingConfig(
            level=config.level,
            format=LogFormat(env_format),
            include_caller=config.include_caller,
            slow_threshold_ms=config.slow_threshold_ms,
            service_name=config.service_name,
        )

    # Choose formatter
    if config.format == LogFormat.JSON:
        formatter = StructuredFormatter(
            service_name=config.service_name,
            include_caller=config.include_caller,
        )
    else:
        formatter = ConsoleFormatter()

    # Configure root logger
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, config.level.value))

    # Quiet noisy third-party loggers
    for noisy in ("urllib3", "asyncio", "websockets", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance.

    Convenience wrapper that returns a standard library logger.
    When configure_logging() has been called, all output goes through
    the structured formatter.

    Args:
        name: Logger name, typically __name__.

    Returns:
        Configured logger instance.
    """
    return logging.getLogger(name)
