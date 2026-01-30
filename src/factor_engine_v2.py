"""Factor Engine v2.0 - Next-generation multi-factor scoring system.

Key improvements over v1:
1. 12+ factors across 6 categories (up from 4 factors)
2. Adaptive weights based on market regime
3. Sector-relative scoring (not just universe-relative)
4. Factor momentum overlay
5. Multi-timeframe analysis support

Usage:
    from src.factor_engine_v2 import FactorEngineV2
    
    engine = FactorEngineV2()
    scores = engine.compute_scores(prices, fundamentals)
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

import numpy as np
import pandas as pd

from src.factors.registry import FactorRegistry, create_default_registry
from src.regime.detector import RegimeDetector, MarketRegime, RegimeClassification
from src.regime.weights import AdaptiveWeights, STATIC_WEIGHTS


@dataclass
class FactorScoresV2:
    """Container for factor scores with metadata."""
    
    # Core scores DataFrame: tickers x factors
    scores: pd.DataFrame
    
    # Category-level scores
    category_scores: pd.DataFrame
    
    # Final composite score
    composite: pd.Series
    
    # Metadata
    regime: MarketRegime
    regime_confidence: float
    weights_used: dict[str, float]
    computed_at: datetime
    factor_count: int
    ticker_count: int
    
    def get_top_stocks(self, n: int = 10, by: str = "composite") -> pd.DataFrame:
        """Get top N stocks by a given score."""
        if by == "composite":
            top = self.composite.nlargest(n)
            return pd.DataFrame({
                "ticker": top.index,
                "composite": top.values,
            }).reset_index(drop=True)
        elif by in self.category_scores.columns:
            top = self.category_scores[by].nlargest(n)
            return pd.DataFrame({
                "ticker": top.index,
                by: top.values,
            }).reset_index(drop=True)
        else:
            raise ValueError(f"Unknown score type: {by}")
    
    def get_stock_profile(self, ticker: str) -> dict:
        """Get detailed factor profile for a single stock."""
        if ticker not in self.scores.index:
            raise ValueError(f"Ticker not found: {ticker}")
        
        return {
            "ticker": ticker,
            "composite": float(self.composite[ticker]),
            "category_scores": self.category_scores.loc[ticker].to_dict(),
            "factor_scores": self.scores.loc[ticker].to_dict(),
            "percentile_rank": float(self.composite.rank(pct=True)[ticker]),
        }


class FactorEngineV2:
    """Next-generation factor scoring engine.
    
    Features:
    - 12+ factors across 6 categories
    - Regime-adaptive weights
    - Sector-relative scoring
    - Factor momentum overlay
    
    Example:
        engine = FactorEngineV2()
        result = engine.compute_scores(prices, fundamentals)
        
        print(f"Regime: {result.regime.value}")
        print(result.get_top_stocks(10))
    """
    
    SECTOR_WEIGHT = 0.40  # Weight for sector-relative score
    UNIVERSE_WEIGHT = 0.60  # Weight for universe-relative score
    
    def __init__(
        self,
        use_adaptive_weights: bool = True,
        use_sector_relative: bool = True,
        use_factor_momentum: bool = True,
    ):
        """Initialize the factor engine.
        
        Args:
            use_adaptive_weights: Use regime-based adaptive weights
            use_sector_relative: Use sector-relative scoring blend
            use_factor_momentum: Apply factor momentum overlay
        """
        self.use_adaptive_weights = use_adaptive_weights
        self.use_sector_relative = use_sector_relative
        self.use_factor_momentum = use_factor_momentum
        
        # Initialize components
        self.registry = create_default_registry()
        self.regime_detector = RegimeDetector()
        self.adaptive_weights = AdaptiveWeights(
            use_momentum_overlay=use_factor_momentum,
        )
        
        self._sector_map: Optional[dict[str, str]] = None
    
    def set_sector_map(self, sector_map: dict[str, str]) -> None:
        """Set the ticker-to-sector mapping for sector-relative scoring.
        
        Args:
            sector_map: Dict mapping ticker -> GICS sector name
        """
        self._sector_map = sector_map
    
    def compute_scores(
        self,
        prices: pd.DataFrame,
        fundamentals: pd.DataFrame,
        market_prices: Optional[pd.DataFrame] = None,
        vix_data: Optional[pd.Series] = None,
        sector_map: Optional[dict[str, str]] = None,
    ) -> FactorScoresV2:
        """Compute factor scores for all stocks.
        
        Args:
            prices: Price DataFrame (dates x tickers)
            fundamentals: Fundamentals DataFrame (tickers x fields)
            market_prices: Market benchmark prices for regime detection
            vix_data: VIX data for regime detection
            sector_map: Optional sector mapping override
            
        Returns:
            FactorScoresV2 with all scores and metadata
        """
        if sector_map:
            self._sector_map = sector_map
        
        # Step 1: Detect market regime
        regime_result = self._detect_regime(prices, market_prices, vix_data)
        
        # Step 2: Get adaptive weights
        weights = self._get_weights(regime_result.regime)
        
        # Step 3: Compute all factor scores
        all_factor_scores = self.registry.compute_all(prices, fundamentals, market_prices)
        
        # Step 4: Compute category-level scores
        category_scores = self._compute_category_scores(all_factor_scores)
        
        # Step 5: Apply sector-relative scoring if enabled
        if self.use_sector_relative and self._sector_map:
            category_scores = self._apply_sector_relative(category_scores, fundamentals)
        
        # Step 6: Compute composite score
        composite = self._compute_composite(category_scores, weights)
        
        # Step 7: Combine all individual factor scores into one DataFrame
        combined_scores = self._combine_factor_scores(all_factor_scores)
        
        return FactorScoresV2(
            scores=combined_scores,
            category_scores=category_scores,
            composite=composite,
            regime=regime_result.regime,
            regime_confidence=regime_result.confidence,
            weights_used=weights,
            computed_at=datetime.now(),
            factor_count=self.registry.total_factor_count(),
            ticker_count=len(composite),
        )
    
    def _detect_regime(
        self,
        prices: pd.DataFrame,
        market_prices: Optional[pd.DataFrame],
        vix_data: Optional[pd.Series],
    ) -> RegimeClassification:
        """Detect market regime from available data."""
        # Use market prices if provided, otherwise use prices DataFrame
        market_data = market_prices if market_prices is not None else prices
        
        return self.regime_detector.classify(
            market_prices=market_data,
            vix_data=vix_data,
            universe_prices=prices,
        )
    
    def _get_weights(self, regime: MarketRegime) -> dict[str, float]:
        """Get factor weights based on regime."""
        if self.use_adaptive_weights:
            return self.adaptive_weights.get_weights(regime)
        else:
            return STATIC_WEIGHTS.copy()
    
    def _compute_category_scores(
        self,
        all_factor_scores: dict[str, pd.DataFrame],
    ) -> pd.DataFrame:
        """Compute category-level scores from individual factors."""
        category_scores = pd.DataFrame()
        
        for category_name, factor_df in all_factor_scores.items():
            calculator = self.registry.get_calculator(category_name)
            if calculator:
                category_scores[category_name] = calculator.get_composite_score(factor_df)
            else:
                # Simple average as fallback
                category_scores[category_name] = factor_df.mean(axis=1)
        
        return category_scores
    
    def _apply_sector_relative(
        self,
        category_scores: pd.DataFrame,
        fundamentals: pd.DataFrame,
    ) -> pd.DataFrame:
        """Apply sector-relative scoring blend.
        
        Final score = UNIVERSE_WEIGHT * universe_score + SECTOR_WEIGHT * sector_score
        """
        if not self._sector_map:
            return category_scores
        
        # Add sector information
        tickers = category_scores.index
        sectors = pd.Series({t: self._sector_map.get(t, "Unknown") for t in tickers})
        
        adjusted_scores = category_scores.copy()
        
        for category in category_scores.columns:
            universe_scores = category_scores[category]
            
            # Compute sector-relative scores
            sector_scores = pd.Series(index=tickers, dtype=float)
            
            for sector in sectors.unique():
                sector_mask = sectors == sector
                sector_tickers = sectors[sector_mask].index
                
                if len(sector_tickers) < 5:
                    # Not enough stocks for meaningful sector ranking
                    sector_scores[sector_tickers] = universe_scores[sector_tickers]
                else:
                    # Rank within sector
                    sector_scores[sector_tickers] = universe_scores[sector_tickers].rank(pct=True)
            
            # Blend universe and sector scores
            adjusted_scores[category] = (
                self.UNIVERSE_WEIGHT * universe_scores +
                self.SECTOR_WEIGHT * sector_scores.fillna(0.5)
            )
        
        return adjusted_scores
    
    def _compute_composite(
        self,
        category_scores: pd.DataFrame,
        weights: dict[str, float],
    ) -> pd.Series:
        """Compute weighted composite score."""
        composite = pd.Series(0.0, index=category_scores.index)
        
        for category, weight in weights.items():
            if category in category_scores.columns:
                composite += weight * category_scores[category].fillna(0.5)
        
        return composite
    
    def _combine_factor_scores(
        self,
        all_factor_scores: dict[str, pd.DataFrame],
    ) -> pd.DataFrame:
        """Combine all individual factor scores into a single DataFrame."""
        combined = pd.DataFrame()
        
        for category_name, factor_df in all_factor_scores.items():
            for col in factor_df.columns:
                combined[f"{category_name}_{col}"] = factor_df[col]
        
        return combined
    
    def get_regime_summary(self) -> str:
        """Get summary of current regime detection logic."""
        return """
