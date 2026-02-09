"""Tests for Smart Multi-Broker Execution (PRD-146).

8 test classes, ~50 tests covering registry, routing, aggregation,
execution, and module imports.
"""

import asyncio
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# =====================================================================
# Helper: Mock Broker Adapter
# =====================================================================


def _make_mock_adapter(connected=True, assets=None, positions=None, account=None):
    """Create a mock broker adapter satisfying the BrokerAdapter protocol."""
    adapter = MagicMock()
    adapter.is_connected = connected
    adapter.supported_assets = assets or ["stock"]
    adapter.connect = AsyncMock(return_value=True)
    adapter.disconnect = AsyncMock()
    adapter.get_account = AsyncMock(return_value=account or {
        "equity": 100000.0, "cash": 50000.0, "buying_power": 100000.0,
    })
    adapter.get_positions = AsyncMock(return_value=positions or [
        {"symbol": "AAPL", "qty": 100, "market_value": 23000.0,
         "cost_basis": 21000.0, "unrealized_pnl": 2000.0, "average_price": 210.0},
    ])
    adapter.place_order = AsyncMock(return_value={
        "order_id": "MOCK-001", "status": "FILLED",
        "fill_price": 230.0, "filled_quantity": 10, "fee": 0.0,
    })
    adapter.cancel_order = AsyncMock(return_value=True)
    adapter.get_quote = AsyncMock(return_value={
        "symbol": "AAPL", "last_price": 230.0, "bid": 229.95, "ask": 230.05,
    })
    return adapter


# =====================================================================
# Test: BrokerRegistry
# =====================================================================


class TestBrokerRegistry:
    """Tests for BrokerRegistry (8 tests)."""

    def test_register_broker(self):
        from src.multi_broker.registry import BrokerRegistry
        registry = BrokerRegistry()
        adapter = _make_mock_adapter()
        info = registry.register("alpaca", adapter)
        assert info.broker_name == "alpaca"
        assert "alpaca" in registry.brokers

    def test_register_duplicate_raises(self):
        from src.multi_broker.registry import BrokerRegistry
        registry = BrokerRegistry()
        adapter = _make_mock_adapter()
        registry.register("alpaca", adapter)
        with pytest.raises(ValueError, match="already registered"):
            registry.register("alpaca", adapter)

    def test_unregister_broker(self):
        from src.multi_broker.registry import BrokerRegistry
        registry = BrokerRegistry()
        adapter = _make_mock_adapter()
        registry.register("alpaca", adapter)
        assert registry.unregister("alpaca") is True
        assert "alpaca" not in registry.brokers

    def test_unregister_nonexistent(self):
        from src.multi_broker.registry import BrokerRegistry
        registry = BrokerRegistry()
        assert registry.unregister("nonexistent") is False

    def test_get_connected(self):
        from src.multi_broker.registry import BrokerRegistry
        registry = BrokerRegistry()
        connected_adapter = _make_mock_adapter(connected=True)
        disconnected_adapter = _make_mock_adapter(connected=False)
        registry.register("alpaca", connected_adapter)
        registry.register("schwab", disconnected_adapter)
        connected = registry.get_connected()
        assert len(connected) == 1
        assert connected[0].broker_name == "alpaca"

    def test_get_by_asset_stock(self):
        from src.multi_broker.registry import BrokerRegistry
        registry = BrokerRegistry()
        adapter1 = _make_mock_adapter(connected=True)
        adapter2 = _make_mock_adapter(connected=True)
        registry.register("alpaca", adapter1, supported_assets=["stock", "options"])
        registry.register("coinbase", adapter2, supported_assets=["crypto"])
        stock_brokers = registry.get_by_asset("stock")
        assert len(stock_brokers) == 1
        assert stock_brokers[0].broker_name == "alpaca"

    def test_get_by_asset_crypto(self):
        from src.multi_broker.registry import BrokerRegistry
        registry = BrokerRegistry()
        adapter1 = _make_mock_adapter(connected=True)
        adapter2 = _make_mock_adapter(connected=True)
        registry.register("robinhood", adapter1, supported_assets=["stock", "crypto"])
        registry.register("coinbase", adapter2, supported_assets=["crypto"])
        crypto_brokers = registry.get_by_asset("crypto")
        assert len(crypto_brokers) == 2

    def test_status_summary(self):
        from src.multi_broker.registry import BrokerRegistry
        registry = BrokerRegistry()
        adapter1 = _make_mock_adapter(connected=True)
        adapter2 = _make_mock_adapter(connected=False)
        registry.register("alpaca", adapter1)
        registry.register("schwab", adapter2)
        summary = registry.status_summary()
        assert summary["total"] == 2
        assert summary["connected"] == 1
        assert summary["disconnected"] == 1
        assert "alpaca" in summary["brokers"]
        assert "schwab" in summary["brokers"]


