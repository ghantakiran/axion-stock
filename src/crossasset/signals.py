"""Composite Cross-Asset Signal Generator.

Combines intermarket, lead-lag, momentum, and mean-reversion
components into a single actionable signal per asset.
"""

import logging
from typing import Optional

import numpy as np

from src.crossasset.config import SignalConfig, SignalStrength, SignalDirection
from src.crossasset.models import (
    CrossAssetSignal,
    MomentumSignal,
    LeadLagResult,
    AssetPairCorrelation,
)

logger = logging.getLogger(__name__)


class CrossAssetSignalGenerator:
    """Generates composite cross-asset signals."""

    def __init__(self, config: Optional[SignalConfig] = None) -> None:
        self.config = config or SignalConfig()

    def generate(
        self,
        asset: str,
        momentum: Optional[MomentumSignal] = None,
        lead_lag: Optional[LeadLagResult] = None,
        lead_lag_signal: float = 0.0,
        correlations: Optional[list[AssetPairCorrelation]] = None,
    ) -> CrossAssetSignal:
        """Generate composite signal for a single asset.

        Args:
            asset: Asset label.
            momentum: MomentumSignal for this asset.
            lead_lag: LeadLagResult where this asset is the lagger.
            lead_lag_signal: Extracted signal from the leading asset.
            correlations: Relevant correlation results.

        Returns:
            CrossAssetSignal.
        """
        components: dict[str, float] = {}
        weights_used = 0.0

        # Momentum component
        mom_score = 0.0
        if momentum:
            mom_score = momentum.ts_momentum * 100  # Scale to make comparable
            components["ts_momentum"] = momentum.ts_momentum
            components["xs_rank"] = momentum.xs_rank
            weights_used += self.config.momentum_weight

        # Mean-reversion component
        mr_score = 0.0
        if momentum and momentum.is_mean_reverting:
            # Mean reversion: negative z-score → bullish (oversold)
            mr_score = -momentum.z_score * 0.01
            components["z_score"] = momentum.z_score
            weights_used += self.config.mean_reversion_weight

        # Lead-lag component
        ll_score = 0.0
        if lead_lag and lead_lag.is_significant and lead_lag_signal != 0:
            ll_score = lead_lag_signal * lead_lag.correlation_at_lag * 100
            components["lead_lag_signal"] = lead_lag_signal
            components["lead_lag_corr"] = lead_lag.correlation_at_lag
            weights_used += self.config.leadlag_weight

        # Intermarket component
        im_score = 0.0
        if correlations:
            # Average divergence signal
            divergence_signals = []
            for corr in correlations:
                if corr.is_diverging:
                    divergence_signals.append(-corr.z_score * 0.005)
            if divergence_signals:
                im_score = float(np.mean(divergence_signals))
                components["intermarket_divergences"] = len(divergence_signals)
                weights_used += self.config.intermarket_weight

        # Composite score (weighted average of non-zero components)
        if weights_used > 0:
            score = (
                self.config.momentum_weight * mom_score
                + self.config.mean_reversion_weight * mr_score
                + self.config.leadlag_weight * ll_score
                + self.config.intermarket_weight * im_score
            ) / weights_used
        else:
            score = 0.0

        # Confidence: proportion of available components
        max_possible_weight = (
            self.config.momentum_weight
            + self.config.mean_reversion_weight
            + self.config.leadlag_weight
            + self.config.intermarket_weight
        )
        confidence = weights_used / max_possible_weight if max_possible_weight > 0 else 0.0

        # Direction and strength
        direction = self._classify_direction(score)
        strength = self._classify_strength(abs(score), confidence)

        return CrossAssetSignal(
            asset=asset,
            direction=direction,
            strength=strength,
            score=round(score, 6),
            confidence=round(confidence, 4),
            intermarket_component=round(im_score, 6),
            leadlag_component=round(ll_score, 6),
            momentum_component=round(mom_score, 6),
            mean_reversion_component=round(mr_score, 6),
            components=components,
        )

    def generate_all(
        self,
        momentum_signals: list[MomentumSignal],
        lead_lag_results: Optional[list[LeadLagResult]] = None,
        lead_lag_signals: Optional[dict[str, float]] = None,
        correlation_map: Optional[dict[str, list[AssetPairCorrelation]]] = None,
    ) -> list[CrossAssetSignal]:
        """Generate signals for all assets.

        Args:
            momentum_signals: List of per-asset MomentumSignals.
            lead_lag_results: Optional list of LeadLagResults.
            lead_lag_signals: Optional dict of {lagger_asset: signal_value}.
            correlation_map: Optional dict of {asset: [correlations]}.

        Returns:
            List of CrossAssetSignal, sorted by absolute score.
        """
        lead_lag_signals = lead_lag_signals or {}
        lead_lag_results = lead_lag_results or []
        correlation_map = correlation_map or {}

        # Index lead-lag by lagger
        ll_by_lagger: dict[str, LeadLagResult] = {}
        for ll in lead_lag_results:
            if ll.is_significant:
                ll_by_lagger[ll.lagger] = ll

        results = []
        for mom in momentum_signals:
            asset = mom.asset
            ll = ll_by_lagger.get(asset)
            ll_sig = lead_lag_signals.get(asset, 0.0)
            corrs = correlation_map.get(asset, [])

            signal = self.generate(
                asset=asset,
                momentum=mom,
                lead_lag=ll,
                lead_lag_signal=ll_sig,
                correlations=corrs if corrs else None,
            )
            results.append(signal)

        results.sort(key=lambda x: abs(x.score), reverse=True)
        return results

    def _classify_direction(self, score: float) -> str:
        """Classify signal direction from score."""
        if score > 0.001:
            return SignalDirection.BULLISH.value
        elif score < -0.001:
            return SignalDirection.BEARISH.value
        return SignalDirection.NEUTRAL.value

    def _classify_strength(self, abs_score: float, confidence: float) -> str:
        """Classify signal strength."""
        if confidence < self.config.min_confidence:
            return SignalStrength.NONE.value
        if abs_score >= self.config.strong_threshold:
            return SignalStrength.STRONG.value
        if abs_score >= self.config.moderate_threshold:
            return SignalStrength.MODERATE.value
        if abs_score > 0.001:
            return SignalStrength.WEAK.value
        return SignalStrength.NONE.value
