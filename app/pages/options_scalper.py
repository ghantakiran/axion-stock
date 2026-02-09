"""Options & ETF Scalper Dashboard (PRD-136).

Specialized scalping engine control center.
5 tabs: Live Scalps, Strike/ETF Picker, Scalp History, Performance, Mode Comparison.
"""

try:
    import streamlit as st
    st.set_page_config(page_title="Options Scalper", layout="wide")
except Exception:
    import streamlit as st

st.title("Options & ETF Scalper")
st.caption("0DTE/1DTE options and leveraged ETF scalping engine")

# ── Sidebar Controls ────────────────────────────────────────────

with st.sidebar:
    st.subheader("Scalp Settings")
    scalp_mode = st.selectbox(
        "Scalp Mode",
        ["Options", "Leveraged ETFs", "Both"],
    )
    paper_mode = st.toggle("Paper Mode", value=True)

    st.divider()
    st.subheader("Options Settings")
    target_delta = st.slider("Target Delta", 0.20, 0.60, (0.30, 0.50))
    max_spread = st.slider("Max Spread (%)", 1, 20, 10)
    profit_target = st.slider("Profit Target (%)", 10, 50, 25)
    max_loss = st.slider("Max Loss (%)", 20, 80, 50)

    st.divider()
    st.subheader("ETF Settings")
    etf_stop = st.slider("ETF Stop Loss (%)", 1, 5, 2)
    etf_target = st.slider("ETF Profit Target (%)", 1, 5, 2)
    prefer_3x = st.toggle("Prefer 3x ETFs", value=True)

# ── Tabs ────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Live Scalps",
    "Strike / ETF Picker",
    "Scalp History",
    "Performance",
    "Mode Comparison",
])

# ── Tab 1: Live Scalps ─────────────────────────────────────────

with tab1:
    st.subheader("Active Scalp Positions")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Options Positions**")
        options_positions = [
            {
                "Ticker": "SPY", "Type": "0DTE Call", "Strike": 500,
                "Contracts": 3, "Entry": "$2.50", "Current": "$3.10",
                "P&L": "+$180", "P&L %": "+24%", "Delta": 0.52,
                "Theta": -0.12, "Status": "Near Target",
            },
        ]
        if scalp_mode in ("Options", "Both"):
            st.dataframe(options_positions, use_container_width=True)
        else:
            st.info("Options mode disabled")

    with col2:
        st.markdown("**ETF Positions**")
        etf_positions = [
            {
                "Ticker": "TQQQ", "Signal": "QQQ Long", "Leverage": "3x",
                "Shares": 200, "Entry": "$48.50", "Current": "$49.30",
                "P&L": "+$160", "P&L %": "+1.6%", "Stop": "$47.53",
                "Target": "$49.47",
            },
        ]
        if scalp_mode in ("Leveraged ETFs", "Both"):
            st.dataframe(etf_positions, use_container_width=True)
        else:
            st.info("ETF mode disabled")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Active Scalps", "2")
    with col2:
        st.metric("Total P&L", "+$340")
    with col3:
        st.metric("Win Rate", "67%")
    with col4:
        st.metric("Avg Hold", "12 min")


# ── Tab 2: Strike / ETF Picker ─────────────────────────────────

with tab2:
    if scalp_mode in ("Options", "Both"):
        st.subheader("Options Chain — Strike Selection")

        st.selectbox("Ticker", ["SPY", "QQQ", "NVDA", "TSLA", "AAPL"])

        chain_data = [
            {"Strike": 498, "Type": "Call", "Delta": 0.58, "Bid": "$3.20", "Ask": "$3.40",
             "Volume": 5200, "OI": 12000, "IV": "22%", "Score": 72},
            {"Strike": 500, "Type": "Call", "Delta": 0.48, "Bid": "$2.40", "Ask": "$2.60",
             "Volume": 8100, "OI": 15000, "IV": "20%", "Score": 88},
            {"Strike": 502, "Type": "Call", "Delta": 0.35, "Bid": "$1.50", "Ask": "$1.70",
             "Volume": 3500, "OI": 8000, "IV": "21%", "Score": 75},
        ]
        st.dataframe(chain_data, use_container_width=True)

    if scalp_mode in ("Leveraged ETFs", "Both"):
        st.subheader("Leveraged ETF Selector")

        etf_catalog = [
            {"Sector": "NASDAQ-100", "Bull": "TQQQ (3x)", "Bear": "SQQQ (3x)",
             "Vol": "$12.5B", "Spread": "0.01%"},
            {"Sector": "S&P 500", "Bull": "SPXL (3x)", "Bear": "SPXS (3x)",
             "Vol": "$5.2B", "Spread": "0.02%"},
            {"Sector": "Semiconductors", "Bull": "SOXL (3x)", "Bear": "SOXS (3x)",
             "Vol": "$3.8B", "Spread": "0.03%"},
            {"Sector": "Technology", "Bull": "TECL (3x)", "Bear": "TECS (3x)",
             "Vol": "$1.1B", "Spread": "0.04%"},
            {"Sector": "Financials", "Bull": "FAS (3x)", "Bear": "FAZ (3x)",
             "Vol": "$800M", "Spread": "0.04%"},
        ]
        st.dataframe(etf_catalog, use_container_width=True)


