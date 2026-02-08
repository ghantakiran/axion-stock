"""Tests for PRD-112: Data Pipeline Orchestration & Monitoring."""

import time
from datetime import datetime, timedelta

import pytest

from src.pipeline.config import (
    NodeStatus,
    PipelineConfig,
    PipelineStatus,
    ScheduleType,
    SLAConfig,
)
from src.pipeline.definition import Pipeline, PipelineNode, PipelineRun
from src.pipeline.engine import ExecutionResult, PipelineEngine
from src.pipeline.lineage import LineageEdge, LineageGraph, LineageNode
from src.pipeline.scheduler import PipelineScheduler, Schedule
from src.pipeline.monitoring import (
    FreshnessCheck,
    PipelineMetrics,
    PipelineMonitor,
    SLAResult,
)


# ── Helper functions used as node tasks ──────────────────────────────


def _noop():
    """Minimal no-op task."""
    time.sleep(0.01)


def _fast_task():
    """Fast task for testing."""
    time.sleep(0.005)
    return "done"


def _failing_task():
    """Always-failing task."""
    raise RuntimeError("intentional failure")


def _slow_task():
    """Task that takes a while (for timeout testing)."""
    time.sleep(5)


# ═══════════════════════════════════════════════════════════════════════
# Config Tests
# ═══════════════════════════════════════════════════════════════════════


class TestPipelineConfig:
    """Tests for configuration enums and dataclasses."""

    def test_pipeline_status_values(self):
        assert PipelineStatus.PENDING.value == "pending"
        assert PipelineStatus.RUNNING.value == "running"
        assert PipelineStatus.SUCCESS.value == "success"
        assert PipelineStatus.FAILED.value == "failed"
        assert PipelineStatus.SKIPPED.value == "skipped"
        assert PipelineStatus.CANCELLED.value == "cancelled"

    def test_pipeline_status_count(self):
        assert len(PipelineStatus) == 6

    def test_node_status_values(self):
        assert NodeStatus.PENDING.value == "pending"
        assert NodeStatus.RUNNING.value == "running"
        assert NodeStatus.SUCCESS.value == "success"
        assert NodeStatus.FAILED.value == "failed"
        assert NodeStatus.SKIPPED.value == "skipped"
        assert NodeStatus.CANCELLED.value == "cancelled"

    def test_node_status_count(self):
        assert len(NodeStatus) == 6

    def test_schedule_type_values(self):
        assert ScheduleType.ONCE.value == "once"
        assert ScheduleType.RECURRING.value == "recurring"
        assert ScheduleType.CRON.value == "cron"
        assert ScheduleType.MARKET_HOURS.value == "market_hours"

    def test_schedule_type_count(self):
        assert len(ScheduleType) == 4

    def test_default_pipeline_config(self):
        cfg = PipelineConfig()
        assert cfg.max_parallel_nodes == 4
        assert cfg.default_timeout_seconds == 300
        assert cfg.default_retries == 3
        assert cfg.retry_backoff_base == 2.0
        assert cfg.enable_lineage is True
        assert cfg.enable_monitoring is True

    def test_custom_pipeline_config(self):
        cfg = PipelineConfig(
            max_parallel_nodes=8,
            default_timeout_seconds=60,
            default_retries=1,
            retry_backoff_base=1.5,
            enable_lineage=False,
            enable_monitoring=False,
        )
        assert cfg.max_parallel_nodes == 8
        assert cfg.default_timeout_seconds == 60
        assert cfg.default_retries == 1
        assert cfg.retry_backoff_base == 1.5
        assert cfg.enable_lineage is False
        assert cfg.enable_monitoring is False

    def test_sla_config_defaults(self):
        sla = SLAConfig()
        assert sla.max_duration_seconds == 600.0
        assert sla.max_failure_rate == 0.1
        assert sla.min_data_freshness_seconds == 3600.0

    def test_sla_config_custom(self):
        sla = SLAConfig(
            max_duration_seconds=120.0,
            max_failure_rate=0.05,
            min_data_freshness_seconds=300.0,
        )
        assert sla.max_duration_seconds == 120.0
        assert sla.max_failure_rate == 0.05


