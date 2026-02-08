"""API Error Configuration.

Defines error codes, severity levels, and configuration for
structured error handling across the Axion API.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List


class ErrorCode(Enum):
    """Standardized error codes for API responses."""

    # Validation errors (400)
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_SYMBOL = "INVALID_SYMBOL"
    INVALID_DATE_RANGE = "INVALID_DATE_RANGE"
    INVALID_QUANTITY = "INVALID_QUANTITY"
    INVALID_PAGINATION = "INVALID_PAGINATION"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"

    # Authentication errors (401)
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    INVALID_TOKEN = "INVALID_TOKEN"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"

    # Authorization errors (403)
    INSUFFICIENT_PERMISSIONS = "INSUFFICIENT_PERMISSIONS"
    ACCOUNT_SUSPENDED = "ACCOUNT_SUSPENDED"

    # Not found errors (404)
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    SYMBOL_NOT_FOUND = "SYMBOL_NOT_FOUND"
    ORDER_NOT_FOUND = "ORDER_NOT_FOUND"

    # Conflict errors (409)
    DUPLICATE_ORDER = "DUPLICATE_ORDER"
    RESOURCE_CONFLICT = "RESOURCE_CONFLICT"

    # Rate limit errors (429)
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"

    # Server errors (500)
    INTERNAL_ERROR = "INTERNAL_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    BROKER_ERROR = "BROKER_ERROR"

    # Service unavailable (503)
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    MARKET_CLOSED = "MARKET_CLOSED"


class ErrorSeverity(Enum):
    """Severity levels for error logging."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# Map error codes to HTTP status codes
ERROR_STATUS_MAP: Dict[ErrorCode, int] = {
    ErrorCode.VALIDATION_ERROR: 400,
    ErrorCode.INVALID_SYMBOL: 400,
    ErrorCode.INVALID_DATE_RANGE: 400,
    ErrorCode.INVALID_QUANTITY: 400,
    ErrorCode.INVALID_PAGINATION: 400,
    ErrorCode.MISSING_REQUIRED_FIELD: 400,
    ErrorCode.AUTHENTICATION_REQUIRED: 401,
    ErrorCode.INVALID_TOKEN: 401,
    ErrorCode.TOKEN_EXPIRED: 401,
    ErrorCode.INSUFFICIENT_PERMISSIONS: 403,
    ErrorCode.ACCOUNT_SUSPENDED: 403,
    ErrorCode.RESOURCE_NOT_FOUND: 404,
    ErrorCode.SYMBOL_NOT_FOUND: 404,
    ErrorCode.ORDER_NOT_FOUND: 404,
    ErrorCode.DUPLICATE_ORDER: 409,
    ErrorCode.RESOURCE_CONFLICT: 409,
    ErrorCode.RATE_LIMIT_EXCEEDED: 429,
    ErrorCode.INTERNAL_ERROR: 500,
    ErrorCode.DATABASE_ERROR: 500,
    ErrorCode.BROKER_ERROR: 500,
    ErrorCode.SERVICE_UNAVAILABLE: 503,
    ErrorCode.MARKET_CLOSED: 503,
}

# Map error codes to severity
ERROR_SEVERITY_MAP: Dict[ErrorCode, ErrorSeverity] = {
    ErrorCode.VALIDATION_ERROR: ErrorSeverity.LOW,
    ErrorCode.INVALID_SYMBOL: ErrorSeverity.LOW,
    ErrorCode.INVALID_DATE_RANGE: ErrorSeverity.LOW,
    ErrorCode.INVALID_QUANTITY: ErrorSeverity.LOW,
    ErrorCode.INVALID_PAGINATION: ErrorSeverity.LOW,
    ErrorCode.MISSING_REQUIRED_FIELD: ErrorSeverity.LOW,
    ErrorCode.AUTHENTICATION_REQUIRED: ErrorSeverity.MEDIUM,
    ErrorCode.INVALID_TOKEN: ErrorSeverity.MEDIUM,
    ErrorCode.TOKEN_EXPIRED: ErrorSeverity.LOW,
    ErrorCode.INSUFFICIENT_PERMISSIONS: ErrorSeverity.MEDIUM,
    ErrorCode.ACCOUNT_SUSPENDED: ErrorSeverity.HIGH,
    ErrorCode.RESOURCE_NOT_FOUND: ErrorSeverity.LOW,
    ErrorCode.SYMBOL_NOT_FOUND: ErrorSeverity.LOW,
    ErrorCode.ORDER_NOT_FOUND: ErrorSeverity.MEDIUM,
    ErrorCode.DUPLICATE_ORDER: ErrorSeverity.MEDIUM,
    ErrorCode.RESOURCE_CONFLICT: ErrorSeverity.MEDIUM,
    ErrorCode.RATE_LIMIT_EXCEEDED: ErrorSeverity.MEDIUM,
    ErrorCode.INTERNAL_ERROR: ErrorSeverity.CRITICAL,
    ErrorCode.DATABASE_ERROR: ErrorSeverity.CRITICAL,
    ErrorCode.BROKER_ERROR: ErrorSeverity.HIGH,
    ErrorCode.SERVICE_UNAVAILABLE: ErrorSeverity.HIGH,
    ErrorCode.MARKET_CLOSED: ErrorSeverity.LOW,
}


@dataclass
class ErrorConfig:
    """Configuration for API error handling."""

    include_stack_trace: bool = False
    include_request_id: bool = True
    log_all_errors: bool = True
    log_request_body_on_error: bool = False
    max_error_detail_length: int = 1000
    suppress_internal_details: bool = True
    error_rate_threshold: float = 0.05
    custom_error_messages: Dict[str, str] = field(default_factory=dict)


DEFAULT_ERROR_CONFIG = ErrorConfig()
