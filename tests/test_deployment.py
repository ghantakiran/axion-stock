"""Tests for PRD-120: Deployment Strategies & Rollback Automation."""

from datetime import datetime, timedelta

import pytest

from src.deployment.config import (
    DeploymentStrategy,
    DeploymentStatus,
    ValidationStatus,
    DeploymentConfig,
)
from src.deployment.orchestrator import Deployment, DeploymentOrchestrator
from src.deployment.traffic import TrafficSplit, TrafficManager
from src.deployment.rollback import RollbackAction, RollbackEngine
from src.deployment.validation import ValidationCheck, DeploymentValidator


# ── Config Tests ─────────────────────────────────────────────────────


class TestDeploymentConfig:
    def test_deployment_strategy_enum(self):
        assert len(DeploymentStrategy) == 3
        assert DeploymentStrategy.ROLLING.value == "rolling"
        assert DeploymentStrategy.BLUE_GREEN.value == "blue_green"
        assert DeploymentStrategy.CANARY.value == "canary"

    def test_deployment_status_enum(self):
        assert len(DeploymentStatus) == 6
        assert DeploymentStatus.PENDING.value == "pending"
        assert DeploymentStatus.DEPLOYING.value == "deploying"
        assert DeploymentStatus.VALIDATING.value == "validating"
        assert DeploymentStatus.ACTIVE.value == "active"
        assert DeploymentStatus.ROLLED_BACK.value == "rolled_back"
        assert DeploymentStatus.FAILED.value == "failed"

    def test_validation_status_enum(self):
        assert len(ValidationStatus) == 4
        assert ValidationStatus.PENDING.value == "pending"
        assert ValidationStatus.PASSING.value == "passing"
        assert ValidationStatus.FAILING.value == "failing"
        assert ValidationStatus.SKIPPED.value == "skipped"

    def test_default_config(self):
        cfg = DeploymentConfig()
        assert cfg.default_strategy == DeploymentStrategy.ROLLING
        assert cfg.canary_initial_percent == 5.0
        assert cfg.canary_increment_percent == 10.0
        assert cfg.validation_timeout_seconds == 300
        assert cfg.error_rate_threshold == 0.05
        assert cfg.latency_threshold_ms == 500.0
        assert cfg.auto_rollback is True
        assert cfg.smoke_test_timeout_seconds == 60
        assert cfg.min_healthy_percent == 0.9

    def test_custom_config(self):
        cfg = DeploymentConfig(
            default_strategy=DeploymentStrategy.CANARY,
            canary_initial_percent=10.0,
            error_rate_threshold=0.01,
            auto_rollback=False,
        )
        assert cfg.default_strategy == DeploymentStrategy.CANARY
        assert cfg.canary_initial_percent == 10.0
        assert cfg.error_rate_threshold == 0.01
        assert cfg.auto_rollback is False


# ── Orchestrator Tests ───────────────────────────────────────────────


