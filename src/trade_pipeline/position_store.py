"""Position Store — in-memory position tracking with P&L.

Tracks open positions from pipeline executions, calculates unrealized
P&L, and provides portfolio-level summaries. Supports serialization
for persistence across restarts.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


# ═══════════════════════════════════════════════════════════════════════
# Data Models
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class TrackedPosition:
    """A tracked open position.

    Attributes:
        symbol: Ticker symbol.
        qty: Number of shares held (negative for short).
        avg_entry_price: Weighted average entry price.
        current_price: Latest market price.
        side: 'long' or 'short'.
        signal_type: Source signal type that opened this position.
        stop_loss_price: Stop loss level (absolute price).
        target_price: Take profit target (absolute price).
        opened_at: When the position was first opened.
        order_ids: Pipeline order IDs that contributed to this position.
    """

    symbol: str = ""
    qty: float = 0.0
    avg_entry_price: float = 0.0
    current_price: float = 0.0
    side: str = "long"
    signal_type: str = ""
    stop_loss_price: float = 0.0
    target_price: float = 0.0
    opened_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    order_ids: list[str] = field(default_factory=list)

    @property
    def market_value(self) -> float:
        """Current market value of the position."""
        return abs(self.qty) * self.current_price

    @property
    def cost_basis(self) -> float:
        """Total cost of the position."""
        return abs(self.qty) * self.avg_entry_price

    @property
    def unrealized_pnl(self) -> float:
        """Unrealized P&L."""
        if self.side == "long":
            return self.qty * (self.current_price - self.avg_entry_price)
        else:
            return abs(self.qty) * (self.avg_entry_price - self.current_price)

    @property
    def unrealized_pnl_pct(self) -> float:
        """Unrealized P&L as percentage."""
        if self.cost_basis == 0:
            return 0.0
        return self.unrealized_pnl / self.cost_basis * 100.0

    @property
    def hit_stop_loss(self) -> bool:
        """Whether current price has reached the stop loss."""
        if self.stop_loss_price <= 0:
            return False
        if self.side == "long":
            return self.current_price <= self.stop_loss_price
        return self.current_price >= self.stop_loss_price

    @property
    def hit_target(self) -> bool:
        """Whether current price has reached the profit target."""
        if self.target_price <= 0:
            return False
        if self.side == "long":
            return self.current_price >= self.target_price
        return self.current_price <= self.target_price

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "qty": self.qty,
            "avg_entry_price": round(self.avg_entry_price, 4),
            "current_price": round(self.current_price, 4),
            "side": self.side,
            "signal_type": self.signal_type,
            "stop_loss_price": round(self.stop_loss_price, 4),
            "target_price": round(self.target_price, 4),
            "market_value": round(self.market_value, 2),
            "unrealized_pnl": round(self.unrealized_pnl, 2),
            "unrealized_pnl_pct": round(self.unrealized_pnl_pct, 2),
            "opened_at": self.opened_at.isoformat(),
            "order_ids": self.order_ids,
        }

    @classmethod
    def from_dict(cls, data: dict) -> TrackedPosition:
        opened_at = data.get("opened_at", "")
        if isinstance(opened_at, str) and opened_at:
            opened_at = datetime.fromisoformat(opened_at)
        else:
            opened_at = datetime.now(timezone.utc)
        return cls(
            symbol=data.get("symbol", ""),
            qty=float(data.get("qty", 0)),
            avg_entry_price=float(data.get("avg_entry_price", 0)),
            current_price=float(data.get("current_price", 0)),
            side=data.get("side", "long"),
            signal_type=data.get("signal_type", ""),
            stop_loss_price=float(data.get("stop_loss_price", 0)),
            target_price=float(data.get("target_price", 0)),
            opened_at=opened_at,
            order_ids=data.get("order_ids", []),
        )


# ═══════════════════════════════════════════════════════════════════════
# Position Store
# ═══════════════════════════════════════════════════════════════════════


class PositionStore:
    """In-memory store for tracked positions with P&L.

    Manages the lifecycle of positions opened through the pipeline:
    open, update price, add to existing, close (partial or full).
    Provides portfolio-level summaries and serialization.

    Example:
        store = PositionStore()
        store.open_position("AAPL", 100, 185.50, "long", "fusion", "ord123")
        store.update_price("AAPL", 187.00)
        print(store.get("AAPL").unrealized_pnl)  # +150.0
        store.close_position("AAPL")
    """

    def __init__(self) -> None:
        self._positions: dict[str, TrackedPosition] = {}
        self._closed: list[dict[str, Any]] = []

    @property
    def position_count(self) -> int:
        return len(self._positions)

    def open_position(
        self,
        symbol: str,
        qty: float,
        entry_price: float,
        side: str = "long",
        signal_type: str = "",
        order_id: str = "",
        stop_loss_price: float = 0.0,
        target_price: float = 0.0,
    ) -> TrackedPosition:
        """Open a new position or add to an existing one.

        If a position for this symbol already exists, updates the
        average entry price and adds quantity.

        Args:
            symbol: Ticker symbol.
            qty: Shares to add.
            entry_price: Price of this entry.
            side: 'long' or 'short'.
            signal_type: Source signal type.
            order_id: Pipeline order ID.
            stop_loss_price: Stop loss level.
            target_price: Profit target level.

        Returns:
            The new or updated TrackedPosition.
        """
        existing = self._positions.get(symbol)

        if existing:
            # Average into existing position
            total_cost = existing.avg_entry_price * existing.qty + entry_price * qty
            new_qty = existing.qty + qty
            existing.avg_entry_price = total_cost / new_qty if new_qty > 0 else entry_price
            existing.qty = new_qty
            existing.current_price = entry_price
            if order_id:
                existing.order_ids.append(order_id)
            if stop_loss_price > 0:
                existing.stop_loss_price = stop_loss_price
            if target_price > 0:
                existing.target_price = target_price
            return existing

        pos = TrackedPosition(
            symbol=symbol,
            qty=qty,
            avg_entry_price=entry_price,
            current_price=entry_price,
            side=side,
            signal_type=signal_type,
            stop_loss_price=stop_loss_price,
            target_price=target_price,
            order_ids=[order_id] if order_id else [],
        )
        self._positions[symbol] = pos
        return pos

    def close_position(
        self, symbol: str, exit_price: Optional[float] = None
    ) -> Optional[dict[str, Any]]:
        """Close an entire position.

        Args:
            symbol: Ticker to close.
            exit_price: Exit price (uses current_price if not provided).

        Returns:
            Dict with closed position details and realized P&L, or None.
        """
        pos = self._positions.pop(symbol, None)
        if pos is None:
            return None

        price = exit_price if exit_price is not None else pos.current_price
        pos.current_price = price

        closed_record = {
            "symbol": pos.symbol,
            "qty": pos.qty,
            "entry_price": pos.avg_entry_price,
            "exit_price": price,
            "side": pos.side,
            "realized_pnl": pos.unrealized_pnl,
            "realized_pnl_pct": pos.unrealized_pnl_pct,
            "signal_type": pos.signal_type,
            "closed_at": datetime.now(timezone.utc).isoformat(),
        }
        self._closed.append(closed_record)
        return closed_record

    def reduce_position(
        self, symbol: str, qty: float, exit_price: Optional[float] = None
    ) -> Optional[dict[str, Any]]:
        """Partially close a position.

        Args:
            symbol: Ticker symbol.
            qty: Shares to sell.
            exit_price: Exit price.

        Returns:
            Dict with the partial close details, or None.
        """
        pos = self._positions.get(symbol)
        if pos is None:
            return None

        sell_qty = min(qty, pos.qty)
        price = exit_price if exit_price is not None else pos.current_price

        if pos.side == "long":
            realized_pnl = sell_qty * (price - pos.avg_entry_price)
        else:
            realized_pnl = sell_qty * (pos.avg_entry_price - price)

        pos.qty -= sell_qty
        if pos.qty <= 0:
            return self.close_position(symbol, price)

        return {
            "symbol": symbol,
            "qty_sold": sell_qty,
            "remaining_qty": pos.qty,
            "exit_price": price,
            "realized_pnl": round(realized_pnl, 2),
        }

    def get(self, symbol: str) -> Optional[TrackedPosition]:
        """Get a position by symbol."""
        return self._positions.get(symbol)

    def get_all(self) -> list[TrackedPosition]:
        """Get all open positions."""
        return list(self._positions.values())

    def update_price(self, symbol: str, price: float) -> Optional[TrackedPosition]:
        """Update the current market price for a position.

        Args:
            symbol: Ticker symbol.
            price: Latest market price.

        Returns:
            Updated TrackedPosition or None if not found.
        """
        pos = self._positions.get(symbol)
        if pos:
            pos.current_price = price
        return pos

    def update_prices(self, prices: dict[str, float]) -> int:
        """Bulk update prices for multiple positions.

        Args:
            prices: Dict mapping symbol → latest price.

        Returns:
            Number of positions updated.
        """
        updated = 0
        for symbol, price in prices.items():
            if symbol in self._positions:
                self._positions[symbol].current_price = price
                updated += 1
        return updated

    def get_portfolio_summary(self) -> dict[str, Any]:
        """Compute portfolio-level summary.

        Returns:
            Dict with total value, P&L, position count, etc.
        """
        positions = self.get_all()
        total_value = sum(p.market_value for p in positions)
        total_cost = sum(p.cost_basis for p in positions)
        total_pnl = sum(p.unrealized_pnl for p in positions)
        total_realized = sum(c.get("realized_pnl", 0) for c in self._closed)

        return {
            "position_count": len(positions),
            "total_market_value": round(total_value, 2),
            "total_cost_basis": round(total_cost, 2),
            "unrealized_pnl": round(total_pnl, 2),
            "realized_pnl": round(total_realized, 2),
            "closed_count": len(self._closed),
        }

    def get_closed_trades(self) -> list[dict[str, Any]]:
        """Get all closed trade records."""
        return list(self._closed)

    def check_exits(self) -> list[str]:
        """Check all positions for stop loss or target hits.

        Returns:
            List of symbols that have hit their stop or target.
        """
        triggered = []
        for symbol, pos in self._positions.items():
            if pos.hit_stop_loss or pos.hit_target:
                triggered.append(symbol)
        return triggered

    # ── Serialization ───────────────────────────────────────────────

    def to_json(self) -> str:
        """Serialize all positions to JSON."""
        data = {
            "positions": {s: p.to_dict() for s, p in self._positions.items()},
            "closed": self._closed,
        }
        return json.dumps(data)

    @classmethod
    def from_json(cls, json_str: str) -> PositionStore:
        """Restore a PositionStore from JSON."""
        data = json.loads(json_str)
        store = cls()
        for symbol, pos_data in data.get("positions", {}).items():
            store._positions[symbol] = TrackedPosition.from_dict(pos_data)
        store._closed = data.get("closed", [])
        return store
