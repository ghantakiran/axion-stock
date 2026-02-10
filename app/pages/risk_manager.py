"""Risk Manager Dashboard (PRD-150).

Four-tab Streamlit dashboard for portfolio risk monitoring,
circuit breaker status, kill switch control, and market hours.
"""

import streamlit as st
from app.styles import inject_global_styles

inject_global_styles()
from datetime import datetime, timezone

from src.risk_manager.portfolio_risk import (
    PortfolioRiskConfig, PortfolioRiskMonitor, RiskLevel, SECTOR_MAP,
)
from src.risk_manager.circuit_breaker import (
    CircuitBreakerConfig, CircuitBreakerStatus, TradingCircuitBreaker,
)
from src.risk_manager.kill_switch import (
    EnhancedKillSwitch, KillSwitchConfig, KillSwitchState,
)
from src.risk_manager.market_hours import (
    MarketCalendarConfig, MarketHoursEnforcer, MarketSession,
)

st.header("Risk Manager")
st.caption("PRD-150 · Advanced portfolio risk, circuit breaker, kill switch, and market hours")

tab1, tab2, tab3, tab4 = st.tabs([
    "Portfolio Risk", "Circuit Breaker", "Kill Switch", "Market Hours",
])

# ── Tab 1: Portfolio Risk ───────────────────────────────────────────

with tab1:
    st.subheader("Portfolio Risk Monitor")

    equity = st.number_input("Account Equity ($)", 10_000, 10_000_000, 100_000, step=10_000)
    vix = st.slider("VIX Level", 10.0, 60.0, 20.0)

    monitor = PortfolioRiskMonitor(equity=float(equity))

    # Demo positions
    demo_positions = [
        {"symbol": "AAPL", "side": "long", "market_value": 18_000, "qty": 100, "current_price": 180},
        {"symbol": "GOOG", "side": "long", "market_value": 14_000, "qty": 100, "current_price": 140},
        {"symbol": "NVDA", "side": "long", "market_value": 12_000, "qty": 24, "current_price": 500},
        {"symbol": "JPM", "side": "long", "market_value": 8_000, "qty": 40, "current_price": 200},
        {"symbol": "XOM", "side": "long", "market_value": 5_000, "qty": 50, "current_price": 100},
    ]

    snapshot = monitor.assess(demo_positions, vix=vix)

    risk_colors = {
        RiskLevel.LOW: "🟢", RiskLevel.MODERATE: "🟡",
        RiskLevel.ELEVATED: "🟠", RiskLevel.HIGH: "🔴",
        RiskLevel.CRITICAL: "⛔",
    }
    icon = risk_colors.get(snapshot.risk_level, "⚪")
    st.markdown(f"### Risk Level: {icon} {snapshot.risk_level.value.upper()}")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Gross Leverage", f"{snapshot.gross_leverage:.2f}x")
    m2.metric("Largest Position", f"{snapshot.largest_position_pct:.1f}%")
    m3.metric("VIX-Adjusted Size", f"{snapshot.vix_adjusted_size_pct:.1f}%")
    m4.metric("Correlated", snapshot.correlated_count)

    if snapshot.warnings:
        for w in snapshot.warnings:
            st.warning(w)

    if snapshot.sector_concentrations:
        st.write("**Sector Concentrations:**")
        for sector, pct in sorted(snapshot.sector_concentrations.items(), key=lambda x: -x[1]):
            st.write(f"  {sector}: {pct:.1f}%")

# ── Tab 2: Circuit Breaker ──────────────────────────────────────────

with tab2:
    st.subheader("Trading Circuit Breaker")

    cb_losses = st.number_input("Max Consecutive Losses", 1, 10, 3)
    cb_drawdown = st.slider("Max Daily Drawdown %", 1.0, 20.0, 5.0, key="cb_dd")

    cb = TradingCircuitBreaker(
        CircuitBreakerConfig(
            max_consecutive_losses=int(cb_losses),
            max_daily_drawdown_pct=cb_drawdown,
            cooldown_seconds=0,
        ),
        equity=float(equity),
    )

    status_map = {
        CircuitBreakerStatus.CLOSED: ("🟢", "TRADING ACTIVE"),
        CircuitBreakerStatus.OPEN: ("🔴", "TRADING HALTED"),
        CircuitBreakerStatus.HALF_OPEN: ("🟡", "RECOVERY MODE"),
    }

    if st.button("Simulate 5 Losses"):
        for i in range(5):
            status = cb.record_result(-500)
        icon, label = status_map.get(cb.status, ("⚪", "UNKNOWN"))
        st.markdown(f"### {icon} {label}")
        st.write(f"Trip reason: {cb.state.trip_reason}")
        st.write(f"Trip count: {cb.state.trip_count}")
        st.write(f"Size multiplier: {cb.get_size_multiplier():.2f}x")
    else:
        icon, label = status_map.get(cb.status, ("⚪", "UNKNOWN"))
        st.markdown(f"### {icon} {label}")

    st.json(cb.state.to_dict())

# ── Tab 3: Kill Switch ──────────────────────────────────────────────

with tab3:
    st.subheader("Emergency Kill Switch")

    ks = EnhancedKillSwitch(
        KillSwitchConfig(equity_floor=25_000, max_daily_drawdown_pct=10.0),
        initial_equity=float(equity),
    )

    c1, c2 = st.columns(2)
    with c1:
        if st.button("ARM Kill Switch"):
            ks.arm()
            st.success("Kill switch ARMED")
    with c2:
        if st.button("TRIGGER Kill Switch"):
            ks.arm()
            ks.trigger("Manual dashboard trigger", "manual", float(equity), 0.0)
            st.error("TRADING HALTED!")

    state_colors = {
        KillSwitchState.ARMED: "🟡 ARMED",
        KillSwitchState.TRIGGERED: "🔴 TRIGGERED",
        KillSwitchState.DISARMED: "⚪ DISARMED",
    }
    st.markdown(f"### Status: {state_colors.get(ks.state, 'Unknown')}")

    if ks.events:
        st.write("**Recent Events:**")
        for e in ks.get_history(5):
            st.write(f"  {e.action}: {e.reason} ({e.triggered_by})")

# ── Tab 4: Market Hours ────────────────────────────────────────────

with tab4:
    st.subheader("Market Session & Calendar")

    enforcer = MarketHoursEnforcer()
    info = enforcer.get_session_info()

    session_colors = {
        "regular": "🟢", "pre_market": "🟡",
        "after_hours": "🟠", "closed": "🔴",
    }
    icon = session_colors.get(info["session"], "⚪")
    st.markdown(f"### Current Session: {icon} {info['session'].upper()}")

    m1, m2, m3 = st.columns(3)
    m1.metric("Is Open", "Yes" if info["is_open"] else "No")
    m2.metric("Is Holiday", "Yes" if info["is_holiday"] else "No")
    m3.metric("Is Early Close", "Yes" if info["is_early_close"] else "No")

    if info["time_until_close_min"] is not None:
        st.metric("Minutes Until Close", f"{info['time_until_close_min']:.0f}")

    st.write("**Asset Availability:**")
    for asset in ["stock", "options", "crypto"]:
        allowed = enforcer.is_trading_allowed(asset_type=asset)
        icon = "✅" if allowed else "❌"
        st.write(f"  {icon} {asset.title()}")
