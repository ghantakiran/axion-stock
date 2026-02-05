"""Recovery Estimation.

Estimates time-to-recovery from drawdowns based on historical
patterns, volatility, and drift assumptions.
"""

import logging
import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass
class RecoveryEstimate:
    """Estimated time to recover from drawdown."""
    symbol: str = ""
    current_drawdown: float = 0.0
    expected_days: float = 0.0
    median_days: float = 0.0
    days_90th_pctile: float = 0.0  # 90% chance of recovery by this many days
    probability_30d: float = 0.0  # Prob of recovery within 30 days
    probability_90d: float = 0.0
    probability_180d: float = 0.0
    method: str = ""  # historical, monte_carlo, analytical

    @property
    def is_quick_recovery(self) -> bool:
        return self.expected_days < 30

    @property
    def recovery_confidence(self) -> str:
        if self.probability_90d > 0.8:
            return "high"
        elif self.probability_90d > 0.5:
            return "medium"
        return "low"


@dataclass
class RecoveryPath:
    """Simulated or historical recovery path."""
    days: list[int] = field(default_factory=list)
    values: list[float] = field(default_factory=list)
    drawdowns: list[float] = field(default_factory=list)
    recovered: bool = False
    recovery_day: Optional[int] = None

    @property
    def n_days(self) -> int:
        return len(self.days)


@dataclass
class RecoveryAnalysis:
    """Comprehensive recovery analysis."""
    symbol: str = ""
    estimate: Optional[RecoveryEstimate] = None
    historical_recoveries: list[int] = field(default_factory=list)
    simulated_paths: int = 0
    avg_historical_recovery: float = 0.0
    recovery_volatility: float = 0.0

    @property
    def has_historical_data(self) -> bool:
        return len(self.historical_recoveries) > 0

    @property
    def recovery_uncertainty(self) -> str:
        if self.recovery_volatility < 10:
            return "low"
        elif self.recovery_volatility < 30:
            return "medium"
        return "high"


@dataclass
class BreakevenAnalysis:
    """Analysis of breakeven point."""
    current_value: float = 0.0
    peak_value: float = 0.0
    required_gain_pct: float = 0.0
    expected_daily_return: float = 0.0
    days_to_breakeven: float = 0.0
    compound_effect: float = 0.0  # Extra days due to compounding

    @property
    def is_deep_hole(self) -> bool:
        """Significant compounding effect (> 20% longer)."""
        return self.compound_effect > 0.2 * self.days_to_breakeven


