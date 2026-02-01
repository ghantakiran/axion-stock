"""Tests for Market Breadth module (PRD-36)."""

import pytest
from datetime import date, timedelta

from src.breadth.config import (
    BreadthIndicator,
    MarketHealthLevel,
    BreadthSignal,
    BreadthTimeframe,
    McClellanConfig,
    ThrustConfig,
    HealthConfig,
    NewHighsLowsConfig,
    BreadthConfig,
    GICS_SECTORS,
    DEFAULT_BREADTH_CONFIG,
)
from src.breadth.models import (
    AdvanceDecline,
    NewHighsLows,
    McClellanData,
    BreadthThrustData,
    BreadthSnapshot,
    SectorBreadth,
    MarketHealth,
)
from src.breadth.indicators import BreadthIndicators
from src.breadth.health import HealthScorer
from src.breadth.sector import SectorBreadthAnalyzer


# =========================================================================
# Config Tests
# =========================================================================


class TestConfig:
    def test_breadth_indicators(self):
        assert len(BreadthIndicator) == 7

    def test_health_levels(self):
        assert len(MarketHealthLevel) == 5
        assert MarketHealthLevel.VERY_BULLISH.value == "very_bullish"

    def test_breadth_signals(self):
        assert len(BreadthSignal) == 9

    def test_timeframes(self):
        assert len(BreadthTimeframe) == 3

    def test_gics_sectors(self):
        assert len(GICS_SECTORS) == 11
        assert "Technology" in GICS_SECTORS
        assert "Financials" in GICS_SECTORS

    def test_mcclellan_config(self):
        cfg = McClellanConfig()
        assert cfg.fast_period == 19
        assert cfg.slow_period == 39
        assert cfg.overbought == 100.0
        assert cfg.oversold == -100.0

    def test_thrust_config(self):
        cfg = ThrustConfig()
        assert cfg.ema_period == 10
        assert cfg.low_threshold == 0.40
        assert cfg.high_threshold == 0.615

    def test_health_config(self):
        cfg = HealthConfig()
        weights = cfg.ad_weight + cfg.nhnl_weight + cfg.mcclellan_weight + cfg.thrust_weight + cfg.volume_weight
        assert weights == pytest.approx(1.0)

    def test_breadth_config(self):
        cfg = BreadthConfig()
        assert isinstance(cfg.mcclellan, McClellanConfig)
        assert isinstance(cfg.thrust, ThrustConfig)
        assert cfg.timeframe == BreadthTimeframe.DAILY

    def test_default_config(self):
        assert DEFAULT_BREADTH_CONFIG.mcclellan.fast_period == 19


# =========================================================================
# Model Tests
# =========================================================================


class TestModels:
    def test_advance_decline_properties(self):
        ad = AdvanceDecline(
            date=date(2026, 1, 31),
            advancing=2200,
            declining=1300,
            unchanged=500,
            up_volume=5_000_000,
            down_volume=2_500_000,
        )
        assert ad.total == 4000
        assert ad.net_advances == 900
        assert ad.ad_ratio == pytest.approx(2200 / 1300)
        assert ad.breadth_pct == pytest.approx(2200 / 3500)
        assert ad.volume_ratio == pytest.approx(2.0)

    def test_advance_decline_zero_decline(self):
        ad = AdvanceDecline(date=date.today(), advancing=100, declining=0)
        assert ad.ad_ratio == 100.0
        assert ad.net_advances == 100

    def test_advance_decline_zero_all(self):
        ad = AdvanceDecline(date=date.today())
        assert ad.total == 0
        assert ad.breadth_pct == 0.5

    def test_new_highs_lows(self):
        nhnl = NewHighsLows(date=date.today(), new_highs=80, new_lows=20)
        assert nhnl.net == 60
        assert nhnl.ratio == pytest.approx(4.0)

    def test_new_highs_lows_zero(self):
        nhnl = NewHighsLows(date=date.today(), new_highs=50, new_lows=0)
        assert nhnl.ratio == 50.0

    def test_mcclellan_data(self):
        mc = McClellanData(
            date=date.today(), oscillator=120.0, summation_index=500.0,
        )
        assert mc.is_overbought is True
        assert mc.is_oversold is False

    def test_mcclellan_oversold(self):
        mc = McClellanData(date=date.today(), oscillator=-110.0)
        assert mc.is_oversold is True
        assert mc.is_overbought is False

    def test_breadth_thrust_data(self):
        bt = BreadthThrustData(
            date=date.today(), breadth_ema=0.55, thrust_active=False,
        )
        assert bt.thrust_active is False

    def test_breadth_snapshot(self):
        snap = BreadthSnapshot(date=date.today())
        assert len(snap.snapshot_id) == 16
        assert snap.cumulative_ad_line == 0.0

    def test_sector_breadth(self):
        sb = SectorBreadth(
            sector="Technology", advancing=40, declining=10, unchanged=5,
        )
        assert sb.total == 55
        assert sb.pct_advancing == 0.0  # Not auto-computed

    def test_market_health_to_dict(self):
        mh = MarketHealth(score=72.5, level=MarketHealthLevel.BULLISH)
        d = mh.to_dict()
        assert d["score"] == 72.5
        assert d["level"] == "bullish"

    def test_market_health_with_signals(self):
        mh = MarketHealth(
            signals=[BreadthSignal.BREADTH_THRUST, BreadthSignal.ZERO_CROSS_UP],
        )
        d = mh.to_dict()
        assert "breadth_thrust" in d["signals"]


