"""Options Strategy Builder.

Pre-built strategy templates and custom strategy construction
with payoff analysis and probability of profit calculation.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd

from src.options.config import StrategyConfig
from src.options.pricing import OptionLeg, OptionPrice, OptionsPricingEngine

logger = logging.getLogger(__name__)


class StrategyType(str, Enum):
    LONG_CALL = "long_call"
    LONG_PUT = "long_put"
    COVERED_CALL = "covered_call"
    CASH_SECURED_PUT = "cash_secured_put"
    BULL_CALL_SPREAD = "bull_call_spread"
    BEAR_PUT_SPREAD = "bear_put_spread"
    IRON_CONDOR = "iron_condor"
    IRON_BUTTERFLY = "iron_butterfly"
    STRADDLE = "straddle"
    STRANGLE = "strangle"
    CALENDAR_SPREAD = "calendar_spread"
    DIAGONAL_SPREAD = "diagonal_spread"
    JADE_LIZARD = "jade_lizard"
    RATIO_SPREAD = "ratio_spread"
    CUSTOM = "custom"


@dataclass
class PayoffCurve:
    """Payoff diagram data."""

    prices: np.ndarray = field(default_factory=lambda: np.array([]))
    pnl: np.ndarray = field(default_factory=lambda: np.array([]))
    breakeven_points: list = field(default_factory=list)


@dataclass
class StrategyAnalysis:
    """Complete strategy analysis result."""

    name: str = ""
    strategy_type: str = "custom"
    legs: list = field(default_factory=list)
    max_profit: float = 0.0
    max_loss: float = 0.0
    breakeven_points: list = field(default_factory=list)
    probability_of_profit: float = 0.0
    expected_value: float = 0.0
    risk_reward_ratio: float = 0.0
    net_debit_credit: float = 0.0
    capital_required: float = 0.0
    annualized_return_max: float = 0.0
    net_delta: float = 0.0
    net_gamma: float = 0.0
    net_theta: float = 0.0
    net_vega: float = 0.0
    days_to_expiry: int = 0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "strategy_type": self.strategy_type,
            "max_profit": self.max_profit,
            "max_loss": self.max_loss,
            "breakeven_points": self.breakeven_points,
            "probability_of_profit": self.probability_of_profit,
            "expected_value": self.expected_value,
            "risk_reward_ratio": self.risk_reward_ratio,
            "net_debit_credit": self.net_debit_credit,
            "capital_required": self.capital_required,
            "net_delta": self.net_delta,
            "net_gamma": self.net_gamma,
            "net_theta": self.net_theta,
            "net_vega": self.net_vega,
        }


class StrategyBuilder:
    """Build and analyze options strategies.

    Provides pre-built strategy templates and custom multi-leg
    strategy construction with full payoff analysis.

    Example:
        builder = StrategyBuilder()
        legs = builder.build_bull_call_spread(spot=100, width=5, dte=30, iv=0.25)
        analysis = builder.analyze(legs, spot=100, iv=0.25)
    """

    def __init__(
        self,
        config: Optional[StrategyConfig] = None,
        pricing_engine: Optional[OptionsPricingEngine] = None,
    ):
        self.config = config or StrategyConfig()
        self.engine = pricing_engine or OptionsPricingEngine()

    # ========================================================================
    # Pre-built strategies
    # ========================================================================

    def build_long_call(
        self, spot: float, strike: float, dte: int, iv: float,
    ) -> list[OptionLeg]:
        """Long call: Buy 1 call."""
        T = dte / 365.0
        price = self.engine.black_scholes(spot, strike, T, self.engine.config.risk_free_rate, iv, "call")
        return [OptionLeg(option_type="call", strike=strike, premium=price.price,
                         quantity=1, expiry_days=dte, iv=iv, greeks=price)]

    def build_long_put(
        self, spot: float, strike: float, dte: int, iv: float,
    ) -> list[OptionLeg]:
        """Long put: Buy 1 put."""
        T = dte / 365.0
        price = self.engine.black_scholes(spot, strike, T, self.engine.config.risk_free_rate, iv, "put")
        return [OptionLeg(option_type="put", strike=strike, premium=price.price,
                         quantity=1, expiry_days=dte, iv=iv, greeks=price)]

    def build_covered_call(
        self, spot: float, call_strike: float, dte: int, iv: float,
    ) -> list[OptionLeg]:
        """Covered call: Long 100 shares + sell 1 call."""
        T = dte / 365.0
        call_price = self.engine.black_scholes(spot, call_strike, T, self.engine.config.risk_free_rate, iv, "call")
        return [
            OptionLeg(option_type="call", strike=call_strike, premium=call_price.price,
                     quantity=-1, expiry_days=dte, iv=iv, greeks=call_price),
        ]

    def build_cash_secured_put(
        self, spot: float, put_strike: float, dte: int, iv: float,
    ) -> list[OptionLeg]:
        """Cash-secured put: Sell 1 put."""
        T = dte / 365.0
        put_price = self.engine.black_scholes(spot, put_strike, T, self.engine.config.risk_free_rate, iv, "put")
        return [
            OptionLeg(option_type="put", strike=put_strike, premium=put_price.price,
                     quantity=-1, expiry_days=dte, iv=iv, greeks=put_price),
        ]

    def build_bull_call_spread(
        self, spot: float, width: float = 5.0, dte: int = 30, iv: float = 0.25,
    ) -> list[OptionLeg]:
        """Bull call spread: Buy lower call, sell higher call."""
        T = dte / 365.0
        r = self.engine.config.risk_free_rate
        lower_strike = spot
        upper_strike = spot + width

        lower_price = self.engine.black_scholes(spot, lower_strike, T, r, iv, "call")
        upper_price = self.engine.black_scholes(spot, upper_strike, T, r, iv, "call")

        return [
            OptionLeg(option_type="call", strike=lower_strike, premium=lower_price.price,
                     quantity=1, expiry_days=dte, iv=iv, greeks=lower_price),
            OptionLeg(option_type="call", strike=upper_strike, premium=upper_price.price,
                     quantity=-1, expiry_days=dte, iv=iv, greeks=upper_price),
        ]

    def build_bear_put_spread(
        self, spot: float, width: float = 5.0, dte: int = 30, iv: float = 0.25,
    ) -> list[OptionLeg]:
        """Bear put spread: Buy higher put, sell lower put."""
        T = dte / 365.0
        r = self.engine.config.risk_free_rate
        upper_strike = spot
        lower_strike = spot - width

        upper_price = self.engine.black_scholes(spot, upper_strike, T, r, iv, "put")
        lower_price = self.engine.black_scholes(spot, lower_strike, T, r, iv, "put")

        return [
            OptionLeg(option_type="put", strike=upper_strike, premium=upper_price.price,
                     quantity=1, expiry_days=dte, iv=iv, greeks=upper_price),
            OptionLeg(option_type="put", strike=lower_strike, premium=lower_price.price,
                     quantity=-1, expiry_days=dte, iv=iv, greeks=lower_price),
        ]

    def build_iron_condor(
        self, spot: float, put_width: float = 10.0, call_width: float = 10.0,
        wing_width: float = 5.0, dte: int = 30, iv: float = 0.25,
    ) -> list[OptionLeg]:
        """Iron condor: Bull put spread + bear call spread."""
        T = dte / 365.0
        r = self.engine.config.risk_free_rate

        put_sell = spot - put_width
        put_buy = put_sell - wing_width
        call_sell = spot + call_width
        call_buy = call_sell + wing_width

        p1 = self.engine.black_scholes(spot, put_buy, T, r, iv, "put")
        p2 = self.engine.black_scholes(spot, put_sell, T, r, iv, "put")
        p3 = self.engine.black_scholes(spot, call_sell, T, r, iv, "call")
        p4 = self.engine.black_scholes(spot, call_buy, T, r, iv, "call")

        return [
            OptionLeg(option_type="put", strike=put_buy, premium=p1.price,
                     quantity=1, expiry_days=dte, iv=iv, greeks=p1),
            OptionLeg(option_type="put", strike=put_sell, premium=p2.price,
                     quantity=-1, expiry_days=dte, iv=iv, greeks=p2),
            OptionLeg(option_type="call", strike=call_sell, premium=p3.price,
                     quantity=-1, expiry_days=dte, iv=iv, greeks=p3),
            OptionLeg(option_type="call", strike=call_buy, premium=p4.price,
                     quantity=1, expiry_days=dte, iv=iv, greeks=p4),
        ]

    def build_iron_butterfly(
        self, spot: float, wing_width: float = 10.0, dte: int = 30, iv: float = 0.25,
    ) -> list[OptionLeg]:
        """Iron butterfly: Sell ATM straddle + buy OTM wings."""
        T = dte / 365.0
        r = self.engine.config.risk_free_rate

        p1 = self.engine.black_scholes(spot, spot - wing_width, T, r, iv, "put")
        p2 = self.engine.black_scholes(spot, spot, T, r, iv, "put")
        p3 = self.engine.black_scholes(spot, spot, T, r, iv, "call")
        p4 = self.engine.black_scholes(spot, spot + wing_width, T, r, iv, "call")

        return [
            OptionLeg(option_type="put", strike=spot - wing_width, premium=p1.price,
                     quantity=1, expiry_days=dte, iv=iv, greeks=p1),
            OptionLeg(option_type="put", strike=spot, premium=p2.price,
                     quantity=-1, expiry_days=dte, iv=iv, greeks=p2),
            OptionLeg(option_type="call", strike=spot, premium=p3.price,
                     quantity=-1, expiry_days=dte, iv=iv, greeks=p3),
            OptionLeg(option_type="call", strike=spot + wing_width, premium=p4.price,
                     quantity=1, expiry_days=dte, iv=iv, greeks=p4),
        ]

    def build_straddle(
        self, spot: float, strike: Optional[float] = None, dte: int = 30, iv: float = 0.25,
    ) -> list[OptionLeg]:
        """Straddle: Buy ATM call + ATM put."""
        strike = strike or spot
        T = dte / 365.0
        r = self.engine.config.risk_free_rate

        call_price = self.engine.black_scholes(spot, strike, T, r, iv, "call")
        put_price = self.engine.black_scholes(spot, strike, T, r, iv, "put")

        return [
            OptionLeg(option_type="call", strike=strike, premium=call_price.price,
                     quantity=1, expiry_days=dte, iv=iv, greeks=call_price),
            OptionLeg(option_type="put", strike=strike, premium=put_price.price,
                     quantity=1, expiry_days=dte, iv=iv, greeks=put_price),
        ]

    def build_strangle(
        self, spot: float, put_offset: float = 5.0, call_offset: float = 5.0,
        dte: int = 30, iv: float = 0.25,
    ) -> list[OptionLeg]:
        """Strangle: Buy OTM call + OTM put."""
        T = dte / 365.0
        r = self.engine.config.risk_free_rate

        call_strike = spot + call_offset
        put_strike = spot - put_offset

        call_price = self.engine.black_scholes(spot, call_strike, T, r, iv, "call")
        put_price = self.engine.black_scholes(spot, put_strike, T, r, iv, "put")

        return [
            OptionLeg(option_type="call", strike=call_strike, premium=call_price.price,
                     quantity=1, expiry_days=dte, iv=iv, greeks=call_price),
            OptionLeg(option_type="put", strike=put_strike, premium=put_price.price,
                     quantity=1, expiry_days=dte, iv=iv, greeks=put_price),
        ]

    def build_jade_lizard(
        self, spot: float, put_strike: float, call_sell_strike: float,
        call_buy_strike: float, dte: int = 30, iv: float = 0.25,
    ) -> list[OptionLeg]:
        """Jade lizard: Short put + short call spread (no upside risk)."""
        T = dte / 365.0
        r = self.engine.config.risk_free_rate

        p1 = self.engine.black_scholes(spot, put_strike, T, r, iv, "put")
        p2 = self.engine.black_scholes(spot, call_sell_strike, T, r, iv, "call")
        p3 = self.engine.black_scholes(spot, call_buy_strike, T, r, iv, "call")

        return [
            OptionLeg(option_type="put", strike=put_strike, premium=p1.price,
                     quantity=-1, expiry_days=dte, iv=iv, greeks=p1),
            OptionLeg(option_type="call", strike=call_sell_strike, premium=p2.price,
                     quantity=-1, expiry_days=dte, iv=iv, greeks=p2),
            OptionLeg(option_type="call", strike=call_buy_strike, premium=p3.price,
                     quantity=1, expiry_days=dte, iv=iv, greeks=p3),
        ]

    # ========================================================================
    # Analysis
    # ========================================================================

    def analyze(
        self,
        legs: list[OptionLeg],
        spot: float,
        iv: float = 0.25,
        name: str = "",
        strategy_type: str = "custom",
    ) -> StrategyAnalysis:
        """Analyze a multi-leg strategy.

        Args:
            legs: List of option legs.
            spot: Current underlying price.
            iv: Implied volatility for PoP calc.
            name: Strategy name.
            strategy_type: Strategy type identifier.

        Returns:
            StrategyAnalysis with all metrics.
        """
        multiplier = self.config.contract_multiplier

        # Net debit/credit
        net_premium = sum(leg.premium * leg.quantity for leg in legs)

        # Payoff curve
        payoff = self.payoff_diagram(legs, spot)

        # Max profit / loss from payoff curve
        max_profit = float(payoff.pnl.max())
        max_loss = float(payoff.pnl.min())

        # Breakeven points
        breakevens = self._find_breakevens(payoff)

        # PoP
        dte = max(leg.expiry_days for leg in legs) if legs else 30
        pop = self.probability_of_profit(legs, spot, iv, dte)

        # Expected value (PoP * avg_win - (1-PoP) * avg_loss)
        profitable = payoff.pnl[payoff.pnl > 0]
        unprofitable = payoff.pnl[payoff.pnl <= 0]
        avg_win = float(profitable.mean()) if len(profitable) > 0 else 0
        avg_loss = float(unprofitable.mean()) if len(unprofitable) > 0 else 0
        ev = pop * avg_win + (1 - pop) * avg_loss

        # Risk/reward
        rr = abs(max_profit / max_loss) if max_loss != 0 else float("inf")

        # Net Greeks
        net_delta = sum(
            (leg.greeks.delta if leg.greeks else 0) * leg.quantity
            for leg in legs
        )
        net_gamma = sum(
            (leg.greeks.gamma if leg.greeks else 0) * leg.quantity
            for leg in legs
        )
        net_theta = sum(
            (leg.greeks.theta if leg.greeks else 0) * leg.quantity
            for leg in legs
        )
        net_vega = sum(
            (leg.greeks.vega if leg.greeks else 0) * leg.quantity
            for leg in legs
        )

        # Capital required
        capital = abs(max_loss) if max_loss < 0 else abs(net_premium) * multiplier

        # Annualized return
        ann_return = 0.0
        if capital > 0 and dte > 0:
            ann_return = (max_profit / capital) * (365 / dte)

        return StrategyAnalysis(
            name=name,
            strategy_type=strategy_type,
            legs=legs,
            max_profit=max_profit,
            max_loss=max_loss,
            breakeven_points=breakevens,
            probability_of_profit=pop,
            expected_value=ev,
            risk_reward_ratio=rr,
            net_debit_credit=net_premium * multiplier,
            capital_required=capital,
            annualized_return_max=ann_return,
            net_delta=net_delta,
            net_gamma=net_gamma,
            net_theta=net_theta,
            net_vega=net_vega,
            days_to_expiry=dte,
        )

    def payoff_diagram(
        self,
        legs: list[OptionLeg],
        spot: float,
        price_range_pct: float = 0.30,
    ) -> PayoffCurve:
        """Generate P&L at expiration across price range.

        Args:
            legs: Option legs.
            spot: Current underlying price.
            price_range_pct: Range as pct of spot (each direction).

        Returns:
            PayoffCurve with prices and P&L arrays.
        """
        n_points = self.config.payoff_price_points
        multiplier = self.config.contract_multiplier

        low = spot * (1 - price_range_pct)
        high = spot * (1 + price_range_pct)
        prices = np.linspace(low, high, n_points)
        pnl = np.zeros(n_points)

        for leg in legs:
            if leg.option_type == "call":
                intrinsic = np.maximum(prices - leg.strike, 0)
            else:
                intrinsic = np.maximum(leg.strike - prices, 0)

            leg_pnl = (intrinsic - leg.premium) * leg.quantity * multiplier
            pnl += leg_pnl

        breakevens = self._find_breakevens(PayoffCurve(prices=prices, pnl=pnl))

        return PayoffCurve(prices=prices, pnl=pnl, breakeven_points=breakevens)

    def probability_of_profit(
        self,
        legs: list[OptionLeg],
        spot: float,
        iv: float,
        dte: int,
        n_simulations: Optional[int] = None,
    ) -> float:
        """Monte Carlo probability of profit estimation.

        Args:
            legs: Option legs.
            spot: Current underlying price.
            iv: Implied volatility.
            dte: Days to expiration.
            n_simulations: Number of simulations.

        Returns:
            Probability of profit (0 to 1).
        """
        n_sims = n_simulations or self.config.default_pop_simulations
        multiplier = self.config.contract_multiplier
        dt = dte / 365.0

        if dt <= 0:
            return 0.0

        rng = np.random.default_rng(42)
        z = rng.standard_normal(n_sims)
        r = self.engine.config.risk_free_rate

        # GBM simulation
        ST = spot * np.exp((r - 0.5 * iv**2) * dt + iv * np.sqrt(dt) * z)

        # Calculate P&L for each simulation
        pnl = np.zeros(n_sims)
        for leg in legs:
            if leg.option_type == "call":
                intrinsic = np.maximum(ST - leg.strike, 0)
            else:
                intrinsic = np.maximum(leg.strike - ST, 0)
            pnl += (intrinsic - leg.premium) * leg.quantity * multiplier

        return float((pnl > 0).mean())

    def compare_strategies(
        self,
        strategies: dict[str, list[OptionLeg]],
        spot: float,
        iv: float = 0.25,
    ) -> pd.DataFrame:
        """Compare multiple strategies side by side.

        Args:
            strategies: Dict of strategy_name -> legs.
            spot: Current underlying price.
            iv: Implied volatility.

        Returns:
            DataFrame with comparison metrics.
        """
        rows = []
        for name, legs in strategies.items():
            analysis = self.analyze(legs, spot, iv, name=name)
            rows.append({
                "Strategy": name,
                "Max Profit": analysis.max_profit,
                "Max Loss": analysis.max_loss,
                "Breakeven": analysis.breakeven_points,
                "PoP": analysis.probability_of_profit,
                "Risk/Reward": analysis.risk_reward_ratio,
                "Capital": analysis.capital_required,
                "Ann. Return": analysis.annualized_return_max,
                "Net Delta": analysis.net_delta,
                "Net Theta": analysis.net_theta,
            })

        return pd.DataFrame(rows)

    def _find_breakevens(self, payoff: PayoffCurve) -> list[float]:
        """Find breakeven prices where P&L crosses zero."""
        breakevens = []
        for i in range(len(payoff.pnl) - 1):
            if payoff.pnl[i] * payoff.pnl[i + 1] < 0:
                # Linear interpolation
                x0, x1 = payoff.prices[i], payoff.prices[i + 1]
                y0, y1 = payoff.pnl[i], payoff.pnl[i + 1]
                be = x0 - y0 * (x1 - x0) / (y1 - y0)
                breakevens.append(round(float(be), 2))
        return breakevens