# ---------------------------------------------------------------------------
# Recovery Estimator
# ---------------------------------------------------------------------------
class RecoveryEstimator:
    """Estimates recovery time from drawdowns.

    Uses analytical formulas, Monte Carlo simulation, and
    historical pattern matching to estimate recovery duration.
    """

    def __init__(
        self,
        default_drift: float = 0.0003,  # ~7.5% annual
        default_volatility: float = 0.015,  # ~24% annual
        n_simulations: int = 1000,
        max_days: int = 500,
    ) -> None:
        self.default_drift = default_drift
        self.default_volatility = default_volatility
        self.n_simulations = n_simulations
        self.max_days = max_days

    def analytical_estimate(
        self,
        current_drawdown: float,
        drift: Optional[float] = None,
        volatility: Optional[float] = None,
        symbol: str = "",
    ) -> RecoveryEstimate:
        """Estimate recovery using analytical approach.

        Uses drift-diffusion model to estimate expected recovery time.

        Args:
            current_drawdown: Current drawdown (negative).
            drift: Daily drift (return).
            volatility: Daily volatility.
            symbol: Ticker symbol.

        Returns:
            RecoveryEstimate with expected days.
        """
        mu = drift if drift is not None else self.default_drift
        sigma = volatility if volatility is not None else self.default_volatility

        if current_drawdown >= 0:
            return RecoveryEstimate(
                symbol=symbol,
                current_drawdown=0.0,
                expected_days=0.0,
                method="analytical",
            )

        # Required gain to recover
        required_gain = abs(current_drawdown) / (1 + current_drawdown)

        # Expected days assuming constant drift
        if mu <= 0:
            expected_days = float("inf")
        else:
            # First-order approximation
            expected_days = required_gain / mu

        # Add uncertainty from volatility
        sigma_effect = (sigma ** 2) / (2 * mu ** 2) if mu > 0 else 0
        adjusted_days = expected_days * (1 + sigma_effect)

        # Probability estimates using normal approximation
        def prob_recovery_by_day(n: int) -> float:
            if n <= 0 or mu <= 0:
                return 0.0
            expected_value = mu * n
            std = sigma * np.sqrt(n)
            z = (required_gain - expected_value) / std if std > 0 else float("inf")
            return float(1 - 0.5 * (1 + math.erf(z / math.sqrt(2))))

        return RecoveryEstimate(
            symbol=symbol,
            current_drawdown=round(current_drawdown, 6),
            expected_days=round(min(adjusted_days, self.max_days), 2),
            median_days=round(min(expected_days, self.max_days), 2),
            days_90th_pctile=round(min(adjusted_days * 2.5, self.max_days), 2),
            probability_30d=round(prob_recovery_by_day(30), 4),
            probability_90d=round(prob_recovery_by_day(90), 4),
            probability_180d=round(prob_recovery_by_day(180), 4),
            method="analytical",
        )

    def monte_carlo_estimate(
        self,
        current_drawdown: float,
        drift: Optional[float] = None,
        volatility: Optional[float] = None,
        symbol: str = "",
    ) -> RecoveryEstimate:
        """Estimate recovery using Monte Carlo simulation.

        Simulates many price paths and counts days to recovery.

        Args:
            current_drawdown: Current drawdown (negative).
            drift: Daily drift.
            volatility: Daily volatility.
            symbol: Ticker symbol.

        Returns:
            RecoveryEstimate from simulations.
        """
        mu = drift if drift is not None else self.default_drift
        sigma = volatility if volatility is not None else self.default_volatility

        if current_drawdown >= 0:
            return RecoveryEstimate(
                symbol=symbol,
                current_drawdown=0.0,
                expected_days=0.0,
                method="monte_carlo",
            )

        recovery_days = []
        recovered_30d = 0
        recovered_90d = 0
        recovered_180d = 0

        for _ in range(self.n_simulations):
            value = 1 + current_drawdown  # Start at current level relative to peak
            recovered = False

            for day in range(1, self.max_days + 1):
                ret = np.random.normal(mu, sigma)
                value *= (1 + ret)

                if value >= 1.0:
                    recovery_days.append(day)
                    recovered = True
                    if day <= 30:
                        recovered_30d += 1
                    if day <= 90:
                        recovered_90d += 1
                    if day <= 180:
                        recovered_180d += 1
                    break

            if not recovered:
                recovery_days.append(self.max_days)

        arr = np.array(recovery_days)
        return RecoveryEstimate(
            symbol=symbol,
            current_drawdown=round(current_drawdown, 6),
            expected_days=round(float(np.mean(arr)), 2),
            median_days=round(float(np.median(arr)), 2),
            days_90th_pctile=round(float(np.percentile(arr, 90)), 2),
            probability_30d=round(recovered_30d / self.n_simulations, 4),
            probability_90d=round(recovered_90d / self.n_simulations, 4),
            probability_180d=round(recovered_180d / self.n_simulations, 4),
            method="monte_carlo",
        )

    def historical_estimate(
        self,
        historical_recovery_days: list[int],
        current_drawdown: float,
        symbol: str = "",
    ) -> RecoveryEstimate:
        """Estimate recovery from historical patterns.

        Args:
            historical_recovery_days: Past recovery durations.
            current_drawdown: Current drawdown.
            symbol: Ticker symbol.

        Returns:
            RecoveryEstimate from historical data.
        """
        if not historical_recovery_days:
            return RecoveryEstimate(
                symbol=symbol,
                current_drawdown=round(current_drawdown, 6),
                method="historical",
            )

        arr = np.array(historical_recovery_days)
        return RecoveryEstimate(
            symbol=symbol,
            current_drawdown=round(current_drawdown, 6),
            expected_days=round(float(np.mean(arr)), 2),
            median_days=round(float(np.median(arr)), 2),
            days_90th_pctile=round(float(np.percentile(arr, 90)), 2),
            probability_30d=round(float(np.mean(arr <= 30)), 4),
            probability_90d=round(float(np.mean(arr <= 90)), 4),
            probability_180d=round(float(np.mean(arr <= 180)), 4),
            method="historical",
        )

    def breakeven_analysis(
        self,
        current_value: float,
        peak_value: float,
        expected_daily_return: Optional[float] = None,
    ) -> BreakevenAnalysis:
        """Analyze breakeven point from current drawdown.

        Args:
            current_value: Current portfolio/asset value.
            peak_value: Previous high-water mark.
            expected_daily_return: Expected daily return.

        Returns:
            BreakevenAnalysis with recovery insights.
        """
        mu = expected_daily_return if expected_daily_return else self.default_drift

        if current_value >= peak_value:
            return BreakevenAnalysis(
                current_value=current_value,
                peak_value=peak_value,
            )

        # Required gain percentage
        required_gain = (peak_value - current_value) / current_value

        # Simple linear estimate (ignoring compounding)
        simple_days = required_gain / mu if mu > 0 else float("inf")

        # Compound estimate: solve (1+mu)^n = 1 + required_gain
        if mu > 0:
            compound_days = np.log(1 + required_gain) / np.log(1 + mu)
        else:
            compound_days = float("inf")

        compound_effect = compound_days - simple_days if np.isfinite(compound_days) else 0

        return BreakevenAnalysis(
            current_value=round(current_value, 2),
            peak_value=round(peak_value, 2),
            required_gain_pct=round(required_gain, 6),
            expected_daily_return=round(mu, 6),
            days_to_breakeven=round(min(compound_days, self.max_days), 2),
            compound_effect=round(max(0, compound_effect), 2),
        )

    def comprehensive_analysis(
        self,
        current_drawdown: float,
        historical_recovery_days: Optional[list[int]] = None,
        drift: Optional[float] = None,
        volatility: Optional[float] = None,
        symbol: str = "",
    ) -> RecoveryAnalysis:
        """Perform comprehensive recovery analysis.

        Combines analytical, Monte Carlo, and historical methods.

        Args:
            current_drawdown: Current drawdown.
            historical_recovery_days: Past recovery durations.
            drift: Daily drift.
            volatility: Daily volatility.
            symbol: Ticker symbol.

        Returns:
            RecoveryAnalysis with full insights.
        """
        # Use Monte Carlo as primary estimate
        mc_estimate = self.monte_carlo_estimate(
            current_drawdown, drift, volatility, symbol
        )

        # Historical stats if available
        hist_recoveries = historical_recovery_days or []
        avg_hist = float(np.mean(hist_recoveries)) if hist_recoveries else 0.0
        std_hist = float(np.std(hist_recoveries)) if len(hist_recoveries) > 1 else 0.0

        return RecoveryAnalysis(
            symbol=symbol,
            estimate=mc_estimate,
            historical_recoveries=hist_recoveries,
            simulated_paths=self.n_simulations,
            avg_historical_recovery=round(avg_hist, 2),
            recovery_volatility=round(std_hist, 2),
        )
