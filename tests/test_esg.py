"""Tests for ESG Scoring & Impact Tracking."""

import pytest
from src.esg.config import (
    ESGCategory,
    ESGRating,
    ESGPillar,
    ImpactCategory,
    ESGConfig,
    RATING_THRESHOLDS,
    PILLAR_CATEGORIES,
    DEFAULT_ESG_CONFIG,
)
from src.esg.models import (
    ESGScore,
    PillarScore,
    ImpactMetric,
    ESGScreenResult,
    CarbonMetrics,
    ESGPortfolioSummary,
)
from src.esg.scoring import ESGScorer
from src.esg.impact import ImpactTracker


# ── Config Tests ──


class TestEnums:
    def test_esg_category_values(self):
        assert ESGCategory.ENVIRONMENTAL.value == "environmental"
        assert ESGCategory.SOCIAL.value == "social"
        assert ESGCategory.GOVERNANCE.value == "governance"
        assert ESGCategory.COMPOSITE.value == "composite"

    def test_esg_rating_order(self):
        ratings = list(ESGRating)
        assert ratings[0] == ESGRating.AAA
        assert ratings[-1] == ESGRating.CCC
        assert len(ratings) == 7

    def test_esg_pillar_categories(self):
        assert PILLAR_CATEGORIES[ESGPillar.CARBON_EMISSIONS] == ESGCategory.ENVIRONMENTAL
        assert PILLAR_CATEGORIES[ESGPillar.LABOR_PRACTICES] == ESGCategory.SOCIAL
        assert PILLAR_CATEGORIES[ESGPillar.BOARD_COMPOSITION] == ESGCategory.GOVERNANCE

    def test_impact_categories(self):
        assert len(ImpactCategory) == 8
        assert ImpactCategory.CARBON_FOOTPRINT.value == "carbon_footprint"

    def test_rating_thresholds(self):
        assert RATING_THRESHOLDS[ESGRating.AAA] == 85
        assert RATING_THRESHOLDS[ESGRating.CCC] == 0

    def test_default_config(self):
        cfg = DEFAULT_ESG_CONFIG
        assert cfg.environmental_weight == 0.35
        assert cfg.social_weight == 0.30
        assert cfg.governance_weight == 0.35
        assert cfg.max_score == 100.0


# ── Model Tests ──


class TestPillarScore:
    def test_weighted_score(self):
        p = PillarScore(pillar=ESGPillar.CARBON_EMISSIONS, score=80, weight=0.5)
        assert p.weighted_score == 40.0

    def test_to_dict(self):
        p = PillarScore(pillar=ESGPillar.LABOR_PRACTICES, score=70)
        d = p.to_dict()
        assert d["pillar"] == "labor_practices"
        assert d["score"] == 70


class TestESGScore:
    def test_category_scores(self):
        s = ESGScore(environmental_score=80, social_score=70, governance_score=90, composite_score=80)
        cats = s.category_scores
        assert cats["environmental"] == 80
        assert cats["social"] == 70
        assert cats["governance"] == 90
        assert cats["composite"] == 80

    def test_to_dict(self):
        s = ESGScore(symbol="AAPL", composite_score=75, rating=ESGRating.AA)
        d = s.to_dict()
        assert d["symbol"] == "AAPL"
        assert d["rating"] == "AA"

    def test_default_values(self):
        s = ESGScore()
        assert s.composite_score == 50.0
        assert s.rating == ESGRating.BBB
        assert s.controversies == []


class TestCarbonMetrics:
    def test_total_scope12(self):
        c = CarbonMetrics(scope1_emissions=100, scope2_emissions=50)
        assert c.total_scope12 == 150

    def test_to_dict(self):
        c = CarbonMetrics(symbol="XOM", carbon_intensity=800)
        d = c.to_dict()
        assert d["symbol"] == "XOM"
        assert d["carbon_intensity"] == 800


