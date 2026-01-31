"""Position Calculator Data Models.

Dataclasses for sizing inputs/outputs, portfolio heat,
drawdown state, and position risk records.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import uuid

from src.position_calculator.config import StopType, InstrumentType, SizingMethod


def _new_id() -> str:
    return uuid.uuid4().hex[:16]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class SizingInputs:
    """Inputs for position size calculation."""
    account_value: float
    entry_price: float
    stop_price: float
    risk_per_trade_pct: float = 1.0
    risk_per_trade_dollars: Optional[float] = None
    target_price: Optional[float] = None
    stop_type: StopType = StopType.FIXED
    instrument_type: InstrumentType = InstrumentType.STOCK
    contract_multiplier: int = 1
    symbol: str = ""
    atr_value: Optional[float] = None
    atr_multiplier: float = 2.0

    @property
    def risk_per_share(self) -> float:
        """Risk per share/contract based on entry and stop."""
        return abs(self.entry_price - self.stop_price)

    @property
    def is_long(self) -> bool:
        """True if this is a long trade (stop below entry)."""
        return self.stop_price < self.entry_price

    @property
    def risk_dollars(self) -> float:
        """Dollar risk amount for this trade."""
        if self.risk_per_trade_dollars is not None:
            return self.risk_per_trade_dollars
        return self.account_value * (self.risk_per_trade_pct / 100.0)


@dataclass
class SizingResult:
    """Output from position size calculation."""
    position_size: int = 0
    position_value: float = 0.0
    risk_amount: float = 0.0
    risk_pct: float = 0.0
    risk_reward_ratio: Optional[float] = None
    r_multiple: Optional[float] = None
    sizing_method: SizingMethod = SizingMethod.FIXED_RISK
    exceeds_max_position: bool = False
    exceeds_portfolio_heat: bool = False
    drawdown_adjusted: bool = False
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """True if position size is valid (positive, no critical warnings)."""
        return self.position_size > 0 and not self.exceeds_portfolio_heat


@dataclass
class PositionRisk:
    """Risk record for a single open position."""
    symbol: str
    qty: int
    entry_price: float
    stop_price: float
    current_price: float
    instrument_type: InstrumentType = InstrumentType.STOCK
    contract_multiplier: int = 1

    @property
    def risk_per_unit(self) -> float:
        """Risk per share/contract from current price to stop."""
        return abs(self.current_price - self.stop_price)

    @property
    def initial_risk_per_unit(self) -> float:
        """Risk per share/contract from entry to stop."""
        return abs(self.entry_price - self.stop_price)

    @property
    def risk_dollars(self) -> float:
        """Total dollar risk for this position."""
        return self.risk_per_unit * self.qty * self.contract_multiplier

    @property
    def initial_risk_dollars(self) -> float:
        """Initial dollar risk for this position."""
        return self.initial_risk_per_unit * self.qty * self.contract_multiplier

    @property
    def market_value(self) -> float:
        """Current market value of the position."""
        return self.current_price * self.qty * self.contract_multiplier

    @property
    def unrealized_pnl(self) -> float:
        """Unrealized P&L."""
        return (self.current_price - self.entry_price) * self.qty * self.contract_multiplier

    @property
    def is_long(self) -> bool:
        return self.stop_price < self.entry_price


@dataclass
class PortfolioHeat:
    """Portfolio heat (total risk exposure) summary."""
    total_heat_pct: float = 0.0
    total_heat_dollars: float = 0.0
    position_heats: dict[str, float] = field(default_factory=dict)
    position_heat_dollars: dict[str, float] = field(default_factory=dict)
    exceeds_limit: bool = False
    at_warning: bool = False
    heat_limit_pct: float = 6.0
    available_heat_pct: float = 6.0
    n_positions: int = 0


@dataclass
class DrawdownState:
    """Current drawdown state."""
    peak_value: float = 0.0
    current_value: float = 0.0
    drawdown_pct: float = 0.0
    drawdown_dollars: float = 0.0
    at_limit: bool = False
    at_warning: bool = False
    at_reduce: bool = False
    limit_pct: float = 10.0
    size_multiplier: float = 1.0
    blocked: bool = False
    peak_date: Optional[datetime] = None
    trough_date: Optional[datetime] = None

    @property
    def days_in_drawdown(self) -> int:
        """Number of days in current drawdown."""
        if self.drawdown_pct == 0 or not self.peak_date:
            return 0
        end = self.trough_date or _utc_now()
        return (end - self.peak_date).days


@dataclass
class SizingRecord:
    """Persisted sizing calculation record."""
    record_id: str = field(default_factory=_new_id)
    symbol: str = ""
    sizing_method: str = ""
    account_value: float = 0.0
    entry_price: float = 0.0
    stop_price: float = 0.0
    position_size: int = 0
    risk_amount: float = 0.0
    risk_pct: float = 0.0
    risk_reward_ratio: Optional[float] = None
    warnings_json: list[str] = field(default_factory=list)
    computed_at: datetime = field(default_factory=_utc_now)
