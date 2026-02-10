"""Tests for Factor Engine v2.0.

Tests cover:
- Individual factor calculations
- Regime detection
- Adaptive weights
- Sector-relative scoring
- Integration with existing v1 interface
"""

import numpy as np
import pandas as pd
import pytest
from datetime import datetime, timedelta

from src.factor_engine_v2 import FactorEngineV2, compute_composite_scores_v2
from src.factors.registry import create_default_registry
from src.factors.value import ValueFactors
from src.factors.momentum import MomentumFactors
from src.factors.quality import QualityFactors
from src.factors.growth import GrowthFactors
from src.factors.volatility import VolatilityFactors
from src.factors.technical import TechnicalFactors
from src.regime.detector import RegimeDetector, MarketRegime
from src.regime.weights import AdaptiveWeights, REGIME_WEIGHTS


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_prices():
    """Generate sample price data for testing."""
    np.random.seed(42)
    dates = pd.date_range(end=datetime.now(), periods=300, freq='D')
    tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA', 'JPM', 'V', 'WMT']
    
    # Generate random walk prices
    prices = pd.DataFrame(index=dates, columns=tickers)
    for ticker in tickers:
        base = np.random.uniform(50, 500)
        returns = np.random.normal(0.001, 0.02, len(dates))
        prices[ticker] = base * np.cumprod(1 + returns)
    
    return prices.astype(float)


@pytest.fixture
def sample_fundamentals():
    """Generate sample fundamental data for testing."""
    tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA', 'JPM', 'V', 'WMT']
    
    data = {
        'trailingPE': [28, 32, 25, 60, 15, 70, 80, 12, 30, 22],
        'priceToBook': [45, 12, 6, 8, 5, 25, 15, 1.5, 13, 6],
        'dividendYield': [0.005, 0.008, 0.0, 0.0, 0.0, 0.001, 0.0, 0.025, 0.007, 0.014],
        'enterpriseToEbitda': [22, 24, 18, 35, 10, 50, 55, 8, 20, 12],
        'returnOnEquity': [1.5, 0.4, 0.25, 0.15, 0.25, 0.5, 0.15, 0.12, 0.35, 0.18],
        'debtToEquity': [1.8, 0.4, 0.1, 0.6, 0.05, 0.4, 0.1, 1.2, 0.5, 0.7],
        'revenueGrowth': [0.08, 0.12, 0.10, 0.15, -0.02, 0.50, 0.20, 0.05, 0.10, 0.06],
        'earningsGrowth': [0.10, 0.15, 0.08, 0.20, -0.05, 0.80, 0.25, 0.08, 0.12, 0.05],
        'marketCap': [3e12, 2.8e12, 1.8e12, 1.5e12, 1e12, 1.2e12, 0.8e12, 0.5e12, 0.5e12, 0.4e12],
        'currentPrice': [180, 380, 140, 150, 350, 500, 250, 180, 280, 160],
    }
    
    return pd.DataFrame(data, index=tickers)


@pytest.fixture
def sample_market_prices(sample_prices):
    """Market benchmark prices (SPY-like)."""
    dates = sample_prices.index
    np.random.seed(42)
    spy_returns = np.random.normal(0.0005, 0.01, len(dates))
    spy_prices = 400 * np.cumprod(1 + spy_returns)
    
    return pd.DataFrame({'SPY': spy_prices}, index=dates)


@pytest.fixture
def sample_sector_map():
    """Sample GICS sector mapping."""
    return {
        'AAPL': 'Information Technology',
        'MSFT': 'Information Technology',
        'GOOGL': 'Communication Services',
        'AMZN': 'Consumer Discretionary',
        'META': 'Communication Services',
        'NVDA': 'Information Technology',
        'TSLA': 'Consumer Discretionary',
        'JPM': 'Financials',
        'V': 'Financials',
        'WMT': 'Consumer Staples',
    }


# ============================================================================
# Factor Registry Tests
# ============================================================================

