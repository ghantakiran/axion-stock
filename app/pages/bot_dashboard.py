"""Bot Command Center Dashboard (PRD-137).

6 tabs: Bot Control, Performance, Signal History, Configuration, Positions, Alerts.
Unified control center for the autonomous trading bot with real-time monitoring.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import streamlit as st
from app.styles import inject_global_styles

try:
    st.set_page_config(page_title="Bot Command Center", page_icon="", layout="wide")
except Exception:
    pass

inject_global_styles()
st.title("Bot Command Center")
st.caption("Unified dashboard for monitoring and controlling the autonomous trading bot")

import numpy as np
import pandas as pd
from datetime import datetime, timedelta, date

# ---- Try importing real module ----
_module_available = False
try:
    from src.bot_dashboard import (
        BotController,
        BotEvent,
        BotState,
        DashboardConfig,
        PerformanceMetrics,
        DailyMetrics,
        CloudChartRenderer,
    )
    _module_available = True
except ImportError:
    st.warning("Bot dashboard module (src.bot_dashboard) is not available. Showing demo data.")

# =====================================================================
# Demo Data
# =====================================================================

np.random.seed(137)

TICKERS = ["AAPL", "MSFT", "NVDA", "TSLA", "META", "GOOGL", "AMD", "SPY", "QQQ", "AMZN"]
SIGNAL_TYPES = ["ema_bullish_cross", "ema_bearish_cross", "cloud_breakout", "pullback_entry", "momentum_surge", "mean_reversion"]
INSTRUMENT_MODES = ["options", "leveraged_etf", "both"]
BOT_STATUSES = ["paper", "live", "paused", "killed"]
SEVERITIES = ["info", "warning", "error", "critical"]

# Bot state
bot_status = "paper"
uptime_seconds = 14523
account_equity = 102450.00
starting_equity = 100000.00
daily_pnl = 1284.50
daily_pnl_pct = 0.0127
unrealized_pnl = 345.20
realized_pnl = 939.30
total_trades_today = 12
winning_trades = 8
losing_trades = 4
win_rate = winning_trades / total_trades_today
current_exposure_pct = 0.42
max_drawdown_today = 0.018
kill_switch_active = False

# Positions
n_positions = 6
demo_positions = pd.DataFrame({
    "ticker": np.random.choice(TICKERS[:7], n_positions, replace=False),
    "side": np.random.choice(["long", "short"], n_positions, p=[0.7, 0.3]),
    "instrument": np.random.choice(["0DTE Call", "0DTE Put", "TQQQ", "SQQQ", "Stock", "1DTE Call"], n_positions),
    "entry_price": np.round(np.random.uniform(150, 500, n_positions), 2),
    "current_price": np.round(np.random.uniform(150, 510, n_positions), 2),
    "quantity": np.random.randint(10, 200, n_positions),
    "unrealized_pnl": np.round(np.random.normal(50, 200, n_positions), 2),
    "conviction": np.random.randint(45, 95, n_positions),
    "entry_time": [(datetime(2025, 4, 10, 9, 30) + timedelta(minutes=np.random.randint(0, 300))).strftime("%H:%M") for _ in range(n_positions)],
    "exit_strategy": np.random.choice(["trailing_stop", "time_stop", "profit_target", "ema_cross"], n_positions),
})

# Signals
n_signals = 30
base_time = datetime(2025, 4, 10, 9, 30)
demo_signals = pd.DataFrame({
    "signal_id": [f"SIG-{4000 + i}" for i in range(n_signals)],
    "timestamp": [(base_time + timedelta(minutes=i * 10)).strftime("%H:%M:%S") for i in range(n_signals)],
    "ticker": np.random.choice(TICKERS, n_signals),
    "signal_type": np.random.choice(SIGNAL_TYPES, n_signals),
    "direction": np.random.choice(["long", "short"], n_signals, p=[0.6, 0.4]),
    "conviction": np.random.randint(30, 98, n_signals),
    "acted_on": np.random.choice(["Yes", "No", "Filtered"], n_signals, p=[0.45, 0.30, 0.25]),
    "reason": np.random.choice(
        ["Executed", "Low conviction", "Risk gate blocked", "Max positions", "Duplicate", "Market hours", "Stale signal"],
        n_signals,
    ),
})

# Trade history
n_history = 25
demo_history = pd.DataFrame({
    "trade_id": [f"BOT-{6000 + i}" for i in range(n_history)],
    "timestamp": [(base_time + timedelta(minutes=i * 20)).strftime("%Y-%m-%d %H:%M") for i in range(n_history)],
    "ticker": np.random.choice(TICKERS, n_history),
    "direction": np.random.choice(["long", "short"], n_history, p=[0.65, 0.35]),
    "instrument": np.random.choice(["0DTE Call", "0DTE Put", "TQQQ", "SQQQ", "Stock"], n_history),
    "entry_price": np.round(np.random.uniform(100, 500, n_history), 2),
    "exit_price": np.round(np.random.uniform(100, 510, n_history), 2),
    "pnl": np.round(np.random.normal(40, 250, n_history), 2),
    "hold_minutes": np.random.randint(5, 240, n_history),
    "exit_reason": np.random.choice(["trailing_stop", "profit_target", "time_stop", "ema_cross", "kill_switch"], n_history),
})

# Events / Alerts
n_events = 20
demo_events = pd.DataFrame({
    "timestamp": [(base_time + timedelta(minutes=i * 12)).strftime("%H:%M:%S") for i in range(n_events)],
    "event_type": np.random.choice(
        ["lifecycle", "trade", "signal", "risk", "kill", "config_change", "error"],
        n_events,
    ),
    "severity": np.random.choice(SEVERITIES, n_events, p=[0.40, 0.30, 0.20, 0.10]),
    "message": np.random.choice([
        "Bot started in paper mode",
        "Signal processed: AAPL ema_bullish_cross",
        "Trade executed: LONG NVDA 0DTE Call",
        "Risk gate blocked: max positions reached",
        "Position closed: TSLA trailing stop hit",
        "Daily loss limit warning: 75% of limit",
        "Kill switch activated: manual",
        "Config updated: max_positions changed",
        "Connection to data feed restored",
        "Error: order rejected by broker",
    ], n_events),
})

# Daily P&L series (for equity curve)
daily_pnl_series = np.round(np.random.normal(200, 500, 20), 2)
cumulative_pnl = np.cumsum(daily_pnl_series)

# =====================================================================
# Tabs
# =====================================================================

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Bot Control",
    "Performance",
    "Signal History",
    "Configuration",
    "Positions",
    "Alerts",
])

# -- Tab 1: Bot Control ----------------------------------------------------

with tab1:
    st.subheader("Bot Status & Control")

    # Status banner
    status_colors = {
        "paper": "info",
        "live": "success",
        "paused": "warning",
        "killed": "error",
    }
    status_label = bot_status.upper()
    if bot_status == "paper":
        st.info(f"Bot Status: **{status_label}** -- Paper trading mode active")
    elif bot_status == "live":
        st.success(f"Bot Status: **{status_label}** -- Live trading active")
    elif bot_status == "paused":
        st.warning(f"Bot Status: **{status_label}** -- Signal processing paused")
    else:
        st.error(f"Bot Status: **{status_label}** -- Kill switch engaged")

    st.divider()

    # Top-level metrics
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Account Equity", f"${account_equity:,.2f}", f"+${account_equity - starting_equity:,.2f}")
    m2.metric("Daily P&L", f"${daily_pnl:,.2f}", f"{daily_pnl_pct:.1%}")
    m3.metric("Win Rate", f"{win_rate:.0%}", f"{winning_trades}W / {losing_trades}L")
    m4.metric("Trades Today", total_trades_today)

    st.divider()

    m5, m6, m7, m8 = st.columns(4)
    hours = uptime_seconds // 3600
    minutes = (uptime_seconds % 3600) // 60
    m5.metric("Uptime", f"{hours}h {minutes}m")
    m6.metric("Exposure", f"{current_exposure_pct:.0%}")
    m7.metric("Max DD Today", f"{max_drawdown_today:.1%}")
    m8.metric("Open Positions", n_positions)

    st.divider()

    # Control buttons
    st.subheader("Bot Controls")
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        if st.button("Start (Paper)", type="primary", use_container_width=True):
            st.success("Bot started in paper mode.")
            st.info("In production: BotController.start(paper_mode=True)")

    with col2:
        if st.button("Pause", use_container_width=True):
            st.warning("Bot paused -- existing positions monitored.")
            st.info("In production: BotController.pause()")

    with col3:
        if st.button("Resume", use_container_width=True):
            st.success("Bot resumed.")
            st.info("In production: BotController.resume()")

    with col4:
        if st.button("Start (Live)", use_container_width=True):
            st.error("Live mode requires confirmation. Use with caution.")

    with col5:
        if st.button("KILL SWITCH", type="secondary", use_container_width=True):
            st.error("Kill switch activated -- all trading halted.")
            st.info("In production: BotController.kill(reason='Manual')")

    st.divider()

    # Quick status panel
    st.subheader("System Status")
    sys_data = pd.DataFrame({
        "Component": ["Data Feed", "Broker", "Risk Gate", "Signal Engine", "Kill Switch"],
        "Status": ["Connected", "Paper (simulated)", "Active", "Running", "Inactive"],
        "Last Check": [
            (datetime.now() - timedelta(seconds=5)).strftime("%H:%M:%S"),
            (datetime.now() - timedelta(seconds=12)).strftime("%H:%M:%S"),
            (datetime.now() - timedelta(seconds=3)).strftime("%H:%M:%S"),
            (datetime.now() - timedelta(seconds=8)).strftime("%H:%M:%S"),
            (datetime.now() - timedelta(seconds=2)).strftime("%H:%M:%S"),
        ],
    })
    st.dataframe(sys_data, use_container_width=True)


# -- Tab 2: Performance ---------------------------------------------------

with tab2:
    st.subheader("Bot Performance Metrics")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total P&L", f"${realized_pnl + unrealized_pnl:,.2f}")
    m2.metric("Realized P&L", f"${realized_pnl:,.2f}")
    m3.metric("Unrealized P&L", f"${unrealized_pnl:,.2f}")
    gross_profit = demo_history[demo_history["pnl"] > 0]["pnl"].sum()
    gross_loss = demo_history[demo_history["pnl"] <= 0]["pnl"].sum()
    pf = abs(gross_profit / gross_loss) if gross_loss != 0 else float("inf")
    m4.metric("Profit Factor", f"{pf:.2f}" if pf < 100 else "Inf")

    st.divider()

    # Equity curve
    st.subheader("Equity Curve (20 days)")
    eq_df = pd.DataFrame({"Cumulative P&L ($)": cumulative_pnl}, index=range(1, 21))
    st.line_chart(eq_df)

    st.divider()

    # Daily P&L
    st.subheader("Daily P&L")
    daily_df = pd.DataFrame({"Daily P&L ($)": daily_pnl_series}, index=range(1, 21))
    st.bar_chart(daily_df)

    st.divider()

    # Win rate by ticker
    st.subheader("Win Rate by Ticker")
    wr_by_ticker = {}
    for ticker in TICKERS[:7]:
        t_trades = demo_history[demo_history["ticker"] == ticker]
        if len(t_trades) > 0:
            wr_by_ticker[ticker] = (t_trades["pnl"] > 0).mean()
    if wr_by_ticker:
        wr_df = pd.Series(wr_by_ticker).sort_values(ascending=True)
        st.bar_chart(wr_df)

    st.divider()

    # Win rate by conviction
    st.subheader("Win Rate by Conviction Level")
    conviction_buckets = {"High (75+)": [], "Medium (50-74)": [], "Low (<50)": []}
    for _, sig in demo_signals.iterrows():
        if sig["acted_on"] == "Yes":
            matching = demo_history[demo_history["ticker"] == sig["ticker"]]
            if len(matching) > 0:
                trade = matching.iloc[0]
                if sig["conviction"] >= 75:
                    conviction_buckets["High (75+)"].append(trade["pnl"])
                elif sig["conviction"] >= 50:
                    conviction_buckets["Medium (50-74)"].append(trade["pnl"])
                else:
                    conviction_buckets["Low (<50)"].append(trade["pnl"])

    conv_stats = []
    for level, pnls in conviction_buckets.items():
        if pnls:
            conv_stats.append({
                "Conviction Level": level,
                "Trades": len(pnls),
                "Win Rate": f"{sum(1 for p in pnls if p > 0) / len(pnls):.0%}",
                "Avg P&L": f"${np.mean(pnls):.2f}",
            })
    if conv_stats:
        st.dataframe(pd.DataFrame(conv_stats), use_container_width=True)

    st.divider()

    # Hold time analysis
    st.subheader("Average Hold Time by Exit Reason")
    exit_hold = demo_history.groupby("exit_reason")["hold_minutes"].mean().round(1).sort_values(ascending=True)
    st.bar_chart(exit_hold)


# -- Tab 3: Signal History -------------------------------------------------

with tab3:
    st.subheader("Signal History")

    acted = len(demo_signals[demo_signals["acted_on"] == "Yes"])
    filtered_out = len(demo_signals[demo_signals["acted_on"] == "Filtered"])
    ignored = len(demo_signals[demo_signals["acted_on"] == "No"])

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Signals", n_signals)
    m2.metric("Acted On", acted, f"{acted / n_signals:.0%}")
    m3.metric("Filtered", filtered_out)
    m4.metric("Avg Conviction", f"{demo_signals['conviction'].mean():.0f}")

    st.divider()

    # Signal filters
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        sig_ticker = st.selectbox("Ticker", ["All"] + sorted(TICKERS), key="sh_ticker")
    with col_f2:
        sig_type = st.selectbox("Signal Type", ["All"] + sorted(SIGNAL_TYPES), key="sh_type")
    with col_f3:
        sig_acted = st.selectbox("Acted On", ["All", "Yes", "No", "Filtered"], key="sh_acted")

    sig_display = demo_signals.copy()
    if sig_ticker != "All":
        sig_display = sig_display[sig_display["ticker"] == sig_ticker]
    if sig_type != "All":
        sig_display = sig_display[sig_display["signal_type"] == sig_type]
    if sig_acted != "All":
        sig_display = sig_display[sig_display["acted_on"] == sig_acted]

    st.dataframe(sig_display, use_container_width=True)

    st.divider()

    st.subheader("Signals by Type")
    type_counts = demo_signals["signal_type"].value_counts()
    st.bar_chart(type_counts)

    st.divider()

    st.subheader("Filter/Rejection Reasons")
    rejected = demo_signals[demo_signals["acted_on"] != "Yes"]
    if len(rejected) > 0:
        reason_counts = rejected["reason"].value_counts()
        st.bar_chart(reason_counts)
    else:
        st.info("All signals were acted on.")

    st.divider()

    # Trade journal from bot
    st.subheader("Trade Execution History")
    st.dataframe(demo_history, use_container_width=True)


# -- Tab 4: Configuration --------------------------------------------------

with tab4:
    st.subheader("Bot Configuration")

    if _module_available:
        st.success("Bot dashboard module loaded successfully.")
    else:
        st.info("Module not loaded. Configuration shown as demo defaults.")

    st.divider()

    st.subheader("Dashboard Settings")
    config_data = pd.DataFrame({
        "Setting": [
            "Refresh Interval (s)", "P&L Chart Lookback (days)", "Max Signals Displayed",
            "Max Events Displayed", "Sound Alerts", "Paper Mode",
            "Require Live Confirmation",
        ],
        "Value": ["5", "30", "50", "100", "Enabled", "Yes", "Yes"],
    })
    st.dataframe(config_data, use_container_width=True)

    st.divider()

    # Editable config
    st.subheader("Update Configuration")
    with st.expander("Edit Settings", expanded=False):
        cfg_c1, cfg_c2 = st.columns(2)
        with cfg_c1:
            new_refresh = st.number_input("Refresh Interval (s)", 1, 60, 5, key="cfg_refresh")
            new_lookback = st.number_input("P&L Lookback (days)", 1, 365, 30, key="cfg_lookback")
            new_max_signals = st.number_input("Max Signals", 10, 500, 50, key="cfg_signals")
            new_max_events = st.number_input("Max Events", 10, 1000, 100, key="cfg_events")
        with cfg_c2:
            new_sound = st.checkbox("Enable Sound Alerts", True, key="cfg_sound")
            new_paper = st.checkbox("Paper Mode", True, key="cfg_paper")
            new_confirm = st.checkbox("Require Live Confirmation", True, key="cfg_confirm")

        if st.button("Apply Configuration", type="primary", use_container_width=True):
            st.success("Configuration updated successfully.")
            st.info("In production: BotController.update_config({...})")

    st.divider()

    # Risk settings
    st.subheader("Risk Parameters")
    risk_config = pd.DataFrame({
        "Parameter": [
            "Max Daily Loss ($)", "Max Daily Loss (%)", "Max Positions",
            "Max Single Position (%)", "Max Exposure (%)",
            "Kill Switch Threshold ($)", "Circuit Breaker Cooldown (min)",
        ],
        "Value": ["$5,000", "5%", "10", "15%", "60%", "$3,000", "15"],
    })
    st.dataframe(risk_config, use_container_width=True)

    st.divider()

    st.subheader("Instrument Configuration")
    inst_config = pd.DataFrame({
        "Setting": [
            "Instrument Mode", "Options Enabled", "Leveraged ETF Enabled",
            "Max 0DTE Contracts", "Max ETF Shares",
            "Strike Selection", "ETF Routing",
        ],
        "Value": ["both", "Yes", "Yes", "5", "500", "ATM +/- 2 strikes", "Sector-based"],
    })
    st.dataframe(inst_config, use_container_width=True)


# -- Tab 5: Positions ------------------------------------------------------

with tab5:
    st.subheader("Open Positions")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Open Positions", n_positions)
    m2.metric("Unrealized P&L", f"${demo_positions['unrealized_pnl'].sum():,.2f}")
    m3.metric("Avg Conviction", f"{demo_positions['conviction'].mean():.0f}")
    long_count = len(demo_positions[demo_positions["side"] == "long"])
    short_count = len(demo_positions[demo_positions["side"] == "short"])
    m4.metric("Long / Short", f"{long_count} / {short_count}")

    st.divider()

    st.dataframe(demo_positions, use_container_width=True)

    st.divider()

    # Position P&L breakdown
    st.subheader("Position P&L Breakdown")
    pos_pnl = demo_positions.set_index("ticker")["unrealized_pnl"].sort_values(ascending=True)
    st.bar_chart(pos_pnl)

    st.divider()

    # Exit strategies summary
    st.subheader("Exit Strategy Distribution")
    exit_dist = demo_positions["exit_strategy"].value_counts()
    st.bar_chart(exit_dist)

    st.divider()

    # Position details
    st.subheader("Position Details")
    selected_pos = st.selectbox(
        "Select Position",
        demo_positions["ticker"].tolist(),
        key="pos_select",
    )
    pos_row = demo_positions[demo_positions["ticker"] == selected_pos].iloc[0]

    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Ticker", pos_row["ticker"])
    p2.metric("Side", pos_row["side"].upper())
    p3.metric("Instrument", pos_row["instrument"])
    p4.metric("Quantity", pos_row["quantity"])

    p5, p6, p7, p8 = st.columns(4)
    p5.metric("Entry Price", f"${pos_row['entry_price']:.2f}")
    p6.metric("Current Price", f"${pos_row['current_price']:.2f}")
    pnl_val = pos_row["unrealized_pnl"]
    p7.metric("Unrealized P&L", f"${pnl_val:+,.2f}")
    p8.metric("Exit Strategy", pos_row["exit_strategy"].replace("_", " ").title())


# -- Tab 6: Alerts ---------------------------------------------------------

with tab6:
    st.subheader("Bot Alerts & Events")

    critical_count = len(demo_events[demo_events["severity"] == "critical"])
    error_count = len(demo_events[demo_events["severity"] == "error"])
    warning_count = len(demo_events[demo_events["severity"] == "warning"])
    info_count = len(demo_events[demo_events["severity"] == "info"])

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Events", n_events)
    m2.metric("Critical", critical_count)
    m3.metric("Errors", error_count)
    m4.metric("Warnings", warning_count)

    if critical_count > 0:
        st.error(f"{critical_count} critical event(s) detected -- review immediately.")
    if error_count > 0:
        st.warning(f"{error_count} error(s) logged.")

    st.divider()

    # Filter events
    sev_filter = st.selectbox(
        "Filter by Severity",
        ["All"] + SEVERITIES,
        key="alert_sev",
    )
    evt_display = demo_events.copy()
    if sev_filter != "All":
        evt_display = evt_display[evt_display["severity"] == sev_filter]

    st.dataframe(evt_display, use_container_width=True)

    st.divider()

    st.subheader("Events by Type")
    evt_type_counts = demo_events["event_type"].value_counts()
    st.bar_chart(evt_type_counts)

    st.divider()

    st.subheader("Events by Severity")
    sev_counts = demo_events["severity"].value_counts()
    st.bar_chart(sev_counts)

    st.divider()

    # Critical/Error event details
    st.subheader("Critical & Error Events")
    critical_errors = demo_events[demo_events["severity"].isin(["critical", "error"])]
    if len(critical_errors) > 0:
        for _, evt in critical_errors.iterrows():
            if evt["severity"] == "critical":
                st.error(f"[{evt['timestamp']}] **{evt['event_type'].upper()}**: {evt['message']}")
            else:
                st.warning(f"[{evt['timestamp']}] **{evt['event_type'].upper()}**: {evt['message']}")
    else:
        st.success("No critical or error events.")
