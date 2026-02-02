"""Crowding Analysis Data Models."""

from dataclasses import dataclass, field
from datetime import datetime

from src.crowding.config import CrowdingLevel, SqueezeRisk, ConsensusRating


@dataclass
class CrowdingScore:
    """Position crowding assessment."""
    symbol: str
    score: float  # 0 to 1
    level: CrowdingLevel = CrowdingLevel.LOW
    n_holders: int = 0
    concentration: float = 0.0  # HHI
    momentum: float = 0.0  # crowding trend
    percentile: float = 0.0  # historical ranking
    is_decrowding: bool = False
    computed_at: datetime = field(default_factory=datetime.now)

    @property
    def is_crowded(self) -> bool:
        return self.level in (CrowdingLevel.HIGH, CrowdingLevel.EXTREME)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "score": self.score,
            "level": self.level.value,
            "n_holders": self.n_holders,
            "concentration": self.concentration,
            "momentum": self.momentum,
            "percentile": self.percentile,
            "is_crowded": self.is_crowded,
            "is_decrowding": self.is_decrowding,
        }


@dataclass
class FundOverlap:
    """Pairwise fund overlap result."""
    fund_a: str
    fund_b: str
    overlap_score: float  # 0 to 1
    shared_positions: int
    total_positions_a: int
    total_positions_b: int
    top_shared: list[str] = field(default_factory=list)
    computed_at: datetime = field(default_factory=datetime.now)

    @property
    def overlap_pct(self) -> float:
        """Overlap as percentage."""
        return self.overlap_score * 100

    def to_dict(self) -> dict:
        return {
            "fund_a": self.fund_a,
            "fund_b": self.fund_b,
            "overlap_score": self.overlap_score,
            "overlap_pct": self.overlap_pct,
            "shared_positions": self.shared_positions,
            "total_positions_a": self.total_positions_a,
            "total_positions_b": self.total_positions_b,
            "top_shared": self.top_shared,
        }


@dataclass
class CrowdedName:
    """Most-crowded stock identified from overlap analysis."""
    symbol: str
    n_funds: int  # number of funds holding
    total_ownership_pct: float
    avg_position_size: float  # avg % of fund portfolio
    breadth: float = 0.0  # how widely held (0 to 1)
    depth: float = 0.0  # how large positions are (0 to 1)
    computed_at: datetime = field(default_factory=datetime.now)

    @property
    def crowding_intensity(self) -> float:
        """Combined breadth and depth score."""
        return 0.5 * self.breadth + 0.5 * self.depth

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "n_funds": self.n_funds,
            "total_ownership_pct": self.total_ownership_pct,
            "avg_position_size": self.avg_position_size,
            "breadth": self.breadth,
            "depth": self.depth,
            "crowding_intensity": self.crowding_intensity,
        }


@dataclass
class ShortInterestData:
    """Short interest snapshot."""
    symbol: str
    shares_short: float
    float_shares: float
    avg_daily_volume: float
    cost_to_borrow: float = 0.0  # annualized %
    date: str = ""
    computed_at: datetime = field(default_factory=datetime.now)

    @property
    def si_ratio(self) -> float:
        """Short interest as fraction of float."""
        if self.float_shares == 0:
            return 0.0
        return self.shares_short / self.float_shares

    @property
    def days_to_cover(self) -> float:
        """Days to cover all short positions."""
        if self.avg_daily_volume == 0:
            return 0.0
        return self.shares_short / self.avg_daily_volume

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "shares_short": self.shares_short,
            "float_shares": self.float_shares,
            "si_ratio": round(self.si_ratio, 4),
            "days_to_cover": round(self.days_to_cover, 2),
            "cost_to_borrow": self.cost_to_borrow,
            "date": self.date,
        }


@dataclass
class ShortSqueezeScore:
    """Short squeeze risk assessment."""
    symbol: str
    squeeze_score: float  # 0 to 1
    risk: SqueezeRisk = SqueezeRisk.LOW
    si_ratio: float = 0.0
    days_to_cover: float = 0.0
    si_momentum: float = 0.0  # positive = increasing shorts
    cost_to_borrow: float = 0.0
    computed_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "squeeze_score": self.squeeze_score,
            "risk": self.risk.value,
            "si_ratio": self.si_ratio,
            "days_to_cover": self.days_to_cover,
            "si_momentum": self.si_momentum,
            "cost_to_borrow": self.cost_to_borrow,
        }


@dataclass
class ConsensusSnapshot:
    """Analyst consensus snapshot."""
    symbol: str
    mean_rating: float  # 1=strong sell to 5=strong buy
    n_analysts: int
    buy_count: int = 0
    hold_count: int = 0
    sell_count: int = 0
    mean_target: float = 0.0
    target_upside: float = 0.0  # % upside to mean target
    revision_momentum: float = 0.0  # positive = upgrades
    divergence: float = 0.0  # std dev of ratings
    is_contrarian: bool = False
    computed_at: datetime = field(default_factory=datetime.now)

    @property
    def rating(self) -> ConsensusRating:
        if self.mean_rating >= 4.5:
            return ConsensusRating.STRONG_BUY
        elif self.mean_rating >= 3.5:
            return ConsensusRating.BUY
        elif self.mean_rating >= 2.5:
            return ConsensusRating.HOLD
        elif self.mean_rating >= 1.5:
            return ConsensusRating.SELL
        return ConsensusRating.STRONG_SELL

    @property
    def buy_pct(self) -> float:
        if self.n_analysts == 0:
            return 0.0
        return self.buy_count / self.n_analysts * 100

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "mean_rating": self.mean_rating,
            "rating": self.rating.value,
            "n_analysts": self.n_analysts,
            "buy_count": self.buy_count,
            "hold_count": self.hold_count,
            "sell_count": self.sell_count,
            "buy_pct": round(self.buy_pct, 1),
            "mean_target": self.mean_target,
            "target_upside": self.target_upside,
            "revision_momentum": self.revision_momentum,
            "divergence": self.divergence,
            "is_contrarian": self.is_contrarian,
        }
