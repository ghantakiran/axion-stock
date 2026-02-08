"""Signal generation based on market regimes."""

from datetime import datetime, timezone, timedelta
from typing import Optional
import time
import math

from src.regime_signals.config import (
    RegimeType,
    SignalType,
    SignalDirection,
    REGIME_PARAMETERS,
    SignalConfig,
    DEFAULT_SIGNAL_CONFIG,
)
from src.regime_signals.models import (
    RegimeState,
    RegimeSignal,
    SignalResult,
)
from src.regime_signals.detector import RegimeDetector


class SignalGenerator:
    """Generates regime-aware trading signals."""
    
    def __init__(
        self,
        detector: Optional[RegimeDetector] = None,
        config: SignalConfig = DEFAULT_SIGNAL_CONFIG,
    ):
        self.detector = detector or RegimeDetector(config)
        self.config = config
    
    def generate_signals(
        self,
        symbol: str,
        prices: list[float],
        highs: Optional[list[float]] = None,
        lows: Optional[list[float]] = None,
        volumes: Optional[list[float]] = None,
    ) -> SignalResult:
        """Generate regime-aware signals for a symbol."""
        start_time = time.time()
        warnings = []
        indicators_computed = []
        
        # Detect current regime
        regime_state = self.detector.detect_regime(symbol, prices, volumes)
        
        # Get regime-specific parameters
        regime_params = REGIME_PARAMETERS.get(
            regime_state.regime_type.value,
            REGIME_PARAMETERS[RegimeType.SIDEWAYS_LOW_VOL.value]
        )
        
        signals = []
        
        # Generate signals based on preferred signal types for this regime
        preferred_signals = regime_params.get("preferred_signals", [])
        
        for signal_type in preferred_signals:
            signal = self._generate_signal(
                symbol=symbol,
                signal_type=signal_type,
                regime_state=regime_state,
                regime_params=regime_params,
                prices=prices,
                highs=highs,
                lows=lows,
                volumes=volumes,
            )
            if signal:
                signals.append(signal)
                indicators_computed.extend(signal.indicators_used)
        
        # Filter signals by minimum strength
        signals = [s for s in signals if s.strength >= self.config.min_signal_strength]
        
        # Sort by strength
        signals.sort(key=lambda s: s.strength, reverse=True)
        
        generation_time = (time.time() - start_time) * 1000
        
        return SignalResult(
            signals=signals,
            regime_state=regime_state,
            generation_time_ms=generation_time,
            indicators_computed=list(set(indicators_computed)),
            warnings=warnings,
        )
    
    def _generate_signal(
        self,
        symbol: str,
        signal_type: SignalType,
        regime_state: RegimeState,
        regime_params: dict,
        prices: list[float],
        highs: Optional[list[float]],
        lows: Optional[list[float]],
        volumes: Optional[list[float]],
    ) -> Optional[RegimeSignal]:
        """Generate a specific type of signal."""
        if signal_type == SignalType.MOMENTUM:
            return self._momentum_signal(symbol, regime_state, regime_params, prices)
        elif signal_type == SignalType.MEAN_REVERSION:
            return self._mean_reversion_signal(symbol, regime_state, regime_params, prices)
        elif signal_type == SignalType.BREAKOUT:
            return self._breakout_signal(symbol, regime_state, regime_params, prices, highs, lows)
        elif signal_type == SignalType.TREND_FOLLOWING:
            return self._trend_following_signal(symbol, regime_state, regime_params, prices)
        elif signal_type == SignalType.DEFENSIVE:
            return self._defensive_signal(symbol, regime_state, regime_params, prices)
        elif signal_type == SignalType.AGGRESSIVE:
            return self._aggressive_signal(symbol, regime_state, regime_params, prices)
        elif signal_type == SignalType.VOLATILITY_EXPANSION:
            return self._volatility_signal(symbol, regime_state, regime_params, prices)
        elif signal_type == SignalType.COUNTER_TREND:
            return self._counter_trend_signal(symbol, regime_state, regime_params, prices)
        else:
            return None
    
    def _momentum_signal(
        self,
        symbol: str,
        regime_state: RegimeState,
        params: dict,
        prices: list[float],
    ) -> Optional[RegimeSignal]:
        """Generate momentum signal."""
        if len(prices) < params["sma_period"] + 5:
            return None
        
        # Calculate RSI
        rsi = self._calculate_rsi(prices, params["rsi_period"])
        if rsi is None:
            return None
        
        # Calculate SMA
        sma = sum(prices[-params["sma_period"]:]) / params["sma_period"]
        current_price = prices[-1]
        
        # Determine direction
        if current_price > sma and rsi > 50 and rsi < params["rsi_overbought"]:
            direction = SignalDirection.LONG
            strength = min((rsi - 50) / 50 * 1.5, 1.0)
        elif current_price < sma and rsi < 50 and rsi > params["rsi_oversold"]:
            direction = SignalDirection.SHORT
            strength = min((50 - rsi) / 50 * 1.5, 1.0)
        else:
            return None
        
        # Calculate ATR for stops
        atr = self._calculate_atr(prices, 14)
        stop_loss_dist = atr * params["stop_loss_atr"]
        take_profit_dist = atr * params["take_profit_atr"]
        
        if direction == SignalDirection.LONG:
            stop_loss = current_price - stop_loss_dist
            take_profit = current_price + take_profit_dist
        else:
            stop_loss = current_price + stop_loss_dist
            take_profit = current_price - take_profit_dist
        
        signal = RegimeSignal(
            symbol=symbol,
            signal_type=SignalType.MOMENTUM,
            direction=direction,
            regime_type=regime_state.regime_type,
            strength=strength,
            confidence=regime_state.confidence * strength,
            regime_confidence=regime_state.confidence,
            entry_price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            indicators_used=["RSI", "SMA"],
            parameters={"rsi": rsi, "sma": sma, "atr": atr},
            expires_at=datetime.now(timezone.utc) + timedelta(hours=self.config.signal_expiry_hours),
        )
        signal.calculate_risk_reward()
        
        return signal
    
    def _mean_reversion_signal(
        self,
        symbol: str,
        regime_state: RegimeState,
        params: dict,
        prices: list[float],
    ) -> Optional[RegimeSignal]:
        """Generate mean reversion signal."""
        if len(prices) < params["sma_period"] + 5:
            return None
        
        # Calculate RSI
        rsi = self._calculate_rsi(prices, params["rsi_period"])
        if rsi is None:
            return None
        
        # Calculate Bollinger Bands
        sma = sum(prices[-params["sma_period"]:]) / params["sma_period"]
        window = prices[-params["sma_period"]:]
        variance = sum((p - sma) ** 2 for p in window) / len(window)
        std = math.sqrt(variance)
        upper_band = sma + 2 * std
        lower_band = sma - 2 * std
        
        current_price = prices[-1]
        
        # Mean reversion conditions
        if current_price < lower_band and rsi < params["rsi_oversold"]:
            direction = SignalDirection.LONG
            strength = min((params["rsi_oversold"] - rsi) / 30, 1.0)
        elif current_price > upper_band and rsi > params["rsi_overbought"]:
            direction = SignalDirection.SHORT
            strength = min((rsi - params["rsi_overbought"]) / 30, 1.0)
        else:
            return None
        
        # Calculate stops - tighter for mean reversion
        atr = self._calculate_atr(prices, 14)
        stop_loss_dist = atr * params["stop_loss_atr"] * 0.8  # Tighter
        take_profit_dist = atr * params["take_profit_atr"] * 0.6  # Target mean
        
        if direction == SignalDirection.LONG:
            stop_loss = current_price - stop_loss_dist
            take_profit = sma  # Target the mean
        else:
            stop_loss = current_price + stop_loss_dist
            take_profit = sma
        
        signal = RegimeSignal(
            symbol=symbol,
            signal_type=SignalType.MEAN_REVERSION,
            direction=direction,
            regime_type=regime_state.regime_type,
            strength=strength,
            confidence=regime_state.confidence * strength,
            regime_confidence=regime_state.confidence,
            entry_price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            indicators_used=["RSI", "Bollinger Bands"],
            parameters={
                "rsi": rsi,
                "sma": sma,
                "upper_band": upper_band,
                "lower_band": lower_band,
            },
            expires_at=datetime.now(timezone.utc) + timedelta(hours=self.config.signal_expiry_hours),
        )
        signal.calculate_risk_reward()
        
        return signal
    
    def _breakout_signal(
        self,
        symbol: str,
        regime_state: RegimeState,
        params: dict,
        prices: list[float],
        highs: Optional[list[float]],
        lows: Optional[list[float]],
    ) -> Optional[RegimeSignal]:
        """Generate breakout signal."""
        lookback = 20
        if len(prices) < lookback + 5:
            return None
        
        # Use highs/lows if available, else approximate from prices
        if highs and lows and len(highs) >= lookback:
            recent_high = max(highs[-lookback:-1])
            recent_low = min(lows[-lookback:-1])
        else:
            recent_high = max(prices[-lookback:-1])
            recent_low = min(prices[-lookback:-1])
        
        current_price = prices[-1]
        prev_price = prices[-2]
        
        # Breakout conditions
        if current_price > recent_high and prev_price <= recent_high:
            direction = SignalDirection.LONG
            breakout_pct = (current_price - recent_high) / recent_high
            strength = min(breakout_pct * 20 + 0.5, 1.0)
        elif current_price < recent_low and prev_price >= recent_low:
            direction = SignalDirection.SHORT
            breakout_pct = (recent_low - current_price) / recent_low
            strength = min(breakout_pct * 20 + 0.5, 1.0)
        else:
            return None
        
        # Calculate stops
        atr = self._calculate_atr(prices, 14)
        stop_loss_dist = atr * params["stop_loss_atr"]
        take_profit_dist = atr * params["take_profit_atr"]
        
        if direction == SignalDirection.LONG:
            stop_loss = recent_high - atr  # Just below breakout level
            take_profit = current_price + take_profit_dist
        else:
            stop_loss = recent_low + atr
            take_profit = current_price - take_profit_dist
        
        signal = RegimeSignal(
            symbol=symbol,
            signal_type=SignalType.BREAKOUT,
            direction=direction,
            regime_type=regime_state.regime_type,
            strength=strength,
            confidence=regime_state.confidence * strength,
            regime_confidence=regime_state.confidence,
            entry_price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            indicators_used=["Price Range", "ATR"],
            parameters={
                "recent_high": recent_high,
                "recent_low": recent_low,
                "atr": atr,
            },
            expires_at=datetime.now(timezone.utc) + timedelta(hours=self.config.signal_expiry_hours // 2),
        )
        signal.calculate_risk_reward()
        
        return signal
    
    def _trend_following_signal(
        self,
        symbol: str,
        regime_state: RegimeState,
        params: dict,
        prices: list[float],
    ) -> Optional[RegimeSignal]:
        """Generate trend following signal."""
        short_period = params["sma_period"]
        long_period = 50
        
        if len(prices) < long_period + 5:
            return None
        
        short_sma = sum(prices[-short_period:]) / short_period
        long_sma = sum(prices[-long_period:]) / long_period
        current_price = prices[-1]
        
        # Previous SMAs for crossover detection
        prev_short = sum(prices[-short_period-1:-1]) / short_period
        prev_long = sum(prices[-long_period-1:-1]) / long_period
        
        # Trend following: price above both MAs, short > long
        if short_sma > long_sma and current_price > short_sma:
            direction = SignalDirection.LONG
            strength = min((short_sma - long_sma) / long_sma * 20 + 0.5, 1.0)
        elif short_sma < long_sma and current_price < short_sma:
            direction = SignalDirection.SHORT
            strength = min((long_sma - short_sma) / long_sma * 20 + 0.5, 1.0)
        else:
            return None
        
        # Boost strength on MA crossover
        if prev_short <= prev_long and short_sma > long_sma:
            strength = min(strength + 0.2, 1.0)  # Golden cross
        elif prev_short >= prev_long and short_sma < long_sma:
            strength = min(strength + 0.2, 1.0)  # Death cross
        
        atr = self._calculate_atr(prices, 14)
        
        if direction == SignalDirection.LONG:
            stop_loss = long_sma - atr  # Below long MA
            take_profit = current_price + atr * params["take_profit_atr"]
        else:
            stop_loss = long_sma + atr
            take_profit = current_price - atr * params["take_profit_atr"]
        
        signal = RegimeSignal(
            symbol=symbol,
            signal_type=SignalType.TREND_FOLLOWING,
            direction=direction,
            regime_type=regime_state.regime_type,
            strength=strength,
            confidence=regime_state.confidence * strength,
            regime_confidence=regime_state.confidence,
            entry_price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            indicators_used=["SMA_short", "SMA_long"],
            parameters={
                "short_sma": short_sma,
                "long_sma": long_sma,
                "sma_spread": (short_sma - long_sma) / long_sma,
            },
            expires_at=datetime.now(timezone.utc) + timedelta(hours=self.config.signal_expiry_hours * 2),
        )
        signal.calculate_risk_reward()
        
        return signal
    
    def _defensive_signal(
        self,
        symbol: str,
        regime_state: RegimeState,
        params: dict,
        prices: list[float],
    ) -> Optional[RegimeSignal]:
        """Generate defensive signal for risk-off positioning."""
        if len(prices) < 20:
            return None
        
        # Calculate volatility
        returns = [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]
        recent_returns = returns[-20:]
        volatility = math.sqrt(sum(r ** 2 for r in recent_returns) / len(recent_returns)) * math.sqrt(252)
        
        # Calculate drawdown from recent high
        recent_high = max(prices[-20:])
        current_price = prices[-1]
        drawdown = (recent_high - current_price) / recent_high
        
        # Defensive signal when volatility high or drawdown significant
        if volatility > 0.3 or drawdown > 0.05:
            direction = SignalDirection.NEUTRAL
            strength = min(volatility + drawdown, 1.0)
            
            signal = RegimeSignal(
                symbol=symbol,
                signal_type=SignalType.DEFENSIVE,
                direction=direction,
                regime_type=regime_state.regime_type,
                strength=strength,
                confidence=regime_state.confidence * strength,
                regime_confidence=regime_state.confidence,
                entry_price=current_price,
                indicators_used=["Volatility", "Drawdown"],
                parameters={
                    "volatility": volatility,
                    "drawdown": drawdown,
                    "recent_high": recent_high,
                },
                notes="Risk-off signal: reduce exposure",
                expires_at=datetime.now(timezone.utc) + timedelta(hours=self.config.signal_expiry_hours),
            )
            return signal
        
        return None
    
    def _aggressive_signal(
        self,
        symbol: str,
        regime_state: RegimeState,
        params: dict,
        prices: list[float],
    ) -> Optional[RegimeSignal]:
        """Generate aggressive signal for recovery positioning."""
        if len(prices) < 30:
            return None
        
        # Recovery signal: bouncing from lows with momentum
        recent_low = min(prices[-30:])
        current_price = prices[-1]
        recovery = (current_price - recent_low) / recent_low
        
        # Calculate short-term momentum
        momentum = (current_price - prices[-5]) / prices[-5]
        
        rsi = self._calculate_rsi(prices, 10)
        if rsi is None:
            return None
        
        # Aggressive long on recovery with momentum
        if recovery > 0.05 and momentum > 0.02 and rsi > 50 and rsi < 70:
            direction = SignalDirection.LONG
            strength = min(recovery * 5 + momentum * 10, 1.0)
            
            atr = self._calculate_atr(prices, 14)
            stop_loss = current_price - atr * params["stop_loss_atr"]
            take_profit = current_price + atr * params["take_profit_atr"]
            
            signal = RegimeSignal(
                symbol=symbol,
                signal_type=SignalType.AGGRESSIVE,
                direction=direction,
                regime_type=regime_state.regime_type,
                strength=strength,
                confidence=regime_state.confidence * strength,
                regime_confidence=regime_state.confidence,
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                indicators_used=["Recovery", "Momentum", "RSI"],
                parameters={
                    "recovery": recovery,
                    "momentum": momentum,
                    "rsi": rsi,
                    "recent_low": recent_low,
                },
                notes="Aggressive entry on recovery",
                expires_at=datetime.now(timezone.utc) + timedelta(hours=self.config.signal_expiry_hours),
            )
            signal.calculate_risk_reward()
            return signal
        
        return None
    
    def _volatility_signal(
        self,
        symbol: str,
        regime_state: RegimeState,
        params: dict,
        prices: list[float],
    ) -> Optional[RegimeSignal]:
        """Generate volatility expansion signal."""
        if len(prices) < 30:
            return None
        
        # Calculate recent vs historical volatility
        returns = [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]
        
        recent_vol = math.sqrt(sum(r ** 2 for r in returns[-10:]) / 10)
        hist_vol = math.sqrt(sum(r ** 2 for r in returns[-30:-10]) / 20) if len(returns) >= 30 else recent_vol
        
        vol_expansion = recent_vol / hist_vol if hist_vol > 0 else 1.0
        
        current_price = prices[-1]
        
        # Signal on volatility expansion
        if vol_expansion > 1.5:
            # Direction based on recent trend
            trend = (current_price - prices[-5]) / prices[-5]
            direction = SignalDirection.LONG if trend > 0 else SignalDirection.SHORT
            strength = min((vol_expansion - 1.0) * 0.5, 1.0)
            
            atr = self._calculate_atr(prices, 14)
            
            if direction == SignalDirection.LONG:
                stop_loss = current_price - atr * params["stop_loss_atr"]
                take_profit = current_price + atr * params["take_profit_atr"]
            else:
                stop_loss = current_price + atr * params["stop_loss_atr"]
                take_profit = current_price - atr * params["take_profit_atr"]
            
            signal = RegimeSignal(
                symbol=symbol,
                signal_type=SignalType.VOLATILITY_EXPANSION,
                direction=direction,
                regime_type=regime_state.regime_type,
                strength=strength,
                confidence=regime_state.confidence * strength,
                regime_confidence=regime_state.confidence,
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                indicators_used=["Volatility Ratio"],
                parameters={
                    "vol_expansion": vol_expansion,
                    "recent_vol": recent_vol,
                    "hist_vol": hist_vol,
                },
                expires_at=datetime.now(timezone.utc) + timedelta(hours=self.config.signal_expiry_hours // 2),
            )
            signal.calculate_risk_reward()
            return signal
        
        return None
    
    def _counter_trend_signal(
        self,
        symbol: str,
        regime_state: RegimeState,
        params: dict,
        prices: list[float],
    ) -> Optional[RegimeSignal]:
        """Generate counter-trend signal."""
        if len(prices) < 30:
            return None
        
        rsi = self._calculate_rsi(prices, params["rsi_period"])
        if rsi is None:
            return None
        
        current_price = prices[-1]
        sma = sum(prices[-params["sma_period"]:]) / params["sma_period"]
        
        # Counter-trend on extreme RSI
        if rsi < 25:  # Oversold
            direction = SignalDirection.LONG
            strength = min((25 - rsi) / 25, 1.0)
        elif rsi > 75:  # Overbought
            direction = SignalDirection.SHORT
            strength = min((rsi - 75) / 25, 1.0)
        else:
            return None
        
        atr = self._calculate_atr(prices, 14)
        
        if direction == SignalDirection.LONG:
            stop_loss = current_price - atr * params["stop_loss_atr"] * 0.7
            take_profit = sma  # Target mean
        else:
            stop_loss = current_price + atr * params["stop_loss_atr"] * 0.7
            take_profit = sma
        
        signal = RegimeSignal(
            symbol=symbol,
            signal_type=SignalType.COUNTER_TREND,
            direction=direction,
            regime_type=regime_state.regime_type,
            strength=strength,
            confidence=regime_state.confidence * strength * 0.8,  # Lower confidence for counter-trend
            regime_confidence=regime_state.confidence,
            entry_price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            indicators_used=["RSI", "SMA"],
            parameters={"rsi": rsi, "sma": sma},
            notes="Counter-trend: trade against momentum",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=self.config.signal_expiry_hours // 2),
        )
        signal.calculate_risk_reward()
        
        return signal
    
    def _calculate_rsi(self, prices: list[float], period: int) -> Optional[float]:
        """Calculate RSI."""
        if len(prices) < period + 1:
            return None
        
        gains = []
        losses = []
        
        for i in range(-period, 0):
            change = prices[i] - prices[i-1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _calculate_atr(self, prices: list[float], period: int) -> float:
        """Calculate ATR approximation from prices."""
        if len(prices) < period + 1:
            return abs(prices[-1] - prices[-2]) if len(prices) >= 2 else prices[-1] * 0.02
        
        tr_values = []
        for i in range(-period, 0):
            tr = abs(prices[i] - prices[i-1])
            tr_values.append(tr)
        
        return sum(tr_values) / len(tr_values)
