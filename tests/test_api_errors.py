"""Tests for PRD-106: API Error Handling & Validation."""

import json
from datetime import date, timedelta

import pytest

from src.api_errors.config import (
    DEFAULT_ERROR_CONFIG,
    ERROR_SEVERITY_MAP,
    ERROR_STATUS_MAP,
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
    ErrorDetail,
    ErrorResponse,
    create_error_response,
    handle_axion_error,
    handle_unhandled_error,
)
from src.api_errors.middleware import (
    ErrorHandlingMiddleware,
    RequestSanitizer,
    detect_injection,
    sanitize_string,
)
from src.api_errors.validators import (
    validate_date_range,
    validate_pagination,
    validate_quantity,
    validate_symbol,
    validate_symbols_list,
)


class TestErrorConfig:
    """Tests for error configuration."""

    def test_error_code_enum_values(self):
        assert ErrorCode.VALIDATION_ERROR.value == "VALIDATION_ERROR"
        assert ErrorCode.INTERNAL_ERROR.value == "INTERNAL_ERROR"
        assert ErrorCode.RATE_LIMIT_EXCEEDED.value == "RATE_LIMIT_EXCEEDED"

    def test_error_severity_enum(self):
        assert ErrorSeverity.LOW.value == "low"
        assert ErrorSeverity.CRITICAL.value == "critical"

    def test_error_status_map_covers_all_codes(self):
        for code in ErrorCode:
            assert code in ERROR_STATUS_MAP

    def test_error_severity_map_covers_all_codes(self):
        for code in ErrorCode:
            assert code in ERROR_SEVERITY_MAP

    def test_default_config(self):
        config = DEFAULT_ERROR_CONFIG
        assert config.include_request_id is True
        assert config.suppress_internal_details is True
        assert config.log_all_errors is True

    def test_custom_config(self):
        config = ErrorConfig(include_stack_trace=True, suppress_internal_details=False)
        assert config.include_stack_trace is True
        assert config.suppress_internal_details is False

    def test_validation_errors_map_to_400(self):
        for code in (ErrorCode.VALIDATION_ERROR, ErrorCode.INVALID_SYMBOL, ErrorCode.INVALID_DATE_RANGE):
            assert ERROR_STATUS_MAP[code] == 400

    def test_auth_errors_map_to_401(self):
        assert ERROR_STATUS_MAP[ErrorCode.AUTHENTICATION_REQUIRED] == 401
        assert ERROR_STATUS_MAP[ErrorCode.INVALID_TOKEN] == 401

    def test_server_errors_map_to_500(self):
        assert ERROR_STATUS_MAP[ErrorCode.INTERNAL_ERROR] == 500
        assert ERROR_STATUS_MAP[ErrorCode.DATABASE_ERROR] == 500


class TestExceptions:
    """Tests for custom exception hierarchy."""

    def test_axion_api_error_base(self):
        exc = AxionAPIError("test error")
        assert str(exc) == "test error"
        assert exc.status_code == 500
        assert exc.error_code == ErrorCode.INTERNAL_ERROR

    def test_validation_error(self):
        exc = ValidationError("bad input", field="symbol")
        assert exc.status_code == 400
        assert exc.error_code == ErrorCode.VALIDATION_ERROR
        assert len(exc.details) == 1
        assert exc.details[0]["field"] == "symbol"

    def test_authentication_error(self):
        exc = AuthenticationError()
        assert exc.status_code == 401
        assert exc.message == "Authentication required"

    def test_authorization_error(self):
        exc = AuthorizationError()
        assert exc.status_code == 403

    def test_not_found_error(self):
        exc = NotFoundError(resource_type="order", resource_id="123")
        assert exc.status_code == 404
        assert exc.details[0]["resource_type"] == "order"

    def test_conflict_error(self):
        exc = ConflictError("Duplicate order")
        assert exc.status_code == 409

    def test_rate_limit_error(self):
        exc = RateLimitError(retry_after=60)
        assert exc.status_code == 429
        assert exc.headers["Retry-After"] == "60"
        assert exc.retry_after == 60

    def test_service_unavailable_error(self):
        exc = ServiceUnavailableError()
        assert exc.status_code == 503

    def test_exception_inheritance(self):
        exc = ValidationError("test")
        assert isinstance(exc, AxionAPIError)
        assert isinstance(exc, Exception)

    def test_custom_error_code(self):
        exc = ValidationError("bad symbol", error_code=ErrorCode.INVALID_SYMBOL)
        assert exc.error_code == ErrorCode.INVALID_SYMBOL


