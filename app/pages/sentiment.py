"""Sentiment Intelligence Dashboard.

Provides:
- Composite sentiment overview
- News sentiment feed
- Social media buzz tracker
- Insider trading signals
- Analyst consensus view
- Earnings call tone analysis
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta

# Page config
st.set_page_config(
    page_title="Axion Sentiment Intelligence",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Import sentiment module
try:
    from src.sentiment import (
        SentimentConfig,
        NewsSentimentEngine,
        SocialMediaMonitor,
        InsiderTracker,
        AnalystConsensusTracker,
        EarningsCallAnalyzer,
        SentimentComposite,
    )
    SENTIMENT_AVAILABLE = True
except ImportError as e:
    SENTIMENT_AVAILABLE = False
    st.error(f"Sentiment module not available: {e}")


# =============================================================================
# Demo Data
# =============================================================================

def get_demo_composite():
    """Generate demo composite sentiment data."""
    np.random.seed(42)
    symbols = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "JPM",
               "JNJ", "XOM"]

    rows = []
    for symbol in symbols:
        news = np.random.uniform(-0.3, 0.9)
        social = np.random.uniform(-0.5, 0.9)
        insider = np.random.uniform(-0.6, 0.8)
        analyst = np.random.uniform(-0.4, 0.8)
        earnings = np.random.uniform(-0.3, 0.7)
        options = np.random.uniform(-0.4, 0.8)

        composite = (0.25 * news + 0.15 * social + 0.20 * insider +
                    0.20 * analyst + 0.10 * earnings + 0.10 * options)

        rows.append({
            "Symbol": symbol,
            "Composite": composite,
            "News": news,
            "Social": social,
            "Insider": insider,
            "Analyst": analyst,
            "Earnings": earnings,
            "Options Flow": options,
        })

    return pd.DataFrame(rows).sort_values("Composite", ascending=False).reset_index(drop=True)


def get_demo_news():
    """Generate demo news feed."""
    return [
        {"title": "Apple Reports Record Services Revenue", "sentiment": 0.8,
         "source": "Reuters", "time": "2h ago", "symbols": "AAPL"},
        {"title": "NVIDIA AI Chip Demand Exceeds Supply", "sentiment": 0.9,
         "source": "Bloomberg", "time": "3h ago", "symbols": "NVDA"},
        {"title": "Tesla Faces Regulatory Scrutiny in EU", "sentiment": -0.5,
         "source": "FT", "time": "4h ago", "symbols": "TSLA"},
        {"title": "Microsoft Azure Growth Accelerates", "sentiment": 0.7,
         "source": "CNBC", "time": "5h ago", "symbols": "MSFT"},
        {"title": "Amazon Expands Same-Day Delivery Network", "sentiment": 0.4,
         "source": "WSJ", "time": "6h ago", "symbols": "AMZN"},
        {"title": "JPMorgan Warns of Credit Headwinds", "sentiment": -0.3,
         "source": "Reuters", "time": "8h ago", "symbols": "JPM"},
    ]


def get_demo_social():
    """Generate demo social buzz data."""
    return pd.DataFrame([
        {"Symbol": "NVDA", "Reddit": 1250, "Twitter": 8400, "StockTwits": 620,
         "Sentiment": 0.82, "Trending": True},
        {"Symbol": "TSLA", "Reddit": 980, "Twitter": 12300, "StockTwits": 890,
         "Sentiment": 0.35, "Trending": True},
        {"Symbol": "AAPL", "Reddit": 420, "Twitter": 5200, "StockTwits": 380,
         "Sentiment": 0.71, "Trending": False},
        {"Symbol": "GME", "Reddit": 3200, "Twitter": 2100, "StockTwits": 1500,
         "Sentiment": 0.55, "Trending": True},
        {"Symbol": "META", "Reddit": 310, "Twitter": 3800, "StockTwits": 250,
         "Sentiment": 0.64, "Trending": False},
    ])


def get_demo_insider():
    """Generate demo insider data."""
    return pd.DataFrame([
        {"Symbol": "AAPL", "Insider": "Tim Cook (CEO)", "Action": "Buy",
         "Shares": "50,000", "Value": "$9.0M", "Date": "Jan 25", "Signal": "+0.6"},
        {"Symbol": "NVDA", "Insider": "Jensen Huang (CEO)", "Action": "Sell (10b5-1)",
         "Shares": "100,000", "Value": "$14.2M", "Date": "Jan 20", "Signal": "-0.1"},
        {"Symbol": "JPM", "Insider": "Jamie Dimon (CEO)", "Action": "Buy",
         "Shares": "25,000", "Value": "$5.2M", "Date": "Jan 18", "Signal": "+0.6"},
        {"Symbol": "MSFT", "Insider": "Director A", "Action": "Buy",
         "Shares": "10,000", "Value": "$4.1M", "Date": "Jan 15", "Signal": "+0.4"},
    ])


# =============================================================================
# Dashboard Components
# =============================================================================

def render_composite_overview(df):
    """Render composite sentiment overview."""
    st.markdown("### Composite Sentiment Scores")

    # Top metrics
    cols = st.columns(4)
    with cols[0]:
        avg = df["Composite"].mean()
        st.metric("Market Sentiment", f"{avg:.2f}",
                  "Bullish" if avg > 0.2 else ("Bearish" if avg < -0.2 else "Neutral"))
    with cols[1]:
        bullish = (df["Composite"] > 0.1).sum()
        st.metric("Bullish Stocks", f"{bullish}/{len(df)}")
    with cols[2]:
        top = df.iloc[0]
        st.metric(f"Most Bullish", top["Symbol"], f"{top['Composite']:.2f}")
    with cols[3]:
        bottom = df.iloc[-1]
        st.metric(f"Most Bearish", bottom["Symbol"], f"{bottom['Composite']:.2f}")

    # Heatmap-style table
    st.dataframe(
        df.style.format({
            "Composite": "{:.2f}", "News": "{:.2f}", "Social": "{:.2f}",
            "Insider": "{:.2f}", "Analyst": "{:.2f}",
            "Earnings": "{:.2f}", "Options Flow": "{:.2f}",
        }).background_gradient(
            subset=["Composite", "News", "Social", "Insider", "Analyst",
                    "Earnings", "Options Flow"],
            cmap="RdYlGn", vmin=-1, vmax=1,
        ),
        use_container_width=True,
        hide_index=True,
        height=400,
    )


def render_news_feed(news_data):
    """Render news sentiment feed."""
    st.markdown("### Trending News")

    for item in news_data:
        score = item["sentiment"]
        color = "green" if score > 0.2 else ("red" if score < -0.2 else "orange")
        bar_width = int(abs(score) * 100)

        st.markdown(f"""
        <div style="padding: 0.5rem 1rem; margin: 0.3rem 0;
                    border-left: 4px solid {color}; background: {color}08;
                    border-radius: 4px;">
            <strong>{item['title']}</strong>
            <span style="color: {color}; float: right;">
                {'+' if score > 0 else ''}{score:.1f}
            </span><br>
            <small style="color: #888;">
                {item['source']} &bull; {item['time']} &bull; {item['symbols']}
            </small>
        </div>
        """, unsafe_allow_html=True)


def render_social_buzz(social_df):
    """Render social media buzz tracker."""
    st.markdown("### Social Media Buzz")

    col1, col2 = st.columns([2, 1])

    with col1:
        fig = go.Figure()
        for source in ["Reddit", "Twitter", "StockTwits"]:
            fig.add_trace(go.Bar(
                name=source,
                x=social_df["Symbol"],
                y=social_df[source],
            ))
        fig.update_layout(
            barmode="stack",
            title="Mention Volume by Platform",
            height=300,
            margin=dict(l=0, r=0, t=40, b=0),
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("**Trending Tickers**")
        trending = social_df[social_df["Trending"]]
        for _, row in trending.iterrows():
            total = row["Reddit"] + row["Twitter"] + row["StockTwits"]
            st.markdown(f"**{row['Symbol']}** - {total:,} mentions")
            st.progress(min(row["Sentiment"], 1.0))


def render_insider_signals(insider_df):
    """Render insider trading signals."""
    st.markdown("### Insider Trading Activity")

    st.dataframe(
        insider_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Signal": st.column_config.TextColumn("Score"),
        },
    )


# =============================================================================
# Main Page
# =============================================================================

def main():
    st.title("📰 Sentiment Intelligence")

    if not SENTIMENT_AVAILABLE:
        st.error("Sentiment module not available. Please check installation.")
        return

    # Sidebar
    with st.sidebar:
        st.markdown("## Sentiment")
        st.markdown("---")
        st.toggle("Demo Mode", value=True, key="sent_demo_mode")
        st.markdown("---")
        st.markdown("### Market Pulse")
        st.metric("Overall Sentiment", "0.42", "Bullish")
        st.metric("News Flow", "68% Positive")
        st.metric("Social Buzz", "NVDA Trending")
        st.metric("Insider Activity", "Net Buying")

    # Tabs
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
        "📊 Overview", "📰 News", "💬 Social", "👔 Insider & Analyst",
        "⏱ Decay Weighting", "🔀 Fusion", "🤝 Consensus", "📈 Momentum",
    ])

    with tab1:
        composite_df = get_demo_composite()
        render_composite_overview(composite_df)

    with tab2:
        news = get_demo_news()
        render_news_feed(news)

    with tab3:
        social = get_demo_social()
        render_social_buzz(social)

    with tab4:
        insider = get_demo_insider()
        render_insider_signals(insider)

    with tab5:
        st.markdown("### Time-Decay Weighted Sentiment")
        st.markdown("Applies exponential half-life decay so recent signals "
                     "carry more weight than stale observations.")

        decay_df = pd.DataFrame([
            {"Symbol": "AAPL", "Weighted Score": 0.52, "Unweighted": 0.45,
             "Avg Age (hrs)": 18.5, "Freshness": 0.75, "Sources": 4},
            {"Symbol": "NVDA", "Weighted Score": 0.71, "Unweighted": 0.58,
             "Avg Age (hrs)": 12.0, "Freshness": 0.90, "Sources": 5},
            {"Symbol": "TSLA", "Weighted Score": -0.15, "Unweighted": -0.05,
             "Avg Age (hrs)": 36.0, "Freshness": 0.40, "Sources": 4},
            {"Symbol": "MSFT", "Weighted Score": 0.38, "Unweighted": 0.35,
             "Avg Age (hrs)": 24.0, "Freshness": 0.60, "Sources": 3},
            {"Symbol": "AMZN", "Weighted Score": 0.25, "Unweighted": 0.30,
             "Avg Age (hrs)": 30.0, "Freshness": 0.50, "Sources": 3},
        ])
        st.dataframe(
            decay_df.style.format({
                "Weighted Score": "{:.2f}", "Unweighted": "{:.2f}",
                "Avg Age (hrs)": "{:.1f}", "Freshness": "{:.0%}",
            }).background_gradient(
                subset=["Weighted Score"], cmap="RdYlGn", vmin=-1, vmax=1,
            ),
            use_container_width=True, hide_index=True,
        )

        col1, col2 = st.columns(2)
        with col1:
            hours = np.linspace(0, 200, 100)
            decay = np.power(2.0, -hours / 48.0)
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=hours, y=decay, mode="lines", name="Decay Factor",
                line=dict(color="steelblue"),
            ))
            fig.add_hline(y=0.5, line_dash="dash", annotation_text="Half-life (48h)")
            fig.update_layout(
                title="Exponential Decay Curve (48h Half-Life)",
                xaxis_title="Age (hours)", yaxis_title="Weight",
                height=300, margin=dict(l=0, r=0, t=40, b=0),
            )
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.markdown("**Decay Impact Analysis**")
            st.markdown("- Fresh obs (<24h) get **75-100%** weight")
            st.markdown("- 48h old observations get **50%** weight")
            st.markdown("- 1-week old observations get **~3%** weight")
            st.markdown("- High-credibility sources get a boost")

    with tab6:
        st.markdown("### Multi-Source Sentiment Fusion")
        st.markdown("Combines signals from diverse sources with adaptive "
                     "weighting and conflict detection.")

        fusion_df = pd.DataFrame([
            {"Symbol": "AAPL", "Fused Score": 0.55, "Confidence": 0.82,
             "Agreement": 0.90, "Conflict": 0.08, "Dominant": "news", "Sources": 5},
            {"Symbol": "NVDA", "Fused Score": 0.72, "Confidence": 0.88,
             "Agreement": 0.95, "Conflict": 0.04, "Dominant": "analyst", "Sources": 5},
            {"Symbol": "TSLA", "Fused Score": 0.05, "Confidence": 0.45,
             "Agreement": 0.50, "Conflict": 0.55, "Dominant": "social", "Sources": 4},
            {"Symbol": "MSFT", "Fused Score": 0.48, "Confidence": 0.75,
             "Agreement": 0.80, "Conflict": 0.15, "Dominant": "analyst", "Sources": 4},
            {"Symbol": "JPM", "Fused Score": -0.12, "Confidence": 0.60,
             "Agreement": 0.65, "Conflict": 0.30, "Dominant": "insider", "Sources": 3},
        ])
        st.dataframe(
            fusion_df.style.format({
                "Fused Score": "{:.2f}", "Confidence": "{:.0%}",
                "Agreement": "{:.0%}", "Conflict": "{:.0%}",
            }).background_gradient(
                subset=["Fused Score"], cmap="RdYlGn", vmin=-1, vmax=1,
            ),
            use_container_width=True, hide_index=True,
        )

        col1, col2 = st.columns(2)
        with col1:
            fig = go.Figure(go.Bar(
                x=fusion_df["Symbol"],
                y=fusion_df["Fused Score"],
                marker_color=["green" if s > 0.1 else ("red" if s < -0.1 else "gray")
                              for s in fusion_df["Fused Score"]],
            ))
            fig.update_layout(
                title="Fused Sentiment Scores",
                height=300, margin=dict(l=0, r=0, t=40, b=0),
            )
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.markdown("**Source Weight Allocation**")
            weights = {"News": 0.25, "Analyst": 0.20, "Insider": 0.20,
                       "Social": 0.15, "Earnings": 0.10, "Options": 0.10}
            fig = go.Figure(go.Pie(
                labels=list(weights.keys()),
                values=list(weights.values()),
                hole=0.4,
            ))
            fig.update_layout(
                title="Default Source Weights",
                height=300, margin=dict(l=0, r=0, t=40, b=0),
            )
            st.plotly_chart(fig, use_container_width=True)

    with tab7:
        st.markdown("### Sentiment Consensus")
        st.markdown("Measures agreement across sources and tracks "
                     "consensus shifts over time.")

        consensus_df = pd.DataFrame([
            {"Symbol": "AAPL", "Direction": "Bullish", "Score": 0.52,
             "Strength": 0.75, "Unanimity": 0.85, "Bull": 4, "Bear": 0, "Neutral": 1},
            {"Symbol": "NVDA", "Direction": "Bullish", "Score": 0.68,
             "Strength": 0.88, "Unanimity": 1.00, "Bull": 5, "Bear": 0, "Neutral": 0},
            {"Symbol": "TSLA", "Direction": "Neutral", "Score": 0.05,
             "Strength": 0.20, "Unanimity": 0.40, "Bull": 2, "Bear": 2, "Neutral": 1},
            {"Symbol": "JPM", "Direction": "Bearish", "Score": -0.22,
             "Strength": 0.55, "Unanimity": 0.67, "Bull": 1, "Bear": 2, "Neutral": 0},
        ])
        st.dataframe(
            consensus_df.style.format({
                "Score": "{:.2f}", "Strength": "{:.0%}", "Unanimity": "{:.0%}",
            }),
            use_container_width=True, hide_index=True,
        )

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Market Breadth**")
            breadth_data = {"Bullish": 6, "Neutral": 2, "Bearish": 2}
            fig = go.Figure(go.Pie(
                labels=list(breadth_data.keys()),
                values=list(breadth_data.values()),
                marker_colors=["green", "gray", "red"],
                hole=0.5,
            ))
            fig.update_layout(
                title="Consensus Direction Distribution",
                height=300, margin=dict(l=0, r=0, t=40, b=0),
            )
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.markdown("**Recent Consensus Shifts**")
            shifts = [
                {"Symbol": "TSLA", "From": "Bearish", "To": "Neutral",
                 "Change": "+0.25", "Type": "Reversal"},
                {"Symbol": "JPM", "From": "Neutral", "To": "Bearish",
                 "Change": "-0.18", "Type": "Shift"},
            ]
            st.dataframe(pd.DataFrame(shifts), use_container_width=True,
                         hide_index=True)

    with tab8:
        st.markdown("### Sentiment Momentum")
        st.markdown("Tracks sentiment trends and detects inflection points.")

        momentum_df = pd.DataFrame([
            {"Symbol": "AAPL", "Current": 0.52, "Momentum": 0.04,
             "Accel": 0.01, "Trend": "Improving", "Strength": 0.82},
            {"Symbol": "NVDA", "Current": 0.71, "Momentum": 0.02,
             "Accel": -0.01, "Trend": "Improving", "Strength": 0.90},
            {"Symbol": "TSLA", "Current": 0.05, "Momentum": 0.08,
             "Accel": 0.03, "Trend": "Improving", "Strength": 0.65},
            {"Symbol": "MSFT", "Current": 0.38, "Momentum": -0.02,
             "Accel": -0.01, "Trend": "Deteriorating", "Strength": 0.55},
            {"Symbol": "JPM", "Current": -0.12, "Momentum": -0.05,
             "Accel": 0.00, "Trend": "Deteriorating", "Strength": 0.70},
        ])
        st.dataframe(
            momentum_df.style.format({
                "Current": "{:.2f}", "Momentum": "{:+.2f}",
                "Accel": "{:+.2f}", "Strength": "{:.0%}",
            }).background_gradient(
                subset=["Momentum"], cmap="RdYlGn", vmin=-0.1, vmax=0.1,
            ),
            use_container_width=True, hide_index=True,
        )

        # Sentiment trend chart
        np.random.seed(42)
        periods = 20
        trend_data = {}
        for sym in ["AAPL", "NVDA", "TSLA", "MSFT"]:
            base = np.random.uniform(-0.2, 0.5)
            trend = np.random.uniform(-0.02, 0.03)
            noise = np.random.normal(0, 0.05, periods)
            trend_data[sym] = np.clip(
                base + trend * np.arange(periods) + noise, -1, 1
            )
        fig = go.Figure()
        for sym, vals in trend_data.items():
            fig.add_trace(go.Scatter(
                x=list(range(periods)), y=vals,
                mode="lines+markers", name=sym,
            ))
        fig.update_layout(
            title="Sentiment Trend (Last 20 Periods)",
            xaxis_title="Period", yaxis_title="Sentiment Score",
            height=350, margin=dict(l=0, r=0, t=40, b=0),
        )
        st.plotly_chart(fig, use_container_width=True)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Momentum Summary**")
            st.metric("Improving", "6/10 stocks")
            st.metric("Avg Momentum", "+0.015")
            st.metric("Breadth", "65%")
        with col2:
            st.markdown("**Detected Reversals**")
            reversals = [
                {"Symbol": "TSLA", "Type": "Bullish Reversal",
                 "From": "-0.15", "To": "+0.05", "Confidence": "62%"},
            ]
            st.dataframe(pd.DataFrame(reversals), use_container_width=True,
                         hide_index=True)


if __name__ == "__main__":
    main()
