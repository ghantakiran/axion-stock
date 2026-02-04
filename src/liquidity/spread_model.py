"""Bid-Ask Spread Modeling.

Roll model estimation of effective spread from daily close prices,
intraday spread decomposition (adverse selection, order processing,
inventory), and spread forecasting using historical patterns.
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
class RollSpreadEstimate:
    """Roll (1984) model estimate of effective spread from close prices."""
    symbol: str = ""
    estimated_spread: float = 0.0  # Absolute spread estimate
    serial_covariance: float = 0.0  # First-order autocovariance
    n_observations: int = 0
    is_valid: bool = True  # False if covariance is positive

    @property
    def spread_bps(self) -> float:
        return self.estimated_spread * 10_000

    @property
    def is_liquid(self) -> bool:
        return self.estimated_spread < 0.001


@dataclass
class SpreadDecomposition:
    """Decomposition of bid-ask spread into components."""
    symbol: str = ""
    total_spread: float = 0.0
    adverse_selection_pct: float = 0.0  # Information component
    order_processing_pct: float = 0.0  # Fixed cost component
    inventory_pct: float = 0.0  # Inventory holding component
    adverse_selection_bps: float = 0.0
    order_processing_bps: float = 0.0
    inventory_bps: float = 0.0

    @property
    def information_share(self) -> float:
        return self.adverse_selection_pct

    @property
    def is_information_driven(self) -> bool:
        return self.adverse_selection_pct > 0.5


@dataclass
class SpreadForecast:
    """Forecast of expected spread over a horizon."""
    symbol: str = ""
    current_spread_bps: float = 0.0
    forecast_spread_bps: float = 0.0
    forecast_horizon_days: int = 1
    volatility_adjustment: float = 0.0
    volume_adjustment: float = 0.0
    confidence: float = 0.0

    @property
    def expected_change_bps(self) -> float:
        return self.forecast_spread_bps - self.current_spread_bps

    @property
    def is_widening(self) -> bool:
        return self.forecast_spread_bps > self.current_spread_bps * 1.05


@dataclass
class SpreadRegimeProfile:
    """Spread behavior across different market regimes."""
    symbol: str = ""
    avg_spread_normal: float = 0.0
    avg_spread_stressed: float = 0.0
    spread_stress_ratio: float = 0.0  # stressed / normal
    max_observed_spread: float = 0.0
    spread_at_vix_25: float = 0.0
    spread_at_vix_35: float = 0.0

    @property
    def stress_multiplier(self) -> float:
        return self.spread_stress_ratio

    @property
    def is_stress_sensitive(self) -> bool:
        return self.spread_stress_ratio > 3.0


# ---------------------------------------------------------------------------
# Spread Model
# ---------------------------------------------------------------------------
class SpreadModeler:
    """Models bid-ask spread dynamics and decomposition."""

    def __init__(self, min_observations: int = 20) -> None:
        self.min_observations = min_observations

    def roll_estimate(
        self,
        close_prices: list[float],
        symbol: str = "",
    ) -> RollSpreadEstimate:
        """Estimate effective spread using Roll (1984) model.

        The Roll model uses first-order autocovariance of price changes
        to estimate the effective spread: spread = 2 * sqrt(-cov).

        Args:
            close_prices: List of daily closing prices.
            symbol: Ticker symbol.

        Returns:
            RollSpreadEstimate with spread estimate.
        """
        if len(close_prices) < self.min_observations:
            return RollSpreadEstimate(
                symbol=symbol, n_observations=len(close_prices),
                is_valid=False,
            )

        prices = np.array(close_prices, dtype=float)
        returns = np.diff(prices) / prices[:-1]

        # First-order autocovariance of returns
        n = len(returns)
        mean_r = np.mean(returns)
        centered = returns - mean_r
        cov = np.sum(centered[:-1] * centered[1:]) / (n - 1)

        if cov >= 0:
            # Positive covariance invalidates Roll model
            return RollSpreadEstimate(
                symbol=symbol,
                estimated_spread=0.0,
                serial_covariance=round(float(cov), 8),
                n_observations=n,
                is_valid=False,
            )

        spread = 2.0 * np.sqrt(-cov)

        return RollSpreadEstimate(
            symbol=symbol,
            estimated_spread=round(float(spread), 6),
            serial_covariance=round(float(cov), 8),
            n_observations=n,
            is_valid=True,
        )

    def decompose_spread(
        self,
        spreads: list[float],
        trade_sizes: list[float],
        price_impacts: list[float],
        symbol: str = "",
    ) -> SpreadDecomposition:
        """Decompose spread into adverse selection, order processing, inventory.

        Uses the Huang-Stoll (1997) approach: adverse selection is
        estimated from price impact, order processing from residual.

        Args:
            spreads: List of observed bid-ask spreads.
            trade_sizes: List of trade sizes (shares).
            price_impacts: List of post-trade price changes (signed).
            symbol: Ticker symbol.

        Returns:
            SpreadDecomposition with component breakdown.
        """
        if not spreads or not trade_sizes or not price_impacts:
            return SpreadDecomposition(symbol=symbol)

        avg_spread = float(np.mean(spreads))
        if avg_spread <= 0:
            return SpreadDecomposition(symbol=symbol)

        # Adverse selection: proportion of spread due to information
        # Estimated from correlation between trade direction and price impact
        impacts = np.array(price_impacts, dtype=float)
        sizes = np.array(trade_sizes, dtype=float)

        # Normalize impacts by spread
        avg_abs_impact = float(np.mean(np.abs(impacts)))
        adverse_pct = min(1.0, avg_abs_impact / avg_spread) if avg_spread > 0 else 0.0

        # Inventory: estimated from trade size variation effect
        size_std = float(np.std(sizes))
        size_mean = float(np.mean(sizes))
        size_cv = size_std / size_mean if size_mean > 0 else 0.0
        inventory_pct = min(0.5, size_cv * 0.3)

        # Order processing: residual
        order_pct = max(0.0, 1.0 - adverse_pct - inventory_pct)

        # Normalize to sum to 1
        total = adverse_pct + order_pct + inventory_pct
        if total > 0:
            adverse_pct /= total
            order_pct /= total
            inventory_pct /= total

        spread_bps = avg_spread * 10_000

        return SpreadDecomposition(
            symbol=symbol,
            total_spread=round(avg_spread, 6),
            adverse_selection_pct=round(adverse_pct, 4),
            order_processing_pct=round(order_pct, 4),
            inventory_pct=round(inventory_pct, 4),
            adverse_selection_bps=round(spread_bps * adverse_pct, 2),
            order_processing_bps=round(spread_bps * order_pct, 2),
            inventory_bps=round(spread_bps * inventory_pct, 2),
        )

    def forecast_spread(
        self,
        historical_spreads_bps: list[float],
        current_volatility: float = 0.0,
        avg_volatility: float = 0.0,
        current_volume_ratio: float = 1.0,
        horizon_days: int = 5,
        symbol: str = "",
    ) -> SpreadForecast:
        """Forecast spread based on historical patterns and conditions.

        Uses mean-reversion with volatility and volume adjustments.

        Args:
            historical_spreads_bps: Historical spread in basis points.
            current_volatility: Current realized volatility.
            avg_volatility: Long-term average volatility.
            current_volume_ratio: Current volume / average volume.
            horizon_days: Forecast horizon in days.
            symbol: Ticker symbol.

        Returns:
            SpreadForecast with expected spread.
        """
        if not historical_spreads_bps:
            return SpreadForecast(symbol=symbol)

        spreads = np.array(historical_spreads_bps, dtype=float)
        current = float(spreads[-1])
        mean_spread = float(np.mean(spreads))

        # Mean reversion: spread tends toward average
        # Reversion speed increases with horizon
        reversion_speed = min(1.0, horizon_days * 0.1)
        base_forecast = current + (mean_spread - current) * reversion_speed

        # Volatility adjustment: higher vol = wider spreads
        vol_adj = 0.0
        if avg_volatility > 0 and current_volatility > 0:
            vol_ratio = current_volatility / avg_volatility
            vol_adj = (vol_ratio - 1.0) * mean_spread * 0.5

        # Volume adjustment: higher volume = tighter spreads
        volume_adj = 0.0
        if current_volume_ratio > 0:
            volume_adj = -(current_volume_ratio - 1.0) * mean_spread * 0.2

        forecast = max(0.1, base_forecast + vol_adj + volume_adj)

        # Confidence decreases with horizon
        confidence = max(0.2, 0.9 - horizon_days * 0.05)

        return SpreadForecast(
            symbol=symbol,
            current_spread_bps=round(current, 2),
            forecast_spread_bps=round(forecast, 2),
            forecast_horizon_days=horizon_days,
            volatility_adjustment=round(vol_adj, 2),
            volume_adjustment=round(volume_adj, 2),
            confidence=round(confidence, 4),
        )

    def regime_profile(
        self,
        spreads_bps: list[float],
        volatilities: list[float],
        symbol: str = "",
    ) -> SpreadRegimeProfile:
        """Profile spread behavior across volatility regimes.

        Args:
            spreads_bps: Historical spreads in basis points.
            volatilities: Corresponding volatility values.
            symbol: Ticker symbol.

        Returns:
            SpreadRegimeProfile with stress analysis.
        """
        if not spreads_bps or not volatilities:
            return SpreadRegimeProfile(symbol=symbol)

        spreads = np.array(spreads_bps, dtype=float)
        vols = np.array(volatilities, dtype=float)
        n = min(len(spreads), len(vols))
        spreads = spreads[:n]
        vols = vols[:n]

        # Normal: below median vol, Stressed: above 75th percentile
        vol_median = float(np.median(vols))
        vol_p75 = float(np.percentile(vols, 75))

        normal_mask = vols <= vol_median
        stressed_mask = vols >= vol_p75

        avg_normal = float(np.mean(spreads[normal_mask])) if normal_mask.any() else 0.0
        avg_stressed = float(np.mean(spreads[stressed_mask])) if stressed_mask.any() else 0.0

        ratio = avg_stressed / avg_normal if avg_normal > 0 else 0.0

        # Estimate spread at specific VIX levels using linear interpolation
        if len(vols) > 5:
            # Simple linear regression: spread = a + b * vol
            vol_mean = float(np.mean(vols))
            spread_mean = float(np.mean(spreads))
            cov_sv = float(np.mean((vols - vol_mean) * (spreads - spread_mean)))
            var_v = float(np.var(vols))
            if var_v > 0:
                beta = cov_sv / var_v
                alpha = spread_mean - beta * vol_mean
                spread_vix_25 = max(0.0, alpha + beta * 25.0)
                spread_vix_35 = max(0.0, alpha + beta * 35.0)
            else:
                spread_vix_25 = avg_normal
                spread_vix_35 = avg_stressed
        else:
            spread_vix_25 = avg_normal
            spread_vix_35 = avg_stressed

        return SpreadRegimeProfile(
            symbol=symbol,
            avg_spread_normal=round(avg_normal, 2),
            avg_spread_stressed=round(avg_stressed, 2),
            spread_stress_ratio=round(ratio, 2),
            max_observed_spread=round(float(np.max(spreads)), 2),
            spread_at_vix_25=round(spread_vix_25, 2),
            spread_at_vix_35=round(spread_vix_35, 2),
        )
