"""Trade Journal Dashboard - PRD-66.

Comprehensive trade journaling with:
- Trade entry and exit logging
- Emotion tracking
- Setup/strategy management
- Performance analytics by dimension
- Daily and periodic reviews
- Pattern recognition and insights
"""

import json
import sys
import os
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
from app.styles import inject_global_styles
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

try:
    st.set_page_config(page_title="Trade Journal", page_icon="📓", layout="wide")
except st.errors.StreamlitAPIException:
    pass

inject_global_styles()


# Try to import journal modules
try:
    from src.journal import JournalAnalytics, JournalService
    from src.db.session import get_session
    JOURNAL_AVAILABLE = True
except ImportError:
    JOURNAL_AVAILABLE = False


def init_session_state():
    """Initialize session state."""
    if "demo_entries" not in st.session_state:
        st.session_state.demo_entries = generate_demo_entries()
    if "demo_setups" not in st.session_state:
        st.session_state.demo_setups = [
            {"id": "breakout", "name": "Breakout", "category": "breakout"},
            {"id": "pullback", "name": "Pullback", "category": "pullback"},
            {"id": "reversal", "name": "Reversal", "category": "reversal"},
            {"id": "momentum", "name": "Momentum", "category": "momentum"},
            {"id": "gap_play", "name": "Gap Play", "category": "gap"},
        ]
    if "demo_strategies" not in st.session_state:
        st.session_state.demo_strategies = [
            {"id": "trend_follow", "name": "Trend Following"},
            {"id": "mean_rev", "name": "Mean Reversion"},
            {"id": "earnings", "name": "Earnings Play"},
        ]


def generate_demo_entries():
    """Generate demo journal entries."""
    import random

    symbols = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "AMD", "SPY", "QQQ"]
    setups = ["breakout", "pullback", "reversal", "momentum", "gap_play"]
    emotions = ["calm", "confident", "anxious", "fomo", "fearful", "euphoric"]
    trade_types = ["scalp", "day", "swing"]

    entries = []
    base_date = datetime.now() - timedelta(days=90)

    for i in range(50):
        entry_date = base_date + timedelta(days=random.randint(0, 85))
        symbol = random.choice(symbols)
        direction = random.choice(["long", "short"])
        entry_price = random.uniform(100, 500)
        quantity = random.randint(10, 100)

        # Some trades are still open
        is_closed = random.random() > 0.15

        if is_closed:
            exit_date = entry_date + timedelta(hours=random.randint(1, 72))
            # Slightly positive bias
            pnl_pct = random.gauss(0.01, 0.03)
            exit_price = entry_price * (1 + pnl_pct) if direction == "long" else entry_price * (1 - pnl_pct)
            realized_pnl = (exit_price - entry_price) * quantity if direction == "long" else (entry_price - exit_price) * quantity
        else:
            exit_date = None
            exit_price = None
            realized_pnl = None

        stop_distance = entry_price * random.uniform(0.01, 0.03)
        target_distance = stop_distance * random.uniform(1.5, 3.0)

        entries.append({
            "entry_id": f"TRD-{i+1:04d}",
            "symbol": symbol,
            "direction": direction,
            "trade_type": random.choice(trade_types),
            "entry_date": entry_date,
            "entry_price": round(entry_price, 2),
            "entry_quantity": quantity,
            "exit_date": exit_date,
            "exit_price": round(exit_price, 2) if exit_price else None,
            "realized_pnl": round(realized_pnl, 2) if realized_pnl else None,
            "realized_pnl_pct": round(pnl_pct * 100, 2) if is_closed else None,
            "setup_id": random.choice(setups),
            "strategy_id": random.choice(["trend_follow", "mean_rev", "earnings"]),
            "pre_trade_emotion": random.choice(emotions),
            "during_trade_emotion": random.choice(emotions) if is_closed else None,
            "post_trade_emotion": random.choice(emotions) if is_closed else None,
            "initial_stop": round(entry_price - stop_distance if direction == "long" else entry_price + stop_distance, 2),
            "initial_target": round(entry_price + target_distance if direction == "long" else entry_price - target_distance, 2),
            "risk_reward_planned": round(target_distance / stop_distance, 2),
            "notes": f"Demo trade {i+1}",
        })

    return entries


