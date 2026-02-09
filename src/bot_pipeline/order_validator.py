"""Order fill validation — prevents ghost positions from unfilled orders.

Validates that an order was actually filled at a reasonable price
before creating a local position. Catches:
- Rejected orders
- Zero-fill quantity
- Zero/negative fill prices
- Partial fills (adjusts quantity)
- Stale fill timestamps
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from src.trade_executor.router import OrderResult

logger = logging.getLogger(__name__)


@dataclass
class FillValidation:
    """Result of validating an order fill.

    Attributes:
        is_valid: Whether the fill is acceptable for position creation.
        adjusted_qty: Actual filled quantity (may differ from requested).
        fill_price: Validated fill price.
        reason: Explanation of validation result.
        warnings: Non-fatal issues detected.
    """

    is_valid: bool
    adjusted_qty: int = 0
    fill_price: float = 0.0
    reason: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "is_valid": self.is_valid,
            "adjusted_qty": self.adjusted_qty,
            "fill_price": round(self.fill_price, 4),
            "reason": self.reason,
            "warnings": self.warnings,
        }


class OrderValidator:
    """Validate order execution results before position creation.

    Prevents creating positions from orders that weren't actually filled.
    This is the key guard against ghost positions — positions tracked
    locally that don't exist at the broker.

    Args:
        max_slippage_pct: Maximum acceptable slippage from expected price.
        max_fill_age_seconds: Maximum age of a fill timestamp before stale.
        allow_partial: Whether to accept partial fills.

    Example:
        validator = OrderValidator()
        result = router.submit_order(order)
        validation = validator.validate_fill(result, expected_qty=100)
        if validation.is_valid:
            create_position(shares=validation.adjusted_qty)
    """

    def __init__(
        self,
        max_slippage_pct: float = 2.0,
        max_fill_age_seconds: float = 300.0,
        allow_partial: bool = True,
    ) -> None:
        self.max_slippage_pct = max_slippage_pct
        self.max_fill_age_seconds = max_fill_age_seconds
        self.allow_partial = allow_partial

    def validate_fill(
        self,
        order_result: OrderResult,
        expected_qty: int,
        expected_price: float = 0.0,
    ) -> FillValidation:
        """Validate that an order was properly filled.

        Args:
            order_result: The result from OrderRouter.submit_order().
            expected_qty: The number of shares we requested.
            expected_price: The price we expected (for slippage check).

        Returns:
            FillValidation with is_valid=True only if safe to create position.
        """
        warnings: list[str] = []

        # 1. Check order status
        if order_result.status == "rejected":
            return FillValidation(
                is_valid=False,
                reason=f"Order rejected by broker: {order_result.rejection_reason or 'unknown'}",
            )

        if order_result.status == "cancelled":
            return FillValidation(
                is_valid=False,
                reason="Order was cancelled",
            )

        if order_result.status == "pending":
            return FillValidation(
                is_valid=False,
                reason="Order still pending — not yet filled",
            )

        # 2. Check fill quantity
        if order_result.filled_qty <= 0:
            return FillValidation(
                is_valid=False,
                reason=f"Zero fill quantity (status={order_result.status})",
            )

        is_partial = (
            order_result.status == "partial"
            or order_result.filled_qty < expected_qty
        )
        if is_partial:
            if not self.allow_partial:
                return FillValidation(
                    is_valid=False,
                    reason=f"Partial fill {order_result.filled_qty}/{expected_qty} — partials disabled",
                )
            fill_ratio = order_result.filled_qty / max(expected_qty, 1)
            if fill_ratio < 0.5:
                warnings.append(
                    f"Low fill ratio: {order_result.filled_qty}/{expected_qty} ({fill_ratio:.0%})"
                )

        # 3. Check fill price
        if order_result.filled_price <= 0:
            return FillValidation(
                is_valid=False,
                reason=f"Invalid fill price: {order_result.filled_price}",
            )

        # 4. Check slippage
        if expected_price > 0:
            slippage_pct = abs(order_result.filled_price - expected_price) / expected_price * 100
            if slippage_pct > self.max_slippage_pct:
                return FillValidation(
                    is_valid=False,
                    reason=(
                        f"Excessive slippage: {slippage_pct:.2f}% "
                        f"(limit: {self.max_slippage_pct}%)"
                    ),
                )
            if slippage_pct > self.max_slippage_pct * 0.5:
                warnings.append(f"Elevated slippage: {slippage_pct:.2f}%")

        # 5. Check fill timestamp freshness
        if hasattr(order_result, "timestamp") and order_result.timestamp:
            age = (datetime.now(timezone.utc) - order_result.timestamp).total_seconds()
            if age > self.max_fill_age_seconds:
                warnings.append(f"Stale fill: {age:.0f}s old")

        return FillValidation(
            is_valid=True,
            adjusted_qty=order_result.filled_qty,
            fill_price=order_result.filled_price,
            reason="Fill validated successfully",
            warnings=warnings,
        )
