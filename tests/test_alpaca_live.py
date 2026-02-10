"""Tests for Alpaca Live Broker Integration (PRD-139).

8 test classes, ~55 tests covering client, streaming, sync,
order management, market data, and module imports.
"""

import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest


# ═══════════════════════════════════════════════════════════════════════
# Test: AlpacaConfig
# ═══════════════════════════════════════════════════════════════════════


class TestAlpacaConfig:
    """Tests for AlpacaConfig dataclass."""

    def test_defaults(self):
        from src.alpaca_live.client import AlpacaConfig, AlpacaEnvironment
        config = AlpacaConfig()
        assert config.api_key == ""
        assert config.api_secret == ""
        assert config.environment == AlpacaEnvironment.PAPER
        assert config.max_requests_per_minute == 200
        assert config.data_feed == "iex"

    def test_paper_urls(self):
        from src.alpaca_live.client import AlpacaConfig, AlpacaEnvironment
        config = AlpacaConfig(environment=AlpacaEnvironment.PAPER)
        assert "paper" in config.base_url
        assert config.data_url == "https://data.alpaca.markets"
        assert "iex" in config.stream_url

    def test_live_urls(self):
        from src.alpaca_live.client import AlpacaConfig, AlpacaEnvironment
        config = AlpacaConfig(environment=AlpacaEnvironment.LIVE)
        assert "paper" not in config.base_url
        assert config.base_url == "https://api.alpaca.markets"

    def test_sip_data_feed(self):
        from src.alpaca_live.client import AlpacaConfig
        config = AlpacaConfig(data_feed="sip")
        assert "sip" in config.stream_url

    def test_trading_stream_url(self):
        from src.alpaca_live.client import AlpacaConfig, AlpacaEnvironment
        paper = AlpacaConfig(environment=AlpacaEnvironment.PAPER)
        assert "paper" in paper.trading_stream_url
        live = AlpacaConfig(environment=AlpacaEnvironment.LIVE)
        assert "paper" not in live.trading_stream_url


# ═══════════════════════════════════════════════════════════════════════
# Test: AlpacaClient
# ═══════════════════════════════════════════════════════════════════════


class TestAlpacaClient:
    """Tests for AlpacaClient REST operations."""

    def _make_client(self, **kwargs):
        from src.alpaca_live.client import AlpacaClient, AlpacaConfig
        config = AlpacaConfig(**kwargs)
        return AlpacaClient(config)

    @pytest.mark.asyncio
    async def test_connect_demo_no_credentials(self):
        client = self._make_client()
        result = await client.connect()
        assert result is True
        assert client.mode == "demo"
        assert client.is_connected is True

    @pytest.mark.asyncio
    async def test_disconnect(self):
        client = self._make_client()
        await client.connect()
        await client.disconnect()
        assert client.is_connected is False
        assert client.mode == "demo"

    @pytest.mark.asyncio
    async def test_get_account_demo(self):
        client = self._make_client()
        await client.connect()
        account = await client.get_account()
        assert account.account_id == "demo_account"
        assert account.status == "ACTIVE"
        assert account.cash == 50000.0
        assert account.equity == 87400.0

    @pytest.mark.asyncio
    async def test_get_positions_demo(self):
        client = self._make_client()
        await client.connect()
        positions = await client.get_positions()
        assert len(positions) == 2
        assert positions[0].symbol == "AAPL"
        assert positions[0].qty == 100
        assert positions[1].symbol == "MSFT"

    @pytest.mark.asyncio
    async def test_get_position_by_symbol(self):
        client = self._make_client()
        await client.connect()
        pos = await client.get_position("AAPL")
        assert pos is not None
        assert pos.symbol == "AAPL"
        assert pos.qty == 100

    @pytest.mark.asyncio
    async def test_get_position_not_found(self):
        client = self._make_client()
        await client.connect()
        pos = await client.get_position("UNKNOWN")
        assert pos is None

    @pytest.mark.asyncio
    async def test_submit_order_demo(self):
        client = self._make_client()
        await client.connect()
        order = await client.submit_order(
            symbol="AAPL", qty=10, side="buy", order_type="market"
        )
        assert order.symbol == "AAPL"
        assert order.qty == 10.0
        assert order.side == "buy"
        assert order.status == "filled"  # market orders fill immediately in demo

    @pytest.mark.asyncio
    async def test_submit_limit_order_demo(self):
        client = self._make_client()
        await client.connect()
        order = await client.submit_order(
            symbol="MSFT", qty=5, side="buy",
            order_type="limit", limit_price=370.0,
        )
        assert order.symbol == "MSFT"
        assert order.order_type == "limit"
        assert order.status == "new"

    @pytest.mark.asyncio
    async def test_get_bars_demo(self):
        client = self._make_client()
        await client.connect()
        bars = await client.get_bars("AAPL", limit=10)
        assert len(bars) == 10
        assert bars[0].open > 0
        assert bars[0].close > 0
        assert bars[0].volume > 0

    @pytest.mark.asyncio
    async def test_get_snapshot_demo(self):
        client = self._make_client()
        await client.connect()
        snap = await client.get_snapshot("AAPL")
        assert snap.symbol == "AAPL"
        assert snap.latest_trade_price == 185.0

    @pytest.mark.asyncio
    async def test_get_clock_demo(self):
        client = self._make_client()
        await client.connect()
        clock = await client.get_clock()
        assert "is_open" in clock
        assert "timestamp" in clock

    @pytest.mark.asyncio
    async def test_get_asset_demo(self):
        client = self._make_client()
        await client.connect()
        asset = await client.get_asset("AAPL")
        assert asset is not None
        assert asset["symbol"] == "AAPL"
        assert asset["tradable"] is True