def calculate_demo_metrics(entries):
    """Calculate performance metrics from demo entries."""
    closed = [e for e in entries if e.get("exit_date")]

    if not closed:
        return {}

    winners = [e for e in closed if (e.get("realized_pnl") or 0) > 0]
    losers = [e for e in closed if (e.get("realized_pnl") or 0) < 0]

    total_profit = sum(e["realized_pnl"] for e in winners)
    total_loss = abs(sum(e["realized_pnl"] for e in losers))

    win_rate = len(winners) / len(closed) if closed else 0
    profit_factor = total_profit / total_loss if total_loss > 0 else float("inf")
    avg_winner = total_profit / len(winners) if winners else 0
    avg_loser = total_loss / len(losers) if losers else 0
    expectancy = (win_rate * avg_winner) - ((1 - win_rate) * avg_loser)

    return {
        "total_trades": len(closed),
        "winning_trades": len(winners),
        "losing_trades": len(losers),
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "expectancy": expectancy,
        "avg_winner": avg_winner,
        "avg_loser": avg_loser,
        "total_pnl": sum(e["realized_pnl"] for e in closed),
        "largest_win": max((e["realized_pnl"] for e in winners), default=0),
        "largest_loss": abs(min((e["realized_pnl"] for e in losers), default=0)),
    }


def render_metrics_row(metrics):
    """Render key metrics row."""
    col1, col2, col3, col4, col5, col6 = st.columns(6)

    col1.metric(
        "Total Trades",
        metrics.get("total_trades", 0),
        f"W: {metrics.get('winning_trades', 0)} / L: {metrics.get('losing_trades', 0)}"
    )
    col2.metric(
        "Win Rate",
        f"{metrics.get('win_rate', 0):.1%}",
        "Above 50%" if metrics.get('win_rate', 0) > 0.5 else "Below 50%"
    )
    col3.metric(
        "Profit Factor",
        f"{metrics.get('profit_factor', 0):.2f}" if metrics.get('profit_factor', 0) != float('inf') else "∞",
    )
    col4.metric(
        "Expectancy",
        f"${metrics.get('expectancy', 0):,.2f}",
    )
    col5.metric(
        "Total P&L",
        f"${metrics.get('total_pnl', 0):,.2f}",
        delta_color="normal" if metrics.get('total_pnl', 0) >= 0 else "inverse"
    )
    col6.metric(
        "Avg Win / Loss",
        f"${metrics.get('avg_winner', 0):,.0f} / ${metrics.get('avg_loser', 0):,.0f}",
    )


def render_equity_curve(entries):
    """Render equity curve chart."""
    closed = [e for e in entries if e.get("exit_date") and e.get("realized_pnl")]

    if not closed:
        st.info("No closed trades to display equity curve.")
        return

    # Sort by exit date
    closed = sorted(closed, key=lambda x: x["exit_date"])

    cumulative = 0
    data = []
    for e in closed:
        cumulative += e["realized_pnl"]
        data.append({
            "date": e["exit_date"],
            "cumulative_pnl": cumulative,
            "trade_pnl": e["realized_pnl"],
            "symbol": e["symbol"],
        })

    df = pd.DataFrame(data)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["date"],
        y=df["cumulative_pnl"],
        mode="lines+markers",
        name="Cumulative P&L",
        line=dict(color="#00C853", width=2),
        hovertemplate="<b>%{x}</b><br>Cumulative: $%{y:,.2f}<extra></extra>"
    ))

    # Add zero line
    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)

    # Color fill based on positive/negative
    fig.update_traces(fill='tozeroy', fillcolor='rgba(0, 200, 83, 0.1)')

    fig.update_layout(
        title="Equity Curve",
        xaxis_title="Date",
        yaxis_title="Cumulative P&L ($)",
        height=400,
        showlegend=False,
    )

    st.plotly_chart(fig, use_container_width=True)


