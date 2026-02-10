"""Tests for PRD-64: Liquidity Risk Analytics."""

import pytest
from datetime import datetime, timezone

from src.liquidity import (
    LiquidityTier,
    ImpactModel,
    OrderSide,
    SpreadComponent,
    TIER_THRESHOLDS,
    IMPACT_COEFFICIENTS,
    LiquidityScore,
    SpreadSnapshot,
    MarketImpactEstimate,
    SlippageRecord,
    LiquidityProfile,
    LiquidityScorer,
    SpreadAnalyzer,
    ImpactEstimator,
    SlippageTracker,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def scorer() -> LiquidityScorer:
    return LiquidityScorer()


@pytest.fixture
def spread_analyzer() -> SpreadAnalyzer:
    return SpreadAnalyzer()


@pytest.fixture
def impact_estimator() -> ImpactEstimator:
    return ImpactEstimator()


@pytest.fixture
def slippage_tracker() -> SlippageTracker:
    return SlippageTracker()


# ---------------------------------------------------------------------------
# Config Tests
# ---------------------------------------------------------------------------


class TestLiquidityConfig:
    def test_liquidity_tiers(self):
        assert LiquidityTier.HIGHLY_LIQUID.value == "highly_liquid"
        assert LiquidityTier.ILLIQUID.value == "illiquid"
        assert len(LiquidityTier) == 5

    def test_impact_models(self):
        assert ImpactModel.SQUARE_ROOT.value == "square_root"
        assert ImpactModel.LINEAR.value == "linear"
        assert len(ImpactModel) == 4

    def test_order_sides(self):
        assert OrderSide.BUY.value == "buy"
        assert OrderSide.SELL.value == "sell"

    def test_tier_thresholds(self):
        assert len(TIER_THRESHOLDS) == 5
        for tier, (low, high) in TIER_THRESHOLDS.items():
            assert low < high

    def test_impact_coefficients(self):
        assert len(IMPACT_COEFFICIENTS) == 5
        for tier, coeffs in IMPACT_COEFFICIENTS.items():
            assert "linear_coeff" in coeffs
            assert "sqrt_coeff" in coeffs


# ---------------------------------------------------------------------------
# Models Tests
# ---------------------------------------------------------------------------


class TestLiquidityModels:
    def test_liquidity_score(self):
        score = LiquidityScore(
            symbol="AAPL",
            composite_score=85.0,
            volume_score=90.0,
            spread_score=80.0,
            liquidity_tier=LiquidityTier.HIGHLY_LIQUID,
        )

        assert score.symbol == "AAPL"
        assert score.composite_score == 85.0
        d = score.to_dict()
        assert d["liquidity_tier"] == "highly_liquid"

    def test_spread_snapshot(self):
        snap = SpreadSnapshot(
            symbol="AAPL",
            bid_price=149.95,
            ask_price=150.05,
            bid_size=1000,
            ask_size=800,
        )

        assert snap.mid_price == 150.0
        assert snap.spread == pytest.approx(0.10)
        assert snap.spread_bps == pytest.approx(6.67, rel=0.01)
        assert snap.spread_pct == pytest.approx(0.0667, rel=0.01)

        d = snap.to_dict()
        assert "spread_bps" in d

    def test_market_impact_estimate(self):
        est = MarketImpactEstimate(
            symbol="AAPL",
            order_size_shares=10000,
            order_size_value=1_500_000,
            side=OrderSide.BUY,
            estimated_impact_bps=5.0,
            temporary_impact_bps=3.0,
            permanent_impact_bps=2.0,
        )

        assert est.total_cost_bps == 5.0
        d = est.to_dict()
        assert d["side"] == "buy"

    def test_slippage_record_buy(self):
        rec = SlippageRecord(
            symbol="AAPL",
            side=OrderSide.BUY,
            order_size=1000,
            expected_price=150.00,
            executed_price=150.05,
        )

        assert rec.slippage == pytest.approx(0.05)
        assert rec.slippage_bps == pytest.approx(3.33, rel=0.01)
        assert rec.slippage_cost == pytest.approx(50.0)

    def test_slippage_record_sell(self):
        rec = SlippageRecord(
            symbol="AAPL",
            side=OrderSide.SELL,
            order_size=1000,
            expected_price=150.00,
            executed_price=149.90,
        )

        assert rec.slippage == pytest.approx(0.10)
        assert rec.slippage_bps == pytest.approx(6.67, rel=0.01)

    def test_liquidity_profile(self):
        score = LiquidityScore(
            symbol="AAPL",
            composite_score=85.0,
            liquidity_tier=LiquidityTier.HIGHLY_LIQUID,
        )

        snap1 = SpreadSnapshot(symbol="AAPL", bid_price=149.95, ask_price=150.05)
        snap2 = SpreadSnapshot(symbol="AAPL", bid_price=149.96, ask_price=150.04)

        profile = LiquidityProfile(
            symbol="AAPL",
            score=score,
            recent_spreads=[snap1, snap2],
        )

        assert profile.avg_spread_bps > 0
        d = profile.to_dict()
        assert d["spread_count"] == 2


# ---------------------------------------------------------------------------
# Liquidity Scorer Tests
# ---------------------------------------------------------------------------


class TestLiquidityScorer:
    def test_score_highly_liquid(self, scorer: LiquidityScorer):
        score = scorer.score(
            symbol="AAPL",
            avg_daily_volume=50_000_000,
            avg_spread_bps=3.0,
            market_cap=150_000_000_000,
            volatility=0.25,
        )

        assert score.composite_score > 70
        assert score.liquidity_tier in [LiquidityTier.HIGHLY_LIQUID, LiquidityTier.LIQUID]

    def test_score_illiquid(self, scorer: LiquidityScorer):
        score = scorer.score(
            symbol="PENNY",
            avg_daily_volume=50_000,
            avg_spread_bps=80.0,
            market_cap=50_000_000,
            volatility=0.80,
        )

        assert score.composite_score < 40
        assert score.liquidity_tier in [LiquidityTier.ILLIQUID, LiquidityTier.HIGHLY_ILLIQUID]

    def test_volume_scoring(self, scorer: LiquidityScorer):
        high_vol = scorer.score("A", 50_000_000, 5.0)
        low_vol = scorer.score("B", 100_000, 5.0)

        assert high_vol.volume_score > low_vol.volume_score

    def test_spread_scoring(self, scorer: LiquidityScorer):
        tight = scorer.score("A", 10_000_000, 2.0)
        wide = scorer.score("B", 10_000_000, 40.0)

        assert tight.spread_score > wide.spread_score

    def test_volatility_scoring(self, scorer: LiquidityScorer):
        low_vol = scorer.score("A", 10_000_000, 5.0, volatility=0.10)
        high_vol = scorer.score("B", 10_000_000, 5.0, volatility=0.60)

        assert low_vol.volatility_score > high_vol.volatility_score

    def test_tier_classification(self, scorer: LiquidityScorer):
        # Score multiple stocks to cover different tiers
        tiers_seen = set()
        configs = [
            (100_000_000, 1.0, 0.10),
            (50_000_000, 5.0, 0.20),
            (5_000_000, 15.0, 0.35),
            (500_000, 40.0, 0.50),
            (10_000, 100.0, 0.80),
        ]
        for i, (vol, spread, vol_) in enumerate(configs):
            score = scorer.score(f"SYM{i}", vol, spread, volatility=vol_)
            tiers_seen.add(score.liquidity_tier)

        assert len(tiers_seen) >= 3

    def test_portfolio_scoring(self, scorer: LiquidityScorer):
        holdings = {
            "AAPL": {"avg_daily_volume": 50_000_000, "avg_spread_bps": 3.0, "value": 500_000},
            "MSFT": {"avg_daily_volume": 30_000_000, "avg_spread_bps": 4.0, "value": 300_000},
        }

        result = scorer.score_portfolio(holdings)

        assert "portfolio_score" in result
        assert "portfolio_tier" in result
        assert result["portfolio_score"] > 0
        assert "AAPL" in result["symbol_scores"]

    def test_score_history(self, scorer: LiquidityScorer):
        for _ in range(5):
            scorer.score("AAPL", 50_000_000, 3.0)

        history = scorer.get_score_history("AAPL")
        assert len(history) == 5


# ---------------------------------------------------------------------------
# Spread Analyzer Tests
# ---------------------------------------------------------------------------


class TestLiquiditySpreadAnalyzer:
    def test_record_spread(self, spread_analyzer: SpreadAnalyzer):
        snap = spread_analyzer.record_spread("AAPL", 149.95, 150.05, 1000, 800)

        assert snap.symbol == "AAPL"
        assert snap.spread_bps > 0

    def test_get_current_spread(self, spread_analyzer: SpreadAnalyzer):
        spread_analyzer.record_spread("AAPL", 149.95, 150.05)
        spread_analyzer.record_spread("AAPL", 149.96, 150.04)

        current = spread_analyzer.get_current_spread("AAPL")
        assert current is not None
        assert current.bid_price == 149.96

    def test_get_average_spread(self, spread_analyzer: SpreadAnalyzer):
        for i in range(10):
            spread_analyzer.record_spread("AAPL", 149.90 + i * 0.01, 150.10 - i * 0.01)

        avg = spread_analyzer.get_average_spread("AAPL")
        assert avg is not None
        assert avg > 0

    def test_spread_statistics(self, spread_analyzer: SpreadAnalyzer):
        for i in range(20):
            spread_analyzer.record_spread("AAPL", 149.90 + i * 0.005, 150.10 - i * 0.005, 1000, 900)

        stats = spread_analyzer.get_spread_statistics("AAPL")

        assert stats["data_points"] == 20
        assert "avg_spread_bps" in stats
        assert "min_spread_bps" in stats
        assert "max_spread_bps" in stats
        assert "avg_bid_ask_imbalance" in stats

    def test_decompose_spread(self, spread_analyzer: SpreadAnalyzer):
        spread_analyzer.record_spread("AAPL", 149.95, 150.05)

        decomp = spread_analyzer.decompose_spread("AAPL", volatility=0.02)

        assert SpreadComponent.ADVERSE_SELECTION.value in decomp
        assert SpreadComponent.INVENTORY.value in decomp
        assert SpreadComponent.ORDER_PROCESSING.value in decomp

    def test_detect_anomalies(self, spread_analyzer: SpreadAnalyzer):
        # Record normal spreads
        for _ in range(30):
            spread_analyzer.record_spread("AAPL", 149.98, 150.02)

        # Record wide spread
        spread_analyzer.record_spread("AAPL", 149.50, 150.50)

        anomalies = spread_analyzer.detect_spread_anomalies("AAPL")
        assert len(anomalies) >= 1

    def test_empty_symbol(self, spread_analyzer: SpreadAnalyzer):
        current = spread_analyzer.get_current_spread("UNKNOWN")
        assert current is None

        avg = spread_analyzer.get_average_spread("UNKNOWN")
        assert avg is None

    def test_get_stats(self, spread_analyzer: SpreadAnalyzer):
        spread_analyzer.record_spread("AAPL", 149.95, 150.05)
        spread_analyzer.record_spread("MSFT", 299.90, 300.10)

        stats = spread_analyzer.get_stats()
        assert stats["total_snapshots"] == 2
        assert stats["symbols_tracked"] == 2


# ---------------------------------------------------------------------------
# Impact Estimator Tests
# ---------------------------------------------------------------------------


class TestImpactEstimator:
    def test_estimate_impact(self, impact_estimator: ImpactEstimator):
        est = impact_estimator.estimate_impact(
            symbol="AAPL",
            order_size_shares=10000,
            price=150.0,
            side=OrderSide.BUY,
            avg_daily_volume=50_000_000,
            volatility=0.25,
        )

        assert est.estimated_impact_bps > 0
        assert est.temporary_impact_bps > 0
        assert est.permanent_impact_bps > 0
        assert est.estimated_cost > 0
        assert est.participation_rate > 0

    def test_impact_scales_with_size(self, impact_estimator: ImpactEstimator):
        small = impact_estimator.estimate_impact("AAPL", 1000, 150.0, OrderSide.BUY, 50_000_000)
        large = impact_estimator.estimate_impact("AAPL", 100000, 150.0, OrderSide.BUY, 50_000_000)

        assert large.estimated_impact_bps > small.estimated_impact_bps

    def test_impact_models(self, impact_estimator: ImpactEstimator):
        results = {}
        for model in [ImpactModel.LINEAR, ImpactModel.SQUARE_ROOT, ImpactModel.POWER_LAW]:
            est = impact_estimator.estimate_impact(
                "AAPL", 10000, 150.0, OrderSide.BUY, 50_000_000,
                model=model,
            )
            results[model] = est.estimated_impact_bps
            assert est.model_used == model

        # All models should produce positive impact
        for impact_bps in results.values():
            assert impact_bps > 0

    def test_liquidity_tier_impact(self, impact_estimator: ImpactEstimator):
        liquid = impact_estimator.estimate_impact(
            "AAPL", 10000, 150.0, OrderSide.BUY, 50_000_000,
            liquidity_tier=LiquidityTier.HIGHLY_LIQUID,
        )
        illiquid = impact_estimator.estimate_impact(
            "PENNY", 10000, 5.0, OrderSide.BUY, 100_000,
            liquidity_tier=LiquidityTier.ILLIQUID,
        )

        assert illiquid.estimated_impact_bps > liquid.estimated_impact_bps

    def test_optimal_execution(self, impact_estimator: ImpactEstimator):
        result = impact_estimator.estimate_optimal_execution(
            symbol="AAPL",
            total_shares=100000,
            price=150.0,
            avg_daily_volume=50_000_000,
        )

        assert "optimal_strategy" in result
        assert "all_strategies" in result
        assert result["optimal_strategy"]["slices"] >= 1

    def test_estimate_history(self, impact_estimator: ImpactEstimator):
        for _ in range(5):
            impact_estimator.estimate_impact("AAPL", 10000, 150.0, OrderSide.BUY, 50_000_000)

        history = impact_estimator.get_estimate_history("AAPL")
        assert len(history) == 5

    def test_get_stats(self, impact_estimator: ImpactEstimator):
        impact_estimator.estimate_impact("AAPL", 10000, 150.0, OrderSide.BUY, 50_000_000)

        stats = impact_estimator.get_stats()
        assert stats["total_estimates"] == 1
        assert stats["avg_impact_bps"] > 0


# ---------------------------------------------------------------------------
# Slippage Tracker Tests
# ---------------------------------------------------------------------------


class TestSlippageTracker:
    def test_record_slippage(self, slippage_tracker: SlippageTracker):
        rec = slippage_tracker.record_slippage(
            symbol="AAPL",
            side=OrderSide.BUY,
            order_size=1000,
            expected_price=150.00,
            executed_price=150.05,
            market_volume=50_000_000,
        )

        assert rec.slippage_bps > 0
        assert rec.participation_rate is not None

    def test_forecast_slippage_no_history(self, slippage_tracker: SlippageTracker):
        forecast = slippage_tracker.forecast_slippage(
            "AAPL", 10000, 150.0, OrderSide.BUY, avg_daily_volume=50_000_000,
        )

        assert forecast["model"] == "default"
        assert forecast["estimated_slippage_bps"] > 0
        assert forecast["confidence"] < 0.5

    def test_forecast_slippage_with_history(self, slippage_tracker: SlippageTracker):
        # Record history
        for i in range(10):
            slippage_tracker.record_slippage(
                "AAPL", OrderSide.BUY, 1000, 150.0, 150.0 + 0.05 * (i % 3),
            )

        forecast = slippage_tracker.forecast_slippage(
            "AAPL", 1000, 150.0, OrderSide.BUY,
        )

        assert forecast["model"] == "historical"
        assert forecast["sample_size"] == 10

    def test_slippage_history(self, slippage_tracker: SlippageTracker):
        for i in range(5):
            slippage_tracker.record_slippage(
                "AAPL", OrderSide.BUY, 1000, 150.0, 150.05,
            )
            slippage_tracker.record_slippage(
                "AAPL", OrderSide.SELL, 1000, 150.0, 149.95,
            )

        all_history = slippage_tracker.get_slippage_history("AAPL")
        assert len(all_history) == 10

        buy_history = slippage_tracker.get_slippage_history("AAPL", OrderSide.BUY)
        assert len(buy_history) == 5

    def test_slippage_statistics(self, slippage_tracker: SlippageTracker):
        for _ in range(20):
            slippage_tracker.record_slippage(
                "AAPL", OrderSide.BUY, 1000, 150.0, 150.03,
            )

        stats = slippage_tracker.get_slippage_statistics("AAPL")

        assert stats["total_records"] == 20
        assert "avg_slippage_bps" in stats
        assert "total_slippage_cost" in stats

    def test_cost_attribution(self, slippage_tracker: SlippageTracker):
        for _ in range(10):
            slippage_tracker.record_slippage(
                "AAPL", OrderSide.BUY, 1000, 150.0, 150.05,
            )

        attrib = slippage_tracker.get_cost_attribution("AAPL", spread_cost_bps=3.0)

        assert "spread_cost_bps" in attrib
        assert "impact_cost_bps" in attrib
        assert attrib["sample_size"] == 10

    def test_portfolio_slippage(self, slippage_tracker: SlippageTracker):
        result = slippage_tracker.get_portfolio_slippage(
            holdings={"AAPL": 1000, "MSFT": 500},
            prices={"AAPL": 150.0, "MSFT": 300.0},
        )

        assert result["portfolio_value"] == 300_000
        assert result["total_estimated_cost"] >= 0
        assert "AAPL" in result["holdings"]

    def test_get_stats(self, slippage_tracker: SlippageTracker):
        slippage_tracker.record_slippage("AAPL", OrderSide.BUY, 1000, 150.0, 150.05)
        slippage_tracker.record_slippage("MSFT", OrderSide.SELL, 500, 300.0, 299.90)

        stats = slippage_tracker.get_stats()
        assert stats["total_records"] == 2
        assert stats["symbols_tracked"] == 2


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------


class TestLiquidityIntegration:
    def test_full_workflow(
        self,
        scorer: LiquidityScorer,
        spread_analyzer: SpreadAnalyzer,
        impact_estimator: ImpactEstimator,
        slippage_tracker: SlippageTracker,
    ):
        symbol = "AAPL"
        price = 150.0
        adv = 50_000_000

        # 1. Score liquidity
        score = scorer.score(symbol, adv, 3.0, volatility=0.25)
        assert score.composite_score > 50

        # 2. Record spreads
        for i in range(5):
            spread_analyzer.record_spread(symbol, 149.95 + i * 0.01, 150.05 - i * 0.01)

        avg_spread = spread_analyzer.get_average_spread(symbol)
        assert avg_spread is not None

        # 3. Estimate impact
        est = impact_estimator.estimate_impact(
            symbol, 10000, price, OrderSide.BUY, adv,
            liquidity_tier=score.liquidity_tier,
        )
        assert est.estimated_impact_bps > 0

        # 4. Record slippage
        slippage_tracker.record_slippage(
            symbol, OrderSide.BUY, 10000, price, price + 0.03,
            market_volume=adv,
        )

        # 5. Forecast
        forecast = slippage_tracker.forecast_slippage(symbol, 10000, price, OrderSide.BUY)
        assert forecast["estimated_slippage_bps"] >= 0

        # 6. Build profile
        profile = LiquidityProfile(
            symbol=symbol,
            score=score,
            recent_spreads=spread_analyzer.get_spread_history(symbol),
            recent_slippage=slippage_tracker.get_slippage_history(symbol),
        )
        assert profile.avg_spread_bps > 0