# =====================================================================
# Test: BrokerInfo
# =====================================================================


class TestBrokerInfo:
    """Tests for BrokerInfo dataclass."""

    def test_defaults(self):
        from src.multi_broker.registry import BrokerInfo, BrokerStatus
        info = BrokerInfo(broker_name="test", adapter=None)
        assert info.status == BrokerStatus.DISCONNECTED
        assert info.latency_ms == 100.0
        assert info.priority == 0

    def test_to_dict(self):
        from src.multi_broker.registry import BrokerInfo, BrokerStatus
        info = BrokerInfo(
            broker_name="alpaca",
            adapter=None,
            status=BrokerStatus.CONNECTED,
            supported_assets=["stock"],
            fee_schedule={"stock_commission": 0.0},
            latency_ms=50.0,
        )
        d = info.to_dict()
        assert d["broker_name"] == "alpaca"
        assert d["status"] == "connected"
        assert d["latency_ms"] == 50.0

    def test_to_dict_with_sync(self):
        from src.multi_broker.registry import BrokerInfo, BrokerStatus
        sync_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
        info = BrokerInfo(
            broker_name="schwab", adapter=None,
            last_sync=sync_time,
        )
        d = info.to_dict()
        assert d["last_sync"] is not None
        assert "2025" in d["last_sync"]

    def test_update_status(self):
        from src.multi_broker.registry import BrokerRegistry, BrokerStatus
        registry = BrokerRegistry()
        adapter = _make_mock_adapter(connected=True)
        registry.register("alpaca", adapter)
        registry.update_status("alpaca", BrokerStatus.ERROR, "Connection lost")
        info = registry.get("alpaca")
        assert info.status == BrokerStatus.ERROR
        assert info.error_message == "Connection lost"


# =====================================================================
# Test: RoutingRule
# =====================================================================


class TestRoutingRule:
    """Tests for RoutingRule dataclass (4 tests)."""

    def test_defaults(self):
        from src.multi_broker.router import RoutingRule, RoutingCriteria
        rule = RoutingRule()
        assert rule.asset_type == "stock"
        assert rule.preferred_broker == ""
        assert rule.criteria == RoutingCriteria.COST

    def test_custom_rule(self):
        from src.multi_broker.router import RoutingRule, RoutingCriteria
        rule = RoutingRule(
            asset_type="crypto",
            preferred_broker="coinbase",
            fallback_brokers=["robinhood"],
            criteria=RoutingCriteria.SPEED,
        )
        assert rule.asset_type == "crypto"
        assert rule.preferred_broker == "coinbase"
        assert rule.criteria == RoutingCriteria.SPEED

    def test_to_dict(self):
        from src.multi_broker.router import RoutingRule
        rule = RoutingRule(asset_type="options", preferred_broker="schwab")
        d = rule.to_dict()
        assert d["asset_type"] == "options"
        assert d["preferred_broker"] == "schwab"

    def test_fallback_list(self):
        from src.multi_broker.router import RoutingRule
        rule = RoutingRule(
            asset_type="stock",
            preferred_broker="alpaca",
            fallback_brokers=["schwab", "robinhood"],
        )
        assert len(rule.fallback_brokers) == 2
        assert "schwab" in rule.fallback_brokers