# =========================================================================
# Indicators Tests
# =========================================================================


class TestBreadthIndicators:
    def _make_ad(self, day_offset: int, adv: int, dec: int) -> AdvanceDecline:
        return AdvanceDecline(
            date=date(2026, 1, 1) + timedelta(days=day_offset),
            advancing=adv,
            declining=dec,
            unchanged=200,
            up_volume=adv * 1000.0,
            down_volume=dec * 1000.0,
        )

    def test_cumulative_ad_line(self):
        ind = BreadthIndicators()
        ind.process_day(self._make_ad(0, 2000, 1500))  # net +500
        ind.process_day(self._make_ad(1, 1800, 1700))  # net +100
        assert ind.cumulative_ad_line == 600.0

    def test_cumulative_ad_line_negative(self):
        ind = BreadthIndicators()
        ind.process_day(self._make_ad(0, 1000, 2000))  # net -1000
        assert ind.cumulative_ad_line == -1000.0

    def test_mcclellan_oscillator(self):
        ind = BreadthIndicators()
        snap = ind.process_day(self._make_ad(0, 2000, 1500))
        assert snap.mcclellan is not None
        assert snap.mcclellan.oscillator == 0.0  # First bar: fast == slow

    def test_mcclellan_diverges(self):
        ind = BreadthIndicators()
        # Start neutral then ramp up to create divergence
        for i in range(5):
            snap = ind.process_day(self._make_ad(i, 1500 + i * 200, 1500 - i * 100))
        # Increasing net advances makes fast EMA > slow EMA
        assert snap.mcclellan.oscillator > 0  # Fast > slow

    def test_mcclellan_summation_accumulates(self):
        ind = BreadthIndicators()
        # Varying net advances to create non-zero oscillator
        for i in range(10):
            snap = ind.process_day(self._make_ad(i, 1500 + i * 100, 1500 - i * 50))
        assert ind.summation_index != 0.0
        assert snap.mcclellan.summation_index == pytest.approx(ind.summation_index, abs=0.01)

    def test_zero_cross_up_signal(self):
        ind = BreadthIndicators()
        # Start bearish to drive oscillator negative
        for i in range(20):
            ind.process_day(self._make_ad(i, 1200, 2000))

        # Switch to bullish
        found_cross = False
        for i in range(20, 60):
            snap = ind.process_day(self._make_ad(i, 2500, 1000))
            if BreadthSignal.ZERO_CROSS_UP in snap.signals:
                found_cross = True
                break
        assert found_cross

    def test_overbought_signal(self):
        ind = BreadthIndicators(mcclellan_config=McClellanConfig(overbought=50.0))
        # Strong bullish should eventually trigger overbought
        for i in range(30):
            snap = ind.process_day(self._make_ad(i, 3000, 500))
        assert any(
            BreadthSignal.OVERBOUGHT in s.signals
            for s in ind.snapshots
        )

    def test_new_highs_lows_signals(self):
        ind = BreadthIndicators(nhnl_config=NewHighsLowsConfig(high_pole_threshold=50))
        nhnl = NewHighsLows(date=date(2026, 1, 1), new_highs=80, new_lows=10)
        snap = ind.process_day(self._make_ad(0, 2000, 1500), nhnl=nhnl)
        assert BreadthSignal.NEW_HIGH_POLE in snap.signals

    def test_new_low_pole_signal(self):
        ind = BreadthIndicators(nhnl_config=NewHighsLowsConfig(low_pole_threshold=50))
        nhnl = NewHighsLows(date=date(2026, 1, 1), new_highs=5, new_lows=80)
        snap = ind.process_day(self._make_ad(0, 1000, 2500), nhnl=nhnl)
        assert BreadthSignal.NEW_LOW_POLE in snap.signals

    def test_breadth_thrust_detection(self):
        ind = BreadthIndicators(thrust_config=ThrustConfig(
            ema_period=5, low_threshold=0.35, high_threshold=0.60,
        ))
        # Bearish days to push EMA below threshold
        for i in range(10):
            ind.process_day(self._make_ad(i, 800, 2500))

        # Strong bullish surge
        found_thrust = False
        for i in range(10, 30):
            snap = ind.process_day(self._make_ad(i, 3000, 500))
            if snap.thrust and snap.thrust.thrust_active:
                found_thrust = True
                break
        assert found_thrust

    def test_nhnl_moving_average(self):
        ind = BreadthIndicators()
        for i in range(5):
            nhnl = NewHighsLows(
                date=date(2026, 1, 1) + timedelta(days=i),
                new_highs=50 + i * 10,
                new_lows=20,
            )
            ind.process_day(self._make_ad(i, 2000, 1500), nhnl=nhnl)

        ma = ind.get_nhnl_moving_average()
        assert ma > 0  # Positive NH-NL average

    def test_bar_count(self):
        ind = BreadthIndicators()
        for i in range(5):
            ind.process_day(self._make_ad(i, 2000, 1500))
        assert ind.bar_count == 5

    def test_snapshots_stored(self):
        ind = BreadthIndicators()
        for i in range(3):
            ind.process_day(self._make_ad(i, 2000, 1500))
        assert len(ind.snapshots) == 3

    def test_reset(self):
        ind = BreadthIndicators()
        for i in range(5):
            ind.process_day(self._make_ad(i, 2000, 1500))
        ind.reset()
        assert ind.bar_count == 0
        assert ind.cumulative_ad_line == 0.0
        assert ind.summation_index == 0.0
        assert len(ind.snapshots) == 0