class TestErrorResponse:
    """Tests for error response formatting."""

    def test_error_response_to_dict(self):
        resp = ErrorResponse(
            code="VALIDATION_ERROR",
            message="bad input",
            status_code=400,
            request_id="abc-123",
        )
        d = resp.to_dict()
        assert d["error"]["code"] == "VALIDATION_ERROR"
        assert d["error"]["message"] == "bad input"
        assert d["error"]["request_id"] == "abc-123"
        assert "timestamp" in d["error"]

    def test_error_response_without_details(self):
        resp = ErrorResponse(code="INTERNAL_ERROR", message="oops")
        d = resp.to_dict()
        assert "details" not in d["error"]

    def test_error_response_with_details(self):
        resp = ErrorResponse(
            code="VALIDATION_ERROR",
            message="bad",
            details=[{"field": "x", "issue": "required"}],
        )
        d = resp.to_dict()
        assert len(d["error"]["details"]) == 1

    def test_error_detail_to_dict(self):
        detail = ErrorDetail(field="symbol", issue="Invalid format")
        d = detail.to_dict()
        assert d["field"] == "symbol"
        assert d["issue"] == "Invalid format"

    def test_create_error_response(self):
        resp = create_error_response(
            ErrorCode.INVALID_SYMBOL,
            "Bad symbol",
            request_id="req-1",
        )
        assert resp.code == "INVALID_SYMBOL"
        assert resp.status_code == 400
        assert resp.request_id == "req-1"


class TestErrorHandlers:
    """Tests for error handler functions."""

    def test_handle_axion_error(self):
        exc = ValidationError("bad data", field="quantity")
        resp = handle_axion_error(exc)
        assert resp.code == "VALIDATION_ERROR"
        assert resp.status_code == 400

    def test_handle_unhandled_error(self):
        exc = RuntimeError("unexpected")
        resp = handle_unhandled_error(exc)
        assert resp.code == "INTERNAL_ERROR"
        assert resp.status_code == 500
        assert "unexpected" not in resp.message  # suppressed by default

    def test_handle_unhandled_error_with_details(self):
        config = ErrorConfig(suppress_internal_details=False)
        exc = ValueError("bad value")
        resp = handle_unhandled_error(exc, config)
        assert "ValueError" in resp.message


class TestSanitization:
    """Tests for input sanitization utilities."""

    def test_sanitize_string_escapes_html(self):
        result = sanitize_string("<script>alert('xss')</script>")
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_sanitize_string_truncates(self):
        result = sanitize_string("a" * 2000, max_length=100)
        assert len(result) == 100

    def test_sanitize_string_normal_input(self):
        result = sanitize_string("hello world")
        assert result == "hello world"

    def test_detect_injection_clean(self):
        threats = detect_injection("AAPL")
        assert threats == []

    def test_detect_injection_sql(self):
        threats = detect_injection("' OR 1=1 --")
        assert "sql_injection" in threats

    def test_detect_injection_xss(self):
        threats = detect_injection("<script>alert(1)</script>")
        assert "xss" in threats

    def test_request_sanitizer_sanitize_dict(self):
        sanitizer = RequestSanitizer()
        data = {"name": "<b>bold</b>", "count": 42}
        result = sanitizer.sanitize_dict(data)
        assert "&lt;b&gt;" in result["name"]
        assert result["count"] == 42

    def test_request_sanitizer_scan_dict(self):
        sanitizer = RequestSanitizer()
        data = {"safe": "hello", "dangerous": "<script>alert(1)</script>"}
        threats = sanitizer.scan_dict(data)
        assert "dangerous" in threats
        assert "safe" not in threats

    def test_request_sanitizer_sanitize_value_list(self):
        sanitizer = RequestSanitizer()
        result = sanitizer.sanitize_value(["<b>a</b>", "normal"])
        assert "&lt;b&gt;" in result[0]
        assert result[1] == "normal"


