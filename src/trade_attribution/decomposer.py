"""P&L Decomposition Engine.

Breaks down each trade's P&L into:
- Entry quality: How well timed was the entry vs. the bar's range?
- Market movement: How much did the market help/hurt?
- Exit timing: Was the exit well-timed relative to subsequent price action?
- Transaction costs: Commission + slippage
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
import math


@dataclass
class PnLBreakdown:
    """Decomposed P&L for a single trade."""

    trade_id: str = ""
    symbol: str = ""
    total_pnl: float = 0.0
    # Components
    entry_quality: float = 0.0  # +/- vs bar midpoint at entry
    market_movement: float = 0.0  # Broad market contribution
    exit_timing: float = 0.0  # +/- vs bar midpoint at exit
    transaction_costs: float = 0.0  # Commission + slippage
    residual: float = 0.0  # Unexplained remainder
    # Percentages
    entry_quality_pct: float = 0.0
    market_movement_pct: float = 0.0
    exit_timing_pct: float = 0.0
    cost_pct: float = 0.0
    # Quality scores (-1 to +1)
    entry_score: float = 0.0  # -1 = worst, +1 = best
    exit_score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "total_pnl": round(self.total_pnl, 2),
            "entry_quality": round(self.entry_quality, 2),
            "market_movement": round(self.market_movement, 2),
            "exit_timing": round(self.exit_timing, 2),
            "transaction_costs": round(self.transaction_costs, 2),
            "residual": round(self.residual, 2),
            "entry_quality_pct": round(self.entry_quality_pct, 4),
            "market_movement_pct": round(self.market_movement_pct, 4),
            "exit_timing_pct": round(self.exit_timing_pct, 4),
            "cost_pct": round(self.cost_pct, 4),
            "entry_score": round(self.entry_score, 3),
            "exit_score": round(self.exit_score, 3),
        }


@dataclass
class DecompositionReport:
    """Aggregate decomposition across multiple trades."""

    breakdowns: list[PnLBreakdown] = field(default_factory=list)
    total_pnl: float = 0.0
    total_entry_quality: float = 0.0
    total_market_movement: float = 0.0
    total_exit_timing: float = 0.0
    total_costs: float = 0.0
    avg_entry_score: float = 0.0
    avg_exit_score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "total_pnl": round(self.total_pnl, 2),
            "total_entry_quality": round(self.total_entry_quality, 2),
            "total_market_movement": round(self.total_market_movement, 2),
            "total_exit_timing": round(self.total_exit_timing, 2),
            "total_costs": round(self.total_costs, 2),
            "avg_entry_score": round(self.avg_entry_score, 3),
            "avg_exit_score": round(self.avg_exit_score, 3),
            "trade_count": len(self.breakdowns),
        }

    def to_dataframe(self):
        import pandas as pd

        if not self.breakdowns:
            return pd.DataFrame()
        return pd.DataFrame([b.to_dict() for b in self.breakdowns])


class TradeDecomposer:
    """Decomposes trade P&L into entry, market, exit, and cost components.

    Simple method:
    - entry_quality = (bar_midpoint_at_entry - entry_price) * shares * direction_multiplier
    - market_movement = (exit_bar_midpoint - entry_bar_midpoint) * shares * direction_multiplier
    - exit_timing = (exit_price - exit_bar_midpoint) * shares * direction_multiplier
    - transaction_costs = commission + slippage
    - residual = total_pnl - sum(components)
    """

    def __init__(self, config: Optional[AttributionConfig] = None):
        from src.trade_attribution.config import AttributionConfig

        self.config = config or AttributionConfig()

    def decompose(
        self,
        trade: dict,
        entry_bar: Optional[dict] = None,
        exit_bar: Optional[dict] = None,
    ) -> PnLBreakdown:
        """Decompose a single trade's P&L.

        trade: {trade_id, symbol, entry_price, exit_price, shares, direction, pnl}
        entry_bar: {open, high, low, close} - OHLC at entry time
        exit_bar: {open, high, low, close} - OHLC at exit time
        """
        trade_id = trade.get("trade_id", "")
        symbol = trade.get("symbol", "")
        entry_price = trade.get("entry_price", 0.0)
        exit_price = trade.get("exit_price", 0.0)
        shares = trade.get("shares", 0.0)
        direction = 1.0 if trade.get("direction", "long") == "long" else -1.0
        total_pnl = trade.get(
            "pnl", (exit_price - entry_price) * shares * direction
        )

        # Default bars if not provided
        if entry_bar is None:
            entry_bar = {
                "open": entry_price,
                "high": entry_price * 1.005,
                "low": entry_price * 0.995,
                "close": entry_price,
            }
        if exit_bar is None:
            exit_bar = {
                "open": exit_price,
                "high": exit_price * 1.005,
                "low": exit_price * 0.995,
                "close": exit_price,
            }

        entry_mid = (entry_bar["high"] + entry_bar["low"]) / 2
        exit_mid = (exit_bar["high"] + exit_bar["low"]) / 2

        # Entry quality: positive = entered below midpoint (for longs)
        entry_quality = (entry_mid - entry_price) * shares * direction

        # Market movement: midpoint to midpoint
        market_movement = (exit_mid - entry_mid) * shares * direction

        # Exit timing: positive = exited above midpoint (for longs)
        exit_timing = (exit_price - exit_mid) * shares * direction

        # Transaction costs
        commission = self.config.commission_per_share * shares * 2  # round trip
        # Sqrt market impact model
        impact = 0.0
        if self.config.slippage_model == "sqrt" and shares > 0:
            impact = 0.01 * math.sqrt(shares) * entry_price / 100  # basis points
        costs = commission + impact

        residual = total_pnl - (entry_quality + market_movement + exit_timing - costs)

        # Entry score: -1 (worst of bar) to +1 (best of bar)
        entry_range = entry_bar["high"] - entry_bar["low"]
        if entry_range > 0:
            # For longs: lower entry = better
            if direction > 0:
                entry_score = (
                    1.0
                    - 2.0 * (entry_price - entry_bar["low"]) / entry_range
                )
            else:
                entry_score = (
                    -1.0
                    + 2.0 * (entry_price - entry_bar["low"]) / entry_range
                )
        else:
            entry_score = 0.0

        exit_range = exit_bar["high"] - exit_bar["low"]
        if exit_range > 0:
            if direction > 0:
                exit_score = (
                    -1.0
                    + 2.0 * (exit_price - exit_bar["low"]) / exit_range
                )
            else:
                exit_score = (
                    1.0
                    - 2.0 * (exit_price - exit_bar["low"]) / exit_range
                )
        else:
            exit_score = 0.0

        # Percentages (of total P&L)
        abs_total = abs(total_pnl) if total_pnl != 0 else 1.0

        return PnLBreakdown(
            trade_id=trade_id,
            symbol=symbol,
            total_pnl=total_pnl,
            entry_quality=entry_quality,
            market_movement=market_movement,
            exit_timing=exit_timing,
            transaction_costs=costs,
            residual=residual,
            entry_quality_pct=entry_quality / abs_total,
            market_movement_pct=market_movement / abs_total,
            exit_timing_pct=exit_timing / abs_total,
            cost_pct=costs / abs_total,
            entry_score=max(-1.0, min(1.0, entry_score)),
            exit_score=max(-1.0, min(1.0, exit_score)),
        )

    def decompose_batch(
        self, trades: list[dict], bars: Optional[dict] = None
    ) -> DecompositionReport:
        """Decompose multiple trades.

        bars: optional dict mapping trade_id -> {"entry_bar": {...}, "exit_bar": {...}}
        """
        breakdowns = []
        for trade in trades:
            tid = trade.get("trade_id", "")
            trade_bars = (bars or {}).get(tid, {})
            bd = self.decompose(
                trade, trade_bars.get("entry_bar"), trade_bars.get("exit_bar")
            )
            breakdowns.append(bd)

        total_pnl = sum(b.total_pnl for b in breakdowns)
        total_entry = sum(b.entry_quality for b in breakdowns)
        total_market = sum(b.market_movement for b in breakdowns)
        total_exit = sum(b.exit_timing for b in breakdowns)
        total_costs = sum(b.transaction_costs for b in breakdowns)
        n = len(breakdowns) or 1

        return DecompositionReport(
            breakdowns=breakdowns,
            total_pnl=total_pnl,
            total_entry_quality=total_entry,
            total_market_movement=total_market,
            total_exit_timing=total_exit,
            total_costs=total_costs,
            avg_entry_score=sum(b.entry_score for b in breakdowns) / n,
            avg_exit_score=sum(b.exit_score for b in breakdowns) / n,
        )
