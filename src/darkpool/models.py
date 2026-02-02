"""Dark Pool Data Models."""

from dataclasses import dataclass, field
from datetime import datetime

from src.darkpool.config import PrintType, BlockDirection, LiquidityLevel


@dataclass
class DarkPoolVolume:
    """Dark pool volume snapshot."""
    symbol: str
    date: str
    dark_volume: float
    lit_volume: float
    total_volume: float
    short_volume: float = 0.0
    n_venues: int = 0
    computed_at: datetime = field(default_factory=datetime.now)

    @property
    def dark_share(self) -> float:
        """Dark pool market share."""
        if self.total_volume == 0:
            return 0.0
        return self.dark_volume / self.total_volume

    @property
    def short_ratio(self) -> float:
        """Short volume as fraction of dark volume."""
        if self.dark_volume == 0:
            return 0.0
        return self.short_volume / self.dark_volume

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "date": self.date,
            "dark_volume": self.dark_volume,
            "lit_volume": self.lit_volume,
            "total_volume": self.total_volume,
            "dark_share": round(self.dark_share, 4),
            "short_volume": self.short_volume,
            "short_ratio": round(self.short_ratio, 4),
            "n_venues": self.n_venues,
        }


@dataclass
class VolumeSummary:
    """Aggregated dark pool volume summary."""
    symbol: str
    avg_dark_share: float
    dark_share_trend: float  # positive = increasing dark activity
    total_dark_volume: float
    total_lit_volume: float
    avg_short_ratio: float
    n_days: int = 0
    is_elevated: bool = False  # dark share above warning threshold
    computed_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "avg_dark_share": self.avg_dark_share,
            "dark_share_trend": self.dark_share_trend,
            "total_dark_volume": self.total_dark_volume,
            "total_lit_volume": self.total_lit_volume,
            "avg_short_ratio": self.avg_short_ratio,
            "n_days": self.n_days,
            "is_elevated": self.is_elevated,
        }


@dataclass
class DarkPrint:
    """Single dark pool print (trade)."""
    symbol: str
    price: float
    size: float
    timestamp: float
    venue: str = ""
    nbbo_bid: float = 0.0
    nbbo_ask: float = 0.0
    print_type: PrintType = PrintType.UNKNOWN
    computed_at: datetime = field(default_factory=datetime.now)

    @property
    def midpoint(self) -> float:
        if self.nbbo_bid > 0 and self.nbbo_ask > 0:
            return (self.nbbo_bid + self.nbbo_ask) / 2
        return self.price

    @property
    def price_improvement(self) -> float:
        """Price improvement from midpoint in bps."""
        mid = self.midpoint
        if mid == 0:
            return 0.0
        return abs(self.price - mid) / mid * 10000

    @property
    def notional(self) -> float:
        return self.price * self.size

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "price": self.price,
            "size": self.size,
            "venue": self.venue,
            "print_type": self.print_type.value,
            "price_improvement": round(self.price_improvement, 2),
            "notional": self.notional,
        }


@dataclass
class PrintSummary:
    """Aggregated dark print analysis."""
    symbol: str
    total_prints: int
    total_volume: float
    total_notional: float
    avg_size: float
    avg_price_improvement: float
    block_count: int = 0
    block_volume: float = 0.0
    retail_count: int = 0
    midpoint_count: int = 0
    type_distribution: dict = field(default_factory=dict)
    computed_at: datetime = field(default_factory=datetime.now)

    @property
    def block_pct(self) -> float:
        """Block volume as percentage of total."""
        if self.total_volume == 0:
            return 0.0
        return self.block_volume / self.total_volume * 100

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "total_prints": self.total_prints,
            "total_volume": self.total_volume,
            "total_notional": self.total_notional,
            "avg_size": self.avg_size,
            "avg_price_improvement": self.avg_price_improvement,
            "block_count": self.block_count,
            "block_pct": round(self.block_pct, 2),
            "type_distribution": self.type_distribution,
        }


@dataclass
class DarkBlock:
    """Detected dark pool block trade."""
    symbol: str
    size: float
    notional: float
    price: float
    direction: BlockDirection = BlockDirection.UNKNOWN
    adv_ratio: float = 0.0  # size as % of ADV
    venue: str = ""
    timestamp: float = 0.0
    cluster_id: int = 0  # 0 = no cluster
    computed_at: datetime = field(default_factory=datetime.now)

    @property
    def is_significant(self) -> bool:
        return self.adv_ratio >= 0.01  # >= 1% of ADV

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "size": self.size,
            "notional": self.notional,
            "price": self.price,
            "direction": self.direction.value,
            "adv_ratio": self.adv_ratio,
            "venue": self.venue,
            "cluster_id": self.cluster_id,
            "is_significant": self.is_significant,
        }


@dataclass
class DarkLiquidity:
    """Dark pool liquidity estimation."""
    symbol: str
    liquidity_score: float  # 0 to 1
    level: LiquidityLevel = LiquidityLevel.SHALLOW
    estimated_depth: float = 0.0  # shares available
    dark_lit_ratio: float = 0.0
    fill_rates: dict = field(default_factory=dict)  # size -> estimated fill rate
    consistency: float = 0.0  # how stable is dark liquidity
    computed_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "liquidity_score": self.liquidity_score,
            "level": self.level.value,
            "estimated_depth": self.estimated_depth,
            "dark_lit_ratio": self.dark_lit_ratio,
            "fill_rates": self.fill_rates,
            "consistency": self.consistency,
        }
