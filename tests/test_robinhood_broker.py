"""Tests for Robinhood Broker Integration (PRD-143).

8 test classes, ~50 tests covering client, models, streaming, portfolio,
and module imports.
"""

import time
import threading
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.robinhood_broker.client import (
    RobinhoodClient,
    RobinhoodConfig,
    RobinhoodAccount,
    RobinhoodPosition,
    RobinhoodOrder,
    RobinhoodQuote,
)
from src.robinhood_broker.streaming import (
    RobinhoodStreaming,
    QuoteUpdate,
    OrderStatusUpdate,
)
from src.robinhood_broker.portfolio import (
    PortfolioTracker,
    PortfolioSnapshot,
)


# =====================================================================
# Test: RobinhoodConfig
# =====================================================================


class TestRobinhoodConfig:
    """Test RobinhoodConfig defaults and custom values."""

    def test_defaults(self):
        config = RobinhoodConfig()
        assert config.username == ""
        assert config.password == ""
        assert config.mfa_code is None
        assert config.device_token is None
        assert config.base_url == "https://api.robinhood.com"
        assert config.max_requests_per_minute == 60
        assert config.request_timeout == 30
        assert config.max_retries == 3

    def test_custom_values(self):
        config = RobinhoodConfig(
            username="user@example.com",
            password="secret123",
            mfa_code="123456",
            device_token="tok_abc",
        )
        assert config.username == "user@example.com"
        assert config.password == "secret123"
        assert config.mfa_code == "123456"
        assert config.device_token == "tok_abc"

    def test_base_url_default(self):
        config = RobinhoodConfig()
        assert config.base_url == "https://api.robinhood.com"

    def test_custom_base_url(self):
        config = RobinhoodConfig(base_url="https://custom.api.com")
        assert config.base_url == "https://custom.api.com"


# =====================================================================
# Test: RobinhoodClient
# =====================================================================


class TestRobinhoodClient:
    """Test RobinhoodClient in demo mode."""

    def setup_method(self):
        self.config = RobinhoodConfig()
        self.client = RobinhoodClient(self.config)

    def test_connect_demo_no_credentials(self):
        result = self.client.connect()
        assert result is True
        assert self.client.is_connected is True
        assert self.client.mode == "demo"

    def test_disconnect(self):
        self.client.connect()
        self.client.disconnect()
        assert self.client.is_connected is False
        assert self.client.mode == "demo"

    def test_get_account_demo(self):
        self.client.connect()
        account = self.client.get_account()
        assert isinstance(account, RobinhoodAccount)
        assert account.buying_power > 0
        assert account.equity > 0
        assert account.cash > 0
        assert account.status == "active"

    def test_get_positions_demo(self):
        self.client.connect()
        positions = self.client.get_positions()
        assert isinstance(positions, list)
        assert len(positions) >= 2
        for p in positions:
            assert isinstance(p, RobinhoodPosition)
            assert p.symbol != ""
            assert p.quantity > 0
            assert p.market_value > 0

    def test_get_orders_demo(self):
        self.client.connect()
        orders = self.client.get_orders()
        assert isinstance(orders, list)
        assert len(orders) >= 1
        for o in orders:
            assert isinstance(o, RobinhoodOrder)
            assert o.order_id != ""
            assert o.symbol != ""

    def test_get_orders_filter_status(self):
        self.client.connect()
        filled = self.client.get_orders(status="filled")
        assert all(o.status == "filled" for o in filled)

    def test_place_order_demo(self):
        self.client.connect()
        order = self.client.place_order(
            symbol="AAPL", qty=10, side="buy",
            order_type="market", time_in_force="gfd",
        )
        assert isinstance(order, RobinhoodOrder)
        assert order.symbol == "AAPL"
        assert order.quantity == 10
        assert order.side == "buy"
        assert order.status == "filled"  # market orders fill immediately in demo

    def test_place_limit_order_demo(self):
        self.client.connect()
        order = self.client.place_order(
            symbol="NVDA", qty=5, side="buy",
            order_type="limit", limit_price=600.0,
        )
        assert order.order_type == "limit"
        assert order.status == "confirmed"
        assert order.limit_price == 600.0

    def test_cancel_order_demo(self):
        self.client.connect()
        result = self.client.cancel_order("fake_order_id")
        assert result is True

    def test_get_quote_demo(self):
        self.client.connect()
        quote = self.client.get_quote("AAPL")
        assert isinstance(quote, RobinhoodQuote)
        assert quote.symbol == "AAPL"
        assert quote.bid_price > 0
        assert quote.ask_price > 0
        assert quote.last_trade_price > 0
        assert quote.bid_price <= quote.ask_price

    def test_get_crypto_quote_demo(self):
        self.client.connect()
        quote = self.client.get_crypto_quote("BTC")
        assert isinstance(quote, RobinhoodQuote)
        assert quote.symbol == "BTC"
        assert quote.last_trade_price > 50000

    def test_get_options_chain_demo(self):
        self.client.connect()
        chain = self.client.get_options_chain("AAPL")
        assert isinstance(chain, list)
        assert len(chain) > 0
        assert any(c["type"] == "call" for c in chain)
        assert any(c["type"] == "put" for c in chain)

    def test_default_config(self):
        client = RobinhoodClient()
        assert client.config.username == ""
        assert client.mode == "demo"


