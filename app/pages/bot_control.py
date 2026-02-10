"""Bot Control Center Dashboard (PRD-137).

Unified command center for the autonomous trading bot.
6 tabs: Command Center, Positions, Signals, Cloud Charts, Performance, Configuration.
"""

try:
    import streamlit as st
from app.styles import inject_global_styles
    st.set_page_config(page_title="Bot Control", layout="wide")

inject_global_styles()
except Exception:
    import streamlit as st

st.title("Bot Control Center")
st.caption("Autonomous trading bot — monitor, control, and analyze")

# ── Top Bar: Status & Controls ──────────────────────────────────

col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
with col1:
    bot_status = st.selectbox(
        "Bot Status",
        ["Paper Mode", "Live Mode", "Paused", "Killed"],
        index=0,
        label_visibility="collapsed",
    )
with col2:
    if st.button("Pause", use_container_width=True):
        st.toast("Bot paused")
with col3:
    if st.button("Resume", use_container_width=True):
        st.toast("Bot resumed")
with col4:
    if st.button("KILL SWITCH", type="primary", use_container_width=True):
        st.error("Kill switch activated!")

# ── Summary Metrics Bar ─────────────────────────────────────────

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("Day P&L", "+$1,247", "+2.4%")
with col2:
    st.metric("Win Rate", "68%", "12 trades")
with col3:
    st.metric("Open Positions", "4")
with col4:
    st.metric("Exposure", "32%")
with col5:
    st.metric("Max Drawdown", "-1.8%")

st.divider()

# ── Tabs ────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Command Center",
    "Positions",
    "Signals",
    "Cloud Charts",
    "Performance",
    "Configuration",
])

# ── Tab 1: Command Center ──────────────────────────────────────

with tab1:
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("Intraday P&L")
        # Placeholder for P&L chart
        st.line_chart({"P&L": [0, 200, 150, 400, 350, 600, 800, 1100, 1247]})

    with col2:
        st.subheader("Status")
        st.text(f"Status: {'Paper' if bot_status == 'Paper Mode' else bot_status}")
        st.text("Uptime: 4h 23m")
        st.text("Broker: Alpaca (Paper)")
        st.text("Mode: Both")
        st.text("Feed: Connected")

    st.divider()
    st.subheader("Active Positions")
    positions_data = [
        {"Ticker": "NVDA", "Dir": "Long", "Type": "Stock", "Shares": 150,
         "P&L": "+$234", "Cloud": "Bullish"},
        {"Ticker": "SPY 500C", "Dir": "Long Call", "Type": "0DTE", "Shares": "3 contracts",
         "P&L": "+$180", "Cloud": "Bullish"},
        {"Ticker": "TQQQ", "Dir": "Long", "Type": "3x ETF", "Shares": 200,
         "P&L": "+$156", "Cloud": "Bullish"},
        {"Ticker": "SOXS", "Dir": "Long", "Type": "3x ETF", "Shares": 150,
         "P&L": "-$48", "Cloud": "Bearish"},
    ]
    st.dataframe(positions_data, use_container_width=True)

    st.divider()
    st.subheader("Recent Signals")
    signals_data = [
        {"Time": "14:23", "Ticker": "AAPL", "Signal": "Cloud Cross Bullish",
         "Conv": 82, "Action": "Executed"},
        {"Time": "14:15", "Ticker": "MSFT", "Signal": "Cloud Bounce Long",
         "Conv": 67, "Action": "Executed (half)"},
        {"Time": "14:08", "Ticker": "AMZN", "Signal": "Cloud Flip Bearish",
         "Conv": 45, "Action": "Logged Only"},
        {"Time": "13:55", "Ticker": "META", "Signal": "MTF Confluence",
         "Conv": 91, "Action": "Executed"},
    ]
    st.dataframe(signals_data, use_container_width=True)


# ── Tab 2: Positions ───────────────────────────────────────────

with tab2:
    st.subheader("All Open Positions")

    position_groups = {
        "Day Trades": [
            {"Ticker": "NVDA", "Entry": "$128.50", "Current": "$130.06",
             "Shares": 150, "P&L": "+$234", "Stop": "$126.00", "Target": "$133.00",
             "Hold": "2h 15m"},
        ],
        "Options Scalps": [
            {"Ticker": "SPY 500C 0DTE", "Entry": "$2.50", "Current": "$3.10",
             "Contracts": 3, "P&L": "+$180", "Delta": 0.52, "Theta": -0.12},
        ],
        "ETF Scalps": [
            {"Ticker": "TQQQ", "Entry": "$48.50", "Current": "$49.28",
             "Shares": 200, "P&L": "+$156", "Stop": "$47.53", "Leverage": "3x"},
            {"Ticker": "SOXS", "Entry": "$9.60", "Current": "$9.28",
             "Shares": 150, "P&L": "-$48", "Stop": "$10.08", "Leverage": "3x"},
        ],
    }

    for group_name, group_positions in position_groups.items():
        st.markdown(f"**{group_name}**")
        st.dataframe(group_positions, use_container_width=True)


# ── Tab 3: Signals ─────────────────────────────────────────────