# =====================================================================
# Test: RouteDecision
# =====================================================================


class TestRouteDecision:
    """Tests for RouteDecision dataclass (3 tests)."""

    def test_creation(self):
        from src.multi_broker.router import RouteDecision
        decision = RouteDecision(broker_name="alpaca", reason="Best cost")
        assert decision.broker_name == "alpaca"
        assert decision.reason == "Best cost"
        assert len(decision.route_id) == 12

    def test_to_dict(self):
        from src.multi_broker.router import RouteDecision
        decision = RouteDecision(
            broker_name="coinbase",
            reason="Smart default: crypto -> coinbase",
            estimated_fee=1.20,
            estimated_latency=60.0,
        )
        d = decision.to_dict()
        assert d["broker_name"] == "coinbase"
        assert d["estimated_fee"] == 1.20
        assert "timestamp" in d

    def test_fallback_chain(self):
        from src.multi_broker.router import RouteDecision
        decision = RouteDecision(
            broker_name="alpaca",
            fallback_chain=["schwab", "robinhood"],
        )
        assert len(decision.fallback_chain) == 2


# =====================================================================
# Test: OrderRouter
# =====================================================================


class TestOrderRouter:
    """Tests for OrderRouter (10 tests)."""

    def _make_registry_with_brokers(self):
        """Create a registry with 4 connected mock brokers."""
        from src.multi_broker.registry import BrokerRegistry
        registry = BrokerRegistry()
        registry.register(
            "alpaca", _make_mock_adapter(connected=True),
            supported_assets=["stock", "options"], latency_ms=50.0, priority=0,
        )
        registry.register(
            "robinhood", _make_mock_adapter(connected=True),
            supported_assets=["stock", "crypto", "options"], latency_ms=80.0, priority=1,
        )
        registry.register(
            "coinbase", _make_mock_adapter(connected=True),
            supported_assets=["crypto"], latency_ms=60.0, priority=0,
        )
        registry.register(
            "schwab", _make_mock_adapter(connected=True),
            supported_assets=["stock", "options", "mutual_funds"], latency_ms=90.0, priority=2,
        )
        return registry

    def test_route_crypto_to_coinbase(self):
        from src.multi_broker.router import OrderRouter
        registry = self._make_registry_with_brokers()
        router = OrderRouter(registry)
        decision = router.route({"symbol": "BTC-USD", "asset_type": "crypto"})
        assert decision.broker_name == "coinbase"
        assert "crypto" in decision.reason.lower() or "coinbase" in decision.reason.lower()

    def test_route_stock_to_alpaca(self):
        from src.multi_broker.router import OrderRouter
        registry = self._make_registry_with_brokers()
        router = OrderRouter(registry)
        decision = router.route({"symbol": "AAPL", "asset_type": "stock"})
        assert decision.broker_name == "alpaca"

    def test_route_options_to_schwab(self):
        from src.multi_broker.router import OrderRouter
        registry = self._make_registry_with_brokers()
        router = OrderRouter(registry)
        decision = router.route({"symbol": "AAPL_C230", "asset_type": "options"})
        assert decision.broker_name == "schwab"

    def test_route_fractional_to_robinhood(self):
        from src.multi_broker.router import OrderRouter
        registry = self._make_registry_with_brokers()
        router = OrderRouter(registry)
        decision = router.route({"symbol": "AAPL", "asset_type": "stock", "fractional": True})
        assert decision.broker_name == "robinhood"

    def test_route_with_user_rule(self):
        from src.multi_broker.router import OrderRouter, RoutingRule
        registry = self._make_registry_with_brokers()
        router = OrderRouter(registry)
        router.add_rule(RoutingRule(asset_type="stock", preferred_broker="schwab"))
        decision = router.route({"symbol": "AAPL", "asset_type": "stock"})
        assert decision.broker_name == "schwab"
        assert "User rule" in decision.reason

    def test_route_user_rule_overrides_smart_default(self):
        from src.multi_broker.router import OrderRouter, RoutingRule
        registry = self._make_registry_with_brokers()
        router = OrderRouter(registry)
        router.add_rule(RoutingRule(
            asset_type="crypto",
            preferred_broker="robinhood",
            fallback_brokers=["coinbase"],
        ))
        decision = router.route({"symbol": "BTC-USD", "asset_type": "crypto"})
        assert decision.broker_name == "robinhood"
        assert "coinbase" in decision.fallback_chain

    def test_route_no_broker_available(self):
        from src.multi_broker.registry import BrokerRegistry
        from src.multi_broker.router import OrderRouter
        registry = BrokerRegistry()
        router = OrderRouter(registry)
        decision = router.route({"symbol": "AAPL", "asset_type": "stock"})
        assert decision.broker_name == ""
        assert "no connected broker" in decision.reason.lower() or "no connected" in decision.reason.lower()

    def test_route_builds_fallback_chain(self):
        from src.multi_broker.router import OrderRouter
        registry = self._make_registry_with_brokers()
        router = OrderRouter(registry)
        decision = router.route({"symbol": "AAPL", "asset_type": "stock"})
        # alpaca is primary; schwab and robinhood should be fallbacks
        assert len(decision.fallback_chain) > 0
        assert "alpaca" not in decision.fallback_chain

    def test_route_batch(self):
        from src.multi_broker.router import OrderRouter
        registry = self._make_registry_with_brokers()
        router = OrderRouter(registry)
        orders = [
            {"symbol": "AAPL", "asset_type": "stock"},
            {"symbol": "BTC-USD", "asset_type": "crypto"},
            {"symbol": "SPY_C590", "asset_type": "options"},
        ]
        decisions = router.route_batch(orders)
        assert len(decisions) == 3
        assert decisions[0].broker_name == "alpaca"
        assert decisions[1].broker_name == "coinbase"
        assert decisions[2].broker_name == "schwab"

    def test_route_history(self):
        from src.multi_broker.router import OrderRouter
        registry = self._make_registry_with_brokers()
        router = OrderRouter(registry)
        router.route({"symbol": "AAPL", "asset_type": "stock"})
        router.route({"symbol": "BTC-USD", "asset_type": "crypto"})
        assert len(router.route_history) == 2


