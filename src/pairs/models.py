"""Pairs Trading Data Models."""

from dataclasses import dataclass, field
from typing import Optional

from src.pairs.config import PairSignalType, PairStatus


@dataclass
class CointegrationResult:
    """Result of cointegration test between two assets."""
    asset_a: str = ""
    asset_b: str = ""
    test_statistic: float = 0.0
    pvalue: float = 1.0
    hedge_ratio: float = 0.0
    intercept: float = 0.0
    correlation: float = 0.0
    status: PairStatus = PairStatus.NOT_COINTEGRATED

    @property
    def is_cointegrated(self) -> bool:
        return self.status == PairStatus.COINTEGRATED

    def to_dict(self) -> dict:
        return {
            "asset_a": self.asset_a,
            "asset_b": self.asset_b,
            "test_statistic": self.test_statistic,
            "pvalue": self.pvalue,
            "hedge_ratio": self.hedge_ratio,
            "intercept": self.intercept,
            "correlation": self.correlation,
            "status": self.status.value,
            "is_cointegrated": self.is_cointegrated,
        }


@dataclass
class SpreadAnalysis:
    """Spread analysis for a pair."""
    asset_a: str = ""
    asset_b: str = ""
    current_spread: float = 0.0
    spread_mean: float = 0.0
    spread_std: float = 0.0
    zscore: float = 0.0
    half_life: float = 0.0
    hurst_exponent: float = 0.5
    signal: PairSignalType = PairSignalType.NO_SIGNAL

    @property
    def is_mean_reverting(self) -> bool:
        return self.hurst_exponent < 0.5

    @property
    def spread_deviation(self) -> float:
        return abs(self.current_spread - self.spread_mean)

    def to_dict(self) -> dict:
        return {
            "asset_a": self.asset_a,
            "asset_b": self.asset_b,
            "current_spread": self.current_spread,
            "spread_mean": self.spread_mean,
            "spread_std": self.spread_std,
            "zscore": self.zscore,
            "half_life": self.half_life,
            "hurst_exponent": self.hurst_exponent,
            "signal": self.signal.value,
            "is_mean_reverting": self.is_mean_reverting,
        }


@dataclass
class PairScore:
    """Composite pair quality score."""
    asset_a: str = ""
    asset_b: str = ""
    total_score: float = 0.0
    cointegration_score: float = 0.0
    half_life_score: float = 0.0
    correlation_score: float = 0.0
    hurst_score: float = 0.0
    rank: int = 0

    def to_dict(self) -> dict:
        return {
            "asset_a": self.asset_a,
            "asset_b": self.asset_b,
            "total_score": self.total_score,
            "cointegration_score": self.cointegration_score,
            "half_life_score": self.half_life_score,
            "correlation_score": self.correlation_score,
            "hurst_score": self.hurst_score,
            "rank": self.rank,
        }


@dataclass
class PairSignal:
    """Trading signal for a pair."""
    asset_a: str = ""
    asset_b: str = ""
    signal: PairSignalType = PairSignalType.NO_SIGNAL
    zscore: float = 0.0
    hedge_ratio: float = 0.0
    spread: float = 0.0
    confidence: float = 0.0

    @property
    def is_entry(self) -> bool:
        return self.signal in (PairSignalType.LONG_SPREAD, PairSignalType.SHORT_SPREAD)

    @property
    def is_exit(self) -> bool:
        return self.signal == PairSignalType.EXIT

    def to_dict(self) -> dict:
        return {
            "asset_a": self.asset_a,
            "asset_b": self.asset_b,
            "signal": self.signal.value,
            "zscore": self.zscore,
            "hedge_ratio": self.hedge_ratio,
            "spread": self.spread,
            "confidence": self.confidence,
            "is_entry": self.is_entry,
            "is_exit": self.is_exit,
        }


@dataclass
class PairTrade:
    """Active or historical pair trade."""
    asset_a: str = ""
    asset_b: str = ""
    direction: str = ""  # "long_spread" or "short_spread"
    entry_zscore: float = 0.0
    entry_spread: float = 0.0
    current_zscore: float = 0.0
    current_spread: float = 0.0
    hedge_ratio: float = 0.0
    pnl: float = 0.0
    is_open: bool = True

    def to_dict(self) -> dict:
        return {
            "asset_a": self.asset_a,
            "asset_b": self.asset_b,
            "direction": self.direction,
            "entry_zscore": self.entry_zscore,
            "entry_spread": self.entry_spread,
            "current_zscore": self.current_zscore,
            "current_spread": self.current_spread,
            "hedge_ratio": self.hedge_ratio,
            "pnl": self.pnl,
            "is_open": self.is_open,
        }