def render_win_rate_by_setup(entries):
    """Render win rate by setup chart."""
    from collections import defaultdict

    closed = [e for e in entries if e.get("exit_date") and e.get("setup_id")]

    if not closed:
        st.info("No closed trades with setups.")
        return

    by_setup = defaultdict(list)
    for e in closed:
        by_setup[e["setup_id"]].append(e)

    data = []
    for setup_id, setup_entries in by_setup.items():
        winners = [e for e in setup_entries if (e.get("realized_pnl") or 0) > 0]
        win_rate = len(winners) / len(setup_entries) if setup_entries else 0
        total_pnl = sum(e.get("realized_pnl", 0) for e in setup_entries)
        data.append({
            "Setup": setup_id.replace("_", " ").title(),
            "Win Rate": win_rate,
            "Total P&L": total_pnl,
            "Trades": len(setup_entries),
        })

    df = pd.DataFrame(data).sort_values("Win Rate", ascending=True)

    colors = ["#EF5350" if wr < 0.5 else "#66BB6A" for wr in df["Win Rate"]]

    fig = go.Figure(go.Bar(
        x=df["Win Rate"],
        y=df["Setup"],
        orientation="h",
        marker_color=colors,
        text=[f"{wr:.0%} ({t} trades)" for wr, t in zip(df["Win Rate"], df["Trades"])],
        textposition="auto",
    ))

    fig.add_vline(x=0.5, line_dash="dash", line_color="gray", opacity=0.7)

    fig.update_layout(
        title="Win Rate by Setup",
        xaxis_title="Win Rate",
        yaxis_title="",
        xaxis=dict(tickformat=".0%", range=[0, 1]),
        height=300,
    )

    st.plotly_chart(fig, use_container_width=True)


def render_emotion_analysis(entries):
    """Render emotion vs performance analysis."""
    from collections import defaultdict

    closed = [e for e in entries if e.get("exit_date") and e.get("pre_trade_emotion")]

    if not closed:
        st.info("No closed trades with emotion data.")
        return

    by_emotion = defaultdict(list)
    for e in closed:
        by_emotion[e["pre_trade_emotion"]].append(e)

    data = []
    for emotion, emotion_entries in by_emotion.items():
        winners = [e for e in emotion_entries if (e.get("realized_pnl") or 0) > 0]
        win_rate = len(winners) / len(emotion_entries) if emotion_entries else 0
        avg_pnl = sum(e.get("realized_pnl", 0) for e in emotion_entries) / len(emotion_entries)

        if win_rate >= 0.6:
            recommendation = "Favorable"
            color = "#66BB6A"
        elif win_rate <= 0.4:
            recommendation = "Avoid"
            color = "#EF5350"
        else:
            recommendation = "Neutral"
            color = "#FFA726"

        data.append({
            "Emotion": emotion.title(),
            "Win Rate": win_rate,
            "Avg P&L": avg_pnl,
            "Trades": len(emotion_entries),
            "Status": recommendation,
            "Color": color,
        })

    df = pd.DataFrame(data).sort_values("Win Rate", ascending=False)

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=df["Emotion"],
        y=df["Win Rate"],
        marker_color=df["Color"],
        text=[f"{wr:.0%}" for wr in df["Win Rate"]],
        textposition="auto",
        name="Win Rate",
    ))

    fig.add_hline(y=0.5, line_dash="dash", line_color="gray", opacity=0.7)

    fig.update_layout(
        title="Pre-Trade Emotion vs Win Rate",
        xaxis_title="Emotional State",
        yaxis_title="Win Rate",
        yaxis=dict(tickformat=".0%", range=[0, 1]),
        height=350,
        showlegend=False,
    )

    st.plotly_chart(fig, use_container_width=True)

    # Show table
    st.dataframe(
        df[["Emotion", "Win Rate", "Avg P&L", "Trades", "Status"]].style.format({
            "Win Rate": "{:.1%}",
            "Avg P&L": "${:,.2f}",
        }),
        use_container_width=True,
        hide_index=True,
    )


