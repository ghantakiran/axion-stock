"""Correlation Analysis for Social Signals.

Computes Pearson correlation between signal scores and forward returns
at various lag periods to determine optimal signal timing.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CorrelationResult:
    """Correlation measurement for a specific ticker and lag."""

    ticker: str = ""
    lag_days: int = 0
    correlation: float = 0.0
    p_value: float = 1.0
    sample_size: int = 0
    is_significant: bool = False

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "lag_days": self.lag_days,
            "correlation": round(self.correlation, 4),
            "p_value": round(self.p_value, 6),
            "sample_size": self.sample_size,
            "is_significant": self.is_significant,
        }


@dataclass
class LagAnalysis:
    """Lag analysis across multiple lag periods for a ticker."""

    ticker: str = ""
    results: list[CorrelationResult] = field(default_factory=list)
    optimal_lag: int = 0
    optimal_correlation: float = 0.0

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "results": [r.to_dict() for r in self.results],
            "optimal_lag": self.optimal_lag,
            "optimal_correlation": round(self.optimal_correlation, 4),
        }

    def to_dataframe(self):
        import pandas as pd

        if not self.results:
            return pd.DataFrame()
        return pd.DataFrame([r.to_dict() for r in self.results])


class CorrelationAnalyzer:
    """Analyzes correlation between social signal scores and forward returns.

    For each ticker, computes Pearson correlation at multiple lag periods
    to find the optimal time delay between signal and price reaction.
    """

    DEFAULT_LAGS = [0, 1, 2, 5, 10]

    def __init__(self, config=None):
        self.config = config
        sig_level = 0.05
        if config and hasattr(config, 'significance_level'):
            sig_level = config.significance_level
        self._significance_level = sig_level

    def analyze(
        self,
        signals: list,
        prices: dict,
        ticker: str,
        lags: Optional[list[int]] = None,
    ) -> LagAnalysis:
        """Analyze score-return correlation for a single ticker.

        Args:
            signals: List of ArchivedSignal objects.
            prices: Dict mapping ticker -> DataFrame with 'close' column.
            ticker: Ticker to analyze.
            lags: Lag periods in days (default: [0, 1, 2, 5, 10]).

        Returns:
            LagAnalysis with correlation at each lag.
        """
        lags = lags or self.DEFAULT_LAGS
        ticker_signals = [s for s in signals if s.ticker == ticker]
        price_df = prices.get(ticker)

        if not ticker_signals or price_df is None:
            return LagAnalysis(ticker=ticker)

        close_values = self._extract_closes(price_df)
        if not close_values:
            return LagAnalysis(ticker=ticker)

        results = []
        best_abs_corr = 0.0
        best_lag = 0
        best_corr = 0.0

        for lag in lags:
            scores = []
            returns = []

            for sig in ticker_signals:
                sig_date = sig.signal_time.date() if hasattr(sig.signal_time, 'date') else sig.signal_time
                idx = self._find_date_index(close_values, sig_date)
                if idx is None:
                    continue

                future_idx = idx + lag
                if future_idx >= len(close_values):
                    continue

                base_price = close_values[idx][1]
                future_price = close_values[future_idx][1]
                if base_price == 0:
                    continue

                fwd_return = (future_price - base_price) / base_price
                scores.append(sig.composite_score)
                returns.append(fwd_return)

            if len(scores) < 3:
                results.append(CorrelationResult(
                    ticker=ticker, lag_days=lag,
                    sample_size=len(scores),
                ))
                continue

            corr = self._pearson_correlation(scores, returns)
            p_val = self._p_value(corr, len(scores))
            is_sig = p_val < self._significance_level

            result = CorrelationResult(
                ticker=ticker,
                lag_days=lag,
                correlation=corr,
                p_value=p_val,
                sample_size=len(scores),
                is_significant=is_sig,
            )
            results.append(result)

            if abs(corr) > best_abs_corr:
                best_abs_corr = abs(corr)
                best_lag = lag
                best_corr = corr

        return LagAnalysis(
            ticker=ticker,
            results=results,
            optimal_lag=best_lag,
            optimal_correlation=best_corr,
        )

    def analyze_universe(
        self,
        signals: list,
        prices: dict,
        tickers: Optional[list[str]] = None,
    ) -> dict[str, LagAnalysis]:
        """Analyze correlations across multiple tickers."""
        if tickers is None:
            tickers = sorted(set(s.ticker for s in signals))

        return {
            ticker: self.analyze(signals, prices, ticker)
            for ticker in tickers
        }

    def _extract_closes(self, prices) -> Optional[list]:
        """Extract (date, close) pairs from DataFrame."""
        try:
            if hasattr(prices, 'iterrows'):
                result = []
                for idx_val, row in prices.iterrows():
                    close = row.get('close', row.get('Close', None))
                    if close is not None:
                        result.append((idx_val, float(close)))
                return result if result else None
            return None
        except Exception:
            return None

    def _find_date_index(self, close_values: list, signal_date) -> Optional[int]:
        """Find the index closest to signal_date."""
        for i, (d, _) in enumerate(close_values):
            d_date = d.date() if hasattr(d, 'date') else d
            if d_date >= signal_date:
                return i
        return len(close_values) - 1 if close_values else None

    @staticmethod
    def _pearson_correlation(x: list[float], y: list[float]) -> float:
        """Compute Pearson correlation coefficient."""
        n = len(x)
        if n < 2:
            return 0.0
        mean_x = sum(x) / n
        mean_y = sum(y) / n
        cov = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
        var_x = sum((xi - mean_x) ** 2 for xi in x)
        var_y = sum((yi - mean_y) ** 2 for yi in y)
        denom = math.sqrt(var_x * var_y)
        if denom == 0:
            return 0.0
        return cov / denom

    @staticmethod
    def _p_value(r: float, n: int) -> float:
        """Approximate p-value for Pearson r using t-distribution."""
        if n < 3 or abs(r) >= 1.0:
            return 1.0 if abs(r) < 1.0 else 0.0
        t_stat = r * math.sqrt((n - 2) / (1 - r * r))
        # Approximate two-tailed p-value using normal approximation for large n
        # For small n this is an approximation
        df = n - 2
        # Use simple approximation: p ≈ 2 * (1 - Φ(|t|))
        # where Φ is normal CDF approximated
        abs_t = abs(t_stat)
        if abs_t > 6:
            return 0.0001
        # Abramowitz & Stegun approximation
        b = 1.0 / (1.0 + 0.2316419 * abs_t)
        poly = b * (0.319381530 + b * (-0.356563782 + b * (1.781477937
               + b * (-1.821255978 + b * 1.330274429))))
        phi = (1.0 / math.sqrt(2 * math.pi)) * math.exp(-0.5 * abs_t * abs_t)
        p_one_tail = phi * poly
        return max(0.0, min(1.0, 2 * p_one_tail))
