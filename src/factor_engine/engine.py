"""Factor Engine v2.0 - Main orchestrator for multi-factor scoring."""

import logging
from datetime import date
from typing import Optional

import pandas as pd

from src.factor_engine.factors import FactorRegistry
from src.factor_engine.regime import MarketRegime, RegimeDetector
from src.factor_engine.sector import SectorRelativeScorer, get_sector_from_fundamentals
from src.factor_engine.weights import AdaptiveWeightManager

logger = logging.getLogger(__name__)


class FactorEngineV2:
    """Advanced multi-factor scoring engine with regime detection.

    Features:
    - 6 factor categories (value, momentum, quality, growth, volatility, technical)
    - Regime detection (bull, bear, sideways, crisis)
    - Adaptive weights based on regime
    - Sector-relative scoring option
    - Backward compatible with v1 output format

    Usage:
        engine = FactorEngineV2()
        scores = engine.compute_all_scores(prices, fundamentals, returns)
    """

    def __init__(
        self,
        use_adaptive_weights: bool = True,
        use_sector_relative: bool = True,
        use_momentum_overlay: bool = True,
    ):
        """Initialize the factor engine.

        Args:
            use_adaptive_weights: Use regime-based weight adaptation
            use_sector_relative: Apply sector-relative scoring adjustment
            use_momentum_overlay: Tilt weights toward recently-performing factors
        """
        self.use_adaptive_weights = use_adaptive_weights
        self.use_sector_relative = use_sector_relative

        # Initialize components
        self.factor_registry = FactorRegistry()
        self.regime_detector = RegimeDetector()
        self.weight_manager = AdaptiveWeightManager(
            regime_detector=self.regime_detector,
            enable_momentum_overlay=use_momentum_overlay,
        )
        self.sector_scorer = SectorRelativeScorer()

        # Cache
        self._last_regime: Optional[MarketRegime] = None
        self._last_weights: Optional[dict] = None

    def compute_all_scores(
        self,
        prices: pd.DataFrame,
        fundamentals: pd.DataFrame,
        returns: Optional[pd.DataFrame] = None,
        sp500_prices: Optional[pd.Series] = None,
        as_of_date: Optional[date] = None,
    ) -> pd.DataFrame:
        """Compute factor scores for entire universe.

        Args:
            prices: DataFrame[dates x tickers] of adjusted close prices
            fundamentals: DataFrame[tickers x fields] of fundamental data
            returns: DataFrame[tickers x {ret_3m, ret_6m, ret_12m}] (computed if None)
            sp500_prices: S&P 500 price series for regime detection
            as_of_date: Date for regime classification

        Returns:
            DataFrame[tickers x factors] with columns:
            - value, momentum, quality, growth (v1 compatible)
            - volatility, technical (v2 new)
            - composite (weighted average)
            - regime (current market regime)
        """
        # Ensure returns DataFrame exists
        if returns is None:
            returns = self._compute_returns(prices)

        # Get universe (union of all tickers)
        all_tickers = (
            fundamentals.index.union(returns.index)
            if not returns.empty
            else fundamentals.index
        )

        # Align inputs
        fund_aligned = fundamentals.reindex(all_tickers)
        ret_aligned = returns.reindex(all_tickers) if not returns.empty else returns

        # 1. Detect current regime
        regime = self.regime_detector.classify(
            as_of_date=as_of_date,
            sp500_prices=sp500_prices,
        )
        self._last_regime = regime

        # 2. Get adaptive weights
        weights = self.weight_manager.get_weights(
            regime=regime,
            use_adaptive=self.use_adaptive_weights,
        )
        self._last_weights = weights

        # 3. Compute each factor category
        category_scores = {}
        for name, category in self.factor_registry.all().items():
            try:
                score = category.compute(prices, fund_aligned, ret_aligned)
                category_scores[name] = score.reindex(all_tickers).fillna(0.5)
            except Exception as e:
                logger.warning("Failed to compute %s factor: %s", name, e)
                category_scores[name] = pd.Series(0.5, index=all_tickers)

        # Build scores DataFrame
        scores = pd.DataFrame(category_scores, index=all_tickers)

        # 4. Apply sector-relative adjustment (optional)
        if self.use_sector_relative:
            sector_mapping = get_sector_from_fundamentals(fund_aligned)
            if not sector_mapping.empty:
                scores = self.sector_scorer.compute_blended_scores(
                    scores, sector_mapping
                )

        # 5. Compute composite score with adaptive weights
        composite = pd.Series(0.0, index=all_tickers)
        for factor, weight in weights.items():
            if factor in scores.columns:
                composite += weight * scores[factor]

        scores["composite"] = composite

        # 6. Add regime metadata
        scores["regime"] = regime.value

        logger.info(
            "Computed scores for %d tickers (regime=%s)",
            len(scores),
            regime.value,
        )

        return scores

    def compute_v1_compatible_scores(
        self,
        prices: pd.DataFrame,
        fundamentals: pd.DataFrame,
        returns: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """Compute scores in v1-compatible format (4 factors only).

        Returns DataFrame with columns:
        - value, momentum, quality, growth, composite

        Uses static v1 weights for backward compatibility.
        """
        # Compute full v2 scores
        full_scores = self.compute_all_scores(prices, fundamentals, returns)

        # Get v1 weights
        v1_weights = self.weight_manager.get_static_weights_v1()

        # Recompute composite with v1 weights
        composite = pd.Series(0.0, index=full_scores.index)
        for factor, weight in v1_weights.items():
            if factor in full_scores.columns:
                composite += weight * full_scores[factor]

        # Return only v1 columns
        v1_scores = full_scores[["value", "momentum", "quality", "growth"]].copy()
        v1_scores["composite"] = composite

        return v1_scores

    def _compute_returns(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Compute momentum returns from price data."""
        if prices.empty:
            return pd.DataFrame(columns=["ret_3m", "ret_6m", "ret_12m"])

        # Skip last 21 trading days (1 month) to avoid short-term reversal
        prices_ex_last = prices.iloc[:-21] if len(prices) > 21 else prices

        results = {}
        for col in prices_ex_last.columns:
            series = prices_ex_last[col].dropna()
            if len(series) < 22:
                results[col] = {"ret_3m": pd.NA, "ret_6m": pd.NA, "ret_12m": pd.NA}
                continue

            current = series.iloc[-1]

            # 3-month return (~63 trading days)
            idx_3m = max(0, len(series) - 63)
            ret_3m = (
                (current / series.iloc[idx_3m] - 1)
                if series.iloc[idx_3m] > 0
                else pd.NA
            )

            # 6-month return (~126 trading days)
            idx_6m = max(0, len(series) - 126)
            ret_6m = (
                (current / series.iloc[idx_6m] - 1)
                if series.iloc[idx_6m] > 0
                else pd.NA
            )

            # 12-month return (~252 trading days)
            idx_12m = max(0, len(series) - 252)
            ret_12m = (
                (current / series.iloc[idx_12m] - 1)
                if series.iloc[idx_12m] > 0
                else pd.NA
            )

            results[col] = {"ret_3m": ret_3m, "ret_6m": ret_6m, "ret_12m": ret_12m}

        return pd.DataFrame(results).T

    @property
    def last_regime(self) -> Optional[MarketRegime]:
        """Get the last detected market regime."""
        return self._last_regime

    @property
    def last_weights(self) -> Optional[dict]:
        """Get the last computed factor weights."""
        return self._last_weights

    def get_factor_breakdown(
        self,
        ticker: str,
        prices: pd.DataFrame,
        fundamentals: pd.DataFrame,
    ) -> dict:
        """Get detailed factor breakdown for a single ticker.

        Returns dict with:
        - Category scores
        - Sub-factor scores
        - Regime and weights
        """
        returns = self._compute_returns(prices)

        breakdown = {
            "ticker": ticker,
            "regime": self._last_regime.value if self._last_regime else "unknown",
            "weights": self._last_weights or {},
            "category_scores": {},
            "sub_factors": {},
        }

        # Get single-row fundamentals and returns
        fund_row = fundamentals.loc[[ticker]] if ticker in fundamentals.index else pd.DataFrame()
        ret_row = returns.loc[[ticker]] if ticker in returns.index else pd.DataFrame()

        for name, category in self.factor_registry.all().items():
            try:
                # Category score
                score = category.compute(prices, fund_row, ret_row)
                if ticker in score.index:
                    breakdown["category_scores"][name] = score.loc[ticker]

                # Sub-factor breakdown
                sub_scores = category.compute_sub_factors(prices, fund_row, ret_row)
                if ticker in sub_scores.index:
                    breakdown["sub_factors"][name] = sub_scores.loc[ticker].to_dict()
            except Exception as e:
                logger.debug("Failed to get breakdown for %s/%s: %s", ticker, name, e)

        return breakdown
