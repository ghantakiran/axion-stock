"""Trade Journal Analytics - PRD-66.

Provides performance analytics across multiple dimensions:
- Win rate, profit factor, expectancy by setup/strategy
- Emotion correlation analysis
- Time-based patterns (day of week, hour of day)
- Pattern recognition and insights
"""

import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from src.db.models import JournalEntry, DailyReview, PeriodicReview, TradeSetup, TradingStrategy

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Core trading performance metrics."""

    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    expectancy: float = 0.0
    avg_winner: float = 0.0
    avg_loser: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    total_pnl: float = 0.0
    avg_risk_reward: float = 0.0


@dataclass
class DimensionBreakdown:
    """Performance breakdown by a dimension."""

    dimension: str
    category: str
    metrics: PerformanceMetrics


@dataclass
class EmotionAnalysis:
    """Emotion correlation analysis results."""

    emotion: str
    trade_count: int
    win_rate: float
    avg_pnl: float
    avg_pnl_pct: float
    recommendation: str  # "favorable", "neutral", "avoid"


@dataclass
class PatternInsight:
    """Detected pattern or insight."""

    insight_type: str  # "strength", "weakness", "pattern", "recommendation"
    title: str
    description: str
    confidence: float
    supporting_data: dict


class JournalAnalytics:
    """Analytics engine for trade journal data."""

    def __init__(self, session: Session):
        """Initialize analytics with database session."""
        self.session = session

    def calculate_metrics(self, entries: list[JournalEntry]) -> PerformanceMetrics:
        """Calculate performance metrics from journal entries.

        Args:
            entries: List of closed journal entries.

        Returns:
            PerformanceMetrics dataclass.
        """
        if not entries:
            return PerformanceMetrics()

        # Filter to closed trades only
        closed = [e for e in entries if e.exit_date is not None and e.realized_pnl is not None]

        if not closed:
            return PerformanceMetrics(total_trades=len(entries))

        winners = [e for e in closed if e.realized_pnl > 0]
        losers = [e for e in closed if e.realized_pnl < 0]

        total_profit = sum(e.realized_pnl for e in winners)
        total_loss = abs(sum(e.realized_pnl for e in losers))

        win_rate = len(winners) / len(closed) if closed else 0
        profit_factor = total_profit / total_loss if total_loss > 0 else float("inf")

        avg_winner = total_profit / len(winners) if winners else 0
        avg_loser = total_loss / len(losers) if losers else 0

        expectancy = (win_rate * avg_winner) - ((1 - win_rate) * avg_loser)

        # Risk/reward
        rr_values = [e.risk_reward_actual for e in closed if e.risk_reward_actual]
        avg_rr = np.mean(rr_values) if rr_values else 0

        return PerformanceMetrics(
            total_trades=len(closed),
            winning_trades=len(winners),
            losing_trades=len(losers),
            win_rate=win_rate,
            profit_factor=profit_factor,
            expectancy=expectancy,
            avg_winner=avg_winner,
            avg_loser=avg_loser,
            largest_win=max((e.realized_pnl for e in winners), default=0),
            largest_loss=abs(min((e.realized_pnl for e in losers), default=0)),
            total_pnl=sum(e.realized_pnl for e in closed),
            avg_risk_reward=avg_rr,
        )

    def get_overall_metrics(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> PerformanceMetrics:
        """Get overall performance metrics.

        Args:
            start_date: Filter entries after this date.
            end_date: Filter entries before this date.

        Returns:
            PerformanceMetrics for the period.
        """
        query = self.session.query(JournalEntry)

        if start_date:
            query = query.filter(JournalEntry.entry_date >= start_date)
        if end_date:
            query = query.filter(JournalEntry.entry_date <= end_date)

        entries = query.all()
        return self.calculate_metrics(entries)

    def get_breakdown_by_setup(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[DimensionBreakdown]:
        """Get performance breakdown by trade setup.

        Args:
            start_date: Filter entries after this date.
            end_date: Filter entries before this date.

        Returns:
            List of DimensionBreakdown by setup.
        """
        query = self.session.query(JournalEntry).filter(JournalEntry.setup_id.isnot(None))

        if start_date:
            query = query.filter(JournalEntry.entry_date >= start_date)
        if end_date:
            query = query.filter(JournalEntry.entry_date <= end_date)

        entries = query.all()

        # Group by setup
        by_setup = defaultdict(list)
        for entry in entries:
            by_setup[entry.setup_id].append(entry)

        results = []
        for setup_id, setup_entries in by_setup.items():
            metrics = self.calculate_metrics(setup_entries)
            results.append(
                DimensionBreakdown(
                    dimension="setup",
                    category=setup_id,
                    metrics=metrics,
                )
            )

        # Sort by win rate descending
        results.sort(key=lambda x: x.metrics.win_rate, reverse=True)
        return results

    def get_breakdown_by_strategy(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[DimensionBreakdown]:
        """Get performance breakdown by trading strategy.

        Args:
            start_date: Filter entries after this date.
            end_date: Filter entries before this date.

        Returns:
            List of DimensionBreakdown by strategy.
        """
        query = self.session.query(JournalEntry).filter(JournalEntry.strategy_id.isnot(None))

        if start_date:
            query = query.filter(JournalEntry.entry_date >= start_date)
        if end_date:
            query = query.filter(JournalEntry.entry_date <= end_date)

        entries = query.all()

        by_strategy = defaultdict(list)
        for entry in entries:
            by_strategy[entry.strategy_id].append(entry)

        results = []
        for strategy_id, strategy_entries in by_strategy.items():
            metrics = self.calculate_metrics(strategy_entries)
            results.append(
                DimensionBreakdown(
                    dimension="strategy",
                    category=strategy_id,
                    metrics=metrics,
                )
            )

        results.sort(key=lambda x: x.metrics.profit_factor, reverse=True)
        return results

    def get_breakdown_by_day_of_week(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[DimensionBreakdown]:
        """Get performance breakdown by day of week.

        Args:
            start_date: Filter entries after this date.
            end_date: Filter entries before this date.

        Returns:
            List of DimensionBreakdown by day of week.
        """
        query = self.session.query(JournalEntry)

        if start_date:
            query = query.filter(JournalEntry.entry_date >= start_date)
        if end_date:
            query = query.filter(JournalEntry.entry_date <= end_date)

        entries = query.all()

        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        by_day = defaultdict(list)

        for entry in entries:
            if entry.entry_date:
                day_idx = entry.entry_date.weekday()
                by_day[days[day_idx]].append(entry)

        results = []
        for day in days[:5]:  # Trading days only
            if day in by_day:
                metrics = self.calculate_metrics(by_day[day])
                results.append(
                    DimensionBreakdown(
                        dimension="day_of_week",
                        category=day,
                        metrics=metrics,
                    )
                )

        return results

    def get_breakdown_by_hour(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[DimensionBreakdown]:
        """Get performance breakdown by hour of day.

        Args:
            start_date: Filter entries after this date.
            end_date: Filter entries before this date.

        Returns:
            List of DimensionBreakdown by hour.
        """
        query = self.session.query(JournalEntry)

        if start_date:
            query = query.filter(JournalEntry.entry_date >= start_date)
        if end_date:
            query = query.filter(JournalEntry.entry_date <= end_date)

        entries = query.all()

        by_hour = defaultdict(list)
        for entry in entries:
            if entry.entry_date:
                hour = entry.entry_date.hour
                by_hour[hour].append(entry)

        results = []
        for hour in sorted(by_hour.keys()):
            metrics = self.calculate_metrics(by_hour[hour])
            results.append(
                DimensionBreakdown(
                    dimension="hour",
                    category=f"{hour:02d}:00",
                    metrics=metrics,
                )
            )

        return results

    def get_breakdown_by_trade_type(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[DimensionBreakdown]:
        """Get performance breakdown by trade type (scalp, day, swing, position).

        Args:
            start_date: Filter entries after this date.
            end_date: Filter entries before this date.

        Returns:
            List of DimensionBreakdown by trade type.
        """
        query = self.session.query(JournalEntry).filter(JournalEntry.trade_type.isnot(None))

        if start_date:
            query = query.filter(JournalEntry.entry_date >= start_date)
        if end_date:
            query = query.filter(JournalEntry.entry_date <= end_date)

        entries = query.all()

        by_type = defaultdict(list)
        for entry in entries:
            by_type[entry.trade_type].append(entry)

        results = []
        for trade_type, type_entries in by_type.items():
            metrics = self.calculate_metrics(type_entries)
            results.append(
                DimensionBreakdown(
                    dimension="trade_type",
                    category=trade_type,
                    metrics=metrics,
                )
            )

        return results

    def analyze_emotions(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> dict[str, list[EmotionAnalysis]]:
        """Analyze performance correlation with emotional states.

        Args:
            start_date: Filter entries after this date.
            end_date: Filter entries before this date.

        Returns:
            Dict with keys 'pre_trade', 'during_trade', 'post_trade'.
        """
        query = self.session.query(JournalEntry)

        if start_date:
            query = query.filter(JournalEntry.entry_date >= start_date)
        if end_date:
            query = query.filter(JournalEntry.entry_date <= end_date)

        entries = query.all()

        results = {
            "pre_trade": self._analyze_emotion_phase(entries, "pre_trade_emotion"),
            "during_trade": self._analyze_emotion_phase(entries, "during_trade_emotion"),
            "post_trade": self._analyze_emotion_phase(entries, "post_trade_emotion"),
        }

        return results

    def _analyze_emotion_phase(
        self, entries: list[JournalEntry], phase_attr: str
    ) -> list[EmotionAnalysis]:
        """Analyze a specific emotion phase."""
        by_emotion = defaultdict(list)

        for entry in entries:
            emotion = getattr(entry, phase_attr)
            if emotion and entry.exit_date and entry.realized_pnl is not None:
                by_emotion[emotion].append(entry)

        results = []
        for emotion, emotion_entries in by_emotion.items():
            winners = [e for e in emotion_entries if e.realized_pnl > 0]
            win_rate = len(winners) / len(emotion_entries) if emotion_entries else 0

            avg_pnl = np.mean([e.realized_pnl for e in emotion_entries]) if emotion_entries else 0
            avg_pnl_pct = (
                np.mean([e.realized_pnl_pct for e in emotion_entries if e.realized_pnl_pct])
                if emotion_entries
                else 0
            )

            # Determine recommendation
            if win_rate >= 0.6 and avg_pnl > 0:
                recommendation = "favorable"
            elif win_rate <= 0.4 or avg_pnl < 0:
                recommendation = "avoid"
            else:
                recommendation = "neutral"

            results.append(
                EmotionAnalysis(
                    emotion=emotion,
                    trade_count=len(emotion_entries),
                    win_rate=win_rate,
                    avg_pnl=avg_pnl,
                    avg_pnl_pct=avg_pnl_pct,
                    recommendation=recommendation,
                )
            )

        # Sort by win rate
        results.sort(key=lambda x: x.win_rate, reverse=True)
        return results

    def get_equity_curve(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> pd.DataFrame:
        """Generate equity curve from closed trades.

        Args:
            start_date: Filter entries after this date.
            end_date: Filter entries before this date.

        Returns:
            DataFrame with date and cumulative_pnl columns.
        """
        query = self.session.query(JournalEntry).filter(
            JournalEntry.exit_date.isnot(None),
            JournalEntry.realized_pnl.isnot(None),
        )

        if start_date:
            query = query.filter(JournalEntry.exit_date >= start_date)
        if end_date:
            query = query.filter(JournalEntry.exit_date <= end_date)

        entries = query.order_by(JournalEntry.exit_date).all()

        if not entries:
            return pd.DataFrame(columns=["date", "cumulative_pnl", "trade_pnl"])

        data = []
        cumulative = 0
        for entry in entries:
            cumulative += entry.realized_pnl
            data.append(
                {
                    "date": entry.exit_date.date() if isinstance(entry.exit_date, datetime) else entry.exit_date,
                    "cumulative_pnl": cumulative,
                    "trade_pnl": entry.realized_pnl,
                    "symbol": entry.symbol,
                }
            )

        return pd.DataFrame(data)

    def get_drawdown_analysis(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> dict:
        """Analyze drawdowns from equity curve.

        Args:
            start_date: Filter entries after this date.
            end_date: Filter entries before this date.

        Returns:
            Dict with max_drawdown, current_drawdown, avg_drawdown_duration.
        """
        equity_df = self.get_equity_curve(start_date, end_date)

        if equity_df.empty:
            return {
                "max_drawdown": 0,
                "max_drawdown_pct": 0,
                "current_drawdown": 0,
                "avg_drawdown_duration": 0,
            }

        cumulative = equity_df["cumulative_pnl"].values
        peak = np.maximum.accumulate(cumulative)
        drawdown = peak - cumulative

        max_dd = np.max(drawdown)
        max_dd_pct = max_dd / np.max(peak) if np.max(peak) > 0 else 0
        current_dd = drawdown[-1] if len(drawdown) > 0 else 0

        return {
            "max_drawdown": max_dd,
            "max_drawdown_pct": max_dd_pct,
            "current_drawdown": current_dd,
            "drawdown_series": drawdown.tolist(),
        }

    def generate_insights(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[PatternInsight]:
        """Generate automated insights from trading data.

        Args:
            start_date: Filter entries after this date.
            end_date: Filter entries before this date.

        Returns:
            List of PatternInsight with detected patterns and recommendations.
        """
        insights = []

        # Get breakdowns
        overall = self.get_overall_metrics(start_date, end_date)
        by_setup = self.get_breakdown_by_setup(start_date, end_date)
        by_day = self.get_breakdown_by_day_of_week(start_date, end_date)
        emotions = self.analyze_emotions(start_date, end_date)

        # Insight: Best performing setups
        if by_setup:
            best = by_setup[0]
            if best.metrics.total_trades >= 5 and best.metrics.win_rate >= 0.6:
                insights.append(
                    PatternInsight(
                        insight_type="strength",
                        title=f"Strong Setup: {best.category}",
                        description=f"Your {best.category} setup has a {best.metrics.win_rate:.0%} win rate "
                        f"across {best.metrics.total_trades} trades with profit factor {best.metrics.profit_factor:.2f}.",
                        confidence=min(0.9, best.metrics.total_trades / 20),
                        supporting_data={
                            "setup": best.category,
                            "win_rate": best.metrics.win_rate,
                            "profit_factor": best.metrics.profit_factor,
                            "trade_count": best.metrics.total_trades,
                        },
                    )
                )

            # Worst performing setups
            worst = by_setup[-1]
            if worst.metrics.total_trades >= 5 and worst.metrics.win_rate <= 0.4:
                insights.append(
                    PatternInsight(
                        insight_type="weakness",
                        title=f"Underperforming Setup: {worst.category}",
                        description=f"Your {worst.category} setup has only {worst.metrics.win_rate:.0%} win rate. "
                        f"Consider reviewing or avoiding this setup.",
                        confidence=min(0.9, worst.metrics.total_trades / 20),
                        supporting_data={
                            "setup": worst.category,
                            "win_rate": worst.metrics.win_rate,
                            "total_pnl": worst.metrics.total_pnl,
                        },
                    )
                )

        # Insight: Day of week patterns
        if by_day and len(by_day) >= 3:
            best_day = max(by_day, key=lambda x: x.metrics.win_rate)
            worst_day = min(by_day, key=lambda x: x.metrics.win_rate)

            if best_day.metrics.win_rate - worst_day.metrics.win_rate > 0.15:
                insights.append(
                    PatternInsight(
                        insight_type="pattern",
                        title=f"Day Pattern Detected",
                        description=f"You perform best on {best_day.category} ({best_day.metrics.win_rate:.0%}) "
                        f"and worst on {worst_day.category} ({worst_day.metrics.win_rate:.0%}). "
                        f"Consider reducing size on {worst_day.category}.",
                        confidence=0.7,
                        supporting_data={
                            "best_day": best_day.category,
                            "best_win_rate": best_day.metrics.win_rate,
                            "worst_day": worst_day.category,
                            "worst_win_rate": worst_day.metrics.win_rate,
                        },
                    )
                )

        # Insight: Emotional patterns
        pre_emotions = emotions.get("pre_trade", [])
        avoid_emotions = [e for e in pre_emotions if e.recommendation == "avoid" and e.trade_count >= 5]

        for em in avoid_emotions[:2]:  # Top 2 emotions to avoid
            insights.append(
                PatternInsight(
                    insight_type="recommendation",
                    title=f"Avoid Trading When {em.emotion.title()}",
                    description=f"When entering trades feeling {em.emotion}, your win rate is only "
                    f"{em.win_rate:.0%} with avg P&L of ${em.avg_pnl:.2f}. "
                    f"Consider stepping away when feeling {em.emotion}.",
                    confidence=min(0.85, em.trade_count / 15),
                    supporting_data={
                        "emotion": em.emotion,
                        "win_rate": em.win_rate,
                        "avg_pnl": em.avg_pnl,
                        "trade_count": em.trade_count,
                    },
                )
            )

        # Insight: Risk/reward
        if overall.avg_risk_reward > 0:
            if overall.avg_risk_reward < 1.0:
                insights.append(
                    PatternInsight(
                        insight_type="weakness",
                        title="Risk/Reward Below 1:1",
                        description=f"Your average risk/reward is {overall.avg_risk_reward:.2f}. "
                        f"Consider targeting at least 1.5:1 R:R on trades.",
                        confidence=0.8,
                        supporting_data={"avg_rr": overall.avg_risk_reward},
                    )
                )
            elif overall.avg_risk_reward >= 2.0:
                insights.append(
                    PatternInsight(
                        insight_type="strength",
                        title="Excellent Risk/Reward",
                        description=f"Your average risk/reward is {overall.avg_risk_reward:.2f}:1. "
                        f"Great job maintaining favorable R:R!",
                        confidence=0.85,
                        supporting_data={"avg_rr": overall.avg_risk_reward},
                    )
                )

        return insights

    def get_streak_analysis(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> dict:
        """Analyze winning and losing streaks.

        Args:
            start_date: Filter entries after this date.
            end_date: Filter entries before this date.

        Returns:
            Dict with max_win_streak, max_loss_streak, current_streak.
        """
        query = self.session.query(JournalEntry).filter(
            JournalEntry.exit_date.isnot(None),
            JournalEntry.realized_pnl.isnot(None),
        )

        if start_date:
            query = query.filter(JournalEntry.exit_date >= start_date)
        if end_date:
            query = query.filter(JournalEntry.exit_date <= end_date)

        entries = query.order_by(JournalEntry.exit_date).all()

        if not entries:
            return {
                "max_win_streak": 0,
                "max_loss_streak": 0,
                "current_streak": 0,
                "current_streak_type": None,
            }

        max_win = 0
        max_loss = 0
        current = 0
        current_type = None

        for entry in entries:
            if entry.realized_pnl > 0:
                if current_type == "win":
                    current += 1
                else:
                    current = 1
                    current_type = "win"
                max_win = max(max_win, current)
            else:
                if current_type == "loss":
                    current += 1
                else:
                    current = 1
                    current_type = "loss"
                max_loss = max(max_loss, current)

        return {
            "max_win_streak": max_win,
            "max_loss_streak": max_loss,
            "current_streak": current,
            "current_streak_type": current_type,
        }

    def get_r_multiple_distribution(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> dict:
        """Analyze R-multiple distribution.

        R-multiple = Actual P&L / Initial Risk

        Args:
            start_date: Filter entries after this date.
            end_date: Filter entries before this date.

        Returns:
            Dict with distribution stats and histogram data.
        """
        query = self.session.query(JournalEntry).filter(
            JournalEntry.exit_date.isnot(None),
            JournalEntry.realized_pnl.isnot(None),
            JournalEntry.initial_stop.isnot(None),
        )

        if start_date:
            query = query.filter(JournalEntry.exit_date >= start_date)
        if end_date:
            query = query.filter(JournalEntry.exit_date <= end_date)

        entries = query.all()

        if not entries:
            return {"avg_r": 0, "median_r": 0, "distribution": []}

        r_multiples = []
        for entry in entries:
            # Calculate initial risk
            if entry.direction == "long":
                initial_risk = entry.entry_price - entry.initial_stop
            else:
                initial_risk = entry.initial_stop - entry.entry_price

            if initial_risk > 0:
                r_multiple = entry.realized_pnl / (initial_risk * entry.entry_quantity)
                r_multiples.append(r_multiple)

        if not r_multiples:
            return {"avg_r": 0, "median_r": 0, "distribution": []}

        return {
            "avg_r": np.mean(r_multiples),
            "median_r": np.median(r_multiples),
            "std_r": np.std(r_multiples),
            "min_r": np.min(r_multiples),
            "max_r": np.max(r_multiples),
            "distribution": r_multiples,
        }
