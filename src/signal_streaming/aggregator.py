"""Streaming Sentiment Aggregator.

Buffers incoming sentiment observations and emits aggregated
updates when thresholds are crossed or time windows expire.
Prevents client overload from high-frequency sentiment streams.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class AggregatorConfig:
    """Configuration for streaming aggregator."""

    window_seconds: float = 30.0  # Aggregation window
    min_score_change: float = 0.1  # Min change to emit update
    min_observations: int = 1  # Min obs per window to emit
    max_buffer_size: int = 1000  # Max buffered observations per ticker
    emit_on_urgency: bool = True  # Bypass window for high-urgency


@dataclass
class TickerState:
    """Current aggregated state for a ticker."""

    ticker: str = ""
    current_score: float = 0.0
    previous_score: float = 0.0
    observation_count: int = 0
    window_count: int = 0  # Observations in current window
    avg_confidence: float = 0.0
    dominant_sentiment: str = "neutral"
    last_updated: Optional[datetime] = None
    last_emitted: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "current_score": round(self.current_score, 3),
            "previous_score": round(self.previous_score, 3),
            "observation_count": self.observation_count,
            "avg_confidence": round(self.avg_confidence, 3),
            "dominant_sentiment": self.dominant_sentiment,
        }

    @property
    def score_change(self) -> float:
        return self.current_score - self.previous_score


@dataclass
class AggregatedUpdate:
    """An aggregated sentiment update ready for broadcast."""

    ticker: str = ""
    score: float = 0.0
    score_change: float = 0.0
    sentiment: str = "neutral"
    confidence: float = 0.0
    observation_count: int = 0
    source_types: list[str] = field(default_factory=list)
    urgency: str = "low"
    timestamp: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "score": round(self.score, 3),
            "score_change": round(self.score_change, 3),
            "sentiment": self.sentiment,
            "confidence": round(self.confidence, 3),
            "observation_count": self.observation_count,
            "source_types": self.source_types,
            "urgency": self.urgency,
            "timestamp": self.timestamp.isoformat() if self.timestamp else "",
        }


@dataclass
class _Observation:
    """Internal: a buffered observation."""

    score: float
    confidence: float
    source_type: str
    urgency: str
    timestamp: datetime


class StreamingAggregator:
    """Aggregate incoming sentiment observations into windowed updates.

    Buffers high-frequency sentiment data and emits updates only when
    score changes exceed the configured threshold or the aggregation
    window expires.

    Example::

        agg = StreamingAggregator()
        agg.add_observation("AAPL", 0.7, confidence=0.8, source_type="llm")
        agg.add_observation("AAPL", 0.65, confidence=0.7, source_type="social")
        updates = agg.flush()
        for update in updates:
            print(f"{update.ticker}: {update.score:+.2f}")
    """

    def __init__(self, config: Optional[AggregatorConfig] = None):
        self.config = config or AggregatorConfig()
        self._states: dict[str, TickerState] = {}
        self._buffers: dict[str, list[_Observation]] = {}
        self._pending_urgent: list[AggregatedUpdate] = []

    def add_observation(
        self,
        ticker: str,
        score: float,
        confidence: float = 0.5,
        source_type: str = "unknown",
        urgency: str = "low",
    ) -> Optional[AggregatedUpdate]:
        """Add a sentiment observation.

        Args:
            ticker: Stock ticker symbol.
            score: Sentiment score (-1 to +1).
            confidence: Confidence level (0-1).
            source_type: Source of the observation (llm, social, news).
            urgency: Urgency level (low, medium, high).

        Returns:
            AggregatedUpdate if urgency bypass triggers, else None.
        """
        now = datetime.now(timezone.utc)

        if ticker not in self._states:
            self._states[ticker] = TickerState(ticker=ticker)
            self._buffers[ticker] = []

        obs = _Observation(
            score=score, confidence=confidence,
            source_type=source_type, urgency=urgency,
            timestamp=now,
        )

        buffer = self._buffers[ticker]
        buffer.append(obs)

        # Trim buffer if too large
        if len(buffer) > self.config.max_buffer_size:
            buffer[:] = buffer[-self.config.max_buffer_size:]

        state = self._states[ticker]
        state.observation_count += 1
        state.window_count += 1
        state.last_updated = now

        # High-urgency bypass: emit immediately
        if urgency == "high" and self.config.emit_on_urgency:
            update = self._emit_update(ticker, now)
            if update:
                self._pending_urgent.append(update)
                return update

        return None

    def flush(self) -> list[AggregatedUpdate]:
        """Flush all tickers that have crossed threshold or window expiry.

        Returns:
            List of AggregatedUpdate ready for broadcast.
        """
        now = datetime.now(timezone.utc)
        updates: list[AggregatedUpdate] = []

        # Include any urgent updates
        updates.extend(self._pending_urgent)
        self._pending_urgent.clear()

        for ticker in list(self._states.keys()):
            state = self._states[ticker]
            buffer = self._buffers.get(ticker, [])

            if not buffer or state.window_count < self.config.min_observations:
                continue

            # Check window expiry
            window_expired = False
            if state.last_emitted:
                elapsed = (now - state.last_emitted).total_seconds()
                window_expired = elapsed >= self.config.window_seconds
            else:
                window_expired = True  # Never emitted

            if not window_expired:
                continue

            update = self._emit_update(ticker, now)
            if update:
                updates.append(update)

        return updates

    def get_state(self, ticker: str) -> Optional[TickerState]:
        """Get current aggregated state for a ticker."""
        return self._states.get(ticker)

    @property
    def tracked_tickers(self) -> list[str]:
        return sorted(self._states.keys())

    @property
    def ticker_count(self) -> int:
        return len(self._states)

    def clear(self, ticker: Optional[str] = None):
        """Clear state for a ticker or all tickers."""
        if ticker:
            self._states.pop(ticker, None)
            self._buffers.pop(ticker, None)
        else:
            self._states.clear()
            self._buffers.clear()
            self._pending_urgent.clear()

    def _emit_update(self, ticker: str, now: datetime) -> Optional[AggregatedUpdate]:
        """Compute and emit an aggregated update for a ticker."""
        state = self._states[ticker]
        buffer = self._buffers.get(ticker, [])

        if not buffer:
            return None

        # Compute weighted average score
        total_weight = sum(o.confidence for o in buffer)
        if total_weight == 0:
            avg_score = sum(o.score for o in buffer) / len(buffer)
        else:
            avg_score = sum(o.score * o.confidence for o in buffer) / total_weight

        avg_confidence = sum(o.confidence for o in buffer) / len(buffer)

        # Check if change exceeds threshold
        score_change = avg_score - state.current_score
        if abs(score_change) < self.config.min_score_change and state.last_emitted:
            # Score hasn't changed enough, skip
            state.window_count = 0
            self._buffers[ticker] = []
            return None

        # Update state
        state.previous_score = state.current_score
        state.current_score = avg_score
        state.avg_confidence = avg_confidence
        state.last_emitted = now
        state.window_count = 0

        # Determine dominant sentiment
        if avg_score > 0.2:
            state.dominant_sentiment = "bullish"
        elif avg_score < -0.2:
            state.dominant_sentiment = "bearish"
        else:
            state.dominant_sentiment = "neutral"

        # Source types in this batch
        source_types = list({o.source_type for o in buffer})

        # Max urgency in batch
        urgency_rank = {"low": 0, "medium": 1, "high": 2}
        max_urgency = max(buffer, key=lambda o: urgency_rank.get(o.urgency, 0)).urgency

        # Clear buffer
        self._buffers[ticker] = []

        return AggregatedUpdate(
            ticker=ticker,
            score=avg_score,
            score_change=score_change,
            sentiment=state.dominant_sentiment,
            confidence=avg_confidence,
            observation_count=len(buffer),
            source_types=source_types,
            urgency=max_urgency,
            timestamp=now,
        )
