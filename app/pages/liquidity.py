"""Liquidity Analysis Dashboard."""

import streamlit as st
import pandas as pd

st.set_page_config(page_title="Liquidity Analysis", layout="wide")
st.title("Liquidity Analysis")

# --- Sidebar ---
st.sidebar.header("Liquidity Settings")
symbol = st.sidebar.text_input("Symbol", "AAPL")
window = st.sidebar.selectbox("Window", ["1 Week", "1 Month", "3 Months"], index=1)
trade_size = st.sidebar.number_input("Trade Size (shares)", value=10000, step=1000)

# --- Main Content ---
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10, tab11 = st.tabs([
    "Overview", "Spread", "Impact", "Scoring",
    "Redemption Risk", "LaVaR",
    "Spread Modeling", "Market Depth", "Illiquidity Premium",
    "Concentration", "Cost Curves",
])

# --- Tab 1: Overview ---
with tab1:
    st.subheader("Liquidity Overview")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Liquidity Score", "87/100")
    col2.metric("Level", "Very High")
    col3.metric("Avg Spread", "0.02 (1.3 bps)")
    col4.metric("Avg Daily Volume", "52.3M")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Dollar Volume", "$7.8B")
    col6.metric("VWAP", "$150.23")
    col7.metric("Max Safe Size", "523,000 shares")
    col8.metric("Impact (10k)", "0.8 bps")

    st.markdown("#### Liquidity Summary")
    summary_data = pd.DataFrame([
        {"Metric": "Average Spread", "Value": "$0.02", "Assessment": "Excellent"},
        {"Metric": "Relative Spread", "Value": "1.3 bps", "Assessment": "Excellent"},
        {"Metric": "Avg Daily Volume", "Value": "52.3M shares", "Assessment": "Very High"},
        {"Metric": "Dollar Volume", "Value": "$7.8B/day", "Assessment": "Very High"},
        {"Metric": "Market Impact (10k)", "Value": "0.8 bps", "Assessment": "Minimal"},
        {"Metric": "Max Safe Size (10%)", "Value": "523,000 shares", "Assessment": "Large"},
    ])
    st.dataframe(summary_data, use_container_width=True, hide_index=True)

# --- Tab 2: Spread ---
with tab2:
    st.subheader("Spread Analysis")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Avg Spread", "$0.02")
    col2.metric("Median Spread", "$0.01")
    col3.metric("Spread Vol", "$0.008")
    col4.metric("Effective Spread", "$0.02")

    st.markdown("#### Spread Statistics")
    spread_data = pd.DataFrame([
        {"Metric": "Average Absolute Spread", "Value": "$0.020"},
        {"Metric": "Median Absolute Spread", "Value": "$0.015"},
        {"Metric": "Spread Volatility", "Value": "$0.008"},
        {"Metric": "Relative Spread (bps)", "Value": "1.3"},
        {"Metric": "Effective Spread", "Value": "$0.018"},
        {"Metric": "Observations", "Value": "21"},
    ])
    st.dataframe(spread_data, use_container_width=True, hide_index=True)

# --- Tab 3: Impact ---
with tab3:
    st.subheader("Market Impact Estimation")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Trade Size", "10,000 shares")
    col2.metric("Participation Rate", "0.02%")
    col3.metric("Total Cost", "0.8 bps")
    col4.metric("Execution Days", "1")

    st.markdown("#### Impact Breakdown")
    impact_data = pd.DataFrame([
        {"Component": "Spread Cost", "Value": "0.7 bps", "Fraction": "85%"},
        {"Component": "Impact Cost", "Value": "0.1 bps", "Fraction": "15%"},
        {"Component": "Total Cost", "Value": "0.8 bps", "Fraction": "100%"},
    ])
    st.dataframe(impact_data, use_container_width=True, hide_index=True)

    st.markdown("#### Size Sensitivity")
    size_data = pd.DataFrame([
        {"Trade Size": "1,000", "Participation": "0.002%", "Impact (bps)": 0.3, "Days": 1},
        {"Trade Size": "10,000", "Participation": "0.019%", "Impact (bps)": 0.8, "Days": 1},
        {"Trade Size": "100,000", "Participation": "0.191%", "Impact (bps)": 2.5, "Days": 1},
        {"Trade Size": "500,000", "Participation": "0.956%", "Impact (bps)": 5.6, "Days": 1},
        {"Trade Size": "1,000,000", "Participation": "1.913%", "Impact (bps)": 7.9, "Days": 2},
        {"Trade Size": "5,000,000", "Participation": "9.564%", "Impact (bps)": 17.8, "Days": 10},
    ])
    st.dataframe(size_data, use_container_width=True, hide_index=True)

