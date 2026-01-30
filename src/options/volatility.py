"""Volatility Surface Modeling.

Constructs implied volatility surfaces from options chain data,
fits SVI parametrization, and computes volatility analytics.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from src.options.config import VolatilityConfig
from src.options.pricing import OptionsPricingEngine

try:
    from scipy.optimize import minimize
    from scipy.interpolate import griddata
    SCIPY_AVAILABLE = True
except (ImportError, ValueError):
    SCIPY_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class VolPoint:
    """Single point on the volatility surface."""

    moneyness: float = 1.0
    dte: int = 30
    iv: float = 0.30
    strike: float = 0.0
    option_type: str = "call"


@dataclass
class VolAnalytics:
    """Volatility analytics summary."""

    atm_iv: float = 0.0
    iv_skew_25d: float = 0.0
    iv_term_structure: dict = field(default_factory=dict)
    iv_percentile: float = 0.0
    iv_rank: float = 0.0
    hv_iv_spread: float = 0.0
    realized_vol_30d: float = 0.0
    realized_vol_60d: float = 0.0

    def to_dict(self) -> dict:
        return {
            "atm_iv": self.atm_iv,
            "iv_skew_25d": self.iv_skew_25d,
            "iv_term_structure": self.iv_term_structure,
            "iv_percentile": self.iv_percentile,
            "iv_rank": self.iv_rank,
            "hv_iv_spread": self.hv_iv_spread,
            "realized_vol_30d": self.realized_vol_30d,
            "realized_vol_60d": self.realized_vol_60d,
        }


@dataclass
class VolSurface:
    """Fitted volatility surface."""

    moneyness_grid: np.ndarray = field(default_factory=lambda: np.array([]))
    dte_grid: np.ndarray = field(default_factory=lambda: np.array([]))
    iv_grid: np.ndarray = field(default_factory=lambda: np.array([]))
    svi_params: dict = field(default_factory=dict)
    raw_points: list = field(default_factory=list)

    def get_iv(self, moneyness: float, dte: int) -> float:
        """Interpolate IV at given moneyness and DTE."""
        if self.svi_params:
            t = dte / 365.0
            return _svi_total_variance(
                np.log(moneyness), t, self.svi_params
            ) ** 0.5

        if len(self.iv_grid) == 0:
            return 0.30

        # Nearest point interpolation fallback
        if len(self.raw_points) > 0:
            min_dist = float("inf")
            best_iv = 0.30
            for p in self.raw_points:
                dist = (p.moneyness - moneyness) ** 2 + ((p.dte - dte) / 365) ** 2
                if dist < min_dist:
                    min_dist = dist
                    best_iv = p.iv
            return best_iv

        return 0.30


def _svi_total_variance(k: float, t: float, params: dict) -> float:
    """SVI (Stochastic Volatility Inspired) parametrization.

    w(k) = a + b * (rho * (k - m) + sqrt((k - m)^2 + sigma^2))

    Args:
        k: Log-moneyness ln(K/F).
        t: Time to expiration in years.
        params: SVI parameters {a, b, rho, m, sigma}.

    Returns:
        Total implied variance w = sigma^2 * t.
    """
    a = params.get("a", 0.04)
    b = params.get("b", 0.1)
    rho = params.get("rho", -0.3)
    m = params.get("m", 0.0)
    sigma = params.get("sigma", 0.2)

    w = a + b * (rho * (k - m) + np.sqrt((k - m) ** 2 + sigma ** 2))
    return max(w, 1e-8)


class VolatilitySurfaceBuilder:
    """Build and analyze volatility surfaces.

    Constructs IV surface from options chain data, fits SVI
    parametrization, and computes vol analytics.

    Example:
        builder = VolatilitySurfaceBuilder()
        surface = builder.build_from_chain(chain_df, spot_price=100)
        analytics = builder.compute_analytics(surface, price_history)
    """

    def __init__(
        self,
        config: Optional[VolatilityConfig] = None,
        pricing_engine: Optional[OptionsPricingEngine] = None,
    ):
        self.config = config or VolatilityConfig()
        self.engine = pricing_engine or OptionsPricingEngine()

    def build_from_chain(
        self,
        chain: pd.DataFrame,
        spot_price: float,
        risk_free_rate: float = 0.05,
    ) -> VolSurface:
        """Build volatility surface from options chain data.

        Args:
            chain: DataFrame with columns: strike, dte, mid_price, option_type.
            spot_price: Current underlying price.
            risk_free_rate: Risk-free rate.

        Returns:
            VolSurface with fitted parameters.
        """
        points = []

        for _, row in chain.iterrows():
            strike = row["strike"]
            dte = int(row["dte"])
            mid_price = row["mid_price"]
            opt_type = row.get("option_type", "call")

            if dte < self.config.min_dte or dte > self.config.max_dte:
                continue

            moneyness = strike / spot_price
            if moneyness < self.config.min_moneyness or moneyness > self.config.max_moneyness:
                continue

            if mid_price <= 0:
                continue

            T = dte / 365.0
            iv = self.engine.implied_volatility(
                mid_price, spot_price, strike, T, risk_free_rate, opt_type
            )

            if 0.01 < iv < 3.0:
                points.append(VolPoint(
                    moneyness=moneyness,
                    dte=dte,
                    iv=iv,
                    strike=strike,
                    option_type=opt_type,
                ))

        surface = VolSurface(raw_points=points)

        if len(points) >= 5 and SCIPY_AVAILABLE:
            surface.svi_params = self._fit_svi(points)

        if len(points) >= 4:
            surface = self._interpolate_grid(surface, points)

        return surface

    def build_from_ivs(self, iv_data: list[dict]) -> VolSurface:
        """Build surface from pre-computed IVs.

        Args:
            iv_data: List of dicts with keys: moneyness, dte, iv.

        Returns:
            VolSurface.
        """
        points = [
            VolPoint(moneyness=d["moneyness"], dte=d["dte"], iv=d["iv"])
            for d in iv_data
        ]

        surface = VolSurface(raw_points=points)

        if len(points) >= 5 and SCIPY_AVAILABLE:
            surface.svi_params = self._fit_svi(points)

        if len(points) >= 4:
            surface = self._interpolate_grid(surface, points)

        return surface

    def compute_analytics(
        self,
        surface: VolSurface,
        price_history: Optional[pd.Series] = None,
        iv_history: Optional[pd.Series] = None,
    ) -> VolAnalytics:
        """Compute volatility analytics.

        Args:
            surface: Fitted volatility surface.
            price_history: Historical price series for realized vol.
            iv_history: Historical ATM IV series for percentile/rank.

        Returns:
            VolAnalytics summary.
        """
        analytics = VolAnalytics()

        # ATM IV (moneyness=1.0, nearest DTE ~30)
        analytics.atm_iv = surface.get_iv(1.0, 30)

        # IV Skew: 25-delta put IV - 25-delta call IV
        # Approximate: ~0.9 moneyness put vs ~1.1 moneyness call
        put_iv = surface.get_iv(0.90, 30)
        call_iv = surface.get_iv(1.10, 30)
        analytics.iv_skew_25d = put_iv - call_iv

        # Term structure
        for dte in [7, 30, 60, 90, 180, 365]:
            iv = surface.get_iv(1.0, dte)
            analytics.iv_term_structure[dte] = iv

        # Realized volatility from price history
        if price_history is not None and len(price_history) >= 30:
            log_returns = np.log(price_history / price_history.shift(1)).dropna()
            analytics.realized_vol_30d = float(log_returns.tail(30).std() * np.sqrt(252))
            if len(log_returns) >= 60:
                analytics.realized_vol_60d = float(log_returns.tail(60).std() * np.sqrt(252))
            analytics.hv_iv_spread = analytics.realized_vol_30d - analytics.atm_iv

        # IV percentile and rank from history
        if iv_history is not None and len(iv_history) >= 20:
            current_iv = analytics.atm_iv
            analytics.iv_percentile = float((iv_history < current_iv).mean())
            iv_low = iv_history.min()
            iv_high = iv_history.max()
            if iv_high > iv_low:
                analytics.iv_rank = float((current_iv - iv_low) / (iv_high - iv_low))

        return analytics

    def get_vol_cone(
        self,
        price_history: pd.Series,
    ) -> pd.DataFrame:
        """Compute realized volatility cone.

        Args:
            price_history: Historical price series.

        Returns:
            DataFrame with vol statistics for each window.
        """
        log_returns = np.log(price_history / price_history.shift(1)).dropna()
        results = []

        for window in self.config.vol_cone_windows:
            if len(log_returns) < window:
                continue

            rolling_vol = log_returns.rolling(window).std() * np.sqrt(252)
            rolling_vol = rolling_vol.dropna()

            if len(rolling_vol) == 0:
                continue

            results.append({
                "window": window,
                "current": float(rolling_vol.iloc[-1]),
                "min": float(rolling_vol.min()),
                "percentile_25": float(rolling_vol.quantile(0.25)),
                "median": float(rolling_vol.median()),
                "percentile_75": float(rolling_vol.quantile(0.75)),
                "max": float(rolling_vol.max()),
            })

        return pd.DataFrame(results)

    def _fit_svi(self, points: list[VolPoint]) -> dict:
        """Fit SVI parametrization to observed IVs."""
        log_m = np.array([np.log(p.moneyness) for p in points])
        total_var = np.array([p.iv ** 2 * (p.dte / 365.0) for p in points])

        init = [
            self.config.svi_initial_params["a"],
            self.config.svi_initial_params["b"],
            self.config.svi_initial_params["rho"],
            self.config.svi_initial_params["m"],
            self.config.svi_initial_params["sigma"],
        ]

        def objective(params):
            a, b, rho, m, sigma = params
            if b < 0 or sigma < 0 or abs(rho) >= 1:
                return 1e10
            pred = a + b * (rho * (log_m - m) + np.sqrt((log_m - m) ** 2 + sigma ** 2))
            return float(np.sum((pred - total_var) ** 2))

        result = minimize(
            objective,
            init,
            method="Nelder-Mead",
            options={"maxiter": 1000},
        )

        a, b, rho, m, sigma = result.x
        return {"a": float(a), "b": float(b), "rho": float(rho),
                "m": float(m), "sigma": float(abs(sigma))}

    def _interpolate_grid(
        self,
        surface: VolSurface,
        points: list[VolPoint],
    ) -> VolSurface:
        """Create interpolated grid from raw points."""
        moneyness_arr = np.array([p.moneyness for p in points])
        dte_arr = np.array([p.dte for p in points])
        iv_arr = np.array([p.iv for p in points])

        m_min, m_max = moneyness_arr.min(), moneyness_arr.max()
        d_min, d_max = dte_arr.min(), dte_arr.max()

        m_grid = np.linspace(m_min, m_max, 20)
        d_grid = np.linspace(d_min, d_max, 20)
        mm, dd = np.meshgrid(m_grid, d_grid)

        if SCIPY_AVAILABLE:
            try:
                iv_grid = griddata(
                    (moneyness_arr, dte_arr),
                    iv_arr,
                    (mm, dd),
                    method="linear",
                    fill_value=np.nanmean(iv_arr),
                )
                surface.moneyness_grid = m_grid
                surface.dte_grid = d_grid
                surface.iv_grid = iv_grid
            except Exception:
                pass

        return surface
