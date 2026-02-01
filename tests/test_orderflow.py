"""Tests for PRD-42: Order Flow Analysis."""

import pytest
import numpy as np
import pandas as pd

from src.orderflow.config import (
    FlowSignal,
    ImbalanceType,
    BlockSize,
    PressureDirection,
    ImbalanceConfig,
    BlockConfig,
    PressureConfig,
    OrderFlowConfig,
    DEFAULT_IMBALANCE_CONFIG,
    DEFAULT_BLOCK_CONFIG,
    DEFAULT_PRESSURE_CONFIG,
    DEFAULT_CONFIG,
)
from src.orderflow.models import (
    OrderBookSnapshot,
    BlockTrade,
    FlowPressure,
    SmartMoneySignal,
    OrderFlowSnapshot,
)
from src.orderflow.imbalance import ImbalanceAnalyzer
from src.orderflow.blocks import BlockDetector
from src.orderflow.pressure import PressureAnalyzer


# ===========================================================================
# Config Tests
# ===========================================================================

class TestConfig:
    """Test configuration enums and dataclasses."""

    def test_flow_signal_values(self):
        assert FlowSignal.STRONG_BUY.value == "strong_buy"
        assert FlowSignal.BUY.value == "buy"
        assert FlowSignal.NEUTRAL.value == "neutral"
        assert FlowSignal.SELL.value == "sell"
        assert FlowSignal.STRONG_SELL.value == "strong_sell"

    def test_imbalance_type_values(self):
        assert ImbalanceType.BID_HEAVY.value == "bid_heavy"
        assert ImbalanceType.ASK_HEAVY.value == "ask_heavy"
        assert ImbalanceType.BALANCED.value == "balanced"

    def test_block_size_values(self):
        assert BlockSize.SMALL.value == "small"
        assert BlockSize.MEDIUM.value == "medium"
        assert BlockSize.LARGE.value == "large"
        assert BlockSize.INSTITUTIONAL.value == "institutional"

    def test_pressure_direction_values(self):
        assert PressureDirection.BUYING.value == "buying"
        assert PressureDirection.SELLING.value == "selling"
        assert PressureDirection.NEUTRAL.value == "neutral"

    def test_imbalance_config_defaults(self):
        cfg = ImbalanceConfig()
        assert cfg.bid_heavy_threshold == 1.5
        assert cfg.ask_heavy_threshold == 0.67
        assert cfg.smoothing_window == 5

    def test_block_config_defaults(self):
        cfg = BlockConfig()
        assert cfg.medium_threshold == 10_000
        assert cfg.institutional_threshold == 100_000

    def test_pressure_config_defaults(self):
        cfg = PressureConfig()
        assert cfg.window == 20
        assert cfg.strong_buying_threshold == 1.5

    def test_orderflow_config_bundles(self):
        cfg = OrderFlowConfig()
        assert isinstance(cfg.imbalance, ImbalanceConfig)
        assert isinstance(cfg.block, BlockConfig)
        assert isinstance(cfg.pressure, PressureConfig)

    def test_default_config_exists(self):
        assert DEFAULT_CONFIG.imbalance.bid_heavy_threshold == 1.5


# ===========================================================================
# Model Tests
# ===========================================================================

class TestModels:
    """Test data models."""

    def test_orderbook_snapshot_properties(self):
        snap = OrderBookSnapshot(bid_volume=50000, ask_volume=30000)
        assert snap.total_volume == 80000
        assert snap.net_imbalance == 20000

    def test_orderbook_snapshot_to_dict(self):
        snap = OrderBookSnapshot(symbol="AAPL", imbalance_ratio=1.67, imbalance_type=ImbalanceType.BID_HEAVY)
        d = snap.to_dict()
        assert d["symbol"] == "AAPL"
        assert d["imbalance_type"] == "bid_heavy"

    def test_block_trade_institutional(self):
        bt = BlockTrade(block_size=BlockSize.INSTITUTIONAL)
        assert bt.is_institutional is True
        bt2 = BlockTrade(block_size=BlockSize.LARGE)
        assert bt2.is_institutional is False

    def test_block_trade_to_dict(self):
        bt = BlockTrade(symbol="MSFT", size=150000, side="buy", block_size=BlockSize.INSTITUTIONAL)
        d = bt.to_dict()
        assert d["is_institutional"] is True
        assert d["side"] == "buy"

    def test_flow_pressure_properties(self):
        fp = FlowPressure(buy_volume=60000, sell_volume=40000)
        assert fp.total_volume == 100000
        assert fp.buy_pct == 60.0

    def test_flow_pressure_to_dict(self):
        fp = FlowPressure(symbol="SPY", net_flow=20000, direction=PressureDirection.BUYING)
        d = fp.to_dict()
        assert d["direction"] == "buying"

    def test_smart_money_signal_to_dict(self):
        sm = SmartMoneySignal(symbol="AAPL", signal=FlowSignal.BUY, confidence=0.75)
        d = sm.to_dict()
        assert d["signal"] == "buy"
        assert d["confidence"] == 0.75

    def test_orderflow_snapshot_to_dict(self):
        snap = OrderFlowSnapshot(
            symbol="TEST",
            book=OrderBookSnapshot(symbol="TEST", bid_volume=100),
            n_blocks=5,
        )
        d = snap.to_dict()
        assert d["book"] is not None
        assert d["n_blocks"] == 5
        assert d["pressure"] is None