# ═══════════════════════════════════════════════════════════════════════
# Test: Response Models
# ═══════════════════════════════════════════════════════════════════════


class TestAlpacaLiveResponseModels:
    """Tests for API response model parsing."""

    def test_account_from_api(self):
        from src.alpaca_live.client import AlpacaAccount
        data = {
            "id": "abc123",
            "status": "ACTIVE",
            "cash": "50000.0",
            "portfolio_value": "87400.0",
            "buying_power": "90000.0",
            "equity": "87400.0",
            "pattern_day_trader": False,
        }
        account = AlpacaAccount.from_api(data)
        assert account.account_id == "abc123"
        assert account.cash == 50000.0
        assert account.equity == 87400.0

    def test_position_from_api(self):
        from src.alpaca_live.client import AlpacaPosition
        data = {
            "asset_id": "xyz",
            "symbol": "AAPL",
            "qty": "100",
            "avg_entry_price": "150.0",
            "current_price": "185.0",
            "market_value": "18500.0",
            "unrealized_pl": "3500.0",
            "side": "long",
        }
        pos = AlpacaPosition.from_api(data)
        assert pos.symbol == "AAPL"
        assert pos.qty == 100.0
        assert pos.unrealized_pl == 3500.0

    def test_order_from_api(self):
        from src.alpaca_live.client import AlpacaOrder
        data = {
            "id": "order123",
            "symbol": "MSFT",
            "qty": "50",
            "filled_qty": "50",
            "filled_avg_price": "378.0",
            "type": "market",
            "side": "buy",
            "status": "filled",
            "time_in_force": "day",
        }
        order = AlpacaOrder.from_api(data)
        assert order.order_id == "order123"
        assert order.filled_avg_price == 378.0
        assert order.status == "filled"

    def test_bar_from_api(self):
        from src.alpaca_live.client import AlpacaBar
        data = {"o": 185.0, "h": 187.0, "l": 184.0, "c": 186.0, "v": 50000000}
        bar = AlpacaBar.from_api(data)
        assert bar.open == 185.0
        assert bar.high == 187.0
        assert bar.volume == 50000000

    def test_quote_from_api(self):
        from src.alpaca_live.client import AlpacaQuote
        data = {"bp": 184.5, "ap": 185.0, "bs": 100, "as": 200}
        quote = AlpacaQuote.from_api(data, symbol="AAPL")
        assert quote.symbol == "AAPL"
        assert quote.bid_price == 184.5
        assert quote.ask_size == 200

    def test_snapshot_from_api(self):
        from src.alpaca_live.client import AlpacaSnapshot
        data = {
            "latestTrade": {"p": 185.0, "s": 100},
            "latestQuote": {"bp": 184.5, "ap": 185.5},
            "dailyBar": {"o": 183, "h": 186, "l": 182, "c": 185, "v": 40000000},
        }
        snap = AlpacaSnapshot.from_api(data, symbol="AAPL")
        assert snap.latest_trade_price == 185.0
        assert snap.daily_bar is not None
        assert snap.daily_bar.close == 185


