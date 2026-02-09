"""Tests for Interactive Brokers (IBKR) Integration (PRD-157).

8 test classes, ~50 tests covering config, client, response models,
streaming, gateway, token manager, contract search, and module imports.
"""

import asyncio
from datetime import datetime, timezone

import pytest


# =====================================================================
# Test: IBKRConfig
# =====================================================================


class TestIBKRConfig:
    """Tests for IBKRConfig dataclass."""

    def test_defaults(self):
        from src.ibkr_broker.client import IBKRConfig
        config = IBKRConfig()
        assert config.gateway_host == "localhost"
        assert config.gateway_port == 5000
        assert config.ssl_verify is False
        assert config.account_id == ""
        assert config.max_requests_per_minute == 50

    def test_gateway_url_property(self):
        from src.ibkr_broker.client import IBKRConfig
        config = IBKRConfig()
        assert config.gateway_url == "https://localhost:5000/v1/api"

    def test_custom_account_id(self):
        from src.ibkr_broker.client import IBKRConfig
        config = IBKRConfig(account_id="U9876543")
        assert config.account_id == "U9876543"

    def test_rate_limit(self):
        from src.ibkr_broker.client import IBKRConfig
        config = IBKRConfig()
        assert config.max_requests_per_minute == 50
        config2 = IBKRConfig(max_requests_per_minute=30)
        assert config2.max_requests_per_minute == 30

    def test_auth_and_token_urls(self):
        from src.ibkr_broker.client import IBKRConfig
        config = IBKRConfig()
        assert "iserver/auth/status" in config.auth_url
        assert "interactivebrokers" in config.token_url


# =====================================================================
# Test: IBKRClient
# =====================================================================


class TestIBKRClient:
    """Tests for IBKRClient REST operations."""

    def _make_client(self, **kwargs):
        from src.ibkr_broker.client import IBKRClient, IBKRConfig
        # Use short timeout so gateway connection attempt fails fast
        # and falls back to demo mode without hanging.
        kwargs.setdefault("request_timeout", 1)
        config = IBKRConfig(**kwargs)
        return IBKRClient(config)

    @pytest.mark.asyncio
    async def test_connect_demo(self):
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
    async def test_get_accounts(self):
        client = self._make_client()
        await client.connect()
        accounts = await client.get_accounts()
        assert len(accounts) >= 1
        assert accounts[0].net_liquidation == 285400.0
        assert accounts[0].base_currency == "USD"
        assert accounts[0].position_count == 4

    @pytest.mark.asyncio
    async def test_get_positions(self):
        client = self._make_client()
        await client.connect()
        positions = await client.get_positions()
        assert len(positions) == 4
        # STK positions
        assert positions[0].symbol == "SPY"
        assert positions[0].asset_class == "STK"
        assert positions[1].symbol == "AAPL"
        assert positions[1].asset_class == "STK"
        # Forex (CASH) position
        assert positions[2].symbol == "EUR.USD"
        assert positions[2].asset_class == "CASH"
        # Futures position
        assert positions[3].symbol == "ESH5"
        assert positions[3].asset_class == "FUT"

    @pytest.mark.asyncio
    async def test_get_orders(self):
        client = self._make_client()
        await client.connect()
        orders = await client.get_orders()
        assert len(orders) == 3
        assert orders[0].symbol == "AAPL"
        assert orders[0].status == "Filled"
        assert orders[1].symbol == "SPY"
        assert orders[2].symbol == "ESH5"

    @pytest.mark.asyncio
    async def test_place_order(self):
        client = self._make_client()
        await client.connect()
        order = await client.place_order("DU1234567", {
            "conid": 265598,
            "side": "BUY",
            "quantity": 100,
            "orderType": "MKT",
            "tif": "DAY",
        })
        assert order.symbol == "AAPL"
        assert order.quantity == 100
        assert order.status == "Filled"
        assert order.order_type == "MKT"

    @pytest.mark.asyncio
    async def test_modify_order(self):
        client = self._make_client()
        await client.connect()
        order = await client.modify_order("DU1234567", "DEMO-IB-001", {
            "price": 235.0,
            "quantity": 150,
            "orderType": "LMT",
        })
        assert order.order_id == "DEMO-IB-001"
        assert order.quantity == 150
        assert order.price == 235.0
        assert order.status == "PreSubmitted"

    @pytest.mark.asyncio
    async def test_cancel_order(self):
        client = self._make_client()
        await client.connect()
        result = await client.cancel_order("DU1234567", "DEMO-IB-001")
        assert result is True

    @pytest.mark.asyncio
    async def test_get_quote(self):
        client = self._make_client()
        await client.connect()
        quotes = await client.get_quote(["SPY", "AAPL", "EURUSD", "ES"])
        assert len(quotes) == 4
        spy = [q for q in quotes if q.symbol == "SPY"][0]
        assert spy.last == 590.50
        assert spy.bid == 590.45
        eur = [q for q in quotes if q.symbol == "EUR.USD"][0]
        assert eur.last == 1.0875
        es = [q for q in quotes if q.symbol == "ESH5"][0]
        assert es.last == 5965.50

    @pytest.mark.asyncio
    async def test_search_contract(self):
        client = self._make_client()
        await client.connect()
        contracts = await client.search_contract("ES", sec_type="FUT")
        assert len(contracts) >= 1
        assert contracts[0].sec_type == "FUT"
        assert contracts[0].symbol == "ES"

    @pytest.mark.asyncio
    async def test_get_forex_pairs(self):
        client = self._make_client()
        await client.connect()
        pairs = await client.get_forex_pairs()
        assert len(pairs) == 10
        for pair in pairs:
            assert pair.sec_type == "CASH"
            assert pair.exchange == "IDEALPRO"

    @pytest.mark.asyncio
    async def test_get_price_history(self):
        client = self._make_client()
        await client.connect()
        candles = await client.get_price_history(265598)
        assert len(candles) == 30
        assert candles[0].open > 0
        assert candles[0].close > 0
        assert candles[0].volume > 0
        assert candles[0].wap > 0
        assert candles[0].trade_count > 0