class TestDeploymentOrchestrator:
    def setup_method(self):
        self.orchestrator = DeploymentOrchestrator()

    def test_create_deployment(self):
        dep = self.orchestrator.create_deployment("v1.0.0")
        assert dep.version == "v1.0.0"
        assert dep.status == DeploymentStatus.PENDING
        assert dep.strategy == DeploymentStrategy.ROLLING
        assert dep.deployed_by == "system"
        assert dep.deployment_id is not None

    def test_create_deployment_with_strategy(self):
        dep = self.orchestrator.create_deployment(
            "v2.0.0",
            strategy=DeploymentStrategy.CANARY,
            previous_version="v1.0.0",
            deployed_by="engineer",
        )
        assert dep.strategy == DeploymentStrategy.CANARY
        assert dep.previous_version == "v1.0.0"
        assert dep.deployed_by == "engineer"

    def test_start_deployment(self):
        dep = self.orchestrator.create_deployment("v1.0.0")
        started = self.orchestrator.start_deployment(dep.deployment_id)
        assert started.status == DeploymentStatus.DEPLOYING
        assert started.started_at is not None

    def test_start_deployment_invalid_status(self):
        dep = self.orchestrator.create_deployment("v1.0.0")
        self.orchestrator.start_deployment(dep.deployment_id)
        with pytest.raises(ValueError):
            self.orchestrator.start_deployment(dep.deployment_id)

    def test_complete_deployment(self):
        dep = self.orchestrator.create_deployment("v1.0.0")
        self.orchestrator.start_deployment(dep.deployment_id)
        completed = self.orchestrator.complete_deployment(dep.deployment_id)
        assert completed.status == DeploymentStatus.ACTIVE
        assert completed.completed_at is not None

    def test_complete_sets_active(self):
        dep = self.orchestrator.create_deployment("v1.0.0")
        self.orchestrator.start_deployment(dep.deployment_id)
        self.orchestrator.complete_deployment(dep.deployment_id)
        active = self.orchestrator.get_active_deployment()
        assert active is not None
        assert active.deployment_id == dep.deployment_id

    def test_fail_deployment(self):
        dep = self.orchestrator.create_deployment("v1.0.0")
        self.orchestrator.start_deployment(dep.deployment_id)
        failed = self.orchestrator.fail_deployment(
            dep.deployment_id, "Health check failed"
        )
        assert failed.status == DeploymentStatus.FAILED
        assert failed.rollback_reason == "Health check failed"
        assert failed.completed_at is not None

    def test_get_deployment(self):
        dep = self.orchestrator.create_deployment("v1.0.0")
        retrieved = self.orchestrator.get_deployment(dep.deployment_id)
        assert retrieved is not None
        assert retrieved.version == "v1.0.0"

    def test_get_deployment_not_found(self):
        result = self.orchestrator.get_deployment("nonexistent")
        assert result is None

    def test_list_deployments(self):
        self.orchestrator.create_deployment("v1.0.0")
        self.orchestrator.create_deployment("v2.0.0")
        self.orchestrator.create_deployment("v3.0.0")
        all_deps = self.orchestrator.list_deployments()
        assert len(all_deps) == 3

    def test_list_deployments_by_status(self):
        d1 = self.orchestrator.create_deployment("v1.0.0")
        self.orchestrator.start_deployment(d1.deployment_id)
        self.orchestrator.complete_deployment(d1.deployment_id)
        self.orchestrator.create_deployment("v2.0.0")

        active = self.orchestrator.list_deployments(status=DeploymentStatus.ACTIVE)
        assert len(active) == 1
        pending = self.orchestrator.list_deployments(status=DeploymentStatus.PENDING)
        assert len(pending) == 1

    def test_get_deployment_history(self):
        for i in range(5):
            d = self.orchestrator.create_deployment(f"v{i}.0.0")
            self.orchestrator.start_deployment(d.deployment_id)
        history = self.orchestrator.get_deployment_history(limit=3)
        assert len(history) == 3

    def test_get_summary(self):
        d1 = self.orchestrator.create_deployment("v1.0.0")
        self.orchestrator.start_deployment(d1.deployment_id)
        self.orchestrator.complete_deployment(d1.deployment_id)

        d2 = self.orchestrator.create_deployment("v2.0.0")
        self.orchestrator.start_deployment(d2.deployment_id)
        self.orchestrator.fail_deployment(d2.deployment_id, "Crash")

        summary = self.orchestrator.get_summary()
        assert summary["total"] == 2
        assert summary["active"] == 1
        assert summary["failed"] == 1
        assert summary["success_rate"] == 0.5

    def test_reset(self):
        self.orchestrator.create_deployment("v1.0.0")
        self.orchestrator.reset()
        assert len(self.orchestrator.list_deployments()) == 0
        assert self.orchestrator.get_active_deployment() is None


# ── Traffic Manager Tests ────────────────────────────────────────────