# --- Tab 4: Scoring ---
with tab4:
    st.subheader("Liquidity Scoring")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Composite Score", "87/100")
    col2.metric("Spread Score", "95/100")
    col3.metric("Volume Score", "90/100")
    col4.metric("Impact Score", "82/100")

    st.markdown("#### Universe Ranking")
    ranking_data = pd.DataFrame([
        {"Rank": 1, "Symbol": "SPY", "Score": 98, "Level": "Very High", "Spread (bps)": 0.3},
        {"Rank": 2, "Symbol": "AAPL", "Score": 87, "Level": "Very High", "Spread (bps)": 1.3},
        {"Rank": 3, "Symbol": "MSFT", "Score": 86, "Level": "Very High", "Spread (bps)": 1.5},
        {"Rank": 4, "Symbol": "GOOGL", "Score": 84, "Level": "Very High", "Spread (bps)": 2.0},
        {"Rank": 5, "Symbol": "TSLA", "Score": 82, "Level": "Very High", "Spread (bps)": 2.5},
        {"Rank": 6, "Symbol": "NVDA", "Score": 80, "Level": "Very High", "Spread (bps)": 2.8},
        {"Rank": 7, "Symbol": "JPM", "Score": 78, "Level": "High", "Spread (bps)": 3.0},
        {"Rank": 8, "Symbol": "META", "Score": 75, "Level": "High", "Spread (bps)": 3.5},
    ])
    st.dataframe(ranking_data, use_container_width=True, hide_index=True)

# --- Tab 5: Redemption Risk ---
with tab5:
    st.subheader("Redemption Risk Analysis")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Redemption Probability", "12%")
    col2.metric("Buffer Coverage", "1.8x")
    col3.metric("Buffer Deficit", "$0")
    col4.metric("Days to Liquidate", "8.5")

    st.markdown("#### Stress Scenarios")
    scenario_data = pd.DataFrame([
        {
            "Scenario": "Normal (5%)",
            "Redemption": "$5.0M",
            "Coverage": "3.60x",
            "Shortfall": "$0",
            "Days": 0,
        },
        {
            "Scenario": "Stressed (15%)",
            "Redemption": "$15.0M",
            "Coverage": "1.20x",
            "Shortfall": "$0",
            "Days": 0,
        },
        {
            "Scenario": "Crisis (30%)",
            "Redemption": "$30.0M",
            "Coverage": "0.60x",
            "Shortfall": "$12.0M",
            "Days": 7,
        },
    ])
    st.dataframe(scenario_data, use_container_width=True, hide_index=True)

    st.markdown("#### Liquidity Buffer")
    buffer_data = pd.DataFrame([
        {"Metric": "Total AUM", "Value": "$100M"},
        {"Metric": "Cash on Hand", "Value": "$8M"},
        {"Metric": "Liquid Assets (< 1 day)", "Value": "$10M"},
        {"Metric": "Expected Redemption (5%)", "Value": "$5M"},
        {"Metric": "Required Buffer (1.5x)", "Value": "$7.5M"},
        {"Metric": "Buffer Coverage", "Value": "2.40x"},
        {"Metric": "Buffer Deficit", "Value": "$0"},
    ])
    st.dataframe(buffer_data, use_container_width=True, hide_index=True)

    st.markdown("#### Liquidation Schedule")
    liq_sched = pd.DataFrame([
        {"Priority": 1, "Symbol": "SPY", "Value": "$15M", "ADV": "$25B",
         "DTL": "0.1 days", "Cost": "1.2 bps"},
        {"Priority": 2, "Symbol": "AAPL", "Value": "$12M", "ADV": "$8B",
         "DTL": "0.2 days", "Cost": "2.5 bps"},
        {"Priority": 3, "Symbol": "MSFT", "Value": "$10M", "ADV": "$5B",
         "DTL": "0.2 days", "Cost": "3.0 bps"},
        {"Priority": 4, "Symbol": "NVDA", "Value": "$8M", "ADV": "$3B",
         "DTL": "0.3 days", "Cost": "4.5 bps"},
        {"Priority": 5, "Symbol": "ILLQ", "Value": "$5M", "ADV": "$50M",
         "DTL": "10.0 days", "Cost": "45.0 bps"},
    ])
    st.dataframe(liq_sched, use_container_width=True, hide_index=True)

