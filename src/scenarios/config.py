"""Portfolio Scenarios Configuration.

Enums, constants, and configuration for portfolio scenario analysis.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# =============================================================================
# Enums
# =============================================================================

class TradeAction(str, Enum):
    """Trade action type."""
    BUY = "buy"
    SELL = "sell"
    SELL_ALL = "sell_all"


class SizeMethod(str, Enum):
    """Position sizing method."""
    SHARES = "shares"
    DOLLARS = "dollars"
    WEIGHT = "weight"
    PERCENT_OF_POSITION = "percent_of_position"


class RebalanceStrategy(str, Enum):
    """Rebalancing strategy."""
    TARGET_WEIGHT = "target_weight"
    THRESHOLD = "threshold"
    CALENDAR = "calendar"
    TAX_AWARE = "tax_aware"
    CASH_FLOW = "cash_flow"


class ScenarioType(str, Enum):
    """Market scenario type."""
    MARKET_CRASH = "market_crash"
    BEAR_MARKET = "bear_market"
    BULL_MARKET = "bull_market"
    SECTOR_ROTATION = "sector_rotation"
    RATE_SPIKE = "rate_spike"
    RECESSION = "recession"
    INFLATION = "inflation"
    BLACK_SWAN = "black_swan"
    CUSTOM = "custom"


class GoalType(str, Enum):
    """Investment goal type."""
    RETIREMENT = "retirement"
    HOUSE = "house"
    EDUCATION = "education"
    EMERGENCY_FUND = "emergency_fund"
    VACATION = "vacation"
    CAR = "car"
    CUSTOM = "custom"


class GoalPriority(str, Enum):
    """Goal priority."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# =============================================================================
# Constants
# =============================================================================

# Default assumptions
DEFAULT_EXPECTED_RETURN = 0.07  # 7% annual
DEFAULT_VOLATILITY = 0.15  # 15% annual
DEFAULT_INFLATION = 0.03  # 3% annual
DEFAULT_RISK_FREE_RATE = 0.045  # 4.5%

# Rebalancing thresholds
DEFAULT_REBALANCE_THRESHOLD = 0.05  # 5% drift
MIN_TRADE_SIZE = 100  # Minimum trade size in dollars

# Scenario defaults
DEFAULT_MARKET_CRASH = -0.20
DEFAULT_BEAR_MARKET = -0.35
DEFAULT_BLACK_SWAN = -0.50

# Sector beta assumptions (relative to market)
SECTOR_BETAS = {
    "Technology": 1.20,
    "Healthcare": 0.85,
    "Financial": 1.10,
    "Consumer Cyclical": 1.15,
    "Consumer Defensive": 0.70,
    "Industrial": 1.05,
    "Energy": 1.30,
    "Utilities": 0.55,
    "Real Estate": 0.90,
    "Basic Materials": 1.10,
    "Communication Services": 0.95,
}

# Factor sensitivities for scenarios
FACTOR_SENSITIVITIES = {
    "value": {"recession": 0.8, "inflation": 1.1, "rate_spike": 0.9},
    "growth": {"recession": 1.3, "inflation": 0.8, "rate_spike": 1.2},
    "momentum": {"recession": 1.1, "inflation": 1.0, "rate_spike": 1.0},
    "quality": {"recession": 0.7, "inflation": 0.9, "rate_spike": 0.85},
    "size": {"recession": 1.2, "inflation": 1.0, "rate_spike": 1.1},
}


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class SimulationConfig:
    """Configuration for simulations."""
    # Cost assumptions
    commission_per_trade: float = 0.0
    slippage_bps: int = 5  # Basis points
    
    # Tax assumptions
    short_term_rate: float = 0.35
    long_term_rate: float = 0.15
    
    # Monte Carlo
    monte_carlo_runs: int = 1000
    
    # Rebalancing
    min_trade_size: float = MIN_TRADE_SIZE
    rebalance_threshold: float = DEFAULT_REBALANCE_THRESHOLD


@dataclass
class GoalConfig:
    """Configuration for goal planning."""
    expected_return: float = DEFAULT_EXPECTED_RETURN
    volatility: float = DEFAULT_VOLATILITY
    inflation_rate: float = DEFAULT_INFLATION
    monte_carlo_runs: int = 1000


DEFAULT_SIMULATION_CONFIG = SimulationConfig()
DEFAULT_GOAL_CONFIG = GoalConfig()