# =========================================================================
# Health Scorer Tests
# =========================================================================


class TestHealthScorer:
    def test_neutral_market(self):
        scorer = HealthScorer()
        snap = BreadthSnapshot(
            date=date.today(),
            advance_decline=AdvanceDecline(
                date=date.today(), advancing=1500, declining=1500,
                up_volume=3_000_000, down_volume=3_000_000,
            ),
            mcclellan=McClellanData(date=date.today(), oscillator=0.0),
            thrust=BreadthThrustData(date=date.today(), breadth_ema=0.50),
        )
        health = scorer.score(snap)
        assert 35 <= health.score <= 65
        assert health.level in (MarketHealthLevel.NEUTRAL, MarketHealthLevel.BULLISH)

    def test_bullish_market(self):
        scorer = HealthScorer()
        snap = BreadthSnapshot(
            date=date.today(),
            advance_decline=AdvanceDecline(
                date=date.today(), advancing=2500, declining=800,
                up_volume=6_000_000, down_volume=2_000_000,
            ),
            new_highs_lows=NewHighsLows(date=date.today(), new_highs=120, new_lows=10),
            mcclellan=McClellanData(date=date.today(), oscillator=80.0),
            thrust=BreadthThrustData(date=date.today(), breadth_ema=0.65),
        )
        health = scorer.score(snap)
        assert health.score >= 60
        assert health.level in (MarketHealthLevel.BULLISH, MarketHealthLevel.VERY_BULLISH)

    def test_bearish_market(self):
        scorer = HealthScorer()
        snap = BreadthSnapshot(
            date=date.today(),
            advance_decline=AdvanceDecline(
                date=date.today(), advancing=800, declining=2500,
                up_volume=1_000_000, down_volume=5_000_000,
            ),
            new_highs_lows=NewHighsLows(date=date.today(), new_highs=5, new_lows=150),
            mcclellan=McClellanData(date=date.today(), oscillator=-80.0),
            thrust=BreadthThrustData(date=date.today(), breadth_ema=0.25),
        )
        health = scorer.score(snap)
        assert health.score <= 40
        assert health.level in (MarketHealthLevel.BEARISH, MarketHealthLevel.VERY_BEARISH)

    def test_thrust_boosts_score(self):
        scorer = HealthScorer()
        snap = BreadthSnapshot(
            date=date.today(),
            advance_decline=AdvanceDecline(
                date=date.today(), advancing=1500, declining=1500,
                up_volume=3_000_000, down_volume=3_000_000,
            ),
            thrust=BreadthThrustData(
                date=date.today(), breadth_ema=0.65, thrust_active=True,
            ),
        )
        health = scorer.score(snap)
        # Thrust active gives 95 thrust score which boosts composite
        assert health.thrust_score >= 90

    def test_health_to_dict(self):
        scorer = HealthScorer()
        snap = BreadthSnapshot(
            date=date.today(),
            advance_decline=AdvanceDecline(
                date=date.today(), advancing=2000, declining=1500,
                up_volume=4_000_000, down_volume=3_000_000,
            ),
        )
        health = scorer.score(snap)
        d = health.to_dict()
        assert "score" in d
        assert "level" in d
        assert "summary" in d

    def test_health_summary_text(self):
        scorer = HealthScorer()
        snap = BreadthSnapshot(
            date=date.today(),
            advance_decline=AdvanceDecline(
                date=date.today(), advancing=2000, declining=1500,
                up_volume=4_000_000, down_volume=3_000_000,
            ),
            mcclellan=McClellanData(date=date.today(), oscillator=30.0),
            signals=[BreadthSignal.ZERO_CROSS_UP],
        )
        health = scorer.score(snap)
        assert "Market health" in health.summary
        assert "McClellan" in health.summary

    def test_with_sector_breadth(self):
        scorer = HealthScorer()
        snap = BreadthSnapshot(
            date=date.today(),
            advance_decline=AdvanceDecline(
                date=date.today(), advancing=2000, declining=1500,
            ),
        )
        sectors = [
            SectorBreadth(sector="Technology", advancing=40, declining=10, breadth_score=80.0),
            SectorBreadth(sector="Financials", advancing=20, declining=30, breadth_score=40.0),
        ]
        health = scorer.score(snap, sector_breadth=sectors)
        assert len(health.sector_breadth) == 2

    def test_empty_snapshot(self):
        scorer = HealthScorer()
        snap = BreadthSnapshot(date=date.today())
        health = scorer.score(snap)
        assert health.score == 50.0  # All defaults


