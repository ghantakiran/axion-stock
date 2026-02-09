"""Social Signal Archive.

Stores and replays archived social trading signals for backtesting.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class ArchivedSignal:
    """A social trading signal archived for backtesting."""

    signal_id: str = ""
    ticker: str = ""
    composite_score: float = 0.0
    direction: str = "neutral"  # bullish / bearish / neutral
    action: str = "watch"
    sentiment_avg: float = 0.0
    platform_count: int = 0
    platform_consensus: float = 0.0
    influencer_signal: bool = False
    volume_anomaly: bool = False
    mention_count: int = 0
    confidence: float = 0.0
    signal_time: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def __post_init__(self):
        if not self.signal_id:
            self.signal_id = str(uuid.uuid4())[:8]

    def to_dict(self) -> dict:
        return {
            "signal_id": self.signal_id,
            "ticker": self.ticker,
            "composite_score": round(self.composite_score, 2),
            "direction": self.direction,
            "action": self.action,
            "sentiment_avg": round(self.sentiment_avg, 3),
            "platform_count": self.platform_count,
            "platform_consensus": round(self.platform_consensus, 3),
            "influencer_signal": self.influencer_signal,
            "volume_anomaly": self.volume_anomaly,
            "mention_count": self.mention_count,
            "confidence": round(self.confidence, 2),
            "signal_time": self.signal_time.isoformat(),
        }


@dataclass
class ArchiveStats:
    """Summary statistics for the signal archive."""

    total: int = 0
    by_direction: dict = field(default_factory=dict)
    by_action: dict = field(default_factory=dict)
    avg_score: float = 0.0
    date_range: tuple = ("", "")

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "by_direction": self.by_direction,
            "by_action": self.by_action,
            "avg_score": round(self.avg_score, 2),
            "date_range": list(self.date_range),
        }


class SignalArchive:
    """Archive of social trading signals for backtesting replay.

    Stores signals with timestamps, supports time-range queries,
    and chronological replay for backtesting.
    """

    def __init__(self):
        self._signals: list[ArchivedSignal] = []

    def add(self, signal: ArchivedSignal) -> None:
        """Add a single signal to the archive."""
        self._signals.append(signal)

    def add_batch(self, signals: list[ArchivedSignal]) -> None:
        """Add multiple signals at once."""
        self._signals.extend(signals)

    def get_signals(
        self,
        ticker: Optional[str] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> list[ArchivedSignal]:
        """Query signals by ticker and/or time range."""
        result = self._signals
        if ticker:
            result = [s for s in result if s.ticker == ticker]
        if start:
            result = [s for s in result if s.signal_time >= start]
        if end:
            result = [s for s in result if s.signal_time <= end]
        return result

    def get_stats(self) -> ArchiveStats:
        """Compute summary statistics for the archive."""
        if not self._signals:
            return ArchiveStats()

        by_dir: dict[str, int] = {}
        by_action: dict[str, int] = {}
        total_score = 0.0

        for s in self._signals:
            by_dir[s.direction] = by_dir.get(s.direction, 0) + 1
            by_action[s.action] = by_action.get(s.action, 0) + 1
            total_score += s.composite_score

        times = [s.signal_time for s in self._signals]
        return ArchiveStats(
            total=len(self._signals),
            by_direction=by_dir,
            by_action=by_action,
            avg_score=total_score / len(self._signals),
            date_range=(min(times).isoformat(), max(times).isoformat()),
        )

    def replay(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ):
        """Yield signals in chronological order for replay."""
        filtered = self.get_signals(start=start, end=end)
        filtered.sort(key=lambda s: s.signal_time)
        yield from filtered

    def get_unique_tickers(self) -> list[str]:
        """Get all unique tickers in the archive."""
        return sorted(set(s.ticker for s in self._signals))

    def clear(self) -> None:
        """Clear all archived signals."""
        self._signals.clear()

    @property
    def size(self) -> int:
        return len(self._signals)
