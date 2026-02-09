"""Sentiment Prediction & Momentum Forecasting.

Uses historical sentiment observations to forecast future sentiment
direction, detect reversals, and estimate sentiment half-life.
Pure computation — no LLM required.
"""

import enum
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional


class ForecastHorizon(enum.Enum):
    """Prediction time horizons."""

    HOURS_4 = "4h"
    HOURS_24 = "24h"
    DAYS_3 = "3d"
    DAYS_7 = "7d"


@dataclass
class PredictorConfig:
    """Configuration for sentiment predictor."""

    min_observations: int = 5
    ema_fast_span: int = 5
    ema_slow_span: int = 20
    reversal_threshold: float = 0.3  # Score swing to flag reversal
    decay_halflife_hours: float = 24.0
    momentum_window: int = 10


@dataclass
class SentimentForecast:
    """A single sentiment forecast for a ticker."""

    ticker: str = ""
    horizon: str = "24h"
    current_score: float = 0.0
    predicted_score: float = 0.0
    predicted_direction: str = "stable"  # improving, deteriorating, stable
    confidence: float = 0.0
    momentum: float = 0.0  # Rate of change
    reversal_probability: float = 0.0
    half_life_hours: float = 0.0

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "horizon": self.horizon,
            "current_score": self.current_score,
            "predicted_score": self.predicted_score,
            "predicted_direction": self.predicted_direction,
            "confidence": self.confidence,
            "momentum": self.momentum,
            "reversal_probability": self.reversal_probability,
            "half_life_hours": self.half_life_hours,
        }


@dataclass
class PredictionReport:
    """Full prediction report across multiple tickers."""

    forecasts: list[SentimentForecast] = field(default_factory=list)
    generated_at: str = ""
    horizon: str = "24h"

    def to_dict(self) -> dict:
        return {
            "forecasts": [f.to_dict() for f in self.forecasts],
            "generated_at": self.generated_at,
            "horizon": self.horizon,
        }

    def get_improving(self) -> list[SentimentForecast]:
        """Tickers with predicted improving sentiment."""
        return [f for f in self.forecasts if f.predicted_direction == "improving"]

    def get_deteriorating(self) -> list[SentimentForecast]:
        """Tickers with predicted deteriorating sentiment."""
        return [f for f in self.forecasts if f.predicted_direction == "deteriorating"]

    def get_reversals(self, min_prob: float = 0.5) -> list[SentimentForecast]:
        """Tickers with high reversal probability."""
        return [f for f in self.forecasts if f.reversal_probability >= min_prob]

    @property
    def ticker_count(self) -> int:
        return len(self.forecasts)


@dataclass
class _Observation:
    """Internal: a single timestamped sentiment reading."""

    score: float
    timestamp: datetime
    volume: float = 1.0  # Mention/article count


