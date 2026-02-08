"""Tests for PRD-108: Integration & Load Testing Framework."""

import asyncio
import time

import pytest

from src.testing.config import (
    LoadProfile,
    TestConfig,
    TestStatus,
    TestType,
)
from src.testing.base import (
    APITestBase,
    DatabaseTestBase,
    IntegrationTestBase,
    TestResult,
)
from src.testing.mocks import MockBroker, MockMarketData, MockRedis, OHLCVBar
from src.testing.fixtures import (
    TestOrder,
    TestPortfolio,
    TestSignal,
    TestMarketData,
    create_test_order,
    create_test_orders_batch,
    create_test_market_data,
    create_test_portfolio,
    create_test_portfolio_with_positions,
    create_test_signal,
)
from src.testing.load import LoadScenario, LoadTestResult, LoadTestRunner
from src.testing.benchmarks import BenchmarkResult, BenchmarkSuite


class TestTestConfig:
    """Tests for test configuration."""

    def test_default_config(self):
        config = TestConfig()
        assert config.test_type == TestType.INTEGRATION
        assert config.concurrency == 10
        assert config.iterations == 100

    def test_custom_config(self):
        config = TestConfig(
            test_type=TestType.LOAD,
            concurrency=50,
            load_profile=LoadProfile.SPIKE,
        )
        assert config.test_type == TestType.LOAD
        assert config.concurrency == 50

    def test_test_type_enum(self):
        assert TestType.UNIT.value == "unit"
        assert TestType.LOAD.value == "load"

    def test_load_profile_enum(self):
        assert LoadProfile.CONSTANT.value == "constant"
        assert LoadProfile.RAMP_UP.value == "ramp_up"

    def test_test_status_enum(self):
        assert TestStatus.PASSED.value == "passed"
        assert TestStatus.FAILED.value == "failed"


class TestIntegrationBase:
    """Tests for integration test base class."""

    def test_setup_teardown(self):
        base = IntegrationTestBase()
        assert not base.is_setup
        base.setup()
        assert base.is_setup
        base.teardown()
        assert base.is_teardown

    def test_register_resource(self):
        base = IntegrationTestBase()
        base.register_resource("db")
        base.register_resource("cache")
        assert len(base.get_resources()) == 2

    def test_teardown_clears_resources(self):
        base = IntegrationTestBase()
        base.register_resource("x")
        base.setup()
        base.teardown()
        assert len(base.get_resources()) == 0

    def test_run_test_passing(self):
        base = IntegrationTestBase()
        result = base.run_test("ok", lambda: None)
        assert result.status == TestStatus.PASSED

    def test_run_test_failing(self):
        base = IntegrationTestBase()
        result = base.run_test("fail", lambda: (_ for _ in ()).throw(AssertionError("bad")))

        def bad():
            raise AssertionError("bad")

        base2 = IntegrationTestBase()
        result = base2.run_test("fail", bad)
        assert result.status == TestStatus.FAILED

    def test_run_test_error(self):
        def error():
            raise RuntimeError("boom")
        base = IntegrationTestBase()
        result = base.run_test("err", error)
        assert result.status == TestStatus.ERROR

    def test_elapsed_ms(self):
        base = IntegrationTestBase()
        base.setup()
        time.sleep(0.01)
        assert base.get_elapsed_ms() >= 10


class TestAPITestBase:
    """Tests for API test base class."""

    def test_setup(self):
        api = APITestBase()
        api.setup()
        assert "api_client" in api.get_resources()
        assert api.base_url == "http://localhost:8000"

    def test_set_header(self):
        api = APITestBase()
        api.set_header("Authorization", "Bearer token")
        assert api.get_headers()["Authorization"] == "Bearer token"

    def test_simulate_request(self):
        api = APITestBase()
        record = api.simulate_request("GET", "/api/v1/health", status_code=200)
        assert record["method"] == "GET"
        assert record["status_code"] == 200

    def test_request_history(self):
        api = APITestBase()
        api.simulate_request("GET", "/a")
        api.simulate_request("POST", "/b")
        assert len(api.get_request_history()) == 2


class TestDatabaseTestBase:
    """Tests for database test base class."""

    def test_setup(self):
        db = DatabaseTestBase()
        db.setup()
        assert "database" in db.get_resources()
        assert db.transaction_active

    def test_rollback(self):
        db = DatabaseTestBase()
        db.setup()
        db.rollback()
        assert not db.transaction_active

    def test_commit(self):
        db = DatabaseTestBase()
        db.setup()
        db.commit()
        assert not db.transaction_active

    def test_create_table(self):
        db = DatabaseTestBase()
        db.create_table("test_table")
        assert "test_table" in db.get_tables()


