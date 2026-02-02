"""Consensus Analysis.

Tracks analyst consensus, computes divergence scores,
identifies revision momentum, and detects contrarian opportunities.
"""

import logging
from typing import Optional

import numpy as np

from src.crowding.config import ConsensusConfig, DEFAULT_CONSENSUS_CONFIG
from src.crowding.models import ConsensusSnapshot

logger = logging.getLogger(__name__)


class ConsensusAnalyzer:
    """Analyzes analyst consensus and contrarian signals."""

    def __init__(self, config: Optional[ConsensusConfig] = None) -> None:
        self.config = config or DEFAULT_CONSENSUS_CONFIG
        self._history: dict[str, list[ConsensusSnapshot]] = {}

    def analyze(
        self,
        symbol: str,
        ratings: list[float],
        targets: Optional[list[float]] = None,
        current_price: float = 0.0,
    ) -> ConsensusSnapshot:
        """Analyze analyst consensus.

        Args:
            symbol: Stock symbol.
            ratings: List of analyst ratings (1=strong sell to 5=strong buy).
            targets: Optional list of price targets.
            current_price: Current stock price for upside calculation.

        Returns:
            ConsensusSnapshot with consensus metrics.
        """
        if len(ratings) < self.config.min_analysts:
            return self._empty_snapshot(symbol)

        arr = np.array(ratings, dtype=float)
        mean_rating = float(np.mean(arr))
        divergence = float(np.std(arr))

        # Buy/hold/sell counts
        buy_count = int(np.sum(arr >= 3.5))
        hold_count = int(np.sum((arr >= 2.5) & (arr < 3.5)))
        sell_count = int(np.sum(arr < 2.5))

        # Target analysis
        mean_target = 0.0
        target_upside = 0.0
        if targets and len(targets) > 0:
            mean_target = float(np.mean(targets))
            if current_price > 0:
                target_upside = (mean_target - current_price) / current_price * 100

        # Revision momentum from history
        revision_momentum = self._compute_revision_momentum(symbol, mean_rating)

        # Contrarian detection: extreme consensus may be contrarian signal
        total = len(ratings)
        max_pct = max(buy_count, sell_count) / total if total > 0 else 0
        is_contrarian = max_pct >= self.config.contrarian_threshold

        snapshot = ConsensusSnapshot(
            symbol=symbol,
            mean_rating=round(mean_rating, 2),
            n_analysts=len(ratings),
            buy_count=buy_count,
            hold_count=hold_count,
            sell_count=sell_count,
            mean_target=round(mean_target, 2),
            target_upside=round(target_upside, 2),
            revision_momentum=round(revision_momentum, 4),
            divergence=round(divergence, 4),
            is_contrarian=is_contrarian,
        )

        if symbol not in self._history:
            self._history[symbol] = []
        self._history[symbol].append(snapshot)

        return snapshot

    def _compute_revision_momentum(
        self, symbol: str, current_rating: float
    ) -> float:
        """Compute rating revision momentum.

        Positive = upgrades trending, negative = downgrades trending.
        """
        history = self._history.get(symbol, [])
        if not history:
            return 0.0

        prev_rating = history[-1].mean_rating
        if prev_rating == 0:
            return 0.0
        return (current_rating - prev_rating) / abs(prev_rating)

    def get_history(self, symbol: str) -> list[ConsensusSnapshot]:
        return self._history.get(symbol, [])

    def reset(self) -> None:
        self._history.clear()

    def _empty_snapshot(self, symbol: str) -> ConsensusSnapshot:
        return ConsensusSnapshot(
            symbol=symbol, mean_rating=0.0, n_analysts=0,
        )
