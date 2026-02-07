"""Tests for PRD-59: Real-time WebSocket API."""

import pytest
from datetime import datetime, timezone, timedelta

from src.websocket.config import (
    ChannelType,
    MessageType,
    ConnectionStatus,
    WebSocketConfig,
    DEFAULT_WEBSOCKET_CONFIG,
    CHANNEL_CONFIGS,
)
from src.websocket.models import (
    WebSocketConnection,
    Subscription,
    StreamMessage,
    QuoteData,
    TradeData,
    BarData,
    OrderUpdate,
    PortfolioUpdate,
    AlertNotification,
)
from src.websocket.manager import ConnectionManager
from src.websocket.subscriptions import SubscriptionManager
from src.websocket.channels import ChannelRouter


class TestWebSocketConfig:
    """Tests for WebSocket configuration."""

    def test_channel_types(self):
        """Test channel type enum."""
        assert ChannelType.QUOTES.value == "quotes"
        assert ChannelType.TRADES.value == "trades"
        assert ChannelType.BARS.value == "bars"
        assert ChannelType.ORDERS.value == "orders"
        assert ChannelType.PORTFOLIO.value == "portfolio"
        assert ChannelType.ALERTS.value == "alerts"
        assert ChannelType.NEWS.value == "news"

    def test_message_types(self):
        """Test message type enum."""
        assert MessageType.CONNECTED.value == "connected"
        assert MessageType.SUBSCRIBED.value == "subscribed"
        assert MessageType.UPDATE.value == "update"
        assert MessageType.ERROR.value == "error"

    def test_connection_status(self):
        """Test connection status enum."""
        assert ConnectionStatus.CONNECTING.value == "connecting"
        assert ConnectionStatus.CONNECTED.value == "connected"
        assert ConnectionStatus.DISCONNECTED.value == "disconnected"

    def test_default_config(self):
        """Test default WebSocket config."""
        config = DEFAULT_WEBSOCKET_CONFIG
        assert config.max_connections_per_user > 0
        assert config.max_total_connections > 0
        assert config.heartbeat_interval_seconds > 0
        assert config.default_throttle_ms > 0

    def test_channel_configs(self):
        """Test channel configurations."""
        quotes_config = CHANNEL_CONFIGS.get(ChannelType.QUOTES)
        assert quotes_config is not None
        assert "requires_symbols" in quotes_config
        assert "default_throttle_ms" in quotes_config


class TestWebSocketConnection:
    """Tests for WebSocket connection model."""

    def test_connection_creation(self):
        """Test connection creation."""
        conn = WebSocketConnection(user_id="user123")
        assert conn.user_id == "user123"
        assert conn.connection_id is not None
        assert conn.session_token is not None
        assert conn.status == ConnectionStatus.CONNECTING
        assert conn.messages_sent == 0
        assert conn.messages_received == 0

    def test_connection_heartbeat(self):
        """Test heartbeat update."""
        conn = WebSocketConnection(user_id="user123")
        old_heartbeat = conn.last_heartbeat
        # Small delay to ensure time difference
        import time
        time.sleep(0.01)
        conn.update_heartbeat()
        assert conn.last_heartbeat >= old_heartbeat

    def test_add_subscription(self):
        """Test adding subscription to connection."""
        conn = WebSocketConnection(user_id="user123")
        sub = Subscription(channel=ChannelType.QUOTES, symbols=["AAPL"])
        conn.add_subscription(sub)
        assert sub.subscription_id in conn.subscriptions
        assert conn.subscriptions[sub.subscription_id] == sub

    def test_remove_subscription(self):
        """Test removing subscription from connection."""
        conn = WebSocketConnection(user_id="user123")
        sub = Subscription(channel=ChannelType.QUOTES)
        conn.add_subscription(sub)
        removed = conn.remove_subscription(sub.subscription_id)
        assert removed == sub
        assert sub.subscription_id not in conn.subscriptions

    def test_get_subscriptions_for_channel(self):
        """Test getting subscriptions by channel."""
        conn = WebSocketConnection(user_id="user123")
        sub1 = Subscription(channel=ChannelType.QUOTES, symbols=["AAPL"])
        sub2 = Subscription(channel=ChannelType.TRADES, symbols=["MSFT"])
        sub3 = Subscription(channel=ChannelType.QUOTES, symbols=["GOOGL"])
        conn.add_subscription(sub1)
        conn.add_subscription(sub2)
        conn.add_subscription(sub3)

        quote_subs = conn.get_subscriptions_for_channel(ChannelType.QUOTES)
        assert len(quote_subs) == 2

    def test_connection_to_dict(self):
        """Test connection serialization."""
        conn = WebSocketConnection(user_id="user123")
        data = conn.to_dict()
        assert "connection_id" in data
        assert data["user_id"] == "user123"
        assert "status" in data
        assert "connected_at" in data


