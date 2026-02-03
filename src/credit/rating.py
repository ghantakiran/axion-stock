"""Credit Rating Migration Tracker.

Tracks rating history, computes transition matrices, detects
migration momentum, and maintains negative-outlook watchlists.
"""

import logging
from collections import defaultdict
from datetime import date
from typing import Optional

import numpy as np

from src.credit.config import (
    CreditRating,
    RatingOutlook,
    RatingConfig,
    RATING_ORDER,
    DEFAULT_CREDIT_CONFIG,
)
from src.credit.models import RatingSnapshot, RatingTransition

logger = logging.getLogger(__name__)


class RatingTracker:
    """Tracks credit ratings and migration patterns."""

    def __init__(self, config: Optional[RatingConfig] = None) -> None:
        self.config = config or DEFAULT_CREDIT_CONFIG.rating
        self._history: dict[str, list[RatingSnapshot]] = defaultdict(list)

    def add_rating(self, snapshot: RatingSnapshot) -> RatingSnapshot:
        """Add a rating observation.

        Auto-populates previous_rating from history.
        """
        history = self._history[snapshot.symbol]
        if history:
            last = history[-1]
            snapshot.previous_rating = last.rating
        history.append(snapshot)
        return snapshot

    def add_ratings(self, snapshots: list[RatingSnapshot]) -> list[RatingSnapshot]:
        """Add multiple rating observations."""
        return [self.add_rating(s) for s in snapshots]

    def get_history(self, symbol: str) -> list[RatingSnapshot]:
        """Get rating history for a symbol, most recent first."""
        return sorted(
            self._history.get(symbol, []),
            key=lambda s: s.as_of,
            reverse=True,
        )

    def current_rating(self, symbol: str) -> Optional[RatingSnapshot]:
        """Get current (latest) rating for a symbol."""
        history = self._history.get(symbol, [])
        if not history:
            return None
        return max(history, key=lambda s: s.as_of)

    def migration_matrix(self) -> dict[CreditRating, dict[CreditRating, float]]:
        """Compute empirical transition probability matrix.

        Counts observed rating transitions across all issuers
        and normalizes to probabilities.

        Returns:
            Nested dict: from_rating -> to_rating -> probability.
        """
        counts: dict[CreditRating, dict[CreditRating, int]] = {}
        for rating in CreditRating:
            counts[rating] = {r: 0 for r in CreditRating}

        for history in self._history.values():
            sorted_h = sorted(history, key=lambda s: s.as_of)
            for i in range(1, len(sorted_h)):
                prev = sorted_h[i - 1].rating
                curr = sorted_h[i].rating
                counts[prev][curr] += 1

        # Normalize
        matrix: dict[CreditRating, dict[CreditRating, float]] = {}
        for from_r in CreditRating:
            row_total = sum(counts[from_r].values())
            matrix[from_r] = {}
            for to_r in CreditRating:
                if row_total > 0:
                    matrix[from_r][to_r] = round(
                        counts[from_r][to_r] / row_total, 4
                    )
                else:
                    # Default: 100% stay in same rating
                    matrix[from_r][to_r] = 1.0 if from_r == to_r else 0.0

        return matrix

    def rating_momentum(self, symbol: str) -> float:
        """Compute rating momentum for a symbol.

        Positive = improving (upgrades), negative = deteriorating.
        Computed as average numeric rating change over recent history.

        Returns:
            Momentum score (negative = improving since lower rating number is better).
        """
        history = sorted(
            self._history.get(symbol, []),
            key=lambda s: s.as_of,
        )
        if len(history) < 2:
            return 0.0

        window = min(len(history), self.config.momentum_window)
        recent = history[-window:]

        changes = []
        for i in range(1, len(recent)):
            prev_num = RATING_ORDER.get(recent[i - 1].rating, 99)
            curr_num = RATING_ORDER.get(recent[i].rating, 99)
            changes.append(curr_num - prev_num)

        return round(float(np.mean(changes)), 4) if changes else 0.0

    def watchlist(self) -> list[RatingSnapshot]:
        """Get symbols on negative outlook or watch.

        Returns:
            List of current ratings with NEGATIVE or WATCH outlook.
        """
        watch = []
        for symbol in self._history:
            current = self.current_rating(symbol)
            if current and current.outlook in (
                RatingOutlook.NEGATIVE, RatingOutlook.WATCH
            ):
                watch.append(current)

        return sorted(watch, key=lambda s: RATING_ORDER.get(s.rating, 99))

    def transitions_for(self, symbol: str) -> list[RatingTransition]:
        """Get observed transitions for a symbol."""
        history = sorted(
            self._history.get(symbol, []),
            key=lambda s: s.as_of,
        )
        transitions = []
        for i in range(1, len(history)):
            prev = history[i - 1].rating
            curr = history[i].rating
            if prev != curr:
                transitions.append(RatingTransition(
                    from_rating=prev,
                    to_rating=curr,
                    probability=0.0,
                    historical_count=1,
                ))
        return transitions

    def reset(self) -> None:
        """Clear all stored ratings."""
        self._history.clear()
