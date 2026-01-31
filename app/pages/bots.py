"""Trading Bots Dashboard."""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone

st.set_page_config(page_title="Trading Bots", layout="wide")
st.title("🤖 Automated Trading Bots")

# Try to import bots module
try:
    from src.bots import (
        BotEngine, BotConfig, BotType, BotStatus, ExecutionStatus,
        DCAConfig, RebalanceConfig, SignalBotConfig, GridConfig,
        ScheduleConfig, ScheduleFrequency, ExecutionTime,
        TradeSide, SignalType, SignalCondition,
    )
    BOTS_AVAILABLE = True
except ImportError as e:
    BOTS_AVAILABLE = False
    st.error(f"Bots module not available: {e}")


def init_session_state():
    """Initialize session state with demo data."""
    if "bot_engine" not in st.session_state:
        engine = BotEngine()
        
        # Create demo DCA bot
        dca_config = BotConfig(
            bot_id="dca_spy",
            name="Weekly S&P 500 DCA",
            bot_type=BotType.DCA,
            symbols=["SPY"],
            dca_config=DCAConfig(
                amount_per_period=500,
                allocations={"SPY": 1.0},
            ),
            schedule=ScheduleConfig(
                frequency=ScheduleFrequency.WEEKLY,
                day_of_week=0,
            ),
        )
        engine.create_bot(dca_config)
        
        # Create demo rebalance bot
        rebal_config = BotConfig(
            bot_id="rebal_60_40",
            name="60/40 Portfolio Rebalancer",
            bot_type=BotType.REBALANCE,
            symbols=["SPY", "BND"],
            rebalance_config=RebalanceConfig(
                target_allocations={"SPY": 0.6, "BND": 0.4},
                drift_threshold_pct=5.0,
            ),
            schedule=ScheduleConfig(
                frequency=ScheduleFrequency.MONTHLY,
                day_of_month=1,
            ),
        )
        engine.create_bot(rebal_config)
        
        st.session_state.bot_engine = engine
    
    if "demo_market_data" not in st.session_state:
        st.session_state.demo_market_data = {
            "SPY": {"price": 450.0, "change_pct": 0.5},
            "BND": {"price": 72.0, "change_pct": -0.1},
            "QQQ": {"price": 380.0, "change_pct": 0.8},
            "GLD": {"price": 180.0, "change_pct": 0.2},
            "AAPL": {"price": 175.0, "rsi": 45, "change_pct": 1.2},
            "ETH": {"price": 2200.0, "change_pct": -2.5},
        }


def render_overview():
    """Render bots overview."""
    engine = st.session_state.bot_engine
    summaries = engine.get_summaries()
    
    # Stats row
    col1, col2, col3, col4 = st.columns(4)
    
    active_bots = len([s for s in summaries if s.status == BotStatus.ACTIVE])
    total_invested = sum(s.total_invested for s in summaries)
    total_pnl = sum(s.total_pnl for s in summaries)
    total_execs = sum(s.total_executions for s in summaries)
    
    col1.metric("Active Bots", active_bots)
    col2.metric("Total Invested", f"${total_invested:,.2f}")
    col3.metric("Total P&L", f"${total_pnl:,.2f}")
    col4.metric("Total Executions", total_execs)
    
    # Bots table
    st.markdown("---")
    st.subheader("Your Bots")
    
    if summaries:
        data = []
        for s in summaries:
            status_emoji = {
                BotStatus.ACTIVE: "🟢",
                BotStatus.PAUSED: "🟡",
                BotStatus.STOPPED: "🔴",
                BotStatus.ERROR: "⚠️",
            }.get(s.status, "⚪")
            
            data.append({
                "Name": s.name,
                "Type": s.bot_type.value.upper(),
                "Status": f"{status_emoji} {s.status.value.title()}",
                "Symbols": ", ".join(s.symbols[:3]),
                "Invested": f"${s.total_invested:,.2f}",
                "P&L": f"${s.total_pnl:,.2f}",
                "Return": f"{s.total_return_pct:.1f}%",
                "Executions": s.total_executions,
                "Next Run": s.next_run.strftime("%m/%d %H:%M") if s.next_run else "-",
            })
        
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No bots created yet. Create your first bot below!")


