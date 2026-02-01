"""Liquidity Analysis Data Models."""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from src.liquidity.config import LiquidityLevel, ImpactModel


@dataclass
class SpreadAnalysis:
    """Bid-ask spread statistics."""
    symbol: str = ""
    avg_spread: float = 0.0
    median_spread: float = 0.0
    spread_volatility: float = 0.0
    relative_spread: float = 0.0
    effective_spread: float = 0.0
    n_observations: int = 0
    date: Optional[date] = None

    @property
    def spread_bps(self) -> float:
        """Relative spread in basis points."""
        return round(self.relative_spread * 10000, 2)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "avg_spread": round(self.avg_spread, 6),
            "median_spread": round(self.median_spread, 6),
            "relative_spread": round(self.relative_spread, 6),
            "spread_bps": self.spread_bps,
            "effective_spread": round(self.effective_spread, 6),
            "n_observations": self.n_observations,
        }


@dataclass
class VolumeAnalysis:
    """Volume statistics."""
    symbol: str = ""
    avg_volume: float = 0.0
    median_volume: float = 0.0
    volume_ratio: float = 1.0
    avg_dollar_volume: float = 0.0
    vwap: float = 0.0
    n_observations: int = 0
    date: Optional[date] = None

    @property
    def is_low_volume(self) -> bool:
        """Current volume below 50% of average."""
        return self.volume_ratio < 0.5

    @property
    def is_high_volume(self) -> bool:
        """Current volume above 200% of average."""
        return self.volume_ratio > 2.0

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "avg_volume": round(self.avg_volume, 0),
            "median_volume": round(self.median_volume, 0),
            "volume_ratio": round(self.volume_ratio, 3),
            "avg_dollar_volume": round(self.avg_dollar_volume, 0),
            "vwap": round(self.vwap, 4),
            "n_observations": self.n_observations,
        }


@dataclass
class MarketImpact:
    """Market impact estimation for a trade."""
    symbol: str = ""
    trade_size: int = 0
    avg_volume: float = 0.0
    participation_rate: float = 0.0
    spread_cost: float = 0.0
    impact_cost: float = 0.0
    total_cost: float = 0.0
    total_cost_bps: float = 0.0
    model: ImpactModel = ImpactModel.SQUARE_ROOT
    max_safe_size: int = 0
    execution_days: int = 1

    @property
    def is_within_safe_limit(self) -> bool:
        """Trade size within safe participation limit."""
        return self.trade_size <= self.max_safe_size

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "trade_size": self.trade_size,
            "participation_rate": round(self.participation_rate, 4),
            "spread_cost": round(self.spread_cost, 6),
            "impact_cost": round(self.impact_cost, 6),
            "total_cost": round(self.total_cost, 6),
            "total_cost_bps": round(self.total_cost_bps, 2),
            "max_safe_size": self.max_safe_size,
            "execution_days": self.execution_days,
            "is_safe": self.is_within_safe_limit,
        }


@dataclass
class LiquidityScore:
    """Composite liquidity assessment."""
    symbol: str = ""
    score: float = 50.0
    level: LiquidityLevel = LiquidityLevel.MEDIUM
    spread_score: float = 50.0
    volume_score: float = 50.0
    impact_score: float = 50.0
    max_safe_shares: int = 0
    max_safe_dollars: float = 0.0
    date: Optional[date] = None

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "score": round(self.score, 1),
            "level": self.level.value,
            "spread_score": round(self.spread_score, 1),
            "volume_score": round(self.volume_score, 1),
            "impact_score": round(self.impact_score, 1),
            "max_safe_shares": self.max_safe_shares,
            "max_safe_dollars": round(self.max_safe_dollars, 0),
        }


@dataclass
class LiquiditySnapshot:
    """Point-in-time liquidity assessment combining all metrics."""
    symbol: str = ""
    spread: Optional[SpreadAnalysis] = None
    volume: Optional[VolumeAnalysis] = None
    impact: Optional[MarketImpact] = None
    score: Optional[LiquidityScore] = None
    date: Optional[date] = None

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "date": self.date.isoformat() if self.date else None,
            "spread": self.spread.to_dict() if self.spread else None,
            "volume": self.volume.to_dict() if self.volume else None,
            "impact": self.impact.to_dict() if self.impact else None,
            "score": self.score.to_dict() if self.score else None,
        }
