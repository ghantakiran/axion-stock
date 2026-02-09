"""Signal Query — builder pattern for filtering persisted signals.

Provides a fluent API for querying signal records with filters
on ticker, source, status, time range, direction, and strength.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional

from src.signal_persistence.models import SignalRecord, SignalStatus
from src.signal_persistence.store import SignalStore


@dataclass
class SignalQuery:
    """Result of a signal query with records and metadata."""

    records: list[SignalRecord] = field(default_factory=list)
    total_count: int = 0
    filtered_count: int = 0
    query_params: dict = field(default_factory=dict)

    @property
    def tickers(self) -> list[str]:
        """Unique tickers in result set."""
        return list({r.ticker for r in self.records})

    @property
    def sources(self) -> list[str]:
        """Unique sources in result set."""
        return list({r.source for r in self.records})

    def to_dicts(self) -> list[dict]:
        """Serialize all records."""
        return [r.to_dict() for r in self.records]


class SignalQueryBuilder:
    """Fluent builder for querying the signal store.

    Example:
        results = (
            SignalQueryBuilder(store)
            .ticker("AAPL")
            .source("ema_cloud")
            .status(SignalStatus.EXECUTED)
            .since_minutes(60)
            .min_strength(70)
            .limit(50)
            .execute()
        )
    """

    def __init__(self, store: SignalStore) -> None:
        self._store = store
        self._ticker: Optional[str] = None
        self._source: Optional[str] = None
        self._status: Optional[SignalStatus] = None
        self._direction: Optional[str] = None
        self._min_strength: float = 0.0
        self._max_strength: float = 100.0
        self._min_confidence: float = 0.0
        self._since: Optional[datetime] = None
        self._until: Optional[datetime] = None
        self._limit: int = 100

    def ticker(self, ticker: str) -> SignalQueryBuilder:
        """Filter by ticker symbol."""
        self._ticker = ticker
        return self

    def source(self, source: str) -> SignalQueryBuilder:
        """Filter by signal source."""
        self._source = source
        return self

    def status(self, status: SignalStatus) -> SignalQueryBuilder:
        """Filter by signal status."""
        self._status = status
        return self

    def direction(self, direction: str) -> SignalQueryBuilder:
        """Filter by direction (bullish/bearish/neutral)."""
        self._direction = direction
        return self

    def min_strength(self, value: float) -> SignalQueryBuilder:
        """Filter signals with strength >= value."""
        self._min_strength = value
        return self

    def max_strength(self, value: float) -> SignalQueryBuilder:
        """Filter signals with strength <= value."""
        self._max_strength = value
        return self

    def min_confidence(self, value: float) -> SignalQueryBuilder:
        """Filter signals with confidence >= value."""
        self._min_confidence = value
        return self

    def since(self, dt: datetime) -> SignalQueryBuilder:
        """Filter signals generated after this datetime."""
        self._since = dt
        return self

    def since_minutes(self, minutes: int) -> SignalQueryBuilder:
        """Filter signals generated within the last N minutes."""
        self._since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        return self

    def until(self, dt: datetime) -> SignalQueryBuilder:
        """Filter signals generated before this datetime."""
        self._until = dt
        return self

    def limit(self, n: int) -> SignalQueryBuilder:
        """Limit the number of results."""
        self._limit = n
        return self

    def execute(self) -> SignalQuery:
        """Execute the query and return results."""
        # Start with the broadest matching set
        if self._ticker:
            candidates = self._store.get_signals_by_ticker(
                self._ticker, limit=self._limit * 5
            )
        elif self._source:
            candidates = self._store.get_signals_by_source(
                self._source, limit=self._limit * 5
            )
        elif self._status:
            candidates = self._store.get_signals_by_status(self._status)
        else:
            # All signals (via store internals)
            candidates = list(self._store._signals.values())

        total_count = len(candidates)

        # Apply filters
        filtered = []
        for r in candidates:
            if self._ticker and r.ticker != self._ticker:
                continue
            if self._source and r.source != self._source:
                continue
            if self._status and r.status != self._status:
                continue
            if self._direction and r.direction != self._direction:
                continue
            if r.strength < self._min_strength or r.strength > self._max_strength:
                continue
            if r.confidence < self._min_confidence:
                continue
            if self._since and r.timestamp < self._since:
                continue
            if self._until and r.timestamp > self._until:
                continue
            filtered.append(r)

        # Sort by timestamp descending
        filtered.sort(key=lambda r: r.timestamp, reverse=True)
        result_records = filtered[: self._limit]

        return SignalQuery(
            records=result_records,
            total_count=total_count,
            filtered_count=len(filtered),
            query_params={
                "ticker": self._ticker,
                "source": self._source,
                "status": self._status.value if self._status else None,
                "direction": self._direction,
                "min_strength": self._min_strength,
                "limit": self._limit,
            },
        )