# ═══════════════════════════════════════════════════════════════════════
# Definition Tests
# ═══════════════════════════════════════════════════════════════════════


class TestPipelineDefinition:
    """Tests for Pipeline, PipelineNode, and PipelineRun."""

    def setup_method(self):
        self.pipeline = Pipeline("test-pipe", "Test Pipeline", "A test pipeline")

    def test_add_node(self):
        node = PipelineNode(node_id="n1", name="Node 1", func=_noop)
        self.pipeline.add_node(node)
        assert "n1" in self.pipeline.nodes
        assert self.pipeline.nodes["n1"].name == "Node 1"

    def test_add_duplicate_node_raises(self):
        node = PipelineNode(node_id="n1", name="Node 1")
        self.pipeline.add_node(node)
        with pytest.raises(ValueError, match="already exists"):
            self.pipeline.add_node(PipelineNode(node_id="n1", name="Dup"))

    def test_remove_node(self):
        self.pipeline.add_node(PipelineNode(node_id="n1", name="N1"))
        self.pipeline.add_node(
            PipelineNode(node_id="n2", name="N2", dependencies=["n1"])
        )
        self.pipeline.remove_node("n1")
        assert "n1" not in self.pipeline.nodes
        # n2's dependency should be cleaned up
        assert "n1" not in self.pipeline.nodes["n2"].dependencies

    def test_remove_missing_node_raises(self):
        with pytest.raises(KeyError, match="not found"):
            self.pipeline.remove_node("nonexistent")

    def test_topological_sort_linear(self):
        self.pipeline.add_node(PipelineNode(node_id="a", name="A"))
        self.pipeline.add_node(
            PipelineNode(node_id="b", name="B", dependencies=["a"])
        )
        self.pipeline.add_node(
            PipelineNode(node_id="c", name="C", dependencies=["b"])
        )
        levels = self.pipeline.get_execution_order()
        assert levels[0] == ["a"]
        assert levels[1] == ["b"]
        assert levels[2] == ["c"]

    def test_topological_sort_parallel(self):
        self.pipeline.add_node(PipelineNode(node_id="a", name="A"))
        self.pipeline.add_node(
            PipelineNode(node_id="b", name="B", dependencies=["a"])
        )
        self.pipeline.add_node(
            PipelineNode(node_id="c", name="C", dependencies=["a"])
        )
        self.pipeline.add_node(
            PipelineNode(node_id="d", name="D", dependencies=["b", "c"])
        )
        levels = self.pipeline.get_execution_order()
        assert levels[0] == ["a"]
        assert set(levels[1]) == {"b", "c"}
        assert levels[2] == ["d"]

    def test_cycle_detection(self):
        self.pipeline.add_node(
            PipelineNode(node_id="a", name="A", dependencies=["b"])
        )
        self.pipeline.add_node(
            PipelineNode(node_id="b", name="B", dependencies=["a"])
        )
        with pytest.raises(ValueError, match="cycle"):
            self.pipeline.get_execution_order()

    def test_validate_valid_pipeline(self):
        self.pipeline.add_node(PipelineNode(node_id="a", name="A"))
        self.pipeline.add_node(
            PipelineNode(node_id="b", name="B", dependencies=["a"])
        )
        errors = self.pipeline.validate()
        assert errors == []

    def test_validate_missing_dependency(self):
        self.pipeline.add_node(
            PipelineNode(node_id="a", name="A", dependencies=["missing"])
        )
        errors = self.pipeline.validate()
        assert any("missing" in e for e in errors)

    def test_validate_cycle(self):
        self.pipeline.add_node(
            PipelineNode(node_id="a", name="A", dependencies=["b"])
        )
        self.pipeline.add_node(
            PipelineNode(node_id="b", name="B", dependencies=["a"])
        )
        errors = self.pipeline.validate()
        assert any("cycle" in e.lower() for e in errors)

    def test_get_node_dependents(self):
        self.pipeline.add_node(PipelineNode(node_id="a", name="A"))
        self.pipeline.add_node(
            PipelineNode(node_id="b", name="B", dependencies=["a"])
        )
        self.pipeline.add_node(
            PipelineNode(node_id="c", name="C", dependencies=["a"])
        )
        deps = self.pipeline.get_node_dependents("a")
        assert set(deps) == {"b", "c"}

    def test_create_run(self):
        self.pipeline.add_node(PipelineNode(node_id="a", name="A"))
        self.pipeline.add_node(
            PipelineNode(node_id="b", name="B", dependencies=["a"])
        )
        run = self.pipeline.create_run()
        assert run.pipeline_id == "test-pipe"
        assert len(run.nodes) == 2
        assert run.status == PipelineStatus.PENDING
        assert all(n.status == NodeStatus.PENDING for n in run.nodes.values())

    def test_pipeline_run_defaults(self):
        run = PipelineRun()
        assert run.run_id  # UUID generated
        assert run.status == PipelineStatus.PENDING
        assert run.started_at is None
        assert run.completed_at is None
        assert run.error is None

    def test_pipeline_node_defaults(self):
        node = PipelineNode(node_id="x", name="X")
        assert node.func is None
        assert node.dependencies == []
        assert node.timeout_seconds == 300
        assert node.retries == 3
        assert node.metadata == {}
        assert node.status == NodeStatus.PENDING