# =====================================================================
# Test: Response Models
# =====================================================================


class TestIBKRResponseModels:
    """Tests for API response model parsing."""

    def test_account_from_api(self):
        from src.ibkr_broker.client import IBKRAccount
        data = {
            "accountId": "U1234567",
            "type": "INDIVIDUAL",
            "currency": "USD",
            "summary": {
                "netliquidation": {"amount": 285400.0, "currency": "USD"},
                "buyingpower": {"amount": 571200.0, "currency": "USD"},
                "excessliquidity": {"amount": 168200.0, "currency": "USD"},
                "sma": {"amount": 285400.0, "currency": "USD"},
            },
            "positionCount": 4,
        }
        account = IBKRAccount.from_api(data)
        assert account.account_id == "U1234567"
        assert account.net_liquidation == 285400.0
        assert account.buying_power == 571200.0

    def test_account_to_dict(self):
        from src.ibkr_broker.client import IBKRAccount
        account = IBKRAccount(
            account_id="U999", net_liquidation=100000.0,
            sma=100000.0, excess_liquidity=50000.0,
        )
        d = account.to_dict()
        assert d["account_id"] == "U999"
        assert d["sma"] == 100000.0
        assert d["excess_liquidity"] == 50000.0

    def test_position_from_api(self):
        from src.ibkr_broker.client import IBKRPosition
        stk = IBKRPosition.from_api({
            "conid": 265598, "contractDesc": "AAPL", "assetClass": "STK",
            "position": 200, "avgCost": 218.0, "mktPrice": 230.75,
            "mktValue": 46150.0, "unrealizedPnl": 2550.0, "currency": "USD",
        })
        assert stk.symbol == "AAPL"
        assert stk.asset_class == "STK"
        assert stk.quantity == 200

        cash = IBKRPosition.from_api({
            "conid": 12087792, "contractDesc": "EUR.USD", "assetClass": "CASH",
            "position": 50000, "avgCost": 1.0820, "mktPrice": 1.0875,
        })
        assert cash.asset_class == "CASH"

        fut = IBKRPosition.from_api({
            "conid": 495512552, "contractDesc": "ESH5", "assetClass": "FUT",
            "position": 2, "avgCost": 5920.0, "mktPrice": 5965.50,
        })
        assert fut.asset_class == "FUT"

    def test_order_from_api(self):
        from src.ibkr_broker.client import IBKROrder
        data = {
            "orderId": "12345",
            "conid": 265598,
            "ticker": "AAPL",
            "side": "BUY",
            "totalSize": 100,
            "filledQuantity": 100,
            "price": 218.0,
            "orderType": "LMT",
            "timeInForce": "DAY",
            "status": "Filled",
            "acct": "U1234567",
        }
        order = IBKROrder.from_api(data)
        assert order.order_id == "12345"
        assert order.symbol == "AAPL"
        assert order.status == "Filled"
        assert order.filled_quantity == 100

    def test_quote_from_api(self):
        from src.ibkr_broker.client import IBKRQuote
        data = {
            "conid": 265598,
            "55": "AAPL",
            "31": 230.75,
            "84": 230.70,
            "85": 230.80,
            "82": 1.85,
            "83": 0.81,
            "6509": "Open",
        }
        quote = IBKRQuote.from_api(data)
        assert quote.symbol == "AAPL"
        assert quote.last == 230.75
        assert quote.bid == 230.70
        assert quote.market_status == "Open"

    def test_candle_from_api(self):
        from src.ibkr_broker.client import IBKRCandle
        data = {
            "o": 228.5, "h": 231.5, "l": 227.0, "c": 230.75,
            "v": 55200000, "wap": 229.44, "n": 150000,
            "t": 1705382400000,
        }
        candle = IBKRCandle.from_api(data)
        assert candle.open == 228.5
        assert candle.high == 231.5
        assert candle.close == 230.75
        assert candle.volume == 55200000
        assert candle.wap == 229.44
        assert candle.trade_count == 150000

    def test_contract_from_api(self):
        from src.ibkr_broker.client import IBKRContract
        data = {
            "conid": 265598,
            "symbol": "AAPL",
            "secType": "STK",
            "listingExchange": "NASDAQ",
            "currency": "USD",
            "companyName": "Apple Inc",
        }
        contract = IBKRContract.from_api(data)
        assert contract.conid == 265598
        assert contract.symbol == "AAPL"
        assert contract.sec_type == "STK"
        assert contract.exchange == "NASDAQ"

    def test_quote_from_api_named_keys(self):
        from src.ibkr_broker.client import IBKRQuote
        data = {
            "conid": 756733,
            "symbol": "SPY",
            "lastPrice": 590.50,
            "bid": 590.45,
            "ask": 590.55,
            "volume": 78500000,
            "change": 2.30,
            "changePercent": 0.39,
            "marketStatus": "Open",
        }
        quote = IBKRQuote.from_api(data)
        assert quote.symbol == "SPY"
        assert quote.last == 590.50
        assert quote.market_status == "Open"


