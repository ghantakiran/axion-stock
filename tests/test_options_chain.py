"""Tests for PRD-43: Options Chain Analysis."""

import pytest
import numpy as np

from src.options.config import (
    FlowType,
    ActivityLevel,
    Sentiment,
    ChainConfig,
    FlowConfig,
    OptionsConfig,
)
from src.options.pricing import OptionType
from src.options.models import (
    OptionGreeks,
    OptionContract,
    ChainSummary,
    OptionsFlow,
    UnusualActivity,
)
from src.options.chain import ChainAnalyzer
from src.options.flow import FlowDetector


# ===========================================================================
# Config Tests
# ===========================================================================

class TestConfig:
    """Test new configuration enums and dataclasses."""

    def test_flow_type_values(self):
        assert FlowType.SWEEP.value == "sweep"
        assert FlowType.BLOCK.value == "block"
        assert FlowType.SPLIT.value == "split"
        assert FlowType.NORMAL.value == "normal"

    def test_activity_level_values(self):
        assert ActivityLevel.NORMAL.value == "normal"
        assert ActivityLevel.ELEVATED.value == "elevated"
        assert ActivityLevel.UNUSUAL.value == "unusual"
        assert ActivityLevel.EXTREME.value == "extreme"

    def test_sentiment_values(self):
        assert Sentiment.BULLISH.value == "bullish"
        assert Sentiment.BEARISH.value == "bearish"
        assert Sentiment.NEUTRAL.value == "neutral"

    def test_chain_config_defaults(self):
        cfg = ChainConfig()
        assert cfg.min_volume == 10
        assert cfg.min_open_interest == 100
        assert cfg.skew_otm_range == 0.10

    def test_flow_config_defaults(self):
        cfg = FlowConfig()
        assert cfg.unusual_vol_oi_ratio == 2.0
        assert cfg.block_min_size == 100
        assert cfg.min_premium == 25_000.0

    def test_options_config_has_chain_and_flow(self):
        cfg = OptionsConfig()
        assert isinstance(cfg.chain, ChainConfig)
        assert isinstance(cfg.flow, FlowConfig)


# ===========================================================================
# Model Tests
# ===========================================================================

class TestModels:
    """Test data models."""

    def test_option_greeks_to_dict(self):
        g = OptionGreeks(delta=0.55, gamma=0.03, theta=-0.05, vega=0.15, rho=0.02)
        d = g.to_dict()
        assert d["delta"] == 0.55
        assert d["vega"] == 0.15

    def test_option_contract_mid(self):
        c = OptionContract(bid=5.0, ask=5.50)
        assert c.mid == 5.25

    def test_option_contract_mid_fallback(self):
        c = OptionContract(bid=0.0, ask=0.0, last=4.80)
        assert c.mid == 4.80

    def test_option_contract_spread(self):
        c = OptionContract(bid=5.0, ask=5.50)
        assert c.spread == 0.50

    def test_option_contract_vol_oi_ratio(self):
        c = OptionContract(volume=500, open_interest=200)
        assert c.vol_oi_ratio == 2.5

    def test_option_contract_vol_oi_zero_oi(self):
        c = OptionContract(volume=500, open_interest=0)
        assert c.vol_oi_ratio == 0.0

    def test_option_contract_to_dict(self):
        c = OptionContract(
            symbol="AAPL", strike=150.0, option_type=OptionType.CALL,
            bid=5.0, ask=5.50, volume=300, open_interest=1000,
        )
        d = c.to_dict()
        assert d["option_type"] == "call"
        assert d["mid"] == 5.25

    def test_chain_summary_properties(self):
        cs = ChainSummary(total_call_volume=5000, total_put_volume=3000,
                          total_call_oi=10000, total_put_oi=8000)
        assert cs.total_volume == 8000
        assert cs.total_oi == 18000

    def test_chain_summary_sentiment_bullish(self):
        cs = ChainSummary(pcr_volume=0.5)
        assert cs.net_sentiment == "bullish"

    def test_chain_summary_sentiment_bearish(self):
        cs = ChainSummary(pcr_volume=1.5)
        assert cs.net_sentiment == "bearish"

    def test_chain_summary_sentiment_neutral(self):
        cs = ChainSummary(pcr_volume=1.0)
        assert cs.net_sentiment == "neutral"

    def test_chain_summary_to_dict(self):
        cs = ChainSummary(symbol="SPY", pcr_volume=0.85, max_pain_strike=450.0)
        d = cs.to_dict()
        assert d["symbol"] == "SPY"
        assert d["max_pain_strike"] == 450.0
        assert "net_sentiment" in d

    def test_options_flow_properties(self):
        f = OptionsFlow(flow_type=FlowType.SWEEP)
        assert f.is_sweep is True
        assert f.is_block is False

    def test_options_flow_to_dict(self):
        f = OptionsFlow(symbol="TSLA", flow_type=FlowType.BLOCK, sentiment=Sentiment.BULLISH)
        d = f.to_dict()
        assert d["flow_type"] == "block"
        assert d["sentiment"] == "bullish"

    def test_unusual_activity_is_unusual(self):
        ua = UnusualActivity(activity_level=ActivityLevel.UNUSUAL)
        assert ua.is_unusual is True
        ua2 = UnusualActivity(activity_level=ActivityLevel.ELEVATED)
        assert ua2.is_unusual is False

    def test_unusual_activity_to_dict(self):
        ua = UnusualActivity(symbol="NVDA", vol_oi_ratio=3.5, activity_level=ActivityLevel.UNUSUAL)
        d = ua.to_dict()
        assert d["activity_level"] == "unusual"
        assert d["is_unusual"] is True


