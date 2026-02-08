"""Logging Configuration.

Settings for structured logging, log levels, and output formats.
"""

from dataclasses import dataclass, field
from enum import Enum


class LogLevel(str, Enum):
    """Log level options."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogFormat(str, Enum):
    """Log output format."""
    JSON = "json"
    CONSOLE = "console"


@dataclass
class LoggingConfig:
    """Structured logging configuration."""

    level: LogLevel = LogLevel.INFO
    format: LogFormat = LogFormat.JSON
    include_caller: bool = True
    include_timestamp: bool = True
    slow_threshold_ms: float = 1000.0
    log_request_body: bool = False
    log_response_body: bool = False
    exclude_paths: list[str] = field(
        default_factory=lambda: ["/health", "/metrics", "/_stcore/health"]
    )
    date_format: str = "iso"
    service_name: str = "axion"


DEFAULT_LOGGING_CONFIG = LoggingConfig()
