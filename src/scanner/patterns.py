"""Pattern Detection.

Detect chart patterns and candlestick formations.
"""

from datetime import datetime, timezone
from typing import Optional
import logging

from src.scanner.config import PatternType, CandlePattern, SignalStrength
from src.scanner.models import ChartPattern, CandlestickPattern

logger = logging.getLogger(__name__)


class PatternDetector:
    """Detects chart and candlestick patterns.
    
    Identifies technical patterns that may indicate
    potential trading opportunities.
    
    Example:
        detector = PatternDetector()
        
        # Detect candlestick patterns
        candle_patterns = detector.detect_candlesticks(ohlc_data)
        
        # Detect chart patterns
        chart_patterns = detector.detect_chart_patterns(ohlc_data)
    """
    
    def __init__(self):
        self._detected_patterns: list[ChartPattern] = []
        self._detected_candles: list[CandlestickPattern] = []
    
    # =========================================================================
    # Candlestick Patterns
    # =========================================================================
    
    def detect_candlesticks(
        self,
        symbol: str,
        ohlc: list[dict],  # [{open, high, low, close, date}, ...]
    ) -> list[CandlestickPattern]:
        """Detect candlestick patterns.
        
        Args:
            symbol: Stock symbol.
            ohlc: OHLC data (most recent last).
            
        Returns:
            List of detected CandlestickPattern.
        """
        if len(ohlc) < 3:
            return []
        
        patterns = []
        
        # Check latest candle
        latest = ohlc[-1]
        prev = ohlc[-2]
        prev2 = ohlc[-3] if len(ohlc) >= 3 else None
        
        # Doji
        if self._is_doji(latest):
            patterns.append(CandlestickPattern(
                symbol=symbol,
                pattern_type=CandlePattern.DOJI,
                pattern_date=latest.get("date"),
                is_bullish=True,  # Neutral
                price=latest["close"],
                confidence=self._calculate_doji_confidence(latest),
                description="Doji - indecision candle",
            ))
        
        # Hammer (bullish reversal at bottom)
        if self._is_hammer(latest, ohlc):
            patterns.append(CandlestickPattern(
                symbol=symbol,
                pattern_type=CandlePattern.HAMMER,
                pattern_date=latest.get("date"),
                is_bullish=True,
                price=latest["close"],
                confidence=75,
                description="Hammer - potential bullish reversal",
            ))
        
        # Shooting Star (bearish reversal at top)
        if self._is_shooting_star(latest, ohlc):
            patterns.append(CandlestickPattern(
                symbol=symbol,
                pattern_type=CandlePattern.SHOOTING_STAR,
                pattern_date=latest.get("date"),
                is_bullish=False,
                price=latest["close"],
                confidence=75,
                description="Shooting Star - potential bearish reversal",
            ))
        
        # Bullish Engulfing
        if self._is_bullish_engulfing(latest, prev):
            patterns.append(CandlestickPattern(
                symbol=symbol,
                pattern_type=CandlePattern.ENGULFING_BULL,
                pattern_date=latest.get("date"),
                is_bullish=True,
                price=latest["close"],
                confidence=80,
                description="Bullish Engulfing - strong reversal signal",
            ))
        
        # Bearish Engulfing
        if self._is_bearish_engulfing(latest, prev):
            patterns.append(CandlestickPattern(
                symbol=symbol,
                pattern_type=CandlePattern.ENGULFING_BEAR,
                pattern_date=latest.get("date"),
                is_bullish=False,
                price=latest["close"],
                confidence=80,
                description="Bearish Engulfing - strong reversal signal",
            ))
        
        # Morning Star (3-candle bullish reversal)
        if prev2 and self._is_morning_star(prev2, prev, latest):
            patterns.append(CandlestickPattern(
                symbol=symbol,
                pattern_type=CandlePattern.MORNING_STAR,
                pattern_date=latest.get("date"),
                is_bullish=True,
                price=latest["close"],
                confidence=85,
                description="Morning Star - strong bullish reversal",
            ))
        
        # Evening Star (3-candle bearish reversal)
        if prev2 and self._is_evening_star(prev2, prev, latest):
            patterns.append(CandlestickPattern(
                symbol=symbol,
                pattern_type=CandlePattern.EVENING_STAR,
                pattern_date=latest.get("date"),
                is_bullish=False,
                price=latest["close"],
                confidence=85,
                description="Evening Star - strong bearish reversal",
            ))
        
        self._detected_candles = patterns
        return patterns
    
    def _is_doji(self, candle: dict) -> bool:
        """Check if candle is a doji."""
        body = abs(candle["close"] - candle["open"])
        range_hl = candle["high"] - candle["low"]
        
        if range_hl == 0:
            return False
        
        body_pct = body / range_hl
        return body_pct < 0.1  # Body < 10% of range
    
    def _calculate_doji_confidence(self, candle: dict) -> float:
        """Calculate doji confidence."""
        body = abs(candle["close"] - candle["open"])
        range_hl = candle["high"] - candle["low"]
        
        if range_hl == 0:
            return 50
        
        body_pct = body / range_hl
        # More confident the smaller the body
        return min(95, 50 + (0.1 - body_pct) * 500)
    
    def _is_hammer(self, candle: dict, ohlc: list[dict]) -> bool:
        """Check if candle is a hammer (bullish reversal)."""
        body = abs(candle["close"] - candle["open"])
        lower_shadow = min(candle["open"], candle["close"]) - candle["low"]
        upper_shadow = candle["high"] - max(candle["open"], candle["close"])
        range_hl = candle["high"] - candle["low"]
        
        if range_hl == 0 or body == 0:
            return False
        
        # Hammer: long lower shadow, small upper shadow
        if lower_shadow >= body * 2 and upper_shadow <= body * 0.5:
            # Check if in downtrend (price below recent average)
            if len(ohlc) >= 5:
                avg = sum(c["close"] for c in ohlc[-5:]) / 5
                if candle["close"] < avg:
                    return True
        
        return False
    
    def _is_shooting_star(self, candle: dict, ohlc: list[dict]) -> bool:
        """Check if candle is a shooting star (bearish reversal)."""
        body = abs(candle["close"] - candle["open"])
        lower_shadow = min(candle["open"], candle["close"]) - candle["low"]
        upper_shadow = candle["high"] - max(candle["open"], candle["close"])
        
        if body == 0:
            return False
        
        # Shooting star: long upper shadow, small lower shadow
        if upper_shadow >= body * 2 and lower_shadow <= body * 0.5:
            # Check if in uptrend
            if len(ohlc) >= 5:
                avg = sum(c["close"] for c in ohlc[-5:]) / 5
                if candle["close"] > avg:
                    return True
        
        return False
    
    def _is_bullish_engulfing(self, current: dict, prev: dict) -> bool:
        """Check for bullish engulfing pattern."""
        # Previous candle is bearish
        prev_bearish = prev["close"] < prev["open"]
        # Current candle is bullish
        curr_bullish = current["close"] > current["open"]
        # Current body engulfs previous
        engulfs = (current["open"] <= prev["close"] and 
                   current["close"] >= prev["open"])
        
        return prev_bearish and curr_bullish and engulfs
    
    def _is_bearish_engulfing(self, current: dict, prev: dict) -> bool:
        """Check for bearish engulfing pattern."""
        # Previous candle is bullish
        prev_bullish = prev["close"] > prev["open"]
        # Current candle is bearish
        curr_bearish = current["close"] < current["open"]
        # Current body engulfs previous
        engulfs = (current["open"] >= prev["close"] and 
                   current["close"] <= prev["open"])
        
        return prev_bullish and curr_bearish and engulfs
    
    def _is_morning_star(self, first: dict, second: dict, third: dict) -> bool:
        """Check for morning star pattern."""
        # First: bearish candle
        first_bearish = first["close"] < first["open"]
        # Second: small body (doji-like)
        second_body = abs(second["close"] - second["open"])
        first_body = abs(first["close"] - first["open"])
        second_small = second_body < first_body * 0.3
        # Third: bullish candle closing above first's midpoint
        third_bullish = third["close"] > third["open"]
        first_mid = (first["open"] + first["close"]) / 2
        third_above_mid = third["close"] > first_mid
        
        return first_bearish and second_small and third_bullish and third_above_mid
    
    def _is_evening_star(self, first: dict, second: dict, third: dict) -> bool:
        """Check for evening star pattern."""
        # First: bullish candle
        first_bullish = first["close"] > first["open"]
        # Second: small body
        second_body = abs(second["close"] - second["open"])
        first_body = abs(first["close"] - first["open"])
        second_small = second_body < first_body * 0.3
        # Third: bearish candle closing below first's midpoint
        third_bearish = third["close"] < third["open"]
        first_mid = (first["open"] + first["close"]) / 2
        third_below_mid = third["close"] < first_mid
        
        return first_bullish and second_small and third_bearish and third_below_mid
    
    # =========================================================================
    # Chart Patterns (Simplified)
    # =========================================================================
    
    def detect_chart_patterns(
        self,
        symbol: str,
        ohlc: list[dict],
        min_bars: int = 20,
    ) -> list[ChartPattern]:
        """Detect chart patterns.
        
        Args:
            symbol: Stock symbol.
            ohlc: OHLC data (most recent last).
            min_bars: Minimum bars to analyze.
            
        Returns:
            List of detected ChartPattern.
        """
        if len(ohlc) < min_bars:
            return []
        
        patterns = []
        
        # Get highs and lows
        highs = [c["high"] for c in ohlc]
        lows = [c["low"] for c in ohlc]
        closes = [c["close"] for c in ohlc]
        
        # Simple double bottom detection
        double_bottom = self._detect_double_bottom(symbol, lows, closes)
        if double_bottom:
            patterns.append(double_bottom)
        
        # Simple double top detection
        double_top = self._detect_double_top(symbol, highs, closes)
        if double_top:
            patterns.append(double_top)
        
        self._detected_patterns = patterns
        return patterns
    
    def _detect_double_bottom(
        self,
        symbol: str,
        lows: list[float],
        closes: list[float],
    ) -> Optional[ChartPattern]:
        """Detect double bottom pattern."""
        if len(lows) < 20:
            return None
        
        # Find two local minimums
        window = 5
        local_mins = []
        
        for i in range(window, len(lows) - window):
            if lows[i] == min(lows[i-window:i+window+1]):
                local_mins.append((i, lows[i]))
        
        if len(local_mins) < 2:
            return None
        
        # Check last two minimums
        idx1, low1 = local_mins[-2]
        idx2, low2 = local_mins[-1]
        
        # Bottoms should be similar (within 3%)
        if abs(low1 - low2) / low1 > 0.03:
            return None
        
        # Should be at least 10 bars apart
        if idx2 - idx1 < 10:
            return None
        
        # Current price should be above the neckline
        neckline = max(closes[idx1:idx2])
        current = closes[-1]
        
        if current > neckline:
            target = neckline + (neckline - low1)
            
            return ChartPattern(
                symbol=symbol,
                pattern_type=PatternType.DOUBLE_BOTTOM,
                pattern_length=idx2 - idx1,
                entry_price=neckline,
                target_price=target,
                stop_price=low2 * 0.98,
                confidence=70,
                signal_strength=SignalStrength.MODERATE,
                is_confirmed=True,
                breakout_price=neckline,
            )
        
        return None
    
    def _detect_double_top(
        self,
        symbol: str,
        highs: list[float],
        closes: list[float],
    ) -> Optional[ChartPattern]:
        """Detect double top pattern."""
        if len(highs) < 20:
            return None
        
        # Find two local maximums
        window = 5
        local_maxs = []
        
        for i in range(window, len(highs) - window):
            if highs[i] == max(highs[i-window:i+window+1]):
                local_maxs.append((i, highs[i]))
        
        if len(local_maxs) < 2:
            return None
        
        # Check last two maximums
        idx1, high1 = local_maxs[-2]
        idx2, high2 = local_maxs[-1]
        
        # Tops should be similar (within 3%)
        if abs(high1 - high2) / high1 > 0.03:
            return None
        
        # Should be at least 10 bars apart
        if idx2 - idx1 < 10:
            return None
        
        # Current price should be below the neckline
        neckline = min(closes[idx1:idx2])
        current = closes[-1]
        
        if current < neckline:
            target = neckline - (high1 - neckline)
            
            return ChartPattern(
                symbol=symbol,
                pattern_type=PatternType.DOUBLE_TOP,
                pattern_length=idx2 - idx1,
                entry_price=neckline,
                target_price=target,
                stop_price=high2 * 1.02,
                confidence=70,
                signal_strength=SignalStrength.MODERATE,
                is_confirmed=True,
                breakout_price=neckline,
            )
        
        return None
    
    def get_bullish_patterns(self) -> list:
        """Get bullish candlestick patterns."""
        return [p for p in self._detected_candles if p.is_bullish]
    
    def get_bearish_patterns(self) -> list:
        """Get bearish candlestick patterns."""
        return [p for p in self._detected_candles if not p.is_bullish]