# ═══════════════════════════════════════════════════════════════════════
# Engine Tests
# ═══════════════════════════════════════════════════════════════════════


class TestPipelineEngine:
    """Tests for the pipeline execution engine."""

    def setup_method(self):
        self.config = PipelineConfig(max_parallel_nodes=2, default_retries=1)
        self.engine = PipelineEngine(config=self.config)

    def test_execute_simple_pipeline(self):
        pipe = Pipeline("p1", "Simple")
        pipe.add_node(PipelineNode(node_id="a", name="A", func=_noop))
        pipe.add_node(
            PipelineNode(node_id="b", name="B", func=_noop, dependencies=["a"])
        )
        run = self.engine.execute(pipe)
        assert run.status == PipelineStatus.SUCCESS
        assert run.nodes["a"].status == NodeStatus.SUCCESS
        assert run.nodes["b"].status == NodeStatus.SUCCESS
        assert run.started_at is not None
        assert run.completed_at is not None

    def test_execute_parallel_nodes(self):
        pipe = Pipeline("p2", "Parallel")
        pipe.add_node(PipelineNode(node_id="root", name="Root", func=_fast_task))
        pipe.add_node(
            PipelineNode(
                node_id="a", name="A", func=_fast_task, dependencies=["root"]
            )
        )
        pipe.add_node(
            PipelineNode(
                node_id="b", name="B", func=_fast_task, dependencies=["root"]
            )
        )
        pipe.add_node(
            PipelineNode(
                node_id="c", name="C", func=_fast_task, dependencies=["root"]
            )
        )
        run = self.engine.execute(pipe)
        assert run.status == PipelineStatus.SUCCESS
        assert all(
            run.nodes[n].status == NodeStatus.SUCCESS for n in ["root", "a", "b", "c"]
        )

    def test_failure_handling(self):
        pipe = Pipeline("p3", "Fail")
        pipe.add_node(
            PipelineNode(node_id="bad", name="Bad", func=_failing_task, retries=0)
        )
        run = self.engine.execute(pipe)
        assert run.status == PipelineStatus.FAILED
        assert run.nodes["bad"].status == NodeStatus.FAILED

    def test_retry_logic(self):
        call_count = 0

        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("flaky")

        pipe = Pipeline("p4", "Retry")
        pipe.add_node(
            PipelineNode(node_id="flaky", name="Flaky", func=flaky, retries=3)
        )
        run = self.engine.execute(pipe)
        assert run.status == PipelineStatus.SUCCESS
        assert run.nodes["flaky"].status == NodeStatus.SUCCESS
        assert call_count == 3  # 2 failures + 1 success

    def test_skip_downstream_on_failure(self):
        pipe = Pipeline("p5", "Skip")
        pipe.add_node(
            PipelineNode(node_id="a", name="A", func=_failing_task, retries=0)
        )
        pipe.add_node(
            PipelineNode(
                node_id="b", name="B", func=_noop, dependencies=["a"]
            )
        )
        pipe.add_node(
            PipelineNode(
                node_id="c", name="C", func=_noop, dependencies=["b"]
            )
        )
        run = self.engine.execute(pipe)
        assert run.status == PipelineStatus.FAILED
        assert run.nodes["a"].status == NodeStatus.FAILED
        assert run.nodes["b"].status == NodeStatus.SKIPPED
        assert run.nodes["c"].status == NodeStatus.SKIPPED

    def test_timeout(self):
        pipe = Pipeline("p6", "Timeout")
        pipe.add_node(
            PipelineNode(
                node_id="slow",
                name="Slow",
                func=_slow_task,
                timeout_seconds=1,
                retries=0,
            )
        )
        run = self.engine.execute(pipe)
        assert run.status == PipelineStatus.FAILED
        assert run.nodes["slow"].status == NodeStatus.FAILED

    def test_cancel_run(self):
        pipe = Pipeline("p7", "Cancel")
        pipe.add_node(PipelineNode(node_id="a", name="A", func=_noop))
        run = pipe.create_run()
        run.status = PipelineStatus.RUNNING
        self.engine._runs[run.run_id] = run
        result = self.engine.cancel_run(run.run_id)
        assert result is True
        assert self.engine.get_run(run.run_id).status == PipelineStatus.CANCELLED

    def test_cancel_nonexistent_run(self):
        assert self.engine.cancel_run("nonexistent") is False

    def test_get_run(self):
        pipe = Pipeline("p8", "GetRun")
        pipe.add_node(PipelineNode(node_id="a", name="A", func=_noop))
        run = self.engine.execute(pipe)
        retrieved = self.engine.get_run(run.run_id)
        assert retrieved is not None
        assert retrieved.run_id == run.run_id

    def test_get_runs(self):
        pipe = Pipeline("p9", "Runs")
        pipe.add_node(PipelineNode(node_id="a", name="A", func=_noop))
        self.engine.execute(pipe)
        self.engine.execute(pipe)
        assert len(self.engine.get_runs()) == 2

    def test_execute_invalid_pipeline(self):
        pipe = Pipeline("bad", "Bad")
        pipe.add_node(
            PipelineNode(node_id="a", name="A", dependencies=["missing"])
        )
        with pytest.raises(ValueError, match="Invalid pipeline"):
            self.engine.execute(pipe)

    def test_execution_result_dataclass(self):
        r = ExecutionResult(node_id="x", status=NodeStatus.SUCCESS, duration_ms=42.0)
        assert r.node_id == "x"
        assert r.error is None
        assert r.retries_used == 0

    def test_node_without_func(self):
        """Nodes without a callable should succeed immediately."""
        pipe = Pipeline("p10", "NoFunc")
        pipe.add_node(PipelineNode(node_id="a", name="A"))
        run = self.engine.execute(pipe)
        assert run.status == PipelineStatus.SUCCESS
        assert run.nodes["a"].status == NodeStatus.SUCCESS

    def test_independent_failure_does_not_skip_siblings(self):
        """A failure in one branch should not skip an independent branch."""
        pipe = Pipeline("p11", "IndepFail")
        pipe.add_node(PipelineNode(node_id="root", name="Root", func=_noop))
        pipe.add_node(
            PipelineNode(
                node_id="fail_branch",
                name="Fail",
                func=_failing_task,
                dependencies=["root"],
                retries=0,
            )
        )
        pipe.add_node(
            PipelineNode(
                node_id="ok_branch",
                name="OK",
                func=_noop,
                dependencies=["root"],
            )
        )
        run = self.engine.execute(pipe)
        assert run.status == PipelineStatus.FAILED
        assert run.nodes["fail_branch"].status == NodeStatus.FAILED
        assert run.nodes["ok_branch"].status == NodeStatus.SUCCESS


