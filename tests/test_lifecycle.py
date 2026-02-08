"""Tests for PRD-107: Application Lifecycle Management."""

import time

import pytest

from src.lifecycle.config import (
    AppState,
    HealthStatus,
    LifecycleConfig,
    ProbeType,
    ShutdownPhase,
)
from src.lifecycle.health import HealthCheckRegistry, HealthCheckResult, ProbeResponse
from src.lifecycle.hooks import Hook, HookRegistry, HookResult
from src.lifecycle.manager import LifecycleEvent, LifecycleManager
from src.lifecycle.signals import SignalHandler


class TestLifecycleConfig:
    """Tests for lifecycle configuration."""

    def test_default_config(self):
        config = LifecycleConfig()
        assert config.shutdown_timeout_seconds == 30
        assert config.service_name == "axion-platform"
        assert config.graceful_shutdown is True

    def test_custom_config(self):
        config = LifecycleConfig(
            shutdown_timeout_seconds=60,
            service_name="test-service",
        )
        assert config.shutdown_timeout_seconds == 60
        assert config.service_name == "test-service"

    def test_app_state_enum(self):
        assert AppState.STARTING.value == "starting"
        assert AppState.RUNNING.value == "running"
        assert AppState.SHUTTING_DOWN.value == "shutting_down"
        assert AppState.STOPPED.value == "stopped"

    def test_health_status_enum(self):
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"

    def test_shutdown_phase_enum(self):
        assert ShutdownPhase.NOT_STARTED.value == "not_started"
        assert ShutdownPhase.COMPLETED.value == "completed"

    def test_probe_type_enum(self):
        assert ProbeType.LIVENESS.value == "liveness"
        assert ProbeType.READINESS.value == "readiness"
        assert ProbeType.STARTUP.value == "startup"

    def test_default_probe_endpoints(self):
        config = LifecycleConfig()
        assert "/health/live" in config.probe_endpoints.values()
        assert "/health/ready" in config.probe_endpoints.values()

    def test_registered_services_default(self):
        config = LifecycleConfig()
        assert "database" in config.registered_services


class TestHealthCheckRegistry:
    """Tests for health check registry."""

    def test_register_check(self):
        registry = HealthCheckRegistry()
        registry.register_check("test", lambda: True)
        assert "test" in registry.get_registered_checks()

    def test_unregister_check(self):
        registry = HealthCheckRegistry()
        registry.register_check("test", lambda: True)
        assert registry.unregister_check("test") is True
        assert "test" not in registry.get_registered_checks()

    def test_unregister_nonexistent(self):
        registry = HealthCheckRegistry()
        assert registry.unregister_check("missing") is False

    def test_run_check_healthy(self):
        registry = HealthCheckRegistry()
        registry.register_check("ok", lambda: True)
        result = registry.run_check("ok")
        assert result.status == HealthStatus.HEALTHY

    def test_run_check_unhealthy(self):
        registry = HealthCheckRegistry()
        registry.register_check("bad", lambda: False)
        result = registry.run_check("bad")
        assert result.status == HealthStatus.UNHEALTHY

    def test_run_check_exception(self):
        def failing():
            raise RuntimeError("boom")
        registry = HealthCheckRegistry()
        registry.register_check("crash", failing)
        result = registry.run_check("crash")
        assert result.status == HealthStatus.UNHEALTHY
        assert "boom" in result.message

    def test_run_check_unknown(self):
        registry = HealthCheckRegistry()
        result = registry.run_check("missing")
        assert result.status == HealthStatus.UNKNOWN

    def test_run_all_checks(self):
        registry = HealthCheckRegistry()
        registry.register_check("a", lambda: True)
        registry.register_check("b", lambda: True)
        results = registry.run_all_checks()
        assert len(results) == 2

    def test_liveness_probe_alive(self):
        registry = HealthCheckRegistry()
        registry.app_state = AppState.RUNNING
        probe = registry.liveness_probe()
        assert probe.status == "healthy"

    def test_liveness_probe_stopped(self):
        registry = HealthCheckRegistry()
        registry.app_state = AppState.STOPPED
        probe = registry.liveness_probe()
        assert probe.status == "unhealthy"

    def test_readiness_probe_running(self):
        registry = HealthCheckRegistry()
        registry.app_state = AppState.RUNNING
        probe = registry.readiness_probe()
        assert probe.status == "healthy"

    def test_readiness_probe_not_running(self):
        registry = HealthCheckRegistry()
        registry.app_state = AppState.STARTING
        probe = registry.readiness_probe()
        assert probe.status == "unhealthy"

    def test_startup_probe_running(self):
        registry = HealthCheckRegistry()
        registry.app_state = AppState.RUNNING
        probe = registry.startup_probe()
        assert probe.status == "healthy"

    def test_startup_probe_starting(self):
        registry = HealthCheckRegistry()
        registry.app_state = AppState.STARTING
        probe = registry.startup_probe()
        assert probe.status == "unhealthy"

    def test_probe_response_to_dict(self):
        probe = ProbeResponse(status="healthy", uptime_seconds=100.0)
        d = probe.to_dict()
        assert d["status"] == "healthy"
        assert d["uptime_seconds"] == 100.0

    def test_uptime_seconds(self):
        registry = HealthCheckRegistry()
        time.sleep(0.01)
        assert registry.uptime_seconds >= 0.01

    def test_clear(self):
        registry = HealthCheckRegistry()
        registry.register_check("a", lambda: True)
        registry.clear()
        assert len(registry.get_registered_checks()) == 0