def render_pnl_by_day(entries):
    """Render P&L by day of week."""
    closed = [e for e in entries if e.get("exit_date")]

    if not closed:
        return

    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    from collections import defaultdict

    by_day = defaultdict(list)
    for e in closed:
        day_idx = e["entry_date"].weekday()
        if day_idx < 5:
            by_day[days[day_idx]].append(e)

    data = []
    for day in days:
        day_entries = by_day.get(day, [])
        if day_entries:
            winners = [e for e in day_entries if (e.get("realized_pnl") or 0) > 0]
            total_pnl = sum(e.get("realized_pnl", 0) for e in day_entries)
            win_rate = len(winners) / len(day_entries)
        else:
            total_pnl = 0
            win_rate = 0
        data.append({
            "Day": day,
            "Total P&L": total_pnl,
            "Win Rate": win_rate,
            "Trades": len(day_entries),
        })

    df = pd.DataFrame(data)

    colors = ["#66BB6A" if pnl >= 0 else "#EF5350" for pnl in df["Total P&L"]]

    fig = go.Figure(go.Bar(
        x=df["Day"],
        y=df["Total P&L"],
        marker_color=colors,
        text=[f"${pnl:,.0f}" for pnl in df["Total P&L"]],
        textposition="auto",
    ))

    fig.update_layout(
        title="P&L by Day of Week",
        xaxis_title="",
        yaxis_title="Total P&L ($)",
        height=300,
    )

    st.plotly_chart(fig, use_container_width=True)


def render_trade_entry_form():
    """Render trade entry form."""
    st.subheader("Log New Trade")

    with st.form("trade_entry_form"):
        col1, col2, col3 = st.columns(3)

        with col1:
            symbol = st.text_input("Symbol", placeholder="AAPL").upper()
            direction = st.selectbox("Direction", ["long", "short"])
            trade_type = st.selectbox("Trade Type", ["day", "swing", "scalp", "position"])

        with col2:
            entry_date = st.date_input("Entry Date", value=date.today())
            entry_time = st.time_input("Entry Time")
            entry_price = st.number_input("Entry Price", min_value=0.01, step=0.01)

        with col3:
            entry_quantity = st.number_input("Quantity", min_value=1, step=1, value=100)
            initial_stop = st.number_input("Stop Loss", min_value=0.01, step=0.01)
            initial_target = st.number_input("Target", min_value=0.01, step=0.01)

        st.markdown("#### Context")
        col4, col5 = st.columns(2)

        with col4:
            setup = st.selectbox(
                "Setup",
                options=[s["id"] for s in st.session_state.demo_setups],
                format_func=lambda x: next((s["name"] for s in st.session_state.demo_setups if s["id"] == x), x)
            )
            strategy = st.selectbox(
                "Strategy",
                options=[s["id"] for s in st.session_state.demo_strategies],
                format_func=lambda x: next((s["name"] for s in st.session_state.demo_strategies if s["id"] == x), x)
            )

        with col5:
            pre_emotion = st.selectbox(
                "Pre-Trade Emotion",
                ["calm", "confident", "anxious", "fomo", "greedy", "fearful", "frustrated", "euphoric", "revenge"]
            )
            timeframe = st.selectbox("Timeframe", ["1m", "5m", "15m", "1h", "4h", "1d"])

        entry_reason = st.text_area("Entry Reason", placeholder="Why are you taking this trade?")
        notes = st.text_area("Notes", placeholder="Additional notes...")

        submitted = st.form_submit_button("Log Trade", type="primary", use_container_width=True)

        if submitted:
            if symbol and entry_price > 0:
                new_entry = {
                    "entry_id": f"TRD-{len(st.session_state.demo_entries)+1:04d}",
                    "symbol": symbol,
                    "direction": direction,
                    "trade_type": trade_type,
                    "entry_date": datetime.combine(entry_date, entry_time),
                    "entry_price": entry_price,
                    "entry_quantity": entry_quantity,
                    "exit_date": None,
                    "exit_price": None,
                    "realized_pnl": None,
                    "setup_id": setup,
                    "strategy_id": strategy,
                    "pre_trade_emotion": pre_emotion,
                    "initial_stop": initial_stop,
                    "initial_target": initial_target,
                    "notes": notes,
                    "entry_reason": entry_reason,
                }
                st.session_state.demo_entries.append(new_entry)
                st.success(f"Trade logged: {direction.upper()} {entry_quantity} {symbol} @ ${entry_price}")
                st.rerun()
            else:
                st.error("Please fill in required fields (Symbol, Entry Price)")


