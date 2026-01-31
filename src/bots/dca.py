"""DCA (Dollar-Cost Averaging) Bot.

Automated recurring investment bot.
"""

from datetime import datetime, timezone
from typing import Optional
import logging

from src.bots.config import BotConfig, DCAConfig, TradeSide, OrderType
from src.bots.models import BotOrder
from src.bots.base import BaseBot, BrokerInterface

logger = logging.getLogger(__name__)


class DCABot(BaseBot):
    """Dollar-Cost Averaging Bot.
    
    Executes recurring purchases according to a schedule
    and allocation strategy.
    
    Features:
    - Fixed amount per period
    - Multi-asset allocation
    - Dip buying enhancement
    - Skip conditions
    
    Example:
        config = BotConfig(
            bot_id="dca_1",
            name="Monthly S&P 500",
            bot_type=BotType.DCA,
            symbols=["SPY"],
            dca_config=DCAConfig(
                amount_per_period=500,
                allocations={"SPY": 1.0},
            ),
        )
        bot = DCABot(config)
        execution = bot.execute({"SPY": {"price": 450.0}})
    """
    
    def __init__(
        self,
        config: BotConfig,
        broker: Optional[BrokerInterface] = None,
    ):
        super().__init__(config, broker)
        self.dca_config = config.dca_config or DCAConfig()
        
        # Track historical prices for dip detection
        self._price_history: dict[str, list[float]] = {}
        self._last_execution_date: Optional[datetime] = None
    
    def generate_orders(self, market_data: dict[str, dict]) -> list[BotOrder]:
        """Generate DCA buy orders.
        
        Args:
            market_data: Current market prices.
            
        Returns:
            List of buy orders.
        """
        orders = []
        amount = self.dca_config.amount_per_period
        allocations = self.dca_config.allocations
        
        # Check for dip buying
        if self.dca_config.increase_on_dip:
            dip_multiplier = self._check_dip(market_data)
            if dip_multiplier > 1.0:
                increase = self.dca_config.dip_increase_pct / 100
                amount = amount * (1 + increase * (dip_multiplier - 1))
                logger.info(f"Dip detected, increasing investment to ${amount:.2f}")
        
        for symbol, allocation in allocations.items():
            if symbol not in market_data:
                logger.warning(f"No market data for {symbol}")
                continue
            
            price = market_data[symbol].get("price", 0)
            if price <= 0:
                continue
            
            # Check skip condition
            if self.dca_config.skip_if_price_above:
                if price > self.dca_config.skip_if_price_above:
                    logger.info(f"Skipping {symbol}: price ${price} above threshold")
                    continue
            
            # Calculate investment amount for this symbol
            symbol_amount = amount * allocation
            quantity = symbol_amount / price
            
            # Round to reasonable precision
            quantity = round(quantity, 4)
            
            if quantity > 0:
                order = BotOrder(
                    bot_id=self.bot_id,
                    symbol=symbol,
                    side=TradeSide.BUY,
                    quantity=quantity,
                    order_type=OrderType.MARKET,
                    limit_price=price,
                )
                orders.append(order)
                
                logger.info(
                    f"DCA order: {symbol} {quantity:.4f} shares @ ${price:.2f} "
                    f"(${symbol_amount:.2f})"
                )
        
        # Update price history
        self._update_price_history(market_data)
        self._last_execution_date = datetime.now(timezone.utc)
        
        return orders
    
    def _check_dip(self, market_data: dict[str, dict]) -> float:
        """Check if prices are in a dip.
        
        Returns:
            Multiplier > 1 if dip detected, 1.0 otherwise.
        """
        if not self._price_history:
            return 1.0
        
        threshold = self.dca_config.dip_threshold_pct / 100
        max_dip = 0.0
        
        for symbol, data in market_data.items():
            current_price = data.get("price", 0)
            history = self._price_history.get(symbol, [])
            
            if history and current_price > 0:
                avg_price = sum(history) / len(history)
                dip_pct = (avg_price - current_price) / avg_price
                
                if dip_pct > threshold:
                    max_dip = max(max_dip, dip_pct)
        
        if max_dip > 0:
            # Scale from 1.0 to 2.0 based on dip magnitude
            return 1.0 + min(max_dip / threshold, 1.0)
        
        return 1.0
    
    def _update_price_history(self, market_data: dict[str, dict]) -> None:
        """Update price history for dip detection."""
        max_history = 20  # Keep last 20 prices
        
        for symbol, data in market_data.items():
            price = data.get("price", 0)
            if price > 0:
                if symbol not in self._price_history:
                    self._price_history[symbol] = []
                
                self._price_history[symbol].append(price)
                
                # Trim to max history
                if len(self._price_history[symbol]) > max_history:
                    self._price_history[symbol] = self._price_history[symbol][-max_history:]
    
    def get_next_investment_amount(self, market_data: dict[str, dict]) -> float:
        """Preview the next investment amount.
        
        Args:
            market_data: Current market data.
            
        Returns:
            Investment amount in dollars.
        """
        amount = self.dca_config.amount_per_period
        
        if self.dca_config.increase_on_dip:
            dip_multiplier = self._check_dip(market_data)
            if dip_multiplier > 1.0:
                increase = self.dca_config.dip_increase_pct / 100
                amount = amount * (1 + increase * (dip_multiplier - 1))
        
        return amount
    
    def get_allocation_preview(
        self,
        market_data: dict[str, dict],
    ) -> list[dict]:
        """Preview the next DCA allocation.
        
        Args:
            market_data: Current market data.
            
        Returns:
            List of allocation details.
        """
        amount = self.get_next_investment_amount(market_data)
        preview = []
        
        for symbol, allocation in self.dca_config.allocations.items():
            price = market_data.get(symbol, {}).get("price", 0)
            symbol_amount = amount * allocation
            shares = symbol_amount / price if price > 0 else 0
            
            preview.append({
                "symbol": symbol,
                "allocation_pct": allocation * 100,
                "amount": symbol_amount,
                "price": price,
                "shares": shares,
            })
        
        return preview
