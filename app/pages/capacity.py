"""PRD-130: Capacity Planning & Auto-Scaling Dashboard."""

import streamlit as st
from datetime import datetime, timezone, timedelta
import random

from src.capacity import (
    ResourceType,
    ScalingDirection,
    ScalingPolicy,
    CapacityStatus,
    CapacityConfig,
    ResourceThreshold,
    ResourceMetric,
    ResourceSnapshot,
    ResourceMonitor,
    ForecastPoint,
    DemandForecast,
    DemandForecaster,
    ScalingRule,
    ScalingAction,
    ScalingManager,
    ResourceCost,
    CostReport,
    SavingsOpportunity,
    CostAnalyzer,
)


def _generate_sample_data():
    """Generate sample data for the dashboard."""
    config = CapacityConfig(enable_auto_scaling=True)
    monitor = ResourceMonitor(config=config)

    now = datetime.now(timezone.utc)
    services = ["api", "worker", "database", "cache"]
    resource_types = [ResourceType.CPU, ResourceType.MEMORY, ResourceType.DISK, ResourceType.NETWORK]

    # Seed historical metrics
    for hour in range(48):
        ts = now - timedelta(hours=48 - hour)
        for svc in services:
            for rt in resource_types:
                base = random.uniform(30, 70)
                noise = random.uniform(-10, 10)
                val = max(5, min(95, base + noise))
                monitor.record_metric(
                    ResourceMetric(
                        resource_type=rt,
                        current_value=val,
                        capacity=100,
                        utilization_pct=val,
                        service=svc,
                        timestamp=ts,
                    )
                )

    forecaster = DemandForecaster(monitor=monitor, config=config)
    manager = ScalingManager(monitor=monitor, config=config)
    analyzer = CostAnalyzer(monitor=monitor, config=config)

    # Add scaling rules
    for svc in services:
        rule = ScalingRule(
            resource_type=ResourceType.CPU,
            service=svc,
            policy=ScalingPolicy.THRESHOLD,
            current_instances=random.randint(2, 5),
        )
        manager.add_rule(rule)

    # Add cost rates
    cost_map = {
        ResourceType.CPU: 0.50,
        ResourceType.MEMORY: 0.30,
        ResourceType.DISK: 0.10,
        ResourceType.NETWORK: 0.05,
    }
    for svc in services:
        for rt, rate in cost_map.items():
            analyzer.set_cost_rate(
                ResourceCost(
                    resource_type=rt,
                    service=svc,
                    hourly_cost=rate * random.uniform(0.8, 1.2),
                )
            )

    analyzer.set_trade_count(50000)

    return monitor, forecaster, manager, analyzer, services, resource_types