def render_close_trade_form():
    """Render form to close open trades."""
    open_trades = [e for e in st.session_state.demo_entries if not e.get("exit_date")]

    if not open_trades:
        st.info("No open trades to close.")
        return

    st.subheader("Close Trade")

    with st.form("close_trade_form"):
        trade_options = {e["entry_id"]: f"{e['entry_id']}: {e['direction'].upper()} {e['entry_quantity']} {e['symbol']} @ ${e['entry_price']}" for e in open_trades}
        selected_trade = st.selectbox("Select Trade", options=list(trade_options.keys()), format_func=lambda x: trade_options[x])

        col1, col2 = st.columns(2)
        with col1:
            exit_date = st.date_input("Exit Date", value=date.today())
            exit_time = st.time_input("Exit Time")
            exit_price = st.number_input("Exit Price", min_value=0.01, step=0.01)

        with col2:
            during_emotion = st.selectbox("During Trade Emotion", ["calm", "confident", "anxious", "fomo", "greedy", "fearful", "frustrated", "euphoric"])
            post_emotion = st.selectbox("Post Trade Emotion", ["calm", "confident", "anxious", "fomo", "greedy", "fearful", "frustrated", "euphoric"])
            fees = st.number_input("Fees/Commission", min_value=0.0, step=0.01, value=0.0)

        exit_reason = st.text_area("Exit Reason", placeholder="Why did you exit?")
        lessons = st.text_area("Lessons Learned", placeholder="What did you learn from this trade?")

        submitted = st.form_submit_button("Close Trade", type="primary", use_container_width=True)

        if submitted and exit_price > 0:
            for entry in st.session_state.demo_entries:
                if entry["entry_id"] == selected_trade:
                    entry["exit_date"] = datetime.combine(exit_date, exit_time)
                    entry["exit_price"] = exit_price
                    entry["during_trade_emotion"] = during_emotion
                    entry["post_trade_emotion"] = post_emotion
                    entry["exit_reason"] = exit_reason
                    entry["lessons_learned"] = lessons

                    # Calculate P&L
                    if entry["direction"] == "long":
                        pnl = (exit_price - entry["entry_price"]) * entry["entry_quantity"] - fees
                    else:
                        pnl = (entry["entry_price"] - exit_price) * entry["entry_quantity"] - fees

                    entry["realized_pnl"] = round(pnl, 2)
                    entry["realized_pnl_pct"] = round(pnl / (entry["entry_price"] * entry["entry_quantity"]) * 100, 2)
                    entry["fees"] = fees

                    st.success(f"Trade closed: P&L ${pnl:,.2f} ({entry['realized_pnl_pct']:.2f}%)")
                    st.rerun()
                    break


def render_open_positions():
    """Render open positions table."""
    open_trades = [e for e in st.session_state.demo_entries if not e.get("exit_date")]

    if not open_trades:
        st.info("No open positions.")
        return

    st.subheader(f"Open Positions ({len(open_trades)})")

    df = pd.DataFrame([{
        "ID": e["entry_id"],
        "Symbol": e["symbol"],
        "Direction": e["direction"].upper(),
        "Qty": e["entry_quantity"],
        "Entry Price": f"${e['entry_price']:,.2f}",
        "Entry Date": e["entry_date"].strftime("%Y-%m-%d %H:%M"),
        "Setup": e.get("setup_id", "").replace("_", " ").title(),
        "Stop": f"${e.get('initial_stop', 0):,.2f}" if e.get("initial_stop") else "-",
        "Target": f"${e.get('initial_target', 0):,.2f}" if e.get("initial_target") else "-",
    } for e in open_trades])

    st.dataframe(df, use_container_width=True, hide_index=True)


def render_trade_history():
    """Render trade history table."""
    closed = [e for e in st.session_state.demo_entries if e.get("exit_date")]
    closed = sorted(closed, key=lambda x: x["exit_date"], reverse=True)

    if not closed:
        st.info("No closed trades.")
        return

    st.subheader(f"Trade History ({len(closed)} trades)")

    df = pd.DataFrame([{
        "ID": e["entry_id"],
        "Symbol": e["symbol"],
        "Direction": e["direction"].upper(),
        "Qty": e["entry_quantity"],
        "Entry": f"${e['entry_price']:,.2f}",
        "Exit": f"${e['exit_price']:,.2f}",
        "P&L": e["realized_pnl"],
        "P&L %": e.get("realized_pnl_pct", 0),
        "Setup": e.get("setup_id", "").replace("_", " ").title(),
        "Entry Date": e["entry_date"].strftime("%Y-%m-%d"),
        "Exit Date": e["exit_date"].strftime("%Y-%m-%d") if e["exit_date"] else "",
    } for e in closed[:50]])  # Limit to 50

    def color_pnl(val):
        if val > 0:
            return "color: green"
        elif val < 0:
            return "color: red"
        return ""

    st.dataframe(
        df.style.applymap(color_pnl, subset=["P&L", "P&L %"]).format({
            "P&L": "${:,.2f}",
            "P&L %": "{:.2f}%",
        }),
        use_container_width=True,
        hide_index=True,
    )