# ===========================================================================
# Chain Analyzer Tests
# ===========================================================================

def _make_chain(underlying=150.0) -> list[OptionContract]:
    """Create a sample options chain for testing."""
    contracts = []
    for strike in [140, 145, 150, 155, 160]:
        # Calls
        iv = 0.30 + (strike - underlying) * 0.001
        contracts.append(OptionContract(
            symbol="TEST", strike=float(strike), expiry_days=30.0,
            option_type=OptionType.CALL, bid=max(underlying - strike + 2, 0.5),
            ask=max(underlying - strike + 3, 1.0), last=max(underlying - strike + 2.5, 0.75),
            volume=200 + (160 - strike) * 20, open_interest=1000 + (160 - strike) * 100,
            greeks=OptionGreeks(implied_vol=iv),
        ))
        # Puts
        contracts.append(OptionContract(
            symbol="TEST", strike=float(strike), expiry_days=30.0,
            option_type=OptionType.PUT, bid=max(strike - underlying + 2, 0.5),
            ask=max(strike - underlying + 3, 1.0), last=max(strike - underlying + 2.5, 0.75),
            volume=150 + (strike - 140) * 15, open_interest=800 + (strike - 140) * 80,
            greeks=OptionGreeks(implied_vol=iv + 0.02),
        ))
    return contracts


class TestChainAnalyzer:
    """Test chain analysis."""

    def test_analyze_chain(self):
        analyzer = ChainAnalyzer()
        chain = _make_chain()
        summary = analyzer.analyze_chain(chain, underlying_price=150.0, symbol="TEST")
        assert summary.symbol == "TEST"
        assert summary.n_contracts > 0
        assert summary.total_volume > 0
        assert summary.pcr_volume > 0

    def test_put_call_ratio_volume(self):
        analyzer = ChainAnalyzer()
        chain = _make_chain()
        pcr = analyzer.put_call_ratio(chain, use_oi=False)
        assert pcr > 0

    def test_put_call_ratio_oi(self):
        analyzer = ChainAnalyzer()
        chain = _make_chain()
        pcr = analyzer.put_call_ratio(chain, use_oi=True)
        assert pcr > 0

    def test_put_call_ratio_no_calls(self):
        analyzer = ChainAnalyzer()
        puts_only = [
            OptionContract(option_type=OptionType.PUT, volume=100, open_interest=500),
        ]
        pcr = analyzer.put_call_ratio(puts_only)
        assert pcr == 999.0

    def test_max_pain(self):
        analyzer = ChainAnalyzer()
        chain = _make_chain(150.0)
        mp = analyzer.compute_max_pain(chain, 150.0)
        # Max pain should be near ATM
        assert 140 <= mp <= 160

    def test_max_pain_empty(self):
        analyzer = ChainAnalyzer()
        mp = analyzer.compute_max_pain([], 150.0)
        assert mp == 150.0

    def test_iv_skew(self):
        analyzer = ChainAnalyzer()
        chain = _make_chain(150.0)
        skew = analyzer.compute_iv_skew(chain, 150.0)
        # With our test data, puts have higher IV
        assert isinstance(skew, float)

    def test_compute_greeks_for_chain(self):
        analyzer = ChainAnalyzer()
        contracts = [
            OptionContract(strike=150.0, expiry_days=30.0, option_type=OptionType.CALL,
                          bid=5.0, ask=5.50, volume=200, open_interest=1000),
            OptionContract(strike=155.0, expiry_days=30.0, option_type=OptionType.PUT,
                          bid=6.0, ask=6.50, volume=150, open_interest=800),
        ]
        result = analyzer.compute_greeks_for_chain(contracts, 150.0)
        assert result[0].greeks is not None
        assert result[0].greeks.delta != 0
        assert result[1].greeks is not None

    def test_atm_iv(self):
        analyzer = ChainAnalyzer()
        chain = _make_chain(150.0)
        summary = analyzer.analyze_chain(chain, 150.0)
        assert summary.atm_iv > 0

    def test_chain_sentiment(self):
        analyzer = ChainAnalyzer()
        chain = _make_chain(150.0)
        summary = analyzer.analyze_chain(chain, 150.0, symbol="SPY")
        assert summary.net_sentiment in ("bullish", "bearish", "neutral")


