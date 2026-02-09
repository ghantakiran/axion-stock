"""Pre-trade risk validation gate.

Validates every signal against 8 risk checks before allowing execution.
All checks must pass for a trade to proceed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, time, timezone
from typing import Optional

from src.ema_signals.detector import TradeSignal
from src.trade_executor.executor import AccountState, ExecutorConfig

logger = logging.getLogger(__name__)


@dataclass
class RiskDecision:
    """Result of risk gate validation."""

    approved: bool
    reason: Optional[str] = None
    adjustments: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "approved": self.approved,
            "reason": self.reason,
            "adjustments": self.adjustments,
        }


# ═══════════════════════════════════════════════════════════════════════
# Risk Gate
# ═══════════════════════════════════════════════════════════════════════


class RiskGate:
    """Gate that rejects signals violating risk parameters.

    All 8 checks must pass for a trade to be approved:
    1. Daily P&L above loss limit
    2. Open positions below max
    3. No duplicate ticker (unless adding to winner)
    4. No conflicting signals (long + short same ticker)
    5. Sector exposure within limits
    6. Market hours check
    7. Account equity above minimum (PDT)
    8. Sufficient buying power
    """

    def __init__(self, config: ExecutorConfig):
        self.config = config

    def validate(
        self, signal: TradeSignal, account: AccountState
    ) -> RiskDecision:
        """Run all risk checks against a signal.

        Returns RiskDecision with approved=True if all checks pass.
        """
        checks = [
            self._check_daily_loss_limit,
            self._check_max_positions,
            self._check_duplicate_ticker,
            self._check_conflicting_signals,
            self._check_sector_exposure,
            self._check_market_hours,
            self._check_min_equity,
            self._check_buying_power,
        ]

        for check_fn in checks:
            decision = check_fn(signal, account)
            if not decision.approved:
                logger.info(
                    "Signal REJECTED for %s: %s", signal.ticker, decision.reason
                )
                return decision

        return RiskDecision(approved=True)

    def _check_daily_loss_limit(
        self, signal: TradeSignal, account: AccountState
    ) -> RiskDecision:
        """1. Daily P&L must be above the loss limit."""
        if account.starting_equity <= 0:
            return RiskDecision(approved=True)

        daily_loss_pct = abs(account.daily_pnl) / account.starting_equity
        if account.daily_pnl < 0 and daily_loss_pct >= self.config.daily_loss_limit:
            return RiskDecision(
                approved=False,
                reason=f"Daily loss limit reached: {daily_loss_pct:.1%} >= {self.config.daily_loss_limit:.0%}",
            )
        return RiskDecision(approved=True)

    def _check_max_positions(
        self, signal: TradeSignal, account: AccountState
    ) -> RiskDecision:
        """2. Open positions must be below the maximum."""
        if len(account.open_positions) >= self.config.max_concurrent_positions:
            return RiskDecision(
                approved=False,
                reason=f"Max positions reached: {len(account.open_positions)}/{self.config.max_concurrent_positions}",
            )
        return RiskDecision(approved=True)

    def _check_duplicate_ticker(
        self, signal: TradeSignal, account: AccountState
    ) -> RiskDecision:
        """3. No existing position in same ticker (unless adding to winner)."""
        for pos in account.open_positions:
            if pos.ticker == signal.ticker:
                # Allow adding if existing position is profitable
                if pos.unrealized_pnl > 0 and pos.direction == signal.direction:
                    return RiskDecision(
                        approved=True,
                        adjustments={"add_to_existing": True},
                    )
                return RiskDecision(
                    approved=False,
                    reason=f"Existing position in {signal.ticker} (P&L: {pos.unrealized_pnl:.2f})",
                )
        return RiskDecision(approved=True)

    def _check_conflicting_signals(
        self, signal: TradeSignal, account: AccountState
    ) -> RiskDecision:
        """4. No conflicting direction on same ticker."""
        for pos in account.open_positions:
            if pos.ticker == signal.ticker and pos.direction != signal.direction:
                return RiskDecision(
                    approved=False,
                    reason=f"Conflicting signal: existing {pos.direction} vs new {signal.direction} for {signal.ticker}",
                )
        return RiskDecision(approved=True)

    def _check_sector_exposure(
        self, signal: TradeSignal, account: AccountState
    ) -> RiskDecision:
        """5. Sector exposure within limits.

        Simplified: counts ticker exposure as single-stock check.
        Full sector mapping would integrate with Axion's sector data.
        """
        if account.equity <= 0:
            return RiskDecision(approved=True)

        ticker_exposure = sum(
            abs(p.shares * p.current_price)
            for p in account.open_positions
            if p.ticker == signal.ticker
        )
        exposure_pct = ticker_exposure / account.equity
        if exposure_pct >= self.config.max_single_stock_exposure:
            return RiskDecision(
                approved=False,
                reason=f"Single-stock exposure limit: {signal.ticker} at {exposure_pct:.1%} >= {self.config.max_single_stock_exposure:.0%}",
            )
        return RiskDecision(approved=True)

    def _check_market_hours(
        self, signal: TradeSignal, account: AccountState
    ) -> RiskDecision:
        """6. Only trade during market hours (9:30 AM - 4:00 PM ET)."""
        now_utc = datetime.now(timezone.utc)

        # Use proper timezone for ET (handles DST automatically)
        try:
            from zoneinfo import ZoneInfo
            now_et = now_utc.astimezone(ZoneInfo("America/New_York"))
            current_et = now_et.time()
        except ImportError:
            # Fallback: approximate ET as UTC-5 (EST)
            et_hour = (now_utc.hour - 5) % 24
            current_et = time(et_hour, now_utc.minute)

        market_open = time(9, 30)
        market_close = time(16, 0)

        if current_et < market_open or current_et >= market_close:
            # Allow if it's pre-market scan or if signal is daily timeframe
            if signal.timeframe in ("1d",):
                return RiskDecision(approved=True)
            return RiskDecision(
                approved=False,
                reason=f"Outside market hours: {current_et}",
            )
        return RiskDecision(approved=True)

    def _check_min_equity(
        self, signal: TradeSignal, account: AccountState
    ) -> RiskDecision:
        """7. Account equity above minimum (PDT compliance)."""
        if account.equity < self.config.min_account_equity:
            return RiskDecision(
                approved=False,
                reason=f"Equity ${account.equity:,.0f} below minimum ${self.config.min_account_equity:,.0f}",
            )
        return RiskDecision(approved=True)

    def _check_buying_power(
        self, signal: TradeSignal, account: AccountState
    ) -> RiskDecision:
        """8. Sufficient buying power for the position."""
        estimated_cost = signal.entry_price * 100  # Rough estimate for min position
        if account.buying_power < estimated_cost:
            return RiskDecision(
                approved=False,
                reason=f"Insufficient buying power: ${account.buying_power:,.0f} < ${estimated_cost:,.0f}",
            )
        return RiskDecision(approved=True)
