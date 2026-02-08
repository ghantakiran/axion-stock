"""Strategy Marketplace Dashboard."""

import streamlit as st
from datetime import datetime
import pandas as pd
import numpy as np

try:
    st.set_page_config(page_title="Strategy Marketplace", layout="wide")
except st.errors.StreamlitAPIException:
    pass

st.title("Strategy Marketplace")

# --- Sidebar ---
st.sidebar.header("Filters")

category = st.sidebar.selectbox(
    "Category",
    ["All", "Momentum", "Value", "Growth", "Dividend", "Swing", "Day Trading", "Options", "Quantitative"],
)

risk_level = st.sidebar.selectbox(
    "Risk Level",
    ["All", "Conservative", "Moderate", "Aggressive", "Very Aggressive"],
)

pricing = st.sidebar.selectbox(
    "Pricing",
    ["All", "Free", "Subscription", "Performance Fee"],
)

min_return = st.sidebar.slider("Min Return %", -50, 200, 0)
min_rating = st.sidebar.slider("Min Rating", 0.0, 5.0, 0.0, 0.5)

verified_only = st.sidebar.checkbox("Verified Only")

st.sidebar.markdown("---")
st.sidebar.markdown("**Your Stats**")
st.sidebar.markdown("Subscriptions: 3")
st.sidebar.markdown("Total Invested: $25,000")

# --- Main Content ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Browse", "Leaderboard", "My Subscriptions", "Creator Dashboard", "Create Strategy"
])

# --- Tab 1: Browse ---
with tab1:
    col1, col2 = st.columns([3, 1])
    with col1:
        search_query = st.text_input("Search strategies...", placeholder="e.g., momentum, tech stocks")
    with col2:
        sort_by = st.selectbox("Sort by", ["Most Popular", "Top Rated", "Best Returns", "Newest", "Price: Low to High"])

    # Featured strategies
    st.subheader("Featured Strategies")

    featured = [
        {
            "id": "strat_001",
            "name": "Momentum Alpha",
            "creator": "QuantTrader",
            "category": "Momentum",
            "return_pct": 45.2,
            "sharpe": 1.85,
            "drawdown": 12.5,
            "subscribers": 342,
            "rating": 4.7,
            "reviews": 89,
            "price": 29.99,
            "verified": True,
        },
        {
            "id": "strat_002",
            "name": "Value Investor Pro",
            "creator": "BuffettFan",
            "category": "Value",
            "return_pct": 28.5,
            "sharpe": 1.42,
            "drawdown": 8.3,
            "subscribers": 567,
            "rating": 4.8,
            "reviews": 156,
            "price": 19.99,
            "verified": True,
        },
        {
            "id": "strat_003",
            "name": "Dividend Champion",
            "creator": "IncomeInvestor",
            "category": "Dividend",
            "return_pct": 15.8,
            "sharpe": 1.12,
            "drawdown": 5.2,
            "subscribers": 823,
            "rating": 4.6,
            "reviews": 234,
            "price": 0,
            "verified": True,
        },
    ]

    cols = st.columns(3)
    for i, strat in enumerate(featured):
        with cols[i]:
            with st.container():
                verified_badge = " Verified" if strat["verified"] else ""
                st.markdown(f"### {strat['name']}{verified_badge}")
                st.caption(f"by {strat['creator']} | {strat['category']}")

                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Return", f"+{strat['return_pct']}%")
                with col2:
                    st.metric("Sharpe", f"{strat['sharpe']}")

                st.caption(f"Rating: {'*' * int(strat['rating'])} ({strat['reviews']} reviews)")
                st.caption(f"Subscribers: {strat['subscribers']:,}")

                price_text = "FREE" if strat["price"] == 0 else f"${strat['price']}/mo"
                if st.button(f"Subscribe ({price_text})", key=f"sub_{strat['id']}"):
                    st.success(f"Subscribed to {strat['name']}")

    st.markdown("---")

    # All strategies
    st.subheader("All Strategies")

    all_strategies = pd.DataFrame([
        {"Name": "Momentum Alpha", "Category": "Momentum", "Return": "+45.2%", "Sharpe": 1.85, "Subscribers": 342, "Rating": 4.7, "Price": "$29.99/mo"},
        {"Name": "Value Investor Pro", "Category": "Value", "Return": "+28.5%", "Sharpe": 1.42, "Subscribers": 567, "Rating": 4.8, "Price": "$19.99/mo"},
        {"Name": "Dividend Champion", "Category": "Dividend", "Return": "+15.8%", "Sharpe": 1.12, "Subscribers": 823, "Rating": 4.6, "Price": "FREE"},
        {"Name": "Swing Trader Elite", "Category": "Swing", "Return": "+62.3%", "Sharpe": 1.95, "Subscribers": 234, "Rating": 4.5, "Price": "$49.99/mo"},
        {"Name": "Tech Growth", "Category": "Growth", "Return": "+78.4%", "Sharpe": 1.65, "Subscribers": 456, "Rating": 4.4, "Price": "$39.99/mo"},
        {"Name": "Options Income", "Category": "Options", "Return": "+22.1%", "Sharpe": 1.88, "Subscribers": 189, "Rating": 4.3, "Price": "$59.99/mo"},
    ])

    st.dataframe(all_strategies, use_container_width=True, hide_index=True)

