"""News & Events Alerts.

Manages alert configurations and notifications for news and events.
"""

from datetime import datetime, timezone
from typing import Optional, Callable
import logging

from src.news.config import (
    NewsCategory,
    NewsSource,
    EventImportance,
    FilingType,
    AlertTrigger,
    NewsAlertsConfig,
    NewsConfig,
    DEFAULT_NEWS_CONFIG,
)
from src.news.models import (
    NewsArticle,
    EarningsEvent,
    EconomicEvent,
    SECFiling,
    InsiderTransaction,
    DividendEvent,
    NewsAlert,
    AlertNotification,
)

logger = logging.getLogger(__name__)


class NewsAlertManager:
    """Manages news and event alerts.
    
    Features:
    - Create/manage alert configurations
    - Evaluate incoming data against alerts
    - Generate notifications
    - Track alert history
    """
    
    def __init__(self, config: Optional[NewsConfig] = None):
        self.config = config or DEFAULT_NEWS_CONFIG
        self._alerts_config = self.config.alerts
        self._alerts: dict[str, NewsAlert] = {}  # alert_id -> alert
        self._user_alerts: dict[str, list[str]] = {}  # user_id -> alert_ids
        self._notifications: list[AlertNotification] = []
        self._callbacks: list[Callable[[AlertNotification], None]] = []
    
    def create_alert(
        self,
        user_id: str,
        name: str,
        trigger: AlertTrigger,
        symbols: Optional[list[str]] = None,
        keywords: Optional[list[str]] = None,
        categories: Optional[list[NewsCategory]] = None,
        channels: Optional[list[str]] = None,
        **kwargs,
    ) -> NewsAlert:
        """Create a new alert.
        
        Args:
            user_id: User ID.
            name: Alert name.
            trigger: Alert trigger type.
            symbols: Symbols to watch.
            keywords: Keywords to match.
            categories: News categories to filter.
            channels: Delivery channels.
            **kwargs: Additional alert options.
            
        Returns:
            Created NewsAlert.
        """
        # Check user alert limit
        user_alert_ids = self._user_alerts.get(user_id, [])
        if len(user_alert_ids) >= self._alerts_config.max_alerts_per_user:
            raise ValueError(
                f"User has reached maximum alerts ({self._alerts_config.max_alerts_per_user})"
            )
        
        alert = NewsAlert(
            user_id=user_id,
            name=name,
            trigger=trigger,
            symbols=symbols or [],
            keywords=keywords or [],
            categories=categories or [],
            channels=channels or ["in_app"],
            **kwargs,
        )
        
        self._alerts[alert.alert_id] = alert
        
        if user_id not in self._user_alerts:
            self._user_alerts[user_id] = []
        self._user_alerts[user_id].append(alert.alert_id)
        
        logger.info(f"Created alert '{name}' for user {user_id}")
        return alert
    
    def get_alert(self, alert_id: str) -> Optional[NewsAlert]:
        """Get an alert by ID."""
        return self._alerts.get(alert_id)
    
    def get_user_alerts(self, user_id: str) -> list[NewsAlert]:
        """Get all alerts for a user."""
        alert_ids = self._user_alerts.get(user_id, [])
        return [self._alerts[aid] for aid in alert_ids if aid in self._alerts]
    
    def update_alert(
        self,
        alert_id: str,
        **updates,
    ) -> Optional[NewsAlert]:
        """Update an alert.
        
        Args:
            alert_id: Alert to update.
            **updates: Fields to update.
            
        Returns:
            Updated alert or None if not found.
        """
        alert = self._alerts.get(alert_id)
        if not alert:
            return None
        
        for key, value in updates.items():
            if hasattr(alert, key):
                setattr(alert, key, value)
        
        return alert
    
    def delete_alert(self, alert_id: str) -> bool:
        """Delete an alert.
        
        Args:
            alert_id: Alert to delete.
            
        Returns:
            True if deleted, False if not found.
        """
        alert = self._alerts.get(alert_id)
        if not alert:
            return False
        
        del self._alerts[alert_id]
        
        if alert.user_id in self._user_alerts:
            self._user_alerts[alert.user_id] = [
                aid for aid in self._user_alerts[alert.user_id]
                if aid != alert_id
            ]
        
        return True
    
    def enable_alert(self, alert_id: str) -> bool:
        """Enable an alert."""
        alert = self._alerts.get(alert_id)
        if alert:
            alert.enabled = True
            return True
        return False
    
    def disable_alert(self, alert_id: str) -> bool:
        """Disable an alert."""
        alert = self._alerts.get(alert_id)
        if alert:
            alert.enabled = False
            return True
        return False
    
    def register_callback(
        self,
        callback: Callable[[AlertNotification], None],
    ) -> None:
        """Register a callback for alert notifications.
        
        Args:
            callback: Function to call when alert triggers.
        """
        self._callbacks.append(callback)
    
    def evaluate_article(self, article: NewsArticle) -> list[AlertNotification]:
        """Evaluate a news article against all alerts.
        
        Args:
            article: NewsArticle to evaluate.
            
        Returns:
            List of triggered notifications.
        """
        notifications = []
        
        for alert in self._alerts.values():
            if not alert.enabled:
                continue
            
            if alert.trigger not in [AlertTrigger.SYMBOL_NEWS, AlertTrigger.BREAKING_NEWS]:
                continue
            
            if self._matches_article(alert, article):
                notif = self._create_notification(
                    alert=alert,
                    title=f"News Alert: {article.symbols[0] if article.symbols else 'Market'}",
                    message=article.headline,
                    symbol=article.symbols[0] if article.symbols else None,
                    reference_id=article.article_id,
                    reference_type="article",
                )
                notifications.append(notif)
        
        return notifications
    
    def evaluate_earnings(self, event: EarningsEvent) -> list[AlertNotification]:
        """Evaluate an earnings event against alerts.
        
        Args:
            event: EarningsEvent to evaluate.
            
        Returns:
            List of triggered notifications.
        """
        notifications = []
        
        for alert in self._alerts.values():
            if not alert.enabled:
                continue
            
            if alert.trigger == AlertTrigger.EARNINGS_ANNOUNCE:
                if not alert.symbols or event.symbol in alert.symbols:
                    notif = self._create_notification(
                        alert=alert,
                        title=f"Earnings: {event.symbol}",
                        message=f"{event.company_name} reported {event.fiscal_quarter}",
                        symbol=event.symbol,
                        reference_id=event.event_id,
                        reference_type="earnings",
                    )
                    notifications.append(notif)
            
            elif alert.trigger == AlertTrigger.EARNINGS_SURPRISE:
                if event.eps_surprise_pct is not None and abs(event.eps_surprise_pct) > 5:
                    if not alert.symbols or event.symbol in alert.symbols:
                        direction = "beat" if event.eps_surprise_pct > 0 else "missed"
                        notif = self._create_notification(
                            alert=alert,
                            title=f"Earnings Surprise: {event.symbol}",
                            message=f"{event.symbol} {direction} by {abs(event.eps_surprise_pct):.1f}%",
                            symbol=event.symbol,
                            reference_id=event.event_id,
                            reference_type="earnings",
                        )
                        notifications.append(notif)
        
        return notifications
    
    def evaluate_filing(self, filing: SECFiling) -> list[AlertNotification]:
        """Evaluate an SEC filing against alerts.
        
        Args:
            filing: SECFiling to evaluate.
            
        Returns:
            List of triggered notifications.
        """
        notifications = []
        
        for alert in self._alerts.values():
            if not alert.enabled:
                continue
            
            if alert.trigger != AlertTrigger.SEC_FILING:
                continue
            
            if alert.symbols and filing.symbol not in alert.symbols:
                continue
            
            if alert.filing_types and filing.form_type not in alert.filing_types:
                continue
            
            notif = self._create_notification(
                alert=alert,
                title=f"SEC Filing: {filing.symbol}",
                message=f"{filing.form_type.value} filed on {filing.filed_date}",
                symbol=filing.symbol,
                reference_id=filing.filing_id,
                reference_type="filing",
            )
            notifications.append(notif)
        
        return notifications
    
    def evaluate_insider(self, txn: InsiderTransaction) -> list[AlertNotification]:
        """Evaluate an insider transaction against alerts.
        
        Args:
            txn: InsiderTransaction to evaluate.
            
        Returns:
            List of triggered notifications.
        """
        notifications = []
        
        for alert in self._alerts.values():
            if not alert.enabled:
                continue
            
            if alert.trigger != AlertTrigger.INSIDER_TRANSACTION:
                continue
            
            if alert.symbols and txn.symbol not in alert.symbols:
                continue
            
            action = "bought" if txn.is_purchase else "sold"
            value_str = f"${txn.value:,.0f}" if txn.value else f"{txn.shares:,.0f} shares"
            
            notif = self._create_notification(
                alert=alert,
                title=f"Insider {action.title()}: {txn.symbol}",
                message=f"{txn.insider_name} ({txn.insider_title}) {action} {value_str}",
                symbol=txn.symbol,
                reference_id=txn.transaction_id,
                reference_type="insider",
            )
            notifications.append(notif)
        
        return notifications
    
    def evaluate_dividend(self, dividend: DividendEvent) -> list[AlertNotification]:
        """Evaluate a dividend announcement against alerts.
        
        Args:
            dividend: DividendEvent to evaluate.
            
        Returns:
            List of triggered notifications.
        """
        notifications = []
        
        for alert in self._alerts.values():
            if not alert.enabled:
                continue
            
            if alert.trigger != AlertTrigger.DIVIDEND_DECLARED:
                continue
            
            if alert.symbols and dividend.symbol not in alert.symbols:
                continue
            
            notif = self._create_notification(
                alert=alert,
                title=f"Dividend: {dividend.symbol}",
                message=f"${dividend.amount:.4f} ex-date {dividend.ex_date}",
                symbol=dividend.symbol,
                reference_id=dividend.event_id,
                reference_type="dividend",
            )
            notifications.append(notif)
        
        return notifications
    
    def _matches_article(self, alert: NewsAlert, article: NewsArticle) -> bool:
        """Check if article matches alert criteria."""
        # Symbol match
        if alert.symbols and not any(s in article.symbols for s in alert.symbols):
            return False
        
        # Category match
        if alert.categories and not any(c in article.categories for c in alert.categories):
            return False
        
        # Source match
        if alert.sources and article.source not in alert.sources:
            return False
        
        # Keyword match
        if alert.keywords:
            text = (article.headline + " " + article.summary).lower()
            if not any(kw.lower() in text for kw in alert.keywords):
                return False
        
        # Sentiment filter
        if alert.min_sentiment is not None and article.sentiment_score < alert.min_sentiment:
            return False
        if alert.max_sentiment is not None and article.sentiment_score > alert.max_sentiment:
            return False
        
        # Breaking news filter
        if alert.trigger == AlertTrigger.BREAKING_NEWS and not article.is_breaking:
            return False
        
        return True
    
    def _create_notification(
        self,
        alert: NewsAlert,
        title: str,
        message: str,
        symbol: Optional[str],
        reference_id: str,
        reference_type: str,
    ) -> AlertNotification:
        """Create and store a notification."""
        notif = AlertNotification(
            alert_id=alert.alert_id,
            user_id=alert.user_id,
            trigger=alert.trigger,
            title=title,
            message=message,
            symbol=symbol,
            reference_id=reference_id,
            reference_type=reference_type,
            channels_sent=alert.channels.copy(),
        )
        
        self._notifications.append(notif)
        
        # Update alert stats
        alert.last_triggered_at = datetime.now(timezone.utc)
        alert.trigger_count += 1
        
        # Fire callbacks
        for callback in self._callbacks:
            try:
                callback(notif)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")
        
        logger.info(f"Alert triggered: {title}")
        return notif
    
    def get_notifications(
        self,
        user_id: str,
        unread_only: bool = False,
        limit: int = 50,
    ) -> list[AlertNotification]:
        """Get notifications for a user.
        
        Args:
            user_id: User ID.
            unread_only: Only return unread notifications.
            limit: Maximum notifications to return.
            
        Returns:
            List of notifications (newest first).
        """
        user_notifs = [n for n in self._notifications if n.user_id == user_id]
        
        if unread_only:
            user_notifs = [n for n in user_notifs if not n.is_read]
        
        user_notifs.sort(key=lambda n: n.created_at, reverse=True)
        return user_notifs[:limit]
    
    def mark_read(self, notification_id: str) -> bool:
        """Mark a notification as read."""
        for notif in self._notifications:
            if notif.notification_id == notification_id:
                notif.is_read = True
                return True
        return False
    
    def get_unread_count(self, user_id: str) -> int:
        """Get count of unread notifications for a user."""
        return len([
            n for n in self._notifications
            if n.user_id == user_id and not n.is_read
        ])
