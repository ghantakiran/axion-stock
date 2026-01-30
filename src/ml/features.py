"""Feature Engineering Pipeline.

Creates ML-ready features from raw data with:
- Cross-sectional normalization (ranking)
- Sector-relative features
- Interaction features
- Lagged features (no look-ahead)
- Rolling statistics
- Macro features
"""

import logging
from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from src.ml.config import FeatureConfig

logger = logging.getLogger(__name__)


class FeatureEngineer:
    """Create ML features from raw stock and market data.

    All features use only data available before the prediction date
    to prevent look-ahead bias.

    Example:
        engineer = FeatureEngineer()
        features = engineer.create_features(
            raw_data=stock_data_df,
            macro_data=macro_df,
            target_date=date(2026, 1, 15),
        )
    """

    def __init__(self, config: Optional[FeatureConfig] = None):
        self.config = config or FeatureConfig()
        self._feature_names: list[str] = []

    @property
    def feature_names(self) -> list[str]:
        """Get list of feature names from last create_features call."""
        return self._feature_names

    def create_features(
        self,
        raw_data: pd.DataFrame,
        macro_data: Optional[pd.DataFrame] = None,
        target_date: Optional[date] = None,
    ) -> pd.DataFrame:
        """Create full feature set for a given date.

        Args:
            raw_data: DataFrame indexed by (date, symbol) or symbol with columns
                      for raw factor values. Must only contain data <= target_date.
            macro_data: DataFrame with macro indicators indexed by date.
            target_date: Date for which features are created. Used to filter data.

        Returns:
            DataFrame with features indexed by symbol.
        """
        if raw_data.empty:
            return pd.DataFrame()

        # Filter to data available at target_date
        if target_date is not None and isinstance(raw_data.index, pd.MultiIndex):
            raw_data = raw_data.loc[:target_date]

        # Get latest cross-section
        if isinstance(raw_data.index, pd.MultiIndex):
            # Multi-index (date, symbol) - get latest date
            latest_date = raw_data.index.get_level_values(0).max()
            cross_section = raw_data.loc[latest_date].copy()
        else:
            cross_section = raw_data.copy()

        feature_dfs = []

        # 1. Cross-sectional ranked features
        ranked = self._rank_features(cross_section)
        feature_dfs.append(ranked)

        # 2. Sector-relative features
        if "sector" in cross_section.columns:
            sector_ranked = self._sector_relative_features(cross_section)
            feature_dfs.append(sector_ranked)

        # 3. Interaction features
        interactions = self._create_interactions(ranked)
        feature_dfs.append(interactions)

        # 4. Lagged features
        if isinstance(raw_data.index, pd.MultiIndex):
            lagged = self._create_lags(raw_data, target_date)
            if not lagged.empty:
                feature_dfs.append(lagged)

        # 5. Rolling statistics
        if isinstance(raw_data.index, pd.MultiIndex):
            rolling = self._create_rolling_stats(raw_data, target_date)
            if not rolling.empty:
                feature_dfs.append(rolling)

        # 6. Macro features (broadcast to all stocks)
        if macro_data is not None and not macro_data.empty:
            macro_feats = self._create_macro_features(macro_data, target_date)
            if not macro_feats.empty:
                feature_dfs.append(macro_feats.reindex(cross_section.index))

        # 7. Time features
        if target_date is not None:
            time_feats = self._create_time_features(target_date, cross_section.index)
            feature_dfs.append(time_feats)

        # Combine all features
        features = pd.concat(feature_dfs, axis=1)

        # Remove collinear features
        features = self._remove_collinear(features)

        # Cap at max features
        if len(features.columns) > self.config.max_features:
            features = features.iloc[:, :self.config.max_features]

        # Handle missing values
        features = features.fillna(0.5)  # Neutral value for ranked features

        self._feature_names = list(features.columns)
        return features

    def create_target(
        self,
        returns_data: pd.DataFrame,
        target_date: date,
        forward_days: int = 21,
        num_quintiles: int = 5,
    ) -> pd.Series:
        """Create target variable: forward return quintile.

        Args:
            returns_data: DataFrame with daily returns, columns are symbols.
            target_date: Start date for forward returns.
            forward_days: Number of trading days forward.
            num_quintiles: Number of quintile buckets.

        Returns:
            Series of quintile labels (1=worst to 5=best).
        """
        # Calculate forward returns
        future_start = pd.Timestamp(target_date)
        future_end = future_start + pd.Timedelta(days=forward_days * 1.5)

        future_returns = returns_data.loc[future_start:future_end]
        if len(future_returns) < forward_days:
            logger.warning(f"Insufficient forward data: {len(future_returns)} < {forward_days}")
            return pd.Series(dtype=float)

        # Use exactly forward_days
        future_returns = future_returns.iloc[:forward_days]

        # Cumulative return
        cum_returns = (1 + future_returns).prod() - 1

        # Rank into quintiles
        ranks = cum_returns.rank(pct=True)
        quintiles = (ranks * num_quintiles).clip(1, num_quintiles).astype(int)

        return quintiles

    # =========================================================================
    # Feature Creation Methods
    # =========================================================================

    def _rank_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Cross-sectional percentile ranking of features."""
        numeric_cols = data.select_dtypes(include=[np.number]).columns
        feature_cols = [c for c in numeric_cols if c in self.config.sub_factors + self.config.factor_scores]

        if not feature_cols:
            feature_cols = [c for c in numeric_cols if c != "sector"]

        ranked = data[feature_cols].rank(pct=True)
        ranked.columns = [f"{c}_rank" for c in ranked.columns]
        return ranked

    def _sector_relative_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Sector-relative ranked features."""
        numeric_cols = data.select_dtypes(include=[np.number]).columns
        feature_cols = [c for c in numeric_cols if c != "sector"]

        if not feature_cols or "sector" not in data.columns:
            return pd.DataFrame(index=data.index)

        # Limit to key features for sector-relative
        key_features = [c for c in feature_cols if c in self.config.factor_scores + self.config.sub_factors[:10]]
        if not key_features:
            key_features = feature_cols[:10]

        sector_ranked = data[key_features].copy()
        sector_ranked["sector"] = data["sector"]
        sector_ranked = sector_ranked.groupby("sector")[key_features].rank(pct=True)
        sector_ranked.columns = [f"{c}_sector_rank" for c in sector_ranked.columns]
        return sector_ranked

    def _create_interactions(self, ranked_data: pd.DataFrame) -> pd.DataFrame:
        """Create interaction features from pairs."""
        interactions = pd.DataFrame(index=ranked_data.index)

        for feat1, feat2 in self.config.interactions:
            col1 = f"{feat1}_rank" if f"{feat1}_rank" in ranked_data.columns else feat1
            col2 = f"{feat2}_rank" if f"{feat2}_rank" in ranked_data.columns else feat2

            if col1 in ranked_data.columns and col2 in ranked_data.columns:
                interactions[f"{feat1}_x_{feat2}"] = ranked_data[col1] * ranked_data[col2]

        return interactions

    def _create_lags(
        self,
        data: pd.DataFrame,
        target_date: Optional[date],
    ) -> pd.DataFrame:
        """Create lagged features (lookback)."""
        if not isinstance(data.index, pd.MultiIndex):
            return pd.DataFrame()

        lagged_features = pd.DataFrame()

        # Get dates available
        dates = data.index.get_level_values(0).unique().sort_values()
        if target_date:
            dates = dates[dates <= pd.Timestamp(target_date)]

        if len(dates) < max(self.config.lag_periods) + 1:
            return pd.DataFrame()

        latest = dates[-1]

        # Key features to lag
        lag_cols = [c for c in data.columns if c in self.config.factor_scores]
        if not lag_cols:
            numeric_cols = data.select_dtypes(include=[np.number]).columns
            lag_cols = list(numeric_cols[:6])

        for lag_days in self.config.lag_periods:
            lag_idx = max(0, len(dates) - 1 - lag_days)
            lag_date = dates[lag_idx]

            if lag_date in data.index.get_level_values(0):
                lagged = data.loc[lag_date, lag_cols].copy()
                lagged.columns = [f"{c}_lag{lag_days}d" for c in lagged.columns]
                if lagged_features.empty:
                    lagged_features = lagged
                else:
                    lagged_features = lagged_features.join(lagged, how="outer")

        return lagged_features

    def _create_rolling_stats(
        self,
        data: pd.DataFrame,
        target_date: Optional[date],
    ) -> pd.DataFrame:
        """Create rolling statistics features."""
        if not isinstance(data.index, pd.MultiIndex):
            return pd.DataFrame()

        dates = data.index.get_level_values(0).unique().sort_values()
        if target_date:
            dates = dates[dates <= pd.Timestamp(target_date)]

        if len(dates) < max(self.config.rolling_windows) + 1:
            return pd.DataFrame()

        # Use factor scores for rolling stats
        roll_cols = [c for c in data.columns if c in self.config.factor_scores[:3]]
        if not roll_cols:
            return pd.DataFrame()

        latest = dates[-1]
        latest_data = data.loc[latest]

        rolling_features = pd.DataFrame(index=latest_data.index)

        for window in self.config.rolling_windows:
            window_dates = dates[-window:]
            window_data = data.loc[window_dates]

            for col in roll_cols:
                if col in window_data.columns:
                    # Mean and std of cross-sectional ranks over window
                    by_symbol = window_data.groupby(level=1)[col]
                    rolling_features[f"{col}_mean_{window}d"] = by_symbol.mean()
                    rolling_features[f"{col}_std_{window}d"] = by_symbol.std()

        return rolling_features

    def _create_macro_features(
        self,
        macro_data: pd.DataFrame,
        target_date: Optional[date],
    ) -> pd.DataFrame:
        """Create macro environment features."""
        if macro_data.empty:
            return pd.DataFrame()

        if target_date:
            macro_data = macro_data.loc[:target_date]

        if macro_data.empty:
            return pd.DataFrame()

        latest = macro_data.iloc[-1]
        # Return as single-row DataFrame, will be broadcast
        return pd.DataFrame([latest])

    def _create_time_features(
        self,
        target_date: date,
        index: pd.Index,
    ) -> pd.DataFrame:
        """Create time-based features."""
        time_feats = pd.DataFrame(index=index)
        time_feats["month_of_year"] = target_date.month / 12
        time_feats["quarter"] = (target_date.month - 1) // 3 / 3
        time_feats["day_of_month"] = target_date.day / 31
        return time_feats

    def _remove_collinear(self, features: pd.DataFrame) -> pd.DataFrame:
        """Remove highly correlated features."""
        if len(features.columns) <= 1:
            return features

        # Calculate correlation matrix
        corr = features.corr().abs()

        # Find pairs above threshold
        upper = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool))

        to_drop = set()
        for col in upper.columns:
            high_corr = upper[col][upper[col] > self.config.collinearity_threshold]
            if not high_corr.empty:
                to_drop.add(col)

        if to_drop:
            logger.info(f"Removing {len(to_drop)} collinear features")
            features = features.drop(columns=list(to_drop))

        return features

    # =========================================================================
    # Regime Features
    # =========================================================================

    def create_regime_features(
        self,
        market_data: pd.DataFrame,
        target_date: Optional[date] = None,
    ) -> pd.DataFrame:
        """Create features for regime classification.

        Args:
            market_data: DataFrame with market indicators
                         (SPX returns, VIX, yield curve, etc.)
            target_date: Date for feature calculation.

        Returns:
            DataFrame with regime features (single row per date).
        """
        if target_date:
            market_data = market_data.loc[:target_date]

        if market_data.empty or len(market_data) < 60:
            return pd.DataFrame()

        features = {}

        # Return features
        if "sp500_close" in market_data.columns:
            prices = market_data["sp500_close"]
            features["sp500_return_20d"] = prices.pct_change(20).iloc[-1]
            features["sp500_return_60d"] = prices.pct_change(60).iloc[-1]
            features["sp500_volatility_20d"] = prices.pct_change().rolling(20).std().iloc[-1] * np.sqrt(252)

        # VIX features
        if "vix" in market_data.columns:
            features["vix_level"] = market_data["vix"].iloc[-1]
            if "vix3m" in market_data.columns:
                features["vix_term_structure"] = (
                    market_data["vix"].iloc[-1] - market_data["vix3m"].iloc[-1]
                )

        # Yield curve
        if "yield_10y" in market_data.columns and "yield_2y" in market_data.columns:
            features["yield_curve_10y_2y"] = (
                market_data["yield_10y"].iloc[-1] - market_data["yield_2y"].iloc[-1]
            )

        # Credit spread
        if "credit_spread_hy" in market_data.columns and "credit_spread_ig" in market_data.columns:
            features["credit_spread_hy_ig"] = (
                market_data["credit_spread_hy"].iloc[-1] - market_data["credit_spread_ig"].iloc[-1]
            )

        # Breadth indicators
        if "advance_decline" in market_data.columns:
            features["advance_decline_10d"] = market_data["advance_decline"].rolling(10).mean().iloc[-1]

        if "pct_above_200sma" in market_data.columns:
            features["pct_above_200sma"] = market_data["pct_above_200sma"].iloc[-1]

        if "put_call_ratio" in market_data.columns:
            features["put_call_ratio"] = market_data["put_call_ratio"].iloc[-1]

        return pd.DataFrame([features])
