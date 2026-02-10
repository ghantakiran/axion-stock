"""PRD-175: Performance metrics — pure functions for financial calculations.

Sharpe ratio, Sortino ratio, Calmar ratio, and max drawdown.
All functions operate on lists of P&L values (not returns).
"""

from __future__ import annotations

import math


def sharpe_ratio(
    pnls: list[float],
    risk_free_rate: float = 0.05,
    periods_per_year: int = 252,
) -> float:
    """Compute annualized Sharpe ratio from a P&L series.

    Args:
        pnls: List of per-trade or per-period P&L values.
        risk_free_rate: Annualized risk-free rate.
        periods_per_year: Trading periods per year.

    Returns:
        Annualized Sharpe ratio (0.0 if insufficient data).
    """
    if len(pnls) < 2:
        return 0.0
    mean = sum(pnls) / len(pnls)
    variance = sum((p - mean) ** 2 for p in pnls) / len(pnls)
    std = math.sqrt(variance)
    if std < 1e-10:
        return 0.0
    daily_rf = risk_free_rate / periods_per_year
    return ((mean - daily_rf) / std) * math.sqrt(periods_per_year)


def sortino_ratio(
    pnls: list[float],
    risk_free_rate: float = 0.05,
    periods_per_year: int = 252,
) -> float:
    """Compute annualized Sortino ratio (downside deviation only).

    Args:
        pnls: P&L series.
        risk_free_rate: Annualized risk-free rate.
        periods_per_year: Periods per year.

    Returns:
        Annualized Sortino ratio (0.0 if insufficient data).
    """
    if len(pnls) < 2:
        return 0.0
    mean = sum(pnls) / len(pnls)
    downside = [p for p in pnls if p < 0]
    if not downside:
        return 0.0 if mean <= 0 else 10.0  # Capped positive
    downside_var = sum(p ** 2 for p in downside) / len(pnls)
    downside_std = math.sqrt(downside_var)
    if downside_std < 1e-10:
        return 0.0
    daily_rf = risk_free_rate / periods_per_year
    return ((mean - daily_rf) / downside_std) * math.sqrt(periods_per_year)


def calmar_ratio(
    pnls: list[float],
    periods_per_year: int = 252,
) -> float:
    """Compute Calmar ratio (annualized return / max drawdown).

    Args:
        pnls: P&L series.
        periods_per_year: Periods per year for annualization.

    Returns:
        Calmar ratio (0.0 if no drawdown or insufficient data).
    """
    if len(pnls) < 2:
        return 0.0
    total_return = sum(pnls)
    dd = max_drawdown(pnls)
    if dd < 1e-10:
        return 0.0
    annualized_factor = periods_per_year / max(len(pnls), 1)
    annualized_return = total_return * annualized_factor
    return annualized_return / dd


def max_drawdown(pnls: list[float]) -> float:
    """Compute maximum drawdown from a P&L series.

    Tracks cumulative equity and finds the largest peak-to-trough decline.

    Args:
        pnls: P&L series.

    Returns:
        Maximum drawdown as a positive dollar amount (0.0 if none).
    """
    if not pnls:
        return 0.0
    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0
    for p in pnls:
        cumulative += p
        if cumulative > peak:
            peak = cumulative
        dd = peak - cumulative
        if dd > max_dd:
            max_dd = dd
    return max_dd
