"""Event Calendar Analytics.

Event density scoring, clustering detection, cross-event
interaction analysis, and catalyst timeline generation.
"""

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

import numpy as np

from src.events.config import EventConfig, DEFAULT_EVENT_CONFIG

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass
class CalendarEvent:
    """Generic calendar event entry."""
    symbol: str = ""
    event_type: str = ""  # earnings, merger, dividend, split, etc.
    event_date: date = field(default_factory=date.today)
    description: str = ""
    expected_impact: str = "neutral"  # positive, negative, neutral
    importance: float = 0.5  # 0-1


@dataclass
class EventDensity:
    """Event density score for a time window."""
    start_date: date = field(default_factory=date.today)
    end_date: date = field(default_factory=date.today)
    n_events: int = 0
    density_score: float = 0.0  # events per trading day
    high_importance_count: int = 0
    symbols_affected: int = 0

    @property
    def is_busy(self) -> bool:
        return self.density_score >= 0.5

    @property
    def window_days(self) -> int:
        return max(1, (self.end_date - self.start_date).days)


@dataclass
class EventCluster:
    """Cluster of related events within a time window."""
    cluster_date: date = field(default_factory=date.today)
    events: list[CalendarEvent] = field(default_factory=list)
    n_events: int = 0
    symbols: list[str] = field(default_factory=list)
    dominant_type: str = ""
    combined_importance: float = 0.0

    @property
    def is_significant(self) -> bool:
        return self.n_events >= 3 or self.combined_importance >= 1.5


@dataclass
class CatalystTimeline:
    """Timeline of upcoming catalysts for a symbol."""
    symbol: str = ""
    catalysts: list[CalendarEvent] = field(default_factory=list)
    next_catalyst_days: int = 0
    n_catalysts_30d: int = 0
    n_catalysts_90d: int = 0
    catalyst_density: float = 0.0

    @property
    def has_near_term_catalyst(self) -> bool:
        return self.next_catalyst_days <= 14

    @property
    def is_catalyst_rich(self) -> bool:
        return self.n_catalysts_30d >= 2


@dataclass
class CrossEventInteraction:
    """Interaction between multiple events on same symbol."""
    symbol: str = ""
    event_a: str = ""
    event_b: str = ""
    days_apart: int = 0
    interaction_type: str = ""  # reinforcing, conflicting, neutral
    combined_score: float = 0.0

    @property
    def is_reinforcing(self) -> bool:
        return self.interaction_type == "reinforcing"


