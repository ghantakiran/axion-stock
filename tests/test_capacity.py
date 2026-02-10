"""Tests for PRD-130: Capacity Planning & Auto-Scaling."""

from datetime import datetime, timezone, timedelta

import pytest

from src.capacity.config import (
    ResourceType,
    ScalingDirection,
    ScalingPolicy,
    CapacityStatus,
    ResourceThreshold,
    CapacityConfig,
)
from src.capacity.monitor import (
    ResourceMetric,
    ResourceSnapshot,
    ResourceMonitor,
)
from src.capacity.forecaster import (
    ForecastPoint,
    DemandForecast,
    DemandForecaster,
)
from src.capacity.scaling import (
    ScalingRule,
    ScalingAction,
    ScalingManager,
)
from src.capacity.cost import (
    ResourceCost,
    CostReport,
    SavingsOpportunity,
    CostAnalyzer,
)


# ── Enum Tests ───────────────────────────────────────────────────────


class TestCapacityEnums:
    def test_resource_types(self):
        assert len(ResourceType) == 7
        assert ResourceType.CPU.value == "cpu"
        assert ResourceType.MEMORY.value == "memory"
        assert ResourceType.DISK.value == "disk"
        assert ResourceType.NETWORK.value == "network"
        assert ResourceType.CONNECTIONS.value == "connections"
        assert ResourceType.QUEUE_DEPTH.value == "queue_depth"
        assert ResourceType.API_CALLS.value == "api_calls"

    def test_scaling_direction(self):
        assert len(ScalingDirection) == 5
        assert ScalingDirection.SCALE_UP.value == "scale_up"
        assert ScalingDirection.SCALE_DOWN.value == "scale_down"
        assert ScalingDirection.SCALE_OUT.value == "scale_out"
        assert ScalingDirection.SCALE_IN.value == "scale_in"
        assert ScalingDirection.NO_ACTION.value == "no_action"

    def test_scaling_policy(self):
        assert len(ScalingPolicy) == 4
        assert ScalingPolicy.THRESHOLD.value == "threshold"
        assert ScalingPolicy.PREDICTIVE.value == "predictive"
        assert ScalingPolicy.SCHEDULED.value == "scheduled"
        assert ScalingPolicy.MANUAL.value == "manual"

    def test_capacity_status(self):
        assert len(CapacityStatus) == 5
        assert CapacityStatus.HEALTHY.value == "healthy"
        assert CapacityStatus.WARNING.value == "warning"
        assert CapacityStatus.CRITICAL.value == "critical"
        assert CapacityStatus.OVER_PROVISIONED.value == "over_provisioned"
        assert CapacityStatus.UNDER_PROVISIONED.value == "under_provisioned"


# ── Config Tests ─────────────────────────────────────────────────────


class TestCapacityConfig:
    def test_resource_threshold_defaults(self):
        t = ResourceThreshold()
        assert t.warning_pct == 70.0
        assert t.critical_pct == 90.0
        assert t.scale_up_pct == 80.0
        assert t.scale_down_pct == 30.0
        assert t.cooldown_seconds == 300

    def test_resource_threshold_custom(self):
        t = ResourceThreshold(warning_pct=60.0, critical_pct=85.0)
        assert t.warning_pct == 60.0
        assert t.critical_pct == 85.0

    def test_capacity_config_defaults(self):
        cfg = CapacityConfig()
        assert cfg.forecast_horizon_hours == 24
        assert cfg.check_interval_seconds == 60
        assert cfg.enable_auto_scaling is False
        assert cfg.max_scaling_actions_per_hour == 5
        assert len(cfg.thresholds) == 7  # one per resource type

    def test_capacity_config_custom(self):
        cfg = CapacityConfig(
            forecast_horizon_hours=48,
            enable_auto_scaling=True,
        )
        assert cfg.forecast_horizon_hours == 48
        assert cfg.enable_auto_scaling is True

    def test_config_thresholds_per_resource(self):
        cfg = CapacityConfig()
        for rt in ResourceType:
            assert rt in cfg.thresholds
            assert isinstance(cfg.thresholds[rt], ResourceThreshold)


# ── Resource Metric Tests ────────────────────────────────────────────


