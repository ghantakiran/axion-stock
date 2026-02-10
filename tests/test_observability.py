"""Tests for PRD-103: Observability & Metrics Export."""

import asyncio
import time
from datetime import datetime

import pytest

from src.observability.config import (
    MetricType,
    ExportFormat,
    HistogramBuckets,
    MetricsConfig,
)
from src.observability.registry import (
    MetricMeta,
    Counter,
    Gauge,
    Histogram,
    MetricsRegistry,
)
from src.observability.trading import TradingMetrics
from src.observability.system import SystemMetrics
from src.observability.exporter import PrometheusExporter
from src.observability.decorators import track_latency, count_calls, track_errors


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def reset_registry():
    """Reset the singleton registry before each test."""
    MetricsRegistry.destroy()
    registry = MetricsRegistry()
    registry.reset()
    yield
    MetricsRegistry.destroy()


# ── Config Tests ─────────────────────────────────────────────────────


class TestObservabilityEnums:
    def test_metric_types(self):
        assert len(MetricType) == 3
        assert MetricType.COUNTER.value == "counter"
        assert MetricType.GAUGE.value == "gauge"
        assert MetricType.HISTOGRAM.value == "histogram"

    def test_export_formats(self):
        assert len(ExportFormat) == 2
        assert ExportFormat.PROMETHEUS.value == "prometheus"
        assert ExportFormat.JSON.value == "json"

    def test_metric_type_from_value(self):
        assert MetricType("counter") == MetricType.COUNTER


class TestHistogramBuckets:
    def test_default_latency_buckets(self):
        b = HistogramBuckets()
        assert len(b.latency) == 11
        assert b.latency[0] == 0.005
        assert b.latency[-1] == 10.0

    def test_default_order_latency_buckets(self):
        b = HistogramBuckets()
        assert len(b.order_latency) == 9
        assert b.order_latency[0] == 0.01
        assert b.order_latency[-1] == 10.0

    def test_default_slippage_buckets(self):
        b = HistogramBuckets()
        assert len(b.slippage) == 8
        assert b.slippage[0] == 0.5

    def test_default_duration_buckets(self):
        b = HistogramBuckets()
        assert len(b.duration) == 8

    def test_custom_buckets(self):
        b = HistogramBuckets(latency=[0.1, 0.5, 1.0])
        assert b.latency == [0.1, 0.5, 1.0]


class TestMetricsConfig:
    def test_defaults(self):
        cfg = MetricsConfig()
        assert cfg.export_format == ExportFormat.PROMETHEUS
        assert cfg.endpoint_path == "/metrics"
        assert cfg.prefix == "axion"
        assert cfg.include_timestamp is True
        assert cfg.collection_interval_seconds == 15.0
        assert cfg.retention_minutes == 60

    def test_prefixed(self):
        cfg = MetricsConfig(prefix="test")
        assert cfg.prefixed("my_metric") == "test_my_metric"

    def test_prefixed_empty(self):
        cfg = MetricsConfig(prefix="")
        assert cfg.prefixed("my_metric") == "my_metric"

    def test_feature_flags(self):
        cfg = MetricsConfig()
        assert cfg.enable_trading_metrics is True
        assert cfg.enable_system_metrics is True
        assert cfg.enable_runtime_metrics is True

    def test_custom_config(self):
        cfg = MetricsConfig(
            prefix="custom",
            collection_interval_seconds=30.0,
            retention_minutes=120,
        )
        assert cfg.prefix == "custom"
        assert cfg.collection_interval_seconds == 30.0
        assert cfg.retention_minutes == 120

    def test_global_labels(self):
        cfg = MetricsConfig(global_labels={"env": "prod"})
        assert cfg.global_labels == {"env": "prod"}

    def test_custom_export_format(self):
        cfg = MetricsConfig(export_format=ExportFormat.JSON)
        assert cfg.export_format == ExportFormat.JSON

    def test_default_buckets_instance(self):
        cfg = MetricsConfig()
        assert isinstance(cfg.buckets, HistogramBuckets)


# ── Counter Tests ────────────────────────────────────────────────────


