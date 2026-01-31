"""Screen Alert Manager.

Monitors screens and triggers alerts when conditions are met.
"""

from datetime import datetime, timezone
from typing import Optional
import logging

from src.screener.config import AlertType
from src.screener.models import (
    Screen,
    ScreenAlert,
    AlertNotification,
    ScreenResult,
)
from src.screener.engine import ScreenerEngine

logger = logging.getLogger(__name__)


class ScreenAlertManager:
    """Manages screen alerts.
    
    Monitors screens and triggers alerts when:
    - Stocks enter/exit screen criteria
    - Match count crosses thresholds
    - Scheduled runs complete
    
    Example:
        manager = ScreenAlertManager(engine)
        manager.add_alert(screen_id, AlertType.ENTRY)
        notifications = manager.check_alerts(stock_data)
    """
    
    def __init__(self, engine: Optional[ScreenerEngine] = None):
        self.engine = engine or ScreenerEngine()
        self._alerts: dict[str, ScreenAlert] = {}
        self._screens: dict[str, Screen] = {}
        self._last_results: dict[str, set[str]] = {}  # screen_id -> set of symbols
    
    def add_alert(
        self,
        screen: Screen,
        alert_type: AlertType = AlertType.ENTRY,
        notify_on_entry: bool = True,
        notify_on_exit: bool = False,
        channels: list[str] = None,
        count_threshold: int = None,
    ) -> ScreenAlert:
        """Add an alert for a screen.
        
        Args:
            screen: Screen to monitor.
            alert_type: Type of alert.
            notify_on_entry: Notify when stocks enter screen.
            notify_on_exit: Notify when stocks exit screen.
            channels: Delivery channels.
            count_threshold: For count alerts.
            
        Returns:
            Created ScreenAlert.
        """
        alert = ScreenAlert(
            screen_id=screen.screen_id,
            alert_type=alert_type,
            notify_on_entry=notify_on_entry,
            notify_on_exit=notify_on_exit,
            channels=channels or ["push"],
            count_threshold=count_threshold,
        )
        
        self._alerts[alert.alert_id] = alert
        self._screens[screen.screen_id] = screen
        self._last_results[screen.screen_id] = set()
        
        return alert
    
    def remove_alert(self, alert_id: str) -> bool:
        """Remove an alert.
        
        Returns:
            True if removed, False if not found.
        """
        if alert_id in self._alerts:
            del self._alerts[alert_id]
            return True
        return False
    
    def enable_alert(self, alert_id: str) -> bool:
        """Enable an alert."""
        if alert_id in self._alerts:
            self._alerts[alert_id].enabled = True
            return True
        return False
    
    def disable_alert(self, alert_id: str) -> bool:
        """Disable an alert."""
        if alert_id in self._alerts:
            self._alerts[alert_id].enabled = False
            return True
        return False
    
    def get_alert(self, alert_id: str) -> Optional[ScreenAlert]:
        """Get an alert by ID."""
        return self._alerts.get(alert_id)
    
    def get_alerts_for_screen(self, screen_id: str) -> list[ScreenAlert]:
        """Get all alerts for a screen."""
        return [a for a in self._alerts.values() if a.screen_id == screen_id]
    
    def check_alerts(
        self,
        stock_data: dict[str, dict],
    ) -> list[AlertNotification]:
        """Check all alerts and return triggered notifications.
        
        Args:
            stock_data: Current stock data.
            
        Returns:
            List of triggered AlertNotifications.
        """
        notifications = []
        
        for alert in self._alerts.values():
            if not alert.enabled:
                continue
            
            screen = self._screens.get(alert.screen_id)
            if not screen:
                continue
            
            # Run the screen
            result = self.engine.run_screen(screen, stock_data)
            current_symbols = {m.symbol for m in result.stocks}
            
            # Get previous results
            previous_symbols = self._last_results.get(alert.screen_id, set())
            
            # Check for entry/exit
            notification = self._check_alert(
                alert, screen, result, current_symbols, previous_symbols
            )
            
            if notification:
                notifications.append(notification)
            
            # Update last results
            self._last_results[alert.screen_id] = current_symbols
            alert.last_run = datetime.now(timezone.utc)
            alert.last_matches = list(current_symbols)
        
        return notifications
    
    def _check_alert(
        self,
        alert: ScreenAlert,
        screen: Screen,
        result: ScreenResult,
        current_symbols: set[str],
        previous_symbols: set[str],
    ) -> Optional[AlertNotification]:
        """Check if an alert should be triggered.
        
        Returns:
            AlertNotification if triggered, None otherwise.
        """
        entered = current_symbols - previous_symbols
        exited = previous_symbols - current_symbols
        
        should_notify = False
        trigger_type = ""
        
        if alert.alert_type == AlertType.ENTRY:
            # Notify on entry
            if alert.notify_on_entry and entered:
                should_notify = True
                trigger_type = "entry"
            # Notify on exit
            if alert.notify_on_exit and exited:
                should_notify = True
                trigger_type = "exit" if not entered else "entry_exit"
        
        elif alert.alert_type == AlertType.EXIT:
            if exited:
                should_notify = True
                trigger_type = "exit"
        
        elif alert.alert_type == AlertType.COUNT:
            if alert.count_threshold:
                current_count = len(current_symbols)
                if alert.count_direction == "above" and current_count >= alert.count_threshold:
                    should_notify = True
                    trigger_type = "count_above"
                elif alert.count_direction == "below" and current_count <= alert.count_threshold:
                    should_notify = True
                    trigger_type = "count_below"
        
        if should_notify:
            return AlertNotification(
                alert_id=alert.alert_id,
                screen_id=screen.screen_id,
                screen_name=screen.name,
                trigger_type=trigger_type,
                entered_stocks=list(entered),
                exited_stocks=list(exited),
                current_count=len(current_symbols),
            )
        
        return None
    
    def get_alert_summary(self) -> dict:
        """Get summary of all alerts.
        
        Returns:
            Dict with alert statistics.
        """
        total = len(self._alerts)
        enabled = sum(1 for a in self._alerts.values() if a.enabled)
        
        by_type = {}
        for a in self._alerts.values():
            by_type[a.alert_type.value] = by_type.get(a.alert_type.value, 0) + 1
        
        return {
            "total_alerts": total,
            "enabled": enabled,
            "disabled": total - enabled,
            "by_type": by_type,
        }
