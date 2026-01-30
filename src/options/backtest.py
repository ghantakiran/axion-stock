"""Options Strategy Backtester.

Backtests options strategies against historical price and IV data
with configurable entry/exit rules.
"""

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from src.options.config import BacktestConfig
from src.options.pricing import OptionsPricingEngine, OptionLeg

logger = logging.getLogger(__name__)


@dataclass
class EntryRules:
    """Rules for strategy entry."""

    min_dte: int = 30
    max_dte: int = 60
    min_iv_rank: float = 0.0
    max_iv_rank: float = 1.0
    entry_days: list = field(default_factory=lambda: [0, 1, 2, 3, 4])  # Mon-Fri
    min_underlying_price: float = 0.0
    max_underlying_price: float = float("inf")


@dataclass
class ExitRules:
    """Rules for strategy exit."""

    profit_target_pct: float = 0.50  # Close at 50% of max profit
    stop_loss_pct: float = 2.0  # Close at 200% of credit received (loss)
    min_dte_exit: int = 7  # Close at 7 DTE regardless
    max_hold_days: int = 45


@dataclass
class BacktestTrade:
    """Single backtested trade."""

    entry_date: str = ""
    exit_date: str = ""
    entry_price: float = 0.0
    exit_price: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    hold_days: int = 0
    exit_reason: str = ""  # profit_target, stop_loss, dte_exit, expiration
    underlying_entry: float = 0.0
    underlying_exit: float = 0.0
    iv_entry: float = 0.0

    def to_dict(self) -> dict:
        return {
            "entry_date": self.entry_date,
            "exit_date": self.exit_date,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "pnl": self.pnl,
            "pnl_pct": self.pnl_pct,
            "hold_days": self.hold_days,
            "exit_reason": self.exit_reason,
        }


@dataclass
class BacktestResult:
    """Complete backtest results."""

    trades: list = field(default_factory=list)
    total_pnl: float = 0.0
    win_rate: float = 0.0
    avg_trade_pnl: float = 0.0
    avg_winner: float = 0.0
    avg_loser: float = 0.0
    max_drawdown: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    avg_hold_days: float = 0.0

    def summary(self) -> dict:
        return {
            "total_trades": self.total_trades,
            "win_rate": self.win_rate,
            "total_pnl": self.total_pnl,
            "avg_trade_pnl": self.avg_trade_pnl,
            "avg_winner": self.avg_winner,
            "avg_loser": self.avg_loser,
            "max_drawdown": self.max_drawdown,
            "profit_factor": self.profit_factor,
            "sharpe_ratio": self.sharpe_ratio,
            "avg_hold_days": self.avg_hold_days,
        }