# =====================================================================
# Test: PortfolioAggregator
# =====================================================================


class TestPortfolioAggregator:
    """Tests for PortfolioAggregator (8 tests)."""

    def _make_registry_with_positions(self):
        from src.multi_broker.registry import BrokerRegistry
        registry = BrokerRegistry()
        alpaca_adapter = _make_mock_adapter(
            connected=True,
            account={"equity": 100000.0, "cash": 50000.0},
            positions=[
                {"symbol": "AAPL", "qty": 100, "market_value": 23000.0,
                 "cost_basis": 21000.0, "unrealized_pnl": 2000.0, "average_price": 210.0},
                {"symbol": "MSFT", "qty": 50, "market_value": 20750.0,
                 "cost_basis": 20000.0, "unrealized_pnl": 750.0, "average_price": 400.0},
            ],
        )
        schwab_adapter = _make_mock_adapter(
            connected=True,
            account={"equity": 80000.0, "cash": 30000.0},
            positions=[
                {"symbol": "AAPL", "qty": 50, "market_value": 11500.0,
                 "cost_basis": 10500.0, "unrealized_pnl": 1000.0, "average_price": 210.0},
                {"symbol": "SPY", "qty": 30, "market_value": 17715.0,
                 "cost_basis": 17250.0, "unrealized_pnl": 465.0, "average_price": 575.0},
            ],
        )
        registry.register("alpaca", alpaca_adapter, supported_assets=["stock", "options"])
        registry.register("schwab", schwab_adapter, supported_assets=["stock", "options"])
        return registry

    @pytest.mark.asyncio
    async def test_sync_all(self):
        from src.multi_broker.aggregator import PortfolioAggregator
        registry = self._make_registry_with_positions()
        agg = PortfolioAggregator(registry)
        results = await agg.sync_all()
        assert results["alpaca"] is True
        assert results["schwab"] is True
        assert agg.last_sync is not None

    @pytest.mark.asyncio
    async def test_unified_portfolio(self):
        from src.multi_broker.aggregator import PortfolioAggregator
        registry = self._make_registry_with_positions()
        agg = PortfolioAggregator(registry)
        await agg.sync_all()
        portfolio = agg.get_unified_portfolio()
        assert portfolio.total_value > 0
        assert len(portfolio.positions) > 0
        assert "alpaca" in portfolio.by_broker
        assert "schwab" in portfolio.by_broker

    @pytest.mark.asyncio
    async def test_cross_broker_aapl(self):
        from src.multi_broker.aggregator import PortfolioAggregator
        registry = self._make_registry_with_positions()
        agg = PortfolioAggregator(registry)
        await agg.sync_all()
        exposure = agg.get_cross_broker_exposure("AAPL")
        assert exposure["symbol"] == "AAPL"
        assert exposure["total_qty"] == 150  # 100 + 50
        assert exposure["broker_count"] == 2
        assert "alpaca" in exposure["by_broker"]
        assert "schwab" in exposure["by_broker"]

    @pytest.mark.asyncio
    async def test_cross_broker_concentration(self):
        from src.multi_broker.aggregator import PortfolioAggregator
        registry = self._make_registry_with_positions()
        agg = PortfolioAggregator(registry)
        await agg.sync_all()
        exposure = agg.get_cross_broker_exposure("AAPL")
        # alpaca has 100/150 = 66.67%, schwab has 50/150 = 33.33%
        assert abs(exposure["concentration"]["alpaca"] - 66.67) < 1.0
        assert abs(exposure["concentration"]["schwab"] - 33.33) < 1.0

    @pytest.mark.asyncio
    async def test_broker_allocation(self):
        from src.multi_broker.aggregator import PortfolioAggregator
        registry = self._make_registry_with_positions()
        agg = PortfolioAggregator(registry)
        await agg.sync_all()
        allocation = agg.get_broker_allocation()
        assert "alpaca" in allocation
        assert "schwab" in allocation
        total = sum(allocation.values())
        assert abs(total - 100.0) < 1.0  # Should sum to ~100%

    @pytest.mark.asyncio
    async def test_empty_portfolio(self):
        from src.multi_broker.registry import BrokerRegistry
        from src.multi_broker.aggregator import PortfolioAggregator
        registry = BrokerRegistry()
        agg = PortfolioAggregator(registry)
        await agg.sync_all()
        portfolio = agg.get_unified_portfolio()
        assert portfolio.total_value == 0.0
        assert len(portfolio.positions) == 0

    @pytest.mark.asyncio
    async def test_portfolio_to_dict(self):
        from src.multi_broker.aggregator import PortfolioAggregator
        registry = self._make_registry_with_positions()
        agg = PortfolioAggregator(registry)
        await agg.sync_all()
        portfolio = agg.get_unified_portfolio()
        d = portfolio.to_dict()
        assert "total_value" in d
        assert "positions" in d
        assert "allocation" in d
        assert isinstance(d["positions"], list)

    @pytest.mark.asyncio
    async def test_sync_failure_handled(self):
        from src.multi_broker.registry import BrokerRegistry
        from src.multi_broker.aggregator import PortfolioAggregator
        registry = BrokerRegistry()
        broken_adapter = _make_mock_adapter(connected=True)
        broken_adapter.get_account = AsyncMock(side_effect=Exception("Connection lost"))
        registry.register("broken", broken_adapter, supported_assets=["stock"])
        agg = PortfolioAggregator(registry)
        results = await agg.sync_all()
        assert results["broken"] is False