class TestSubscription:
    """Tests for subscription model."""

    def test_subscription_creation(self):
        """Test subscription creation."""
        sub = Subscription(channel=ChannelType.QUOTES, symbols=["AAPL", "MSFT"])
        assert sub.channel == ChannelType.QUOTES
        assert sub.symbols == ["AAPL", "MSFT"]
        assert sub.is_active
        assert sub.throttle_ms == 100

    def test_matches_symbol(self):
        """Test symbol matching."""
        sub = Subscription(channel=ChannelType.QUOTES, symbols=["AAPL", "MSFT"])
        assert sub.matches_symbol("AAPL")
        assert sub.matches_symbol("MSFT")
        assert not sub.matches_symbol("GOOGL")

    def test_matches_all_symbols_when_empty(self):
        """Test that empty symbols list matches all."""
        sub = Subscription(channel=ChannelType.QUOTES, symbols=[])
        assert sub.matches_symbol("AAPL")
        assert sub.matches_symbol("ANY_SYMBOL")

    def test_throttling(self):
        """Test message throttling."""
        sub = Subscription(channel=ChannelType.QUOTES, throttle_ms=100)
        # No message yet, should not throttle
        assert not sub.should_throttle()
        # Mark delivered
        sub.mark_delivered()
        # Immediately after, should throttle
        assert sub.should_throttle()

    def test_no_throttle_when_zero(self):
        """Test no throttling when throttle_ms is 0."""
        sub = Subscription(channel=ChannelType.QUOTES, throttle_ms=0)
        sub.mark_delivered()
        assert not sub.should_throttle()

    def test_mark_delivered(self):
        """Test marking message as delivered."""
        sub = Subscription(channel=ChannelType.QUOTES)
        assert sub.messages_delivered == 0
        sub.mark_delivered()
        assert sub.messages_delivered == 1
        assert sub.last_message_at is not None

    def test_subscription_to_dict(self):
        """Test subscription serialization."""
        sub = Subscription(channel=ChannelType.QUOTES, symbols=["AAPL"])
        data = sub.to_dict()
        assert data["channel"] == "quotes"
        assert data["symbols"] == ["AAPL"]
        assert data["is_active"]


class TestStreamMessage:
    """Tests for stream message model."""

    def test_message_creation(self):
        """Test message creation."""
        msg = StreamMessage(
            type=MessageType.UPDATE,
            channel=ChannelType.QUOTES,
            data={"symbol": "AAPL", "price": 185.50},
        )
        assert msg.type == MessageType.UPDATE
        assert msg.channel == ChannelType.QUOTES
        assert msg.data["symbol"] == "AAPL"

    def test_message_to_dict(self):
        """Test message serialization."""
        msg = StreamMessage(
            type=MessageType.UPDATE,
            channel=ChannelType.QUOTES,
            data={"price": 185.50},
            sequence=123,
        )
        data = msg.to_dict()
        assert data["type"] == "update"
        assert data["channel"] == "quotes"
        assert data["sequence"] == 123
        assert "timestamp" in data

    def test_error_message_factory(self):
        """Test error message creation."""
        msg = StreamMessage.error_message("Connection failed")
        assert msg.type == MessageType.ERROR
        assert msg.error == "Connection failed"

    def test_connected_message_factory(self):
        """Test connected message creation."""
        msg = StreamMessage.connected_message("conn123")
        assert msg.type == MessageType.CONNECTED
        assert msg.data["connection_id"] == "conn123"

    def test_subscribed_message_factory(self):
        """Test subscribed message creation."""
        sub = Subscription(channel=ChannelType.QUOTES, symbols=["AAPL"])
        msg = StreamMessage.subscribed_message(sub)
        assert msg.type == MessageType.SUBSCRIBED
        assert msg.channel == ChannelType.QUOTES


