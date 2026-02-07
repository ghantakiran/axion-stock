"""Performance tracking for marketplace strategies."""

from datetime import datetime, timezone, date, timedelta
from typing import Optional
from collections import defaultdict

from src.marketplace.config import MarketplaceConfig, DEFAULT_MARKETPLACE_CONFIG
from src.marketplace.models import Strategy, PerformanceSnapshot, LeaderboardEntry


class PerformanceTracker:
    """Tracks strategy performance for the marketplace."""

    def __init__(self, config: Optional[MarketplaceConfig] = None):
        self.config = config or DEFAULT_MARKETPLACE_CONFIG
        # strategy_id -> date -> snapshot
        self._snapshots: dict[str, dict[date, PerformanceSnapshot]] = defaultdict(dict)

    def record_snapshot(
        self,
        strategy_id: str,
        snapshot_date: date,
        daily_return_pct: float = 0.0,
        cumulative_return_pct: float = 0.0,
        benchmark_return_pct: float = 0.0,
        sharpe_ratio: Optional[float] = None,
        sortino_ratio: Optional[float] = None,
        max_drawdown_pct: float = 0.0,
        current_drawdown_pct: float = 0.0,
        volatility_pct: Optional[float] = None,
        win_rate: Optional[float] = None,
        profit_factor: Optional[float] = None,
        avg_win_pct: Optional[float] = None,
        avg_loss_pct: Optional[float] = None,
        trade_count: int = 0,
        open_positions: int = 0,
        portfolio_value: Optional[float] = None,
    ) -> PerformanceSnapshot:
        """Record a daily performance snapshot."""
        snapshot = PerformanceSnapshot(
            strategy_id=strategy_id,
            snapshot_date=snapshot_date,
            daily_return_pct=daily_return_pct,
            cumulative_return_pct=cumulative_return_pct,
            benchmark_return_pct=benchmark_return_pct,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            max_drawdown_pct=max_drawdown_pct,
            current_drawdown_pct=current_drawdown_pct,
            volatility_pct=volatility_pct,
            win_rate=win_rate,
            profit_factor=profit_factor,
            avg_win_pct=avg_win_pct,
            avg_loss_pct=avg_loss_pct,
            trade_count=trade_count,
            open_positions=open_positions,
            portfolio_value=portfolio_value,
        )

        self._snapshots[strategy_id][snapshot_date] = snapshot
        return snapshot

    def get_snapshot(self, strategy_id: str, snapshot_date: date) -> Optional[PerformanceSnapshot]:
        """Get snapshot for a specific date."""
        return self._snapshots.get(strategy_id, {}).get(snapshot_date)

    def get_latest_snapshot(self, strategy_id: str) -> Optional[PerformanceSnapshot]:
        """Get the most recent snapshot for a strategy."""
        strategy_snapshots = self._snapshots.get(strategy_id, {})
        if not strategy_snapshots:
            return None

        latest_date = max(strategy_snapshots.keys())
        return strategy_snapshots[latest_date]

    def get_snapshots(
        self,
        strategy_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[PerformanceSnapshot]:
        """Get snapshots for a date range."""
        strategy_snapshots = self._snapshots.get(strategy_id, {})

        snapshots = []
        for snapshot_date, snapshot in sorted(strategy_snapshots.items()):
            if start_date and snapshot_date < start_date:
                continue
            if end_date and snapshot_date > end_date:
                continue
            snapshots.append(snapshot)

        return snapshots

    def get_period_return(
        self,
        strategy_id: str,
        days: int = 30,
    ) -> Optional[float]:
        """Get return over a period."""
        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        snapshots = self.get_snapshots(strategy_id, start_date, end_date)
        if len(snapshots) < 2:
            return None

        start_value = snapshots[0].cumulative_return_pct
        end_value = snapshots[-1].cumulative_return_pct

        return end_value - start_value

    def get_max_drawdown(
        self,
        strategy_id: str,
        days: Optional[int] = None,
    ) -> float:
        """Get maximum drawdown over a period."""
        if days:
            end_date = date.today()
            start_date = end_date - timedelta(days=days)
            snapshots = self.get_snapshots(strategy_id, start_date, end_date)
        else:
            snapshots = list(self._snapshots.get(strategy_id, {}).values())

        if not snapshots:
            return 0.0

        return max(s.max_drawdown_pct for s in snapshots)

    def calculate_sharpe_ratio(
        self,
        strategy_id: str,
        risk_free_rate: float = 0.05,
        days: int = 252,
    ) -> Optional[float]:
        """Calculate Sharpe ratio from daily returns."""
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        snapshots = self.get_snapshots(strategy_id, start_date, end_date)

        if len(snapshots) < 30:  # Need enough data
            return None

        daily_returns = [s.daily_return_pct / 100 for s in snapshots]
        if not daily_returns:
            return None

        import statistics
        try:
            mean_return = statistics.mean(daily_returns)
            std_return = statistics.stdev(daily_returns)

            if std_return == 0:
                return None

            # Annualized
            annual_return = mean_return * 252
            annual_std = std_return * (252 ** 0.5)

            return (annual_return - risk_free_rate) / annual_std
        except statistics.StatisticsError:
            return None

    def get_leaderboard(
        self,
        strategies: list[Strategy],
        sort_by: str = "return",
        period_days: int = 30,
        limit: int = 100,
    ) -> list[LeaderboardEntry]:
        """Generate strategy leaderboard."""
        entries = []

        for strategy in strategies:
            if not strategy.is_published:
                continue

            # Check minimum history
            snapshots = self.get_snapshots(strategy.strategy_id)
            if len(snapshots) < self.config.min_days_for_leaderboard:
                continue

            latest = self.get_latest_snapshot(strategy.strategy_id)
            if not latest:
                continue

            period_return = self.get_period_return(strategy.strategy_id, period_days) or 0

            # Calculate score (weighted combination)
            score = self._calculate_score(latest, period_return, strategy)

            entries.append(LeaderboardEntry(
                rank=0,  # Set after sorting
                strategy=strategy,
                performance=latest,
                score=score,
            ))

        # Sort by score (descending)
        if sort_by == "return":
            entries.sort(key=lambda e: e.performance.cumulative_return_pct, reverse=True)
        elif sort_by == "sharpe":
            entries.sort(key=lambda e: e.performance.sharpe_ratio or 0, reverse=True)
        elif sort_by == "subscribers":
            entries.sort(key=lambda e: e.strategy.subscriber_count, reverse=True)
        elif sort_by == "rating":
            entries.sort(key=lambda e: e.strategy.avg_rating, reverse=True)
        else:
            entries.sort(key=lambda e: e.score, reverse=True)

        # Assign ranks and limit
        for i, entry in enumerate(entries[:limit]):
            entry.rank = i + 1

        return entries[:limit]

    def _calculate_score(
        self,
        snapshot: PerformanceSnapshot,
        period_return: float,
        strategy: Strategy,
    ) -> float:
        """Calculate composite score for ranking."""
        score = 0.0

        # Return component (40%)
        if snapshot.cumulative_return_pct > 0:
            score += min(snapshot.cumulative_return_pct / 100, 1.0) * 40

        # Risk-adjusted component (30%)
        if snapshot.sharpe_ratio and snapshot.sharpe_ratio > 0:
            score += min(snapshot.sharpe_ratio / 3, 1.0) * 30

        # Drawdown penalty (15%)
        if snapshot.max_drawdown_pct < 20:
            score += (1 - snapshot.max_drawdown_pct / 20) * 15

        # Social proof (15%)
        if strategy.subscriber_count > 0:
            score += min(strategy.subscriber_count / 100, 1.0) * 7.5
        if strategy.avg_rating > 0:
            score += (strategy.avg_rating / 5) * 7.5

        return round(score, 2)

    def get_performance_summary(self, strategy_id: str) -> dict:
        """Get performance summary for a strategy."""
        latest = self.get_latest_snapshot(strategy_id)
        if not latest:
            return {}

        return {
            "cumulative_return_pct": latest.cumulative_return_pct,
            "sharpe_ratio": latest.sharpe_ratio,
            "sortino_ratio": latest.sortino_ratio,
            "max_drawdown_pct": latest.max_drawdown_pct,
            "win_rate": latest.win_rate,
            "profit_factor": latest.profit_factor,
            "trade_count": latest.trade_count,
            "return_7d": self.get_period_return(strategy_id, 7),
            "return_30d": self.get_period_return(strategy_id, 30),
            "return_90d": self.get_period_return(strategy_id, 90),
        }

    def get_stats(self) -> dict:
        """Get performance tracking statistics."""
        total_snapshots = sum(len(s) for s in self._snapshots.values())

        return {
            "tracked_strategies": len(self._snapshots),
            "total_snapshots": total_snapshots,
        }
