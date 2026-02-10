"""Tests for PRD-100: System Dashboard."""

from datetime import datetime, timedelta

import pytest

from src.system_dashboard.config import (
    ServiceName,
    ServiceStatus,
    HealthLevel,
    MetricType,
    SystemConfig,
    AlertThresholds,
)
from src.system_dashboard.models import (
    ServiceHealth,
    SystemMetrics,
    DataFreshness,
    HealthSnapshot,
    SystemAlert,
    DependencyStatus,
    SystemSummary,
)
from src.system_dashboard.health import HealthChecker
from src.system_dashboard.metrics import MetricsCollector
from src.system_dashboard.alerts import SystemAlertManager


# ── Config Tests ──────────────────────────────────────────────────────


class TestSystemDashboardEnums:
    def test_service_names(self):
        assert len(ServiceName) == 8
        assert ServiceName.API.value == "api"
        assert ServiceName.DATABASE.value == "database"

    def test_service_status(self):
        assert len(ServiceStatus) == 4
        assert ServiceStatus.HEALTHY.value == "healthy"

    def test_health_levels(self):
        assert len(HealthLevel) == 4

    def test_metric_types(self):
        assert len(MetricType) == 4


class TestSystemDashboardConfigs:
    def test_alert_thresholds(self):
        t = AlertThresholds()
        assert t.cpu_warn == 0.80
        assert t.cpu_crit == 0.95
        assert t.response_time_warn_ms == 500

    def test_system_config(self):
        cfg = SystemConfig()
        assert len(cfg.monitored_services) == 8
        assert len(cfg.data_sources) == 7

    def test_custom_thresholds(self):
        t = AlertThresholds(cpu_warn=0.70, cpu_crit=0.90)
        assert t.cpu_warn == 0.70


# ── Model Tests ───────────────────────────────────────────────────────


class TestServiceHealth:
    def test_creation(self):
        sh = ServiceHealth(service_name="api", status="healthy", response_time_ms=45)
        assert sh.uptime_pct == 100.0

    def test_degraded(self):
        sh = ServiceHealth(service_name="api", status="degraded", error_rate=0.05)
        assert sh.status == "degraded"


class TestHealthSnapshot:
    def test_counts(self):
        services = [
            ServiceHealth("api", "healthy"),
            ServiceHealth("db", "healthy"),
            ServiceHealth("cache", "degraded"),
            ServiceHealth("ml", "down"),
        ]
        snap = HealthSnapshot(services=services)
        assert snap.n_healthy == 2
        assert snap.n_degraded == 1
        assert snap.n_down == 1

    def test_stale_sources(self):
        freshness = [
            DataFreshness("yahoo", is_stale=False, status="fresh"),
            DataFreshness("polygon", is_stale=True, status="stale"),
            DataFreshness("fred", is_stale=True, status="stale"),
        ]
        snap = HealthSnapshot(data_freshness=freshness)
        assert len(snap.stale_sources) == 2
        assert "polygon" in snap.stale_sources


class TestSystemSummary:
    def test_creation(self):
        s = SystemSummary(
            overall_status="healthy",
            total_services=8,
            healthy_services=7,
            degraded_services=1,
            cpu_usage=0.45,
        )
        assert s.healthy_services == 7


class TestSystemAlert:
    def test_creation(self):
        a = SystemAlert(
            alert_id="A1", level="critical",
            service="api", message="High latency",
        )
        assert a.is_active
        assert not a.acknowledged


# ── Health Checker Tests ──────────────────────────────────────────────


