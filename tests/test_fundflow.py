"""Tests for Fund Flow Analysis module."""

import numpy as np
import pytest

from src.fundflow.config import (
    FlowDirection,
    FlowStrength,
    RotationPhase,
    SmartMoneySignal,
    FlowTrackerConfig,
    InstitutionalConfig,
    RotationConfig,
    SmartMoneyConfig,
    FundFlowConfig,
    DEFAULT_CONFIG,
)
from src.fundflow.models import (
    FundFlow,
    FlowSummary,
    InstitutionalPosition,
    InstitutionalSummary,
    SectorRotation,
    SmartMoneyResult,
)
from src.fundflow.tracker import FlowTracker
from src.fundflow.institutional import InstitutionalAnalyzer
from src.fundflow.rotation import RotationDetector
from src.fundflow.smartmoney import SmartMoneyDetector


# ── Helpers ──────────────────────────────────────────────────


def _make_flows(fund_name="SPY", n=20, base_inflow=1e6, trend=0.0):
    """Generate synthetic fund flows."""
    rng = np.random.RandomState(42)
    flows = []
    for i in range(n):
        inflow = base_inflow + trend * i + rng.randn() * base_inflow * 0.1
        outflow = base_inflow * 0.8 + rng.randn() * base_inflow * 0.1
        flows.append(FundFlow(
            fund_name=fund_name,
            date=f"2026-01-{i + 1:02d}",
            inflow=max(0, inflow),
            outflow=max(0, outflow),
            aum=100e6,
        ))
    return flows


def _make_positions(symbol="AAPL", n=5):
    """Generate synthetic institutional positions."""
    holders = ["Vanguard", "BlackRock", "State Street", "Fidelity", "T. Rowe Price"]
    positions = []
    for i in range(n):
        positions.append(InstitutionalPosition(
            holder_name=holders[i % len(holders)],
            symbol=symbol,
            shares=1e6 * (n - i),
            market_value=150e6 * (n - i),
            ownership_pct=8.0 - i * 1.5,
            change_shares=1e5 * (2 - i),
            change_pct=10.0 - i * 5,
            quarter="Q4 2025",
        ))
    return positions


# ── Config Tests ─────────────────────────────────────────────


class TestConfig:
    def test_flow_direction_values(self):
        assert FlowDirection.INFLOW.value == "inflow"
        assert FlowDirection.OUTFLOW.value == "outflow"
        assert FlowDirection.NEUTRAL.value == "neutral"

    def test_flow_strength_values(self):
        assert FlowStrength.STRONG.value == "strong"
        assert FlowStrength.MODERATE.value == "moderate"
        assert FlowStrength.WEAK.value == "weak"

    def test_rotation_phase_values(self):
        assert RotationPhase.EARLY_CYCLE.value == "early_cycle"
        assert RotationPhase.LATE_CYCLE.value == "late_cycle"
        assert RotationPhase.RECESSION.value == "recession"

    def test_smart_money_signal_values(self):
        assert SmartMoneySignal.ACCUMULATION.value == "accumulation"
        assert SmartMoneySignal.DISTRIBUTION.value == "distribution"

    def test_tracker_config_defaults(self):
        cfg = FlowTrackerConfig()
        assert cfg.lookback_days == 20
        assert cfg.momentum_window == 5
        assert cfg.significant_flow_pct == 0.02

    def test_institutional_config_defaults(self):
        cfg = InstitutionalConfig()
        assert cfg.min_ownership_pct == 0.5
        assert cfg.top_holders_count == 10

    def test_rotation_config_defaults(self):
        cfg = RotationConfig()
        assert len(cfg.sectors) == 11
        assert "Technology" in cfg.sectors

    def test_smartmoney_config_defaults(self):
        cfg = SmartMoneyConfig()
        assert cfg.institutional_weight == 0.7
        assert cfg.retail_weight == 0.3
        assert cfg.conviction_threshold == 0.6

    def test_fundflow_config_bundles(self):
        cfg = FundFlowConfig()
        assert isinstance(cfg.tracker, FlowTrackerConfig)
        assert isinstance(cfg.institutional, InstitutionalConfig)
        assert isinstance(cfg.rotation, RotationConfig)
        assert isinstance(cfg.smartmoney, SmartMoneyConfig)


# ── Model Tests ──────────────────────────────────────────────


