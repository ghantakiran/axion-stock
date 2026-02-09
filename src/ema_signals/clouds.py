"""EMA Cloud computation engine.

Implements the Ripster EMA Cloud methodology with 4 cloud layers:
- Fast (5/12): Fluid trendline for day trades
- Pullback (8/9): Pullback support/resistance levels
- Trend (20/21): Intermediate trend confirmation
- Macro (34/50): Major trend bias and risk boundary
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class CloudConfig:
    """Configuration for EMA cloud layer periods."""

    fast_short: int = 5
    fast_long: int = 12
    pullback_short: int = 8
    pullback_long: int = 9
    trend_short: int = 20
    trend_long: int = 21
    macro_short: int = 34
    macro_long: int = 50

    def get_pairs(self) -> list[tuple[str, int, int]]:
        """Return (cloud_name, short_period, long_period) tuples."""
        return [
            ("fast", self.fast_short, self.fast_long),
            ("pullback", self.pullback_short, self.pullback_long),
            ("trend", self.trend_short, self.trend_long),
            ("macro", self.macro_short, self.macro_long),
        ]

    @property
    def max_period(self) -> int:
        """Minimum bars required for all EMAs to be valid."""
        return self.macro_long


@dataclass
class CloudState:
    """State of a single EMA cloud at a point in time."""

    cloud_name: str
    short_ema: float
    long_ema: float
    is_bullish: bool
    thickness: float
    price_above: bool
    price_inside: bool
    price_below: bool

    def to_dict(self) -> dict:
        return {
            "cloud_name": self.cloud_name,
            "short_ema": round(self.short_ema, 4),
            "long_ema": round(self.long_ema, 4),
            "is_bullish": self.is_bullish,
            "thickness": round(self.thickness, 6),
            "price_above": self.price_above,
            "price_inside": self.price_inside,
            "price_below": self.price_below,
        }


@dataclass
class EMASignalConfig:
    """Master configuration for the EMA signal engine."""

    cloud_config: CloudConfig = field(default_factory=CloudConfig)

    # Scanning
    scan_interval_seconds: int = 30
    max_tickers_per_scan: int = 80
    min_daily_volume: float = 5_000_000
    unusual_volume_threshold: float = 2.0
    earnings_exclusion_days: int = 2

    # Conviction thresholds
    min_conviction_to_signal: int = 25
    min_conviction_to_execute: int = 50
    high_conviction_threshold: int = 75

    # Timeframes
    active_timeframes: list[str] = field(
        default_factory=lambda: ["1m", "5m", "10m", "1h", "1d"]
    )

    # Market hours
    pre_market_scan: bool = True
    after_hours_scan: bool = False

    # Data source priority
    data_source: str = "polygon"


class EMACloudCalculator:
    """Compute EMA clouds from OHLCV data.

    Uses pandas ewm() for vectorized EMA computation across
    all 4 cloud layers (fast, pullback, trend, macro).
    """

    def __init__(self, config: Optional[CloudConfig] = None):
        self.config = config or CloudConfig()

    def compute_clouds(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add EMA cloud columns to a DataFrame with OHLCV data.

        Expects columns: open, high, low, close, volume.
        Adds columns:
        - ema_{period} for each EMA period (8 columns)
        - cloud_{name}_bull boolean for each cloud layer (4 columns)
        """
        result = df.copy()
        close = result["close"]

        for cloud_name, short_p, long_p in self.config.get_pairs():
            short_col = f"ema_{short_p}"
            long_col = f"ema_{long_p}"

            if short_col not in result.columns:
                result[short_col] = close.ewm(span=short_p, adjust=False).mean()
            if long_col not in result.columns:
                result[long_col] = close.ewm(span=long_p, adjust=False).mean()

            result[f"cloud_{cloud_name}_bull"] = result[short_col] > result[long_col]

        return result

    def get_cloud_states(self, df: pd.DataFrame) -> list[CloudState]:
        """Return current CloudState for all 4 layers from the latest bar.

        The DataFrame must already have EMA columns computed via compute_clouds().
        """
        if df.empty:
            return []

        cloud_df = df if f"ema_{self.config.fast_short}" in df.columns else self.compute_clouds(df)
        last = cloud_df.iloc[-1]
        price = float(last["close"])
        states: list[CloudState] = []

        for cloud_name, short_p, long_p in self.config.get_pairs():
            short_val = float(last[f"ema_{short_p}"])
            long_val = float(last[f"ema_{long_p}"])
            upper = max(short_val, long_val)
            lower = min(short_val, long_val)

            thickness = abs(short_val - long_val) / price if price > 0 else 0.0

            states.append(
                CloudState(
                    cloud_name=cloud_name,
                    short_ema=short_val,
                    long_ema=long_val,
                    is_bullish=short_val > long_val,
                    thickness=thickness,
                    price_above=price > upper,
                    price_inside=lower <= price <= upper,
                    price_below=price < lower,
                )
            )

        return states

    def get_all_cloud_states(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute per-bar cloud state booleans for the entire DataFrame.

        Returns DataFrame with columns:
        - price_above_{cloud}, price_inside_{cloud}, price_below_{cloud}
        for each cloud layer.
        """
        cloud_df = df if f"ema_{self.config.fast_short}" in df.columns else self.compute_clouds(df)
        result = cloud_df.copy()

        for cloud_name, short_p, long_p in self.config.get_pairs():
            short_col = f"ema_{short_p}"
            long_col = f"ema_{long_p}"
            upper = result[[short_col, long_col]].max(axis=1)
            lower = result[[short_col, long_col]].min(axis=1)

            result[f"price_above_{cloud_name}"] = result["close"] > upper
            result[f"price_inside_{cloud_name}"] = (
                (result["close"] >= lower) & (result["close"] <= upper)
            )
            result[f"price_below_{cloud_name}"] = result["close"] < lower

        return result

    def cloud_thickness(self, df: pd.DataFrame, cloud_name: str) -> pd.Series:
        """Return cloud thickness as percentage of price for a specific cloud layer."""
        cloud_df = df if f"ema_{self.config.fast_short}" in df.columns else self.compute_clouds(df)
        pair = {name: (s, l) for name, s, l in self.config.get_pairs()}
        if cloud_name not in pair:
            raise ValueError(f"Unknown cloud: {cloud_name}. Valid: {list(pair)}")

        short_p, long_p = pair[cloud_name]
        short_col = f"ema_{short_p}"
        long_col = f"ema_{long_p}"
        return (cloud_df[short_col] - cloud_df[long_col]).abs() / cloud_df["close"]