class TestHealthChecker:
    def test_check_healthy_service(self):
        checker = HealthChecker()
        health = checker.check_service("api", response_time_ms=50, error_rate=0.001)
        assert health.status == "healthy"

    def test_check_degraded_service(self):
        checker = HealthChecker()
        health = checker.check_service("api", response_time_ms=2500, error_rate=0.06)
        assert health.status == "degraded"

    def test_check_down_service(self):
        checker = HealthChecker()
        health = checker.check_service("api", is_available=False)
        assert health.status == "down"

    def test_check_all_services(self):
        checker = HealthChecker()
        data = {
            "api": {"response_time_ms": 50, "error_rate": 0.001, "is_available": True},
            "database": {"response_time_ms": 10, "error_rate": 0.0, "is_available": True},
        }
        results = checker.check_all_services(data)
        assert len(results) == 8  # All monitored services

    def test_custom_check(self):
        checker = HealthChecker()
        checker.register_check("api", lambda: False)  # Always fails
        data = {"api": {"response_time_ms": 50, "error_rate": 0.0, "is_available": True}}
        results = checker.check_all_services(data)
        api = [r for r in results if r.service_name == "api"][0]
        assert api.status == "degraded"

    def test_data_freshness_fresh(self):
        checker = HealthChecker()
        now = datetime.now()
        updates = {"yahoo_finance": now - timedelta(minutes=5)}
        results = checker.check_data_freshness(updates)
        yahoo = [r for r in results if r.source_name == "yahoo_finance"][0]
        assert not yahoo.is_stale
        assert yahoo.status == "fresh"

    def test_data_freshness_stale(self):
        checker = HealthChecker()
        updates = {"yahoo_finance": datetime.now() - timedelta(hours=2)}
        results = checker.check_data_freshness(updates)
        yahoo = [r for r in results if r.source_name == "yahoo_finance"][0]
        assert yahoo.is_stale

    def test_data_freshness_unknown(self):
        checker = HealthChecker()
        results = checker.check_data_freshness({})
        assert all(r.is_stale for r in results)
        assert all(r.status == "unknown" for r in results)

    def test_check_dependencies(self):
        checker = HealthChecker()
        deps = [
            {"name": "Yahoo Finance API", "available": True, "response_time_ms": 200},
            {"name": "Polygon API", "available": False, "failures": 3},
        ]
        results = checker.check_dependencies(deps)
        assert len(results) == 2
        assert results[0].status == "healthy"
        assert results[1].status == "down"

    def test_capture_snapshot(self):
        checker = HealthChecker()
        snapshot = checker.capture_snapshot()
        assert snapshot.overall_status == "healthy"
        assert len(snapshot.services) == 8

    def test_snapshot_with_down_service(self):
        checker = HealthChecker()
        data = {"api": {"is_available": False}}
        snapshot = checker.capture_snapshot(service_data=data)
        assert snapshot.overall_status == "down"

    def test_get_summary(self):
        checker = HealthChecker()
        metrics = SystemMetrics(cpu_usage=0.45, memory_usage=0.60, disk_usage=0.50)
        snapshot = checker.capture_snapshot(metrics=metrics)
        summary = checker.get_summary(snapshot)
        assert summary.total_services == 8
        assert summary.cpu_usage == 0.45

    def test_sample_snapshot(self):
        snapshot = HealthChecker.generate_sample_snapshot()
        assert snapshot.overall_status == "healthy"
        assert len(snapshot.services) == 8
        assert snapshot.metrics.cpu_usage > 0

    def test_history(self):
        checker = HealthChecker()
        checker.capture_snapshot()
        checker.capture_snapshot()
        assert len(checker.get_history()) == 2


# ── Metrics Collector Tests ──────────────────────────────────────────


class TestMetricsCollector:
    def test_record_snapshot(self):
        collector = MetricsCollector()
        m = SystemMetrics(cpu_usage=0.5, memory_usage=0.6)
        collector.record_snapshot(m)
        assert collector.get_latest().cpu_usage == 0.5

    def test_counters(self):
        collector = MetricsCollector()
        collector.increment_counter("requests", 10)
        collector.increment_counter("requests", 5)
        assert collector.get_counter("requests") == 15

    def test_gauges(self):
        collector = MetricsCollector()
        collector.set_gauge("cpu", 0.75)
        assert collector.get_gauge("cpu") == 0.75

    def test_history(self):
        collector = MetricsCollector()
        for i in range(5):
            collector.record_snapshot(SystemMetrics(cpu_usage=0.1 * i))
        assert len(collector.get_history(3)) == 3

    def test_averages(self):
        collector = MetricsCollector()
        for cpu in [0.3, 0.4, 0.5]:
            collector.record_snapshot(SystemMetrics(cpu_usage=cpu, memory_usage=0.6))
        avgs = collector.get_averages()
        assert avgs["avg_cpu"] == pytest.approx(0.4, abs=0.01)
        assert avgs["max_cpu"] == 0.5

    def test_percentiles(self):
        collector = MetricsCollector()
        for i in range(100):
            collector.record_snapshot(SystemMetrics(cpu_usage=i / 100))
        pcts = collector.get_percentiles("cpu_usage", [50, 90, 99])
        assert pcts["p50"] > 0
        assert pcts["p99"] > pcts["p50"]

    def test_anomaly_detection(self):
        collector = MetricsCollector()
        for _ in range(20):
            collector.record_snapshot(SystemMetrics(cpu_usage=0.50))
        # Add spike
        collector.record_snapshot(SystemMetrics(cpu_usage=0.99))
        result = collector.detect_anomaly("cpu_usage")
        assert result is not None
        assert result["is_anomaly"]

    def test_no_anomaly(self):
        collector = MetricsCollector()
        for _ in range(20):
            collector.record_snapshot(SystemMetrics(cpu_usage=0.50))
        result = collector.detect_anomaly("cpu_usage")
        assert result is None

    def test_max_history(self):
        collector = MetricsCollector(max_history=10)
        for i in range(20):
            collector.record_snapshot(SystemMetrics(cpu_usage=i / 20))
        assert len(collector.get_history(100)) == 10

    def test_reset_counters(self):
        collector = MetricsCollector()
        collector.increment_counter("test", 5)
        collector.reset_counters()
        assert collector.get_counter("test") == 0

    def test_sample_history(self):
        collector = MetricsCollector.generate_sample_history(30)
        assert len(collector.get_history(100)) == 30
        avgs = collector.get_averages()
        assert avgs["avg_cpu"] > 0


