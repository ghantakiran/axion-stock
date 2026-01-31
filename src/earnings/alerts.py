"""Earnings Alerts.

Generate and manage earnings-related alerts.
"""

from datetime import date, datetime, timedelta, timezone
from typing import Optional, Callable
import logging

from src.earnings.config import (
    AlertType,
    EarningsConfig,
    DEFAULT_EARNINGS_CONFIG,
    BEAT_THRESHOLD,
    MISS_THRESHOLD,
)
from src.earnings.models import EarningsEvent, EarningsAlert

logger = logging.getLogger(__name__)


class EarningsAlertManager:
    """Manages earnings alerts.
    
    Generates alerts for upcoming earnings, estimate revisions,
    earnings releases, surprises, and guidance changes.
    
    Example:
        manager = EarningsAlertManager()
        
        # Check for alerts
        alerts = manager.check_upcoming_earnings(events)
        for alert in alerts:
            print(f"{alert.symbol}: {alert.title}")
    """
    
    def __init__(self, config: Optional[EarningsConfig] = None):
        self.config = config or DEFAULT_EARNINGS_CONFIG
        self._alerts: dict[str, EarningsAlert] = {}
        self._subscribers: list[Callable[[EarningsAlert], None]] = []
        self._notified: set[str] = set()  # Track what we've notified
    
    def subscribe(self, callback: Callable[[EarningsAlert], None]) -> None:
        """Subscribe to alert notifications."""
        self._subscribers.append(callback)
    
    def _notify(self, alert: EarningsAlert) -> None:
        """Notify subscribers of an alert."""
        for callback in self._subscribers:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")
    
    def _create_alert(
        self,
        symbol: str,
        alert_type: AlertType,
        title: str,
        message: str,
        event: Optional[EarningsEvent] = None,
    ) -> EarningsAlert:
        """Create and store an alert."""
        alert = EarningsAlert(
            symbol=symbol,
            alert_type=alert_type,
            title=title,
            message=message,
            earnings_event=event,
            triggered_at=datetime.now(timezone.utc),
        )
        
        self._alerts[alert.alert_id] = alert
        return alert
    
    def check_upcoming_earnings(
        self,
        events: list[EarningsEvent],
        portfolio_symbols: Optional[list[str]] = None,
    ) -> list[EarningsAlert]:
        """Check for upcoming earnings and generate alerts.
        
        Args:
            events: List of earnings events.
            portfolio_symbols: Optional filter to portfolio.
            
        Returns:
            List of generated alerts.
        """
        alerts = []
        today = date.today()
        
        for event in events:
            if not event.report_date:
                continue
            
            # Filter to portfolio if specified
            if portfolio_symbols and event.symbol not in portfolio_symbols:
                continue
            
            days_until = (event.report_date - today).days
            
            # Check each alert threshold
            for alert_days in self.config.alert_days_before:
                if days_until == alert_days:
                    # Check if already notified
                    key = f"{event.symbol}_{event.fiscal_quarter}_{alert_days}"
                    if key in self._notified:
                        continue
                    
                    if alert_days == 1:
                        title = f"{event.symbol} reports earnings tomorrow"
                    elif alert_days == 0:
                        title = f"{event.symbol} reports earnings today"
                    else:
                        title = f"{event.symbol} reports earnings in {alert_days} days"
                    
                    message = self._build_upcoming_message(event)
                    
                    alert = self._create_alert(
                        symbol=event.symbol,
                        alert_type=AlertType.UPCOMING,
                        title=title,
                        message=message,
                        event=event,
                    )
                    
                    alerts.append(alert)
                    self._notified.add(key)
                    self._notify(alert)
        
        return alerts
    
    def _build_upcoming_message(self, event: EarningsEvent) -> str:
        """Build message for upcoming earnings alert."""
        parts = [f"{event.company_name} ({event.symbol})"]
        parts.append(f"Reports: {event.report_date} {event.report_time.value.upper()}")
        parts.append(f"Quarter: {event.fiscal_quarter}")
        
        if event.eps_estimate:
            parts.append(f"EPS Est: ${event.eps_estimate:.2f}")
        
        if event.revenue_estimate:
            parts.append(f"Rev Est: ${event.revenue_estimate/1e9:.2f}B")
        
        return " | ".join(parts)
    
    def check_earnings_released(
        self,
        event: EarningsEvent,
    ) -> Optional[EarningsAlert]:
        """Generate alert when earnings are released.
        
        Args:
            event: Earnings event with actuals.
            
        Returns:
            EarningsAlert if criteria met.
        """
        if not event.is_reported or event.eps_actual is None:
            return None
        
        key = f"{event.symbol}_{event.fiscal_quarter}_released"
        if key in self._notified:
            return None
        
        title = f"{event.symbol} reported earnings"
        message = self._build_released_message(event)
        
        alert = self._create_alert(
            symbol=event.symbol,
            alert_type=AlertType.RELEASED,
            title=title,
            message=message,
            event=event,
        )
        
        self._notified.add(key)
        self._notify(alert)
        return alert
    
    def _build_released_message(self, event: EarningsEvent) -> str:
        """Build message for earnings released alert."""
        parts = [f"{event.company_name} ({event.symbol})"]
        
        if event.eps_actual is not None:
            parts.append(f"EPS: ${event.eps_actual:.2f}")
            if event.eps_estimate:
                surprise = event.eps_surprise_pct
                if surprise and surprise > BEAT_THRESHOLD:
                    parts.append(f"BEAT by {surprise:.1%}")
                elif surprise and surprise < MISS_THRESHOLD:
                    parts.append(f"MISSED by {abs(surprise):.1%}")
                else:
                    parts.append("In-line")
        
        if event.revenue_actual:
            parts.append(f"Revenue: ${event.revenue_actual/1e9:.2f}B")
        
        return " | ".join(parts)
    
    def check_surprise_alert(
        self,
        event: EarningsEvent,
    ) -> Optional[EarningsAlert]:
        """Generate alert for significant earnings surprise.
        
        Args:
            event: Earnings event with actuals.
            
        Returns:
            EarningsAlert if surprise exceeds threshold.
        """
        surprise = event.eps_surprise_pct
        if surprise is None:
            return None
        
        if abs(surprise) < self.config.surprise_alert_threshold:
            return None
        
        key = f"{event.symbol}_{event.fiscal_quarter}_surprise"
        if key in self._notified:
            return None
        
        if surprise > 0:
            title = f"{event.symbol} beats by {surprise:.1%}"
        else:
            title = f"{event.symbol} misses by {abs(surprise):.1%}"
        
        message = self._build_surprise_message(event)
        
        alert = self._create_alert(
            symbol=event.symbol,
            alert_type=AlertType.SURPRISE,
            title=title,
            message=message,
            event=event,
        )
        
        self._notified.add(key)
        self._notify(alert)
        return alert
    
    def _build_surprise_message(self, event: EarningsEvent) -> str:
        """Build message for surprise alert."""
        parts = []
        
        if event.eps_estimate and event.eps_actual is not None:
            parts.append(f"Est: ${event.eps_estimate:.2f}")
            parts.append(f"Act: ${event.eps_actual:.2f}")
        
        return " → ".join(parts)
    
    def check_revision_alert(
        self,
        symbol: str,
        old_estimate: float,
        new_estimate: float,
        fiscal_quarter: str,
    ) -> Optional[EarningsAlert]:
        """Generate alert for significant estimate revision.
        
        Args:
            symbol: Stock symbol.
            old_estimate: Previous estimate.
            new_estimate: New estimate.
            fiscal_quarter: Quarter.
            
        Returns:
            EarningsAlert if revision is significant.
        """
        if old_estimate == 0:
            return None
        
        change_pct = (new_estimate - old_estimate) / abs(old_estimate)
        
        # Only alert on significant revisions (>5%)
        if abs(change_pct) < 0.05:
            return None
        
        key = f"{symbol}_{fiscal_quarter}_revision_{new_estimate}"
        if key in self._notified:
            return None
        
        direction = "raised" if change_pct > 0 else "lowered"
        title = f"{symbol} estimates {direction} by {abs(change_pct):.1%}"
        message = f"Previous: ${old_estimate:.2f} → New: ${new_estimate:.2f}"
        
        alert = self._create_alert(
            symbol=symbol,
            alert_type=AlertType.REVISION,
            title=title,
            message=message,
        )
        
        self._notified.add(key)
        self._notify(alert)
        return alert
    
    def get_alerts(
        self,
        symbol: Optional[str] = None,
        alert_type: Optional[AlertType] = None,
        unread_only: bool = False,
    ) -> list[EarningsAlert]:
        """Get alerts with optional filters.
        
        Args:
            symbol: Filter by symbol.
            alert_type: Filter by type.
            unread_only: Only unread alerts.
            
        Returns:
            List of matching alerts.
        """
        alerts = list(self._alerts.values())
        
        if symbol:
            alerts = [a for a in alerts if a.symbol == symbol]
        
        if alert_type:
            alerts = [a for a in alerts if a.alert_type == alert_type]
        
        if unread_only:
            alerts = [a for a in alerts if not a.is_read]
        
        return sorted(alerts, key=lambda a: a.created_at, reverse=True)
    
    def mark_read(self, alert_id: str) -> None:
        """Mark an alert as read."""
        if alert_id in self._alerts:
            self._alerts[alert_id].is_read = True
    
    def dismiss(self, alert_id: str) -> None:
        """Dismiss an alert."""
        if alert_id in self._alerts:
            self._alerts[alert_id].is_dismissed = True
    
    def clear_old_alerts(self, days: int = 30) -> int:
        """Clear alerts older than specified days.
        
        Returns:
            Number of alerts cleared.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        to_remove = [
            aid for aid, alert in self._alerts.items()
            if alert.created_at < cutoff
        ]
        
        for aid in to_remove:
            del self._alerts[aid]
        
        return len(to_remove)
