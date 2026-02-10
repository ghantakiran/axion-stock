"""Tests for PRD-52: Event-Driven Analytics."""

import pytest
import numpy as np
from datetime import date, timedelta

from src.events.config import (
    EventType,
    EarningsResult,
    DealStatus,
    SignalStrength,
    EarningsConfig,
    MergerConfig,
    CorporateConfig,
    SignalConfig,
    EventConfig,
    DEFAULT_EVENT_CONFIG,
)
from src.events.models import (
    EarningsEvent,
    EarningsSummary,
    MergerEvent,
    CorporateAction,
    DividendSummary,
    EventSignal,
    CompositeEventScore,
)
from src.events.earnings import EarningsAnalyzer
from src.events.mergers import MergerAnalyzer
from src.events.corporate import CorporateActionTracker
from src.events.signals import EventSignalGenerator


# ── Config Tests ────────────────────────────────────────────────────


class TestEventsConfig:
    """Test configuration."""

    def test_enums(self):
        assert len(EventType) == 6
        assert len(EarningsResult) == 3
        assert len(DealStatus) == 5
        assert len(SignalStrength) == 4

    def test_default_config(self):
        config = DEFAULT_EVENT_CONFIG
        assert config.earnings.beat_threshold == 0.02
        assert config.merger.min_probability == 0.5
        assert config.signal.earnings_weight == 0.40

    def test_earnings_config_defaults(self):
        c = EarningsConfig()
        assert c.drift_window == 20
        assert c.min_history == 4

    def test_signal_config_weights_sum(self):
        c = SignalConfig()
        total = c.earnings_weight + c.merger_weight + c.corporate_weight
        assert abs(total - 1.0) < 1e-10


# ── Model Tests ─────────────────────────────────────────────────────