# ═══════════════════════════════════════════════════════════════════════
# Lineage Tests
# ═══════════════════════════════════════════════════════════════════════


class TestLineageGraph:
    """Tests for the data lineage graph."""

    def setup_method(self):
        self.graph = LineageGraph()

    def _build_sample_graph(self):
        """Build: src1 -> transform -> sink1, src2 -> transform."""
        self.graph.add_node(LineageNode("src1", "source", "Source 1"))
        self.graph.add_node(LineageNode("src2", "source", "Source 2"))
        self.graph.add_node(LineageNode("tx", "transform", "Transform"))
        self.graph.add_node(LineageNode("sink1", "sink", "Sink 1"))
        self.graph.add_edge(LineageEdge("src1", "tx", "feeds_into"))
        self.graph.add_edge(LineageEdge("src2", "tx", "feeds_into"))
        self.graph.add_edge(LineageEdge("tx", "sink1", "feeds_into"))

    def test_add_node(self):
        self.graph.add_node(LineageNode("n1", "source", "N1"))
        assert "n1" in self.graph._nodes

    def test_add_edge(self):
        self.graph.add_node(LineageNode("a", "source", "A"))
        self.graph.add_node(LineageNode("b", "sink", "B"))
        self.graph.add_edge(LineageEdge("a", "b"))
        assert len(self.graph._edges) == 1

    def test_add_edge_missing_source(self):
        self.graph.add_node(LineageNode("b", "sink", "B"))
        with pytest.raises(KeyError, match="Source node"):
            self.graph.add_edge(LineageEdge("missing", "b"))

    def test_add_edge_missing_target(self):
        self.graph.add_node(LineageNode("a", "source", "A"))
        with pytest.raises(KeyError, match="Target node"):
            self.graph.add_edge(LineageEdge("a", "missing"))

    def test_get_upstream(self):
        self._build_sample_graph()
        upstream = self.graph.get_upstream("tx")
        assert set(upstream) == {"src1", "src2"}

    def test_get_downstream(self):
        self._build_sample_graph()
        downstream = self.graph.get_downstream("tx")
        assert downstream == ["sink1"]

    def test_get_impact(self):
        self._build_sample_graph()
        impact = self.graph.get_impact("src1")
        assert "tx" in impact
        assert "sink1" in impact

    def test_get_lineage(self):
        self._build_sample_graph()
        lineage = self.graph.get_lineage("sink1")
        assert "tx" in lineage
        assert "src1" in lineage
        assert "src2" in lineage

    def test_get_roots(self):
        self._build_sample_graph()
        roots = self.graph.get_roots()
        assert set(roots) == {"src1", "src2"}

    def test_get_leaves(self):
        self._build_sample_graph()
        leaves = self.graph.get_leaves()
        assert leaves == ["sink1"]

    def test_to_dict(self):
        self._build_sample_graph()
        d = self.graph.to_dict()
        assert "nodes" in d
        assert "edges" in d
        assert len(d["nodes"]) == 4
        assert len(d["edges"]) == 3

    def test_to_dict_node_fields(self):
        self.graph.add_node(
            LineageNode("x", "source", "X", metadata={"key": "val"})
        )
        d = self.graph.to_dict()
        node = d["nodes"][0]
        assert node["node_id"] == "x"
        assert node["node_type"] == "source"
        assert node["name"] == "X"
        assert node["metadata"] == {"key": "val"}

    def test_impact_no_downstream(self):
        self.graph.add_node(LineageNode("solo", "source", "Solo"))
        assert self.graph.get_impact("solo") == []

    def test_lineage_no_upstream(self):
        self.graph.add_node(LineageNode("solo", "source", "Solo"))
        assert self.graph.get_lineage("solo") == []


