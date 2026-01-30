"""Options Platform Configuration.

Contains all configurable parameters for options pricing,
volatility surface, strategy building, and activity detection.
"""

from dataclasses import dataclass, field


@dataclass
class PricingConfig:
    """Options pricing engine configuration."""

    risk_free_rate: float = 0.05
    dividend_yield: float = 0.0
    iv_solver_max_iterations: int = 100
    iv_solver_tolerance: float = 1e-8
    iv_initial_guess: float = 0.30
    iv_min: float = 0.001
    iv_max: float = 5.0
    binomial_steps: int = 200
    monte_carlo_simulations: int = 100_000
    monte_carlo_seed: int = 42


@dataclass
class VolatilityConfig:
    """Volatility surface configuration."""

    min_dte: int = 7
    max_dte: int = 365
    min_moneyness: float = 0.7
    max_moneyness: float = 1.3
    svi_initial_params: dict = field(default_factory=lambda: {
        "a": 0.04, "b": 0.1, "rho": -0.3, "m": 0.0, "sigma": 0.2,
    })
    iv_history_lookback_days: int = 252
    vol_cone_windows: list = field(default_factory=lambda: [20, 40, 60, 120, 252])


@dataclass
class StrategyConfig:
    """Strategy builder configuration."""

    default_pop_simulations: int = 100_000
    payoff_price_points: int = 200
    max_legs: int = 8
    contract_multiplier: int = 100


@dataclass
class ActivityConfig:
    """Unusual options activity detection thresholds."""

    volume_spike_multiplier: float = 5.0
    oi_surge_multiplier: float = 3.0
    iv_rank_threshold: float = 0.80
    large_block_threshold: int = 1000
    put_call_ratio_high: float = 2.0
    put_call_ratio_low: float = 0.3
    near_expiry_volume_multiplier: float = 10.0
    near_expiry_max_dte: int = 7


@dataclass
class BacktestConfig:
    """Options backtesting configuration."""

    slippage_pct: float = 0.01
    commission_per_contract: float = 0.65
    min_dte_entry: int = 30
    max_dte_entry: int = 60
    profit_target_pct: float = 0.50
    stop_loss_pct: float = 2.0
    min_iv_rank: float = 0.0


@dataclass
class OptionsConfig:
    """Top-level options platform configuration."""

    pricing: PricingConfig = field(default_factory=PricingConfig)
    volatility: VolatilityConfig = field(default_factory=VolatilityConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    activity: ActivityConfig = field(default_factory=ActivityConfig)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)
