"""Tests for the options trading platform."""

import numpy as np
import pandas as pd
import pytest
from datetime import datetime, date

from src.options.config import (
    OptionsConfig,
    PricingConfig,
    VolatilityConfig,
    StrategyConfig,
    ActivityConfig,
    BacktestConfig,
)
from src.options.pricing import (
    OptionsPricingEngine,
    OptionPrice,
    OptionLeg,
    OptionType,
)
from src.options.volatility import (
    VolatilitySurfaceBuilder,
    VolSurface,
    VolAnalytics,
    VolPoint,
)
from src.options.strategies import (
    StrategyBuilder,
    StrategyAnalysis,
    StrategyType,
    PayoffCurve,
)
from src.options.activity import (
    UnusualActivityDetector,
    ActivitySignal,
    ActivitySummary,
    SignalType,
)
from src.options.backtest import (
    OptionsBacktester,
    BacktestResult,
    BacktestTrade,
    EntryRules,
    ExitRules,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def pricing_engine():
    """Create pricing engine."""
    return OptionsPricingEngine()


@pytest.fixture
def strategy_builder():
    """Create strategy builder."""
    return StrategyBuilder()


@pytest.fixture
def vol_builder():
    """Create volatility surface builder."""
    return VolatilitySurfaceBuilder()


@pytest.fixture
def activity_detector():
    """Create activity detector."""
    return UnusualActivityDetector()


@pytest.fixture
def sample_price_history():
    """Generate sample price history."""
    np.random.seed(42)
    dates = pd.date_range(start='2024-01-01', periods=252, freq='D')
    returns = np.random.normal(0.0005, 0.015, 252)
    prices = 100 * np.cumprod(1 + returns)
    return pd.Series(prices, index=dates)


@pytest.fixture
def sample_iv_history():
    """Generate sample IV history."""
    np.random.seed(43)
    dates = pd.date_range(start='2024-01-01', periods=252, freq='D')
    iv = 0.25 + 0.05 * np.sin(np.arange(252) / 20) + np.random.normal(0, 0.02, 252)
    iv = np.clip(iv, 0.10, 0.50)
    return pd.Series(iv, index=dates)


# =============================================================================
# Test Options Pricing Engine
# =============================================================================

class TestOptionsPricingEngine:
    """Tests for options pricing engine."""

    def test_black_scholes_call(self, pricing_engine):
        """Test Black-Scholes call pricing."""
        result = pricing_engine.black_scholes(
            S=100, K=100, T=0.25, r=0.05, sigma=0.20, option_type="call"
        )

        assert isinstance(result, OptionPrice)
        assert result.price > 0
        assert result.option_type == "call"
        # ATM call delta should be around 0.5
        assert 0.4 < result.delta < 0.7

    def test_black_scholes_put(self, pricing_engine):
        """Test Black-Scholes put pricing."""
        result = pricing_engine.black_scholes(
            S=100, K=100, T=0.25, r=0.05, sigma=0.20, option_type="put"
        )

        assert result.price > 0
        assert result.option_type == "put"
        # ATM put delta should be around -0.5
        assert -0.7 < result.delta < -0.4

    def test_put_call_parity(self, pricing_engine):
        """Test put-call parity holds."""
        S, K, T, r, sigma = 100, 105, 0.5, 0.05, 0.25

        call = pricing_engine.black_scholes(S, K, T, r, sigma, "call")
        put = pricing_engine.black_scholes(S, K, T, r, sigma, "put")

        # C - P = S - K*e^(-rT)
        parity_lhs = call.price - put.price
        parity_rhs = S - K * np.exp(-r * T)

        assert abs(parity_lhs - parity_rhs) < 0.01

    def test_greeks_signs(self, pricing_engine):
        """Test Greeks have correct signs."""
        call = pricing_engine.black_scholes(
            S=100, K=100, T=0.25, r=0.05, sigma=0.20, option_type="call"
        )

        # Call delta positive
        assert call.delta > 0
        # Gamma always positive
        assert call.gamma > 0
        # Theta usually negative for long options
        assert call.theta < 0
        # Vega always positive
        assert call.vega > 0

    def test_binomial_tree_american_put(self, pricing_engine):
        """Test binomial tree for American put."""
        result = pricing_engine.binomial_tree(
            S=100, K=105, T=0.25, r=0.05, sigma=0.20,
            option_type="put", american=True
        )

        # American put should be >= European put
        european = pricing_engine.black_scholes(
            S=100, K=105, T=0.25, r=0.05, sigma=0.20, option_type="put"
        )

        assert result.price >= european.price - 0.01

    def test_monte_carlo_pricing(self, pricing_engine):
        """Test Monte Carlo pricing."""
        result = pricing_engine.monte_carlo(
            S=100, K=100, T=0.25, r=0.05, sigma=0.20,
            option_type="call", n_simulations=50000
        )

        bs = pricing_engine.black_scholes(
            S=100, K=100, T=0.25, r=0.05, sigma=0.20, option_type="call"
        )

        # MC should be close to BS for European options
        assert abs(result.price - bs.price) < 0.5

    def test_implied_volatility(self, pricing_engine):
        """Test implied volatility solver."""
        # Price an option at 25% vol
        S, K, T, r = 100, 100, 0.25, 0.05
        true_vol = 0.25

        result = pricing_engine.black_scholes(S, K, T, r, true_vol, "call")

        # Recover IV from the price
        iv = pricing_engine.implied_volatility(
            result.price, S, K, T, r, "call"
        )

        assert abs(iv - true_vol) < 0.01

    def test_otm_option_pricing(self, pricing_engine):
        """Test OTM options have lower prices."""
        S, T, r, sigma = 100, 0.25, 0.05, 0.25

        atm_call = pricing_engine.black_scholes(S, 100, T, r, sigma, "call")
        otm_call = pricing_engine.black_scholes(S, 110, T, r, sigma, "call")

        assert otm_call.price < atm_call.price

    def test_expiring_option(self, pricing_engine):
        """Test nearly expired option."""
        result = pricing_engine.black_scholes(
            S=100, K=95, T=0.001, r=0.05, sigma=0.20, option_type="call"
        )

        # Should be close to intrinsic value
        intrinsic = 100 - 95
        assert abs(result.price - intrinsic) < 0.5


# =============================================================================
# Test Volatility Surface Builder
# =============================================================================

class TestVolatilitySurfaceBuilder:
    """Tests for volatility surface builder."""

    def test_build_from_ivs(self, vol_builder):
        """Test building surface from IV data."""
        iv_data = [
            {"moneyness": 0.9, "dte": 30, "iv": 0.28},
            {"moneyness": 0.95, "dte": 30, "iv": 0.26},
            {"moneyness": 1.0, "dte": 30, "iv": 0.25},
            {"moneyness": 1.05, "dte": 30, "iv": 0.26},
            {"moneyness": 1.1, "dte": 30, "iv": 0.28},
            {"moneyness": 1.0, "dte": 60, "iv": 0.27},
        ]

        surface = vol_builder.build_from_ivs(iv_data)

        assert isinstance(surface, VolSurface)
        assert len(surface.raw_points) == 6

    def test_get_iv_interpolation(self, vol_builder):
        """Test IV interpolation from surface."""
        iv_data = [
            {"moneyness": 0.9, "dte": 30, "iv": 0.30},
            {"moneyness": 1.0, "dte": 30, "iv": 0.25},
            {"moneyness": 1.1, "dte": 30, "iv": 0.30},
        ]

        surface = vol_builder.build_from_ivs(iv_data)
        iv = surface.get_iv(1.0, 30)

        # Should be close to ATM IV
        assert 0.20 < iv < 0.35

    def test_compute_analytics(self, vol_builder, sample_price_history, sample_iv_history):
        """Test volatility analytics computation."""
        iv_data = [
            {"moneyness": 0.9, "dte": 30, "iv": 0.30},
            {"moneyness": 1.0, "dte": 30, "iv": 0.25},
            {"moneyness": 1.1, "dte": 30, "iv": 0.27},
            {"moneyness": 1.0, "dte": 60, "iv": 0.26},
        ]

        surface = vol_builder.build_from_ivs(iv_data)
        analytics = vol_builder.compute_analytics(
            surface, sample_price_history, sample_iv_history
        )

        assert isinstance(analytics, VolAnalytics)
        assert analytics.atm_iv > 0
        assert analytics.realized_vol_30d > 0

    def test_vol_cone(self, vol_builder, sample_price_history):
        """Test volatility cone calculation."""
        cone = vol_builder.get_vol_cone(sample_price_history)

        assert isinstance(cone, pd.DataFrame)
        assert "window" in cone.columns
        assert "current" in cone.columns
        assert len(cone) > 0


# =============================================================================
# Test Strategy Builder
# =============================================================================

class TestStrategyBuilder:
    """Tests for strategy builder."""

    def test_build_long_call(self, strategy_builder):
        """Test long call construction."""
        legs = strategy_builder.build_long_call(
            spot=100, strike=105, dte=30, iv=0.25
        )

        assert len(legs) == 1
        assert legs[0].option_type == "call"
        assert legs[0].strike == 105
        assert legs[0].quantity == 1

    def test_build_bull_call_spread(self, strategy_builder):
        """Test bull call spread construction."""
        legs = strategy_builder.build_bull_call_spread(
            spot=100, width=5, dte=30, iv=0.25
        )

        assert len(legs) == 2
        # Long lower strike, short upper strike
        assert legs[0].quantity == 1
        assert legs[1].quantity == -1
        assert legs[0].strike < legs[1].strike

    def test_build_iron_condor(self, strategy_builder):
        """Test iron condor construction."""
        legs = strategy_builder.build_iron_condor(
            spot=100, put_width=10, call_width=10, wing_width=5, dte=30, iv=0.25
        )

        assert len(legs) == 4
        # Should have 2 puts and 2 calls
        puts = [l for l in legs if l.option_type == "put"]
        calls = [l for l in legs if l.option_type == "call"]
        assert len(puts) == 2
        assert len(calls) == 2

    def test_build_straddle(self, strategy_builder):
        """Test straddle construction."""
        legs = strategy_builder.build_straddle(spot=100, dte=30, iv=0.25)

        assert len(legs) == 2
        assert legs[0].option_type == "call"
        assert legs[1].option_type == "put"
        assert legs[0].strike == legs[1].strike

    def test_analyze_strategy(self, strategy_builder):
        """Test strategy analysis."""
        legs = strategy_builder.build_bull_call_spread(
            spot=100, width=5, dte=30, iv=0.25
        )
        analysis = strategy_builder.analyze(legs, spot=100, iv=0.25)

        assert isinstance(analysis, StrategyAnalysis)
        assert analysis.max_profit > 0
        assert analysis.max_loss < 0
        assert len(analysis.breakeven_points) > 0
        assert 0 <= analysis.probability_of_profit <= 1

    def test_payoff_diagram(self, strategy_builder):
        """Test payoff diagram generation."""
        legs = strategy_builder.build_long_call(
            spot=100, strike=100, dte=30, iv=0.25
        )
        payoff = strategy_builder.payoff_diagram(legs, spot=100)

        assert isinstance(payoff, PayoffCurve)
        assert len(payoff.prices) > 0
        assert len(payoff.pnl) == len(payoff.prices)

    def test_probability_of_profit(self, strategy_builder):
        """Test PoP calculation."""
        legs = strategy_builder.build_long_call(
            spot=100, strike=100, dte=30, iv=0.25
        )
        pop = strategy_builder.probability_of_profit(
            legs, spot=100, iv=0.25, dte=30, n_simulations=10000
        )

        # ATM call should have ~40-60% PoP
        assert 0.3 < pop < 0.7

    def test_compare_strategies(self, strategy_builder):
        """Test strategy comparison."""
        strategies = {
            "Bull Call Spread": strategy_builder.build_bull_call_spread(
                spot=100, width=5, dte=30, iv=0.25
            ),
            "Straddle": strategy_builder.build_straddle(
                spot=100, dte=30, iv=0.25
            ),
        }

        comparison = strategy_builder.compare_strategies(strategies, spot=100, iv=0.25)

        assert isinstance(comparison, pd.DataFrame)
        assert len(comparison) == 2
        assert "Strategy" in comparison.columns
        assert "Max Profit" in comparison.columns


# =============================================================================
# Test Unusual Activity Detector
# =============================================================================

class TestUnusualActivityDetector:
    """Tests for unusual activity detector."""

    def test_volume_spike_detection(self, activity_detector):
        """Test volume spike detection."""
        flow_data = pd.DataFrame([{
            "symbol": "AAPL",
            "option_type": "call",
            "strike": 180,
            "expiry": "2024-02-16",
            "volume": 50000,
            "oi": 10000,
            "premium": 100000,
            "iv": 0.30,
            "avg_volume": 5000,  # 10x avg
            "avg_oi": 10000,
            "iv_rank": 0.50,
            "dte": 30,
        }])

        signals = activity_detector.scan(flow_data)

        assert len(signals) > 0
        vol_signals = [s for s in signals if s.signal_type == SignalType.VOLUME_SPIKE]
        assert len(vol_signals) > 0

    def test_large_block_detection(self, activity_detector):
        """Test large block detection."""
        flow_data = pd.DataFrame([{
            "symbol": "TSLA",
            "option_type": "put",
            "strike": 250,
            "expiry": "2024-02-16",
            "volume": 5000,  # Over 1000 threshold
            "oi": 1000,
            "premium": 500000,
            "iv": 0.45,
            "avg_volume": 5000,
            "avg_oi": 1000,
            "iv_rank": 0.60,
            "dte": 30,
        }])

        signals = activity_detector.scan(flow_data)

        block_signals = [s for s in signals if s.signal_type == SignalType.LARGE_BLOCK]
        assert len(block_signals) > 0

    def test_iv_spike_detection(self, activity_detector):
        """Test IV spike detection."""
        flow_data = pd.DataFrame([{
            "symbol": "NVDA",
            "option_type": "call",
            "strike": 500,
            "expiry": "2024-02-16",
            "volume": 1000,
            "oi": 500,
            "premium": 50000,
            "iv": 0.60,
            "avg_volume": 1000,
            "avg_oi": 500,
            "iv_rank": 0.90,  # High IV rank
            "dte": 30,
        }])

        signals = activity_detector.scan(flow_data)

        iv_signals = [s for s in signals if s.signal_type == SignalType.IV_SPIKE]
        assert len(iv_signals) > 0

    def test_put_call_ratio_detection(self, activity_detector):
        """Test put/call ratio detection."""
        flow_data = pd.DataFrame([
            {"symbol": "SPY", "option_type": "put", "volume": 100000},
            {"symbol": "SPY", "option_type": "call", "volume": 30000},
        ])

        signals = activity_detector.scan_put_call_ratio(flow_data)

        # P/C ratio > 3, should detect bearish skew
        pc_signals = [s for s in signals if s.signal_type == SignalType.PUT_CALL_SKEW]
        assert len(pc_signals) > 0

    def test_summarize_signals(self, activity_detector):
        """Test signal summarization."""
        signals = [
            ActivitySignal(symbol="AAPL", signal_type=SignalType.VOLUME_SPIKE,
                          option_type="call", premium_total=100000),
            ActivitySignal(symbol="AAPL", signal_type=SignalType.LARGE_BLOCK,
                          option_type="call", premium_total=200000),
            ActivitySignal(symbol="TSLA", signal_type=SignalType.IV_SPIKE,
                          option_type="put", premium_total=50000),
        ]

        summaries = activity_detector.summarize(signals)

        assert "AAPL" in summaries
        assert "TSLA" in summaries
        assert summaries["AAPL"].total_signals == 2
        assert summaries["TSLA"].total_signals == 1


# =============================================================================
# Test Options Backtester
# =============================================================================

class TestOptionsBacktester:
    """Tests for options backtester."""

    def test_backtest_short_put(self, sample_price_history, sample_iv_history):
        """Test short put backtest."""
        bt = OptionsBacktester()

        result = bt.backtest_short_put(
            sample_price_history,
            sample_iv_history,
            delta_target=0.30,
            entry_rules=EntryRules(min_dte=30, max_dte=45),
            exit_rules=ExitRules(profit_target_pct=0.50, min_dte_exit=7),
        )

        assert isinstance(result, BacktestResult)
        assert result.total_trades >= 0

    def test_backtest_iron_condor(self, sample_price_history, sample_iv_history):
        """Test iron condor backtest."""
        bt = OptionsBacktester()

        result = bt.backtest_iron_condor(
            sample_price_history,
            sample_iv_history,
            wing_delta=0.15,
            wing_width=5.0,
            entry_rules=EntryRules(min_dte=30, max_dte=45),
            exit_rules=ExitRules(profit_target_pct=0.50),
        )

        assert isinstance(result, BacktestResult)

    def test_backtest_result_statistics(self, sample_price_history, sample_iv_history):
        """Test backtest result statistics."""
        bt = OptionsBacktester()

        result = bt.backtest_short_put(
            sample_price_history,
            sample_iv_history,
            delta_target=0.30,
        )

        if result.total_trades > 0:
            assert 0 <= result.win_rate <= 1
            assert result.avg_hold_days >= 0
            # Summary should work
            summary = result.summary()
            assert "total_trades" in summary

    def test_entry_rules_filtering(self, sample_price_history, sample_iv_history):
        """Test entry rules filter trades."""
        bt = OptionsBacktester()

        # Very restrictive rules
        strict_rules = EntryRules(
            min_iv_rank=0.90,  # Very high IV required
            max_iv_rank=1.0,
        )

        result = bt.backtest_short_put(
            sample_price_history,
            sample_iv_history,
            delta_target=0.30,
            entry_rules=strict_rules,
        )

        # Should have fewer trades with strict rules
        assert result.total_trades >= 0


# =============================================================================
# Test Configuration
# =============================================================================

class TestOptionsConfig:
    """Tests for options configuration."""

    def test_default_pricing_config(self):
        """Test default pricing config values."""
        config = PricingConfig()
        assert config.risk_free_rate == 0.05
        assert config.binomial_steps == 200
        assert config.monte_carlo_simulations == 100_000

    def test_default_strategy_config(self):
        """Test default strategy config."""
        config = StrategyConfig()
        assert config.contract_multiplier == 100
        assert config.default_pop_simulations == 100_000

    def test_default_activity_config(self):
        """Test default activity config."""
        config = ActivityConfig()
        assert config.volume_spike_multiplier == 5.0
        assert config.large_block_threshold == 1000

    def test_options_config_composite(self):
        """Test composite options config."""
        config = OptionsConfig()
        assert isinstance(config.pricing, PricingConfig)
        assert isinstance(config.volatility, VolatilityConfig)
        assert isinstance(config.strategy, StrategyConfig)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