# ── Tab 3: Scalp History ───────────────────────────────────────

with tab3:
    st.subheader("Recent Scalps")

    history = [
        {"Time": "14:32", "Type": "Options", "Ticker": "SPY 500C",
         "Entry": "$2.50", "Exit": "$3.10", "P&L": "+$180", "Reason": "Target"},
        {"Time": "13:15", "Type": "ETF", "Ticker": "TQQQ",
         "Entry": "$48.20", "Exit": "$49.10", "P&L": "+$180", "Reason": "Target"},
        {"Time": "11:42", "Type": "Options", "Ticker": "QQQ 440P",
         "Entry": "$1.80", "Exit": "$0.90", "P&L": "-$270", "Reason": "Stop Loss"},
        {"Time": "10:55", "Type": "ETF", "Ticker": "SOXL",
         "Entry": "$32.00", "Exit": "$32.60", "P&L": "+$90", "Reason": "Target"},
    ]
    st.dataframe(history, use_container_width=True)


# ── Tab 4: Performance ─────────────────────────────────────────

with tab4:
    st.subheader("Scalp Performance")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Options Performance**")
        st.metric("Total Trades", "15")
        st.metric("Win Rate", "60%")
        st.metric("Net P&L", "+$1,250")
        st.metric("Avg P&L/Trade", "+$83")
    with col2:
        st.markdown("**ETF Performance**")
        st.metric("Total Trades", "22")
        st.metric("Win Rate", "68%")
        st.metric("Net P&L", "+$1,840")
        st.metric("Avg P&L/Trade", "+$84")

    st.divider()
    st.subheader("By Exit Reason")
    exit_perf = [
        {"Reason": "Profit Target", "Count": 20, "Win Rate": "100%", "Avg P&L": "+$125"},
        {"Reason": "Stop Loss", "Count": 10, "Win Rate": "0%", "Avg P&L": "-$180"},
        {"Reason": "Cloud Flip", "Count": 4, "Win Rate": "75%", "Avg P&L": "+$45"},
        {"Reason": "Time Cutoff", "Count": 3, "Win Rate": "33%", "Avg P&L": "-$20"},
    ]
    st.dataframe(exit_perf, use_container_width=True)


# ── Tab 5: Mode Comparison ─────────────────────────────────────

with tab5:
    st.subheader("Options vs Leveraged ETFs — Comparison")
    st.info("Compare the same signals executed as options vs leveraged ETFs")

    comparison = [
        {"Metric": "Win Rate", "Options": "60%", "ETFs": "68%"},
        {"Metric": "Avg P&L/Trade", "Options": "+$83", "ETFs": "+$84"},
        {"Metric": "Max Loss/Trade", "Options": "-$375", "ETFs": "-$180"},
        {"Metric": "Avg Hold Time", "Options": "18 min", "ETFs": "15 min"},
        {"Metric": "Sharpe Ratio", "Options": "1.85", "ETFs": "2.10"},
        {"Metric": "Total Net P&L", "Options": "+$1,250", "ETFs": "+$1,840"},
    ]
    st.dataframe(comparison, use_container_width=True)

    st.markdown("""
    **Key Insights:**
    - ETF scalps have higher win rate due to linear risk profile (no theta decay)
    - Options scalps have higher max loss per trade (premium can go to zero)
    - Both modes produce similar average P&L per trade
    - ETFs recommended for accounts without options approval or for simpler execution
    """)
