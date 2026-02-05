"""Volatility Skew Analytics.

Risk reversal analysis, skew dynamics tracking, skew regime
classification, and skew term structure modeling.
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
class RiskReversal:
    """25-delta risk reversal (put vol - call vol)."""
    symbol: str = ""
    tenor_days: int = 30
    put_vol: float = 0.0  # OTM put IV
    call_vol: float = 0.0  # OTM call IV
    atm_vol: float = 0.0
    risk_reversal: float = 0.0  # put_vol - call_vol
    butterfly: float = 0.0  # (put_vol + call_vol)/2 - atm_vol

    @property
    def skew_direction(self) -> str:
        if self.risk_reversal > 0.01:
            return "put_skew"  # Normal: puts more expensive
        elif self.risk_reversal < -0.01:
            return "call_skew"  # Unusual: calls more expensive
        return "symmetric"

    @property
    def skew_magnitude(self) -> str:
        rr = abs(self.risk_reversal)
        if rr > 0.08:
            return "extreme"
        elif rr > 0.04:
            return "elevated"
        elif rr > 0.02:
            return "moderate"
        return "low"

    @property
    def wing_premium(self) -> float:
        """How much wings cost over ATM."""
        return self.butterfly


@dataclass
class SkewDynamics:
    """Skew behavior over time."""
    symbol: str = ""
    current_rr: float = 0.0
    avg_rr: float = 0.0
    std_rr: float = 0.0
    z_score: float = 0.0
    percentile: float = 50.0
    trend: str = "flat"  # steepening, flattening, flat
    n_observations: int = 0

    @property
    def is_extreme(self) -> bool:
        return abs(self.z_score) > 2.0

    @property
    def is_cheap(self) -> bool:
        """Skew below average — downside protection cheaper than usual."""
        return self.z_score < -1.0

    @property
    def is_expensive(self) -> bool:
        """Skew above average — downside protection pricey."""
        return self.z_score > 1.0


@dataclass
class SkewTermStructure:
    """Risk reversal across tenors."""
    symbol: str = ""
    points: list[tuple[int, float]] = field(default_factory=list)
    shape: str = "flat"  # normal, inverted, humped, flat
    front_rr: float = 0.0
    back_rr: float = 0.0
    slope: float = 0.0

    @property
    def n_tenors(self) -> int:
        return len(self.points)

    @property
    def is_inverted(self) -> bool:
        return self.shape == "inverted"


@dataclass
class SkewRegime:
    """Skew regime classification."""
    symbol: str = ""
    regime: str = "normal"  # panic, normal, complacent, speculative
    rr_level: float = 0.0
    butterfly_level: float = 0.0
    confidence: float = 0.5

    @property
    def is_panic(self) -> bool:
        return self.regime == "panic"

    @property
    def is_complacent(self) -> bool:
        return self.regime == "complacent"


# ---------------------------------------------------------------------------
# Skew Analyzer
# ---------------------------------------------------------------------------
class SkewAnalyzer:
    """Analyzes volatility skew dynamics and regimes.

    Computes risk reversals, tracks skew evolution, classifies
    skew regimes, and builds skew term structures.
    """

    def __init__(
        self,
        put_moneyness: float = 0.90,
        call_moneyness: float = 1.10,
    ) -> None:
        self.put_moneyness = put_moneyness
        self.call_moneyness = call_moneyness
        self._rr_history: dict[str, list[float]] = {}

    def compute_risk_reversal(
        self,
        put_vol: float,
        call_vol: float,
        atm_vol: float,
        tenor_days: int = 30,
        symbol: str = "",
    ) -> RiskReversal:
        """Compute risk reversal and butterfly from vol quotes.

        Args:
            put_vol: OTM put implied vol.
            call_vol: OTM call implied vol.
            atm_vol: ATM implied vol.
            tenor_days: Tenor in days.
            symbol: Ticker symbol.

        Returns:
            RiskReversal with skew metrics.
        """
        rr = put_vol - call_vol
        bfly = (put_vol + call_vol) / 2.0 - atm_vol

        result = RiskReversal(
            symbol=symbol,
            tenor_days=tenor_days,
            put_vol=round(put_vol, 6),
            call_vol=round(call_vol, 6),
            atm_vol=round(atm_vol, 6),
            risk_reversal=round(rr, 6),
            butterfly=round(bfly, 6),
        )

        # Track history
        self._rr_history.setdefault(symbol, []).append(rr)

        return result

    def compute_from_smile(
        self,
        moneyness_iv: list[tuple[float, float]],
        tenor_days: int = 30,
        symbol: str = "",
    ) -> RiskReversal:
        """Extract risk reversal from a vol smile.

        Args:
            moneyness_iv: List of (moneyness, iv) tuples.
            tenor_days: Tenor in days.
            symbol: Ticker symbol.

        Returns:
            RiskReversal computed from the smile.
        """
        if len(moneyness_iv) < 3:
            return RiskReversal(symbol=symbol, tenor_days=tenor_days)

        sorted_pts = sorted(moneyness_iv, key=lambda x: x[0])

        # Find closest to put/call/ATM moneyness
        def nearest_vol(target: float) -> float:
            return min(sorted_pts, key=lambda p: abs(p[0] - target))[1]

        put_v = nearest_vol(self.put_moneyness)
        call_v = nearest_vol(self.call_moneyness)
        atm_v = nearest_vol(1.0)

        return self.compute_risk_reversal(put_v, call_v, atm_v, tenor_days, symbol)

    def skew_dynamics(
        self,
        rr_history: list[float],
        symbol: str = "",
    ) -> SkewDynamics:
        """Analyze skew dynamics from risk reversal history.

        Args:
            rr_history: Historical risk reversal values.
            symbol: Ticker symbol.

        Returns:
            SkewDynamics with trend, z-score, percentile.
        """
        if len(rr_history) < 5:
            current = rr_history[-1] if rr_history else 0.0
            return SkewDynamics(
                symbol=symbol,
                current_rr=round(current, 6),
                n_observations=len(rr_history),
            )

        arr = np.array(rr_history)
        current = float(arr[-1])
        avg = float(np.mean(arr))
        std = float(np.std(arr))

        z = (current - avg) / std if std > 0 else 0.0
        pct = float(np.mean(arr <= current)) * 100.0

        # Trend from recent vs prior
        mid = len(arr) // 2
        recent_avg = float(np.mean(arr[mid:]))
        prior_avg = float(np.mean(arr[:mid]))
        diff = recent_avg - prior_avg
        if diff > 0.005:
            trend = "steepening"
        elif diff < -0.005:
            trend = "flattening"
        else:
            trend = "flat"

        return SkewDynamics(
            symbol=symbol,
            current_rr=round(current, 6),
            avg_rr=round(avg, 6),
            std_rr=round(std, 6),
            z_score=round(z, 4),
            percentile=round(pct, 2),
            trend=trend,
            n_observations=len(rr_history),
        )

    def skew_term_structure(
        self,
        tenor_rr: list[tuple[int, float]],
        symbol: str = "",
    ) -> SkewTermStructure:
        """Build skew term structure from per-tenor risk reversals.

        Args:
            tenor_rr: List of (tenor_days, risk_reversal) tuples.
            symbol: Ticker symbol.

        Returns:
            SkewTermStructure with shape classification.
        """
        if not tenor_rr:
            return SkewTermStructure(symbol=symbol)

        sorted_pts = sorted(tenor_rr, key=lambda x: x[0])
        front = sorted_pts[0][1]
        back = sorted_pts[-1][1]

        if len(sorted_pts) < 2:
            shape = "flat"
            slope = 0.0
        else:
            tenor_diff = sorted_pts[-1][0] - sorted_pts[0][0]
            slope = (back - front) / tenor_diff if tenor_diff > 0 else 0.0

            # Classify shape
            if len(sorted_pts) >= 3:
                mid_idx = len(sorted_pts) // 2
                mid_rr = sorted_pts[mid_idx][1]
                if mid_rr > front and mid_rr > back:
                    shape = "humped"
                elif front > back + 0.005:
                    shape = "inverted"
                elif back > front + 0.005:
                    shape = "normal"
                else:
                    shape = "flat"
            else:
                if front > back + 0.005:
                    shape = "inverted"
                elif back > front + 0.005:
                    shape = "normal"
                else:
                    shape = "flat"

        return SkewTermStructure(
            symbol=symbol,
            points=sorted_pts,
            shape=shape,
            front_rr=round(front, 6),
            back_rr=round(back, 6),
            slope=round(slope, 8),
        )

    def classify_regime(
        self,
        rr: float,
        butterfly: float,
        symbol: str = "",
    ) -> SkewRegime:
        """Classify skew regime from current risk reversal and butterfly.

        Args:
            rr: Current risk reversal.
            butterfly: Current butterfly spread.
            symbol: Ticker symbol.

        Returns:
            SkewRegime classification.
        """
        # Panic: steep put skew + high butterfly (fat tails priced)
        if rr > 0.06 and butterfly > 0.02:
            regime = "panic"
            confidence = min(1.0, (rr - 0.04) * 10)
        # Complacent: low skew + low butterfly
        elif abs(rr) < 0.02 and butterfly < 0.005:
            regime = "complacent"
            confidence = min(1.0, (0.02 - abs(rr)) * 30)
        # Speculative: call skew (calls more expensive)
        elif rr < -0.02:
            regime = "speculative"
            confidence = min(1.0, abs(rr) * 15)
        else:
            regime = "normal"
            confidence = 0.5

        return SkewRegime(
            symbol=symbol,
            regime=regime,
            rr_level=round(rr, 6),
            butterfly_level=round(butterfly, 6),
            confidence=round(confidence, 4),
        )
