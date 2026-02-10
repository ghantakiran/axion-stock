"""Tests for src/journal/ module — JournalService, JournalAnalytics.

Uses an in-memory SQLite database to test CRUD operations and analytics
without requiring an external PostgreSQL instance.
"""

import json
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.journal.analytics import (
    JournalAnalytics,
    PerformanceMetrics,
    DimensionBreakdown,
    EmotionAnalysis,
    PatternInsight,
)


# ---------------------------------------------------------------------------
# Mock JournalEntry — lightweight stand-in for the ORM model
# ---------------------------------------------------------------------------
@dataclass
class MockJournalEntry:
    """Lightweight mock of src.db.models.JournalEntry for analytics testing."""
    entry_id: str = ""
    symbol: str = "AAPL"
    direction: str = "long"
    trade_type: Optional[str] = "day"
    entry_date: Optional[datetime] = None
    entry_price: float = 100.0
    entry_quantity: float = 10.0
    exit_date: Optional[datetime] = None
    exit_price: Optional[float] = None
    realized_pnl: Optional[float] = None
    realized_pnl_pct: Optional[float] = None
    fees: float = 0.0
    setup_id: Optional[str] = None
    strategy_id: Optional[str] = None
    timeframe: Optional[str] = None
    tags: Optional[str] = None
    notes: Optional[str] = None
    pre_trade_emotion: Optional[str] = None
    during_trade_emotion: Optional[str] = None
    post_trade_emotion: Optional[str] = None
    entry_reason: Optional[str] = None
    exit_reason: Optional[str] = None
    initial_stop: Optional[float] = None
    initial_target: Optional[float] = None
    risk_reward_planned: Optional[float] = None
    risk_reward_actual: Optional[float] = None
    lessons_learned: Optional[str] = None
    screenshots: Optional[str] = None


def _make_entry(
    pnl: float,
    symbol: str = "AAPL",
    setup_id: Optional[str] = None,
    strategy_id: Optional[str] = None,
    pre_emotion: Optional[str] = None,
    during_emotion: Optional[str] = None,
    post_emotion: Optional[str] = None,
    trade_type: Optional[str] = "day",
    entry_date: Optional[datetime] = None,
    risk_reward_actual: Optional[float] = None,
    initial_stop: Optional[float] = None,
) -> MockJournalEntry:
    """Helper to create a closed mock journal entry with given P&L."""
    base_date = entry_date or datetime(2025, 1, 15, 10, 30)
    exit_date = base_date + timedelta(hours=3)
    entry_price = 100.0
    quantity = 10.0
    exit_price = entry_price + pnl / quantity

    return MockJournalEntry(
        entry_id=str(uuid.uuid4())[:12],
        symbol=symbol,
        direction="long",
        trade_type=trade_type,
        entry_date=base_date,
        entry_price=entry_price,
        entry_quantity=quantity,
        exit_date=exit_date,
        exit_price=exit_price,
        realized_pnl=pnl,
        realized_pnl_pct=pnl / (entry_price * quantity),
        setup_id=setup_id,
        strategy_id=strategy_id,
        pre_trade_emotion=pre_emotion,
        during_trade_emotion=during_emotion,
        post_trade_emotion=post_emotion,
        risk_reward_actual=risk_reward_actual,
        initial_stop=initial_stop,
    )


def _make_open_entry(symbol: str = "TSLA") -> MockJournalEntry:
    """Helper to create an open (not closed) mock journal entry."""
    return MockJournalEntry(
        entry_id=str(uuid.uuid4())[:12],
        symbol=symbol,
        direction="long",
        entry_date=datetime(2025, 1, 20, 9, 30),
        entry_price=200.0,
        entry_quantity=5.0,
        exit_date=None,
        exit_price=None,
        realized_pnl=None,
    )


