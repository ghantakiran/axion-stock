"""Configuration for Liquidity Risk Analytics."""

from enum import Enum
from dataclasses import dataclass


class LiquidityTier(Enum):
    """Liquidity classification tiers."""
    HIGHLY_LIQUID = "highly_liquid"
    LIQUID = "liquid"
    MODERATELY_LIQUID = "moderately_liquid"
    ILLIQUID = "illiquid"
    HIGHLY_ILLIQUID = "highly_illiquid"


class ImpactModel(Enum):
    """Market impact model types."""
    LINEAR = "linear"
    SQUARE_ROOT = "square_root"
    POWER_LAW = "power_law"
    ALMGREN_CHRISS = "almgren_chriss"


class OrderSide(Enum):
    """Order side."""
    BUY = "buy"
    SELL = "sell"


class SpreadComponent(Enum):
    """Spread decomposition components."""
    ADVERSE_SELECTION = "adverse_selection"
    INVENTORY = "inventory"
    ORDER_PROCESSING = "order_processing"


# Tier thresholds (composite score ranges)
TIER_THRESHOLDS: dict[str, tuple[float, float]] = {
    LiquidityTier.HIGHLY_LIQUID.value: (80, 100),
    LiquidityTier.LIQUID.value: (60, 80),
    LiquidityTier.MODERATELY_LIQUID.value: (40, 60),
    LiquidityTier.ILLIQUID.value: (20, 40),
    LiquidityTier.HIGHLY_ILLIQUID.value: (0, 20),
}

# Market impact coefficients by tier
IMPACT_COEFFICIENTS: dict[str, dict] = {
    LiquidityTier.HIGHLY_LIQUID.value: {
        "linear_coeff": 0.05,
        "sqrt_coeff": 0.10,
        "temp_decay": 0.5,
        "perm_fraction": 0.3,
    },
    LiquidityTier.LIQUID.value: {
        "linear_coeff": 0.10,
        "sqrt_coeff": 0.20,
        "temp_decay": 0.4,
        "perm_fraction": 0.35,
    },
    LiquidityTier.MODERATELY_LIQUID.value: {
        "linear_coeff": 0.20,
        "sqrt_coeff": 0.40,
        "temp_decay": 0.3,
        "perm_fraction": 0.4,
    },
    LiquidityTier.ILLIQUID.value: {
        "linear_coeff": 0.50,
        "sqrt_coeff": 0.80,
        "temp_decay": 0.2,
        "perm_fraction": 0.5,
    },
    LiquidityTier.HIGHLY_ILLIQUID.value: {
        "linear_coeff": 1.00,
        "sqrt_coeff": 1.50,
        "temp_decay": 0.1,
        "perm_fraction": 0.6,
    },
}


@dataclass
class LiquidityConfig:
    """Liquidity analysis configuration."""

    # Scoring weights
    volume_weight: float = 0.30
    spread_weight: float = 0.25
    depth_weight: float = 0.20
    volatility_weight: float = 0.25

    # Volume thresholds
    high_volume_threshold: int = 10_000_000
    low_volume_threshold: int = 100_000

    # Spread thresholds (bps)
    tight_spread_bps: float = 5.0
    wide_spread_bps: float = 50.0

    # Impact modeling
    default_impact_model: ImpactModel = ImpactModel.SQUARE_ROOT
    max_participation_rate: float = 0.10

    # Slippage
    slippage_lookback_days: int = 30


DEFAULT_LIQUIDITY_CONFIG = LiquidityConfig()
