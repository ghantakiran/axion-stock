"""Tests for PRD-117: Performance Profiling & Query Optimization."""

import time
from datetime import datetime, timedelta

import pytest

from src.profiling.config import (
    IndexStatus,
    ProfilingConfig,
    QuerySeverity,
)
from src.profiling.query_profiler import QueryFingerprint, QueryProfiler
from src.profiling.analyzer import PerformanceAnalyzer, PerformanceSnapshot
from src.profiling.index_advisor import IndexAdvisor, IndexRecommendation
from src.profiling.connections import (
    ConnectionMonitor,
    ConnectionStats,
    LongRunningQuery,
)


# ── Config Tests ─────────────────────────────────────────────────────


class TestQuerySeverityEnum:
    def test_values(self):
        assert QuerySeverity.NORMAL.value == "normal"
        assert QuerySeverity.SLOW.value == "slow"
        assert QuerySeverity.CRITICAL.value == "critical"

    def test_count(self):
        assert len(QuerySeverity) == 3


class TestIndexStatusEnum:
    def test_values(self):
        assert IndexStatus.RECOMMENDED.value == "recommended"
        assert IndexStatus.APPROVED.value == "approved"
        assert IndexStatus.APPLIED.value == "applied"
        assert IndexStatus.REJECTED.value == "rejected"

    def test_count(self):
        assert len(IndexStatus) == 4


class TestProfilingConfig:
    def test_defaults(self):
        cfg = ProfilingConfig()
        assert cfg.slow_query_threshold_ms == 1000.0
        assert cfg.critical_query_threshold_ms == 5000.0
        assert cfg.max_query_history == 10000
        assert cfg.enable_explain is True
        assert cfg.enable_n1_detection is True
        assert cfg.pool_warning_threshold == 0.8
        assert cfg.pool_critical_threshold == 0.95
        assert cfg.idle_connection_timeout_seconds == 300

    def test_custom(self):
        cfg = ProfilingConfig(slow_query_threshold_ms=500, max_query_history=5000)
        assert cfg.slow_query_threshold_ms == 500
        assert cfg.max_query_history == 5000


# ── QueryProfiler Tests ─────────────────────────────────────────────


