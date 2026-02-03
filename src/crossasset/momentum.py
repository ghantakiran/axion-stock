"""Cross-Asset Momentum and Mean-Reversion Signals.

Computes time-series momentum, cross-sectional momentum (rank-based),
Z-score mean-reversion, and trend strength across asset classes.
"""

import logging
from typing import Optional

import numpy as np

from src.crossasset.config import MomentumConfig
from src.crossasset.models import MomentumSignal

logger = logging.getLogger(__name__)


class CrossAssetMomentum:
    """Computes momentum and mean-reversion signals across assets."""

    def __init__(self, config: Optional[MomentumConfig] = None) -> None:
        self.config = config or MomentumConfig()

    def time_series_momentum(
        self, returns: list[float], asset: str = "", asset_class: str = ""
    ) -> MomentumSignal:
        """Compute time-series momentum for a single asset.

        Uses lookback return as the momentum signal.

        Args:
            returns: Return series.
            asset: Asset label.
            asset_class: Asset class label.

        Returns:
            MomentumSignal.
        """
        if len(returns) < self.config.lookback_short:
            return MomentumSignal(asset=asset, asset_class=asset_class)

        arr = np.array(returns)

        # Short-term momentum (cumulative return over lookback)
        short_ret = np.sum(arr[-self.config.lookback_short :])

        # Long-term momentum
        long_len = min(self.config.lookback_long, len(arr))
        long_ret = np.sum(arr[-long_len:])

        # Z-score for mean reversion
        w = min(self.config.zscore_window, len(arr))
        window_returns = arr[-w:]
        cum_ret = np.cumsum(arr)
        if len(cum_ret) > w:
            recent_level = cum_ret[-1]
            window_levels = cum_ret[-w:]
            mean_level = np.mean(window_levels)
            std_level = np.std(window_levels, ddof=1)
            z_score = (recent_level - mean_level) / std_level if std_level > 0 else 0.0
        else:
            z_score = 0.0

        # Trend strength: ratio of return to volatility
        vol = np.std(arr[-self.config.lookback_short :], ddof=1)
        trend_strength = short_ret / vol if vol > 0 else 0.0

        # Classify signal
        is_mean_reverting = bool(abs(z_score) > self.config.mean_reversion_threshold)
        if is_mean_reverting:
            signal = "bearish" if z_score > 0 else "bullish"
        elif trend_strength > self.config.trend_strength_threshold:
            signal = "bullish"
        elif trend_strength < -self.config.trend_strength_threshold:
            signal = "bearish"
        else:
            signal = "neutral"

        return MomentumSignal(
            asset=asset,
            asset_class=asset_class,
            ts_momentum=round(float(short_ret), 6),
            xs_rank=0.0,  # Set during cross-sectional analysis
            z_score=round(float(z_score), 4),
            trend_strength=round(float(trend_strength), 4),
            signal=signal,
            is_mean_reverting=is_mean_reverting,
        )

    def cross_sectional_momentum(
        self, returns_dict: dict[str, list[float]], asset_classes: Optional[dict[str, str]] = None
    ) -> list[MomentumSignal]:
        """Compute cross-sectional (rank-based) momentum across assets.

        Assets are ranked by their lookback return; top-ranked get
        bullish signals, bottom-ranked get bearish signals.

        Args:
            returns_dict: Dict of {asset: return_series}.
            asset_classes: Optional dict of {asset: asset_class}.

        Returns:
            List of MomentumSignal with cross-sectional ranks.
        """
        if not returns_dict:
            return []

        asset_classes = asset_classes or {}

        # Compute TS momentum for each asset
        signals = {}
        for asset, rets in returns_dict.items():
            ac = asset_classes.get(asset, "")
            signals[asset] = self.time_series_momentum(rets, asset, ac)

        # Rank by ts_momentum
        sorted_assets = sorted(
            signals.keys(), key=lambda x: signals[x].ts_momentum, reverse=True
        )
        n = len(sorted_assets)

        results = []
        for rank, asset in enumerate(sorted_assets):
            sig = signals[asset]
            # Normalize rank to [0, 1] where 1 = best
            xs_rank = 1.0 - (rank / (n - 1)) if n > 1 else 0.5
            sig.xs_rank = round(xs_rank, 4)

            # Override signal if cross-sectional rank is extreme
            if xs_rank >= 0.8 and sig.signal == "neutral":
                sig.signal = "bullish"
            elif xs_rank <= 0.2 and sig.signal == "neutral":
                sig.signal = "bearish"

            results.append(sig)

        return results

    def mean_reversion_signals(
        self, returns_dict: dict[str, list[float]], asset_classes: Optional[dict[str, str]] = None
    ) -> list[MomentumSignal]:
        """Identify assets exhibiting mean-reversion behavior.

        Returns only assets where |z_score| > threshold.

        Args:
            returns_dict: Dict of {asset: return_series}.
            asset_classes: Optional asset class mapping.

        Returns:
            List of mean-reverting MomentumSignals.
        """
        all_signals = self.cross_sectional_momentum(returns_dict, asset_classes)
        return [s for s in all_signals if s.is_mean_reverting]

    def trend_signals(
        self, returns_dict: dict[str, list[float]], asset_classes: Optional[dict[str, str]] = None
    ) -> list[MomentumSignal]:
        """Identify assets with strong trends.

        Returns only assets where |trend_strength| > threshold.

        Args:
            returns_dict: Dict of {asset: return_series}.
            asset_classes: Optional asset class mapping.

        Returns:
            List of trending MomentumSignals.
        """
        all_signals = self.cross_sectional_momentum(returns_dict, asset_classes)
        return [s for s in all_signals if s.is_trending]