class TestCounter:
    def test_initial_value(self):
        c = Counter(name="test_counter")
        assert c.value == 0.0

    def test_increment(self):
        c = Counter(name="test_counter")
        c.increment()
        assert c.value == 1.0

    def test_increment_by_amount(self):
        c = Counter(name="test_counter")
        c.increment(5.0)
        assert c.value == 5.0

    def test_multiple_increments(self):
        c = Counter(name="test_counter")
        c.increment(3.0)
        c.increment(7.0)
        assert c.value == 10.0

    def test_negative_increment_raises(self):
        c = Counter(name="test_counter")
        with pytest.raises(ValueError):
            c.increment(-1.0)

    def test_labels(self):
        c = Counter(name="test_counter", label_names=("method", "status"))
        c.increment(labels={"method": "GET", "status": "200"})
        c.increment(labels={"method": "POST", "status": "201"})
        assert c.get(labels={"method": "GET", "status": "200"}) == 1.0
        assert c.get(labels={"method": "POST", "status": "201"}) == 1.0

    def test_get_all(self):
        c = Counter(name="test_counter", label_names=("x",))
        c.increment(labels={"x": "a"})
        c.increment(labels={"x": "b"})
        all_vals = c.get_all()
        assert len(all_vals) == 2

    def test_reset(self):
        c = Counter(name="test_counter")
        c.increment(10)
        c.reset()
        assert c.value == 0.0

    def test_get_unlabeled_default(self):
        c = Counter(name="test_counter", label_names=("x",))
        assert c.get(labels={"x": "missing"}) == 0.0


# ── Gauge Tests ──────────────────────────────────────────────────────


class TestGauge:
    def test_initial_value(self):
        g = Gauge(name="test_gauge")
        assert g.value == 0.0

    def test_set(self):
        g = Gauge(name="test_gauge")
        g.set(42.0)
        assert g.value == 42.0

    def test_increment(self):
        g = Gauge(name="test_gauge")
        g.set(10.0)
        g.increment(5.0)
        assert g.value == 15.0

    def test_decrement(self):
        g = Gauge(name="test_gauge")
        g.set(10.0)
        g.decrement(3.0)
        assert g.value == 7.0

    def test_negative_value(self):
        g = Gauge(name="test_gauge")
        g.decrement(5.0)
        assert g.value == -5.0

    def test_labels(self):
        g = Gauge(name="test_gauge", label_names=("source",))
        g.set(1.5, labels={"source": "polygon"})
        g.set(12.0, labels={"source": "yahoo"})
        assert g.get(labels={"source": "polygon"}) == 1.5
        assert g.get(labels={"source": "yahoo"}) == 12.0

    def test_get_all(self):
        g = Gauge(name="test_gauge", label_names=("x",))
        g.set(1.0, labels={"x": "a"})
        g.set(2.0, labels={"x": "b"})
        assert len(g.get_all()) == 2

    def test_reset(self):
        g = Gauge(name="test_gauge")
        g.set(100.0)
        g.reset()
        assert g.value == 0.0

    def test_default_increment(self):
        g = Gauge(name="test_gauge")
        g.increment()
        assert g.value == 1.0

    def test_default_decrement(self):
        g = Gauge(name="test_gauge")
        g.set(5.0)
        g.decrement()
        assert g.value == 4.0


# ── Histogram Tests ──────────────────────────────────────────────────


