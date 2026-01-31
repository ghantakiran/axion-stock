"""Bot Scheduler.

Manages scheduling and execution timing for trading bots.
"""

from dataclasses import dataclass, field
from datetime import datetime, date, time, timedelta, timezone
from typing import Optional, Callable
import logging
import heapq

from src.bots.config import (
    BotConfig,
    ScheduleConfig,
    ScheduleFrequency,
    ExecutionTime,
    GlobalBotSettings,
    DEFAULT_GLOBAL_SETTINGS,
)
from src.bots.models import ScheduledRun, BotExecution

logger = logging.getLogger(__name__)


# US market holidays (simplified list)
US_HOLIDAYS_2024_2026 = [
    date(2024, 1, 1),   # New Year's Day
    date(2024, 1, 15),  # MLK Day
    date(2024, 2, 19),  # Presidents Day
    date(2024, 3, 29),  # Good Friday
    date(2024, 5, 27),  # Memorial Day
    date(2024, 6, 19),  # Juneteenth
    date(2024, 7, 4),   # Independence Day
    date(2024, 9, 2),   # Labor Day
    date(2024, 11, 28), # Thanksgiving
    date(2024, 12, 25), # Christmas
    date(2025, 1, 1),
    date(2025, 1, 20),
    date(2025, 2, 17),
    date(2025, 4, 18),
    date(2025, 5, 26),
    date(2025, 6, 19),
    date(2025, 7, 4),
    date(2025, 9, 1),
    date(2025, 11, 27),
    date(2025, 12, 25),
    date(2026, 1, 1),
    date(2026, 1, 19),
    date(2026, 2, 16),
    date(2026, 4, 3),
    date(2026, 5, 25),
    date(2026, 6, 19),
    date(2026, 7, 3),
    date(2026, 9, 7),
    date(2026, 11, 26),
    date(2026, 12, 25),
]