class TestFactorEngineV2FactorRegistry:
    """Tests for the factor registry."""
    
    def test_registry_creation(self):
        """Test that the default registry is created correctly."""
        registry = create_default_registry()
        
        assert len(registry.categories) == 6
        assert 'value' in registry.categories
        assert 'momentum' in registry.categories
        assert 'quality' in registry.categories
        assert 'growth' in registry.categories
        assert 'volatility' in registry.categories
        assert 'technical' in registry.categories
    
    def test_total_factor_count(self):
        """Test that we have 30+ individual factors."""
        registry = create_default_registry()
        
        # PRD specifies 12+ factors, we should have 30+
        assert registry.total_factor_count() >= 30
    
    def test_list_factors(self):
        """Test listing all factors by category."""
        registry = create_default_registry()
        factors = registry.list_factors()
        
        assert len(factors['value']) >= 5
        assert len(factors['momentum']) >= 5
        assert len(factors['quality']) >= 5
        assert len(factors['growth']) >= 5
        assert len(factors['volatility']) >= 4
        assert len(factors['technical']) >= 5


# ============================================================================
# Individual Factor Tests
# ============================================================================

class TestFactorEngineV2ValueFactors:
    """Tests for value factors."""
    
    def test_value_factor_compute(self, sample_prices, sample_fundamentals):
        """Test value factor computation."""
        calc = ValueFactors()
        scores = calc.compute(sample_prices, sample_fundamentals)
        
        assert not scores.empty
        assert len(scores.columns) == 6
        assert all(scores.min() >= 0)
        assert all(scores.max() <= 1)
    
    def test_value_composite(self, sample_prices, sample_fundamentals):
        """Test value composite score."""
        calc = ValueFactors()
        scores = calc.compute(sample_prices, sample_fundamentals)
        composite = calc.get_composite_score(scores)
        
        assert len(composite) == len(sample_fundamentals)
        assert composite.min() >= 0
        assert composite.max() <= 1


class TestFactorEngineV2MomentumFactors:
    """Tests for momentum factors."""
    
    def test_momentum_factor_compute(self, sample_prices, sample_fundamentals):
        """Test momentum factor computation."""
        calc = MomentumFactors()
        scores = calc.compute(sample_prices, sample_fundamentals)
        
        assert not scores.empty
        assert all(scores.min() >= 0)
        assert all(scores.max() <= 1)
    
    def test_momentum_with_short_history(self, sample_fundamentals):
        """Test momentum with insufficient price history."""
        short_prices = pd.DataFrame(
            np.random.randn(30, 5),
            columns=['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META']
        )
        
        calc = MomentumFactors()
        scores = calc.compute(short_prices, sample_fundamentals)
        
        # Should return valid scores even with short history
        assert not scores.empty


class TestFactorEngineV2VolatilityFactors:
    """Tests for volatility factors."""
    
    def test_volatility_factor_compute(self, sample_prices, sample_fundamentals, sample_market_prices):
        """Test volatility factor computation."""
        calc = VolatilityFactors()
        scores = calc.compute(sample_prices, sample_fundamentals, sample_market_prices)
        
        assert not scores.empty
        assert 'realized_vol' in scores.columns
        assert 'beta' in scores.columns
        assert 'max_drawdown' in scores.columns
    
    def test_beta_calculation(self, sample_prices, sample_fundamentals, sample_market_prices):
        """Test that beta calculation is reasonable."""
        calc = VolatilityFactors()
        scores = calc.compute(sample_prices, sample_fundamentals, sample_market_prices)
        
        # Beta scores should be between 0 and 1 (percentile ranked)
        assert scores['beta'].min() >= 0
        assert scores['beta'].max() <= 1


class TestFactorEngineV2TechnicalFactors:
    """Tests for technical factors."""
    
    def test_technical_factor_compute(self, sample_prices, sample_fundamentals):
        """Test technical factor computation."""
        calc = TechnicalFactors()
        scores = calc.compute(sample_prices, sample_fundamentals)
        
        assert not scores.empty
        assert 'rsi' in scores.columns
        assert 'macd_signal' in scores.columns
        assert 'price_vs_200sma' in scores.columns


# ============================================================================
# Regime Detection Tests
# ============================================================================

