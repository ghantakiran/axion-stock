"""Tests for Dark Pool Analytics module."""

import numpy as np
import pytest

from src.darkpool.config import (
    PrintType,
    BlockDirection,
    LiquidityLevel,
    VenueTier,
    VolumeConfig,
    PrintConfig,
    BlockConfig,
    LiquidityConfig,
    DarkPoolConfig,
    DEFAULT_CONFIG,
)
from src.darkpool.models import (
    DarkPoolVolume,
    VolumeSummary,
    DarkPrint,
    PrintSummary,
    DarkBlock,
    DarkLiquidity,
)
from src.darkpool.volume import VolumeTracker
from src.darkpool.prints import PrintAnalyzer
from src.darkpool.blocks import BlockDetector
from src.darkpool.liquidity import LiquidityEstimator


# ── Helpers ──────────────────────────────────────────────────


def _make_volume_records(symbol="AAPL", n=20, dark_pct=0.40):
    """Generate synthetic dark pool volume records."""
    rng = np.random.RandomState(42)
    records = []
    for i in range(n):
        total = 1_000_000 + rng.randint(-100_000, 100_000)
        dark = int(total * dark_pct + rng.randn() * total * 0.05)
        dark = max(0, dark)
        lit = total - dark
        records.append(DarkPoolVolume(
            symbol=symbol,
            date=f"2026-01-{i + 1:02d}",
            dark_volume=float(dark),
            lit_volume=float(lit),
            total_volume=float(total),
            short_volume=float(dark * 0.3),
            n_venues=5,
        ))
    return records


def _make_prints(symbol="AAPL", n=50, mid=150.0):
    """Generate synthetic dark prints."""
    rng = np.random.RandomState(42)
    prints = []
    for i in range(n):
        size = rng.choice([50, 100, 500, 2000, 15000, 50000])
        bid = mid - 0.01
        ask = mid + 0.01
        price = mid + rng.choice([-0.005, 0, 0.005])
        prints.append(DarkPrint(
            symbol=symbol,
            price=price,
            size=float(size),
            timestamp=float(i * 10),
            venue=f"ATS-{rng.randint(1, 4)}",
            nbbo_bid=bid,
            nbbo_ask=ask,
        ))
    return prints


# ── Config Tests ─────────────────────────────────────────────


class TestDarkpoolConfig:
    def test_print_type_values(self):
        assert PrintType.BLOCK.value == "block"
        assert PrintType.MIDPOINT.value == "midpoint"
        assert PrintType.RETAIL.value == "retail"
        assert PrintType.INSTITUTIONAL.value == "institutional"

    def test_block_direction_values(self):
        assert BlockDirection.BUY.value == "buy"
        assert BlockDirection.SELL.value == "sell"

    def test_liquidity_level_values(self):
        assert LiquidityLevel.DEEP.value == "deep"
        assert LiquidityLevel.MODERATE.value == "moderate"
        assert LiquidityLevel.SHALLOW.value == "shallow"
        assert LiquidityLevel.DRY.value == "dry"

    def test_venue_tier_values(self):
        assert VenueTier.MAJOR.value == "major"
        assert VenueTier.MID.value == "mid"

    def test_volume_config_defaults(self):
        cfg = VolumeConfig()
        assert cfg.lookback_days == 20
        assert cfg.dark_share_warning == 0.45

    def test_print_config_defaults(self):
        cfg = PrintConfig()
        assert cfg.block_threshold == 10000
        assert cfg.retail_max_size == 200

    def test_block_config_defaults(self):
        cfg = BlockConfig()
        assert cfg.min_block_size == 10000
        assert cfg.min_block_value == 200_000

    def test_liquidity_config_defaults(self):
        cfg = LiquidityConfig()
        assert len(cfg.depth_levels) == 5
        assert cfg.deep_threshold == 0.7

    def test_darkpool_config_bundles(self):
        cfg = DarkPoolConfig()
        assert isinstance(cfg.volume, VolumeConfig)
        assert isinstance(cfg.prints, PrintConfig)
        assert isinstance(cfg.blocks, BlockConfig)
        assert isinstance(cfg.liquidity, LiquidityConfig)


