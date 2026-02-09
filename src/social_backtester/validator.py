"""Outcome Validation for Social Signals.

Validates whether social signals correctly predicted price direction
and magnitude across multiple horizons.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SignalOutcome:
    """Outcome measurement for a single archived signal."""

    signal_id: str = ""
    ticker: str = ""
    direction: str = "neutral"
    score: float = 0.0
    price_at_signal: float = 0.0
    return_1d: float = 0.0
    return_5d: float = 0.0
    return_10d: float = 0.0
    return_30d: float = 0.0
    direction_correct_1d: bool = False
    direction_correct_5d: bool = False
    direction_correct_30d: bool = False

    def to_dict(self) -> dict:
        return {
            "signal_id": self.signal_id,
            "ticker": self.ticker,
            "direction": self.direction,
            "score": round(self.score, 2),
            "price_at_signal": round(self.price_at_signal, 4),
            "return_1d": round(self.return_1d, 6),
            "return_5d": round(self.return_5d, 6),
            "return_10d": round(self.return_10d, 6),
            "return_30d": round(self.return_30d, 6),
            "direction_correct_1d": self.direction_correct_1d,
            "direction_correct_5d": self.direction_correct_5d,
            "direction_correct_30d": self.direction_correct_30d,
        }


@dataclass
class ValidationReport:
    """Aggregated signal validation results."""

    total_signals: int = 0
    outcomes: list[SignalOutcome] = field(default_factory=list)
    hit_rates: dict = field(default_factory=dict)  # horizon -> rate
    avg_return_by_direction: dict = field(default_factory=dict)
    high_score_hit_rate: float = 0.0
    low_score_hit_rate: float = 0.0
    per_ticker_rates: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "total_signals": self.total_signals,
            "hit_rates": {k: round(v, 4) for k, v in self.hit_rates.items()},
            "avg_return_by_direction": {
                k: round(v, 6) for k, v in self.avg_return_by_direction.items()
            },
            "high_score_hit_rate": round(self.high_score_hit_rate, 4),
            "low_score_hit_rate": round(self.low_score_hit_rate, 4),
            "per_ticker_rates": {
                k: round(v, 4) for k, v in self.per_ticker_rates.items()
            },
            "outcome_count": len(self.outcomes),
        }

    def to_dataframe(self):
        import pandas as pd

        if not self.outcomes:
            return pd.DataFrame()
        return pd.DataFrame([o.to_dict() for o in self.outcomes])


class OutcomeValidator:
    """Validates social signal predictiveness against price data.

    For each archived signal, looks up the ticker's price at signal time,
    computes forward returns at standard horizons, and checks direction
    accuracy.
    """

    def __init__(self, config=None):
        self.config = config

    def validate(
        self,
        signals: list,
        price_data: dict,
    ) -> ValidationReport:
        """Validate signals against historical price data.

        Args:
            signals: List of ArchivedSignal objects.
            price_data: Dict mapping ticker -> DataFrame with 'close' column
                        and DatetimeIndex (or 'date' column).

        Returns:
            ValidationReport with hit rates and outcomes.
        """
        outcomes = []

        for sig in signals:
            prices = price_data.get(sig.ticker)
            if prices is None or len(prices) == 0:
                continue

            # Find signal date in price data
            signal_date = sig.signal_time.date() if hasattr(sig.signal_time, 'date') else sig.signal_time
            close_values = self._get_close_series(prices)
            if close_values is None:
                continue

            # Find the index closest to signal date
            idx = self._find_date_index(close_values, signal_date)
            if idx is None:
                continue

            price_at_signal = close_values[idx][1]  # (date, price) tuple

            # Compute forward returns
            ret_1d = self._forward_return(close_values, idx, 1)
            ret_5d = self._forward_return(close_values, idx, 5)
            ret_10d = self._forward_return(close_values, idx, 10)
            ret_30d = self._forward_return(close_values, idx, 30)

            # Direction correctness
            is_bullish = sig.direction == "bullish"
            is_bearish = sig.direction == "bearish"

            outcome = SignalOutcome(
                signal_id=sig.signal_id,
                ticker=sig.ticker,
                direction=sig.direction,
                score=sig.composite_score,
                price_at_signal=price_at_signal,
                return_1d=ret_1d,
                return_5d=ret_5d,
                return_10d=ret_10d,
                return_30d=ret_30d,
                direction_correct_1d=(
                    (is_bullish and ret_1d > 0) or (is_bearish and ret_1d < 0)
                ),
                direction_correct_5d=(
                    (is_bullish and ret_5d > 0) or (is_bearish and ret_5d < 0)
                ),
                direction_correct_30d=(
                    (is_bullish and ret_30d > 0) or (is_bearish and ret_30d < 0)
                ),
            )
            outcomes.append(outcome)

        return self._build_report(outcomes, signals)

    def _get_close_series(self, prices) -> Optional[list]:
        """Extract (date, close) pairs from DataFrame or dict."""
        try:
            if hasattr(prices, 'iterrows'):
                # DataFrame
                result = []
                for idx_val, row in prices.iterrows():
                    close = row.get('close', row.get('Close', None))
                    if close is not None:
                        date_val = idx_val if hasattr(idx_val, 'date') else row.get('date', idx_val)
                        result.append((date_val, float(close)))
                return result if result else None
            return None
        except Exception:
            return None

    def _find_date_index(self, close_values: list, signal_date) -> Optional[int]:
        """Find the index in close_values closest to signal_date."""
        for i, (d, _) in enumerate(close_values):
            d_date = d.date() if hasattr(d, 'date') else d
            if d_date >= signal_date:
                return i
        # If signal_date is after all data, use last
        return len(close_values) - 1 if close_values else None

    def _forward_return(self, close_values: list, idx: int, days: int) -> float:
        """Compute forward return from idx to idx + days."""
        future_idx = idx + days
        if future_idx >= len(close_values):
            future_idx = len(close_values) - 1
        if idx >= len(close_values):
            return 0.0
        base_price = close_values[idx][1]
        future_price = close_values[future_idx][1]
        if base_price == 0:
            return 0.0
        return (future_price - base_price) / base_price

    def _build_report(self, outcomes: list[SignalOutcome], signals: list) -> ValidationReport:
        """Build aggregated report from outcomes."""
        report = ValidationReport(
            total_signals=len(signals),
            outcomes=outcomes,
        )

        if not outcomes:
            return report

        n = len(outcomes)

        # Hit rates by horizon
        correct_1d = sum(1 for o in outcomes if o.direction_correct_1d)
        correct_5d = sum(1 for o in outcomes if o.direction_correct_5d)
        correct_30d = sum(1 for o in outcomes if o.direction_correct_30d)
        report.hit_rates = {
            "1d": correct_1d / n,
            "5d": correct_5d / n,
            "30d": correct_30d / n,
        }

        # Average return by direction
        by_dir: dict[str, list[float]] = {}
        for o in outcomes:
            by_dir.setdefault(o.direction, []).append(o.return_5d)
        report.avg_return_by_direction = {
            d: sum(rets) / len(rets) for d, rets in by_dir.items() if rets
        }

        # High vs low score hit rates (5d horizon)
        high_score = [o for o in outcomes if o.score >= 50.0]
        low_score = [o for o in outcomes if o.score < 50.0]
        if high_score:
            report.high_score_hit_rate = (
                sum(1 for o in high_score if o.direction_correct_5d) / len(high_score)
            )
        if low_score:
            report.low_score_hit_rate = (
                sum(1 for o in low_score if o.direction_correct_5d) / len(low_score)
            )

        # Per-ticker hit rates (5d)
        by_ticker: dict[str, list[bool]] = {}
        for o in outcomes:
            by_ticker.setdefault(o.ticker, []).append(o.direction_correct_5d)
        report.per_ticker_rates = {
            t: sum(hits) / len(hits) for t, hits in by_ticker.items() if hits
        }

        return report
