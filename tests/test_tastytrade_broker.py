"""Tests for tastytrade Broker Integration (PRD-158).

8 test classes, ~50 tests covering config, client, response models,
streaming, options chain analyzer, session manager, multi-leg orders,
and module imports.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# =====================================================================
# Test: TastytradeConfig
# =====================================================================


class TestTastytradeConfig:
    """Tests for TastytradeConfig dataclass."""

    def test_defaults(self):
        from src.tastytrade_broker.client import TastytradeConfig
        config = TastytradeConfig()
        assert config.username == ""
        assert config.password == ""
        assert config.sandbox is True
        assert config.base_url == config.sandbox_url

    def test_custom_credentials(self):
        from src.tastytrade_broker.client import TastytradeConfig
        config = TastytradeConfig(
            username="trader@example.com",
            password="s3cret",
        )
        assert config.username == "trader@example.com"
        assert config.password == "s3cret"

    def test_url_toggle_sandbox(self):
        from src.tastytrade_broker.client import TastytradeConfig
        config = TastytradeConfig(sandbox=True)
        assert config.base_url == "https://api.cert.tastyworks.com"

    def test_url_toggle_production(self):
        from src.tastytrade_broker.client import TastytradeConfig
        config = TastytradeConfig(sandbox=False)
        assert config.base_url == "https://api.tastyworks.com"


# =====================================================================
# Test: TastytradeClient
# =====================================================================


class TestTastytradeClient:
    """Tests for TastytradeClient REST operations in demo mode."""

    def _make_client(self, **kwargs):
        from src.tastytrade_broker.client import TastytradeClient, TastytradeConfig
        config = TastytradeConfig(**kwargs)
        return TastytradeClient(config)

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
        assert len(accounts) >= 1
        assert accounts[0].account_number == "DEMO-5YT12345"
        assert accounts[0].option_level == 4
        assert accounts[0].futures_enabled is True

    @pytest.mark.asyncio
    async def test_get_positions_equity(self):
        client = self._make_client()
        await client.connect()
        positions = await client.get_positions("DEMO-5YT12345")
        assert len(positions) == 4
        assert positions[0].symbol == "AAPL"
        assert positions[0].instrument_type == "Equity"

    @pytest.mark.asyncio
    async def test_get_positions_option(self):
        client = self._make_client()
        await client.connect()
        positions = await client.get_positions("DEMO-5YT12345")
        assert positions[1].instrument_type == "Equity Option"
        assert positions[1].multiplier == 100

    @pytest.mark.asyncio
    async def test_get_positions_future(self):
        client = self._make_client()
        await client.connect()
        positions = await client.get_positions("DEMO-5YT12345")
        assert positions[2].symbol == "/ESH5"
        assert positions[2].instrument_type == "Future"

    @pytest.mark.asyncio
    async def test_get_positions_cryptocurrency(self):
        client = self._make_client()
        await client.connect()
        positions = await client.get_positions("DEMO-5YT12345")
        assert positions[3].symbol == "BTC/USD"
        assert positions[3].instrument_type == "Cryptocurrency"

    @pytest.mark.asyncio
    async def test_get_orders_demo(self):
        client = self._make_client()
        await client.connect()
        orders = await client.get_orders("DEMO-5YT12345")
        assert len(orders) == 4
        assert orders[0].symbol == "AAPL"
        assert orders[0].status == "Filled"
        # Second order is a spread
        assert orders[1].order_class == "spread"
        # Fourth order is a combo (iron condor)
        assert orders[3].order_class == "combo"

    @pytest.mark.asyncio
    async def test_place_order_demo(self):
        client = self._make_client()
        await client.connect()
        order_req = {
            "order-type": "Market",
            "time-in-force": "Day",
            "legs": [{
                "symbol": "AAPL",
                "action": "Buy to Open",
                "quantity": 50,
                "instrument-type": "Equity",
            }],
        }
        order = await client.place_order("DEMO-5YT12345", order_req)
        assert order.symbol == "AAPL"
        assert order.size == 50
        assert order.status == "Filled"

    @pytest.mark.asyncio
    async def test_place_complex_order_iron_condor(self):
        client = self._make_client()
        await client.connect()
        legs = [
            {"symbol": "SPY  250418C00600000", "action": "Sell to Open", "quantity": 5, "instrument-type": "Equity Option"},
            {"symbol": "SPY  250418C00610000", "action": "Buy to Open", "quantity": 5, "instrument-type": "Equity Option"},
            {"symbol": "SPY  250418P00570000", "action": "Sell to Open", "quantity": 5, "instrument-type": "Equity Option"},
            {"symbol": "SPY  250418P00560000", "action": "Buy to Open", "quantity": 5, "instrument-type": "Equity Option"},
        ]
        order = await client.place_complex_order("DEMO-5YT12345", legs)
        assert order.order_class == "combo"
        assert len(order.legs) == 4

    @pytest.mark.asyncio
    async def test_cancel_order_demo(self):
        client = self._make_client()
        await client.connect()
        result = await client.cancel_order("DEMO-5YT12345", "DEMO-TT-001")
        assert result is True

    @pytest.mark.asyncio
    async def test_get_quote_demo(self):
        client = self._make_client()
        await client.connect()
        quotes = await client.get_quote(["AAPL"])
        assert len(quotes) == 1
        assert quotes[0].symbol == "AAPL"
        assert quotes[0].iv_rank == 28.3
        assert quotes[0].iv_percentile == 42.1

    @pytest.mark.asyncio
    async def test_get_price_history_demo(self):
        client = self._make_client()
        await client.connect()
        candles = await client.get_price_history("AAPL")
        assert len(candles) == 30
        assert candles[0].open > 0
        assert candles[0].close > 0
        assert candles[0].volume > 0

    @pytest.mark.asyncio
    async def test_get_option_chain_demo(self):
        client = self._make_client()
        await client.connect()
        chain = await client.get_option_chain("SPY")
        assert chain["symbol"] == "SPY"
        strikes = chain["strikes"]
        assert len(strikes) == 21  # -10 to +10 inclusive

    @pytest.mark.asyncio
    async def test_get_futures_products_demo(self):
        client = self._make_client()
        await client.connect()
        products = await client.get_futures_products()
        assert len(products) == 6
        symbols = [p["symbol"] for p in products]
        assert "/ES" in symbols
        assert "/NQ" in symbols
        assert "/CL" in symbols
        assert "/GC" in symbols
        assert "/ZB" in symbols
        assert "/RTY" in symbols

    @pytest.mark.asyncio
    async def test_get_crypto_quotes_demo(self):
        client = self._make_client()
        await client.connect()
        quotes = await client.get_crypto_quotes(["BTC/USD", "ETH/USD"])
        assert len(quotes) == 2
        btc = [q for q in quotes if q.symbol == "BTC/USD"][0]
        eth = [q for q in quotes if q.symbol == "ETH/USD"][0]
        assert btc.last == 101500.0
        assert eth.last == 3850.0


# =====================================================================
# Test: Response Models
# =====================================================================


class TestTastytradeResponseModels:
    """Tests for API response model parsing."""

    def test_account_from_api(self):
        from src.tastytrade_broker.client import TastytradeAccount
        data = {
            "account": {
                "account-number": "TT-99887766",
                "account-type-name": "Individual",
                "nickname": "My Options",
                "option-level": 3,
                "futures-enabled": True,
                "margin-or-cash": "Margin",
            },
            "balances": {
                "net-liquidating-value": 125000.0,
                "cash-balance": 48000.0,
                "equity-buying-power": 96000.0,
                "derivative-buying-power": 48000.0,
            },
        }
        account = TastytradeAccount.from_api(data)
        assert account.account_number == "TT-99887766"
        assert account.cash_balance == 48000.0
        assert account.option_level == 3
        assert account.futures_enabled is True

    def test_account_to_dict(self):
        from src.tastytrade_broker.client import TastytradeAccount
        account = TastytradeAccount(
            account_number="TEST-123", option_level=4,
            net_liquidating_value=100000.0, cash_balance=50000.0,
        )
        d = account.to_dict()
        assert d["account_number"] == "TEST-123"
        assert d["option_level"] == 4
        assert d["net_liquidating_value"] == 100000.0

    def test_position_from_api_option_multiplier(self):
        from src.tastytrade_broker.client import TastytradePosition
        data = {
            "symbol": "SPY  250321P00580000",
            "instrument-type": "Equity Option",
            "quantity": 5,
            "average-open-price": 4.20,
            "mark-price": 3.85,
            "close-price": 3.85,
        }
        pos = TastytradePosition.from_api(data)
        assert pos.instrument_type == "Equity Option"
        assert pos.multiplier == 100

    def test_order_from_api_legs(self):
        from src.tastytrade_broker.client import TastytradeOrder
        data = {
            "id": "ORD-555",
            "order-type": "Limit",
            "status": "Filled",
            "filled-quantity": 10,
            "price": 1.25,
            "legs": [
                {"symbol": "SPY  250321P00580000", "action": "Buy to Open", "quantity": 10, "instrument-type": "Equity Option"},
                {"symbol": "SPY  250321P00570000", "action": "Sell to Open", "quantity": 10, "instrument-type": "Equity Option"},
            ],
        }
        order = TastytradeOrder.from_api(data)
        assert order.order_id == "ORD-555"
        assert order.order_class == "spread"
        assert len(order.legs) == 2

    def test_quote_from_api_iv_rank(self):
        from src.tastytrade_broker.client import TastytradeQuote
        data = {
            "symbol": "TSLA",
            "quote": {
                "bid": 382.40,
                "ask": 382.60,
                "last": 382.50,
                "volume": 38000000,
                "net-change": -8.20,
                "net-change-pct": -2.10,
                "implied-volatility-rank": 62.3,
                "implied-volatility-percentile": 75.8,
            },
        }
        quote = TastytradeQuote.from_api(data, symbol="TSLA")
        assert quote.symbol == "TSLA"
        assert quote.iv_rank == 62.3

    def test_candle_from_api(self):
        from src.tastytrade_broker.client import TastytradeCandle
        data = {
            "open": 228.5, "high": 231.5, "low": 227.0, "close": 230.75,
            "volume": 55200000, "datetime": 1705382400000,
        }
        candle = TastytradeCandle.from_api(data)
        assert candle.open == 228.5
        assert candle.high == 231.5
        assert candle.close == 230.75
        assert candle.volume == 55200000

    def test_position_from_api_equity_multiplier(self):
        from src.tastytrade_broker.client import TastytradePosition
        data = {
            "symbol": "AAPL",
            "instrument-type": "Equity",
            "quantity": 100,
            "average-open-price": 218.0,
            "mark-price": 230.75,
            "close-price": 230.75,
        }
        pos = TastytradePosition.from_api(data)
        assert pos.instrument_type == "Equity"
        assert pos.multiplier == 1


# =====================================================================
# Test: Streaming
# =====================================================================


class TestTastytradeStreaming:
    """Tests for tastytrade WebSocket streaming."""

    @pytest.mark.asyncio
    async def test_subscribe_unsubscribe(self):
        from src.tastytrade_broker.client import TastytradeConfig
        from src.tastytrade_broker.streaming import TastytradeStreaming, StreamChannel
        config = TastytradeConfig()
        streaming = TastytradeStreaming(config)
        await streaming.subscribe(["AAPL", "SPY"], [StreamChannel.QUOTE])
        subs = streaming.subscriptions
        assert "QUOTE" in subs
        assert "AAPL" in subs["QUOTE"]
        assert "SPY" in subs["QUOTE"]
        await streaming.unsubscribe(["AAPL"], [StreamChannel.QUOTE])
        subs = streaming.subscriptions
        assert "AAPL" not in subs.get("QUOTE", [])
        assert "SPY" in subs.get("QUOTE", [])

    def test_channels(self):
        from src.tastytrade_broker.streaming import StreamChannel
        assert StreamChannel.QUOTE.value == "QUOTE"
        assert StreamChannel.GREEKS.value == "GREEKS"
        assert StreamChannel.TRADES.value == "TRADES"
        assert StreamChannel.ORDERS.value == "ORDERS"

    @pytest.mark.asyncio
    async def test_start_stop(self):
        from src.tastytrade_broker.client import TastytradeConfig
        from src.tastytrade_broker.streaming import TastytradeStreaming
        config = TastytradeConfig()
        streaming = TastytradeStreaming(config)
        assert streaming.is_running is False
        await streaming.start()
        assert streaming.is_running is True
        await streaming.stop()
        assert streaming.is_running is False

    def test_on_greeks_callback(self):
        from src.tastytrade_broker.client import TastytradeConfig
        from src.tastytrade_broker.streaming import TastytradeStreaming, StreamEvent, StreamChannel
        config = TastytradeConfig()
        streaming = TastytradeStreaming(config)
        events = []
        streaming.on_greeks(lambda e: events.append(e))
        # Verify callback is registered (no error)
        assert len(streaming._callbacks[StreamChannel.GREEKS]) == 1

    def test_stream_event_types(self):
        from src.tastytrade_broker.streaming import StreamEvent, StreamChannel
        quote = StreamEvent(channel=StreamChannel.QUOTE, symbol="AAPL")
        assert quote.is_quote is True
        assert quote.is_greeks is False
        greeks = StreamEvent(channel=StreamChannel.GREEKS, symbol="AAPL")
        assert greeks.is_greeks is True
        assert greeks.is_quote is False
        trade = StreamEvent(channel=StreamChannel.TRADES, symbol="SPY")
        assert trade.is_trade is True
        order = StreamEvent(channel=StreamChannel.ORDERS, symbol="SPY")
        assert order.is_order is True


# =====================================================================
# Test: OptionsChainAnalyzer
# =====================================================================


class TestOptionsChainAnalyzer:
    """Tests for tastytrade options chain analytics."""

    @pytest.mark.asyncio
    async def test_get_expirations(self):
        from src.tastytrade_broker.options_chain import OptionsChainAnalyzer
        analyzer = OptionsChainAnalyzer()
        expirations = await analyzer.get_expirations("SPY")
        assert len(expirations) == 7

    @pytest.mark.asyncio
    async def test_get_chain(self):
        from src.tastytrade_broker.options_chain import OptionsChainAnalyzer
        analyzer = OptionsChainAnalyzer()
        chain = await analyzer.get_chain("SPY", "2025-03-21")
        assert len(chain) == 21  # -10 to +10

    @pytest.mark.asyncio
    async def test_find_optimal_strike_long_call(self):
        from src.tastytrade_broker.options_chain import OptionsChainAnalyzer
        analyzer = OptionsChainAnalyzer()
        strike = await analyzer.find_optimal_strike("SPY", "long_call", target_delta=0.30)
        assert abs(abs(strike.call_greeks.delta) - 0.30) < 0.15

    @pytest.mark.asyncio
    async def test_get_iv_surface(self):
        from src.tastytrade_broker.options_chain import OptionsChainAnalyzer
        analyzer = OptionsChainAnalyzer()
        surface = await analyzer.get_iv_surface("SPY")
        assert len(surface) == 21  # 21 strikes
        # Each strike has entries for 7 expirations
        first_strike = list(surface.values())[0]
        assert len(first_strike) == 7

    def test_option_greeks_to_dict(self):
        from src.tastytrade_broker.options_chain import OptionGreeks
        greeks = OptionGreeks(delta=0.45, gamma=0.03, theta=-0.06, vega=0.20, rho=0.02, iv=0.25)
        d = greeks.to_dict()
        assert d["delta"] == 0.45
        assert d["gamma"] == 0.03
        assert d["theta"] == -0.06
        assert d["vega"] == 0.20
        assert d["rho"] == 0.02
        assert d["iv"] == 0.25

    def test_option_strike_fields(self):
        from src.tastytrade_broker.options_chain import OptionStrike, OptionGreeks
        strike = OptionStrike(
            strike_price=590.0,
            call_bid=5.00, call_ask=5.20, call_last=5.10,
            call_volume=1500, call_oi=8000,
            call_greeks=OptionGreeks(delta=0.48, gamma=0.03, theta=-0.07, vega=0.22, rho=0.02, iv=0.22),
            put_bid=4.50, put_ask=4.70, put_last=4.60,
            put_volume=1200, put_oi=6500,
            put_greeks=OptionGreeks(delta=-0.52, gamma=0.03, theta=-0.06, vega=0.22, rho=-0.03, iv=0.225),
        )
        assert strike.call_greeks.delta == 0.48
        assert strike.put_greeks.delta == -0.52
        assert strike.strike_price == 590.0

    def test_option_expiration_fields(self):
        from src.tastytrade_broker.options_chain import OptionExpiration
        exp = OptionExpiration(
            expiration_date="2025-03-21",
            days_to_expiration=30,
            strikes=[],
        )
        assert exp.expiration_date == "2025-03-21"
        assert exp.days_to_expiration == 30
        assert exp.strikes == []

    def test_option_expiration_to_dict(self):
        from src.tastytrade_broker.options_chain import OptionExpiration
        exp = OptionExpiration(
            expiration_date="2025-04-17",
            days_to_expiration=60,
            strikes=[],
        )
        d = exp.to_dict()
        assert d["expiration_date"] == "2025-04-17"
        assert d["days_to_expiration"] == 60
        assert d["strikes"] == []


# =====================================================================
# Test: SessionManager
# =====================================================================


class TestSessionManager:
    """Tests for tastytrade session-based auth manager."""

    def test_initial_state_no_token(self):
        from src.tastytrade_broker.client import TastytradeConfig, _SessionManager
        config = TastytradeConfig()
        mgr = _SessionManager(config)
        assert mgr.session_token == ""
        assert mgr.is_valid is False

    def test_login_sets_token(self):
        from src.tastytrade_broker.client import TastytradeConfig, _SessionManager
        config = TastytradeConfig(session_token="test-token-abc123")
        mgr = _SessionManager(config)
        assert mgr.session_token == "test-token-abc123"

    def test_auth_headers_format(self):
        from src.tastytrade_broker.client import TastytradeConfig, _SessionManager
        config = TastytradeConfig(session_token="my-session-token")
        mgr = _SessionManager(config)
        headers = mgr.auth_headers()
        assert headers == {"Authorization": "my-session-token"}


# =====================================================================
# Test: Multi-Leg Orders
# =====================================================================


class TestMultiLegOrders:
    """Tests for multi-leg order construction and classification."""

    @pytest.mark.asyncio
    async def test_single_order(self):
        from src.tastytrade_broker.client import TastytradeClient, TastytradeConfig
        client = TastytradeClient(TastytradeConfig())
        await client.connect()
        order_req = {
            "order-type": "Market",
            "time-in-force": "Day",
            "legs": [{
                "symbol": "AAPL",
                "action": "Buy to Open",
                "quantity": 100,
                "instrument-type": "Equity",
            }],
        }
        order = await client.place_order("DEMO-5YT12345", order_req)
        assert order.order_class == "single"
        assert len(order.legs) == 1

    @pytest.mark.asyncio
    async def test_spread_two_legs(self):
        from src.tastytrade_broker.client import TastytradeClient, TastytradeConfig
        client = TastytradeClient(TastytradeConfig())
        await client.connect()
        legs = [
            {"symbol": "SPY  250321P00580000", "action": "Buy to Open", "quantity": 10, "instrument-type": "Equity Option"},
            {"symbol": "SPY  250321P00570000", "action": "Sell to Open", "quantity": 10, "instrument-type": "Equity Option"},
        ]
        order = await client.place_complex_order("DEMO-5YT12345", legs)
        assert order.order_class == "spread"
        assert len(order.legs) == 2

    @pytest.mark.asyncio
    async def test_combo_four_legs(self):
        from src.tastytrade_broker.client import TastytradeClient, TastytradeConfig
        client = TastytradeClient(TastytradeConfig())
        await client.connect()
        legs = [
            {"symbol": "SPY  250418C00600000", "action": "Sell to Open", "quantity": 5, "instrument-type": "Equity Option"},
            {"symbol": "SPY  250418C00610000", "action": "Buy to Open", "quantity": 5, "instrument-type": "Equity Option"},
            {"symbol": "SPY  250418P00570000", "action": "Sell to Open", "quantity": 5, "instrument-type": "Equity Option"},
            {"symbol": "SPY  250418P00560000", "action": "Buy to Open", "quantity": 5, "instrument-type": "Equity Option"},
        ]
        order = await client.place_complex_order("DEMO-5YT12345", legs)
        assert order.order_class == "combo"
        assert len(order.legs) == 4


# =====================================================================
# Test: Module Imports
# =====================================================================


class TestModuleImports:
    """Tests for module import integrity."""

    def test_all_exports_importable(self):
        from src.tastytrade_broker import __all__
        import src.tastytrade_broker as mod
        for name in __all__:
            assert hasattr(mod, name), f"Missing export: {name}"

    def test_config_defaults(self):
        from src.tastytrade_broker import (
            TastytradeClient,
            TastytradeConfig,
            TastytradeStreaming,
            OptionsChainAnalyzer,
            TastytradeAccount,
            TastytradePosition,
            TastytradeOrder,
            TastytradeQuote,
            TastytradeCandle,
            OptionGreeks,
            OptionExpiration,
            OptionStrike,
        )
        assert TastytradeClient is not None
        assert TastytradeConfig is not None
        assert TastytradeStreaming is not None
        assert OptionsChainAnalyzer is not None
        config = TastytradeConfig()
        assert config.sandbox is True
        assert config.max_requests_per_minute == 60