class TestModels:
    def test_fund_flow_properties(self):
        f = FundFlow(fund_name="SPY", date="2026-01-01",
                     inflow=1e6, outflow=0.5e6, aum=100e6)
        assert f.net_flow == 0.5e6
        assert abs(f.flow_pct - 0.5) < 0.01
        assert f.direction == FlowDirection.INFLOW

    def test_fund_flow_outflow(self):
        f = FundFlow(fund_name="SPY", date="2026-01-01",
                     inflow=0.3e6, outflow=0.8e6, aum=100e6)
        assert f.net_flow < 0
        assert f.direction == FlowDirection.OUTFLOW

    def test_fund_flow_zero_aum(self):
        f = FundFlow(fund_name="X", date="2026-01-01",
                     inflow=1e6, outflow=0, aum=0)
        assert f.flow_pct == 0.0

    def test_fund_flow_to_dict(self):
        f = FundFlow(fund_name="SPY", date="2026-01-01",
                     inflow=1e6, outflow=0.5e6, aum=100e6)
        d = f.to_dict()
        assert d["fund_name"] == "SPY"
        assert d["net_flow"] == 0.5e6
        assert d["direction"] == "inflow"

    def test_flow_summary_ratio(self):
        s = FlowSummary(name="SPY", total_inflow=10e6, total_outflow=5e6,
                        net_flow=5e6, flow_momentum=0.5,
                        cumulative_flow=5e6, avg_flow_pct=0.5)
        assert abs(s.flow_ratio - 2.0) < 0.01

    def test_flow_summary_zero_outflow(self):
        s = FlowSummary(name="SPY", total_inflow=10e6, total_outflow=0,
                        net_flow=10e6, flow_momentum=1.0,
                        cumulative_flow=10e6, avg_flow_pct=1.0)
        assert s.flow_ratio == float("inf")

    def test_flow_summary_to_dict(self):
        s = FlowSummary(name="SPY", total_inflow=10e6, total_outflow=5e6,
                        net_flow=5e6, flow_momentum=0.5,
                        cumulative_flow=5e6, avg_flow_pct=0.5,
                        strength=FlowStrength.MODERATE, n_days=20)
        d = s.to_dict()
        assert d["strength"] == "moderate"
        assert d["flow_ratio"] == 2.0

    def test_institutional_position_new(self):
        p = InstitutionalPosition(
            holder_name="Vanguard", symbol="AAPL",
            shares=1e6, market_value=150e6, ownership_pct=5.0,
            change_shares=1e6, change_pct=100.0,
        )
        assert p.is_new_position
        assert not p.is_exit

    def test_institutional_position_exit(self):
        p = InstitutionalPosition(
            holder_name="Fidelity", symbol="AAPL",
            shares=0, market_value=0, ownership_pct=0,
            change_shares=-1e6, change_pct=-100.0,
        )
        assert p.is_exit
        assert not p.is_new_position

    def test_institutional_position_to_dict(self):
        p = InstitutionalPosition(
            holder_name="Vanguard", symbol="AAPL",
            shares=1e6, market_value=150e6, ownership_pct=5.0,
            change_shares=1e5, change_pct=10.0, quarter="Q4 2025",
        )
        d = p.to_dict()
        assert d["holder_name"] == "Vanguard"
        assert d["quarter"] == "Q4 2025"

    def test_institutional_summary_concentrated(self):
        s = InstitutionalSummary(
            symbol="AAPL", total_institutional_pct=65.0,
            n_holders=10, top_holder="Vanguard",
            top_holder_pct=8.0, concentration=0.30,
            net_change_pct=5.0,
        )
        assert s.is_concentrated

    def test_institutional_summary_to_dict(self):
        s = InstitutionalSummary(
            symbol="AAPL", total_institutional_pct=65.0,
            n_holders=10, top_holder="Vanguard",
            top_holder_pct=8.0, concentration=0.15,
            net_change_pct=5.0, new_positions=2, exits=1,
        )
        d = s.to_dict()
        assert d["new_positions"] == 2
        assert d["exits"] == 1

    def test_sector_rotation_composite(self):
        r = SectorRotation(sector="Technology",
                           flow_score=1.5, momentum_score=0.8)
        expected = 0.6 * 1.5 + 0.4 * 0.8
        assert abs(r.composite_score - expected) < 0.001

    def test_sector_rotation_to_dict(self):
        r = SectorRotation(sector="Tech", flow_score=1.0,
                           momentum_score=0.5, rank=1,
                           phase=RotationPhase.MID_CYCLE)
        d = r.to_dict()
        assert d["phase"] == "mid_cycle"
        assert d["rank"] == 1

    def test_smart_money_result_net(self):
        r = SmartMoneyResult(
            symbol="AAPL",
            institutional_flow=5e6, retail_flow=2e6,
            smart_money_score=0.5, conviction=0.7,
            signal=SmartMoneySignal.ACCUMULATION,
        )
        assert r.net_smart_flow == 3e6

    def test_smart_money_result_to_dict(self):
        r = SmartMoneyResult(
            symbol="AAPL",
            institutional_flow=5e6, retail_flow=2e6,
            smart_money_score=0.5, conviction=0.7,
            signal=SmartMoneySignal.ACCUMULATION,
            is_contrarian=True,
        )
        d = r.to_dict()
        assert d["signal"] == "accumulation"
        assert d["is_contrarian"] is True


