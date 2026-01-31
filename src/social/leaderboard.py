"""Leaderboard computation and management.

Ranks traders by performance metrics with anti-gaming rules.
"""

import logging
from typing import Optional

from src.social.config import (
    LeaderboardMetric,
    LeaderboardPeriod,
    LEADERBOARD_MINIMUMS,
    SocialConfig,
    DEFAULT_SOCIAL_CONFIG,
)
from src.social.models import (
    Leaderboard,
    LeaderboardEntry,
    TraderProfile,
    PerformanceStats,
    _utc_now,
)

logger = logging.getLogger(__name__)


class LeaderboardManager:
    """Computes and manages leaderboards.

    Features:
    - Multiple ranking metrics (return, Sharpe, win rate, etc.)
    - Multiple time periods
    - Anti-gaming minimum requirements
    - Rank change tracking
    """

    def __init__(self, config: Optional[SocialConfig] = None) -> None:
        self.config = config or DEFAULT_SOCIAL_CONFIG
        self._leaderboards: dict[str, Leaderboard] = {}
        self._previous_ranks: dict[str, dict[str, int]] = {}

    def _board_key(
        self,
        metric: LeaderboardMetric,
        period: LeaderboardPeriod,
    ) -> str:
        """Generate a key for a leaderboard."""
        return f"{metric.value}_{period.value}"

    def compute_leaderboard(
        self,
        profiles: list[TraderProfile],
        metric: LeaderboardMetric = LeaderboardMetric.TOTAL_RETURN,
        period: LeaderboardPeriod = LeaderboardPeriod.THREE_MONTHS,
    ) -> Leaderboard:
        """Compute a leaderboard from trader profiles.

        Args:
            profiles: List of all trader profiles.
            metric: Metric to rank by.
            period: Time period for ranking.

        Returns:
            Computed Leaderboard.
        """
        key = self._board_key(metric, period)
        previous = self._previous_ranks.get(key, {})

        # Filter by minimums
        qualified = [
            p for p in profiles
            if self._is_qualified(p.stats)
        ]

        # Sort by metric
        sorted_profiles = sorted(
            qualified,
            key=lambda p: self._get_metric_value(p.stats, metric),
            reverse=True,
        )

        # Build entries
        max_entries = self.config.leaderboard.max_entries
        entries: list[LeaderboardEntry] = []
        for i, profile in enumerate(sorted_profiles[:max_entries]):
            entry = LeaderboardEntry(
                rank=i + 1,
                user_id=profile.user_id,
                display_name=profile.display_name,
                metric_value=self._get_metric_value(profile.stats, metric),
                stats=profile.stats,
                badges=list(profile.badges),
                followers_count=profile.followers_count,
                previous_rank=previous.get(profile.user_id),
            )
            entries.append(entry)

        leaderboard = Leaderboard(
            metric=metric,
            period=period,
            entries=entries,
        )

        # Store current ranks for next comparison
        self._previous_ranks[key] = {
            e.user_id: e.rank for e in entries
        }

        self._leaderboards[key] = leaderboard
        logger.info(
            "Computed leaderboard %s with %d entries",
            key, len(entries),
        )
        return leaderboard

    def get_leaderboard(
        self,
        metric: LeaderboardMetric = LeaderboardMetric.TOTAL_RETURN,
        period: LeaderboardPeriod = LeaderboardPeriod.THREE_MONTHS,
    ) -> Optional[Leaderboard]:
        """Get a cached leaderboard.

        Args:
            metric: Ranking metric.
            period: Time period.

        Returns:
            Leaderboard, or None if not computed yet.
        """
        key = self._board_key(metric, period)
        return self._leaderboards.get(key)

    def get_user_rank(
        self,
        user_id: str,
        metric: LeaderboardMetric = LeaderboardMetric.TOTAL_RETURN,
        period: LeaderboardPeriod = LeaderboardPeriod.THREE_MONTHS,
    ) -> Optional[LeaderboardEntry]:
        """Get a user's rank on a leaderboard.

        Args:
            user_id: User ID.
            metric: Ranking metric.
            period: Time period.

        Returns:
            LeaderboardEntry, or None if not ranked.
        """
        board = self.get_leaderboard(metric, period)
        if not board:
            return None

        for entry in board.entries:
            if entry.user_id == user_id:
                return entry
        return None

    def _is_qualified(self, stats: PerformanceStats) -> bool:
        """Check if stats meet leaderboard minimums.

        Args:
            stats: Performance stats.

        Returns:
            True if qualified.
        """
        return stats.total_trades >= LEADERBOARD_MINIMUMS["min_trades"]

    @staticmethod
    def _get_metric_value(
        stats: PerformanceStats,
        metric: LeaderboardMetric,
    ) -> float:
        """Extract metric value from performance stats.

        Args:
            stats: Performance stats.
            metric: Metric to extract.

        Returns:
            Metric value.
        """
        if metric == LeaderboardMetric.TOTAL_RETURN:
            return stats.total_return
        elif metric == LeaderboardMetric.SHARPE_RATIO:
            return stats.sharpe_ratio
        elif metric == LeaderboardMetric.WIN_RATE:
            return stats.win_rate
        elif metric == LeaderboardMetric.CONSISTENCY:
            # Composite: win_rate * (1 - |max_drawdown|)
            return stats.win_rate * (1 - abs(stats.max_drawdown))
        elif metric == LeaderboardMetric.RISK_ADJUSTED:
            return stats.calmar_ratio
        elif metric == LeaderboardMetric.PROFIT_FACTOR:
            return stats.profit_factor
        else:
            return stats.total_return
