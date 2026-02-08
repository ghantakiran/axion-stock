"""Error Handling Middleware & Request Sanitization.

ASGI middleware that catches exceptions and returns structured
error responses. Also provides input sanitization utilities.
"""

import html
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from src.api_errors.config import DEFAULT_ERROR_CONFIG, ErrorCode, ErrorConfig
from src.api_errors.exceptions import AxionAPIError
from src.api_errors.handlers import create_error_response, handle_axion_error, handle_unhandled_error

logger = logging.getLogger(__name__)


# Patterns that may indicate injection attempts
SQL_INJECTION_PATTERNS = [
    r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER)\b.*\b(FROM|INTO|TABLE|SET)\b)",
    r"(--|;|/\*|\*/)",
    r"(\bOR\b\s+\d+\s*=\s*\d+)",
]

XSS_PATTERNS = [
    r"<script[^>]*>",
    r"javascript:",
    r"on\w+\s*=",
]

# Compiled patterns for performance
_SQL_COMPILED = [re.compile(p, re.IGNORECASE) for p in SQL_INJECTION_PATTERNS]
_XSS_COMPILED = [re.compile(p, re.IGNORECASE) for p in XSS_PATTERNS]


def sanitize_string(value: str, max_length: int = 1000) -> str:
    """Sanitize a string input by escaping HTML and truncating.

    Args:
        value: Raw string input.
        max_length: Maximum allowed length.

    Returns:
        Sanitized string.
    """
    if not isinstance(value, str):
        return str(value)[:max_length]

    # HTML-escape to prevent XSS
    sanitized = html.escape(value, quote=True)

    # Truncate to max length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]

    return sanitized


def detect_injection(value: str) -> List[str]:
    """Check a string for potential injection patterns.

    Returns a list of detected threat types (empty if clean).
    """
    threats: List[str] = []

    for pattern in _SQL_COMPILED:
        if pattern.search(value):
            threats.append("sql_injection")
            break

    for pattern in _XSS_COMPILED:
        if pattern.search(value):
            threats.append("xss")
            break

    return threats


@dataclass
class RequestSanitizer:
    """Sanitizes request parameters and detects injection attempts.

    Provides methods to clean query parameters, path parameters,
    and request bodies before they reach route handlers.
    """

    max_string_length: int = 1000
    block_on_injection: bool = True
    allowed_html_tags: Set[str] = field(default_factory=set)

    def sanitize_value(self, value: Any) -> Any:
        """Sanitize a single value."""
        if isinstance(value, str):
            return sanitize_string(value, self.max_string_length)
        elif isinstance(value, dict):
            return self.sanitize_dict(value)
        elif isinstance(value, list):
            return [self.sanitize_value(v) for v in value]
        return value

    def sanitize_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize all string values in a dictionary."""
        return {k: self.sanitize_value(v) for k, v in data.items()}

    def check_for_threats(self, value: str) -> List[str]:
        """Check a string value for injection threats."""
        return detect_injection(value)

    def scan_dict(self, data: Dict[str, Any]) -> Dict[str, List[str]]:
        """Scan all string values in a dictionary for threats.

        Returns a mapping of field names to detected threats.
        """
        threats: Dict[str, List[str]] = {}
        for key, value in data.items():
            if isinstance(value, str):
                found = detect_injection(value)
                if found:
                    threats[key] = found
        return threats


class ErrorHandlingMiddleware:
    """ASGI middleware that catches unhandled exceptions.

    Wraps the application to ensure all errors produce structured
    JSON responses rather than raw stack traces.
    """

    def __init__(self, app: Any, config: Optional[ErrorConfig] = None):
        self.app = app
        self.config = config or DEFAULT_ERROR_CONFIG

    async def __call__(self, scope: Dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start_time = time.perf_counter()

        async def send_wrapper(message: Dict[str, Any]) -> None:
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except AxionAPIError as exc:
            error_response = handle_axion_error(exc, self.config)
            await self._send_error(send, error_response, exc.headers)
        except Exception as exc:
            error_response = handle_unhandled_error(exc, self.config)
            await self._send_error(send, error_response)
        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000
            if duration_ms > 5000:
                path = scope.get("path", "unknown")
                logger.warning(
                    f"Slow request: {path} took {duration_ms:.1f}ms",
                    extra={"duration_ms": round(duration_ms, 2)},
                )

    async def _send_error(
        self,
        send: Any,
        error_response: Any,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        """Send a structured error response over ASGI."""
        import json

        body = json.dumps(error_response.to_dict()).encode("utf-8")
        response_headers = [
            [b"content-type", b"application/json"],
            [b"content-length", str(len(body)).encode()],
        ]
        if headers:
            for key, value in headers.items():
                response_headers.append([key.encode(), value.encode()])

        await send({
            "type": "http.response.start",
            "status": error_response.status_code,
            "headers": response_headers,
        })
        await send({
            "type": "http.response.body",
            "body": body,
        })
