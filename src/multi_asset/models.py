"""Multi-Asset Data Models.

Data structures for crypto, futures, international equities,
FX rates, and cross-asset portfolios.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

from src.multi_asset.config import (
    AssetClass,
    CryptoCategory,
    FuturesCategory,
    SettlementType,
    MarginAlertLevel,
)


# ─── Crypto Models ──────────────────────────────────────────────────────

@dataclass
class CryptoAsset:
    """Cryptocurrency asset."""

    symbol: str
    name: str
    category: CryptoCategory
    price_usd: float = 0.0
    market_cap: float = 0.0
    volume_24h: float = 0.0
    circulating_supply: float = 0.0
    max_supply: Optional[float] = None
    rank: int = 0

    @property
    def fully_diluted_value(self) -> float:
        if self.max_supply and self.price_usd:
            return self.price_usd * self.max_supply
        return self.market_cap


@dataclass
class CryptoFactorScores:
    """Factor scores for a crypto asset."""

    symbol: str
    score_date: date = field(default_factory=date.today)
    value: float = 0.0       # NVT, MVRV
    momentum: float = 0.0    # 30/90/180d returns
    quality: float = 0.0     # Dev activity, TVL
    sentiment: float = 0.0   # Social, fear/greed
    network: float = 0.0     # Active addrs, hash rate
    composite: float = 0.0

    def compute_composite(self, weights: Optional[dict[str, float]] = None) -> float:
        w = weights or {
            "value": 0.20, "momentum": 0.25, "quality": 0.20,
            "sentiment": 0.15, "network": 0.20,
        }
        self.composite = (
            self.value * w["value"]
            + self.momentum * w["momentum"]
            + self.quality * w["quality"]
            + self.sentiment * w["sentiment"]
            + self.network * w["network"]
        )
        return self.composite


@dataclass
class OnChainMetrics:
    """On-chain metrics for a crypto asset."""

    symbol: str
    nvt_ratio: float = 0.0
    mvrv_ratio: float = 0.0
    stock_to_flow: float = 0.0
    active_addresses_24h: int = 0
    transaction_count_24h: int = 0
    hash_rate: float = 0.0
    staking_ratio: float = 0.0
    tvl: float = 0.0
    developer_commits_30d: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)


# ─── Futures Models ─────────────────────────────────────────────────────

@dataclass
class FuturesContract:
    """A specific futures contract instance."""

    root: str                # e.g. "ES"
    contract_month: str      # e.g. "H25" (March 2025)
    symbol: str = ""         # e.g. "ESH25"
    expiry: Optional[date] = None
    price: float = 0.0
    volume: int = 0
    open_interest: int = 0
    is_front_month: bool = False

    def __post_init__(self):
        if not self.symbol:
            self.symbol = f"{self.root}{self.contract_month}"


@dataclass
class FuturesPosition:
    """Futures position with margin tracking."""

    contract: FuturesContract
    qty: int  # positive = long, negative = short
    avg_entry_price: float = 0.0
    current_price: float = 0.0
    multiplier: float = 1.0
    margin_required: float = 0.0

    @property
    def notional_value(self) -> float:
        return abs(self.qty) * self.current_price * self.multiplier

    @property
    def unrealized_pnl(self) -> float:
        return self.qty * (self.current_price - self.avg_entry_price) * self.multiplier

    @property
    def side(self) -> str:
        return "long" if self.qty > 0 else "short"


@dataclass
class RollOrder:
    """Futures contract roll order."""

    old_contract: str
    new_contract: str
    qty: int
    roll_date: date = field(default_factory=date.today)
    spread_price: Optional[float] = None
    reason: str = "expiry"


@dataclass
class MarginStatus:
    """Account margin status."""

    total_margin_required: float = 0.0
    total_margin_available: float = 0.0
    utilization_pct: float = 0.0
    alert_level: MarginAlertLevel = MarginAlertLevel.NORMAL
    excess_margin: float = 0.0

    def update(self):
        if self.total_margin_available > 0:
            self.utilization_pct = self.total_margin_required / self.total_margin_available
        else:
            self.utilization_pct = 0.0

        self.excess_margin = self.total_margin_available - self.total_margin_required

        if self.utilization_pct >= 1.10:
            self.alert_level = MarginAlertLevel.LIQUIDATION
        elif self.utilization_pct >= 1.00:
            self.alert_level = MarginAlertLevel.MARGIN_CALL
        elif self.utilization_pct >= 0.90:
            self.alert_level = MarginAlertLevel.CRITICAL
        elif self.utilization_pct >= 0.80:
            self.alert_level = MarginAlertLevel.WARNING
        else:
            self.alert_level = MarginAlertLevel.NORMAL


# ─── International Equity Models ────────────────────────────────────────

@dataclass
class FXRate:
    """Foreign exchange rate."""

    base: str
    quote: str
    rate: float
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def pair(self) -> str:
        return f"{self.base}/{self.quote}"

    @property
    def inverse(self) -> float:
        return 1.0 / self.rate if self.rate > 0 else 0.0


@dataclass
class IntlEquity:
    """International equity instrument."""

    symbol: str
    name: str
    exchange: str
    currency: str
    market: str
    price_local: float = 0.0
    price_usd: float = 0.0
    market_cap_usd: float = 0.0
    sector: str = ""

    def convert_to_usd(self, fx_rate: float):
        self.price_usd = self.price_local * fx_rate


# ─── Cross-Asset Models ────────────────────────────────────────────────

@dataclass
class AssetAllocation:
    """Single asset allocation within a multi-asset portfolio."""

    symbol: str
    asset_class: AssetClass
    weight: float
    value_usd: float = 0.0
    currency: str = "USD"
    fx_rate: float = 1.0


@dataclass
class MultiAssetPortfolio:
    """Multi-asset portfolio."""

    name: str
    total_value_usd: float
    allocations: list[AssetAllocation] = field(default_factory=list)
    template: str = "custom"

    @property
    def allocation_by_class(self) -> dict[AssetClass, float]:
        result: dict[AssetClass, float] = {}
        for alloc in self.allocations:
            result[alloc.asset_class] = result.get(alloc.asset_class, 0) + alloc.weight
        return result

    @property
    def n_positions(self) -> int:
        return len(self.allocations)


@dataclass
class CrossAssetRiskReport:
    """Cross-asset risk analysis report."""

    total_var_95: float = 0.0
    total_var_99: float = 0.0
    risk_by_asset_class: dict[str, float] = field(default_factory=dict)
    currency_risk: float = 0.0
    leverage_ratio: float = 1.0
    margin_utilization: float = 0.0
    correlation_regime: str = "normal"
    max_drawdown: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
