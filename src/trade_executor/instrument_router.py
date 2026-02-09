"""Instrument routing for trade signals.

Routes EMA cloud signals to the correct instrument based on user-selected mode:
Options, Leveraged ETFs, or Both.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Literal, Optional

from src.ema_signals.detector import TradeSignal
from src.trade_executor.executor import ExecutorConfig, InstrumentMode

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# Leveraged ETF Catalog
# ═══════════════════════════════════════════════════════════════════════

LEVERAGED_ETF_CATALOG: dict[str, dict] = {
    # Broad Market — NASDAQ-100
    "TQQQ": {"tracks": "NASDAQ-100", "leverage": 3.0, "direction": "bull", "inverse": False},
    "SQQQ": {"tracks": "NASDAQ-100", "leverage": 3.0, "direction": "bear", "inverse": True},
    "QLD": {"tracks": "NASDAQ-100", "leverage": 2.0, "direction": "bull", "inverse": False},
    "QID": {"tracks": "NASDAQ-100", "leverage": 2.0, "direction": "bear", "inverse": True},
    # Broad Market — S&P 500
    "SPXL": {"tracks": "S&P 500", "leverage": 3.0, "direction": "bull", "inverse": False},
    "SPXS": {"tracks": "S&P 500", "leverage": 3.0, "direction": "bear", "inverse": True},
    "SSO": {"tracks": "S&P 500", "leverage": 2.0, "direction": "bull", "inverse": False},
    "SDS": {"tracks": "S&P 500", "leverage": 2.0, "direction": "bear", "inverse": True},
    # Semiconductors
    "SOXL": {"tracks": "Semiconductors", "leverage": 3.0, "direction": "bull", "inverse": False},
    "SOXS": {"tracks": "Semiconductors", "leverage": 3.0, "direction": "bear", "inverse": True},
    # Technology
    "TECL": {"tracks": "Technology", "leverage": 3.0, "direction": "bull", "inverse": False},
    "TECS": {"tracks": "Technology", "leverage": 3.0, "direction": "bear", "inverse": True},
    # Financials
    "FAS": {"tracks": "Financials", "leverage": 3.0, "direction": "bull", "inverse": False},
    "FAZ": {"tracks": "Financials", "leverage": 3.0, "direction": "bear", "inverse": True},
    # Energy
    "ERX": {"tracks": "Energy", "leverage": 2.0, "direction": "bull", "inverse": False},
    "ERY": {"tracks": "Energy", "leverage": 2.0, "direction": "bear", "inverse": True},
    # Small Caps
    "TNA": {"tracks": "Russell 2000", "leverage": 3.0, "direction": "bull", "inverse": False},
    "TZA": {"tracks": "Russell 2000", "leverage": 3.0, "direction": "bear", "inverse": True},
    # Biotech
    "LABU": {"tracks": "Biotech", "leverage": 3.0, "direction": "bull", "inverse": False},
    "LABD": {"tracks": "Biotech", "leverage": 3.0, "direction": "bear", "inverse": True},
}

# Ticker → sector mapping for ETF selection
TICKER_SECTOR_MAP: dict[str, str] = {
    # Indexes
    "QQQ": "NASDAQ-100", "SPY": "S&P 500", "IWM": "Russell 2000",
    # Tech / Semi
    "AAPL": "Technology", "MSFT": "Technology", "GOOGL": "Technology",
    "NVDA": "Semiconductors", "AMD": "Semiconductors", "AVGO": "Semiconductors",
    "INTC": "Semiconductors", "MU": "Semiconductors", "QCOM": "Semiconductors",
    "META": "Technology", "AMZN": "Technology", "NFLX": "Technology",
    "CRM": "Technology", "ADBE": "Technology", "ORCL": "Technology",
    # Financials
    "JPM": "Financials", "BAC": "Financials", "GS": "Financials",
    "MS": "Financials", "C": "Financials", "WFC": "Financials",
    # Energy
    "XOM": "Energy", "CVX": "Energy", "COP": "Energy", "SLB": "Energy",
    # Biotech
    "MRNA": "Biotech", "BIIB": "Biotech", "GILD": "Biotech",
    "AMGN": "Biotech", "REGN": "Biotech",
}


# ═══════════════════════════════════════════════════════════════════════
# Data Models
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class ETFSelection:
    """Selected leveraged ETF for a signal."""

    ticker: str
    leverage: float
    tracks: str
    is_inverse: bool
    avg_daily_volume: float = 0.0

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "leverage": self.leverage,
            "tracks": self.tracks,
            "is_inverse": self.is_inverse,
        }


@dataclass
class InstrumentDecision:
    """Result of instrument routing."""

    instrument_type: Literal["stock", "option", "leveraged_etf"]
    ticker: str
    original_signal_ticker: str
    leverage: float = 1.0
    is_inverse: bool = False
    etf_metadata: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "instrument_type": self.instrument_type,
            "ticker": self.ticker,
            "original_signal_ticker": self.original_signal_ticker,
            "leverage": self.leverage,
            "is_inverse": self.is_inverse,
        }


# ═══════════════════════════════════════════════════════════════════════
# Instrument Router
# ═══════════════════════════════════════════════════════════════════════


class InstrumentRouter:
    """Route EMA cloud signals to the appropriate instrument.

    The user selects their instrument mode via the dashboard.
    This router translates directional signals into the correct
    tradeable instrument.
    """

    def __init__(
        self,
        mode: InstrumentMode = InstrumentMode.BOTH,
        config: Optional[ExecutorConfig] = None,
    ):
        self.mode = mode
        self.config = config or ExecutorConfig()
        self.catalog = LEVERAGED_ETF_CATALOG

    def route(self, signal: TradeSignal, trade_type: str = "day") -> InstrumentDecision:
        """Determine which instrument to trade for a given signal.

        Logic:
        - OPTIONS mode: scalp signals -> options, day/swing -> stocks
        - LEVERAGED_ETF mode: all signals -> leveraged ETFs
        - BOTH mode: scalp -> options, day -> leveraged ETFs, swing -> stocks
        """
        if self.mode == InstrumentMode.OPTIONS:
            if trade_type == "scalp":
                return InstrumentDecision(
                    instrument_type="option",
                    ticker=signal.ticker,
                    original_signal_ticker=signal.ticker,
                )
            return InstrumentDecision(
                instrument_type="stock",
                ticker=signal.ticker,
                original_signal_ticker=signal.ticker,
            )

        if self.mode == InstrumentMode.LEVERAGED_ETF:
            etf = self.select_etf(signal)
            if etf:
                return InstrumentDecision(
                    instrument_type="leveraged_etf",
                    ticker=etf.ticker,
                    original_signal_ticker=signal.ticker,
                    leverage=etf.leverage,
                    is_inverse=etf.is_inverse,
                    etf_metadata=self.catalog.get(etf.ticker),
                )
            return InstrumentDecision(
                instrument_type="stock",
                ticker=signal.ticker,
                original_signal_ticker=signal.ticker,
            )

        # BOTH mode
        if trade_type == "scalp":
            return InstrumentDecision(
                instrument_type="option",
                ticker=signal.ticker,
                original_signal_ticker=signal.ticker,
            )
        if trade_type == "day":
            etf = self.select_etf(signal)
            if etf:
                return InstrumentDecision(
                    instrument_type="leveraged_etf",
                    ticker=etf.ticker,
                    original_signal_ticker=signal.ticker,
                    leverage=etf.leverage,
                    is_inverse=etf.is_inverse,
                    etf_metadata=self.catalog.get(etf.ticker),
                )
        return InstrumentDecision(
            instrument_type="stock",
            ticker=signal.ticker,
            original_signal_ticker=signal.ticker,
        )

    def select_etf(self, signal: TradeSignal) -> Optional[ETFSelection]:
        """Pick the best leveraged ETF for a signal.

        Selection logic:
        1. Map signal ticker to its sector/index
        2. Find matching ETF pair (bull/bear)
        3. Bull signal -> bull ETF, bear signal -> inverse ETF
        4. Prefer 3x for day trades (configurable)
        """
        sector = TICKER_SECTOR_MAP.get(signal.ticker)
        if not sector:
            # Default to NASDAQ-100 for unknown tickers
            sector = "NASDAQ-100"

        is_bull = signal.direction == "long"
        target_direction = "bull" if is_bull else "bear"

        # Find matching ETFs for this sector and direction
        candidates = [
            (ticker, meta) for ticker, meta in self.catalog.items()
            if meta["tracks"] == sector and meta["direction"] == target_direction
        ]

        if not candidates:
            return None

        # Prefer 3x for day trades if configured
        if self.config.prefer_3x_for_day_trades:
            three_x = [(t, m) for t, m in candidates if m["leverage"] == 3.0]
            if three_x:
                candidates = three_x

        # Pick first match (highest leverage)
        candidates.sort(key=lambda x: x[1]["leverage"], reverse=True)
        ticker, meta = candidates[0]

        return ETFSelection(
            ticker=ticker,
            leverage=meta["leverage"],
            tracks=meta["tracks"],
            is_inverse=meta["inverse"],
        )

    def get_available_etfs(self, sector: Optional[str] = None) -> list[dict]:
        """Return available ETFs, optionally filtered by sector."""
        result = []
        for ticker, meta in self.catalog.items():
            if sector and meta["tracks"] != sector:
                continue
            result.append({"ticker": ticker, **meta})
        return result