# =====================================================================
# Test: Streaming
# =====================================================================


class TestIBKRStreaming:
    """Tests for WebSocket streaming."""

    def test_stream_channels(self):
        from src.ibkr_broker.streaming import StreamChannel
        assert StreamChannel.QUOTE.value == "QUOTE"
        assert StreamChannel.TRADES.value == "TRADES"
        assert StreamChannel.DEPTH.value == "DEPTH"
        assert StreamChannel.ORDERS.value == "ORDERS"
        assert StreamChannel.PNL.value == "PNL"

    @pytest.mark.asyncio
    async def test_subscribe_unsubscribe(self):
        from src.ibkr_broker.client import IBKRConfig
        from src.ibkr_broker.streaming import IBKRStreaming, StreamChannel
        config = IBKRConfig()
        streaming = IBKRStreaming(config)
        await streaming.subscribe(["AAPL", "SPY"], [StreamChannel.QUOTE])
        subs = streaming.subscriptions
        assert "QUOTE" in subs
        assert "AAPL" in subs["QUOTE"]
        assert "SPY" in subs["QUOTE"]
        await streaming.unsubscribe(["AAPL"], [StreamChannel.QUOTE])
        subs = streaming.subscriptions
        assert "AAPL" not in subs.get("QUOTE", [])
        assert "SPY" in subs.get("QUOTE", [])

    @pytest.mark.asyncio
    async def test_start_stop(self):
        from src.ibkr_broker.client import IBKRConfig
        from src.ibkr_broker.streaming import IBKRStreaming
        config = IBKRConfig()
        streaming = IBKRStreaming(config)
        await streaming.start()
        assert streaming.is_running is True
        await streaming.stop()
        assert streaming.is_running is False

    def test_callback_registration(self):
        from src.ibkr_broker.client import IBKRConfig
        from src.ibkr_broker.streaming import IBKRStreaming
        config = IBKRConfig()
        streaming = IBKRStreaming(config)
        events = []
        streaming.on_quote(lambda e: events.append(e))
        streaming.on_trade(lambda e: events.append(e))
        streaming.on_depth(lambda e: events.append(e))
        streaming.on_order(lambda e: events.append(e))
        streaming.on_pnl(lambda e: events.append(e))
        # Verify all 5 callbacks registered without error
        assert streaming.is_running is False

    def test_stream_event_types(self):
        from src.ibkr_broker.streaming import StreamEvent, StreamChannel
        quote = StreamEvent(channel=StreamChannel.QUOTE, symbol="AAPL", conid=265598)
        assert quote.is_quote is True
        assert quote.is_trade is False
        trade = StreamEvent(channel=StreamChannel.TRADES, symbol="SPY", conid=756733)
        assert trade.is_trade is True
        assert trade.is_quote is False
        depth = StreamEvent(channel=StreamChannel.DEPTH, symbol="MSFT")
        assert depth.is_depth is True
        order = StreamEvent(channel=StreamChannel.ORDERS, symbol="AAPL")
        assert order.is_order is True
        pnl = StreamEvent(channel=StreamChannel.PNL, symbol="")
        assert pnl.is_pnl is True


