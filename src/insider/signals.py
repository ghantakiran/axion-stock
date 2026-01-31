"""Insider Trading Signals.

Generate signals and alerts from insider activity.
"""

from datetime import datetime, date, timedelta, timezone
from typing import Optional, Callable
import logging

from src.insider.config import (
    InsiderType,
    TransactionType,
    SignalStrength,
    LARGE_BUY_THRESHOLD,
    SIGNIFICANT_BUY_THRESHOLD,
)
from src.insider.models import (
    InsiderTransaction,
    InsiderCluster,
    InsiderSignal,
    InsiderAlert,
)
from src.insider.transactions import TransactionTracker
from src.insider.clusters import ClusterDetector

logger = logging.getLogger(__name__)


class SignalGenerator:
    """Generates insider trading signals.
    
    Example:
        generator = SignalGenerator(tracker, detector)
        
        # Generate signals
        signals = generator.generate_signals()
        
        for signal in signals:
            print(f"{signal.symbol}: {signal.signal_type} - {signal.signal_strength.value}")
    """
    
    def __init__(
        self,
        tracker: TransactionTracker,
        cluster_detector: Optional[ClusterDetector] = None,
    ):
        self.tracker = tracker
        self.cluster_detector = cluster_detector or ClusterDetector(tracker)
        self._signals: list[InsiderSignal] = []
        self._alert_subscribers: list[Callable[[InsiderSignal], None]] = []
    
    def subscribe(self, callback: Callable[[InsiderSignal], None]) -> None:
        """Subscribe to signal notifications."""
        self._alert_subscribers.append(callback)
    
    def _notify(self, signal: InsiderSignal) -> None:
        """Notify subscribers of a signal."""
        for callback in self._alert_subscribers:
            try:
                callback(signal)
            except Exception as e:
                logger.error(f"Signal callback error: {e}")
    
    def generate_signals(self, days: int = 30) -> list[InsiderSignal]:
        """Generate all insider signals.
        
        Args:
            days: Look back period.
            
        Returns:
            List of generated signals.
        """
        signals = []
        
        # Detect cluster buying
        clusters = self.cluster_detector.detect_clusters(days=days)
        for cluster in clusters:
            signal = self._create_cluster_signal(cluster)
            signals.append(signal)
        
        # Detect large buys
        large_buys = self.tracker.get_large_transactions(
            min_value=LARGE_BUY_THRESHOLD,
            days=days
        )
        for txn in large_buys:
            if txn.is_buy:
                signal = self._create_large_buy_signal(txn)
                signals.append(signal)
        
        # Detect CEO buys
        ceo_buys = self.tracker.get_ceo_transactions(days=days, buys_only=True)
        for txn in ceo_buys:
            if txn.value >= SIGNIFICANT_BUY_THRESHOLD:
                signal = self._create_ceo_buy_signal(txn)
                signals.append(signal)
        
        # Deduplicate (same symbol can have multiple signal types)
        # Keep highest strength for each symbol
        unique_signals = self._deduplicate_signals(signals)
        
        # Sort by strength and value
        unique_signals.sort(
            key=lambda s: (
                {"very_strong": 4, "strong": 3, "moderate": 2, "weak": 1}.get(s.signal_strength.value, 0),
                s.total_value
            ),
            reverse=True
        )
        
        self._signals = unique_signals
        
        # Notify subscribers
        for signal in unique_signals:
            self._notify(signal)
        
        return unique_signals
    
    def _create_cluster_signal(self, cluster: InsiderCluster) -> InsiderSignal:
        """Create signal from cluster."""
        return InsiderSignal(
            symbol=cluster.symbol,
            company_name=cluster.company_name,
            signal_type="cluster_buy",
            signal_strength=cluster.signal_strength,
            description=f"{cluster.insider_count} insiders bought ${cluster.total_value:,.0f} worth",
            insiders_involved=cluster.insiders,
            total_value=cluster.total_value,
            transactions=cluster.transactions,
            cluster=cluster,
            signal_date=cluster.end_date,
        )
    
    def _create_large_buy_signal(self, txn: InsiderTransaction) -> InsiderSignal:
        """Create signal from large buy."""
        strength = SignalStrength.STRONG if txn.value >= 1_000_000 else SignalStrength.MODERATE
        
        return InsiderSignal(
            symbol=txn.symbol,
            company_name=txn.company_name,
            signal_type="large_buy",
            signal_strength=strength,
            description=f"{txn.insider_name} ({txn.insider_title}) bought ${txn.value:,.0f}",
            insiders_involved=[txn.insider_name],
            total_value=txn.value,
            transactions=[txn],
            signal_date=txn.transaction_date,
        )
    
    def _create_ceo_buy_signal(self, txn: InsiderTransaction) -> InsiderSignal:
        """Create signal from CEO buy."""
        strength = SignalStrength.STRONG if txn.value >= 500_000 else SignalStrength.MODERATE
        
        return InsiderSignal(
            symbol=txn.symbol,
            company_name=txn.company_name,
            signal_type="ceo_buy",
            signal_strength=strength,
            description=f"CEO {txn.insider_name} bought ${txn.value:,.0f}",
            insiders_involved=[txn.insider_name],
            total_value=txn.value,
            transactions=[txn],
            signal_date=txn.transaction_date,
        )
    
    def _deduplicate_signals(self, signals: list[InsiderSignal]) -> list[InsiderSignal]:
        """Deduplicate signals, keeping strongest for each symbol."""
        strength_order = {
            SignalStrength.WEAK: 0,
            SignalStrength.MODERATE: 1,
            SignalStrength.STRONG: 2,
            SignalStrength.VERY_STRONG: 3,
        }
        
        best_by_symbol: dict[str, InsiderSignal] = {}
        
        for signal in signals:
            existing = best_by_symbol.get(signal.symbol)
            
            if not existing:
                best_by_symbol[signal.symbol] = signal
            else:
                # Keep cluster signals over individual signals
                if signal.signal_type == "cluster_buy" and existing.signal_type != "cluster_buy":
                    best_by_symbol[signal.symbol] = signal
                elif signal.signal_type == existing.signal_type:
                    # Keep stronger signal
                    if strength_order.get(signal.signal_strength, 0) > strength_order.get(existing.signal_strength, 0):
                        best_by_symbol[signal.symbol] = signal
        
        return list(best_by_symbol.values())
    
    def get_signals(
        self,
        signal_type: Optional[str] = None,
        min_strength: Optional[SignalStrength] = None,
    ) -> list[InsiderSignal]:
        """Get signals with optional filtering."""
        signals = self._signals
        
        if signal_type:
            signals = [s for s in signals if s.signal_type == signal_type]
        
        if min_strength:
            strength_order = {
                SignalStrength.WEAK: 0,
                SignalStrength.MODERATE: 1,
                SignalStrength.STRONG: 2,
                SignalStrength.VERY_STRONG: 3,
            }
            min_level = strength_order[min_strength]
            signals = [
                s for s in signals
                if strength_order.get(s.signal_strength, 0) >= min_level
            ]
        
        return signals
    
    def get_strongest_signals(self, limit: int = 10) -> list[InsiderSignal]:
        """Get strongest signals."""
        return self._signals[:limit]


