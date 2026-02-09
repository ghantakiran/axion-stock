"""Influencer Intelligence Dashboard (PRD-152).

Four-tab Streamlit dashboard for influencer discovery,
performance tracking, network analysis, and alert monitoring.
"""

import streamlit as st
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from src.influencer_intel.discovery import (
    DiscoveryConfig,
    InfluencerDiscovery,
)
from src.influencer_intel.ledger import (
    PerformanceLedger,
    PredictionRecord,
)
from src.influencer_intel.network import (
    NetworkAnalyzer,
    NetworkConfig,
)
from src.influencer_intel.alerts import (
    AlertConfig,
    InfluencerAlertBridge,
)

st.header("Influencer Intelligence")
st.caption("PRD-152 · Discovery, performance tracking, network analysis, and alerts")

tab1, tab2, tab3, tab4 = st.tabs([
    "Discovery", "Performance", "Network", "Alerts",
])


# ── Mock data helper ──────────────────────────────────────────────────

@dataclass
class _DemoPost:
    author: str = ""
    source: str = "twitter"
    upvotes: int = 100
    comments: int = 10
    sentiment: float = 0.5
    tickers: list = field(default_factory=list)
    text: str = ""
    timestamp: str = ""


def _generate_demo_posts():
    now = datetime.now(timezone.utc)
    posts = []
    authors = {
        "whale_trader": (500, ["AAPL", "NVDA", "TSLA"], 0.7),
        "tech_guru": (300, ["NVDA", "AMD", "MSFT"], 0.5),
        "value_hunter": (200, ["JPM", "GS", "BAC"], 0.3),
        "crypto_king": (150, ["BTC", "ETH", "SOL"], 0.6),
        "penny_scout": (50, ["AAPL", "TSLA"], -0.2),
    }
    for author, (upvotes, tickers, sentiment) in authors.items():
        for i in range(8):
            ts = (now - timedelta(hours=32 - i * 4)).isoformat()
            posts.append(_DemoPost(
                author=author, source="twitter", upvotes=upvotes,
                sentiment=sentiment + i * 0.05, tickers=tickers,
                text=f"{author} post about {tickers[0]}", timestamp=ts,
            ))
    return posts


# ── Tab 1: Discovery ──────────────────────────────────────────────────

with tab1:
    st.subheader("Influencer Discovery")

    min_posts = st.slider("Min Posts", 1, 20, 3, key="disc_min")
    min_engagement = st.slider("Min Engagement Rate", 0.1, 100.0, 0.5, key="disc_eng")

    if st.button("Run Discovery", key="discover"):
        discovery = InfluencerDiscovery(DiscoveryConfig(
            min_posts=int(min_posts),
            min_engagement_rate=min_engagement,
        ))
        discovery.ingest_posts(_generate_demo_posts())
        result = discovery.discover()

        st.write(f"**Posts Analyzed:** {result.total_posts_analyzed}")
        st.write(f"**Authors Seen:** {result.total_authors_seen}")
        st.write(f"**Candidates Found:** {result.candidate_count}")

        for c in result.candidates:
            st.markdown(f"### {c.author_id} ({c.platform})")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Posts", c.post_count)
            m2.metric("Upvotes", c.total_upvotes)
            m3.metric("Engagement", f"{c.engagement_rate:.1f}")
            m4.metric("Score", f"{c.discovery_score:.3f}")

            if c.top_tickers:
                st.write(f"Top tickers: {', '.join(c.top_tickers)}")

# ── Tab 2: Performance ────────────────────────────────────────────────

with tab2:
    st.subheader("Performance Ledger")

    ledger = PerformanceLedger()

    # Demo: add predictions and evaluate them
    demo_preds = [
        ("trader1", "AAPL", "bullish", 180.0, 195.0),
        ("trader1", "TSLA", "bearish", 200.0, 180.0),
        ("trader1", "NVDA", "bullish", 500.0, 480.0),
        ("trader2", "AAPL", "bullish", 180.0, 190.0),
        ("trader2", "GOOG", "bearish", 140.0, 150.0),
    ]

    for i, (author, ticker, direction, entry, exit_p) in enumerate(demo_preds):
        pid = f"demo_{i}"
        ledger.record_prediction(PredictionRecord(
            prediction_id=pid, author_id=author, platform="twitter",
            ticker=ticker, direction=direction, entry_price=entry,
        ))
        ledger.evaluate(pid, exit_price=exit_p, sector="technology")

    report = ledger.generate_report()

    st.write(f"**Total Predictions:** {report.total_predictions}")
    st.write(f"**Overall Accuracy:** {report.overall_accuracy:.0%}")

    for stats in report.stats:
        st.markdown(f"### {stats.author_id}")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Accuracy", f"{stats.accuracy_rate:.0%}")
        m2.metric("Avg Return", f"{stats.avg_return_pct:+.1f}%")
        m3.metric("Best Call", f"{stats.best_call_return_pct:+.1f}%")
        m4.metric("Streak", stats.streak_current)

# ── Tab 3: Network ────────────────────────────────────────────────────

with tab3:
    st.subheader("Influencer Network")

    min_co = st.slider("Min Shared Tickers", 1, 10, 3, key="net_co")

    if st.button("Analyze Network", key="net_analyze"):
        analyzer = NetworkAnalyzer(NetworkConfig(min_co_mentions=int(min_co)))
        analyzer.ingest_posts(_generate_demo_posts())
        report = analyzer.analyze()

        st.write(f"**Nodes:** {report.node_count}")
        st.write(f"**Edges:** {report.total_edges}")
        st.write(f"**Density:** {report.density:.4f}")
        st.write(f"**Clusters:** {report.cluster_count}")

        for cluster in report.clusters:
            st.markdown(f"#### Cluster {cluster.cluster_id}")
            st.write(f"Members: {', '.join(cluster.members)}")
            st.write(f"Shared: {', '.join(cluster.shared_tickers)}")
            st.write(f"Coordination: {cluster.coordination_score:.2f}")

# ── Tab 4: Alerts ─────────────────────────────────────────────────────

with tab4:
    st.subheader("Influencer Alerts")

    @dataclass
    class _DemoSignal:
        author_id: str = ""
        platform: str = "twitter"
        symbol: str = "AAPL"
        sentiment: float = 0.5
        direction: str = "bullish"
        impact_score: float = 0.7
        tier: str = "macro"

    bridge = InfluencerAlertBridge(AlertConfig(
        sentiment_reversal_threshold=0.3,
    ))

    # Demo signals
    demo_signals = [
        _DemoSignal(author_id="whale", tier="mega", symbol="NVDA", sentiment=0.9),
        _DemoSignal(author_id="guru", tier="macro", symbol="AAPL", sentiment=0.6),
    ]

    alerts = bridge.check_signals(demo_signals)

    # Simulate reversal
    bridge.check_signals([_DemoSignal(author_id="flipper", tier="macro", sentiment=0.8)])
    reversal_alerts = bridge.check_signals([
        _DemoSignal(author_id="flipper", tier="macro", sentiment=-0.5)
    ])

    all_alerts = bridge.get_recent_alerts(20)
    st.write(f"**Total Alerts:** {bridge.alert_count}")

    for alert in all_alerts:
        priority_icons = {"low": "🔵", "medium": "🟡", "high": "🟠", "critical": "🔴"}
        icon = priority_icons.get(alert.priority.value, "⚪")
        st.write(f"{icon} **{alert.alert_type}** — {alert.message}")
