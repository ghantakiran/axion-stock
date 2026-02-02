"""Fund Flow Analysis Configuration."""

from dataclasses import dataclass, field
from enum import Enum


class FlowDirection(Enum):
    """Fund flow direction."""
    INFLOW = "inflow"
    OUTFLOW = "outflow"
    NEUTRAL = "neutral"


class FlowStrength(Enum):
    """Flow signal strength."""
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    NEUTRAL = "neutral"


class RotationPhase(Enum):
    """Sector rotation phase."""
    EARLY_CYCLE = "early_cycle"
    MID_CYCLE = "mid_cycle"
    LATE_CYCLE = "late_cycle"
    RECESSION = "recession"


class SmartMoneySignal(Enum):
    """Smart money signal type."""
    ACCUMULATION = "accumulation"
    DISTRIBUTION = "distribution"
    NEUTRAL = "neutral"


@dataclass
class FlowTrackerConfig:
    """Flow tracker configuration."""
    lookback_days: int = 20
    momentum_window: int = 5  # days for flow momentum
    significant_flow_pct: float = 0.02  # 2% of AUM
    smoothing_window: int = 5  # EMA smoothing
    min_aum: float = 1e6  # minimum AUM to track


@dataclass
class InstitutionalConfig:
    """Institutional analysis configuration."""
    min_ownership_pct: float = 0.5  # 0.5% minimum position
    concentration_threshold: float = 0.25  # top holders owning >25%
    change_threshold_pct: float = 5.0  # 5% position change is significant
    top_holders_count: int = 10


@dataclass
class RotationConfig:
    """Sector rotation configuration."""
    sectors: list[str] = field(default_factory=lambda: [
        "Technology", "Healthcare", "Financials", "Energy",
        "Consumer Discretionary", "Consumer Staples", "Industrials",
        "Materials", "Utilities", "Real Estate", "Communications",
    ])
    momentum_window: int = 20  # days
    ranking_window: int = 10  # days for relative ranking
    divergence_threshold: float = 2.0  # std devs for divergence


@dataclass
class SmartMoneyConfig:
    """Smart money detection configuration."""
    institutional_weight: float = 0.7  # weight for institutional flows
    retail_weight: float = 0.3  # weight for retail flows
    conviction_threshold: float = 0.6  # minimum conviction score
    divergence_lookback: int = 10  # days for flow-price divergence
    accumulation_threshold: float = 0.3  # net flow ratio for accumulation
    distribution_threshold: float = -0.3  # net flow ratio for distribution


@dataclass
class FundFlowConfig:
    """Top-level fund flow configuration."""
    tracker: FlowTrackerConfig = field(default_factory=FlowTrackerConfig)
    institutional: InstitutionalConfig = field(default_factory=InstitutionalConfig)
    rotation: RotationConfig = field(default_factory=RotationConfig)
    smartmoney: SmartMoneyConfig = field(default_factory=SmartMoneyConfig)


DEFAULT_TRACKER_CONFIG = FlowTrackerConfig()
DEFAULT_INSTITUTIONAL_CONFIG = InstitutionalConfig()
DEFAULT_ROTATION_CONFIG = RotationConfig()
DEFAULT_SMARTMONEY_CONFIG = SmartMoneyConfig()
DEFAULT_CONFIG = FundFlowConfig()
