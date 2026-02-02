"""Fund Flow Data Models."""

from dataclasses import dataclass, field
from datetime import datetime

from src.fundflow.config import FlowDirection, FlowStrength, RotationPhase, SmartMoneySignal


@dataclass
class FundFlow:
    """Single fund flow record."""
    fund_name: str
    date: str
    inflow: float
    outflow: float
    aum: float  # assets under management
    computed_at: datetime = field(default_factory=datetime.now)

    @property
    def net_flow(self) -> float:
        return self.inflow - self.outflow

    @property
    def flow_pct(self) -> float:
        """Net flow as percentage of AUM."""
        if self.aum == 0:
            return 0.0
        return self.net_flow / self.aum * 100

    @property
    def direction(self) -> FlowDirection:
        if self.net_flow > 0:
            return FlowDirection.INFLOW
        elif self.net_flow < 0:
            return FlowDirection.OUTFLOW
        return FlowDirection.NEUTRAL

    def to_dict(self) -> dict:
        return {
            "fund_name": self.fund_name,
            "date": self.date,
            "inflow": self.inflow,
            "outflow": self.outflow,
            "net_flow": self.net_flow,
            "aum": self.aum,
            "flow_pct": self.flow_pct,
            "direction": self.direction.value,
        }


@dataclass
class FlowSummary:
    """Aggregated flow summary for a fund or sector."""
    name: str
    total_inflow: float
    total_outflow: float
    net_flow: float
    flow_momentum: float  # rate of change
    cumulative_flow: float
    avg_flow_pct: float  # average flow as % of AUM
    strength: FlowStrength = FlowStrength.NEUTRAL
    n_days: int = 0
    computed_at: datetime = field(default_factory=datetime.now)

    @property
    def flow_ratio(self) -> float:
        """Inflow-to-outflow ratio."""
        if self.total_outflow == 0:
            return float("inf") if self.total_inflow > 0 else 0.0
        return self.total_inflow / self.total_outflow

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "total_inflow": self.total_inflow,
            "total_outflow": self.total_outflow,
            "net_flow": self.net_flow,
            "flow_momentum": self.flow_momentum,
            "cumulative_flow": self.cumulative_flow,
            "avg_flow_pct": self.avg_flow_pct,
            "strength": self.strength.value,
            "n_days": self.n_days,
            "flow_ratio": self.flow_ratio,
        }


@dataclass
class InstitutionalPosition:
    """Institutional holder position."""
    holder_name: str
    symbol: str
    shares: float
    market_value: float
    ownership_pct: float
    change_shares: float = 0.0  # quarter-over-quarter
    change_pct: float = 0.0
    quarter: str = ""
    computed_at: datetime = field(default_factory=datetime.now)

    @property
    def is_new_position(self) -> bool:
        return self.change_pct >= 100.0 or (self.change_shares > 0 and self.shares == self.change_shares)

    @property
    def is_exit(self) -> bool:
        return self.change_pct <= -100.0

    def to_dict(self) -> dict:
        return {
            "holder_name": self.holder_name,
            "symbol": self.symbol,
            "shares": self.shares,
            "market_value": self.market_value,
            "ownership_pct": self.ownership_pct,
            "change_shares": self.change_shares,
            "change_pct": self.change_pct,
            "quarter": self.quarter,
        }


@dataclass
class InstitutionalSummary:
    """Institutional ownership summary for a symbol."""
    symbol: str
    total_institutional_pct: float
    n_holders: int
    top_holder: str
    top_holder_pct: float
    concentration: float  # HHI-style concentration
    net_change_pct: float  # aggregate position change
    new_positions: int = 0
    exits: int = 0
    increases: int = 0
    decreases: int = 0
    computed_at: datetime = field(default_factory=datetime.now)

    @property
    def is_concentrated(self) -> bool:
        return self.concentration > 0.25

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "total_institutional_pct": self.total_institutional_pct,
            "n_holders": self.n_holders,
            "top_holder": self.top_holder,
            "top_holder_pct": self.top_holder_pct,
            "concentration": self.concentration,
            "net_change_pct": self.net_change_pct,
            "new_positions": self.new_positions,
            "exits": self.exits,
            "increases": self.increases,
            "decreases": self.decreases,
        }


@dataclass
class SectorRotation:
    """Sector rotation score."""
    sector: str
    flow_score: float  # normalized flow strength
    momentum_score: float  # flow momentum
    rank: int = 0
    phase: RotationPhase = RotationPhase.MID_CYCLE
    relative_strength: float = 0.0
    computed_at: datetime = field(default_factory=datetime.now)

    @property
    def composite_score(self) -> float:
        return 0.6 * self.flow_score + 0.4 * self.momentum_score

    def to_dict(self) -> dict:
        return {
            "sector": self.sector,
            "flow_score": self.flow_score,
            "momentum_score": self.momentum_score,
            "rank": self.rank,
            "phase": self.phase.value,
            "relative_strength": self.relative_strength,
            "composite_score": self.composite_score,
        }


@dataclass
class SmartMoneyResult:
    """Smart money detection result."""
    symbol: str
    institutional_flow: float
    retail_flow: float
    smart_money_score: float  # -1 to 1
    conviction: float  # 0 to 1
    signal: SmartMoneySignal = SmartMoneySignal.NEUTRAL
    flow_price_divergence: float = 0.0  # positive = bullish divergence
    is_contrarian: bool = False
    computed_at: datetime = field(default_factory=datetime.now)

    @property
    def net_smart_flow(self) -> float:
        return self.institutional_flow - self.retail_flow

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "institutional_flow": self.institutional_flow,
            "retail_flow": self.retail_flow,
            "smart_money_score": self.smart_money_score,
            "conviction": self.conviction,
            "signal": self.signal.value,
            "flow_price_divergence": self.flow_price_divergence,
            "is_contrarian": self.is_contrarian,
            "net_smart_flow": self.net_smart_flow,
        }