class TestESGScreenResult:
    def test_passed(self):
        r = ESGScreenResult(symbol="AAPL", passed=True)
        assert r.passed
        assert r.excluded_reasons == []

    def test_failed(self):
        r = ESGScreenResult(symbol="XOM", passed=False, excluded_reasons=["Fossil fuel"])
        assert not r.passed
        assert len(r.excluded_reasons) == 1

    def test_to_dict(self):
        r = ESGScreenResult(symbol="AAPL", passed=True, score=80, rating=ESGRating.AA)
        d = r.to_dict()
        assert d["rating"] == "AA"


class TestImpactMetric:
    def test_vs_benchmark(self):
        m = ImpactMetric(category=ImpactCategory.CARBON_FOOTPRINT, value=100, unit="tCO2e/$M", benchmark=200)
        assert m.vs_benchmark == -0.5

    def test_vs_benchmark_none(self):
        m = ImpactMetric(category=ImpactCategory.CARBON_FOOTPRINT, value=100, unit="tCO2e/$M")
        assert m.vs_benchmark is None

    def test_to_dict(self):
        m = ImpactMetric(category=ImpactCategory.RENEWABLE_ENERGY, value=85, unit="%", trend="improving")
        d = m.to_dict()
        assert d["category"] == "renewable_energy"
        assert d["trend"] == "improving"


class TestESGPortfolioSummary:
    def test_defaults(self):
        s = ESGPortfolioSummary()
        assert s.weighted_esg_score == 50.0
        assert s.portfolio_rating == ESGRating.BBB

    def test_to_dict(self):
        s = ESGPortfolioSummary(weighted_esg_score=75, portfolio_rating=ESGRating.AA)
        d = s.to_dict()
        assert d["weighted_esg_score"] == 75
        assert d["portfolio_rating"] == "AA"


# ── Scorer Tests ──


class TestESGScorer:
    def setup_method(self):
        self.scorer = ESGScorer()

    def test_score_security_basic(self):
        score = self.scorer.score_security("AAPL", environmental=80, social=70, governance=85)
        assert score.symbol == "AAPL"
        assert score.environmental_score == 80
        assert score.social_score == 70
        assert score.governance_score == 85
        assert score.composite_score > 0

    def test_composite_weighted(self):
        score = self.scorer.score_security("TEST", environmental=100, social=100, governance=100)
        assert score.composite_score == 100.0

    def test_composite_zero(self):
        score = self.scorer.score_security("TEST", environmental=0, social=0, governance=0)
        assert score.composite_score == 0.0

    def test_rating_aaa(self):
        score = self.scorer.score_security("TEST", environmental=90, social=90, governance=90)
        assert score.rating == ESGRating.AAA

    def test_rating_ccc(self):
        score = self.scorer.score_security("TEST", environmental=10, social=10, governance=10)
        assert score.rating == ESGRating.CCC

    def test_controversy_penalty(self):
        score1 = self.scorer.score_security("A", environmental=80, social=80, governance=80)
        score2 = self.scorer.score_security("B", environmental=80, social=80, governance=80,
                                            controversies=["Issue 1", "Issue 2"])
        assert score2.composite_score < score1.composite_score
        assert score2.controversy_score == 20.0

    def test_score_clamped(self):
        score = self.scorer.score_security("TEST", environmental=150, social=-10, governance=50)
        assert score.environmental_score == 100.0
        assert score.social_score == 0.0

    def test_get_score(self):
        self.scorer.score_security("AAPL", environmental=80, social=70, governance=85)
        assert self.scorer.get_score("AAPL") is not None
        assert self.scorer.get_score("UNKNOWN") is None

    def test_get_all_scores(self):
        self.scorer.score_security("AAPL", environmental=80, social=70, governance=85)
        self.scorer.score_security("MSFT", environmental=82, social=80, governance=88)
        assert len(self.scorer.get_all_scores()) == 2

    def test_pillar_scores(self):
        pillars = [PillarScore(pillar=ESGPillar.CARBON_EMISSIONS, score=75)]
        score = self.scorer.score_security("TEST", pillar_scores=pillars)
        assert len(score.pillar_scores) == 1

    def test_carbon_metrics(self):
        self.scorer.set_carbon_metrics("XOM", CarbonMetrics(carbon_intensity=800))
        carbon = self.scorer.get_carbon_metrics("XOM")
        assert carbon is not None
        assert carbon.carbon_intensity == 800

    def test_carbon_metrics_none(self):
        assert self.scorer.get_carbon_metrics("UNKNOWN") is None