# ── Flow Tracker Tests ───────────────────────────────────────


class TestFlowTracker:
    def test_add_and_summarize(self):
        tracker = FlowTracker()
        flows = _make_flows("SPY", n=20)
        tracker.add_flows(flows)
        summary = tracker.summarize("SPY")

        assert summary.name == "SPY"
        assert summary.total_inflow > 0
        assert summary.total_outflow > 0
        assert summary.n_days == 20

    def test_net_flow_positive_trend(self):
        tracker = FlowTracker()
        flows = _make_flows("QQQ", n=20, base_inflow=2e6, trend=0)
        tracker.add_flows(flows)
        summary = tracker.summarize("QQQ")
        # base_inflow > base_outflow (0.8x), so net should be positive
        assert summary.net_flow > 0

    def test_momentum_increasing(self):
        tracker = FlowTracker()
        flows = _make_flows("SPY", n=20, trend=1e5)
        tracker.add_flows(flows)
        summary = tracker.summarize("SPY")
        assert summary.flow_momentum > 0  # increasing trend

    def test_flow_strength_classification(self):
        tracker = FlowTracker()
        # Large inflows relative to AUM
        for i in range(20):
            tracker.add_flow(FundFlow(
                fund_name="BIG", date=f"2026-01-{i+1:02d}",
                inflow=5e6, outflow=0, aum=100e6,
            ))
        summary = tracker.summarize("BIG")
        assert summary.strength in (FlowStrength.STRONG, FlowStrength.MODERATE)

    def test_empty_fund(self):
        tracker = FlowTracker()
        summary = tracker.summarize("UNKNOWN")
        assert summary.net_flow == 0.0
        assert summary.n_days == 0

    def test_summarize_all(self):
        tracker = FlowTracker()
        tracker.add_flows(_make_flows("SPY", 10))
        tracker.add_flows(_make_flows("QQQ", 10))
        summaries = tracker.summarize_all()
        assert len(summaries) == 2

    def test_get_history(self):
        tracker = FlowTracker()
        flows = _make_flows("SPY", 5)
        tracker.add_flows(flows)
        history = tracker.get_history("SPY")
        assert len(history) == 5

    def test_reset(self):
        tracker = FlowTracker()
        tracker.add_flows(_make_flows("SPY", 5))
        tracker.reset()
        assert tracker.get_history("SPY") == []


# ── Institutional Analyzer Tests ─────────────────────────────


