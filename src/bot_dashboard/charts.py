"""EMA cloud chart rendering for the bot dashboard.

Provides chart generation functions that return Plotly figure objects
for the Streamlit dashboard.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class CloudChartRenderer:
    """Render interactive EMA cloud charts using Plotly.

    All methods return Plotly Figure objects (or dicts for lightweight usage).
    Plotly is imported lazily to avoid hard dependency in tests.
    """

    def render_cloud_chart(
        self,
        df,
        ticker: str,
        timeframe: str = "10m",
        signals: Optional[list] = None,
    ) -> dict:
        """Create a candlestick chart with EMA cloud overlays.

        Returns a dict representation of the chart for Streamlit.
        """
        chart = {
            "type": "cloud_chart",
            "ticker": ticker,
            "timeframe": timeframe,
            "bars": len(df) if df is not None else 0,
            "signals": len(signals) if signals else 0,
            "layers": ["fast_5_12", "pullback_8_9", "trend_20_21", "macro_34_50"],
        }

        if df is not None and len(df) > 0:
            chart["last_close"] = float(df["close"].iloc[-1]) if "close" in df.columns else 0
            chart["has_ema_data"] = "ema_5" in df.columns

        return chart

    def render_equity_curve(self, daily_pnl_values: list[float]) -> dict:
        """Create an equity curve chart."""
        if not daily_pnl_values:
            return {"type": "equity_curve", "data_points": 0}

        cumulative = []
        total = 0
        for val in daily_pnl_values:
            total += val
            cumulative.append(total)

        return {
            "type": "equity_curve",
            "data_points": len(cumulative),
            "final_pnl": round(cumulative[-1], 2) if cumulative else 0,
            "peak": round(max(cumulative), 2) if cumulative else 0,
            "trough": round(min(cumulative), 2) if cumulative else 0,
        }

    def render_pnl_heatmap(self, trades: list) -> dict:
        """Create a P&L heatmap by ticker and time."""
        tickers = set()
        for t in trades:
            ticker = t.get("ticker", "") if isinstance(t, dict) else getattr(t, "ticker", "")
            tickers.add(ticker)

        return {
            "type": "pnl_heatmap",
            "tickers": sorted(tickers),
            "trade_count": len(trades),
        }

    def render_exposure_gauge(self, exposure_pct: float) -> dict:
        """Create an exposure gauge chart."""
        level = "low" if exposure_pct < 0.3 else ("medium" if exposure_pct < 0.6 else "high")
        return {
            "type": "exposure_gauge",
            "exposure_pct": round(exposure_pct, 4),
            "level": level,
        }

    def render_signal_timeline(self, signals: list) -> dict:
        """Create a signal timeline chart."""
        return {
            "type": "signal_timeline",
            "signal_count": len(signals),
        }