# ===========================================================================
# Imbalance Analyzer Tests
# ===========================================================================

class TestImbalanceAnalyzer:
    """Test order book imbalance analysis."""

    def test_bid_heavy(self):
        analyzer = ImbalanceAnalyzer()
        snap = analyzer.compute_imbalance(50000, 20000, symbol="TEST")
        assert snap.imbalance_type == ImbalanceType.BID_HEAVY
        assert snap.imbalance_ratio > 1.5

    def test_ask_heavy(self):
        analyzer = ImbalanceAnalyzer()
        snap = analyzer.compute_imbalance(20000, 50000, symbol="TEST")
        assert snap.imbalance_type == ImbalanceType.ASK_HEAVY
        assert snap.imbalance_ratio < 0.67

    def test_balanced(self):
        analyzer = ImbalanceAnalyzer()
        snap = analyzer.compute_imbalance(40000, 42000, symbol="TEST")
        assert snap.imbalance_type == ImbalanceType.BALANCED

    def test_strong_buy_signal(self):
        analyzer = ImbalanceAnalyzer()
        snap = analyzer.compute_imbalance(90000, 20000)
        assert snap.signal == FlowSignal.STRONG_BUY

    def test_strong_sell_signal(self):
        analyzer = ImbalanceAnalyzer()
        snap = analyzer.compute_imbalance(20000, 90000)
        assert snap.signal == FlowSignal.STRONG_SELL

    def test_neutral_signal(self):
        analyzer = ImbalanceAnalyzer()
        snap = analyzer.compute_imbalance(40000, 40000)
        assert snap.signal == FlowSignal.NEUTRAL

    def test_zero_ask_volume(self):
        analyzer = ImbalanceAnalyzer()
        snap = analyzer.compute_imbalance(50000, 0)
        assert snap.imbalance_type == ImbalanceType.BID_HEAVY

    def test_zero_both(self):
        analyzer = ImbalanceAnalyzer()
        snap = analyzer.compute_imbalance(0, 0)
        assert snap.imbalance_type == ImbalanceType.BALANCED

    def test_rolling_imbalance(self):
        analyzer = ImbalanceAnalyzer()
        bids = pd.Series([50000, 55000, 60000, 45000, 70000])
        asks = pd.Series([30000, 35000, 40000, 50000, 25000])
        results = analyzer.rolling_imbalance(bids, asks, symbol="ROLL")
        assert len(results) == 5

    def test_history(self):
        analyzer = ImbalanceAnalyzer()
        analyzer.compute_imbalance(50000, 30000)
        analyzer.compute_imbalance(30000, 50000)
        assert len(analyzer.get_history()) == 2

    def test_reset(self):
        analyzer = ImbalanceAnalyzer()
        analyzer.compute_imbalance(50000, 30000)
        analyzer.reset()
        assert len(analyzer.get_history()) == 0


# ===========================================================================
# Block Detector Tests
# ===========================================================================