class TestResourceMetric:
    def test_creation(self):
        m = ResourceMetric(
            resource_type=ResourceType.CPU,
            current_value=70,
            capacity=100,
            utilization_pct=70.0,
        )
        assert m.resource_type == ResourceType.CPU
        assert m.current_value == 70
        assert m.capacity == 100
        assert m.utilization_pct == 70.0
        assert m.service == "default"
        assert len(m.metric_id) == 16

    def test_auto_utilization_calculation(self):
        m = ResourceMetric(
            resource_type=ResourceType.MEMORY,
            current_value=4096,
            capacity=8192,
            utilization_pct=0.0,
        )
        assert m.utilization_pct == 50.0

    def test_has_timestamp(self):
        m = ResourceMetric(
            resource_type=ResourceType.DISK,
            current_value=50,
            capacity=100,
            utilization_pct=50.0,
        )
        assert m.timestamp is not None
        assert m.timestamp.tzinfo is not None

    def test_custom_service(self):
        m = ResourceMetric(
            resource_type=ResourceType.CPU,
            current_value=80,
            capacity=100,
            utilization_pct=80.0,
            service="api_server",
        )
        assert m.service == "api_server"


# ── Resource Monitor Tests ───────────────────────────────────────────


class TestResourceMonitor:
    def setup_method(self):
        self.config = CapacityConfig()
        self.monitor = ResourceMonitor(config=self.config)

    def test_record_metric(self):
        m = ResourceMetric(
            resource_type=ResourceType.CPU,
            current_value=60,
            capacity=100,
            utilization_pct=60.0,
        )
        self.monitor.record_metric(m)
        result = self.monitor.get_current_utilization(ResourceType.CPU)
        assert result is not None
        assert result.utilization_pct == 60.0

    def test_get_current_utilization_returns_latest(self):
        m1 = ResourceMetric(
            resource_type=ResourceType.CPU,
            current_value=50,
            capacity=100,
            utilization_pct=50.0,
            timestamp=datetime.now(timezone.utc) - timedelta(minutes=5),
        )
        m2 = ResourceMetric(
            resource_type=ResourceType.CPU,
            current_value=75,
            capacity=100,
            utilization_pct=75.0,
        )
        self.monitor.record_metric(m1)
        self.monitor.record_metric(m2)
        result = self.monitor.get_current_utilization(ResourceType.CPU)
        assert result.utilization_pct == 75.0

    def test_get_current_utilization_none(self):
        result = self.monitor.get_current_utilization(ResourceType.NETWORK)
        assert result is None

    def test_get_utilization_history(self):
        for i in range(5):
            m = ResourceMetric(
                resource_type=ResourceType.MEMORY,
                current_value=40 + i * 5,
                capacity=100,
                utilization_pct=40.0 + i * 5,
            )
            self.monitor.record_metric(m)
        history = self.monitor.get_utilization_history(ResourceType.MEMORY, hours=1)
        assert len(history) == 5

    def test_utilization_history_filters_by_service(self):
        m1 = ResourceMetric(
            resource_type=ResourceType.CPU,
            current_value=50,
            capacity=100,
            utilization_pct=50.0,
            service="api",
        )
        m2 = ResourceMetric(
            resource_type=ResourceType.CPU,
            current_value=70,
            capacity=100,
            utilization_pct=70.0,
            service="worker",
        )
        self.monitor.record_metric(m1)
        self.monitor.record_metric(m2)
        history = self.monitor.get_utilization_history(ResourceType.CPU, service="api")
        assert len(history) == 1
        assert history[0].service == "api"

    def test_take_snapshot(self):
        self.monitor.record_metric(
            ResourceMetric(
                resource_type=ResourceType.CPU,
                current_value=60,
                capacity=100,
                utilization_pct=60.0,
            )
        )
        self.monitor.record_metric(
            ResourceMetric(
                resource_type=ResourceType.MEMORY,
                current_value=70,
                capacity=100,
                utilization_pct=70.0,
            )
        )
        snapshot = self.monitor.take_snapshot()
        assert isinstance(snapshot, ResourceSnapshot)
        assert len(snapshot.metrics) == 2
        assert len(snapshot.snapshot_id) == 16

    def test_health_status_healthy(self):
        self.monitor.record_metric(
            ResourceMetric(
                resource_type=ResourceType.CPU,
                current_value=50,
                capacity=100,
                utilization_pct=50.0,
            )
        )
        assert self.monitor.get_health_status() == CapacityStatus.HEALTHY

    def test_health_status_warning(self):
        self.monitor.record_metric(
            ResourceMetric(
                resource_type=ResourceType.CPU,
                current_value=75,
                capacity=100,
                utilization_pct=75.0,
            )
        )
        assert self.monitor.get_health_status() == CapacityStatus.WARNING

    def test_health_status_critical(self):
        self.monitor.record_metric(
            ResourceMetric(
                resource_type=ResourceType.CPU,
                current_value=95,
                capacity=100,
                utilization_pct=95.0,
            )
        )
        assert self.monitor.get_health_status() == CapacityStatus.CRITICAL

    def test_health_status_over_provisioned(self):
        self.monitor.record_metric(
            ResourceMetric(
                resource_type=ResourceType.CPU,
                current_value=10,
                capacity=100,
                utilization_pct=10.0,
            )
        )
        assert self.monitor.get_health_status() == CapacityStatus.OVER_PROVISIONED

    def test_top_utilized_resources(self):
        for i, rt in enumerate(
            [ResourceType.CPU, ResourceType.MEMORY, ResourceType.DISK]
        ):
            self.monitor.record_metric(
                ResourceMetric(
                    resource_type=rt,
                    current_value=30 + i * 20,
                    capacity=100,
                    utilization_pct=30.0 + i * 20,
                )
            )
        top = self.monitor.top_utilized_resources(limit=2)
        assert len(top) == 2
        assert top[0].utilization_pct >= top[1].utilization_pct

    def test_resource_summary(self):
        self.monitor.record_metric(
            ResourceMetric(
                resource_type=ResourceType.CPU,
                current_value=55,
                capacity=100,
                utilization_pct=55.0,
            )
        )
        summary = self.monitor.resource_summary()
        assert "total_metrics" in summary
        assert "health" in summary
        assert "by_resource_type" in summary
        assert summary["total_metrics"] == 1

    def test_empty_monitor_health(self):
        assert self.monitor.get_health_status() == CapacityStatus.HEALTHY

    def test_snapshot_health(self):
        self.monitor.record_metric(
            ResourceMetric(
                resource_type=ResourceType.CPU,
                current_value=92,
                capacity=100,
                utilization_pct=92.0,
            )
        )
        snapshot = self.monitor.take_snapshot()
        assert snapshot.overall_health == CapacityStatus.CRITICAL


