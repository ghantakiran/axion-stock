"""Earnings Event Analyzer.

Models earnings surprises, classifies results, tracks post-earnings
announcement drift (PEAD), and analyzes historical patterns.
"""

import logging
from collections import defaultdict
from typing import Optional

import numpy as np

from src.events.config import (
    EarningsResult,
    EarningsConfig,
    DEFAULT_EVENT_CONFIG,
)
from src.events.models import EarningsEvent, EarningsSummary

logger = logging.getLogger(__name__)


class EarningsAnalyzer:
    """Analyzes earnings events and patterns."""

    def __init__(self, config: Optional[EarningsConfig] = None) -> None:
        self.config = config or DEFAULT_EVENT_CONFIG.earnings
        self._events: dict[str, list[EarningsEvent]] = defaultdict(list)

    def add_event(self, event: EarningsEvent) -> EarningsEvent:
        """Add an earnings event and classify it.

        Auto-classifies as beat/meet/miss based on EPS surprise.
        """
        surprise = event.eps_surprise
        if surprise >= self.config.beat_threshold:
            event.result = EarningsResult.BEAT
        elif surprise <= self.config.miss_threshold:
            event.result = EarningsResult.MISS
        else:
            event.result = EarningsResult.MEET

        self._events[event.symbol].append(event)
        return event

    def add_events(self, events: list[EarningsEvent]) -> list[EarningsEvent]:
        """Add multiple earnings events."""
        return [self.add_event(e) for e in events]

    def summarize(self, symbol: str) -> EarningsSummary:
        """Summarize earnings history for a symbol.

        Returns beat rate, average surprise, streak, and drift stats.
        """
        events = self._events.get(symbol, [])
        if not events:
            return EarningsSummary(symbol=symbol)

        beats = sum(1 for e in events if e.result == EarningsResult.BEAT)
        meets = sum(1 for e in events if e.result == EarningsResult.MEET)
        misses = sum(1 for e in events if e.result == EarningsResult.MISS)

        eps_surprises = [e.eps_surprise for e in events]
        rev_surprises = [e.revenue_surprise for e in events]
        post_drifts = [e.post_drift for e in events if e.post_drift != 0]

        # Compute streak (from most recent)
        streak = self._compute_streak(events)

        return EarningsSummary(
            symbol=symbol,
            total_reports=len(events),
            beats=beats,
            meets=meets,
            misses=misses,
            avg_eps_surprise=float(np.mean(eps_surprises)) if eps_surprises else 0.0,
            avg_revenue_surprise=float(np.mean(rev_surprises)) if rev_surprises else 0.0,
            avg_post_drift=float(np.mean(post_drifts)) if post_drifts else 0.0,
            streak=streak,
        )

    def estimate_drift(
        self, symbol: str, surprise_pct: float
    ) -> float:
        """Estimate post-earnings drift based on historical pattern.

        Uses historical relationship between surprise magnitude and drift.

        Args:
            symbol: Stock symbol.
            surprise_pct: Earnings surprise percentage.

        Returns:
            Estimated post-earnings drift.
        """
        events = self._events.get(symbol, [])
        if len(events) < self.config.min_history:
            # Fallback: simple linear estimate
            return surprise_pct * 0.5

        # Regression: drift = alpha + beta * surprise
        surprises = np.array([e.eps_surprise for e in events])
        drifts = np.array([e.post_drift for e in events])

        if np.std(surprises) < 1e-10:
            return surprise_pct * 0.5

        beta = float(np.cov(surprises, drifts)[0, 1] / np.var(surprises))
        alpha = float(np.mean(drifts) - beta * np.mean(surprises))

        return alpha + beta * surprise_pct

    def get_events(
        self, symbol: str, n: Optional[int] = None
    ) -> list[EarningsEvent]:
        """Get earnings events for a symbol, most recent first."""
        events = sorted(
            self._events.get(symbol, []),
            key=lambda e: e.report_date,
            reverse=True,
        )
        if n is not None:
            return events[:n]
        return events

    def _compute_streak(self, events: list[EarningsEvent]) -> int:
        """Compute consecutive beat/miss streak from most recent."""
        if not events:
            return 0

        sorted_events = sorted(events, key=lambda e: e.report_date, reverse=True)
        first_result = sorted_events[0].result
        if first_result == EarningsResult.MEET:
            return 0

        streak = 0
        for e in sorted_events:
            if e.result == first_result:
                streak += 1
            else:
                break

        return streak if first_result == EarningsResult.BEAT else -streak

    def reset(self) -> None:
        """Clear all stored events."""
        self._events.clear()