class OptionsBacktester:
    """Backtest options strategies on historical data.

    Simulates strategy entry/exit using historical price and IV data
    with configurable rules.

    Example:
        bt = OptionsBacktester()
        result = bt.backtest_short_put(
            price_history, iv_history,
            delta_target=0.30,
            entry_rules=EntryRules(min_iv_rank=0.50),
            exit_rules=ExitRules(profit_target_pct=0.50),
        )
    """

    def __init__(
        self,
        config: Optional[BacktestConfig] = None,
        pricing_engine: Optional[OptionsPricingEngine] = None,
    ):
        self.config = config or BacktestConfig()
        self.engine = pricing_engine or OptionsPricingEngine()

    def backtest_strategy(
        self,
        price_history: pd.Series,
        iv_history: pd.Series,
        strategy_fn: callable,
        entry_rules: Optional[EntryRules] = None,
        exit_rules: Optional[ExitRules] = None,
    ) -> BacktestResult:
        """Backtest a generic options strategy.

        Args:
            price_history: Daily price series (DatetimeIndex).
            iv_history: Daily ATM IV series.
            strategy_fn: Function(spot, iv, dte) -> list[OptionLeg].
            entry_rules: Entry criteria.
            exit_rules: Exit criteria.

        Returns:
            BacktestResult with all trades and stats.
        """
        entry_rules = entry_rules or EntryRules()
        exit_rules = exit_rules or ExitRules()

        trades = []
        i = 0
        dates = price_history.index

        while i < len(dates) - entry_rules.min_dte:
            entry_date = dates[i]

            # Check entry conditions
            if not self._check_entry(
                entry_date, price_history.iloc[i],
                iv_history.get(entry_date, 0.25), entry_rules, iv_history
            ):
                i += 1
                continue

            spot = price_history.iloc[i]
            iv = iv_history.get(entry_date, 0.25)
            dte = entry_rules.max_dte

            # Build strategy legs
            legs = strategy_fn(spot, iv, dte)
            if not legs:
                i += 1
                continue

            # Net entry premium
            entry_premium = sum(leg.premium * leg.quantity for leg in legs)
            multiplier = 100

            # Simulate to exit
            trade = self._simulate_to_exit(
                legs, i, price_history, iv_history,
                entry_premium, exit_rules, multiplier
            )

            trade.underlying_entry = float(spot)
            trade.iv_entry = float(iv)
            trade.entry_date = str(entry_date.date()) if hasattr(entry_date, 'date') else str(entry_date)

            trades.append(trade)

            # Skip to after exit
            exit_idx = min(i + trade.hold_days + 1, len(dates) - 1)
            i = exit_idx

        return self._compute_results(trades)

    def backtest_short_put(
        self,
        price_history: pd.Series,
        iv_history: pd.Series,
        delta_target: float = 0.30,
        entry_rules: Optional[EntryRules] = None,
        exit_rules: Optional[ExitRules] = None,
    ) -> BacktestResult:
        """Backtest selling puts at target delta.

        Args:
            price_history: Daily underlying prices.
            iv_history: Daily ATM IV.
            delta_target: Target put delta (e.g., 0.30 = 30-delta).
            entry_rules: Entry criteria.
            exit_rules: Exit criteria.

        Returns:
            BacktestResult.
        """
        def strategy_fn(spot, iv, dte):
            T = dte / 365.0
            r = self.engine.config.risk_free_rate
            # Find strike for target delta
            strike = self._find_delta_strike(spot, T, r, iv, "put", delta_target)
            price = self.engine.black_scholes(spot, strike, T, r, iv, "put")
            return [OptionLeg(
                option_type="put", strike=strike, premium=price.price,
                quantity=-1, expiry_days=dte, iv=iv, greeks=price,
            )]

        return self.backtest_strategy(
            price_history, iv_history, strategy_fn,
            entry_rules, exit_rules,
        )

    def backtest_iron_condor(
        self,
        price_history: pd.Series,
        iv_history: pd.Series,
        wing_delta: float = 0.15,
        wing_width: float = 5.0,
        entry_rules: Optional[EntryRules] = None,
        exit_rules: Optional[ExitRules] = None,
    ) -> BacktestResult:
        """Backtest iron condors.

        Args:
            price_history: Daily underlying prices.
            iv_history: Daily ATM IV.
            wing_delta: Target delta for short strikes.
            wing_width: Width of each spread.
            entry_rules: Entry criteria.
            exit_rules: Exit criteria.

        Returns:
            BacktestResult.
        """
        def strategy_fn(spot, iv, dte):
            T = dte / 365.0
            r = self.engine.config.risk_free_rate

            put_sell = self._find_delta_strike(spot, T, r, iv, "put", wing_delta)
            call_sell = self._find_delta_strike(spot, T, r, iv, "call", wing_delta)
            put_buy = put_sell - wing_width
            call_buy = call_sell + wing_width

            legs = []
            for strike, opt_type, qty in [
                (put_buy, "put", 1), (put_sell, "put", -1),
                (call_sell, "call", -1), (call_buy, "call", 1),
            ]:
                price = self.engine.black_scholes(spot, strike, T, r, iv, opt_type)
                legs.append(OptionLeg(
                    option_type=opt_type, strike=strike, premium=price.price,
                    quantity=qty, expiry_days=dte, iv=iv, greeks=price,
                ))
            return legs

        return self.backtest_strategy(
            price_history, iv_history, strategy_fn,
            entry_rules, exit_rules,
        )

    def _check_entry(
        self,
        entry_date,
        price: float,
        iv: float,
        rules: EntryRules,
        iv_history: pd.Series,
    ) -> bool:
        """Check if entry conditions are met."""
        # Day of week
        if hasattr(entry_date, 'weekday'):
            if entry_date.weekday() not in rules.entry_days:
                return False

        # Price range
        if price < rules.min_underlying_price or price > rules.max_underlying_price:
            return False

        # IV rank
        if len(iv_history) >= 252:
            iv_vals = iv_history.iloc[-252:]
            iv_low, iv_high = iv_vals.min(), iv_vals.max()
            if iv_high > iv_low:
                iv_rank = (iv - iv_low) / (iv_high - iv_low)
            else:
                iv_rank = 0.5
            if iv_rank < rules.min_iv_rank or iv_rank > rules.max_iv_rank:
                return False

        return True

    def _simulate_to_exit(
        self,
        legs: list[OptionLeg],
        entry_idx: int,
        price_history: pd.Series,
        iv_history: pd.Series,
        entry_premium: float,
        rules: ExitRules,
        multiplier: int,
    ) -> BacktestTrade:
        """Simulate strategy from entry to exit."""
        dates = price_history.index
        r = self.engine.config.risk_free_rate

        max_credit = abs(entry_premium) * multiplier if entry_premium < 0 else 0
        max_hold = min(rules.max_hold_days, len(dates) - entry_idx - 1)
        dte_at_entry = max(leg.expiry_days for leg in legs)

        for day in range(1, max_hold + 1):
            idx = entry_idx + day
            if idx >= len(dates):
                break

            current_price = price_history.iloc[idx]
            current_iv = iv_history.get(dates[idx], 0.25)
            remaining_dte = dte_at_entry - day
            T = max(remaining_dte / 365.0, 1 / 365.0)

            # Reprice legs
            current_value = 0.0
            for leg in legs:
                repriced = self.engine.black_scholes(
                    current_price, leg.strike, T, r, current_iv, leg.option_type,
                )
                current_value += repriced.price * leg.quantity

            pnl = (current_value - entry_premium) * multiplier

            # Check profit target
            if max_credit > 0 and pnl >= max_credit * rules.profit_target_pct:
                return BacktestTrade(
                    exit_date=str(dates[idx].date()) if hasattr(dates[idx], 'date') else str(dates[idx]),
                    entry_price=entry_premium * multiplier,
                    exit_price=current_value * multiplier,
                    pnl=float(pnl),
                    pnl_pct=float(pnl / abs(entry_premium * multiplier)) if entry_premium != 0 else 0,
                    hold_days=day,
                    exit_reason="profit_target",
                    underlying_exit=float(current_price),
                )

            # Check stop loss
            if max_credit > 0 and pnl <= -max_credit * rules.stop_loss_pct:
                return BacktestTrade(
                    exit_date=str(dates[idx].date()) if hasattr(dates[idx], 'date') else str(dates[idx]),
                    entry_price=entry_premium * multiplier,
                    exit_price=current_value * multiplier,
                    pnl=float(pnl),
                    pnl_pct=float(pnl / abs(entry_premium * multiplier)) if entry_premium != 0 else 0,
                    hold_days=day,
                    exit_reason="stop_loss",
                    underlying_exit=float(current_price),
                )

            # Check DTE exit
            if remaining_dte <= rules.min_dte_exit:
                return BacktestTrade(
                    exit_date=str(dates[idx].date()) if hasattr(dates[idx], 'date') else str(dates[idx]),
                    entry_price=entry_premium * multiplier,
                    exit_price=current_value * multiplier,
                    pnl=float(pnl),
                    pnl_pct=float(pnl / abs(entry_premium * multiplier)) if entry_premium != 0 else 0,
                    hold_days=day,
                    exit_reason="dte_exit",
                    underlying_exit=float(current_price),
                )

        # Expiration
        idx = min(entry_idx + max_hold, len(dates) - 1)
        current_price = price_history.iloc[idx]
        exp_value = 0.0
        for leg in legs:
            if leg.option_type == "call":
                intrinsic = max(current_price - leg.strike, 0)
            else:
                intrinsic = max(leg.strike - current_price, 0)
            exp_value += intrinsic * leg.quantity

        pnl = (exp_value - entry_premium) * multiplier

        return BacktestTrade(
            exit_date=str(dates[idx].date()) if hasattr(dates[idx], 'date') else str(dates[idx]),
            entry_price=entry_premium * multiplier,
            exit_price=exp_value * multiplier,
            pnl=float(pnl),
            pnl_pct=float(pnl / abs(entry_premium * multiplier)) if entry_premium != 0 else 0,
            hold_days=max_hold,
            exit_reason="expiration",
            underlying_exit=float(current_price),
        )

    def _find_delta_strike(
        self,
        spot: float,
        T: float,
        r: float,
        sigma: float,
        option_type: str,
        target_delta: float,
    ) -> float:
        """Find strike for target absolute delta via bisection."""
        low = spot * 0.7
        high = spot * 1.3

        for _ in range(50):
            mid = (low + high) / 2
            price = self.engine.black_scholes(spot, mid, T, r, sigma, option_type)
            current_delta = abs(price.delta)

            if abs(current_delta - target_delta) < 0.001:
                break

            if option_type == "put":
                if current_delta > target_delta:
                    low = mid  # Move strike lower (more OTM)
                else:
                    high = mid
            else:
                if current_delta > target_delta:
                    high = mid  # Move strike higher (more OTM)
                else:
                    low = mid

        return round(mid, 2)

    def _compute_results(self, trades: list[BacktestTrade]) -> BacktestResult:
        """Compute aggregate backtest statistics."""
        result = BacktestResult(trades=trades)

        if not trades:
            return result

        pnls = [t.pnl for t in trades]
        result.total_trades = len(trades)
        result.total_pnl = sum(pnls)
        result.avg_trade_pnl = float(np.mean(pnls))

        winners = [p for p in pnls if p > 0]
        losers = [p for p in pnls if p <= 0]

        result.winning_trades = len(winners)
        result.losing_trades = len(losers)
        result.win_rate = len(winners) / len(trades) if trades else 0

        result.avg_winner = float(np.mean(winners)) if winners else 0
        result.avg_loser = float(np.mean(losers)) if losers else 0

        # Profit factor
        gross_profit = sum(winners)
        gross_loss = abs(sum(losers))
        result.profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

        # Max drawdown
        cumulative = np.cumsum(pnls)
        peak = np.maximum.accumulate(cumulative)
        drawdowns = cumulative - peak
        result.max_drawdown = float(drawdowns.min()) if len(drawdowns) > 0 else 0

        # Sharpe (annualized, assuming ~12 trades/year)
        if len(pnls) >= 2:
            trades_per_year = max(12, len(trades))
            std = float(np.std(pnls))
            if std > 0:
                result.sharpe_ratio = float(np.mean(pnls) / std * np.sqrt(trades_per_year))

        result.avg_hold_days = float(np.mean([t.hold_days for t in trades]))

        return result
