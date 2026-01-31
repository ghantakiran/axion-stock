"""Bot Execution Engine.

Central manager for all trading bots.
"""

from datetime import datetime, timezone
from typing import Optional, Callable, Type
import logging

from src.bots.config import (
    BotConfig,
    BotType,
    BotStatus,
    GlobalBotSettings,
    DEFAULT_GLOBAL_SETTINGS,
)
from src.bots.models import (
    BotExecution,
    BotOrder,
    BotPerformance,
    BotSummary,
)
from src.bots.base import BaseBot, BrokerInterface
from src.bots.dca import DCABot
from src.bots.rebalance import RebalanceBot
from src.bots.signal import SignalBot
from src.bots.grid import GridBot
from src.bots.scheduler import BotScheduler

logger = logging.getLogger(__name__)


# Bot type registry
BOT_CLASSES: dict[BotType, Type[BaseBot]] = {
    BotType.DCA: DCABot,
    BotType.REBALANCE: RebalanceBot,
    BotType.SIGNAL: SignalBot,
    BotType.GRID: GridBot,
    BotType.MEAN_REVERSION: SignalBot,  # Uses signal bot with RSI config
    BotType.MOMENTUM: SignalBot,  # Uses signal bot with momentum config
}


class BotEngine:
    """Central bot management engine.
    
    Features:
    - Create and manage multiple bots
    - Schedule and execute bots
    - Monitor performance
    - Apply global risk controls
    
    Example:
        engine = BotEngine()
        
        # Create a DCA bot
        config = BotConfig(
            name="Weekly SPY",
            bot_type=BotType.DCA,
            symbols=["SPY"],
            dca_config=DCAConfig(amount_per_period=100),
        )
        bot = engine.create_bot(config)
        
        # Run scheduled bots
        engine.run_due_bots()
    """
    
    def __init__(
        self,
        broker: Optional[BrokerInterface] = None,
        settings: Optional[GlobalBotSettings] = None,
    ):
        self.broker = broker
        self.settings = settings or DEFAULT_GLOBAL_SETTINGS
        
        # Bot storage
        self._bots: dict[str, BaseBot] = {}
        self._configs: dict[str, BotConfig] = {}
        
        # Scheduler
        self.scheduler = BotScheduler(self.settings)
        
        # Execution history
        self._executions: list[BotExecution] = []
        
        # Callbacks
        self._on_execution: Optional[Callable[[BotExecution], None]] = None
        self._on_order: Optional[Callable[[BotOrder], None]] = None
        
        # Global state
        self._total_orders_today: int = 0
        self._last_reset_date: Optional[datetime] = None
    
    def create_bot(self, config: BotConfig) -> BaseBot:
        """Create and register a new bot.
        
        Args:
            config: Bot configuration.
            
        Returns:
            The created bot instance.
        """
        # Generate ID if not provided
        if not config.bot_id:
            config.bot_id = f"{config.bot_type.value}_{len(self._bots) + 1}"
        
        # Get bot class
        bot_class = BOT_CLASSES.get(config.bot_type)
        if not bot_class:
            raise ValueError(f"Unknown bot type: {config.bot_type}")
        
        # Create bot instance
        bot = bot_class(config, self.broker)
        
        # Register callbacks
        bot.on_execution_complete(self._handle_execution)
        bot.on_order_filled(self._handle_order)
        
        # Store bot
        self._bots[config.bot_id] = bot
        self._configs[config.bot_id] = config
        
        # Schedule if enabled
        if config.enabled:
            self.scheduler.schedule_bot(config)
        
        logger.info(f"Created bot '{config.name}' ({config.bot_type.value})")
        return bot
    
    def get_bot(self, bot_id: str) -> Optional[BaseBot]:
        """Get a bot by ID."""
        return self._bots.get(bot_id)
    
    def get_all_bots(self) -> list[BaseBot]:
        """Get all registered bots."""
        return list(self._bots.values())
    
    def delete_bot(self, bot_id: str) -> bool:
        """Delete a bot.
        
        Args:
            bot_id: Bot to delete.
            
        Returns:
            True if deleted.
        """
        if bot_id not in self._bots:
            return False
        
        # Stop and remove
        self._bots[bot_id].stop()
        self.scheduler.unschedule_bot(bot_id)
        
        del self._bots[bot_id]
        del self._configs[bot_id]
        
        logger.info(f"Deleted bot {bot_id}")
        return True
    
    def start_bot(self, bot_id: str) -> bool:
        """Start a paused bot."""
        bot = self._bots.get(bot_id)
        if not bot:
            return False
        
        bot.resume()
        
        config = self._configs.get(bot_id)
        if config:
            self.scheduler.schedule_bot(config)
        
        return True
    
    def stop_bot(self, bot_id: str) -> bool:
        """Stop a running bot."""
        bot = self._bots.get(bot_id)
        if not bot:
            return False
        
        bot.stop()
        self.scheduler.unschedule_bot(bot_id)
        
        return True
    
    def pause_bot(self, bot_id: str) -> bool:
        """Pause a bot."""
        bot = self._bots.get(bot_id)
        if not bot:
            return False
        
        bot.pause()
        return True
    
    def run_bot(
        self,
        bot_id: str,
        market_data: Optional[dict[str, dict]] = None,
    ) -> Optional[BotExecution]:
        """Manually run a bot.
        
        Args:
            bot_id: Bot to run.
            market_data: Market data (optional).
            
        Returns:
            Execution result or None.
        """
        bot = self._bots.get(bot_id)
        if not bot:
            logger.error(f"Bot {bot_id} not found")
            return None
        
        # Check global settings
        if self.settings.emergency_stop_all:
            logger.warning("Emergency stop is active, not running bot")
            return None
        
        # Check trading hours
        if not self.settings.paper_mode and not self.scheduler.is_trading_hours():
            logger.warning("Outside trading hours")
            return None
        
        return bot.execute(market_data, trigger_reason="manual")
    
    def run_due_bots(
        self,
        market_data: Optional[dict[str, dict]] = None,
    ) -> list[BotExecution]:
        """Run all bots that are due.
        
        Args:
            market_data: Market data for all symbols.
            
        Returns:
            List of executions.
        """
        self._reset_daily_counters()
        
        # Check global emergency stop
        if self.settings.emergency_stop_all:
            logger.warning("Emergency stop is active")
            return []
        
        # Get due runs
        due_runs = self.scheduler.get_due_runs()
        executions = []
        
        for run in due_runs:
            bot = self._bots.get(run.bot_id)
            if not bot:
                self.scheduler.mark_missed(run.schedule_id, "Bot not found")
                continue
            
            if not bot.is_active:
                self.scheduler.mark_missed(run.schedule_id, "Bot not active")
                continue
            
            # Check concurrent order limit
            if self._total_orders_today >= self.settings.max_concurrent_orders:
                self.scheduler.mark_missed(run.schedule_id, "Order limit reached")
                continue
            
            # Execute bot
            execution = bot.execute(market_data, trigger_reason="scheduled")
            executions.append(execution)
            
            # Mark completed and reschedule
            self.scheduler.mark_completed(run.schedule_id, execution)
        
        return executions
    
    def _handle_execution(self, execution: BotExecution) -> None:
        """Handle execution completion."""
        self._executions.append(execution)
        self._total_orders_today += execution.orders_placed
        
        if self._on_execution:
            self._on_execution(execution)
        
        logger.info(
            f"Bot '{execution.bot_name}' executed: "
            f"{execution.orders_placed} orders, ${execution.total_value:.2f}"
        )
    
    def _handle_order(self, order: BotOrder) -> None:
        """Handle order fill."""
        if self._on_order:
            self._on_order(order)
    
    def _reset_daily_counters(self) -> None:
        """Reset daily counters if new day."""
        now = datetime.now(timezone.utc)
        
        if (self._last_reset_date is None or
            self._last_reset_date.date() != now.date()):
            self._total_orders_today = 0
            self._last_reset_date = now
    
    def get_executions(
        self,
        bot_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[BotExecution]:
        """Get recent executions.
        
        Args:
            bot_id: Filter by bot.
            limit: Maximum results.
            
        Returns:
            List of executions.
        """
        execs = self._executions.copy()
        
        if bot_id:
            execs = [e for e in execs if e.bot_id == bot_id]
        
        execs.sort(key=lambda e: e.created_at, reverse=True)
        return execs[:limit]
    
    def get_performance(self, bot_id: str) -> Optional[BotPerformance]:
        """Get performance metrics for a bot."""
        bot = self._bots.get(bot_id)
        if bot:
            return bot.get_performance()
        return None
    
    def get_all_performance(self) -> dict[str, BotPerformance]:
        """Get performance for all bots."""
        return {
            bot_id: bot.get_performance()
            for bot_id, bot in self._bots.items()
        }
    
    def get_summaries(self) -> list[BotSummary]:
        """Get summary of all bots.
        
        Returns:
            List of bot summaries.
        """
        summaries = []
        
        for bot_id, bot in self._bots.items():
            config = self._configs.get(bot_id)
            perf = bot.get_performance()
            
            summary = BotSummary(
                bot_id=bot_id,
                name=bot.name,
                bot_type=bot.bot_type,
                status=bot.status,
                symbols=config.symbols if config else [],
                last_run=bot._executions[-1].completed_at if bot._executions else None,
                next_run=self.scheduler.get_next_run(bot_id),
                total_executions=perf.num_executions,
                total_invested=perf.total_invested,
                current_value=perf.current_value,
                total_pnl=perf.total_pnl,
                total_return_pct=perf.total_return_pct,
            )
            summaries.append(summary)
        
        return summaries
    
    def emergency_stop(self) -> None:
        """Emergency stop all bots."""
        self.settings.emergency_stop_all = True
        
        for bot in self._bots.values():
            bot.stop()
        
        logger.warning("EMERGENCY STOP: All bots stopped")
    
    def resume_all(self) -> None:
        """Resume all bots after emergency stop."""
        self.settings.emergency_stop_all = False
        
        for bot_id, config in self._configs.items():
            if config.enabled:
                self._bots[bot_id].resume()
                self.scheduler.schedule_bot(config)
        
        logger.info("All bots resumed")
    
    def on_execution(self, callback: Callable[[BotExecution], None]) -> None:
        """Register execution callback."""
        self._on_execution = callback
    
    def on_order(self, callback: Callable[[BotOrder], None]) -> None:
        """Register order callback."""
        self._on_order = callback
