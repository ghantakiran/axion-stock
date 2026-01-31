"""Grid Trading Bot.

Automated grid trading for range-bound markets.
"""

from datetime import datetime, timezone
from typing import Optional
import logging
import math

from src.bots.config import (
    BotConfig,
    GridConfig,
    GridType,
    TradeSide,
    OrderType,
)
from src.bots.models import BotOrder, GridLevel
from src.bots.base import BaseBot, BrokerInterface

logger = logging.getLogger(__name__)


class GridBot(BaseBot):
    """Grid Trading Bot.
    
    Places buy and sell orders at predefined price levels
    to profit from range-bound market movements.
    
    Features:
    - Arithmetic or geometric grid spacing
    - Configurable grid density
    - Stop-loss and take-profit levels
    - Trailing grid option
    
    Example:
        config = BotConfig(
            bot_id="grid_1",
            name="ETH Grid",
            bot_type=BotType.GRID,
            symbols=["ETH"],
            grid_config=GridConfig(
                symbol="ETH",
                upper_price=2500,
                lower_price=2000,
                num_grids=10,
                total_investment=10000,
            ),
        )
        bot = GridBot(config)
    """
    
    def __init__(
        self,
        config: BotConfig,
        broker: Optional[BrokerInterface] = None,
    ):
        super().__init__(config, broker)
        self.grid_config = config.grid_config or GridConfig()
        
        # Initialize grid levels
        self._levels: list[GridLevel] = []
        self._setup_grid()
        
        # Track grid statistics
        self._total_grid_trades: int = 0
        self._total_grid_profit: float = 0.0
    
    def _setup_grid(self) -> None:
        """Initialize grid levels."""
        gc = self.grid_config
        
        if gc.upper_price <= gc.lower_price:
            logger.error("Upper price must be greater than lower price")
            return
        
        if gc.num_grids < 2:
            logger.error("Need at least 2 grid levels")
            return
        
        self._levels = []
        
        if gc.grid_type == GridType.ARITHMETIC:
            # Equal price spacing
            step = (gc.upper_price - gc.lower_price) / (gc.num_grids - 1)
            for i in range(gc.num_grids):
                price = gc.lower_price + (i * step)
                self._levels.append(GridLevel(
                    bot_id=self.bot_id,
                    price=round(price, 4),
                    level_index=i,
                ))
        else:
            # Geometric (equal percentage spacing)
            ratio = (gc.upper_price / gc.lower_price) ** (1 / (gc.num_grids - 1))
            for i in range(gc.num_grids):
                price = gc.lower_price * (ratio ** i)
                self._levels.append(GridLevel(
                    bot_id=self.bot_id,
                    price=round(price, 4),
                    level_index=i,
                ))
        
        # Calculate amount per grid
        self._amount_per_grid = gc.total_investment / gc.num_grids
        
        logger.info(
            f"Grid initialized: {gc.num_grids} levels from "
            f"${gc.lower_price} to ${gc.upper_price}"
        )
    
    def generate_orders(self, market_data: dict[str, dict]) -> list[BotOrder]:
        """Generate grid orders based on current price.
        
        Args:
            market_data: Current market data.
            
        Returns:
            List of buy/sell orders.
        """
        symbol = self.grid_config.symbol
        if symbol not in market_data:
            logger.warning(f"No market data for {symbol}")
            return []
        
        current_price = market_data[symbol].get("price", 0)
        if current_price <= 0:
            return []
        
        orders = []
        
        # Check stop-loss
        if self.grid_config.stop_loss_price:
            if current_price <= self.grid_config.stop_loss_price:
                logger.warning(f"Stop-loss triggered at ${current_price}")
                # Close all positions
                return self._close_all_positions(current_price)
        
        # Check take-profit
        if self.grid_config.take_profit_price:
            if current_price >= self.grid_config.take_profit_price:
                logger.info(f"Take-profit triggered at ${current_price}")
                return self._close_all_positions(current_price)
        
        # Find relevant grid levels
        for level in self._levels:
            # Check if price crossed this level
            if level.has_position:
                # We have a position at this level, check for sell
                if current_price >= level.price * 1.01:  # Above level + buffer
                    # Sell at this level
                    order = self._create_sell_order(level, current_price)
                    if order:
                        orders.append(order)
            else:
                # No position at this level, check for buy
                if current_price <= level.price * 0.99:  # Below level - buffer
                    # Buy at this level
                    order = self._create_buy_order(level, current_price)
                    if order:
                        orders.append(order)
        
        # Limit orders per execution
        return orders[:3]  # Max 3 orders per execution
    
    def _create_buy_order(
        self,
        level: GridLevel,
        current_price: float,
    ) -> Optional[BotOrder]:
        """Create a buy order for a grid level.
        
        Args:
            level: Grid level.
            current_price: Current market price.
            
        Returns:
            Buy order or None.
        """
        quantity = self._amount_per_grid / current_price
        
        order = BotOrder(
            bot_id=self.bot_id,
            symbol=self.grid_config.symbol,
            side=TradeSide.BUY,
            quantity=round(quantity, 6),
            order_type=OrderType.LIMIT,
            limit_price=level.price,
        )
        
        # Update level state (optimistically)
        level.has_position = True
        level.quantity = quantity
        level.entry_price = level.price
        level.times_bought += 1
        
        logger.info(
            f"Grid buy: Level {level.level_index} @ ${level.price:.2f}, "
            f"qty {quantity:.6f}"
        )
        
        return order
    
    def _create_sell_order(
        self,
        level: GridLevel,
        current_price: float,
    ) -> Optional[BotOrder]:
        """Create a sell order for a grid level.
        
        Args:
            level: Grid level.
            current_price: Current market price.
            
        Returns:
            Sell order or None.
        """
        if level.quantity <= 0:
            return None
        
        # Find next level up to sell at
        next_level_price = self._get_next_level_up(level)
        sell_price = next_level_price or current_price
        
        order = BotOrder(
            bot_id=self.bot_id,
            symbol=self.grid_config.symbol,
            side=TradeSide.SELL,
            quantity=round(level.quantity, 6),
            order_type=OrderType.LIMIT,
            limit_price=sell_price,
        )
        
        # Calculate profit
        if level.entry_price:
            profit = (sell_price - level.entry_price) * level.quantity
            level.total_profit += profit
            self._total_grid_profit += profit
        
        # Update level state
        level.has_position = False
        level.times_sold += 1
        level.quantity = 0
        level.entry_price = None
        
        self._total_grid_trades += 1
        
        logger.info(
            f"Grid sell: Level {level.level_index} @ ${sell_price:.2f}, "
            f"profit ${profit:.2f}"
        )
        
        return order
    
    def _get_next_level_up(self, current_level: GridLevel) -> Optional[float]:
        """Get the price of the next grid level up."""
        current_idx = current_level.level_index
        
        for level in self._levels:
            if level.level_index == current_idx + 1:
                return level.price
        
        return None
    
    def _close_all_positions(self, current_price: float) -> list[BotOrder]:
        """Close all grid positions.
        
        Args:
            current_price: Current market price.
            
        Returns:
            List of sell orders.
        """
        orders = []
        
        for level in self._levels:
            if level.has_position and level.quantity > 0:
                order = BotOrder(
                    bot_id=self.bot_id,
                    symbol=self.grid_config.symbol,
                    side=TradeSide.SELL,
                    quantity=round(level.quantity, 6),
                    order_type=OrderType.MARKET,
                    limit_price=current_price,
                )
                orders.append(order)
                
                level.has_position = False
                level.quantity = 0
        
        return orders
    
    def get_grid_status(self) -> dict:
        """Get current grid status.
        
        Returns:
            Dict with grid statistics.
        """
        positions = [l for l in self._levels if l.has_position]
        total_invested = sum(
            (l.entry_price or 0) * l.quantity
            for l in positions
        )
        
        return {
            "symbol": self.grid_config.symbol,
            "num_levels": len(self._levels),
            "active_positions": len(positions),
            "total_invested": total_invested,
            "total_trades": self._total_grid_trades,
            "total_profit": self._total_grid_profit,
            "grid_range": f"${self.grid_config.lower_price} - ${self.grid_config.upper_price}",
        }
    
    def get_levels(self) -> list[dict]:
        """Get all grid levels with status.
        
        Returns:
            List of level details.
        """
        return [
            {
                "level": l.level_index,
                "price": l.price,
                "has_position": l.has_position,
                "quantity": l.quantity,
                "entry_price": l.entry_price,
                "times_bought": l.times_bought,
                "times_sold": l.times_sold,
                "profit": l.total_profit,
            }
            for l in self._levels
        ]
    
    def reconfigure_grid(
        self,
        upper_price: Optional[float] = None,
        lower_price: Optional[float] = None,
        num_grids: Optional[int] = None,
    ) -> None:
        """Reconfigure the grid.
        
        Args:
            upper_price: New upper price.
            lower_price: New lower price.
            num_grids: New number of grid levels.
        """
        if upper_price:
            self.grid_config.upper_price = upper_price
        if lower_price:
            self.grid_config.lower_price = lower_price
        if num_grids:
            self.grid_config.num_grids = num_grids
        
        self._setup_grid()
        logger.info("Grid reconfigured")