class TestInstitutionalAnalyzer:
    def test_basic_analysis(self):
        positions = _make_positions("AAPL", 5)
        analyzer = InstitutionalAnalyzer()
        result = analyzer.analyze(positions, "AAPL")

        assert result.symbol == "AAPL"
        assert result.n_holders > 0
        assert result.total_institutional_pct > 0
        assert result.top_holder == "Vanguard"

    def test_concentration(self):
        # One dominant holder
        positions = [
            InstitutionalPosition("Mega Fund", "X", 5e6, 500e6, 50.0),
            InstitutionalPosition("Small Fund", "X", 1e5, 10e6, 1.0),
        ]
        analyzer = InstitutionalAnalyzer()
        result = analyzer.analyze(positions, "X")
        assert result.concentration > 0.9  # highly concentrated

    def test_low_concentration(self):
        # Equal holders
        positions = [
            InstitutionalPosition(f"Fund {i}", "X", 1e6, 100e6, 5.0)
            for i in range(10)
        ]
        analyzer = InstitutionalAnalyzer()
        result = analyzer.analyze(positions, "X")
        assert result.concentration <= 0.15  # evenly distributed

    def test_position_changes(self):
        positions = [
            InstitutionalPosition("New Fund", "AAPL", 1e6, 150e6, 5.0,
                                  change_shares=1e6, change_pct=100.0),
            InstitutionalPosition("Exit Fund", "AAPL", 0, 0, 0.5,
                                  change_shares=-1e6, change_pct=-100.0),
            InstitutionalPosition("Increase", "AAPL", 2e6, 300e6, 10.0,
                                  change_shares=5e5, change_pct=25.0),
        ]
        analyzer = InstitutionalAnalyzer()
        result = analyzer.analyze(positions, "AAPL")
        assert result.new_positions == 1
        assert result.exits == 1
        assert result.increases == 1

    def test_top_holders(self):
        positions = _make_positions("AAPL", 5)
        analyzer = InstitutionalAnalyzer(InstitutionalConfig(top_holders_count=3))
        top = analyzer.top_holders(positions)
        assert len(top) == 3
        assert top[0].ownership_pct >= top[1].ownership_pct

    def test_empty_positions(self):
        analyzer = InstitutionalAnalyzer()
        result = analyzer.analyze([], "EMPTY")
        assert result.n_holders == 0
        assert result.total_institutional_pct == 0.0

    def test_min_ownership_filter(self):
        positions = [
            InstitutionalPosition("Big", "X", 1e6, 100e6, 5.0),
            InstitutionalPosition("Tiny", "X", 100, 10000, 0.001),
        ]
        analyzer = InstitutionalAnalyzer()
        result = analyzer.analyze(positions, "X")
        assert result.n_holders == 1  # tiny filtered out


# ── Rotation Detector Tests ──────────────────────────────────


class TestRotationDetector:
    def test_basic_rotation(self):
        rng = np.random.RandomState(42)
        sector_flows = {
            "Technology": list(rng.randn(20) * 1e6 + 5e5),
            "Healthcare": list(rng.randn(20) * 1e6 - 2e5),
            "Financials": list(rng.randn(20) * 1e6 + 3e5),
        }
        detector = RotationDetector()
        results = detector.analyze(sector_flows)

        assert len(results) == 3
        assert results[0].rank == 1
        assert results[-1].rank == 3

    def test_ranking_order(self):
        sector_flows = {
            "Tech": [1e6] * 20,      # strong positive
            "Energy": [-1e6] * 20,    # strong negative
            "Health": [0.0] * 20,     # neutral
        }
        detector = RotationDetector()
        results = detector.analyze(sector_flows)
        assert results[0].sector == "Tech"
        assert results[-1].sector == "Energy"

    def test_phase_detection(self):
        # Make tech/industrials strong -> mid cycle
        sector_flows = {
            "Technology": [5e6] * 20,
            "Industrials": [4e6] * 20,
            "Financials": [0] * 20,
            "Energy": [-1e6] * 20,
            "Utilities": [-2e6] * 20,
        }
        detector = RotationDetector()
        results = detector.analyze(sector_flows)
        assert results[0].phase == RotationPhase.MID_CYCLE

    def test_divergence(self):
        sector_flows = {
            "Tech": [5e6] * 20,
            "Energy": [-5e6] * 20,
        }
        detector = RotationDetector()
        div = detector.detect_divergence(sector_flows)
        assert div["Tech"] > 0
        assert div["Energy"] < 0

    def test_empty_flows(self):
        detector = RotationDetector()
        results = detector.analyze({})
        assert results == []

    def test_composite_score(self):
        sector_flows = {
            "A": [1e6] * 20,
            "B": [-1e6] * 20,
        }
        detector = RotationDetector()
        results = detector.analyze(sector_flows)
        for r in results:
            expected = 0.6 * r.flow_score + 0.4 * r.momentum_score
            assert abs(r.composite_score - expected) < 0.001


# ── Smart Money Detector Tests ───────────────────────────────


