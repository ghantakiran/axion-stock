"""PRD-117: Performance Profiling & Query Optimization Dashboard."""

import streamlit as st
from datetime import datetime, timedelta

from src.profiling import (
    QueryProfiler,
    PerformanceAnalyzer,
    IndexAdvisor,
    ConnectionMonitor,
    ConnectionStats,
    ProfilingConfig,
    QuerySeverity,
    IndexStatus,
)

try:
    st.set_page_config(page_title="Performance Profiling", page_icon="\U0001f4ca")
except st.errors.StreamlitAPIException:
    pass



def render():
    st.title("\U0001f4ca Performance Profiling & Query Optimization")

    tabs = st.tabs(["Query Profiler", "Performance", "Index Advisor", "Connections"])

    # ── Setup sample data ─────────────────────────────────────────────
    profiler = QueryProfiler()
    sample_queries = [
        ("SELECT * FROM orders WHERE user_id = 42 AND status = 'active'", 150.0),
        ("SELECT * FROM orders WHERE user_id = 99 AND status = 'pending'", 180.0),
        ("SELECT * FROM trades WHERE symbol = 'AAPL' AND date > '2024-01-01'", 320.0),
        ("SELECT * FROM trades WHERE symbol = 'MSFT' AND date > '2024-06-01'", 280.0),
        ("SELECT p.*, f.* FROM portfolios p JOIN factors f ON p.id = f.portfolio_id", 1200.0),
        ("SELECT p.*, f.* FROM portfolios p JOIN factors f ON p.id = f.portfolio_id", 1500.0),
        ("SELECT * FROM price_bars WHERE instrument_id = 1 ORDER BY date DESC LIMIT 100", 45.0),
        ("SELECT * FROM price_bars WHERE instrument_id = 2 ORDER BY date DESC LIMIT 100", 52.0),
        ("UPDATE positions SET quantity = 500 WHERE account_id = 7", 80.0),
        ("SELECT * FROM risk_metrics WHERE portfolio_id = 3", 5500.0),
    ]
    for query, duration in sample_queries:
        profiler.record_query(query, duration)
    # Add more to build up call counts
    for i in range(15):
        profiler.record_query(
            f"SELECT * FROM orders WHERE user_id = {i}", 100.0 + i * 20
        )

    analyzer = PerformanceAnalyzer()
    for i in range(10):
        analyzer.take_snapshot(
            memory_mb=512 + i * 30,
            cpu_pct=35 + i * 3,
            connections=5 + i,
        )

    advisor = IndexAdvisor()
    advisor.analyze_query_patterns(profiler)
    advisor.report_unused_index("idx_old_status", "orders", "No queries reference this index in 30 days")

    monitor = ConnectionMonitor()
    for active in [5, 6, 7, 8, 7, 8, 9, 10, 9, 8]:
        monitor.record_stats(ConnectionStats(pool_size=20, active=active, idle=20 - active))
    monitor.track_long_query("SELECT * FROM huge_analytics_view", user="reporting_svc")

    # ── Tab 1: Query Profiler ─────────────────────────────────────────
    with tabs[0]:
        st.subheader("Query Performance Overview")

        stats = profiler.get_query_stats()
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Queries", stats["total_queries"])
        col2.metric("Unique Patterns", stats["unique_fingerprints"])
        col3.metric("Avg Duration", f"{stats['avg_duration_ms']:.1f}ms")
        col4.metric("Total Time", f"{stats['total_duration_ms']:.0f}ms")

        st.subheader("Top Queries by Total Duration")
        top = profiler.get_top_queries(n=10)
        top_data = []
        for fp in top:
            severity_color = {
                QuerySeverity.NORMAL: "green",
                QuerySeverity.SLOW: "orange",
                QuerySeverity.CRITICAL: "red",
            }
            top_data.append({
                "Query": fp.query_template[:80],
                "Calls": fp.call_count,
                "Avg (ms)": f"{fp.avg_duration_ms:.1f}",
                "Max (ms)": f"{fp.max_duration_ms:.1f}",
                "Total (ms)": f"{fp.total_duration_ms:.1f}",
                "Severity": fp.severity.value.upper(),
            })
        st.dataframe(top_data, use_container_width=True)

        st.subheader("Slow Queries")
        slow = profiler.get_slow_queries()
        if slow:
            for fp in slow:
                st.warning(
                    f"**{fp.severity.value.upper()}** | "
                    f"{fp.query_template[:60]}... | "
                    f"Avg: {fp.avg_duration_ms:.0f}ms | "
                    f"Calls: {fp.call_count}"
                )
        else:
            st.success("No slow queries detected.")

        st.subheader("Regression Detection")
        regressions = profiler.detect_regressions()
        if regressions:
            for fp in regressions:
                st.error(f"Regression: {fp.query_template[:60]}... (avg now {fp.avg_duration_ms:.0f}ms)")
        else:
            st.success("No query regressions detected.")

    # ── Tab 2: Performance ────────────────────────────────────────────
    with tabs[1]:
        st.subheader("Performance Snapshots")

        snaps = analyzer.get_snapshots(limit=5)
        if snaps:
            col1, col2, col3 = st.columns(3)
            latest = snaps[0]
            col1.metric("Memory", f"{latest.memory_usage_mb:.0f} MB")
            col2.metric("CPU", f"{latest.cpu_percent:.1f}%")
            col3.metric("Connections", latest.active_connections)

        st.subheader("Memory Trend")
        trend = analyzer.get_memory_trend()
        if trend:
            st.line_chart(trend)

        if len(snaps) >= 2:
            st.subheader("Snapshot Comparison (Latest vs First)")
            diff = analyzer.compare_snapshots(snaps[-1].snapshot_id, snaps[0].snapshot_id)
            col1, col2, col3 = st.columns(3)
            col1.metric("Memory Change", f"{diff.get('memory_change_mb', 0):.0f} MB")
            col2.metric("CPU Change", f"{diff.get('cpu_change_pct', 0):.1f}%")
            col3.metric("Connection Change", diff.get("connection_change", 0))

        st.subheader("N+1 Query Detection")
        n1_detections = analyzer.get_n1_detections()
        if n1_detections:
            for det in n1_detections:
                st.warning(
                    f"N+1 pattern: {det['template'][:60]}... "
                    f"({det['count_in_window']} calls in 100ms window)"
                )
        else:
            st.success("No N+1 query patterns detected.")

    # ── Tab 3: Index Advisor ──────────────────────────────────────────
    with tabs[2]:
        st.subheader("Index Recommendations")

        summary = advisor.get_summary()
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Recommendations", summary["total_recommendations"])
        col2.metric("Unused Indexes", summary["unused_indexes"])
        status_str = ", ".join(f"{k}: {v}" for k, v in summary.get("by_status", {}).items())
        col3.metric("By Status", status_str or "None")

        recs = advisor.get_recommendations()
        if recs:
            rec_data = []
            for r in recs:
                rec_data.append({
                    "Table": r.table_name,
                    "Columns": ", ".join(r.columns),
                    "Type": r.index_type,
                    "Impact": r.estimated_impact,
                    "Status": r.status.value.upper(),
                    "Rationale": r.rationale[:60],
                })
            st.dataframe(rec_data, use_container_width=True)

        st.subheader("Unused Indexes")
        unused = advisor.get_unused_indexes()
        if unused:
            for idx in unused:
                st.info(
                    f"**{idx['index_name']}** on `{idx['table_name']}` - "
                    f"{idx['reason']}"
                )
        else:
            st.success("No unused indexes reported.")

    # ── Tab 4: Connections ────────────────────────────────────────────
    with tabs[3]:
        st.subheader("Connection Pool Status")

        current = monitor.get_current_stats()
        if current:
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Pool Size", current.pool_size)
            col2.metric("Active", current.active)
            col3.metric("Idle", current.idle)
            col4.metric("Utilization", f"{current.utilization:.0%}")

        health = monitor.get_pool_health()
        status_color = {"healthy": "green", "warning": "orange", "critical": "red"}
        st.markdown(
            f"Pool Health: :{status_color.get(health['status'], 'gray')}"
            f"[**{health['status'].upper()}**]"
        )

        st.subheader("Utilization Trend")
        util_trend = monitor.get_utilization_trend()
        if util_trend:
            st.line_chart(util_trend)

        st.subheader("Pool Exhaustion Check")
        exhaustion = monitor.detect_pool_exhaustion()
        if exhaustion["at_risk"]:
            st.error(exhaustion["recommendation"])
        else:
            st.success(exhaustion["recommendation"])

        st.subheader("Leak Detection")
        leaks = monitor.detect_leaks()
        if leaks:
            for leak in leaks:
                st.error(f"Suspected leak: {leak['description']}")
        else:
            st.success("No connection leaks detected.")

        st.subheader("Long-Running Queries")
        long_running = monitor.get_long_running(threshold_ms=1000)
        if long_running:
            for lq in long_running:
                st.warning(
                    f"Query {lq.query_id[:8]}... | "
                    f"User: {lq.user} | "
                    f"Duration: {lq.duration_ms:.0f}ms | "
                    f"State: {lq.state}"
                )
        else:
            st.info("No long-running queries above threshold.")



render()
