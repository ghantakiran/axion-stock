"""Signal Streaming Dashboard (PRD-153).

Four-tab Streamlit dashboard for real-time signal streaming,
aggregation monitoring, filter configuration, and health checks.
"""

import streamlit as st
from datetime import datetime, timezone

from src.signal_streaming.aggregator import (
    AggregatorConfig,
    StreamingAggregator,
)
from src.signal_streaming.broadcaster import (
    BroadcasterConfig,
    SignalBroadcaster,
)
from src.signal_streaming.filters import (
    FilterConfig,
    StreamFilter,
    ThresholdRule,
)
from src.signal_streaming.monitor import (
    MonitorConfig,
    StreamMonitor,
)

st.header("Signal Streaming")
st.caption("PRD-153 · Real-time sentiment & signal broadcasting pipeline")

tab1, tab2, tab3, tab4 = st.tabs([
    "Live Feed", "Aggregation", "Filters", "Health",
])

# ── Tab 1: Live Feed ──────────────────────────────────────────────────

with tab1:
    st.subheader("Live Signal Feed")

    agg = StreamingAggregator(AggregatorConfig(
        window_seconds=0, min_score_change=0.0,
    ))
    broadcaster = SignalBroadcaster()

    # Simulate some observations
    demo_data = [
        ("AAPL", 0.7, 0.85, "llm", "low"),
        ("TSLA", -0.3, 0.6, "social", "medium"),
        ("NVDA", 0.9, 0.95, "llm", "high"),
        ("MSFT", 0.2, 0.5, "news", "low"),
        ("GOOG", -0.5, 0.7, "social", "medium"),
    ]

    if st.button("Simulate Stream", key="simulate"):
        for ticker, score, conf, source, urgency in demo_data:
            agg.add_observation(ticker, score, confidence=conf,
                              source_type=source, urgency=urgency)

        updates = agg.flush()
        messages = broadcaster.format_sentiment_updates(updates)

        st.write(f"**Updates Generated:** {len(updates)}")
        st.write(f"**Messages Queued:** {broadcaster.queue_size}")

        for msg in messages:
            wire = msg.to_wire()
            icon = {"bullish": "🟢", "bearish": "🔴", "neutral": "⚪"}.get(
                msg.data.get("sentiment", "neutral"), "⚪"
            )
            st.write(
                f"{icon} **{msg.ticker}**: "
                f"{msg.data.get('score', 0):+.2f} "
                f"({msg.data.get('urgency', 'low')}) "
                f"via {msg.channel}"
            )

# ── Tab 2: Aggregation ───────────────────────────────────────────────

with tab2:
    st.subheader("Aggregation Settings")

    window = st.slider("Window (seconds)", 5, 120, 30, key="agg_window")
    min_change = st.slider("Min Score Change", 0.01, 0.5, 0.1, key="agg_change")

    st.write(f"**Window:** {window}s — updates buffer for this long before emission")
    st.write(f"**Min Change:** {min_change} — suppress updates below this threshold")
    st.write(f"**Effect:** Reduces noise by {int((1 - min_change) * 100)}% for small movements")

    st.divider()
    st.subheader("How Aggregation Works")
    st.markdown("""
    1. Observations arrive from LLM, social crawlers, and news feeds
    2. They buffer per-ticker for the configured window duration
    3. At flush time, compute confidence-weighted average score
    4. Only emit if score change exceeds the minimum threshold
    5. High-urgency observations bypass the window for immediate delivery
    """)

# ── Tab 3: Filters ────────────────────────────────────────────────────

with tab3:
    st.subheader("Stream Filter Rules")

    filt = StreamFilter(FilterConfig(
        default_rule=ThresholdRule(
            name="default",
            min_score_change=0.1,
            min_confidence=0.3,
            min_observations=1,
        ),
        pass_high_urgency=True,
    ))

    # Test various updates
    from dataclasses import dataclass, field

    @dataclass
    class _TestUpdate:
        ticker: str = ""
        score_change: float = 0.0
        confidence: float = 0.5
        observation_count: int = 5
        urgency: str = "low"

    test_cases = [
        _TestUpdate(ticker="AAPL", score_change=0.3, confidence=0.8, urgency="low"),
        _TestUpdate(ticker="TSLA", score_change=0.05, confidence=0.9, urgency="low"),
        _TestUpdate(ticker="NVDA", score_change=0.01, confidence=0.2, urgency="high"),
        _TestUpdate(ticker="GME", score_change=0.5, confidence=0.1, urgency="low"),
    ]

    for tc in test_cases:
        result = filt.apply(tc)
        icon = "✅" if result.passed else "❌"
        reason = f" ({result.rejection_reason})" if result.rejection_reason else ""
        st.write(f"{icon} **{tc.ticker}** — Rule: {result.rule_applied}{reason}")

    st.metric("Pass Rate", f"{filt.pass_rate:.0%}")

# ── Tab 4: Health ─────────────────────────────────────────────────────

with tab4:
    st.subheader("Stream Health")

    monitor = StreamMonitor()

    # Simulate activity
    for i in range(50):
        monitor.record_in(ticker=f"T{i % 5}")
        monitor.record_out(latency_ms=10 + i * 0.5)
    monitor.record_error()
    monitor.record_error()
    monitor.set_queue_depth(15)

    health = monitor.check_health()
    stats = monitor.get_stats()

    status_icons = {"healthy": "🟢", "degraded": "🟡", "unhealthy": "🔴"}
    icon = status_icons.get(health.status, "⚪")
    st.markdown(f"### {icon} {health.status.upper()}")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Messages In", stats.messages_in)
    m2.metric("Messages Out", stats.messages_out)
    m3.metric("Errors", stats.messages_errored)
    m4.metric("Queue Depth", stats.queue_depth)

    m5, m6, m7, m8 = st.columns(4)
    m5.metric("Avg Latency", f"{stats.avg_latency_ms:.1f}ms")
    m6.metric("Max Latency", f"{stats.max_latency_ms:.1f}ms")
    m7.metric("Throughput", f"{stats.throughput_per_min:.0f}/min")
    m8.metric("Active Tickers", stats.active_tickers)

    if health.issues:
        st.warning("**Issues Detected:**")
        for issue in health.issues:
            st.write(f"  - {issue}")
