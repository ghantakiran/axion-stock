"""Tests for Fidelity Broker Integration (PRD-156).

8 test classes, ~50 tests covering config, client, response models,
streaming, research, token manager, option chains, and module imports.
"""

import asyncio
from datetime import datetime, timezone

import pytest


# =====================================================================
# Test: FidelityConfig
# =====================================================================


class TestFidelityConfig:
    """Tests for FidelityConfig dataclass."""

    def test_defaults(self):
        from src.fidelity_broker.client import FidelityConfig
        config = FidelityConfig()
        assert config.client_id == ""
        assert config.client_secret == ""
        assert config.base_url == "https://api.fidelity.com"
        assert config.redirect_uri == "https://127.0.0.1:8182/callback"
        assert config.max_requests_per_minute == 60
        assert config.request_timeout == 30

    def test_url_properties(self):
        from src.fidelity_broker.client import FidelityConfig
        config = FidelityConfig()
        assert config.trader_url == "https://api.fidelity.com/trader/v1"
        assert config.marketdata_url == "https://api.fidelity.com/marketdata/v1"
        assert "oauth" in config.auth_url
        assert "oauth" in config.token_url

    def test_auth_urls(self):
        from src.fidelity_broker.client import FidelityConfig
        config = FidelityConfig()
        assert config.auth_url == "https://api.fidelity.com/v1/oauth/authorize"
        assert config.token_url == "https://api.fidelity.com/v1/oauth/token"

    def test_custom_values(self):
        from src.fidelity_broker.client import FidelityConfig
        config = FidelityConfig(
            client_id="my-id",
            client_secret="my-secret",
            base_url="https://custom.fidelity.com",
            max_retries=5,
        )
        assert config.client_id == "my-id"
        assert config.client_secret == "my-secret"
        assert config.trader_url == "https://custom.fidelity.com/trader/v1"
        assert config.marketdata_url == "https://custom.fidelity.com/marketdata/v1"
        assert config.max_retries == 5


# =====================================================================
# Test: FidelityClient
# =====================================================================


class TestFidelityClient:
    """Tests for FidelityClient REST operations."""

    def _make_client(self, **kwargs):
        from src.fidelity_broker.client import FidelityClient, FidelityConfig
        config = FidelityConfig(**kwargs)
        return FidelityClient(config)

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
        assert accounts[0].account_number == "DEMO-FID-78901234"
        assert accounts[0].equity == 158500.0
        assert accounts[0].cash == 72000.0

    @pytest.mark.asyncio
    async def test_get_positions_demo(self):
        client = self._make_client()
        await client.connect()
        positions = await client.get_positions("DEMO-FID-78901234")
        assert len(positions) == 3
        assert positions[0].symbol == "SPY"
        assert positions[0].quantity == 50
        assert positions[1].symbol == "AAPL"
        assert positions[2].symbol == "GOOGL"

    @pytest.mark.asyncio
    async def test_get_orders_demo(self):
        client = self._make_client()
        await client.connect()
        orders = await client.get_orders("DEMO-FID-78901234")
        assert len(orders) == 3
        assert orders[0].symbol == "AAPL"
        assert orders[0].status == "FILLED"
        assert orders[1].symbol == "SPY"
        assert orders[2].symbol == "GOOGL"

    @pytest.mark.asyncio
    async def test_place_order_demo_market(self):
        client = self._make_client()
        await client.connect()
        order_req = {
            "orderType": "MARKET",
            "session": "NORMAL",
            "duration": "DAY",
            "orderLegCollection": [{
                "instruction": "BUY",
                "quantity": 10,
                "instrument": {"symbol": "AAPL", "assetType": "EQUITY"},
            }],
        }
        order = await client.place_order("DEMO-FID-78901234", order_req)
        assert order.symbol == "AAPL"
        assert order.quantity == 10
        assert order.status == "FILLED"
        assert order.order_type == "MARKET"

    @pytest.mark.asyncio
    async def test_cancel_order_demo(self):
        client = self._make_client()
        await client.connect()
        result = await client.cancel_order("DEMO-FID-78901234", "DEMO-FID-ORD-001")
        assert result is True

    @pytest.mark.asyncio
    async def test_get_quote_demo(self):
        client = self._make_client()
        await client.connect()
        quotes = await client.get_quote(["SPY", "AAPL"])
        assert len(quotes) == 2
        spy = [q for q in quotes if q.symbol == "SPY"][0]
        assert spy.last_price == 590.50
        assert spy.bid_price == 590.45
        aapl = [q for q in quotes if q.symbol == "AAPL"][0]
        assert aapl.last_price == 230.75

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
    async def test_get_mutual_funds_demo(self):
        client = self._make_client()
        await client.connect()
        funds = await client.get_mutual_funds()
        assert len(funds) == 8
        # Filter by category
        large_blend = await client.get_mutual_funds("Large Blend")
        assert len(large_blend) == 2
        assert all("Large Blend" in f.category for f in large_blend)