class TestTrafficManager:
    def setup_method(self):
        self.manager = TrafficManager()

    def test_set_split(self):
        split = self.manager.set_split("dep-1", "v1.0", "v2.0", percent_b=10.0)
        assert split.version_a == "v1.0"
        assert split.version_b == "v2.0"
        assert split.percent_a == 90.0
        assert split.percent_b == 10.0
        assert split.deployment_id == "dep-1"

    def test_set_split_clamp(self):
        split = self.manager.set_split("dep-1", "v1.0", "v2.0", percent_b=150.0)
        assert split.percent_b == 100.0
        assert split.percent_a == 0.0

        split2 = self.manager.set_split("dep-2", "v1.0", "v2.0", percent_b=-10.0)
        assert split2.percent_b == 0.0
        assert split2.percent_a == 100.0

    def test_shift_traffic(self):
        self.manager.set_split("dep-1", "v1.0", "v2.0", percent_b=10.0)
        shifted = self.manager.shift_traffic("dep-1", 15.0)
        assert shifted.percent_b == 25.0
        assert shifted.percent_a == 75.0

    def test_shift_traffic_cap_at_100(self):
        self.manager.set_split("dep-1", "v1.0", "v2.0", percent_b=95.0)
        shifted = self.manager.shift_traffic("dep-1", 20.0)
        assert shifted.percent_b == 100.0
        assert shifted.percent_a == 0.0

    def test_shift_traffic_not_found(self):
        with pytest.raises(KeyError):
            self.manager.shift_traffic("nonexistent", 10.0)

    def test_get_split(self):
        self.manager.set_split("dep-1", "v1.0", "v2.0", percent_b=20.0)
        split = self.manager.get_split("dep-1")
        assert split is not None
        assert split.percent_b == 20.0

    def test_get_split_not_found(self):
        assert self.manager.get_split("nonexistent") is None

    def test_route_request_deterministic(self):
        self.manager.set_split("dep-1", "v1.0", "v2.0", percent_b=50.0)
        # Same request_id should always route to the same version
        version1 = self.manager.route_request("dep-1", "req-abc")
        version2 = self.manager.route_request("dep-1", "req-abc")
        assert version1 == version2

    def test_route_request_distribution(self):
        self.manager.set_split("dep-1", "v1.0", "v2.0", percent_b=50.0)
        routes = {
            self.manager.route_request("dep-1", f"req-{i}")
            for i in range(100)
        }
        # With 50/50 split and 100 requests, we should see both versions
        assert "v1.0" in routes
        assert "v2.0" in routes

    def test_route_request_all_to_a(self):
        self.manager.set_split("dep-1", "v1.0", "v2.0", percent_b=0.0)
        routes = [
            self.manager.route_request("dep-1", f"req-{i}")
            for i in range(50)
        ]
        assert all(r == "v1.0" for r in routes)

    def test_enable_disable_shadow(self):
        assert self.manager.enable_shadow("dep-1", "v3.0-shadow") is True
        assert self.manager.disable_shadow("dep-1") is True
        assert self.manager.disable_shadow("dep-1") is False

    def test_drain_to_version_b(self):
        self.manager.set_split("dep-1", "v1.0", "v2.0", percent_b=50.0)
        drained = self.manager.drain_to_version("dep-1", "v2.0")
        assert drained.percent_b == 100.0
        assert drained.percent_a == 0.0

    def test_drain_to_version_a(self):
        self.manager.set_split("dep-1", "v1.0", "v2.0", percent_b=50.0)
        drained = self.manager.drain_to_version("dep-1", "v1.0")
        assert drained.percent_a == 100.0
        assert drained.percent_b == 0.0

    def test_drain_not_found(self):
        with pytest.raises(KeyError):
            self.manager.drain_to_version("nonexistent", "v1.0")

    def test_get_routing_stats(self):
        self.manager.set_split("dep-1", "v1.0", "v2.0", percent_b=25.0)
        self.manager.enable_shadow("dep-2", "v3.0")
        stats = self.manager.get_routing_stats()
        assert stats["total_splits"] == 1
        assert stats["shadow_targets"] == 1
        assert len(stats["splits"]) == 1

    def test_reset(self):
        self.manager.set_split("dep-1", "v1.0", "v2.0")
        self.manager.enable_shadow("dep-1", "v3.0")
        self.manager.reset()
        assert self.manager.get_split("dep-1") is None
        assert self.manager.get_routing_stats()["shadow_targets"] == 0


# ── Rollback Engine Tests ────────────────────────────────────────────