# --- Tab 6: LaVaR ---
with tab6:
    st.subheader("Liquidity-Adjusted VaR")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Standard VaR (95%)", "$1.65M")
    col2.metric("Liquidity Cost", "$0.35M")
    col3.metric("LaVaR", "$2.00M")
    col4.metric("Liquidity Share", "17.5%")

    st.markdown("#### VaR Components")
    var_data = pd.DataFrame([
        {"Component": "Standard VaR (95%, 1-day)", "Pct": "1.65%", "Dollar": "$1.65M"},
        {"Component": "Spread Cost", "Pct": "0.12%", "Dollar": "$0.12M"},
        {"Component": "Market Impact", "Pct": "0.23%", "Dollar": "$0.23M"},
        {"Component": "Total Liquidity Cost", "Pct": "0.35%", "Dollar": "$0.35M"},
        {"Component": "LaVaR (95%, 1-day)", "Pct": "2.00%", "Dollar": "$2.00M"},
    ])
    st.dataframe(var_data, use_container_width=True, hide_index=True)

    st.markdown("#### Position LaVaR Decomposition")
    pos_lavar = pd.DataFrame([
        {"Symbol": "ILLQ", "Weight": "5%", "VaR Contrib": "0.08%",
         "Liq Cost": "0.15%", "LaVaR": "0.23%", "DTL": "10.0 days"},
        {"Symbol": "AAPL", "Weight": "20%", "VaR Contrib": "0.33%",
         "Liq Cost": "0.04%", "LaVaR": "0.37%", "DTL": "0.2 days"},
        {"Symbol": "SPY", "Weight": "30%", "VaR Contrib": "0.50%",
         "Liq Cost": "0.02%", "LaVaR": "0.52%", "DTL": "0.1 days"},
        {"Symbol": "MSFT", "Weight": "25%", "VaR Contrib": "0.41%",
         "Liq Cost": "0.05%", "LaVaR": "0.46%", "DTL": "0.2 days"},
        {"Symbol": "NVDA", "Weight": "20%", "VaR Contrib": "0.33%",
         "Liq Cost": "0.09%", "LaVaR": "0.42%", "DTL": "0.3 days"},
    ])
    st.dataframe(pos_lavar, use_container_width=True, hide_index=True)

    st.markdown("#### Horizon Sensitivity")
    horizon_data = pd.DataFrame([
        {"Horizon": "1 day", "VaR": "1.65%", "Liq Cost": "0.35%", "LaVaR": "2.00%"},
        {"Horizon": "5 days", "VaR": "3.69%", "Liq Cost": "0.78%", "LaVaR": "4.47%"},
        {"Horizon": "10 days", "VaR": "5.22%", "Liq Cost": "1.11%", "LaVaR": "6.33%"},
        {"Horizon": "20 days", "VaR": "7.38%", "Liq Cost": "1.57%", "LaVaR": "8.95%"},
    ])
    st.dataframe(horizon_data, use_container_width=True, hide_index=True)