class TestQueryProfiler:
    def setup_method(self):
        self.profiler = QueryProfiler()

    def test_record_single_query(self):
        fp = self.profiler.record_query("SELECT * FROM users WHERE id = 1", 50.0)
        assert fp.call_count == 1
        assert fp.total_duration_ms == 50.0
        assert fp.fingerprint is not None

    def test_record_duplicate_queries_fingerprint(self):
        self.profiler.record_query("SELECT * FROM users WHERE id = 1", 30.0)
        self.profiler.record_query("SELECT * FROM users WHERE id = 2", 40.0)
        stats = self.profiler.get_query_stats()
        # Both should map to same fingerprint (id = ? normalization)
        assert stats["unique_fingerprints"] == 1
        assert stats["total_queries"] == 2

    def test_fingerprint_stats(self):
        self.profiler.record_query("SELECT * FROM orders WHERE price > 100", 20.0)
        self.profiler.record_query("SELECT * FROM orders WHERE price > 200", 80.0)
        fps = self.profiler.get_top_queries(n=1)
        fp = fps[0]
        assert fp.call_count == 2
        assert fp.total_duration_ms == 100.0
        assert fp.avg_duration_ms == 50.0
        assert fp.min_duration_ms == 20.0
        assert fp.max_duration_ms == 80.0

    def test_slow_query_detection(self):
        self.profiler.record_query("SELECT * FROM big_table", 1500.0)
        slow = self.profiler.get_slow_queries()
        assert len(slow) == 1
        assert slow[0].severity == QuerySeverity.SLOW

    def test_critical_query_detection(self):
        self.profiler.record_query("SELECT * FROM huge_table", 6000.0)
        fps = self.profiler.get_top_queries(n=1)
        assert fps[0].severity == QuerySeverity.CRITICAL

    def test_slow_queries_custom_threshold(self):
        self.profiler.record_query("SELECT 1", 200.0)
        slow = self.profiler.get_slow_queries(threshold_ms=100)
        assert len(slow) == 1

    def test_top_queries_sort_by_call_count(self):
        for _ in range(10):
            self.profiler.record_query("SELECT * FROM a", 10.0)
        for _ in range(5):
            self.profiler.record_query("SELECT * FROM b", 10.0)
        top = self.profiler.get_top_queries(n=2, sort_by="call_count")
        assert top[0].call_count >= top[1].call_count

    def test_top_queries_sort_by_avg_duration(self):
        self.profiler.record_query("SELECT * FROM fast", 10.0)
        self.profiler.record_query("SELECT * FROM slow_table", 5000.0)
        top = self.profiler.get_top_queries(n=2, sort_by="avg_duration")
        assert top[0].avg_duration_ms >= top[1].avg_duration_ms

    def test_get_query_stats(self):
        self.profiler.record_query("SELECT 1", 10.0)
        self.profiler.record_query("SELECT 2", 20.0)
        stats = self.profiler.get_query_stats()
        assert stats["total_queries"] == 2
        assert stats["avg_duration_ms"] == 15.0

    def test_get_fingerprint(self):
        fp = self.profiler.record_query("SELECT * FROM test", 50.0)
        retrieved = self.profiler.get_fingerprint(fp.fingerprint)
        assert retrieved is not None
        assert retrieved.fingerprint == fp.fingerprint

    def test_get_fingerprint_not_found(self):
        result = self.profiler.get_fingerprint("nonexistent")
        assert result is None

    def test_detect_regressions(self):
        # Record stable baseline (20 queries at ~50ms)
        for _ in range(20):
            self.profiler.record_query("SELECT * FROM stable", 50.0)
        # Record regression (10 queries at ~200ms, >2x)
        for _ in range(10):
            self.profiler.record_query("SELECT * FROM stable", 200.0)
        regressions = self.profiler.detect_regressions(window_size=10)
        assert len(regressions) == 1

    def test_no_regression(self):
        for _ in range(25):
            self.profiler.record_query("SELECT * FROM consistent", 50.0)
        regressions = self.profiler.detect_regressions(window_size=10)
        assert len(regressions) == 0

    def test_normalize_query(self):
        normalized = self.profiler._normalize_query(
            "SELECT * FROM users WHERE name = 'Alice' AND age > 30"
        )
        assert "Alice" not in normalized
        assert "30" not in normalized
        assert "?" in normalized

    def test_normalize_query_numbers(self):
        normalized = self.profiler._normalize_query(
            "UPDATE t SET val = 3.14 WHERE id = 42"
        )
        assert "3.14" not in normalized
        assert "42" not in normalized

    def test_p95_p99(self):
        for i in range(100):
            self.profiler.record_query("SELECT * FROM pct_test", float(i + 1))
        fps = self.profiler.get_top_queries(n=1)
        fp = fps[0]
        assert fp.p95_duration_ms >= 95.0
        assert fp.p99_duration_ms >= 99.0

    def test_reset(self):
        self.profiler.record_query("SELECT 1", 10.0)
        self.profiler.reset()
        stats = self.profiler.get_query_stats()
        assert stats["total_queries"] == 0

    def test_record_with_params(self):
        fp = self.profiler.record_query(
            "SELECT * FROM t WHERE id = 1", 25.0, params={"id": 1}
        )
        assert fp.call_count == 1


# ── PerformanceAnalyzer Tests ────────────────────────────────────────