class TestQuoteData:
    """Tests for quote data model."""

    def test_quote_creation(self):
        """Test quote data creation."""
        quote = QuoteData(
            symbol="AAPL",
            bid=185.50,
            ask=185.52,
            last=185.51,
            bid_size=100,
            ask_size=200,
            volume=45000000,
            change=2.51,
            change_pct=1.37,
        )
        assert quote.symbol == "AAPL"
        assert quote.bid == 185.50
        assert quote.ask == 185.52
        assert quote.last == 185.51

    def test_quote_to_dict(self):
        """Test quote serialization."""
        quote = QuoteData(symbol="AAPL", bid=185.50, ask=185.52, last=185.51)
        data = quote.to_dict()
        assert data["symbol"] == "AAPL"
        assert data["bid"] == 185.50
        assert "timestamp" in data


class TestTradeData:
    """Tests for trade data model."""

    def test_trade_creation(self):
        """Test trade data creation."""
        trade = TradeData(
            symbol="AAPL",
            price=185.51,
            size=100,
            exchange="NYSE",
        )
        assert trade.symbol == "AAPL"
        assert trade.price == 185.51
        assert trade.size == 100
        assert trade.exchange == "NYSE"

    def test_trade_to_dict(self):
        """Test trade serialization."""
        trade = TradeData(symbol="AAPL", price=185.51, size=100)
        data = trade.to_dict()
        assert data["symbol"] == "AAPL"
        assert data["price"] == 185.51


class TestBarData:
    """Tests for bar data model."""

    def test_bar_creation(self):
        """Test bar data creation."""
        bar = BarData(
            symbol="AAPL",
            interval="1m",
            open=185.00,
            high=185.75,
            low=184.80,
            close=185.51,
            volume=150000,
        )
        assert bar.symbol == "AAPL"
        assert bar.interval == "1m"
        assert bar.open == 185.00
        assert bar.close == 185.51

    def test_bar_to_dict(self):
        """Test bar serialization."""
        bar = BarData(
            symbol="AAPL",
            interval="1m",
            open=185.00,
            high=185.75,
            low=184.80,
            close=185.51,
        )
        data = bar.to_dict()
        assert data["symbol"] == "AAPL"
        assert data["interval"] == "1m"


class TestOrderUpdate:
    """Tests for order update model."""

    def test_order_update_creation(self):
        """Test order update creation."""
        order = OrderUpdate(
            order_id="ord123",
            symbol="AAPL",
            status="filled",
            side="buy",
            order_type="market",
            quantity=100,
            filled_quantity=100,
            avg_fill_price=185.50,
        )
        assert order.order_id == "ord123"
        assert order.status == "filled"
        assert order.filled_quantity == 100

    def test_order_update_to_dict(self):
        """Test order update serialization."""
        order = OrderUpdate(
            order_id="ord123",
            symbol="AAPL",
            status="pending",
            side="buy",
            order_type="limit",
            quantity=100,
        )
        data = order.to_dict()
        assert data["order_id"] == "ord123"
        assert data["status"] == "pending"