# ---------------------------------------------------------------------------
# Event Calendar Analyzer
# ---------------------------------------------------------------------------
class EventCalendarAnalyzer:
    """Analyzes event calendars for density, clustering, and interactions."""

    def __init__(self, config: Optional[EventConfig] = None) -> None:
        self.config = config or DEFAULT_EVENT_CONFIG

    def compute_density(
        self,
        events: list[CalendarEvent],
        start_date: date,
        end_date: date,
    ) -> EventDensity:
        """Compute event density for a time window.

        Args:
            events: List of calendar events.
            start_date: Window start.
            end_date: Window end.

        Returns:
            EventDensity score.
        """
        window_days = max(1, (end_date - start_date).days)
        in_window = [
            e for e in events
            if start_date <= e.event_date <= end_date
        ]

        n = len(in_window)
        # Approximate trading days (5/7 of calendar days)
        trading_days = max(1, int(window_days * 5 / 7))
        density = n / trading_days

        high_imp = sum(1 for e in in_window if e.importance >= 0.7)
        symbols = len(set(e.symbol for e in in_window))

        return EventDensity(
            start_date=start_date,
            end_date=end_date,
            n_events=n,
            density_score=round(density, 4),
            high_importance_count=high_imp,
            symbols_affected=symbols,
        )

    def detect_clusters(
        self,
        events: list[CalendarEvent],
        cluster_window_days: int = 3,
    ) -> list[EventCluster]:
        """Detect clusters of events within a time window.

        Args:
            events: List of calendar events.
            cluster_window_days: Days to group events together.

        Returns:
            List of EventCluster objects.
        """
        if not events:
            return []

        sorted_events = sorted(events, key=lambda e: e.event_date)
        clusters: list[EventCluster] = []
        current_group: list[CalendarEvent] = [sorted_events[0]]

        for i in range(1, len(sorted_events)):
            if (sorted_events[i].event_date - current_group[-1].event_date).days <= cluster_window_days:
                current_group.append(sorted_events[i])
            else:
                if len(current_group) >= 2:
                    clusters.append(self._build_cluster(current_group))
                current_group = [sorted_events[i]]

        if len(current_group) >= 2:
            clusters.append(self._build_cluster(current_group))

        clusters.sort(key=lambda c: c.combined_importance, reverse=True)
        return clusters

    def catalyst_timeline(
        self,
        events: list[CalendarEvent],
        symbol: str,
        reference_date: Optional[date] = None,
    ) -> CatalystTimeline:
        """Build catalyst timeline for a specific symbol.

        Args:
            events: List of calendar events.
            symbol: Target symbol.
            reference_date: Reference date (default: today).

        Returns:
            CatalystTimeline with upcoming catalysts.
        """
        ref = reference_date or date.today()
        symbol_events = [
            e for e in events
            if e.symbol == symbol and e.event_date >= ref
        ]
        symbol_events.sort(key=lambda e: e.event_date)

        next_days = (
            (symbol_events[0].event_date - ref).days
            if symbol_events else 999
        )

        in_30d = sum(
            1 for e in symbol_events
            if (e.event_date - ref).days <= 30
        )
        in_90d = sum(
            1 for e in symbol_events
            if (e.event_date - ref).days <= 90
        )

        density = in_90d / 90.0 if in_90d > 0 else 0.0

        return CatalystTimeline(
            symbol=symbol,
            catalysts=symbol_events,
            next_catalyst_days=next_days,
            n_catalysts_30d=in_30d,
            n_catalysts_90d=in_90d,
            catalyst_density=round(density, 4),
        )

    def detect_interactions(
        self,
        events: list[CalendarEvent],
        symbol: str,
        interaction_window_days: int = 10,
    ) -> list[CrossEventInteraction]:
        """Detect interactions between events for a symbol.

        Args:
            events: List of calendar events.
            symbol: Target symbol.
            interaction_window_days: Max days apart for interaction.

        Returns:
            List of CrossEventInteraction objects.
        """
        sym_events = sorted(
            [e for e in events if e.symbol == symbol],
            key=lambda e: e.event_date,
        )

        interactions = []
        for i in range(len(sym_events)):
            for j in range(i + 1, len(sym_events)):
                days = (sym_events[j].event_date - sym_events[i].event_date).days
                if days > interaction_window_days:
                    break

                interaction = self._classify_interaction(
                    sym_events[i], sym_events[j], days
                )
                interactions.append(interaction)

        return interactions

    def weekly_summary(
        self,
        events: list[CalendarEvent],
        start_date: date,
        n_weeks: int = 4,
    ) -> list[EventDensity]:
        """Generate weekly event density summaries.

        Args:
            events: List of calendar events.
            start_date: Starting Monday.
            n_weeks: Number of weeks to analyze.

        Returns:
            List of weekly EventDensity objects.
        """
        weeks = []
        for w in range(n_weeks):
            week_start = start_date + timedelta(weeks=w)
            week_end = week_start + timedelta(days=6)
            density = self.compute_density(events, week_start, week_end)
            weeks.append(density)
        return weeks

    def _build_cluster(self, group: list[CalendarEvent]) -> EventCluster:
        """Build an EventCluster from a group of events."""
        symbols = sorted(set(e.symbol for e in group))
        types = [e.event_type for e in group]
        # Dominant type = most frequent
        type_counts: dict[str, int] = {}
        for t in types:
            type_counts[t] = type_counts.get(t, 0) + 1
        dominant = max(type_counts, key=type_counts.get) if type_counts else ""

        combined_imp = sum(e.importance for e in group)

        return EventCluster(
            cluster_date=group[0].event_date,
            events=group,
            n_events=len(group),
            symbols=symbols,
            dominant_type=dominant,
            combined_importance=round(combined_imp, 4),
        )

    def _classify_interaction(
        self,
        event_a: CalendarEvent,
        event_b: CalendarEvent,
        days_apart: int,
    ) -> CrossEventInteraction:
        """Classify the interaction between two events."""
        # Determine interaction type based on event types and impacts
        impact_a = event_a.expected_impact
        impact_b = event_b.expected_impact

        if impact_a == impact_b and impact_a != "neutral":
            interaction_type = "reinforcing"
            combined = (event_a.importance + event_b.importance) * 1.2
        elif (
            (impact_a == "positive" and impact_b == "negative")
            or (impact_a == "negative" and impact_b == "positive")
        ):
            interaction_type = "conflicting"
            combined = abs(event_a.importance - event_b.importance)
        else:
            interaction_type = "neutral"
            combined = event_a.importance + event_b.importance

        return CrossEventInteraction(
            symbol=event_a.symbol,
            event_a=event_a.event_type,
            event_b=event_b.event_type,
            days_apart=days_apart,
            interaction_type=interaction_type,
            combined_score=round(combined, 4),
        )