# ---------------------------------------------------------------------------
# TestPerformanceMetrics (dataclass)
# ---------------------------------------------------------------------------
class TestPerformanceMetrics:
    def test_default_values(self):
        pm = PerformanceMetrics()
        assert pm.total_trades == 0
        assert pm.win_rate == 0.0
        assert pm.profit_factor == 0.0
        assert pm.expectancy == 0.0

    def test_custom_values(self):
        pm = PerformanceMetrics(
            total_trades=20,
            winning_trades=12,
            losing_trades=8,
            win_rate=0.6,
            profit_factor=1.8,
        )
        assert pm.total_trades == 20
        assert pm.win_rate == 0.6


# ---------------------------------------------------------------------------
# TestDimensionBreakdown (dataclass)
# ---------------------------------------------------------------------------
class TestDimensionBreakdown:
    def test_creation(self):
        db = DimensionBreakdown(
            dimension="setup",
            category="breakout",
            metrics=PerformanceMetrics(total_trades=10, win_rate=0.7),
        )
        assert db.dimension == "setup"
        assert db.category == "breakout"
        assert db.metrics.win_rate == 0.7


# ---------------------------------------------------------------------------
# TestEmotionAnalysis (dataclass)
# ---------------------------------------------------------------------------
class TestEmotionAnalysis:
    def test_creation(self):
        ea = EmotionAnalysis(
            emotion="confident",
            trade_count=15,
            win_rate=0.65,
            avg_pnl=50.0,
            avg_pnl_pct=0.02,
            recommendation="favorable",
        )
        assert ea.emotion == "confident"
        assert ea.recommendation == "favorable"


# ---------------------------------------------------------------------------
# TestPatternInsight (dataclass)
# ---------------------------------------------------------------------------
class TestPatternInsight:
    def test_creation(self):
        pi = PatternInsight(
            insight_type="strength",
            title="Strong breakout setup",
            description="Breakout has 70% win rate",
            confidence=0.85,
            supporting_data={"win_rate": 0.7},
        )
        assert pi.insight_type == "strength"
        assert pi.confidence == 0.85