class TestPortfolioUpdate:
    """Tests for portfolio update model."""

    def test_portfolio_update_creation(self):
        """Test portfolio update creation."""
        portfolio = PortfolioUpdate(
            total_value=100000.0,
            cash_balance=10000.0,
            positions_value=90000.0,
            day_pnl=500.0,
            day_return_pct=0.5,
            total_pnl=15000.0,
            total_return_pct=17.6,
        )
        assert portfolio.total_value == 100000.0
        assert portfolio.day_pnl == 500.0

    def test_portfolio_update_to_dict(self):
        """Test portfolio update serialization."""
        portfolio = PortfolioUpdate(
            total_value=100000.0,
            cash_balance=10000.0,
            positions_value=90000.0,
            day_pnl=500.0,
            day_return_pct=0.5,
            total_pnl=15000.0,
            total_return_pct=17.6,
        )
        data = portfolio.to_dict()
        assert data["total_value"] == 100000.0
        assert "positions" in data


class TestAlertNotification:
    """Tests for alert notification model."""

    def test_alert_creation(self):
        """Test alert notification creation."""
        alert = AlertNotification(
            alert_id="alert123",
            alert_type="price",
            symbol="AAPL",
            condition="price > 190",
            message="AAPL crossed $190",
            triggered_value=190.50,
        )
        assert alert.alert_id == "alert123"
        assert alert.alert_type == "price"
        assert alert.triggered_value == 190.50

    def test_alert_to_dict(self):
        """Test alert serialization."""
        alert = AlertNotification(
            alert_id="alert123",
            alert_type="volume",
            symbol="AAPL",
            condition="volume > 50M",
            message="High volume detected",
        )
        data = alert.to_dict()
        assert data["alert_id"] == "alert123"
        assert data["alert_type"] == "volume"


class TestConnectionManager:
    """Tests for connection manager."""

    def test_create_connection(self):
        """Test creating a connection."""
        manager = ConnectionManager()
        conn = manager.create_connection(user_id="user123")
        assert conn.user_id == "user123"
        assert conn.status == ConnectionStatus.CONNECTED
        assert manager.connection_count == 1

    def test_get_connection(self):
        """Test getting a connection by ID."""
        manager = ConnectionManager()
        conn = manager.create_connection(user_id="user123")
        retrieved = manager.get_connection(conn.connection_id)
        assert retrieved == conn

    def test_get_nonexistent_connection(self):
        """Test getting a nonexistent connection."""
        manager = ConnectionManager()
        conn = manager.get_connection("nonexistent")
        assert conn is None

    def test_get_user_connections(self):
        """Test getting all connections for a user."""
        manager = ConnectionManager()
        conn1 = manager.create_connection(user_id="user123")
        conn2 = manager.create_connection(user_id="user123")
        manager.create_connection(user_id="user456")

        user_conns = manager.get_user_connections("user123")
        assert len(user_conns) == 2
        assert conn1 in user_conns
        assert conn2 in user_conns

    def test_disconnect(self):
        """Test disconnecting a connection."""
        manager = ConnectionManager()
        conn = manager.create_connection(user_id="user123")
        result = manager.disconnect(conn.connection_id)
        assert result
        assert manager.connection_count == 0
        assert manager.get_connection(conn.connection_id) is None

    def test_heartbeat(self):
        """Test heartbeat processing."""
        manager = ConnectionManager()
        conn = manager.create_connection(user_id="user123")
        old_heartbeat = conn.last_heartbeat
        import time
        time.sleep(0.01)
        result = manager.heartbeat(conn.connection_id)
        assert result
        assert conn.last_heartbeat >= old_heartbeat

    def test_subscribe(self):
        """Test subscribing to a channel."""
        manager = ConnectionManager()
        conn = manager.create_connection(user_id="user123")
        sub = manager.subscribe(
            connection_id=conn.connection_id,
            channel=ChannelType.QUOTES,
            symbols=["AAPL", "MSFT"],
        )
        assert sub.channel == ChannelType.QUOTES
        assert sub.symbols == ["AAPL", "MSFT"]
        assert sub.subscription_id in conn.subscriptions

    def test_unsubscribe(self):
        """Test unsubscribing from a channel."""
        manager = ConnectionManager()
        conn = manager.create_connection(user_id="user123")
        sub = manager.subscribe(
            connection_id=conn.connection_id,
            channel=ChannelType.QUOTES,
        )
        result = manager.unsubscribe(conn.connection_id, sub.subscription_id)
        assert result
        assert not sub.is_active

    def test_broadcast_to_channel(self):
        """Test broadcasting to a channel."""
        manager = ConnectionManager()
        conn = manager.create_connection(user_id="user123")
        manager.subscribe(
            connection_id=conn.connection_id,
            channel=ChannelType.QUOTES,
            symbols=["AAPL"],
            throttle_ms=0,  # No throttling
        )

        delivered = manager.broadcast_to_channel(
            ChannelType.QUOTES,
            {"price": 185.50},
            symbol="AAPL",
        )
        assert delivered == 1

    def test_send_to_user(self):
        """Test sending to a specific user."""
        manager = ConnectionManager()
        conn1 = manager.create_connection(user_id="user123")
        conn2 = manager.create_connection(user_id="user123")
        manager.create_connection(user_id="user456")

        msg = StreamMessage(type=MessageType.UPDATE, data={"test": True})
        sent = manager.send_to_user("user123", msg)
        assert sent == 2

    def test_max_connections_per_user(self):
        """Test max connections per user limit."""
        config = WebSocketConfig(max_connections_per_user=2)
        manager = ConnectionManager(config=config)
        manager.create_connection(user_id="user123")
        manager.create_connection(user_id="user123")
        with pytest.raises(ConnectionError):
            manager.create_connection(user_id="user123")

    def test_get_stats(self):
        """Test getting connection statistics."""
        manager = ConnectionManager()
        conn = manager.create_connection(user_id="user123")
        manager.subscribe(
            connection_id=conn.connection_id,
            channel=ChannelType.QUOTES,
        )

        stats = manager.get_stats()
        assert stats["active_connections"] == 1
        assert stats["total_subscriptions"] == 1
        assert stats["users_connected"] == 1


