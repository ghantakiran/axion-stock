"""PRD-103: Observability & Metrics Export."""

import streamlit as st
from datetime import datetime

from src.observability import (
    MetricsRegistry,
    MetricsConfig,
    PrometheusExporter,
    TradingMetrics,
    SystemMetrics,
)


def render():
    st.title("Observability & Metrics Export")

    tabs = st.tabs(["Overview", "Trading Metrics", "System Metrics", "Prometheus Export"])

    # Reset and generate fresh sample data
    registry = MetricsRegistry()
    registry.reset()
    trading = TradingMetrics.generate_sample_data()
    system = SystemMetrics.generate_sample_data()
    exporter = PrometheusExporter()

    # ── Tab 1: Overview ──────────────────────────────────────────────
    with tabs[0]:
        st.subheader("Metrics Overview")

        all_metrics = registry.get_all_metrics()
        all_meta = registry.get_all_meta()

        col1, col2, col3 = st.columns(3)
        counters = sum(1 for m in all_meta.values() if m.metric_type.value == "counter")
        gauges = sum(1 for m in all_meta.values() if m.metric_type.value == "gauge")
        histograms = sum(1 for m in all_meta.values() if m.metric_type.value == "histogram")

        col1.metric("Counters", counters)
        col2.metric("Gauges", gauges)
        col3.metric("Histograms", histograms)

        st.subheader("Registered Metrics")
        metric_data = []
        for name, meta in sorted(all_meta.items()):
            metric_data.append({
                "Name": name,
                "Type": meta.metric_type.value.upper(),
                "Description": meta.description,
                "Labels": ", ".join(meta.label_names) if meta.label_names else "none",
            })
        st.dataframe(metric_data, use_container_width=True)

    # ── Tab 2: Trading Metrics ───────────────────────────────────────
    with tabs[1]:
        st.subheader("Trading Metrics")

        # Orders
        st.markdown("#### Orders")
        col1, col2, col3, col4 = st.columns(4)
        filled_buy = trading.orders_total.get({"status": "filled", "broker": "alpaca", "side": "buy"})
        filled_sell = trading.orders_total.get({"status": "filled", "broker": "alpaca", "side": "sell"})
        rejected = trading.orders_total.get({"status": "rejected", "broker": "ib", "side": "buy"})
        cancelled = trading.orders_total.get({"status": "cancelled", "broker": "alpaca", "side": "buy"})

        col1.metric("Filled (Buy)", int(filled_buy))
        col2.metric("Filled (Sell)", int(filled_sell))
        col3.metric("Rejected", int(rejected))
        col4.metric("Cancelled", int(cancelled))

        # Positions
        st.markdown("#### Positions")
        col1, col2 = st.columns(2)
        col1.metric("Active Positions", int(trading.positions_active.value))
        col2.metric("Portfolio Value", f"${trading.portfolio_value_dollars.value:,.0f}")

        # Signals
        st.markdown("#### Signals")
        col1, col2, col3 = st.columns(3)
        mom_long = trading.signals_generated_total.get({"strategy": "momentum", "direction": "long"})
        mr_short = trading.signals_generated_total.get({"strategy": "mean_reversion", "direction": "short"})
        ml_long = trading.signals_generated_total.get({"strategy": "ml_ranking", "direction": "long"})
        col1.metric("Momentum Long", int(mom_long))
        col2.metric("Mean Rev Short", int(mr_short))
        col3.metric("ML Ranking Long", int(ml_long))

        # Slippage
        st.markdown("#### Slippage")
        col1, col2, col3 = st.columns(3)
        col1.metric("Observations", trading.slippage_basis_points.count)
        col2.metric("Avg BPS", f"{trading.slippage_basis_points.sum / max(trading.slippage_basis_points.count, 1):.1f}")
        col3.metric("P95 BPS", f"{trading.slippage_basis_points.quantile(0.95):.1f}")

    # ── Tab 3: System Metrics ────────────────────────────────────────
    with tabs[2]:
        st.subheader("System Metrics")

        # API
        st.markdown("#### API Requests")
        col1, col2, col3 = st.columns(3)
        get_200 = system.api_requests_total.get({"method": "GET", "path": "/api/v1/quotes", "status_code": "200"})
        post_201 = system.api_requests_total.get({"method": "POST", "path": "/api/v1/orders", "status_code": "201"})
        get_500 = system.api_requests_total.get({"method": "GET", "path": "/api/v1/quotes", "status_code": "500"})

        col1.metric("GET 200 (Quotes)", int(get_200))
        col2.metric("POST 201 (Orders)", int(post_201))
        col3.metric("GET 500 (Errors)", int(get_500))

        # Cache
        st.markdown("#### Cache Performance")
        col1, col2, col3 = st.columns(3)
        col1.metric("Cache Hits", int(system.cache_hits_total.value))
        col2.metric("Cache Misses", int(system.cache_misses_total.value))
        col3.metric("Hit Rate", f"{system.cache_hit_rate():.0%}")

        # Infrastructure
        st.markdown("#### Infrastructure")
        col1, col2 = st.columns(2)
        col1.metric("WebSocket Connections", int(system.websocket_connections_active.value))
        col2.metric("DB Queries (select)", system.db_query_duration_seconds.get_count(labels={"operation": "select"}))

        # Pipeline lag
        st.markdown("#### Data Pipeline Lag")
        lag_data = []
        for source in ["polygon", "yahoo_finance", "alpaca"]:
            lag = system.data_pipeline_lag_seconds.get(labels={"source": source})
            lag_data.append({"Source": source, "Lag (seconds)": f"{lag:.1f}"})
        st.dataframe(lag_data, use_container_width=True)

    # ── Tab 4: Prometheus Export ──────────────────────────────────────
    with tabs[3]:
        st.subheader("Prometheus Exposition Format")
        st.markdown(
            "This is the raw output served at the `/metrics` endpoint "
            "for Prometheus scraping."
        )

        output = exporter.expose_metrics()
        st.code(output, language="text")

        st.markdown("#### Configuration")
        config = MetricsConfig()
        config_data = {
            "Export Format": config.export_format.value,
            "Endpoint": config.endpoint_path,
            "Prefix": config.prefix,
            "Include Timestamp": str(config.include_timestamp),
            "Collection Interval": f"{config.collection_interval_seconds}s",
            "Retention": f"{config.retention_minutes} min",
        }
        st.json(config_data)


if __name__ == "__main__":
    render()
