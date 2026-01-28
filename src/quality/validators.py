"""Data quality validation rules for price and fundamental data."""

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of a single validation check."""

    passed: bool
    check_name: str
    severity: str  # info, warning, error, critical
    message: str
    details: Optional[dict] = None


class PriceValidator:
    """Validate OHLCV price data quality."""

    def validate_ohlcv(self, df: pd.DataFrame, ticker: str) -> list[ValidationResult]:
        """Run all price validation checks on a DataFrame.

        Expects columns: open, high, low, close (at minimum).
        """
        results = []

        if df.empty:
            results.append(ValidationResult(
                passed=False, check_name="non_empty",
                severity="error", message=f"{ticker}: Empty price DataFrame",
            ))
            return results

        # Check for zero or negative close prices
        if "close" in df.columns:
            bad_prices = df[df["close"] <= 0]
            results.append(ValidationResult(
                passed=len(bad_prices) == 0,
                check_name="positive_prices",
                severity="critical",
                message=f"{ticker}: {len(bad_prices)} bars with zero/negative close",
            ))

        # Check OHLC consistency: low <= open,close <= high
        if all(c in df.columns for c in ["open", "high", "low", "close"]):
            invalid = df[
                (df["low"] > df["open"]) | (df["low"] > df["close"])
                | (df["high"] < df["open"]) | (df["high"] < df["close"])
            ]
            results.append(ValidationResult(
                passed=len(invalid) == 0,
                check_name="ohlc_consistency",
                severity="error",
                message=f"{ticker}: {len(invalid)} bars with invalid OHLC relationship",
            ))

        # Check for extreme daily moves (>50%)
        if "close" in df.columns and len(df) > 1:
            returns = df["close"].pct_change().abs()
            extreme = returns[returns > 0.5]
            results.append(ValidationResult(
                passed=len(extreme) == 0,
                check_name="extreme_moves",
                severity="warning",
                message=f"{ticker}: {len(extreme)} days with >50% move",
                details={"dates": [str(d) for d in extreme.index]} if len(extreme) > 0 else None,
            ))

        # Check for volume anomalies (>10x average)
        if "volume" in df.columns and len(df) > 20:
            avg_vol = df["volume"].rolling(20).mean()
            spikes = df["volume"] > (avg_vol * 10)
            spike_count = spikes.sum()
            results.append(ValidationResult(
                passed=spike_count < 5,
                check_name="volume_anomaly",
                severity="info",
                message=f"{ticker}: {spike_count} days with volume >10x 20d average",
            ))

        # Check for stale data (same close for 5+ days)
        if "close" in df.columns and len(df) > 5:
            stale = (df["close"].diff() == 0).rolling(5).sum()
            stale_count = (stale >= 5).sum()
            results.append(ValidationResult(
                passed=stale_count == 0,
                check_name="stale_prices",
                severity="warning",
                message=f"{ticker}: {stale_count} periods with 5+ identical closes",
            ))

        return results


class FundamentalValidator:
    """Validate fundamental data quality."""

    def validate(self, df: pd.DataFrame) -> list[ValidationResult]:
        """Run all fundamental validation checks."""
        results = []

        if df.empty:
            results.append(ValidationResult(
                passed=False, check_name="non_empty",
                severity="error", message="Empty fundamentals DataFrame",
            ))
            return results

        # Check for negative market caps
        if "marketCap" in df.columns:
            neg = df[df["marketCap"] < 0]
            results.append(ValidationResult(
                passed=len(neg) == 0,
                check_name="positive_market_cap",
                severity="error",
                message=f"{len(neg)} tickers with negative market cap",
            ))

        # Check data completeness per field
        null_pct = df.isnull().mean()
        high_null = null_pct[null_pct > 0.5]
        results.append(ValidationResult(
            passed=len(high_null) == 0,
            check_name="data_completeness",
            severity="warning",
            message=f"{len(high_null)} fields with >50% null values",
            details={"fields": high_null.to_dict()} if len(high_null) > 0 else None,
        ))

        # Check PE ratio sanity (should be positive or NaN, <1000)
        if "trailingPE" in df.columns:
            insane_pe = df[(df["trailingPE"] < 0) | (df["trailingPE"] > 1000)]
            results.append(ValidationResult(
                passed=len(insane_pe) < df.shape[0] * 0.1,
                check_name="pe_sanity",
                severity="info",
                message=f"{len(insane_pe)} tickers with PE <0 or >1000",
            ))

        # Check overall ticker coverage
        total = len(df)
        results.append(ValidationResult(
            passed=total >= 400,
            check_name="universe_coverage",
            severity="warning" if total < 400 else "info",
            message=f"Fundamentals available for {total} tickers",
        ))

        return results
