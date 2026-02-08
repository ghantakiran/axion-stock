"""Input Validation Utilities.

Reusable validators for common trading domain patterns:
stock symbols, date ranges, quantities, and pagination.
"""

import re
from datetime import date, datetime
from typing import List, Optional, Tuple

from src.api_errors.config import ErrorCode
from src.api_errors.exceptions import ValidationError

# Valid US stock symbol: 1-5 uppercase letters (e.g., AAPL, MSFT, BRK.A)
SYMBOL_PATTERN = re.compile(r"^[A-Z]{1,5}(\.[A-Z])?$")

# Valid crypto symbol (e.g., BTC-USD, ETH-USD)
CRYPTO_PATTERN = re.compile(r"^[A-Z]{2,10}-[A-Z]{2,5}$")

# Maximum pagination limits
MAX_PAGE_SIZE = 1000
DEFAULT_PAGE_SIZE = 50


def validate_symbol(symbol: str) -> str:
    """Validate a stock or crypto symbol.

    Args:
        symbol: The symbol string to validate.

    Returns:
        The validated, uppercased symbol.

    Raises:
        ValidationError: If the symbol format is invalid.
    """
    if not symbol or not isinstance(symbol, str):
        raise ValidationError(
            message="Symbol is required",
            error_code=ErrorCode.INVALID_SYMBOL,
            field="symbol",
        )

    symbol = symbol.strip().upper()

    if not SYMBOL_PATTERN.match(symbol) and not CRYPTO_PATTERN.match(symbol):
        raise ValidationError(
            message=f"Invalid symbol format: '{symbol}'. Expected 1-5 uppercase letters (e.g., AAPL) or crypto format (e.g., BTC-USD)",
            error_code=ErrorCode.INVALID_SYMBOL,
            field="symbol",
        )

    return symbol


def validate_symbols_list(
    symbols: List[str],
    max_symbols: int = 100,
) -> List[str]:
    """Validate a list of stock symbols.

    Args:
        symbols: List of symbol strings.
        max_symbols: Maximum number of symbols allowed.

    Returns:
        List of validated symbols.

    Raises:
        ValidationError: If any symbol is invalid or list exceeds max.
    """
    if not symbols:
        raise ValidationError(
            message="At least one symbol is required",
            error_code=ErrorCode.VALIDATION_ERROR,
            field="symbols",
        )

    if len(symbols) > max_symbols:
        raise ValidationError(
            message=f"Too many symbols: {len(symbols)} exceeds maximum of {max_symbols}",
            error_code=ErrorCode.VALIDATION_ERROR,
            field="symbols",
        )

    return [validate_symbol(s) for s in symbols]


def validate_date_range(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    max_days: int = 365 * 5,
) -> Tuple[Optional[date], Optional[date]]:
    """Validate a date range.

    Args:
        start_date: Start of the date range.
        end_date: End of the date range.
        max_days: Maximum allowed range in days.

    Returns:
        Tuple of (start_date, end_date).

    Raises:
        ValidationError: If the date range is invalid.
    """
    if start_date and end_date:
        if start_date > end_date:
            raise ValidationError(
                message=f"start_date ({start_date}) must be before end_date ({end_date})",
                error_code=ErrorCode.INVALID_DATE_RANGE,
                details=[
                    {"field": "start_date", "issue": "Must be before end_date"},
                ],
            )

        delta = (end_date - start_date).days
        if delta > max_days:
            raise ValidationError(
                message=f"Date range of {delta} days exceeds maximum of {max_days} days",
                error_code=ErrorCode.INVALID_DATE_RANGE,
                field="date_range",
            )

    today = date.today()
    if end_date and end_date > today:
        # Allow future dates for forward-looking queries but warn
        pass

    if start_date and start_date > today:
        raise ValidationError(
            message="start_date cannot be in the future",
            error_code=ErrorCode.INVALID_DATE_RANGE,
            field="start_date",
        )

    return start_date, end_date


def validate_quantity(
    quantity: float,
    min_quantity: float = 0.0001,
    max_quantity: float = 1_000_000,
    allow_fractional: bool = True,
) -> float:
    """Validate an order quantity.

    Args:
        quantity: The quantity to validate.
        min_quantity: Minimum allowed quantity.
        max_quantity: Maximum allowed quantity.
        allow_fractional: Whether fractional shares are allowed.

    Returns:
        The validated quantity.

    Raises:
        ValidationError: If the quantity is invalid.
    """
    if not isinstance(quantity, (int, float)):
        raise ValidationError(
            message="Quantity must be a number",
            error_code=ErrorCode.INVALID_QUANTITY,
            field="quantity",
        )

    if quantity <= 0:
        raise ValidationError(
            message="Quantity must be positive",
            error_code=ErrorCode.INVALID_QUANTITY,
            field="quantity",
        )

    if quantity < min_quantity:
        raise ValidationError(
            message=f"Quantity {quantity} is below minimum of {min_quantity}",
            error_code=ErrorCode.INVALID_QUANTITY,
            field="quantity",
        )

    if quantity > max_quantity:
        raise ValidationError(
            message=f"Quantity {quantity} exceeds maximum of {max_quantity}",
            error_code=ErrorCode.INVALID_QUANTITY,
            field="quantity",
        )

    if not allow_fractional and quantity != int(quantity):
        raise ValidationError(
            message="Fractional quantities are not allowed",
            error_code=ErrorCode.INVALID_QUANTITY,
            field="quantity",
        )

    return float(quantity)


def validate_pagination(
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    max_page_size: int = MAX_PAGE_SIZE,
) -> Tuple[int, int]:
    """Validate pagination parameters.

    Args:
        page: Page number (1-indexed).
        page_size: Number of items per page.
        max_page_size: Maximum allowed page size.

    Returns:
        Tuple of (page, page_size).

    Raises:
        ValidationError: If pagination parameters are invalid.
    """
    if not isinstance(page, int) or page < 1:
        raise ValidationError(
            message="Page must be a positive integer",
            error_code=ErrorCode.INVALID_PAGINATION,
            field="page",
        )

    if not isinstance(page_size, int) or page_size < 1:
        raise ValidationError(
            message="Page size must be a positive integer",
            error_code=ErrorCode.INVALID_PAGINATION,
            field="page_size",
        )

    if page_size > max_page_size:
        raise ValidationError(
            message=f"Page size {page_size} exceeds maximum of {max_page_size}",
            error_code=ErrorCode.INVALID_PAGINATION,
            field="page_size",
        )

    return page, page_size