class TestPerformanceAnalyzer:
    def setup_method(self):
        self.analyzer = PerformanceAnalyzer()

    def test_take_snapshot(self):
        snap = self.analyzer.take_snapshot(memory_mb=512.0, cpu_pct=45.0)
        assert isinstance(snap, PerformanceSnapshot)
        assert snap.memory_usage_mb == 512.0
        assert snap.cpu_percent == 45.0

    def test_get_snapshots(self):
        self.analyzer.take_snapshot(memory_mb=100)
        self.analyzer.take_snapshot(memory_mb=200)
        self.analyzer.take_snapshot(memory_mb=300)
        snaps = self.analyzer.get_snapshots(limit=2)
        assert len(snaps) == 2
        # Most recent first
        assert snaps[0].memory_usage_mb == 300

    def test_detect_n1_queries(self):
        queries = []
        for i in range(10):
            queries.append({"template": "SELECT * FROM orders WHERE user_id = ?", "timestamp_ms": float(i * 5)})
        detections = self.analyzer.detect_n1_queries(queries)
        assert len(detections) == 1
        assert detections[0]["count_in_window"] > 5

    def test_detect_n1_no_pattern(self):
        queries = [
            {"template": "SELECT * FROM a", "timestamp_ms": 0.0},
            {"template": "SELECT * FROM b", "timestamp_ms": 50.0},
            {"template": "SELECT * FROM c", "timestamp_ms": 100.0},
        ]
        detections = self.analyzer.detect_n1_queries(queries)
        assert len(detections) == 0

    def test_compare_snapshots(self):
        s1 = self.analyzer.take_snapshot(memory_mb=512, cpu_pct=30, connections=5)
        s2 = self.analyzer.take_snapshot(memory_mb=768, cpu_pct=60, connections=10)
        diff = self.analyzer.compare_snapshots(s1.snapshot_id, s2.snapshot_id)
        assert diff["memory_change_mb"] == 256
        assert diff["cpu_change_pct"] == 30
        assert diff["connection_change"] == 5

    def test_compare_snapshots_not_found(self):
        result = self.analyzer.compare_snapshots("bad_id_1", "bad_id_2")
        assert "error" in result

    def test_memory_trend(self):
        for mb in [100, 200, 300, 400]:
            self.analyzer.take_snapshot(memory_mb=mb)
        trend = self.analyzer.get_memory_trend()
        assert trend == [100, 200, 300, 400]

    def test_get_n1_detections(self):
        queries = []
        for i in range(10):
            queries.append({"template": "SELECT * FROM items WHERE order_id = ?", "timestamp_ms": float(i * 5)})
        self.analyzer.detect_n1_queries(queries)
        detections = self.analyzer.get_n1_detections()
        assert len(detections) >= 1

    def test_reset(self):
        self.analyzer.take_snapshot(memory_mb=100)
        self.analyzer.reset()
        assert len(self.analyzer.get_snapshots()) == 0
        assert len(self.analyzer.get_n1_detections()) == 0

    def test_snapshot_default_values(self):
        snap = PerformanceSnapshot()
        assert snap.memory_usage_mb == 0.0
        assert snap.cpu_percent == 0.0
        assert snap.active_connections == 0
        assert isinstance(snap.snapshot_id, str)


# ── IndexAdvisor Tests ───────────────────────────────────────────────