# --- Tab 7: Spread Modeling ---
with tab7:
    st.subheader("Spread Modeling & Decomposition")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Roll Spread", "1.8 bps")
    col2.metric("Adverse Selection", "42%")
    col3.metric("Forecast (5d)", "2.1 bps")
    col4.metric("Stress Ratio", "2.8x")

    st.markdown("#### Spread Decomposition")
    decomp_data = pd.DataFrame([
        {"Component": "Adverse Selection", "Share": "42%", "BPS": "0.76",
         "Driver": "Information asymmetry"},
        {"Component": "Order Processing", "Share": "38%", "BPS": "0.68",
         "Driver": "Fixed execution costs"},
        {"Component": "Inventory", "Share": "20%", "BPS": "0.36",
         "Driver": "Market-maker inventory risk"},
    ])
    st.dataframe(decomp_data, use_container_width=True, hide_index=True)

    st.markdown("#### Spread Regime Profile")
    regime_data = pd.DataFrame([
        {"Condition": "Normal (VIX < 18)", "Avg Spread": "1.3 bps",
         "Max Spread": "2.5 bps"},
        {"Condition": "Elevated (VIX 18-25)", "Avg Spread": "2.1 bps",
         "Max Spread": "4.0 bps"},
        {"Condition": "Stressed (VIX 25-35)", "Avg Spread": "3.6 bps",
         "Max Spread": "8.5 bps"},
        {"Condition": "Crisis (VIX > 35)", "Avg Spread": "6.2 bps",
         "Max Spread": "15.0 bps"},
    ])
    st.dataframe(regime_data, use_container_width=True, hide_index=True)

# --- Tab 8: Market Depth ---
with tab8:
    st.subheader("Market Depth Analysis")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Depth Score", "78/100")
    col2.metric("Bid Depth (10bps)", "$2.3M")
    col3.metric("Imbalance", "+0.15")
    col4.metric("Resilience", "82/100")

    st.markdown("#### Depth at Price Levels")
    depth_data = pd.DataFrame([
        {"Distance": "5 bps", "Bid Depth": "$850K", "Ask Depth": "$720K",
         "Total": "$1.57M"},
        {"Distance": "10 bps", "Bid Depth": "$2.3M", "Ask Depth": "$1.9M",
         "Total": "$4.2M"},
        {"Distance": "25 bps", "Bid Depth": "$5.8M", "Ask Depth": "$5.1M",
         "Total": "$10.9M"},
    ])
    st.dataframe(depth_data, use_container_width=True, hide_index=True)

    st.markdown("#### Order Book Imbalance Signal")
    imb_data = pd.DataFrame([
        {"Symbol": "AAPL", "Best Bid Size": "1,200", "Best Ask Size": "800",
         "Imbalance": "+0.20", "Direction": "Up", "Strength": "Moderate"},
        {"Symbol": "NVDA", "Best Bid Size": "500", "Best Ask Size": "1,100",
         "Imbalance": "-0.38", "Direction": "Down", "Strength": "Strong"},
        {"Symbol": "MSFT", "Best Bid Size": "900", "Best Ask Size": "950",
         "Imbalance": "-0.03", "Direction": "Neutral", "Strength": "Weak"},
    ])
    st.dataframe(imb_data, use_container_width=True, hide_index=True)

# --- Tab 9: Illiquidity Premium ---
with tab9:
    st.subheader("Illiquidity Premium Estimation")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Amihud Ratio", "0.00032")
    col2.metric("Premium", "85 bps/yr")
    col3.metric("Quintile", "Q3")
    col4.metric("Long-Short", "210 bps")

    st.markdown("#### Quintile Analysis")
    quintile_data = pd.DataFrame([
        {"Quintile": "Q1 (Most Liquid)", "Avg Amihud": "0.00001",
         "Avg Premium": "12 bps", "N Stocks": "100"},
        {"Quintile": "Q2", "Avg Amihud": "0.00008",
         "Avg Premium": "45 bps", "N Stocks": "100"},
        {"Quintile": "Q3", "Avg Amihud": "0.00032",
         "Avg Premium": "85 bps", "N Stocks": "100"},
        {"Quintile": "Q4", "Avg Amihud": "0.00120",
         "Avg Premium": "145 bps", "N Stocks": "100"},
        {"Quintile": "Q5 (Least Liquid)", "Avg Amihud": "0.00500",
         "Avg Premium": "222 bps", "N Stocks": "100"},
    ])
    st.dataframe(quintile_data, use_container_width=True, hide_index=True)

