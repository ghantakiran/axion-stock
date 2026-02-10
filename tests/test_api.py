"""Tests for PRD-11: Mobile App & Public API.

Tests cover: config, auth (API keys, rate limiting, webhook signing),
WebSocket manager, webhook manager, SDK client, FastAPI routes,
and module imports.
"""

import json
import time

import pytest
import numpy as np

from src.api.config import (
    APITier,
    WebSocketChannel,
    WebhookEvent,
    RATE_LIMITS,
    APIConfig,
    WebSocketConfig,
    WebhookConfig,
    DEFAULT_API_CONFIG,
)
from src.api.models import (
    QuoteResponse,
    OHLCVResponse,
    FactorScoreResponse,
    ScreenResponse,
    PortfolioResponse,
    OptimizeRequest,
    CreateOrderRequest,
    OrderResponse,
    OrderSideEnum,
    OrderTypeEnum,
    OrderStatusEnum,
    ChatRequest,
    BacktestRequest,
    WSMessage,
    WebhookCreateRequest,
    APIKeyCreateRequest,
    ErrorResponse,
    HealthResponse,
)
from src.api.auth import (
    APIKeyManager,
    RateLimiter,
    WebhookSigner,
)
from src.api.websocket import WebSocketManager
from src.api.webhooks import WebhookManager
from src.api.sdk import AxionClient, SDKConfig
from src.api.app import create_app


# =============================================================================
# Config Tests
# =============================================================================


class TestAPIConfig:
    """Test API configuration."""

    def test_default_config(self):
        config = DEFAULT_API_CONFIG
        assert config.title == "Axion API"
        assert config.version == "1.0.0"
        assert config.prefix == "/api/v1"
        assert config.api_key_prefix == "ax_"

    def test_rate_limits_per_tier(self):
        assert RATE_LIMITS[APITier.FREE]["daily_limit"] == 100
        assert RATE_LIMITS[APITier.PRO]["daily_limit"] == 1_000
        assert RATE_LIMITS[APITier.ENTERPRISE]["daily_limit"] == 0  # unlimited

    def test_api_tier_enum(self):
        assert APITier.FREE.value == "free"
        assert APITier.PRO.value == "pro"
        assert APITier.ENTERPRISE.value == "enterprise"

    def test_websocket_channels(self):
        assert WebSocketChannel.QUOTES.value == "quotes"
        assert WebSocketChannel.PORTFOLIO.value == "portfolio"
        assert WebSocketChannel.ALERTS.value == "alerts"

    def test_webhook_events(self):
        assert WebhookEvent.ORDER_FILLED.value == "order.filled"
        assert WebhookEvent.SIGNAL_NEW.value == "signal.new"
        assert WebhookEvent.DRAWDOWN_WARNING.value == "drawdown.warning"


# =============================================================================
# Auth Tests
# =============================================================================


class TestAPIKeyManager:
    """Test API key management."""

    @pytest.fixture
    def manager(self):
        return APIKeyManager()

    def test_create_key(self, manager):
        result = manager.create_key(
            user_id="user1",
            name="Test Key",
            scopes=["read", "write"],
            tier=APITier.PRO,
        )

        assert result["key_id"]
        assert result["key"].startswith("ax_")
        assert len(result["key"]) == 51  # "ax_" + 48 hex chars
        assert result["name"] == "Test Key"
        assert result["scopes"] == ["read", "write"]

    def test_validate_key(self, manager):
        result = manager.create_key(user_id="user1", name="My Key")
        raw_key = result["key"]

        metadata = manager.validate_key(raw_key)
        assert metadata is not None
        assert metadata["user_id"] == "user1"
        assert metadata["is_active"] is True

    def test_validate_invalid_key(self, manager):
        assert manager.validate_key("invalid_key") is None
        assert manager.validate_key("ax_nonexistent123") is None

    def test_revoke_key(self, manager):
        result = manager.create_key(user_id="user1", name="Temp Key")
        key_id = result["key_id"]
        raw_key = result["key"]

        assert manager.revoke_key(key_id) is True
        assert manager.validate_key(raw_key) is None

    def test_revoke_nonexistent_key(self, manager):
        assert manager.revoke_key("nonexistent") is False

    def test_list_keys(self, manager):
        manager.create_key(user_id="user1", name="Key A")
        manager.create_key(user_id="user1", name="Key B")
        manager.create_key(user_id="user2", name="Key C")

        keys = manager.list_keys("user1")
        assert len(keys) == 2

    def test_has_scope(self, manager):
        result = manager.create_key(user_id="user1", name="RW", scopes=["read", "write"])
        meta = manager.validate_key(result["key"])

        assert manager.has_scope(meta, "read") is True
        assert manager.has_scope(meta, "write") is True
        assert manager.has_scope(meta, "admin") is False

    def test_admin_scope_grants_all(self, manager):
        result = manager.create_key(user_id="user1", name="Admin", scopes=["admin"])
        meta = manager.validate_key(result["key"])

        assert manager.has_scope(meta, "read") is True
        assert manager.has_scope(meta, "write") is True
        assert manager.has_scope(meta, "admin") is True

    def test_write_implies_read(self, manager):
        result = manager.create_key(user_id="user1", name="W", scopes=["write"])
        meta = manager.validate_key(result["key"])

        assert manager.has_scope(meta, "read") is True


class TestRateLimiter:
    """Test rate limiting."""

    @pytest.fixture
    def limiter(self):
        return RateLimiter()

    def test_allow_under_limit(self, limiter):
        allowed, info = limiter.check_rate_limit("user1", APITier.PRO)
        assert allowed is True
        assert info["remaining"] >= 0

    def test_enforce_per_minute_limit(self, limiter):
        # Free tier: 10/min
        for i in range(10):
            allowed, _ = limiter.check_rate_limit("user1", APITier.FREE)
            assert allowed is True

        # 11th request should be blocked
        allowed, info = limiter.check_rate_limit("user1", APITier.FREE)
        assert allowed is False
        assert info["reason"] == "per_minute"

    def test_get_usage(self, limiter):
        limiter.check_rate_limit("user1", APITier.PRO)
        limiter.check_rate_limit("user1", APITier.PRO)

        usage = limiter.get_usage("user1", APITier.PRO)
        assert usage["tier"] == "pro"
        assert usage["minute_used"] == 2
        assert usage["daily_used"] == 2