class TestIndexAdvisor:
    def setup_method(self):
        self.advisor = IndexAdvisor()

    def test_add_recommendation(self):
        rec = self.advisor.add_recommendation(
            table="orders",
            columns=["user_id", "created_at"],
            rationale="Frequent filter on user_id",
        )
        assert rec.table_name == "orders"
        assert rec.columns == ["user_id", "created_at"]
        assert rec.status == IndexStatus.RECOMMENDED

    def test_approve_recommendation(self):
        rec = self.advisor.add_recommendation("t", ["col"], "test")
        assert self.advisor.approve(rec.recommendation_id)
        recs = self.advisor.get_recommendations(status=IndexStatus.APPROVED)
        assert len(recs) == 1

    def test_reject_recommendation(self):
        rec = self.advisor.add_recommendation("t", ["col"], "test")
        assert self.advisor.reject(rec.recommendation_id)
        recs = self.advisor.get_recommendations(status=IndexStatus.REJECTED)
        assert len(recs) == 1

    def test_mark_applied(self):
        rec = self.advisor.add_recommendation("t", ["col"], "test")
        self.advisor.approve(rec.recommendation_id)
        assert self.advisor.mark_applied(rec.recommendation_id)
        recs = self.advisor.get_recommendations(status=IndexStatus.APPLIED)
        assert len(recs) == 1

    def test_mark_applied_not_approved(self):
        rec = self.advisor.add_recommendation("t", ["col"], "test")
        # Cannot apply without approval
        assert not self.advisor.mark_applied(rec.recommendation_id)

    def test_approve_nonexistent(self):
        assert not self.advisor.approve("nonexistent")

    def test_reject_applied(self):
        rec = self.advisor.add_recommendation("t", ["col"], "test")
        self.advisor.approve(rec.recommendation_id)
        self.advisor.mark_applied(rec.recommendation_id)
        # Cannot reject an applied index
        assert not self.advisor.reject(rec.recommendation_id)

    def test_report_unused_index(self):
        entry = self.advisor.report_unused_index(
            "idx_old", "orders", "No queries use this index"
        )
        assert entry["index_name"] == "idx_old"
        unused = self.advisor.get_unused_indexes()
        assert len(unused) == 1

    def test_get_recommendations_all(self):
        self.advisor.add_recommendation("t1", ["a"], "r1")
        self.advisor.add_recommendation("t2", ["b"], "r2")
        recs = self.advisor.get_recommendations()
        assert len(recs) == 2

    def test_get_recommendations_filtered(self):
        rec1 = self.advisor.add_recommendation("t1", ["a"], "r1")
        self.advisor.add_recommendation("t2", ["b"], "r2")
        self.advisor.approve(rec1.recommendation_id)
        approved = self.advisor.get_recommendations(status=IndexStatus.APPROVED)
        assert len(approved) == 1

    def test_summary(self):
        self.advisor.add_recommendation("t1", ["a"], "r1")
        rec2 = self.advisor.add_recommendation("t2", ["b"], "r2")
        self.advisor.approve(rec2.recommendation_id)
        self.advisor.report_unused_index("idx", "t", "unused")
        summary = self.advisor.get_summary()
        assert summary["total_recommendations"] == 2
        assert summary["unused_indexes"] == 1
        assert "recommended" in summary["by_status"]
        assert "approved" in summary["by_status"]

    def test_analyze_query_patterns(self):
        profiler = QueryProfiler()
        for _ in range(10):
            profiler.record_query(
                "SELECT * FROM orders WHERE user_id = 1 AND status = 'active'",
                500.0,
            )
        recs = self.advisor.analyze_query_patterns(profiler)
        # Should find at least one recommendation based on WHERE clause
        assert len(recs) >= 1

    def test_reset(self):
        self.advisor.add_recommendation("t", ["c"], "r")
        self.advisor.report_unused_index("idx", "t", "x")
        self.advisor.reset()
        assert len(self.advisor.get_recommendations()) == 0
        assert len(self.advisor.get_unused_indexes()) == 0

    def test_recommendation_defaults(self):
        rec = IndexRecommendation(table_name="test", columns=["id"])
        assert rec.index_type == "btree"
        assert rec.estimated_impact == "medium"
        assert rec.status == IndexStatus.RECOMMENDED
        assert isinstance(rec.recommendation_id, str)


# ── ConnectionMonitor Tests ──────────────────────────────────────────


