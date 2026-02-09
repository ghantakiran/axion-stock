"""Leveraged ETF scalping engine.

Alternative to options scalping using 3x leveraged ETFs
for equivalent directional exposure without options complexity.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, Optional

from src.ema_signals.detector import TradeSignal
from src.trade_executor.instrument_router import (
    LEVERAGED_ETF_CATALOG,
    TICKER_SECTOR_MAP,
    ETFSelection,
)
from src.trade_executor.router import Order, OrderResult, OrderRouter

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# Data Models
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class ETFScalpPosition:
    """An open leveraged ETF scalp position."""

    ticker: str
    original_signal_ticker: str
    leverage: float
    direction: Literal["long", "short"]
    shares: int
    entry_price: float
    current_price: float
    stop_loss: float
    target_price: float
    entry_time: datetime
    signal_id: str = ""

    @property
    def unrealized_pnl(self) -> float:
        mult = 1 if self.direction == "long" else -1
        return mult * (self.current_price - self.entry_price) * self.shares

    @property
    def unrealized_pnl_pct(self) -> float:
        if self.entry_price <= 0:
            return 0.0
        mult = 1 if self.direction == "long" else -1
        return mult * (self.current_price - self.entry_price) / self.entry_price

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "original_signal_ticker": self.original_signal_ticker,
            "leverage": self.leverage,
            "direction": self.direction,
            "shares": self.shares,
            "entry_price": round(self.entry_price, 2),
            "current_price": round(self.current_price, 2),
            "pnl": round(self.unrealized_pnl, 2),
            "pnl_pct": round(self.unrealized_pnl_pct, 4),
            "stop_loss": round(self.stop_loss, 2),
            "target_price": round(self.target_price, 2),
        }


@dataclass
class ETFScalpResult:
    """Result of an ETF scalp attempt."""

    success: bool
    position: Optional[ETFScalpPosition] = None
    order_result: Optional[OrderResult] = None
    rejection_reason: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "rejection_reason": self.rejection_reason,
            "position": self.position.to_dict() if self.position else None,
        }


# ═══════════════════════════════════════════════════════════════════════
# ETF Scalp Sizer
# ═══════════════════════════════════════════════════════════════════════


class ETFScalpSizer:
    """Position sizing for leveraged ETF scalps.

    - Max risk per scalp: 3% of equity
    - Stop loss: 2% of ETF price
    - Target: 1-3% of ETF price
    - Max 5 concurrent ETF scalps
    """

    def __init__(self, config):
        self.config = config

    def calculate(
        self,
        etf_price: float,
        leverage: float,
        conviction: int,
        account_equity: float,
    ) -> int:
        """Calculate number of shares for an ETF scalp."""
        if etf_price <= 0 or account_equity <= 0:
            return 0

        risk_budget = account_equity * self.config.etf_max_risk_per_scalp
        risk_per_share = etf_price * self.config.etf_stop_loss_pct

        if risk_per_share <= 0:
            return 0

        raw_shares = risk_budget / risk_per_share

        # Conviction multiplier
        if conviction >= 75:
            mult = 1.0
        else:
            mult = 0.5

        shares = int(raw_shares * mult)
        return max(shares, 1) if raw_shares >= 0.5 else 0

    def compute_stop_target(
        self, entry_price: float, direction: str
    ) -> tuple[float, float]:
        """Compute stop loss and target price."""
        stop_dist = entry_price * self.config.etf_stop_loss_pct
        target_dist = entry_price * self.config.etf_profit_target_pct

        if direction == "long":
            stop = entry_price - stop_dist
            target = entry_price + target_dist
        else:
            stop = entry_price + stop_dist
            target = entry_price - target_dist

        return round(stop, 2), round(target, 2)


# ═══════════════════════════════════════════════════════════════════════
# ETF Scalper
# ═══════════════════════════════════════════════════════════════════════


class ETFScalper:
    """Leveraged ETF scalping as an alternative to options scalping.

    Uses the same EMA cloud signals on 1-min charts but trades
    leveraged ETFs instead of options contracts.
    """

    def __init__(self, config=None, router: Optional[OrderRouter] = None):
        from src.options_scalper.scalper import ScalpConfig
        self.config = config or ScalpConfig()
        self.router = router or OrderRouter(paper_mode=True)
        self.sizer = ETFScalpSizer(self.config)
        self.positions: list[ETFScalpPosition] = []
        self.closed_trades: list[dict] = []

    def process_signal(
        self,
        signal: TradeSignal,
        account_equity: float = 100_000.0,
    ) -> ETFScalpResult:
        """Convert EMA signal to leveraged ETF order."""
        if signal.conviction < self.config.min_conviction_to_scalp:
            return ETFScalpResult(
                success=False,
                rejection_reason=f"Conviction {signal.conviction} below minimum {self.config.min_conviction_to_scalp}",
            )

        if len(self.positions) >= self.config.etf_max_concurrent_scalps:
            return ETFScalpResult(
                success=False,
                rejection_reason="Max concurrent ETF scalps reached",
            )

        # Map ticker to ETF
        etf_ticker, leverage, is_inverse = self._map_ticker_to_etf(
            signal.ticker, signal.direction
        )
        if not etf_ticker:
            return ETFScalpResult(
                success=False,
                rejection_reason=f"No leveraged ETF mapping for {signal.ticker}",
            )

        # Size position
        etf_price = signal.entry_price  # Proxy; real price fetched at order time
        shares = self.sizer.calculate(etf_price, leverage, signal.conviction, account_equity)
        if shares <= 0:
            return ETFScalpResult(success=False, rejection_reason="Position size too small")

        # Compute stop/target
        stop_loss, target_price = self.sizer.compute_stop_target(
            etf_price, "long"  # Always buy bull ETF or inverse ETF (long direction)
        )

        # Submit order
        order = Order(
            ticker=etf_ticker,
            side="buy",
            qty=shares,
            order_type="market",
            signal_id=signal.metadata.get("signal_id", ""),
        )
        order_result = self.router.submit_order(order)

        if order_result.status == "rejected":
            return ETFScalpResult(
                success=False,
                order_result=order_result,
                rejection_reason=order_result.rejection_reason,
            )

        fill_price = order_result.filled_price or etf_price

        position = ETFScalpPosition(
            ticker=etf_ticker,
            original_signal_ticker=signal.ticker,
            leverage=leverage,
            direction="long",
            shares=shares,
            entry_price=fill_price,
            current_price=fill_price,
            stop_loss=stop_loss,
            target_price=target_price,
            entry_time=datetime.now(timezone.utc),
            signal_id=signal.metadata.get("signal_id", ""),
        )

        self.positions.append(position)
        logger.info(
            "ETF scalp opened: %s %d shares @ $%.2f (signal: %s %s)",
            etf_ticker, shares, fill_price, signal.direction, signal.ticker,
        )
        return ETFScalpResult(success=True, position=position, order_result=order_result)

    def check_exits(self) -> list[dict]:
        """Check all open ETF scalp positions for exit conditions."""
        exits = []
        for pos in list(self.positions):
            reason = self._check_exit(pos)
            if reason:
                exits.append({"position": pos, "reason": reason})
                self._close_position(pos, reason)
        return exits

    def _check_exit(self, pos: ETFScalpPosition) -> Optional[str]:
        """Check exit conditions for an ETF scalp."""
        if pos.direction == "long":
            if pos.current_price <= pos.stop_loss:
                return "stop_loss"
            if pos.current_price >= pos.target_price:
                return "profit_target"
        else:
            if pos.current_price >= pos.stop_loss:
                return "stop_loss"
            if pos.current_price <= pos.target_price:
                return "profit_target"
        return None

    def _close_position(self, pos: ETFScalpPosition, reason: str) -> None:
        """Close an ETF scalp position."""
        self.positions.remove(pos)
        self.closed_trades.append({
            "ticker": pos.ticker,
            "original_ticker": pos.original_signal_ticker,
            "direction": pos.direction,
            "shares": pos.shares,
            "entry_price": pos.entry_price,
            "exit_price": pos.current_price,
            "pnl": pos.unrealized_pnl,
            "pnl_pct": pos.unrealized_pnl_pct,
            "exit_reason": reason,
            "leverage": pos.leverage,
        })
        logger.info(
            "ETF scalp closed: %s P&L $%.2f (%s)",
            pos.ticker, pos.unrealized_pnl, reason,
        )

    def _map_ticker_to_etf(
        self, ticker: str, direction: str
    ) -> tuple[Optional[str], float, bool]:
        """Map a signal ticker to its corresponding leveraged ETF.

        Returns (etf_ticker, leverage, is_inverse).
        """
        sector = TICKER_SECTOR_MAP.get(ticker)
        if not sector:
            sector = "NASDAQ-100"

        is_bull = direction == "long"
        target_direction = "bull" if is_bull else "bear"

        candidates = [
            (t, m) for t, m in LEVERAGED_ETF_CATALOG.items()
            if m["tracks"] == sector and m["direction"] == target_direction
        ]

        if not candidates:
            return None, 0.0, False

        # Prefer 3x
        if self.config.etf_prefer_3x:
            three_x = [(t, m) for t, m in candidates if m["leverage"] == 3.0]
            if three_x:
                candidates = three_x

        candidates.sort(key=lambda x: x[1]["leverage"], reverse=True)
        etf_ticker, meta = candidates[0]
        return etf_ticker, meta["leverage"], meta["inverse"]