class TestSmartMoneyDetector:
    def test_accumulation_signal(self):
        inst = [1e6] * 20    # consistent institutional buying
        ret = [-0.5e6] * 20  # retail selling
        detector = SmartMoneyDetector()
        result = detector.analyze(inst, ret, symbol="AAPL")

        assert result.smart_money_score > 0
        assert result.signal == SmartMoneySignal.ACCUMULATION

    def test_distribution_signal(self):
        inst = [-1e6] * 20   # institutional selling
        ret = [0.5e6] * 20   # retail buying
        detector = SmartMoneyDetector()
        result = detector.analyze(inst, ret, symbol="AAPL")

        assert result.smart_money_score < 0
        assert result.signal == SmartMoneySignal.DISTRIBUTION

    def test_neutral_signal(self):
        inst = [0.1e6, -0.1e6] * 10  # mixed
        ret = [0.1e6, -0.1e6] * 10
        detector = SmartMoneyDetector()
        result = detector.analyze(inst, ret, symbol="TEST")
        assert result.signal == SmartMoneySignal.NEUTRAL

    def test_conviction_consistent_flows(self):
        inst = [1e6] * 20  # very consistent
        ret = [0] * 20
        detector = SmartMoneyDetector()
        result = detector.analyze(inst, ret, symbol="TEST")
        assert result.conviction > 0.5

    def test_conviction_inconsistent_flows(self):
        rng = np.random.RandomState(42)
        inst = list(rng.randn(20) * 1e6)  # random
        ret = [0] * 20
        detector = SmartMoneyDetector()
        result = detector.analyze(inst, ret, symbol="TEST")
        # Inconsistent flows -> lower conviction
        assert result.conviction < 0.8

    def test_flow_price_divergence(self):
        inst = [1e6] * 20   # buying
        ret = [0] * 20
        prices = list(np.linspace(100, 90, 20))  # price declining
        detector = SmartMoneyDetector()
        result = detector.analyze(inst, ret, prices, "TEST")
        assert result.flow_price_divergence > 0  # bullish divergence

    def test_contrarian_detection(self):
        inst = [1e6] * 20
        ret = [-0.5e6] * 20
        prices = list(np.linspace(100, 95, 20))  # declining >2%
        detector = SmartMoneyDetector()
        result = detector.analyze(inst, ret, prices, "TEST")
        assert result.is_contrarian  # buying into decline

    def test_empty_flows(self):
        detector = SmartMoneyDetector()
        result = detector.analyze([], [], symbol="EMPTY")
        assert result.smart_money_score == 0.0
        assert result.conviction == 0.0

    def test_net_smart_flow(self):
        detector = SmartMoneyDetector()
        result = detector.analyze([5e6], [2e6], symbol="TEST")
        assert result.net_smart_flow == result.institutional_flow - result.retail_flow


# ── Integration Tests ────────────────────────────────────────


class TestIntegration:
    def test_full_pipeline(self):
        """End-to-end: flows -> tracker -> rotation + smart money."""
        rng = np.random.RandomState(42)

        # Track flows
        tracker = FlowTracker()
        for fund in ["SPY", "QQQ", "XLF"]:
            flows = _make_flows(fund, 20)
            tracker.add_flows(flows)

        summaries = tracker.summarize_all()
        assert len(summaries) == 3

        # Rotation detection
        sector_flows = {
            "Technology": list(rng.randn(20) * 1e6 + 5e5),
            "Financials": list(rng.randn(20) * 1e6 + 2e5),
            "Energy": list(rng.randn(20) * 1e6 - 3e5),
        }
        rotation = RotationDetector()
        rotations = rotation.analyze(sector_flows)
        assert len(rotations) == 3
        assert rotations[0].rank == 1

        # Smart money
        detector = SmartMoneyDetector()
        result = detector.analyze(
            [1e6] * 20, [-0.5e6] * 20,
            list(np.linspace(100, 95, 20)), "AAPL",
        )
        assert result.signal in (
            SmartMoneySignal.ACCUMULATION,
            SmartMoneySignal.DISTRIBUTION,
            SmartMoneySignal.NEUTRAL,
        )

    def test_institutional_to_smart_money(self):
        """Institutional positions inform smart money signals."""
        positions = _make_positions("AAPL", 5)
        inst_analyzer = InstitutionalAnalyzer()
        inst_summary = inst_analyzer.analyze(positions, "AAPL")
        assert inst_summary.n_holders > 0

        # Use net change as proxy for institutional flow direction
        detector = SmartMoneyDetector()
        flow_sign = 1e6 if inst_summary.net_change_pct > 0 else -1e6
        result = detector.analyze(
            [flow_sign] * 10, [0] * 10, symbol="AAPL",
        )
        assert isinstance(result.signal, SmartMoneySignal)


class TestModuleImports:
    def test_top_level_imports(self):
        from src.fundflow import (
            FlowTracker,
            InstitutionalAnalyzer,
            RotationDetector,
            SmartMoneyDetector,
            FundFlow,
            FlowSummary,
            InstitutionalPosition,
            InstitutionalSummary,
            SectorRotation,
            SmartMoneyResult,
            FlowDirection,
            FlowStrength,
            RotationPhase,
            SmartMoneySignal,
            DEFAULT_CONFIG,
        )
        assert DEFAULT_CONFIG is not None