# =========================================================================
# Sector Breadth Tests
# =========================================================================


class TestSectorBreadthAnalyzer:
    def _sample_data(self) -> dict[str, dict[str, int]]:
        return {
            "Technology": {"advancing": 40, "declining": 10, "unchanged": 5},
            "Healthcare": {"advancing": 25, "declining": 20, "unchanged": 5},
            "Financials": {"advancing": 10, "declining": 35, "unchanged": 5},
            "Energy": {"advancing": 30, "declining": 15, "unchanged": 5},
        }

    def test_compute_sector_breadth(self):
        analyzer = SectorBreadthAnalyzer()
        results = analyzer.compute_sector_breadth(self._sample_data())
        assert len(results) == 4
        # Sorted by score descending
        assert results[0].sector == "Technology"  # 40/50 = 80%
        assert results[-1].sector == "Financials"  # 10/45 = 22.2%

    def test_sector_scores(self):
        analyzer = SectorBreadthAnalyzer()
        results = analyzer.compute_sector_breadth(self._sample_data())
        tech = [s for s in results if s.sector == "Technology"][0]
        assert tech.breadth_score == pytest.approx(80.0)

    def test_rank_sectors(self):
        analyzer = SectorBreadthAnalyzer()
        results = analyzer.compute_sector_breadth(self._sample_data())
        rankings = analyzer.rank_sectors(results)
        assert rankings[0][0] == "Technology"
        assert rankings[-1][0] == "Financials"

    def test_strongest_sectors(self):
        analyzer = SectorBreadthAnalyzer()
        results = analyzer.compute_sector_breadth(self._sample_data())
        strongest = analyzer.get_strongest_sectors(results, n=2)
        assert len(strongest) == 2
        assert strongest[0].sector == "Technology"

    def test_weakest_sectors(self):
        analyzer = SectorBreadthAnalyzer()
        results = analyzer.compute_sector_breadth(self._sample_data())
        weakest = analyzer.get_weakest_sectors(results, n=1)
        assert len(weakest) == 1
        assert weakest[0].sector == "Financials"

    def test_momentum_detection(self):
        analyzer = SectorBreadthAnalyzer()
        # First day
        analyzer.compute_sector_breadth({
            "Technology": {"advancing": 20, "declining": 30, "unchanged": 5},
        })
        # Second day: big improvement
        results = analyzer.compute_sector_breadth({
            "Technology": {"advancing": 40, "declining": 10, "unchanged": 5},
        })
        tech = results[0]
        assert tech.momentum == "improving"

    def test_deteriorating_momentum(self):
        analyzer = SectorBreadthAnalyzer()
        # First day
        analyzer.compute_sector_breadth({
            "Technology": {"advancing": 40, "declining": 10, "unchanged": 5},
        })
        # Second day: big decline
        results = analyzer.compute_sector_breadth({
            "Technology": {"advancing": 15, "declining": 35, "unchanged": 5},
        })
        tech = results[0]
        assert tech.momentum == "deteriorating"

    def test_improving_sectors_filter(self):
        analyzer = SectorBreadthAnalyzer()
        analyzer.compute_sector_breadth({
            "Technology": {"advancing": 20, "declining": 30, "unchanged": 5},
            "Energy": {"advancing": 30, "declining": 15, "unchanged": 5},
        })
        results = analyzer.compute_sector_breadth({
            "Technology": {"advancing": 40, "declining": 10, "unchanged": 5},
            "Energy": {"advancing": 30, "declining": 15, "unchanged": 5},
        })
        improving = analyzer.get_improving_sectors(results)
        assert any(s.sector == "Technology" for s in improving)

    def test_clear_history(self):
        analyzer = SectorBreadthAnalyzer()
        analyzer.compute_sector_breadth(self._sample_data())
        analyzer.clear_history()
        # After clear, momentum should be "flat"
        results = analyzer.compute_sector_breadth(self._sample_data())
        assert all(s.momentum == "flat" for s in results)