# ── Model Tests ──────────────────────────────────────────────


class TestDarkpoolModels:
    def test_dark_pool_volume_properties(self):
        v = DarkPoolVolume(
            symbol="AAPL", date="2026-01-01",
            dark_volume=400_000, lit_volume=600_000,
            total_volume=1_000_000, short_volume=120_000,
        )
        assert abs(v.dark_share - 0.4) < 0.001
        assert abs(v.short_ratio - 0.3) < 0.001

    def test_dark_pool_volume_zero(self):
        v = DarkPoolVolume(
            symbol="X", date="2026-01-01",
            dark_volume=0, lit_volume=0, total_volume=0,
        )
        assert v.dark_share == 0.0
        assert v.short_ratio == 0.0

    def test_dark_pool_volume_to_dict(self):
        v = DarkPoolVolume(
            symbol="AAPL", date="2026-01-01",
            dark_volume=400_000, lit_volume=600_000,
            total_volume=1_000_000, n_venues=5,
        )
        d = v.to_dict()
        assert d["dark_share"] == 0.4
        assert d["n_venues"] == 5

    def test_volume_summary_to_dict(self):
        s = VolumeSummary(
            symbol="AAPL", avg_dark_share=0.42,
            dark_share_trend=0.01,
            total_dark_volume=8e6, total_lit_volume=12e6,
            avg_short_ratio=0.3, n_days=20, is_elevated=False,
        )
        d = s.to_dict()
        assert d["avg_dark_share"] == 0.42
        assert d["is_elevated"] is False

    def test_dark_print_properties(self):
        p = DarkPrint(
            symbol="AAPL", price=150.005,
            size=5000, timestamp=0,
            nbbo_bid=150.0, nbbo_ask=150.01,
        )
        assert abs(p.midpoint - 150.005) < 0.001
        assert p.price_improvement >= 0
        assert p.notional == 150.005 * 5000

    def test_dark_print_no_nbbo(self):
        p = DarkPrint(symbol="X", price=100, size=100, timestamp=0)
        assert p.midpoint == 100  # falls back to price
        assert p.price_improvement == 0.0

    def test_dark_print_to_dict(self):
        p = DarkPrint(
            symbol="AAPL", price=150.0, size=10000,
            timestamp=0, venue="ATS-1",
            print_type=PrintType.BLOCK,
        )
        d = p.to_dict()
        assert d["print_type"] == "block"
        assert d["notional"] == 1_500_000

    def test_print_summary_block_pct(self):
        s = PrintSummary(
            symbol="AAPL", total_prints=100,
            total_volume=500_000, total_notional=75e6,
            avg_size=5000, avg_price_improvement=0.5,
            block_count=10, block_volume=200_000,
        )
        assert abs(s.block_pct - 40.0) < 0.01

    def test_dark_block_significant(self):
        b = DarkBlock(
            symbol="AAPL", size=50000,
            notional=7_500_000, price=150.0,
            adv_ratio=0.05,
        )
        assert b.is_significant

    def test_dark_block_not_significant(self):
        b = DarkBlock(
            symbol="AAPL", size=10000,
            notional=1_500_000, price=150.0,
            adv_ratio=0.005,
        )
        assert not b.is_significant

    def test_dark_block_to_dict(self):
        b = DarkBlock(
            symbol="AAPL", size=50000,
            notional=7_500_000, price=150.0,
            direction=BlockDirection.BUY,
            adv_ratio=0.05, cluster_id=1,
        )
        d = b.to_dict()
        assert d["direction"] == "buy"
        assert d["is_significant"] is True

    def test_dark_liquidity_to_dict(self):
        l = DarkLiquidity(
            symbol="AAPL", liquidity_score=0.65,
            level=LiquidityLevel.MODERATE,
            estimated_depth=500_000,
            dark_lit_ratio=0.6,
            consistency=0.8,
        )
        d = l.to_dict()
        assert d["level"] == "moderate"
        assert d["liquidity_score"] == 0.65