# =====================================================================
# Test: Response Models
# =====================================================================


class TestFidelityResponseModels:
    """Tests for API response model parsing."""

    def test_account_from_api(self):
        from src.fidelity_broker.client import FidelityAccount
        data = {
            "account": {
                "accountNumber": "FID-123456",
                "type": "INDIVIDUAL",
                "isMarginAccount": True,
                "currentBalances": {
                    "cashBalance": 50000.0,
                    "equity": 158500.0,
                    "longMarketValue": 86500.0,
                    "buyingPower": 130000.0,
                },
                "positions": [{"symbol": "AAPL"}, {"symbol": "MSFT"}, {"symbol": "GOOGL"}],
            },
        }
        account = FidelityAccount.from_api(data)
        assert account.account_number == "FID-123456"
        assert account.cash == 50000.0
        assert account.equity == 158500.0
        assert account.position_count == 3

    def test_account_to_dict(self):
        from src.fidelity_broker.client import FidelityAccount
        account = FidelityAccount(
            account_number="TEST-001", account_type="MARGIN",
            cash=10000.0, equity=50000.0,
        )
        d = account.to_dict()
        assert d["account_number"] == "TEST-001"
        assert d["cash"] == 10000.0
        assert d["equity"] == 50000.0
        assert "is_margin_account" in d

    def test_position_from_api(self):
        from src.fidelity_broker.client import FidelityPosition
        data = {
            "instrument": {"symbol": "AAPL", "assetType": "EQUITY"},
            "longQuantity": 100,
            "averagePrice": 218.0,
            "marketValue": 23075.0,
            "currentDayProfitLoss": 1275.0,
        }
        pos = FidelityPosition.from_api(data)
        assert pos.symbol == "AAPL"
        assert pos.quantity == 100
        assert pos.market_value == 23075.0

    def test_position_to_dict(self):
        from src.fidelity_broker.client import FidelityPosition
        pos = FidelityPosition(symbol="SPY", quantity=50, market_value=29525.0)
        d = pos.to_dict()
        assert d["symbol"] == "SPY"
        assert d["quantity"] == 50
        assert "cost_basis" in d

    def test_order_from_api(self):
        from src.fidelity_broker.client import FidelityOrder
        data = {
            "orderId": "ORD-999",
            "orderType": "MARKET",
            "status": "FILLED",
            "filledQuantity": 50,
            "duration": "DAY",
            "enteredTime": "2025-01-15T10:30:00Z",
            "orderLegCollection": [{
                "instruction": "BUY",
                "quantity": 50,
                "instrument": {"symbol": "SPY"},
            }],
        }
        order = FidelityOrder.from_api(data)
        assert order.order_id == "ORD-999"
        assert order.symbol == "SPY"
        assert order.status == "FILLED"
        assert order.filled_quantity == 50

    def test_order_to_dict(self):
        from src.fidelity_broker.client import FidelityOrder
        order = FidelityOrder(order_id="T-001", symbol="AAPL", status="QUEUED")
        d = order.to_dict()
        assert d["order_id"] == "T-001"
        assert d["symbol"] == "AAPL"
        assert "stop_price" in d

    def test_quote_from_api(self):
        from src.fidelity_broker.client import FidelityQuote
        data = {
            "quote": {
                "bidPrice": 230.70,
                "askPrice": 230.80,
                "lastPrice": 230.75,
                "totalVolume": 55200000,
                "netChange": 1.85,
                "dividendYield": 0.44,
                "marketCap": 3.56e12,
            },
            "reference": {"symbol": "AAPL", "description": "Apple Inc"},
        }
        quote = FidelityQuote.from_api(data, symbol="AAPL")
        assert quote.symbol == "AAPL"
        assert quote.last_price == 230.75
        assert quote.bid_price == 230.70
        assert quote.dividend_yield == 0.44
        assert quote.market_cap == 3.56e12

    def test_quote_to_dict(self):
        from src.fidelity_broker.client import FidelityQuote
        quote = FidelityQuote(symbol="SPY", last_price=590.50, dividend_yield=1.30)
        d = quote.to_dict()
        assert d["symbol"] == "SPY"
        assert d["last_price"] == 590.50
        assert d["dividend_yield"] == 1.30

    def test_candle_from_api(self):
        from src.fidelity_broker.client import FidelityCandle
        data = {"open": 228.5, "high": 231.5, "low": 227.0, "close": 230.75, "volume": 55200000, "datetime": 1705382400000}
        candle = FidelityCandle.from_api(data)
        assert candle.open == 228.5
        assert candle.high == 231.5
        assert candle.close == 230.75
        assert candle.volume == 55200000

    def test_mutual_fund_to_dict(self):
        from src.fidelity_broker.client import FidelityMutualFund
        fund = FidelityMutualFund(
            symbol="FXAIX", name="Fidelity 500 Index Fund",
            category="Large Blend", morningstar_rating=5,
            expense_ratio=0.015, nav=196.50,
        )
        d = fund.to_dict()
        assert d["symbol"] == "FXAIX"
        assert d["morningstar_rating"] == 5
        assert d["expense_ratio"] == 0.015
        assert d["nav"] == 196.50