# =========================================================================
# Integration Tests
# =========================================================================


class TestIntegration:
    def test_full_workflow(self):
        """Process multiple days and score market health."""
        ind = BreadthIndicators()
        scorer = HealthScorer()
        sector_analyzer = SectorBreadthAnalyzer()

        base = date(2026, 1, 20)
        for i in range(10):
            ad = AdvanceDecline(
                date=base + timedelta(days=i),
                advancing=2000 + i * 50,
                declining=1500 - i * 30,
                unchanged=300,
                up_volume=(2000 + i * 50) * 1000.0,
                down_volume=(1500 - i * 30) * 1000.0,
            )
            nhnl = NewHighsLows(
                date=base + timedelta(days=i),
                new_highs=50 + i * 5,
                new_lows=30 - i * 2,
            )
            snap = ind.process_day(ad, nhnl=nhnl)

        # Score final snapshot
        sector_data = {
            "Technology": {"advancing": 40, "declining": 10, "unchanged": 5},
            "Financials": {"advancing": 25, "declining": 25, "unchanged": 5},
        }
        sectors = sector_analyzer.compute_sector_breadth(sector_data)
        health = scorer.score(snap, sector_breadth=sectors)

        assert health.score > 50  # Bullish trend
        assert len(health.sector_breadth) == 2
        assert ind.bar_count == 10
        assert ind.cumulative_ad_line > 0

    def test_bearish_to_bullish_reversal(self):
        """Detect signals during market reversal."""
        ind = BreadthIndicators(
            thrust_config=ThrustConfig(
                ema_period=5, low_threshold=0.35, high_threshold=0.60,
            ),
        )

        # Bearish phase
        base = date(2026, 1, 1)
        for i in range(15):
            ind.process_day(AdvanceDecline(
                date=base + timedelta(days=i),
                advancing=800, declining=2500, unchanged=200,
            ))

        # Bullish reversal
        signals_seen = set()
        for i in range(15, 40):
            snap = ind.process_day(AdvanceDecline(
                date=base + timedelta(days=i),
                advancing=2800, declining=700, unchanged=200,
            ))
            signals_seen.update(snap.signals)

        # Should see zero cross up and possibly breadth thrust
        assert BreadthSignal.ZERO_CROSS_UP in signals_seen


# =========================================================================
# Module Import Test
# =========================================================================


class TestModuleImports:
    def test_top_level_imports(self):
        from src.breadth import (
            BreadthIndicators,
            HealthScorer,
            SectorBreadthAnalyzer,
            AdvanceDecline,
            NewHighsLows,
            McClellanData,
            BreadthSnapshot,
            MarketHealth,
            SectorBreadth,
            BreadthSignal,
            MarketHealthLevel,
        )
        assert BreadthIndicators is not None
        assert HealthScorer is not None
        assert SectorBreadthAnalyzer is not None