# ===========================================================================
# Flow Detector Tests
# ===========================================================================

class TestFlowDetector:
    """Test flow classification."""

    def test_classify_block(self):
        detector = FlowDetector()
        flow = detector.classify_flow(
            size=200, price=5.0, n_exchanges=1,
            option_type=OptionType.CALL, side="buy", symbol="AAPL",
        )
        assert flow.flow_type == FlowType.BLOCK
        assert flow.sentiment == Sentiment.BULLISH

    def test_classify_sweep(self):
        detector = FlowDetector()
        flow = detector.classify_flow(
            size=150, price=3.0, n_exchanges=3,
            option_type=OptionType.PUT, side="buy",
        )
        assert flow.flow_type == FlowType.SWEEP
        assert flow.sentiment == Sentiment.BEARISH

    def test_classify_split(self):
        detector = FlowDetector()
        flow = detector.classify_flow(
            size=50, price=2.0, n_exchanges=2,
        )
        assert flow.flow_type == FlowType.SPLIT

    def test_classify_normal(self):
        detector = FlowDetector()
        flow = detector.classify_flow(
            size=10, price=1.0, n_exchanges=1,
        )
        assert flow.flow_type == FlowType.NORMAL

    def test_premium_calculation(self):
        detector = FlowDetector()
        flow = detector.classify_flow(size=100, price=5.0, n_exchanges=1)
        # 100 contracts * $5.00 * 100 multiplier = $50,000
        assert flow.premium == 50_000.0

    def test_sentiment_buy_call(self):
        detector = FlowDetector()
        flow = detector.classify_flow(
            size=100, price=5.0, option_type=OptionType.CALL, side="buy",
        )
        assert flow.sentiment == Sentiment.BULLISH

    def test_sentiment_sell_call(self):
        detector = FlowDetector()
        flow = detector.classify_flow(
            size=100, price=5.0, option_type=OptionType.CALL, side="sell",
        )
        assert flow.sentiment == Sentiment.BEARISH

    def test_sentiment_buy_put(self):
        detector = FlowDetector()
        flow = detector.classify_flow(
            size=100, price=5.0, option_type=OptionType.PUT, side="buy",
        )
        assert flow.sentiment == Sentiment.BEARISH

    def test_sentiment_sell_put(self):
        detector = FlowDetector()
        flow = detector.classify_flow(
            size=100, price=5.0, option_type=OptionType.PUT, side="sell",
        )
        assert flow.sentiment == Sentiment.BULLISH

    def test_detect_unusual(self):
        detector = FlowDetector()
        contracts = [
            OptionContract(volume=500, open_interest=100, bid=5.0, ask=5.50,
                          strike=150.0, expiry_days=30.0),
            OptionContract(volume=50, open_interest=1000, bid=3.0, ask=3.50,
                          strike=155.0, expiry_days=30.0),
            OptionContract(volume=1000, open_interest=100, bid=2.0, ask=2.50,
                          strike=160.0, expiry_days=30.0),
        ]
        unusual = detector.detect_unusual(contracts, symbol="TEST")
        assert len(unusual) >= 2  # 500/100=5.0 and 1000/100=10.0 are unusual
        assert unusual[0].score >= unusual[-1].score  # Sorted by score

    def test_detect_unusual_elevated(self):
        detector = FlowDetector()
        contracts = [
            OptionContract(volume=180, open_interest=100, bid=5.0, ask=5.50),
        ]
        unusual = detector.detect_unusual(contracts)
        assert len(unusual) == 1
        assert unusual[0].activity_level == ActivityLevel.ELEVATED

    def test_detect_unusual_extreme(self):
        detector = FlowDetector()
        contracts = [
            OptionContract(volume=600, open_interest=100, bid=5.0, ask=5.50),
        ]
        unusual = detector.detect_unusual(contracts)
        assert len(unusual) == 1
        assert unusual[0].activity_level == ActivityLevel.EXTREME

    def test_detect_unusual_skips_normal(self):
        detector = FlowDetector()
        contracts = [
            OptionContract(volume=50, open_interest=1000, bid=5.0, ask=5.50),
        ]
        unusual = detector.detect_unusual(contracts)
        assert len(unusual) == 0

    def test_net_sentiment_bullish(self):
        detector = FlowDetector()
        detector.classify_flow(size=200, price=5.0, option_type=OptionType.CALL, side="buy")
        detector.classify_flow(size=100, price=3.0, option_type=OptionType.CALL, side="buy")
        detector.classify_flow(size=50, price=2.0, option_type=OptionType.PUT, side="buy")
        sentiment, net = detector.compute_net_sentiment()
        assert sentiment == Sentiment.BULLISH
        assert net > 0

    def test_net_sentiment_bearish(self):
        detector = FlowDetector()
        detector.classify_flow(size=200, price=5.0, option_type=OptionType.PUT, side="buy")
        detector.classify_flow(size=50, price=2.0, option_type=OptionType.CALL, side="buy")
        sentiment, net = detector.compute_net_sentiment()
        assert sentiment == Sentiment.BEARISH
        assert net < 0

    def test_net_sentiment_empty(self):
        detector = FlowDetector()
        sentiment, net = detector.compute_net_sentiment()
        assert sentiment == Sentiment.NEUTRAL
        assert net == 0.0

    def test_history_and_reset(self):
        detector = FlowDetector()
        detector.classify_flow(size=100, price=5.0)
        detector.classify_flow(size=200, price=3.0)
        assert len(detector.get_flows()) == 2
        detector.reset()
        assert len(detector.get_flows()) == 0