# =====================================================================
# Test: Response Models
# =====================================================================


class TestResponseModels:
    """Test from_api and to_dict for response models."""

    def test_account_from_api(self):
        data = {
            "id": "acct_123",
            "account_number": "5RH999",
            "buying_power": "55000.00",
            "equity": "95000.00",
            "cash": "40000.00",
            "type": "margin",
            "state": "active",
        }
        account = RobinhoodAccount.from_api(data)
        assert account.account_id == "acct_123"
        assert account.buying_power == 55000.0
        assert account.equity == 95000.0
        assert account.margin_enabled is True

    def test_position_from_api(self):
        data = {
            "symbol": "AAPL",
            "instrument_id": "instr_001",
            "quantity": "100",
            "average_buy_price": "150.00",
            "current_price": "185.00",
        }
        pos = RobinhoodPosition.from_api(data)
        assert pos.symbol == "AAPL"
        assert pos.quantity == 100.0
        assert pos.average_cost == 150.0
        assert pos.market_value == 18500.0
        assert pos.unrealized_pnl == 3500.0

    def test_order_from_api(self):
        data = {
            "id": "ord_abc",
            "symbol": "TSLA",
            "side": "sell",
            "quantity": "20",
            "type": "limit",
            "time_in_force": "gtc",
            "price": "330.00",
            "state": "confirmed",
            "cumulative_quantity": "0",
            "average_price": "0",
        }
        order = RobinhoodOrder.from_api(data)
        assert order.order_id == "ord_abc"
        assert order.symbol == "TSLA"
        assert order.side == "sell"
        assert order.limit_price == 330.0
        assert order.status == "confirmed"

    def test_quote_from_api(self):
        data = {
            "symbol": "NVDA",
            "bid_price": "620.00",
            "ask_price": "625.00",
            "last_trade_price": "622.50",
            "previous_close": "615.00",
            "volume": "35000000",
            "high": "630.00",
            "low": "610.00",
            "open": "618.00",
        }
        quote = RobinhoodQuote.from_api(data)
        assert quote.symbol == "NVDA"
        assert quote.bid_price == 620.0
        assert quote.ask_price == 625.0
        assert quote.volume == 35000000

    def test_to_dict_round_trip(self):
        account = RobinhoodAccount(
            account_id="test", buying_power=1000.0, equity=5000.0
        )
        d = account.to_dict()
        assert d["account_id"] == "test"
        assert d["buying_power"] == 1000.0

        pos = RobinhoodPosition(symbol="AAPL", quantity=10)
        d = pos.to_dict()
        assert d["symbol"] == "AAPL"
        assert d["quantity"] == 10

        order = RobinhoodOrder(order_id="ord1", symbol="MSFT")
        d = order.to_dict()
        assert d["order_id"] == "ord1"

        quote = RobinhoodQuote(symbol="TSLA", bid_price=320.0)
        d = quote.to_dict()
        assert d["symbol"] == "TSLA"


# =====================================================================
# Test: RobinhoodStreaming
# =====================================================================


class TestRobinhoodStreaming:
    """Test polling-based streaming manager."""

    def test_start_stop_polling(self):
        streaming = RobinhoodStreaming()
        streaming.start_polling(interval_seconds=0.1)
        assert streaming.is_running is True
        time.sleep(0.05)
        streaming.stop_polling()
        assert streaming.is_running is False

    def test_double_start(self):
        streaming = RobinhoodStreaming()
        streaming.start_polling(interval_seconds=0.1)
        streaming.start_polling(interval_seconds=0.1)  # should not create second thread
        assert streaming.is_running is True
        streaming.stop_polling()

    def test_add_remove_symbols(self):
        streaming = RobinhoodStreaming()
        streaming.add_symbols(["AAPL", "MSFT"])
        assert "AAPL" in streaming.watched_symbols
        assert "MSFT" in streaming.watched_symbols
        streaming.remove_symbols(["AAPL"])
        assert "AAPL" not in streaming.watched_symbols
        assert "MSFT" in streaming.watched_symbols

    def test_quote_callback(self):
        received = []
        streaming = RobinhoodStreaming()
        streaming.on_quote_update(lambda update: received.append(update))
        streaming.add_symbols(["AAPL"])
        streaming.start_polling(interval_seconds=0.1)
        time.sleep(0.5)
        streaming.stop_polling()
        assert len(received) >= 1
        assert all(isinstance(u, QuoteUpdate) for u in received)
        assert all(u.symbol == "AAPL" for u in received)

    def test_order_callback_registration(self):
        received = []
        streaming = RobinhoodStreaming()
        streaming.on_order_update(lambda update: received.append(update))
        # Order callbacks fire on status changes; no client means no order polling
        streaming.start_polling(interval_seconds=0.1)
        time.sleep(0.3)
        streaming.stop_polling()
        # No errors should occur even without client