# ═══════════════════════════════════════════════════════════════════════
# Test: Streaming
# ═══════════════════════════════════════════════════════════════════════


class TestAlpacaStreaming:
    """Tests for WebSocket streaming."""

    def test_stream_channel_enum(self):
        from src.alpaca_live.streaming import StreamChannel
        assert StreamChannel.TRADES.value == "trades"
        assert StreamChannel.QUOTES.value == "quotes"
        assert StreamChannel.BARS.value == "bars"

    def test_stream_event_types(self):
        from src.alpaca_live.streaming import StreamEvent, StreamChannel
        trade = StreamEvent(channel=StreamChannel.TRADES, symbol="AAPL")
        assert trade.is_trade is True
        assert trade.is_quote is False

        quote = StreamEvent(channel=StreamChannel.QUOTES, symbol="MSFT")
        assert quote.is_quote is True
        assert quote.is_bar is False

    def test_order_update_from_stream(self):
        from src.alpaca_live.streaming import OrderUpdate
        data = {
            "event": "fill",
            "order": {
                "id": "abc123",
                "symbol": "AAPL",
                "side": "buy",
                "qty": "100",
                "filled_qty": "100",
                "filled_avg_price": "185.0",
                "type": "market",
                "status": "filled",
            },
        }
        update = OrderUpdate.from_stream(data)
        assert update.event == "fill"
        assert update.order_id == "abc123"
        assert update.filled_avg_price == 185.0

    def test_streaming_subscriptions(self):
        from src.alpaca_live.client import AlpacaConfig
        from src.alpaca_live.streaming import AlpacaStreaming, StreamChannel
        config = AlpacaConfig()
        streaming = AlpacaStreaming(config)
        assert streaming.is_running is False
        assert streaming.subscriptions == {}

    def test_callback_registration(self):
        from src.alpaca_live.client import AlpacaConfig
        from src.alpaca_live.streaming import AlpacaStreaming
        config = AlpacaConfig()
        streaming = AlpacaStreaming(config)

        events = []
        streaming.on_trade(lambda e: events.append(e))
        streaming.on_quote(lambda e: events.append(e))
        streaming.on_order_update(lambda e: events.append(e))
        # No assertion needed — just verifying no errors

    @pytest.mark.asyncio
    async def test_subscribe_adds_symbols(self):
        from src.alpaca_live.client import AlpacaConfig
        from src.alpaca_live.streaming import AlpacaStreaming, StreamChannel
        config = AlpacaConfig()
        streaming = AlpacaStreaming(config)
        await streaming.subscribe(["AAPL", "MSFT"], [StreamChannel.QUOTES])
        subs = streaming.subscriptions
        assert "quotes" in subs
        assert "AAPL" in subs["quotes"]
        assert "MSFT" in subs["quotes"]

    @pytest.mark.asyncio
    async def test_unsubscribe_removes_symbols(self):
        from src.alpaca_live.client import AlpacaConfig
        from src.alpaca_live.streaming import AlpacaStreaming, StreamChannel
        config = AlpacaConfig()
        streaming = AlpacaStreaming(config)
        await streaming.subscribe(["AAPL", "MSFT"], [StreamChannel.QUOTES])
        await streaming.unsubscribe(["AAPL"], [StreamChannel.QUOTES])
        subs = streaming.subscriptions
        assert "AAPL" not in subs.get("quotes", [])
        assert "MSFT" in subs.get("quotes", [])


# ═══════════════════════════════════════════════════════════════════════
# Test: Account Sync
# ═══════════════════════════════════════════════════════════════════════


