"""Time-Decay Weighted Sentiment Aggregation.

Applies exponential and half-life decay to sentiment observations
so that recent signals carry more weight than stale ones.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass
class SentimentObservation:
    """Single sentiment observation with timestamp."""
    source: str = ""  # news, social, insider, analyst, earnings
    score: float = 0.0  # -1 to +1
    age_hours: float = 0.0  # How old the observation is
    credibility: float = 1.0  # Source credibility 0-1
    symbol: str = ""

    @property
    def is_fresh(self) -> bool:
        return self.age_hours <= 24.0

    @property
    def is_stale(self) -> bool:
        return self.age_hours > 168.0  # > 7 days


@dataclass
class DecayedScore:
    """Score after applying time-decay weighting."""
    symbol: str = ""
    source: str = ""
    raw_score: float = 0.0
    decayed_score: float = 0.0
    decay_factor: float = 1.0
    effective_weight: float = 0.0
    age_hours: float = 0.0

    @property
    def weight_loss_pct(self) -> float:
        return (1.0 - self.decay_factor) * 100.0

    @property
    def is_heavily_decayed(self) -> bool:
        return self.decay_factor < 0.3


@dataclass
class DecayProfile:
    """Decay profile for a symbol across sources."""
    symbol: str = ""
    n_observations: int = 0
    weighted_score: float = 0.0
    unweighted_score: float = 0.0
    avg_age_hours: float = 0.0
    freshness_ratio: float = 0.0  # Fraction of fresh observations
    scores_by_source: dict = field(default_factory=dict)
    effective_sources: int = 0

    @property
    def decay_impact(self) -> float:
        """How much decay changed the aggregate score."""
        if self.unweighted_score == 0:
            return 0.0
        return abs(self.weighted_score - self.unweighted_score)

    @property
    def is_reliable(self) -> bool:
        return self.effective_sources >= 2 and self.freshness_ratio >= 0.3


@dataclass
class DecayConfig:
    """Configuration for decay weighting."""
    half_life_hours: float = 48.0  # Score loses half weight after 48 hours
    max_age_hours: float = 720.0  # 30 days; older observations ignored
    min_decay_factor: float = 0.05  # Floor on decay weight
    credibility_boost: float = 0.5  # How much credibility affects weight
    freshness_window_hours: float = 24.0


# ---------------------------------------------------------------------------
# Decay Weighting Engine
# ---------------------------------------------------------------------------
class DecayWeightingEngine:
    """Applies time-decay weighting to sentiment observations.

    Uses exponential half-life decay: weight = 2^(-age / half_life),
    adjusted by source credibility.
    """

    def __init__(self, config: Optional[DecayConfig] = None) -> None:
        self.config = config or DecayConfig()

    def compute_decay_factor(self, age_hours: float) -> float:
        """Compute decay factor for a given age.

        Args:
            age_hours: Age of observation in hours.

        Returns:
            Decay factor between min_decay_factor and 1.0.
        """
        if age_hours <= 0:
            return 1.0
        if age_hours > self.config.max_age_hours:
            return self.config.min_decay_factor

        raw = float(np.power(2.0, -age_hours / self.config.half_life_hours))
        return max(self.config.min_decay_factor, raw)

    def decay_observation(self, obs: SentimentObservation) -> DecayedScore:
        """Apply decay to a single observation.

        Args:
            obs: Sentiment observation with age and credibility.

        Returns:
            DecayedScore with decay-adjusted score and weight.
        """
        decay = self.compute_decay_factor(obs.age_hours)

        # Effective weight combines decay and credibility
        cred_factor = 1.0 + self.config.credibility_boost * (obs.credibility - 0.5)
        effective = decay * max(0.1, cred_factor)

        return DecayedScore(
            symbol=obs.symbol,
            source=obs.source,
            raw_score=obs.score,
            decayed_score=round(obs.score * decay, 6),
            decay_factor=round(decay, 6),
            effective_weight=round(effective, 6),
            age_hours=obs.age_hours,
        )

    def aggregate(
        self,
        observations: list[SentimentObservation],
        symbol: str = "",
    ) -> DecayProfile:
        """Aggregate observations with decay weighting.

        Args:
            observations: List of sentiment observations.
            symbol: Ticker symbol.

        Returns:
            DecayProfile with weighted aggregate score.
        """
        if not observations:
            return DecayProfile(symbol=symbol)

        # Filter out observations beyond max age
        valid = [
            o for o in observations
            if o.age_hours <= self.config.max_age_hours
        ]
        if not valid:
            return DecayProfile(symbol=symbol, n_observations=0)

        # Compute decayed scores
        decayed = [self.decay_observation(o) for o in valid]

        # Weighted average
        total_weight = sum(d.effective_weight for d in decayed)
        if total_weight <= 0:
            weighted = 0.0
        else:
            weighted = sum(
                d.raw_score * d.effective_weight for d in decayed
            ) / total_weight

        # Unweighted average for comparison
        unweighted = float(np.mean([d.raw_score for d in decayed]))

        # Per-source aggregation
        source_scores: dict[str, list[float]] = {}
        source_weights: dict[str, list[float]] = {}
        for d in decayed:
            source_scores.setdefault(d.source, []).append(d.raw_score)
            source_weights.setdefault(d.source, []).append(d.effective_weight)

        scores_by_source = {}
        for src in source_scores:
            sw = source_weights[src]
            ss = source_scores[src]
            tw = sum(sw)
            if tw > 0:
                scores_by_source[src] = round(
                    sum(s * w for s, w in zip(ss, sw)) / tw, 4
                )

        # Freshness
        fresh = sum(
            1 for o in valid
            if o.age_hours <= self.config.freshness_window_hours
        )
        freshness_ratio = fresh / len(valid)

        return DecayProfile(
            symbol=symbol,
            n_observations=len(valid),
            weighted_score=round(float(np.clip(weighted, -1.0, 1.0)), 4),
            unweighted_score=round(float(np.clip(unweighted, -1.0, 1.0)), 4),
            avg_age_hours=round(float(np.mean([o.age_hours for o in valid])), 2),
            freshness_ratio=round(freshness_ratio, 4),
            scores_by_source=scores_by_source,
            effective_sources=len(scores_by_source),
        )

    def compare_decay_profiles(
        self,
        profiles: list[DecayProfile],
    ) -> dict:
        """Compare decay profiles across symbols.

        Args:
            profiles: List of DecayProfile objects.

        Returns:
            Dict with ranking and comparison metrics.
        """
        if not profiles:
            return {"symbols": [], "ranking": []}

        ranked = sorted(
            profiles,
            key=lambda p: p.weighted_score,
            reverse=True,
        )

        return {
            "symbols": [p.symbol for p in ranked],
            "ranking": [
                {
                    "symbol": p.symbol,
                    "weighted_score": p.weighted_score,
                    "freshness": p.freshness_ratio,
                    "sources": p.effective_sources,
                    "reliable": p.is_reliable,
                }
                for p in ranked
            ],
            "avg_freshness": round(
                float(np.mean([p.freshness_ratio for p in profiles])), 4
            ),
            "n_reliable": sum(1 for p in profiles if p.is_reliable),
        }