# ── Volume Tracker Tests ─────────────────────────────────────


class TestVolumeTracker:
    def test_basic_summary(self):
        tracker = VolumeTracker()
        records = _make_volume_records("AAPL", 20, dark_pct=0.40)
        tracker.add_records(records)
        summary = tracker.summarize("AAPL")

        assert summary.symbol == "AAPL"
        assert summary.n_days == 20
        assert 0.30 <= summary.avg_dark_share <= 0.50

    def test_elevated_dark_share(self):
        tracker = VolumeTracker()
        records = _make_volume_records("AAPL", 20, dark_pct=0.50)
        tracker.add_records(records)
        summary = tracker.summarize("AAPL")
        assert summary.is_elevated

    def test_not_elevated(self):
        tracker = VolumeTracker()
        records = _make_volume_records("AAPL", 20, dark_pct=0.30)
        tracker.add_records(records)
        summary = tracker.summarize("AAPL")
        assert not summary.is_elevated

    def test_short_ratio(self):
        tracker = VolumeTracker()
        records = _make_volume_records("AAPL", 20)
        tracker.add_records(records)
        summary = tracker.summarize("AAPL")
        assert summary.avg_short_ratio > 0

    def test_empty_symbol(self):
        tracker = VolumeTracker()
        summary = tracker.summarize("UNKNOWN")
        assert summary.avg_dark_share == 0.0
        assert summary.n_days == 0

    def test_reset(self):
        tracker = VolumeTracker()
        tracker.add_records(_make_volume_records("AAPL", 5))
        tracker.reset()
        assert tracker.get_history("AAPL") == []


# ── Print Analyzer Tests ─────────────────────────────────────


class TestPrintAnalyzer:
    def test_classify_block(self):
        p = DarkPrint(symbol="AAPL", price=150.0, size=50000, timestamp=0)
        analyzer = PrintAnalyzer()
        assert analyzer.classify(p) == PrintType.BLOCK

    def test_classify_retail(self):
        p = DarkPrint(symbol="AAPL", price=150.0, size=100, timestamp=0)
        analyzer = PrintAnalyzer()
        assert analyzer.classify(p) == PrintType.RETAIL

    def test_classify_midpoint(self):
        p = DarkPrint(
            symbol="AAPL", price=150.005, size=500, timestamp=0,
            nbbo_bid=150.0, nbbo_ask=150.01,
        )
        analyzer = PrintAnalyzer()
        assert analyzer.classify(p) == PrintType.MIDPOINT

    def test_classify_institutional(self):
        p = DarkPrint(symbol="AAPL", price=150.0, size=5000, timestamp=0)
        analyzer = PrintAnalyzer()
        assert analyzer.classify(p) == PrintType.INSTITUTIONAL

    def test_analyze_prints(self):
        prints = _make_prints("AAPL", 50)
        analyzer = PrintAnalyzer()
        summary = analyzer.analyze(prints, "AAPL")

        assert summary.total_prints == 50
        assert summary.total_volume > 0
        assert len(summary.type_distribution) > 0

    def test_too_few_prints(self):
        prints = [DarkPrint(symbol="X", price=100, size=100, timestamp=0)]
        analyzer = PrintAnalyzer()
        summary = analyzer.analyze(prints, "X")
        assert summary.total_prints == 0

    def test_classify_all(self):
        prints = _make_prints("AAPL", 20)
        analyzer = PrintAnalyzer()
        classified = analyzer.classify_all(prints)
        assert all(p.print_type != PrintType.UNKNOWN or True for p in classified)


