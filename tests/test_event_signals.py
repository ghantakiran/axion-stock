"""Tests for PRD-60: Event-Driven Signals."""

import numpy as np
import pytest
from datetime import date, timedelta

from src.events.models import EarningsEvent, EarningsSummary, MergerEvent
from src.events.config import DealStatus

from src.events.scoring import (
    EarningsQualityScore,
    GuidanceRevision,
    EarningsScorecardSummary,
    EarningsScorer,
)
from src.events.probability import (
    DealRiskFactors,
    CompletionEstimate,
    HistoricalRates,
    DealProbabilityModeler,
)
from src.events.impact import (
    DividendImpact,
    SplitImpact,
    BuybackImpact,
    SpinoffImpact,
    ImpactSummary,
    CorporateActionImpactEstimator,
)
from src.events.calendar import (
    CalendarEvent,
    EventDensity,
    EventCluster,
    CatalystTimeline,
    CrossEventInteraction,
    EventCalendarAnalyzer,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _beat_event(symbol="AAPL", surprise=0.05):
    return EarningsEvent(
        symbol=symbol, report_date=date(2025, 7, 31),
        fiscal_quarter="Q1 2025",
        eps_estimate=1.00, eps_actual=1.00 * (1 + surprise),
        revenue_estimate=10_000, revenue_actual=10_200,
    )


def _miss_event(symbol="AAPL", surprise=-0.05):
    return EarningsEvent(
        symbol=symbol, report_date=date(2025, 7, 31),
        fiscal_quarter="Q2 2025",
        eps_estimate=1.00, eps_actual=1.00 * (1 + surprise),
        revenue_estimate=10_000, revenue_actual=9_800,
    )


def _summary(beats=6, total=8, streak=3):
    return EarningsSummary(
        symbol="AAPL", total_reports=total, beats=beats,
        meets=total - beats, avg_eps_surprise=0.03, streak=streak,
    )


def _merger(status=DealStatus.PENDING, is_cash=True, spread=0.08):
    return MergerEvent(
        acquirer="MSFT", target="ATVI",
        announce_date=date(2025, 1, 15),
        deal_value=69_000_000_000, offer_price=95.0,
        premium=0.45, probability=0.75, status=status,
        current_price=95.0 * (1 - spread), is_cash=is_cash,
    )


def _calendar_events():
    ref = date(2025, 6, 1)
    return [
        CalendarEvent("AAPL", "earnings", ref + timedelta(days=2), "Q2 Earnings", "positive", 0.8),
        CalendarEvent("AAPL", "dividend", ref + timedelta(days=3), "Ex-date", "neutral", 0.4),
        CalendarEvent("MSFT", "earnings", ref + timedelta(days=2), "Q2 Earnings", "positive", 0.7),
        CalendarEvent("GOOGL", "split", ref + timedelta(days=15), "20:1 Split", "positive", 0.6),
        CalendarEvent("AAPL", "buyback", ref + timedelta(days=40), "$10B Buyback", "positive", 0.5),
        CalendarEvent("TSLA", "earnings", ref + timedelta(days=60), "Q3 Earnings", "neutral", 0.7),
    ]


# ---------------------------------------------------------------------------
# Earnings Quality Score
# ---------------------------------------------------------------------------
class TestEarningsQualityScore:
    def test_grade(self):
        assert EarningsQualityScore(overall_score=0.8).grade == "A"
        assert EarningsQualityScore(overall_score=0.5).grade == "B"
        assert EarningsQualityScore(overall_score=0.2).grade == "C"
        assert EarningsQualityScore(overall_score=0.0).grade == "D"
        assert EarningsQualityScore(overall_score=-0.5).grade == "F"

    def test_quality_flags(self):
        assert EarningsQualityScore(overall_score=0.7).is_high_quality is True
        assert EarningsQualityScore(overall_score=-0.5).is_low_quality is True
        assert EarningsQualityScore(overall_score=0.3).is_high_quality is False


class TestGuidanceRevision:
    def test_revision_pct(self):
        g = GuidanceRevision(prior_low=1.0, prior_high=1.2, new_low=1.1, new_high=1.3)
        assert g.revision_pct == pytest.approx(0.0909, abs=0.01)

    def test_is_raise(self):
        g = GuidanceRevision(prior_low=1.0, prior_high=1.0, new_low=1.1, new_high=1.1)
        assert g.is_raise is True

    def test_is_cut(self):
        g = GuidanceRevision(prior_low=1.0, prior_high=1.0, new_low=0.8, new_high=0.8)
        assert g.is_cut is True

    def test_range_narrowed(self):
        g = GuidanceRevision(prior_low=1.0, prior_high=1.4, new_low=1.1, new_high=1.3)
        assert g.range_narrowed is True


# ---------------------------------------------------------------------------
# EarningsScorer
# ---------------------------------------------------------------------------
class TestEarningsScorer:
    def test_score_beat_event(self):
        scorer = EarningsScorer()
        event = _beat_event(surprise=0.10)
        score = scorer.score_event(event)
        assert score.overall_score > 0
        assert score.surprise_score > 0
        assert score.symbol == "AAPL"

    def test_score_miss_event(self):
        scorer = EarningsScorer()
        event = _miss_event(surprise=-0.10)
        score = scorer.score_event(event)
        assert score.overall_score < 0
        assert score.surprise_score < 0

    def test_score_with_summary(self):
        scorer = EarningsScorer()
        event = _beat_event()
        summary = _summary(beats=7, total=8, streak=5)
        score = scorer.score_event(event, summary=summary)
        assert score.consistency_score > 0
        assert score.beat_rate > 0

    def test_score_with_guidance(self):
        scorer = EarningsScorer()
        event = _beat_event()
        guidance = GuidanceRevision(
            prior_low=1.0, prior_high=1.1, new_low=1.15, new_high=1.25
        )
        score = scorer.score_event(event, guidance=guidance)
        assert score.guidance_score > 0

    def test_double_beat(self):
        scorer = EarningsScorer()
        event = EarningsEvent(
            symbol="X", report_date=date(2025, 4, 15),
            fiscal_quarter="Q1",
            eps_estimate=1.0, eps_actual=1.10,
            revenue_estimate=100, revenue_actual=105,
        )
        score = scorer.score_event(event)
        assert score.beat_breadth_score > 0

    def test_scorecard(self):
        scorer = EarningsScorer()
        scores = [
            EarningsQualityScore(symbol="AAPL", quarter=f"Q{i}", overall_score=0.3 + i * 0.1)
            for i in range(4)
        ]
        card = scorer.scorecard(scores)
        assert card.n_quarters == 4
        assert card.avg_quality_score > 0
        assert card.is_improving is True

    def test_scorecard_empty(self):
        scorer = EarningsScorer()
        card = scorer.scorecard([])
        assert card.n_quarters == 0


# ---------------------------------------------------------------------------
# Deal Risk Factors
# ---------------------------------------------------------------------------
class TestDealRiskFactors:
    def test_total_risk(self):
        rf = DealRiskFactors(
            regulatory_risk=0.5, financing_risk=0.3,
            antitrust_risk=0.4, shareholder_risk=0.1, market_risk=0.1
        )
        assert 0 < rf.total_risk < 1

    def test_risk_level(self):
        assert DealRiskFactors(
            regulatory_risk=0.9, financing_risk=0.8,
            antitrust_risk=0.9, shareholder_risk=0.7, market_risk=0.6,
        ).risk_level == "high"
        assert DealRiskFactors().risk_level == "low"


class TestCompletionEstimate:
    def test_is_likely(self):
        assert CompletionEstimate(adjusted_probability=0.85).is_likely is True
        assert CompletionEstimate(adjusted_probability=0.50).is_likely is False


# ---------------------------------------------------------------------------
# DealProbabilityModeler
# ---------------------------------------------------------------------------
class TestDealProbabilityModeler:
    def test_basic_estimate(self):
        modeler = DealProbabilityModeler()
        deal = _merger(status=DealStatus.PENDING)
        est = modeler.estimate_probability(deal)
        assert 0 < est.adjusted_probability <= 1
        assert est.target == "ATVI"
        assert est.confidence > 0

    def test_approved_deal(self):
        modeler = DealProbabilityModeler()
        deal = _merger(status=DealStatus.APPROVED)
        est = modeler.estimate_probability(deal)
        assert est.adjusted_probability > 0.85

    def test_hostile_reduces_probability(self):
        modeler = DealProbabilityModeler()
        deal = _merger()
        friendly = modeler.estimate_probability(deal, is_hostile=False)
        hostile = modeler.estimate_probability(deal, is_hostile=True)
        assert hostile.adjusted_probability < friendly.adjusted_probability

    def test_cross_border_risk(self):
        modeler = DealProbabilityModeler()
        deal = _merger()
        domestic = modeler.estimate_probability(deal, is_cross_border=False)
        cross = modeler.estimate_probability(deal, is_cross_border=True)
        assert cross.risk_factors.regulatory_risk > domestic.risk_factors.regulatory_risk

    def test_no_financing(self):
        modeler = DealProbabilityModeler()
        deal = _merger()
        financed = modeler.estimate_probability(deal, has_financing=True)
        no_fin = modeler.estimate_probability(deal, has_financing=False)
        assert no_fin.risk_factors.financing_risk > financed.risk_factors.financing_risk

    def test_compare_deals(self):
        modeler = DealProbabilityModeler()
        deals = [
            modeler.estimate_probability(_merger(status=DealStatus.APPROVED)),
            modeler.estimate_probability(_merger(status=DealStatus.ANNOUNCED)),
        ]
        ranked = modeler.compare_deals(deals)
        assert len(ranked) == 2


# ---------------------------------------------------------------------------
# Corporate Action Impact
# ---------------------------------------------------------------------------
class TestDividendImpact:
    def test_yield_bps(self):
        d = DividendImpact(annualized_yield=0.035)
        assert d.yield_bps == pytest.approx(350)

    def test_is_high_yield(self):
        assert DividendImpact(annualized_yield=0.05).is_high_yield is True
        assert DividendImpact(annualized_yield=0.02).is_high_yield is False


class TestBuybackImpact:
    def test_is_significant(self):
        assert BuybackImpact(buyback_pct=0.03).is_significant is True
        assert BuybackImpact(buyback_pct=0.01).is_significant is False


class TestSpinoffImpact:
    def test_has_value_creation(self):
        assert SpinoffImpact(value_creation_pct=0.15).has_value_creation is True
        assert SpinoffImpact(value_creation_pct=-0.05).has_value_creation is False


class TestCorporateActionImpactEstimator:
    def test_dividend_impact(self):
        est = CorporateActionImpactEstimator()
        impact = est.estimate_dividend_impact("AAPL", 0.96, 180.0)
        assert impact.ex_date_adjustment_pct < 0
        assert impact.annualized_yield > 0
        assert impact.yield_signal in ("attractive", "neutral", "low")

    def test_dividend_zero_price(self):
        est = CorporateActionImpactEstimator()
        impact = est.estimate_dividend_impact("X", 1.0, 0.0)
        assert impact.annualized_yield == 0.0

    def test_split_impact(self):
        est = CorporateActionImpactEstimator()
        impact = est.estimate_split_impact("AAPL", 4.0, 600.0)
        assert impact.post_split_price == 150.0
        assert impact.liquidity_effect_pct > 0
        assert impact.total_expected_impact_pct > 0

    def test_split_invalid_ratio(self):
        est = CorporateActionImpactEstimator()
        impact = est.estimate_split_impact("X", 1.0, 100.0)
        assert impact.liquidity_effect_pct == 0.0

    def test_buyback_impact(self):
        est = CorporateActionImpactEstimator()
        impact = est.estimate_buyback_impact(
            "AAPL", buyback_amount=10_000_000_000,
            market_cap=3_000_000_000_000,
            shares_outstanding=15_000_000_000,
            current_eps=6.50, current_price=200.0,
            net_income=97_500_000_000,
        )
        assert impact.buyback_pct > 0
        assert impact.eps_accretion_pct > 0
        assert impact.new_eps > impact.current_eps

    def test_buyback_zero_mcap(self):
        est = CorporateActionImpactEstimator()
        impact = est.estimate_buyback_impact("X", 1e9, 0, 0, 0, 0)
        assert impact.eps_accretion_pct == 0.0

    def test_spinoff_impact(self):
        est = CorporateActionImpactEstimator()
        impact = est.estimate_spinoff_impact(
            "GE", current_market_cap=100_000_000_000,
            parent_estimated_value=70_000_000_000,
            spinoff_estimated_value=45_000_000_000,
        )
        assert impact.has_value_creation is True
        assert impact.value_creation_pct > 0

    def test_summarize_impacts(self):
        est = CorporateActionImpactEstimator()
        impacts = [
            DividendImpact(annualized_yield=0.035),
            BuybackImpact(
                eps_accretion_pct=0.005,
                price_support_estimate_pct=0.003,
            ),
        ]
        summary = est.summarize_impacts("AAPL", impacts)
        assert summary.n_actions == 2
        assert summary.total_expected_impact_pct > 0

    def test_summarize_empty(self):
        est = CorporateActionImpactEstimator()
        summary = est.summarize_impacts("X", [])
        assert summary.n_actions == 0


# ---------------------------------------------------------------------------
# Event Calendar
# ---------------------------------------------------------------------------
class TestEventDensity:
    def test_is_busy(self):
        assert EventDensity(density_score=0.6).is_busy is True
        assert EventDensity(density_score=0.2).is_busy is False


class TestEventCluster:
    def test_is_significant(self):
        assert EventCluster(n_events=4).is_significant is True
        assert EventCluster(n_events=1, combined_importance=2.0).is_significant is True


class TestCatalystTimeline:
    def test_has_near_term(self):
        assert CatalystTimeline(next_catalyst_days=7).has_near_term_catalyst is True
        assert CatalystTimeline(next_catalyst_days=30).has_near_term_catalyst is False

    def test_is_catalyst_rich(self):
        assert CatalystTimeline(n_catalysts_30d=3).is_catalyst_rich is True


class TestCrossEventInteraction:
    def test_is_reinforcing(self):
        assert CrossEventInteraction(interaction_type="reinforcing").is_reinforcing is True
        assert CrossEventInteraction(interaction_type="conflicting").is_reinforcing is False


class TestEventCalendarAnalyzer:
    def test_compute_density(self):
        analyzer = EventCalendarAnalyzer()
        events = _calendar_events()
        ref = date(2025, 6, 1)
        density = analyzer.compute_density(events, ref, ref + timedelta(days=7))
        assert density.n_events > 0
        assert density.density_score > 0

    def test_compute_density_empty(self):
        analyzer = EventCalendarAnalyzer()
        ref = date(2025, 6, 1)
        density = analyzer.compute_density([], ref, ref + timedelta(days=7))
        assert density.n_events == 0

    def test_detect_clusters(self):
        analyzer = EventCalendarAnalyzer()
        events = _calendar_events()
        clusters = analyzer.detect_clusters(events, cluster_window_days=3)
        assert len(clusters) > 0
        assert clusters[0].n_events >= 2

    def test_detect_clusters_empty(self):
        analyzer = EventCalendarAnalyzer()
        assert analyzer.detect_clusters([]) == []

    def test_catalyst_timeline(self):
        analyzer = EventCalendarAnalyzer()
        events = _calendar_events()
        ref = date(2025, 6, 1)
        timeline = analyzer.catalyst_timeline(events, "AAPL", ref)
        assert timeline.symbol == "AAPL"
        assert len(timeline.catalysts) > 0
        assert timeline.has_near_term_catalyst is True

    def test_catalyst_timeline_no_events(self):
        analyzer = EventCalendarAnalyzer()
        ref = date(2025, 6, 1)
        timeline = analyzer.catalyst_timeline([], "AAPL", ref)
        assert timeline.n_catalysts_30d == 0
        assert timeline.has_near_term_catalyst is False

    def test_detect_interactions(self):
        analyzer = EventCalendarAnalyzer()
        events = _calendar_events()
        interactions = analyzer.detect_interactions(events, "AAPL", 5)
        assert len(interactions) > 0
        assert interactions[0].symbol == "AAPL"

    def test_weekly_summary(self):
        analyzer = EventCalendarAnalyzer()
        events = _calendar_events()
        ref = date(2025, 6, 2)  # Monday
        weeks = analyzer.weekly_summary(events, ref, n_weeks=4)
        assert len(weeks) == 4
