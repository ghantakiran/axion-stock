"""Backtesting Configuration.

Contains all configurable parameters for the backtesting engine,
cost models, execution models, and analysis settings.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional, Any
from enum import Enum


class BarType(str, Enum):
    """Supported bar frequencies."""
    MINUTE_1 = "1m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    HOUR_1 = "1h"
    DAILY = "1d"
    WEEKLY = "1w"
    MONTHLY = "1M"


class RebalanceFrequency(str, Enum):
    """Rebalancing frequency options."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class FillModel(str, Enum):
    """Order fill simulation models."""
    IMMEDIATE = "immediate"  # Fill at bar close
    VWAP = "vwap"  # Volume-weighted average price
    VOLUME_PARTICIPATION = "volume_participation"  # Proportional to volume
    SLIPPAGE = "slippage"  # Close + random spread
    LIMIT = "limit"  # Fill only if price touches limit


@dataclass
class CostModelConfig:
    """Trading cost model configuration."""

    commission_per_share: float = 0.0  # Commission-free era
    commission_per_trade: float = 0.0  # Flat fee per trade
    commission_pct: float = 0.0  # Percentage of notional

    # Regulatory fees
    sec_fee_rate: float = 0.0000278  # SEC transaction fee
    taf_fee_per_share: float = 0.000166  # FINRA TAF

    # Spread and market impact
    min_spread_bps: float = 1.0  # Minimum half-spread in basis points
    market_impact_bps_per_pct_adv: float = 10.0  # Impact per 1% of ADV

    # Slippage
    slippage_bps: float = 2.0  # Random slippage range in bps

    def total_fixed_cost(self, shares: int) -> float:
        """Calculate fixed costs per trade."""
        return (
            shares * self.commission_per_share +
            self.commission_per_trade
        )


@dataclass
class ExecutionConfig:
    """Execution simulation configuration."""

    fill_model: FillModel = FillModel.SLIPPAGE
    max_participation_rate: float = 0.05  # Max 5% of daily volume
    partial_fills: bool = True  # Allow partial order fills
    fill_delay_bars: int = 0  # Delay before fill (bars)


@dataclass
class RiskConfig:
    """Risk management rules for backtesting."""

    max_position_pct: float = 0.15  # Max 15% per position
    max_sector_pct: float = 0.35  # Max 35% per sector
    max_drawdown_halt: float = -0.15  # Stop trading at -15% drawdown
    position_stop_loss: float = -0.15  # Per-position stop-loss
    max_portfolio_beta: float = 1.5


@dataclass
class BacktestConfig:
    """Main backtest configuration."""

    # Time range
    start_date: date = field(default_factory=lambda: date(2020, 1, 1))
    end_date: date = field(default_factory=lambda: date(2024, 12, 31))
    bar_type: BarType = BarType.DAILY

    # Capital
    initial_capital: float = 100_000.0
    currency: str = "USD"

    # Universe
    universe: str = "sp500"  # sp500, nasdaq100, custom
    symbols: list[str] = field(default_factory=list)

    # Strategy (set externally)
    strategy: Any = None
    strategy_params: dict = field(default_factory=dict)

    # Execution
    cost_model: CostModelConfig = field(default_factory=CostModelConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)

    # Risk
    risk_rules: RiskConfig = field(default_factory=RiskConfig)

    # Rebalancing
    rebalance_frequency: RebalanceFrequency = RebalanceFrequency.MONTHLY
    rebalance_day: int = 1  # Day of period (1 = first day)

    # Data handling
    adjust_for_splits: bool = True
    adjust_for_dividends: bool = True
    survivorship_bias_free: bool = True

    # Benchmark
    benchmark: str = "SPY"

    # Random seed for reproducibility
    seed: int = 42


@dataclass
class WalkForwardConfig:
    """Walk-forward optimization configuration."""

    n_windows: int = 5  # Number of walk-forward windows
    in_sample_pct: float = 0.70  # 70% in-sample, 30% OOS
    optimization_metric: str = "sharpe"  # sharpe, cagr, sortino
    min_trades_per_window: int = 10


@dataclass
class MonteCarloConfig:
    """Monte Carlo analysis configuration."""

    n_simulations: int = 10_000
    confidence_level: float = 0.95
    bootstrap_block_size: int = 1  # For block bootstrap
    random_strategy_tests: int = 1000  # For significance testing


# Default configurations
DEFAULT_COST_MODEL = CostModelConfig()
DEFAULT_EXECUTION = ExecutionConfig()
DEFAULT_RISK = RiskConfig()
DEFAULT_BACKTEST = BacktestConfig()
DEFAULT_WALK_FORWARD = WalkForwardConfig()
DEFAULT_MONTE_CARLO = MonteCarloConfig()