# =====================================================================
# Test: PortfolioTracker
# =====================================================================


class TestPortfolioTracker:
    """Test portfolio tracking and analytics."""

    def setup_method(self):
        self.tracker = PortfolioTracker()

    def test_sync_positions_demo(self):
        self.tracker.sync_positions()
        assert len(self.tracker.positions) >= 2
        assert self.tracker.cash > 0
        assert self.tracker.last_sync is not None

    def test_total_value(self):
        self.tracker.sync_positions()
        total = self.tracker.get_total_value()
        assert total > 0
        # Total should be cash + sum of market values
        expected = self.tracker.cash + sum(p.market_value for p in self.tracker.positions)
        assert abs(total - expected) < 0.01

    def test_daily_pnl(self):
        self.tracker.sync_positions()
        pnl = self.tracker.get_daily_pnl()
        assert isinstance(pnl, float)
        # Sum of unrealized PnL from positions
        expected = sum(p.unrealized_pnl for p in self.tracker.positions)
        assert abs(pnl - expected) < 0.01

    def test_allocation(self):
        self.tracker.sync_positions()
        allocation = self.tracker.get_allocation()
        assert isinstance(allocation, dict)
        assert "CASH" in allocation
        # Weights should sum to approximately 1.0
        total_weight = sum(allocation.values())
        assert abs(total_weight - 1.0) < 0.01

    def test_history_demo(self):
        history = self.tracker.get_history(days=30)
        assert isinstance(history, list)
        assert len(history) == 30
        for snap in history:
            assert isinstance(snap, PortfolioSnapshot)
            assert snap.total_value > 0

    def test_position_summary(self):
        self.tracker.sync_positions()
        summary = self.tracker.get_position_summary()
        assert isinstance(summary, list)
        assert len(summary) >= 2
        for entry in summary:
            assert "symbol" in entry
            assert "quantity" in entry
            assert "market_value" in entry
            assert "unrealized_pnl" in entry
            assert "weight" in entry

    def test_tracker_with_client(self):
        client = RobinhoodClient()
        client.connect()
        tracker = PortfolioTracker(client)
        tracker.sync_positions()
        assert len(tracker.positions) >= 2
        assert tracker.get_total_value() > 0


# =====================================================================
# Test: QuoteUpdate / OrderStatusUpdate Models
# =====================================================================


class TestStreamingModels:
    """Test streaming update data models."""

    def test_quote_update_creation(self):
        update = QuoteUpdate(
            symbol="AAPL", bid_price=187.0, ask_price=188.0,
            last_trade_price=187.50, volume=50_000_000,
        )
        assert update.symbol == "AAPL"
        assert update.bid_price == 187.0

    def test_quote_update_to_dict(self):
        update = QuoteUpdate(symbol="AAPL", bid_price=187.0)
        d = update.to_dict()
        assert d["symbol"] == "AAPL"
        assert "timestamp" in d

    def test_order_status_update_creation(self):
        update = OrderStatusUpdate(
            order_id="ord_123", symbol="TSLA",
            status="filled", filled_quantity=10, average_fill_price=325.0,
        )
        assert update.order_id == "ord_123"
        assert update.status == "filled"

    def test_order_status_update_to_dict(self):
        update = OrderStatusUpdate(order_id="ord_123", symbol="TSLA")
        d = update.to_dict()
        assert d["order_id"] == "ord_123"
        assert "timestamp" in d


# =====================================================================
# Test: Module Imports
# =====================================================================


class TestModuleImports:
    """Test that all public exports are importable."""

    def test_all_exports(self):
        from src.robinhood_broker import __all__
        assert "RobinhoodClient" in __all__
        assert "RobinhoodConfig" in __all__
        assert "RobinhoodAccount" in __all__
        assert "RobinhoodPosition" in __all__
        assert "RobinhoodOrder" in __all__
        assert "RobinhoodQuote" in __all__
        assert "RobinhoodStreaming" in __all__
        assert "PortfolioTracker" in __all__

    def test_config_defaults_via_module(self):
        from src.robinhood_broker import RobinhoodConfig
        config = RobinhoodConfig()
        assert config.base_url == "https://api.robinhood.com"
        assert config.username == ""

    def test_key_classes_instantiation(self):
        from src.robinhood_broker import (
            RobinhoodClient,
            RobinhoodConfig,
            RobinhoodStreaming,
            PortfolioTracker,
        )
        config = RobinhoodConfig()
        client = RobinhoodClient(config)
        assert client.mode == "demo"

        streaming = RobinhoodStreaming()
        assert streaming.is_running is False

        tracker = PortfolioTracker()
        assert tracker.cash == 0.0
