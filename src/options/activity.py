"""Unusual Options Activity Detection.

Detects unusual volume, open interest, IV spikes, large blocks,
sweep orders, and put/call skew in options flow data.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

from src.options.config import ActivityConfig

logger = logging.getLogger(__name__)


class SignalType:
    VOLUME_SPIKE = "VOLUME_SPIKE"
    OI_SURGE = "OI_SURGE"
    IV_SPIKE = "IV_SPIKE"
    LARGE_BLOCK = "LARGE_BLOCK"
    SWEEP = "SWEEP"
    PUT_CALL_SKEW = "PUT_CALL_SKEW"
    NEAR_EXPIRY = "NEAR_EXPIRY"


@dataclass
class ActivitySignal:
    """Single unusual activity signal."""

    symbol: str = ""
    signal_type: str = ""
    option_type: str = ""
    strike: float = 0.0
    expiry: str = ""
    volume: int = 0
    open_interest: int = 0
    premium_total: float = 0.0
    iv: float = 0.0
    description: str = ""
    severity: str = "medium"  # low, medium, high
    timestamp: str = ""

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "signal_type": self.signal_type,
            "option_type": self.option_type,
            "strike": self.strike,
            "expiry": self.expiry,
            "volume": self.volume,
            "open_interest": self.open_interest,
            "premium_total": self.premium_total,
            "iv": self.iv,
            "description": self.description,
            "severity": self.severity,
            "timestamp": self.timestamp,
        }


@dataclass
class ActivitySummary:
    """Summary of unusual activity for a symbol."""

    symbol: str = ""
    total_signals: int = 0
    signal_types: list = field(default_factory=list)
    net_sentiment: str = "neutral"  # bullish, bearish, neutral
    total_premium: float = 0.0
    call_premium: float = 0.0
    put_premium: float = 0.0
    signals: list = field(default_factory=list)


class UnusualActivityDetector:
    """Detect unusual options activity patterns.

    Scans options flow data for volume spikes, OI surges,
    IV spikes, large blocks, sweeps, and put/call skew.

    Example:
        detector = UnusualActivityDetector()
        signals = detector.scan(flow_data, historical_data)
    """

    def __init__(self, config: Optional[ActivityConfig] = None):
        self.config = config or ActivityConfig()

    def scan(
        self,
        flow_data: pd.DataFrame,
        historical_stats: Optional[pd.DataFrame] = None,
    ) -> list[ActivitySignal]:
        """Scan for unusual activity signals.

        Args:
            flow_data: Current options flow with columns:
                symbol, option_type, strike, expiry, volume, oi,
                premium, iv, dte, avg_volume, avg_oi, iv_rank.
            historical_stats: Historical averages for comparison.

        Returns:
            List of ActivitySignal detected.
        """
        signals = []

        if flow_data.empty:
            return signals

        # Merge historical stats if provided separately
        df = flow_data.copy()
        if historical_stats is not None:
            merge_cols = [c for c in ["symbol", "strike", "expiry"] if c in historical_stats.columns]
            if merge_cols:
                df = df.merge(historical_stats, on=merge_cols, how="left", suffixes=("", "_hist"))

        for _, row in df.iterrows():
            row_signals = self._check_row(row)
            signals.extend(row_signals)

        # Sort by severity then premium
        severity_order = {"high": 0, "medium": 1, "low": 2}
        signals.sort(key=lambda s: (severity_order.get(s.severity, 2), -s.premium_total))

        return signals

    def scan_put_call_ratio(
        self,
        flow_data: pd.DataFrame,
    ) -> list[ActivitySignal]:
        """Detect unusual put/call ratios at the symbol level.

        Args:
            flow_data: Options flow data.

        Returns:
            List of put/call skew signals.
        """
        signals = []

        if "symbol" not in flow_data.columns:
            return signals

        for symbol, group in flow_data.groupby("symbol"):
            calls = group[group["option_type"] == "call"]
            puts = group[group["option_type"] == "put"]

            call_vol = calls["volume"].sum() if not calls.empty else 0
            put_vol = puts["volume"].sum() if not puts.empty else 0

            if call_vol == 0 and put_vol == 0:
                continue

            if call_vol > 0:
                pc_ratio = put_vol / call_vol
            else:
                pc_ratio = float("inf")

            if pc_ratio > self.config.put_call_ratio_high:
                signals.append(ActivitySignal(
                    symbol=str(symbol),
                    signal_type=SignalType.PUT_CALL_SKEW,
                    option_type="put",
                    volume=int(put_vol),
                    description=f"P/C ratio {pc_ratio:.1f}x - heavy put activity",
                    severity="high",
                    timestamp=datetime.now().isoformat(),
                ))
            elif pc_ratio < self.config.put_call_ratio_low:
                signals.append(ActivitySignal(
                    symbol=str(symbol),
                    signal_type=SignalType.PUT_CALL_SKEW,
                    option_type="call",
                    volume=int(call_vol),
                    description=f"P/C ratio {pc_ratio:.2f}x - heavy call activity",
                    severity="medium",
                    timestamp=datetime.now().isoformat(),
                ))

        return signals

    def summarize(
        self,
        signals: list[ActivitySignal],
    ) -> dict[str, ActivitySummary]:
        """Summarize signals by symbol.

        Args:
            signals: List of activity signals.

        Returns:
            Dict of symbol -> ActivitySummary.
        """
        summaries: dict[str, ActivitySummary] = {}

        for signal in signals:
            if signal.symbol not in summaries:
                summaries[signal.symbol] = ActivitySummary(symbol=signal.symbol)

            summary = summaries[signal.symbol]
            summary.total_signals += 1
            if signal.signal_type not in summary.signal_types:
                summary.signal_types.append(signal.signal_type)
            summary.total_premium += signal.premium_total
            summary.signals.append(signal)

            if signal.option_type == "call":
                summary.call_premium += signal.premium_total
            elif signal.option_type == "put":
                summary.put_premium += signal.premium_total

        # Determine sentiment
        for summary in summaries.values():
            if summary.call_premium > summary.put_premium * 1.5:
                summary.net_sentiment = "bullish"
            elif summary.put_premium > summary.call_premium * 1.5:
                summary.net_sentiment = "bearish"
            else:
                summary.net_sentiment = "neutral"

        return summaries

    def _check_row(self, row: pd.Series) -> list[ActivitySignal]:
        """Check a single flow row for signals."""
        signals = []
        symbol = str(row.get("symbol", ""))
        timestamp = datetime.now().isoformat()

        base = dict(
            symbol=symbol,
            option_type=str(row.get("option_type", "")),
            strike=float(row.get("strike", 0)),
            expiry=str(row.get("expiry", "")),
            volume=int(row.get("volume", 0)),
            open_interest=int(row.get("oi", 0)),
            premium_total=float(row.get("premium", 0)),
            iv=float(row.get("iv", 0)),
            timestamp=timestamp,
        )

        # Volume spike
        avg_vol = row.get("avg_volume", 0)
        vol = row.get("volume", 0)
        if avg_vol > 0 and vol > avg_vol * self.config.volume_spike_multiplier:
            signals.append(ActivitySignal(
                **base,
                signal_type=SignalType.VOLUME_SPIKE,
                description=f"Volume {vol:,} is {vol/avg_vol:.1f}x average",
                severity="high" if vol > avg_vol * 10 else "medium",
            ))

        # OI surge
        avg_oi = row.get("avg_oi", 0)
        oi = row.get("oi", 0)
        if avg_oi > 0 and oi > avg_oi * self.config.oi_surge_multiplier:
            signals.append(ActivitySignal(
                **base,
                signal_type=SignalType.OI_SURGE,
                description=f"OI {oi:,} is {oi/avg_oi:.1f}x average",
                severity="medium",
            ))

        # IV spike
        iv_rank = row.get("iv_rank", 0)
        if iv_rank > self.config.iv_rank_threshold:
            signals.append(ActivitySignal(
                **base,
                signal_type=SignalType.IV_SPIKE,
                description=f"IV rank {iv_rank:.0%} - elevated implied vol",
                severity="medium",
            ))

        # Large block
        if vol >= self.config.large_block_threshold:
            signals.append(ActivitySignal(
                **base,
                signal_type=SignalType.LARGE_BLOCK,
                description=f"Large block: {vol:,} contracts",
                severity="high",
            ))

        # Near-expiry volume
        dte = row.get("dte", 999)
        if (dte <= self.config.near_expiry_max_dte
                and avg_vol > 0
                and vol > avg_vol * self.config.near_expiry_volume_multiplier):
            signals.append(ActivitySignal(
                **base,
                signal_type=SignalType.NEAR_EXPIRY,
                description=f"Near-expiry ({dte}d) volume {vol:,} is {vol/avg_vol:.1f}x avg",
                severity="high",
            ))

        return signals