class TestWebhookSigner:
    """Test webhook HMAC signing."""

    def test_sign_payload(self):
        payload = '{"event": "order.filled"}'
        secret = "test_secret"

        sig = WebhookSigner.sign(payload, secret)
        assert isinstance(sig, str)
        assert len(sig) == 64  # SHA-256 hex digest

    def test_verify_valid_signature(self):
        payload = '{"event": "order.filled"}'
        secret = "test_secret"

        sig = WebhookSigner.sign(payload, secret)
        assert WebhookSigner.verify(payload, sig, secret) is True

    def test_verify_invalid_signature(self):
        payload = '{"event": "order.filled"}'
        assert WebhookSigner.verify(payload, "bad_sig", "secret") is False

    def test_verify_wrong_secret(self):
        payload = '{"event": "order.filled"}'
        sig = WebhookSigner.sign(payload, "correct_secret")
        assert WebhookSigner.verify(payload, sig, "wrong_secret") is False


# =============================================================================
# WebSocket Tests
# =============================================================================


class TestWebSocketManager:
    """Test WebSocket connection and subscription management."""

    @pytest.fixture
    def ws_manager(self):
        return WebSocketManager()

    def test_connect(self, ws_manager):
        ok, msg = ws_manager.connect("conn1", "user1")
        assert ok is True
        assert msg == "connected"

    def test_max_connections(self, ws_manager):
        config = WebSocketConfig(max_connections_per_user=2)
        mgr = WebSocketManager(config)

        mgr.connect("c1", "user1")
        mgr.connect("c2", "user1")
        ok, msg = mgr.connect("c3", "user1")
        assert ok is False
        assert "exceeded" in msg.lower()

    def test_disconnect(self, ws_manager):
        ws_manager.connect("conn1", "user1")
        ws_manager.subscribe("conn1", "quotes", ["AAPL"])
        ws_manager.disconnect("conn1")

        assert ws_manager.get_connection_info("conn1") is None

    def test_subscribe_channel(self, ws_manager):
        ws_manager.connect("conn1", "user1")
        ok, msg = ws_manager.subscribe("conn1", "quotes")
        assert ok is True

        subs = ws_manager.get_subscribers("quotes")
        assert "conn1" in subs

    def test_subscribe_with_symbols(self, ws_manager):
        ws_manager.connect("conn1", "user1")
        ws_manager.subscribe("conn1", "quotes", ["AAPL", "MSFT"])

        subs = ws_manager.get_subscribers("quotes", "AAPL")
        assert "conn1" in subs

        subs = ws_manager.get_subscribers("quotes", "GOOGL")
        assert "conn1" not in subs

    def test_unsubscribe(self, ws_manager):
        ws_manager.connect("conn1", "user1")
        ws_manager.subscribe("conn1", "quotes", ["AAPL", "MSFT"])

        ws_manager.unsubscribe("conn1", "quotes", ["AAPL"])
        subs = ws_manager.get_subscribers("quotes", "AAPL")
        assert "conn1" not in subs

    def test_broadcast(self, ws_manager):
        ws_manager.connect("conn1", "user1")
        ws_manager.connect("conn2", "user2")
        ws_manager.subscribe("conn1", "quotes", ["AAPL"])
        ws_manager.subscribe("conn2", "quotes", ["AAPL"])

        messages = ws_manager.broadcast("quotes", {"price": 150.0}, "AAPL")
        assert len(messages) == 2
        for m in messages:
            parsed = json.loads(m["message"])
            assert parsed["channel"] == "quotes"
            assert parsed["price"] == 150.0

    def test_heartbeat(self, ws_manager):
        ws_manager.connect("conn1", "user1")
        assert ws_manager.heartbeat("conn1") is True
        assert ws_manager.heartbeat("nonexistent") is False

    def test_get_stats(self, ws_manager):
        ws_manager.connect("c1", "u1")
        ws_manager.connect("c2", "u2")
        ws_manager.subscribe("c1", "quotes")

        stats = ws_manager.get_stats()
        assert stats["total_connections"] == 2
        assert stats["total_users"] == 2

    def test_stale_connections(self, ws_manager):
        ws_manager.connect("conn1", "user1")
        # Manually set stale heartbeat
        ws_manager._connections["conn1"].last_heartbeat = time.time() - 200
        stale = ws_manager.get_stale_connections()
        assert "conn1" in stale


# =============================================================================
# Webhook Tests
# =============================================================================


