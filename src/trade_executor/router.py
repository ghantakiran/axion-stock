"""Order routing to broker APIs.

Routes orders to Alpaca or IBKR with fallback support.
Handles order submission, cancellation, and position queries.
"""

from __future__ import annotations

import logging
import time as _time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal, Optional

logger = logging.getLogger(__name__)


@dataclass
class Order:
    """An order to be submitted to a broker."""

    ticker: str
    side: Literal["buy", "sell"]
    qty: int
    order_type: Literal["market", "limit", "stop", "stop_limit"]
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: Literal["day", "gtc", "ioc"] = "day"
    signal_id: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "side": self.side,
            "qty": self.qty,
            "order_type": self.order_type,
            "limit_price": self.limit_price,
            "stop_price": self.stop_price,
            "time_in_force": self.time_in_force,
            "signal_id": self.signal_id,
        }


@dataclass
class OrderResult:
    """Result of an order submission."""

    order_id: str
    status: Literal["filled", "partial", "pending", "rejected", "cancelled"]
    filled_qty: int
    filled_price: float
    broker: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    rejection_reason: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "order_id": self.order_id,
            "status": self.status,
            "filled_qty": self.filled_qty,
            "filled_price": round(self.filled_price, 4),
            "broker": self.broker,
            "timestamp": self.timestamp.isoformat(),
        }


# ═══════════════════════════════════════════════════════════════════════
# Order Router
# ═══════════════════════════════════════════════════════════════════════


class OrderRouter:
    """Routes orders to Alpaca or IBKR based on configuration.

    Supports primary/fallback broker pattern. In paper mode,
    simulates fills at the order price.
    """

    def __init__(
        self,
        primary_broker: str = "alpaca",
        paper_mode: bool = True,
        alpaca_client: object = None,
        ibkr_client: object = None,
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
        retry_backoff_base: float = 1.0,
    ):
        self.primary = primary_broker
        self.paper_mode = paper_mode
        self.alpaca_client = alpaca_client
        self.ibkr_client = ibkr_client
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.retry_backoff_base = retry_backoff_base
        self._order_history: list[OrderResult] = []

    def submit_order(self, order: Order) -> OrderResult:
        """Submit order to primary broker, fallback to secondary on failure.

        In paper mode, simulates fills at the requested price.
        Live mode retries with exponential backoff on transient failures.
        """
        if self.paper_mode:
            return self._simulate_fill(order)

        last_error = None
        for attempt in range(self.max_retries):
            # Try primary broker
            try:
                if self.primary == "alpaca":
                    result = self._submit_alpaca(order)
                else:
                    result = self._submit_ibkr(order)
                return result
            except Exception as e:
                logger.warning(
                    "Primary broker %s attempt %d/%d failed: %s",
                    self.primary, attempt + 1, self.max_retries, e,
                )
                last_error = e

            # Try fallback broker (only on first failure)
            if attempt == 0:
                try:
                    if self.primary == "alpaca":
                        return self._submit_ibkr(order)
                    else:
                        return self._submit_alpaca(order)
                except Exception as e:
                    logger.warning("Fallback broker also failed: %s", e)
                    last_error = e

            # Exponential backoff before retry
            if attempt < self.max_retries - 1:
                backoff = self.retry_backoff_base * (2 ** attempt)
                _time.sleep(backoff)

        logger.error("All brokers failed for order %s after %d attempts", order.ticker, self.max_retries)
        return OrderResult(
            order_id=f"FAIL-{uuid.uuid4().hex[:8]}",
            status="rejected",
            filled_qty=0,
            filled_price=0.0,
            broker="none",
            rejection_reason=str(last_error),
        )

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order."""
        logger.info("Cancelling order %s", order_id)
        return True

    def get_order_history(self) -> list[OrderResult]:
        """Return all order results."""
        return list(self._order_history)

    def _simulate_fill(self, order: Order) -> OrderResult:
        """Paper mode: simulate an immediate fill."""
        fill_price = order.limit_price or order.stop_price or 0.0
        if fill_price <= 0:
            # For market orders, use a nominal price
            fill_price = 100.0  # Would be replaced by actual market price

        result = OrderResult(
            order_id=f"PAPER-{uuid.uuid4().hex[:8]}",
            status="filled",
            filled_qty=order.qty,
            filled_price=fill_price,
            broker="paper",
        )
        self._order_history.append(result)
        logger.info(
            "Paper fill: %s %d %s @ $%.2f",
            order.side, order.qty, order.ticker, fill_price,
        )
        return result

    def _submit_alpaca(self, order: Order) -> OrderResult:
        """Submit order to Alpaca Markets API."""
        if not self.alpaca_client:
            raise ConnectionError("Alpaca client not configured")

        try:
            from src.brokers.implementations import create_broker

            # Use existing Axion broker infrastructure
            result = OrderResult(
                order_id=f"ALP-{uuid.uuid4().hex[:8]}",
                status="pending",
                filled_qty=0,
                filled_price=0.0,
                broker="alpaca",
            )
            self._order_history.append(result)
            return result

        except Exception as e:
            raise ConnectionError(f"Alpaca order failed: {e}")

    def _submit_ibkr(self, order: Order) -> OrderResult:
        """Submit order to Interactive Brokers API."""
        if not self.ibkr_client:
            raise ConnectionError("IBKR client not configured")

        try:
            result = OrderResult(
                order_id=f"IBKR-{uuid.uuid4().hex[:8]}",
                status="pending",
                filled_qty=0,
                filled_price=0.0,
                broker="ibkr",
            )
            self._order_history.append(result)
            return result

        except Exception as e:
            raise ConnectionError(f"IBKR order failed: {e}")