# ═══════════════════════════════════════════════════════════════════════
# Scheduler Tests
# ═══════════════════════════════════════════════════════════════════════


class TestPipelineScheduler:
    """Tests for the pipeline scheduler."""

    def setup_method(self):
        self.scheduler = PipelineScheduler()

    def test_add_schedule(self):
        sched = Schedule(
            schedule_id="s1",
            pipeline_id="p1",
            schedule_type=ScheduleType.ONCE,
            next_run=datetime.utcnow(),
        )
        self.scheduler.add_schedule(sched)
        assert self.scheduler.get_schedule("s1") is not None

    def test_remove_schedule(self):
        sched = Schedule(schedule_id="s1", pipeline_id="p1")
        self.scheduler.add_schedule(sched)
        self.scheduler.remove_schedule("s1")
        assert self.scheduler.get_schedule("s1") is None

    def test_remove_missing_raises(self):
        with pytest.raises(KeyError, match="not found"):
            self.scheduler.remove_schedule("nonexistent")

    def test_get_due_schedules(self):
        past = datetime.utcnow() - timedelta(minutes=5)
        future = datetime.utcnow() + timedelta(hours=1)
        s1 = Schedule(schedule_id="s1", pipeline_id="p1", next_run=past)
        s2 = Schedule(schedule_id="s2", pipeline_id="p2", next_run=future)
        self.scheduler.add_schedule(s1)
        self.scheduler.add_schedule(s2)
        due = self.scheduler.get_due_schedules()
        assert len(due) == 1
        assert due[0].schedule_id == "s1"

    def test_due_schedules_skips_disabled(self):
        past = datetime.utcnow() - timedelta(minutes=1)
        s = Schedule(schedule_id="s1", pipeline_id="p1", next_run=past, enabled=False)
        self.scheduler.add_schedule(s)
        assert self.scheduler.get_due_schedules() == []

    def test_enable_disable_schedule(self):
        s = Schedule(schedule_id="s1", pipeline_id="p1", enabled=True)
        self.scheduler.add_schedule(s)
        self.scheduler.disable_schedule("s1")
        assert self.scheduler.get_schedule("s1").enabled is False
        self.scheduler.enable_schedule("s1")
        assert self.scheduler.get_schedule("s1").enabled is True

    def test_enable_missing_raises(self):
        with pytest.raises(KeyError):
            self.scheduler.enable_schedule("nope")

    def test_disable_missing_raises(self):
        with pytest.raises(KeyError):
            self.scheduler.disable_schedule("nope")

    def test_update_next_run_once(self):
        s = Schedule(
            schedule_id="s1",
            pipeline_id="p1",
            schedule_type=ScheduleType.ONCE,
            next_run=datetime.utcnow(),
        )
        self.scheduler.add_schedule(s)
        self.scheduler.update_next_run("s1")
        updated = self.scheduler.get_schedule("s1")
        assert updated.next_run is None
        assert updated.enabled is False

    def test_update_next_run_recurring(self):
        s = Schedule(
            schedule_id="s1",
            pipeline_id="p1",
            schedule_type=ScheduleType.RECURRING,
            interval_seconds=60,
            next_run=datetime.utcnow(),
        )
        self.scheduler.add_schedule(s)
        self.scheduler.update_next_run("s1")
        updated = self.scheduler.get_schedule("s1")
        assert updated.next_run is not None
        assert updated.last_run is not None

    def test_update_next_run_cron(self):
        s = Schedule(
            schedule_id="s1",
            pipeline_id="p1",
            schedule_type=ScheduleType.CRON,
            cron_expression="0 * * * *",
            next_run=datetime.utcnow(),
        )
        self.scheduler.add_schedule(s)
        self.scheduler.update_next_run("s1")
        assert self.scheduler.get_schedule("s1").next_run is not None

    def test_market_hours_weekday(self):
        # Monday at 10:00 AM Eastern = 15:00 UTC
        monday_market = datetime(2024, 1, 8, 15, 0, 0)  # Monday
        assert PipelineScheduler.is_market_hours(monday_market) is True

    def test_market_hours_weekend(self):
        # Saturday
        saturday = datetime(2024, 1, 6, 15, 0, 0)
        assert PipelineScheduler.is_market_hours(saturday) is False

    def test_market_hours_before_open(self):
        # Monday at 8:00 AM Eastern = 13:00 UTC
        early = datetime(2024, 1, 8, 13, 0, 0)
        assert PipelineScheduler.is_market_hours(early) is False

    def test_get_schedules(self):
        self.scheduler.add_schedule(Schedule(schedule_id="s1", pipeline_id="p1"))
        self.scheduler.add_schedule(Schedule(schedule_id="s2", pipeline_id="p2"))
        assert len(self.scheduler.get_schedules()) == 2

    def test_market_hours_filter_in_due_schedules(self):
        # Set next_run to a Saturday
        sat = datetime(2024, 1, 6, 15, 0, 0)
        s = Schedule(
            schedule_id="s1",
            pipeline_id="p1",
            next_run=sat - timedelta(minutes=1),
            market_hours_only=True,
        )
        self.scheduler.add_schedule(s)
        due = self.scheduler.get_due_schedules(now=sat)
        assert len(due) == 0  # Saturday is not market hours