class TestHistogram:
    def test_initial_state(self):
        h = Histogram(name="test_hist", buckets=[1.0, 5.0, 10.0])
        assert h.count == 0
        assert h.sum == 0.0

    def test_observe(self):
        h = Histogram(name="test_hist", buckets=[1.0, 5.0, 10.0])
        h.observe(0.5)
        assert h.count == 1
        assert h.sum == 0.5

    def test_multiple_observations(self):
        h = Histogram(name="test_hist", buckets=[1.0, 5.0, 10.0])
        h.observe(0.5)
        h.observe(2.0)
        h.observe(7.0)
        assert h.count == 3
        assert h.sum == pytest.approx(9.5)

    def test_bucket_counts(self):
        h = Histogram(name="test_hist", buckets=[1.0, 5.0, 10.0])
        h.observe(0.5)  # <= 1.0, 5.0, 10.0
        h.observe(2.0)  # <= 5.0, 10.0
        h.observe(7.0)  # <= 10.0
        h.observe(15.0)  # > 10.0 (only +Inf)
        buckets = h.get_buckets()
        # Cumulative counts (Prometheus convention)
        assert buckets[0] == (1.0, 1)   # 0.5 fits here
        assert buckets[1] == (5.0, 2)   # 0.5, 2.0 fit here
        assert buckets[2] == (10.0, 3)  # 0.5, 2.0, 7.0 fit here
        assert buckets[3] == (float("inf"), 4)  # all 4 in +Inf

    def test_quantile(self):
        h = Histogram(name="test_hist", buckets=[1.0, 5.0, 10.0])
        for v in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]:
            h.observe(float(v))
        p50 = h.quantile(0.5)
        assert 4.0 <= p50 <= 6.0
        p90 = h.quantile(0.9)
        assert p90 >= 8.0

    def test_labels(self):
        h = Histogram(name="test_hist", label_names=("op",), buckets=[1.0])
        h.observe(0.5, labels={"op": "select"})
        h.observe(0.8, labels={"op": "insert"})
        assert h.get_count(labels={"op": "select"}) == 1
        assert h.get_count(labels={"op": "insert"}) == 1

    def test_get_sum_with_labels(self):
        h = Histogram(name="test_hist", label_names=("op",), buckets=[1.0])
        h.observe(0.5, labels={"op": "select"})
        h.observe(0.3, labels={"op": "select"})
        assert h.get_sum(labels={"op": "select"}) == pytest.approx(0.8)

    def test_reset(self):
        h = Histogram(name="test_hist", buckets=[1.0])
        h.observe(0.5)
        h.reset()
        assert h.count == 0

    def test_default_buckets(self):
        h = Histogram(name="test_hist")
        assert len(h.bucket_bounds) == 11

    def test_sorted_buckets(self):
        h = Histogram(name="test_hist", buckets=[10.0, 1.0, 5.0])
        assert h.bucket_bounds == [1.0, 5.0, 10.0]

    def test_get_all(self):
        h = Histogram(name="test_hist", label_names=("op",), buckets=[1.0])
        h.observe(0.5, labels={"op": "a"})
        h.observe(0.5, labels={"op": "b"})
        assert len(h.get_all()) == 2


# ── Registry Tests ───────────────────────────────────────────────────


class TestMetricsRegistry:
    def test_singleton(self):
        r1 = MetricsRegistry()
        r2 = MetricsRegistry()
        assert r1 is r2

    def test_register_counter(self):
        r = MetricsRegistry()
        c = r.counter("test_counter", "A test counter")
        assert isinstance(c, Counter)
        assert c.name == "test_counter"

    def test_register_gauge(self):
        r = MetricsRegistry()
        g = r.gauge("test_gauge", "A test gauge")
        assert isinstance(g, Gauge)

    def test_register_histogram(self):
        r = MetricsRegistry()
        h = r.histogram("test_hist", "A test histogram", buckets=[1.0, 5.0])
        assert isinstance(h, Histogram)

    def test_duplicate_registration_returns_same(self):
        r = MetricsRegistry()
        c1 = r.counter("dup_counter", "first")
        c2 = r.counter("dup_counter", "second")
        assert c1 is c2

    def test_type_mismatch_raises(self):
        r = MetricsRegistry()
        r.counter("conflict", "A counter")
        with pytest.raises(TypeError):
            r.gauge("conflict", "Not a gauge")

    def test_get_metric(self):
        r = MetricsRegistry()
        c = r.counter("lookup_test")
        assert r.get_metric("lookup_test") is c
        assert r.get_metric("nonexistent") is None

    def test_get_meta(self):
        r = MetricsRegistry()
        r.counter("meta_test", "desc", label_names=("a", "b"))
        meta = r.get_meta("meta_test")
        assert meta is not None
        assert meta.description == "desc"
        assert meta.metric_type == MetricType.COUNTER
        assert meta.label_names == ("a", "b")

    def test_get_all_metrics(self):
        r = MetricsRegistry()
        r.counter("c1")
        r.gauge("g1")
        all_m = r.get_all_metrics()
        assert "c1" in all_m
        assert "g1" in all_m

    def test_reset(self):
        r = MetricsRegistry()
        r.counter("will_be_cleared")
        r.reset()
        assert r.get_metric("will_be_cleared") is None
        assert len(r.get_all_metrics()) == 0

    def test_destroy(self):
        r1 = MetricsRegistry()
        r1.counter("before_destroy")
        MetricsRegistry.destroy()
        r2 = MetricsRegistry()
        assert r2.get_metric("before_destroy") is None


