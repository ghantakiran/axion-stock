"""Social Trading Dashboard."""

import streamlit as st
import pandas as pd

st.set_page_config(page_title="Social Trading", layout="wide")
st.title("Social Trading")

# --- Sidebar ---
st.sidebar.header("Social")
view = st.sidebar.selectbox(
    "View", ["Feed", "Leaderboard", "Copy Trading", "My Profile"],
)

# --- Main Content ---
tab1, tab2, tab3, tab4 = st.tabs([
    "Feed", "Leaderboard", "Copy Trading", "Strategies",
])

# --- Tab 1: Social Feed ---
with tab1:
    st.subheader("Trade Ideas & Discussion")

    feed_data = pd.DataFrame([
        {"Author": "AlphaTrader", "Type": "Trade Idea",
         "Content": "AAPL bullish above $200, targeting $220. Strong momentum.",
         "Symbol": "AAPL", "Likes": "24", "Comments": "8"},
        {"Author": "QuantPro", "Type": "Market Analysis",
         "Content": "VIX dropping below 15 signals risk-on environment.",
         "Symbol": "VIX", "Likes": "42", "Comments": "15"},
        {"Author": "SwingKing", "Type": "Position Update",
         "Content": "Closed MSFT long at $410 for +8.2% gain.",
         "Symbol": "MSFT", "Likes": "18", "Comments": "5"},
        {"Author": "ValueHunter", "Type": "Trade Idea",
         "Content": "GOOGL undervalued at 22x forward PE. Adding to position.",
         "Symbol": "GOOGL", "Likes": "31", "Comments": "12"},
    ])
    st.dataframe(feed_data, use_container_width=True, hide_index=True)

    st.markdown("#### Trending")
    trending = pd.DataFrame([
        {"Rank": "1", "Post": "VIX analysis by QuantPro", "Engagement": "57"},
        {"Rank": "2", "Post": "GOOGL value play by ValueHunter", "Engagement": "43"},
        {"Rank": "3", "Post": "AAPL breakout by AlphaTrader", "Engagement": "32"},
    ])
    st.dataframe(trending, use_container_width=True, hide_index=True)

# --- Tab 2: Leaderboard ---
with tab2:
    st.subheader("Top Traders")

    col1, col2 = st.columns(2)
    metric = col1.selectbox("Metric", ["Total Return", "Sharpe Ratio", "Win Rate"])
    period = col2.selectbox("Period", ["3M", "6M", "1Y", "All Time"])

    leaderboard_data = pd.DataFrame([
        {"Rank": "1", "Trader": "AlphaTrader", "Return": "+35.2%",
         "Sharpe": "2.10", "Win Rate": "62%", "Trades": "100",
         "Badges": "Top, Risk Master", "Followers": "245"},
        {"Rank": "2", "Trader": "GammaTrader", "Return": "+28.5%",
         "Sharpe": "1.80", "Win Rate": "55%", "Trades": "200",
         "Badges": "Veteran", "Followers": "180"},
        {"Rank": "3", "Trader": "QuantPro", "Return": "+22.1%",
         "Sharpe": "1.65", "Win Rate": "58%", "Trades": "75",
         "Badges": "Consistent", "Followers": "312"},
        {"Rank": "4", "Trader": "SwingKing", "Return": "+18.7%",
         "Sharpe": "1.42", "Win Rate": "60%", "Trades": "120",
         "Badges": "Veteran", "Followers": "156"},
        {"Rank": "5", "Trader": "ValueHunter", "Return": "+15.3%",
         "Sharpe": "1.20", "Win Rate": "65%", "Trades": "45",
         "Badges": "Consistent", "Followers": "98"},
    ])
    st.dataframe(leaderboard_data, use_container_width=True, hide_index=True)

# --- Tab 3: Copy Trading ---
with tab3:
    st.subheader("Copy Trading")

    col1, col2, col3 = st.columns(3)
    col1.metric("Active Copies", "3")
    col2.metric("Total P&L", "+$2,450")
    col3.metric("Trades Copied", "47")

    st.markdown("#### Active Copy Relationships")
    copy_data = pd.DataFrame([
        {"Leader": "AlphaTrader", "Strategy": "Momentum Alpha",
         "Allocation": "$5,000", "P&L": "+$850",
         "Trades": "18", "Status": "Active"},
        {"Leader": "QuantPro", "Strategy": "Factor Timing",
         "Allocation": "$3,000", "P&L": "+$420",
         "Trades": "12", "Status": "Active"},
        {"Leader": "SwingKing", "Strategy": "Swing Breakouts",
         "Allocation": "$2,000", "P&L": "+$180",
         "Trades": "8", "Status": "Paused"},
    ])
    st.dataframe(copy_data, use_container_width=True, hide_index=True)

    st.markdown("#### Available Strategies to Copy")
    strategies_data = pd.DataFrame([
        {"Strategy": "Momentum Alpha", "Author": "AlphaTrader",
         "Return (3M)": "+12.5%", "Sharpe": "2.10",
         "Min Capital": "$1,000", "Copiers": "45", "Risk": "3/5"},
        {"Strategy": "Factor Timing", "Author": "QuantPro",
         "Return (3M)": "+8.2%", "Sharpe": "1.65",
         "Min Capital": "$2,000", "Copiers": "32", "Risk": "2/5"},
        {"Strategy": "Value Deep Dive", "Author": "ValueHunter",
         "Return (3M)": "+6.8%", "Sharpe": "1.20",
         "Min Capital": "$5,000", "Copiers": "18", "Risk": "2/5"},
    ])
    st.dataframe(strategies_data, use_container_width=True, hide_index=True)

# --- Tab 4: Strategies ---
with tab4:
    st.subheader("Strategy Marketplace")

    from src.social.config import StrategyCategory
    categories = [c.value.replace("_", " ").title() for c in StrategyCategory]
    st.multiselect("Filter by Category", categories, default=[])

    all_strategies = pd.DataFrame([
        {"Name": "Momentum Alpha", "Category": "Momentum", "Author": "AlphaTrader",
         "Return": "+35.2%", "Sharpe": "2.10", "Copiers": "45",
         "Risk": "3/5", "Status": "Published"},
        {"Name": "Factor Timing", "Category": "Quantitative", "Author": "QuantPro",
         "Return": "+22.1%", "Sharpe": "1.65", "Copiers": "32",
         "Risk": "2/5", "Status": "Published"},
        {"Name": "Swing Breakouts", "Category": "Momentum", "Author": "SwingKing",
         "Return": "+18.7%", "Sharpe": "1.42", "Copiers": "28",
         "Risk": "4/5", "Status": "Published"},
        {"Name": "Value Deep Dive", "Category": "Value", "Author": "ValueHunter",
         "Return": "+15.3%", "Sharpe": "1.20", "Copiers": "18",
         "Risk": "2/5", "Status": "Published"},
        {"Name": "Crypto Momentum", "Category": "Crypto", "Author": "CryptoWhale",
         "Return": "+42.5%", "Sharpe": "1.35", "Copiers": "62",
         "Risk": "5/5", "Status": "Published"},
    ])
    st.dataframe(all_strategies, use_container_width=True, hide_index=True)
