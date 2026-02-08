"""Data models for Liquidity Risk Analytics."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import uuid

from src.liquidity.config import (
    LiquidityTier,
    ImpactModel,
    OrderSide,
    SpreadComponent,
)


def _new_id() -> str:
    return uuid.uuid4().hex[:16]


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class LiquidityScore:
    """Composite liquidity score for a symbol."""

    symbol: str
    composite_score: float  # 0-100
    volume_score: float = 0.0
    spread_score: float = 0.0
    depth_score: float = 0.0
    volatility_score: float = 0.0
    turnover_ratio: Optional[float] = None
    avg_daily_volume: Optional[int] = None
    avg_spread_bps: Optional[float] = None
    market_cap: Optional[int] = None
    liquidity_tier: LiquidityTier = LiquidityTier.MODERATELY_LIQUID
    timestamp: datetime = field(default_factory=_now)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "composite_score": self.composite_score,
            "volume_score": self.volume_score,
            "spread_score": self.spread_score,
            "depth_score": self.depth_score,
            "volatility_score": self.volatility_score,
            "turnover_ratio": self.turnover_ratio,
            "avg_daily_volume": self.avg_daily_volume,
            "avg_spread_bps": self.avg_spread_bps,
            "market_cap": self.market_cap,
            "liquidity_tier": self.liquidity_tier.value,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class SpreadSnapshot:
    """Bid-ask spread snapshot."""

    symbol: str
    bid_price: float
    ask_price: float
    bid_size: int = 0
    ask_size: int = 0
    effective_spread: Optional[float] = None
    realized_spread: Optional[float] = None
    timestamp: datetime = field(default_factory=_now)

    @property
    def mid_price(self) -> float:
        return (self.bid_price + self.ask_price) / 2

    @property
    def spread(self) -> float:
        return self.ask_price - self.bid_price

    @property
    def spread_bps(self) -> float:
        mid = self.mid_price
        if mid == 0:
            return 0.0
        return (self.spread / mid) * 10_000

    @property
    def spread_pct(self) -> float:
        mid = self.mid_price
        if mid == 0:
            return 0.0
        return (self.spread / mid) * 100

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "bid_price": self.bid_price,
            "ask_price": self.ask_price,
            "mid_price": self.mid_price,
            "spread": self.spread,
            "spread_bps": self.spread_bps,
            "spread_pct": self.spread_pct,
            "bid_size": self.bid_size,
            "ask_size": self.ask_size,
            "effective_spread": self.effective_spread,
            "realized_spread": self.realized_spread,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class MarketImpactEstimate:
    """Market impact estimation result."""

    symbol: str
    order_size_shares: int
    order_size_value: float
    side: OrderSide
    estimated_impact_bps: float
    temporary_impact_bps: float = 0.0
    permanent_impact_bps: float = 0.0
    estimated_cost: float = 0.0
    participation_rate: Optional[float] = None
    model_used: ImpactModel = ImpactModel.SQUARE_ROOT
    model_params: dict = field(default_factory=dict)
    confidence: float = 0.0
    estimate_id: str = field(default_factory=_new_id)
    timestamp: datetime = field(default_factory=_now)

    @property
    def total_cost_bps(self) -> float:
        return self.temporary_impact_bps + self.permanent_impact_bps

    def to_dict(self) -> dict:
        return {
            "estimate_id": self.estimate_id,
            "symbol": self.symbol,
            "order_size_shares": self.order_size_shares,
            "order_size_value": self.order_size_value,
            "side": self.side.value,
            "estimated_impact_bps": self.estimated_impact_bps,
            "temporary_impact_bps": self.temporary_impact_bps,
            "permanent_impact_bps": self.permanent_impact_bps,
            "total_cost_bps": self.total_cost_bps,
            "estimated_cost": self.estimated_cost,
            "participation_rate": self.participation_rate,
            "model_used": self.model_used.value,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class SlippageRecord:
    """Historical slippage record."""

    symbol: str
    side: OrderSide
    order_size: int
    expected_price: float
    executed_price: float
    market_volume: Optional[int] = None
    participation_rate: Optional[float] = None
    spread_at_entry: Optional[float] = None
    volatility_at_entry: Optional[float] = None
    timestamp: datetime = field(default_factory=_now)

    @property
    def slippage(self) -> float:
        if self.side == OrderSide.BUY:
            return self.executed_price - self.expected_price
        return self.expected_price - self.executed_price

    @property
    def slippage_bps(self) -> float:
        if self.expected_price == 0:
            return 0.0
        return (self.slippage / self.expected_price) * 10_000

    @property
    def slippage_cost(self) -> float:
        return abs(self.slippage) * self.order_size

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "side": self.side.value,
            "order_size": self.order_size,
            "expected_price": self.expected_price,
            "executed_price": self.executed_price,
            "slippage": self.slippage,
            "slippage_bps": self.slippage_bps,
            "slippage_cost": self.slippage_cost,
            "market_volume": self.market_volume,
            "participation_rate": self.participation_rate,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class LiquidityProfile:
    """Complete liquidity profile for a symbol."""

    symbol: str
    score: LiquidityScore
    recent_spreads: list[SpreadSnapshot] = field(default_factory=list)
    impact_estimates: list[MarketImpactEstimate] = field(default_factory=list)
    recent_slippage: list[SlippageRecord] = field(default_factory=list)
    alerts: list[str] = field(default_factory=list)

    @property
    def avg_spread_bps(self) -> float:
        if not self.recent_spreads:
            return 0.0
        return sum(s.spread_bps for s in self.recent_spreads) / len(self.recent_spreads)

    @property
    def avg_slippage_bps(self) -> float:
        if not self.recent_slippage:
            return 0.0
        return sum(s.slippage_bps for s in self.recent_slippage) / len(self.recent_slippage)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "score": self.score.to_dict(),
            "avg_spread_bps": self.avg_spread_bps,
            "avg_slippage_bps": self.avg_slippage_bps,
            "spread_count": len(self.recent_spreads),
            "slippage_count": len(self.recent_slippage),
            "alerts": self.alerts,
        }