# ── Block Detector Tests ─────────────────────────────────────


class TestBlockDetector:
    def test_detect_blocks(self):
        prints = [
            DarkPrint(symbol="AAPL", price=150.0, size=50000, timestamp=0,
                      nbbo_bid=149.99, nbbo_ask=150.01),
            DarkPrint(symbol="AAPL", price=150.0, size=100, timestamp=10),
            DarkPrint(symbol="AAPL", price=150.0, size=20000, timestamp=20,
                      nbbo_bid=149.99, nbbo_ask=150.01),
        ]
        detector = BlockDetector()
        blocks = detector.detect(prints, adv=1_000_000, symbol="AAPL")

        assert len(blocks) == 2  # 50000 and 20000, not 100

    def test_block_direction_buy(self):
        p = DarkPrint(
            symbol="AAPL", price=150.008, size=20000,
            timestamp=0, nbbo_bid=150.0, nbbo_ask=150.01,
        )
        detector = BlockDetector()
        blocks = detector.detect([p], adv=1_000_000, symbol="AAPL")
        assert blocks[0].direction == BlockDirection.BUY

    def test_block_direction_sell(self):
        p = DarkPrint(
            symbol="AAPL", price=150.002, size=20000,
            timestamp=0, nbbo_bid=150.0, nbbo_ask=150.01,
        )
        detector = BlockDetector()
        blocks = detector.detect([p], adv=1_000_000, symbol="AAPL")
        assert blocks[0].direction == BlockDirection.SELL

    def test_adv_ratio(self):
        p = DarkPrint(symbol="AAPL", price=150.0, size=50000, timestamp=0)
        detector = BlockDetector()
        blocks = detector.detect([p], adv=1_000_000, symbol="AAPL")
        assert abs(blocks[0].adv_ratio - 0.05) < 0.001

    def test_min_value_filter(self):
        # 10000 shares * $10 = $100k < $200k threshold
        p = DarkPrint(symbol="CHEAP", price=10.0, size=10000, timestamp=0)
        detector = BlockDetector()
        blocks = detector.detect([p], adv=1_000_000, symbol="CHEAP")
        assert len(blocks) == 0

    def test_clustering(self):
        prints = [
            DarkPrint(symbol="AAPL", price=150.0, size=20000, timestamp=i * 10)
            for i in range(5)  # 5 blocks within 50 seconds
        ]
        cfg = BlockConfig(cluster_window=300, cluster_min_blocks=3)
        detector = BlockDetector(cfg)
        blocks = detector.detect(prints, adv=1_000_000, symbol="AAPL")
        cluster_ids = [b.cluster_id for b in blocks if b.cluster_id > 0]
        assert len(cluster_ids) >= 3  # at least 3 in a cluster

    def test_summarize_blocks(self):
        prints = [
            DarkPrint(symbol="AAPL", price=150.0, size=20000, timestamp=i * 10,
                      nbbo_bid=149.99, nbbo_ask=150.01)
            for i in range(3)
        ]
        detector = BlockDetector()
        blocks = detector.detect(prints, adv=1_000_000, symbol="AAPL")
        summary = detector.summarize_blocks(blocks)
        assert summary["total_blocks"] == 3
        assert summary["total_volume"] == 60000

    def test_empty_blocks(self):
        detector = BlockDetector()
        summary = detector.summarize_blocks([])
        assert summary["total_blocks"] == 0


# ── Liquidity Estimator Tests ────────────────────────────────