class TestRollbackEngine:
    def setup_method(self):
        self.engine = RollbackEngine()

    def test_trigger_rollback(self):
        action = self.engine.trigger_rollback(
            "dep-1", "v2.0", "v1.0", "High error rate"
        )
        assert action.deployment_id == "dep-1"
        assert action.from_version == "v2.0"
        assert action.to_version == "v1.0"
        assert action.reason == "High error rate"
        assert action.triggered_by == "auto"
        assert action.success is False
        assert action.completed_at is None

    def test_trigger_rollback_manual(self):
        action = self.engine.trigger_rollback(
            "dep-1", "v2.0", "v1.0", "User requested",
            triggered_by="admin",
        )
        assert action.triggered_by == "admin"

    def test_execute_rollback(self):
        action = self.engine.trigger_rollback(
            "dep-1", "v2.0", "v1.0", "Error rate spike"
        )
        executed = self.engine.execute_rollback(action.rollback_id)
        assert executed.success is True
        assert executed.completed_at is not None
        assert len(executed.steps_completed) == 4
        assert "drain_traffic" in executed.steps_completed
        assert "swap_version" in executed.steps_completed
        assert "validate_health" in executed.steps_completed
        assert "complete_rollback" in executed.steps_completed

    def test_execute_rollback_not_found(self):
        with pytest.raises(KeyError):
            self.engine.execute_rollback("nonexistent")

    def test_get_rollback(self):
        action = self.engine.trigger_rollback(
            "dep-1", "v2.0", "v1.0", "Test"
        )
        retrieved = self.engine.get_rollback(action.rollback_id)
        assert retrieved is not None
        assert retrieved.rollback_id == action.rollback_id

    def test_get_rollback_not_found(self):
        assert self.engine.get_rollback("nonexistent") is None

    def test_list_rollbacks(self):
        self.engine.trigger_rollback("dep-1", "v2.0", "v1.0", "Reason A")
        self.engine.trigger_rollback("dep-1", "v3.0", "v2.0", "Reason B")
        self.engine.trigger_rollback("dep-2", "v1.1", "v1.0", "Reason C")

        all_rollbacks = self.engine.list_rollbacks()
        assert len(all_rollbacks) == 3

        dep1_rollbacks = self.engine.list_rollbacks(deployment_id="dep-1")
        assert len(dep1_rollbacks) == 2

    def test_should_auto_rollback_error_rate(self):
        should, reason = self.engine.should_auto_rollback(0.10, 100.0)
        assert should is True
        assert "Error rate" in reason

    def test_should_auto_rollback_latency(self):
        should, reason = self.engine.should_auto_rollback(0.01, 800.0)
        assert should is True
        assert "Latency" in reason

    def test_should_auto_rollback_both(self):
        should, reason = self.engine.should_auto_rollback(0.10, 800.0)
        assert should is True
        assert "Error rate" in reason
        assert "Latency" in reason

    def test_should_not_auto_rollback_healthy(self):
        should, reason = self.engine.should_auto_rollback(0.01, 100.0)
        assert should is False
        assert reason == ""

    def test_should_not_auto_rollback_disabled(self):
        config = DeploymentConfig(auto_rollback=False)
        engine = RollbackEngine(config=config)
        should, reason = engine.should_auto_rollback(0.50, 2000.0)
        assert should is False

    def test_get_rollback_stats(self):
        a1 = self.engine.trigger_rollback("dep-1", "v2.0", "v1.0", "Reason")
        self.engine.execute_rollback(a1.rollback_id)
        a2 = self.engine.trigger_rollback("dep-2", "v3.0", "v2.0", "Reason")

        stats = self.engine.get_rollback_stats()
        assert stats["total"] == 2
        assert stats["successful"] == 1
        assert stats["failed"] == 1

    def test_reset(self):
        self.engine.trigger_rollback("dep-1", "v2.0", "v1.0", "Test")
        self.engine.reset()
        assert len(self.engine.list_rollbacks()) == 0


# ── Validator Tests ──────────────────────────────────────────────────