# ═══════════════════════════════════════════════════════════════════════
# Monitor Tests
# ═══════════════════════════════════════════════════════════════════════


class TestPipelineMonitor:
    """Tests for pipeline monitoring, SLAs, and freshness."""

    def setup_method(self):
        self.monitor = PipelineMonitor()

    def _make_run(
        self, status: PipelineStatus = PipelineStatus.SUCCESS, duration_ms: float = 100
    ) -> PipelineRun:
        now = datetime.utcnow()
        return PipelineRun(
            pipeline_id="p1",
            status=status,
            started_at=now - timedelta(milliseconds=duration_ms),
            completed_at=now,
        )

    def test_record_run(self):
        run = self._make_run()
        self.monitor.record_run("p1", run)
        m = self.monitor.get_metrics("p1")
        assert m is not None
        assert m.total_runs == 1
        assert m.successful_runs == 1

    def test_record_failed_run(self):
        run = self._make_run(PipelineStatus.FAILED)
        self.monitor.record_run("p1", run)
        m = self.monitor.get_metrics("p1")
        assert m.failed_runs == 1
        assert m.successful_runs == 0

    def test_multiple_runs_metrics(self):
        self.monitor.record_run("p1", self._make_run(PipelineStatus.SUCCESS))
        self.monitor.record_run("p1", self._make_run(PipelineStatus.SUCCESS))
        self.monitor.record_run("p1", self._make_run(PipelineStatus.FAILED))
        m = self.monitor.get_metrics("p1")
        assert m.total_runs == 3
        assert m.successful_runs == 2
        assert m.failed_runs == 1

    def test_success_rate(self):
        self.monitor.record_run("p1", self._make_run(PipelineStatus.SUCCESS))
        self.monitor.record_run("p1", self._make_run(PipelineStatus.FAILED))
        m = self.monitor.get_metrics("p1")
        assert m.success_rate == pytest.approx(0.5)

    def test_success_rate_zero_runs(self):
        m = PipelineMetrics(pipeline_id="empty")
        assert m.success_rate == 0.0

    def test_avg_duration(self):
        self.monitor.record_run("p1", self._make_run(duration_ms=100))
        self.monitor.record_run("p1", self._make_run(duration_ms=200))
        m = self.monitor.get_metrics("p1")
        assert m.avg_duration_ms > 0

    def test_get_all_metrics(self):
        self.monitor.record_run("p1", self._make_run())
        self.monitor.record_run("p2", self._make_run())
        all_m = self.monitor.get_all_metrics()
        assert "p1" in all_m
        assert "p2" in all_m

    def test_get_metrics_missing(self):
        assert self.monitor.get_metrics("nonexistent") is None

    def test_sla_check_passes(self):
        self.monitor.set_sla("p1", SLAConfig(max_failure_rate=0.5))
        self.monitor.record_run("p1", self._make_run(PipelineStatus.SUCCESS))
        result = self.monitor.check_sla("p1")
        assert result.passed is True
        assert result.violations == []

    def test_sla_check_fails_on_failure_rate(self):
        self.monitor.set_sla("p1", SLAConfig(max_failure_rate=0.1))
        self.monitor.record_run("p1", self._make_run(PipelineStatus.FAILED))
        result = self.monitor.check_sla("p1")
        assert result.passed is False
        assert len(result.violations) > 0

    def test_sla_no_config(self):
        result = self.monitor.check_sla("no-sla")
        assert result.passed is True

    def test_freshness_check_fresh(self):
        self.monitor.add_freshness_check("prices", max_staleness_seconds=3600)
        self.monitor.update_freshness("prices")
        stale = self.monitor.get_stale_sources()
        assert "prices" not in stale

    def test_freshness_check_stale(self):
        self.monitor.add_freshness_check("prices", max_staleness_seconds=1)
        self.monitor.update_freshness(
            "prices", timestamp=datetime.utcnow() - timedelta(seconds=10)
        )
        stale = self.monitor.get_stale_sources()
        assert "prices" in stale

    def test_freshness_never_updated(self):
        self.monitor.add_freshness_check("quotes", max_staleness_seconds=60)
        stale = self.monitor.get_stale_sources()
        assert "quotes" in stale

    def test_update_freshness_missing_raises(self):
        with pytest.raises(KeyError, match="not registered"):
            self.monitor.update_freshness("nonexistent")

    def test_health_score_perfect(self):
        self.monitor.set_sla("p1", SLAConfig(max_failure_rate=0.5))
        self.monitor.record_run("p1", self._make_run(PipelineStatus.SUCCESS))
        score = self.monitor.get_health_score("p1")
        assert score == pytest.approx(1.0)

    def test_health_score_no_data(self):
        assert self.monitor.get_health_score("empty") == 0.0

    def test_health_score_partial(self):
        self.monitor.set_sla("p1", SLAConfig(max_failure_rate=0.1))
        self.monitor.record_run("p1", self._make_run(PipelineStatus.SUCCESS))
        self.monitor.record_run("p1", self._make_run(PipelineStatus.FAILED))
        score = self.monitor.get_health_score("p1")
        # 50% success rate * 0.7 = 0.35, SLA failed * 0.3 = 0.0 => 0.35
        assert score == pytest.approx(0.35)

    def test_freshness_is_fresh_property(self):
        fc = FreshnessCheck(
            source_name="x",
            last_updated=datetime.utcnow(),
            max_staleness_seconds=3600,
        )
        assert fc.is_fresh is True

    def test_freshness_is_fresh_none(self):
        fc = FreshnessCheck(source_name="x", max_staleness_seconds=3600)
        assert fc.is_fresh is False

    def test_sla_result_defaults(self):
        r = SLAResult()
        assert r.passed is True
        assert r.violations == []