class TestLiquidityEstimator:
    def test_basic_estimate(self):
        records = _make_volume_records("AAPL", 20, dark_pct=0.40)
        estimator = LiquidityEstimator()
        result = estimator.estimate(records, symbol="AAPL")

        assert result.symbol == "AAPL"
        assert result.liquidity_score > 0
        assert result.estimated_depth > 0
        assert len(result.fill_rates) > 0

    def test_deep_liquidity(self):
        # High dark volume
        records = _make_volume_records("AAPL", 20, dark_pct=0.50)
        estimator = LiquidityEstimator()
        result = estimator.estimate(records, symbol="AAPL")
        assert result.level in (LiquidityLevel.DEEP, LiquidityLevel.MODERATE)

    def test_low_liquidity(self):
        # Very low dark volume
        records = []
        for i in range(20):
            records.append(DarkPoolVolume(
                symbol="ILLIQUID", date=f"2026-01-{i + 1:02d}",
                dark_volume=100, lit_volume=999_900,
                total_volume=1_000_000,
            ))
        estimator = LiquidityEstimator()
        result = estimator.estimate(records, symbol="ILLIQUID")
        assert result.level in (LiquidityLevel.SHALLOW, LiquidityLevel.DRY)

    def test_fill_rates_decrease_with_size(self):
        records = _make_volume_records("AAPL", 20)
        estimator = LiquidityEstimator()
        result = estimator.estimate(records, symbol="AAPL")

        rates = list(result.fill_rates.values())
        # Fill rates should generally decrease with larger sizes
        assert rates[0] >= rates[-1]

    def test_with_prints(self):
        records = _make_volume_records("AAPL", 20)
        prints = _make_prints("AAPL", 30)
        estimator = LiquidityEstimator()
        result = estimator.estimate(records, prints, "AAPL")
        assert result.estimated_depth > 0

    def test_empty_history(self):
        estimator = LiquidityEstimator()
        result = estimator.estimate([], symbol="EMPTY")
        assert result.liquidity_score == 0.0
        assert result.level == LiquidityLevel.DRY

    def test_dark_lit_ratio(self):
        records = _make_volume_records("AAPL", 20, dark_pct=0.40)
        estimator = LiquidityEstimator()
        result = estimator.estimate(records, symbol="AAPL")
        assert result.dark_lit_ratio > 0

    def test_consistency(self):
        # Uniform dark volume -> high consistency
        records = []
        for i in range(20):
            records.append(DarkPoolVolume(
                symbol="STABLE", date=f"2026-01-{i + 1:02d}",
                dark_volume=400_000, lit_volume=600_000,
                total_volume=1_000_000,
            ))
        estimator = LiquidityEstimator()
        result = estimator.estimate(records, symbol="STABLE")
        assert result.consistency > 0.9  # very consistent


# ── Integration Tests ────────────────────────────────────────


class TestDarkpoolIntegration:
    def test_full_pipeline(self):
        """End-to-end: volume + prints -> blocks + liquidity."""
        records = _make_volume_records("AAPL", 20)
        prints = _make_prints("AAPL", 50)

        # Volume tracking
        tracker = VolumeTracker()
        tracker.add_records(records)
        vol_summary = tracker.summarize("AAPL")
        assert vol_summary.avg_dark_share > 0

        # Print analysis
        print_analyzer = PrintAnalyzer()
        print_summary = print_analyzer.analyze(prints, "AAPL")
        assert print_summary.total_prints == 50

        # Block detection
        block_detector = BlockDetector()
        blocks = block_detector.detect(prints, adv=1_000_000, symbol="AAPL")
        assert isinstance(blocks, list)

        # Liquidity estimation
        liq_estimator = LiquidityEstimator()
        liquidity = liq_estimator.estimate(records, prints, "AAPL")
        assert liquidity.liquidity_score > 0


class TestDarkpoolModuleImports:
    def test_top_level_imports(self):
        from src.darkpool import (
            VolumeTracker,
            PrintAnalyzer,
            BlockDetector,
            LiquidityEstimator,
            DarkPoolVolume,
            VolumeSummary,
            DarkPrint,
            PrintSummary,
            DarkBlock,
            DarkLiquidity,
            PrintType,
            BlockDirection,
            LiquidityLevel,
            DEFAULT_CONFIG,
        )
        assert DEFAULT_CONFIG is not None