# =====================================================================
# Test: Gateway
# =====================================================================


class TestIBKRGateway:
    """Tests for IBKR Client Portal Gateway management."""

    @pytest.mark.asyncio
    async def test_check_status(self):
        from src.ibkr_broker.client import IBKRConfig
        from src.ibkr_broker.gateway import IBKRGateway
        config = IBKRConfig()
        gateway = IBKRGateway(config)
        status = await gateway.check_status()
        assert status.connected is True
        assert status.authenticated is True
        assert status.server_name == "IBKR-Demo-Gateway"
        assert status.competing is False

    @pytest.mark.asyncio
    async def test_reauthenticate(self):
        from src.ibkr_broker.client import IBKRConfig
        from src.ibkr_broker.gateway import IBKRGateway
        config = IBKRConfig()
        gateway = IBKRGateway(config)
        result = await gateway.reauthenticate()
        assert result is True

    @pytest.mark.asyncio
    async def test_keep_alive(self):
        from src.ibkr_broker.client import IBKRConfig
        from src.ibkr_broker.gateway import IBKRGateway
        config = IBKRConfig()
        gateway = IBKRGateway(config)
        result = await gateway.keep_alive()
        assert result is True

    @pytest.mark.asyncio
    async def test_get_server_info(self):
        from src.ibkr_broker.client import IBKRConfig
        from src.ibkr_broker.gateway import IBKRGateway
        config = IBKRConfig()
        gateway = IBKRGateway(config)
        info = await gateway.get_server_info()
        assert info["serverName"] == "IBKR-Demo-Gateway"
        assert "features" in info
        assert info["features"]["optionChains"] is True
        assert info["features"]["futures"] is True
        assert info["features"]["forex"] is True

    @pytest.mark.asyncio
    async def test_competing_session(self):
        from src.ibkr_broker.gateway import GatewayStatus
        status = GatewayStatus(
            connected=True, authenticated=True, competing=True,
            server_name="IBKR-Live", server_version="10.25.0",
        )
        assert status.competing is True
        d = status.to_dict()
        assert d["competing"] is True
        assert d["server_name"] == "IBKR-Live"


