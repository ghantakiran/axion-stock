"""Tests for Schwab Broker Integration (PRD-145).

8 test classes, ~50 tests covering config, client, response models,
streaming, research, and module imports.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# =====================================================================
# Test: SchwabConfig
# =====================================================================


class TestSchwabConfig:
    """Tests for SchwabConfig dataclass."""

    def test_defaults(self):
        from src.schwab_broker.client import SchwabConfig
        config = SchwabConfig()
        assert config.app_key == ""
        assert config.app_secret == ""
        assert config.base_url == "https://api.schwabapi.com"
        assert config.callback_url == "https://127.0.0.1:8182/callback"

    def test_trader_url(self):
        from src.schwab_broker.client import SchwabConfig
        config = SchwabConfig()
        assert config.trader_url == "https://api.schwabapi.com/trader/v1"

    def test_marketdata_url(self):
        from src.schwab_broker.client import SchwabConfig
        config = SchwabConfig()
        assert config.marketdata_url == "https://api.schwabapi.com/marketdata/v1"

    def test_auth_urls(self):
        from src.schwab_broker.client import SchwabConfig
        config = SchwabConfig()
        assert "oauth" in config.auth_url
        assert "oauth" in config.token_url


# =====================================================================
# Test: SchwabClient
# =====================================================================


class TestSchwabClient:
    """Tests for SchwabClient REST operations."""

    def _make_client(self, **kwargs):
        from src.schwab_broker.client import SchwabClient, SchwabConfig
        config = SchwabConfig(**kwargs)
        return SchwabClient(config)

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
        assert accounts[0].account_number == "DEMO-12345678"
        assert accounts[0].equity == 142500.0
        assert accounts[0].cash == 65000.0

    @pytest.mark.asyncio
    async def test_get_positions_demo(self):
        client = self._make_client()
        await client.connect()
        positions = await client.get_positions("DEMO-12345678")
        assert len(positions) == 3
        assert positions[0].symbol == "SPY"
        assert positions[0].quantity == 50
        assert positions[1].symbol == "AAPL"
        assert positions[2].symbol == "MSFT"

    @pytest.mark.asyncio
    async def test_get_orders_demo(self):
        client = self._make_client()
        await client.connect()
        orders = await client.get_orders("DEMO-12345678")
        assert len(orders) == 3
        assert orders[0].symbol == "AAPL"
        assert orders[0].status == "FILLED"

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
        order = await client.place_order("DEMO-12345678", order_req)
        assert order.symbol == "AAPL"
        assert order.quantity == 10
        assert order.status == "FILLED"

    @pytest.mark.asyncio
    async def test_place_order_demo_limit(self):
        client = self._make_client()
        await client.connect()
        order_req = {
            "orderType": "LIMIT",
            "session": "NORMAL",
            "duration": "DAY",
            "price": "225.00",
            "orderLegCollection": [{
                "instruction": "BUY",
                "quantity": 5,
                "instrument": {"symbol": "AAPL", "assetType": "EQUITY"},
            }],
        }
        order = await client.place_order("DEMO-12345678", order_req)
        assert order.symbol == "AAPL"
        assert order.order_type == "LIMIT"
        assert order.status == "QUEUED"

    @pytest.mark.asyncio
    async def test_cancel_order_demo(self):
        client = self._make_client()
        await client.connect()
        result = await client.cancel_order("DEMO-12345678", "DEMO-ORD-001")
        assert result is True

    @pytest.mark.asyncio
    async def test_get_quotes_demo(self):
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
    async def test_get_option_chain_demo(self):
        client = self._make_client()
        await client.connect()
        chain = await client.get_option_chain("AAPL", strike_count=10)
        assert chain["symbol"] == "AAPL"
        assert chain["status"] == "SUCCESS"
        assert "callExpDateMap" in chain
        assert "putExpDateMap" in chain

    @pytest.mark.asyncio
    async def test_get_movers_demo(self):
        client = self._make_client()
        await client.connect()
        movers = await client.get_movers("$SPX")
        assert len(movers) >= 3
        assert movers[0].symbol == "NVDA"
        assert movers[0].percent_change == 1.45


# =====================================================================
# Test: Response Models
# =====================================================================


class TestResponseModels:
    """Tests for API response model parsing."""

    def test_account_from_api(self):
        from src.schwab_broker.client import SchwabAccount
        data = {
            "securitiesAccount": {
                "accountNumber": "123456",
                "type": "INDIVIDUAL",
                "isDayTrader": False,
                "currentBalances": {
                    "cashBalance": 50000.0,
                    "equity": 142500.0,
                    "longMarketValue": 77500.0,
                    "buyingPower": 130000.0,
                },
                "positions": [{"symbol": "AAPL"}, {"symbol": "MSFT"}],
            },
        }
        account = SchwabAccount.from_api(data)
        assert account.account_number == "123456"
        assert account.cash == 50000.0
        assert account.equity == 142500.0
        assert account.position_count == 2

    def test_position_from_api(self):
        from src.schwab_broker.client import SchwabPosition
        data = {
            "instrument": {"symbol": "AAPL", "assetType": "EQUITY"},
            "longQuantity": 100,
            "averagePrice": 218.0,
            "marketValue": 23075.0,
            "currentDayProfitLoss": 1275.0,
        }
        pos = SchwabPosition.from_api(data)
        assert pos.symbol == "AAPL"
        assert pos.quantity == 100
        assert pos.market_value == 23075.0

    def test_order_from_api(self):
        from src.schwab_broker.client import SchwabOrder
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
        order = SchwabOrder.from_api(data)
        assert order.order_id == "ORD-999"
        assert order.symbol == "SPY"
        assert order.status == "FILLED"
        assert order.filled_quantity == 50

    def test_quote_from_api(self):
        from src.schwab_broker.client import SchwabQuote
        data = {
            "quote": {
                "bidPrice": 230.70,
                "askPrice": 230.80,
                "lastPrice": 230.75,
                "totalVolume": 55200000,
                "netChange": 1.85,
            },
            "reference": {"symbol": "AAPL", "description": "Apple Inc"},
        }
        quote = SchwabQuote.from_api(data, symbol="AAPL")
        assert quote.symbol == "AAPL"
        assert quote.last_price == 230.75
        assert quote.bid_price == 230.70
        assert quote.total_volume == 55200000

    def test_candle_from_api(self):
        from src.schwab_broker.client import SchwabCandle
        data = {"open": 228.5, "high": 231.5, "low": 227.0, "close": 230.75, "volume": 55200000, "datetime": 1705382400000}
        candle = SchwabCandle.from_api(data)
        assert candle.open == 228.5
        assert candle.high == 231.5
        assert candle.close == 230.75
        assert candle.volume == 55200000

    def test_mover_from_api(self):
        from src.schwab_broker.client import SchwabMover
        data = {
            "symbol": "NVDA",
            "description": "NVIDIA Corp",
            "direction": "up",
            "change": 12.5,
            "percentChange": 1.45,
            "totalVolume": 42000000,
            "lastPrice": 875.20,
        }
        mover = SchwabMover.from_api(data)
        assert mover.symbol == "NVDA"
        assert mover.direction == "up"
        assert mover.percent_change == 1.45
        assert mover.last_price == 875.20


# =====================================================================
# Test: Streaming
# =====================================================================


class TestSchwabStreaming:
    """Tests for WebSocket streaming."""

    def test_stream_channel_enum(self):
        from src.schwab_broker.streaming import StreamChannel
        assert StreamChannel.QUOTE.value == "QUOTE"
        assert StreamChannel.CHART.value == "CHART_EQUITY"
        assert StreamChannel.OPTION.value == "OPTION"
        assert StreamChannel.TIMESALE.value == "TIMESALE_EQUITY"
        assert StreamChannel.NEWS.value == "NEWS_HEADLINE"

    def test_stream_event_types(self):
        from src.schwab_broker.streaming import StreamEvent, StreamChannel
        quote = StreamEvent(channel=StreamChannel.QUOTE, symbol="AAPL")
        assert quote.is_quote is True
        assert quote.is_chart is False
        chart = StreamEvent(channel=StreamChannel.CHART, symbol="MSFT")
        assert chart.is_chart is True
        assert chart.is_quote is False

    def test_streaming_subscriptions_empty(self):
        from src.schwab_broker.client import SchwabConfig
        from src.schwab_broker.streaming import SchwabStreaming
        config = SchwabConfig()
        streaming = SchwabStreaming(config)
        assert streaming.is_running is False
        assert streaming.subscriptions == {}

    def test_callback_registration(self):
        from src.schwab_broker.client import SchwabConfig
        from src.schwab_broker.streaming import SchwabStreaming
        config = SchwabConfig()
        streaming = SchwabStreaming(config)
        events = []
        streaming.on_quote(lambda e: events.append(e))
        streaming.on_chart(lambda e: events.append(e))
        streaming.on_option(lambda e: events.append(e))
        streaming.on_timesale(lambda e: events.append(e))
        streaming.on_news(lambda e: events.append(e))
        # No assertion needed -- verifying no errors

    @pytest.mark.asyncio
    async def test_subscribe_adds_symbols(self):
        from src.schwab_broker.client import SchwabConfig
        from src.schwab_broker.streaming import SchwabStreaming, StreamChannel
        config = SchwabConfig()
        streaming = SchwabStreaming(config)
        await streaming.subscribe(["AAPL", "MSFT"], [StreamChannel.QUOTE])
        subs = streaming.subscriptions
        assert "QUOTE" in subs
        assert "AAPL" in subs["QUOTE"]
        assert "MSFT" in subs["QUOTE"]

    @pytest.mark.asyncio
    async def test_unsubscribe_removes_symbols(self):
        from src.schwab_broker.client import SchwabConfig
        from src.schwab_broker.streaming import SchwabStreaming, StreamChannel
        config = SchwabConfig()
        streaming = SchwabStreaming(config)
        await streaming.subscribe(["AAPL", "MSFT"], [StreamChannel.QUOTE])
        await streaming.unsubscribe(["AAPL"], [StreamChannel.QUOTE])
        subs = streaming.subscriptions
        assert "AAPL" not in subs.get("QUOTE", [])
        assert "MSFT" in subs.get("QUOTE", [])


# =====================================================================
# Test: Research
# =====================================================================


class TestSchwabResearch:
    """Tests for Schwab research tools."""

    @pytest.mark.asyncio
    async def test_get_fundamentals(self):
        from src.schwab_broker.research import SchwabResearch
        research = SchwabResearch()
        data = await research.get_fundamentals("AAPL")
        assert data.symbol == "AAPL"
        assert data.pe_ratio == 31.2
        assert data.market_cap == 3.56e12
        assert data.sector == "Technology"

    @pytest.mark.asyncio
    async def test_get_screener(self):
        from src.schwab_broker.research import SchwabResearch
        research = SchwabResearch()
        results = await research.get_screener({"sector": "Technology"})
        assert len(results) >= 1
        for r in results:
            assert r.sector == "Technology"

    @pytest.mark.asyncio
    async def test_get_screener_with_pe_filter(self):
        from src.schwab_broker.research import SchwabResearch
        research = SchwabResearch()
        results = await research.get_screener({"max_pe": 30})
        for r in results:
            assert r.pe_ratio <= 30

    @pytest.mark.asyncio
    async def test_get_analyst_ratings(self):
        from src.schwab_broker.research import SchwabResearch
        research = SchwabResearch()
        rating = await research.get_analyst_ratings("AAPL")
        assert rating.symbol == "AAPL"
        assert rating.consensus == "Buy"
        assert rating.num_analysts == 42
        assert rating.buy_count > rating.sell_count


# =====================================================================
# Test: FundamentalData from_api
# =====================================================================


class TestFundamentalDataFromApi:
    """Tests for FundamentalData.from_api parsing."""

    def test_from_api_with_fundamental_key(self):
        from src.schwab_broker.research import FundamentalData
        data = {
            "fundamental": {
                "peRatio": 25.5,
                "eps": 8.0,
                "marketCap": 1.0e12,
                "dividendYield": 1.2,
                "beta": 1.1,
                "sector": "Technology",
                "industry": "Software",
            },
        }
        f = FundamentalData.from_api(data, symbol="TEST")
        assert f.symbol == "TEST"
        assert f.pe_ratio == 25.5
        assert f.eps == 8.0
        assert f.market_cap == 1.0e12

    def test_from_api_flat_dict(self):
        from src.schwab_broker.research import FundamentalData
        data = {
            "peRatio": 15.0,
            "eps": 4.0,
            "marketCap": 5.0e10,
        }
        f = FundamentalData.from_api(data, symbol="FLAT")
        assert f.pe_ratio == 15.0
        assert f.eps == 4.0


# =====================================================================
# Test: ScreenerResult and AnalystRating from_api
# =====================================================================


class TestResearchModelsFromApi:
    """Tests for ScreenerResult and AnalystRating from_api."""

    def test_screener_result_from_api(self):
        from src.schwab_broker.research import ScreenerResult
        data = {
            "symbol": "TSLA",
            "description": "Tesla Inc",
            "lastPrice": 382.50,
            "totalVolume": 38000000,
            "marketCap": 1.2e12,
            "peRatio": 70.0,
            "netPercentChange": -2.10,
            "sector": "Consumer Cyclical",
        }
        r = ScreenerResult.from_api(data)
        assert r.symbol == "TSLA"
        assert r.last_price == 382.50
        assert r.change_pct == -2.10

    def test_analyst_rating_from_api(self):
        from src.schwab_broker.research import AnalystRating
        data = {
            "symbol": "TSLA",
            "consensus": "Hold",
            "targetPrice": 400.0,
            "highTarget": 500.0,
            "lowTarget": 250.0,
            "numAnalysts": 35,
            "buyCount": 12,
            "holdCount": 15,
            "sellCount": 8,
        }
        r = AnalystRating.from_api(data)
        assert r.symbol == "TSLA"
        assert r.consensus == "Hold"
        assert r.target_price == 400.0
        assert r.num_analysts == 35


# =====================================================================
# Test: Module Imports
# =====================================================================


class TestModuleImports:
    """Tests for module import integrity."""

    def test_all_exports_importable(self):
        from src.schwab_broker import __all__
        import src.schwab_broker as mod
        for name in __all__:
            assert hasattr(mod, name), f"Missing export: {name}"

    def test_key_classes_importable(self):
        from src.schwab_broker import (
            SchwabClient,
            SchwabConfig,
            SchwabStreaming,
            SchwabResearch,
            SchwabAccount,
            SchwabPosition,
            SchwabOrder,
            SchwabQuote,
            SchwabCandle,
            SchwabMover,
        )
        assert SchwabClient is not None
        assert SchwabConfig is not None
        assert SchwabStreaming is not None
        assert SchwabResearch is not None

    def test_research_models_importable(self):
        from src.schwab_broker import (
            FundamentalData,
            ScreenerResult,
            AnalystRating,
        )
        assert FundamentalData is not None
        assert ScreenerResult is not None
        assert AnalystRating is not None
