"""Sentiment Momentum and Trend Detection.

Tracks sentiment changes over time to identify momentum,
trend reversals, and acceleration/deceleration patterns.
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
class SentimentSnapshot:
    """Point-in-time sentiment reading."""
    symbol: str = ""
    score: float = 0.0  # -1 to +1
    period_index: int = 0  # Time ordering (0=oldest)


@dataclass
class MomentumResult:
    """Sentiment momentum for a symbol."""
    symbol: str = ""
    current_score: float = 0.0
    momentum: float = 0.0  # Rate of change
    acceleration: float = 0.0  # Change in momentum
    trend_direction: str = "flat"  # improving, deteriorating, flat
    trend_strength: float = 0.0  # 0-1
    n_periods: int = 0
    is_inflecting: bool = False  # Momentum changing sign

    @property
    def is_positive_momentum(self) -> bool:
        return self.momentum > 0.02

    @property
    def is_negative_momentum(self) -> bool:
        return self.momentum < -0.02

    @property
    def is_accelerating(self) -> bool:
        return self.acceleration > 0.01 and self.momentum > 0

    @property
    def is_decelerating(self) -> bool:
        return self.acceleration < -0.01 and self.momentum > 0

    @property
    def signal_strength(self) -> float:
        """Combined momentum + trend signal strength."""
        return min(1.0, abs(self.momentum) * 5.0 * self.trend_strength)


@dataclass
class TrendReversal:
    """Detected sentiment trend reversal."""
    symbol: str = ""
    reversal_type: str = ""  # bullish_reversal, bearish_reversal
    from_score: float = 0.0
    to_score: float = 0.0
    magnitude: float = 0.0
    confidence: float = 0.0

    @property
    def is_bullish_reversal(self) -> bool:
        return self.reversal_type == "bullish_reversal"

    @property
    def is_significant(self) -> bool:
        return self.magnitude >= 0.3 and self.confidence >= 0.5


@dataclass
class MomentumSummary:
    """Cross-symbol momentum summary."""
    n_symbols: int = 0
    n_improving: int = 0
    n_deteriorating: int = 0
    n_flat: int = 0
    n_inflecting: int = 0
    avg_momentum: float = 0.0
    strongest_up: str = ""
    strongest_down: str = ""
    breadth: float = 0.5  # Fraction with positive momentum

    @property
    def market_momentum(self) -> str:
        if self.breadth > 0.65:
            return "positive"
        elif self.breadth < 0.35:
            return "negative"
        return "neutral"


# ---------------------------------------------------------------------------
# Sentiment Momentum Tracker
# ---------------------------------------------------------------------------
class SentimentMomentumTracker:
    """Tracks sentiment momentum and detects trend changes.

    Computes momentum as rate-of-change, acceleration as the
    second derivative, and detects inflection points and reversals.
    """

    def __init__(
        self,
        min_periods: int = 3,
        smoothing_factor: float = 0.3,
        reversal_threshold: float = 0.2,
    ) -> None:
        self.min_periods = min_periods
        self.smoothing_factor = smoothing_factor
        self.reversal_threshold = reversal_threshold
        self._history: dict[str, list[float]] = {}

    def add_snapshot(self, snapshot: SentimentSnapshot) -> None:
        """Record a sentiment snapshot.

        Args:
            snapshot: Point-in-time sentiment reading.
        """
        self._history.setdefault(snapshot.symbol, []).append(snapshot.score)

    def add_scores(self, symbol: str, scores: list[float]) -> None:
        """Bulk-add historical scores.

        Args:
            symbol: Ticker symbol.
            scores: List of scores in chronological order.
        """
        self._history[symbol] = list(scores)

    def compute_momentum(
        self,
        symbol: str,
        scores: Optional[list[float]] = None,
    ) -> MomentumResult:
        """Compute sentiment momentum for a symbol.

        Args:
            symbol: Ticker symbol.
            scores: Optional explicit score series (overrides history).

        Returns:
            MomentumResult with momentum, acceleration, and trend.
        """
        series = scores if scores is not None else self._history.get(symbol, [])

        if len(series) < self.min_periods:
            return MomentumResult(
                symbol=symbol,
                current_score=series[-1] if series else 0.0,
                n_periods=len(series),
            )

        arr = np.array(series, dtype=float)

        # Exponential smoothing
        smoothed = self._ema(arr, self.smoothing_factor)

        current = float(smoothed[-1])

        # Momentum: first derivative (rate of change)
        diffs = np.diff(smoothed)
        momentum = float(diffs[-1])

        # Acceleration: second derivative
        if len(diffs) >= 2:
            acceleration = float(diffs[-1] - diffs[-2])
        else:
            acceleration = 0.0

        # Trend via linear regression
        x = np.arange(len(smoothed))
        coeffs = np.polyfit(x, smoothed, 1)
        slope = float(coeffs[0])
        r_squared = self._r_squared(x, smoothed, coeffs)

        if slope > 0.01:
            trend_dir = "improving"
        elif slope < -0.01:
            trend_dir = "deteriorating"
        else:
            trend_dir = "flat"

        # Inflection: momentum changing sign
        if len(diffs) >= 2:
            is_inflecting = (diffs[-1] * diffs[-2]) < 0
        else:
            is_inflecting = False

        return MomentumResult(
            symbol=symbol,
            current_score=round(current, 4),
            momentum=round(momentum, 4),
            acceleration=round(acceleration, 4),
            trend_direction=trend_dir,
            trend_strength=round(float(r_squared), 4),
            n_periods=len(series),
            is_inflecting=is_inflecting,
        )

    def detect_reversal(
        self,
        symbol: str,
        scores: Optional[list[float]] = None,
        window: int = 5,
    ) -> Optional[TrendReversal]:
        """Detect if a trend reversal has occurred.

        Args:
            symbol: Ticker symbol.
            scores: Optional explicit score series.
            window: Window for comparing recent vs prior trend.

        Returns:
            TrendReversal if detected, None otherwise.
        """
        series = scores if scores is not None else self._history.get(symbol, [])

        if len(series) < window * 2:
            return None

        prior = series[-window * 2: -window]
        recent = series[-window:]

        prior_avg = float(np.mean(prior))
        recent_avg = float(np.mean(recent))
        change = recent_avg - prior_avg

        if abs(change) < self.reversal_threshold:
            return None

        # Check it's actually a reversal (not continuation)
        prior_trend = float(np.mean(np.diff(prior)))
        recent_trend = float(np.mean(np.diff(recent)))

        if prior_trend * recent_trend >= 0:
            # Same direction — not a reversal
            return None

        reversal_type = "bullish_reversal" if change > 0 else "bearish_reversal"

        # Confidence from magnitude and consistency
        magnitude = abs(change)
        consistency = 1.0 - float(np.std(recent)) / max(0.01, abs(recent_avg))
        confidence = min(1.0, magnitude * consistency * 2.0)

        return TrendReversal(
            symbol=symbol,
            reversal_type=reversal_type,
            from_score=round(prior_avg, 4),
            to_score=round(recent_avg, 4),
            magnitude=round(magnitude, 4),
            confidence=round(max(0.0, confidence), 4),
        )

    def momentum_summary(
        self,
        symbols: Optional[list[str]] = None,
    ) -> MomentumSummary:
        """Compute cross-symbol momentum summary.

        Args:
            symbols: Specific symbols to include (default: all in history).

        Returns:
            MomentumSummary with market-wide momentum metrics.
        """
        syms = symbols or list(self._history.keys())
        if not syms:
            return MomentumSummary()

        results = []
        for sym in syms:
            if sym in self._history:
                results.append(self.compute_momentum(sym))

        if not results:
            return MomentumSummary()

        n_improving = sum(1 for r in results if r.trend_direction == "improving")
        n_deteriorating = sum(1 for r in results if r.trend_direction == "deteriorating")
        n_flat = sum(1 for r in results if r.trend_direction == "flat")
        n_inflecting = sum(1 for r in results if r.is_inflecting)

        avg_mom = float(np.mean([r.momentum for r in results]))
        positive_fraction = sum(
            1 for r in results if r.momentum > 0.01
        ) / len(results)

        strongest_up = max(results, key=lambda r: r.momentum)
        strongest_down = min(results, key=lambda r: r.momentum)

        return MomentumSummary(
            n_symbols=len(results),
            n_improving=n_improving,
            n_deteriorating=n_deteriorating,
            n_flat=n_flat,
            n_inflecting=n_inflecting,
            avg_momentum=round(avg_mom, 4),
            strongest_up=strongest_up.symbol,
            strongest_down=strongest_down.symbol,
            breadth=round(positive_fraction, 4),
        )

    @staticmethod
    def _ema(arr: np.ndarray, alpha: float) -> np.ndarray:
        """Exponential moving average."""
        result = np.zeros_like(arr)
        result[0] = arr[0]
        for i in range(1, len(arr)):
            result[i] = alpha * arr[i] + (1 - alpha) * result[i - 1]
        return result

    @staticmethod
    def _r_squared(x: np.ndarray, y: np.ndarray, coeffs: np.ndarray) -> float:
        """R-squared for linear fit."""
        y_pred = np.polyval(coeffs, x)
        ss_res = float(np.sum((y - y_pred) ** 2))
        ss_tot = float(np.sum((y - np.mean(y)) ** 2))
        if ss_tot == 0:
            return 1.0
        return max(0.0, 1.0 - ss_res / ss_tot)
