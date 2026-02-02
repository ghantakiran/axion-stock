"""Macro Regime Data Models."""

from dataclasses import dataclass, field
from datetime import datetime

from src.macro.config import RegimeType, CurveShape, IndicatorType, MacroFactor


@dataclass
class EconomicIndicator:
    """Single economic indicator reading."""
    name: str
    value: float
    previous: float
    consensus: float = 0.0
    indicator_type: IndicatorType = IndicatorType.COINCIDENT
    date: str = ""
    computed_at: datetime = field(default_factory=datetime.now)

    @property
    def surprise(self) -> float:
        """Actual minus consensus."""
        return self.value - self.consensus

    @property
    def change(self) -> float:
        return self.value - self.previous

    @property
    def change_pct(self) -> float:
        if self.previous == 0:
            return 0.0
        return (self.value - self.previous) / abs(self.previous) * 100

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "value": self.value,
            "previous": self.previous,
            "consensus": self.consensus,
            "surprise": self.surprise,
            "change": self.change,
            "change_pct": self.change_pct,
            "indicator_type": self.indicator_type.value,
            "date": self.date,
        }


@dataclass
class IndicatorSummary:
    """Aggregated indicator summary."""
    composite_index: float  # weighted composite score
    n_improving: int
    n_deteriorating: int
    n_stable: int
    leading_score: float
    coincident_score: float
    lagging_score: float
    computed_at: datetime = field(default_factory=datetime.now)

    @property
    def breadth(self) -> float:
        """Fraction of indicators improving."""
        total = self.n_improving + self.n_deteriorating + self.n_stable
        if total == 0:
            return 0.0
        return self.n_improving / total

    def to_dict(self) -> dict:
        return {
            "composite_index": self.composite_index,
            "n_improving": self.n_improving,
            "n_deteriorating": self.n_deteriorating,
            "n_stable": self.n_stable,
            "leading_score": self.leading_score,
            "coincident_score": self.coincident_score,
            "lagging_score": self.lagging_score,
            "breadth": self.breadth,
        }


@dataclass
class YieldCurveSnapshot:
    """Yield curve at a point in time."""
    date: str
    rates: dict  # tenor -> yield (e.g., {"2Y": 4.25, "10Y": 4.50})
    shape: CurveShape = CurveShape.NORMAL
    term_spread: float = 0.0  # 2s10s spread in pct
    slope: float = 0.0  # Nelson-Siegel slope factor
    curvature: float = 0.0  # Nelson-Siegel curvature factor
    level: float = 0.0  # Nelson-Siegel level factor
    is_inverted: bool = False
    inversion_depth: float = 0.0  # max inversion in pct
    computed_at: datetime = field(default_factory=datetime.now)

    @property
    def short_rate(self) -> float:
        """Shortest available rate."""
        if not self.rates:
            return 0.0
        return next(iter(self.rates.values()))

    @property
    def long_rate(self) -> float:
        """Longest available rate."""
        if not self.rates:
            return 0.0
        return list(self.rates.values())[-1]

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "rates": self.rates,
            "shape": self.shape.value,
            "term_spread": self.term_spread,
            "slope": self.slope,
            "curvature": self.curvature,
            "level": self.level,
            "is_inverted": self.is_inverted,
            "inversion_depth": self.inversion_depth,
        }


@dataclass
class RegimeState:
    """Detected macro regime."""
    regime: RegimeType
    probability: float  # confidence in current regime
    duration: int  # months in current regime
    transition_probs: dict = field(default_factory=dict)  # regime -> prob
    indicator_consensus: float = 0.0  # % of indicators agreeing
    computed_at: datetime = field(default_factory=datetime.now)

    @property
    def is_confident(self) -> bool:
        return self.probability >= 0.6

    def to_dict(self) -> dict:
        return {
            "regime": self.regime.value,
            "probability": self.probability,
            "duration": self.duration,
            "transition_probs": {k.value: v for k, v in self.transition_probs.items()},
            "indicator_consensus": self.indicator_consensus,
            "is_confident": self.is_confident,
        }


@dataclass
class MacroFactorResult:
    """Macro factor model output."""
    factor_returns: dict  # factor_name -> return
    factor_exposures: dict  # factor_name -> exposure score
    factor_momentum: dict  # factor_name -> momentum score
    regime_conditional: dict = field(default_factory=dict)  # regime -> factor_returns
    dominant_factor: str = ""
    computed_at: datetime = field(default_factory=datetime.now)

    @property
    def n_positive(self) -> int:
        return sum(1 for v in self.factor_returns.values() if v > 0)

    @property
    def n_negative(self) -> int:
        return sum(1 for v in self.factor_returns.values() if v < 0)

    def to_dict(self) -> dict:
        return {
            "factor_returns": self.factor_returns,
            "factor_exposures": self.factor_exposures,
            "factor_momentum": self.factor_momentum,
            "regime_conditional": self.regime_conditional,
            "dominant_factor": self.dominant_factor,
            "n_positive": self.n_positive,
            "n_negative": self.n_negative,
        }