# ── Alert Manager Tests ──────────────────────────────────────────────


class TestSystemAlertManager:
    def test_cpu_warning(self):
        mgr = SystemAlertManager()
        metrics = SystemMetrics(cpu_usage=0.85)
        alerts = mgr.evaluate_metrics(metrics)
        cpu_alerts = [a for a in alerts if "CPU" in a.message]
        assert len(cpu_alerts) == 1
        assert cpu_alerts[0].level == "warning"

    def test_cpu_critical(self):
        mgr = SystemAlertManager()
        metrics = SystemMetrics(cpu_usage=0.96)
        alerts = mgr.evaluate_metrics(metrics)
        cpu_alerts = [a for a in alerts if "CPU" in a.message]
        assert len(cpu_alerts) == 1
        assert cpu_alerts[0].level == "critical"

    def test_memory_alert(self):
        mgr = SystemAlertManager()
        metrics = SystemMetrics(memory_usage=0.92)
        alerts = mgr.evaluate_metrics(metrics)
        mem_alerts = [a for a in alerts if "Memory" in a.message]
        assert len(mem_alerts) == 1

    def test_disk_alert(self):
        mgr = SystemAlertManager()
        metrics = SystemMetrics(disk_usage=0.96)
        alerts = mgr.evaluate_metrics(metrics)
        disk_alerts = [a for a in alerts if "Disk" in a.message]
        assert len(disk_alerts) == 1
        assert disk_alerts[0].level == "critical"

    def test_response_time_alert(self):
        mgr = SystemAlertManager()
        metrics = SystemMetrics(avg_response_time_ms=2500)
        alerts = mgr.evaluate_metrics(metrics)
        rt_alerts = [a for a in alerts if "response time" in a.message]
        assert len(rt_alerts) == 1

    def test_no_alerts_healthy(self):
        mgr = SystemAlertManager()
        metrics = SystemMetrics(cpu_usage=0.30, memory_usage=0.40, disk_usage=0.50)
        alerts = mgr.evaluate_metrics(metrics)
        assert len(alerts) == 0

    def test_evaluate_snapshot_down_service(self):
        mgr = SystemAlertManager()
        snapshot = HealthSnapshot(
            services=[ServiceHealth("api", "down")],
        )
        alerts = mgr.evaluate_snapshot(snapshot)
        assert len(alerts) >= 1
        assert any(a.level == "down" for a in alerts)

    def test_evaluate_stale_data(self):
        mgr = SystemAlertManager()
        snapshot = HealthSnapshot(
            data_freshness=[
                DataFreshness("yahoo", is_stale=True, staleness_minutes=120, status="stale"),
            ],
        )
        alerts = mgr.evaluate_snapshot(snapshot)
        stale_alerts = [a for a in alerts if "stale" in a.message]
        assert len(stale_alerts) == 1

    def test_acknowledge_alert(self):
        mgr = SystemAlertManager()
        metrics = SystemMetrics(cpu_usage=0.96)
        alerts = mgr.evaluate_metrics(metrics)
        assert len(alerts) > 0

        acked = mgr.acknowledge_alert(alerts[0].alert_id, "admin")
        assert acked
        assert alerts[0].acknowledged

    def test_resolve_alert(self):
        mgr = SystemAlertManager()
        metrics = SystemMetrics(cpu_usage=0.96)
        alerts = mgr.evaluate_metrics(metrics)

        resolved = mgr.resolve_alert(alerts[0].alert_id)
        assert resolved
        assert not alerts[0].is_active

    def test_get_active_alerts(self):
        mgr = SystemAlertManager()
        mgr.evaluate_metrics(SystemMetrics(cpu_usage=0.96, memory_usage=0.92))
        active = mgr.get_active_alerts()
        assert len(active) >= 2

        critical = mgr.get_active_alerts(level="critical")
        assert all(a.level == "critical" for a in critical)

    def test_alert_counts(self):
        mgr = SystemAlertManager()
        mgr.evaluate_metrics(SystemMetrics(cpu_usage=0.85, memory_usage=0.96))
        counts = mgr.get_alert_counts()
        assert isinstance(counts, dict)
        assert sum(counts.values()) >= 2

    def test_clear_resolved(self):
        mgr = SystemAlertManager()
        alerts = mgr.evaluate_metrics(SystemMetrics(cpu_usage=0.96))
        mgr.resolve_alert(alerts[0].alert_id)
        cleared = mgr.clear_resolved()
        assert cleared >= 1