class TestDeploymentValidator:
    def setup_method(self):
        self.validator = DeploymentValidator()

    def test_add_check(self):
        check = self.validator.add_check(
            "dep-1", "error_rate", "error_rate", threshold=0.05
        )
        assert check.name == "error_rate"
        assert check.check_type == "error_rate"
        assert check.threshold == 0.05
        assert check.status == ValidationStatus.PENDING

    def test_run_check_pass(self):
        check = self.validator.add_check(
            "dep-1", "error_rate", "error_rate", threshold=0.05
        )
        result = self.validator.run_check("dep-1", check.check_id, 0.02)
        assert result.passed is True
        assert result.status == ValidationStatus.PASSING
        assert result.actual_value == 0.02

    def test_run_check_fail(self):
        check = self.validator.add_check(
            "dep-1", "error_rate", "error_rate", threshold=0.05
        )
        result = self.validator.run_check("dep-1", check.check_id, 0.10)
        assert result.passed is False
        assert result.status == ValidationStatus.FAILING

    def test_run_check_latency_pass(self):
        check = self.validator.add_check(
            "dep-1", "response_time", "latency", threshold=500.0
        )
        result = self.validator.run_check("dep-1", check.check_id, 200.0)
        assert result.passed is True

    def test_run_check_latency_fail(self):
        check = self.validator.add_check(
            "dep-1", "response_time", "latency", threshold=500.0
        )
        result = self.validator.run_check("dep-1", check.check_id, 800.0)
        assert result.passed is False

    def test_run_check_higher_is_better(self):
        check = self.validator.add_check(
            "dep-1", "uptime", "uptime", threshold=0.99
        )
        result = self.validator.run_check("dep-1", check.check_id, 0.999)
        assert result.passed is True

    def test_run_check_no_threshold(self):
        check = self.validator.add_check("dep-1", "info_metric", "info")
        result = self.validator.run_check("dep-1", check.check_id, 42.0)
        assert result.passed is True
        assert result.actual_value == 42.0

    def test_run_check_not_found(self):
        with pytest.raises(KeyError):
            self.validator.run_check("dep-1", "nonexistent", 1.0)

    def test_run_smoke_tests(self):
        results = self.validator.run_smoke_tests("dep-1")
        assert len(results) == 5
        assert all(r.status != ValidationStatus.PENDING for r in results)
        # All smoke tests should have been executed
        assert all(r.executed_at is not None for r in results)

    def test_get_checks(self):
        self.validator.add_check("dep-1", "check_a", "error_rate", 0.05)
        self.validator.add_check("dep-1", "check_b", "latency", 500.0)
        checks = self.validator.get_checks("dep-1")
        assert len(checks) == 2

    def test_get_checks_empty(self):
        checks = self.validator.get_checks("nonexistent")
        assert checks == []

    def test_is_deployment_healthy_no_checks(self):
        assert self.validator.is_deployment_healthy("dep-1") is True

    def test_is_deployment_healthy_all_pass(self):
        c1 = self.validator.add_check(
            "dep-1", "err", "error_rate", threshold=0.05
        )
        c2 = self.validator.add_check(
            "dep-1", "lat", "latency", threshold=500.0
        )
        self.validator.run_check("dep-1", c1.check_id, 0.01)
        self.validator.run_check("dep-1", c2.check_id, 100.0)
        assert self.validator.is_deployment_healthy("dep-1") is True

    def test_is_deployment_unhealthy(self):
        c1 = self.validator.add_check(
            "dep-1", "err", "error_rate", threshold=0.05
        )
        self.validator.run_check("dep-1", c1.check_id, 0.20)
        assert self.validator.is_deployment_healthy("dep-1") is False

    def test_generate_report(self):
        c1 = self.validator.add_check(
            "dep-1", "err", "error_rate", threshold=0.05
        )
        c2 = self.validator.add_check(
            "dep-1", "lat", "latency", threshold=500.0
        )
        self.validator.run_check("dep-1", c1.check_id, 0.01)
        self.validator.run_check("dep-1", c2.check_id, 800.0)

        report = self.validator.generate_report("dep-1")
        assert report["deployment_id"] == "dep-1"
        assert report["passed_count"] == 1
        assert report["failed_count"] == 1
        assert report["overall"] == "unhealthy"
        assert len(report["checks"]) == 2

    def test_generate_report_healthy(self):
        c1 = self.validator.add_check(
            "dep-1", "err", "error_rate", threshold=0.05
        )
        self.validator.run_check("dep-1", c1.check_id, 0.01)
        report = self.validator.generate_report("dep-1")
        assert report["overall"] == "healthy"

    def test_get_validation_summary(self):
        c1 = self.validator.add_check("dep-1", "err", "error_rate", 0.05)
        c2 = self.validator.add_check("dep-1", "lat", "latency", 500.0)
        c3 = self.validator.add_check("dep-2", "err", "error_rate", 0.05)
        self.validator.run_check("dep-1", c1.check_id, 0.01)
        self.validator.run_check("dep-1", c2.check_id, 100.0)
        self.validator.run_check("dep-2", c3.check_id, 0.10)

        summary = self.validator.get_validation_summary()
        assert summary["deployments_checked"] == 2
        assert summary["total_checks"] == 3
        assert summary["total_passed"] == 2
        assert summary["total_failed"] == 1

    def test_reset(self):
        self.validator.add_check("dep-1", "check", "error_rate", 0.05)
        self.validator.reset()
        assert self.validator.get_checks("dep-1") == []
        summary = self.validator.get_validation_summary()
        assert summary["total_checks"] == 0