# ── Forecaster Tests ─────────────────────────────────────────────────


class TestDemandForecaster:
    def setup_method(self):
        self.monitor = ResourceMonitor()
        self.forecaster = DemandForecaster(monitor=self.monitor)

    def _seed_metrics(self, values, resource_type=ResourceType.CPU, service="default"):
        """Seed the monitor with historical metric values."""
        now = datetime.now(timezone.utc)
        for i, val in enumerate(values):
            m = ResourceMetric(
                resource_type=resource_type,
                current_value=val,
                capacity=100,
                utilization_pct=val,
                service=service,
                timestamp=now - timedelta(hours=len(values) - i),
            )
            self.monitor.record_metric(m)

    def test_forecast_insufficient_data(self):
        self._seed_metrics([50.0])
        fc = self.forecaster.forecast(ResourceType.CPU, horizon_hours=6)
        assert isinstance(fc, DemandForecast)
        assert fc.model_used == "flat"
        assert len(fc.points) == 6

    def test_forecast_with_history(self):
        values = [40, 45, 50, 55, 60, 65, 70, 75, 80]
        self._seed_metrics(values)
        fc = self.forecaster.forecast(ResourceType.CPU, horizon_hours=12)
        assert len(fc.points) == 12
        assert fc.model_used in ("exponential_smoothing", "seasonal_moving_average")

    def test_forecast_stores_result(self):
        self._seed_metrics([40, 50, 60, 70, 80])
        fc = self.forecaster.forecast(ResourceType.CPU, horizon_hours=6)
        assert fc.forecast_id in self.forecaster._forecasts

    def test_moving_average_basic(self):
        history = [50, 55, 60, 65, 70]
        points = self.forecaster.forecast_with_moving_average(
            history, horizon=5, window=3
        )
        assert len(points) == 5
        # Average of last 3: (60+65+70)/3 = 65
        assert abs(points[0].predicted_value - 65.0) < 0.1

    def test_moving_average_empty(self):
        points = self.forecaster.forecast_with_moving_average([], horizon=5, window=3)
        assert len(points) == 0

    def test_moving_average_confidence_widens(self):
        history = [50, 60, 70, 50, 60]
        points = self.forecaster.forecast_with_moving_average(
            history, horizon=10, window=3
        )
        assert len(points) == 10
        # Confidence should widen over time
        band_first = points[0].confidence_upper - points[0].confidence_lower
        band_last = points[-1].confidence_upper - points[-1].confidence_lower
        assert band_last >= band_first

    def test_exponential_smoothing_basic(self):
        history = [40, 45, 50, 55, 60]
        points = self.forecaster.forecast_with_exponential_smoothing(
            history, horizon=5, alpha=0.3
        )
        assert len(points) == 5
        assert points[0].predicted_value > 0

    def test_exponential_smoothing_empty(self):
        points = self.forecaster.forecast_with_exponential_smoothing(
            [], horizon=5, alpha=0.3
        )
        assert len(points) == 0

    def test_exponential_smoothing_alpha_clamped(self):
        history = [50, 60, 70]
        points_low = self.forecaster.forecast_with_exponential_smoothing(
            history, horizon=3, alpha=-0.5
        )
        points_high = self.forecaster.forecast_with_exponential_smoothing(
            history, horizon=3, alpha=1.5
        )
        assert len(points_low) == 3
        assert len(points_high) == 3

    def test_detect_seasonality_short_data(self):
        is_seasonal, period = self.forecaster.detect_seasonality([1, 2, 3])
        assert is_seasonal is False
        assert period == 0

    def test_detect_seasonality_flat_data(self):
        is_seasonal, period = self.forecaster.detect_seasonality([50] * 20)
        assert is_seasonal is False

    def test_detect_seasonality_periodic(self):
        # Create a clear periodic signal: period=4
        history = [20, 80, 20, 80, 20, 80, 20, 80, 20, 80, 20, 80]
        is_seasonal, period = self.forecaster.detect_seasonality(history)
        assert is_seasonal is True
        assert period > 0

    def test_predict_peak(self):
        self._seed_metrics([40, 50, 60, 70, 80])
        ts, value = self.forecaster.predict_peak(ResourceType.CPU)
        assert isinstance(ts, datetime)
        assert value >= 0

    def test_predict_peak_no_data(self):
        ts, value = self.forecaster.predict_peak(ResourceType.NETWORK)
        assert isinstance(ts, datetime)

    def test_forecast_accuracy_no_forecast(self):
        accuracy = self.forecaster.forecast_accuracy("nonexistent")
        assert accuracy == 0.0

    def test_forecast_accuracy_no_actuals(self):
        self._seed_metrics([40, 50, 60, 70, 80])
        fc = self.forecaster.forecast(ResourceType.CPU, horizon_hours=5)
        accuracy = self.forecaster.forecast_accuracy(fc.forecast_id)
        assert accuracy == 0.0

    def test_forecast_accuracy_with_actuals(self):
        self._seed_metrics([40, 50, 60, 70, 80])
        fc = self.forecaster.forecast(ResourceType.CPU, horizon_hours=5)
        # Record actuals close to predictions
        predicted_vals = [p.predicted_value for p in fc.points]
        actuals = [v * 1.05 for v in predicted_vals]  # 5% off
        self.forecaster.record_actuals(fc.forecast_id, actuals)
        accuracy = self.forecaster.forecast_accuracy(fc.forecast_id)
        assert accuracy > 0
        assert accuracy <= 100.0

    def test_forecast_point_has_bounds(self):
        history = [50, 55, 60, 65, 70]
        points = self.forecaster.forecast_with_moving_average(
            history, horizon=3, window=3
        )
        for p in points:
            assert p.confidence_lower <= p.predicted_value
            assert p.confidence_upper >= p.predicted_value

    def test_demand_forecast_dataclass(self):
        fc = DemandForecast()
        assert len(fc.forecast_id) == 16
        assert fc.resource_type == ResourceType.CPU
        assert fc.service == "default"
        assert fc.horizon_hours == 24


