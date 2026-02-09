"""Signal replay analysis.

Replays historical signals through the trade executor's risk gate
and position sizer, enabling A/B testing of risk configurations
without re-running the full backtest.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

from src.ema_signals.detector import TradeSignal
from src.trade_executor.executor import (
    AccountState,
    ExecutorConfig,
    Position,
    PositionSizer,
)
from src.trade_executor.risk_gate import RiskGate


@dataclass
class ReplayEntry:
    """Result of replaying a single signal through risk rules."""

    signal: TradeSignal
    approved: bool
    rejection_reason: Optional[str] = None
    position_size: int = 0

    def to_dict(self) -> dict:
        return {
            "ticker": self.signal.ticker,
            "signal_type": self.signal.signal_type.value,
            "direction": self.signal.direction,
            "conviction": self.signal.conviction,
            "entry_price": self.signal.entry_price,
            "approved": self.approved,
            "rejection_reason": self.rejection_reason,
            "position_size": self.position_size,
        }


@dataclass
class ReplayResult:
    """Aggregate result of replaying multiple signals."""

    total: int = 0
    approved: int = 0
    rejected: int = 0
    approval_rate: float = 0.0
    entries: list[ReplayEntry] = field(default_factory=list)
    rejection_reasons: dict[str, int] = field(default_factory=dict)

    def to_dataframe(self) -> pd.DataFrame:
        if not self.entries:
            return pd.DataFrame()
        return pd.DataFrame([e.to_dict() for e in self.entries])


class SignalReplay:
    """Replay historical signals through risk gate and position sizer.

    Simulates the trade executor's validation pipeline against a
    sequence of signals, tracking account state progression to
    give accurate rejection/approval decisions.
    """

    def __init__(self, config: Optional[ExecutorConfig] = None):
        self.config = config or ExecutorConfig()
        self.risk_gate = RiskGate(self.config)
        self.sizer = PositionSizer(self.config)

    def replay(
        self,
        signals: list[TradeSignal],
        starting_equity: float = 100_000.0,
    ) -> ReplayResult:
        """Replay signals sequentially, simulating account state.

        Each approved signal updates the simulated account state
        (adds a position, reduces buying power) so subsequent
        signals see realistic conditions.

        Args:
            signals: List of TradeSignal to replay.
            starting_equity: Starting account equity.

        Returns:
            ReplayResult with per-signal decisions.
        """
        entries: list[ReplayEntry] = []
        rejection_reasons: dict[str, int] = {}

        # Simulated account state
        account = AccountState(
            equity=starting_equity,
            cash=starting_equity,
            buying_power=starting_equity,
            open_positions=[],
            daily_pnl=0.0,
            daily_trades=0,
            starting_equity=starting_equity,
        )

        for signal in signals:
            decision = self.risk_gate.validate(signal, account)

            if decision.approved:
                # Size the position
                size = self.sizer.calculate(signal, account)
                notional = size.shares * signal.entry_price

                # Update account state
                position = Position(
                    ticker=signal.ticker,
                    direction=signal.direction,
                    entry_price=signal.entry_price,
                    current_price=signal.entry_price,
                    shares=size.shares,
                    stop_loss=signal.stop_loss,
                    target_price=signal.target_price,
                    entry_time=signal.timestamp,
                )
                account.open_positions.append(position)
                account.cash -= notional
                account.buying_power -= notional

                entries.append(ReplayEntry(
                    signal=signal,
                    approved=True,
                    position_size=size.shares,
                ))
            else:
                reason = decision.reason or "unknown"
                rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1

                entries.append(ReplayEntry(
                    signal=signal,
                    approved=False,
                    rejection_reason=reason,
                ))

        total = len(entries)
        approved = sum(1 for e in entries if e.approved)
        rejected = total - approved

        return ReplayResult(
            total=total,
            approved=approved,
            rejected=rejected,
            approval_rate=approved / total if total > 0 else 0.0,
            entries=entries,
            rejection_reasons=rejection_reasons,
        )

    def compare_configs(
        self,
        signals: list[TradeSignal],
        configs: dict[str, ExecutorConfig],
        starting_equity: float = 100_000.0,
    ) -> dict[str, ReplayResult]:
        """A/B test multiple risk configurations against the same signals.

        Args:
            signals: Signals to replay.
            configs: Named executor configs to compare.
            starting_equity: Starting account equity.

        Returns:
            Dict mapping config name to ReplayResult.
        """
        results: dict[str, ReplayResult] = {}
        for name, config in configs.items():
            replay = SignalReplay(config)
            results[name] = replay.replay(signals, starting_equity)
        return results
