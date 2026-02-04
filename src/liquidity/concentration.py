"""Liquidity Concentration & Risk Scoring.

Portfolio-level liquidity concentration risk assessment,
time-to-liquidate analysis, and liquidity-adjusted position limits.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass
class PositionLiquidity:
    """Liquidity assessment for a single position."""
    symbol: str = ""
    position_value: float = 0.0
    portfolio_weight: float = 0.0
    avg_daily_volume_usd: float = 0.0
    days_to_liquidate: float = 0.0
    participation_rate: float = 0.0
    liquidity_score: float = 0.0  # 0-100

    @property
    def is_concentrated(self) -> bool:
        return self.days_to_liquidate > 5.0

    @property
    def is_liquid(self) -> bool:
        return self.days_to_liquidate <= 1.0


@dataclass
class ConcentrationMetrics:
    """Portfolio-level liquidity concentration metrics."""
    n_positions: int = 0
    hhi_liquidity: float = 0.0  # Herfindahl index of liquidity risk
    pct_liquid_1d: float = 0.0  # % portfolio liquidatable in 1 day
    pct_liquid_5d: float = 0.0
    pct_liquid_20d: float = 0.0
    weighted_avg_dtl: float = 0.0  # Weight-averaged days to liquidate
    max_dtl: float = 0.0  # Max days to liquidate any position
    illiquid_weight: float = 0.0  # Weight of positions > 5 days DTL

    @property
    def concentration_level(self) -> str:
        if self.hhi_liquidity > 0.25:
            return "high"
        elif self.hhi_liquidity > 0.10:
            return "moderate"
        return "low"

    @property
    def is_portfolio_liquid(self) -> bool:
        return self.pct_liquid_5d >= 0.90


@dataclass
class LiquidityLimit:
    """Position limit based on liquidity constraints."""
    symbol: str = ""
    max_position_usd: float = 0.0
    max_weight_pct: float = 0.0
    current_weight_pct: float = 0.0
    headroom_pct: float = 0.0
    binding_constraint: str = ""  # dtl, participation, portfolio

    @property
    def is_at_limit(self) -> bool:
        return self.headroom_pct < 0.01

    @property
    def utilization_pct(self) -> float:
        if self.max_weight_pct <= 0:
            return 0.0
        return self.current_weight_pct / self.max_weight_pct


@dataclass
class LiquidityRiskReport:
    """Portfolio liquidity risk report."""
    positions: list[PositionLiquidity] = field(default_factory=list)
    concentration: ConcentrationMetrics = field(
        default_factory=ConcentrationMetrics
    )
    limits: list[LiquidityLimit] = field(default_factory=list)
    overall_score: float = 0.0  # 0-100
    risk_level: str = "low"  # low, moderate, high, critical

    @property
    def n_concentrated(self) -> int:
        return sum(1 for p in self.positions if p.is_concentrated)

    @property
    def n_at_limit(self) -> int:
        return sum(1 for l in self.limits if l.is_at_limit)


# ---------------------------------------------------------------------------
# Concentration Analyzer
# ---------------------------------------------------------------------------
class LiquidityConcentrationAnalyzer:
    """Analyzes portfolio liquidity concentration and position limits."""

    def __init__(
        self,
        max_participation_rate: float = 0.10,
        max_dtl_days: float = 20.0,
        max_single_position_pct: float = 0.10,
    ) -> None:
        self.max_participation_rate = max_participation_rate
        self.max_dtl_days = max_dtl_days
        self.max_single_position_pct = max_single_position_pct

    def assess_position(
        self,
        symbol: str,
        position_value: float,
        portfolio_value: float,
        avg_daily_volume_usd: float,
    ) -> PositionLiquidity:
        """Assess liquidity for a single position.

        Args:
            symbol: Ticker symbol.
            position_value: Position value in USD.
            portfolio_value: Total portfolio value.
            avg_daily_volume_usd: Average daily dollar volume.

        Returns:
            PositionLiquidity with DTL and score.
        """
        if portfolio_value <= 0 or avg_daily_volume_usd <= 0:
            return PositionLiquidity(symbol=symbol)

        weight = position_value / portfolio_value
        max_daily = avg_daily_volume_usd * self.max_participation_rate
        dtl = position_value / max_daily if max_daily > 0 else 999.0
        participation = position_value / avg_daily_volume_usd

        # Score: lower DTL = better
        if dtl <= 1:
            score = 90 + 10 * (1.0 - dtl)
        elif dtl <= 5:
            score = 70 + 20 * (5.0 - dtl) / 4.0
        elif dtl <= 20:
            score = 30 + 40 * (20.0 - dtl) / 15.0
        else:
            score = max(0, 30 * (1.0 - dtl / 100.0))

        return PositionLiquidity(
            symbol=symbol,
            position_value=round(position_value, 2),
            portfolio_weight=round(weight, 6),
            avg_daily_volume_usd=round(avg_daily_volume_usd, 2),
            days_to_liquidate=round(dtl, 2),
            participation_rate=round(participation, 6),
            liquidity_score=round(min(100, score), 1),
        )

    def concentration_metrics(
        self,
        positions: list[PositionLiquidity],
        portfolio_value: float,
    ) -> ConcentrationMetrics:
        """Compute portfolio-level concentration metrics.

        Args:
            positions: List of position liquidity assessments.
            portfolio_value: Total portfolio value.

        Returns:
            ConcentrationMetrics with HHI and liquidation timeline.
        """
        if not positions or portfolio_value <= 0:
            return ConcentrationMetrics()

        n = len(positions)

        # HHI of DTL-weighted positions
        # Higher HHI = more concentrated liquidity risk
        dtl_weights = []
        for p in positions:
            # Weight = position weight * normalized DTL
            dtl_norm = min(1.0, p.days_to_liquidate / self.max_dtl_days)
            dtl_weights.append(p.portfolio_weight * dtl_norm)

        total_dtl_w = sum(dtl_weights) or 1.0
        hhi = sum((w / total_dtl_w) ** 2 for w in dtl_weights)

        # Percentage liquidatable in 1, 5, 20 days
        liquid_1d = sum(
            p.portfolio_weight for p in positions if p.days_to_liquidate <= 1.0
        )
        liquid_5d = sum(
            p.portfolio_weight for p in positions if p.days_to_liquidate <= 5.0
        )
        liquid_20d = sum(
            p.portfolio_weight for p in positions if p.days_to_liquidate <= 20.0
        )

        # Weighted average DTL
        weighted_dtl = sum(
            p.portfolio_weight * p.days_to_liquidate for p in positions
        )

        max_dtl = max(p.days_to_liquidate for p in positions)
        illiquid_w = sum(
            p.portfolio_weight for p in positions if p.days_to_liquidate > 5.0
        )

        return ConcentrationMetrics(
            n_positions=n,
            hhi_liquidity=round(hhi, 4),
            pct_liquid_1d=round(liquid_1d, 4),
            pct_liquid_5d=round(liquid_5d, 4),
            pct_liquid_20d=round(liquid_20d, 4),
            weighted_avg_dtl=round(weighted_dtl, 2),
            max_dtl=round(max_dtl, 2),
            illiquid_weight=round(illiquid_w, 4),
        )

    def compute_limits(
        self,
        positions: list[PositionLiquidity],
        portfolio_value: float,
    ) -> list[LiquidityLimit]:
        """Compute position limits based on liquidity constraints.

        Args:
            positions: List of position liquidity assessments.
            portfolio_value: Total portfolio value.

        Returns:
            List of LiquidityLimit per position.
        """
        limits = []
        for p in positions:
            # Constraint 1: Max DTL
            max_by_dtl = (
                p.avg_daily_volume_usd * self.max_participation_rate * self.max_dtl_days
            )

            # Constraint 2: Max participation rate (already in DTL calc)
            max_by_participation = max_by_dtl

            # Constraint 3: Max portfolio weight
            max_by_weight = portfolio_value * self.max_single_position_pct

            # Binding = most restrictive
            max_pos = min(max_by_dtl, max_by_weight)
            if max_pos == max_by_weight:
                binding = "portfolio"
            else:
                binding = "dtl"

            max_weight = max_pos / portfolio_value if portfolio_value > 0 else 0.0
            headroom = max(0, max_weight - p.portfolio_weight)

            limits.append(LiquidityLimit(
                symbol=p.symbol,
                max_position_usd=round(max_pos, 2),
                max_weight_pct=round(max_weight * 100, 2),
                current_weight_pct=round(p.portfolio_weight * 100, 2),
                headroom_pct=round(headroom * 100, 2),
                binding_constraint=binding,
            ))

        return limits

    def generate_report(
        self,
        holdings: list[dict],
        portfolio_value: float,
    ) -> LiquidityRiskReport:
        """Generate comprehensive liquidity risk report.

        Args:
            holdings: List of {symbol, value, adv_usd} dicts.
            portfolio_value: Total portfolio value.

        Returns:
            LiquidityRiskReport with positions, concentration, and limits.
        """
        positions = [
            self.assess_position(
                h["symbol"], h["value"], portfolio_value, h["adv_usd"],
            )
            for h in holdings
        ]

        concentration = self.concentration_metrics(positions, portfolio_value)
        limits = self.compute_limits(positions, portfolio_value)

        # Overall score
        if positions:
            avg_score = float(np.mean([p.liquidity_score for p in positions]))
            concentration_penalty = concentration.hhi_liquidity * 20
            score = max(0, min(100, avg_score - concentration_penalty))
        else:
            score = 0.0

        if score >= 70:
            risk_level = "low"
        elif score >= 50:
            risk_level = "moderate"
        elif score >= 30:
            risk_level = "high"
        else:
            risk_level = "critical"

        return LiquidityRiskReport(
            positions=positions,
            concentration=concentration,
            limits=limits,
            overall_score=round(score, 1),
            risk_level=risk_level,
        )