class TestBlockDetector:
    """Test block trade detection."""

    def test_detect_blocks(self):
        detector = BlockDetector()
        sizes = pd.Series([500, 15000, 75000, 150000, 8000])
        prices = pd.Series([10.0, 10.0, 10.0, 10.0, 10.0])
        sides = pd.Series(["buy", "buy", "sell", "buy", "sell"])
        blocks = detector.detect_blocks(sizes, prices, sides, symbol="TEST")
        # 500 and 8000 are small, should be filtered
        assert len(blocks) == 3
        sizes_found = {b.size for b in blocks}
        assert 15000 in sizes_found
        assert 75000 in sizes_found
        assert 150000 in sizes_found

    def test_classify_medium(self):
        detector = BlockDetector()
        blocks = detector.detect_blocks(
            pd.Series([15000]), pd.Series([10.0]), pd.Series(["buy"])
        )
        assert blocks[0].block_size == BlockSize.MEDIUM

    def test_classify_large(self):
        detector = BlockDetector()
        blocks = detector.detect_blocks(
            pd.Series([75000]), pd.Series([10.0]), pd.Series(["sell"])
        )
        assert blocks[0].block_size == BlockSize.LARGE

    def test_classify_institutional_by_shares(self):
        detector = BlockDetector()
        blocks = detector.detect_blocks(
            pd.Series([150000]), pd.Series([50.0]), pd.Series(["buy"])
        )
        assert blocks[0].block_size == BlockSize.INSTITUTIONAL

    def test_classify_institutional_by_dollars(self):
        detector = BlockDetector()
        # 20000 shares * $100 = $2M > $1M threshold
        blocks = detector.detect_blocks(
            pd.Series([20000]), pd.Series([100.0]), pd.Series(["buy"])
        )
        assert blocks[0].block_size == BlockSize.INSTITUTIONAL

    def test_no_blocks_all_small(self):
        detector = BlockDetector()
        blocks = detector.detect_blocks(
            pd.Series([100, 200, 500]), pd.Series([150.0, 150.0, 150.0]),
            pd.Series(["buy", "sell", "buy"])
        )
        assert len(blocks) == 0

    def test_smart_money_buy_signal(self):
        detector = BlockDetector()
        blocks = [
            BlockTrade(size=150000, side="buy", block_size=BlockSize.INSTITUTIONAL),
            BlockTrade(size=120000, side="buy", block_size=BlockSize.INSTITUTIONAL),
            BlockTrade(size=100000, side="sell", block_size=BlockSize.INSTITUTIONAL),
        ]
        signal = detector.compute_smart_money(blocks, total_volume=1_000_000, symbol="SPY")
        assert signal.signal in (FlowSignal.BUY, FlowSignal.STRONG_BUY)
        assert signal.institutional_buy_pct > 50

    def test_smart_money_sell_signal(self):
        detector = BlockDetector()
        blocks = [
            BlockTrade(size=150000, side="sell", block_size=BlockSize.INSTITUTIONAL),
            BlockTrade(size=120000, side="sell", block_size=BlockSize.INSTITUTIONAL),
            BlockTrade(size=50000, side="buy", block_size=BlockSize.INSTITUTIONAL),
        ]
        signal = detector.compute_smart_money(blocks, total_volume=1_000_000)
        assert signal.signal in (FlowSignal.SELL, FlowSignal.STRONG_SELL)

    def test_smart_money_no_blocks(self):
        detector = BlockDetector()
        signal = detector.compute_smart_money([], symbol="EMPTY")
        assert signal.signal == FlowSignal.NEUTRAL
        assert signal.confidence == 0.0


# ===========================================================================
# Pressure Analyzer Tests
# ===========================================================================

