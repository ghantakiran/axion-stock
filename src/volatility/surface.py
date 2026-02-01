"""Volatility Surface Analyzer.

Builds and analyzes volatility surfaces (strike x tenor grids),
computes smile characteristics, skew, and butterfly spreads.
"""

import logging
from datetime import date
from typing import Optional

import numpy as np

from src.volatility.config import (
    SurfaceConfig,
    DEFAULT_SURFACE_CONFIG,
)
from src.volatility.models import (
    VolSmilePoint,
    VolSurface,
)

logger = logging.getLogger(__name__)


class VolSurfaceAnalyzer:
    """Builds and analyzes volatility surfaces."""

    def __init__(self, config: Optional[SurfaceConfig] = None) -> None:
        self.config = config or DEFAULT_SURFACE_CONFIG

    def build_surface(
        self,
        iv_data: dict[int, list[tuple[float, float]]],
        spot: float,
        symbol: str = "",
    ) -> VolSurface:
        """Build volatility surface from IV data.

        Args:
            iv_data: Dict of tenor_days -> list of (strike, iv) tuples.
            spot: Current spot price.
            symbol: Asset symbol.

        Returns:
            VolSurface with smile curves per tenor.
        """
        smiles: dict[int, list[VolSmilePoint]] = {}

        for tenor, strike_iv_pairs in iv_data.items():
            smile_points: list[VolSmilePoint] = []
            for strike, iv in sorted(strike_iv_pairs, key=lambda x: x[0]):
                moneyness = strike / spot if spot > 0 else 1.0
                smile_points.append(VolSmilePoint(
                    strike=strike,
                    moneyness=round(moneyness, 4),
                    implied_vol=round(iv, 6),
                ))
            smiles[tenor] = smile_points

        return VolSurface(
            symbol=symbol,
            spot=spot,
            smiles=smiles,
            date=date.today(),
        )

    def compute_smile(
        self,
        strikes: list[float],
        ivs: list[float],
        spot: float,
    ) -> list[VolSmilePoint]:
        """Build smile from strike/IV arrays.

        Args:
            strikes: Strike prices.
            ivs: Implied volatilities corresponding to strikes.
            spot: Current spot price.

        Returns:
            List of VolSmilePoint sorted by moneyness.
        """
        if len(strikes) != len(ivs):
            return []

        points: list[VolSmilePoint] = []
        for strike, iv in zip(strikes, ivs):
            moneyness = strike / spot if spot > 0 else 1.0
            points.append(VolSmilePoint(
                strike=strike,
                moneyness=round(moneyness, 4),
                implied_vol=round(iv, 6),
            ))

        points.sort(key=lambda p: p.moneyness)
        return points

    def compute_skew(
        self,
        surface: VolSurface,
        tenor_days: int,
    ) -> Optional[float]:
        """Compute 25-delta skew for a tenor.

        Skew = OTM put vol - OTM call vol (low moneyness - high moneyness).

        Returns:
            Skew value, or None if insufficient data.
        """
        return surface.skew(tenor_days)

    def compute_butterfly(
        self,
        surface: VolSurface,
        tenor_days: int,
    ) -> Optional[float]:
        """Compute 25-delta butterfly for a tenor.

        Butterfly = avg wing vol - ATM vol.

        Returns:
            Butterfly value, or None if insufficient data.
        """
        return surface.butterfly(tenor_days)

    def atm_term_structure(
        self,
        surface: VolSurface,
    ) -> list[tuple[int, float]]:
        """Extract ATM volatility term structure from surface.

        Returns:
            List of (tenor_days, atm_vol) tuples sorted by tenor.
        """
        result: list[tuple[int, float]] = []
        for tenor in surface.tenors:
            atm = surface.get_atm_vol(tenor)
            if atm is not None:
                result.append((tenor, atm))
        return result

    def smile_metrics(
        self,
        surface: VolSurface,
        tenor_days: int,
    ) -> dict[str, Optional[float]]:
        """Compute summary metrics for a smile.

        Returns:
            Dict with atm_vol, skew, butterfly, min_vol, max_vol.
        """
        atm = surface.get_atm_vol(tenor_days)
        skew = surface.skew(tenor_days)
        bfly = surface.butterfly(tenor_days)
        smile = surface.get_smile(tenor_days)

        min_vol = min((p.implied_vol for p in smile), default=None)
        max_vol = max((p.implied_vol for p in smile), default=None)

        return {
            "atm_vol": round(atm, 6) if atm is not None else None,
            "skew": round(skew, 6) if skew is not None else None,
            "butterfly": round(bfly, 6) if bfly is not None else None,
            "min_vol": round(min_vol, 6) if min_vol is not None else None,
            "max_vol": round(max_vol, 6) if max_vol is not None else None,
            "n_strikes": len(smile),
        }