# =====================================================================
# Test: MultiBrokerExecutor
# =====================================================================


class TestMultiBrokerExecutor:
    """Tests for MultiBrokerExecutor (6 tests)."""

    def _make_full_setup(self):
        from src.multi_broker.registry import BrokerRegistry
        from src.multi_broker.router import OrderRouter
        from src.multi_broker.executor import MultiBrokerExecutor
        registry = BrokerRegistry()
        registry.register(
            "alpaca", _make_mock_adapter(connected=True),
            supported_assets=["stock", "options"], latency_ms=50.0,
        )
        registry.register(
            "schwab", _make_mock_adapter(connected=True),
            supported_assets=["stock", "options"], latency_ms=90.0, priority=2,
        )
        registry.register(
            "coinbase", _make_mock_adapter(connected=True),
            supported_assets=["crypto"], latency_ms=60.0,
        )
        router = OrderRouter(registry)
        executor = MultiBrokerExecutor(registry, router)
        return registry, router, executor

    @pytest.mark.asyncio
    async def test_execute_success(self):
        from src.multi_broker.executor import ExecutionStatus
        _, _, executor = self._make_full_setup()
        result = await executor.execute({"symbol": "AAPL", "asset_type": "stock", "qty": 10})
        assert result.status == ExecutionStatus.FILLED
        assert result.broker_name == "alpaca"
        assert result.failover_used is False

    @pytest.mark.asyncio
    async def test_execute_failover(self):
        from src.multi_broker.registry import BrokerRegistry
        from src.multi_broker.router import OrderRouter
        from src.multi_broker.executor import MultiBrokerExecutor, ExecutionStatus
        registry = BrokerRegistry()
        # Primary broker that will fail
        broken_adapter = _make_mock_adapter(connected=True)
        broken_adapter.place_order = AsyncMock(side_effect=Exception("Broker down"))
        registry.register(
            "alpaca", broken_adapter,
            supported_assets=["stock"], latency_ms=50.0,
        )
        # Fallback broker that works
        registry.register(
            "schwab", _make_mock_adapter(connected=True),
            supported_assets=["stock"], latency_ms=90.0, priority=2,
        )
        router = OrderRouter(registry)
        executor = MultiBrokerExecutor(registry, router)
        result = await executor.execute({"symbol": "AAPL", "asset_type": "stock", "qty": 10})
        assert result.status == ExecutionStatus.FILLED
        assert result.broker_name == "schwab"
        assert result.failover_used is True
        assert result.failover_from == "alpaca"

    @pytest.mark.asyncio
    async def test_execute_all_fail(self):
        from src.multi_broker.registry import BrokerRegistry
        from src.multi_broker.router import OrderRouter
        from src.multi_broker.executor import MultiBrokerExecutor, ExecutionStatus
        registry = BrokerRegistry()
        broken = _make_mock_adapter(connected=True)
        broken.place_order = AsyncMock(side_effect=Exception("Down"))
        registry.register("alpaca", broken, supported_assets=["stock"])
        router = OrderRouter(registry)
        executor = MultiBrokerExecutor(registry, router)
        result = await executor.execute({"symbol": "AAPL", "asset_type": "stock"})
        assert result.status == ExecutionStatus.FAILED
        assert "failed" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_execute_batch(self):
        from src.multi_broker.executor import ExecutionStatus
        _, _, executor = self._make_full_setup()
        orders = [
            {"symbol": "AAPL", "asset_type": "stock", "qty": 10},
            {"symbol": "BTC-USD", "asset_type": "crypto", "qty": 1},
        ]
        results = await executor.execute_batch(orders)
        assert len(results) == 2
        assert results[0].broker_name == "alpaca"
        assert results[1].broker_name == "coinbase"

    @pytest.mark.asyncio
    async def test_rate_limiting(self):
        from src.multi_broker.registry import BrokerRegistry
        from src.multi_broker.router import OrderRouter
        from src.multi_broker.executor import MultiBrokerExecutor, ExecutionStatus
        registry = BrokerRegistry()
        registry.register(
            "alpaca", _make_mock_adapter(connected=True),
            supported_assets=["stock"], latency_ms=50.0,
        )
        registry.register(
            "schwab", _make_mock_adapter(connected=True),
            supported_assets=["stock"], latency_ms=90.0, priority=2,
        )
        router = OrderRouter(registry)
        executor = MultiBrokerExecutor(registry, router, max_requests_per_minute=2)
        # Execute 3 orders; the 3rd should failover due to rate limiting on alpaca
        r1 = await executor.execute({"symbol": "AAPL", "asset_type": "stock", "qty": 10})
        r2 = await executor.execute({"symbol": "AAPL", "asset_type": "stock", "qty": 10})
        r3 = await executor.execute({"symbol": "AAPL", "asset_type": "stock", "qty": 10})
        assert r1.broker_name == "alpaca"
        assert r2.broker_name == "alpaca"
        # Third should failover to schwab because alpaca is rate limited
        assert r3.broker_name == "schwab"
        assert r3.failover_used is True

    @pytest.mark.asyncio
    async def test_execution_history(self):
        _, _, executor = self._make_full_setup()
        await executor.execute({"symbol": "AAPL", "asset_type": "stock", "qty": 10})
        await executor.execute({"symbol": "BTC-USD", "asset_type": "crypto", "qty": 1})
        history = executor.execution_history
        assert len(history) == 2