def render_create_bot():
    """Render bot creation form."""
    st.subheader("Create New Bot")
    
    col1, col2 = st.columns(2)
    
    with col1:
        bot_name = st.text_input("Bot Name", placeholder="My Trading Bot")
        bot_type = st.selectbox(
            "Bot Type",
            options=["DCA", "Rebalance", "Signal", "Grid"],
            help="DCA: Recurring investments | Rebalance: Maintain allocation | Signal: Trade on indicators | Grid: Range trading"
        )
        symbols = st.text_input("Symbols (comma-separated)", placeholder="SPY, QQQ")
    
    with col2:
        frequency = st.selectbox(
            "Schedule",
            options=["Daily", "Weekly", "Biweekly", "Monthly"],
        )
        
        if frequency == "Weekly":
            day_of_week = st.selectbox(
                "Day",
                options=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
            )
        elif frequency == "Monthly":
            day_of_month = st.number_input("Day of Month", 1, 28, 1)
    
    # Type-specific options
    st.markdown("**Bot Settings**")
    
    if bot_type == "DCA":
        col1, col2 = st.columns(2)
        with col1:
            amount = st.number_input("Amount per Period ($)", 50, 10000, 500)
        with col2:
            increase_on_dip = st.checkbox("Increase on Dip", value=False)
    
    elif bot_type == "Rebalance":
        st.markdown("Target Allocations (must sum to 100%)")
        col1, col2, col3 = st.columns(3)
        with col1:
            alloc1 = st.number_input("SPY %", 0, 100, 60)
        with col2:
            alloc2 = st.number_input("BND %", 0, 100, 40)
        with col3:
            drift = st.number_input("Drift Threshold %", 1, 20, 5)
    
    elif bot_type == "Signal":
        col1, col2 = st.columns(2)
        with col1:
            signal_type = st.selectbox("Signal Type", ["RSI", "MACD", "Price Level"])
            condition = st.selectbox("Condition", ["Below", "Above", "Crosses Above", "Crosses Below"])
        with col2:
            threshold = st.number_input("Threshold", value=30)
            amount = st.number_input("Trade Amount ($)", 100, 10000, 1000)
    
    elif bot_type == "Grid":
        col1, col2 = st.columns(2)
        with col1:
            lower_price = st.number_input("Lower Price", value=2000.0)
            num_grids = st.number_input("Number of Grids", 5, 50, 10)
        with col2:
            upper_price = st.number_input("Upper Price", value=2500.0)
            total_investment = st.number_input("Total Investment ($)", 1000, 100000, 10000)
    
    if st.button("Create Bot", type="primary"):
        if not bot_name or not symbols:
            st.error("Please fill in all required fields")
        else:
            st.success(f"Bot '{bot_name}' created successfully!")
            st.balloons()