class TestEventsModels:
    """Test data models."""

    def test_earnings_event_surprise(self):
        e = EarningsEvent(
            symbol="AAPL", report_date=date(2025, 7, 30),
            eps_estimate=1.50, eps_actual=1.65,
        )
        assert abs(e.eps_surprise - 0.10) < 1e-10

    def test_earnings_event_miss(self):
        e = EarningsEvent(
            symbol="AAPL", report_date=date(2025, 7, 30),
            eps_estimate=1.50, eps_actual=1.35,
            result=EarningsResult.MISS,
        )
        assert e.is_miss
        assert not e.is_beat
        assert e.eps_surprise < 0

    def test_earnings_event_revenue_surprise(self):
        e = EarningsEvent(
            symbol="AAPL", report_date=date(2025, 7, 30),
            revenue_estimate=100.0, revenue_actual=105.0,
        )
        assert abs(e.revenue_surprise - 0.05) < 1e-10

    def test_earnings_event_zero_estimate(self):
        e = EarningsEvent(
            symbol="X", report_date=date(2025, 1, 1),
            eps_estimate=0.0, eps_actual=0.5,
        )
        assert e.eps_surprise == 0.0

    def test_earnings_summary_beat_rate(self):
        s = EarningsSummary(symbol="AAPL", total_reports=10, beats=7)
        assert abs(s.beat_rate - 0.7) < 1e-10

    def test_earnings_summary_empty(self):
        s = EarningsSummary(symbol="X")
        assert s.beat_rate == 0.0
        assert s.miss_rate == 0.0

    def test_merger_event_spread(self):
        m = MergerEvent(
            acquirer="AVGO", target="VMW",
            announce_date=date(2025, 5, 1),
            offer_price=142.50, current_price=135.00,
        )
        expected_spread = (142.50 - 135.00) / 135.00
        assert abs(m.spread - expected_spread) < 1e-10

    def test_merger_event_active(self):
        m = MergerEvent(
            acquirer="A", target="B",
            announce_date=date(2025, 1, 1),
            status=DealStatus.PENDING,
        )
        assert m.is_active

    def test_merger_event_closed(self):
        m = MergerEvent(
            acquirer="A", target="B",
            announce_date=date(2025, 1, 1),
            status=DealStatus.CLOSED,
        )
        assert not m.is_active

    def test_merger_expected_return(self):
        m = MergerEvent(
            acquirer="A", target="B",
            announce_date=date(2025, 1, 1),
            offer_price=100.0, current_price=95.0,
            probability=0.8,
        )
        expected = 0.8 * m.spread
        assert abs(m.expected_return - expected) < 1e-10

    def test_corporate_action_upcoming(self):
        tomorrow = date.today() + timedelta(days=1)
        a = CorporateAction(
            symbol="AAPL", action_type=EventType.DIVIDEND,
            announce_date=date.today(), effective_date=tomorrow,
        )
        assert a.is_upcoming
        assert a.days_until == 1

    def test_corporate_action_past(self):
        yesterday = date.today() - timedelta(days=1)
        a = CorporateAction(
            symbol="AAPL", action_type=EventType.DIVIDEND,
            announce_date=date.today() - timedelta(days=5),
            effective_date=yesterday,
        )
        assert not a.is_upcoming

    def test_dividend_summary_grower(self):
        d = DividendSummary(symbol="JNJ", consecutive_increases=25)
        assert d.is_dividend_grower

    def test_dividend_summary_not_grower(self):
        d = DividendSummary(symbol="X", consecutive_increases=3)
        assert not d.is_dividend_grower

    def test_event_signal_actionable(self):
        s = EventSignal(
            symbol="AAPL", event_type=EventType.EARNINGS,
            strength=SignalStrength.STRONG,
        )
        assert s.is_actionable

    def test_event_signal_not_actionable(self):
        s = EventSignal(
            symbol="X", event_type=EventType.EARNINGS,
            strength=SignalStrength.WEAK,
        )
        assert not s.is_actionable

    def test_composite_consensus(self):
        signals = [
            EventSignal(symbol="X", event_type=EventType.EARNINGS, direction="bullish"),
            EventSignal(symbol="X", event_type=EventType.MERGER, direction="bullish"),
            EventSignal(symbol="X", event_type=EventType.DIVIDEND, direction="neutral"),
        ]
        c = CompositeEventScore(symbol="X", signals=signals)
        assert c.has_consensus  # 2/3 bullish > 0.6


# ── EarningsAnalyzer Tests ──────────────────────────────────────────


