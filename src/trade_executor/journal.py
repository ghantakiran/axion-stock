"""Automated trade journaling.

Logs every trade with signal context, execution details, and P&L.
Provides daily summaries and history queries.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Optional

from src.ema_signals.detector import TradeSignal
from src.trade_executor.executor import Position
from src.trade_executor.router import OrderResult

logger = logging.getLogger(__name__)


@dataclass
class TradeRecord:
    """A completed trade with full context."""

    ticker: str
    direction: str
    instrument_type: str
    entry_price: float
    exit_price: float
    shares: int
    pnl: float
    pnl_pct: float
    entry_time: datetime
    exit_time: datetime
    exit_reason: str
    conviction: int
    signal_type: str
    timeframe: str
    broker: str
    order_id: str
    trade_type: str  # day, swing, scalp
    leverage: float = 1.0
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "direction": self.direction,
            "instrument_type": self.instrument_type,
            "entry_price": round(self.entry_price, 4),
            "exit_price": round(self.exit_price, 4),
            "shares": self.shares,
            "pnl": round(self.pnl, 2),
            "pnl_pct": round(self.pnl_pct, 4),
            "exit_reason": self.exit_reason,
            "conviction": self.conviction,
            "signal_type": self.signal_type,
            "timeframe": self.timeframe,
            "trade_type": self.trade_type,
            "broker": self.broker,
        }


@dataclass
class DailySummary:
    """Daily trading performance summary."""

    date: date
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    gross_profit: float
    gross_loss: float
    net_pnl: float
    largest_winner: float
    largest_loser: float
    avg_hold_minutes: float

    def to_dict(self) -> dict:
        return {
            "date": self.date.isoformat(),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": round(self.win_rate, 4),
            "net_pnl": round(self.net_pnl, 2),
            "largest_winner": round(self.largest_winner, 2),
            "largest_loser": round(self.largest_loser, 2),
        }


class TradeJournalWriter:
    """Automatically log every trade with signal context and P&L."""

    def __init__(self):
        self._trades: list[TradeRecord] = []
        self._pending: dict[str, dict] = {}  # signal_id → entry context

    def record_entry(
        self,
        signal: TradeSignal,
        order_result: OrderResult,
        position: Position,
    ) -> None:
        """Record a trade entry for later matching with exit."""
        self._pending[position.signal_id] = {
            "signal": signal,
            "order_result": order_result,
            "position": position,
        }
        logger.info(
            "Journal entry: %s %s %d shares @ $%.2f (conviction: %d)",
            signal.direction, signal.ticker, position.shares,
            order_result.filled_price, signal.conviction,
        )

    def record_exit(
        self,
        position: Position,
        exit_reason: str,
        exit_price: float,
        order_result: Optional[OrderResult] = None,
    ) -> TradeRecord:
        """Record a trade exit and compute P&L."""
        entry_ctx = self._pending.pop(position.signal_id, None)

        mult = 1 if position.direction == "long" else -1
        pnl = mult * (exit_price - position.entry_price) * position.shares
        pnl_pct = mult * (exit_price - position.entry_price) / position.entry_price if position.entry_price > 0 else 0

        record = TradeRecord(
            ticker=position.ticker,
            direction=position.direction,
            instrument_type=position.instrument_type,
            entry_price=position.entry_price,
            exit_price=exit_price,
            shares=position.shares,
            pnl=pnl,
            pnl_pct=pnl_pct,
            entry_time=position.entry_time,
            exit_time=datetime.now(timezone.utc),
            exit_reason=exit_reason,
            conviction=entry_ctx["signal"].conviction if entry_ctx else 0,
            signal_type=entry_ctx["signal"].signal_type.value if entry_ctx else "",
            timeframe=entry_ctx["signal"].timeframe if entry_ctx else "",
            broker=order_result.broker if order_result else "paper",
            order_id=order_result.order_id if order_result else "",
            trade_type=position.trade_type,
            leverage=position.leverage,
        )

        self._trades.append(record)
        logger.info(
            "Journal exit: %s %s P&L $%.2f (%.2f%%) — %s",
            position.direction, position.ticker, pnl, pnl_pct * 100, exit_reason,
        )
        return record

    def get_daily_summary(self, target_date: Optional[date] = None) -> DailySummary:
        """Compute summary stats for a given date."""
        if target_date is None:
            target_date = date.today()

        day_trades = [
            t for t in self._trades
            if t.exit_time.date() == target_date
        ]

        if not day_trades:
            return DailySummary(
                date=target_date, total_trades=0, winning_trades=0,
                losing_trades=0, win_rate=0.0, gross_profit=0.0,
                gross_loss=0.0, net_pnl=0.0, largest_winner=0.0,
                largest_loser=0.0, avg_hold_minutes=0.0,
            )

        winners = [t for t in day_trades if t.pnl > 0]
        losers = [t for t in day_trades if t.pnl <= 0]
        gross_profit = sum(t.pnl for t in winners)
        gross_loss = sum(t.pnl for t in losers)

        hold_times = [
            (t.exit_time - t.entry_time).total_seconds() / 60
            for t in day_trades
        ]

        return DailySummary(
            date=target_date,
            total_trades=len(day_trades),
            winning_trades=len(winners),
            losing_trades=len(losers),
            win_rate=len(winners) / len(day_trades) if day_trades else 0.0,
            gross_profit=gross_profit,
            gross_loss=gross_loss,
            net_pnl=gross_profit + gross_loss,
            largest_winner=max((t.pnl for t in winners), default=0.0),
            largest_loser=min((t.pnl for t in losers), default=0.0),
            avg_hold_minutes=sum(hold_times) / len(hold_times) if hold_times else 0.0,
        )

    def get_trade_history(
        self,
        ticker: Optional[str] = None,
        days: int = 30,
    ) -> list[TradeRecord]:
        """Query trade history with optional filters."""
        cutoff = datetime.now(timezone.utc) - __import__("datetime").timedelta(days=days)

        result = [t for t in self._trades if t.exit_time >= cutoff]
        if ticker:
            result = [t for t in result if t.ticker == ticker]
        return result

    @property
    def all_trades(self) -> list[TradeRecord]:
        return list(self._trades)