# --- Tab 2: Leaderboard ---
with tab2:
    st.subheader("Strategy Leaderboard")

    col1, col2, col3 = st.columns(3)
    with col1:
        leaderboard_period = st.selectbox("Period", ["30 Days", "90 Days", "1 Year", "All Time"])
    with col2:
        leaderboard_metric = st.selectbox("Rank By", ["Return", "Sharpe Ratio", "Subscribers", "Rating"])
    with col3:
        leaderboard_category = st.selectbox("Category", ["All Categories"] + [cat for cat in ["Momentum", "Value", "Growth"]])

    leaderboard_data = pd.DataFrame([
        {"Rank": 1, "Strategy": "Swing Trader Elite", "Creator": "SwingMaster", "Return": "+62.3%", "Sharpe": 1.95, "Max DD": "-15.2%", "Subscribers": 234},
        {"Rank": 2, "Strategy": "Tech Growth", "Creator": "TechInvestor", "Return": "+78.4%", "Sharpe": 1.65, "Max DD": "-22.5%", "Subscribers": 456},
        {"Rank": 3, "Strategy": "Momentum Alpha", "Creator": "QuantTrader", "Return": "+45.2%", "Sharpe": 1.85, "Max DD": "-12.5%", "Subscribers": 342},
        {"Rank": 4, "Strategy": "Value Investor Pro", "Creator": "BuffettFan", "Return": "+28.5%", "Sharpe": 1.42, "Max DD": "-8.3%", "Subscribers": 567},
        {"Rank": 5, "Strategy": "Options Income", "Creator": "OptionsGuru", "Return": "+22.1%", "Sharpe": 1.88, "Max DD": "-6.8%", "Subscribers": 189},
    ])

    st.dataframe(leaderboard_data, use_container_width=True, hide_index=True)

    # Medals for top 3
    st.markdown("### Top Performers")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("#### 1st Place")
        st.markdown("**Swing Trader Elite**")
        st.metric("Return", "+62.3%")
    with col2:
        st.markdown("#### 2nd Place")
        st.markdown("**Tech Growth**")
        st.metric("Return", "+78.4%")
    with col3:
        st.markdown("#### 3rd Place")
        st.markdown("**Momentum Alpha**")
        st.metric("Return", "+45.2%")

# --- Tab 3: My Subscriptions ---
with tab3:
    st.subheader("My Subscriptions")

    # Summary
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Active Subscriptions", "3")
    col2.metric("Monthly Cost", "$69.97")
    col3.metric("Combined P&L", "+$2,345.67", "+12.5%")
    col4.metric("Avg Rating", "4.7")

    st.markdown("---")

    subscriptions = [
        {
            "strategy": "Momentum Alpha",
            "creator": "QuantTrader",
            "status": "Active",
            "since": "2024-06-15",
            "type": "Auto-Trade",
            "position_size": "50%",
            "my_return": "+18.5%",
            "monthly_cost": "$29.99",
        },
        {
            "strategy": "Value Investor Pro",
            "creator": "BuffettFan",
            "status": "Active",
            "since": "2024-08-01",
            "type": "Signals Only",
            "position_size": "100%",
            "my_return": "+8.2%",
            "monthly_cost": "$19.99",
        },
        {
            "strategy": "Dividend Champion",
            "creator": "IncomeInvestor",
            "status": "Active",
            "since": "2024-03-10",
            "type": "Auto-Trade",
            "position_size": "75%",
            "my_return": "+5.8%",
            "monthly_cost": "FREE",
        },
    ]

    for sub in subscriptions:
        with st.expander(f"{sub['strategy']} by {sub['creator']} - {sub['status']}"):
            col1, col2, col3 = st.columns(3)

            with col1:
                st.markdown(f"**Type:** {sub['type']}")
                st.markdown(f"**Since:** {sub['since']}")

            with col2:
                st.markdown(f"**Position Size:** {sub['position_size']}")
                st.markdown(f"**Monthly Cost:** {sub['monthly_cost']}")

            with col3:
                st.metric("My Return", sub["my_return"])

            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("Edit Settings", key=f"edit_{sub['strategy']}"):
                    st.info("Opening settings...")
            with col2:
                if st.button("Pause", key=f"pause_{sub['strategy']}"):
                    st.warning("Subscription paused")
            with col3:
                if st.button("Unsubscribe", key=f"unsub_{sub['strategy']}"):
                    st.error("Unsubscribed")

