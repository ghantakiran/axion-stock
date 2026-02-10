"""PRD-128: Real-Time Anomaly Detection Dashboard."""

import random

import streamlit as st
from app.styles import inject_global_styles

inject_global_styles()
from datetime import datetime, timedelta, timezone

from src.anomaly_detection import (
    AnomalyConfig,
    AnomalySeverity,
    AnomalyStatus,
    AnomalyType,
    DetectionMethod,
    DetectorConfig,
    DetectorEngine,
    DataPoint,
    StreamConfig,
    StreamMonitor,
    PatternAnalyzer,
    AnomalyManager,
)


def _generate_demo_data(n: int = 100, anomaly_pct: float = 0.05):
    """Generate synthetic metric data with injected anomalies."""
    values = []
    for i in range(n):
        v = 100.0 + random.gauss(0, 2)
        if random.random() < anomaly_pct:
            v += random.choice([-1, 1]) * random.uniform(15, 25)
        values.append(v)
    return values


def render():
    st.title("Anomaly Detection Engine")

    tabs = st.tabs([
        "Anomaly Overview",
        "Stream Monitoring",
        "Pattern Analysis",
        "Investigation",
    ])

    # ── Tab 1: Anomaly Overview ──────────────────────────────────────
    with tabs[0]:
        st.subheader("Anomaly Overview")

        config = AnomalyConfig(
            detectors=[
                DetectorConfig(method=DetectionMethod.ZSCORE, threshold=3.0),
            ]
        )
        engine = DetectorEngine(config)

        values = _generate_demo_data(120)
        points = [
            DataPoint(
                timestamp=datetime.now(timezone.utc) - timedelta(minutes=120 - i),
                value=v,
                metric_name="demo_metric",
            )
            for i, v in enumerate(values)
        ]
        results = engine.batch_detect(points)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Data Points", len(points))
        col2.metric("Anomalies Detected", len(results))
        col3.metric("Detection Rate", f"{len(results) / max(len(points), 1) * 100:.1f}%")
        baseline = engine.get_baseline("demo_metric")
        col4.metric("Baseline Mean", f"{baseline.get('mean', 0):.2f}")

        # Severity distribution
        sev_counts = {}
        for r in results:
            sev_counts[r.severity.value] = sev_counts.get(r.severity.value, 0) + 1
        if sev_counts:
            st.bar_chart(sev_counts)
        else:
            st.info("No anomalies detected in demo data.")

        st.write("**Recent Anomalies**")
        for r in results[-10:]:
            st.write(
                f"- [{r.severity.value.upper()}] score={r.score:.2f} "
                f"value={r.data_point.value:.2f} method={r.method.value}"
            )

    # ── Tab 2: Stream Monitoring ─────────────────────────────────────
    with tabs[1]:
        st.subheader("Stream Monitoring")

        monitor = StreamMonitor()
        stream_cfg = StreamConfig(
            metric_name="latency_ms",
            detector_config=DetectorConfig(
                method=DetectionMethod.ZSCORE,
                threshold=2.5,
                min_samples=10,
            ),
        )
        sid = monitor.register_stream(stream_cfg)

        latency_values = _generate_demo_data(80, anomaly_pct=0.08)
        stream_anomalies = []
        for v in latency_values:
            res = monitor.ingest("latency_ms", v)
            if res:
                stream_anomalies.append(res)

        status = monitor.get_stream_status(sid)
        stats = monitor.stream_statistics()

        col1, col2, col3 = st.columns(3)
        col1.metric("Active Streams", stats["active_streams"])
        col2.metric("Total Ingested", status.get("data_count", 0))
        col3.metric("Stream Anomalies", len(stream_anomalies))

        st.write("**Stream Status**")
        st.json(status)

        recent = monitor.get_recent_anomalies(sid, limit=5)
        if recent:
            st.write("**Recent Stream Anomalies**")
            for a in recent:
                st.write(f"- score={a.score:.2f} value={a.data_point.value:.2f}")

    # ── Tab 3: Pattern Analysis ──────────────────────────────────────
    with tabs[2]:
        st.subheader("Pattern Analysis")

        analyzer = PatternAnalyzer(zscore_threshold=2.0)

        # Volume analysis
        volumes = _generate_demo_data(60, anomaly_pct=0.1)
        vol_anomalies = analyzer.analyze_volume_pattern("AAPL", volumes)

        # Price analysis
        prices = [150.0]
        for _ in range(59):
            prices.append(prices[-1] * (1 + random.gauss(0, 0.01)))
        # Inject a spike
        if len(prices) > 30:
            prices[30] *= 1.10
        price_anomalies = analyzer.analyze_price_pattern("AAPL", prices)

        col1, col2 = st.columns(2)
        col1.metric("Volume Anomalies", len(vol_anomalies))
        col2.metric("Price Anomalies", len(price_anomalies))

        # Regime detection
        series = [random.gauss(10, 1) for _ in range(30)] + [random.gauss(20, 1) for _ in range(30)]
        change_pts = analyzer.detect_regime_change(series, window=10)
        st.write(f"**Regime Change Points**: {change_pts if change_pts else 'None detected'}")

        history = analyzer.get_pattern_history("AAPL")
        st.write(f"**Total Patterns Recorded**: {len(history)}")

        if vol_anomalies:
            st.write("**Volume Anomaly Details**")
            for a in vol_anomalies[:5]:
                st.write(
                    f"- deviation={a.deviation_score:.2f} "
                    f"expected={a.expected:.2f} actual={a.actual:.2f}"
                )

    # ── Tab 4: Investigation ─────────────────────────────────────────
    with tabs[3]:
        st.subheader("Investigation & Triage")

        manager = AnomalyManager()

        # Create some records from results
        engine2 = DetectorEngine()
        vals = _generate_demo_data(100, anomaly_pct=0.1)
        pts = [
            DataPoint(
                timestamp=datetime.now(timezone.utc) - timedelta(minutes=100 - i),
                value=v,
                metric_name="cpu_usage",
            )
            for i, v in enumerate(vals)
        ]
        detections = engine2.batch_detect(pts)
        for d in detections:
            manager.record_anomaly(d)

        open_anomalies = manager.get_open_anomalies()
        stats = manager.anomaly_statistics()
        sev_dist = manager.severity_distribution()
        top_metrics = manager.top_anomalous_metrics(limit=5)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Records", stats["total"])
        col2.metric("Open", stats["open"])
        col3.metric("Resolved", stats["resolved"])
        col4.metric("False Positives", stats["false_positives"])

        if sev_dist:
            st.write("**Severity Distribution**")
            st.bar_chart(sev_dist)

        if top_metrics:
            st.write("**Top Anomalous Metrics**")
            for tm in top_metrics:
                st.write(f"- {tm['metric_name']}: {tm['anomaly_count']} anomalies")

        # Demonstrate workflow
        if open_anomalies:
            first = open_anomalies[0]
            manager.update_status(first.record_id, AnomalyStatus.INVESTIGATING, "Looking into it")
            st.write(f"Investigating record {first.record_id}")



render()