class TestHookRegistry:
    """Tests for startup/shutdown hooks."""

    def test_register_startup_hook(self):
        registry = HookRegistry()
        hook = registry.register_startup_hook("init", lambda: None)
        assert hook.name == "init"
        assert len(registry.startup_hooks) == 1

    def test_register_shutdown_hook(self):
        registry = HookRegistry()
        hook = registry.register_shutdown_hook("cleanup", lambda: None)
        assert hook.name == "cleanup"
        assert len(registry.shutdown_hooks) == 1

    def test_hook_priority_ordering(self):
        registry = HookRegistry()
        registry.register_startup_hook("second", lambda: None, priority=200)
        registry.register_startup_hook("first", lambda: None, priority=100)
        hooks = registry.startup_hooks
        assert hooks[0].name == "first"
        assert hooks[1].name == "second"

    def test_run_startup_hooks(self):
        executed = []
        registry = HookRegistry()
        registry.register_startup_hook("a", lambda: executed.append("a"))
        registry.register_startup_hook("b", lambda: executed.append("b"))
        results = registry.run_startup_hooks()
        assert len(results) == 2
        assert all(r.success for r in results)
        assert "a" in executed
        assert "b" in executed

    def test_run_shutdown_hooks(self):
        executed = []
        registry = HookRegistry()
        registry.register_shutdown_hook("c", lambda: executed.append("c"))
        results = registry.run_shutdown_hooks()
        assert len(results) == 1
        assert results[0].success

    def test_hook_failure(self):
        registry = HookRegistry()
        registry.register_startup_hook("fail", lambda: (_ for _ in ()).throw(RuntimeError("boom")))

        def bad():
            raise RuntimeError("boom")

        registry2 = HookRegistry()
        registry2.register_startup_hook("fail", bad)
        results = registry2.run_startup_hooks()
        assert not results[0].success
        assert "boom" in results[0].error

    def test_unregister_startup_hook(self):
        registry = HookRegistry()
        registry.register_startup_hook("x", lambda: None)
        assert registry.unregister_startup_hook("x") is True
        assert len(registry.startup_hooks) == 0

    def test_unregister_shutdown_hook(self):
        registry = HookRegistry()
        registry.register_shutdown_hook("y", lambda: None)
        assert registry.unregister_shutdown_hook("y") is True

    def test_hook_result_duration(self):
        registry = HookRegistry()
        registry.register_startup_hook("slow", lambda: time.sleep(0.01))
        results = registry.run_startup_hooks()
        assert results[0].duration_ms >= 10

    def test_get_hook_count(self):
        registry = HookRegistry()
        registry.register_startup_hook("a", lambda: None)
        registry.register_shutdown_hook("b", lambda: None)
        registry.register_shutdown_hook("c", lambda: None)
        counts = registry.get_hook_count()
        assert counts["startup"] == 1
        assert counts["shutdown"] == 2

    def test_clear(self):
        registry = HookRegistry()
        registry.register_startup_hook("a", lambda: None)
        registry.clear()
        assert len(registry.startup_hooks) == 0

    def test_disabled_hook_skipped(self):
        registry = HookRegistry()
        hook = registry.register_startup_hook("skip", lambda: None)
        hook.enabled = False
        results = registry.run_startup_hooks()
        assert len(results) == 0