# =====================================================================
# Test: TokenManager
# =====================================================================


class TestTokenManager:
    """Tests for OAuth2 token management."""

    def test_initial_expired(self):
        from src.ibkr_broker.client import IBKRConfig, _TokenManager
        config = IBKRConfig()
        mgr = _TokenManager(config)
        assert mgr.is_expired is True
        assert mgr.access_token == ""

    def test_set_tokens(self):
        from src.ibkr_broker.client import IBKRConfig, _TokenManager
        config = IBKRConfig()
        mgr = _TokenManager(config)
        mgr.set_tokens("ibkr-access-abc", "ibkr-refresh-xyz", expires_in=3600)
        assert mgr.is_expired is False
        assert mgr.access_token == "ibkr-access-abc"

    def test_auth_headers(self):
        from src.ibkr_broker.client import IBKRConfig, _TokenManager
        config = IBKRConfig()
        mgr = _TokenManager(config)
        mgr.set_tokens("my-ib-token", "refresh", expires_in=3600)
        headers = mgr.auth_headers()
        assert headers["Authorization"] == "Bearer my-ib-token"


# =====================================================================
# Test: Contract Search
# =====================================================================


class TestContractSearch:
    """Tests for IBKR contract search demo data."""

    def _make_client(self, **kwargs):
        from src.ibkr_broker.client import IBKRClient, IBKRConfig
        kwargs.setdefault("request_timeout", 1)
        config = IBKRConfig(**kwargs)
        return IBKRClient(config)

    @pytest.mark.asyncio
    async def test_search_stk(self):
        client = self._make_client()
        await client.connect()
        contracts = await client.search_contract("AAPL", sec_type="STK")
        assert len(contracts) >= 1
        assert contracts[0].sec_type == "STK"
        assert contracts[0].conid == 265598
        assert contracts[0].symbol == "AAPL"
        assert contracts[0].description == "Apple Inc"

    @pytest.mark.asyncio
    async def test_search_fut(self):
        client = self._make_client()
        await client.connect()
        contracts = await client.search_contract("ES", sec_type="FUT")
        assert len(contracts) >= 1
        for c in contracts:
            assert c.sec_type == "FUT"
            assert c.exchange == "CME"
        # Check that we get multiple ES contracts (different expirations)
        es_contracts = await client.search_contract("ES")
        assert len(es_contracts) >= 2

    @pytest.mark.asyncio
    async def test_search_cash_forex(self):
        client = self._make_client()
        await client.connect()
        contracts = await client.search_contract("EUR", sec_type="CASH")
        assert len(contracts) >= 1
        assert contracts[0].sec_type == "CASH"
        assert contracts[0].exchange == "IDEALPRO"
        assert contracts[0].local_symbol == "EUR.USD"


# =====================================================================
# Test: Module Imports
# =====================================================================


class TestModuleImports:
    """Tests for module import integrity."""

    def test_all_exports_importable(self):
        from src.ibkr_broker import __all__
        import src.ibkr_broker as mod
        for name in __all__:
            assert hasattr(mod, name), f"Missing export: {name}"

    def test_config_defaults_match(self):
        from src.ibkr_broker import IBKRConfig
        config = IBKRConfig()
        assert config.gateway_host == "localhost"
        assert config.gateway_port == 5000
        assert config.ssl_verify is False
        assert config.max_requests_per_minute == 50
        assert config.account_id == ""