class TestEarningsAnalyzer:
    """Test earnings analyzer."""

    def test_classify_beat(self):
        analyzer = EarningsAnalyzer()
        event = EarningsEvent(
            symbol="AAPL", report_date=date(2025, 7, 30),
            eps_estimate=1.50, eps_actual=1.65,
        )
        result = analyzer.add_event(event)
        assert result.result == EarningsResult.BEAT

    def test_classify_miss(self):
        analyzer = EarningsAnalyzer()
        event = EarningsEvent(
            symbol="AAPL", report_date=date(2025, 7, 30),
            eps_estimate=1.50, eps_actual=1.35,
        )
        result = analyzer.add_event(event)
        assert result.result == EarningsResult.MISS

    def test_classify_meet(self):
        analyzer = EarningsAnalyzer()
        event = EarningsEvent(
            symbol="AAPL", report_date=date(2025, 7, 30),
            eps_estimate=1.50, eps_actual=1.51,
        )
        result = analyzer.add_event(event)
        assert result.result == EarningsResult.MEET

    def test_summarize(self):
        analyzer = EarningsAnalyzer()
        dates = [date(2025, m * 3, 1) for m in range(1, 5)]
        for i, d in enumerate(dates):
            analyzer.add_event(EarningsEvent(
                symbol="AAPL", report_date=d,
                eps_estimate=1.50, eps_actual=1.50 + (i + 1) * 0.05,
            ))

        summary = analyzer.summarize("AAPL")
        assert summary.total_reports == 4
        assert summary.beats == 4
        assert summary.beat_rate == 1.0
        assert summary.streak == 4

    def test_summarize_empty(self):
        analyzer = EarningsAnalyzer()
        summary = analyzer.summarize("UNKNOWN")
        assert summary.total_reports == 0

    def test_streak_misses(self):
        analyzer = EarningsAnalyzer()
        for i in range(3):
            analyzer.add_event(EarningsEvent(
                symbol="X", report_date=date(2025, i + 1, 1),
                eps_estimate=1.50, eps_actual=1.30,
            ))
        summary = analyzer.summarize("X")
        assert summary.streak == -3

    def test_estimate_drift_with_history(self):
        analyzer = EarningsAnalyzer()
        for i in range(5):
            surprise = 0.05 * (i + 1)
            drift = 0.02 * (i + 1)
            analyzer.add_event(EarningsEvent(
                symbol="AAPL", report_date=date(2025, i + 1, 1),
                eps_estimate=1.00, eps_actual=1.00 + surprise,
                post_drift=drift,
            ))

        drift = analyzer.estimate_drift("AAPL", 0.10)
        assert drift != 0

    def test_estimate_drift_fallback(self):
        analyzer = EarningsAnalyzer()
        drift = analyzer.estimate_drift("UNKNOWN", 0.10)
        assert abs(drift - 0.05) < 1e-10  # 0.10 * 0.5

    def test_get_events(self):
        analyzer = EarningsAnalyzer()
        for i in range(3):
            analyzer.add_event(EarningsEvent(
                symbol="AAPL", report_date=date(2025, i + 1, 1),
                eps_estimate=1.50, eps_actual=1.60,
            ))
        events = analyzer.get_events("AAPL", n=2)
        assert len(events) == 2
        assert events[0].report_date > events[1].report_date

    def test_reset(self):
        analyzer = EarningsAnalyzer()
        analyzer.add_event(EarningsEvent(
            symbol="X", report_date=date(2025, 1, 1),
            eps_estimate=1.0, eps_actual=1.1,
        ))
        analyzer.reset()
        assert analyzer.summarize("X").total_reports == 0


# ── MergerAnalyzer Tests ────────────────────────────────────────────