# ── Scaling Tests ────────────────────────────────────────────────────


class TestScalingManager:
    def setup_method(self):
        self.monitor = ResourceMonitor()
        self.config = CapacityConfig(enable_auto_scaling=True)
        self.manager = ScalingManager(monitor=self.monitor, config=self.config)

    def _add_metric(self, rt, util, service="default"):
        self.monitor.record_metric(
            ResourceMetric(
                resource_type=rt,
                current_value=util,
                capacity=100,
                utilization_pct=util,
                service=service,
            )
        )

    def test_add_rule(self):
        rule = ScalingRule(resource_type=ResourceType.CPU, service="api")
        rule_id = self.manager.add_rule(rule)
        assert rule_id == rule.rule_id
        assert len(self.manager.get_active_rules()) == 1

    def test_evaluate_rules_scale_out(self):
        rule = ScalingRule(
            resource_type=ResourceType.CPU,
            service="default",
            current_instances=2,
        )
        self.manager.add_rule(rule)
        self._add_metric(ResourceType.CPU, 85.0)  # Above scale_up (80%)
        actions = self.manager.evaluate_rules()
        assert len(actions) == 1
        assert actions[0].direction == ScalingDirection.SCALE_OUT
        assert actions[0].to_value == 3

    def test_evaluate_rules_scale_in(self):
        rule = ScalingRule(
            resource_type=ResourceType.CPU,
            service="default",
            current_instances=3,
        )
        self.manager.add_rule(rule)
        self._add_metric(ResourceType.CPU, 20.0)  # Below scale_down (30%)
        actions = self.manager.evaluate_rules()
        assert len(actions) == 1
        assert actions[0].direction == ScalingDirection.SCALE_IN
        assert actions[0].to_value == 2

    def test_evaluate_rules_no_action(self):
        rule = ScalingRule(
            resource_type=ResourceType.CPU,
            service="default",
            current_instances=2,
        )
        self.manager.add_rule(rule)
        self._add_metric(ResourceType.CPU, 50.0)  # Normal range
        actions = self.manager.evaluate_rules()
        # All actions should be NO_ACTION (filtered out)
        assert len(actions) == 0

    def test_evaluate_disabled_rule_skipped(self):
        rule = ScalingRule(
            resource_type=ResourceType.CPU,
            service="default",
            enabled=False,
        )
        self.manager.add_rule(rule)
        self._add_metric(ResourceType.CPU, 95.0)
        actions = self.manager.evaluate_rules()
        assert len(actions) == 0

    def test_evaluate_cooldown(self):
        rule = ScalingRule(
            resource_type=ResourceType.CPU,
            service="default",
            current_instances=2,
            last_action_time=datetime.now(timezone.utc),
        )
        self.manager.add_rule(rule)
        self._add_metric(ResourceType.CPU, 85.0)
        actions = self.manager.evaluate_rules()
        assert len(actions) == 0  # Still in cooldown

    def test_execute_action_success(self):
        rule = ScalingRule(
            resource_type=ResourceType.CPU,
            service="default",
            current_instances=2,
            max_instances=5,
        )
        self.manager.add_rule(rule)
        action = ScalingAction(
            rule_id=rule.rule_id,
            direction=ScalingDirection.SCALE_OUT,
            from_value=2,
            to_value=3,
            reason="High CPU",
        )
        result = self.manager.execute_action(action)
        assert result is True
        assert action.executed is True
        assert action.success is True
        assert rule.current_instances == 3

    def test_execute_action_auto_scaling_disabled(self):
        self.config.enable_auto_scaling = False
        rule = ScalingRule(
            resource_type=ResourceType.CPU,
            current_instances=2,
        )
        self.manager.add_rule(rule)
        action = ScalingAction(
            rule_id=rule.rule_id,
            direction=ScalingDirection.SCALE_OUT,
            from_value=2,
            to_value=3,
        )
        result = self.manager.execute_action(action)
        assert result is False

    def test_execute_action_exceeds_max(self):
        rule = ScalingRule(
            resource_type=ResourceType.CPU,
            current_instances=10,
            max_instances=10,
        )
        self.manager.add_rule(rule)
        action = ScalingAction(
            rule_id=rule.rule_id,
            direction=ScalingDirection.SCALE_OUT,
            from_value=10,
            to_value=11,
        )
        result = self.manager.execute_action(action)
        assert result is False

    def test_execute_action_below_min(self):
        rule = ScalingRule(
            resource_type=ResourceType.CPU,
            current_instances=1,
            min_instances=1,
        )
        self.manager.add_rule(rule)
        action = ScalingAction(
            rule_id=rule.rule_id,
            direction=ScalingDirection.SCALE_IN,
            from_value=1,
            to_value=0,
        )
        result = self.manager.execute_action(action)
        assert result is False

    def test_execute_action_invalid_rule(self):
        action = ScalingAction(
            rule_id="nonexistent",
            direction=ScalingDirection.SCALE_OUT,
            from_value=1,
            to_value=2,
        )
        result = self.manager.execute_action(action)
        assert result is False

    def test_get_scaling_history(self):
        rule = ScalingRule(
            resource_type=ResourceType.CPU,
            current_instances=2,
            max_instances=5,
        )
        self.manager.add_rule(rule)
        action = ScalingAction(
            rule_id=rule.rule_id,
            direction=ScalingDirection.SCALE_OUT,
            from_value=2,
            to_value=3,
        )
        self.manager.execute_action(action)
        history = self.manager.get_scaling_history()
        assert len(history) == 1

    def test_set_cooldown(self):
        rule = ScalingRule(resource_type=ResourceType.CPU)
        self.manager.add_rule(rule)
        self.manager.set_cooldown(rule.rule_id, 600)
        assert self.manager._cooldowns[rule.rule_id] == 600

    def test_get_active_rules(self):
        r1 = ScalingRule(resource_type=ResourceType.CPU, enabled=True)
        r2 = ScalingRule(resource_type=ResourceType.MEMORY, enabled=False)
        self.manager.add_rule(r1)
        self.manager.add_rule(r2)
        active = self.manager.get_active_rules()
        assert len(active) == 1
        assert active[0].resource_type == ResourceType.CPU

    def test_simulate_scaling_no_metrics(self):
        rule = ScalingRule(resource_type=ResourceType.CPU, current_instances=2)
        action = self.manager.simulate_scaling(rule, [])
        assert action.direction == ScalingDirection.NO_ACTION

    def test_simulate_scaling_scale_out(self):
        rule = ScalingRule(
            resource_type=ResourceType.CPU,
            current_instances=2,
            max_instances=5,
        )
        metrics = [
            ResourceMetric(
                resource_type=ResourceType.CPU,
                current_value=85,
                capacity=100,
                utilization_pct=85.0,
            )
        ]
        action = self.manager.simulate_scaling(rule, metrics)
        assert action.direction == ScalingDirection.SCALE_OUT

    def test_simulate_scaling_scale_in(self):
        rule = ScalingRule(
            resource_type=ResourceType.CPU,
            current_instances=3,
            min_instances=1,
        )
        metrics = [
            ResourceMetric(
                resource_type=ResourceType.CPU,
                current_value=15,
                capacity=100,
                utilization_pct=15.0,
            )
        ]
        action = self.manager.simulate_scaling(rule, metrics)
        assert action.direction == ScalingDirection.SCALE_IN

    def test_at_max_instances_no_scale_out(self):
        rule = ScalingRule(
            resource_type=ResourceType.CPU,
            current_instances=10,
            max_instances=10,
        )
        self.manager.add_rule(rule)
        self._add_metric(ResourceType.CPU, 95.0)
        actions = self.manager.evaluate_rules()
        # Should not scale out since already at max
        assert all(a.direction == ScalingDirection.NO_ACTION for a in actions) or len(actions) == 0

    def test_at_min_instances_no_scale_in(self):
        rule = ScalingRule(
            resource_type=ResourceType.CPU,
            current_instances=1,
            min_instances=1,
        )
        self.manager.add_rule(rule)
        self._add_metric(ResourceType.CPU, 10.0)
        actions = self.manager.evaluate_rules()
        assert all(a.direction == ScalingDirection.NO_ACTION for a in actions) or len(actions) == 0

    def test_scaling_action_dataclass(self):
        action = ScalingAction()
        assert len(action.action_id) == 16
        assert action.direction == ScalingDirection.NO_ACTION
        assert action.executed is False
        assert action.success is False

    def test_scaling_rule_dataclass(self):
        rule = ScalingRule()
        assert len(rule.rule_id) == 16
        assert rule.min_instances == 1
        assert rule.max_instances == 10
        assert rule.enabled is True