class TestPressureAnalyzer:
    """Test buy/sell pressure analysis."""

    def test_buying_pressure(self):
        analyzer = PressureAnalyzer()
        flow = analyzer.compute_pressure(80000, 40000, symbol="BUY")
        assert flow.direction == PressureDirection.BUYING
        assert flow.net_flow > 0
        assert flow.pressure_ratio > 1.5

    def test_selling_pressure(self):
        analyzer = PressureAnalyzer()
        flow = analyzer.compute_pressure(30000, 70000, symbol="SELL")
        assert flow.direction == PressureDirection.SELLING
        assert flow.net_flow < 0

    def test_neutral_pressure(self):
        analyzer = PressureAnalyzer()
        flow = analyzer.compute_pressure(50000, 50000)
        assert flow.direction == PressureDirection.NEUTRAL

    def test_cumulative_delta(self):
        analyzer = PressureAnalyzer()
        analyzer.compute_pressure(60000, 40000)  # +20k
        analyzer.compute_pressure(30000, 50000)  # -20k
        flow = analyzer.compute_pressure(70000, 30000)  # +40k
        assert flow.cumulative_delta == pytest.approx(40000, abs=1)

    def test_compute_series(self):
        analyzer = PressureAnalyzer()
        buys = pd.Series([60000, 30000, 70000, 50000, 80000])
        sells = pd.Series([40000, 50000, 30000, 50000, 20000])
        results = analyzer.compute_series(buys, sells, symbol="SER")
        assert len(results) == 5
        # Last cumulative delta should be sum of net flows
        expected_delta = (60000-40000) + (30000-50000) + (70000-30000) + (50000-50000) + (80000-20000)
        assert results[-1].cumulative_delta == pytest.approx(expected_delta, abs=1)

    def test_smoothed_ratio(self):
        analyzer = PressureAnalyzer()
        buys = pd.Series([60000, 30000, 70000, 50000, 80000])
        sells = pd.Series([40000, 50000, 30000, 50000, 20000])
        smoothed = analyzer.smoothed_ratio(buys, sells)
        assert len(smoothed) == 5
        assert smoothed.iloc[-1] > 0

    def test_zero_sell_volume(self):
        analyzer = PressureAnalyzer()
        flow = analyzer.compute_pressure(50000, 0)
        assert flow.direction == PressureDirection.BUYING
        assert flow.pressure_ratio == 999.0

    def test_history(self):
        analyzer = PressureAnalyzer()
        analyzer.compute_pressure(60000, 40000)
        analyzer.compute_pressure(30000, 50000)
        assert len(analyzer.get_history()) == 2

    def test_reset(self):
        analyzer = PressureAnalyzer()
        analyzer.compute_pressure(60000, 40000)
        analyzer.reset()
        assert analyzer.get_cumulative_delta() == 0.0
        assert len(analyzer.get_history()) == 0

    def test_buy_pct(self):
        analyzer = PressureAnalyzer()
        flow = analyzer.compute_pressure(60000, 40000)
        assert flow.buy_pct == 60.0


# ===========================================================================
# Integration Tests
# ===========================================================================

class TestIntegration:
    """End-to-end integration tests."""

    def test_full_order_flow_pipeline(self):
        """Imbalance -> Blocks -> Pressure -> Smart Money."""
        # Imbalance
        imb_analyzer = ImbalanceAnalyzer()
        book = imb_analyzer.compute_imbalance(60000, 35000, symbol="SPY")
        assert book.imbalance_type == ImbalanceType.BID_HEAVY

        # Blocks
        detector = BlockDetector()
        sizes = pd.Series([150000, 80000, 5000, 200000])
        prices = pd.Series([450.0, 450.0, 450.0, 450.0])
        sides = pd.Series(["buy", "buy", "sell", "buy"])
        blocks = detector.detect_blocks(sizes, prices, sides, symbol="SPY")
        assert len(blocks) >= 2

        smart = detector.compute_smart_money(blocks, total_volume=2_000_000, symbol="SPY")
        assert smart.signal in (FlowSignal.BUY, FlowSignal.STRONG_BUY)

        # Pressure
        pressure = PressureAnalyzer()
        flow = pressure.compute_pressure(100000, 60000, symbol="SPY")
        assert flow.direction == PressureDirection.BUYING

        # Snapshot
        snap = OrderFlowSnapshot(
            symbol="SPY",
            book=book,
            pressure=flow,
            smart_money=smart,
            n_blocks=len(blocks),
        )
        d = snap.to_dict()
        assert d["symbol"] == "SPY"
        assert d["n_blocks"] >= 2

    def test_series_consistency(self):
        """Verify cumulative delta matches sum of net flows."""
        analyzer = PressureAnalyzer()
        buys = pd.Series([50000, 60000, 40000, 70000])
        sells = pd.Series([40000, 50000, 60000, 30000])
        results = analyzer.compute_series(buys, sells)

        total_net = sum(float(buys.iloc[i] - sells.iloc[i]) for i in range(4))
        assert results[-1].cumulative_delta == pytest.approx(total_net, abs=1)


# ===========================================================================
# Module Import Tests
# ===========================================================================

class TestModuleImports:
    """Test module imports work correctly."""

    def test_top_level_imports(self):
        from src.orderflow import (
            ImbalanceAnalyzer,
            BlockDetector,
            PressureAnalyzer,
            FlowSignal,
            ImbalanceType,
            BlockSize,
            PressureDirection,
            OrderBookSnapshot,
            BlockTrade,
            FlowPressure,
            SmartMoneySignal,
            OrderFlowSnapshot,
            DEFAULT_CONFIG,
        )
        assert ImbalanceAnalyzer is not None
        assert BlockDetector is not None
        assert PressureAnalyzer is not None