class TestMergerAnalyzer:
    """Test merger analyzer."""

    def test_annualized_spread(self):
        analyzer = MergerAnalyzer()
        deal = MergerEvent(
            acquirer="AVGO", target="VMW",
            announce_date=date(2025, 1, 1),
            offer_price=142.50, current_price=135.00,
            expected_close=date.today() + timedelta(days=180),
        )
        ann = analyzer.annualized_spread(deal)
        assert ann > deal.spread  # Annualized should be higher

    def test_annualized_spread_no_close_date(self):
        analyzer = MergerAnalyzer()
        deal = MergerEvent(
            acquirer="A", target="B",
            announce_date=date(2025, 1, 1),
            offer_price=100.0, current_price=95.0,
        )
        ann = analyzer.annualized_spread(deal)
        assert abs(ann - deal.spread) < 1e-10

    def test_estimate_probability_announced(self):
        analyzer = MergerAnalyzer()
        deal = MergerEvent(
            acquirer="A", target="B",
            announce_date=date(2025, 1, 1),
            status=DealStatus.ANNOUNCED,
            is_cash=True,
            offer_price=100.0, current_price=95.0,
        )
        prob = analyzer.estimate_probability(deal)
        assert 0.4 < prob < 0.8

    def test_estimate_probability_approved(self):
        analyzer = MergerAnalyzer()
        deal = MergerEvent(
            acquirer="A", target="B",
            announce_date=date(2025, 1, 1),
            status=DealStatus.APPROVED, is_cash=True,
            offer_price=100.0, current_price=99.0,
        )
        prob = analyzer.estimate_probability(deal)
        assert prob > 0.7

    def test_estimate_probability_terminated(self):
        analyzer = MergerAnalyzer()
        deal = MergerEvent(
            acquirer="A", target="B",
            announce_date=date(2025, 1, 1),
            status=DealStatus.TERMINATED,
        )
        prob = analyzer.estimate_probability(deal)
        assert prob == 0.0

    def test_risk_arb_signal_active(self):
        analyzer = MergerAnalyzer()
        deal = MergerEvent(
            acquirer="AVGO", target="VMW",
            announce_date=date(2025, 1, 1),
            offer_price=142.50, current_price=135.00,
            status=DealStatus.APPROVED, is_cash=True,
            expected_close=date.today() + timedelta(days=60),
        )
        result = analyzer.risk_arb_signal(deal)
        assert result["target"] == "VMW"
        assert result["spread"] > 0
        assert result["signal"] in ("strong_buy", "buy", "neutral", "avoid")

    def test_risk_arb_signal_terminated(self):
        analyzer = MergerAnalyzer()
        deal = MergerEvent(
            acquirer="A", target="B",
            announce_date=date(2025, 1, 1),
            status=DealStatus.TERMINATED,
        )
        result = analyzer.risk_arb_signal(deal)
        assert result["signal"] == "none"

    def test_get_active_deals(self):
        analyzer = MergerAnalyzer()
        analyzer.add_deal(MergerEvent(
            acquirer="A", target="B",
            announce_date=date(2025, 1, 1),
            status=DealStatus.PENDING,
        ))
        analyzer.add_deal(MergerEvent(
            acquirer="C", target="D",
            announce_date=date(2025, 2, 1),
            status=DealStatus.CLOSED,
        ))
        active = analyzer.get_active_deals()
        assert len(active) == 1
        assert active[0].target == "B"

    def test_reset(self):
        analyzer = MergerAnalyzer()
        analyzer.add_deal(MergerEvent(
            acquirer="A", target="B",
            announce_date=date(2025, 1, 1),
        ))
        analyzer.reset()
        assert analyzer.get_active_deals() == []


# ── CorporateActionTracker Tests ────────────────────────────────────


