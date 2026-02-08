"""Configuration for smart order routing."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class VenueType(str, Enum):
    LIT_EXCHANGE = "lit_exchange"
    DARK_POOL = "dark_pool"
    ATS = "ats"
    INTERNALIZER = "internalizer"
    MIDPOINT = "midpoint"


class RoutingStrategy(str, Enum):
    BEST_PRICE = "best_price"
    LOWEST_COST = "lowest_cost"
    FASTEST_FILL = "fastest_fill"
    LOWEST_IMPACT = "lowest_impact"
    SMART = "smart"  # Balanced across all factors


class OrderPriority(str, Enum):
    AGGRESSIVE = "aggressive"
    NEUTRAL = "neutral"
    PASSIVE = "passive"


class FeeModel(str, Enum):
    MAKER_TAKER = "maker_taker"
    FLAT = "flat"
    INVERTED = "inverted"
    FREE = "free"


# Default venue fee schedules (per share)
VENUE_FEES: Dict[str, Dict[str, float]] = {
    "NYSE": {"maker": -0.0020, "taker": 0.0030},
    "NASDAQ": {"maker": -0.0025, "taker": 0.0030},
    "ARCA": {"maker": -0.0024, "taker": 0.0030},
    "BATS_BZX": {"maker": -0.0025, "taker": 0.0030},
    "BATS_BYX": {"maker": 0.0003, "taker": -0.0002},  # Inverted
    "IEX": {"maker": 0.0000, "taker": 0.0009},
    "EDGX": {"maker": -0.0020, "taker": 0.0030},
    "EDGA": {"maker": 0.0004, "taker": -0.0002},  # Inverted
    "MEMX": {"maker": -0.0020, "taker": 0.0025},
    "DARK_MIDPOINT": {"maker": 0.0000, "taker": 0.0010},
}

# Default scoring weights
DEFAULT_WEIGHTS = {
    "fill_probability": 0.30,
    "cost": 0.25,
    "latency": 0.15,
    "price_improvement": 0.20,
    "adverse_selection": 0.10,
}


@dataclass
class VenueConfig:
    """Configuration for a single venue."""

    venue_id: str
    name: str
    venue_type: VenueType = VenueType.LIT_EXCHANGE
    fee_model: FeeModel = FeeModel.MAKER_TAKER
    maker_fee: float = -0.0020
    taker_fee: float = 0.0030
    avg_latency_ms: float = 1.0
    fill_rate: float = 0.80
    is_active: bool = True
    supports_hidden: bool = False
    supports_midpoint: bool = False
    supports_peg: bool = False
    min_order_size: int = 1
    max_order_size: int = 1_000_000


@dataclass
class RoutingConfig:
    """Master routing configuration."""

    strategy: RoutingStrategy = RoutingStrategy.SMART
    priority: OrderPriority = OrderPriority.NEUTRAL
    max_venues: int = 5
    max_slices: int = 10
    min_slice_size: int = 100
    dark_pool_pct: float = 0.30
    price_improvement_threshold: float = 0.0001
    latency_weight: float = 0.15
    cost_weight: float = 0.25
    fill_weight: float = 0.30
    impact_weight: float = 0.20
    adverse_selection_weight: float = 0.10
    enable_nbbo_check: bool = True
    enable_trade_through_prevention: bool = True
