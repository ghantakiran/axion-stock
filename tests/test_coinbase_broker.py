"""Tests for Coinbase Broker Integration (PRD-144).

8 test classes, ~50 tests covering client, response models, streaming,
portfolio tracker, and module imports.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# =====================================================================
# Test: CoinbaseConfig
# =====================================================================


class TestCoinbaseConfig:
    """Tests for CoinbaseConfig dataclass."""

    def test_defaults(self):
        from src.coinbase_broker.client import CoinbaseConfig
        config = CoinbaseConfig()
        assert config.api_key == ""
        assert config.api_secret == ""
        assert config.base_url == "https://api.coinbase.com/v2"
        assert config.advanced_url == "https://api.coinbase.com/api/v3"

    def test_custom_values(self):
        from src.coinbase_broker.client import CoinbaseConfig
        config = CoinbaseConfig(
            api_key="my_key",
            api_secret="my_secret",
            max_requests_per_minute=50,
        )
        assert config.api_key == "my_key"
        assert config.api_secret == "my_secret"
        assert config.max_requests_per_minute == 50

    def test_ws_url(self):
        from src.coinbase_broker.client import CoinbaseConfig
        config = CoinbaseConfig()
        assert config.ws_url == "wss://advanced-trade-ws.coinbase.com"

    def test_retry_defaults(self):
        from src.coinbase_broker.client import CoinbaseConfig
        config = CoinbaseConfig()
        assert config.max_retries == 3
        assert config.retry_delay == 1.0
        assert config.request_timeout == 30


# =====================================================================
# Test: CoinbaseClient
# =====================================================================


class TestCoinbaseClient:
    """Tests for CoinbaseClient REST operations."""

    def _make_client(self, **kwargs):
        from src.coinbase_broker.client import CoinbaseClient, CoinbaseConfig
        config = CoinbaseConfig(**kwargs)
        return CoinbaseClient(config)

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
    async def test_get_accounts_demo(self):
        client = self._make_client()
        await client.connect()
        accounts = await client.get_accounts()
        assert len(accounts) == 7  # 6 crypto + 1 USD
        currencies = [a.currency for a in accounts]
        assert "BTC" in currencies
        assert "ETH" in currencies
        assert "SOL" in currencies
        assert "USD" in currencies

    @pytest.mark.asyncio
    async def test_get_portfolio_value_demo(self):
        client = self._make_client()
        await client.connect()
        value = await client.get_portfolio_value()
        assert value > 0
        # BTC alone: 0.52 * 95000 = 49400
        assert value > 49000

    @pytest.mark.asyncio
    async def test_get_spot_price_demo(self):
        client = self._make_client()
        await client.connect()
        btc_price = await client.get_spot_price("BTC-USD")
        assert btc_price == 95000.0
        eth_price = await client.get_spot_price("ETH-USD")
        assert eth_price == 3500.0

    @pytest.mark.asyncio
    async def test_list_products_demo(self):
        client = self._make_client()
        await client.connect()
        products = await client.list_products()
        assert len(products) == 6  # one per DEMO_PRICES entry
        product_ids = [p.product_id for p in products]
        assert "BTC-USD" in product_ids
        assert "ETH-USD" in product_ids
        for p in products:
            assert p.status == "online"
            assert p.price > 0

    @pytest.mark.asyncio
    async def test_place_market_order_demo(self):
        client = self._make_client()
        await client.connect()
        order = await client.place_order(
            product_id="BTC-USD", side="BUY", size=0.01, order_type="MARKET"
        )
        assert order.product_id == "BTC-USD"
        assert order.side == "BUY"
        assert order.size == 0.01
        assert order.status == "FILLED"
        assert order.filled_size == 0.01
        assert order.filled_price == 95000.0
        assert order.fee > 0

    @pytest.mark.asyncio
    async def test_place_limit_order_demo(self):
        client = self._make_client()
        await client.connect()
        order = await client.place_order(
            product_id="ETH-USD", side="BUY", size=1.0,
            order_type="LIMIT", limit_price=3400.0,
        )
        assert order.product_id == "ETH-USD"
        assert order.order_type == "LIMIT"
        assert order.status == "PENDING"
        assert order.limit_price == 3400.0

    @pytest.mark.asyncio
    async def test_cancel_order_demo(self):
        client = self._make_client()
        await client.connect()
        result = await client.cancel_order("fake_order_id")
        assert result is True

    @pytest.mark.asyncio
    async def test_get_fills_demo(self):
        client = self._make_client()
        await client.connect()
        fills = await client.get_fills()
        assert len(fills) == 3
        btc_fills = await client.get_fills("BTC-USD")
        assert len(btc_fills) == 1
        assert btc_fills[0].product_id == "BTC-USD"

    @pytest.mark.asyncio
    async def test_get_candles_demo(self):
        client = self._make_client()
        await client.connect()
        candles = await client.get_candles("BTC-USD")
        assert len(candles) == 30
        for c in candles:
            assert c.open > 0
            assert c.close > 0
            assert c.high >= c.low
            assert c.volume > 0


# =====================================================================
# Test: Response Models
# =====================================================================


class TestCoinbaseBrokerResponseModels:
    """Tests for API response model from_api parsing."""

    def test_account_from_api(self):
        from src.coinbase_broker.client import CoinbaseAccount
        data = {
            "uuid": "acct_123",
            "name": "BTC Wallet",
            "currency": "BTC",
            "balance": {"amount": "0.52", "currency": "BTC"},
            "available_balance": {"value": "0.52"},
            "hold": {"amount": "0.0"},
            "native_balance": {"amount": "49400.0", "currency": "USD"},
        }
        acct = CoinbaseAccount.from_api(data)
        assert acct.account_id == "acct_123"
        assert acct.currency == "BTC"
        assert acct.balance == 0.52
        assert acct.native_balance_amount == 49400.0

    def test_order_from_api(self):
        from src.coinbase_broker.client import CoinbaseOrder
        data = {
            "order_id": "ord_456",
            "product_id": "BTC-USD",
            "side": "BUY",
            "order_type": "MARKET",
            "status": "FILLED",
            "filled_size": "0.01",
            "average_filled_price": "95000.0",
            "total_fees": "5.70",
            "order_configuration": {
                "market_market_ioc": {"base_size": "0.01"},
            },
        }
        order = CoinbaseOrder.from_api(data)
        assert order.order_id == "ord_456"
        assert order.product_id == "BTC-USD"
        assert order.filled_price == 95000.0
        assert order.fee == 5.70

    def test_fill_from_api(self):
        from src.coinbase_broker.client import CoinbaseFill
        data = {
            "entry_id": "fill_789",
            "order_id": "ord_456",
            "product_id": "ETH-USD",
            "side": "BUY",
            "price": "3500.0",
            "size": "2.0",
            "commission": "4.20",
            "trade_time": "2025-01-15T10:30:00Z",
        }
        fill = CoinbaseFill.from_api(data)
        assert fill.fill_id == "fill_789"
        assert fill.price == 3500.0
        assert fill.size == 2.0
        assert fill.fee == 4.20

    def test_product_from_api(self):
        from src.coinbase_broker.client import CoinbaseProduct
        data = {
            "product_id": "BTC-USD",
            "base_currency_id": "BTC",
            "quote_currency_id": "USD",
            "base_min_size": "0.00001",
            "base_max_size": "10000",
            "quote_increment": "0.01",
            "status": "online",
            "price": "95000.0",
        }
        product = CoinbaseProduct.from_api(data)
        assert product.product_id == "BTC-USD"
        assert product.base_currency == "BTC"
        assert product.price == 95000.0

    def test_candle_from_api_dict(self):
        from src.coinbase_broker.client import CoinbaseCandle
        data = {
            "start": "1705324800",
            "open": 94000.0,
            "high": 95500.0,
            "low": 93800.0,
            "close": 95000.0,
            "volume": 1234.56,
        }
        candle = CoinbaseCandle.from_api(data)
        assert candle.open == 94000.0
        assert candle.high == 95500.0
        assert candle.close == 95000.0
        assert candle.volume == 1234.56


# =====================================================================
# Test: CoinbaseWebSocket
# =====================================================================


class TestCoinbaseWebSocket:
    """Tests for WebSocket streaming."""

    def test_ws_channel_enum(self):
        from src.coinbase_broker.streaming import WSChannel
        assert WSChannel.TICKER.value == "ticker"
        assert WSChannel.LEVEL2.value == "level2"
        assert WSChannel.MATCHES.value == "matches"
        assert WSChannel.HEARTBEAT.value == "heartbeats"

    def test_ticker_event_from_ws(self):
        from src.coinbase_broker.streaming import TickerEvent
        data = {
            "product_id": "BTC-USD",
            "price": "95000.0",
            "volume_24_h": "12345.67",
            "low_24_h": "93000.0",
            "high_24_h": "96000.0",
            "best_bid": "94990.0",
            "best_ask": "95010.0",
        }
        event = TickerEvent.from_ws(data)
        assert event.product_id == "BTC-USD"
        assert event.price == 95000.0
        assert event.volume_24h == 12345.67

    def test_match_event_from_ws(self):
        from src.coinbase_broker.streaming import MatchEvent
        data = {
            "product_id": "ETH-USD",
            "trade_id": "trade_123",
            "price": "3500.0",
            "size": "1.5",
            "side": "BUY",
        }
        event = MatchEvent.from_ws(data)
        assert event.product_id == "ETH-USD"
        assert event.price == 3500.0
        assert event.size == 1.5

    @pytest.mark.asyncio
    async def test_subscribe_adds_products(self):
        from src.coinbase_broker.client import CoinbaseConfig
        from src.coinbase_broker.streaming import CoinbaseWebSocket, WSChannel
        config = CoinbaseConfig()
        ws = CoinbaseWebSocket(config)
        await ws.subscribe(["BTC-USD", "ETH-USD"], [WSChannel.TICKER])
        subs = ws.subscriptions
        assert "ticker" in subs
        assert "BTC-USD" in subs["ticker"]
        assert "ETH-USD" in subs["ticker"]

    @pytest.mark.asyncio
    async def test_unsubscribe_removes_products(self):
        from src.coinbase_broker.client import CoinbaseConfig
        from src.coinbase_broker.streaming import CoinbaseWebSocket, WSChannel
        config = CoinbaseConfig()
        ws = CoinbaseWebSocket(config)
        await ws.subscribe(["BTC-USD", "ETH-USD"], [WSChannel.TICKER])
        await ws.unsubscribe(["BTC-USD"], [WSChannel.TICKER])
        subs = ws.subscriptions
        assert "BTC-USD" not in subs.get("ticker", [])
        assert "ETH-USD" in subs.get("ticker", [])

    def test_callback_registration(self):
        from src.coinbase_broker.client import CoinbaseConfig
        from src.coinbase_broker.streaming import CoinbaseWebSocket
        config = CoinbaseConfig()
        ws = CoinbaseWebSocket(config)
        events = []
        ws.on_ticker(lambda e: events.append(e))
        ws.on_match(lambda e: events.append(e))
        # No assertion needed - verifying no errors on registration

    @pytest.mark.asyncio
    async def test_start_stop(self):
        from src.coinbase_broker.client import CoinbaseConfig
        from src.coinbase_broker.streaming import CoinbaseWebSocket
        config = CoinbaseConfig()
        ws = CoinbaseWebSocket(config)
        await ws.start()
        assert ws.is_running is True
        await ws.stop()
        assert ws.is_running is False


# =====================================================================
# Test: CryptoPortfolioTracker
# =====================================================================


class TestCryptoPortfolioTracker:
    """Tests for crypto portfolio tracking."""

    @pytest.mark.asyncio
    async def test_sync_accounts(self):
        from src.coinbase_broker.client import CoinbaseClient, CoinbaseConfig
        from src.coinbase_broker.portfolio import CryptoPortfolioTracker
        client = CoinbaseClient(CoinbaseConfig())
        await client.connect()
        tracker = CryptoPortfolioTracker(client)
        accounts = await tracker.sync_accounts()
        assert len(accounts) == 7
        assert tracker.last_sync is not None

    @pytest.mark.asyncio
    async def test_total_value(self):
        from src.coinbase_broker.client import CoinbaseClient, CoinbaseConfig
        from src.coinbase_broker.portfolio import CryptoPortfolioTracker
        client = CoinbaseClient(CoinbaseConfig())
        await client.connect()
        tracker = CryptoPortfolioTracker(client)
        await tracker.sync_accounts()
        value = tracker.get_total_value_usd()
        assert value > 0
        # At least BTC + ETH value
        assert value > 60000

    @pytest.mark.asyncio
    async def test_allocation(self):
        from src.coinbase_broker.client import CoinbaseClient, CoinbaseConfig
        from src.coinbase_broker.portfolio import CryptoPortfolioTracker
        client = CoinbaseClient(CoinbaseConfig())
        await client.connect()
        tracker = CryptoPortfolioTracker(client)
        await tracker.sync_accounts()
        alloc = tracker.get_allocation()
        assert "BTC" in alloc
        assert "ETH" in alloc
        assert "USD" in alloc
        # Weights should sum to ~1.0
        total_weight = sum(alloc.values())
        assert 0.99 <= total_weight <= 1.01

    @pytest.mark.asyncio
    async def test_pnl(self):
        from src.coinbase_broker.client import CoinbaseClient, CoinbaseConfig
        from src.coinbase_broker.portfolio import CryptoPortfolioTracker
        client = CoinbaseClient(CoinbaseConfig())
        await client.connect()
        tracker = CryptoPortfolioTracker(client)
        await tracker.sync_accounts()
        pnl = tracker.get_pnl()
        assert "BTC" in pnl
        assert "pnl" in pnl["BTC"]
        assert "pnl_pct" in pnl["BTC"]
        # BTC bought at 82000, now 95000 => positive P&L
        assert pnl["BTC"]["pnl"] > 0

    @pytest.mark.asyncio
    async def test_historical_values(self):
        from src.coinbase_broker.client import CoinbaseClient, CoinbaseConfig
        from src.coinbase_broker.portfolio import CryptoPortfolioTracker
        client = CoinbaseClient(CoinbaseConfig())
        await client.connect()
        tracker = CryptoPortfolioTracker(client)
        await tracker.sync_accounts()
        history = tracker.get_historical_values(days=30)
        assert len(history) == 30
        for snap in history:
            assert snap.total_value_usd > 0

    @pytest.mark.asyncio
    async def test_snapshot(self):
        from src.coinbase_broker.client import CoinbaseClient, CoinbaseConfig
        from src.coinbase_broker.portfolio import CryptoPortfolioTracker
        client = CoinbaseClient(CoinbaseConfig())
        await client.connect()
        tracker = CryptoPortfolioTracker(client)
        await tracker.sync_accounts()
        snap = tracker.get_snapshot()
        assert snap.total_value_usd > 0
        assert "BTC" in snap.holdings
        assert "BTC" in snap.allocation
        d = snap.to_dict()
        assert "timestamp" in d
        assert "total_value_usd" in d


# =====================================================================
# Test: Additional Client Edge Cases
# =====================================================================


class TestClientEdgeCases:
    """Tests for client edge cases and auth helpers."""

    def test_demo_prices(self):
        from src.coinbase_broker.client import CoinbaseClient, CoinbaseConfig
        client = CoinbaseClient(CoinbaseConfig())
        assert client.DEMO_PRICES["BTC"] == 95000.0
        assert client.DEMO_PRICES["ETH"] == 3500.0
        assert client.DEMO_PRICES["SOL"] == 200.0
        assert client.DEMO_PRICES["DOGE"] == 0.32

    def test_auth_headers(self):
        from src.coinbase_broker.client import CoinbaseClient, CoinbaseConfig
        client = CoinbaseClient(CoinbaseConfig(
            api_key="test_key", api_secret="test_secret",
        ))
        headers = client._auth_headers("GET", "/api/v3/brokerage/accounts")
        assert headers["CB-ACCESS-KEY"] == "test_key"
        assert "CB-ACCESS-SIGN" in headers
        assert "CB-ACCESS-TIMESTAMP" in headers

    @pytest.mark.asyncio
    async def test_get_order_demo_returns_none(self):
        from src.coinbase_broker.client import CoinbaseClient, CoinbaseConfig
        client = CoinbaseClient(CoinbaseConfig())
        await client.connect()
        result = await client.get_order("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_spot_price_unknown_pair(self):
        from src.coinbase_broker.client import CoinbaseClient, CoinbaseConfig
        client = CoinbaseClient(CoinbaseConfig())
        await client.connect()
        price = await client.get_spot_price("UNKNOWN-USD")
        assert price == 100.0  # fallback default


# =====================================================================
# Test: Module Imports
# =====================================================================


class TestCoinbaseBrokerModuleImports:
    """Tests for module import integrity."""

    def test_all_exports_importable(self):
        from src.coinbase_broker import __all__
        import src.coinbase_broker as mod
        for name in __all__:
            assert hasattr(mod, name), f"Missing export: {name}"

    def test_key_classes_importable(self):
        from src.coinbase_broker import (
            CoinbaseClient,
            CoinbaseConfig,
            CoinbaseWebSocket,
            CryptoPortfolioTracker,
            CoinbaseAccount,
            CoinbaseOrder,
            CoinbaseFill,
            CoinbaseProduct,
            CoinbaseCandle,
        )
        assert CoinbaseClient is not None
        assert CoinbaseConfig is not None
        assert CoinbaseWebSocket is not None

    def test_config_defaults(self):
        from src.coinbase_broker import CoinbaseConfig
        config = CoinbaseConfig()
        assert config.base_url == "https://api.coinbase.com/v2"
        assert config.max_retries == 3