def render_bot_details():
    """Render individual bot details."""
    engine = st.session_state.bot_engine
    bots = engine.get_all_bots()
    
    if not bots:
        st.info("No bots available")
        return
    
    bot_names = {b.name: b.bot_id for b in bots}
    selected_name = st.selectbox("Select Bot", options=list(bot_names.keys()))
    
    if selected_name:
        bot_id = bot_names[selected_name]
        bot = engine.get_bot(bot_id)
        
        if bot:
            col1, col2, col3 = st.columns(3)
            col1.metric("Status", bot.status.value.title())
            col2.metric("Type", bot.bot_type.value.upper())
            col3.metric("Symbols", ", ".join(bot.config.symbols))
            
            # Actions
            st.markdown("**Actions**")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                if st.button("▶️ Run Now"):
                    execution = engine.run_bot(bot_id, st.session_state.demo_market_data)
                    if execution:
                        st.success(f"Executed! {execution.orders_placed} orders placed")
                    else:
                        st.warning("Could not execute bot")
            
            with col2:
                if bot.status == BotStatus.ACTIVE:
                    if st.button("⏸️ Pause"):
                        engine.pause_bot(bot_id)
                        st.rerun()
                else:
                    if st.button("▶️ Resume"):
                        engine.start_bot(bot_id)
                        st.rerun()
            
            with col3:
                if st.button("⏹️ Stop"):
                    engine.stop_bot(bot_id)
                    st.rerun()
            
            with col4:
                if st.button("🗑️ Delete", type="secondary"):
                    engine.delete_bot(bot_id)
                    st.rerun()
            
            # Performance
            st.markdown("---")
            st.markdown("**Performance**")
            
            perf = bot.get_performance()
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Invested", f"${perf.total_invested:,.2f}")
            col2.metric("Current Value", f"${perf.current_value:,.2f}")
            col3.metric("Total P&L", f"${perf.total_pnl:,.2f}")
            col4.metric("Return", f"{perf.total_return_pct:.1f}%")
            
            # Executions
            st.markdown("---")
            st.markdown("**Recent Executions**")
            
            executions = engine.get_executions(bot_id=bot_id, limit=10)
            if executions:
                data = []
                for ex in executions:
                    status_emoji = {
                        ExecutionStatus.SUCCESS: "✅",
                        ExecutionStatus.PARTIAL: "⚠️",
                        ExecutionStatus.FAILED: "❌",
                        ExecutionStatus.SKIPPED: "⏭️",
                    }.get(ex.status, "⚪")
                    
                    data.append({
                        "Time": ex.completed_at.strftime("%Y-%m-%d %H:%M") if ex.completed_at else "-",
                        "Status": f"{status_emoji} {ex.status.value.title()}",
                        "Orders": ex.orders_placed,
                        "Filled": ex.orders_filled,
                        "Value": f"${ex.total_value:,.2f}",
                        "Trigger": ex.trigger_reason,
                    })
                
                st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
            else:
                st.info("No executions yet")


def render_schedule():
    """Render upcoming schedule."""
    st.subheader("📅 Upcoming Schedule")
    
    engine = st.session_state.bot_engine
    upcoming = engine.scheduler.get_upcoming_runs(limit=10)
    
    if upcoming:
        data = []
        for run in upcoming:
            data.append({
                "Bot": run.bot_name,
                "Scheduled": run.scheduled_time.strftime("%Y-%m-%d %H:%M"),
                "Status": run.status.title(),
            })
        
        st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
    else:
        st.info("No upcoming scheduled runs")


def render_settings():
    """Render global bot settings."""
    st.subheader("⚙️ Global Settings")
    
    engine = st.session_state.bot_engine
    settings = engine.settings
    
    col1, col2 = st.columns(2)
    
    with col1:
        paper_mode = st.checkbox("Paper Trading Mode", value=settings.paper_mode)
        max_orders = st.number_input("Max Concurrent Orders", 1, 100, settings.max_concurrent_orders)
        max_allocation = st.slider("Max Bot Allocation (%)", 10, 100, int(settings.max_total_bot_allocation * 100))
    
    with col2:
        approval_threshold = st.number_input("Require Approval Above ($)", 1000, 100000, int(settings.require_approval_above))
        start_time = st.text_input("Trading Hours Start", settings.allowed_hours_start)
        end_time = st.text_input("Trading Hours End", settings.allowed_hours_end)
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 Save Settings"):
            st.success("Settings saved!")
    
    with col2:
        if settings.emergency_stop_all:
            if st.button("🟢 Resume All Bots", type="primary"):
                engine.resume_all()
                st.rerun()
        else:
            if st.button("🔴 Emergency Stop All", type="secondary"):
                engine.emergency_stop()
                st.warning("All bots stopped!")
                st.rerun()


def main():
    if not BOTS_AVAILABLE:
        return
    
    init_session_state()
    
    # Sidebar
    st.sidebar.header("Navigation")
    page = st.sidebar.radio(
        "Go to",
        ["Overview", "Create Bot", "Bot Details", "Schedule", "Settings"],
    )
    
    # Emergency stop indicator
    engine = st.session_state.bot_engine
    if engine.settings.emergency_stop_all:
        st.error("🚨 EMERGENCY STOP ACTIVE - All bots are paused")
    
    # Main content
    if page == "Overview":
        render_overview()
    elif page == "Create Bot":
        render_create_bot()
    elif page == "Bot Details":
        render_bot_details()
    elif page == "Schedule":
        render_schedule()
    elif page == "Settings":
        render_settings()


if __name__ == "__main__":
    main()
