"""ML Prediction Engine Configuration.

Contains all configurable ML parameters, model hyperparameters,
and feature engineering settings.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class FeatureConfig:
    """Feature engineering configuration."""

    # Factor score features
    factor_scores: list[str] = field(default_factory=lambda: [
        "value_score", "momentum_score", "quality_score",
        "growth_score", "volatility_score", "technical_score",
    ])

    # Sub-factor raw values
    sub_factors: list[str] = field(default_factory=lambda: [
        "pe_ratio", "pb_ratio", "ev_ebitda", "fcf_yield",
        "roe", "roa", "roic", "debt_equity",
        "revenue_growth", "eps_growth", "fcf_growth",
        "return_3m", "return_6m", "return_12m",
        "rsi_14", "macd_signal", "price_to_sma200",
        "realized_vol_60d", "beta", "idio_vol",
    ])

    # Cross-sectional features
    cross_sectional: list[str] = field(default_factory=lambda: [
        "sector_rank", "industry_rank",
        "sector_momentum", "sector_dispersion",
    ])

    # Macro features
    macro: list[str] = field(default_factory=lambda: [
        "vix", "yield_curve_slope", "credit_spread",
        "sp500_return_20d", "market_breadth",
    ])

    # Interaction feature pairs
    interactions: list[tuple[str, str]] = field(default_factory=lambda: [
        ("value_score", "momentum_score"),
        ("quality_score", "growth_score"),
        ("momentum_score", "volatility_score"),
    ])

    # Lag periods (in trading days)
    lag_periods: list[int] = field(default_factory=lambda: [21, 63])

    # Rolling window sizes
    rolling_windows: list[int] = field(default_factory=lambda: [5, 10, 21])

    # Maximum features to select (remove collinear > threshold)
    max_features: int = 80
    collinearity_threshold: float = 0.90

    # Cross-sectional normalization
    normalize_cross_sectional: bool = True


@dataclass
class RankingModelConfig:
    """LightGBM stock ranking model configuration."""

    # Target
    forward_days: int = 21  # Predict next 21-trading-day return
    num_quintiles: int = 5  # Rank into quintiles

    # LightGBM hyperparameters (defaults, tuned via Optuna)
    n_estimators: int = 500
    max_depth: int = 6
    learning_rate: float = 0.05
    min_child_samples: int = 50
    subsample: float = 0.8
    colsample_bytree: float = 0.8
    reg_alpha: float = 0.1
    reg_lambda: float = 0.1
    num_leaves: int = 31

    # Ensemble settings
    n_ensemble: int = 5  # Number of models with different seeds
    ensemble_method: str = "mean"  # mean or median

    # Objective
    objective: str = "multiclass"
    num_class: int = 5
    metric: str = "multi_logloss"


@dataclass
class RegimeModelConfig:
    """Regime classification model configuration."""

    # Regimes
    regimes: list[str] = field(default_factory=lambda: [
        "bull", "bear", "sideways", "crisis"
    ])

    # HMM parameters
    n_components: int = 4  # Number of hidden states
    n_iter: int = 100
    covariance_type: str = "full"

    # Random Forest ensemble
    rf_n_estimators: int = 200
    rf_max_depth: int = 8

    # Lookback for feature calculation
    lookback_days: int = 252  # 1 year


@dataclass
class EarningsModelConfig:
    """Earnings prediction model configuration."""

    # XGBoost parameters
    n_estimators: int = 300
    max_depth: int = 6
    learning_rate: float = 0.05
    min_child_weight: int = 20
    subsample: float = 0.8
    colsample_bytree: float = 0.8

    # Threshold for beat/miss classification
    surprise_threshold: float = 0.0  # 0% = any positive surprise

    # Number of historical quarters to use
    history_quarters: int = 8


@dataclass
class FactorTimingConfig:
    """Factor timing model configuration."""

    # Factors to time
    factors: list[str] = field(default_factory=lambda: [
        "value", "momentum", "quality", "growth",
    ])

    # LightGBM parameters
    n_estimators: int = 300
    max_depth: int = 4
    learning_rate: float = 0.05

    # Target: next month factor spread
    forward_days: int = 21


@dataclass
class WalkForwardConfig:
    """Walk-forward validation configuration."""

    train_start: date = field(default_factory=lambda: date(2010, 1, 1))
    initial_train_years: int = 5
    test_months: int = 1
    retrain_months: int = 3
    min_train_samples: int = 1000
    purge_days: int = 5  # Gap between train and test to avoid leakage


@dataclass
class MonitoringConfig:
    """Model monitoring configuration."""

    # IC thresholds
    ic_good: float = 0.05
    ic_acceptable: float = 0.03
    ic_degraded: float = 0.02
    ic_alert_months: int = 3  # Alert after N months below threshold

    # Feature drift
    psi_threshold: float = 0.25  # Population Stability Index
    psi_check_features: int = 20  # Top N features to monitor

    # Regime model
    regime_accuracy_target: float = 0.70
    earnings_accuracy_target: float = 0.60

    # Retraining schedule
    retrain_interval_days: int = 90  # Retrain every 3 months
    max_model_age_days: int = 180  # Force retrain after 6 months


@dataclass
class HybridScoringConfig:
    """Score blending configuration."""

    # Blend weight for ML score (0 = rules only, 1 = ML only)
    ml_weight: float = 0.30

    # Minimum ML model performance to use ML scores
    min_ic_for_ml: float = 0.02

    # Fallback to rules if ML degrades
    fallback_to_rules: bool = True


@dataclass
class MLConfig:
    """Master ML configuration."""

    features: FeatureConfig = field(default_factory=FeatureConfig)
    ranking: RankingModelConfig = field(default_factory=RankingModelConfig)
    regime: RegimeModelConfig = field(default_factory=RegimeModelConfig)
    earnings: EarningsModelConfig = field(default_factory=EarningsModelConfig)
    factor_timing: FactorTimingConfig = field(default_factory=FactorTimingConfig)
    walk_forward: WalkForwardConfig = field(default_factory=WalkForwardConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    hybrid_scoring: HybridScoringConfig = field(default_factory=HybridScoringConfig)

    # Storage paths
    model_dir: str = "models"
    experiment_name: str = "axion_ml"


DEFAULT_ML_CONFIG = MLConfig()