# =====================================================================
# Test: Streaming
# =====================================================================


class TestFidelityStreaming:
    """Tests for WebSocket streaming."""

    def test_stream_channel_enum(self):
        from src.fidelity_broker.streaming import StreamChannel
        assert StreamChannel.QUOTE.value == "QUOTE"
        assert StreamChannel.CHART.value == "CHART_EQUITY"
        assert StreamChannel.OPTION.value == "OPTION"
        assert StreamChannel.TIMESALE.value == "TIMESALE_EQUITY"
        assert StreamChannel.NEWS.value == "NEWS_HEADLINE"

    def test_stream_event_types(self):
        from src.fidelity_broker.streaming import StreamEvent, StreamChannel
        quote = StreamEvent(channel=StreamChannel.QUOTE, symbol="AAPL")
        assert quote.is_quote is True
        assert quote.is_chart is False
        chart = StreamEvent(channel=StreamChannel.CHART, symbol="MSFT")
        assert chart.is_chart is True
        assert chart.is_quote is False

    @pytest.mark.asyncio
    async def test_subscribe_unsubscribe(self):
        from src.fidelity_broker.client import FidelityConfig
        from src.fidelity_broker.streaming import FidelityStreaming, StreamChannel
        config = FidelityConfig()
        streaming = FidelityStreaming(config)
        await streaming.subscribe(["AAPL", "MSFT"], [StreamChannel.QUOTE])
        subs = streaming.subscriptions
        assert "QUOTE" in subs
        assert "AAPL" in subs["QUOTE"]
        assert "MSFT" in subs["QUOTE"]
        await streaming.unsubscribe(["AAPL"], [StreamChannel.QUOTE])
        subs = streaming.subscriptions
        assert "AAPL" not in subs.get("QUOTE", [])
        assert "MSFT" in subs.get("QUOTE", [])

    def test_on_quote_callback(self):
        from src.fidelity_broker.client import FidelityConfig
        from src.fidelity_broker.streaming import FidelityStreaming
        config = FidelityConfig()
        streaming = FidelityStreaming(config)
        events = []
        streaming.on_quote(lambda e: events.append(e))
        # Verify callback registered without error
        assert streaming.is_running is False

    @pytest.mark.asyncio
    async def test_start_stop(self):
        from src.fidelity_broker.client import FidelityConfig
        from src.fidelity_broker.streaming import FidelityStreaming
        config = FidelityConfig()
        streaming = FidelityStreaming(config)
        await streaming.start()
        assert streaming.is_running is True
        await streaming.stop()
        assert streaming.is_running is False

    def test_is_running_default(self):
        from src.fidelity_broker.client import FidelityConfig
        from src.fidelity_broker.streaming import FidelityStreaming
        config = FidelityConfig()
        streaming = FidelityStreaming(config)
        assert streaming.is_running is False
        assert streaming.subscriptions == {}


# =====================================================================
# Test: Research
# =====================================================================


class TestFidelityResearch:
    """Tests for Fidelity research tools."""

    @pytest.mark.asyncio
    async def test_get_fundamentals(self):
        from src.fidelity_broker.research import FidelityResearch
        research = FidelityResearch()
        data = await research.get_fundamentals("AAPL")
        assert data.symbol == "AAPL"
        assert data.pe_ratio == 31.2
        assert data.eps == 7.40
        assert data.sector == "Technology"

    @pytest.mark.asyncio
    async def test_screen_funds_default(self):
        from src.fidelity_broker.research import FidelityResearch
        research = FidelityResearch()
        results = await research.screen_funds({})
        assert len(results) == 8
        for r in results:
            assert r.symbol != ""

    @pytest.mark.asyncio
    async def test_screen_funds_with_filter(self):
        from src.fidelity_broker.research import FidelityResearch
        research = FidelityResearch()
        results = await research.screen_funds({"category": "Large Blend"})
        assert len(results) >= 1
        for r in results:
            assert "large blend" in r.category.lower()

    @pytest.mark.asyncio
    async def test_screen_funds_with_min_rating(self):
        from src.fidelity_broker.research import FidelityResearch
        research = FidelityResearch()
        results = await research.screen_funds({"min_rating": 5})
        for r in results:
            assert r.morningstar_rating >= 5

    @pytest.mark.asyncio
    async def test_get_analyst_ratings(self):
        from src.fidelity_broker.research import FidelityResearch
        research = FidelityResearch()
        ratings = await research.get_analyst_ratings("AAPL")
        assert len(ratings) >= 1
        assert ratings[0].symbol == "AAPL"
        assert ratings[0].firm != ""
        assert ratings[0].target_price > 0

    @pytest.mark.asyncio
    async def test_get_analyst_ratings_multiple_firms(self):
        from src.fidelity_broker.research import FidelityResearch
        research = FidelityResearch()
        ratings = await research.get_analyst_ratings("NVDA")
        assert len(ratings) == 3
        firms = [r.firm for r in ratings]
        assert "Goldman Sachs" in firms