class AlertManager:
    """Manages insider trading alerts.
    
    Example:
        manager = AlertManager(generator)
        
        # Add alert
        alert = InsiderAlert(
            name="Large CEO Buys",
            min_value=500000,
            insider_types=[InsiderType.CEO],
        )
        manager.add_alert(alert)
        
        # Check alerts
        triggered = manager.check_alerts(signals)
    """
    
    def __init__(self, signal_generator: SignalGenerator):
        self.generator = signal_generator
        self._alerts: dict[str, InsiderAlert] = {}
        self._notifications: list[dict] = []
    
    def add_alert(self, alert: InsiderAlert) -> None:
        """Add an alert."""
        self._alerts[alert.alert_id] = alert
    
    def get_alert(self, alert_id: str) -> Optional[InsiderAlert]:
        """Get alert by ID."""
        return self._alerts.get(alert_id)
    
    def delete_alert(self, alert_id: str) -> bool:
        """Delete an alert."""
        if alert_id in self._alerts:
            del self._alerts[alert_id]
            return True
        return False
    
    def get_all_alerts(self) -> list[InsiderAlert]:
        """Get all alerts."""
        return list(self._alerts.values())
    
    def check_alerts(
        self,
        signals: Optional[list[InsiderSignal]] = None,
    ) -> list[dict]:
        """Check signals against alerts.
        
        Args:
            signals: Signals to check (or use generator's signals).
            
        Returns:
            List of triggered notifications.
        """
        if signals is None:
            signals = self.generator.get_signals()
        
        notifications = []
        
        for alert in self._alerts.values():
            if not alert.is_active:
                continue
            
            for signal in signals:
                if self._matches_alert(alert, signal):
                    notification = {
                        "alert_id": alert.alert_id,
                        "alert_name": alert.name,
                        "signal": signal,
                        "triggered_at": datetime.now(timezone.utc),
                    }
                    notifications.append(notification)
                    self._notifications.append(notification)
        
        return notifications
    
    def _matches_alert(self, alert: InsiderAlert, signal: InsiderSignal) -> bool:
        """Check if signal matches alert criteria."""
        # Check value threshold
        if signal.total_value < alert.min_value:
            return False
        
        # Check symbols filter
        if alert.symbols and signal.symbol not in alert.symbols:
            return False
        
        # Check cluster requirement
        if alert.require_cluster and signal.signal_type != "cluster_buy":
            return False
        
        # Check min insiders
        if len(signal.insiders_involved) < alert.min_insiders:
            return False
        
        # Check insider types
        if alert.insider_types:
            for txn in signal.transactions:
                if txn.insider_type in alert.insider_types:
                    return True
            return False
        
        return True
    
    def get_notifications(self, limit: int = 50) -> list[dict]:
        """Get recent notifications."""
        return self._notifications[-limit:]


def create_default_alerts() -> list[InsiderAlert]:
    """Create default insider alerts."""
    return [
        InsiderAlert(
            name="Cluster Buying",
            min_value=100_000,
            require_cluster=True,
            min_insiders=2,
        ),
        InsiderAlert(
            name="Large CEO Buys",
            min_value=500_000,
            insider_types=[InsiderType.CEO],
        ),
        InsiderAlert(
            name="C-Suite Activity",
            min_value=250_000,
            insider_types=[InsiderType.CEO, InsiderType.CFO, InsiderType.COO],
        ),
        InsiderAlert(
            name="Million Dollar Buys",
            min_value=1_000_000,
            transaction_types=[TransactionType.BUY],
        ),
    ]