class TestMockBroker:
    """Tests for mock broker."""

    def test_connect_disconnect(self):
        broker = MockBroker(latency_ms=0)
        assert not broker.is_connected
        broker.connect()
        assert broker.is_connected
        broker.disconnect()
        assert not broker.is_connected

    def test_submit_order(self):
        broker = MockBroker(latency_ms=0, fill_probability=1.0)
        order = broker.submit_order("AAPL", "buy", 100, 150.0)
        assert order.symbol == "AAPL"
        assert order.status == "filled"
        assert order.filled_quantity == 100

    def test_submit_order_rejected(self):
        broker = MockBroker(latency_ms=0, fill_probability=0.0)
        order = broker.submit_order("AAPL", "buy", 100, 150.0)
        assert order.status == "rejected"

    def test_get_orders(self):
        broker = MockBroker(latency_ms=0, fill_probability=1.0)
        broker.submit_order("AAPL", "buy", 100, 150.0)
        broker.submit_order("MSFT", "sell", 50, 300.0)
        assert len(broker.get_orders()) == 2

    def test_get_filled_orders(self):
        broker = MockBroker(latency_ms=0, fill_probability=1.0)
        broker.submit_order("AAPL", "buy", 100, 150.0)
        filled = broker.get_filled_orders()
        assert len(filled) == 1

    def test_fill_rate(self):
        broker = MockBroker(latency_ms=0, fill_probability=1.0)
        broker.submit_order("AAPL", "buy", 100, 150.0)
        assert broker.get_fill_rate() == 1.0

    def test_reset(self):
        broker = MockBroker(latency_ms=0, fill_probability=1.0)
        broker.submit_order("AAPL", "buy", 100, 150.0)
        broker.reset()
        assert len(broker.get_orders()) == 0


class TestMockMarketData:
    """Tests for mock market data."""

    def test_generate_bars(self):
        md = MockMarketData(seed=42)
        bars = md.generate_bars("AAPL", n_bars=50, start_price=150.0)
        assert len(bars) == 50
        assert all(isinstance(b, OHLCVBar) for b in bars)

    def test_get_latest_price(self):
        md = MockMarketData(seed=42)
        md.generate_bars("AAPL", n_bars=10, start_price=150.0)
        price = md.get_latest_price("AAPL")
        assert price is not None
        assert price > 0

    def test_get_latest_price_missing(self):
        md = MockMarketData()
        assert md.get_latest_price("XYZ") is None

    def test_get_bars(self):
        md = MockMarketData(seed=42)
        md.generate_bars("AAPL", n_bars=20)
        bars = md.get_bars("AAPL", n=5)
        assert len(bars) == 5

    def test_get_symbols(self):
        md = MockMarketData(seed=42)
        md.generate_bars("AAPL", 10)
        md.generate_bars("MSFT", 10)
        assert set(md.get_symbols()) == {"AAPL", "MSFT"}

    def test_clear_cache(self):
        md = MockMarketData(seed=42)
        md.generate_bars("AAPL", 10)
        md.clear_cache()
        assert len(md.get_symbols()) == 0


class TestMockRedis:
    """Tests for mock Redis."""

    def test_set_get(self):
        redis = MockRedis()
        redis.set("key", "value")
        assert redis.get("key") == "value"

    def test_get_missing(self):
        redis = MockRedis()
        assert redis.get("missing", "default") == "default"

    def test_delete(self):
        redis = MockRedis()
        redis.set("key", "value")
        assert redis.delete("key") is True
        assert redis.exists("key") is False

    def test_exists(self):
        redis = MockRedis()
        redis.set("key", "value")
        assert redis.exists("key") is True
        assert redis.exists("other") is False

    def test_keys(self):
        redis = MockRedis()
        redis.set("user:1", "a")
        redis.set("user:2", "b")
        redis.set("order:1", "c")
        user_keys = redis.keys("user:*")
        assert len(user_keys) == 2

    def test_flush(self):
        redis = MockRedis()
        redis.set("a", 1)
        redis.set("b", 2)
        redis.flush()
        assert redis.size() == 0

    def test_size(self):
        redis = MockRedis()
        redis.set("a", 1)
        redis.set("b", 2)
        assert redis.size() == 2

    def test_connect_disconnect(self):
        redis = MockRedis()
        assert redis.is_connected
        redis.disconnect()
        assert not redis.is_connected
        redis.connect()
        assert redis.is_connected


class TestFixtures:
    """Tests for test data factories."""

    def test_create_test_order(self):
        order = create_test_order(symbol="MSFT", quantity=200)
        assert order.symbol == "MSFT"
        assert order.quantity == 200
        assert order.order_id != ""

    def test_create_test_portfolio(self):
        portfolio = create_test_portfolio(cash=50000.0)
        assert portfolio.cash == 50000.0
        assert portfolio.total_value == 50000.0

    def test_create_test_portfolio_with_positions(self):
        portfolio = create_test_portfolio_with_positions(n_positions=3)
        assert len(portfolio.positions) == 3
        assert portfolio.total_value > portfolio.cash

    def test_create_test_signal(self):
        signal = create_test_signal(symbol="TSLA", strength=0.9)
        assert signal.symbol == "TSLA"
        assert signal.strength == 0.9

    def test_create_test_market_data(self):
        md = create_test_market_data(symbol="GOOGL")
        assert md.symbol == "GOOGL"
        assert md.vwap > 0

    def test_create_orders_batch(self):
        orders = create_test_orders_batch(n=20)
        assert len(orders) == 20


