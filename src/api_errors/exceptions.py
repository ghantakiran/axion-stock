"""Custom Exception Hierarchy.

Defines typed exceptions that map to specific HTTP status codes
and error codes for consistent API error responses.
"""

from typing import Any, Dict, List, Optional

from src.api_errors.config import ErrorCode, ERROR_STATUS_MAP


class AxionAPIError(Exception):
    """Base exception for all Axion API errors.

    All custom API exceptions inherit from this, allowing a single
    exception handler to catch the entire hierarchy.
    """

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.INTERNAL_ERROR,
        details: Optional[List[Dict[str, Any]]] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = ERROR_STATUS_MAP.get(error_code, 500)
        self.details = details or []
        self.headers = headers or {}


class ValidationError(AxionAPIError):
    """Raised when request input fails validation."""

    def __init__(
        self,
        message: str = "Validation failed",
        error_code: ErrorCode = ErrorCode.VALIDATION_ERROR,
        details: Optional[List[Dict[str, Any]]] = None,
        field: Optional[str] = None,
    ):
        if field and not details:
            details = [{"field": field, "issue": message}]
        super().__init__(message, error_code, details)


class AuthenticationError(AxionAPIError):
    """Raised when authentication fails or is missing."""

    def __init__(
        self,
        message: str = "Authentication required",
        error_code: ErrorCode = ErrorCode.AUTHENTICATION_REQUIRED,
    ):
        super().__init__(message, error_code)


class AuthorizationError(AxionAPIError):
    """Raised when the user lacks required permissions."""

    def __init__(
        self,
        message: str = "Insufficient permissions",
        error_code: ErrorCode = ErrorCode.INSUFFICIENT_PERMISSIONS,
    ):
        super().__init__(message, error_code)


class NotFoundError(AxionAPIError):
    """Raised when a requested resource does not exist."""

    def __init__(
        self,
        message: str = "Resource not found",
        error_code: ErrorCode = ErrorCode.RESOURCE_NOT_FOUND,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
    ):
        details = []
        if resource_type or resource_id:
            details = [{"resource_type": resource_type, "resource_id": resource_id}]
        super().__init__(message, error_code, details)


class ConflictError(AxionAPIError):
    """Raised when an action conflicts with existing state."""

    def __init__(
        self,
        message: str = "Resource conflict",
        error_code: ErrorCode = ErrorCode.RESOURCE_CONFLICT,
    ):
        super().__init__(message, error_code)


class RateLimitError(AxionAPIError):
    """Raised when rate limit is exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: Optional[int] = None,
    ):
        headers = {}
        if retry_after is not None:
            headers["Retry-After"] = str(retry_after)
        super().__init__(
            message,
            ErrorCode.RATE_LIMIT_EXCEEDED,
            headers=headers,
        )
        self.retry_after = retry_after


class ServiceUnavailableError(AxionAPIError):
    """Raised when a dependent service is unavailable."""

    def __init__(
        self,
        message: str = "Service temporarily unavailable",
        error_code: ErrorCode = ErrorCode.SERVICE_UNAVAILABLE,
    ):
        super().__init__(message, error_code)