# =====================================================================
# Test: AggregatedModels
# =====================================================================


class TestAggregatedModels:
    """Tests for AggregatedPosition and AggregatedPortfolio dataclasses (4 tests)."""

    def test_aggregated_position_defaults(self):
        from src.multi_broker.aggregator import AggregatedPosition
        pos = AggregatedPosition()
        assert pos.symbol == ""
        assert pos.total_qty == 0.0
        assert pos.by_broker == {}

    def test_aggregated_position_to_dict(self):
        from src.multi_broker.aggregator import AggregatedPosition
        pos = AggregatedPosition(
            symbol="AAPL", total_qty=150, by_broker={"alpaca": 100, "schwab": 50},
            avg_cost=210.0, total_market_value=34500.0, total_pnl=3000.0,
            total_cost_basis=31500.0, pnl_pct=9.52,
        )
        d = pos.to_dict()
        assert d["symbol"] == "AAPL"
        assert d["total_qty"] == 150
        assert "alpaca" in d["by_broker"]

    def test_aggregated_portfolio_defaults(self):
        from src.multi_broker.aggregator import AggregatedPortfolio
        portfolio = AggregatedPortfolio()
        assert portfolio.total_value == 0.0
        assert portfolio.positions == []

    def test_aggregated_portfolio_to_dict(self):
        from src.multi_broker.aggregator import AggregatedPortfolio, AggregatedPosition
        pos = AggregatedPosition(symbol="AAPL", total_qty=100, total_market_value=23000.0)
        portfolio = AggregatedPortfolio(
            total_value=123000.0, total_pnl=5000.0, total_cash=50000.0,
            positions=[pos], allocation={"alpaca": 55.0, "schwab": 45.0},
        )
        d = portfolio.to_dict()
        assert d["total_value"] == 123000.0
        assert d["position_count"] == 1
        assert len(d["positions"]) == 1


# =====================================================================
# Test: Module Imports
# =====================================================================


class TestModuleImports:
    """Tests for module-level imports and exports (3 tests)."""

    def test_all_exports(self):
        import src.multi_broker as mod
        assert hasattr(mod, "__all__")
        assert len(mod.__all__) >= 12

    def test_key_classes_importable(self):
        from src.multi_broker import (
            BrokerAdapter,
            BrokerInfo,
            BrokerRegistry,
            BrokerStatus,
            RoutingRule,
            RouteDecision,
            OrderRouter,
            AggregatedPosition,
            AggregatedPortfolio,
            PortfolioAggregator,
            ExecutionResult,
            MultiBrokerExecutor,
        )
        assert BrokerRegistry is not None
        assert OrderRouter is not None
        assert PortfolioAggregator is not None
        assert MultiBrokerExecutor is not None

    def test_default_fee_schedules(self):
        from src.multi_broker import DEFAULT_FEE_SCHEDULES
        assert "alpaca" in DEFAULT_FEE_SCHEDULES
        assert "robinhood" in DEFAULT_FEE_SCHEDULES
        assert "coinbase" in DEFAULT_FEE_SCHEDULES
        assert "schwab" in DEFAULT_FEE_SCHEDULES
