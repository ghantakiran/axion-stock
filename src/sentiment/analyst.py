"""Analyst Consensus Tracking.

Tracks analyst ratings, price targets, and estimate revisions
to generate consensus signals.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from src.sentiment.config import AnalystConfig

logger = logging.getLogger(__name__)


@dataclass
class AnalystRating:
    """Individual analyst rating."""

    analyst_name: str = ""
    firm: str = ""
    rating: str = "hold"  # strong_buy, buy, hold, sell, strong_sell
    target_price: float = 0.0
    previous_rating: str = ""
    previous_target: float = 0.0
    date: str = ""


@dataclass
class EstimateRevision:
    """EPS estimate revision."""

    analyst_name: str = ""
    firm: str = ""
    period: str = ""  # Q1_2026, FY_2026
    previous_estimate: float = 0.0
    new_estimate: float = 0.0
    revision_pct: float = 0.0
    date: str = ""


@dataclass
class ConsensusReport:
    """Analyst consensus summary for a symbol."""

    symbol: str = ""
    consensus_rating: str = "hold"
    consensus_score: float = 0.0  # -1 to 1
    target_price_mean: float = 0.0
    target_price_median: float = 0.0
    target_price_high: float = 0.0
    target_price_low: float = 0.0
    current_price: float = 0.0
    upside_pct: float = 0.0
    num_analysts: int = 0
    buy_count: int = 0
    hold_count: int = 0
    sell_count: int = 0
    revision_momentum: float = 0.0  # -1 to 1
    revision_breadth: float = 0.0  # % of analysts revising up
    estimate_change_30d: float = 0.0
    estimate_change_60d: float = 0.0
    estimate_change_90d: float = 0.0

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "consensus_rating": self.consensus_rating,
            "consensus_score": self.consensus_score,
            "target_price_mean": self.target_price_mean,
            "target_price_median": self.target_price_median,
            "upside_pct": self.upside_pct,
            "num_analysts": self.num_analysts,
            "buy_count": self.buy_count,
            "hold_count": self.hold_count,
            "sell_count": self.sell_count,
            "revision_momentum": self.revision_momentum,
        }


class AnalystConsensusTracker:
    """Track analyst ratings, targets, and estimate revisions.

    Computes consensus ratings, price target ranges,
    and estimate revision momentum.

    Example:
        tracker = AnalystConsensusTracker()
        report = tracker.compute_consensus(ratings, current_price=150.0)
        revision_score = tracker.compute_revision_momentum(revisions)
    """

    def __init__(self, config: Optional[AnalystConfig] = None):
        self.config = config or AnalystConfig()

    def compute_consensus(
        self,
        ratings: list[AnalystRating],
        current_price: float = 0.0,
        symbol: str = "",
    ) -> ConsensusReport:
        """Compute analyst consensus from individual ratings.

        Args:
            ratings: List of analyst ratings.
            current_price: Current stock price.
            symbol: Stock symbol.

        Returns:
            ConsensusReport with consensus metrics.
        """
        report = ConsensusReport(symbol=symbol, current_price=current_price)

        if not ratings:
            return report

        rating_scale = self.config.rating_scale

        # Count by category
        for r in ratings:
            rating_lower = r.rating.lower().replace(" ", "_")
            if rating_lower in ("strong_buy", "buy"):
                report.buy_count += 1
            elif rating_lower in ("strong_sell", "sell"):
                report.sell_count += 1
            else:
                report.hold_count += 1

        report.num_analysts = len(ratings)

        # Consensus score: weighted average of rating values
        scores = []
        for r in ratings:
            rating_lower = r.rating.lower().replace(" ", "_")
            score = rating_scale.get(rating_lower, 0.0)
            scores.append(score)

        report.consensus_score = float(np.mean(scores))

        # Determine consensus label
        if report.consensus_score > 0.4:
            report.consensus_rating = "strong_buy"
        elif report.consensus_score > 0.1:
            report.consensus_rating = "buy"
        elif report.consensus_score > -0.1:
            report.consensus_rating = "hold"
        elif report.consensus_score > -0.4:
            report.consensus_rating = "sell"
        else:
            report.consensus_rating = "strong_sell"

        # Price targets
        targets = [r.target_price for r in ratings if r.target_price > 0]
        if targets:
            report.target_price_mean = float(np.mean(targets))
            report.target_price_median = float(np.median(targets))
            report.target_price_high = float(max(targets))
            report.target_price_low = float(min(targets))

            if current_price > 0:
                report.upside_pct = (report.target_price_mean - current_price) / current_price

        return report

    def compute_revision_momentum(
        self,
        revisions: list[EstimateRevision],
    ) -> float:
        """Compute estimate revision momentum score.

        Args:
            revisions: List of estimate revisions.

        Returns:
            Revision momentum score (-1 to 1).
        """
        if not revisions:
            return 0.0

        up_revisions = sum(1 for r in revisions if r.revision_pct > 0)
        down_revisions = sum(1 for r in revisions if r.revision_pct < 0)
        total = len(revisions)

        if total == 0:
            return 0.0

        # Direction score: net up vs down
        direction = (up_revisions - down_revisions) / total

        # Magnitude: average revision %
        avg_revision = float(np.mean([r.revision_pct for r in revisions]))

        # Combine direction and magnitude
        score = 0.6 * direction + 0.4 * np.clip(avg_revision * 10, -1, 1)

        return float(np.clip(score, -1, 1))

    def compute_revision_breadth(
        self,
        revisions: list[EstimateRevision],
    ) -> float:
        """Compute what % of analysts are revising estimates upward.

        Args:
            revisions: Recent revisions.

        Returns:
            Breadth from 0 (all down) to 1 (all up).
        """
        if not revisions:
            return 0.5

        up = sum(1 for r in revisions if r.revision_pct > 0)
        return up / len(revisions)

    def estimate_changes_by_window(
        self,
        revisions: list[EstimateRevision],
    ) -> dict[int, float]:
        """Compute average estimate change for each lookback window.

        Args:
            revisions: Estimate revisions with dates.

        Returns:
            Dict of window_days -> average revision pct.
        """
        now = datetime.now()
        result = {}

        for window_days in self.config.revision_windows_days:
            cutoff = now - timedelta(days=window_days)
            window_revisions = []

            for r in revisions:
                try:
                    rev_date = datetime.fromisoformat(r.date)
                    if rev_date >= cutoff:
                        window_revisions.append(r.revision_pct)
                except (ValueError, TypeError):
                    pass

            if window_revisions:
                result[window_days] = float(np.mean(window_revisions))
            else:
                result[window_days] = 0.0

        return result

    def get_rating_changes(
        self,
        ratings: list[AnalystRating],
    ) -> dict:
        """Summarize recent rating changes (upgrades/downgrades).

        Args:
            ratings: Analyst ratings with previous ratings.

        Returns:
            Dict with upgrade/downgrade counts and details.
        """
        rating_order = {
            "strong_sell": 0, "sell": 1, "hold": 2, "buy": 3, "strong_buy": 4,
        }

        upgrades = []
        downgrades = []
        maintained = []

        for r in ratings:
            current = rating_order.get(r.rating.lower().replace(" ", "_"), 2)
            previous = rating_order.get(r.previous_rating.lower().replace(" ", "_"), 2) if r.previous_rating else current

            if current > previous:
                upgrades.append(r)
            elif current < previous:
                downgrades.append(r)
            else:
                maintained.append(r)

        return {
            "upgrades": len(upgrades),
            "downgrades": len(downgrades),
            "maintained": len(maintained),
            "net": len(upgrades) - len(downgrades),
            "upgrade_details": [
                f"{r.firm}: {r.previous_rating} -> {r.rating}" for r in upgrades
            ],
            "downgrade_details": [
                f"{r.firm}: {r.previous_rating} -> {r.rating}" for r in downgrades
            ],
        }
