"""Factor scoring: value, momentum, quality, growth → composite score."""

import numpy as np
import pandas as pd

import config


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
    fundamentals: pd.DataFrame, returns: pd.DataFrame, verbose: bool = False
) -> pd.DataFrame:
    """Compute all factor scores and weighted composite.

    Returns DataFrame with columns: value, momentum, quality, growth, composite.
    """
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
        print(f"  Scored {len(scores)} tickers")
        print(f"  Composite: mean={scores['composite'].mean():.3f}, "
              f"std={scores['composite'].std():.3f}")

    return scores