class TestESGScreening:
    def setup_method(self):
        self.config = ESGConfig(
            exclude_sin_stocks=True,
            exclude_fossil_fuels=True,
            exclude_weapons=True,
        )
        self.scorer = ESGScorer(self.config)

    def test_pass_clean_security(self):
        result = self.scorer.screen_security("AAPL", industry="technology")
        assert result.passed
        assert result.excluded_reasons == []

    def test_exclude_sin_stock(self):
        result = self.scorer.screen_security("PM", industry="tobacco")
        assert not result.passed
        assert any("Sin stock" in r for r in result.excluded_reasons)

    def test_exclude_fossil_fuel(self):
        result = self.scorer.screen_security("XOM", industry="oil_gas")
        assert not result.passed
        assert any("Fossil fuel" in r for r in result.excluded_reasons)

    def test_exclude_weapons(self):
        result = self.scorer.screen_security("LMT", industry="weapons")
        assert not result.passed
        assert any("Weapons" in r for r in result.excluded_reasons)

    def test_min_score_filter(self):
        self.scorer.score_security("LOW", environmental=20, social=20, governance=20)
        result = self.scorer.screen_security("LOW", min_score=50)
        assert not result.passed
        assert any("below minimum" in r for r in result.excluded_reasons)

    def test_carbon_intensity_filter(self):
        self.scorer.set_carbon_metrics("HIGH_CARBON", CarbonMetrics(carbon_intensity=600))
        result = self.scorer.screen_security("HIGH_CARBON")
        assert not result.passed
        assert any("Carbon intensity" in r for r in result.excluded_reasons)

    def test_no_exclusions_disabled(self):
        scorer = ESGScorer(ESGConfig())  # All exclusions off
        result = scorer.screen_security("PM", industry="tobacco")
        assert result.passed


class TestPortfolioSummary:
    def setup_method(self):
        self.scorer = ESGScorer()
        self.scorer.score_security("AAPL", environmental=80, social=70, governance=85, sector="Tech")
        self.scorer.score_security("MSFT", environmental=82, social=80, governance=88, sector="Tech")
        self.scorer.score_security("XOM", environmental=35, social=55, governance=60, sector="Energy",
                                  controversies=["Spill"])

    def test_basic_summary(self):
        summary = self.scorer.portfolio_summary({"AAPL": 0.5, "MSFT": 0.5})
        assert summary.n_holdings == 2
        assert summary.weighted_esg_score > 0
        assert summary.coverage_pct == 100.0

    def test_empty_holdings(self):
        summary = self.scorer.portfolio_summary({})
        assert summary.weighted_esg_score == 50.0

    def test_controversies_aggregated(self):
        summary = self.scorer.portfolio_summary({"XOM": 1.0})
        assert len(summary.controversies) == 1
        assert "XOM" in summary.controversies[0]

    def test_best_worst_class(self):
        summary = self.scorer.portfolio_summary({"AAPL": 0.4, "MSFT": 0.4, "XOM": 0.2})
        assert len(summary.best_in_class) == 3
        assert summary.best_in_class[0] in ["AAPL", "MSFT"]  # Higher scores first

    def test_rating_assigned(self):
        summary = self.scorer.portfolio_summary({"AAPL": 0.5, "MSFT": 0.5})
        assert isinstance(summary.portfolio_rating, ESGRating)