def render():
    st.title("Capacity Planning & Auto-Scaling")

    monitor, forecaster, manager, analyzer, services, resource_types = _generate_sample_data()

    tabs = st.tabs(["Resource Overview", "Demand Forecast", "Scaling Policies", "Cost Analysis"])

    # ── Tab 1: Resource Overview ─────────────────────────────────────
    with tabs[0]:
        st.subheader("Resource Utilization Overview")

        snapshot = monitor.take_snapshot()
        status_colors = {
            CapacityStatus.HEALTHY: "green",
            CapacityStatus.WARNING: "orange",
            CapacityStatus.CRITICAL: "red",
            CapacityStatus.OVER_PROVISIONED: "blue",
            CapacityStatus.UNDER_PROVISIONED: "violet",
        }
        color = status_colors.get(snapshot.overall_health, "gray")
        st.markdown(f"### System Health: :{color}[{snapshot.overall_health.value.upper()}]")

        # Summary metrics
        summary = monitor.resource_summary()
        col1, col2, col3 = st.columns(3)
        col1.metric("Monitored Resources", summary["total_metrics"])
        col2.metric("Health Status", summary["health"].upper())
        rt_data = summary.get("by_resource_type", {})
        avg_utils = [v.get("avg_utilization_pct", 0) for v in rt_data.values()]
        col3.metric("Avg Utilization", f"{sum(avg_utils) / len(avg_utils):.1f}%" if avg_utils else "N/A")

        # Top utilized resources
        st.subheader("Top Utilized Resources")
        top = monitor.top_utilized_resources(limit=10)
        top_data = []
        for m in top:
            top_data.append({
                "Resource": m.resource_type.value.upper(),
                "Service": m.service,
                "Utilization": f"{m.utilization_pct:.1f}%",
                "Value": f"{m.current_value:.1f} / {m.capacity:.1f}",
            })
        if top_data:
            st.dataframe(top_data, use_container_width=True)

        # Utilization by resource type
        st.subheader("By Resource Type")
        for rt_name, info in rt_data.items():
            st.write(f"**{rt_name.upper()}** - Avg: {info['avg_utilization_pct']:.1f}%, Max: {info['max_utilization_pct']:.1f}%")
            st.progress(min(info["avg_utilization_pct"] / 100.0, 1.0))

    # ── Tab 2: Demand Forecast ───────────────────────────────────────
    with tabs[1]:
        st.subheader("Demand Forecast")

        sel_rt = st.selectbox("Resource Type", [rt.value for rt in resource_types], key="fc_rt")
        sel_svc = st.selectbox("Service", services, key="fc_svc")
        horizon = st.slider("Forecast Horizon (hours)", 6, 48, 24, key="fc_horizon")

        rt_enum = ResourceType(sel_rt)
        fc = forecaster.forecast(rt_enum, sel_svc, horizon_hours=horizon)

        st.write(f"**Model Used:** {fc.model_used}")
        st.write(f"**Points Generated:** {len(fc.points)}")

        if fc.points:
            chart_data = []
            for p in fc.points:
                chart_data.append({
                    "Hour": p.timestamp.strftime("%H:%M"),
                    "Predicted": p.predicted_value,
                    "Lower": p.confidence_lower,
                    "Upper": p.confidence_upper,
                })
            st.dataframe(chart_data, use_container_width=True)

        # Seasonality detection
        st.subheader("Seasonality Detection")
        history = monitor.get_utilization_history(rt_enum, sel_svc, hours=48)
        values = [m.utilization_pct for m in history]
        if values:
            is_seasonal, period = forecaster.detect_seasonality(values)
            st.write(f"**Seasonal Pattern Detected:** {'Yes' if is_seasonal else 'No'}")
            if is_seasonal:
                st.write(f"**Period:** {period} data points")

        # Peak prediction
        st.subheader("Peak Prediction")
        peak_ts, peak_val = forecaster.predict_peak(rt_enum, sel_svc)
        st.write(f"**Next Peak:** {peak_ts.strftime('%Y-%m-%d %H:%M')} UTC at {peak_val:.1f}%")

    # ── Tab 3: Scaling Policies ──────────────────────────────────────
    with tabs[2]:
        st.subheader("Active Scaling Rules")

        rules = manager.get_active_rules()
        rule_data = []
        for r in rules:
            rule_data.append({
                "Rule ID": r.rule_id[:8] + "...",
                "Resource": r.resource_type.value.upper(),
                "Service": r.service,
                "Policy": r.policy.value,
                "Instances": f"{r.current_instances} ({r.min_instances}-{r.max_instances})",
                "Scale Up": f"{r.thresholds.scale_up_pct}%",
                "Scale Down": f"{r.thresholds.scale_down_pct}%",
            })
        if rule_data:
            st.dataframe(rule_data, use_container_width=True)

        # Evaluate rules
        st.subheader("Recommended Actions")
        actions = manager.evaluate_rules()
        if actions:
            for a in actions:
                icon = "^" if "OUT" in a.direction.value.upper() or "UP" in a.direction.value.upper() else "v"
                st.write(f"**{icon} {a.direction.value}** | {a.from_value} -> {a.to_value} | {a.reason}")
        else:
            st.info("No scaling actions needed at this time.")

        # Scaling history
        st.subheader("Scaling History (24h)")
        history = manager.get_scaling_history(hours=24)
        if history:
            hist_data = []
            for a in history:
                hist_data.append({
                    "Time": a.timestamp.strftime("%H:%M"),
                    "Direction": a.direction.value,
                    "From": a.from_value,
                    "To": a.to_value,
                    "Success": "Yes" if a.success else "No",
                })
            st.dataframe(hist_data, use_container_width=True)
        else:
            st.info("No scaling events in the last 24 hours.")

    # ── Tab 4: Cost Analysis ─────────────────────────────────────────
    with tabs[3]:
        st.subheader("Cost Analysis")

        report = analyzer.calculate_costs("monthly")
        col1, col2, col3 = st.columns(3)
        col1.metric("Monthly Cost", f"${report.total_cost:,.2f}")
        col2.metric("Cost per Trade", f"${analyzer.cost_per_trade():.4f}")
        col3.metric("Efficiency Score", f"{analyzer.efficiency_score():.1f}/100")

        # By service
        st.subheader("Cost by Service")
        svc_data = []
        for svc, cost in sorted(report.by_service.items(), key=lambda x: -x[1]):
            svc_data.append({"Service": svc, "Monthly Cost": f"${cost:,.2f}"})
        if svc_data:
            st.dataframe(svc_data, use_container_width=True)

        # By resource
        st.subheader("Cost by Resource Type")
        res_data = []
        for res, cost in sorted(report.by_resource.items(), key=lambda x: -x[1]):
            res_data.append({"Resource": res.upper(), "Monthly Cost": f"${cost:,.2f}"})
        if res_data:
            st.dataframe(res_data, use_container_width=True)

        # Savings
        st.subheader("Savings Opportunities")
        savings = report.savings_opportunities
        if savings:
            total_savings = sum(s.current_cost - s.recommended_cost for s in savings)
            st.write(f"**Total Potential Monthly Savings: ${total_savings:,.2f}**")
            sav_data = []
            for s in savings:
                sav_data.append({
                    "Resource": s.resource.value.upper(),
                    "Service": s.service,
                    "Current": f"${s.current_cost:,.2f}",
                    "Recommended": f"${s.recommended_cost:,.2f}",
                    "Savings": f"{s.savings_pct:.1f}%",
                    "Action": s.action,
                })
            st.dataframe(sav_data, use_container_width=True)
        else:
            st.info("No savings opportunities identified.")

        # Cost forecast
        st.subheader("Cost Forecast (6 months)")
        projections = analyzer.cost_forecast(months=6)
        proj_data = []
        for p in projections:
            proj_data.append({
                "Month": p["month"],
                "Projected Cost": f"${p['projected_cost']:,.2f}",
                "Growth": f"+{p['growth_pct']:.1f}%",
            })
        if proj_data:
            st.dataframe(proj_data, use_container_width=True)


if __name__ == "__main__":
    render()