class TestAccountSync:
    """Tests for account synchronization."""

    def test_sync_state_defaults(self):
        from src.alpaca_live.account_sync import SyncState
        state = SyncState()
        assert state.total_equity == 0.0
        assert state.position_count == 0
        assert state.is_healthy is True
        assert state.symbols_held == []

    def test_sync_state_update_from_account(self):
        from src.alpaca_live.account_sync import SyncState
        from src.alpaca_live.client import AlpacaAccount
        state = SyncState()
        account = AlpacaAccount(equity=100000.0, buying_power=50000.0)
        state.update_from_account(account)
        assert state.total_equity == 100000.0
        assert state.buying_power == 50000.0
        assert state.last_account_sync is not None

    def test_sync_state_update_from_positions(self):
        from src.alpaca_live.account_sync import SyncState
        from src.alpaca_live.client import AlpacaPosition
        state = SyncState()
        positions = [
            AlpacaPosition(symbol="AAPL", qty=100, market_value=18500.0, unrealized_pl=3500.0),
            AlpacaPosition(symbol="MSFT", qty=50, market_value=18900.0, unrealized_pl=1400.0),
        ]
        state.update_from_positions(positions)
        assert state.position_count == 2
        assert state.total_market_value == 37400.0
        assert state.total_unrealized_pnl == 4900.0
        assert "AAPL" in state.symbols_held

    def test_sync_state_get_position(self):
        from src.alpaca_live.account_sync import SyncState
        from src.alpaca_live.client import AlpacaPosition
        state = SyncState()
        state.positions = [
            AlpacaPosition(symbol="AAPL", qty=100),
            AlpacaPosition(symbol="MSFT", qty=50),
        ]
        assert state.get_position("AAPL") is not None
        assert state.get_position("AAPL").qty == 100
        assert state.get_position("UNKNOWN") is None

    def test_sync_state_record_error(self):
        from src.alpaca_live.account_sync import SyncState
        state = SyncState()
        for _ in range(5):
            state.record_error()
        assert state.sync_errors == 5
        assert state.consecutive_failures == 5
        assert state.is_healthy is False

    def test_sync_state_to_dict(self):
        from src.alpaca_live.account_sync import SyncState
        state = SyncState(total_equity=100000.0, position_count=3, is_healthy=True)
        d = state.to_dict()
        assert d["total_equity"] == 100000.0
        assert d["position_count"] == 3
        assert d["is_healthy"] is True

    def test_sync_config_defaults(self):
        from src.alpaca_live.account_sync import SyncConfig
        config = SyncConfig()
        assert config.account_interval == 30.0
        assert config.position_interval == 10.0
        assert config.order_interval == 5.0
        assert config.enabled is True

    @pytest.mark.asyncio
    async def test_sync_all(self):
        from src.alpaca_live.client import AlpacaClient, AlpacaConfig
        from src.alpaca_live.account_sync import AccountSync
        client = AlpacaClient(AlpacaConfig())
        await client.connect()
        sync = AccountSync(client)
        state = await sync.sync_all()
        assert state.account is not None
        assert state.total_equity > 0
        assert state.position_count == 2


# ═══════════════════════════════════════════════════════════════════════
# Test: Order Manager
# ═══════════════════════════════════════════════════════════════════════