class TestCorporateActionTracker:
    """Test corporate action tracker."""

    def test_get_upcoming(self):
        tracker = CorporateActionTracker()
        tomorrow = date.today() + timedelta(days=1)
        next_week = date.today() + timedelta(days=7)

        tracker.add_action(CorporateAction(
            symbol="AAPL", action_type=EventType.DIVIDEND,
            announce_date=date.today(), effective_date=tomorrow,
        ))
        tracker.add_action(CorporateAction(
            symbol="MSFT", action_type=EventType.SPLIT,
            announce_date=date.today(), effective_date=next_week,
        ))
        # Past action — should not appear
        tracker.add_action(CorporateAction(
            symbol="GOOGL", action_type=EventType.DIVIDEND,
            announce_date=date.today() - timedelta(days=30),
            effective_date=date.today() - timedelta(days=1),
        ))

        upcoming = tracker.get_upcoming()
        assert len(upcoming) == 2
        assert upcoming[0].effective_date <= upcoming[1].effective_date

    def test_analyze_dividends(self):
        tracker = CorporateActionTracker()
        for i in range(8):
            tracker.add_action(CorporateAction(
                symbol="JNJ", action_type=EventType.DIVIDEND,
                announce_date=date(2024, i + 1, 1),
                effective_date=date(2024, i + 1, 15),
                amount=1.00 + i * 0.05,
            ))

        result = tracker.analyze_dividends("JNJ", current_price=150.0)
        assert result.annual_dividend > 0
        assert result.current_yield > 0
        assert result.growth_rate > 0
        assert result.consecutive_increases > 0

    def test_analyze_dividends_empty(self):
        tracker = CorporateActionTracker()
        result = tracker.analyze_dividends("UNKNOWN")
        assert result.annual_dividend == 0.0

    def test_analyze_buybacks(self):
        tracker = CorporateActionTracker()
        tracker.add_action(CorporateAction(
            symbol="AAPL", action_type=EventType.BUYBACK,
            announce_date=date(2025, 1, 1), amount=90_000_000_000,
        ))
        result = tracker.analyze_buybacks("AAPL", market_cap=3_000_000_000_000)
        assert result["total_amount"] == 90_000_000_000
        assert result["count"] == 1
        assert result["pct_of_market_cap"] == 0.03
        assert result["is_significant"]

    def test_analyze_buybacks_not_significant(self):
        tracker = CorporateActionTracker()
        tracker.add_action(CorporateAction(
            symbol="X", action_type=EventType.BUYBACK,
            announce_date=date(2025, 1, 1), amount=10_000,
        ))
        result = tracker.analyze_buybacks("X", market_cap=1_000_000_000)
        assert not result["is_significant"]

    def test_analyze_buybacks_empty(self):
        tracker = CorporateActionTracker()
        result = tracker.analyze_buybacks("UNKNOWN")
        assert result["count"] == 0

    def test_get_actions_filtered(self):
        tracker = CorporateActionTracker()
        tracker.add_action(CorporateAction(
            symbol="X", action_type=EventType.DIVIDEND,
            announce_date=date(2025, 1, 1),
        ))
        tracker.add_action(CorporateAction(
            symbol="X", action_type=EventType.BUYBACK,
            announce_date=date(2025, 2, 1),
        ))

        divs = tracker.get_actions("X", EventType.DIVIDEND)
        assert len(divs) == 1
        all_actions = tracker.get_actions("X")
        assert len(all_actions) == 2

    def test_reset(self):
        tracker = CorporateActionTracker()
        tracker.add_action(CorporateAction(
            symbol="X", action_type=EventType.DIVIDEND,
            announce_date=date(2025, 1, 1),
        ))
        tracker.reset()
        assert tracker.get_actions("X") == []


# ── EventSignalGenerator Tests ──────────────────────────────────────