class TestSectorRanking:
    def test_rank_by_sector(self):
        scorer = ESGScorer()
        scorer.score_security("A", environmental=90, social=90, governance=90, sector="Tech")
        scorer.score_security("B", environmental=70, social=70, governance=70, sector="Tech")
        scorer.score_security("C", environmental=50, social=50, governance=50, sector="Tech")

        ranked = scorer.rank_by_sector("Tech")
        assert len(ranked) == 3
        assert ranked[0].sector_rank == 1
        assert ranked[0].composite_score > ranked[1].composite_score

    def test_empty_sector(self):
        scorer = ESGScorer()
        ranked = scorer.rank_by_sector("Empty")
        assert ranked == []


# ── Impact Tracker Tests ──


class TestImpactTracker:
    def setup_method(self):
        self.tracker = ImpactTracker()

    def test_record_metric(self):
        m = self.tracker.record_metric("AAPL", ImpactCategory.CARBON_FOOTPRINT, 45)
        assert m.value == 45
        assert m.category == ImpactCategory.CARBON_FOOTPRINT
        assert m.benchmark == 200.0  # Default benchmark

    def test_get_metrics(self):
        self.tracker.record_metric("AAPL", ImpactCategory.CARBON_FOOTPRINT, 45)
        self.tracker.record_metric("AAPL", ImpactCategory.RENEWABLE_ENERGY, 85)
        metrics = self.tracker.get_metrics("AAPL")
        assert len(metrics) == 2

    def test_get_metrics_by_category(self):
        self.tracker.record_metric("AAPL", ImpactCategory.CARBON_FOOTPRINT, 45)
        self.tracker.record_metric("AAPL", ImpactCategory.RENEWABLE_ENERGY, 85)
        metrics = self.tracker.get_metrics("AAPL", ImpactCategory.CARBON_FOOTPRINT)
        assert len(metrics) == 1
        assert metrics[0].value == 45

    def test_get_metrics_unknown_symbol(self):
        assert self.tracker.get_metrics("UNKNOWN") == []

    def test_get_latest_metrics(self):
        self.tracker.record_metric("AAPL", ImpactCategory.CARBON_FOOTPRINT, 45)
        self.tracker.record_metric("AAPL", ImpactCategory.CARBON_FOOTPRINT, 40)
        latest = self.tracker.get_latest_metrics("AAPL")
        assert latest[ImpactCategory.CARBON_FOOTPRINT].value == 40

    def test_portfolio_impact(self):
        self.tracker.record_metric("AAPL", ImpactCategory.CARBON_FOOTPRINT, 45)
        self.tracker.record_metric("MSFT", ImpactCategory.CARBON_FOOTPRINT, 35)
        impact = self.tracker.portfolio_impact({"AAPL": 0.5, "MSFT": 0.5})
        assert ImpactCategory.CARBON_FOOTPRINT in impact
        assert impact[ImpactCategory.CARBON_FOOTPRINT].value == 40.0

    def test_portfolio_impact_empty(self):
        assert self.tracker.portfolio_impact({}) == {}

    def test_get_tracked_symbols(self):
        self.tracker.record_metric("AAPL", ImpactCategory.CARBON_FOOTPRINT, 45)
        self.tracker.record_metric("MSFT", ImpactCategory.RENEWABLE_ENERGY, 85)
        syms = self.tracker.get_tracked_symbols()
        assert set(syms) == {"AAPL", "MSFT"}

    def test_custom_unit(self):
        m = self.tracker.record_metric("AAPL", ImpactCategory.CARBON_FOOTPRINT, 45, unit="custom_unit")
        assert m.unit == "custom_unit"

    def test_trend(self):
        m = self.tracker.record_metric("AAPL", ImpactCategory.CARBON_FOOTPRINT, 45, trend="improving")
        assert m.trend == "improving"


# ── Module Import Test ──


class TestModuleImports:
    def test_top_level_imports(self):
        from src.esg import ESGScorer, ImpactTracker, ESGConfig, ESGScore
        assert ESGScorer is not None
        assert ImpactTracker is not None
        assert ESGConfig is not None
        assert ESGScore is not None
