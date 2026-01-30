"""Portfolio Optimization Configuration.

Contains all configurable parameters for optimization methods,
constraints, tax management, and portfolio templates.
"""

from dataclasses import dataclass, field


@dataclass
class OptimizationConfig:
    """Core optimization parameters."""

    risk_aversion: float = 2.5  # Lambda for mean-variance
    tau: float = 0.05  # Black-Litterman uncertainty scalar
    max_iterations: int = 1000
    solver_tolerance: float = 1e-8
    risk_free_rate: float = 0.05


@dataclass
class ConstraintConfig:
    """Default constraint values."""

    min_weight: float = 0.0
    max_weight: float = 0.15
    min_positions: int = 10
    max_positions: int = 30
    max_sector_pct: float = 0.35
    min_sectors: int = 5
    max_turnover: float = 0.30
    max_beta: float = 1.5
    max_volatility: float = 0.25
    min_market_cap: float = 1e9


@dataclass
class TaxConfig:
    """Tax-aware portfolio management configuration."""

    short_term_rate: float = 0.37  # Ordinary income rate
    long_term_rate: float = 0.20  # Long-term capital gains
    long_term_threshold_days: int = 365
    wash_sale_window_days: int = 30
    min_harvest_loss: float = 500.0
    harvest_replacement_min_similarity: float = 0.70


@dataclass
class PortfolioConfig:
    """Top-level portfolio optimizer configuration."""

    optimization: OptimizationConfig = field(default_factory=OptimizationConfig)
    constraints: ConstraintConfig = field(default_factory=ConstraintConfig)
    tax: TaxConfig = field(default_factory=TaxConfig)
