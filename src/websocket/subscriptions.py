"""Subscription manager for WebSocket API."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from collections import defaultdict

from src.websocket.config import ChannelType, CHANNEL_CONFIGS
from src.websocket.models import Subscription
from src.websocket.manager import ConnectionManager


class SubscriptionManager:
    """Manages subscriptions and symbol routing."""

    def __init__(self, manager: ConnectionManager):
        self.manager = manager
        # Symbol -> set of subscription_ids
        self._symbol_subscriptions: dict[str, set[str]] = defaultdict(set)
        # channel -> set of subscription_ids
        self._channel_subscriptions: dict[ChannelType, set[str]] = defaultdict(set)

    def subscribe(
        self,
        connection_id: str,
        channel: ChannelType,
        symbols: Optional[list[str]] = None,
        throttle_ms: Optional[int] = None,
        filters: Optional[dict] = None,
    ) -> Subscription:
        """Subscribe to a channel with optional symbols."""
        # Validate channel config
        config = CHANNEL_CONFIGS.get(channel, {})

        if config.get("requires_symbols") and not symbols:
            raise ValueError(f"Channel {channel.value} requires symbols")

        max_symbols = config.get("max_symbols", 500)
        if symbols and len(symbols) > max_symbols:
            raise ValueError(f"Max {max_symbols} symbols allowed for {channel.value}")

        # Use channel default throttle if not specified
        if throttle_ms is None:
            throttle_ms = config.get("default_throttle_ms", 100)

        # Create subscription via manager
        subscription = self.manager.subscribe(
            connection_id=connection_id,
            channel=channel,
            symbols=symbols,
            throttle_ms=throttle_ms,
            filters=filters,
        )

        # Update indexes
        self._channel_subscriptions[channel].add(subscription.subscription_id)
        if symbols:
            for symbol in symbols:
                self._symbol_subscriptions[symbol].add(subscription.subscription_id)

        return subscription

    def unsubscribe(self, connection_id: str, subscription_id: str) -> bool:
        """Unsubscribe from a channel."""
        connection = self.manager.get_connection(connection_id)
        if not connection:
            return False

        subscription = connection.subscriptions.get(subscription_id)
        if not subscription:
            return False

        # Remove from indexes
        self._channel_subscriptions[subscription.channel].discard(subscription_id)
        for symbol in subscription.symbols:
            self._symbol_subscriptions[symbol].discard(subscription_id)

        return self.manager.unsubscribe(connection_id, subscription_id)

    def unsubscribe_all(self, connection_id: str) -> int:
        """Unsubscribe from all channels."""
        connection = self.manager.get_connection(connection_id)
        if not connection:
            return 0

        count = 0
        for sub_id in list(connection.subscriptions.keys()):
            if self.unsubscribe(connection_id, sub_id):
                count += 1

        return count

    def add_symbols(
        self,
        connection_id: str,
        subscription_id: str,
        symbols: list[str],
    ) -> bool:
        """Add symbols to an existing subscription."""
        connection = self.manager.get_connection(connection_id)
        if not connection:
            return False

        subscription = connection.subscriptions.get(subscription_id)
        if not subscription:
            return False

        # Check limit
        config = CHANNEL_CONFIGS.get(subscription.channel, {})
        max_symbols = config.get("max_symbols", 500)

        new_count = len(set(subscription.symbols) | set(symbols))
        if new_count > max_symbols:
            raise ValueError(f"Max {max_symbols} symbols allowed")

        # Add symbols
        for symbol in symbols:
            if symbol not in subscription.symbols:
                subscription.symbols.append(symbol)
                self._symbol_subscriptions[symbol].add(subscription_id)

        return True

    def remove_symbols(
        self,
        connection_id: str,
        subscription_id: str,
        symbols: list[str],
    ) -> bool:
        """Remove symbols from a subscription."""
        connection = self.manager.get_connection(connection_id)
        if not connection:
            return False

        subscription = connection.subscriptions.get(subscription_id)
        if not subscription:
            return False

        for symbol in symbols:
            if symbol in subscription.symbols:
                subscription.symbols.remove(symbol)
                self._symbol_subscriptions[symbol].discard(subscription_id)

        return True

    def get_subscribers_for_symbol(self, symbol: str, channel: ChannelType) -> int:
        """Get count of subscribers for a symbol on a channel."""
        count = 0
        sub_ids = self._symbol_subscriptions.get(symbol, set())

        for sub_id in sub_ids:
            # Find the subscription
            for connection in self.manager._connections.values():
                if sub_id in connection.subscriptions:
                    sub = connection.subscriptions[sub_id]
                    if sub.channel == channel and sub.is_active:
                        count += 1
                    break

        return count

    def get_channel_subscriber_count(self, channel: ChannelType) -> int:
        """Get count of subscribers for a channel."""
        return len(self._channel_subscriptions.get(channel, set()))

    def get_popular_symbols(self, channel: ChannelType, limit: int = 10) -> list[tuple[str, int]]:
        """Get most subscribed symbols for a channel."""
        symbol_counts = defaultdict(int)

        for symbol, sub_ids in self._symbol_subscriptions.items():
            for sub_id in sub_ids:
                for connection in self.manager._connections.values():
                    if sub_id in connection.subscriptions:
                        sub = connection.subscriptions[sub_id]
                        if sub.channel == channel and sub.is_active:
                            symbol_counts[symbol] += 1
                        break

        sorted_symbols = sorted(symbol_counts.items(), key=lambda x: -x[1])
        return sorted_symbols[:limit]

    def get_subscription_stats(self) -> dict:
        """Get subscription statistics."""
        channel_stats = {}
        for channel in ChannelType:
            count = self.get_channel_subscriber_count(channel)
            channel_stats[channel.value] = count

        return {
            "total_symbols_tracked": len(self._symbol_subscriptions),
            "channel_subscriptions": channel_stats,
        }
