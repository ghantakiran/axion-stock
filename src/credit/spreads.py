"""Credit Spread Analyzer.

Tracks credit spreads, computes z-scores and percentiles, detects
widening/tightening trends, and provides cross-issuer relative value.
"""

import logging
from collections import defaultdict
from typing import Optional

import numpy as np

from src.credit.config import SpreadConfig, SpreadType, DEFAULT_CREDIT_CONFIG
from src.credit.models import CreditSpread, SpreadSummary

logger = logging.getLogger(__name__)


class SpreadAnalyzer:
    """Analyzes credit spreads."""

    def __init__(self, config: Optional[SpreadConfig] = None) -> None:
        self.config = config or DEFAULT_CREDIT_CONFIG.spread
        self._history: dict[str, list[CreditSpread]] = defaultdict(list)

    def add_spread(self, spread: CreditSpread) -> CreditSpread:
        """Add a spread observation and compute z-score."""
        history = self._history[spread.symbol]
        if len(history) >= 2:
            values = [s.spread_bps for s in history]
            mean = float(np.mean(values))
            std = float(np.std(values, ddof=1))
            if std > 0:
                spread.z_score = round((spread.spread_bps - mean) / std, 4)
            # Percentile
            spread.percentile = round(
                float(np.sum(np.array(values) <= spread.spread_bps) / len(values)),
                4,
            )
        history.append(spread)
        return spread

    def add_spreads(self, spreads: list[CreditSpread]) -> list[CreditSpread]:
        """Add multiple spread observations."""
        return [self.add_spread(s) for s in spreads]

    def analyze(self, symbol: str) -> SpreadSummary:
        """Analyze spread history for a symbol.

        Returns current spread, average, trend, z-score, and percentile.
        """
        history = self._history.get(symbol, [])
        if not history:
            return SpreadSummary(symbol=symbol)

        values = np.array([s.spread_bps for s in history])
        current = values[-1]

        # Trend via linear regression slope
        trend = 0.0
        if len(values) >= 3:
            x = np.arange(len(values))
            coeffs = np.polyfit(x, values, 1)
            trend = float(coeffs[0])

        mean_val = float(np.mean(values))
        std_val = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0

        z = (current - mean_val) / std_val if std_val > 0 else 0.0
        pct = float(np.sum(values <= current) / len(values))

        return SpreadSummary(
            symbol=symbol,
            current_spread=float(current),
            avg_spread=round(mean_val, 2),
            min_spread=float(np.min(values)),
            max_spread=float(np.max(values)),
            std_spread=round(std_val, 2),
            trend=round(trend, 4),
            z_score=round(z, 4),
            percentile=round(pct, 4),
            n_observations=len(values),
        )

    def term_structure(self, symbol: str) -> list[dict]:
        """Get spread term structure (spread by maturity).

        Returns list of {term, spread_bps} sorted by term.
        """
        history = self._history.get(symbol, [])
        if not history:
            return []

        # Group by term, take latest observation
        by_term: dict[float, float] = {}
        for s in sorted(history, key=lambda x: x.timestamp):
            by_term[s.term] = s.spread_bps

        return sorted(
            [{"term": t, "spread_bps": v} for t, v in by_term.items()],
            key=lambda x: x["term"],
        )

    def relative_value(self, symbols: list[str]) -> list[dict]:
        """Cross-issuer relative value comparison.

        Returns list of {symbol, current_spread, z_score, percentile}
        sorted by z-score descending (most wide relative to history).
        """
        results = []
        for sym in symbols:
            summary = self.analyze(sym)
            if summary.n_observations > 0:
                results.append({
                    "symbol": sym,
                    "current_spread": summary.current_spread,
                    "avg_spread": summary.avg_spread,
                    "z_score": summary.z_score,
                    "percentile": summary.percentile,
                })

        return sorted(results, key=lambda x: x["z_score"], reverse=True)

    def get_history(self, symbol: str) -> list[CreditSpread]:
        """Get spread history for a symbol."""
        return list(self._history.get(symbol, []))

    def reset(self) -> None:
        """Clear all stored spreads."""
        self._history.clear()