class TestMiddleware:
    """Tests for ErrorHandlingMiddleware."""

    def test_middleware_init(self):
        mw = ErrorHandlingMiddleware(app=None)
        assert mw.app is None
        assert mw.config.log_all_errors is True

    def test_middleware_custom_config(self):
        config = ErrorConfig(log_all_errors=False)
        mw = ErrorHandlingMiddleware(app=None, config=config)
        assert mw.config.log_all_errors is False


class TestValidateSymbol:
    """Tests for symbol validation."""

    def test_valid_symbol(self):
        assert validate_symbol("AAPL") == "AAPL"

    def test_lowercase_gets_uppercased(self):
        assert validate_symbol("aapl") == "AAPL"

    def test_symbol_with_dots(self):
        assert validate_symbol("BRK.A") == "BRK.A"

    def test_crypto_symbol(self):
        assert validate_symbol("BTC-USD") == "BTC-USD"

    def test_empty_symbol_raises(self):
        with pytest.raises(ValidationError):
            validate_symbol("")

    def test_invalid_symbol_raises(self):
        with pytest.raises(ValidationError):
            validate_symbol("123")

    def test_too_long_symbol_raises(self):
        with pytest.raises(ValidationError):
            validate_symbol("ABCDEFG")

    def test_symbols_list_valid(self):
        result = validate_symbols_list(["AAPL", "MSFT", "GOOGL"])
        assert len(result) == 3

    def test_symbols_list_empty_raises(self):
        with pytest.raises(ValidationError):
            validate_symbols_list([])

    def test_symbols_list_too_many_raises(self):
        with pytest.raises(ValidationError):
            validate_symbols_list(["A"] * 200, max_symbols=100)


class TestValidateDateRange:
    """Tests for date range validation."""

    def test_valid_date_range(self):
        start = date(2024, 1, 1)
        end = date(2024, 6, 30)
        s, e = validate_date_range(start, end)
        assert s == start
        assert e == end

    def test_reversed_range_raises(self):
        with pytest.raises(ValidationError):
            validate_date_range(date(2024, 12, 1), date(2024, 1, 1))

    def test_too_long_range_raises(self):
        start = date(2010, 1, 1)
        end = date(2024, 12, 31)
        with pytest.raises(ValidationError):
            validate_date_range(start, end)

    def test_future_start_raises(self):
        future = date.today() + timedelta(days=30)
        with pytest.raises(ValidationError):
            validate_date_range(future, future + timedelta(days=10))

    def test_none_dates_pass(self):
        s, e = validate_date_range(None, None)
        assert s is None
        assert e is None


class TestValidateQuantity:
    """Tests for quantity validation."""

    def test_valid_quantity(self):
        assert validate_quantity(100) == 100.0

    def test_zero_raises(self):
        with pytest.raises(ValidationError):
            validate_quantity(0)

    def test_negative_raises(self):
        with pytest.raises(ValidationError):
            validate_quantity(-10)

    def test_too_large_raises(self):
        with pytest.raises(ValidationError):
            validate_quantity(2_000_000)

    def test_fractional_allowed(self):
        assert validate_quantity(0.5) == 0.5

    def test_fractional_disallowed(self):
        with pytest.raises(ValidationError):
            validate_quantity(0.5, allow_fractional=False)

    def test_below_min_raises(self):
        with pytest.raises(ValidationError):
            validate_quantity(0.00001, min_quantity=0.001)


class TestValidatePagination:
    """Tests for pagination validation."""

    def test_valid_pagination(self):
        page, size = validate_pagination(1, 50)
        assert page == 1
        assert size == 50

    def test_invalid_page_raises(self):
        with pytest.raises(ValidationError):
            validate_pagination(0, 50)

    def test_invalid_page_size_raises(self):
        with pytest.raises(ValidationError):
            validate_pagination(1, 0)

    def test_too_large_page_size_raises(self):
        with pytest.raises(ValidationError):
            validate_pagination(1, 5000)

    def test_default_pagination(self):
        page, size = validate_pagination()
        assert page == 1
        assert size == 50
