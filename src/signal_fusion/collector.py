"""Signal Collector — gathers raw signals from all platform sources.

Collects signals from EMA Cloud, Social Intelligence, Factor Engine,
ML models, Sentiment, Technical, Fundamental, and News sources.
Includes demo mode for generating realistic signals for common tickers.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class SignalSource(Enum):
    """Enumeration of all signal sources in the platform."""

    EMA_CLOUD = "ema_cloud"
    SOCIAL = "social"
    FACTOR = "factor"
    ML_RANKING = "ml_ranking"
    SENTIMENT = "sentiment"
    TECHNICAL = "technical"
    FUNDAMENTAL = "fundamental"
    NEWS = "news"

    def __str__(self) -> str:
        return self.value


VALID_DIRECTIONS = ("bullish", "bearish", "neutral")

# Default demo tickers used when generating sample signals
DEMO_TICKERS = ["AAPL", "NVDA", "TSLA", "MSFT", "AMZN", "GOOGL", "META", "AMD"]


@dataclass
class RawSignal:
    """A single raw signal from one source.

    Attributes:
        source: Which system generated this signal.
        symbol: Ticker symbol (e.g. 'AAPL').
        direction: 'bullish', 'bearish', or 'neutral'.
        strength: Signal strength from 0 to 100.
        timestamp: When the signal was generated.
        metadata: Arbitrary extra data from the source.
        confidence: Source self-reported confidence 0.0 to 1.0.
        signal_id: Unique identifier for this signal.
    """

    source: SignalSource
    symbol: str
    direction: str
    strength: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.5
    signal_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])

    def __post_init__(self) -> None:
        if self.direction not in VALID_DIRECTIONS:
            raise ValueError(
                f"direction must be one of {VALID_DIRECTIONS}, got '{self.direction}'"
            )
        self.strength = max(0.0, min(100.0, float(self.strength)))
        self.confidence = max(0.0, min(1.0, float(self.confidence)))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "signal_id": self.signal_id,
            "source": str(self.source),
            "symbol": self.symbol,
            "direction": self.direction,
            "strength": self.strength,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


# ── Demo signal generation helpers ────────────────────────────────────


def _random_direction() -> str:
    """Generate a random direction with a slight bullish bias (market tendency)."""
    return random.choices(
        ["bullish", "bearish", "neutral"], weights=[0.45, 0.35, 0.20], k=1
    )[0]


def _demo_signal(source: SignalSource, symbol: str) -> RawSignal:
    """Create one realistic demo signal for a source and symbol."""
    direction = _random_direction()
    # Strength depends on source reliability
    base_strength = {
        SignalSource.EMA_CLOUD: 70,
        SignalSource.SOCIAL: 50,
        SignalSource.FACTOR: 65,
        SignalSource.ML_RANKING: 60,
        SignalSource.SENTIMENT: 55,
        SignalSource.TECHNICAL: 68,
        SignalSource.FUNDAMENTAL: 62,
        SignalSource.NEWS: 45,
    }
    strength = base_strength.get(source, 55) + random.uniform(-20, 20)
    confidence = min(1.0, max(0.1, 0.5 + random.uniform(-0.3, 0.4)))
    return RawSignal(
        source=source,
        symbol=symbol,
        direction=direction,
        strength=strength,
        confidence=confidence,
        metadata={"demo": True, "source_version": "1.0"},
    )


def _generate_demo_signals(
    symbol: str,
    sources: list[SignalSource] | None = None,
) -> list[RawSignal]:
    """Generate a full set of demo signals for a symbol."""
    if sources is None:
        sources = list(SignalSource)
    return [_demo_signal(source, symbol) for source in sources]


# ── SignalCollector ───────────────────────────────────────────────────


class SignalCollector:
    """Gathers signals from all registered platform sources.

    In demo mode (the default), generates realistic synthetic signals.
    In production mode, each source adapter would query actual engines.

    Args:
        demo_mode: If True, generate synthetic signals. Default True.
        active_sources: Subset of sources to collect from. None means all.
    """

    def __init__(
        self,
        demo_mode: bool = True,
        active_sources: list[SignalSource] | None = None,
    ) -> None:
        self.demo_mode = demo_mode
        self._active_sources = active_sources or list(SignalSource)

    def get_active_sources(self) -> list[SignalSource]:
        """Return the list of currently active signal sources."""
        return list(self._active_sources)

    def collect_all(self, symbol: str) -> list[RawSignal]:
        """Collect signals from all active sources for a symbol.

        Args:
            symbol: Ticker symbol to collect signals for.

        Returns:
            List of RawSignal objects from every active source.
        """
        signals: list[RawSignal] = []
        for source in self._active_sources:
            signals.extend(self.collect_from(source, symbol))
        return signals

    def collect_from(self, source: SignalSource, symbol: str) -> list[RawSignal]:
        """Collect signals from a specific source for a symbol.

        Args:
            source: The signal source to query.
            symbol: Ticker symbol.

        Returns:
            List of RawSignal objects from the given source.
        """
        if source not in self._active_sources:
            return []

        if self.demo_mode:
            return [_demo_signal(source, symbol)]

        # Production adapters would go here
        return self._collect_live(source, symbol)

    def collect_multi(self, symbols: list[str]) -> dict[str, list[RawSignal]]:
        """Collect signals for multiple symbols.

        Args:
            symbols: List of ticker symbols.

        Returns:
            Dict mapping symbol -> list of RawSignal.
        """
        return {symbol: self.collect_all(symbol) for symbol in symbols}

    def _collect_live(self, source: SignalSource, symbol: str) -> list[RawSignal]:
        """Placeholder for live source adapters.

        In a production deployment, this would route to the actual engine
        (e.g. EMA Cloud calculator, Factor Engine, ML inference, etc.).
        """
        # Each source would have a dedicated adapter
        return []