def render_daily_review_form():
    """Render daily review form."""
    st.subheader("Daily Review")

    review_date = st.date_input("Review Date", value=date.today())

    # Get trades for that day
    day_entries = [e for e in st.session_state.demo_entries
                   if e["entry_date"].date() == review_date]
    day_closed = [e for e in day_entries if e.get("exit_date")]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Trades Taken", len(day_entries))
    col2.metric("Closed", len(day_closed))
    pnl = sum(e.get("realized_pnl", 0) for e in day_closed)
    col3.metric("P&L", f"${pnl:,.2f}")
    winners = [e for e in day_closed if (e.get("realized_pnl") or 0) > 0]
    wr = len(winners) / len(day_closed) if day_closed else 0
    col4.metric("Win Rate", f"{wr:.0%}")

    with st.form("daily_review_form"):
        col1, col2 = st.columns(2)

        with col1:
            followed_plan = st.checkbox("Followed Trading Plan", value=True)
            overall_rating = st.slider("Overall Rating", 1, 5, 3)

        with col2:
            tomorrow_focus = st.text_input("Tomorrow's Focus", placeholder="What to focus on tomorrow?")

        mistakes = st.text_area("Mistakes Made", placeholder="List any mistakes...", height=100)
        did_well = st.text_area("What I Did Well", placeholder="List what went well...", height=100)
        notes = st.text_area("Notes", placeholder="Additional reflection...", height=100)

        submitted = st.form_submit_button("Save Review", type="primary", use_container_width=True)

        if submitted:
            st.success(f"Daily review saved for {review_date}")


