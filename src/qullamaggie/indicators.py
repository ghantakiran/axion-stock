"""Qullamaggie shared technical indicator helpers.

Pure-Python implementations with no external dependencies beyond the
standard library. Used by all three strategy modules and the scanner.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ConsolidationResult:
    """Result of consolidation detection.

    Attributes:
        detected: Whether a valid consolidation was found.
        start_idx: Bar index where consolidation begins.
        end_idx: Bar index where consolidation ends.
        duration: Number of bars in consolidation.
        high: Highest price during consolidation.
        low: Lowest price during consolidation.
        range_pct: (high - low) / low * 100.
        volume_ratio: Average volume in consolidation / prior avg volume.
        has_higher_lows: Whether higher lows pattern was detected.
    """

    detected: bool = False
    start_idx: int = 0
    end_idx: int = 0
    duration: int = 0
    high: float = 0.0
    low: float = 0.0
    range_pct: float = 0.0
    volume_ratio: float = 1.0
    has_higher_lows: bool = False


def compute_adr(highs: list[float], lows: list[float], period: int = 20) -> float:
    """Compute Average Daily Range as a percentage.

    ADR% = mean((high - low) / low * 100) over the last *period* bars.

    Args:
        highs: High prices.
        lows: Low prices.
        period: Lookback window.

    Returns:
        ADR percentage. 0.0 if insufficient data.
    """
    if len(highs) < period or len(lows) < period:
        return 0.0
    ranges = []
    for h, l in zip(highs[-period:], lows[-period:]):
        if l > 0:
            ranges.append((h - l) / l * 100)
    return sum(ranges) / max(len(ranges), 1)


def compute_atr(
    highs: list[float], lows: list[float], closes: list[float], period: int = 14
) -> float:
    """Compute Average True Range.

    Uses Wilder's smoothing (simple average of true ranges).

    Args:
        highs: High prices.
        lows: Low prices.
        closes: Close prices.
        period: ATR period.

    Returns:
        ATR value. 0.0 if insufficient data.
    """
    n = min(len(highs), len(lows), len(closes))
    if n < period + 1:
        return 0.0
    true_ranges = []
    for i in range(1, n):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        true_ranges.append(tr)
    if len(true_ranges) < period:
        return 0.0
    return sum(true_ranges[-period:]) / period


def compute_sma(values: list[float], period: int) -> list[float]:
    """Compute Simple Moving Average series.

    Args:
        values: Price series.
        period: SMA period.

    Returns:
        List of SMA values (length = len(values) - period + 1).
        Empty list if insufficient data.
    """
    if len(values) < period:
        return []
    result = []
    for i in range(period - 1, len(values)):
        window = values[i - period + 1: i + 1]
        result.append(sum(window) / period)
    return result


def compute_ema(values: list[float], period: int) -> list[float]:
    """Compute Exponential Moving Average series.

    Args:
        values: Price series.
        period: EMA period.

    Returns:
        List of EMA values (same length as input).
        Empty list if insufficient data.
    """
    if len(values) < period:
        return []
    mult = 2 / (period + 1)
    # Seed with SMA of first *period* values
    ema = [sum(values[:period]) / period]
    for v in values[period:]:
        ema.append(v * mult + ema[-1] * (1 - mult))
    # Pad front with None-equivalent (repeat first EMA)
    result = [ema[0]] * (period - 1) + ema
    return result[: len(values)]


def compute_rsi(closes: list[float], period: int = 14) -> float:
    """Compute Relative Strength Index.

    Args:
        closes: Close prices.
        period: RSI period.

    Returns:
        RSI value (0-100). 50.0 if insufficient data.
    """
    if len(closes) < period + 1:
        return 50.0
    changes = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    recent = changes[-period:]
    gains = [c for c in recent if c > 0]
    losses = [-c for c in recent if c < 0]
    avg_gain = sum(gains) / period if gains else 0.0
    avg_loss = sum(losses) / period if losses else 0.0
    if avg_loss < 1e-10:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def compute_adx(
    highs: list[float], lows: list[float], closes: list[float], period: int = 14
) -> float:
    """Compute Average Directional Index.

    Simplified Wilder's ADX using simple averages for DI+/DI-/DX.

    Args:
        highs: High prices.
        lows: Low prices.
        closes: Close prices.
        period: ADX period.

    Returns:
        ADX value (0-100). 0.0 if insufficient data.
    """
    n = min(len(highs), len(lows), len(closes))
    if n < period + 1:
        return 0.0

    plus_dm_list = []
    minus_dm_list = []
    tr_list = []

    for i in range(1, n):
        up_move = highs[i] - highs[i - 1]
        down_move = lows[i - 1] - lows[i]
        plus_dm = up_move if (up_move > down_move and up_move > 0) else 0.0
        minus_dm = down_move if (down_move > up_move and down_move > 0) else 0.0
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        plus_dm_list.append(plus_dm)
        minus_dm_list.append(minus_dm)
        tr_list.append(tr)

    if len(tr_list) < period:
        return 0.0

    # Use last *period* bars for smoothed averages
    recent_tr = tr_list[-period:]
    recent_plus = plus_dm_list[-period:]
    recent_minus = minus_dm_list[-period:]

    avg_tr = sum(recent_tr) / period
    avg_plus = sum(recent_plus) / period
    avg_minus = sum(recent_minus) / period

    if avg_tr < 1e-10:
        return 0.0

    plus_di = (avg_plus / avg_tr) * 100
    minus_di = (avg_minus / avg_tr) * 100
    di_sum = plus_di + minus_di
    if di_sum < 1e-10:
        return 0.0

    dx = abs(plus_di - minus_di) / di_sum * 100
    return dx


def compute_vwap(
    highs: list[float], lows: list[float], closes: list[float], volumes: list[float]
) -> float:
    """Compute Volume-Weighted Average Price.

    Args:
        highs: High prices.
        lows: Low prices.
        closes: Close prices.
        volumes: Volume data.

    Returns:
        VWAP value. 0.0 if no volume.
    """
    total_vp = 0.0
    total_v = 0.0
    for h, l, c, v in zip(highs, lows, closes, volumes):
        typical = (h + l + c) / 3
        total_vp += typical * v
        total_v += v
    return total_vp / max(total_v, 1.0)


def detect_consolidation(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    config,
) -> Optional[ConsolidationResult]:
    """Detect a consolidation/flag pattern in recent price data.

    Looks for a period of low-range, volume-contracting price action
    following a prior move. Validates higher-lows and tightening range.

    Args:
        highs: High prices.
        lows: Low prices.
        closes: Close prices.
        config: BreakoutConfig with consolidation parameters.

    Returns:
        ConsolidationResult if found, None otherwise.
    """
    n = len(closes)
    min_bars = getattr(config, "consolidation_min_bars", 10)
    max_bars = getattr(config, "consolidation_max_bars", 60)
    pullback_max = getattr(config, "pullback_max_pct", 25.0)

    if n < min_bars + 5:
        return None

    # Find the highest high in the prior move zone
    search_end = n - min_bars
    if search_end <= 0:
        return None

    peak_idx = 0
    peak_val = highs[0]
    for i in range(search_end):
        if highs[i] > peak_val:
            peak_val = highs[i]
            peak_idx = i

    # Consolidation starts after the peak
    cons_start = peak_idx + 1
    if cons_start >= n:
        return None

    cons_end = n - 1
    duration = cons_end - cons_start + 1

    if duration < min_bars or duration > max_bars:
        return None

    # Range check
    cons_highs = highs[cons_start: cons_end + 1]
    cons_lows = lows[cons_start: cons_end + 1]
    cons_high = max(cons_highs) if cons_highs else 0
    cons_low = min(cons_lows) if cons_lows else 0

    if cons_low <= 0:
        return None

    range_pct = (cons_high - cons_low) / cons_low * 100
    pullback_from_peak = (peak_val - cons_low) / peak_val * 100 if peak_val > 0 else 0

    if pullback_from_peak > pullback_max:
        return None

    has_hl = detect_higher_lows(cons_lows, len(cons_lows))

    return ConsolidationResult(
        detected=True,
        start_idx=cons_start,
        end_idx=cons_end,
        duration=duration,
        high=cons_high,
        low=cons_low,
        range_pct=range_pct,
        volume_ratio=1.0,  # Caller can override with actual volume data
        has_higher_lows=has_hl,
    )


def detect_higher_lows(lows: list[float], lookback: int) -> bool:
    """Check if a series has a pattern of higher lows.

    Requires at least 3 swing lows where each successive low
    is higher than the previous.

    Args:
        lows: Low prices.
        lookback: How many bars to examine.

    Returns:
        True if higher-lows pattern is detected.
    """
    recent = lows[-lookback:] if lookback <= len(lows) else lows
    if len(recent) < 3:
        return False

    # Find local minima (simple: lower than both neighbors)
    swing_lows = []
    for i in range(1, len(recent) - 1):
        if recent[i] <= recent[i - 1] and recent[i] <= recent[i + 1]:
            swing_lows.append(recent[i])

    if len(swing_lows) < 2:
        return False

    # Check if swing lows are ascending
    for i in range(1, len(swing_lows)):
        if swing_lows[i] <= swing_lows[i - 1]:
            return False
    return True


def volume_contraction(volumes: list[float], lookback: int = 20) -> float:
    """Compute volume contraction ratio.

    Ratio = recent average volume / longer-term average volume.
    Values < 1.0 indicate volume is contracting (drying up).

    Args:
        volumes: Volume series.
        lookback: Longer-term lookback for average.

    Returns:
        Contraction ratio. 1.0 if insufficient data.
    """
    if len(volumes) < lookback:
        return 1.0
    long_avg = sum(volumes[-lookback:]) / lookback
    # Recent = last 5 bars
    short_period = min(5, lookback)
    short_avg = sum(volumes[-short_period:]) / short_period
    if long_avg < 1e-10:
        return 1.0
    return short_avg / long_avg