class SentimentPredictor:
    """Predict sentiment direction from historical observations.

    Uses exponential moving averages and momentum analysis to
    forecast sentiment trends without requiring LLM calls.

    Example::

        predictor = SentimentPredictor()
        predictor.add_observation("AAPL", 0.6, timestamp1)
        predictor.add_observation("AAPL", 0.4, timestamp2)
        predictor.add_observation("AAPL", 0.2, timestamp3)

        forecast = predictor.predict("AAPL", ForecastHorizon.HOURS_24)
        # forecast.predicted_direction = "deteriorating"
        # forecast.momentum = -0.2
    """

    def __init__(self, config: Optional[PredictorConfig] = None):
        self.config = config or PredictorConfig()
        self._observations: dict[str, list[_Observation]] = {}

    def add_observation(
        self,
        ticker: str,
        score: float,
        timestamp: Optional[datetime] = None,
        volume: float = 1.0,
    ):
        """Add a sentiment observation for a ticker.

        Args:
            ticker: Stock ticker symbol.
            score: Sentiment score (-1 to +1).
            timestamp: When the sentiment was observed.
            volume: Mention/article count weight.
        """
        if ticker not in self._observations:
            self._observations[ticker] = []

        ts = timestamp or datetime.now(timezone.utc)
        self._observations[ticker].append(
            _Observation(score=score, timestamp=ts, volume=volume)
        )

        # Keep sorted by timestamp
        self._observations[ticker].sort(key=lambda o: o.timestamp)

    def predict(
        self,
        ticker: str,
        horizon: ForecastHorizon = ForecastHorizon.HOURS_24,
    ) -> SentimentForecast:
        """Generate a sentiment forecast for a ticker.

        Args:
            ticker: Stock ticker symbol.
            horizon: How far ahead to forecast.

        Returns:
            SentimentForecast with predicted direction and momentum.
        """
        obs = self._observations.get(ticker, [])

        if len(obs) < self.config.min_observations:
            current = obs[-1].score if obs else 0.0
            return SentimentForecast(
                ticker=ticker,
                horizon=horizon.value,
                current_score=current,
                predicted_score=current,
                predicted_direction="stable",
                confidence=0.1,
            )

        scores = [o.score for o in obs]
        current = scores[-1]

        # EMA calculation
        ema_fast = self._ema(scores, self.config.ema_fast_span)
        ema_slow = self._ema(scores, self.config.ema_slow_span)

        # Momentum: rate of change over recent window
        window = min(self.config.momentum_window, len(scores))
        recent = scores[-window:]
        momentum = (recent[-1] - recent[0]) / max(window - 1, 1)

        # Predict: extrapolate EMA trend
        horizon_multiplier = self._horizon_to_steps(horizon)
        predicted = current + momentum * horizon_multiplier

        # Decay toward zero (mean reversion)
        decay = math.exp(-0.693 * horizon_multiplier / max(self.config.decay_halflife_hours, 1))
        predicted = predicted * decay
        predicted = max(-1.0, min(1.0, predicted))

        # Direction
        delta = predicted - current
        if delta > 0.05:
            direction = "improving"
        elif delta < -0.05:
            direction = "deteriorating"
        else:
            direction = "stable"

        # Reversal detection: if EMA crossover or large swing
        reversal_prob = self._reversal_probability(scores, ema_fast, ema_slow)

        # Half-life: time for sentiment to decay to half current level
        half_life = self._estimate_half_life(scores)

        # Confidence: based on data volume and consistency
        confidence = self._compute_confidence(obs)

        return SentimentForecast(
            ticker=ticker,
            horizon=horizon.value,
            current_score=round(current, 3),
            predicted_score=round(predicted, 3),
            predicted_direction=direction,
            confidence=round(confidence, 3),
            momentum=round(momentum, 4),
            reversal_probability=round(reversal_prob, 3),
            half_life_hours=round(half_life, 1),
        )

    def predict_all(
        self, horizon: ForecastHorizon = ForecastHorizon.HOURS_24
    ) -> PredictionReport:
        """Generate forecasts for all tracked tickers."""
        forecasts = [
            self.predict(ticker, horizon)
            for ticker in sorted(self._observations.keys())
        ]

        return PredictionReport(
            forecasts=forecasts,
            generated_at=datetime.now(timezone.utc).isoformat(),
            horizon=horizon.value,
        )

    @property
    def tracked_tickers(self) -> list[str]:
        """List of tickers with observations."""
        return sorted(self._observations.keys())

    def get_observation_count(self, ticker: str) -> int:
        """Number of observations for a ticker."""
        return len(self._observations.get(ticker, []))

    def clear(self, ticker: Optional[str] = None):
        """Clear observations for a ticker (or all)."""
        if ticker:
            self._observations.pop(ticker, None)
        else:
            self._observations.clear()

    # ── Private ───────────────────────────────────────────────────────

    @staticmethod
    def _ema(values: list[float], span: int) -> float:
        """Compute exponential moving average of the last value."""
        if not values:
            return 0.0
        alpha = 2 / (span + 1)
        ema = values[0]
        for v in values[1:]:
            ema = alpha * v + (1 - alpha) * ema
        return ema

    def _reversal_probability(
        self, scores: list[float], ema_fast: float, ema_slow: float
    ) -> float:
        """Estimate probability of a sentiment reversal."""
        if len(scores) < 3:
            return 0.0

        # Factor 1: EMA crossover divergence
        crossover = abs(ema_fast - ema_slow)

        # Factor 2: Recent momentum change (deceleration)
        recent_3 = scores[-3:]
        accel = (recent_3[2] - recent_3[1]) - (recent_3[1] - recent_3[0])

        # Factor 3: Extreme values tend to revert
        extremity = abs(scores[-1])

        prob = 0.0
        # Crossover signals reversal
        if crossover > self.config.reversal_threshold:
            prob += 0.3
        # Deceleration signals momentum loss
        if (scores[-1] > 0 and accel < -0.1) or (scores[-1] < 0 and accel > 0.1):
            prob += 0.3
        # Extreme scores more likely to revert
        if extremity > 0.7:
            prob += 0.2

        return min(prob, 1.0)

    @staticmethod
    def _estimate_half_life(scores: list[float]) -> float:
        """Estimate sentiment half-life in hours (simplified)."""
        if len(scores) < 3:
            return 24.0

        # Find how quickly scores decay toward zero
        peak = max(abs(s) for s in scores)
        if peak < 0.1:
            return 24.0

        half_peak = peak / 2
        peak_idx = max(range(len(scores)), key=lambda i: abs(scores[i]))

        # Look for when score drops below half peak after the peak
        for i in range(peak_idx + 1, len(scores)):
            if abs(scores[i]) <= half_peak:
                steps = i - peak_idx
                return max(steps * 4.0, 1.0)  # Assume ~4h between observations

        return 48.0  # Hasn't decayed yet

    @staticmethod
    def _compute_confidence(observations: list[_Observation]) -> float:
        """Confidence based on data volume and recency."""
        if not observations:
            return 0.0

        n = len(observations)
        # Volume factor: more observations = higher confidence
        vol_factor = min(n / 20.0, 1.0)

        # Recency factor: recent observations = higher confidence
        latest = observations[-1].timestamp
        if latest.tzinfo is None:
            latest = latest.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        hours_since = (now - latest).total_seconds() / 3600
        recency_factor = math.exp(-hours_since / 48.0)  # 48h half-life

        # Consistency factor: low variance = higher confidence
        scores = [o.score for o in observations[-10:]]
        if len(scores) > 1:
            mean = sum(scores) / len(scores)
            variance = sum((s - mean) ** 2 for s in scores) / len(scores)
            consistency = max(0, 1 - variance * 4)
        else:
            consistency = 0.5

        return min(vol_factor * 0.4 + recency_factor * 0.3 + consistency * 0.3, 1.0)

    @staticmethod
    def _horizon_to_steps(horizon: ForecastHorizon) -> float:
        """Convert horizon to number of observation steps."""
        mapping = {
            ForecastHorizon.HOURS_4: 1.0,
            ForecastHorizon.HOURS_24: 6.0,
            ForecastHorizon.DAYS_3: 18.0,
            ForecastHorizon.DAYS_7: 42.0,
        }
        return mapping.get(horizon, 6.0)