def render_insights():
    """Render automated insights."""
    entries = st.session_state.demo_entries
    metrics = calculate_demo_metrics(entries)

    if metrics.get("total_trades", 0) < 5:
        st.info("Need at least 5 trades to generate insights.")
        return

    st.subheader("Trading Insights")

    insights = []

    # Win rate insight
    if metrics["win_rate"] >= 0.55:
        insights.append({
            "type": "strength",
            "icon": "✅",
            "title": "Strong Win Rate",
            "description": f"Your win rate of {metrics['win_rate']:.0%} is above average. Keep executing your plan!"
        })
    elif metrics["win_rate"] < 0.45:
        insights.append({
            "type": "weakness",
            "icon": "⚠️",
            "title": "Low Win Rate",
            "description": f"Your win rate is {metrics['win_rate']:.0%}. Consider reviewing your entry criteria or being more selective."
        })

    # Profit factor
    if metrics["profit_factor"] >= 2.0:
        insights.append({
            "type": "strength",
            "icon": "💰",
            "title": "Excellent Profit Factor",
            "description": f"Profit factor of {metrics['profit_factor']:.2f} shows strong risk management. Winners significantly outpace losers."
        })
    elif metrics["profit_factor"] < 1.0:
        insights.append({
            "type": "weakness",
            "icon": "📉",
            "title": "Negative Profit Factor",
            "description": f"Profit factor is {metrics['profit_factor']:.2f}. Focus on cutting losers faster or letting winners run longer."
        })

    # Average winner vs loser
    if metrics["avg_winner"] > 0 and metrics["avg_loser"] > 0:
        ratio = metrics["avg_winner"] / metrics["avg_loser"]
        if ratio >= 1.5:
            insights.append({
                "type": "strength",
                "icon": "📊",
                "title": "Good Win/Loss Ratio",
                "description": f"Your average winner (${metrics['avg_winner']:,.0f}) is {ratio:.1f}x your average loser (${metrics['avg_loser']:,.0f})."
            })

    # Setup analysis
    from collections import defaultdict
    closed = [e for e in entries if e.get("exit_date") and e.get("setup_id")]
    by_setup = defaultdict(list)
    for e in closed:
        by_setup[e["setup_id"]].append(e)

    if by_setup:
        setup_stats = []
        for setup_id, setup_entries in by_setup.items():
            if len(setup_entries) >= 3:
                winners = [e for e in setup_entries if (e.get("realized_pnl") or 0) > 0]
                wr = len(winners) / len(setup_entries)
                setup_stats.append((setup_id, wr, len(setup_entries)))

        if setup_stats:
            best = max(setup_stats, key=lambda x: x[1])
            worst = min(setup_stats, key=lambda x: x[1])

            if best[1] >= 0.6:
                insights.append({
                    "type": "pattern",
                    "icon": "🎯",
                    "title": f"Best Setup: {best[0].replace('_', ' ').title()}",
                    "description": f"This setup has {best[1]:.0%} win rate across {best[2]} trades. Consider sizing up here."
                })

            if worst[1] <= 0.35 and worst[2] >= 5:
                insights.append({
                    "type": "recommendation",
                    "icon": "🚫",
                    "title": f"Avoid: {worst[0].replace('_', ' ').title()}",
                    "description": f"Only {worst[1]:.0%} win rate across {worst[2]} trades. Consider removing from playbook."
                })

    # Display insights
    if not insights:
        st.info("Keep trading to unlock personalized insights!")
        return

    for insight in insights:
        color = {
            "strength": "#E8F5E9",
            "weakness": "#FFEBEE",
            "pattern": "#E3F2FD",
            "recommendation": "#FFF3E0",
        }.get(insight["type"], "#F5F5F5")

        st.markdown(f"""
        <div style="background-color: {color}; padding: 15px; border-radius: 8px; margin-bottom: 10px;">
            <h4 style="margin: 0;">{insight['icon']} {insight['title']}</h4>
            <p style="margin: 5px 0 0 0;">{insight['description']}</p>
        </div>
        """, unsafe_allow_html=True)


# =============================================================================
# Main
# =============================================================================

def main():
    st.title("📓 Trade Journal")

    init_session_state()

    # Sidebar
    st.sidebar.header("Journal")

    date_range = st.sidebar.selectbox(
        "Time Period",
        ["Last 7 Days", "Last 30 Days", "Last 90 Days", "YTD", "All Time"]
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Quick Stats")
    metrics = calculate_demo_metrics(st.session_state.demo_entries)
    st.sidebar.metric("Total Trades", metrics.get("total_trades", 0))
    st.sidebar.metric("Win Rate", f"{metrics.get('win_rate', 0):.1%}")
    st.sidebar.metric("Total P&L", f"${metrics.get('total_pnl', 0):,.2f}")

    # Main content tabs
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📊 Dashboard",
        "📝 Log Trade",
        "📈 Analytics",
        "🎯 Insights",
        "📋 Review",
        "📜 History",
    ])

    # Tab 1: Dashboard
    with tab1:
        render_metrics_row(metrics)
        st.markdown("---")

        col1, col2 = st.columns([2, 1])

        with col1:
            render_equity_curve(st.session_state.demo_entries)

        with col2:
            render_open_positions()

        col3, col4 = st.columns(2)
        with col3:
            render_win_rate_by_setup(st.session_state.demo_entries)
        with col4:
            render_pnl_by_day(st.session_state.demo_entries)

    # Tab 2: Log Trade
    with tab2:
        col1, col2 = st.columns(2)
        with col1:
            render_trade_entry_form()
        with col2:
            render_close_trade_form()

    # Tab 3: Analytics
    with tab3:
        st.subheader("Performance Analytics")

        render_metrics_row(metrics)
        st.markdown("---")

        col1, col2 = st.columns(2)
        with col1:
            render_win_rate_by_setup(st.session_state.demo_entries)
        with col2:
            render_emotion_analysis(st.session_state.demo_entries)

        render_pnl_by_day(st.session_state.demo_entries)

    # Tab 4: Insights
    with tab4:
        render_insights()

    # Tab 5: Review
    with tab5:
        render_daily_review_form()

    # Tab 6: History
    with tab6:
        render_trade_history()



main()