class TestSubscriptionManager:
    """Tests for subscription manager."""

    def test_subscribe(self):
        """Test subscribing through subscription manager."""
        conn_manager = ConnectionManager()
        sub_manager = SubscriptionManager(conn_manager)
        conn = conn_manager.create_connection(user_id="user123")

        sub = sub_manager.subscribe(
            connection_id=conn.connection_id,
            channel=ChannelType.QUOTES,
            symbols=["AAPL"],
        )
        assert sub.channel == ChannelType.QUOTES
        assert "AAPL" in sub.symbols

    def test_unsubscribe(self):
        """Test unsubscribing through subscription manager."""
        conn_manager = ConnectionManager()
        sub_manager = SubscriptionManager(conn_manager)
        conn = conn_manager.create_connection(user_id="user123")
        sub = sub_manager.subscribe(
            connection_id=conn.connection_id,
            channel=ChannelType.QUOTES,
            symbols=["AAPL"],
        )

        result = sub_manager.unsubscribe(conn.connection_id, sub.subscription_id)
        assert result

    def test_unsubscribe_all(self):
        """Test unsubscribing from all channels."""
        conn_manager = ConnectionManager()
        sub_manager = SubscriptionManager(conn_manager)
        conn = conn_manager.create_connection(user_id="user123")
        sub_manager.subscribe(conn.connection_id, ChannelType.QUOTES, symbols=["AAPL"])
        sub_manager.subscribe(conn.connection_id, ChannelType.TRADES, symbols=["MSFT"])

        count = sub_manager.unsubscribe_all(conn.connection_id)
        assert count == 2
        assert len(conn.subscriptions) == 0

    def test_add_symbols(self):
        """Test adding symbols to subscription."""
        conn_manager = ConnectionManager()
        sub_manager = SubscriptionManager(conn_manager)
        conn = conn_manager.create_connection(user_id="user123")
        sub = sub_manager.subscribe(
            connection_id=conn.connection_id,
            channel=ChannelType.QUOTES,
            symbols=["AAPL"],
        )

        result = sub_manager.add_symbols(conn.connection_id, sub.subscription_id, ["MSFT"])
        assert result
        assert "MSFT" in sub.symbols

    def test_remove_symbols(self):
        """Test removing symbols from subscription."""
        conn_manager = ConnectionManager()
        sub_manager = SubscriptionManager(conn_manager)
        conn = conn_manager.create_connection(user_id="user123")
        sub = sub_manager.subscribe(
            connection_id=conn.connection_id,
            channel=ChannelType.QUOTES,
            symbols=["AAPL", "MSFT"],
        )

        result = sub_manager.remove_symbols(conn.connection_id, sub.subscription_id, ["MSFT"])
        assert result
        assert "MSFT" not in sub.symbols
        assert "AAPL" in sub.symbols

    def test_get_channel_subscriber_count(self):
        """Test getting subscriber count for a channel."""
        conn_manager = ConnectionManager()
        sub_manager = SubscriptionManager(conn_manager)

        conn1 = conn_manager.create_connection(user_id="user1")
        conn2 = conn_manager.create_connection(user_id="user2")
        sub_manager.subscribe(conn1.connection_id, ChannelType.QUOTES, symbols=["AAPL"])
        sub_manager.subscribe(conn2.connection_id, ChannelType.QUOTES, symbols=["MSFT"])
        sub_manager.subscribe(conn1.connection_id, ChannelType.TRADES, symbols=["GOOGL"])

        count = sub_manager.get_channel_subscriber_count(ChannelType.QUOTES)
        assert count == 2

    def test_get_subscription_stats(self):
        """Test getting subscription statistics."""
        conn_manager = ConnectionManager()
        sub_manager = SubscriptionManager(conn_manager)
        conn = conn_manager.create_connection(user_id="user123")
        sub_manager.subscribe(
            connection_id=conn.connection_id,
            channel=ChannelType.QUOTES,
            symbols=["AAPL", "MSFT"],
        )

        stats = sub_manager.get_subscription_stats()
        assert "total_symbols_tracked" in stats
        assert "channel_subscriptions" in stats