class TestEventSignalGenerator:
    """Test event signal generator."""

    def test_earnings_signal_beat(self):
        gen = EventSignalGenerator()
        event = EarningsEvent(
            symbol="AAPL", report_date=date(2025, 7, 30),
            eps_estimate=1.50, eps_actual=1.80,
            result=EarningsResult.BEAT, post_drift=0.03,
        )
        sig = gen.earnings_signal(event)
        assert sig.direction == "bullish"
        assert sig.score > 0
        assert sig.event_type == EventType.EARNINGS

    def test_earnings_signal_miss(self):
        gen = EventSignalGenerator()
        event = EarningsEvent(
            symbol="X", report_date=date(2025, 1, 1),
            eps_estimate=1.50, eps_actual=1.20,
            result=EarningsResult.MISS,
        )
        sig = gen.earnings_signal(event)
        assert sig.direction == "bearish"
        assert sig.score < 0

    def test_earnings_signal_with_history(self):
        gen = EventSignalGenerator()
        event = EarningsEvent(
            symbol="AAPL", report_date=date(2025, 7, 30),
            eps_estimate=1.50, eps_actual=1.65,
            result=EarningsResult.BEAT,
        )
        summary = EarningsSummary(
            symbol="AAPL", total_reports=8, beats=7,
            misses=1, streak=4,
        )
        sig = gen.earnings_signal(event, summary)
        assert sig.direction == "bullish"

    def test_merger_signal_strong_buy(self):
        gen = EventSignalGenerator()
        arb = {
            "target": "VMW", "acquirer": "AVGO",
            "spread": 0.08, "annualized_spread": 0.15,
            "probability": 0.90, "expected_return": 0.07,
            "signal": "strong_buy",
        }
        sig = gen.merger_signal(arb)
        assert sig.direction == "bullish"
        assert sig.strength == SignalStrength.STRONG

    def test_merger_signal_avoid(self):
        gen = EventSignalGenerator()
        arb = {
            "target": "X", "signal": "avoid",
            "probability": 0.3,
        }
        sig = gen.merger_signal(arb)
        assert sig.direction == "bearish"

    def test_corporate_signal_dividend(self):
        gen = EventSignalGenerator()
        action = CorporateAction(
            symbol="JNJ", action_type=EventType.DIVIDEND,
            announce_date=date(2025, 1, 1), amount=1.20,
        )
        sig = gen.corporate_signal(action)
        assert sig.direction == "bullish"
        assert sig.score > 0

    def test_corporate_signal_buyback(self):
        gen = EventSignalGenerator()
        action = CorporateAction(
            symbol="AAPL", action_type=EventType.BUYBACK,
            announce_date=date(2025, 1, 1), amount=90e9,
        )
        sig = gen.corporate_signal(action)
        assert sig.direction == "bullish"
        assert sig.score > 0

    def test_corporate_signal_split(self):
        gen = EventSignalGenerator()
        action = CorporateAction(
            symbol="NVDA", action_type=EventType.SPLIT,
            announce_date=date(2025, 1, 1),
        )
        sig = gen.corporate_signal(action)
        assert sig.direction == "bullish"

    def test_composite_signal(self):
        gen = EventSignalGenerator()
        signals = [
            EventSignal(
                symbol="AAPL", event_type=EventType.EARNINGS,
                strength=SignalStrength.STRONG, direction="bullish",
                score=0.8, confidence=0.7,
            ),
            EventSignal(
                symbol="AAPL", event_type=EventType.BUYBACK,
                strength=SignalStrength.MODERATE, direction="bullish",
                score=0.4, confidence=0.5,
            ),
        ]
        result = gen.composite("AAPL", signals)
        assert result.composite > 0
        assert result.n_signals == 2
        assert result.direction == "bullish"
        assert result.earnings_score > 0

    def test_composite_empty(self):
        gen = EventSignalGenerator()
        result = gen.composite("X", [])
        assert result.composite == 0.0
        assert result.n_signals == 0


# ── Integration Tests ───────────────────────────────────────────────


class TestEventsIntegration:
    """Integration tests."""

    def test_full_workflow(self):
        """End-to-end: earnings → signal → composite."""
        ea = EarningsAnalyzer()
        sg = EventSignalGenerator()

        # Add earnings history
        for i in range(5):
            ea.add_event(EarningsEvent(
                symbol="AAPL", report_date=date(2025, i + 1, 1),
                eps_estimate=1.50, eps_actual=1.60 + i * 0.02,
                post_drift=0.01 + i * 0.005,
            ))

        summary = ea.summarize("AAPL")
        latest = ea.get_events("AAPL", n=1)[0]

        # Generate earnings signal
        earnings_sig = sg.earnings_signal(latest, summary)
        assert earnings_sig.direction == "bullish"

        # Add corporate action
        corp_sig = sg.corporate_signal(CorporateAction(
            symbol="AAPL", action_type=EventType.BUYBACK,
            announce_date=date(2025, 6, 1), amount=90e9,
        ))

        # Composite
        comp = sg.composite("AAPL", [earnings_sig, corp_sig])
        assert comp.n_signals == 2
        assert comp.composite > 0

    def test_module_imports(self):
        """Verify all exports are accessible."""
        from src.events import (
            EventType, EarningsResult, DealStatus, SignalStrength,
            EarningsConfig, MergerConfig, CorporateConfig, SignalConfig,
            EventConfig, DEFAULT_EVENT_CONFIG,
            EarningsEvent, EarningsSummary, MergerEvent,
            CorporateAction, DividendSummary, EventSignal,
            CompositeEventScore,
            EarningsAnalyzer, MergerAnalyzer,
            CorporateActionTracker, EventSignalGenerator,
        )