with tab3:
    st.subheader("Signal Feed")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.selectbox("Direction", ["All", "Long", "Short"], key="sig_dir")
    with col2:
        st.slider("Min Conviction", 0, 100, 50, key="sig_conv")
    with col3:
        st.selectbox("Signal Type", [
            "All", "Cloud Cross", "Cloud Flip", "Cloud Bounce",
            "Trend Aligned", "MTF Confluence", "Exhaustion",
        ], key="sig_type")

    all_signals = [
        {"Time": "14:23", "Ticker": "AAPL", "Type": "Cloud Cross Bull",
         "TF": "1m", "Conv": 82, "Dir": "Long", "Status": "Executed"},
        {"Time": "14:15", "Ticker": "MSFT", "Type": "Cloud Bounce Long",
         "TF": "5m", "Conv": 67, "Dir": "Long", "Status": "Executed"},
        {"Time": "14:08", "Ticker": "AMZN", "Type": "Cloud Flip Bear",
         "TF": "10m", "Conv": 45, "Dir": "Short", "Status": "Skipped"},
        {"Time": "13:55", "Ticker": "META", "Type": "MTF Confluence",
         "TF": "Multi", "Conv": 91, "Dir": "Long", "Status": "Executed"},
        {"Time": "13:42", "Ticker": "NVDA", "Type": "Trend Aligned Bull",
         "TF": "10m", "Conv": 88, "Dir": "Long", "Status": "Executed"},
    ]
    st.dataframe(all_signals, use_container_width=True)

    st.divider()
    st.subheader("Signal Heatmap")
    st.info("Signal strength by ticker x timeframe (coming soon)")


# ── Tab 4: Cloud Charts ───────────────────────────────────────

with tab4:
    st.subheader("EMA Cloud Charts")

    col1, col2 = st.columns([1, 3])
    with col1:
        chart_ticker = st.selectbox("Ticker", ["AAPL", "NVDA", "SPY", "QQQ", "MSFT", "TSLA"])
        chart_tf = st.radio("Timeframe", ["1m", "5m", "10m", "1h", "1d"])
    with col2:
        st.info(f"Cloud chart for {chart_ticker} ({chart_tf}) — requires live data feed")
        st.text("4 EMA Cloud Layers:")
        st.text("  Fast (5/12) — Signal triggers")
        st.text("  Pullback (8/9) — Trailing stops")
        st.text("  Trend (20/21) — Trend direction")
        st.text("  Macro (34/50) — Macro bias filter")


# ── Tab 5: Performance ─────────────────────────────────────────

with tab5:
    st.subheader("Trading Performance")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Profit Factor", "2.35")
    with col2:
        st.metric("Sharpe Ratio", "1.85")
    with col3:
        st.metric("Expectancy", "+$92/trade")
    with col4:
        st.metric("Max Drawdown", "-3.2%")

    st.divider()
    st.subheader("Cumulative P&L")
    st.line_chart({"Cumulative P&L": [
        0, 150, 80, 340, 290, 520, 680, 750, 900, 1050,
        980, 1200, 1350, 1247,
    ]})

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Win Rate by Conviction")
        conviction_wr = [
            {"Conviction": "High (75+)", "Trades": 8, "Win Rate": "75%"},
            {"Conviction": "Medium (50-74)", "Trades": 6, "Win Rate": "50%"},
            {"Conviction": "Low (<50)", "Trades": 2, "Win Rate": "0%"},
        ]
        st.dataframe(conviction_wr, use_container_width=True)
    with col2:
        st.subheader("P&L by Instrument")
        instrument_pnl = [
            {"Type": "Stocks", "Trades": 4, "Net P&L": "+$520"},
            {"Type": "Options", "Trades": 3, "Net P&L": "+$310"},
            {"Type": "Leveraged ETFs", "Trades": 5, "Net P&L": "+$417"},
        ]
        st.dataframe(instrument_pnl, use_container_width=True)


# ── Tab 6: Configuration ──────────────────────────────────────

with tab6:
    st.subheader("Bot Configuration")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Instrument Mode**")
        instrument_mode = st.radio(
            "Trade using:",
            ["Both (Options + ETFs)", "Options Only", "Leveraged ETFs Only"],
            help="How signals are routed to instruments",
        )

        st.markdown("**Risk Parameters**")
        st.slider("Max Risk/Trade (%)", 1, 10, 5, key="cfg_risk")
        st.slider("Max Positions", 1, 20, 10, key="cfg_pos")
        st.slider("Daily Loss Limit (%)", 1, 20, 10, key="cfg_loss")

    with col2:
        st.markdown("**EMA Cloud Settings**")
        st.text("Fast Cloud: EMA 5/12")
        st.text("Pullback Cloud: EMA 8/9")
        st.text("Trend Cloud: EMA 20/21")
        st.text("Macro Cloud: EMA 34/50")

        st.markdown("**Broker Settings**")
        st.selectbox("Primary Broker", ["Alpaca", "IBKR"], key="cfg_broker")
        cfg_paper = st.toggle("Paper Mode", value=True, key="cfg_paper")
        if not cfg_paper:
            st.warning("LIVE MODE — Real money will be traded!")

        st.markdown("**Kill Switch Triggers**")
        st.text("Daily loss > 10%")
        st.text("Equity < $25,000")
        st.text("3 consecutive losses > 3%")
