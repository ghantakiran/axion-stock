"""PRD-120: Deployment Strategies & Rollback Automation Dashboard."""

import streamlit as st
from datetime import datetime, timedelta

from src.deployment import (
    DeploymentStrategy,
    DeploymentStatus,
    DeploymentConfig,
    DeploymentOrchestrator,
    TrafficManager,
    RollbackEngine,
    DeploymentValidator,
)

try:
    st.set_page_config(page_title="Deployment", page_icon="🚀")
except st.errors.StreamlitAPIException:
    pass



def render():
    st.title("Deployment Strategies & Rollback Automation")

    tabs = st.tabs(["Deployments", "Canary Status", "Rollback History", "Validation"])

    # ── Tab 1: Deployments ───────────────────────────────────────────
    with tabs[0]:
        st.subheader("Deployment Overview")

        orchestrator = DeploymentOrchestrator()

        # Create sample deployments
        d1 = orchestrator.create_deployment(
            "v3.2.1",
            strategy=DeploymentStrategy.ROLLING,
            deployed_by="ci-pipeline",
        )
        orchestrator.start_deployment(d1.deployment_id)
        orchestrator.complete_deployment(d1.deployment_id)

        d2 = orchestrator.create_deployment(
            "v3.3.0",
            strategy=DeploymentStrategy.CANARY,
            previous_version="v3.2.1",
            deployed_by="engineer",
        )
        orchestrator.start_deployment(d2.deployment_id)

        d3 = orchestrator.create_deployment(
            "v3.1.0",
            strategy=DeploymentStrategy.BLUE_GREEN,
            deployed_by="ci-pipeline",
        )
        orchestrator.start_deployment(d3.deployment_id)
        orchestrator.fail_deployment(d3.deployment_id, "Health check timeout")

        summary = orchestrator.get_summary()
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Deployments", summary["total"])
        col2.metric("Active", summary["active"])
        col3.metric("Failed", summary["failed"])
        col4.metric("Success Rate", f"{summary['success_rate']:.0%}")

        st.subheader("Deployment History")
        history = orchestrator.get_deployment_history(limit=10)
        history_data = []
        for dep in history:
            history_data.append({
                "ID": dep.deployment_id[:8],
                "Version": dep.version,
                "Strategy": dep.strategy.value,
                "Status": dep.status.value.upper(),
                "Deployed By": dep.deployed_by,
                "Started": dep.started_at.strftime("%Y-%m-%d %H:%M") if dep.started_at else "—",
            })
        st.dataframe(history_data, use_container_width=True)

        active = orchestrator.get_active_deployment()
        if active:
            st.success(f"Active deployment: **{active.version}** ({active.strategy.value})")
        else:
            st.warning("No active deployment")

    # ── Tab 2: Canary Status ─────────────────────────────────────────
    with tabs[1]:
        st.subheader("Canary Traffic Management")

        traffic = TrafficManager()
        config = DeploymentConfig()

        # Simulate canary progression
        traffic.set_split("canary-deploy", "v3.2.1", "v3.3.0", percent_b=config.canary_initial_percent)

        col1, col2 = st.columns(2)
        split = traffic.get_split("canary-deploy")
        col1.metric("Stable (v3.2.1)", f"{split.percent_a:.1f}%")
        col2.metric("Canary (v3.3.0)", f"{split.percent_b:.1f}%")

        st.subheader("Canary Progression")
        progression_data = []
        current_split = traffic.get_split("canary-deploy")
        progression_data.append({
            "Step": "Initial",
            "Stable %": current_split.percent_a,
            "Canary %": current_split.percent_b,
        })

        steps = ["Step 1", "Step 2", "Step 3", "Step 4"]
        for step_name in steps:
            shifted = traffic.shift_traffic("canary-deploy", config.canary_increment_percent)
            progression_data.append({
                "Step": step_name,
                "Stable %": shifted.percent_a,
                "Canary %": shifted.percent_b,
            })
        st.dataframe(progression_data, use_container_width=True)

        st.subheader("Request Routing Test")
        import random
        random.seed(42)
        test_ids = [f"req-{random.randint(1000, 9999)}" for _ in range(20)]
        route_counts = {"v3.2.1": 0, "v3.3.0": 0}
        for rid in test_ids:
            version = traffic.route_request("canary-deploy", rid)
            route_counts[version] = route_counts.get(version, 0) + 1

        col1, col2 = st.columns(2)
        col1.metric("Routed to Stable", route_counts.get("v3.2.1", 0))
        col2.metric("Routed to Canary", route_counts.get("v3.3.0", 0))

        stats = traffic.get_routing_stats()
        st.write(f"**Active Splits:** {stats['total_splits']} | **Shadow Targets:** {stats['shadow_targets']}")

    # ── Tab 3: Rollback History ──────────────────────────────────────
    with tabs[2]:
        st.subheader("Rollback History")

        rollback_engine = RollbackEngine()

        # Simulate rollbacks
        r1 = rollback_engine.trigger_rollback(
            "dep-001", "v3.1.0", "v3.0.5",
            "Error rate exceeded 5% threshold",
            triggered_by="auto",
        )
        rollback_engine.execute_rollback(r1.rollback_id)

        r2 = rollback_engine.trigger_rollback(
            "dep-002", "v3.2.0", "v3.1.0",
            "Latency spike detected (950ms avg)",
            triggered_by="auto",
        )
        rollback_engine.execute_rollback(r2.rollback_id)

        r3 = rollback_engine.trigger_rollback(
            "dep-003", "v3.3.0-beta", "v3.2.1",
            "Manual rollback requested by ops",
            triggered_by="ops-engineer",
        )

        stats = rollback_engine.get_rollback_stats()
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Rollbacks", stats["total"])
        col2.metric("Successful", stats["successful"])
        col3.metric("Failed", stats["failed"])
        col4.metric("Avg Duration", f"{stats['avg_duration_seconds']:.1f}s")

        rollbacks = rollback_engine.list_rollbacks()
        rollback_data = []
        for rb in rollbacks:
            rollback_data.append({
                "ID": rb.rollback_id[:8],
                "From": rb.from_version,
                "To": rb.to_version,
                "Reason": rb.reason[:60],
                "Triggered By": rb.triggered_by,
                "Success": "Yes" if rb.success else "No",
                "Steps": len(rb.steps_completed),
            })
        st.dataframe(rollback_data, use_container_width=True)

        st.subheader("Auto-Rollback Threshold Check")
        test_scenarios = [
            ("Healthy", 0.02, 150.0),
            ("High Error Rate", 0.12, 200.0),
            ("High Latency", 0.01, 850.0),
            ("Both Violated", 0.15, 900.0),
        ]
        for label, err, lat in test_scenarios:
            should, reason = rollback_engine.should_auto_rollback(err, lat)
            status = "ROLLBACK" if should else "OK"
            color = "red" if should else "green"
            st.markdown(
                f":{color}[**{status}**] {label}: error_rate={err:.0%}, latency={lat:.0f}ms"
                + (f" — {reason}" if reason else "")
            )

    # ── Tab 4: Validation ────────────────────────────────────────────
    with tabs[3]:
        st.subheader("Deployment Validation")

        validator = DeploymentValidator()

        # Run smoke tests
        smoke_results = validator.run_smoke_tests("validation-demo")

        col1, col2, col3 = st.columns(3)
        passed = sum(1 for r in smoke_results if r.passed)
        failed = len(smoke_results) - passed
        healthy = validator.is_deployment_healthy("validation-demo")
        col1.metric("Checks Passed", passed)
        col2.metric("Checks Failed", failed)
        col3.metric("Health", "Healthy" if healthy else "Unhealthy")

        st.subheader("Smoke Test Results")
        check_data = []
        for check in smoke_results:
            check_data.append({
                "Name": check.name,
                "Type": check.check_type,
                "Status": check.status.value.upper(),
                "Threshold": f"{check.threshold}" if check.threshold else "—",
                "Actual": f"{check.actual_value:.4f}" if check.actual_value is not None else "—",
                "Passed": "Yes" if check.passed else "No",
            })
        st.dataframe(check_data, use_container_width=True)

        st.subheader("Custom Validation Checks")
        c1 = validator.add_check("custom-deploy", "api_error_rate", "error_rate", 0.05)
        c2 = validator.add_check("custom-deploy", "p99_latency", "latency", 500.0)
        c3 = validator.add_check("custom-deploy", "cpu_usage", "resource", 0.80)

        validator.run_check("custom-deploy", c1.check_id, 0.02)
        validator.run_check("custom-deploy", c2.check_id, 320.0)
        validator.run_check("custom-deploy", c3.check_id, 0.65)

        report = validator.generate_report("custom-deploy")
        status_color = "green" if report["overall"] == "healthy" else "red"
        st.markdown(f"**Overall:** :{status_color}[{report['overall'].upper()}]")
        st.write(
            f"Passed: {report['passed_count']} | "
            f"Failed: {report['failed_count']} | "
            f"Pending: {report['pending_count']}"
        )

        custom_data = []
        for ch in report["checks"]:
            custom_data.append({
                "Name": ch["name"],
                "Type": ch["check_type"],
                "Status": ch["status"].upper(),
                "Threshold": ch["threshold"],
                "Actual": f"{ch['actual_value']:.4f}" if ch["actual_value"] is not None else "—",
                "Message": ch["message"],
            })
        st.dataframe(custom_data, use_container_width=True)

        summary = validator.get_validation_summary()
        st.subheader("Validation Summary")
        st.write(
            f"**Deployments Checked:** {summary['deployments_checked']} | "
            f"**Total Checks:** {summary['total_checks']} | "
            f"**Pass Rate:** {summary['pass_rate']:.0%}"
        )



render()