# --- Tab 4: Creator Dashboard ---
with tab4:
    st.subheader("Creator Dashboard")

    # Summary
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Your Strategies", "2")
    col2.metric("Total Subscribers", "145")
    col3.metric("Monthly Revenue", "$2,145.50")
    col4.metric("Avg Rating", "4.6")

    st.markdown("---")

    st.markdown("### Your Strategies")

    creator_strategies = [
        {
            "name": "My Momentum Strategy",
            "subscribers": 85,
            "revenue": "$1,274.15",
            "rating": 4.5,
            "return": "+32.5%",
            "published": True,
        },
        {
            "name": "Sector Rotation Model",
            "subscribers": 60,
            "revenue": "$871.35",
            "rating": 4.7,
            "return": "+24.8%",
            "published": True,
        },
    ]

    for strat in creator_strategies:
        with st.container():
            col1, col2, col3, col4, col5 = st.columns(5)

            with col1:
                st.markdown(f"**{strat['name']}**")
                status = "Published" if strat["published"] else "Draft"
                st.caption(status)

            with col2:
                st.metric("Subscribers", strat["subscribers"])

            with col3:
                st.metric("Revenue", strat["revenue"])

            with col4:
                st.metric("Rating", strat["rating"])

            with col5:
                st.metric("Return", strat["return"])

            st.markdown("---")

    # Revenue breakdown
    st.markdown("### Revenue Breakdown")

    col1, col2 = st.columns(2)
    with col1:
        revenue_data = pd.DataFrame({
            "Month": ["Oct", "Nov", "Dec", "Jan"],
            "Revenue": [1850, 1920, 2050, 2145],
        })
        st.bar_chart(revenue_data.set_index("Month"))

    with col2:
        st.markdown("**This Month**")
        st.markdown("- Gross Revenue: $2,681.88")
        st.markdown("- Platform Fee (20%): $536.38")
        st.markdown("- **Net Payout: $2,145.50**")
        st.markdown("- Next payout: Feb 1, 2025")

# --- Tab 5: Create Strategy ---
with tab5:
    st.subheader("Create New Strategy")

    with st.form("create_strategy"):
        col1, col2 = st.columns(2)

        with col1:
            name = st.text_input("Strategy Name", placeholder="e.g., Momentum Alpha")
            category = st.selectbox("Category", ["Momentum", "Value", "Growth", "Dividend", "Swing", "Day Trading", "Options", "Quantitative"])
            risk_level = st.selectbox("Risk Level", ["Conservative", "Moderate", "Aggressive", "Very Aggressive"])
            trading_style = st.selectbox("Trading Style", ["Long Only", "Long/Short", "Market Neutral", "Trend Following"])

        with col2:
            time_horizon = st.selectbox("Time Horizon", ["Intraday", "Short Term", "Medium Term", "Long Term"])
            min_capital = st.number_input("Minimum Capital ($)", min_value=100, value=1000)
            max_positions = st.number_input("Max Positions", min_value=1, max_value=50, value=10)
            asset_classes = st.multiselect("Asset Classes", ["Stocks", "ETFs", "Options", "Futures"], default=["Stocks"])

        st.markdown("---")
        description = st.text_area("Description", placeholder="Describe your strategy, its approach, and what makes it unique...")
        short_desc = st.text_input("Short Description (200 chars)", placeholder="Brief one-liner for the strategy card")

        st.markdown("---")
        st.markdown("### Pricing")

        pricing_model = st.selectbox("Pricing Model", ["Free", "Subscription", "Performance Fee", "Hybrid"])

        if pricing_model in ["Subscription", "Hybrid"]:
            monthly_price = st.number_input("Monthly Price ($)", min_value=4.99, max_value=499.99, value=29.99)

        if pricing_model in ["Performance Fee", "Hybrid"]:
            perf_fee = st.slider("Performance Fee (%)", 5, 30, 20)

        submitted = st.form_submit_button("Create Strategy", type="primary")

        if submitted:
            st.success(f"Strategy '{name}' created successfully! Review and publish when ready.")
