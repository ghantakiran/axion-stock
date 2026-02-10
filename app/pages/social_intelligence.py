"""Social Signal Intelligence Dashboard (PRD-141).

4 tabs: Signal Overview, Volume Anomalies, Influencer Tracking, Intelligence Report.
"""

try:
    import streamlit as st
from app.styles import inject_global_styles
    st.set_page_config(page_title="Social Intelligence", layout="wide")

inject_global_styles()
except Exception:
    import streamlit as st

import asyncio
from datetime import datetime, timezone

import pandas as pd

st.title("Social Signal Intelligence")
st.caption("Advanced analytics on social media signals for trading decisions")

# ═══════════════════════════════════════════════════════════════════════
# Tabs
# ═══════════════════════════════════════════════════════════════════════

tab1, tab2, tab3, tab4 = st.tabs([
    "Signal Overview",
    "Volume Anomalies",
    "Influencer Tracking",
    "Intelligence Report",
])


# ── Helpers ────────────────────────────────────────────────────────────

def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _get_demo_posts():
    """Get demo posts from social crawler."""
    from src.social_crawler import FeedAggregator, TwitterCrawler, RedditCrawler
    agg = FeedAggregator()
    agg.add_crawler(TwitterCrawler())
    agg.add_crawler(RedditCrawler())

    async def _crawl():
        await agg.connect_all()
        return await agg.crawl_all()

    return _run_async(_crawl())


# ── Tab 1: Signal Overview ─────────────────────────────────────────────