class TestChannelRouter:
    """Tests for channel router."""

    def test_list_channels(self):
        """Test listing available channels."""
        manager = ConnectionManager()
        router = ChannelRouter(manager)
        channels = router.list_channels()
        assert len(channels) > 0
        assert any(ch["channel"] == "quotes" for ch in channels)

    def test_get_channel_info(self):
        """Test getting channel information."""
        manager = ConnectionManager()
        router = ChannelRouter(manager)
        info = router.get_channel_info(ChannelType.QUOTES)
        assert info["channel"] == "quotes"
        assert "requires_symbols" in info
        assert "default_throttle_ms" in info

    def test_publish_quote(self):
        """Test publishing a quote."""
        manager = ConnectionManager()
        router = ChannelRouter(manager)
        conn = manager.create_connection(user_id="user123")
        manager.subscribe(
            connection_id=conn.connection_id,
            channel=ChannelType.QUOTES,
            symbols=["AAPL"],
            throttle_ms=0,
        )

        quote = QuoteData(symbol="AAPL", bid=185.50, ask=185.52, last=185.51)
        delivered = router.publish_quote(quote)
        assert delivered == 1

    def test_publish_trade(self):
        """Test publishing a trade."""
        manager = ConnectionManager()
        router = ChannelRouter(manager)
        conn = manager.create_connection(user_id="user123")
        manager.subscribe(
            connection_id=conn.connection_id,
            channel=ChannelType.TRADES,
            symbols=["AAPL"],
            throttle_ms=0,
        )

        trade = TradeData(symbol="AAPL", price=185.51, size=100)
        delivered = router.publish_trade(trade)
        assert delivered == 1

    def test_publish_bar(self):
        """Test publishing a bar."""
        manager = ConnectionManager()
        router = ChannelRouter(manager)
        conn = manager.create_connection(user_id="user123")
        manager.subscribe(
            connection_id=conn.connection_id,
            channel=ChannelType.BARS,
            symbols=["AAPL"],
            throttle_ms=0,
        )

        bar = BarData(
            symbol="AAPL",
            interval="1m",
            open=185.00,
            high=185.75,
            low=184.80,
            close=185.51,
        )
        delivered = router.publish_bar(bar)
        assert delivered == 1

    def test_register_handler(self):
        """Test registering a channel handler."""
        manager = ConnectionManager()
        router = ChannelRouter(manager)

        def my_handler(data):
            pass

        router.register_handler(ChannelType.QUOTES, my_handler)
        assert ChannelType.QUOTES in router._handlers

    def test_get_snapshot(self):
        """Test getting channel snapshot."""
        manager = ConnectionManager()
        router = ChannelRouter(manager)

        snapshot = router.get_snapshot(ChannelType.QUOTES, symbol="AAPL")
        assert snapshot is not None
        assert snapshot["symbol"] == "AAPL"

    def test_get_portfolio_snapshot(self):
        """Test getting portfolio snapshot."""
        manager = ConnectionManager()
        router = ChannelRouter(manager)

        snapshot = router.get_snapshot(ChannelType.PORTFOLIO)
        assert snapshot is not None
        assert "total_value" in snapshot


