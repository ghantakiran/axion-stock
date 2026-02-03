"""Cross-Asset Signal Data Models."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AssetPairCorrelation:
    """Correlation between two assets."""
    asset_a: str = ""
    asset_b: str = ""
    correlation: float = 0.0
    long_term_correlation: float = 0.0
    z_score: float = 0.0
    regime: str = "normal"
    beta: float = 0.0

    @property
    def is_diverging(self) -> bool:
        return abs(self.z_score) > 1.5

    @property
    def correlation_pct(self) -> float:
        return round(self.correlation * 100, 1)


@dataclass
class RelativeStrength:
    """Relative strength between asset classes."""
    asset: str = ""
    benchmark: str = ""
    ratio: float = 1.0
    ratio_change_pct: float = 0.0
    trend: str = "neutral"
    rank: int = 0

    @property
    def is_outperforming(self) -> bool:
        return self.ratio_change_pct > 0


@dataclass
class LeadLagResult:
    """Lead-lag relationship between two assets."""
    leader: str = ""
    lagger: str = ""
    optimal_lag: int = 0
    correlation_at_lag: float = 0.0
    is_significant: bool = False
    stability: float = 0.0

    @property
    def lead_days(self) -> int:
        return abs(self.optimal_lag)

    @property
    def is_stable(self) -> bool:
        return self.stability >= 0.5


@dataclass
class MomentumSignal:
    """Per-asset momentum or mean-reversion signal."""
    asset: str = ""
    asset_class: str = ""
    ts_momentum: float = 0.0
    xs_rank: float = 0.0
    z_score: float = 0.0
    trend_strength: float = 0.0
    signal: str = "neutral"
    is_mean_reverting: bool = False

    @property
    def is_trending(self) -> bool:
        return abs(self.trend_strength) >= 0.5


@dataclass
class CrossAssetSignal:
    """Composite cross-asset signal."""
    asset: str = ""
    direction: str = "neutral"
    strength: str = "none"
    score: float = 0.0
    confidence: float = 0.0
    intermarket_component: float = 0.0
    leadlag_component: float = 0.0
    momentum_component: float = 0.0
    mean_reversion_component: float = 0.0
    components: dict[str, float] = field(default_factory=dict)

    @property
    def is_actionable(self) -> bool:
        return self.strength in ("strong", "moderate") and self.confidence >= 0.3

    @property
    def score_bps(self) -> float:
        return round(self.score * 10000, 1)
