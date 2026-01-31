"""Economic Event Alerts.

Alert system for economic calendar events.
"""

from datetime import datetime, date, timedelta, timezone
from typing import Optional, Callable
import logging
import re

from src.economic.config import (
    ImpactLevel,
    EventCategory,
    Country,
    AlertTrigger,
    DEFAULT_ALERT_MINUTES,
    DEFAULT_SURPRISE_THRESHOLD,
)
from src.economic.models import (
    EconomicEvent,
    EventAlert,
    AlertNotification,
)

logger = logging.getLogger(__name__)


class EconomicAlertManager:
    """Manages alerts for economic events.
    
    Example:
        manager = EconomicAlertManager()
        
        # Create alert for high-impact events
        alert = EventAlert(
            name="High Impact Alert",
            min_impact=ImpactLevel.HIGH,
            minutes_before=30,
            on_release=True,
        )
        manager.add_alert(alert)
        
        # Check for alerts
        notifications = manager.check_alerts(events)
    """
    
    def __init__(self):
        self._alerts: dict[str, EventAlert] = {}
        self._notifications: list[AlertNotification] = []
        self._subscribers: list[Callable[[AlertNotification], None]] = []
    
    def subscribe(self, callback: Callable[[AlertNotification], None]) -> None:
        """Subscribe to alert notifications."""
        self._subscribers.append(callback)
    
    def _notify(self, notification: AlertNotification) -> None:
        """Notify subscribers."""
        for callback in self._subscribers:
            try:
                callback(notification)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")
    
    # =========================================================================
    # Alert CRUD
    # =========================================================================
    
    def add_alert(self, alert: EventAlert) -> None:
        """Add an alert."""
        self._alerts[alert.alert_id] = alert
    
    def get_alert(self, alert_id: str) -> Optional[EventAlert]:
        """Get alert by ID."""
        return self._alerts.get(alert_id)
    
    def update_alert(self, alert: EventAlert) -> None:
        """Update an alert."""
        if alert.alert_id in self._alerts:
            self._alerts[alert.alert_id] = alert
    
    def delete_alert(self, alert_id: str) -> bool:
        """Delete an alert."""
        if alert_id in self._alerts:
            del self._alerts[alert_id]
            return True
        return False
    
    def get_all_alerts(self) -> list[EventAlert]:
        """Get all alerts."""
        return list(self._alerts.values())
    
    def get_active_alerts(self) -> list[EventAlert]:
        """Get active alerts."""
        return [a for a in self._alerts.values() if a.is_active]
    
    def toggle_alert(self, alert_id: str) -> bool:
        """Toggle alert active state."""
        alert = self._alerts.get(alert_id)
        if alert:
            alert.is_active = not alert.is_active
            return alert.is_active
        return False
    
    # =========================================================================
    # Alert Checking
    # =========================================================================
    
    def check_alerts(
        self,
        events: list[EconomicEvent],
        current_time: Optional[datetime] = None,
    ) -> list[AlertNotification]:
        """Check events against alerts.
        
        Args:
            events: List of economic events.
            current_time: Current time (defaults to now).
            
        Returns:
            List of triggered notifications.
        """
        if current_time is None:
            current_time = datetime.now(timezone.utc)
        
        notifications = []
        
        for alert in self.get_active_alerts():
            for event in events:
                if self._matches_alert(alert, event):
                    notification = self._check_triggers(alert, event, current_time)
                    if notification:
                        notifications.append(notification)
                        self._notifications.append(notification)
                        self._notify(notification)
        
        return notifications
    
    def _matches_alert(self, alert: EventAlert, event: EconomicEvent) -> bool:
        """Check if event matches alert criteria."""
        # Check event pattern
        if alert.event_pattern:
            pattern = alert.event_pattern.replace("*", ".*")
            if not re.match(pattern, event.name, re.IGNORECASE):
                return False
        
        # Check categories
        if alert.categories and event.category not in alert.categories:
            return False
        
        # Check countries
        if alert.countries and event.country not in alert.countries:
            return False
        
        # Check impact level
        impact_order = {
            ImpactLevel.LOW: 0,
            ImpactLevel.MEDIUM: 1,
            ImpactLevel.HIGH: 2,
        }
        if impact_order.get(event.impact, 0) < impact_order.get(alert.min_impact, 0):
            return False
        
        return True
    
    def _check_triggers(
        self,
        alert: EventAlert,
        event: EconomicEvent,
        current_time: datetime,
    ) -> Optional[AlertNotification]:
        """Check if alert should trigger."""
        
        if alert.trigger_type == AlertTrigger.UPCOMING:
            return self._check_upcoming_trigger(alert, event, current_time)
        
        elif alert.trigger_type == AlertTrigger.RELEASED:
            return self._check_release_trigger(alert, event)
        
        elif alert.trigger_type == AlertTrigger.SURPRISE:
            return self._check_surprise_trigger(alert, event)
        
        return None
    
    def _check_upcoming_trigger(
        self,
        alert: EventAlert,
        event: EconomicEvent,
        current_time: datetime,
    ) -> Optional[AlertNotification]:
        """Check upcoming event trigger."""
        if event.is_released:
            return None
        
        if not event.release_date or not event.release_time:
            return None
        
        # Combine date and time
        event_datetime = datetime.combine(
            event.release_date,
            event.release_time,
        ).replace(tzinfo=timezone.utc)
        
        # Check if within alert window
        alert_window = timedelta(minutes=alert.minutes_before)
        time_until = event_datetime - current_time
        
        if timedelta(0) < time_until <= alert_window:
            return AlertNotification(
                alert_id=alert.alert_id,
                event_id=event.event_id,
                title=f"Upcoming: {event.name}",
                message=f"{event.name} releases in {int(time_until.total_seconds() / 60)} minutes",
                event_name=event.name,
            )
        
        return None
    
    def _check_release_trigger(
        self,
        alert: EventAlert,
        event: EconomicEvent,
    ) -> Optional[AlertNotification]:
        """Check event release trigger."""
        if not alert.on_release:
            return None
        
        if not event.is_released:
            return None
        
        # Build message
        message = f"{event.name}: Actual {event.actual}{event.unit}"
        if event.forecast is not None:
            message += f" vs Forecast {event.forecast}{event.unit}"
        
        if event.beat_or_miss:
            message += f" ({event.beat_or_miss})"
        
        return AlertNotification(
            alert_id=alert.alert_id,
            event_id=event.event_id,
            title=f"Released: {event.name}",
            message=message,
            event_name=event.name,
        )
    
    def _check_surprise_trigger(
        self,
        alert: EventAlert,
        event: EconomicEvent,
    ) -> Optional[AlertNotification]:
        """Check surprise trigger."""
        if not event.is_released:
            return None
        
        threshold = alert.surprise_threshold or DEFAULT_SURPRISE_THRESHOLD
        
        # Need surprise percentage
        if event.surprise_pct is None:
            return None
        
        if abs(event.surprise_pct) >= threshold * 10:  # Convert to percentage points
            direction = "beat" if event.surprise_pct > 0 else "miss"
            
            return AlertNotification(
                alert_id=alert.alert_id,
                event_id=event.event_id,
                title=f"Big {direction.title()}: {event.name}",
                message=f"{event.name} {direction} by {abs(event.surprise_pct):.1f}%",
                event_name=event.name,
            )
        
        return None
    
    # =========================================================================
    # Notifications
    # =========================================================================
    
    def get_notifications(
        self,
        limit: int = 50,
        unread_only: bool = False,
    ) -> list[AlertNotification]:
        """Get notifications."""
        notifications = self._notifications
        
        if unread_only:
            notifications = [n for n in notifications if not n.is_read]
        
        # Sort by creation time (newest first)
        notifications.sort(key=lambda n: n.created_at, reverse=True)
        
        return notifications[:limit]
    
    def mark_read(self, notification_id: str) -> bool:
        """Mark notification as read."""
        for n in self._notifications:
            if n.notification_id == notification_id:
                n.is_read = True
                return True
        return False
    
    def mark_all_read(self) -> int:
        """Mark all notifications as read."""
        count = 0
        for n in self._notifications:
            if not n.is_read:
                n.is_read = True
                count += 1
        return count
    
    def clear_notifications(self) -> int:
        """Clear all notifications."""
        count = len(self._notifications)
        self._notifications = []
        return count


def create_default_alerts() -> list[EventAlert]:
    """Create default alert configurations."""
    return [
        EventAlert(
            name="High Impact Events",
            min_impact=ImpactLevel.HIGH,
            trigger_type=AlertTrigger.UPCOMING,
            minutes_before=30,
            on_release=True,
        ),
        EventAlert(
            name="Fed Decisions",
            event_pattern="*Fed*",
            categories=[EventCategory.CENTRAL_BANK],
            trigger_type=AlertTrigger.UPCOMING,
            minutes_before=60,
            on_release=True,
        ),
        EventAlert(
            name="Big Surprises",
            min_impact=ImpactLevel.MEDIUM,
            trigger_type=AlertTrigger.SURPRISE,
            surprise_threshold=1.5,
        ),
        EventAlert(
            name="Employment Data",
            categories=[EventCategory.EMPLOYMENT],
            min_impact=ImpactLevel.MEDIUM,
            trigger_type=AlertTrigger.UPCOMING,
            minutes_before=30,
        ),
        EventAlert(
            name="Inflation Data",
            categories=[EventCategory.INFLATION],
            min_impact=ImpactLevel.HIGH,
            trigger_type=AlertTrigger.UPCOMING,
            minutes_before=30,
        ),
    ]