class TestWebhookManager:
    """Test webhook registration and dispatch."""

    @pytest.fixture
    def wh_manager(self):
        return WebhookManager()

    def test_register_webhook(self, wh_manager):
        wh, err = wh_manager.register(
            user_id="user1",
            url="https://example.com/webhook",
            events=["order.filled", "alert.risk"],
            description="Test hook",
        )

        assert wh is not None
        assert err == ""
        assert wh.url == "https://example.com/webhook"
        assert len(wh.events) == 2
        assert wh.secret.startswith("whsec_")

    def test_register_with_custom_secret(self, wh_manager):
        wh, _ = wh_manager.register(
            user_id="user1",
            url="https://example.com/wh",
            events=["order.filled"],
            secret="my_custom_secret",
        )
        assert wh.secret == "my_custom_secret"

    def test_max_webhooks(self, wh_manager):
        config = WebhookConfig(max_webhooks_per_user=2)
        mgr = WebhookManager(config)

        mgr.register("user1", "https://a.com", ["order.filled"])
        mgr.register("user1", "https://b.com", ["order.filled"])
        wh, err = mgr.register("user1", "https://c.com", ["order.filled"])
        assert wh is None
        assert "Maximum" in err

    def test_unregister_webhook(self, wh_manager):
        wh, _ = wh_manager.register("user1", "https://a.com", ["order.filled"])
        assert wh_manager.unregister(wh.webhook_id, "user1") is True
        assert wh_manager.get_webhook(wh.webhook_id) is None

    def test_unregister_wrong_user(self, wh_manager):
        wh, _ = wh_manager.register("user1", "https://a.com", ["order.filled"])
        assert wh_manager.unregister(wh.webhook_id, "user2") is False

    def test_dispatch_event(self, wh_manager):
        wh_manager.register("user1", "https://a.com", ["order.filled"])
        wh_manager.register("user2", "https://b.com", ["order.filled"])

        records = wh_manager.dispatch("order.filled", {"order_id": "123"})
        assert len(records) == 2
        for r in records:
            assert r.success is True
            assert r.event == "order.filled"

    def test_dispatch_filters_events(self, wh_manager):
        wh_manager.register("user1", "https://a.com", ["order.filled"])
        wh_manager.register("user2", "https://b.com", ["alert.risk"])

        records = wh_manager.dispatch("order.filled", {"order_id": "123"})
        assert len(records) == 1

    def test_dispatch_skips_inactive(self, wh_manager):
        wh, _ = wh_manager.register("user1", "https://a.com", ["order.filled"])
        wh_manager.toggle_webhook(wh.webhook_id, False)

        records = wh_manager.dispatch("order.filled", {"data": 1})
        assert len(records) == 0

    def test_list_webhooks(self, wh_manager):
        wh_manager.register("user1", "https://a.com", ["order.filled"])
        wh_manager.register("user1", "https://b.com", ["alert.risk"])

        hooks = wh_manager.list_webhooks("user1")
        assert len(hooks) == 2

    def test_delivery_stats(self, wh_manager):
        wh, _ = wh_manager.register("user1", "https://a.com", ["order.filled"])
        wh_manager.dispatch("order.filled", {"data": 1})
        wh_manager.dispatch("order.filled", {"data": 2})

        stats = wh_manager.get_delivery_stats(wh.webhook_id)
        assert stats["total_deliveries"] == 2
        assert stats["success_rate"] == 1.0

    def test_get_deliveries(self, wh_manager):
        wh, _ = wh_manager.register("user1", "https://a.com", ["order.filled"])
        wh_manager.dispatch("order.filled", {"data": 1})

        deliveries = wh_manager.get_deliveries(wh.webhook_id)
        assert len(deliveries) == 1


# =============================================================================
# SDK Tests
# =============================================================================


class TestSDK:
    """Test Python SDK client."""

    @pytest.fixture
    def client(self):
        return AxionClient(api_key="ax_test123", base_url="http://localhost:8000")

    def test_client_init(self, client):
        assert client.api_key == "ax_test123"
        assert client.config.base_url == "http://localhost:8000"
        assert client.config.api_base == "http://localhost:8000/api/v1"

    def test_factors_get(self, client):
        result = client.factors.get("AAPL")
        assert result["_sdk"] is True
        assert result["method"] == "GET"
        assert "/factors/AAPL" in result["url"]

    def test_factors_screen(self, client):
        result = client.factors.screen(factor="momentum", top=10)
        assert result["params"]["factor"] == "momentum"
        assert result["params"]["top"] == 10

    def test_orders_create(self, client):
        result = client.orders.create(
            symbol="AAPL", qty=10, side="buy", limit_price=175.0,
        )
        assert result["method"] == "POST"
        assert result["json"]["symbol"] == "AAPL"
        assert result["json"]["qty"] == 10
        assert result["json"]["limit_price"] == 175.0

    def test_orders_cancel(self, client):
        result = client.orders.cancel("order123")
        assert result["method"] == "DELETE"
        assert "/orders/order123" in result["url"]

    def test_portfolio_optimize(self, client):
        result = client.portfolio.optimize(method="risk_parity")
        assert result["json"]["method"] == "risk_parity"

    def test_ai_chat(self, client):
        result = client.ai.chat("Analyze AAPL")
        assert result["json"]["message"] == "Analyze AAPL"

    def test_backtest_run(self, client):
        result = client.backtest.run(
            strategy="momentum",
            start="2020-01-01",
            end="2024-12-31",
        )
        assert result["json"]["strategy"] == "momentum"
        assert result["json"]["start_date"] == "2020-01-01"

    def test_auth_header(self, client):
        result = client.factors.get("AAPL")
        assert result["headers"]["Authorization"] == "Bearer ax_test123"

    def test_sdk_config(self):
        config = SDKConfig(base_url="https://api.axion.io")
        assert config.api_base == "https://api.axion.io/api/v1"
        assert config.websocket_url == "wss://api.axion.io/ws"

    def test_stream_url(self, client):
        url = client.stream.quotes_url(["AAPL"])
        assert "ws" in url


# =============================================================================
# Pydantic Model Tests
# =============================================================================


class TestPydanticModels:
    """Test Pydantic request/response models."""

    def test_quote_response(self):
        q = QuoteResponse(symbol="AAPL", price=178.50)
        assert q.symbol == "AAPL"
        assert q.price == 178.50

    def test_create_order_validation(self):
        order = CreateOrderRequest(
            symbol="AAPL",
            qty=10,
            side=OrderSideEnum.BUY,
            order_type=OrderTypeEnum.LIMIT,
            limit_price=175.0,
        )
        assert order.qty == 10
        assert order.side == OrderSideEnum.BUY

    def test_create_order_min_qty(self):
        with pytest.raises(Exception):
            CreateOrderRequest(symbol="AAPL", qty=0, side=OrderSideEnum.BUY)

    def test_optimize_request_defaults(self):
        req = OptimizeRequest()
        assert req.method == "max_sharpe"
        assert req.max_weight == 0.10
        assert req.max_positions == 20

    def test_backtest_request(self):
        from datetime import date
        req = BacktestRequest(
            strategy="momentum",
            start_date=date(2020, 1, 1),
            end_date=date(2024, 12, 31),
        )
        assert req.initial_capital == 100_000

    def test_error_response(self):
        err = ErrorResponse(error="Not Found", code="404")
        assert err.error == "Not Found"

    def test_health_response(self):
        h = HealthResponse()
        assert h.status == "ok"


# =============================================================================
# FastAPI Route Tests
# =============================================================================


