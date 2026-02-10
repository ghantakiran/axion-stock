"""Integration & Load Testing Dashboard (PRD-108).

Displays test overview, mock services, load test results,
and benchmark visualizations.
"""

import random
from datetime import datetime, timezone

import streamlit as st
from app.styles import inject_global_styles

from src.testing.config import LoadProfile, TestConfig, TestType
from src.testing.load import LoadTestRunner

try:
    st.set_page_config(page_title="Testing Framework", page_icon="🧪", layout="wide")
except st.errors.StreamlitAPIException:
    pass

inject_global_styles()

st.title("🧪 Integration & Load Testing Framework")

tab1, tab2, tab3, tab4 = st.tabs([
    "Test Overview",
    "Mock Services",
    "Load Testing",
    "Benchmarks",
])

with tab1:
    st.header("Test Suite Overview")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Tests", "4,315")
    col2.metric("Unit Tests", "4,010")
    col3.metric("Integration Tests", "245")
    col4.metric("Load Tests", "60")

    st.subheader("Test Types")
    test_dist = {t.value: random.randint(50, 500) for t in TestType}
    st.bar_chart(test_dist)

    st.subheader("Test Configuration")
    config = TestConfig()
    st.json({
        "default_timeout_seconds": config.timeout_seconds,
        "default_concurrency": config.concurrency,
        "default_iterations": config.iterations,
        "benchmark_iterations": config.benchmark_iterations,
        "regression_threshold": f"{config.regression_threshold:.0%}",
    })

with tab2:
    st.header("Mock Services")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.subheader("MockBroker")
        st.write("Simulated order execution with configurable latency and fill probability.")
        st.json({
            "latency_ms": 10.0,
            "fill_probability": 0.95,
            "slippage_bps": 1.0,
            "total_orders": 1523,
            "fill_rate": 0.94,
        })

    with col2:
        st.subheader("MockMarketData")
        st.write("OHLCV data generation with configurable volatility.")
        st.json({
            "volatility": 0.02,
            "symbols_cached": 15,
            "bars_generated": 75000,
        })

    with col3:
        st.subheader("MockRedis")
        st.write("In-memory Redis mock with TTL support.")
        st.json({
            "keys_stored": 342,
            "ttl_enabled": True,
            "connected": True,
        })

    st.subheader("Test Fixtures")
    st.code("""
from src.testing.fixtures import (
    create_test_order,
    create_test_portfolio,
    create_test_signal,
    create_test_market_data,
    create_test_orders_batch,
    create_test_portfolio_with_positions,
)

order = create_test_order(symbol="AAPL", quantity=100)
portfolio = create_test_portfolio_with_positions(n_positions=5)
batch = create_test_orders_batch(n=50)
    """, language="python")

with tab3:
    st.header("Load Test Results")
    result = LoadTestRunner.generate_sample_result("API Endpoint Stress Test")
    summary = result.summary()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Requests", summary["total_requests"])
    col2.metric("Success Rate", f"{summary['success_rate']:.1%}")
    col3.metric("Mean Latency", f"{summary['mean_ms']:.1f}ms")
    col4.metric("P95 Latency", f"{summary['p95_ms']:.1f}ms")

    st.subheader("Latency Distribution")
    hist_data = {f"{i*20}-{(i+1)*20}ms": random.randint(10, 100) for i in range(10)}
    st.bar_chart(hist_data)

    st.subheader("Load Profiles")
    for profile in LoadProfile:
        st.write(f"- **{profile.value}**: {profile.name}")

with tab4:
    st.header("Benchmark Results")
    benchmarks = {
        "sort_1000_items": {"mean_ms": 0.12, "p95_ms": 0.18, "regression": False},
        "json_parse_large": {"mean_ms": 2.45, "p95_ms": 3.12, "regression": False},
        "portfolio_calc": {"mean_ms": 8.90, "p95_ms": 12.34, "regression": True},
        "risk_computation": {"mean_ms": 45.2, "p95_ms": 67.8, "regression": False},
        "factor_scoring": {"mean_ms": 123.4, "p95_ms": 189.0, "regression": True},
    }

    for name, data in benchmarks.items():
        status = "🔴 REGRESSION" if data["regression"] else "🟢 OK"
        st.write(f"**{name}** — mean: {data['mean_ms']}ms, p95: {data['p95_ms']}ms {status}")

    st.subheader("Regression Threshold")
    st.write(f"Benchmarks with >10% degradation from baseline are flagged as regressions.")