class TestConnectionMonitor:
    def setup_method(self):
        self.monitor = ConnectionMonitor()

    def test_record_stats(self):
        stats = ConnectionStats(pool_size=20, active=5, idle=15)
        self.monitor.record_stats(stats)
        current = self.monitor.get_current_stats()
        assert current is not None
        assert current.active == 5

    def test_utilization(self):
        stats = ConnectionStats(pool_size=20, active=10)
        assert stats.utilization == 0.5
        assert not stats.is_saturated

    def test_saturated(self):
        stats = ConnectionStats(pool_size=10, active=10)
        assert stats.utilization == 1.0
        assert stats.is_saturated

    def test_utilization_zero_pool(self):
        stats = ConnectionStats(pool_size=0, active=0)
        assert stats.utilization == 0.0

    def test_get_utilization_trend(self):
        for active in [2, 4, 6, 8, 10]:
            self.monitor.record_stats(ConnectionStats(pool_size=20, active=active))
        trend = self.monitor.get_utilization_trend()
        assert len(trend) == 5
        assert trend[-1] == 0.5

    def test_detect_pool_exhaustion_critical(self):
        self.monitor.record_stats(ConnectionStats(pool_size=10, active=10))
        result = self.monitor.detect_pool_exhaustion()
        assert result["at_risk"] is True
        assert "CRITICAL" in result["recommendation"]

    def test_detect_pool_exhaustion_warning(self):
        self.monitor.record_stats(ConnectionStats(pool_size=10, active=9))
        result = self.monitor.detect_pool_exhaustion()
        assert result["at_risk"] is True
        assert "WARNING" in result["recommendation"]

    def test_detect_pool_exhaustion_healthy(self):
        self.monitor.record_stats(ConnectionStats(pool_size=20, active=5))
        result = self.monitor.detect_pool_exhaustion()
        assert result["at_risk"] is False

    def test_detect_pool_exhaustion_no_data(self):
        result = self.monitor.detect_pool_exhaustion()
        assert result["at_risk"] is False

    def test_track_long_query(self):
        qid = self.monitor.track_long_query("SELECT * FROM big_table", user="admin")
        assert isinstance(qid, str)

    def test_complete_query(self):
        qid = self.monitor.track_long_query("SELECT * FROM t")
        self.monitor.complete_query(qid, 5000.0)
        # After completion, should show up in long running if threshold met
        long_running = self.monitor.get_long_running(threshold_ms=1000)
        assert any(lq.query_id == qid for lq in long_running)

    def test_get_long_running_active(self):
        # Track a query that we simulate as started 60 seconds ago
        qid = self.monitor.track_long_query("SELECT * FROM slow")
        # Manually backdate the query's start time
        self.monitor._long_queries[qid].started_at = datetime.now() - timedelta(
            seconds=60
        )
        long_running = self.monitor.get_long_running(threshold_ms=30000)
        assert len(long_running) >= 1

    def test_detect_leaks(self):
        # Simulate growing active connections with zero idle
        for active in [3, 4, 5, 6, 7]:
            self.monitor.record_stats(
                ConnectionStats(pool_size=20, active=active, idle=0)
            )
        leaks = self.monitor.detect_leaks()
        assert len(leaks) == 1
        assert "connection_leak" in leaks[0]["type"]

    def test_detect_leaks_no_leak(self):
        for _ in range(5):
            self.monitor.record_stats(
                ConnectionStats(pool_size=20, active=5, idle=15)
            )
        leaks = self.monitor.detect_leaks()
        assert len(leaks) == 0

    def test_detect_leaks_insufficient_data(self):
        self.monitor.record_stats(ConnectionStats(pool_size=10, active=5, idle=0))
        leaks = self.monitor.detect_leaks()
        assert len(leaks) == 0

    def test_report_leak(self):
        entry = self.monitor.report_leak("Connection not returned after 5 minutes")
        assert entry["type"] == "manual_report"
        assert "Connection not returned" in entry["description"]

    def test_pool_health_healthy(self):
        self.monitor.record_stats(ConnectionStats(pool_size=20, active=5, idle=15))
        health = self.monitor.get_pool_health()
        assert health["status"] == "healthy"
        assert health["leak_count"] == 0

    def test_pool_health_warning(self):
        self.monitor.record_stats(ConnectionStats(pool_size=10, active=9))
        health = self.monitor.get_pool_health()
        assert health["status"] == "warning"

    def test_pool_health_critical(self):
        self.monitor.record_stats(ConnectionStats(pool_size=10, active=10))
        self.monitor.report_leak("suspected leak")
        health = self.monitor.get_pool_health()
        assert health["status"] == "critical"
        assert health["leak_count"] == 1

    def test_reset(self):
        self.monitor.record_stats(ConnectionStats(pool_size=10, active=5))
        self.monitor.track_long_query("SELECT 1")
        self.monitor.report_leak("leak")
        self.monitor.reset()
        assert self.monitor.get_current_stats() is None
        assert self.monitor.get_pool_health()["leak_count"] == 0

    def test_long_running_query_defaults(self):
        lq = LongRunningQuery(query_text="SELECT 1")
        assert lq.user == "unknown"
        assert lq.state == "active"
        assert lq.duration_ms == 0.0


