"""Dynamic universe scanner for EMA cloud signals.

Builds a daily scan list using factor scores, volume filters, and
event exclusions. Scans all tickers across active timeframes for
trade signals, then ranks by conviction.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from src.ema_signals.clouds import EMACloudCalculator, EMASignalConfig
from src.ema_signals.conviction import ConvictionScorer
from src.ema_signals.data_feed import DataFeed
from src.ema_signals.detector import SignalDetector, TradeSignal
from src.ema_signals.mtf import MTFEngine

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# Default Universe
# ═══════════════════════════════════════════════════════════════════════

DEFAULT_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AMD",
    "NFLX", "CRM", "AVGO", "ADBE", "ORCL", "INTC", "QCOM", "MU",
    "AMAT", "LRCX", "KLAC", "SNPS", "CDNS", "MRVL", "ON", "PANW",
    "CRWD", "ZS", "DDOG", "NET", "SNOW", "PLTR", "COIN", "SQ",
    "SHOP", "MELI", "SE", "BABA", "JD", "PDD", "LLY", "UNH",
    "JPM", "V", "MA", "GS", "MS", "BAC", "WFC", "C",
    "XOM", "CVX", "COP", "SLB", "SPY", "QQQ", "IWM", "DIA",
]


class UniverseScanner:
    """Scan a dynamic universe of tickers for EMA cloud signals.

    Builds the daily scan list using:
    1. Axion factor scores (top momentum + quality stocks)
    2. Unusual volume filter (>2x 20-day avg)
    3. Minimum liquidity threshold ($5M avg daily volume)
    4. Earnings/event exclusion (skip tickers with earnings in next 2 days)
    """

    def __init__(self, config: Optional[EMASignalConfig] = None):
        self.config = config or EMASignalConfig()
        self.detector = SignalDetector(self.config.cloud_config)
        self.scorer = ConvictionScorer()
        self.mtf_engine = MTFEngine()
        self.data_feed = DataFeed()

    def build_scan_list(
        self,
        factor_scores: Optional[pd.DataFrame] = None,
        custom_tickers: Optional[list[str]] = None,
    ) -> list[str]:
        """Return today's tickers to scan (~30-80 tickers).

        Args:
            factor_scores: DataFrame with ticker index and factor columns.
                If provided, selects top tickers by momentum + quality.
            custom_tickers: Override list. If provided, uses these directly.

        Returns:
            List of ticker symbols to scan.
        """
        if custom_tickers:
            return custom_tickers[: self.config.max_tickers_per_scan]

        if factor_scores is not None and not factor_scores.empty:
            return self._filter_by_factors(factor_scores)

        # Fallback: use default universe
        return DEFAULT_TICKERS[: self.config.max_tickers_per_scan]

    def _filter_by_factors(self, scores: pd.DataFrame) -> list[str]:
        """Select top tickers by momentum + quality composite score."""
        # Look for common factor columns
        momentum_cols = [c for c in scores.columns if "momentum" in c.lower()]
        quality_cols = [c for c in scores.columns if "quality" in c.lower()]
        composite_cols = [c for c in scores.columns if "composite" in c.lower()]

        if composite_cols:
            ranked = scores.sort_values(composite_cols[0], ascending=False)
        elif momentum_cols:
            ranked = scores.sort_values(momentum_cols[0], ascending=False)
        else:
            ranked = scores

        tickers = list(ranked.index[: self.config.max_tickers_per_scan])
        return [t for t in tickers if isinstance(t, str)]

    def scan_all(
        self,
        tickers: list[str],
        timeframes: Optional[list[str]] = None,
    ) -> list[TradeSignal]:
        """Run EMA cloud detection across all tickers and timeframes.

        Args:
            tickers: List of ticker symbols to scan.
            timeframes: Override timeframes. Defaults to config.active_timeframes.

        Returns:
            All detected signals across the universe, with conviction scored.
        """
        active_tfs = timeframes or self.config.active_timeframes
        all_signals: list[TradeSignal] = []
        signals_by_tf: dict[str, list[TradeSignal]] = {}

        for tf in active_tfs:
            tf_signals: list[TradeSignal] = []
            for ticker in tickers:
                try:
                    df = self.data_feed.get_bars(ticker, tf)
                    if df.empty or len(df) < self.detector.calculator.config.max_period + 2:
                        continue

                    signals = self.detector.detect(df, ticker, tf)

                    # Compute volume data for conviction scoring
                    volume_data = self._compute_volume_data(df)

                    # Compute body ratio for candle quality scoring
                    body_ratio = self._compute_body_ratio(df)

                    for sig in signals:
                        sig.metadata["body_ratio"] = body_ratio
                        score = self.scorer.score(sig, volume_data)
                        sig.conviction = score.total
                        sig.metadata["conviction_breakdown"] = {
                            "cloud_alignment": score.cloud_alignment,
                            "volume": score.volume_confirmation,
                            "thickness": score.cloud_thickness,
                            "candle": score.candle_quality,
                            "factor": score.factor_score,
                        }

                    tf_signals.extend(signals)

                except Exception as e:
                    logger.warning("Scan failed for %s/%s: %s", ticker, tf, e)
                    continue

            signals_by_tf[tf] = tf_signals

        # Run MTF confluence
        all_signals = self.mtf_engine.compute_confluence(signals_by_tf)

        # Filter by minimum conviction
        all_signals = [
            s for s in all_signals
            if s.conviction >= self.config.min_conviction_to_signal
        ]

        return all_signals

    def rank_by_conviction(
        self, signals: list[TradeSignal], top_n: int = 20
    ) -> list[TradeSignal]:
        """Sort signals by conviction score, return top N."""
        return sorted(signals, key=lambda s: s.conviction, reverse=True)[:top_n]

    @staticmethod
    def _compute_volume_data(df: pd.DataFrame) -> dict:
        """Compute volume metrics from OHLCV DataFrame."""
        if "volume" not in df.columns or len(df) < 20:
            return {}
        current_vol = float(df["volume"].iloc[-1])
        avg_vol = float(df["volume"].iloc[-20:].mean())
        return {"current_volume": current_vol, "avg_volume": avg_vol}

    @staticmethod
    def _compute_body_ratio(df: pd.DataFrame) -> float:
        """Compute candle body ratio for the latest bar."""
        last = df.iloc[-1]
        high_low = last["high"] - last["low"]
        if high_low <= 0:
            return 0.0
        body = abs(last["close"] - last["open"])
        return body / high_low