class TestFactorEngineV2RegimeDetector:
    """Tests for market regime detection."""
    
    def test_regime_classification(self, sample_market_prices):
        """Test basic regime classification."""
        detector = RegimeDetector()
        result = detector.classify(sample_market_prices)
        
        assert result.regime in [MarketRegime.BULL, MarketRegime.BEAR, 
                                  MarketRegime.SIDEWAYS, MarketRegime.CRISIS]
        assert 0 <= result.confidence <= 1
    
    def test_bull_regime_detection(self):
        """Test detection of bull market."""
        # Create uptrending market data
        dates = pd.date_range(end=datetime.now(), periods=250, freq='D')
        prices = pd.DataFrame({
            'SPY': 400 * np.cumprod(1 + np.random.normal(0.001, 0.005, 250))
        }, index=dates)
        
        detector = RegimeDetector()
        result = detector.classify(prices)
        
        # With consistent uptrend, should likely be bull or sideways
        assert result.regime in [MarketRegime.BULL, MarketRegime.SIDEWAYS]
    
    def test_crisis_detection_high_vix(self):
        """Test that high VIX triggers crisis regime."""
        dates = pd.date_range(end=datetime.now(), periods=250, freq='D')
        prices = pd.DataFrame({
            'SPY': 400 * np.cumprod(1 + np.random.normal(-0.002, 0.03, 250))
        }, index=dates)
        vix = pd.Series(np.full(250, 40.0), index=dates)  # VIX at 40
        
        detector = RegimeDetector()
        result = detector.classify(prices, vix_data=vix)
        
        assert result.regime == MarketRegime.CRISIS


# ============================================================================
# Adaptive Weights Tests
# ============================================================================

class TestAdaptiveWeights:
    """Tests for adaptive factor weights."""
    
    def test_weights_sum_to_one(self):
        """Test that weights sum to 1.0 for all regimes."""
        weights_system = AdaptiveWeights()
        
        for regime in MarketRegime:
            weights = weights_system.get_weights(regime)
            assert abs(sum(weights.values()) - 1.0) < 0.01
    
    def test_regime_specific_weights(self):
        """Test that different regimes have different weights."""
        weights_system = AdaptiveWeights(use_momentum_overlay=False)
        
        bull_weights = weights_system.get_weights(MarketRegime.BULL)
        bear_weights = weights_system.get_weights(MarketRegime.BEAR)
        
        # Bull should favor momentum, bear should favor quality/volatility
        assert bull_weights['momentum'] > bear_weights['momentum']
        assert bear_weights['quality'] > bull_weights['quality']
    
    def test_crisis_weights(self):
        """Test that crisis regime is defensive."""
        weights_system = AdaptiveWeights(use_momentum_overlay=False)
        crisis_weights = weights_system.get_weights(MarketRegime.CRISIS)
        
        # Crisis should heavily weight volatility and quality
        assert crisis_weights['volatility'] >= 0.4
        assert crisis_weights['quality'] >= 0.3
        assert crisis_weights['momentum'] <= 0.05


# ============================================================================
# Factor Engine v2 Integration Tests
# ============================================================================

