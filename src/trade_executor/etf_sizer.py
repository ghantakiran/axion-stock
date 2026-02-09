"""Leverage-adjusted position sizing for leveraged ETFs.

Accounts for ETF leverage factor, tighter stop distances,
daily rebalancing decay risk, and max holding periods.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from src.ema_signals.detector import TradeSignal
from src.trade_executor.executor import AccountState, ExecutorConfig, PositionSize
from src.trade_executor.instrument_router import ETFSelection

logger = logging.getLogger(__name__)


class LeveragedETFSizer:
    """Position sizing that accounts for ETF leverage.

    Key differences from stock sizing:
    - 3x ETF needs 1/3 the shares to get equivalent exposure
    - Stop distances are tighter in nominal terms (divided by leverage)
    - Max holding period depends on leverage (decay risk)
    """

    def __init__(self, config: ExecutorConfig):
        self.config = config

    def calculate(
        self,
        signal: TradeSignal,
        etf: ETFSelection,
        account: AccountState,
    ) -> PositionSize:
        """Size a leveraged ETF position.

        Formula:
        1. risk_amount = equity * max_risk_per_trade
        2. stop_distance = abs(entry - stop) / entry
        3. leveraged_stop = stop_distance / leverage_factor (tighter)
        4. shares = risk_amount / (etf_price * leveraged_stop)
        5. Apply conviction multiplier
        6. Cap at max_single_stock_exposure
        """
        risk_amount = account.equity * self.config.max_risk_per_trade

        stop_distance = abs(signal.entry_price - signal.stop_loss) / signal.entry_price
        if stop_distance < 0.001:
            stop_distance = 0.02

        # Leveraged stop is tighter — price moves leverage-x faster
        leveraged_stop = stop_distance / etf.leverage
        if leveraged_stop < 0.003:
            leveraged_stop = 0.003

        # Use signal entry as proxy for ETF price (will be adjusted at order time)
        etf_price = signal.entry_price
        raw_shares = risk_amount / (etf_price * leveraged_stop)

        # Conviction multiplier
        if signal.conviction >= 75:
            conv_mult = 1.0
            order_type = self.config.high_conviction_order_type
        else:
            conv_mult = 0.5
            order_type = self.config.medium_conviction_order_type

        if self.config.scale_in_enabled and order_type == "limit":
            conv_mult *= self.config.scale_in_initial_pct

        final_shares = int(raw_shares * conv_mult)

        # Cap at max single-stock exposure (adjusted for leverage)
        max_notional = account.equity * self.config.max_single_stock_exposure
        equivalent_max = max_notional / etf.leverage
        max_shares = int(equivalent_max / etf_price) if etf_price > 0 else 0
        final_shares = min(final_shares, max_shares)
        final_shares = max(final_shares, 1)

        notional = final_shares * etf_price

        return PositionSize(
            shares=final_shares,
            notional_value=round(notional, 2),
            risk_amount=round(risk_amount, 2),
            conviction_multiplier=conv_mult,
            order_type=order_type,
        )

    def max_hold_days(self, leverage: float) -> int:
        """Max recommended holding period based on leverage.

        Higher leverage = shorter max hold due to daily rebalancing decay.
        """
        if leverage >= 3.0:
            return self.config.max_etf_hold_days_3x
        if leverage >= 2.0:
            return self.config.max_etf_hold_days_2x
        return 15

    def decay_warning(self, leverage: float, hold_days: int) -> str | None:
        """Return a warning if position exceeds recommended hold period."""
        max_days = self.max_hold_days(leverage)
        if hold_days > max_days:
            return (
                f"Leveraged ETF ({leverage}x) held {hold_days} days "
                f"exceeds recommended max of {max_days} days (decay risk)"
            )
        return None
