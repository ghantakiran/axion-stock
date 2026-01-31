"""Signal-Based Trading Bot.

Trades based on technical indicators and signals.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
import logging

from src.bots.config import (
    BotConfig,
    SignalBotConfig,
    SignalType,
    SignalCondition,
    PositionSizeMethod,
    TradeSide,
    OrderType,
)
from src.bots.models import BotOrder, Signal
from src.bots.base import BaseBot, BrokerInterface

logger = logging.getLogger(__name__)


@dataclass
class SignalRule:
    """Definition of a trading signal rule."""
    signal_type: SignalType
    condition: SignalCondition
    threshold: float
    parameters: dict[str, Any] = field(default_factory=dict)
    action: TradeSide = TradeSide.BUY


class SignalBot(BaseBot):
    """Signal-Based Trading Bot.
    
    Generates trading signals based on technical indicators
    and executes trades when conditions are met.
    
    Features:
    - Multiple signal types (RSI, MACD, MA crossover, etc.)
    - Configurable conditions
    - Position sizing options
    - Signal confirmation
    
    Example:
        config = BotConfig(
            bot_id="sig_1",
            name="RSI Oversold",
            bot_type=BotType.SIGNAL,
            symbols=["AAPL"],
            signal_config=SignalBotConfig(
                signals=[{
                    "type": "rsi",
                    "condition": "below",
                    "threshold": 30,
                    "action": "buy",
                }],
            ),
        )
        bot = SignalBot(config)
    """
    
    def __init__(
        self,
        config: BotConfig,
        broker: Optional[BrokerInterface] = None,
    ):
        super().__init__(config, broker)
        self.signal_config = config.signal_config or SignalBotConfig()
        
        # Parse signal rules
        self._rules: list[SignalRule] = []
        for sig in self.signal_config.signals:
            self._rules.append(SignalRule(
                signal_type=SignalType(sig.get("type", "price_level")),
                condition=SignalCondition(sig.get("condition", "below")),
                threshold=sig.get("threshold", 0),
                parameters=sig.get("parameters", {}),
                action=TradeSide(sig.get("action", "buy")),
            ))
        
        # Signal history
        self._signals: list[Signal] = []
        self._last_signal_time: dict[str, datetime] = {}
        
        # Indicator cache
        self._indicator_cache: dict[str, dict] = {}
    
    def generate_orders(self, market_data: dict[str, dict]) -> list[BotOrder]:
        """Generate orders based on signals.
        
        Args:
            market_data: Current market data with indicators.
            
        Returns:
            List of orders.
        """
        orders = []
        
        for symbol in self.config.symbols:
            if symbol not in market_data:
                continue
            
            data = market_data[symbol]
            
            # Check cooldown
            if self._in_cooldown(symbol):
                continue
            
            # Evaluate signals
            triggered_signals = self._evaluate_signals(symbol, data)
            
            if not triggered_signals:
                continue
            
            # Check if signals meet requirements
            if self.signal_config.require_all_signals:
                if len(triggered_signals) < len(self._rules):
                    continue
            
            # Generate order based on signals
            order = self._create_order_from_signals(symbol, data, triggered_signals)
            if order:
                orders.append(order)
                
                # Record signals
                for signal in triggered_signals:
                    signal.is_executed = True
                    self._signals.append(signal)
                
                # Update cooldown
                self._last_signal_time[symbol] = datetime.now(timezone.utc)
        
        return orders
    
    def _evaluate_signals(
        self,
        symbol: str,
        data: dict,
    ) -> list[Signal]:
        """Evaluate all signal rules for a symbol.
        
        Args:
            symbol: Stock symbol.
            data: Market data including indicators.
            
        Returns:
            List of triggered signals.
        """
        triggered = []
        
        for rule in self._rules:
            signal = self._check_signal(symbol, data, rule)
            if signal:
                triggered.append(signal)
        
        return triggered
    
    def _check_signal(
        self,
        symbol: str,
        data: dict,
        rule: SignalRule,
    ) -> Optional[Signal]:
        """Check if a single signal rule is triggered.
        
        Args:
            symbol: Stock symbol.
            data: Market data.
            rule: Signal rule to check.
            
        Returns:
            Signal if triggered, None otherwise.
        """
        # Get indicator value based on signal type
        indicator_value = self._get_indicator_value(data, rule)
        
        if indicator_value is None:
            return None
        
        # Check condition
        is_triggered = self._check_condition(indicator_value, rule)
        
        if is_triggered:
            return Signal(
                bot_id=self.bot_id,
                symbol=symbol,
                signal_type=rule.signal_type.value,
                side=rule.action,
                strength=self._calculate_signal_strength(indicator_value, rule),
                indicator_value=indicator_value,
                threshold=rule.threshold,
                price_at_signal=data.get("price", 0),
            )
        
        return None
    
    def _get_indicator_value(
        self,
        data: dict,
        rule: SignalRule,
    ) -> Optional[float]:
        """Get indicator value from market data.
        
        Args:
            data: Market data dict.
            rule: Signal rule.
            
        Returns:
            Indicator value or None.
        """
        sig_type = rule.signal_type
        
        if sig_type == SignalType.RSI:
            return data.get("rsi", data.get("indicators", {}).get("rsi"))
        
        elif sig_type == SignalType.PRICE_LEVEL:
            return data.get("price")
        
        elif sig_type == SignalType.PERCENT_CHANGE:
            return data.get("change_pct", data.get("indicators", {}).get("change_pct"))
        
        elif sig_type == SignalType.MACD:
            macd = data.get("indicators", {}).get("macd", {})
            return macd.get("histogram") if isinstance(macd, dict) else macd
        
        elif sig_type == SignalType.BOLLINGER:
            bb = data.get("indicators", {}).get("bollinger", {})
            price = data.get("price", 0)
            lower = bb.get("lower", 0) if isinstance(bb, dict) else 0
            upper = bb.get("upper", 0) if isinstance(bb, dict) else 0
            
            # Return position within bands (0 = lower, 1 = upper)
            if upper > lower:
                return (price - lower) / (upper - lower)
            return None
        
        elif sig_type == SignalType.VOLUME_SPIKE:
            volume = data.get("volume", 0)
            avg_volume = data.get("avg_volume", data.get("indicators", {}).get("avg_volume", volume))
            if avg_volume > 0:
                return volume / avg_volume
            return None
        
        elif sig_type == SignalType.FACTOR_SCORE:
            factor = rule.parameters.get("factor", "composite")
            return data.get("factors", {}).get(factor)
        
        elif sig_type == SignalType.PRICE_CROSS_MA:
            price = data.get("price", 0)
            period = rule.parameters.get("period", 20)
            ma = data.get("indicators", {}).get(f"sma_{period}")
            if ma and price:
                return price / ma
            return None
        
        elif sig_type == SignalType.MA_CROSSOVER:
            fast = rule.parameters.get("fast", 10)
            slow = rule.parameters.get("slow", 20)
            indicators = data.get("indicators", {})
            ma_fast = indicators.get(f"sma_{fast}")
            ma_slow = indicators.get(f"sma_{slow}")
            if ma_fast and ma_slow:
                return ma_fast / ma_slow
            return None
        
        return None
    
    def _check_condition(
        self,
        value: float,
        rule: SignalRule,
    ) -> bool:
        """Check if condition is met.
        
        Args:
            value: Indicator value.
            rule: Signal rule.
            
        Returns:
            True if condition is met.
        """
        cond = rule.condition
        threshold = rule.threshold
        
        if cond == SignalCondition.ABOVE:
            return value > threshold
        elif cond == SignalCondition.BELOW:
            return value < threshold
        elif cond == SignalCondition.EQUALS:
            return abs(value - threshold) < 0.01
        elif cond == SignalCondition.CROSSES_ABOVE:
            # Would need previous value; simplified
            return value > threshold
        elif cond == SignalCondition.CROSSES_BELOW:
            return value < threshold
        elif cond == SignalCondition.BETWEEN:
            lower = rule.parameters.get("lower", threshold)
            upper = rule.parameters.get("upper", threshold)
            return lower <= value <= upper
        
        return False
    
    def _calculate_signal_strength(
        self,
        value: float,
        rule: SignalRule,
    ) -> float:
        """Calculate signal strength (0-1).
        
        Args:
            value: Indicator value.
            rule: Signal rule.
            
        Returns:
            Strength from 0 to 1.
        """
        threshold = rule.threshold
        
        if rule.signal_type == SignalType.RSI:
            # RSI: strength based on extremity
            if value < 30:
                return min(1.0, (30 - value) / 30)
            elif value > 70:
                return min(1.0, (value - 70) / 30)
            return 0.0
        
        # Default: distance from threshold
        if threshold != 0:
            return min(1.0, abs(value - threshold) / abs(threshold))
        
        return 0.5
    
    def _in_cooldown(self, symbol: str) -> bool:
        """Check if symbol is in cooldown period."""
        last_time = self._last_signal_time.get(symbol)
        if not last_time:
            return False
        
        cooldown_periods = self.signal_config.cooldown_periods
        # Assume 1 period = 1 minute for now
        cooldown_seconds = cooldown_periods * 60
        
        elapsed = (datetime.now(timezone.utc) - last_time).total_seconds()
        return elapsed < cooldown_seconds
    
    def _create_order_from_signals(
        self,
        symbol: str,
        data: dict,
        signals: list[Signal],
    ) -> Optional[BotOrder]:
        """Create order based on triggered signals.
        
        Args:
            symbol: Stock symbol.
            data: Market data.
            signals: Triggered signals.
            
        Returns:
            Order or None.
        """
        price = data.get("price", 0)
        if price <= 0:
            return None
        
        # Determine side (majority of signals)
        buy_count = sum(1 for s in signals if s.side == TradeSide.BUY)
        sell_count = len(signals) - buy_count
        side = TradeSide.BUY if buy_count >= sell_count else TradeSide.SELL
        
        # Calculate position size
        quantity = self._calculate_position_size(symbol, price, signals)
        
        if quantity <= 0:
            return None
        
        return BotOrder(
            bot_id=self.bot_id,
            symbol=symbol,
            side=side,
            quantity=round(quantity, 4),
            order_type=OrderType.MARKET,
            limit_price=price,
        )
    
    def _calculate_position_size(
        self,
        symbol: str,
        price: float,
        signals: list[Signal],
    ) -> float:
        """Calculate position size based on method.
        
        Args:
            symbol: Stock symbol.
            price: Current price.
            signals: Triggered signals.
            
        Returns:
            Quantity to trade.
        """
        method = self.signal_config.position_size_method
        
        if method == PositionSizeMethod.FIXED_AMOUNT:
            amount = self.signal_config.fixed_amount
            return amount / price
        
        elif method == PositionSizeMethod.FIXED_SHARES:
            return self.signal_config.fixed_amount
        
        elif method == PositionSizeMethod.PERCENT_PORTFOLIO:
            # Would need portfolio value; use fixed for now
            return self.signal_config.fixed_amount / price
        
        elif method == PositionSizeMethod.VOLATILITY_SCALED:
            # Scale by signal strength
            avg_strength = sum(s.strength for s in signals) / len(signals)
            base_amount = self.signal_config.fixed_amount
            return (base_amount * avg_strength) / price
        
        # Default
        return self.signal_config.fixed_amount / price
    
    def get_signal_history(self, limit: int = 50) -> list[Signal]:
        """Get recent signals."""
        return sorted(
            self._signals,
            key=lambda s: s.created_at,
            reverse=True
        )[:limit]
    
    def add_indicator_data(
        self,
        symbol: str,
        indicators: dict[str, float],
    ) -> None:
        """Add indicator data for signal evaluation.
        
        Args:
            symbol: Stock symbol.
            indicators: Dict of indicator name -> value.
        """
        self._indicator_cache[symbol] = indicators
