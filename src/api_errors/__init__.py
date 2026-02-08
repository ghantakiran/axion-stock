"""API Error Handling & Validation (PRD-106).

Provides structured error responses, global exception handlers,
input validation utilities, and request sanitization for the
Axion FastAPI API layer.
"""

from src.api_errors.config import (
    ErrorCode,
    ErrorConfig,
    ErrorSeverity,
)
from src.api_errors.exceptions import (
    AuthenticationError,
    AuthorizationError,
    AxionAPIError,
    ConflictError,
    NotFoundError,
    RateLimitError,
    ServiceUnavailableError,
    ValidationError,
)
from src.api_errors.handlers import (
    ErrorResponse,
    ErrorDetail,
    create_error_response,
    register_exception_handlers,
)
from src.api_errors.middleware import (
    ErrorHandlingMiddleware,
    RequestSanitizer,
    sanitize_string,
)
from src.api_errors.validators import (
    validate_date_range,
    validate_pagination,
    validate_quantity,
    validate_symbol,
    validate_symbols_list,
)

__all__ = [
    # Config
    "ErrorCode",
    "ErrorConfig",
    "ErrorSeverity",
    # Exceptions
    "AuthenticationError",
    "AuthorizationError",
    "AxionAPIError",
    "ConflictError",
    "NotFoundError",
    "RateLimitError",
    "ServiceUnavailableError",
    "ValidationError",
    # Handlers
    "ErrorResponse",
    "ErrorDetail",
    "create_error_response",
    "register_exception_handlers",
    # Middleware
    "ErrorHandlingMiddleware",
    "RequestSanitizer",
    "sanitize_string",
    # Validators
    "validate_date_range",
    "validate_pagination",
    "validate_quantity",
    "validate_symbol",
    "validate_symbols_list",
]
