"""Trade Journal Dashboard (PRD-66).

4 tabs: Trade Journal, Analytics, Performance, Insights.
Tracks entries, emotions, setups, strategies, and generates actionable insights.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import streamlit as st
from app.styles import inject_global_styles

try:
    st.set_page_config(page_title="Trade Journal", page_icon="", layout="wide")
except Exception:
    pass

inject_global_styles()
st.title("Trade Journal")
st.caption("Record, review, and analyze every trade with emotion tracking and pattern recognition")

import numpy as np
import pandas as pd
from datetime import datetime, timedelta, date

# ---- Try importing real module ----
_module_available = False
try:
    from src.journal import JournalAnalytics, JournalService
    from src.journal.analytics import (
        PerformanceMetrics,
        DimensionBreakdown,
        EmotionAnalysis,
        PatternInsight,
    )
    _module_available = True
except ImportError:
    st.warning("Journal module (src.journal) is not available. Showing demo data.")

# =====================================================================
# Demo Data
# =====================================================================

np.random.seed(66)

TICKERS = ["AAPL", "MSFT", "NVDA", "TSLA", "META", "GOOGL", "AMZN", "AMD", "SPY", "QQQ"]
SETUPS = ["breakout", "pullback", "reversal", "momentum", "mean_reversion", "gap_play"]
STRATEGIES = ["EMA Cloud Trend", "RSI Divergence", "VWAP Reversion", "ORB Breakout"]
TRADE_TYPES = ["scalp", "day", "swing"]
EMOTIONS = ["confident", "anxious", "neutral", "fearful", "excited", "frustrated"]
DIRECTIONS = ["long", "short"]

n_entries = 60
base_time = datetime(2025, 4, 1, 9, 30)

entry_prices = np.round(np.random.uniform(100, 500, n_entries), 2)
pnl_values = np.round(np.random.normal(50, 300, n_entries), 2)
exit_flags = np.random.choice([True, False], n_entries, p=[0.80, 0.20])

demo_entries = pd.DataFrame({
    "entry_id": [f"JRN-{1000 + i}" for i in range(n_entries)],
    "symbol": np.random.choice(TICKERS, n_entries),
    "direction": np.random.choice(DIRECTIONS, n_entries, p=[0.65, 0.35]),
    "trade_type": np.random.choice(TRADE_TYPES, n_entries),
    "setup": np.random.choice(SETUPS, n_entries),
    "strategy": np.random.choice(STRATEGIES, n_entries),
    "entry_date": [(base_time + timedelta(hours=i * 6)).strftime("%Y-%m-%d %H:%M") for i in range(n_entries)],
    "entry_price": entry_prices,
    "quantity": np.random.randint(10, 200, n_entries),
    "status": ["closed" if f else "open" for f in exit_flags],
    "realized_pnl": [round(p, 2) if f else None for p, f in zip(pnl_values, exit_flags)],
    "pre_emotion": np.random.choice(EMOTIONS, n_entries),
    "during_emotion": np.random.choice(EMOTIONS, n_entries),
    "post_emotion": np.random.choice(EMOTIONS, n_entries),
})

closed = demo_entries[demo_entries["status"] == "closed"].copy()
winners = closed[closed["realized_pnl"] > 0]
losers = closed[closed["realized_pnl"] <= 0]

total_pnl = closed["realized_pnl"].sum()
win_rate = len(winners) / len(closed) if len(closed) > 0 else 0
avg_winner = winners["realized_pnl"].mean() if len(winners) > 0 else 0
avg_loser = losers["realized_pnl"].mean() if len(losers) > 0 else 0
profit_factor = abs(winners["realized_pnl"].sum() / losers["realized_pnl"].sum()) if losers["realized_pnl"].sum() != 0 else float("inf")

# Equity curve
cumulative_pnl = closed["realized_pnl"].cumsum().values

# =====================================================================
# Tabs
# =====================================================================

tab1, tab2, tab3, tab4 = st.tabs([
    "Trade Journal",
    "Analytics",
    "Performance",
    "Insights",
])

# -- Tab 1: Trade Journal --------------------------------------------------

with tab1:
    st.subheader("Trade Journal Entries")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Entries", n_entries)
    m2.metric("Open Positions", len(demo_entries[demo_entries["status"] == "open"]))
    m3.metric("Closed Trades", len(closed))
    m4.metric("Total P&L", f"${total_pnl:,.2f}")

    st.divider()

    # Filters
    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    with col_f1:
        filter_symbol = st.selectbox("Filter Symbol", ["All"] + sorted(TICKERS), key="j_sym")
    with col_f2:
        filter_setup = st.selectbox("Filter Setup", ["All"] + sorted(SETUPS), key="j_setup")
    with col_f3:
        filter_status = st.selectbox("Filter Status", ["All", "open", "closed"], key="j_status")
    with col_f4:
        filter_type = st.selectbox("Filter Trade Type", ["All"] + sorted(TRADE_TYPES), key="j_type")

    filtered = demo_entries.copy()
    if filter_symbol != "All":
        filtered = filtered[filtered["symbol"] == filter_symbol]
    if filter_setup != "All":
        filtered = filtered[filtered["setup"] == filter_setup]
    if filter_status != "All":
        filtered = filtered[filtered["status"] == filter_status]
    if filter_type != "All":
        filtered = filtered[filtered["trade_type"] == filter_type]

    st.dataframe(filtered, use_container_width=True)

    st.divider()

    # New entry form
    st.subheader("New Journal Entry")
    with st.expander("Add Trade Entry", expanded=False):
        fc1, fc2, fc3 = st.columns(3)
        with fc1:
            new_symbol = st.text_input("Symbol", "AAPL", key="new_sym")
            new_direction = st.selectbox("Direction", DIRECTIONS, key="new_dir")
            new_price = st.number_input("Entry Price", min_value=0.01, value=175.00, key="new_price")
        with fc2:
            new_quantity = st.number_input("Quantity", min_value=1, value=100, key="new_qty")
            new_setup = st.selectbox("Setup", SETUPS, key="new_setup")
            new_strategy = st.selectbox("Strategy", STRATEGIES, key="new_strat")
        with fc3:
            new_type = st.selectbox("Trade Type", TRADE_TYPES, key="new_type")
            new_emotion = st.selectbox("Pre-Trade Emotion", EMOTIONS, key="new_emo")
            new_notes = st.text_area("Notes", "", key="new_notes", height=80)

        if st.button("Save Entry", type="primary", use_container_width=True):
            st.success(f"Entry saved: {new_direction.upper()} {new_quantity} {new_symbol} @ ${new_price:.2f}")
            st.info("Note: In production, this would be persisted via JournalService.create_entry().")


# -- Tab 2: Analytics ------------------------------------------------------

with tab2:
    st.subheader("Trading Analytics")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Win Rate", f"{win_rate:.0%}")
    m2.metric("Profit Factor", f"{profit_factor:.2f}" if profit_factor < 100 else "Inf")
    m3.metric("Avg Winner", f"${avg_winner:.2f}")
    m4.metric("Avg Loser", f"${avg_loser:.2f}")

    st.divider()

    # Breakdown by setup
    st.subheader("Performance by Setup")
    setup_stats = []
    for setup in SETUPS:
        setup_trades = closed[closed["setup"] == setup]
        if len(setup_trades) > 0:
            s_winners = setup_trades[setup_trades["realized_pnl"] > 0]
            setup_stats.append({
                "Setup": setup.replace("_", " ").title(),
                "Trades": len(setup_trades),
                "Win Rate": f"{len(s_winners) / len(setup_trades):.0%}",
                "Total P&L": f"${setup_trades['realized_pnl'].sum():,.2f}",
                "Avg P&L": f"${setup_trades['realized_pnl'].mean():.2f}",
            })
    st.dataframe(pd.DataFrame(setup_stats), use_container_width=True)

    st.divider()

    # Breakdown by strategy
    st.subheader("Performance by Strategy")
    strat_stats = []
    for strat in STRATEGIES:
        strat_trades = closed[closed["strategy"] == strat]
        if len(strat_trades) > 0:
            s_winners = strat_trades[strat_trades["realized_pnl"] > 0]
            strat_stats.append({
                "Strategy": strat,
                "Trades": len(strat_trades),
                "Win Rate": f"{len(s_winners) / len(strat_trades):.0%}",
                "Total P&L": f"${strat_trades['realized_pnl'].sum():,.2f}",
                "Profit Factor": f"{abs(s_winners['realized_pnl'].sum() / strat_trades[strat_trades['realized_pnl'] <= 0]['realized_pnl'].sum()):.2f}" if strat_trades[strat_trades["realized_pnl"] <= 0]["realized_pnl"].sum() != 0 else "Inf",
            })
    st.dataframe(pd.DataFrame(strat_stats), use_container_width=True)

    st.divider()

    # Breakdown by day of week
    st.subheader("Performance by Day of Week")
    closed_copy = closed.copy()
    closed_copy["day"] = pd.to_datetime(closed_copy["entry_date"]).dt.day_name()
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    day_stats = []
    for day in day_order:
        day_trades = closed_copy[closed_copy["day"] == day]
        if len(day_trades) > 0:
            d_winners = day_trades[day_trades["realized_pnl"] > 0]
            day_stats.append({
                "Day": day,
                "Trades": len(day_trades),
                "Win Rate": f"{len(d_winners) / len(day_trades):.0%}",
                "Avg P&L": f"${day_trades['realized_pnl'].mean():.2f}",
            })
    if day_stats:
        st.dataframe(pd.DataFrame(day_stats), use_container_width=True)

    st.divider()

    # Emotion analysis
    st.subheader("Emotion Correlation Analysis")
    emotion_stats = []
    for emotion in EMOTIONS:
        emo_trades = closed[closed["pre_emotion"] == emotion]
        if len(emo_trades) > 0:
            emo_winners = emo_trades[emo_trades["realized_pnl"] > 0]
            wr = len(emo_winners) / len(emo_trades)
            avg_pnl = emo_trades["realized_pnl"].mean()
            if wr >= 0.6 and avg_pnl > 0:
                rec = "Favorable"
            elif wr <= 0.4 or avg_pnl < 0:
                rec = "Avoid"
            else:
                rec = "Neutral"
            emotion_stats.append({
                "Pre-Trade Emotion": emotion.title(),
                "Trades": len(emo_trades),
                "Win Rate": f"{wr:.0%}",
                "Avg P&L": f"${avg_pnl:.2f}",
                "Recommendation": rec,
            })
    st.dataframe(pd.DataFrame(emotion_stats), use_container_width=True)


# -- Tab 3: Performance ----------------------------------------------------

with tab3:
    st.subheader("Performance Metrics")

    m1, m2, m3, m4 = st.columns(4)
    expectancy = (win_rate * avg_winner) - ((1 - win_rate) * abs(avg_loser))
    m1.metric("Expectancy", f"${expectancy:.2f}")
    m2.metric("Total P&L", f"${total_pnl:,.2f}")
    m3.metric("Largest Win", f"${winners['realized_pnl'].max():,.2f}" if len(winners) > 0 else "$0")
    m4.metric("Largest Loss", f"${losers['realized_pnl'].min():,.2f}" if len(losers) > 0 else "$0")

    st.divider()

    # Equity curve
    st.subheader("Equity Curve")
    if len(cumulative_pnl) > 0:
        eq_df = pd.DataFrame({"Cumulative P&L ($)": cumulative_pnl}, index=range(len(cumulative_pnl)))
        st.line_chart(eq_df)

    st.divider()

    # Drawdown
    st.subheader("Drawdown Analysis")
    if len(cumulative_pnl) > 0:
        peak = np.maximum.accumulate(cumulative_pnl)
        drawdown = peak - cumulative_pnl
        max_dd = np.max(drawdown)
        max_dd_pct = max_dd / np.max(peak) if np.max(peak) > 0 else 0
        current_dd = drawdown[-1]

        d1, d2, d3 = st.columns(3)
        d1.metric("Max Drawdown", f"${max_dd:,.2f}")
        d2.metric("Max DD (%)", f"{max_dd_pct:.1%}")
        d3.metric("Current Drawdown", f"${current_dd:,.2f}")

        dd_df = pd.DataFrame({"Drawdown ($)": -drawdown}, index=range(len(drawdown)))
        st.area_chart(dd_df)

    st.divider()

    # Streak analysis
    st.subheader("Streak Analysis")
    streaks = []
    current_streak = 0
    current_type = None
    max_win_streak = 0
    max_loss_streak = 0

    for pnl in closed["realized_pnl"].values:
        if pnl > 0:
            if current_type == "win":
                current_streak += 1
            else:
                current_streak = 1
                current_type = "win"
            max_win_streak = max(max_win_streak, current_streak)
        else:
            if current_type == "loss":
                current_streak += 1
            else:
                current_streak = 1
                current_type = "loss"
            max_loss_streak = max(max_loss_streak, current_streak)

    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Max Win Streak", max_win_streak)
    s2.metric("Max Loss Streak", max_loss_streak)
    s3.metric("Current Streak", current_streak)
    s4.metric("Current Type", (current_type or "N/A").title())

    st.divider()

    # P&L distribution
    st.subheader("P&L Distribution")
    pnl_hist = pd.DataFrame({"Trade P&L ($)": closed["realized_pnl"].values})
    st.bar_chart(pnl_hist.value_counts(bins=15).sort_index())


# -- Tab 4: Insights -------------------------------------------------------

with tab4:
    st.subheader("Automated Trading Insights")
    st.markdown("Pattern recognition and recommendations generated from your trading data.")

    # Generate demo insights
    insights = []

    # Best setup insight
    if len(closed) > 0:
        setup_perf = closed.groupby("setup")["realized_pnl"].agg(["mean", "count", "sum"])
        setup_perf["win_rate"] = closed.groupby("setup")["realized_pnl"].apply(lambda x: (x > 0).mean())

        best_setup = setup_perf.sort_values("win_rate", ascending=False).iloc[0]
        best_setup_name = setup_perf.sort_values("win_rate", ascending=False).index[0]
        insights.append({
            "type": "strength",
            "icon": "++",
            "title": f"Strong Setup: {best_setup_name.replace('_', ' ').title()}",
            "description": f"Your {best_setup_name} setup has a {best_setup['win_rate']:.0%} win rate "
                          f"across {int(best_setup['count'])} trades with total P&L ${best_setup['sum']:,.2f}.",
            "confidence": min(0.9, best_setup["count"] / 20),
        })

        worst_setup = setup_perf.sort_values("win_rate", ascending=True).iloc[0]
        worst_setup_name = setup_perf.sort_values("win_rate", ascending=True).index[0]
        if worst_setup["win_rate"] < 0.45:
            insights.append({
                "type": "weakness",
                "icon": "--",
                "title": f"Underperforming Setup: {worst_setup_name.replace('_', ' ').title()}",
                "description": f"Your {worst_setup_name} setup has only {worst_setup['win_rate']:.0%} win rate. "
                              f"Consider reviewing or reducing size on this setup.",
                "confidence": min(0.9, worst_setup["count"] / 20),
            })

    # Emotion insight
    avoid_emotions = [e for e in emotion_stats if e["Recommendation"] == "Avoid"]
    for em in avoid_emotions[:2]:
        insights.append({
            "type": "recommendation",
            "icon": "!",
            "title": f"Caution: Trading While {em['Pre-Trade Emotion']}",
            "description": f"When entering trades feeling {em['Pre-Trade Emotion'].lower()}, "
                          f"your win rate is {em['Win Rate']} with avg P&L {em['Avg P&L']}. "
                          f"Consider stepping away when feeling this emotion.",
            "confidence": 0.75,
        })

    # Risk/reward insight
    if expectancy > 0:
        insights.append({
            "type": "strength",
            "icon": "++",
            "title": "Positive Expectancy",
            "description": f"Your expected P&L per trade is ${expectancy:.2f}. "
                          f"Maintain this edge by sticking to your best setups.",
            "confidence": 0.8,
        })
    else:
        insights.append({
            "type": "weakness",
            "icon": "--",
            "title": "Negative Expectancy",
            "description": f"Your expected P&L per trade is ${expectancy:.2f}. "
                          f"Focus on improving win rate or risk/reward ratio.",
            "confidence": 0.8,
        })

    # Profit factor
    if profit_factor >= 1.5 and profit_factor < 100:
        insights.append({
            "type": "strength",
            "icon": "++",
            "title": f"Solid Profit Factor: {profit_factor:.2f}",
            "description": "Your gross profits significantly exceed gross losses. Keep it up.",
            "confidence": 0.85,
        })

    st.divider()

    for insight in insights:
        if insight["type"] == "strength":
            st.success(f"**{insight['title']}** (Confidence: {insight['confidence']:.0%})\n\n{insight['description']}")
        elif insight["type"] == "weakness":
            st.error(f"**{insight['title']}** (Confidence: {insight['confidence']:.0%})\n\n{insight['description']}")
        elif insight["type"] == "recommendation":
            st.warning(f"**{insight['title']}** (Confidence: {insight['confidence']:.0%})\n\n{insight['description']}")
        else:
            st.info(f"**{insight['title']}** (Confidence: {insight['confidence']:.0%})\n\n{insight['description']}")

    st.divider()

    # Daily review section
    st.subheader("Daily Review")
    review_data = pd.DataFrame({
        "Date": [(date(2025, 4, 1) + timedelta(days=i)).isoformat() for i in range(14)],
        "Trades": np.random.randint(2, 12, 14),
        "Net P&L ($)": np.round(np.random.normal(80, 400, 14), 2),
        "Win Rate": [f"{r:.0%}" for r in np.random.uniform(0.3, 0.85, 14)],
        "Followed Plan": np.random.choice(["Yes", "No"], 14, p=[0.75, 0.25]),
        "Rating (1-5)": np.random.randint(2, 6, 14),
    })
    st.dataframe(review_data, use_container_width=True)