# ── Integration Tests ─────────────────────────────────────────────────


class TestSystemDashboardIntegration:
    def test_full_monitoring_workflow(self):
        """End-to-end: health check -> metrics -> alerts -> summary."""
        # 1. Health check
        checker = HealthChecker()
        service_data = {
            "api": {"response_time_ms": 50, "error_rate": 0.001, "is_available": True},
            "database": {"response_time_ms": 10, "error_rate": 0.0, "is_available": True},
            "cache": {"response_time_ms": 2, "error_rate": 0.0, "is_available": True},
        }
        metrics = SystemMetrics(
            cpu_usage=0.45, memory_usage=0.60, disk_usage=0.50,
            requests_per_minute=400, avg_response_time_ms=38,
            cache_hit_rate=0.94,
        )
        now = datetime.now()
        source_updates = {
            "yahoo_finance": now - timedelta(minutes=5),
            "polygon": now - timedelta(minutes=3),
        }
        snapshot = checker.capture_snapshot(service_data, metrics, source_updates)

        # 2. Collect metrics
        collector = MetricsCollector()
        collector.record_snapshot(metrics)

        # 3. Check alerts
        alert_mgr = SystemAlertManager()
        metric_alerts = alert_mgr.evaluate_metrics(metrics)
        snapshot_alerts = alert_mgr.evaluate_snapshot(snapshot)

        # 4. Get summary
        summary = checker.get_summary(snapshot)
        assert summary.total_services == 8
        assert summary.overall_status == "healthy"

    def test_degraded_system(self):
        """Test system with degraded services and high resource usage."""
        checker = HealthChecker()
        service_data = {
            "api": {"response_time_ms": 3000, "error_rate": 0.08, "is_available": True},
            "database": {"is_available": False},
        }
        metrics = SystemMetrics(cpu_usage=0.92, memory_usage=0.88)
        snapshot = checker.capture_snapshot(service_data, metrics)

        assert snapshot.overall_status == "down"  # DB is down

        alert_mgr = SystemAlertManager()
        metric_alerts = alert_mgr.evaluate_metrics(metrics)
        snapshot_alerts = alert_mgr.evaluate_snapshot(snapshot)

        total_alerts = metric_alerts + snapshot_alerts
        assert len(total_alerts) > 0
        assert any(a.level == "down" for a in total_alerts)


# ── Module Import Test ────────────────────────────────────────────────


class TestSystemDashboardModuleImports:
    def test_import_all(self):
        import src.system_dashboard as sd
        assert hasattr(sd, "HealthChecker")
        assert hasattr(sd, "MetricsCollector")
        assert hasattr(sd, "SystemAlertManager")
        assert hasattr(sd, "ServiceName")
        assert hasattr(sd, "ServiceStatus")
        assert hasattr(sd, "HealthLevel")
        assert hasattr(sd, "SystemSummary")
        assert hasattr(sd, "HealthSnapshot")