Factor Engine v2.0 - Regime Detection Summary
==============================================

Regimes:
- BULL: SPY > 200 SMA, VIX < 15, breadth > 55%
  → Favor: Momentum (35%), Growth (25%)
  
- BEAR: SPY < 200 SMA, VIX > 25, breadth < 45%
  → Favor: Quality (35%), Volatility (25%), Value (25%)
  
- SIDEWAYS: Mixed signals, moderate conditions
  → Balanced: Value (25%), Quality (25%), Momentum (15%)
  
- CRISIS: VIX > 35 or correlation spike
  → Defensive: Volatility (50%), Quality (40%)

Factor Categories (6):
1. Value (6 factors): Earnings yield, FCF yield, B/M, EV/EBITDA, Div yield, P/E
2. Momentum (6 factors): 12-1m, 6-1m, 3m returns, 52w high, earnings/revenue mom
3. Quality (7 factors): ROE, ROA, ROIC, Gross profit/assets, Accruals, D/E, Coverage
4. Growth (6 factors): Revenue, EPS, FCF growth, Acceleration, R&D, Asset growth
5. Volatility (5 factors): Realized vol, Idio vol, Beta, Downside beta, Drawdown
6. Technical (6 factors): RSI, MACD, Volume, 200 SMA, 50 SMA, Bollinger

Total: 36 individual factors
"""


# Convenience function for backward compatibility
def compute_composite_scores_v2(
    prices: pd.DataFrame,
    fundamentals: pd.DataFrame,
    use_adaptive: bool = True,
) -> pd.DataFrame:
    """Compute factor scores using the v2 engine.
    
    This is a drop-in replacement for the v1 compute_composite_scores function.
    
    Args:
        prices: Price DataFrame (dates x tickers)
        fundamentals: Fundamentals DataFrame (tickers x fields)
        use_adaptive: Whether to use adaptive regime-based weights
        
    Returns:
        DataFrame with columns: value, momentum, quality, growth, 
                               volatility, technical, composite
    """
    engine = FactorEngineV2(
        use_adaptive_weights=use_adaptive,
        use_sector_relative=False,  # Disable for backward compat
        use_factor_momentum=False,
    )
    
    result = engine.compute_scores(prices, fundamentals)
    
    # Return in v1-compatible format
    output = result.category_scores.copy()
    output["composite"] = result.composite
    
    return output