class TestLifecycleManager:
    """Tests for the lifecycle manager singleton."""

    def setup_method(self):
        LifecycleManager.reset_instance()

    def test_singleton(self):
        a = LifecycleManager()
        b = LifecycleManager()
        assert a is b

    def test_reset_instance(self):
        a = LifecycleManager()
        LifecycleManager.reset_instance()
        b = LifecycleManager()
        assert a is not b

    def test_initial_state(self):
        mgr = LifecycleManager()
        assert mgr.state == AppState.STOPPED
        assert mgr.uptime_seconds == 0.0

    def test_startup(self):
        mgr = LifecycleManager(LifecycleConfig(enable_signal_handlers=False))
        results = mgr.startup()
        assert mgr.state == AppState.RUNNING
        assert mgr.is_running

    def test_shutdown(self):
        mgr = LifecycleManager(LifecycleConfig(enable_signal_handlers=False))
        mgr.startup()
        results = mgr.shutdown()
        assert mgr.state == AppState.STOPPED
        assert mgr.shutdown_phase == ShutdownPhase.COMPLETED

    def test_uptime_tracking(self):
        mgr = LifecycleManager(LifecycleConfig(enable_signal_handlers=False))
        mgr.startup()
        time.sleep(0.01)
        assert mgr.uptime_seconds >= 0.01

    def test_events_recorded(self):
        mgr = LifecycleManager(LifecycleConfig(enable_signal_handlers=False))
        mgr.startup()
        mgr.shutdown()
        assert len(mgr.events) > 0

    def test_get_status(self):
        mgr = LifecycleManager(LifecycleConfig(enable_signal_handlers=False))
        mgr.startup()
        status = mgr.get_status()
        assert status["state"] == "running"
        assert "service_name" in status

    def test_cannot_start_when_running(self):
        mgr = LifecycleManager(LifecycleConfig(enable_signal_handlers=False))
        mgr.startup()
        results = mgr.startup()
        assert results == []

    def test_cannot_shutdown_when_stopped(self):
        mgr = LifecycleManager(LifecycleConfig(enable_signal_handlers=False))
        results = mgr.shutdown()
        assert results == []


class TestSignalHandler:
    """Tests for signal handler."""

    def test_initial_state(self):
        handler = SignalHandler()
        assert handler.shutdown_requested is False
        assert handler.signal_count == 0

    def test_register_callback(self):
        handler = SignalHandler()
        handler.register_shutdown_callback(lambda: None)
        state = handler.get_state()
        assert state["callback_count"] == 1

    def test_shutdown_flag(self):
        handler = SignalHandler()
        assert handler.shutdown_requested is False
        handler._shutdown_flag.set()
        assert handler.shutdown_requested is True

    def test_reset(self):
        handler = SignalHandler()
        handler._shutdown_flag.set()
        handler._signal_count = 5
        handler.reset()
        assert handler.shutdown_requested is False
        assert handler.signal_count == 0

    def test_wait_for_shutdown_timeout(self):
        handler = SignalHandler()
        result = handler.wait_for_shutdown(timeout=0.01)
        assert result is False

    def test_get_state(self):
        handler = SignalHandler()
        state = handler.get_state()
        assert "shutdown_requested" in state
        assert "signal_count" in state
        assert "registered_signals" in state


class TestLifecycleEvent:
    """Tests for lifecycle event dataclass."""

    def test_event_creation(self):
        event = LifecycleEvent(event_type="startup", service_name="test")
        assert event.event_type == "startup"
        assert event.service_name == "test"

    def test_event_default_timestamp(self):
        event = LifecycleEvent(event_type="test", service_name="test")
        assert event.created_at is not None

    def test_sample_events_generation(self):
        events = LifecycleManager.generate_sample_events(5)
        assert len(events) == 5