class TestFastAPIRoutes:
    """Test FastAPI application and routes."""

    @pytest.fixture
    def app(self):
        return create_app()

    @pytest.fixture
    def client(self, app):
        from fastapi.testclient import TestClient
        return TestClient(app)

    def test_health_endpoint(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("ok", "degraded")
        assert "version" in data
        assert "components" in data
        # Verify component keys exist
        components = data["components"]
        assert "database" in components
        assert "redis" in components
        assert "bot" in components
        assert "metrics" in components

    def test_get_quote(self, client):
        resp = client.get("/api/v1/market/quotes/AAPL")
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "AAPL"

    def test_get_ohlcv(self, client):
        resp = client.get("/api/v1/market/ohlcv/AAPL?bar=1d&limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "AAPL"
        assert data["bar_type"] == "1d"

    def test_get_fundamentals(self, client):
        resp = client.get("/api/v1/market/fundamentals/MSFT")
        assert resp.status_code == 200
        assert resp.json()["symbol"] == "MSFT"

    def test_invalid_universe(self, client):
        resp = client.get("/api/v1/market/universe/invalid")
        assert resp.status_code == 404

    def test_valid_universe(self, client):
        resp = client.get("/api/v1/market/universe/sp500")
        assert resp.status_code == 200

    def test_get_factor_scores(self, client):
        resp = client.get("/api/v1/factors/AAPL")
        assert resp.status_code == 200
        assert resp.json()["symbol"] == "AAPL"

    def test_screen_factors(self, client):
        resp = client.get("/api/v1/factors/screen/results?factor=momentum&top=10")
        assert resp.status_code == 200

    def test_get_regime(self, client):
        resp = client.get("/api/v1/factors/regime")
        assert resp.status_code == 200

    def test_get_portfolio(self, client):
        resp = client.get("/api/v1/portfolio")
        assert resp.status_code == 200

    def test_optimize_portfolio(self, client):
        resp = client.post("/api/v1/portfolio/optimize", json={
            "method": "min_variance",
        })
        assert resp.status_code == 200
        assert resp.json()["method"] == "min_variance"

    def test_create_order(self, client):
        resp = client.post("/api/v1/orders", json={
            "symbol": "AAPL",
            "qty": 10,
            "side": "buy",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["symbol"] == "AAPL"
        assert data["status"] == "pending"

    def test_get_order(self, client):
        # Create first
        create_resp = client.post("/api/v1/orders", json={
            "symbol": "MSFT",
            "qty": 5,
            "side": "sell",
        })
        order_id = create_resp.json()["order_id"]

        # Get it
        resp = client.get(f"/api/v1/orders/{order_id}")
        assert resp.status_code == 200
        assert resp.json()["order_id"] == order_id

    def test_cancel_order(self, client):
        create_resp = client.post("/api/v1/orders", json={
            "symbol": "TSLA",
            "qty": 3,
            "side": "buy",
        })
        order_id = create_resp.json()["order_id"]

        resp = client.delete(f"/api/v1/orders/{order_id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    def test_order_not_found(self, client):
        resp = client.get("/api/v1/orders/nonexistent")
        assert resp.status_code == 404

    def test_ai_chat(self, client):
        resp = client.post("/api/v1/ai/chat", json={"message": "Analyze AAPL"})
        assert resp.status_code == 200

    def test_get_prediction(self, client):
        resp = client.get("/api/v1/ai/predictions/AAPL")
        assert resp.status_code == 200

    def test_get_sentiment(self, client):
        resp = client.get("/api/v1/ai/sentiment/NVDA")
        assert resp.status_code == 200

    def test_options_chain(self, client):
        resp = client.get("/api/v1/options/AAPL/chain")
        assert resp.status_code == 200

    def test_run_backtest(self, client):
        resp = client.post("/api/v1/backtest", json={
            "strategy": "momentum",
            "start_date": "2020-01-01",
            "end_date": "2024-12-31",
        })
        assert resp.status_code == 201

    def test_get_backtest(self, client):
        create_resp = client.post("/api/v1/backtest", json={
            "strategy": "equal_weight",
            "start_date": "2020-01-01",
            "end_date": "2024-12-31",
        })
        bt_id = create_resp.json()["backtest_id"]

        resp = client.get(f"/api/v1/backtest/{bt_id}")
        assert resp.status_code == 200


# =============================================================================
# Module Import Tests
# =============================================================================


class TestApiModuleImports:
    """Test that all public API module exports work."""

    def test_import_config(self):
        from src.api import APITier, RATE_LIMITS, DEFAULT_API_CONFIG
        assert APITier.FREE
        assert RATE_LIMITS
        assert DEFAULT_API_CONFIG

    def test_import_auth(self):
        from src.api import APIKeyManager, RateLimiter, WebhookSigner
        assert APIKeyManager
        assert RateLimiter
        assert WebhookSigner

    def test_import_websocket(self):
        from src.api import WebSocketManager, WSConnection
        assert WebSocketManager
        assert WSConnection

    def test_import_webhooks(self):
        from src.api import WebhookManager, Webhook, DeliveryRecord
        assert WebhookManager
        assert Webhook
        assert DeliveryRecord

    def test_import_sdk(self):
        from src.api import AxionClient, SDKConfig
        assert AxionClient
        assert SDKConfig

    def test_import_app(self):
        from src.api import create_app
        app = create_app()
        assert app is not None

    def test_import_models(self):
        from src.api import (
            QuoteResponse, OrderResponse, BacktestResponse,
            WebhookCreateRequest, APIKeyCreateRequest,
        )
        assert QuoteResponse
        assert OrderResponse


# =============================================================================
# Metrics & WebSocket Route Tests
# =============================================================================


class TestMetricsEndpoint:
    """Test the Prometheus /metrics endpoint."""

    @pytest.fixture
    def app(self):
        return create_app()

    @pytest.fixture
    def client(self, app):
        from fastapi.testclient import TestClient
        return TestClient(app)

    def test_metrics_returns_200(self, client):
        resp = client.get("/metrics")
        assert resp.status_code == 200

    def test_metrics_content_type(self, client):
        resp = client.get("/metrics")
        assert "text/plain" in resp.headers["content-type"]

    def test_metrics_prometheus_format(self, client):
        resp = client.get("/metrics")
        # Prometheus text format uses # HELP and # TYPE lines
        # An empty registry is valid (no metrics registered yet)
        text = resp.text
        assert isinstance(text, str)
        # If metrics exist, they follow Prometheus format
        if text.strip():
            for line in text.strip().split("\n"):
                if line and not line.startswith("#"):
                    # Metric lines: name{labels} value [timestamp]
                    assert " " in line or line == ""


class TestWebSocketBotEndpoint:
    """Test the /ws/bot WebSocket endpoint."""

    @pytest.fixture
    def app(self):
        return create_app()

    @pytest.fixture
    def client(self, app):
        from fastapi.testclient import TestClient
        return TestClient(app)

    def test_websocket_connect_and_receive(self, client):
        with client.websocket_connect("/ws/bot") as ws:
            data = ws.receive_json()
            assert data["event"] == "connected"
            assert "connection_id" in data

    def test_websocket_heartbeat(self, client):
        with client.websocket_connect("/ws/bot") as ws:
            ws.receive_json()  # consume connected event
            ws.send_json({"action": "heartbeat"})
            resp = ws.receive_json()
            assert resp["action"] == "heartbeat_ack"
            assert "timestamp" in resp

    def test_websocket_subscribe(self, client):
        with client.websocket_connect("/ws/bot") as ws:
            ws.receive_json()  # consume connected event
            ws.send_json({"action": "subscribe", "channel": "signals"})
            resp = ws.receive_json()
            assert resp["action"] == "subscribed"
            assert resp["channel"] == "signals"
            assert resp["ok"] is True

    def test_websocket_subscribe_unknown_channel(self, client):
        with client.websocket_connect("/ws/bot") as ws:
            ws.receive_json()  # consume connected event
            ws.send_json({"action": "subscribe", "channel": "nonexistent"})
            resp = ws.receive_json()
            assert "error" in resp
            assert "available" in resp

    def test_websocket_unsubscribe(self, client):
        with client.websocket_connect("/ws/bot") as ws:
            ws.receive_json()  # consume connected event
            ws.send_json({"action": "unsubscribe", "channel": "orders"})
            resp = ws.receive_json()
            assert resp["action"] == "unsubscribed"

    def test_websocket_invalid_json(self, client):
        with client.websocket_connect("/ws/bot") as ws:
            ws.receive_json()  # consume connected event
            ws.send_text("not valid json{{{")
            resp = ws.receive_json()
            assert "error" in resp

    def test_websocket_unknown_action(self, client):
        with client.websocket_connect("/ws/bot") as ws:
            ws.receive_json()  # consume connected event
            ws.send_json({"action": "fly_to_moon"})
            resp = ws.receive_json()
            assert "error" in resp

    def test_websocket_connect_with_user_id(self, client):
        with client.websocket_connect("/ws/bot?user_id=testuser") as ws:
            data = ws.receive_json()
            assert data["event"] == "connected"


# =============================================================================
# Middleware Stack Tests
# =============================================================================


class TestSecurityHeaders:
    """Test that security headers are present on all responses."""

    @pytest.fixture
    def app(self):
        return create_app()

    @pytest.fixture
    def client(self, app):
        from fastapi.testclient import TestClient
        return TestClient(app)

    def test_x_content_type_options(self, client):
        resp = client.get("/health")
        assert resp.headers.get("x-content-type-options") == "nosniff"

    def test_x_frame_options(self, client):
        resp = client.get("/health")
        assert resp.headers.get("x-frame-options") == "DENY"

    def test_x_xss_protection(self, client):
        resp = client.get("/health")
        assert resp.headers.get("x-xss-protection") == "1; mode=block"

    def test_referrer_policy(self, client):
        resp = client.get("/health")
        assert resp.headers.get("referrer-policy") == "strict-origin-when-cross-origin"

    def test_hsts_disabled_by_default(self, client):
        resp = client.get("/health")
        assert "strict-transport-security" not in resp.headers

    def test_headers_on_api_routes(self, client):
        """Security headers appear on API routes, not just /health."""
        resp = client.get("/api/v1/market/quotes/AAPL")
        assert resp.headers.get("x-content-type-options") == "nosniff"
        assert resp.headers.get("x-frame-options") == "DENY"

    def test_headers_on_metrics(self, client):
        """Security headers appear on /metrics endpoint."""
        resp = client.get("/metrics")
        assert resp.headers.get("x-content-type-options") == "nosniff"


class TestRequestTracing:
    """Test request tracing middleware."""

    @pytest.fixture
    def app(self):
        return create_app()

    @pytest.fixture
    def client(self, app):
        from fastapi.testclient import TestClient
        return TestClient(app)

    def test_response_has_request_id(self, client):
        resp = client.get("/health")
        assert "x-request-id" in resp.headers
        assert len(resp.headers["x-request-id"]) > 0

    def test_response_has_correlation_id(self, client):
        resp = client.get("/health")
        assert "x-correlation-id" in resp.headers

    def test_propagates_client_request_id(self, client):
        """If client sends X-Request-ID, it is echoed back."""
        custom_id = "test-trace-12345"
        resp = client.get("/health", headers={"X-Request-ID": custom_id})
        assert resp.headers.get("x-request-id") == custom_id

    def test_request_ids_are_unique(self, client):
        """Each request gets a unique ID if none provided."""
        r1 = client.get("/health")
        r2 = client.get("/health")
        assert r1.headers["x-request-id"] != r2.headers["x-request-id"]


class TestErrorHandlingMiddleware:
    """Test that error handling middleware catches exceptions."""

    @pytest.fixture
    def app(self):
        return create_app()

    @pytest.fixture
    def client(self, app):
        from fastapi.testclient import TestClient
        return TestClient(app)

    def test_404_returns_json(self, client):
        resp = client.get("/nonexistent/path")
        assert resp.status_code == 404
        data = resp.json()
        assert "detail" in data or "error" in data

    def test_health_returns_valid_json(self, client):
        """Verifies middleware doesn't corrupt valid responses."""
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data


# =============================================================================
# API Authentication & Rate Limiting Tests
# =============================================================================


class TestAuthDependencyDevMode:
    """Test that auth dependencies pass-through in dev mode (AXION_DEV_MODE=true)."""

    @pytest.fixture
    def app(self):
        return create_app()

    @pytest.fixture
    def client(self, app):
        from fastapi.testclient import TestClient
        return TestClient(app)

    def test_bot_start_no_key_dev_mode(self, client):
        """Bot start works without API key when AXION_REQUIRE_API_KEY is unset."""
        resp = client.post("/api/v1/bot/start", json={"paper_mode": True})
        assert resp.status_code in (200, 409)  # 409 if already running

    def test_bot_status_no_key_dev_mode(self, client):
        resp = client.get("/api/v1/bot/status")
        assert resp.status_code == 200

    def test_create_order_no_key_dev_mode(self, client):
        resp = client.post("/api/v1/orders", json={
            "symbol": "AAPL",
            "side": "buy",
            "qty": 10.0,
            "order_type": "market",
        })
        assert resp.status_code == 201

    def test_list_orders_no_key_dev_mode(self, client):
        resp = client.get("/api/v1/orders")
        assert resp.status_code == 200

    def test_rate_limit_headers_present_dev_mode(self, client):
        """Rate limit headers appear even in dev mode (enterprise tier)."""
        resp = client.get("/api/v1/bot/status")
        assert "x-ratelimit-limit" in resp.headers
        assert "x-ratelimit-remaining" in resp.headers


class TestAuthDependencyEnforced:
    """Test auth enforcement when AXION_REQUIRE_API_KEY=true."""

    @pytest.fixture
    def app(self):
        return create_app()

    @pytest.fixture
    def client(self, app):
        from fastapi.testclient import TestClient
        return TestClient(app)

    @pytest.fixture(autouse=True)
    def _enable_auth(self, monkeypatch):
        monkeypatch.delenv("AXION_DEV_MODE", raising=False)
        monkeypatch.setenv("AXION_REQUIRE_API_KEY", "true")

    def test_bot_start_rejected_no_key(self, client):
        """401 when no X-API-Key header and auth is required."""
        resp = client.post("/api/v1/bot/start", json={"paper_mode": True})
        assert resp.status_code == 401
        assert "Missing API key" in resp.json()["detail"]

    def test_bot_status_rejected_no_key(self, client):
        """Read endpoints also require key when auth is enforced."""
        resp = client.get("/api/v1/bot/status")
        assert resp.status_code == 401

    def test_create_order_rejected_no_key(self, client):
        resp = client.post("/api/v1/orders", json={
            "symbol": "AAPL",
            "side": "buy",
            "qty": 10.0,
            "order_type": "market",
        })
        assert resp.status_code == 401

    def test_invalid_key_rejected(self, client):
        """Invalid API key returns 401."""
        resp = client.post(
            "/api/v1/bot/start",
            json={"paper_mode": True},
            headers={"X-API-Key": "ax_invalid_key_here"},
        )
        assert resp.status_code == 401
        assert "Invalid or expired" in resp.json()["detail"]

    def test_valid_key_accepted(self, client):
        """Valid API key allows write operations."""
        from src.api.dependencies import get_key_manager
        mgr = get_key_manager()
        key_data = mgr.create_key("testuser", "test-key", scopes=["write"], tier=APITier.FREE)
        raw_key = key_data["key"]

        resp = client.post(
            "/api/v1/bot/start",
            json={"paper_mode": True},
            headers={"X-API-Key": raw_key},
        )
        assert resp.status_code in (200, 409)

    def test_read_scope_blocked_on_write_endpoint(self, client):
        """Key with only 'read' scope is blocked from write endpoints."""
        from src.api.dependencies import get_key_manager
        mgr = get_key_manager()
        key_data = mgr.create_key("testuser", "readonly-key", scopes=["read"], tier=APITier.FREE)
        raw_key = key_data["key"]

        resp = client.post(
            "/api/v1/bot/start",
            json={"paper_mode": True},
            headers={"X-API-Key": raw_key},
        )
        assert resp.status_code == 403
        assert "Insufficient scope" in resp.json()["detail"]

    def test_read_scope_allowed_on_read_endpoint(self, client):
        """Key with 'read' scope can access read endpoints."""
        from src.api.dependencies import get_key_manager
        mgr = get_key_manager()
        key_data = mgr.create_key("testuser2", "reader-key", scopes=["read"], tier=APITier.FREE)
        raw_key = key_data["key"]

        resp = client.get(
            "/api/v1/bot/status",
            headers={"X-API-Key": raw_key},
        )
        assert resp.status_code == 200

    def test_admin_scope_grants_write(self, client):
        """Admin scope grants access to write endpoints."""
        from src.api.dependencies import get_key_manager
        mgr = get_key_manager()
        key_data = mgr.create_key("admin", "admin-key", scopes=["admin"], tier=APITier.ENTERPRISE)
        raw_key = key_data["key"]

        resp = client.post(
            "/api/v1/bot/start",
            json={"paper_mode": True},
            headers={"X-API-Key": raw_key},
        )
        assert resp.status_code in (200, 409)

    def test_revoked_key_rejected(self, client):
        """Revoked key returns 401."""
        from src.api.dependencies import get_key_manager
        mgr = get_key_manager()
        key_data = mgr.create_key("testuser3", "to-revoke", scopes=["write"], tier=APITier.FREE)
        raw_key = key_data["key"]
        mgr.revoke_key(key_data["key_id"])

        resp = client.post(
            "/api/v1/bot/start",
            json={"paper_mode": True},
            headers={"X-API-Key": raw_key},
        )
        assert resp.status_code == 401

    def test_health_endpoint_unauthenticated(self, client):
        """Health endpoint doesn't require auth even when auth is enforced."""
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_metrics_endpoint_unauthenticated(self, client):
        """Metrics endpoint doesn't require auth."""
        resp = client.get("/metrics")
        assert resp.status_code == 200


class TestRateLimiting:
    """Test rate limiting on API endpoints."""

    @pytest.fixture(autouse=True)
    def _enable_auth(self, monkeypatch):
        monkeypatch.delenv("AXION_DEV_MODE", raising=False)
        monkeypatch.setenv("AXION_REQUIRE_API_KEY", "true")

    @pytest.fixture
    def app(self):
        return create_app()

    @pytest.fixture
    def client(self, app):
        from fastapi.testclient import TestClient
        return TestClient(app)

    @pytest.fixture
    def free_key(self):
        """Create a FREE tier key (10 req/min)."""
        from src.api.dependencies import get_key_manager, get_rate_limiter
        # Reset singletons for clean rate limit state
        import src.api.dependencies as deps
        deps._key_manager = None
        deps._rate_limiter = None
        mgr = get_key_manager()
        key_data = mgr.create_key("ratelimit-user", "rl-key", scopes=["read", "write"], tier=APITier.FREE)
        return key_data["key"]

    def test_rate_limit_headers_with_key(self, client, free_key):
        """Rate limit headers appear in authenticated responses."""
        resp = client.get(
            "/api/v1/bot/status",
            headers={"X-API-Key": free_key},
        )
        assert resp.status_code == 200
        assert "x-ratelimit-limit" in resp.headers
        assert int(resp.headers["x-ratelimit-limit"]) == 10  # FREE tier: 10/min
        assert "x-ratelimit-remaining" in resp.headers

    def test_rate_limit_remaining_decreases(self, client, free_key):
        """Remaining count decreases with each request."""
        headers = {"X-API-Key": free_key}
        r1 = client.get("/api/v1/bot/status", headers=headers)
        r2 = client.get("/api/v1/bot/status", headers=headers)
        rem1 = int(r1.headers["x-ratelimit-remaining"])
        rem2 = int(r2.headers["x-ratelimit-remaining"])
        assert rem2 < rem1

    def test_rate_limit_429_when_exceeded(self, client, free_key):
        """429 returned when per-minute limit exceeded."""
        headers = {"X-API-Key": free_key}
        # FREE tier allows 10 per minute — exhaust them
        for _ in range(10):
            client.get("/api/v1/bot/status", headers=headers)

        resp = client.get("/api/v1/bot/status", headers=headers)
        assert resp.status_code == 429
        assert "Rate limit exceeded" in resp.json()["detail"]

    def test_rate_limit_daily_remaining_header(self, client, free_key):
        """X-RateLimit-Daily-Remaining header is present."""
        resp = client.get(
            "/api/v1/bot/status",
            headers={"X-API-Key": free_key},
        )
        assert "x-ratelimit-daily-remaining" in resp.headers


# =============================================================================
# Auth Coverage — All Route Modules
# =============================================================================


class TestAllRoutesHaveAuth:
    """Verify rate-limit headers appear on endpoints from every route module.

    In dev mode (AXION_DEV_MODE=true set in conftest), the check_rate_limit
    dependency still runs and injects X-RateLimit-* headers. This proves auth is wired.
    """

    @pytest.fixture
    def app(self):
        return create_app()

    @pytest.fixture
    def client(self, app):
        from fastapi.testclient import TestClient
        return TestClient(app)

    def _assert_rate_headers(self, resp):
        assert "x-ratelimit-limit" in resp.headers, (
            f"Missing x-ratelimit-limit on {resp.url}"
        )
        assert "x-ratelimit-remaining" in resp.headers

    def test_market_data_has_auth(self, client):
        resp = client.get("/api/v1/market/quotes/AAPL")
        assert resp.status_code == 200
        self._assert_rate_headers(resp)

    def test_factors_has_auth(self, client):
        resp = client.get("/api/v1/factors/AAPL")
        assert resp.status_code == 200
        self._assert_rate_headers(resp)

    def test_portfolio_has_auth(self, client):
        resp = client.get("/api/v1/portfolio")
        assert resp.status_code == 200
        self._assert_rate_headers(resp)

    def test_ai_has_auth(self, client):
        resp = client.get("/api/v1/ai/predictions/AAPL")
        assert resp.status_code == 200
        self._assert_rate_headers(resp)

    def test_options_has_auth(self, client):
        resp = client.get("/api/v1/options/AAPL/chain")
        assert resp.status_code == 200
        self._assert_rate_headers(resp)

    def test_backtesting_has_auth(self, client):
        create_resp = client.post("/api/v1/backtest", json={
            "strategy": "momentum",
            "start_date": "2020-01-01",
            "end_date": "2024-12-31",
        })
        bt_id = create_resp.json()["backtest_id"]
        resp = client.get(f"/api/v1/backtest/{bt_id}")
        assert resp.status_code == 200
        self._assert_rate_headers(resp)

    def test_keys_has_auth(self, client):
        resp = client.get("/api/v1/keys")
        assert resp.status_code == 200
        self._assert_rate_headers(resp)


class TestAllRoutesAuthEnforced:
    """Verify 401 on representative endpoints when auth is required."""

    @pytest.fixture
    def app(self):
        return create_app()

    @pytest.fixture
    def client(self, app):
        from fastapi.testclient import TestClient
        return TestClient(app)

    @pytest.fixture(autouse=True)
    def _enable_auth(self, monkeypatch):
        monkeypatch.delenv("AXION_DEV_MODE", raising=False)
        monkeypatch.setenv("AXION_REQUIRE_API_KEY", "true")

    def test_market_data_401(self, client):
        resp = client.get("/api/v1/market/quotes/AAPL")
        assert resp.status_code == 401

    def test_factors_401(self, client):
        resp = client.get("/api/v1/factors/AAPL")
        assert resp.status_code == 401

    def test_portfolio_401(self, client):
        resp = client.get("/api/v1/portfolio")
        assert resp.status_code == 401

    def test_ai_401(self, client):
        resp = client.get("/api/v1/ai/predictions/AAPL")
        assert resp.status_code == 401

    def test_options_401(self, client):
        resp = client.get("/api/v1/options/AAPL/chain")
        assert resp.status_code == 401

    def test_backtesting_401(self, client):
        resp = client.post("/api/v1/backtest", json={
            "strategy": "momentum",
            "start_date": "2020-01-01",
            "end_date": "2024-12-31",
        })
        assert resp.status_code == 401

    def test_keys_list_401(self, client):
        resp = client.get("/api/v1/keys")
        assert resp.status_code == 401

    def test_keys_create_401(self, client):
        resp = client.post("/api/v1/keys", json={"name": "test"})
        assert resp.status_code == 401

    def test_keys_delete_401(self, client):
        resp = client.delete("/api/v1/keys/nonexistent")
        assert resp.status_code == 401

    def test_portfolio_write_401(self, client):
        resp = client.post("/api/v1/portfolio/optimize", json={"method": "min_variance"})
        assert resp.status_code == 401

    def test_ai_write_401(self, client):
        resp = client.post("/api/v1/ai/chat", json={"message": "hello"})
        assert resp.status_code == 401

    def test_options_write_401(self, client):
        resp = client.post("/api/v1/options/analyze", json={"symbol": "AAPL", "strategy": "covered_call"})
        assert resp.status_code == 401


# =============================================================================
# API Key Management Endpoint Tests
# =============================================================================


class TestKeyManagement:
    """Test POST/GET/DELETE /api/v1/keys endpoints."""

    @pytest.fixture(autouse=True)
    def _enable_auth(self, monkeypatch):
        monkeypatch.delenv("AXION_DEV_MODE", raising=False)
        monkeypatch.setenv("AXION_REQUIRE_API_KEY", "true")

    @pytest.fixture(autouse=True)
    def _reset_singletons(self):
        """Ensure clean key manager state per test."""
        import src.api.dependencies as deps
        deps._key_manager = None
        deps._rate_limiter = None
        yield
        deps._key_manager = None
        deps._rate_limiter = None

    @pytest.fixture
    def app(self):
        return create_app()

    @pytest.fixture
    def client(self, app):
        from fastapi.testclient import TestClient
        return TestClient(app)

    @pytest.fixture
    def admin_key(self):
        """Create an admin API key for authenticated requests."""
        from src.api.dependencies import get_key_manager
        mgr = get_key_manager()
        data = mgr.create_key("admin", "bootstrap-admin", scopes=["admin"], tier=APITier.ENTERPRISE)
        return data["key"]

    @pytest.fixture
    def read_key(self):
        """Create a read-only API key."""
        from src.api.dependencies import get_key_manager
        mgr = get_key_manager()
        data = mgr.create_key("reader", "read-key", scopes=["read"], tier=APITier.FREE)
        return data["key"]

    def test_create_key(self, client, admin_key):
        """Admin can create a new API key via POST /api/v1/keys."""
        resp = client.post(
            "/api/v1/keys",
            json={"name": "my-new-key", "scopes": ["read", "write"]},
            headers={"X-API-Key": admin_key},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "my-new-key"
        assert data["key"].startswith("ax_")
        assert data["is_active"] is True
        assert "read" in data["scopes"]
        assert "write" in data["scopes"]

    def test_create_key_default_scopes(self, client, admin_key):
        """Key created without explicit scopes defaults to ['read']."""
        resp = client.post(
            "/api/v1/keys",
            json={"name": "default-scope"},
            headers={"X-API-Key": admin_key},
        )
        assert resp.status_code == 201
        assert resp.json()["scopes"] == ["read"]

    def test_create_key_forbidden_for_read_scope(self, client, read_key):
        """Non-admin key cannot create keys (403)."""
        resp = client.post(
            "/api/v1/keys",
            json={"name": "attempt"},
            headers={"X-API-Key": read_key},
        )
        assert resp.status_code == 403

    def test_list_keys(self, client, admin_key):
        """Admin can list their own keys."""
        # Create one more key first
        client.post(
            "/api/v1/keys",
            json={"name": "extra-key"},
            headers={"X-API-Key": admin_key},
        )
        resp = client.get("/api/v1/keys", headers={"X-API-Key": admin_key})
        assert resp.status_code == 200
        keys = resp.json()
        # Should see the bootstrap-admin key + the extra-key
        assert len(keys) >= 2
        names = [k["name"] for k in keys]
        assert "bootstrap-admin" in names
        assert "extra-key" in names

    def test_list_keys_no_raw_key_exposed(self, client, admin_key):
        """Listed keys do not expose the raw key value."""
        resp = client.get("/api/v1/keys", headers={"X-API-Key": admin_key})
        for k in resp.json():
            assert k.get("key") is None

    def test_revoke_key(self, client, admin_key):
        """Admin can revoke a key by ID."""
        # Create a key to revoke
        create_resp = client.post(
            "/api/v1/keys",
            json={"name": "to-revoke"},
            headers={"X-API-Key": admin_key},
        )
        key_id = create_resp.json()["key_id"]

        resp = client.delete(
            f"/api/v1/keys/{key_id}",
            headers={"X-API-Key": admin_key},
        )
        assert resp.status_code == 200
        assert resp.json()["revoked"] is True

    def test_revoke_nonexistent_key_404(self, client, admin_key):
        """Revoking a non-existent key returns 404."""
        resp = client.delete(
            "/api/v1/keys/does-not-exist",
            headers={"X-API-Key": admin_key},
        )
        assert resp.status_code == 404

    def test_revoke_forbidden_for_read_scope(self, client, admin_key, read_key):
        """Non-admin key cannot revoke keys (403)."""
        resp = client.delete(
            "/api/v1/keys/some-id",
            headers={"X-API-Key": read_key},
        )
        assert resp.status_code == 403

    def test_revoked_key_no_longer_authenticates(self, client, admin_key):
        """Once revoked, the key returns 401 on subsequent requests."""
        # Create a key
        create_resp = client.post(
            "/api/v1/keys",
            json={"name": "ephemeral", "scopes": ["read"]},
            headers={"X-API-Key": admin_key},
        )
        raw_key = create_resp.json()["key"]
        key_id = create_resp.json()["key_id"]

        # Verify it works
        resp = client.get("/api/v1/keys", headers={"X-API-Key": raw_key})
        assert resp.status_code == 200

        # Revoke it
        client.delete(f"/api/v1/keys/{key_id}", headers={"X-API-Key": admin_key})

        # Verify it no longer works
        resp = client.get("/api/v1/keys", headers={"X-API-Key": raw_key})
        assert resp.status_code == 401
