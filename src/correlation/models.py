"""Correlation Analysis Data Models.

Dataclasses for correlation matrices, rolling correlations,
pair analysis, regime detection, and diversification scoring.
"""

from dataclasses import dataclass, field
from datetime import datetime, date, timezone
from typing import Optional
import uuid

import numpy as np

from src.correlation.config import (
    CorrelationMethod,
    RegimeType,
    DiversificationLevel,
)


def _new_id() -> str:
    return uuid.uuid4().hex[:16]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class CorrelationMatrix:
    """N×N correlation matrix with metadata."""
    matrix_id: str = field(default_factory=_new_id)
    symbols: list[str] = field(default_factory=list)
    values: Optional[np.ndarray] = None
    method: CorrelationMethod = CorrelationMethod.PEARSON
    n_periods: int = 0
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    computed_at: datetime = field(default_factory=_utc_now)

    @property
    def n_assets(self) -> int:
        return len(self.symbols)

    @property
    def avg_correlation(self) -> float:
        """Average off-diagonal correlation."""
        if self.values is None or self.n_assets < 2:
            return 0.0
        mask = ~np.eye(self.n_assets, dtype=bool)
        return float(np.mean(self.values[mask]))

    @property
    def max_correlation(self) -> float:
        """Maximum off-diagonal correlation."""
        if self.values is None or self.n_assets < 2:
            return 0.0
        mask = ~np.eye(self.n_assets, dtype=bool)
        return float(np.max(self.values[mask]))

    @property
    def min_correlation(self) -> float:
        """Minimum off-diagonal correlation."""
        if self.values is None or self.n_assets < 2:
            return 0.0
        mask = ~np.eye(self.n_assets, dtype=bool)
        return float(np.min(self.values[mask]))

    def get_pair(self, sym_a: str, sym_b: str) -> float:
        """Get correlation between two symbols."""
        if self.values is None:
            return 0.0
        try:
            i = self.symbols.index(sym_a)
            j = self.symbols.index(sym_b)
            return float(self.values[i, j])
        except ValueError:
            return 0.0

    def to_dict(self) -> dict:
        return {
            "symbols": self.symbols,
            "method": self.method.value,
            "n_assets": self.n_assets,
            "n_periods": self.n_periods,
            "avg_correlation": round(self.avg_correlation, 4),
            "max_correlation": round(self.max_correlation, 4),
            "min_correlation": round(self.min_correlation, 4),
        }


@dataclass
class CorrelationPair:
    """Correlation between two specific assets."""
    symbol_a: str
    symbol_b: str
    correlation: float
    method: CorrelationMethod = CorrelationMethod.PEARSON
    n_periods: int = 0
    stability: float = 0.0  # Low std dev over time = stable

    @property
    def abs_correlation(self) -> float:
        return abs(self.correlation)

    @property
    def is_highly_correlated(self) -> bool:
        return self.abs_correlation >= 0.70

    @property
    def is_negatively_correlated(self) -> bool:
        return self.correlation < -0.30


@dataclass
class RollingCorrelation:
    """Rolling correlation time series for a pair."""
    symbol_a: str
    symbol_b: str
    dates: list[date] = field(default_factory=list)
    values: list[float] = field(default_factory=list)
    window: int = 63

    @property
    def current(self) -> float:
        return self.values[-1] if self.values else 0.0

    @property
    def mean(self) -> float:
        return float(np.mean(self.values)) if self.values else 0.0

    @property
    def std(self) -> float:
        return float(np.std(self.values)) if self.values else 0.0

    @property
    def percentile(self) -> float:
        """Current value's percentile within history."""
        if not self.values or len(self.values) < 2:
            return 50.0
        current = self.values[-1]
        below = sum(1 for v in self.values if v <= current)
        return (below / len(self.values)) * 100.0

    @property
    def n_observations(self) -> int:
        return len(self.values)


@dataclass
class CorrelationRegime:
    """Correlation regime assessment."""
    regime_id: str = field(default_factory=_new_id)
    date: date = field(default_factory=lambda: date.today())
    regime: RegimeType = RegimeType.NORMAL
    avg_correlation: float = 0.0
    dispersion: float = 0.0  # Std dev of pairwise correlations
    prev_regime: Optional[RegimeType] = None
    regime_changed: bool = False
    days_in_regime: int = 0
    computed_at: datetime = field(default_factory=_utc_now)


@dataclass
class DiversificationScore:
    """Portfolio diversification assessment."""
    score_id: str = field(default_factory=_new_id)
    date: date = field(default_factory=lambda: date.today())
    diversification_ratio: float = 1.0
    effective_n_bets: float = 1.0
    avg_pair_correlation: float = 0.0
    max_pair_correlation: float = 0.0
    max_pair: tuple[str, str] = ("", "")
    level: DiversificationLevel = DiversificationLevel.FAIR
    n_assets: int = 0
    highly_correlated_pairs: list[CorrelationPair] = field(default_factory=list)
    computed_at: datetime = field(default_factory=_utc_now)

    def to_dict(self) -> dict:
        return {
            "date": str(self.date),
            "diversification_ratio": round(self.diversification_ratio, 3),
            "effective_n_bets": round(self.effective_n_bets, 1),
            "avg_pair_correlation": round(self.avg_pair_correlation, 4),
            "max_pair_correlation": round(self.max_pair_correlation, 4),
            "max_pair": self.max_pair,
            "level": self.level.value,
            "n_assets": self.n_assets,
            "n_highly_correlated": len(self.highly_correlated_pairs),
        }