class TestOrderManager:
    """Tests for order lifecycle management."""

    def test_managed_order_defaults(self):
        from src.alpaca_live.order_manager import ManagedOrder, OrderLifecycleState
        order = ManagedOrder()
        assert order.state == OrderLifecycleState.PENDING
        assert order.is_active is True
        assert order.is_terminal is False
        assert order.fill_pct == 0.0

    def test_managed_order_terminal_states(self):
        from src.alpaca_live.order_manager import ManagedOrder, OrderLifecycleState
        for state in [
            OrderLifecycleState.FILLED,
            OrderLifecycleState.CANCELED,
            OrderLifecycleState.REJECTED,
            OrderLifecycleState.EXPIRED,
            OrderLifecycleState.FAILED,
        ]:
            order = ManagedOrder(state=state)
            assert order.is_terminal is True
            assert order.is_active is False

    def test_managed_order_fill_pct(self):
        from src.alpaca_live.order_manager import ManagedOrder
        order = ManagedOrder(qty=100, filled_qty=50)
        assert order.fill_pct == 50.0

    def test_managed_order_to_dict(self):
        from src.alpaca_live.order_manager import ManagedOrder
        order = ManagedOrder(symbol="AAPL", side="buy", qty=100)
        d = order.to_dict()
        assert d["symbol"] == "AAPL"
        assert d["side"] == "buy"
        assert d["qty"] == 100
        assert "state" in d
        assert "created_at" in d

    def test_update_from_alpaca(self):
        from src.alpaca_live.order_manager import ManagedOrder, OrderLifecycleState
        from src.alpaca_live.client import AlpacaOrder
        order = ManagedOrder(symbol="AAPL", qty=100)
        alpaca = AlpacaOrder(
            order_id="abc", status="filled",
            filled_qty=100, filled_avg_price=185.0,
        )
        order.update_from_alpaca(alpaca)
        assert order.state == OrderLifecycleState.FILLED
        assert order.filled_avg_price == 185.0
        assert order.filled_at is not None

    def test_update_from_stream(self):
        from src.alpaca_live.order_manager import ManagedOrder, OrderLifecycleState
        from src.alpaca_live.streaming import OrderUpdate
        order = ManagedOrder(symbol="AAPL", qty=100)
        update = OrderUpdate(
            event="partial_fill", order_id="abc",
            filled_qty=50, filled_avg_price=185.0,
        )
        order.update_from_stream(update)
        assert order.state == OrderLifecycleState.PARTIAL
        assert order.filled_qty == 50

    @pytest.mark.asyncio
    async def test_submit_order(self):
        from src.alpaca_live.client import AlpacaClient, AlpacaConfig
        from src.alpaca_live.order_manager import OrderManager, OrderLifecycleState
        client = AlpacaClient(AlpacaConfig())
        await client.connect()
        manager = OrderManager(client)
        order = await manager.submit_order(
            symbol="AAPL", qty=10, side="buy",
            signal_id="test_signal",
        )
        assert order.symbol == "AAPL"
        assert order.qty == 10
        assert order.signal_id == "test_signal"
        # In demo mode, market orders fill immediately
        assert order.state in (
            OrderLifecycleState.FILLED, OrderLifecycleState.SUBMITTED
        )

    @pytest.mark.asyncio
    async def test_active_and_filled_orders(self):
        from src.alpaca_live.client import AlpacaClient, AlpacaConfig
        from src.alpaca_live.order_manager import OrderManager
        client = AlpacaClient(AlpacaConfig())
        await client.connect()
        manager = OrderManager(client)
        await manager.submit_order(symbol="AAPL", qty=10, side="buy")
        await manager.submit_order(symbol="MSFT", qty=5, side="buy")
        assert len(manager.orders) == 2
        assert len(manager.get_order_history()) == 2

    @pytest.mark.asyncio
    async def test_get_orders_for_symbol(self):
        from src.alpaca_live.client import AlpacaClient, AlpacaConfig
        from src.alpaca_live.order_manager import OrderManager
        client = AlpacaClient(AlpacaConfig())
        await client.connect()
        manager = OrderManager(client)
        await manager.submit_order(symbol="AAPL", qty=10, side="buy")
        await manager.submit_order(symbol="MSFT", qty=5, side="buy")
        aapl_orders = manager.get_orders_for_symbol("AAPL")
        assert len(aapl_orders) == 1
        assert aapl_orders[0].symbol == "AAPL"


# ═══════════════════════════════════════════════════════════════════════
# Test: Market Data
# ═══════════════════════════════════════════════════════════════════════