with tab1:
    st.subheader("Scored Tickers")

    if st.button("Analyze Social Signals", type="primary", key="analyze_btn"):
        with st.spinner("Crawling and scoring..."):
            feed = _get_demo_posts()

            from src.social_intelligence import SignalScorer
            scorer = SignalScorer()
            scored = scorer.score_posts(feed.posts)

            st.session_state["scored_tickers"] = scored
            st.session_state["feed_posts"] = feed.posts

            # Metrics
            c1, c2, c3 = st.columns(3)
            c1.metric("Tickers Scored", len(scored))
            c2.metric("Posts Analyzed", len(feed.posts))
            top_score = scored[0].score if scored else 0
            c3.metric("Top Score", f"{top_score:.1f}")

    scored = st.session_state.get("scored_tickers", [])
    if scored:
        rows = []
        for s in scored:
            rows.append({
                "Symbol": s.symbol,
                "Score": round(s.score, 1),
                "Strength": s.strength.value,
                "Direction": s.direction,
                "Sentiment": round(s.sentiment_score, 2),
                "Engagement": round(s.engagement_score, 2),
                "Velocity": round(s.velocity_score, 2),
                "Mentions": s.mention_count,
                "Platforms": ", ".join(s.platforms),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True)

        # Score distribution chart
        if len(rows) > 1:
            df = pd.DataFrame(rows)
            st.bar_chart(df.set_index("Symbol")["Score"])


# ── Tab 2: Volume Anomalies ───────────────────────────────────────────

with tab2:
    st.subheader("Mention Volume Anomaly Detection")

    st.markdown("""
    Detects unusual spikes in social mention volume using Z-score analysis.
    A Z-score above 2.0 indicates the current mention rate is significantly
    above the historical baseline.
    """)

    from src.social_intelligence import VolumeAnalyzer, VolumeConfig

    z_threshold = st.slider("Z-Score Threshold", 1.0, 5.0, 2.0, 0.5, key="z_thresh")

    # Demo data
    demo_history = {
        "AAPL": [10, 12, 11, 13, 10, 12, 11, 45],
        "NVDA": [8, 9, 7, 8, 10, 8, 9, 60],
        "TSLA": [15, 14, 16, 15, 14, 15, 14, 15],
        "MSFT": [6, 7, 5, 6, 7, 6, 5, 6],
        "GME": [3, 4, 3, 2, 3, 4, 3, 35],
    }

    analyzer = VolumeAnalyzer(VolumeConfig(z_score_threshold=z_threshold))
    anomalies = analyzer.detect_anomalies(demo_history)

    if anomalies:
        c1, c2 = st.columns(2)
        c1.metric("Anomalies Detected", len(anomalies))
        c2.metric("Extreme Spikes", sum(1 for a in anomalies if a.is_extreme))

        rows = []
        for a in anomalies:
            rows.append({
                "Symbol": a.symbol,
                "Current Vol": a.current_volume,
                "Baseline": round(a.baseline_mean, 1),
                "Z-Score": round(a.z_score, 2),
                "Ratio": f"{a.volume_ratio:.1f}x",
                "Severity": a.severity,
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True)
    else:
        st.success("No volume anomalies detected with current threshold.")


# ── Tab 3: Influencer Tracking ────────────────────────────────────────

with tab3:
    st.subheader("Influencer Impact Tracking")

    from src.social_intelligence import InfluencerTracker, InfluencerConfig

    min_upvotes = st.number_input("Min Upvotes Threshold", 10, 10000, 100, key="inf_thresh")

    tracker = InfluencerTracker(InfluencerConfig(
        min_total_upvotes=min_upvotes, min_posts=1,
    ))

    # Use cached posts if available
    posts = st.session_state.get("feed_posts")
    if posts:
        tracker.process_posts(posts)
        top = tracker.get_top_influencers(n=20)

        st.metric("Tracked Influencers", len(top))

        if top:
            rows = []
            for p in top:
                rows.append({
                    "Author": p.author_id,
                    "Platform": p.platform,
                    "Tier": p.tier,
                    "Posts": p.total_posts,
                    "Total Upvotes": p.total_upvotes,
                    "Impact Score": round(p.impact_score, 2),
                    "Avg Sentiment": round(p.avg_sentiment, 2),
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True)

            # Influencer signals
            signals = tracker.get_influencer_signals(posts)
            if signals:
                st.subheader("Recent Influencer Signals")
                sig_rows = []
                for s in signals[:20]:
                    sig_rows.append({
                        "Author": s.author_id,
                        "Symbol": s.symbol,
                        "Direction": s.direction,
                        "Confidence": round(s.confidence, 2),
                        "Tier": s.tier,
                    })
                st.dataframe(pd.DataFrame(sig_rows), use_container_width=True)
    else:
        st.info("Run analysis from the Signal Overview tab first.")


# ── Tab 4: Intelligence Report ────────────────────────────────────────

with tab4:
    st.subheader("Full Intelligence Report")

    if st.button("Generate Intelligence Report", type="primary", key="report_btn"):
        with st.spinner("Running full intelligence pipeline..."):
            feed = _get_demo_posts()

            from src.social_intelligence import SocialSignalGenerator
            gen = SocialSignalGenerator()
            report = gen.analyze(feed.posts)

            # Summary metrics
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Posts Analyzed", report.total_posts_analyzed)
            c2.metric("Tickers Found", report.total_tickers_found)
            c3.metric("Signals Generated", report.signals_generated)
            c4.metric("Volume Anomalies", len(report.volume_anomalies))

            st.divider()

            # Trading signals
            if report.signals:
                st.subheader("Trading Signals")
                sig_rows = []
                for s in report.signals:
                    sig_rows.append({
                        "Symbol": s.symbol,
                        "Action": s.action.value,
                        "Confidence": round(s.confidence, 1),
                        "Direction": s.direction,
                        "Score": round(s.final_score, 1),
                        "Consensus": "Yes" if s.is_consensus else "No",
                        "Vol Anomaly": "Yes" if s.has_volume_anomaly else "No",
                        "Reasons": ", ".join(s.reasons) if s.reasons else "-",
                    })
                st.dataframe(pd.DataFrame(sig_rows), use_container_width=True)

            # Correlation results
            if report.correlations:
                st.subheader("Cross-Platform Correlation")
                corr_rows = []
                for c in report.correlations:
                    corr_rows.append({
                        "Symbol": c.symbol,
                        "Consensus": c.consensus_direction,
                        "Agreement": round(c.agreement_score, 2),
                        "Platforms": c.platform_count,
                        "Is Consensus": "Yes" if c.is_consensus else "No",
                    })
                st.dataframe(pd.DataFrame(corr_rows), use_container_width=True)