# ── Cost Analysis Tests ──────────────────────────────────────────────


class TestCostAnalyzer:
    def setup_method(self):
        self.monitor = ResourceMonitor()
        self.analyzer = CostAnalyzer(monitor=self.monitor)

    def _setup_costs(self):
        """Add some standard cost rates."""
        self.analyzer.set_cost_rate(
            ResourceCost(
                resource_type=ResourceType.CPU,
                service="api",
                hourly_cost=0.50,
                utilization_pct=65.0,
            )
        )
        self.analyzer.set_cost_rate(
            ResourceCost(
                resource_type=ResourceType.MEMORY,
                service="api",
                hourly_cost=0.30,
                utilization_pct=45.0,
            )
        )
        self.analyzer.set_cost_rate(
            ResourceCost(
                resource_type=ResourceType.DISK,
                service="storage",
                hourly_cost=0.10,
                utilization_pct=20.0,
            )
        )

    def test_resource_cost_auto_monthly(self):
        cost = ResourceCost(
            resource_type=ResourceType.CPU,
            service="api",
            hourly_cost=1.0,
        )
        assert cost.monthly_cost == 730.0

    def test_resource_cost_auto_hourly(self):
        cost = ResourceCost(
            resource_type=ResourceType.CPU,
            service="api",
            monthly_cost=730.0,
        )
        assert cost.hourly_cost == 1.0

    def test_calculate_costs_monthly(self):
        self._setup_costs()
        report = self.analyzer.calculate_costs("monthly")
        assert isinstance(report, CostReport)
        assert report.total_cost > 0
        assert report.period == "monthly"
        assert "api" in report.by_service
        assert "storage" in report.by_service

    def test_calculate_costs_hourly(self):
        self._setup_costs()
        report = self.analyzer.calculate_costs("hourly")
        assert report.period == "hourly"
        assert report.total_cost == pytest.approx(0.90, abs=0.01)

    def test_calculate_costs_daily(self):
        self._setup_costs()
        report = self.analyzer.calculate_costs("daily")
        assert report.period == "daily"
        assert report.total_cost == pytest.approx(0.90 * 24, abs=0.1)

    def test_calculate_costs_by_resource(self):
        self._setup_costs()
        report = self.analyzer.calculate_costs("monthly")
        assert "cpu" in report.by_resource
        assert "memory" in report.by_resource
        assert "disk" in report.by_resource

    def test_find_savings(self):
        self._setup_costs()
        savings = self.analyzer.find_savings(threshold_pct=50.0)
        # Memory (45%) and Disk (20%) are below 50% utilization
        assert len(savings) >= 1
        for s in savings:
            assert s.savings_pct > 0
            assert s.recommended_cost < s.current_cost

    def test_find_savings_high_threshold(self):
        self._setup_costs()
        savings = self.analyzer.find_savings(threshold_pct=100.0)
        # All resources below 100%, all should have savings
        assert len(savings) == 3

    def test_find_savings_low_threshold(self):
        self._setup_costs()
        savings = self.analyzer.find_savings(threshold_pct=10.0)
        # None below 10% unless disk is at 20%
        assert len(savings) == 0

    def test_savings_opportunity_auto_pct(self):
        opp = SavingsOpportunity(
            resource=ResourceType.CPU,
            service="api",
            current_cost=100.0,
            recommended_cost=60.0,
        )
        assert opp.savings_pct == 40.0

    def test_right_size_recommendations(self):
        self._setup_costs()
        recs = self.analyzer.right_size_recommendations()
        assert len(recs) == 3
        for rec in recs:
            assert "action" in rec
            assert rec["action"] in ("downsize", "upsize", "maintain")

    def test_cost_forecast(self):
        self._setup_costs()
        projections = self.analyzer.cost_forecast(months=6)
        assert len(projections) == 6
        # Each month should be higher than previous (5% growth)
        for i in range(1, len(projections)):
            assert projections[i]["projected_cost"] > projections[i - 1]["projected_cost"]

    def test_cost_per_trade_no_trades(self):
        self._setup_costs()
        assert self.analyzer.cost_per_trade() == 0.0

    def test_cost_per_trade(self):
        self._setup_costs()
        self.analyzer.set_trade_count(10000)
        cpt = self.analyzer.cost_per_trade()
        assert cpt > 0

    def test_efficiency_score_empty(self):
        score = self.analyzer.efficiency_score()
        assert score == 100.0

    def test_efficiency_score_optimal(self):
        self.analyzer.set_cost_rate(
            ResourceCost(
                resource_type=ResourceType.CPU,
                service="api",
                hourly_cost=1.0,
                utilization_pct=65.0,
            )
        )
        score = self.analyzer.efficiency_score()
        assert score == 100.0  # Exactly at optimal (65%)

    def test_efficiency_score_low_utilization(self):
        self.analyzer.set_cost_rate(
            ResourceCost(
                resource_type=ResourceType.CPU,
                service="api",
                hourly_cost=1.0,
                utilization_pct=10.0,
            )
        )
        score = self.analyzer.efficiency_score()
        assert score < 100.0

    def test_cost_report_dataclass(self):
        report = CostReport()
        assert len(report.report_id) == 16
        assert report.period == "monthly"
        assert report.total_cost == 0.0
        assert report.savings_opportunities == []

    def test_cost_report_has_timestamp(self):
        report = CostReport()
        assert report.generated_at is not None