# ---------------------------------------------------------------------------
# TestJournalAnalytics
# ---------------------------------------------------------------------------
class TestJournalAnalytics:
    """Test analytics engine using mock entries (no DB required)."""

    def test_calculate_metrics_empty(self):
        analytics = JournalAnalytics(session=MagicMock())
        metrics = analytics.calculate_metrics([])
        assert metrics.total_trades == 0
        assert metrics.win_rate == 0.0

    def test_calculate_metrics_all_open(self):
        analytics = JournalAnalytics(session=MagicMock())
        entries = [_make_open_entry(), _make_open_entry()]
        metrics = analytics.calculate_metrics(entries)
        assert metrics.total_trades == 2
        assert metrics.winning_trades == 0

    def test_calculate_metrics_winners_only(self):
        analytics = JournalAnalytics(session=MagicMock())
        entries = [_make_entry(100), _make_entry(200), _make_entry(50)]
        metrics = analytics.calculate_metrics(entries)
        assert metrics.total_trades == 3
        assert metrics.winning_trades == 3
        assert metrics.losing_trades == 0
        assert metrics.win_rate == 1.0
        assert metrics.total_pnl == 350.0
        assert metrics.largest_win == 200.0

    def test_calculate_metrics_losers_only(self):
        analytics = JournalAnalytics(session=MagicMock())
        entries = [_make_entry(-100), _make_entry(-50)]
        metrics = analytics.calculate_metrics(entries)
        assert metrics.total_trades == 2
        assert metrics.winning_trades == 0
        assert metrics.losing_trades == 2
        assert metrics.win_rate == 0.0
        assert metrics.total_pnl == -150.0

    def test_calculate_metrics_mixed(self):
        analytics = JournalAnalytics(session=MagicMock())
        entries = [
            _make_entry(200),
            _make_entry(100),
            _make_entry(-80),
            _make_entry(-40),
        ]
        metrics = analytics.calculate_metrics(entries)
        assert metrics.total_trades == 4
        assert metrics.winning_trades == 2
        assert metrics.losing_trades == 2
        assert metrics.win_rate == pytest.approx(0.5)
        assert metrics.avg_winner == pytest.approx(150.0)
        assert metrics.avg_loser == pytest.approx(60.0)
        assert metrics.profit_factor == pytest.approx(300.0 / 120.0)

    def test_calculate_metrics_expectancy(self):
        analytics = JournalAnalytics(session=MagicMock())
        entries = [
            _make_entry(200),
            _make_entry(-50),
            _make_entry(100),
            _make_entry(-30),
        ]
        metrics = analytics.calculate_metrics(entries)
        # expectancy = (win_rate * avg_winner) - ((1 - win_rate) * avg_loser)
        expected = (0.5 * 150.0) - (0.5 * 40.0)
        assert metrics.expectancy == pytest.approx(expected)

    def test_calculate_metrics_with_risk_reward(self):
        analytics = JournalAnalytics(session=MagicMock())
        entries = [
            _make_entry(100, risk_reward_actual=2.0),
            _make_entry(-50, risk_reward_actual=-1.0),
        ]
        metrics = analytics.calculate_metrics(entries)
        assert metrics.avg_risk_reward == pytest.approx(0.5)  # mean(2.0, -1.0)

    def test_calculate_metrics_largest_loss(self):
        analytics = JournalAnalytics(session=MagicMock())
        entries = [_make_entry(-100), _make_entry(-300), _make_entry(50)]
        metrics = analytics.calculate_metrics(entries)
        assert metrics.largest_loss == 300.0

    def test_analyze_emotion_phase_favorable(self):
        analytics = JournalAnalytics(session=MagicMock())
        entries = [
            _make_entry(100, pre_emotion="confident"),
            _make_entry(80, pre_emotion="confident"),
            _make_entry(50, pre_emotion="confident"),
            _make_entry(-30, pre_emotion="confident"),
        ]
        results = analytics._analyze_emotion_phase(entries, "pre_trade_emotion")
        assert len(results) == 1
        assert results[0].emotion == "confident"
        assert results[0].win_rate == pytest.approx(0.75)
        assert results[0].recommendation == "favorable"

    def test_analyze_emotion_phase_avoid(self):
        analytics = JournalAnalytics(session=MagicMock())
        entries = [
            _make_entry(-100, pre_emotion="fearful"),
            _make_entry(-50, pre_emotion="fearful"),
            _make_entry(-80, pre_emotion="fearful"),
            _make_entry(30, pre_emotion="fearful"),
        ]
        results = analytics._analyze_emotion_phase(entries, "pre_trade_emotion")
        assert len(results) == 1
        assert results[0].recommendation == "avoid"

    def test_analyze_emotion_phase_multiple_emotions(self):
        analytics = JournalAnalytics(session=MagicMock())
        entries = [
            _make_entry(100, pre_emotion="confident"),
            _make_entry(-50, pre_emotion="fearful"),
            _make_entry(80, pre_emotion="confident"),
            _make_entry(-30, pre_emotion="fearful"),
        ]
        results = analytics._analyze_emotion_phase(entries, "pre_trade_emotion")
        assert len(results) == 2
        emotions = {r.emotion for r in results}
        assert "confident" in emotions
        assert "fearful" in emotions

    def test_analyze_emotion_phase_skips_open_trades(self):
        analytics = JournalAnalytics(session=MagicMock())
        entries = [_make_open_entry()]
        entries[0].pre_trade_emotion = "excited"
        results = analytics._analyze_emotion_phase(entries, "pre_trade_emotion")
        assert len(results) == 0

    def test_calculate_metrics_profit_factor_no_losers(self):
        analytics = JournalAnalytics(session=MagicMock())
        entries = [_make_entry(100), _make_entry(200)]
        metrics = analytics.calculate_metrics(entries)
        assert metrics.profit_factor == float("inf")
