"""Tests for Webull Broker Integration (PRD-159).

8 test classes, ~50 tests covering config, client, response models,
streaming, extended hours, screener, token manager, and module imports.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# =====================================================================
# Test: WebullConfig
# =====================================================================


class TestWebullConfig:
    """Tests for WebullConfig dataclass."""

    def test_defaults(self):
        from src.webull_broker.client import WebullConfig
        config = WebullConfig()
        assert config.device_id == ""
        assert config.access_token == ""
        assert config.trade_token == ""
        assert config.base_url == "https://userapi.webull.com/api"
        assert config.trade_url == "https://tradeapi.webullbroker.com/api/trade"
        assert config.quotes_url == "https://quotes-gw.webullbroker.com/api"

    def test_custom_device_id(self):
        from src.webull_broker.client import WebullConfig
        config = WebullConfig(device_id="abc-device-123", access_token="tok-xyz")
        assert config.device_id == "abc-device-123"
        assert config.access_token == "tok-xyz"

    def test_trade_url_property(self):
        from src.webull_broker.client import WebullConfig
        config = WebullConfig()
        assert config.order_url == "https://tradeapi.webullbroker.com/api/trade/order"

    def test_quotes_url_property(self):
        from src.webull_broker.client import WebullConfig
        config = WebullConfig()
        assert config.market_url == "https://quotes-gw.webullbroker.com/api/quotes/ticker/getTickerRealTime"
        assert config.screener_url == "https://quotes-gw.webullbroker.com/api/wlas/screener/ng/query"


# =====================================================================
# Test: WebullClient
# =====================================================================


class TestWebullClient:
    """Tests for WebullClient REST operations in demo mode."""

    def _make_client(self, **kwargs):
        from src.webull_broker.client import WebullClient, WebullConfig
        config = WebullConfig(**kwargs)
        return WebullClient(config)

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
        assert account.account_id == "DEMO-WB-88776655"
        assert account.day_trades_remaining == 3
        assert account.buying_power == 50600.00

    @pytest.mark.asyncio
    async def test_get_positions_demo(self):
        client = self._make_client()
        await client.connect()
        positions = await client.get_positions()
        assert len(positions) == 3
        assert positions[0].symbol == "TSLA"
        assert positions[1].symbol == "AMD"
        assert positions[2].symbol == "AAPL"

    @pytest.mark.asyncio
    async def test_get_orders_demo(self):
        client = self._make_client()
        await client.connect()
        orders = await client.get_orders()
        assert len(orders) == 3
        # Check outside_regular_hours flags
        assert orders[0].outside_regular_hours is False
        assert orders[1].outside_regular_hours is True  # Pre-market fill
        assert orders[2].outside_regular_hours is True  # After-hours order

    @pytest.mark.asyncio
    async def test_place_order_demo(self):
        client = self._make_client()
        await client.connect()
        order_req = {
            "symbol": "AAPL",
            "action": "BUY",
            "orderType": "MKT",
            "quantity": 20,
            "outsideRegularTradingHour": True,
        }
        order = await client.place_order(order_req)
        assert order.symbol == "AAPL"
        assert order.quantity == 20
        assert order.outside_regular_hours is True
        assert order.status == "Filled"

    @pytest.mark.asyncio
    async def test_modify_order_demo(self):
        client = self._make_client()
        await client.connect()
        changes = {
            "symbol": "TSLA",
            "action": "BUY",
            "orderType": "LMT",
            "quantity": 15,
            "lmtPrice": 255.00,
            "timeInForce": "GTC",
        }
        order = await client.modify_order("DEMO-WB-ORD-003", changes)
        assert order.order_id == "DEMO-WB-ORD-003"
        assert order.status == "Submitted"
        assert order.limit_price == 255.00

    @pytest.mark.asyncio
    async def test_cancel_order_demo(self):
        client = self._make_client()
        await client.connect()
        result = await client.cancel_order("DEMO-WB-ORD-003")
        assert result is True

    @pytest.mark.asyncio
    async def test_get_quote_demo_single(self):
        client = self._make_client()
        await client.connect()
        quote = await client.get_quote("TSLA")
        assert quote.symbol == "TSLA"
        assert quote.last == 258.75
        assert quote.pre_market_price == 260.15
        assert quote.after_hours_price == 259.30

    @pytest.mark.asyncio
    async def test_get_quotes_demo_multiple(self):
        client = self._make_client()
        await client.connect()
        quotes = await client.get_quotes(["TSLA", "AMD", "AAPL"])
        assert len(quotes) == 3
        symbols = [q.symbol for q in quotes]
        assert "TSLA" in symbols
        assert "AMD" in symbols
        assert "AAPL" in symbols

    @pytest.mark.asyncio
    async def test_get_price_history_demo(self):
        client = self._make_client()
        await client.connect()
        candles = await client.get_price_history("TSLA")
        assert len(candles) == 30
        assert candles[0].open > 0
        assert candles[0].close > 0
        assert candles[0].volume > 0

    @pytest.mark.asyncio
    async def test_get_options_chain_demo(self):
        client = self._make_client()
        await client.connect()
        chain = await client.get_options_chain("AAPL")
        assert chain["symbol"] == "AAPL"
        assert "calls" in chain
        assert "puts" in chain

    @pytest.mark.asyncio
    async def test_get_crypto_quote_demo(self):
        client = self._make_client()
        await client.connect()
        quote = await client.get_crypto_quote("BTC")
        assert quote.symbol == "BTC"
        assert quote.last == 97250.00

    @pytest.mark.asyncio
    async def test_screen_stocks_demo(self):
        client = self._make_client()
        await client.connect()
        results = await client.screen_stocks({})
        assert len(results) == 8
        # With sector filter
        tech_results = await client.screen_stocks({"sector": "Technology"})
        for r in tech_results:
            assert r.sector == "Technology"


# =====================================================================
# Test: Response Models
# =====================================================================


class TestWebullResponseModels:
    """Tests for API response model parsing."""

    def test_account_from_api(self):
        from src.webull_broker.client import WebullAccount
        data = {
            "secAccountId": "12345678",
            "accountType": "INDIVIDUAL",
            "netLiquidation": 95000.0,
            "totalMarketValue": 70000.0,
            "totalCashValue": 25000.0,
            "dayBuyingPower": 50000.0,
            "overnightBuyingPower": 48000.0,
            "unsettledCash": 1200.0,
            "remainingDayTrades": 2,
            "pdt": False,
        }
        account = WebullAccount.from_api(data)
        assert account.account_id == "12345678"
        assert account.day_trades_remaining == 2

    def test_account_to_dict(self):
        from src.webull_broker.client import WebullAccount
        account = WebullAccount(
            account_id="WB-001", day_trades_remaining=3,
            buying_power=50000.0, cash_balance=25000.0,
        )
        d = account.to_dict()
        assert d["account_id"] == "WB-001"
        assert d["day_trades_remaining"] == 3

    def test_position_from_api_ticker_id(self):
        from src.webull_broker.client import WebullPosition
        data = {
            "ticker": {"symbol": "TSLA", "tickerId": 913256135, "close": 258.75},
            "position": 25,
            "costPrice": 242.50,
            "lastPrice": 258.75,
            "assetType": "stock",
        }
        pos = WebullPosition.from_api(data)
        assert pos.symbol == "TSLA"
        assert pos.ticker_id == 913256135

    def test_order_from_api_outside_regular_hours(self):
        from src.webull_broker.client import WebullOrder
        data = {
            "orderId": "ORD-999",
            "ticker": {"symbol": "AMD", "tickerId": 913254235},
            "action": "BUY",
            "orderType": "LMT",
            "totalQuantity": 80,
            "filledQuantity": 80,
            "lmtPrice": 156.00,
            "avgFilledPrice": 155.20,
            "statusStr": "Filled",
            "timeInForce": "GTC",
            "outsideRegularTradingHour": True,
        }
        order = WebullOrder.from_api(data)
        assert order.order_id == "ORD-999"
        assert order.outside_regular_hours is True

    def test_quote_from_api_extended_fields(self):
        from src.webull_broker.client import WebullQuote
        data = {
            "symbol": "TSLA",
            "tickerId": 913256135,
            "quote": {
                "bidPrice": 258.70,
                "askPrice": 258.80,
                "lastPrice": 258.75,
                "open": 252.50,
                "high": 260.10,
                "low": 251.80,
                "close": 258.75,
                "preClose": 252.50,
                "volume": 95200000,
                "avgVol10D": 88500000,
                "change": 6.25,
                "changeRatio": 2.48,
                "preMarketPrice": 260.15,
                "afterHoursPrice": 259.30,
            },
        }
        quote = WebullQuote.from_api(data, symbol="TSLA")
        assert quote.symbol == "TSLA"
        assert quote.pre_market_price == 260.15
        assert quote.after_hours_price == 259.30
        assert quote.avg_volume_10d == 88500000

    def test_candle_from_api(self):
        from src.webull_broker.client import WebullCandle
        data = {
            "open": 252.50, "high": 260.10, "low": 251.80, "close": 258.75,
            "volume": 95200000, "timestamp": "2025-01-20T14:30:00Z",
        }
        candle = WebullCandle.from_api(data)
        assert candle.open == 252.50
        assert candle.high == 260.10
        assert candle.close == 258.75
        assert candle.volume == 95200000

    def test_screener_result_to_dict(self):
        from src.webull_broker.client import WebullScreenerResult
        result = WebullScreenerResult(
            symbol="NVDA", name="NVIDIA Corporation",
            last_price=875.20, change_pct=1.45,
            volume=42000000, market_cap=2160e9,
            pe_ratio=65.0, sector="Technology",
        )
        d = result.to_dict()
        assert d["symbol"] == "NVDA"
        assert d["name"] == "NVIDIA Corporation"
        assert d["change_pct"] == 1.45
        assert d["sector"] == "Technology"

    def test_position_from_api_pnl_calculation(self):
        from src.webull_broker.client import WebullPosition
        data = {
            "ticker": {"symbol": "AAPL", "tickerId": 913256393, "close": 228.50},
            "position": 100,
            "costPrice": 200.00,
            "lastPrice": 228.50,
            "assetType": "stock",
        }
        pos = WebullPosition.from_api(data)
        assert pos.unrealized_pnl == 2850.0  # (228.50 - 200.00) * 100
        assert pos.unrealized_pnl_pct == 14.25  # (28.50 / 200) * 100


# =====================================================================
# Test: Streaming
# =====================================================================


class TestWebullStreaming:
    """Tests for Webull WebSocket streaming."""

    @pytest.mark.asyncio
    async def test_subscribe_unsubscribe(self):
        from src.webull_broker.client import WebullConfig
        from src.webull_broker.streaming import WebullStreaming, StreamChannel
        config = WebullConfig()
        streaming = WebullStreaming(config)
        await streaming.subscribe(["AAPL", "TSLA"], [StreamChannel.QUOTE])
        subs = streaming.subscriptions
        assert "QUOTE" in subs
        assert "AAPL" in subs["QUOTE"]
        assert "TSLA" in subs["QUOTE"]
        await streaming.unsubscribe(["AAPL"], [StreamChannel.QUOTE])
        subs = streaming.subscriptions
        assert "AAPL" not in subs.get("QUOTE", [])
        assert "TSLA" in subs.get("QUOTE", [])

    def test_channels(self):
        from src.webull_broker.streaming import StreamChannel
        assert StreamChannel.QUOTE.value == "QUOTE"
        assert StreamChannel.TRADES.value == "TRADES"
        assert StreamChannel.DEPTH.value == "DEPTH"
        assert StreamChannel.ORDERS.value == "ORDERS"

    @pytest.mark.asyncio
    async def test_start_stop(self):
        from src.webull_broker.client import WebullConfig
        from src.webull_broker.streaming import WebullStreaming
        config = WebullConfig()
        streaming = WebullStreaming(config)
        assert streaming.is_running is False
        await streaming.start()
        assert streaming.is_running is True
        await streaming.stop()
        assert streaming.is_running is False

    def test_stream_event_is_quote(self):
        from src.webull_broker.streaming import StreamEvent, StreamChannel
        quote = StreamEvent(channel=StreamChannel.QUOTE, symbol="AAPL")
        assert quote.is_quote is True
        assert quote.is_trades is False
        assert quote.is_depth is False

    def test_callback_registration(self):
        from src.webull_broker.client import WebullConfig
        from src.webull_broker.streaming import WebullStreaming, StreamChannel
        config = WebullConfig()
        streaming = WebullStreaming(config)
        events = []
        streaming.on_quote(lambda e: events.append(e))
        streaming.on_trades(lambda e: events.append(e))
        streaming.on_depth(lambda e: events.append(e))
        streaming.on_orders(lambda e: events.append(e))
        # Verify all callbacks registered (no error)
        assert len(streaming._callbacks[StreamChannel.QUOTE]) == 1
        assert len(streaming._callbacks[StreamChannel.TRADES]) == 1
        assert len(streaming._callbacks[StreamChannel.DEPTH]) == 1
        assert len(streaming._callbacks[StreamChannel.ORDERS]) == 1


# =====================================================================
# Test: Extended Hours
# =====================================================================


class TestExtendedHours:
    """Tests for extended hours trading features."""

    @pytest.mark.asyncio
    async def test_order_with_ext_hours_true(self):
        from src.webull_broker.client import WebullClient, WebullConfig
        client = WebullClient(WebullConfig())
        await client.connect()
        order_req = {
            "symbol": "TSLA",
            "action": "BUY",
            "orderType": "LMT",
            "quantity": 10,
            "lmtPrice": 255.00,
            "outsideRegularTradingHour": True,
        }
        order = await client.place_order(order_req)
        assert order.outside_regular_hours is True

    @pytest.mark.asyncio
    async def test_quote_has_pre_market_price(self):
        from src.webull_broker.client import WebullClient, WebullConfig
        client = WebullClient(WebullConfig())
        await client.connect()
        quote = await client.get_quote("TSLA")
        assert quote.pre_market_price is not None
        assert quote.pre_market_price == 260.15

    @pytest.mark.asyncio
    async def test_quote_has_after_hours_price(self):
        from src.webull_broker.client import WebullClient, WebullConfig
        client = WebullClient(WebullConfig())
        await client.connect()
        quote = await client.get_quote("AMD")
        assert quote.after_hours_price is not None
        assert quote.after_hours_price == 168.95

    @pytest.mark.asyncio
    async def test_demo_orders_include_ext_hours(self):
        from src.webull_broker.client import WebullClient, WebullConfig
        client = WebullClient(WebullConfig())
        await client.connect()
        orders = await client.get_orders()
        ext_hours_orders = [o for o in orders if o.outside_regular_hours]
        assert len(ext_hours_orders) >= 2


# =====================================================================
# Test: Screener
# =====================================================================


class TestScreener:
    """Tests for Webull stock screener."""

    @pytest.mark.asyncio
    async def test_default_results(self):
        from src.webull_broker.client import WebullClient, WebullConfig
        client = WebullClient(WebullConfig())
        await client.connect()
        results = await client.screen_stocks({})
        assert len(results) == 8

    @pytest.mark.asyncio
    async def test_sector_filter(self):
        from src.webull_broker.client import WebullClient, WebullConfig
        client = WebullClient(WebullConfig())
        await client.connect()
        results = await client.screen_stocks({"sector": "Technology"})
        assert len(results) >= 1
        for r in results:
            assert r.sector == "Technology"

    @pytest.mark.asyncio
    async def test_result_fields(self):
        from src.webull_broker.client import WebullClient, WebullConfig
        client = WebullClient(WebullConfig())
        await client.connect()
        results = await client.screen_stocks({})
        first = results[0]
        assert first.symbol != ""
        assert first.name != ""
        assert isinstance(first.change_pct, float)
        assert first.sector != ""

    @pytest.mark.asyncio
    async def test_sort_order(self):
        from src.webull_broker.client import WebullClient, WebullConfig
        client = WebullClient(WebullConfig())
        await client.connect()
        results = await client.screen_stocks({})
        # The first result should be NVDA based on demo data ordering
        assert results[0].symbol == "NVDA"


# =====================================================================
# Test: TokenManager
# =====================================================================


class TestWebullBrokerTokenManager:
    """Tests for Webull device-based token manager."""

    def test_initial_state(self):
        from src.webull_broker.client import WebullConfig, _TokenManager
        config = WebullConfig()
        mgr = _TokenManager(config)
        assert mgr.access_token == ""
        assert mgr.trade_token == ""
        assert mgr.is_expired is True

    def test_login(self):
        from src.webull_broker.client import WebullConfig, _TokenManager
        config = WebullConfig(access_token="my-access-tok")
        mgr = _TokenManager(config)
        result = mgr.login("device-id-123")
        assert result == "my-access-tok"

    def test_trade_token(self):
        from src.webull_broker.client import WebullConfig, _TokenManager
        config = WebullConfig(trade_token="trade-pin-tok")
        mgr = _TokenManager(config)
        result = mgr.get_trade_token("1234")
        assert result == "trade-pin-tok"


# =====================================================================
# Test: Module Imports
# =====================================================================


class TestWebullBrokerModuleImports:
    """Tests for module import integrity."""

    def test_all_exports_importable(self):
        from src.webull_broker import __all__
        import src.webull_broker as mod
        for name in __all__:
            assert hasattr(mod, name), f"Missing export: {name}"

    def test_config_defaults(self):
        from src.webull_broker import (
            WebullClient,
            WebullConfig,
            WebullStreaming,
            WebullAccount,
            WebullPosition,
            WebullOrder,
            WebullQuote,
            WebullCandle,
            WebullScreenerResult,
        )
        assert WebullClient is not None
        assert WebullConfig is not None
        assert WebullStreaming is not None
        config = WebullConfig()
        assert config.device_id == ""
        assert config.max_requests_per_minute == 60
