"""Volatility Computation Engine.

Provides multiple volatility estimators: historical (close-to-close),
EWMA, Parkinson (high-low), and Garman-Klass (OHLC).
Also computes volatility cones and implied vs realized spreads.
"""

import logging
from datetime import date
from typing import Optional

import numpy as np
import pandas as pd

from src.volatility.config import (
    VolConfig,
    VolMethod,
    DEFAULT_VOL_CONFIG,
)
from src.volatility.models import (
    VolEstimate,
    TermStructure,
    TermStructurePoint,
    VolConePoint,
)

logger = logging.getLogger(__name__)


class VolatilityEngine:
    """Computes volatility using multiple estimators."""

    def __init__(self, config: Optional[VolConfig] = None) -> None:
        self.config = config or DEFAULT_VOL_CONFIG

    def compute_historical(
        self,
        returns: pd.Series,
        window: Optional[int] = None,
        symbol: str = "",
    ) -> VolEstimate:
        """Close-to-close historical volatility.

        Args:
            returns: Log or simple returns series.
            window: Rolling window. Uses last `window` observations.
            symbol: Asset symbol.

        Returns:
            Annualized VolEstimate.
        """
        window = window or self.config.default_window
        if len(returns) < self.config.min_periods:
            return VolEstimate(symbol=symbol, method=VolMethod.HISTORICAL, window=window)

        tail = returns.iloc[-window:] if len(returns) >= window else returns
        daily_vol = float(tail.std(ddof=1))
        ann_vol = daily_vol * np.sqrt(self.config.annualization_factor)

        return VolEstimate(
            symbol=symbol,
            value=round(ann_vol, 6),
            method=VolMethod.HISTORICAL,
            window=window,
            annualized=True,
        )

    def compute_ewma(
        self,
        returns: pd.Series,
        lambda_: Optional[float] = None,
        symbol: str = "",
    ) -> VolEstimate:
        """Exponentially weighted moving average volatility.

        Args:
            returns: Returns series.
            lambda_: Decay factor (0 < lambda < 1). Higher = slower decay.
            symbol: Asset symbol.

        Returns:
            Annualized VolEstimate.
        """
        lambda_ = lambda_ if lambda_ is not None else self.config.ewma_lambda
        if len(returns) < self.config.min_periods:
            return VolEstimate(symbol=symbol, method=VolMethod.EWMA)

        # EWMA variance
        squared = returns ** 2
        ewma_var = float(squared.ewm(alpha=1 - lambda_, adjust=False).mean().iloc[-1])
        daily_vol = np.sqrt(ewma_var)
        ann_vol = daily_vol * np.sqrt(self.config.annualization_factor)

        return VolEstimate(
            symbol=symbol,
            value=round(ann_vol, 6),
            method=VolMethod.EWMA,
            window=len(returns),
            annualized=True,
        )

    def compute_parkinson(
        self,
        high: pd.Series,
        low: pd.Series,
        window: Optional[int] = None,
        symbol: str = "",
    ) -> VolEstimate:
        """Parkinson high-low volatility estimator.

        More efficient than close-to-close (uses intraday range).
        Var = (1 / 4*ln(2)) * mean(ln(H/L)^2)

        Args:
            high: High prices.
            low: Low prices.
            window: Window for computation.
            symbol: Asset symbol.

        Returns:
            Annualized VolEstimate.
        """
        window = window or self.config.default_window
        if len(high) < self.config.min_periods or len(low) < self.config.min_periods:
            return VolEstimate(symbol=symbol, method=VolMethod.PARKINSON, window=window)

        h = high.iloc[-window:] if len(high) >= window else high
        l = low.iloc[-window:] if len(low) >= window else low

        log_hl = np.log(h.values / l.values)
        parkinson_var = float(np.mean(log_hl ** 2) / (4.0 * np.log(2.0)))
        daily_vol = np.sqrt(parkinson_var)
        ann_vol = daily_vol * np.sqrt(self.config.annualization_factor)

        return VolEstimate(
            symbol=symbol,
            value=round(ann_vol, 6),
            method=VolMethod.PARKINSON,
            window=window,
            annualized=True,
        )

    def compute_garman_klass(
        self,
        open_: pd.Series,
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        window: Optional[int] = None,
        symbol: str = "",
    ) -> VolEstimate:
        """Garman-Klass OHLC volatility estimator.

        Most efficient single-day estimator using all four OHLC prices.
        Var = 0.5 * ln(H/L)^2 - (2*ln(2)-1) * ln(C/O)^2

        Args:
            open_: Open prices.
            high: High prices.
            low: Low prices.
            close: Close prices.
            window: Window for computation.
            symbol: Asset symbol.

        Returns:
            Annualized VolEstimate.
        """
        window = window or self.config.default_window
        n = min(len(open_), len(high), len(low), len(close))
        if n < self.config.min_periods:
            return VolEstimate(symbol=symbol, method=VolMethod.GARMAN_KLASS, window=window)

        o = open_.iloc[-window:].values if n >= window else open_.values
        h = high.iloc[-window:].values if n >= window else high.values
        l = low.iloc[-window:].values if n >= window else low.values
        c = close.iloc[-window:].values if n >= window else close.values

        log_hl = np.log(h / l)
        log_co = np.log(c / o)

        gk_var = float(np.mean(
            0.5 * log_hl ** 2 - (2.0 * np.log(2.0) - 1.0) * log_co ** 2
        ))
        gk_var = max(0.0, gk_var)
        daily_vol = np.sqrt(gk_var)
        ann_vol = daily_vol * np.sqrt(self.config.annualization_factor)

        return VolEstimate(
            symbol=symbol,
            value=round(ann_vol, 6),
            method=VolMethod.GARMAN_KLASS,
            window=window,
            annualized=True,
        )

    def compute_all(
        self,
        returns: pd.Series,
        high: Optional[pd.Series] = None,
        low: Optional[pd.Series] = None,
        open_: Optional[pd.Series] = None,
        close: Optional[pd.Series] = None,
        window: Optional[int] = None,
        symbol: str = "",
    ) -> dict[VolMethod, VolEstimate]:
        """Compute all available volatility estimators.

        Returns:
            Dict mapping method to VolEstimate.
        """
        results: dict[VolMethod, VolEstimate] = {}

        results[VolMethod.HISTORICAL] = self.compute_historical(returns, window, symbol)
        results[VolMethod.EWMA] = self.compute_ewma(returns, symbol=symbol)

        if high is not None and low is not None:
            results[VolMethod.PARKINSON] = self.compute_parkinson(high, low, window, symbol)

        if open_ is not None and high is not None and low is not None and close is not None:
            results[VolMethod.GARMAN_KLASS] = self.compute_garman_klass(
                open_, high, low, close, window, symbol
            )

        return results

    def compute_vol_cone(
        self,
        returns: pd.Series,
        symbol: str = "",
    ) -> list[VolConePoint]:
        """Compute volatility cone across multiple windows.

        For each window, computes rolling vol and then percentile bands.

        Args:
            returns: Full returns history.
            symbol: Asset symbol.

        Returns:
            List of VolConePoint, one per window.
        """
        results: list[VolConePoint] = []

        for window in self.config.cone_windows:
            if len(returns) < window + self.config.min_periods:
                continue

            rolling_vol = returns.rolling(window).std(ddof=1) * np.sqrt(
                self.config.annualization_factor
            )
            rolling_vol = rolling_vol.dropna()

            if len(rolling_vol) == 0:
                continue

            pcts: dict[float, float] = {}
            for p in self.config.cone_percentiles:
                pcts[p] = round(float(np.percentile(rolling_vol, p)), 6)

            current = round(float(rolling_vol.iloc[-1]), 6)

            results.append(VolConePoint(
                window=window,
                percentiles=pcts,
                current=current,
            ))

        return results

    def compute_term_structure(
        self,
        returns: pd.Series,
        tenor_days: Optional[tuple[int, ...]] = None,
        iv_by_tenor: Optional[dict[int, float]] = None,
        symbol: str = "",
    ) -> TermStructure:
        """Compute vol term structure from realized and/or implied vol.

        Args:
            returns: Returns series for realized vol.
            tenor_days: Tenor windows in trading days.
            iv_by_tenor: Optional implied vol by tenor (days -> IV).
            symbol: Asset symbol.

        Returns:
            TermStructure with points.
        """
        tenors = tenor_days or self.config.cone_windows
        points: list[TermStructurePoint] = []

        for t in tenors:
            rv = None
            if len(returns) >= t:
                tail = returns.iloc[-t:]
                rv = round(
                    float(tail.std(ddof=1) * np.sqrt(self.config.annualization_factor)),
                    6,
                )

            iv = None
            if iv_by_tenor and t in iv_by_tenor:
                iv = iv_by_tenor[t]

            if rv is not None or iv is not None:
                points.append(TermStructurePoint(
                    tenor_days=t,
                    implied_vol=iv,
                    realized_vol=rv,
                ))

        return TermStructure(
            symbol=symbol,
            points=points,
            date=date.today(),
        )

    def implied_vs_realized(
        self,
        implied_vol: float,
        realized_vol: float,
    ) -> dict[str, float]:
        """Compute implied vs realized vol metrics.

        Returns:
            Dict with spread, ratio, and premium.
        """
        spread = implied_vol - realized_vol
        ratio = implied_vol / realized_vol if realized_vol > 0 else 0.0

        return {
            "implied_vol": round(implied_vol, 6),
            "realized_vol": round(realized_vol, 6),
            "spread": round(spread, 6),
            "ratio": round(ratio, 3),
            "premium_pct": round(spread / realized_vol * 100, 2) if realized_vol > 0 else 0.0,
        }

    def compute_percentile(
        self,
        current_vol: float,
        returns: pd.Series,
        window: Optional[int] = None,
    ) -> float:
        """Compute where current vol sits in historical distribution.

        Args:
            current_vol: Current annualized vol.
            returns: Historical returns.
            window: Rolling window for historical vol distribution.

        Returns:
            Percentile (0-100).
        """
        window = window or self.config.default_window
        if len(returns) < window + self.config.min_periods:
            return 50.0

        rolling_vol = returns.rolling(window).std(ddof=1) * np.sqrt(
            self.config.annualization_factor
        )
        rolling_vol = rolling_vol.dropna()

        if len(rolling_vol) == 0:
            return 50.0

        pct = float((rolling_vol < current_vol).sum() / len(rolling_vol) * 100)
        return round(pct, 1)
