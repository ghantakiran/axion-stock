"""Regime detection for market analysis."""

from datetime import datetime, timezone, timedelta
from typing import Optional
from collections import defaultdict
import math

from src.regime_signals.config import (
    RegimeType,
    DetectionMethod,
    TrendDirection,
    VolatilityLevel,
    SignalConfig,
    DEFAULT_SIGNAL_CONFIG,
)
from src.regime_signals.models import RegimeState


class RegimeDetector:
    """Detects market regimes using multiple methods."""
    
    def __init__(self, config: SignalConfig = DEFAULT_SIGNAL_CONFIG):
        self.config = config
        # symbol -> list of regime states
        self._history: dict[str, list[RegimeState]] = defaultdict(list)
    
    def detect_regime(
        self,
        symbol: str,
        prices: list[float],
        volumes: Optional[list[float]] = None,
        method: DetectionMethod = DetectionMethod.COMBINED,
    ) -> RegimeState:
        """Detect current market regime."""
        if len(prices) < self.config.trend_lookback:
            # Not enough data, return neutral state
            return RegimeState(
                symbol=symbol,
                regime_type=RegimeType.SIDEWAYS_LOW_VOL,
                detection_method=method,
                confidence=0.3,
            )
        
        if method == DetectionMethod.COMBINED:
            return self._detect_combined(symbol, prices, volumes)
        elif method == DetectionMethod.VOLATILITY_CLUSTER:
            return self._detect_volatility(symbol, prices)
        elif method == DetectionMethod.TREND_STRENGTH:
            return self._detect_trend(symbol, prices)
        elif method == DetectionMethod.MOVING_AVERAGE:
            return self._detect_ma_regime(symbol, prices)
        else:
            return self._detect_combined(symbol, prices, volumes)
    
    def _detect_combined(
        self,
        symbol: str,
        prices: list[float],
        volumes: Optional[list[float]] = None,
    ) -> RegimeState:
        """Combined regime detection using multiple signals."""
        # Get individual regime assessments
        vol_state = self._detect_volatility(symbol, prices)
        trend_state = self._detect_trend(symbol, prices)
        ma_state = self._detect_ma_regime(symbol, prices)
        
        # Determine trend direction
        trend_dir = trend_state.trend_direction or TrendDirection.NEUTRAL
        trend_strength = trend_state.trend_strength or 0.0
        
        # Determine volatility level
        vol_level = vol_state.volatility_level or VolatilityLevel.MEDIUM
        
        # Classify regime based on combination
        regime_type = self._classify_regime(trend_dir, trend_strength, vol_level)
        
        # Calculate confidence as weighted average
        confidence = (
            vol_state.confidence * 0.3 +
            trend_state.confidence * 0.4 +
            ma_state.confidence * 0.3
        )
        
        # Check for crisis conditions
        if vol_level == VolatilityLevel.EXTREME and trend_dir == TrendDirection.DOWN:
            regime_type = RegimeType.CRISIS
            confidence = min(confidence + 0.1, 1.0)
        
        # Calculate regime duration
        duration = self._calculate_duration(symbol, regime_type)
        
        # Calculate transition probability
        transition_prob = self._estimate_transition_probability(symbol, regime_type)
        
        state = RegimeState(
            symbol=symbol,
            regime_type=regime_type,
            detection_method=DetectionMethod.COMBINED,
            confidence=confidence,
            volatility_level=vol_level,
            trend_direction=trend_dir,
            trend_strength=trend_strength,
            regime_duration_days=duration,
            transition_probability=transition_prob,
            metadata={
                "vol_confidence": vol_state.confidence,
                "trend_confidence": trend_state.confidence,
                "ma_confidence": ma_state.confidence,
            },
        )
        
        self._history[symbol].append(state)
        return state
    
    def _detect_volatility(self, symbol: str, prices: list[float]) -> RegimeState:
        """Detect regime based on volatility clustering."""
        lookback = self.config.volatility_lookback
        
        # Calculate returns
        returns = []
        for i in range(1, len(prices)):
            ret = (prices[i] - prices[i-1]) / prices[i-1]
            returns.append(ret)
        
        if len(returns) < lookback:
            return RegimeState(
                symbol=symbol,
                regime_type=RegimeType.SIDEWAYS_LOW_VOL,
                detection_method=DetectionMethod.VOLATILITY_CLUSTER,
                confidence=0.3,
            )
        
        # Calculate rolling volatility
        recent_returns = returns[-lookback:]
        mean_ret = sum(recent_returns) / len(recent_returns)
        variance = sum((r - mean_ret) ** 2 for r in recent_returns) / len(recent_returns)
        current_vol = math.sqrt(variance) * math.sqrt(252)  # Annualized
        
        # Historical volatility for comparison
        hist_returns = returns[:-lookback] if len(returns) > lookback * 2 else returns[:lookback]
        hist_mean = sum(hist_returns) / len(hist_returns) if hist_returns else 0
        hist_variance = sum((r - hist_mean) ** 2 for r in hist_returns) / len(hist_returns) if hist_returns else 0.01
        hist_vol = math.sqrt(hist_variance) * math.sqrt(252)
        
        # Classify volatility level
        if hist_vol == 0:
            vol_ratio = 1.0
        else:
            vol_ratio = current_vol / hist_vol
        
        if vol_ratio < 0.7:
            vol_level = VolatilityLevel.LOW
        elif vol_ratio < 1.0:
            vol_level = VolatilityLevel.MEDIUM
        elif vol_ratio < 1.5:
            vol_level = VolatilityLevel.HIGH
        else:
            vol_level = VolatilityLevel.EXTREME
        
        # Determine trend from recent returns
        trend_dir = TrendDirection.UP if mean_ret > 0.0005 else (
            TrendDirection.DOWN if mean_ret < -0.0005 else TrendDirection.NEUTRAL
        )
        
        regime_type = self._classify_regime(trend_dir, abs(mean_ret * 252), vol_level)
        
        confidence = min(0.5 + abs(vol_ratio - 1.0) * 0.3, 0.9)
        
        return RegimeState(
            symbol=symbol,
            regime_type=regime_type,
            detection_method=DetectionMethod.VOLATILITY_CLUSTER,
            confidence=confidence,
            volatility_level=vol_level,
            trend_direction=trend_dir,
            metadata={"current_vol": current_vol, "hist_vol": hist_vol, "vol_ratio": vol_ratio},
        )
    
    def _detect_trend(self, symbol: str, prices: list[float]) -> RegimeState:
        """Detect regime based on trend strength (ADX-like)."""
        lookback = self.config.trend_lookback
        
        if len(prices) < lookback:
            return RegimeState(
                symbol=symbol,
                regime_type=RegimeType.SIDEWAYS_LOW_VOL,
                detection_method=DetectionMethod.TREND_STRENGTH,
                confidence=0.3,
            )
        
        # Calculate price momentum
        recent_prices = prices[-lookback:]
        price_change = (recent_prices[-1] - recent_prices[0]) / recent_prices[0]
        
        # Calculate directional movement
        up_moves = []
        down_moves = []
        
        for i in range(1, len(recent_prices)):
            change = recent_prices[i] - recent_prices[i-1]
            if change > 0:
                up_moves.append(change)
            else:
                down_moves.append(abs(change))
        
        avg_up = sum(up_moves) / len(up_moves) if up_moves else 0
        avg_down = sum(down_moves) / len(down_moves) if down_moves else 0
        
        # Calculate trend strength (0-1)
        total_movement = avg_up + avg_down
        if total_movement == 0:
            trend_strength = 0.0
            trend_dir = TrendDirection.NEUTRAL
        else:
            directional_index = abs(avg_up - avg_down) / total_movement
            trend_strength = directional_index
            trend_dir = TrendDirection.UP if avg_up > avg_down else TrendDirection.DOWN
        
        # Classify based on trend strength
        if trend_strength < 0.2:
            if price_change > 0:
                regime_type = RegimeType.SIDEWAYS_LOW_VOL
            else:
                regime_type = RegimeType.SIDEWAYS_HIGH_VOL
        elif trend_dir == TrendDirection.UP:
            regime_type = RegimeType.BULL_TRENDING if trend_strength > 0.4 else RegimeType.BULL_VOLATILE
        else:
            regime_type = RegimeType.BEAR_TRENDING if trend_strength > 0.4 else RegimeType.BEAR_VOLATILE
        
        confidence = 0.5 + trend_strength * 0.4
        
        return RegimeState(
            symbol=symbol,
            regime_type=regime_type,
            detection_method=DetectionMethod.TREND_STRENGTH,
            confidence=confidence,
            trend_direction=trend_dir,
            trend_strength=trend_strength,
            metadata={"price_change": price_change, "avg_up": avg_up, "avg_down": avg_down},
        )
    
    def _detect_ma_regime(self, symbol: str, prices: list[float]) -> RegimeState:
        """Detect regime based on moving average relationships."""
        short_period = self.config.ma_short
        long_period = self.config.ma_long
        
        if len(prices) < long_period:
            return RegimeState(
                symbol=symbol,
                regime_type=RegimeType.SIDEWAYS_LOW_VOL,
                detection_method=DetectionMethod.MOVING_AVERAGE,
                confidence=0.3,
            )
        
        # Calculate MAs
        short_ma = sum(prices[-short_period:]) / short_period
        long_ma = sum(prices[-long_period:]) / long_period
        current_price = prices[-1]
        
        # MA relationship
        ma_spread = (short_ma - long_ma) / long_ma
        price_to_short = (current_price - short_ma) / short_ma
        price_to_long = (current_price - long_ma) / long_ma
        
        # Classify regime
        if short_ma > long_ma:
            if current_price > short_ma:
                regime_type = RegimeType.BULL_TRENDING
                trend_dir = TrendDirection.UP
            else:
                regime_type = RegimeType.BULL_VOLATILE
                trend_dir = TrendDirection.UP
        elif short_ma < long_ma:
            if current_price < short_ma:
                regime_type = RegimeType.BEAR_TRENDING
                trend_dir = TrendDirection.DOWN
            else:
                regime_type = RegimeType.BEAR_VOLATILE
                trend_dir = TrendDirection.DOWN
        else:
            regime_type = RegimeType.SIDEWAYS_LOW_VOL
            trend_dir = TrendDirection.NEUTRAL
        
        # Calculate confidence based on spread
        confidence = min(0.5 + abs(ma_spread) * 10, 0.9)
        
        return RegimeState(
            symbol=symbol,
            regime_type=regime_type,
            detection_method=DetectionMethod.MOVING_AVERAGE,
            confidence=confidence,
            trend_direction=trend_dir,
            trend_strength=abs(ma_spread),
            metadata={
                "short_ma": short_ma,
                "long_ma": long_ma,
                "ma_spread": ma_spread,
                "price_to_short": price_to_short,
            },
        )
    
    def _classify_regime(
        self,
        trend_dir: TrendDirection,
        trend_strength: float,
        vol_level: VolatilityLevel,
    ) -> RegimeType:
        """Classify regime from trend and volatility."""
        is_trending = trend_strength > 0.3
        
        if trend_dir == TrendDirection.UP:
            if vol_level in [VolatilityLevel.LOW, VolatilityLevel.MEDIUM]:
                return RegimeType.BULL_TRENDING if is_trending else RegimeType.SIDEWAYS_LOW_VOL
            else:
                return RegimeType.BULL_VOLATILE
        elif trend_dir == TrendDirection.DOWN:
            if vol_level == VolatilityLevel.EXTREME:
                return RegimeType.CRISIS
            elif vol_level in [VolatilityLevel.LOW, VolatilityLevel.MEDIUM]:
                return RegimeType.BEAR_TRENDING if is_trending else RegimeType.SIDEWAYS_LOW_VOL
            else:
                return RegimeType.BEAR_VOLATILE
        else:
            if vol_level in [VolatilityLevel.HIGH, VolatilityLevel.EXTREME]:
                return RegimeType.SIDEWAYS_HIGH_VOL
            else:
                return RegimeType.SIDEWAYS_LOW_VOL
    
    def _calculate_duration(self, symbol: str, current_regime: RegimeType) -> int:
        """Calculate how long current regime has persisted."""
        history = self._history.get(symbol, [])
        if not history:
            return 1
        
        duration = 1
        for state in reversed(history):
            if state.regime_type == current_regime:
                duration += 1
            else:
                break
        
        return duration
    
    def _estimate_transition_probability(
        self,
        symbol: str,
        current_regime: RegimeType,
    ) -> float:
        """Estimate probability of regime transition."""
        history = self._history.get(symbol, [])
        if len(history) < 10:
            return 0.2  # Default
        
        # Count transitions from current regime
        transitions = 0
        same_regime = 0
        
        for i in range(1, len(history)):
            if history[i-1].regime_type == current_regime:
                if history[i].regime_type != current_regime:
                    transitions += 1
                else:
                    same_regime += 1
        
        total = transitions + same_regime
        if total == 0:
            return 0.2
        
        return transitions / total
    
    def get_regime_history(
        self,
        symbol: str,
        limit: int = 100,
    ) -> list[RegimeState]:
        """Get regime history for a symbol."""
        history = self._history.get(symbol, [])
        return history[-limit:]
    
    def get_regime_statistics(self, symbol: str) -> dict:
        """Get regime statistics for a symbol."""
        history = self._history.get(symbol, [])
        if not history:
            return {"total_observations": 0}
        
        # Count regimes
        regime_counts: dict[str, int] = defaultdict(int)
        for state in history:
            regime_counts[state.regime_type.value] += 1
        
        # Average confidence
        avg_confidence = sum(s.confidence for s in history) / len(history)
        
        # Current regime duration
        current = history[-1] if history else None
        current_duration = self._calculate_duration(symbol, current.regime_type) if current else 0
        
        return {
            "total_observations": len(history),
            "regime_distribution": dict(regime_counts),
            "average_confidence": avg_confidence,
            "current_regime": current.regime_type.value if current else None,
            "current_duration_days": current_duration,
        }
