"""Web Traffic Analyzer.

Tracks website traffic metrics (visits, unique visitors, bounce rate,
session duration) and computes growth rates, engagement scores,
and traffic momentum.
"""

import logging
from datetime import datetime
from typing import Optional

import numpy as np

from src.altdata.config import WebTrafficConfig, DEFAULT_WEB_TRAFFIC_CONFIG
from src.altdata.models import WebTrafficSnapshot

logger = logging.getLogger(__name__)


class WebTrafficAnalyzer:
    """Analyzes web traffic patterns."""

    def __init__(self, config: Optional[WebTrafficConfig] = None) -> None:
        self.config = config or DEFAULT_WEB_TRAFFIC_CONFIG
        self._history: dict[str, list[WebTrafficSnapshot]] = {}

    def add_snapshot(
        self,
        symbol: str,
        domain: str,
        visits: int,
        unique_visitors: int = 0,
        bounce_rate: float = 0.0,
        avg_duration: float = 0.0,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Record a web traffic snapshot."""
        snapshot = WebTrafficSnapshot(
            symbol=symbol,
            domain=domain,
            visits=visits,
            unique_visitors=unique_visitors or visits,
            bounce_rate=bounce_rate,
            avg_duration=avg_duration,
            timestamp=timestamp or datetime.now(),
        )
        if symbol not in self._history:
            self._history[symbol] = []
        self._history[symbol].append(snapshot)

    def analyze(self, symbol: str) -> WebTrafficSnapshot:
        """Analyze web traffic for a symbol.

        Returns:
            WebTrafficSnapshot with computed growth, engagement, momentum.
        """
        history = self._history.get(symbol, [])
        if not history:
            return WebTrafficSnapshot(symbol=symbol, domain="")

        current = history[-1]

        # Growth rate
        growth = self._compute_growth(history)

        # Engagement score
        engagement = self._engagement_score(
            current.bounce_rate, current.avg_duration
        )

        # Momentum
        momentum = self._compute_momentum(history)

        return WebTrafficSnapshot(
            symbol=current.symbol,
            domain=current.domain,
            visits=current.visits,
            unique_visitors=current.unique_visitors,
            bounce_rate=current.bounce_rate,
            avg_duration=current.avg_duration,
            growth_rate=round(growth, 2),
            engagement_score=round(engagement, 4),
            momentum=round(momentum, 4),
            timestamp=current.timestamp,
        )

    def _compute_growth(self, history: list[WebTrafficSnapshot]) -> float:
        """Compute visit growth rate over the configured window."""
        if len(history) < 2:
            return 0.0

        window = min(self.config.growth_window, len(history))
        recent = history[-1].visits
        past = history[-window].visits

        if past == 0:
            return 0.0
        return (recent - past) / past * 100

    def _engagement_score(
        self, bounce_rate: float, avg_duration: float
    ) -> float:
        """Compute engagement score from bounce rate and duration.

        Lower bounce + higher duration = better engagement.
        Score range: 0.0 to 1.0.
        """
        # Invert bounce rate (lower is better)
        bounce_component = max(0.0, 1.0 - bounce_rate)

        # Normalize duration (cap at 5 minutes)
        duration_component = min(avg_duration / 300.0, 1.0)

        w_b = self.config.engagement_bounce_weight
        w_d = self.config.engagement_duration_weight

        return w_b * bounce_component + w_d * duration_component

    def _compute_momentum(self, history: list[WebTrafficSnapshot]) -> float:
        """Compute traffic momentum via regression slope."""
        window = min(self.config.momentum_window, len(history))
        if window < 3:
            return 0.0

        visits = np.array(
            [h.visits for h in history[-window:]], dtype=float
        )
        mean_v = float(np.mean(visits))
        if mean_v == 0:
            return 0.0

        x = np.arange(len(visits), dtype=float)
        mean_x = np.mean(x)

        num = float(np.sum((x - mean_x) * (visits - mean_v)))
        den = float(np.sum((x - mean_x) ** 2))

        if den == 0:
            return 0.0

        slope = num / den
        return slope / mean_v

    def get_history(self, symbol: str) -> list[WebTrafficSnapshot]:
        return self._history.get(symbol, [])

    def reset(self) -> None:
        self._history.clear()