# ── Trading Metrics Tests ────────────────────────────────────────────


class TestTradingMetrics:
    def test_initialization(self):
        tm = TradingMetrics()
        assert tm.orders_total is not None
        assert tm.order_latency_seconds is not None
        assert tm.positions_active is not None
        assert tm.portfolio_value_dollars is not None
        assert tm.signals_generated_total is not None
        assert tm.slippage_basis_points is not None

    def test_record_order(self):
        tm = TradingMetrics()
        tm.record_order(status="filled", broker="alpaca", side="buy", latency_seconds=0.1)
        assert tm.orders_total.get({"status": "filled", "broker": "alpaca", "side": "buy"}) == 1.0
        assert tm.order_latency_seconds.count == 1

    def test_record_order_no_latency(self):
        tm = TradingMetrics()
        tm.record_order(status="rejected", broker="ib", side="sell")
        assert tm.orders_total.get({"status": "rejected", "broker": "ib", "side": "sell"}) == 1.0
        assert tm.order_latency_seconds.count == 0

    def test_update_positions(self):
        tm = TradingMetrics()
        tm.update_positions(active_count=15, portfolio_value=500_000.0)
        assert tm.positions_active.value == 15.0
        assert tm.portfolio_value_dollars.value == 500_000.0

    def test_record_signal(self):
        tm = TradingMetrics()
        tm.record_signal(strategy="momentum", direction="long")
        tm.record_signal(strategy="momentum", direction="long")
        assert tm.signals_generated_total.get({"strategy": "momentum", "direction": "long"}) == 2.0

    def test_record_slippage(self):
        tm = TradingMetrics()
        tm.record_slippage(2.5)
        tm.record_slippage(1.0)
        assert tm.slippage_basis_points.count == 2
        assert tm.slippage_basis_points.sum == pytest.approx(3.5)

    def test_order_latency_buckets(self):
        tm = TradingMetrics()
        expected = [0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
        assert tm.order_latency_seconds.bucket_bounds == expected

    def test_generate_sample_data(self):
        tm = TradingMetrics.generate_sample_data()
        # Check that orders were recorded
        filled_buy = tm.orders_total.get({"status": "filled", "broker": "alpaca", "side": "buy"})
        assert filled_buy == 150.0
        assert tm.positions_active.value == 23.0
        assert tm.portfolio_value_dollars.value == 1_250_000.0

    def test_metrics_registered_in_registry(self):
        tm = TradingMetrics()
        registry = MetricsRegistry()
        assert registry.get_metric("axion_orders_total") is not None
        assert registry.get_metric("axion_positions_active") is not None

    def test_custom_config_prefix(self):
        cfg = MetricsConfig(prefix="myapp")
        tm = TradingMetrics(config=cfg)
        registry = MetricsRegistry()
        assert registry.get_metric("myapp_orders_total") is not None


# ── System Metrics Tests ─────────────────────────────────────────────


class TestSystemMetrics:
    def test_initialization(self):
        sm = SystemMetrics()
        assert sm.api_requests_total is not None
        assert sm.api_request_duration_seconds is not None
        assert sm.db_query_duration_seconds is not None
        assert sm.cache_hits_total is not None
        assert sm.cache_misses_total is not None
        assert sm.websocket_connections_active is not None
        assert sm.data_pipeline_lag_seconds is not None

    def test_record_api_request(self):
        sm = SystemMetrics()
        sm.record_api_request("GET", "/api/v1/test", "200", duration_seconds=0.05)
        val = sm.api_requests_total.get({"method": "GET", "path": "/api/v1/test", "status_code": "200"})
        assert val == 1.0
        assert sm.api_request_duration_seconds.count == 1

    def test_record_api_request_no_duration(self):
        sm = SystemMetrics()
        sm.record_api_request("POST", "/api/v1/orders", "201")
        val = sm.api_requests_total.get({"method": "POST", "path": "/api/v1/orders", "status_code": "201"})
        assert val == 1.0
        assert sm.api_request_duration_seconds.count == 0

    def test_record_db_query(self):
        sm = SystemMetrics()
        sm.record_db_query("select", 0.005)
        assert sm.db_query_duration_seconds.get_count(labels={"operation": "select"}) == 1
        assert sm.db_query_duration_seconds.get_sum(labels={"operation": "select"}) == pytest.approx(0.005)

    def test_cache_operations(self):
        sm = SystemMetrics()
        sm.record_cache_hit()
        sm.record_cache_hit()
        sm.record_cache_miss()
        assert sm.cache_hits_total.value == 2.0
        assert sm.cache_misses_total.value == 1.0

    def test_cache_hit_rate(self):
        sm = SystemMetrics()
        for _ in range(8):
            sm.record_cache_hit()
        for _ in range(2):
            sm.record_cache_miss()
        assert sm.cache_hit_rate() == pytest.approx(0.8)

    def test_cache_hit_rate_zero(self):
        sm = SystemMetrics()
        assert sm.cache_hit_rate() == 0.0

    def test_websocket_connections(self):
        sm = SystemMetrics()
        sm.update_websocket_connections(25)
        assert sm.websocket_connections_active.value == 25.0

    def test_pipeline_lag(self):
        sm = SystemMetrics()
        sm.update_pipeline_lag("polygon", 0.3)
        sm.update_pipeline_lag("yahoo", 5.0)
        assert sm.data_pipeline_lag_seconds.get(labels={"source": "polygon"}) == 0.3
        assert sm.data_pipeline_lag_seconds.get(labels={"source": "yahoo"}) == 5.0

    def test_generate_sample_data(self):
        sm = SystemMetrics.generate_sample_data()
        assert sm.cache_hits_total.value == 800.0
        assert sm.cache_misses_total.value == 200.0
        assert sm.websocket_connections_active.value == 42.0

    def test_metrics_registered_in_registry(self):
        sm = SystemMetrics()
        registry = MetricsRegistry()
        assert registry.get_metric("axion_api_requests_total") is not None
        assert registry.get_metric("axion_cache_hits_total") is not None
        assert registry.get_metric("axion_db_query_duration_seconds") is not None


# ── Prometheus Exporter Tests ────────────────────────────────────────


class TestPrometheusExporter:
    def test_empty_output(self):
        exporter = PrometheusExporter()
        output = exporter.expose_metrics()
        assert output == ""

    def test_counter_output(self):
        registry = MetricsRegistry()
        c = registry.counter("test_requests_total", "Total requests")
        c.increment(5.0)
        exporter = PrometheusExporter(config=MetricsConfig(include_timestamp=False))
        output = exporter.expose_metrics()
        assert "# HELP test_requests_total Total requests" in output
        assert "# TYPE test_requests_total counter" in output
        assert "test_requests_total 5" in output

    def test_gauge_output(self):
        registry = MetricsRegistry()
        g = registry.gauge("test_temperature", "Current temperature")
        g.set(23.5)
        exporter = PrometheusExporter(config=MetricsConfig(include_timestamp=False))
        output = exporter.expose_metrics()
        assert "# HELP test_temperature Current temperature" in output
        assert "# TYPE test_temperature gauge" in output
        assert "test_temperature 23.5" in output

    def test_histogram_output(self):
        registry = MetricsRegistry()
        h = registry.histogram("test_duration", "Duration", buckets=[0.1, 0.5, 1.0])
        h.observe(0.05)
        h.observe(0.3)
        exporter = PrometheusExporter(config=MetricsConfig(include_timestamp=False))
        output = exporter.expose_metrics()
        assert "# TYPE test_duration histogram" in output
        assert 'test_duration_bucket{le="0.1"}' in output
        assert 'test_duration_bucket{le="0.5"}' in output
        assert 'test_duration_bucket{le="1"}' in output
        assert 'test_duration_bucket{le="+Inf"}' in output
        assert "test_duration_count 2" in output
        assert "test_duration_sum 0.35" in output

    def test_labeled_counter_output(self):
        registry = MetricsRegistry()
        c = registry.counter("http_total", "HTTP requests", label_names=("method",))
        c.increment(labels={"method": "GET"})
        c.increment(labels={"method": "POST"})
        exporter = PrometheusExporter(config=MetricsConfig(include_timestamp=False))
        output = exporter.expose_metrics()
        assert 'http_total{method="GET"} 1' in output
        assert 'http_total{method="POST"} 1' in output

    def test_timestamp_included(self):
        registry = MetricsRegistry()
        registry.counter("ts_test", "timestamp test")
        exporter = PrometheusExporter(config=MetricsConfig(include_timestamp=True))
        output = exporter.expose_metrics()
        # Lines should have a timestamp (integer) at the end
        for line in output.split("\n"):
            if line and not line.startswith("#") and line.strip():
                parts = line.split()
                assert len(parts) >= 3  # name value timestamp

    def test_timestamp_excluded(self):
        registry = MetricsRegistry()
        c = registry.counter("no_ts_test", "no timestamp")
        c.increment()
        exporter = PrometheusExporter(config=MetricsConfig(include_timestamp=False))
        output = exporter.expose_metrics()
        for line in output.split("\n"):
            if line and not line.startswith("#") and line.strip():
                parts = line.split()
                assert len(parts) == 2  # name value only

    def test_empty_counter_output(self):
        registry = MetricsRegistry()
        registry.counter("empty_counter", "empty")
        exporter = PrometheusExporter(config=MetricsConfig(include_timestamp=False))
        output = exporter.expose_metrics()
        assert "empty_counter 0" in output

    def test_format_value_integers(self):
        assert PrometheusExporter._format_value(5.0) == "5"
        assert PrometheusExporter._format_value(0.0) == "0"

    def test_format_value_floats(self):
        assert PrometheusExporter._format_value(0.35) == "0.35"
        assert PrometheusExporter._format_value(float("inf")) == "+Inf"

    def test_full_trading_export(self):
        TradingMetrics.generate_sample_data()
        exporter = PrometheusExporter(config=MetricsConfig(include_timestamp=False))
        output = exporter.expose_metrics()
        assert "axion_orders_total" in output
        assert "axion_positions_active" in output
        assert "axion_slippage_basis_points" in output


# ── Decorator Tests ──────────────────────────────────────────────────


class TestTrackLatency:
    def test_sync_function(self):
        @track_latency("latency_sync_test")
        def slow_func():
            time.sleep(0.01)
            return 42

        result = slow_func()
        assert result == 42
        registry = MetricsRegistry()
        h = registry.get_metric("latency_sync_test")
        assert h is not None
        assert h.count == 1
        assert h.sum >= 0.01

    def test_async_function(self):
        @track_latency("latency_async_test")
        async def async_func():
            await asyncio.sleep(0.01)
            return "ok"

        result = asyncio.get_event_loop().run_until_complete(async_func())
        assert result == "ok"
        registry = MetricsRegistry()
        h = registry.get_metric("latency_async_test")
        assert h is not None
        assert h.count == 1

    def test_preserves_name(self):
        @track_latency("name_test")
        def my_function():
            pass

        assert my_function.__name__ == "my_function"

    def test_multiple_calls(self):
        @track_latency("multi_latency_test")
        def func():
            return True

        func()
        func()
        func()
        registry = MetricsRegistry()
        h = registry.get_metric("multi_latency_test")
        assert h.count == 3

    def test_exception_still_records(self):
        @track_latency("error_latency_test")
        def failing_func():
            raise RuntimeError("oops")

        with pytest.raises(RuntimeError):
            failing_func()
        registry = MetricsRegistry()
        h = registry.get_metric("error_latency_test")
        assert h.count == 1

    def test_custom_buckets(self):
        @track_latency("custom_bucket_test", buckets=[0.001, 0.01, 0.1])
        def func():
            pass

        func()
        registry = MetricsRegistry()
        h = registry.get_metric("custom_bucket_test")
        assert h.bucket_bounds == [0.001, 0.01, 0.1]

    def test_return_value_preserved(self):
        @track_latency("return_test")
        def compute():
            return {"a": 1, "b": [2, 3]}

        result = compute()
        assert result == {"a": 1, "b": [2, 3]}

    def test_args_forwarded(self):
        @track_latency("args_test")
        def add(a, b):
            return a + b

        assert add(3, 4) == 7


class TestCountCalls:
    def test_sync_function(self):
        @count_calls("calls_sync_test")
        def func():
            return "hello"

        func()
        func()
        registry = MetricsRegistry()
        c = registry.get_metric("calls_sync_test")
        assert c.value == 2.0

    def test_async_function(self):
        @count_calls("calls_async_test")
        async def async_func():
            return "async"

        asyncio.get_event_loop().run_until_complete(async_func())
        registry = MetricsRegistry()
        c = registry.get_metric("calls_async_test")
        assert c.value == 1.0

    def test_preserves_name(self):
        @count_calls("name_test_calls")
        def named_func():
            pass

        assert named_func.__name__ == "named_func"

    def test_exception_still_counts(self):
        @count_calls("error_calls_test")
        def failing():
            raise ValueError("bad")

        with pytest.raises(ValueError):
            failing()
        registry = MetricsRegistry()
        c = registry.get_metric("error_calls_test")
        # count_calls increments before executing, so it counts
        assert c.value == 1.0

    def test_return_value_preserved(self):
        @count_calls("return_calls_test")
        def compute():
            return 99

        assert compute() == 99

    def test_many_calls(self):
        @count_calls("many_calls_test")
        def noop():
            pass

        for _ in range(100):
            noop()
        registry = MetricsRegistry()
        c = registry.get_metric("many_calls_test")
        assert c.value == 100.0

    def test_kwargs_forwarded(self):
        @count_calls("kwargs_calls_test")
        def greet(name="World"):
            return f"Hello, {name}!"

        assert greet(name="Test") == "Hello, Test!"

    def test_counter_is_registered(self):
        @count_calls("registered_calls_test")
        def func():
            pass

        registry = MetricsRegistry()
        meta = registry.get_meta("registered_calls_test")
        assert meta is not None
        assert meta.metric_type == MetricType.COUNTER


class TestTrackErrors:
    def test_no_error(self):
        @track_errors("errors_no_error_test")
        def good_func():
            return "ok"

        result = good_func()
        assert result == "ok"
        registry = MetricsRegistry()
        c = registry.get_metric("errors_no_error_test")
        assert c.value == 0.0

    def test_runtime_error(self):
        @track_errors("errors_runtime_test")
        def bad_func():
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            bad_func()
        registry = MetricsRegistry()
        c = registry.get_metric("errors_runtime_test")
        assert c.get(labels={"exception_type": "RuntimeError"}) == 1.0

    def test_value_error(self):
        @track_errors("errors_value_test")
        def bad_func():
            raise ValueError("invalid")

        with pytest.raises(ValueError):
            bad_func()
        registry = MetricsRegistry()
        c = registry.get_metric("errors_value_test")
        assert c.get(labels={"exception_type": "ValueError"}) == 1.0

    def test_multiple_error_types(self):
        call_count = 0

        @track_errors("errors_multi_test")
        def alternating_func():
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:
                raise TypeError("type")
            raise KeyError("key")

        for _ in range(4):
            with pytest.raises(Exception):
                alternating_func()

        registry = MetricsRegistry()
        c = registry.get_metric("errors_multi_test")
        assert c.get(labels={"exception_type": "KeyError"}) == 2.0
        assert c.get(labels={"exception_type": "TypeError"}) == 2.0

    def test_async_function(self):
        @track_errors("errors_async_test")
        async def async_bad():
            raise IOError("io")

        with pytest.raises(IOError):
            asyncio.get_event_loop().run_until_complete(async_bad())

        registry = MetricsRegistry()
        c = registry.get_metric("errors_async_test")
        assert c.get(labels={"exception_type": "OSError"}) == 1.0

    def test_preserves_name(self):
        @track_errors("errors_name_test")
        def my_error_func():
            pass

        assert my_error_func.__name__ == "my_error_func"

    def test_re_raises_exception(self):
        @track_errors("errors_reraise_test")
        def fails():
            raise AttributeError("missing")

        with pytest.raises(AttributeError, match="missing"):
            fails()

    def test_return_value_on_success(self):
        @track_errors("errors_return_test")
        def success():
            return [1, 2, 3]

        assert success() == [1, 2, 3]

    def test_error_labels_in_meta(self):
        @track_errors("errors_meta_test")
        def func():
            pass

        registry = MetricsRegistry()
        meta = registry.get_meta("errors_meta_test")
        assert meta is not None
        assert "exception_type" in meta.label_names


# ── Integration Tests ────────────────────────────────────────────────


class TestObservabilityIntegration:
    def test_full_pipeline(self):
        """End-to-end: register metrics, record data, export."""
        tm = TradingMetrics()
        sm = SystemMetrics()

        # Record some data
        tm.record_order(status="filled", broker="alpaca", side="buy", latency_seconds=0.1)
        sm.record_api_request("GET", "/api/v1/quotes", "200", duration_seconds=0.05)
        sm.record_cache_hit()

        # Export
        exporter = PrometheusExporter(config=MetricsConfig(include_timestamp=False))
        output = exporter.expose_metrics()

        # Verify structure
        assert "# HELP" in output
        assert "# TYPE" in output
        assert "axion_orders_total" in output
        assert "axion_api_requests_total" in output
        assert "axion_cache_hits_total" in output

    def test_decorators_with_trading_metrics(self):
        """Decorators + domain metrics coexist in same registry."""
        tm = TradingMetrics()

        @count_calls("integration_calls")
        def process_order():
            tm.record_order(status="filled", broker="alpaca", side="buy")

        process_order()
        process_order()

        registry = MetricsRegistry()
        assert registry.get_metric("integration_calls").value == 2.0
        assert tm.orders_total.get({"status": "filled", "broker": "alpaca", "side": "buy"}) == 2.0

    def test_concurrent_updates(self):
        """Thread-safe metric updates."""
        import threading

        c = Counter(name="concurrent_test")
        threads = []
        for _ in range(10):
            t = threading.Thread(target=lambda: [c.increment() for _ in range(100)])
            threads.append(t)
            t.start()
        for t in threads:
            t.join()
        assert c.value == 1000.0

    def test_sample_data_export(self):
        """Generate sample data and verify exportable."""
        TradingMetrics.generate_sample_data()
        SystemMetrics.generate_sample_data()
        exporter = PrometheusExporter(config=MetricsConfig(include_timestamp=False))
        output = exporter.expose_metrics()
        lines = [l for l in output.split("\n") if l.strip()]
        # Should have many lines with sample data
        assert len(lines) > 20

    def test_registry_shared_across_modules(self):
        """Trading and System metrics share the same registry."""
        tm = TradingMetrics()
        sm = SystemMetrics()
        registry = MetricsRegistry()
        all_m = registry.get_all_metrics()
        assert "axion_orders_total" in all_m
        assert "axion_api_requests_total" in all_m

    def test_multiple_histogram_observations_export(self):
        """Verify histogram with many observations exports correctly."""
        registry = MetricsRegistry()
        h = registry.histogram("latency_test", "Latency", buckets=[0.1, 0.5, 1.0])
        for v in [0.05, 0.2, 0.8, 1.5]:
            h.observe(v)
        exporter = PrometheusExporter(config=MetricsConfig(include_timestamp=False))
        output = exporter.expose_metrics()
        assert "latency_test_count 4" in output
        assert "latency_test_sum 2.55" in output

    def test_empty_histogram_export(self):
        """Empty histogram still exports _count and _sum."""
        registry = MetricsRegistry()
        registry.histogram("empty_hist", "Empty histogram", buckets=[1.0])
        exporter = PrometheusExporter(config=MetricsConfig(include_timestamp=False))
        output = exporter.expose_metrics()
        assert "empty_hist_count 0" in output
        assert "empty_hist_sum 0" in output

    def test_gauge_overwrite(self):
        """Gauge can be set and overwritten."""
        g = Gauge(name="overwrite_test")
        g.set(10)
        g.set(20)
        assert g.value == 20.0