# ===========================================================================
# Integration Tests
# ===========================================================================

class TestIntegration:
    """End-to-end integration tests."""

    def test_full_chain_analysis_pipeline(self):
        """Chain -> Greeks -> Summary -> Flow -> Unusual."""
        # Build chain
        chain = _make_chain(150.0)

        # Compute greeks
        analyzer = ChainAnalyzer()
        chain = analyzer.compute_greeks_for_chain(chain, 150.0)

        # Analyze chain
        summary = analyzer.analyze_chain(chain, 150.0, symbol="SPY")
        assert summary.n_contracts > 0
        assert summary.pcr_volume > 0
        assert summary.max_pain_strike > 0

        # Flow detection
        flow_det = FlowDetector()
        flow = flow_det.classify_flow(
            size=500, price=5.0, n_exchanges=3,
            option_type=OptionType.CALL, side="buy", symbol="SPY",
        )
        assert flow.is_sweep

        # Unusual activity
        unusual = flow_det.detect_unusual(chain, symbol="SPY")
        # Some contracts may be flagged based on volume/OI ratios

        # Net sentiment
        sentiment, net = flow_det.compute_net_sentiment()
        assert isinstance(sentiment, Sentiment)

    def test_chain_summary_to_dict_roundtrip(self):
        analyzer = ChainAnalyzer()
        chain = _make_chain(150.0)
        summary = analyzer.analyze_chain(chain, 150.0, symbol="AAPL")
        d = summary.to_dict()
        assert d["symbol"] == "AAPL"
        assert isinstance(d["total_volume"], int)
        assert isinstance(d["net_sentiment"], str)


# ===========================================================================
# Module Import Tests
# ===========================================================================

class TestModuleImports:
    """Test module imports work correctly."""

    def test_top_level_imports(self):
        from src.options import (
            ChainAnalyzer,
            FlowDetector,
            ChainConfig,
            FlowConfig,
            FlowType,
            ActivityLevel,
            Sentiment,
            OptionGreeks,
            OptionContract,
            ChainSummary,
            OptionsFlow,
            UnusualActivity,
            OptionType,
            OptionsPricingEngine,
        )
        assert ChainAnalyzer is not None
        assert FlowDetector is not None
        assert OptionType.CALL.value == "call"
