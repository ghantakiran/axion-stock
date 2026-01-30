"""Cryptocurrency Integration.

Factor model, data provider, and execution support for crypto assets.
"""

import logging
from datetime import date, datetime
from typing import Optional

import numpy as np
import pandas as pd

from src.multi_asset.config import (
    CryptoCategory,
    CryptoConfig,
    SUPPORTED_CRYPTO,
)
from src.multi_asset.models import (
    CryptoAsset,
    CryptoFactorScores,
    OnChainMetrics,
)

logger = logging.getLogger(__name__)


class CryptoDataProvider:
    """Provides crypto market data and on-chain metrics.

    In production, fetches from CoinGecko, Binance, Glassnode, etc.
    Here uses in-memory data for the module interface.
    """

    def __init__(self):
        self._assets: dict[str, CryptoAsset] = {}
        self._on_chain: dict[str, OnChainMetrics] = {}
        self._price_history: dict[str, pd.Series] = {}

    def register_asset(self, asset: CryptoAsset):
        """Register a crypto asset."""
        self._assets[asset.symbol.upper()] = asset

    def get_asset(self, symbol: str) -> Optional[CryptoAsset]:
        """Get asset by symbol."""
        return self._assets.get(symbol.upper())

    def get_all_assets(self) -> list[CryptoAsset]:
        """Get all registered assets."""
        return list(self._assets.values())

    def set_on_chain_metrics(self, metrics: OnChainMetrics):
        """Set on-chain metrics for a symbol."""
        self._on_chain[metrics.symbol.upper()] = metrics

    def get_on_chain_metrics(self, symbol: str) -> Optional[OnChainMetrics]:
        """Get on-chain metrics."""
        return self._on_chain.get(symbol.upper())

    def set_price_history(self, symbol: str, prices: pd.Series):
        """Set historical prices for a symbol."""
        self._price_history[symbol.upper()] = prices

    def get_price_history(self, symbol: str) -> Optional[pd.Series]:
        """Get historical prices."""
        return self._price_history.get(symbol.upper())

    def get_returns(self, symbol: str, periods: int = 30) -> Optional[pd.Series]:
        """Get historical returns."""
        prices = self.get_price_history(symbol)
        if prices is None or len(prices) < 2:
            return None
        returns = prices.pct_change().dropna()
        return returns.tail(periods) if len(returns) > periods else returns


class CryptoFactorModel:
    """Factor model for cryptocurrency assets.

    Computes five factors:
    - Value: NVT ratio, MVRV ratio, stock-to-flow
    - Momentum: 30/90/180-day returns
    - Quality: Developer activity, TVL, transaction count
    - Sentiment: Social dominance, fear/greed index
    - Network: Active addresses, hash rate, staking ratio
    """

    def __init__(self, data_provider: Optional[CryptoDataProvider] = None):
        self.data = data_provider or CryptoDataProvider()

    def compute_scores(
        self,
        symbol: str,
        universe: Optional[list[str]] = None,
    ) -> CryptoFactorScores:
        """Compute factor scores for a crypto asset.

        Scores are z-scores normalized against the universe.

        Args:
            symbol: Crypto symbol (e.g. 'BTC').
            universe: List of symbols for cross-sectional ranking.

        Returns:
            CryptoFactorScores with all factor values.
        """
        symbol = symbol.upper()
        scores = CryptoFactorScores(symbol=symbol)

        scores.value = self._compute_value_factor(symbol)
        scores.momentum = self._compute_momentum_factor(symbol)
        scores.quality = self._compute_quality_factor(symbol)
        scores.sentiment = self._compute_sentiment_factor(symbol)
        scores.network = self._compute_network_factor(symbol)
        scores.compute_composite()

        return scores

    def rank_universe(
        self,
        symbols: Optional[list[str]] = None,
        factor: str = "composite",
        top_n: int = 10,
    ) -> list[CryptoFactorScores]:
        """Rank crypto assets by a factor.

        Args:
            symbols: Universe of symbols. Defaults to all supported.
            factor: Factor to rank by.
            top_n: Number of top results.

        Returns:
            Sorted list of factor scores.
        """
        if symbols is None:
            symbols = [s for s, c in SUPPORTED_CRYPTO.items()
                       if c != CryptoCategory.STABLECOIN]

        all_scores = [self.compute_scores(sym) for sym in symbols]
        all_scores.sort(key=lambda s: getattr(s, factor, 0), reverse=True)

        return all_scores[:top_n]

    def _compute_value_factor(self, symbol: str) -> float:
        """Compute value factor from on-chain valuation metrics."""
        metrics = self.data.get_on_chain_metrics(symbol)
        if not metrics:
            return 0.0

        scores = []
        # Lower NVT = more undervalued
        if metrics.nvt_ratio > 0:
            scores.append(max(0, min(1, 1.0 - metrics.nvt_ratio / 100)))
        # MVRV < 1 = undervalued
        if metrics.mvrv_ratio > 0:
            scores.append(max(0, min(1, 1.0 - (metrics.mvrv_ratio - 1) / 3)))
        # Higher S2F = more scarce
        if metrics.stock_to_flow > 0:
            scores.append(min(1, metrics.stock_to_flow / 100))

        return float(np.mean(scores)) if scores else 0.0

    def _compute_momentum_factor(self, symbol: str) -> float:
        """Compute momentum from multi-period returns."""
        prices = self.data.get_price_history(symbol)
        if prices is None or len(prices) < 30:
            return 0.0

        scores = []
        for period in [30, 90, 180]:
            if len(prices) >= period:
                ret = (prices.iloc[-1] / prices.iloc[-period]) - 1
                # Normalize: +100% -> 1.0, -50% -> -0.5
                scores.append(max(-1, min(1, ret)))

        return float(np.mean(scores)) if scores else 0.0

    def _compute_quality_factor(self, symbol: str) -> float:
        """Compute quality from developer activity and TVL."""
        metrics = self.data.get_on_chain_metrics(symbol)
        if not metrics:
            return 0.0

        scores = []
        # Developer activity
        if metrics.developer_commits_30d > 0:
            scores.append(min(1, metrics.developer_commits_30d / 200))
        # TVL (normalized by log)
        if metrics.tvl > 0:
            scores.append(min(1, np.log10(metrics.tvl + 1) / 11))
        # Transaction count
        if metrics.transaction_count_24h > 0:
            scores.append(min(1, np.log10(metrics.transaction_count_24h + 1) / 7))

        return float(np.mean(scores)) if scores else 0.0

    def _compute_sentiment_factor(self, symbol: str) -> float:
        """Compute sentiment (placeholder - would use social/fear-greed data)."""
        # In production, aggregate social media sentiment, fear/greed index
        return 0.0

    def _compute_network_factor(self, symbol: str) -> float:
        """Compute network health from on-chain data."""
        metrics = self.data.get_on_chain_metrics(symbol)
        if not metrics:
            return 0.0

        scores = []
        # Active addresses
        if metrics.active_addresses_24h > 0:
            scores.append(min(1, np.log10(metrics.active_addresses_24h + 1) / 7))
        # Staking ratio (higher = more committed)
        if metrics.staking_ratio > 0:
            scores.append(min(1, metrics.staking_ratio))
        # Hash rate (for PoW)
        if metrics.hash_rate > 0:
            scores.append(min(1, np.log10(metrics.hash_rate + 1) / 20))

        return float(np.mean(scores)) if scores else 0.0