# =====================================================================
# Test: TokenManager
# =====================================================================


class TestTokenManager:
    """Tests for OAuth2 token management."""

    def test_initial_expired(self):
        from src.fidelity_broker.client import FidelityConfig, _TokenManager
        config = FidelityConfig()
        mgr = _TokenManager(config)
        assert mgr.is_expired is True
        assert mgr.access_token == ""

    def test_set_tokens(self):
        from src.fidelity_broker.client import FidelityConfig, _TokenManager
        config = FidelityConfig()
        mgr = _TokenManager(config)
        mgr.set_tokens("access-123", "refresh-456", expires_in=3600)
        assert mgr.is_expired is False
        assert mgr.access_token == "access-123"

    @pytest.mark.asyncio
    async def test_refresh_no_token(self):
        from src.fidelity_broker.client import FidelityConfig, _TokenManager
        config = FidelityConfig()
        mgr = _TokenManager(config)
        result = await mgr.refresh()
        assert result is False

    def test_auth_headers(self):
        from src.fidelity_broker.client import FidelityConfig, _TokenManager
        config = FidelityConfig()
        mgr = _TokenManager(config)
        mgr.set_tokens("my-token", "refresh", expires_in=3600)
        headers = mgr.auth_headers()
        assert headers["Authorization"] == "Bearer my-token"


# =====================================================================
# Test: Option Chain
# =====================================================================


class TestOptionChain:
    """Tests for option chain demo data."""

    @pytest.mark.asyncio
    async def test_get_option_chain_structure(self):
        from src.fidelity_broker.client import FidelityClient, FidelityConfig
        config = FidelityConfig()
        client = FidelityClient(config)
        await client.connect()
        chain = await client.get_option_chain("AAPL", strike_count=10)
        assert chain["symbol"] == "AAPL"
        assert chain["status"] == "SUCCESS"
        assert "callExpDateMap" in chain
        assert "putExpDateMap" in chain

    @pytest.mark.asyncio
    async def test_option_chain_call_put_strikes(self):
        from src.fidelity_broker.client import FidelityClient, FidelityConfig
        config = FidelityConfig()
        client = FidelityClient(config)
        await client.connect()
        chain = await client.get_option_chain("AAPL", strike_count=10)
        calls = chain["callExpDateMap"]
        puts = chain["putExpDateMap"]
        # Both maps should have expiry dates with strikes
        assert len(calls) >= 1
        assert len(puts) >= 1
        for expiry, strikes in calls.items():
            for strike_key, contracts in strikes.items():
                assert contracts[0]["putCall"] == "CALL"
        for expiry, strikes in puts.items():
            for strike_key, contracts in strikes.items():
                assert contracts[0]["putCall"] == "PUT"

    @pytest.mark.asyncio
    async def test_option_chain_underlying_price(self):
        from src.fidelity_broker.client import FidelityClient, FidelityConfig
        config = FidelityConfig()
        client = FidelityClient(config)
        await client.connect()
        chain = await client.get_option_chain("AAPL")
        assert "underlying" in chain
        assert chain["underlying"]["last"] == 230.75


# =====================================================================
# Test: Module Imports
# =====================================================================


class TestModuleImports:
    """Tests for module import integrity."""

    def test_all_exports_importable(self):
        from src.fidelity_broker import __all__
        import src.fidelity_broker as mod
        for name in __all__:
            assert hasattr(mod, name), f"Missing export: {name}"

    def test_config_defaults_match(self):
        from src.fidelity_broker import FidelityConfig
        config = FidelityConfig()
        assert config.base_url == "https://api.fidelity.com"
        assert config.client_id == ""
        assert config.client_secret == ""
        assert config.max_requests_per_minute == 60
