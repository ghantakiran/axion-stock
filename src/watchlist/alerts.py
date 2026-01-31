"""Watchlist Alerts.

Price alerts and notifications for watchlist items.
"""

from datetime import datetime, timezone
from typing import Optional, Callable
import logging

from src.watchlist.config import AlertType, DEFAULT_PCT_CHANGE_THRESHOLD, DEFAULT_VOLUME_SPIKE_RATIO
from src.watchlist.models import (
    WatchlistAlert,
    AlertNotification,
    WatchlistItem,
)

logger = logging.getLogger(__name__)


class AlertManager:
    """Manages watchlist alerts.
    
    Creates, tracks, and triggers alerts for watchlist items.
    
    Example:
        manager = AlertManager()
        
        # Create price alert
        alert = manager.create_alert(
            watchlist_id="wl1",
            symbol="AAPL",
            alert_type=AlertType.PRICE_BELOW,
            threshold=170.0,
        )
        
        # Check alerts
        notifications = manager.check_alerts({"AAPL": {"price": 168.0}})
    """
    
    def __init__(self):
        self._alerts: dict[str, WatchlistAlert] = {}
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
    
    def create_alert(
        self,
        watchlist_id: str,
        symbol: str,
        alert_type: AlertType,
        threshold: float,
        item_id: str = "",
        notify_email: bool = True,
        notify_push: bool = True,
    ) -> WatchlistAlert:
        """Create a new alert.
        
        Args:
            watchlist_id: Parent watchlist ID.
            symbol: Stock symbol.
            alert_type: Type of alert.
            threshold: Alert threshold value.
            item_id: Optional item ID.
            notify_email: Send email notifications.
            notify_push: Send push notifications.
            
        Returns:
            Created WatchlistAlert.
        """
        alert = WatchlistAlert(
            watchlist_id=watchlist_id,
            item_id=item_id,
            symbol=symbol.upper(),
            alert_type=alert_type,
            threshold=threshold,
            notify_email=notify_email,
            notify_push=notify_push,
        )
        
        self._alerts[alert.alert_id] = alert
        return alert
    
    def get_alert(self, alert_id: str) -> Optional[WatchlistAlert]:
        """Get alert by ID."""
        return self._alerts.get(alert_id)
    
    def get_alerts_for_symbol(self, symbol: str) -> list[WatchlistAlert]:
        """Get all alerts for a symbol."""
        return [a for a in self._alerts.values() if a.symbol == symbol.upper()]
    
    def get_alerts_for_watchlist(self, watchlist_id: str) -> list[WatchlistAlert]:
        """Get all alerts for a watchlist."""
        return [a for a in self._alerts.values() if a.watchlist_id == watchlist_id]
    
    def get_active_alerts(self) -> list[WatchlistAlert]:
        """Get all active alerts."""
        return [a for a in self._alerts.values() if a.is_active]
    
    def update_alert(
        self,
        alert_id: str,
        threshold: Optional[float] = None,
        is_active: Optional[bool] = None,
        notify_email: Optional[bool] = None,
        notify_push: Optional[bool] = None,
    ) -> Optional[WatchlistAlert]:
        """Update alert properties."""
        alert = self._alerts.get(alert_id)
        if not alert:
            return None
        
        if threshold is not None:
            alert.threshold = threshold
        if is_active is not None:
            alert.is_active = is_active
        if notify_email is not None:
            alert.notify_email = notify_email
        if notify_push is not None:
            alert.notify_push = notify_push
        
        return alert
    
    def delete_alert(self, alert_id: str) -> bool:
        """Delete an alert."""
        if alert_id in self._alerts:
            del self._alerts[alert_id]
            return True
        return False
    
    def check_alerts(
        self,
        market_data: dict[str, dict],
    ) -> list[AlertNotification]:
        """Check all active alerts against market data.
        
        Args:
            market_data: Dict of symbol -> {price, change, change_pct, volume, avg_volume, rsi, ...}
            
        Returns:
            List of triggered AlertNotifications.
        """
        notifications = []
        
        for alert in self.get_active_alerts():
            data = market_data.get(alert.symbol)
            if not data:
                continue
            
            triggered, message = self._check_alert_condition(alert, data)
            
            if triggered:
                notification = self._trigger_alert(alert, data, message)
                notifications.append(notification)
                self._notify(notification)
        
        return notifications
    
    def _check_alert_condition(
        self,
        alert: WatchlistAlert,
        data: dict,
    ) -> tuple[bool, str]:
        """Check if alert condition is met.
        
        Returns:
            Tuple of (is_triggered, message).
        """
        price = data.get("price", 0)
        change_pct = data.get("change_pct", 0)
        volume = data.get("volume", 0)
        avg_volume = data.get("avg_volume", 1)
        rsi = data.get("rsi", 50)
        
        if alert.alert_type == AlertType.PRICE_ABOVE:
            if price >= alert.threshold:
                return True, f"Price ${price:.2f} is above ${alert.threshold:.2f}"
        
        elif alert.alert_type == AlertType.PRICE_BELOW:
            if price <= alert.threshold:
                return True, f"Price ${price:.2f} is below ${alert.threshold:.2f}"
        
        elif alert.alert_type == AlertType.PCT_CHANGE_UP:
            if change_pct >= alert.threshold:
                return True, f"Up {change_pct:.1%} (threshold: {alert.threshold:.1%})"
        
        elif alert.alert_type == AlertType.PCT_CHANGE_DOWN:
            if change_pct <= -alert.threshold:
                return True, f"Down {abs(change_pct):.1%} (threshold: {alert.threshold:.1%})"
        
        elif alert.alert_type == AlertType.VOLUME_SPIKE:
            if avg_volume > 0:
                ratio = volume / avg_volume
                if ratio >= alert.threshold:
                    return True, f"Volume {ratio:.1f}x average"
        
        elif alert.alert_type == AlertType.RSI_OVERSOLD:
            if rsi <= alert.threshold:
                return True, f"RSI {rsi:.0f} is oversold (below {alert.threshold:.0f})"
        
        elif alert.alert_type == AlertType.RSI_OVERBOUGHT:
            if rsi >= alert.threshold:
                return True, f"RSI {rsi:.0f} is overbought (above {alert.threshold:.0f})"
        
        elif alert.alert_type == AlertType.TARGET_HIT:
            # Check if price hit the threshold (target price)
            if price >= alert.threshold:
                return True, f"Target price ${alert.threshold:.2f} hit!"
        
        elif alert.alert_type == AlertType.STOP_HIT:
            if price <= alert.threshold:
                return True, f"Stop loss ${alert.threshold:.2f} triggered!"
        
        return False, ""
    
    def _trigger_alert(
        self,
        alert: WatchlistAlert,
        data: dict,
        message: str,
    ) -> AlertNotification:
        """Trigger an alert and create notification."""
        alert.triggered_at = datetime.now(timezone.utc)
        alert.trigger_count += 1
        
        # Deactivate after trigger (one-time alert)
        alert.is_active = False
        
        notification = AlertNotification(
            alert_id=alert.alert_id,
            symbol=alert.symbol,
            title=f"{alert.symbol} Alert",
            message=message,
            trigger_value=data.get("price", 0),
            threshold=alert.threshold,
        )
        
        self._notifications.append(notification)
        return notification
    
    def get_notifications(
        self,
        symbol: Optional[str] = None,
        unread_only: bool = False,
        limit: int = 50,
    ) -> list[AlertNotification]:
        """Get alert notifications.
        
        Args:
            symbol: Filter by symbol.
            unread_only: Only unread notifications.
            limit: Maximum to return.
            
        Returns:
            List of notifications (newest first).
        """
        notifications = self._notifications.copy()
        
        if symbol:
            notifications = [n for n in notifications if n.symbol == symbol.upper()]
        
        if unread_only:
            notifications = [n for n in notifications if not n.is_read]
        
        notifications.sort(key=lambda n: n.created_at, reverse=True)
        return notifications[:limit]
    
    def mark_read(self, notification_id: str) -> bool:
        """Mark a notification as read."""
        for n in self._notifications:
            if n.notification_id == notification_id:
                n.is_read = True
                return True
        return False
    
    def create_item_alerts(
        self,
        watchlist_id: str,
        item: WatchlistItem,
    ) -> list[WatchlistAlert]:
        """Create standard alerts for a watchlist item based on its targets.
        
        Creates alerts for buy target, sell target, and stop loss if set.
        
        Returns:
            List of created alerts.
        """
        alerts = []
        
        if item.buy_target:
            alert = self.create_alert(
                watchlist_id=watchlist_id,
                symbol=item.symbol,
                alert_type=AlertType.PRICE_BELOW,
                threshold=item.buy_target,
                item_id=item.item_id,
            )
            alerts.append(alert)
        
        if item.sell_target:
            alert = self.create_alert(
                watchlist_id=watchlist_id,
                symbol=item.symbol,
                alert_type=AlertType.TARGET_HIT,
                threshold=item.sell_target,
                item_id=item.item_id,
            )
            alerts.append(alert)
        
        if item.stop_loss:
            alert = self.create_alert(
                watchlist_id=watchlist_id,
                symbol=item.symbol,
                alert_type=AlertType.STOP_HIT,
                threshold=item.stop_loss,
                item_id=item.item_id,
            )
            alerts.append(alert)
        
        return alerts
