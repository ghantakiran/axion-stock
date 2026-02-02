"""Market Microstructure Data Models."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SpreadMetrics:
    """Spread analysis results."""
    symbol: str
    quoted_spread: float  # best ask - best bid
    quoted_spread_bps: float  # in basis points
    effective_spread: float  # 2 * |price - midpoint|
    effective_spread_bps: float
    realized_spread: float  # 2 * direction * (price - future_midpoint)
    realized_spread_bps: float
    roll_spread: float  # Roll's implied spread
    adverse_selection: float  # effective - realized
    adverse_selection_bps: float
    midpoint: float
    computed_at: datetime = field(default_factory=datetime.now)

    @property
    def spread_efficiency(self) -> float:
        """Ratio of realized to effective spread (inventory component)."""
        if self.effective_spread == 0:
            return 0.0
        return self.realized_spread / self.effective_spread

    @property
    def adverse_selection_pct(self) -> float:
        """Adverse selection as percentage of effective spread."""
        if self.effective_spread == 0:
            return 0.0
        return self.adverse_selection / self.effective_spread * 100

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "quoted_spread": self.quoted_spread,
            "quoted_spread_bps": self.quoted_spread_bps,
            "effective_spread": self.effective_spread,
            "effective_spread_bps": self.effective_spread_bps,
            "realized_spread": self.realized_spread,
            "realized_spread_bps": self.realized_spread_bps,
            "roll_spread": self.roll_spread,
            "adverse_selection": self.adverse_selection,
            "adverse_selection_bps": self.adverse_selection_bps,
            "midpoint": self.midpoint,
        }


@dataclass
class BookLevel:
    """Single order book level."""
    price: float
    size: float
    order_count: int = 0


@dataclass
class OrderBookSnapshot:
    """Order book state at a point in time."""
    symbol: str
    bids: list[BookLevel] = field(default_factory=list)
    asks: list[BookLevel] = field(default_factory=list)
    imbalance: float = 0.0  # (bid_size - ask_size) / (bid_size + ask_size)
    bid_depth: float = 0.0  # total bid size across levels
    ask_depth: float = 0.0  # total ask size across levels
    weighted_midpoint: float = 0.0  # size-weighted midpoint
    book_pressure: float = 0.0  # net pressure metric
    bid_slope: float = 0.0  # price sensitivity of bid side
    ask_slope: float = 0.0  # price sensitivity of ask side
    resilience: float = 0.0  # recovery rate after trades
    computed_at: datetime = field(default_factory=datetime.now)

    @property
    def total_depth(self) -> float:
        return self.bid_depth + self.ask_depth

    @property
    def spread(self) -> float:
        if self.bids and self.asks:
            return self.asks[0].price - self.bids[0].price
        return 0.0

    @property
    def midpoint(self) -> float:
        if self.bids and self.asks:
            return (self.asks[0].price + self.bids[0].price) / 2
        return 0.0

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "imbalance": self.imbalance,
            "bid_depth": self.bid_depth,
            "ask_depth": self.ask_depth,
            "total_depth": self.total_depth,
            "weighted_midpoint": self.weighted_midpoint,
            "book_pressure": self.book_pressure,
            "bid_slope": self.bid_slope,
            "ask_slope": self.ask_slope,
            "resilience": self.resilience,
            "spread": self.spread,
        }


@dataclass
class TickMetrics:
    """Tick-level aggregated metrics."""
    symbol: str
    total_trades: int
    total_volume: float
    buy_volume: float
    sell_volume: float
    vwap: float
    twap: float
    tick_to_trade_ratio: float  # ticks per trade
    kyle_lambda: float  # price impact coefficient
    size_distribution: dict = field(default_factory=dict)  # bucket -> count
    computed_at: datetime = field(default_factory=datetime.now)

    @property
    def buy_ratio(self) -> float:
        """Fraction of volume classified as buyer-initiated."""
        if self.total_volume == 0:
            return 0.0
        return self.buy_volume / self.total_volume

    @property
    def order_imbalance(self) -> float:
        """Signed order imbalance: (buy - sell) / total."""
        if self.total_volume == 0:
            return 0.0
        return (self.buy_volume - self.sell_volume) / self.total_volume

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "total_trades": self.total_trades,
            "total_volume": self.total_volume,
            "buy_volume": self.buy_volume,
            "sell_volume": self.sell_volume,
            "vwap": self.vwap,
            "twap": self.twap,
            "tick_to_trade_ratio": self.tick_to_trade_ratio,
            "kyle_lambda": self.kyle_lambda,
            "buy_ratio": self.buy_ratio,
            "order_imbalance": self.order_imbalance,
        }


@dataclass
class Trade:
    """Single trade record for tick analysis."""
    price: float
    size: float
    timestamp: float  # unix timestamp
    side: int = 0  # 1 = buy, -1 = sell, 0 = unclassified


@dataclass
class ImpactEstimate:
    """Price impact estimation result."""
    symbol: str
    order_size: float  # shares
    temporary_impact_bps: float
    permanent_impact_bps: float
    total_impact_bps: float
    cost_dollars: float  # estimated dollar cost
    participation_rate: float
    daily_volume: float
    volatility: float
    model_used: str = ""
    computed_at: datetime = field(default_factory=datetime.now)

    @property
    def impact_ratio(self) -> float:
        """Permanent as fraction of total impact."""
        if self.total_impact_bps == 0:
            return 0.0
        return self.permanent_impact_bps / self.total_impact_bps

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "order_size": self.order_size,
            "temporary_impact_bps": self.temporary_impact_bps,
            "permanent_impact_bps": self.permanent_impact_bps,
            "total_impact_bps": self.total_impact_bps,
            "cost_dollars": self.cost_dollars,
            "participation_rate": self.participation_rate,
            "daily_volume": self.daily_volume,
            "volatility": self.volatility,
            "model_used": self.model_used,
        }
