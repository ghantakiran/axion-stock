"""Performance Ledger — persistent influencer accuracy tracking.

Records predictions and outcomes over time, computes hit rates,
sector specialization, timing analysis, and generates reports.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class LedgerConfig:
    """Configuration for performance ledger."""

    min_predictions_for_stats: int = 5
    accuracy_decay_days: int = 90  # Older predictions weighted less
    sector_tracking: bool = True


@dataclass
class PredictionRecord:
    """A single prediction entry in the ledger."""

    prediction_id: str = ""
    author_id: str = ""
    platform: str = ""
    ticker: str = ""
    direction: str = "bullish"  # bullish, bearish
    sentiment_score: float = 0.0
    entry_price: float = 0.0
    exit_price: float = 0.0
    actual_return_pct: float = 0.0
    was_correct: bool = False
    sector: str = ""
    predicted_at: Optional[datetime] = None
    evaluated_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "prediction_id": self.prediction_id,
            "author_id": self.author_id,
            "platform": self.platform,
            "ticker": self.ticker,
            "direction": self.direction,
            "sentiment_score": round(self.sentiment_score, 3),
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "actual_return_pct": round(self.actual_return_pct, 2),
            "was_correct": self.was_correct,
            "sector": self.sector,
        }


@dataclass
class PerformanceStats:
    """Aggregated performance statistics for an influencer."""

    author_id: str = ""
    platform: str = ""
    total_predictions: int = 0
    correct_predictions: int = 0
    accuracy_rate: float = 0.0
    avg_return_pct: float = 0.0
    best_call_return_pct: float = 0.0
    worst_call_return_pct: float = 0.0
    bullish_accuracy: float = 0.0
    bearish_accuracy: float = 0.0
    sector_accuracy: dict[str, float] = field(default_factory=dict)
    top_tickers: list[str] = field(default_factory=list)
    streak_current: int = 0  # Positive = win streak, negative = loss streak
    streak_max: int = 0

    def to_dict(self) -> dict:
        return {
            "author_id": self.author_id,
            "platform": self.platform,
            "total_predictions": self.total_predictions,
            "correct_predictions": self.correct_predictions,
            "accuracy_rate": round(self.accuracy_rate, 3),
            "avg_return_pct": round(self.avg_return_pct, 2),
            "best_call_return_pct": round(self.best_call_return_pct, 2),
            "worst_call_return_pct": round(self.worst_call_return_pct, 2),
            "bullish_accuracy": round(self.bullish_accuracy, 3),
            "bearish_accuracy": round(self.bearish_accuracy, 3),
            "sector_accuracy": {
                k: round(v, 3) for k, v in self.sector_accuracy.items()
            },
            "top_tickers": self.top_tickers[:5],
            "streak_current": self.streak_current,
            "streak_max": self.streak_max,
        }


@dataclass
class InfluencerReport:
    """Full report across all tracked influencers."""

    stats: list[PerformanceStats] = field(default_factory=list)
    total_predictions: int = 0
    overall_accuracy: float = 0.0
    generated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "stats": [s.to_dict() for s in self.stats],
            "total_predictions": self.total_predictions,
            "overall_accuracy": round(self.overall_accuracy, 3),
            "generated_at": self.generated_at,
        }

    @property
    def influencer_count(self) -> int:
        return len(self.stats)

    def get_top_by_accuracy(self, n: int = 10) -> list[PerformanceStats]:
        """Top N influencers by accuracy rate."""
        qualified = [s for s in self.stats if s.total_predictions >= 5]
        return sorted(qualified, key=lambda s: s.accuracy_rate, reverse=True)[:n]

    def get_sector_specialists(self, sector: str) -> list[PerformanceStats]:
        """Influencers with best accuracy in a specific sector."""
        result = []
        for s in self.stats:
            if sector in s.sector_accuracy and s.sector_accuracy[sector] > 0:
                result.append(s)
        return sorted(result, key=lambda s: s.sector_accuracy.get(sector, 0), reverse=True)


class PerformanceLedger:
    """Track influencer prediction performance over time.

    Records predictions and outcomes, computes accuracy rates,
    sector specialization, and streak analysis.

    Example::

        ledger = PerformanceLedger()
        ledger.record_prediction(PredictionRecord(
            prediction_id="p1", author_id="trader123",
            platform="twitter", ticker="AAPL",
            direction="bullish", entry_price=180.0,
        ))
        ledger.evaluate("p1", exit_price=190.0)
        stats = ledger.get_stats("twitter", "trader123")
    """

    def __init__(self, config: Optional[LedgerConfig] = None):
        self.config = config or LedgerConfig()
        self._predictions: dict[str, PredictionRecord] = {}
        self._by_author: dict[str, list[str]] = {}  # key → prediction_ids

    def record_prediction(self, record: PredictionRecord) -> str:
        """Record a new prediction.

        Args:
            record: Prediction record with author, ticker, direction.

        Returns:
            Prediction ID.
        """
        if not record.prediction_id:
            record.prediction_id = f"pred_{len(self._predictions)}"

        if record.predicted_at is None:
            record.predicted_at = datetime.now(timezone.utc)

        self._predictions[record.prediction_id] = record

        key = f"{record.platform}:{record.author_id}"
        if key not in self._by_author:
            self._by_author[key] = []
        self._by_author[key].append(record.prediction_id)

        return record.prediction_id

    def evaluate(
        self,
        prediction_id: str,
        exit_price: float,
        sector: str = "",
    ) -> Optional[PredictionRecord]:
        """Evaluate a prediction outcome.

        Args:
            prediction_id: ID of the prediction to evaluate.
            exit_price: Price at evaluation time.
            sector: Optional sector classification.

        Returns:
            Updated PredictionRecord or None if not found.
        """
        record = self._predictions.get(prediction_id)
        if not record:
            return None

        record.exit_price = exit_price
        record.evaluated_at = datetime.now(timezone.utc)

        if sector:
            record.sector = sector

        # Compute return
        if record.entry_price > 0:
            record.actual_return_pct = (
                (exit_price - record.entry_price) / record.entry_price * 100
            )
        else:
            record.actual_return_pct = 0.0

        # Was the prediction correct?
        if record.direction == "bullish":
            record.was_correct = record.actual_return_pct > 0
        elif record.direction == "bearish":
            record.was_correct = record.actual_return_pct < 0
        else:
            record.was_correct = abs(record.actual_return_pct) < 1.0

        return record

    def get_stats(self, platform: str, author_id: str) -> PerformanceStats:
        """Get performance statistics for an influencer.

        Args:
            platform: Source platform.
            author_id: Author identifier.

        Returns:
            PerformanceStats with accuracy, sector breakdown, streaks.
        """
        key = f"{platform}:{author_id}"
        pred_ids = self._by_author.get(key, [])

        evaluated = [
            self._predictions[pid]
            for pid in pred_ids
            if pid in self._predictions and self._predictions[pid].evaluated_at
        ]

        if not evaluated:
            return PerformanceStats(author_id=author_id, platform=platform)

        total = len(evaluated)
        correct = sum(1 for r in evaluated if r.was_correct)
        returns = [r.actual_return_pct for r in evaluated]

        # Direction breakdown
        bullish = [r for r in evaluated if r.direction == "bullish"]
        bearish = [r for r in evaluated if r.direction == "bearish"]

        bullish_acc = (
            sum(1 for r in bullish if r.was_correct) / len(bullish)
            if bullish else 0.0
        )
        bearish_acc = (
            sum(1 for r in bearish if r.was_correct) / len(bearish)
            if bearish else 0.0
        )

        # Sector accuracy
        sector_groups: dict[str, list[PredictionRecord]] = {}
        for r in evaluated:
            if r.sector:
                if r.sector not in sector_groups:
                    sector_groups[r.sector] = []
                sector_groups[r.sector].append(r)

        sector_accuracy = {
            s: sum(1 for r in recs if r.was_correct) / len(recs)
            for s, recs in sector_groups.items()
            if recs
        }

        # Streak tracking
        streak = 0
        max_streak = 0
        for r in evaluated:
            if r.was_correct:
                streak = max(streak, 0) + 1
            else:
                streak = min(streak, 0) - 1
            if abs(streak) > abs(max_streak):
                max_streak = streak

        # Top tickers
        ticker_counts: dict[str, int] = {}
        for r in evaluated:
            ticker_counts[r.ticker] = ticker_counts.get(r.ticker, 0) + 1
        top_tickers = [t for t, _ in sorted(ticker_counts.items(), key=lambda x: -x[1])[:5]]

        return PerformanceStats(
            author_id=author_id,
            platform=platform,
            total_predictions=total,
            correct_predictions=correct,
            accuracy_rate=correct / total if total else 0.0,
            avg_return_pct=sum(returns) / len(returns) if returns else 0.0,
            best_call_return_pct=max(returns) if returns else 0.0,
            worst_call_return_pct=min(returns) if returns else 0.0,
            bullish_accuracy=bullish_acc,
            bearish_accuracy=bearish_acc,
            sector_accuracy=sector_accuracy,
            top_tickers=top_tickers,
            streak_current=streak,
            streak_max=max_streak,
        )

    def generate_report(self) -> InfluencerReport:
        """Generate a report across all tracked influencers."""
        all_stats = []

        for key in self._by_author:
            platform, author_id = key.split(":", 1)
            stats = self.get_stats(platform, author_id)
            if stats.total_predictions > 0:
                all_stats.append(stats)

        total_preds = sum(s.total_predictions for s in all_stats)
        total_correct = sum(s.correct_predictions for s in all_stats)

        return InfluencerReport(
            stats=sorted(all_stats, key=lambda s: s.accuracy_rate, reverse=True),
            total_predictions=total_preds,
            overall_accuracy=total_correct / total_preds if total_preds else 0.0,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    @property
    def prediction_count(self) -> int:
        return len(self._predictions)

    @property
    def author_count(self) -> int:
        return len(self._by_author)

    def get_prediction(self, prediction_id: str) -> Optional[PredictionRecord]:
        """Look up a prediction by ID."""
        return self._predictions.get(prediction_id)
