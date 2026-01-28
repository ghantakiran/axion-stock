"""Factor scoring: value, momentum, quality, growth → composite score.

This module provides both v1 (4-factor) and v2 (6-factor with regime detection)
scoring. The v2 engine is used when AXION_FACTOR_ENGINE_V2=true.
"""

import numpy as np
import pandas as pd

import config


def _use_factor_engine_v2() -> bool:
    """Check if Factor Engine v2 is enabled."""
    try:
        return config.FACTOR_ENGINE_V2
    except AttributeError:
        return False


def _percentile_rank(series: pd.Series) -> pd.Series:
    """Rank values as percentiles in [0, 1]. NaN → 0.5 (median)."""
    ranked = series.rank(pct=True)
    return ranked.fillna(0.5)


def _invert_rank(series: pd.Series) -> pd.Series:
    """Lower raw values → higher score (for PE, PB, etc.)."""
    return 1.0 - _percentile_rank(series)


def compute_value_scores(fundamentals: pd.DataFrame) -> pd.Series:
    """Value factor: low PE, low PB, low EV/EBITDA, high dividend yield."""
    pe_score = _invert_rank(fundamentals.get("trailingPE", pd.Series(dtype=float)))
    pb_score = _invert_rank(fundamentals.get("priceToBook", pd.Series(dtype=float)))
    ev_score = _invert_rank(fundamentals.get("enterpriseToEbitda", pd.Series(dtype=float)))
    div_score = _percentile_rank(fundamentals.get("dividendYield", pd.Series(dtype=float)))

    value = 0.30 * pe_score + 0.25 * pb_score + 0.25 * ev_score + 0.20 * div_score
    value = value.reindex(fundamentals.index).fillna(0.5)
    return value


def compute_momentum_scores(returns: pd.DataFrame) -> pd.Series:
    """Momentum factor: 6m and 12m returns (last month skipped in data_fetcher)."""
    ret_6m = _percentile_rank(returns.get("ret_6m", pd.Series(dtype=float)))
    ret_12m = _percentile_rank(returns.get("ret_12m", pd.Series(dtype=float)))

    momentum = 0.50 * ret_6m + 0.50 * ret_12m
    momentum = momentum.reindex(returns.index).fillna(0.5)
    return momentum


def compute_quality_scores(fundamentals: pd.DataFrame) -> pd.Series:
    """Quality factor: high ROE, low debt/equity."""
    roe_score = _percentile_rank(fundamentals.get("returnOnEquity", pd.Series(dtype=float)))
    de_score = _invert_rank(fundamentals.get("debtToEquity", pd.Series(dtype=float)))

    quality = 0.60 * roe_score + 0.40 * de_score
    quality = quality.reindex(fundamentals.index).fillna(0.5)
    return quality


def compute_growth_scores(fundamentals: pd.DataFrame) -> pd.Series:
    """Growth factor: revenue growth + earnings growth."""
    rev_score = _percentile_rank(fundamentals.get("revenueGrowth", pd.Series(dtype=float)))
    earn_score = _percentile_rank(fundamentals.get("earningsGrowth", pd.Series(dtype=float)))

    growth = 0.50 * rev_score + 0.50 * earn_score
    growth = growth.reindex(fundamentals.index).fillna(0.5)
    return growth


def compute_composite_scores(
    fundamentals: pd.DataFrame,
    returns: pd.DataFrame,
    verbose: bool = False,
    prices: pd.DataFrame = None,
) -> pd.DataFrame:
    """Compute all factor scores and weighted composite.

    When AXION_FACTOR_ENGINE_V2=true, uses the advanced 6-factor engine with
    regime detection and adaptive weights. Otherwise uses the classic 4-factor
    model with static weights.

    Args:
        fundamentals: DataFrame[tickers x fields] of fundamental data
        returns: DataFrame[tickers x {ret_6m, ret_12m}] of momentum returns
        verbose: Print scoring statistics
        prices: DataFrame[dates x tickers] of prices (optional, for v2 engine)

    Returns:
        DataFrame with columns: value, momentum, quality, growth, composite
        (v2 also includes: volatility, technical, regime)
    """
    # Try v2 engine if enabled
    if _use_factor_engine_v2():
        try:
            return _compute_scores_v2(fundamentals, returns, prices, verbose)
        except Exception as e:
            if verbose:
                print(f"  Factor Engine v2 failed, falling back to v1: {e}")
            # Fall through to v1

    # V1 implementation (original)
    return _compute_scores_v1(fundamentals, returns, verbose)


def _compute_scores_v1(
    fundamentals: pd.DataFrame, returns: pd.DataFrame, verbose: bool = False
) -> pd.DataFrame:
    """Original v1 factor scoring (4 factors, static weights)."""
    # Align indices
    all_tickers = fundamentals.index.union(returns.index)

    fund_aligned = fundamentals.reindex(all_tickers)
    ret_aligned = returns.reindex(all_tickers)

    value = compute_value_scores(fund_aligned)
    momentum = compute_momentum_scores(ret_aligned)
    quality = compute_quality_scores(fund_aligned)
    growth = compute_growth_scores(fund_aligned)

    composite = (
        config.FACTOR_WEIGHTS["value"] * value
        + config.FACTOR_WEIGHTS["momentum"] * momentum
        + config.FACTOR_WEIGHTS["quality"] * quality
        + config.FACTOR_WEIGHTS["growth"] * growth
    )

    scores = pd.DataFrame({
        "value": value,
        "momentum": momentum,
        "quality": quality,
        "growth": growth,
        "composite": composite,
    }, index=all_tickers)

    if verbose:
        print(f"  Scored {len(scores)} tickers (v1 engine)")
        print(f"  Composite: mean={scores['composite'].mean():.3f}, "
              f"std={scores['composite'].std():.3f}")

    return scores


def _compute_scores_v2(
    fundamentals: pd.DataFrame,
    returns: pd.DataFrame,
    prices: pd.DataFrame = None,
    verbose: bool = False,
) -> pd.DataFrame:
    """V2 factor scoring (6 factors, regime detection, adaptive weights).

    Returns DataFrame with v1-compatible columns plus v2 extras.
    """
    from src.factor_engine import FactorEngineV2

    # Create engine with settings
    engine = FactorEngineV2(
        use_adaptive_weights=config.FACTOR_ENGINE_ADAPTIVE_WEIGHTS,
        use_sector_relative=config.FACTOR_ENGINE_SECTOR_RELATIVE,
    )

    # Use empty prices DataFrame if not provided
    if prices is None:
        prices = pd.DataFrame()

    # Compute v2 scores
    scores = engine.compute_all_scores(prices, fundamentals, returns)

    if verbose:
        regime = engine.last_regime
        weights = engine.last_weights
        print(f"  Scored {len(scores)} tickers (v2 engine)")
        print(f"  Regime: {regime.value if regime else 'unknown'}")
        print(f"  Composite: mean={scores['composite'].mean():.3f}, "
              f"std={scores['composite'].std():.3f}")
        if weights:
            weight_str = ", ".join(f"{k}={v:.0%}" for k, v in weights.items())
            print(f"  Weights: {weight_str}")

    return scores