class TestFactorEngineV2:
    """Integration tests for Factor Engine v2."""
    
    def test_engine_initialization(self):
        """Test engine initializes correctly."""
        engine = FactorEngineV2()
        
        assert engine.registry is not None
        assert engine.regime_detector is not None
        assert engine.adaptive_weights is not None
    
    def test_compute_scores(self, sample_prices, sample_fundamentals):
        """Test full score computation."""
        engine = FactorEngineV2()
        result = engine.compute_scores(sample_prices, sample_fundamentals)
        
        assert result.scores is not None
        assert result.category_scores is not None
        assert result.composite is not None
        assert result.factor_count >= 30
        assert result.ticker_count == len(sample_fundamentals)
    
    def test_compute_scores_with_sector_map(
        self, sample_prices, sample_fundamentals, sample_sector_map
    ):
        """Test score computation with sector-relative scoring."""
        engine = FactorEngineV2(use_sector_relative=True)
        result = engine.compute_scores(
            sample_prices, sample_fundamentals, sector_map=sample_sector_map
        )
        
        assert result.scores is not None
        assert result.composite is not None
    
    def test_get_top_stocks(self, sample_prices, sample_fundamentals):
        """Test getting top stocks."""
        engine = FactorEngineV2()
        result = engine.compute_scores(sample_prices, sample_fundamentals)
        
        top_5 = result.get_top_stocks(5)
        assert len(top_5) == 5
        assert 'ticker' in top_5.columns
        assert 'composite' in top_5.columns
    
    def test_get_stock_profile(self, sample_prices, sample_fundamentals):
        """Test getting individual stock profile."""
        engine = FactorEngineV2()
        result = engine.compute_scores(sample_prices, sample_fundamentals)
        
        profile = result.get_stock_profile('AAPL')
        assert profile['ticker'] == 'AAPL'
        assert 'composite' in profile
        assert 'category_scores' in profile
        assert 'factor_scores' in profile
    
    def test_static_weights_mode(self, sample_prices, sample_fundamentals):
        """Test engine with static weights (v1 compatibility)."""
        engine = FactorEngineV2(
            use_adaptive_weights=False,
            use_sector_relative=False,
            use_factor_momentum=False,
        )
        result = engine.compute_scores(sample_prices, sample_fundamentals)
        
        assert result.scores is not None
        assert result.composite is not None


# ============================================================================
# Backward Compatibility Tests
# ============================================================================

class TestBackwardCompatibility:
    """Tests for backward compatibility with v1."""
    
    def test_v2_compatible_function(self, sample_prices, sample_fundamentals):
        """Test the v1-compatible compute_composite_scores_v2 function."""
        scores = compute_composite_scores_v2(sample_prices, sample_fundamentals)
        
        # Should return DataFrame with expected columns
        assert 'value' in scores.columns
        assert 'momentum' in scores.columns
        assert 'quality' in scores.columns
        assert 'growth' in scores.columns
        assert 'composite' in scores.columns
        
        # Should also have new columns
        assert 'volatility' in scores.columns
        assert 'technical' in scores.columns
    
    def test_score_range(self, sample_prices, sample_fundamentals):
        """Test that all scores are in valid range."""
        engine = FactorEngineV2()
        result = engine.compute_scores(sample_prices, sample_fundamentals)
        
        # All scores should be between 0 and 1
        for col in result.category_scores.columns:
            assert result.category_scores[col].min() >= 0
            assert result.category_scores[col].max() <= 1
        
        assert result.composite.min() >= 0
        assert result.composite.max() <= 1


# ============================================================================
# Edge Cases
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_empty_prices(self, sample_fundamentals):
        """Test handling of empty price data."""
        empty_prices = pd.DataFrame()
        
        engine = FactorEngineV2()
        # Should handle gracefully (may return neutral scores)
        try:
            result = engine.compute_scores(empty_prices, sample_fundamentals)
            # If it doesn't raise, check scores are valid
            assert result.composite is not None
        except (ValueError, KeyError):
            # Acceptable to raise on empty data
            pass
    
    def test_missing_fundamental_fields(self, sample_prices):
        """Test handling of missing fundamental fields."""
        # Fundamentals with only some fields
        sparse_fundamentals = pd.DataFrame({
            'trailingPE': [20, 25, 30],
            'marketCap': [1e12, 2e12, 3e12],
        }, index=['AAPL', 'MSFT', 'GOOGL'])
        
        engine = FactorEngineV2()
        result = engine.compute_scores(sample_prices, sparse_fundamentals)
        
        # Should still produce valid scores
        assert result.composite is not None
        assert len(result.composite) > 0
    
    def test_nan_handling(self, sample_prices, sample_fundamentals):
        """Test handling of NaN values in data."""
        # Introduce NaNs
        fundamentals_with_nan = sample_fundamentals.copy()
        fundamentals_with_nan.loc['AAPL', 'trailingPE'] = np.nan
        fundamentals_with_nan.loc['MSFT', 'returnOnEquity'] = np.nan
        
        engine = FactorEngineV2()
        result = engine.compute_scores(sample_prices, fundamentals_with_nan)
        
        # Should handle NaNs and produce valid scores
        assert not result.composite.isna().all()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