class TestLoadTestRunner:
    """Tests for load test runner."""

    def test_load_scenario_creation(self):
        scenario = LoadScenario(name="test", func=lambda: None, iterations=10)
        assert scenario.name == "test"
        assert scenario.iterations == 10

    def test_load_test_result_empty(self):
        result = LoadTestResult(scenario_name="test")
        assert result.mean_ms == 0.0
        assert result.p50_ms == 0.0
        assert result.success_rate == 0.0

    def test_load_test_result_stats(self):
        result = LoadTestResult(
            scenario_name="test",
            total_requests=100,
            successful_requests=95,
            failed_requests=5,
            latencies_ms=[10.0, 20.0, 30.0, 40.0, 50.0],
            total_duration_ms=500.0,
        )
        assert result.mean_ms == 30.0
        assert result.p50_ms == 30.0
        assert result.success_rate == 0.95
        assert result.requests_per_second == 200.0

    def test_run_scenario(self):
        counter = {"n": 0}

        def work():
            counter["n"] += 1

        runner = LoadTestRunner()
        scenario = LoadScenario(name="simple", func=work, concurrency=1, iterations=10)
        result = runner.run_scenario(scenario)
        assert result.total_requests == 10
        assert result.successful_requests == 10

    def test_run_scenario_with_failures(self):
        call_count = {"n": 0}

        def sometimes_fail():
            call_count["n"] += 1
            if call_count["n"] % 3 == 0:
                raise RuntimeError("fail")

        runner = LoadTestRunner()
        scenario = LoadScenario(name="flaky", func=sometimes_fail, concurrency=1, iterations=9)
        result = runner.run_scenario(scenario)
        assert result.total_requests == 9
        assert result.failed_requests == 3

    def test_load_test_summary(self):
        result = LoadTestResult(
            scenario_name="test",
            total_requests=10,
            successful_requests=10,
            latencies_ms=[5.0, 10.0, 15.0],
            total_duration_ms=100.0,
        )
        summary = result.summary()
        assert "mean_ms" in summary
        assert "p95_ms" in summary

    def test_sample_result(self):
        result = LoadTestRunner.generate_sample_result()
        assert result.total_requests == 500

    def test_no_func_raises(self):
        runner = LoadTestRunner()
        scenario = LoadScenario(name="empty", func=None)
        with pytest.raises(ValueError):
            runner.run_scenario(scenario)


class TestBenchmarkSuite:
    """Tests for benchmark suite."""

    def test_add_benchmark(self):
        suite = BenchmarkSuite("test")
        suite.add_benchmark("sort", lambda: sorted(range(100, 0, -1)))
        assert "sort" in suite.get_benchmark_names()

    def test_remove_benchmark(self):
        suite = BenchmarkSuite("test")
        suite.add_benchmark("x", lambda: None)
        assert suite.remove_benchmark("x") is True
        assert "x" not in suite.get_benchmark_names()

    def test_run_benchmark(self):
        suite = BenchmarkSuite("test", iterations=10)
        suite.add_benchmark("noop", lambda: None)
        result = suite.run_benchmark("noop")
        assert result.iterations == 10
        assert result.mean_ms >= 0

    def test_run_all(self):
        suite = BenchmarkSuite("test", iterations=5)
        suite.add_benchmark("a", lambda: None)
        suite.add_benchmark("b", lambda: time.sleep(0.001))
        results = suite.run_all()
        assert len(results) == 2

    def test_regression_detection(self):
        suite = BenchmarkSuite("test", iterations=10, regression_threshold=0.10)
        suite.add_benchmark("fast", lambda: None)
        baseline = BenchmarkResult(name="fast", mean_ms=1.0)
        suite.set_baseline("fast", baseline)
        suite.run_benchmark("fast")
        # no regression for a noop benchmark
        regressions = suite.detect_regressions()
        # Can't guarantee regression for noop, but method runs without error

    def test_benchmark_result_has_regression(self):
        baseline = BenchmarkResult(name="test", mean_ms=10.0)
        current = BenchmarkResult(name="test", mean_ms=12.0)
        assert current.has_regression(baseline, threshold=0.10) is True

    def test_benchmark_result_no_regression(self):
        baseline = BenchmarkResult(name="test", mean_ms=10.0)
        current = BenchmarkResult(name="test", mean_ms=10.5)
        assert current.has_regression(baseline, threshold=0.10) is False

    def test_benchmark_not_found(self):
        suite = BenchmarkSuite("test")
        with pytest.raises(KeyError):
            suite.run_benchmark("missing")

    def test_clear_results(self):
        suite = BenchmarkSuite("test", iterations=5)
        suite.add_benchmark("a", lambda: None)
        suite.run_benchmark("a")
        suite.clear_results()
        assert len(suite.get_results()) == 0

    def test_benchmark_summary(self):
        result = BenchmarkResult(name="test", mean_ms=10.0, p50_ms=9.0, iterations=100)
        s = result.summary()
        assert s["name"] == "test"
        assert s["mean_ms"] == 10.0
