"""Exception Handlers & Error Response Builder.

Provides FastAPI exception handlers and a standardized error
response builder for consistent API error formatting.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.api_errors.config import (
    DEFAULT_ERROR_CONFIG,
    ERROR_SEVERITY_MAP,
    ErrorCode,
    ErrorConfig,
    ErrorSeverity,
)
from src.api_errors.exceptions import AxionAPIError

logger = logging.getLogger(__name__)


@dataclass
class ErrorDetail:
    """A single error detail entry."""

    field: Optional[str] = None
    issue: Optional[str] = None
    value: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {}
        if self.field is not None:
            result["field"] = self.field
        if self.issue is not None:
            result["issue"] = self.issue
        if self.value is not None:
            result["value"] = self.value
        return result


@dataclass
class ErrorResponse:
    """Structured error response envelope."""

    code: str
    message: str
    status_code: int = 500
    details: List[Dict[str, Any]] = field(default_factory=list)
    request_id: Optional[str] = None
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "error": {
                "code": self.code,
                "message": self.message,
                "timestamp": self.timestamp,
            }
        }
        if self.details:
            body["error"]["details"] = self.details
        if self.request_id:
            body["error"]["request_id"] = self.request_id
        return body


def create_error_response(
    error_code: ErrorCode,
    message: str,
    details: Optional[List[Dict[str, Any]]] = None,
    request_id: Optional[str] = None,
    status_code: Optional[int] = None,
) -> ErrorResponse:
    """Build a standardized ErrorResponse from components."""
    from src.api_errors.config import ERROR_STATUS_MAP

    resolved_status = status_code or ERROR_STATUS_MAP.get(error_code, 500)

    return ErrorResponse(
        code=error_code.value,
        message=message,
        status_code=resolved_status,
        details=details or [],
        request_id=request_id,
    )


def _get_request_id() -> str:
    """Try to extract request_id from logging context."""
    try:
        from src.logging_config.context import get_request_id
        return get_request_id()
    except ImportError:
        return ""


def _log_error(
    error_code: ErrorCode,
    message: str,
    status_code: int,
    config: ErrorConfig,
) -> None:
    """Log the error at appropriate severity level."""
    if not config.log_all_errors:
        return

    severity = ERROR_SEVERITY_MAP.get(error_code, ErrorSeverity.MEDIUM)
    log_msg = f"API Error [{error_code.value}] ({status_code}): {message}"

    if severity == ErrorSeverity.CRITICAL:
        logger.critical(log_msg)
    elif severity == ErrorSeverity.HIGH:
        logger.error(log_msg)
    elif severity == ErrorSeverity.MEDIUM:
        logger.warning(log_msg)
    else:
        logger.info(log_msg)


def handle_axion_error(exc: AxionAPIError, config: Optional[ErrorConfig] = None) -> ErrorResponse:
    """Handle an AxionAPIError and produce an ErrorResponse."""
    config = config or DEFAULT_ERROR_CONFIG
    request_id = _get_request_id() if config.include_request_id else None

    _log_error(exc.error_code, exc.message, exc.status_code, config)

    return create_error_response(
        error_code=exc.error_code,
        message=exc.message,
        details=exc.details,
        request_id=request_id,
        status_code=exc.status_code,
    )


def handle_unhandled_error(exc: Exception, config: Optional[ErrorConfig] = None) -> ErrorResponse:
    """Handle any unhandled exception with a safe 500 response."""
    config = config or DEFAULT_ERROR_CONFIG
    request_id = _get_request_id() if config.include_request_id else None

    logger.exception(f"Unhandled exception: {type(exc).__name__}: {exc}")

    message = "An internal error occurred"
    if not config.suppress_internal_details:
        message = f"{type(exc).__name__}: {str(exc)}"

    return create_error_response(
        error_code=ErrorCode.INTERNAL_ERROR,
        message=message,
        request_id=request_id,
    )


def register_exception_handlers(app: Any, config: Optional[ErrorConfig] = None) -> None:
    """Register all exception handlers on a FastAPI application.

    Args:
        app: FastAPI application instance.
        config: Error handling configuration.
    """
    config = config or DEFAULT_ERROR_CONFIG

    # Store config on app for middleware access
    app._error_config = config

    logger.info("Registered Axion API exception handlers")