class TestStaleConnectionHandling:
    """Tests for stale connection handling."""

    def test_check_stale_connections(self):
        """Test checking for stale connections."""
        config = WebSocketConfig(heartbeat_timeout_seconds=1)
        manager = ConnectionManager(config=config)
        conn = manager.create_connection(user_id="user123")

        # Should not be stale immediately
        stale = manager.check_stale_connections()
        assert len(stale) == 0

        # Manually set old heartbeat
        conn.last_heartbeat = datetime.now(timezone.utc) - timedelta(seconds=2)
        stale = manager.check_stale_connections()
        assert conn.connection_id in stale

    def test_prune_stale_connections(self):
        """Test pruning stale connections."""
        config = WebSocketConfig(heartbeat_timeout_seconds=1)
        manager = ConnectionManager(config=config)
        conn = manager.create_connection(user_id="user123")
        conn.last_heartbeat = datetime.now(timezone.utc) - timedelta(seconds=2)

        count = manager.prune_stale_connections()
        assert count == 1
        assert manager.connection_count == 0


class TestSymbolRouting:
    """Tests for symbol-based message routing."""

    def test_symbol_specific_broadcast(self):
        """Test broadcasting to specific symbol subscribers."""
        manager = ConnectionManager()
        conn1 = manager.create_connection(user_id="user1")
        conn2 = manager.create_connection(user_id="user2")

        manager.subscribe(
            connection_id=conn1.connection_id,
            channel=ChannelType.QUOTES,
            symbols=["AAPL"],
            throttle_ms=0,
        )
        manager.subscribe(
            connection_id=conn2.connection_id,
            channel=ChannelType.QUOTES,
            symbols=["MSFT"],
            throttle_ms=0,
        )

        # Broadcast AAPL - only conn1 should receive
        delivered = manager.broadcast_to_channel(
            ChannelType.QUOTES,
            {"price": 185.50},
            symbol="AAPL",
        )
        assert delivered == 1

    def test_all_symbols_subscription(self):
        """Test subscription to all symbols."""
        manager = ConnectionManager()
        conn = manager.create_connection(user_id="user123")
        manager.subscribe(
            connection_id=conn.connection_id,
            channel=ChannelType.QUOTES,
            symbols=[],  # Empty = all symbols
            throttle_ms=0,
        )

        # Should receive any symbol
        delivered = manager.broadcast_to_channel(
            ChannelType.QUOTES,
            {"price": 185.50},
            symbol="ANY_SYMBOL",
        )
        assert delivered == 1
