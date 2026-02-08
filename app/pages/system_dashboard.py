"""PRD-100: System Dashboard."""

import streamlit as st
from datetime import datetime

from src.system_dashboard import (
    HealthChecker,
    MetricsCollector,
    SystemAlertManager,
    SystemMetrics,
)


def render():
    st.title("System Dashboard")

    tabs = st.tabs(["Overview", "Services", "Metrics", "Alerts"])

    # Generate sample data
    snapshot = HealthChecker.generate_sample_snapshot()
    checker = HealthChecker()
    summary = checker.get_summary(snapshot)
    collector = MetricsCollector.generate_sample_history(60)

    # ── Tab 1: Overview ──────────────────────────────────────────────
    with tabs[0]:
        status_color = {"healthy": "green", "degraded": "orange", "down": "red"}
        st.markdown(
            f"### System Status: :{status_color.get(summary.overall_status, 'gray')}"
            f"[{summary.overall_status.upper()}]"
        )

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Services", f"{summary.healthy_services}/{summary.total_services} Healthy")
        col2.metric("CPU", f"{summary.cpu_usage:.0%}")
        col3.metric("Memory", f"{summary.memory_usage:.0%}")
        col4.metric("Disk", f"{summary.disk_usage:.0%}")

        col5, col6, col7, col8 = st.columns(4)
        col5.metric("Requests/min", f"{summary.requests_per_minute:.0f}")
        col6.metric("Avg Response", f"{summary.avg_response_time_ms:.0f}ms")
        col7.metric("Cache Hit Rate", f"{summary.cache_hit_rate:.0%}")
        col8.metric("Stale Sources", summary.stale_data_sources)

        # Data freshness
        st.subheader("Data Freshness")
        fresh_data = []
        for df in snapshot.data_freshness:
            fresh_data.append({
                "Source": df.source_name,
                "Status": df.status.upper(),
                "Last Update": df.last_update.strftime("%H:%M:%S") if df.last_update else "Never",
                "Staleness": f"{df.staleness_minutes:.0f} min" if df.staleness_minutes > 0 else "N/A",
            })
        st.dataframe(fresh_data, use_container_width=True)

    # ── Tab 2: Services ──────────────────────────────────────────────
    with tabs[1]:
        st.subheader("Service Health")

        for svc in snapshot.services:
            color = {"healthy": "green", "degraded": "orange", "down": "red"}.get(svc.status, "gray")
            st.markdown(
                f":{color}[**{svc.service_name.upper()}**] — "
                f"{svc.response_time_ms:.0f}ms | "
                f"Errors: {svc.error_rate:.2%} | "
                f"Uptime: {svc.uptime_pct:.0f}%"
            )

    # ── Tab 3: Metrics ───────────────────────────────────────────────
    with tabs[2]:
        st.subheader("System Metrics (Last 60 Minutes)")

        avgs = collector.get_averages()
        col1, col2, col3 = st.columns(3)
        col1.metric("Avg CPU", f"{avgs.get('avg_cpu', 0):.0%}")
        col2.metric("Avg Memory", f"{avgs.get('avg_memory', 0):.0%}")
        col3.metric("Avg Response", f"{avgs.get('avg_response_time_ms', 0):.0f}ms")

        col4, col5, col6 = st.columns(3)
        col4.metric("Peak CPU", f"{avgs.get('max_cpu', 0):.0%}")
        col5.metric("Peak Memory", f"{avgs.get('max_memory', 0):.0%}")
        col6.metric("Total Errors", int(avgs.get("total_errors", 0)))

        st.subheader("Response Time Percentiles")
        pcts = collector.get_percentiles("avg_response_time_ms")
        pct_data = {f"P{k.replace('p', '')}": f"{v:.0f}ms" for k, v in pcts.items()}
        st.write(pct_data)

    # ── Tab 4: Alerts ────────────────────────────────────────────────
    with tabs[3]:
        st.subheader("System Alerts")

        alert_mgr = SystemAlertManager()
        # Generate some sample alerts
        alert_mgr.evaluate_metrics(SystemMetrics(cpu_usage=0.85, disk_usage=0.90))
        alert_mgr.evaluate_snapshot(snapshot)

        active = alert_mgr.get_active_alerts()
        counts = alert_mgr.get_alert_counts()

        col1, col2, col3 = st.columns(3)
        col1.metric("Active Alerts", len(active))
        col2.metric("Critical", counts.get("critical", 0))
        col3.metric("Warnings", counts.get("warning", 0))

        for alert in active:
            color = {"critical": "red", "warning": "orange", "down": "red", "healthy": "green"}
            st.markdown(
                f":{color.get(alert.level, 'gray')}[**{alert.level.upper()}**] | "
                f"{alert.service} | {alert.message}"
            )


if __name__ == "__main__":
    render()
