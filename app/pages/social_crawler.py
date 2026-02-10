"""Social Signal Crawler Dashboard (PRD-140).

4 tabs: Crawler Status, Feed View, Ticker Analysis, Configuration.
"""

try:
    import streamlit as st
from app.styles import inject_global_styles
    st.set_page_config(page_title="Social Crawler", layout="wide")

inject_global_styles()
except Exception:
    import streamlit as st

import asyncio
from datetime import datetime, timezone

import pandas as pd

st.title("Social Signal Crawler")
st.caption("Crawl X/Twitter, Discord, Telegram, Reddit & WhatsApp for stock signals")

# ═══════════════════════════════════════════════════════════════════════
# Tabs
# ═══════════════════════════════════════════════════════════════════════

tab1, tab2, tab3, tab4 = st.tabs([
    "Crawler Status",
    "Feed View",
    "Ticker Analysis",
    "Configuration",
])


# ── Helpers ────────────────────────────────────────────────────────────

def _run_async(coro):
    """Run an async coroutine in a sync Streamlit context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _get_crawlers():
    from src.social_crawler import (
        TwitterCrawler, DiscordCrawler, TelegramCrawler,
        RedditCrawler, WhatsAppCrawler,
    )
    return {
        "Twitter/X": TwitterCrawler(),
        "Discord": DiscordCrawler(),
        "Telegram": TelegramCrawler(),
        "Reddit": RedditCrawler(),
        "WhatsApp": WhatsAppCrawler(),
    }


# ── Tab 1: Crawler Status ─────────────────────────────────────────────

with tab1:
    st.subheader("Platform Crawlers")

    from src.social_crawler import (
        FeedAggregator, TwitterCrawler, DiscordCrawler,
        TelegramCrawler, RedditCrawler, WhatsAppCrawler,
    )

    crawlers = _get_crawlers()

    # Status table
    status_rows = []
    for name, crawler in crawlers.items():
        status_rows.append({
            "Platform": name,
            "Connected": crawler.is_connected(),
            "Status": crawler.status.value if hasattr(crawler, "status") else "idle",
            "Total Crawls": crawler.stats.total_crawls,
            "Total Posts": crawler.stats.total_posts,
        })
    st.dataframe(pd.DataFrame(status_rows), use_container_width=True)

    st.divider()

    # Quick crawl
    st.subheader("Quick Crawl")
    selected_platforms = st.multiselect(
        "Select platforms to crawl",
        list(crawlers.keys()),
        default=list(crawlers.keys()),
    )

    if st.button("Run Crawl", type="primary"):
        with st.spinner("Crawling selected platforms..."):
            agg = FeedAggregator()
            for name in selected_platforms:
                agg.add_crawler(crawlers[name])

            async def _crawl():
                await agg.connect_all()
                return await agg.crawl_all()

            feed = _run_async(_crawl())

            # Metrics
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Posts", feed.total_posts)
            c2.metric("Unique Tickers", len(feed.unique_tickers))
            c3.metric("Platforms", len(feed.platform_counts))

            # Platform breakdown
            if feed.platform_counts:
                st.bar_chart(
                    pd.DataFrame(
                        list(feed.platform_counts.items()),
                        columns=["Platform", "Posts"],
                    ).set_index("Platform"),
                )

            st.success(f"Crawled {feed.total_posts} posts across {len(feed.platform_counts)} platforms")
            st.session_state["last_feed"] = feed


# ── Tab 2: Feed View ──────────────────────────────────────────────────

with tab2:
    st.subheader("Crawled Posts")

    feed = st.session_state.get("last_feed")
    if feed is None:
        st.info("Run a crawl from the Crawler Status tab first.")
    else:
        # Filters
        col1, col2 = st.columns(2)
        with col1:
            platform_filter = st.selectbox(
                "Filter by platform",
                ["All"] + list(feed.platform_counts.keys()),
            )
        with col2:
            ticker_filter = st.selectbox(
                "Filter by ticker",
                ["All"] + sorted(feed.unique_tickers),
            )

        posts = feed.posts
        if platform_filter != "All":
            posts = [p for p in posts if p.source == platform_filter]
        if ticker_filter != "All":
            posts = [p for p in posts if ticker_filter in p.tickers]

        # Posts table
        if posts:
            rows = []
            for p in posts[:200]:
                rows.append({
                    "Platform": p.source,
                    "Text": p.text[:120] + ("..." if len(p.text) > 120 else ""),
                    "Tickers": ", ".join(p.tickers),
                    "Sentiment": round(p.sentiment, 2) if p.sentiment else 0,
                    "Upvotes": p.upvotes,
                    "Comments": p.comments,
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True)
            st.caption(f"Showing {len(rows)} of {len(posts)} posts")
        else:
            st.warning("No posts match the selected filters.")


# ── Tab 3: Ticker Analysis ────────────────────────────────────────────

with tab3:
    st.subheader("Ticker Mention Analysis")

    feed = st.session_state.get("last_feed")
    if feed is None:
        st.info("Run a crawl from the Crawler Status tab first.")
    else:
        from src.social_crawler import SocialCrawlerBridge

        bridge = SocialCrawlerBridge()
        result = bridge.process_feed(feed)

        # Top metrics
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Posts Processed", result.total_posts_processed)
        c2.metric("Tickers Found", result.total_tickers_found)
        c3.metric("Trending", len(result.trending))
        c4.metric("Summaries", len(result.summaries))

        st.divider()

        # Mention counts
        if result.mentions:
            mention_data = sorted(
                [
                    {"Ticker": sym, "Mentions": m.count, "Avg Sentiment": round(m.avg_sentiment, 2)}
                    for sym, m in result.mentions.items()
                ],
                key=lambda x: x["Mentions"],
                reverse=True,
            )
            st.subheader("Top Mentioned Tickers")
            df = pd.DataFrame(mention_data[:20])
            st.bar_chart(df.set_index("Ticker")["Mentions"])
            st.dataframe(df, use_container_width=True)

        # Trending alerts
        if result.trending:
            st.subheader("Trending Alerts")
            for alert in result.trending:
                st.warning(
                    f"**{alert.symbol}** — {alert.current_count} mentions "
                    f"(avg: {alert.historical_avg:.1f}, spike: {alert.spike_ratio:.1f}x)"
                )

        # Per-ticker summaries
        if result.summaries:
            st.subheader("Ticker Summaries")
            selected_ticker = st.selectbox(
                "Select ticker for detail",
                sorted(result.summaries.keys()),
            )
            if selected_ticker:
                summary = result.summaries[selected_ticker]
                sc1, sc2, sc3 = st.columns(3)
                sc1.metric("Total Mentions", summary.total_mentions)
                sc2.metric("Avg Sentiment", f"{summary.avg_sentiment:.2f}")
                sc3.metric("Platforms", len(summary.platform_breakdown) if hasattr(summary, "platform_breakdown") else "-")


# ── Tab 4: Configuration ──────────────────────────────────────────────

with tab4:
    st.subheader("Crawler Configuration")

    st.markdown("### Platform Settings")

    with st.expander("Twitter/X Configuration"):
        st.text_input("API Bearer Token", type="password", key="tw_token",
                       help="Twitter API v2 Bearer Token")
        st.text_input("Search Queries (comma-separated)", value="$AAPL,$MSFT,$NVDA,$TSLA",
                       key="tw_queries")
        st.slider("Min Likes", 0, 100, 5, key="tw_min_likes")
        st.checkbox("Exclude Retweets", value=True, key="tw_exclude_rt")

    with st.expander("Discord Configuration"):
        st.text_input("Bot Token", type="password", key="dc_token")
        st.text_input("Channel IDs (comma-separated)", key="dc_channels")

    with st.expander("Telegram Configuration"):
        st.text_input("Bot Token", type="password", key="tg_token")
        st.text_input("Channel Usernames (comma-separated)",
                       value="wallstreetbets,stockmarket", key="tg_channels")

    with st.expander("Reddit Configuration"):
        st.text_input("Client ID", type="password", key="rd_client")
        st.text_input("Client Secret", type="password", key="rd_secret")
        st.text_input("Subreddits (comma-separated)",
                       value="wallstreetbets,stocks,investing,options,stockmarket",
                       key="rd_subs")

    with st.expander("WhatsApp Configuration"):
        st.text_input("Business API Token", type="password", key="wa_token")
        st.text_input("Phone Number ID", key="wa_phone")

    st.divider()

    st.markdown("### Aggregator Settings")
    st.checkbox("Enable Deduplication", value=True, key="agg_dedup")
    st.number_input("Max Posts per Crawl", min_value=10, max_value=10000,
                     value=1000, key="agg_max")
    st.selectbox("Sort Order", ["newest", "engagement", "sentiment"],
                  key="agg_sort")

    st.info(
        "Configuration changes apply to the next crawl session. "
        "API tokens are stored in the platform's Secrets Vault."
    )