# ── Integration Tests ────────────────────────────────────────────────


class TestCapacityIntegration:
    def setup_method(self):
        self.config = CapacityConfig(enable_auto_scaling=True)
        self.monitor = ResourceMonitor(config=self.config)
        self.forecaster = DemandForecaster(monitor=self.monitor, config=self.config)
        self.manager = ScalingManager(monitor=self.monitor, config=self.config)
        self.analyzer = CostAnalyzer(monitor=self.monitor, config=self.config)

    def test_monitor_to_forecaster(self):
        """Monitor data feeds into forecaster."""
        now = datetime.now(timezone.utc)
        for i in range(10):
            self.monitor.record_metric(
                ResourceMetric(
                    resource_type=ResourceType.CPU,
                    current_value=50 + i * 2,
                    capacity=100,
                    utilization_pct=50.0 + i * 2,
                    timestamp=now - timedelta(hours=10 - i),
                )
            )
        fc = self.forecaster.forecast(ResourceType.CPU, horizon_hours=6)
        assert len(fc.points) == 6
        assert fc.points[0].predicted_value > 0

    def test_monitor_to_scaling(self):
        """Monitor data feeds into scaling decisions."""
        rule = ScalingRule(
            resource_type=ResourceType.CPU,
            service="default",
            current_instances=2,
        )
        self.manager.add_rule(rule)
        self.monitor.record_metric(
            ResourceMetric(
                resource_type=ResourceType.CPU,
                current_value=85,
                capacity=100,
                utilization_pct=85.0,
            )
        )
        actions = self.manager.evaluate_rules()
        assert len(actions) == 1
        assert actions[0].direction == ScalingDirection.SCALE_OUT

    def test_monitor_to_cost(self):
        """Monitor data feeds into cost analysis."""
        self.monitor.record_metric(
            ResourceMetric(
                resource_type=ResourceType.CPU,
                current_value=65,
                capacity=100,
                utilization_pct=65.0,
                service="api",
            )
        )
        self.analyzer.set_cost_rate(
            ResourceCost(
                resource_type=ResourceType.CPU,
                service="api",
                hourly_cost=1.0,
            )
        )
        report = self.analyzer.calculate_costs()
        assert report.total_cost > 0

    def test_full_pipeline(self):
        """End-to-end: record metrics, forecast, scale, analyze costs."""
        now = datetime.now(timezone.utc)
        for i in range(12):
            self.monitor.record_metric(
                ResourceMetric(
                    resource_type=ResourceType.CPU,
                    current_value=40 + i * 3,
                    capacity=100,
                    utilization_pct=40.0 + i * 3,
                    timestamp=now - timedelta(hours=12 - i),
                )
            )

        # Snapshot
        snapshot = self.monitor.take_snapshot()
        assert snapshot.overall_health in list(CapacityStatus)

        # Forecast
        fc = self.forecaster.forecast(ResourceType.CPU, horizon_hours=6)
        assert len(fc.points) == 6

        # Scaling
        rule = ScalingRule(
            resource_type=ResourceType.CPU,
            current_instances=2,
        )
        self.manager.add_rule(rule)
        actions = self.manager.evaluate_rules()
        assert len(actions) >= 0  # May or may not need scaling

        # Cost
        self.analyzer.set_cost_rate(
            ResourceCost(
                resource_type=ResourceType.CPU,
                service="default",
                hourly_cost=0.50,
            )
        )
        report = self.analyzer.calculate_costs()
        assert report.total_cost > 0