class BotScheduler:
    """Manages bot execution schedules.
    
    Features:
    - Schedule bots based on configuration
    - Calculate next run times
    - Handle market hours and holidays
    - Support multiple frequency options
    
    Example:
        scheduler = BotScheduler()
        scheduler.schedule_bot(bot_config)
        
        # Get due bots
        due = scheduler.get_due_runs()
        for run in due:
            bot.execute()
            scheduler.mark_completed(run.schedule_id)
    """
    
    def __init__(self, settings: Optional[GlobalBotSettings] = None):
        self.settings = settings or DEFAULT_GLOBAL_SETTINGS
        
        # Priority queue of scheduled runs (by scheduled_time, counter, run)
        # Counter ensures unique ordering when times are equal
        self._schedule_heap: list[tuple[datetime, int, ScheduledRun]] = []
        self._counter: int = 0
        
        # Bot configurations
        self._bot_configs: dict[str, BotConfig] = {}
        
        # Execution callbacks
        self._on_run_due: Optional[Callable[[ScheduledRun], None]] = None
    
    def schedule_bot(self, config: BotConfig) -> Optional[ScheduledRun]:
        """Add a bot to the schedule.
        
        Args:
            config: Bot configuration.
            
        Returns:
            The scheduled run or None if scheduling failed.
        """
        self._bot_configs[config.bot_id] = config
        
        next_time = self.calculate_next_run(config)
        if not next_time:
            logger.warning(f"Could not calculate next run for bot {config.name}")
            return None
        
        run = ScheduledRun(
            bot_id=config.bot_id,
            bot_name=config.name,
            scheduled_time=next_time,
            status="pending",
        )
        
        self._counter += 1
        heapq.heappush(self._schedule_heap, (next_time, self._counter, run))
        
        logger.info(f"Scheduled bot '{config.name}' for {next_time}")
        return run
    
    def unschedule_bot(self, bot_id: str) -> None:
        """Remove a bot from the schedule.
        
        Args:
            bot_id: Bot to remove.
        """
        self._schedule_heap = [
            (t, c, r) for t, c, r in self._schedule_heap
            if r.bot_id != bot_id
        ]
        heapq.heapify(self._schedule_heap)
        
        if bot_id in self._bot_configs:
            del self._bot_configs[bot_id]
    
    def calculate_next_run(
        self,
        config: BotConfig,
        after: Optional[datetime] = None,
    ) -> Optional[datetime]:
        """Calculate the next run time for a bot.
        
        Args:
            config: Bot configuration.
            after: Calculate next run after this time.
            
        Returns:
            Next run datetime or None.
        """
        schedule = config.schedule
        now = after or datetime.now(timezone.utc)
        
        # Get base time from frequency
        next_date = self._get_next_date(schedule, now.date())
        
        # Get time of day
        run_time = self._get_execution_time(schedule)
        
        # Combine date and time
        next_run = datetime.combine(next_date, run_time, tzinfo=timezone.utc)
        
        # If it's in the past, move to next period
        if next_run <= now:
            next_date = self._get_next_date(schedule, next_date + timedelta(days=1))
            next_run = datetime.combine(next_date, run_time, tzinfo=timezone.utc)
        
        # Skip weekends and holidays if configured
        while True:
            if schedule.skip_weekends and next_run.weekday() >= 5:
                next_run += timedelta(days=1)
                continue
            if schedule.skip_holidays and next_run.date() in US_HOLIDAYS_2024_2026:
                next_run += timedelta(days=1)
                continue
            break
        
        return next_run
    
    def _get_next_date(
        self,
        schedule: ScheduleConfig,
        after_date: date,
    ) -> date:
        """Get the next run date based on frequency.
        
        Args:
            schedule: Schedule configuration.
            after_date: Date to search from.
            
        Returns:
            Next run date.
        """
        freq = schedule.frequency
        
        if freq == ScheduleFrequency.HOURLY:
            return after_date
        
        elif freq == ScheduleFrequency.DAILY:
            return after_date
        
        elif freq == ScheduleFrequency.WEEKLY:
            target_day = schedule.day_of_week or 0  # Default Monday
            days_ahead = target_day - after_date.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            return after_date + timedelta(days=days_ahead)
        
        elif freq == ScheduleFrequency.BIWEEKLY:
            target_day = schedule.day_of_week or 0
            days_ahead = target_day - after_date.weekday()
            if days_ahead <= 0:
                days_ahead += 14
            return after_date + timedelta(days=days_ahead)
        
        elif freq == ScheduleFrequency.MONTHLY:
            target_day = min(schedule.day_of_month or 1, 28)
            
            if after_date.day <= target_day:
                return after_date.replace(day=target_day)
            else:
                # Move to next month
                if after_date.month == 12:
                    return date(after_date.year + 1, 1, target_day)
                else:
                    return date(after_date.year, after_date.month + 1, target_day)
        
        elif freq == ScheduleFrequency.QUARTERLY:
            # First day of next quarter
            quarter_months = [1, 4, 7, 10]
            current_quarter = (after_date.month - 1) // 3
            next_quarter = (current_quarter + 1) % 4
            next_quarter_month = quarter_months[next_quarter]
            
            if next_quarter == 0:
                return date(after_date.year + 1, next_quarter_month, 1)
            else:
                return date(after_date.year, next_quarter_month, 1)
        
        return after_date
    
    def _get_execution_time(self, schedule: ScheduleConfig) -> time:
        """Get execution time from schedule config.
        
        Args:
            schedule: Schedule configuration.
            
        Returns:
            Time of day to execute.
        """
        exec_time = schedule.execution_time
        
        if exec_time == ExecutionTime.MARKET_OPEN:
            return time(9, 30)  # NYSE open
        elif exec_time == ExecutionTime.MARKET_CLOSE:
            return time(15, 55)  # 5 min before close
        elif exec_time == ExecutionTime.MIDDAY:
            return time(12, 0)
        elif exec_time == ExecutionTime.CUSTOM and schedule.custom_time:
            parts = schedule.custom_time.split(":")
            return time(int(parts[0]), int(parts[1]))
        
        return time(9, 30)  # Default market open
    
    def get_due_runs(
        self,
        as_of: Optional[datetime] = None,
    ) -> list[ScheduledRun]:
        """Get all runs that are due for execution.
        
        Args:
            as_of: Check runs due as of this time.
            
        Returns:
            List of due scheduled runs.
        """
        now = as_of or datetime.now(timezone.utc)
        due_runs = []
        
        while self._schedule_heap:
            scheduled_time, _, run = self._schedule_heap[0]
            
            if scheduled_time <= now:
                heapq.heappop(self._schedule_heap)
                
                if run.status == "pending":
                    run.status = "running"
                    due_runs.append(run)
            else:
                break
        
        return due_runs
    
    def mark_completed(
        self,
        schedule_id: str,
        execution: Optional[BotExecution] = None,
    ) -> None:
        """Mark a scheduled run as completed and reschedule.
        
        Args:
            schedule_id: Schedule to mark.
            execution: Execution result.
        """
        # Find and update the run
        for i, (_, _, run) in enumerate(self._schedule_heap):
            if run.schedule_id == schedule_id:
                run.status = "completed"
                if execution:
                    run.execution_id = execution.execution_id
                break
        
        # Reschedule if bot config exists
        for run in self.get_upcoming_runs(limit=100):
            if run.schedule_id == schedule_id:
                bot_config = self._bot_configs.get(run.bot_id)
                if bot_config and bot_config.enabled:
                    self.schedule_bot(bot_config)
                break
    
    def mark_missed(self, schedule_id: str, reason: str = "") -> None:
        """Mark a scheduled run as missed.
        
        Args:
            schedule_id: Schedule to mark.
            reason: Why it was missed.
        """
        for _, _, run in self._schedule_heap:
            if run.schedule_id == schedule_id:
                run.status = "missed"
                break
    
    def get_upcoming_runs(
        self,
        limit: int = 10,
        bot_id: Optional[str] = None,
    ) -> list[ScheduledRun]:
        """Get upcoming scheduled runs.
        
        Args:
            limit: Maximum runs to return.
            bot_id: Filter by bot.
            
        Returns:
            List of upcoming runs.
        """
        runs = [run for _, _, run in self._schedule_heap if run.status == "pending"]
        
        if bot_id:
            runs = [r for r in runs if r.bot_id == bot_id]
        
        runs.sort(key=lambda r: r.scheduled_time)
        return runs[:limit]
    
    def get_next_run(self, bot_id: str) -> Optional[datetime]:
        """Get next run time for a bot.
        
        Args:
            bot_id: Bot ID.
            
        Returns:
            Next scheduled time or None.
        """
        for scheduled_time, _, run in self._schedule_heap:
            if run.bot_id == bot_id and run.status == "pending":
                return scheduled_time
        return None
    
    def is_trading_hours(self, dt: Optional[datetime] = None) -> bool:
        """Check if given time is during trading hours.
        
        Args:
            dt: Datetime to check (default: now).
            
        Returns:
            True if during trading hours.
        """
        dt = dt or datetime.now(timezone.utc)
        
        # Skip weekends
        if dt.weekday() >= 5:
            return False
        
        # Skip holidays
        if dt.date() in US_HOLIDAYS_2024_2026:
            return False
        
        # Check time (assuming UTC-5 for EST)
        # Market hours: 9:30 - 16:00 ET
        start_hour, start_min = map(int, self.settings.allowed_hours_start.split(":"))
        end_hour, end_min = map(int, self.settings.allowed_hours_end.split(":"))
        
        market_open = time(start_hour, start_min)
        market_close = time(end_hour, end_min)
        
        current_time = dt.time()
        return market_open <= current_time <= market_close
    
    def on_run_due(self, callback: Callable[[ScheduledRun], None]) -> None:
        """Register callback for when runs are due."""
        self._on_run_due = callback
