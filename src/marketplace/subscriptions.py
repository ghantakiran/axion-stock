"""Subscription management for marketplace."""

from datetime import datetime, timezone, timedelta
from typing import Optional
from collections import defaultdict

from src.marketplace.config import (
    SubscriptionStatus,
    SubscriptionType,
    MarketplaceConfig,
    DEFAULT_MARKETPLACE_CONFIG,
)
from src.marketplace.models import Strategy, Subscription


class SubscriptionManager:
    """Manages strategy subscriptions."""

    def __init__(self, config: Optional[MarketplaceConfig] = None):
        self.config = config or DEFAULT_MARKETPLACE_CONFIG
        self._subscriptions: dict[str, Subscription] = {}
        self._by_strategy: dict[str, list[str]] = defaultdict(list)
        self._by_subscriber: dict[str, list[str]] = defaultdict(list)

    def subscribe(
        self,
        strategy: Strategy,
        subscriber_id: str,
        subscription_type: SubscriptionType = SubscriptionType.SIGNALS,
        auto_trade_enabled: bool = False,
        position_size_pct: float = 100.0,
        max_position_value: Optional[float] = None,
        risk_multiplier: float = 1.0,
        trial: bool = False,
    ) -> Subscription:
        """Subscribe to a strategy."""
        # Check if already subscribed
        existing = self.get_subscription(strategy.strategy_id, subscriber_id)
        if existing and existing.is_active():
            raise ValueError("Already subscribed to this strategy")

        # Check subscription limit
        user_subs = self.get_subscriber_subscriptions(subscriber_id, active_only=True)
        if len(user_subs) >= self.config.max_subscriptions_per_user:
            raise ValueError(f"Max {self.config.max_subscriptions_per_user} subscriptions allowed")

        # Can't subscribe to own strategy
        if strategy.creator_id == subscriber_id:
            raise ValueError("Cannot subscribe to your own strategy")

        # Check strategy is published
        if not strategy.is_published:
            raise ValueError("Strategy is not published")

        # Create subscription
        subscription = Subscription(
            strategy_id=strategy.strategy_id,
            subscriber_id=subscriber_id,
            subscription_type=subscription_type,
            auto_trade_enabled=auto_trade_enabled and subscription_type == SubscriptionType.AUTO_TRADE,
            position_size_pct=min(max(position_size_pct, 1), 200),  # 1-200%
            max_position_value=max_position_value,
            risk_multiplier=min(max(risk_multiplier, 0.1), 2.0),  # 0.1-2.0x
            status=SubscriptionStatus.TRIAL if trial else SubscriptionStatus.ACTIVE,
        )

        if trial:
            subscription.expires_at = datetime.now(timezone.utc) + timedelta(days=self.config.trial_days)

        # Store
        self._subscriptions[subscription.subscription_id] = subscription
        self._by_strategy[strategy.strategy_id].append(subscription.subscription_id)
        self._by_subscriber[subscriber_id].append(subscription.subscription_id)

        # Update strategy subscriber count
        strategy.subscriber_count += 1

        return subscription

    def unsubscribe(
        self,
        strategy_id: str,
        subscriber_id: str,
        reason: Optional[str] = None,
    ) -> bool:
        """Unsubscribe from a strategy."""
        subscription = self.get_subscription(strategy_id, subscriber_id)
        if not subscription:
            return False

        subscription.cancel(reason)
        return True

    def get_subscription(self, strategy_id: str, subscriber_id: str) -> Optional[Subscription]:
        """Get subscription for a strategy and subscriber."""
        for sub_id in self._by_strategy.get(strategy_id, []):
            sub = self._subscriptions.get(sub_id)
            if sub and sub.subscriber_id == subscriber_id:
                return sub
        return None

    def get_subscription_by_id(self, subscription_id: str) -> Optional[Subscription]:
        """Get subscription by ID."""
        return self._subscriptions.get(subscription_id)

    def get_strategy_subscriptions(
        self,
        strategy_id: str,
        active_only: bool = True,
    ) -> list[Subscription]:
        """Get all subscriptions for a strategy."""
        sub_ids = self._by_strategy.get(strategy_id, [])
        subs = [self._subscriptions[sid] for sid in sub_ids if sid in self._subscriptions]

        if active_only:
            subs = [s for s in subs if s.is_active()]

        return subs

    def get_subscriber_subscriptions(
        self,
        subscriber_id: str,
        active_only: bool = True,
    ) -> list[Subscription]:
        """Get all subscriptions for a subscriber."""
        sub_ids = self._by_subscriber.get(subscriber_id, [])
        subs = [self._subscriptions[sid] for sid in sub_ids if sid in self._subscriptions]

        if active_only:
            subs = [s for s in subs if s.is_active()]

        return subs

    def pause_subscription(self, subscription_id: str) -> bool:
        """Pause a subscription."""
        subscription = self._subscriptions.get(subscription_id)
        if not subscription:
            return False

        subscription.pause()
        return True

    def resume_subscription(self, subscription_id: str) -> bool:
        """Resume a paused subscription."""
        subscription = self._subscriptions.get(subscription_id)
        if not subscription:
            return False

        if subscription.status != SubscriptionStatus.PAUSED:
            return False

        subscription.resume()
        return True

    def update_settings(
        self,
        subscription_id: str,
        auto_trade_enabled: Optional[bool] = None,
        position_size_pct: Optional[float] = None,
        max_position_value: Optional[float] = None,
        risk_multiplier: Optional[float] = None,
    ) -> Optional[Subscription]:
        """Update subscription settings."""
        subscription = self._subscriptions.get(subscription_id)
        if not subscription:
            return None

        if auto_trade_enabled is not None:
            subscription.auto_trade_enabled = auto_trade_enabled
        if position_size_pct is not None:
            subscription.position_size_pct = min(max(position_size_pct, 1), 200)
        if max_position_value is not None:
            subscription.max_position_value = max_position_value
        if risk_multiplier is not None:
            subscription.risk_multiplier = min(max(risk_multiplier, 0.1), 2.0)

        return subscription

    def get_active_subscriber_count(self, strategy_id: str) -> int:
        """Get count of active subscribers for a strategy."""
        subs = self.get_strategy_subscriptions(strategy_id, active_only=True)
        return len(subs)

    def get_expiring_subscriptions(self, days: int = 7) -> list[Subscription]:
        """Get subscriptions expiring within N days."""
        cutoff = datetime.now(timezone.utc) + timedelta(days=days)
        expiring = []

        for subscription in self._subscriptions.values():
            if subscription.is_active() and subscription.expires_at:
                if subscription.expires_at <= cutoff:
                    expiring.append(subscription)

        return expiring

    def process_expired_subscriptions(self) -> int:
        """Mark expired subscriptions as expired."""
        now = datetime.now(timezone.utc)
        count = 0

        for subscription in self._subscriptions.values():
            if subscription.status == SubscriptionStatus.ACTIVE:
                if subscription.expires_at and now > subscription.expires_at:
                    subscription.status = SubscriptionStatus.EXPIRED
                    count += 1

        return count

    def record_payment(self, subscription_id: str, amount: float) -> bool:
        """Record a payment for a subscription."""
        subscription = self._subscriptions.get(subscription_id)
        if not subscription:
            return False

        subscription.total_paid += amount
        return True

    def get_stats(self) -> dict:
        """Get subscription statistics."""
        active = sum(1 for s in self._subscriptions.values() if s.is_active())
        by_type = defaultdict(int)
        by_status = defaultdict(int)

        for sub in self._subscriptions.values():
            by_type[sub.subscription_type.value] += 1
            by_status[sub.status.value] += 1

        return {
            "total_subscriptions": len(self._subscriptions),
            "active_subscriptions": active,
            "unique_subscribers": len(self._by_subscriber),
            "by_type": dict(by_type),
            "by_status": dict(by_status),
        }
