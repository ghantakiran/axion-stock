"""Trade-to-Signal Linkage.

Matches completed trades (entries + exits) back to the TradeSignal objects
that triggered them, creating a complete audit trail.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional


@dataclass
class LinkedTrade:
    """A trade linked to its originating signal."""

    trade_id: str
    signal_id: str = ""
    signal_type: str = "unknown"
    signal_conviction: int = 0
    signal_direction: str = "long"
    # Entry
    symbol: str = ""
    entry_price: float = 0.0
    entry_time: Optional[datetime] = None
    entry_shares: float = 0.0
    # Exit
    exit_price: float = 0.0
    exit_time: Optional[datetime] = None
    exit_reason: str = ""
    # P&L
    realized_pnl: float = 0.0
    realized_pnl_pct: float = 0.0
    hold_duration_seconds: int = 0
    # Context
    regime_at_entry: str = ""
    regime_at_exit: str = ""
    broker: str = ""

    @property
    def is_winner(self) -> bool:
        return self.realized_pnl > 0

    @property
    def hold_duration_hours(self) -> float:
        return self.hold_duration_seconds / 3600.0

    def to_dict(self) -> dict:
        return {
            "trade_id": self.trade_id,
            "signal_id": self.signal_id,
            "signal_type": self.signal_type,
            "signal_conviction": self.signal_conviction,
            "signal_direction": self.signal_direction,
            "symbol": self.symbol,
            "entry_price": round(self.entry_price, 4),
            "entry_time": self.entry_time.isoformat() if self.entry_time else "",
            "entry_shares": self.entry_shares,
            "exit_price": round(self.exit_price, 4),
            "exit_time": self.exit_time.isoformat() if self.exit_time else "",
            "exit_reason": self.exit_reason,
            "realized_pnl": round(self.realized_pnl, 2),
            "realized_pnl_pct": round(self.realized_pnl_pct, 4),
            "hold_duration_seconds": self.hold_duration_seconds,
            "regime_at_entry": self.regime_at_entry,
            "regime_at_exit": self.regime_at_exit,
            "broker": self.broker,
        }


@dataclass
class LinkageReport:
    """Summary of trade-signal linkage results."""

    total_trades: int = 0
    linked_trades: int = 0
    unlinked_trades: int = 0
    linkage_rate: float = 0.0
    trades: list[LinkedTrade] = field(default_factory=list)
    unlinked_trade_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_trades": self.total_trades,
            "linked_trades": self.linked_trades,
            "unlinked_trades": self.unlinked_trades,
            "linkage_rate": round(self.linkage_rate, 4),
            "trades": [t.to_dict() for t in self.trades],
        }


class TradeSignalLinker:
    """Links executed trades to their originating signals.

    Matching strategy:
    1. Exact match: signal_id stored in trade metadata
    2. Fuzzy match: symbol + direction + time window
    3. Conviction match: closest conviction score within window
    """

    def __init__(self, config: Optional[AttributionConfig] = None):
        from src.trade_attribution.config import AttributionConfig

        self.config = config or AttributionConfig()
        self._signal_buffer: list[dict] = []  # Recent signals for matching
        self._linked_trades: list[LinkedTrade] = []

    def register_signal(self, signal: dict) -> None:
        """Register a new signal for future trade matching.

        signal dict should have: signal_id, signal_type, symbol, direction,
        conviction, timestamp
        """
        self._signal_buffer.append(
            {
                "signal_id": signal.get("signal_id", ""),
                "signal_type": signal.get("signal_type", "unknown"),
                "symbol": signal.get("symbol", ""),
                "direction": signal.get("direction", "long"),
                "conviction": signal.get("conviction", 0),
                "timestamp": signal.get("timestamp", datetime.utcnow()),
            }
        )
        # Trim buffer - keep last 1000 signals
        if len(self._signal_buffer) > 1000:
            self._signal_buffer = self._signal_buffer[-500:]

    def link_trade(self, trade: dict) -> LinkedTrade:
        """Link a completed trade to its originating signal.

        trade dict should have: trade_id, symbol, entry_price, exit_price,
        entry_time, exit_time, shares, pnl, exit_reason, broker
        """
        symbol = trade.get("symbol", "")
        entry_time = trade.get("entry_time", datetime.utcnow())
        max_age = timedelta(seconds=self.config.max_signal_age_seconds)

        # Find matching signal
        best_match = None
        best_score = -1

        for sig in reversed(self._signal_buffer):
            if sig["symbol"] != symbol:
                continue
            sig_time = sig["timestamp"]
            if isinstance(sig_time, str):
                continue
            time_diff = abs((entry_time - sig_time).total_seconds())
            if time_diff > max_age.total_seconds():
                continue

            # Score: closer time = better, conviction match = bonus
            score = 1.0 - (time_diff / max_age.total_seconds())
            if self.config.match_by_conviction and sig["conviction"] > 0:
                score += 0.5  # Bonus for having conviction

            if score > best_score:
                best_score = score
                best_match = sig

        entry_price = trade.get("entry_price", 0.0)
        exit_price = trade.get("exit_price", 0.0)
        shares = trade.get("shares", 0.0)
        pnl = trade.get("pnl", (exit_price - entry_price) * shares)
        pnl_pct = (
            ((exit_price - entry_price) / entry_price) if entry_price > 0 else 0.0
        )
        exit_time = trade.get("exit_time", datetime.utcnow())
        hold_secs = (
            int((exit_time - entry_time).total_seconds())
            if isinstance(exit_time, datetime) and isinstance(entry_time, datetime)
            else 0
        )

        linked = LinkedTrade(
            trade_id=trade.get("trade_id", ""),
            signal_id=best_match["signal_id"] if best_match else "",
            signal_type=best_match["signal_type"] if best_match else "unknown",
            signal_conviction=best_match["conviction"] if best_match else 0,
            signal_direction=best_match["direction"] if best_match else "long",
            symbol=symbol,
            entry_price=entry_price,
            entry_time=entry_time,
            entry_shares=shares,
            exit_price=exit_price,
            exit_time=exit_time,
            exit_reason=trade.get("exit_reason", ""),
            realized_pnl=pnl,
            realized_pnl_pct=pnl_pct,
            hold_duration_seconds=hold_secs,
            regime_at_entry=trade.get("regime_at_entry", ""),
            regime_at_exit=trade.get("regime_at_exit", ""),
            broker=trade.get("broker", ""),
        )
        self._linked_trades.append(linked)
        return linked

    def get_linkage_report(self) -> LinkageReport:
        """Generate a report on trade-signal linkage quality."""
        total = len(self._linked_trades)
        linked = sum(1 for t in self._linked_trades if t.signal_id)
        unlinked_ids = [t.trade_id for t in self._linked_trades if not t.signal_id]
        return LinkageReport(
            total_trades=total,
            linked_trades=linked,
            unlinked_trades=total - linked,
            linkage_rate=linked / total if total > 0 else 0.0,
            trades=list(self._linked_trades),
            unlinked_trade_ids=unlinked_ids,
        )

    def get_linked_trades(self) -> list[LinkedTrade]:
        return list(self._linked_trades)

    def clear(self) -> None:
        self._signal_buffer.clear()
        self._linked_trades.clear()