class TestMarketData:
    """Tests for market data provider."""

    @pytest.mark.asyncio
    async def test_get_bars(self):
        from src.alpaca_live.client import AlpacaClient, AlpacaConfig
        from src.alpaca_live.market_data import MarketDataProvider
        client = AlpacaClient(AlpacaConfig())
        await client.connect()
        provider = MarketDataProvider(client)
        bars = await provider.get_bars("AAPL", limit=20)
        assert len(bars) == 20
        assert bars[0].open > 0

    @pytest.mark.asyncio
    async def test_get_ohlcv_df(self):
        from src.alpaca_live.client import AlpacaClient, AlpacaConfig
        from src.alpaca_live.market_data import MarketDataProvider
        client = AlpacaClient(AlpacaConfig())
        await client.connect()
        provider = MarketDataProvider(client)
        df = await provider.get_ohlcv_df("AAPL", limit=30)
        assert isinstance(df, pd.DataFrame)
        assert "open" in df.columns
        assert "close" in df.columns
        assert "volume" in df.columns
        assert len(df) == 30

    @pytest.mark.asyncio
    async def test_get_multi_ohlcv(self):
        from src.alpaca_live.client import AlpacaClient, AlpacaConfig
        from src.alpaca_live.market_data import MarketDataProvider
        client = AlpacaClient(AlpacaConfig())
        await client.connect()
        provider = MarketDataProvider(client)
        data = await provider.get_multi_ohlcv(["AAPL", "MSFT"])
        assert "AAPL" in data
        assert "MSFT" in data

    @pytest.mark.asyncio
    async def test_get_snapshot(self):
        from src.alpaca_live.client import AlpacaClient, AlpacaConfig
        from src.alpaca_live.market_data import MarketDataProvider
        client = AlpacaClient(AlpacaConfig())
        await client.connect()
        provider = MarketDataProvider(client)
        snap = await provider.get_snapshot("AAPL")
        assert snap.symbol == "AAPL"
        assert snap.latest_trade_price > 0

    @pytest.mark.asyncio
    async def test_get_latest_prices(self):
        from src.alpaca_live.client import AlpacaClient, AlpacaConfig
        from src.alpaca_live.market_data import MarketDataProvider
        client = AlpacaClient(AlpacaConfig())
        await client.connect()
        provider = MarketDataProvider(client)
        prices = await provider.get_latest_prices(["AAPL", "MSFT"])
        assert "AAPL" in prices
        assert prices["AAPL"] > 0

    def test_cache_staleness(self):
        from src.alpaca_live.market_data import MarketDataCache
        cache = MarketDataCache(cache_ttl=1.0)
        assert cache.is_stale("test") is True
        cache.last_refresh["test"] = datetime.now(timezone.utc)
        assert cache.is_stale("test") is False

    @pytest.mark.asyncio
    async def test_cache_hit(self):
        from src.alpaca_live.client import AlpacaClient, AlpacaConfig
        from src.alpaca_live.market_data import MarketDataProvider
        client = AlpacaClient(AlpacaConfig())
        await client.connect()
        provider = MarketDataProvider(client, cache_ttl=300)
        # First call populates cache
        snap1 = await provider.get_snapshot("AAPL")
        # Second call should use cache
        snap2 = await provider.get_snapshot("AAPL")
        assert snap1.symbol == snap2.symbol

    @pytest.mark.asyncio
    async def test_market_hours(self):
        from src.alpaca_live.client import AlpacaClient, AlpacaConfig
        from src.alpaca_live.market_data import MarketDataProvider
        client = AlpacaClient(AlpacaConfig())
        await client.connect()
        provider = MarketDataProvider(client)
        hours = await provider.get_market_hours()
        assert "is_open" in hours


# ═══════════════════════════════════════════════════════════════════════
# Test: Module Imports
# ═══════════════════════════════════════════════════════════════════════


class TestAlpacaLiveModuleImports:
    """Tests for module import integrity."""

    def test_all_exports_importable(self):
        from src.alpaca_live import __all__
        import src.alpaca_live as mod
        for name in __all__:
            assert hasattr(mod, name), f"Missing export: {name}"

    def test_key_classes_importable(self):
        from src.alpaca_live import (
            AlpacaClient,
            AlpacaConfig,
            AlpacaEnvironment,
            AlpacaStreaming,
            AccountSync,
            OrderManager,
            MarketDataProvider,
        )
        assert AlpacaClient is not None
        assert AlpacaConfig is not None
        assert AlpacaEnvironment is not None

    def test_config_defaults(self):
        from src.alpaca_live import AlpacaConfig, AlpacaEnvironment
        config = AlpacaConfig()
        assert config.environment == AlpacaEnvironment.PAPER
        assert config.max_retries == 3

    def test_order_lifecycle_states(self):
        from src.alpaca_live import OrderLifecycleState
        assert OrderLifecycleState.PENDING.value == "pending"
        assert OrderLifecycleState.FILLED.value == "filled"
        assert OrderLifecycleState.CANCELED.value == "canceled"