# --- Tab 10: Concentration ---
with tab10:
    st.subheader("Liquidity Concentration Risk")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Overall Score", "72/100")
    col2.metric("Risk Level", "Moderate")
    col3.metric("HHI", "0.18")
    col4.metric("Illiquid Weight", "8.5%")

    st.markdown("#### Position Liquidity")
    pos_data = pd.DataFrame([
        {"Symbol": "AAPL", "Weight": "25%", "DTL": "0.01 days",
         "Score": "98", "Status": "Liquid"},
        {"Symbol": "MSFT", "Weight": "20%", "DTL": "0.01 days",
         "Score": "97", "Status": "Liquid"},
        {"Symbol": "NVDA", "Weight": "15%", "DTL": "0.02 days",
         "Score": "95", "Status": "Liquid"},
        {"Symbol": "SMCAP", "Weight": "8%", "DTL": "3.5 days",
         "Score": "55", "Status": "Moderate"},
        {"Symbol": "ILLQ", "Weight": "5%", "DTL": "12.0 days",
         "Score": "25", "Status": "Concentrated"},
    ])
    st.dataframe(pos_data, use_container_width=True, hide_index=True)

    st.markdown("#### Liquidation Timeline")
    timeline_data = pd.DataFrame([
        {"Timeframe": "1 Day", "% Liquidatable": "73%",
         "Value": "$73M", "Positions": "3"},
        {"Timeframe": "5 Days", "% Liquidatable": "91.5%",
         "Value": "$91.5M", "Positions": "4"},
        {"Timeframe": "20 Days", "% Liquidatable": "100%",
         "Value": "$100M", "Positions": "5"},
    ])
    st.dataframe(timeline_data, use_container_width=True, hide_index=True)

# --- Tab 11: Cost Curves ---
with tab11:
    st.subheader("Transaction Cost Curves")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Optimal Size", "52,300 shares")
    col2.metric("Optimal Cost", "1.8 bps")
    col3.metric("Max Feasible", "523,000 shares")
    col4.metric("Strategy", "Single")

    st.markdown("#### Cost vs Size")
    cost_data = pd.DataFrame([
        {"Size": "1,000", "Participation": "0.002%", "Spread": "0.7 bps",
         "Impact": "0.1 bps", "Total": "0.8 bps", "Days": "0.1"},
        {"Size": "10,000", "Participation": "0.02%", "Spread": "0.7 bps",
         "Impact": "0.3 bps", "Total": "1.0 bps", "Days": "0.1"},
        {"Size": "50,000", "Participation": "0.10%", "Spread": "0.7 bps",
         "Impact": "0.6 bps", "Total": "1.3 bps", "Days": "0.1"},
        {"Size": "100,000", "Participation": "0.19%", "Spread": "0.7 bps",
         "Impact": "0.9 bps", "Total": "1.6 bps", "Days": "0.2"},
        {"Size": "500,000", "Participation": "0.96%", "Spread": "0.7 bps",
         "Impact": "2.0 bps", "Total": "2.7 bps", "Days": "1.0"},
        {"Size": "1,000,000", "Participation": "1.91%", "Spread": "0.7 bps",
         "Impact": "2.8 bps", "Total": "3.5 bps", "Days": "1.9"},
    ])
    st.dataframe(cost_data, use_container_width=True, hide_index=True)

    st.markdown("#### Optimal Execution")
    opt_data = pd.DataFrame([
        {"Symbol": "AAPL", "Target": "100K shares", "Strategy": "Single",
         "Slices": "1", "Cost": "1.6 bps", "Days": "0.2"},
        {"Symbol": "MSFT", "Target": "100K shares", "Strategy": "Single",
         "Slices": "1", "Cost": "1.8 bps", "Days": "0.3"},
        {"Symbol": "ILLQ", "Target": "100K shares", "Strategy": "Multi-Day",
         "Slices": "5", "Cost": "12.5 bps", "Days": "5.0"},
    ])
    st.dataframe(opt_data, use_container_width=True, hide_index=True)
