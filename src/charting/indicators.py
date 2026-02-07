"""Technical indicators for charting."""

from typing import Optional
from datetime import datetime

from src.charting.config import IndicatorCategory, INDICATOR_DEFINITIONS
from src.charting.models import OHLCV, IndicatorResult


class IndicatorEngine:
    """Calculates technical indicators."""
    
    def __init__(self):
        self._indicators = INDICATOR_DEFINITIONS.copy()
    
    def get_available_indicators(self) -> list[dict]:
        """Get list of available indicators."""
        return [
            {
                "id": key,
                "name": val["name"],
                "category": val["category"].value,
                "params": val["params"],
                "overlay": val["overlay"],
            }
            for key, val in self._indicators.items()
        ]
    
    def get_indicators_by_category(self, category: IndicatorCategory) -> list[dict]:
        """Get indicators in a category."""
        return [
            ind for ind in self.get_available_indicators()
            if ind["category"] == category.value
        ]
    
    def calculate(
        self,
        indicator_name: str,
        data: list[OHLCV],
        params: Optional[dict] = None,
    ) -> IndicatorResult:
        """Calculate an indicator."""
        if indicator_name not in self._indicators:
            raise ValueError(f"Unknown indicator: {indicator_name}")
        
        definition = self._indicators[indicator_name]
        merged_params = {**definition["params"], **(params or {})}
        
        # Get calculation method
        method_name = f"_calc_{indicator_name.lower()}"
        if hasattr(self, method_name):
            values = getattr(self, method_name)(data, merged_params)
        else:
            values = self._calc_placeholder(data, indicator_name)
        
        return IndicatorResult(
            name=indicator_name,
            values=values,
            timestamps=[d.timestamp for d in data],
            params=merged_params,
            is_overlay=definition["overlay"],
        )
    
    def _calc_sma(self, data: list[OHLCV], params: dict) -> dict[str, list[float]]:
        """Calculate Simple Moving Average."""
        period = params.get("period", 20)
        closes = [d.close for d in data]
        
        sma = []
        for i in range(len(closes)):
            if i < period - 1:
                sma.append(float('nan'))
            else:
                sma.append(sum(closes[i-period+1:i+1]) / period)
        
        return {"sma": sma}
    
    def _calc_ema(self, data: list[OHLCV], params: dict) -> dict[str, list[float]]:
        """Calculate Exponential Moving Average."""
        period = params.get("period", 20)
        closes = [d.close for d in data]
        
        multiplier = 2 / (period + 1)
        ema = [float('nan')] * (period - 1)
        
        # First EMA is SMA
        ema.append(sum(closes[:period]) / period)
        
        for i in range(period, len(closes)):
            ema.append((closes[i] - ema[-1]) * multiplier + ema[-1])
        
        return {"ema": ema}
    
    def _calc_bb(self, data: list[OHLCV], params: dict) -> dict[str, list[float]]:
        """Calculate Bollinger Bands."""
        period = params.get("period", 20)
        std_mult = params.get("std", 2.0)
        closes = [d.close for d in data]
        
        middle = []
        upper = []
        lower = []
        
        for i in range(len(closes)):
            if i < period - 1:
                middle.append(float('nan'))
                upper.append(float('nan'))
                lower.append(float('nan'))
            else:
                window = closes[i-period+1:i+1]
                mean = sum(window) / period
                variance = sum((x - mean) ** 2 for x in window) / period
                std = variance ** 0.5
                
                middle.append(mean)
                upper.append(mean + std_mult * std)
                lower.append(mean - std_mult * std)
        
        return {"middle": middle, "upper": upper, "lower": lower}
    
    def _calc_rsi(self, data: list[OHLCV], params: dict) -> dict[str, list[float]]:
        """Calculate Relative Strength Index."""
        period = params.get("period", 14)
        closes = [d.close for d in data]
        
        rsi = [float('nan')] * period
        
        gains = []
        losses = []
        
        for i in range(1, len(closes)):
            change = closes[i] - closes[i-1]
            gains.append(max(change, 0))
            losses.append(abs(min(change, 0)))
        
        if len(gains) < period:
            return {"rsi": [float('nan')] * len(data)}
        
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        
        if avg_loss == 0:
            rsi.append(100.0)
        else:
            rs = avg_gain / avg_loss
            rsi.append(100 - (100 / (1 + rs)))
        
        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            
            if avg_loss == 0:
                rsi.append(100.0)
            else:
                rs = avg_gain / avg_loss
                rsi.append(100 - (100 / (1 + rs)))
        
        return {"rsi": rsi}
    
    def _calc_macd(self, data: list[OHLCV], params: dict) -> dict[str, list[float]]:
        """Calculate MACD."""
        fast = params.get("fast", 12)
        slow = params.get("slow", 26)
        signal_period = params.get("signal", 9)
        
        closes = [d.close for d in data]
        
        # Calculate EMAs
        fast_ema = self._ema_calc(closes, fast)
        slow_ema = self._ema_calc(closes, slow)
        
        # MACD line
        macd_line = [f - s if not (f != f or s != s) else float('nan') 
                     for f, s in zip(fast_ema, slow_ema)]
        
        # Signal line (EMA of MACD)
        valid_macd = [m for m in macd_line if m == m]  # Remove NaN
        if len(valid_macd) >= signal_period:
            signal_ema = self._ema_calc(valid_macd, signal_period)
            signal = [float('nan')] * (len(macd_line) - len(signal_ema)) + signal_ema
        else:
            signal = [float('nan')] * len(macd_line)
        
        # Histogram
        histogram = [m - s if not (m != m or s != s) else float('nan')
                     for m, s in zip(macd_line, signal)]
        
        return {"macd": macd_line, "signal": signal, "histogram": histogram}
    
    def _calc_stoch(self, data: list[OHLCV], params: dict) -> dict[str, list[float]]:
        """Calculate Stochastic Oscillator."""
        k_period = params.get("k", 14)
        d_period = params.get("d", 3)
        
        highs = [d.high for d in data]
        lows = [d.low for d in data]
        closes = [d.close for d in data]
        
        k_values = []
        
        for i in range(len(closes)):
            if i < k_period - 1:
                k_values.append(float('nan'))
            else:
                highest = max(highs[i-k_period+1:i+1])
                lowest = min(lows[i-k_period+1:i+1])
                
                if highest == lowest:
                    k_values.append(50.0)
                else:
                    k_values.append((closes[i] - lowest) / (highest - lowest) * 100)
        
        # %D is SMA of %K
        d_values = []
        for i in range(len(k_values)):
            if i < k_period + d_period - 2:
                d_values.append(float('nan'))
            else:
                window = [v for v in k_values[i-d_period+1:i+1] if v == v]
                if window:
                    d_values.append(sum(window) / len(window))
                else:
                    d_values.append(float('nan'))
        
        return {"k": k_values, "d": d_values}
    
    def _calc_atr(self, data: list[OHLCV], params: dict) -> dict[str, list[float]]:
        """Calculate Average True Range."""
        period = params.get("period", 14)
        
        tr_values = []
        for i in range(len(data)):
            if i == 0:
                tr_values.append(data[i].high - data[i].low)
            else:
                tr = max(
                    data[i].high - data[i].low,
                    abs(data[i].high - data[i-1].close),
                    abs(data[i].low - data[i-1].close)
                )
                tr_values.append(tr)
        
        atr = [float('nan')] * (period - 1)
        atr.append(sum(tr_values[:period]) / period)
        
        for i in range(period, len(tr_values)):
            atr.append((atr[-1] * (period - 1) + tr_values[i]) / period)
        
        return {"atr": atr}
    
    def _calc_obv(self, data: list[OHLCV], params: dict) -> dict[str, list[float]]:
        """Calculate On Balance Volume."""
        obv = [0.0]
        
        for i in range(1, len(data)):
            if data[i].close > data[i-1].close:
                obv.append(obv[-1] + data[i].volume)
            elif data[i].close < data[i-1].close:
                obv.append(obv[-1] - data[i].volume)
            else:
                obv.append(obv[-1])
        
        return {"obv": obv}
    
    def _calc_vwap(self, data: list[OHLCV], params: dict) -> dict[str, list[float]]:
        """Calculate Volume Weighted Average Price."""
        cumulative_tp_vol = 0.0
        cumulative_vol = 0
        vwap = []
        
        for bar in data:
            typical_price = (bar.high + bar.low + bar.close) / 3
            cumulative_tp_vol += typical_price * bar.volume
            cumulative_vol += bar.volume
            
            if cumulative_vol > 0:
                vwap.append(cumulative_tp_vol / cumulative_vol)
            else:
                vwap.append(float('nan'))
        
        return {"vwap": vwap}
    
    def _ema_calc(self, values: list[float], period: int) -> list[float]:
        """Helper to calculate EMA."""
        multiplier = 2 / (period + 1)
        ema = [float('nan')] * (period - 1)
        
        valid_values = [v for v in values[:period] if v == v]
        if len(valid_values) == period:
            ema.append(sum(valid_values) / period)
            
            for i in range(period, len(values)):
                if values[i] == values[i]:  # Not NaN
                    ema.append((values[i] - ema[-1]) * multiplier + ema[-1])
                else:
                    ema.append(ema[-1])
        
        return ema
    
    def _calc_placeholder(self, data: list[OHLCV], name: str) -> dict[str, list[float]]:
        """Placeholder for unimplemented indicators."""
        return {"value": [d.close for d in data]}