# ── Integration Tests ────────────────────────────────────────────────


class TestProfilingIntegration:
    def test_full_profiling_workflow(self):
        """End-to-end: profile queries -> analyze -> recommend indexes -> monitor."""
        # 1. Profile queries
        profiler = QueryProfiler()
        for i in range(20):
            profiler.record_query(
                f"SELECT * FROM orders WHERE user_id = {i}", 150.0 + i * 10
            )
        for i in range(5):
            profiler.record_query(
                "SELECT * FROM large_table WHERE status = 'pending'", 3000.0
            )

        stats = profiler.get_query_stats()
        assert stats["total_queries"] == 25

        # 2. Analyze performance
        analyzer = PerformanceAnalyzer()
        snap = analyzer.take_snapshot(
            query_stats=stats, memory_mb=1024, cpu_pct=55, connections=8
        )
        assert snap.memory_usage_mb == 1024

        # 3. Index recommendations
        advisor = IndexAdvisor()
        recs = advisor.analyze_query_patterns(profiler)
        assert len(recs) >= 1

        # 4. Connection monitoring
        monitor = ConnectionMonitor()
        monitor.record_stats(ConnectionStats(pool_size=20, active=8, idle=12))
        health = monitor.get_pool_health()
        assert health["status"] == "healthy"

    def test_degraded_system(self):
        """Simulate a system with performance issues."""
        profiler = QueryProfiler()
        for _ in range(10):
            profiler.record_query("SELECT * FROM huge_join", 8000.0)

        slow = profiler.get_slow_queries()
        assert len(slow) == 1
        assert slow[0].severity == QuerySeverity.CRITICAL

        monitor = ConnectionMonitor()
        for active in [15, 16, 17, 18, 19]:
            monitor.record_stats(
                ConnectionStats(pool_size=20, active=active, idle=0)
            )
        exhaustion = monitor.detect_pool_exhaustion()
        assert exhaustion["at_risk"] is True


# ── Module Import Test ───────────────────────────────────────────────


class TestProfilingModuleImports:
    def test_import_all(self):
        import src.profiling as prof

        assert hasattr(prof, "QuerySeverity")
        assert hasattr(prof, "IndexStatus")
        assert hasattr(prof, "ProfilingConfig")
        assert hasattr(prof, "QueryFingerprint")
        assert hasattr(prof, "QueryProfiler")
        assert hasattr(prof, "PerformanceSnapshot")
        assert hasattr(prof, "PerformanceAnalyzer")
        assert hasattr(prof, "IndexRecommendation")
        assert hasattr(prof, "IndexAdvisor")
        assert hasattr(prof, "ConnectionStats")
        assert hasattr(prof, "LongRunningQuery")
        assert hasattr(prof, "ConnectionMonitor")
