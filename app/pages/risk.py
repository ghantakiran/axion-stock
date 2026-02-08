"""Risk Dashboard - Enterprise Risk Management Interface.

Provides:
- Real-time risk status and alerts
- Portfolio risk metrics (Sharpe, VaR, drawdown)
- Stress test visualization
- Concentration analysis
- Pre-trade risk preview
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta

# Page config
try:
    st.set_page_config(
        page_title="Axion Risk Management",
        page_icon="🛡️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
except st.errors.StreamlitAPIException:
    pass


# Import risk module
try:
    from src.risk import (
        RiskMonitor,
        RiskConfig,
        RiskStatus,
        RiskMetricsCalculator,
        VaRCalculator,
        StressTestEngine,
        HYPOTHETICAL_SCENARIOS,
        AttributionAnalyzer,
        # PRD-65: Portfolio Stress Testing
        ShockPropagationEngine,
        FactorShock,
        DrawdownAnalyzer,
        RecoveryEstimator,
        ScenarioBuilder,
        SCENARIO_TEMPLATES,
    )
    RISK_AVAILABLE = True
except ImportError as e:
    RISK_AVAILABLE = False
    st.error(f"Risk module not available: {e}")


# =============================================================================
# Session State
# =============================================================================

def init_session_state():
    """Initialize session state for risk dashboard."""
    if "risk_config" not in st.session_state:
        st.session_state.risk_config = RiskConfig()
    if "risk_monitor" not in st.session_state:
        st.session_state.risk_monitor = RiskMonitor(config=st.session_state.risk_config)
    if "risk_dashboard_data" not in st.session_state:
        st.session_state.risk_dashboard_data = None
    if "demo_mode" not in st.session_state:
        st.session_state.demo_mode = True


def get_demo_data():
    """Generate demo portfolio data for visualization."""
    np.random.seed(42)

    # Demo positions
    positions = [
        {"symbol": "AAPL", "market_value": 18500, "qty": 100, "entry_price": 175, "current_price": 185, "sector": "Technology"},
        {"symbol": "MSFT", "market_value": 15000, "qty": 40, "entry_price": 360, "current_price": 375, "sector": "Technology"},
        {"symbol": "NVDA", "market_value": 12000, "qty": 15, "entry_price": 750, "current_price": 800, "sector": "Technology"},
        {"symbol": "JPM", "market_value": 9500, "qty": 50, "entry_price": 185, "current_price": 190, "sector": "Financials"},
        {"symbol": "JNJ", "market_value": 8000, "qty": 50, "entry_price": 155, "current_price": 160, "sector": "Healthcare"},
        {"symbol": "XOM", "market_value": 6000, "qty": 55, "entry_price": 105, "current_price": 109, "sector": "Energy"},
        {"symbol": "PG", "market_value": 5500, "qty": 35, "entry_price": 150, "current_price": 157, "sector": "Consumer Staples"},
        {"symbol": "UNH", "market_value": 5000, "qty": 10, "entry_price": 480, "current_price": 500, "sector": "Healthcare"},
    ]

    total_value = sum(p["market_value"] for p in positions)
    for p in positions:
        p["weight"] = p["market_value"] / total_value
        p["pnl_pct"] = (p["current_price"] - p["entry_price"]) / p["entry_price"]

    # Demo returns (252 days)
    dates = pd.date_range(end=datetime.now(), periods=252, freq='D')
    returns = pd.Series(np.random.normal(0.0005, 0.015, 252), index=dates)
    benchmark_returns = pd.Series(np.random.normal(0.0004, 0.012, 252), index=dates)

    return positions, returns, benchmark_returns, total_value


# =============================================================================
# Status Header
# =============================================================================

def render_status_header(dashboard_data):
    """Render the main status header."""
    if dashboard_data is None:
        st.warning("No risk data available. Run analysis to see results.")
        return

    status = dashboard_data.overall_status
    status_colors = {
        RiskStatus.NORMAL: "green",
        RiskStatus.WARNING: "orange",
        RiskStatus.ELEVATED: "red",
        RiskStatus.CRITICAL: "darkred",
    }
    status_icons = {
        RiskStatus.NORMAL: "✅",
        RiskStatus.WARNING: "⚠️",
        RiskStatus.ELEVATED: "🔴",
        RiskStatus.CRITICAL: "🚨",
    }

    color = status_colors.get(status, "gray")
    icon = status_icons.get(status, "⚪")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(f"""
        <div style="padding: 1rem; background: linear-gradient(135deg, {color}22, {color}11);
                    border-left: 4px solid {color}; border-radius: 8px;">
            <h3 style="margin: 0; color: {color};">{icon} {status.upper()}</h3>
            <p style="margin: 0.5rem 0 0 0; color: #666;">{dashboard_data.status_message}</p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        trading_status = "ENABLED" if dashboard_data.trading_allowed else "HALTED"
        trading_color = "green" if dashboard_data.trading_allowed else "red"
        st.metric(
            "Trading Status",
            trading_status,
            delta=None,
            help=dashboard_data.trading_halt_reason if not dashboard_data.trading_allowed else "Trading is active"
        )

    with col3:
        dd = dashboard_data.current_drawdown
        st.metric(
            "Current Drawdown",
            f"{dd:.1%}",
            delta=f"{dd - dashboard_data.max_drawdown:.1%} vs max" if dashboard_data.max_drawdown else None,
            delta_color="inverse"
        )

    with col4:
        alert_count = len(dashboard_data.active_alerts)
        st.metric(
            "Active Alerts",
            alert_count,
            delta=None if alert_count == 0 else f"{alert_count} require attention",
            delta_color="off" if alert_count == 0 else "inverse"
        )


# =============================================================================
# Portfolio Metrics
# =============================================================================

def render_portfolio_metrics(dashboard_data):
    """Render portfolio risk metrics."""
    st.markdown("### 📊 Portfolio Metrics")

    pm = dashboard_data.portfolio_metrics
    if pm is None:
        st.info("Portfolio metrics not available. Ensure return data is provided.")
        return

    col1, col2, col3, col4, col5, col6 = st.columns(6)

    with col1:
        st.metric("Sharpe Ratio", f"{pm.sharpe_ratio:.2f}")
    with col2:
        st.metric("Sortino Ratio", f"{pm.sortino_ratio:.2f}")
    with col3:
        st.metric("Calmar Ratio", f"{pm.calmar_ratio:.2f}")
    with col4:
        st.metric("Portfolio Beta", f"{pm.portfolio_beta:.2f}")
    with col5:
        st.metric("Volatility (Ann.)", f"{pm.portfolio_volatility:.1%}")
    with col6:
        st.metric("Max Drawdown", f"{pm.max_drawdown:.1%}")


# =============================================================================
# VaR Display
# =============================================================================

def render_var_metrics(dashboard_data, portfolio_value):
    """Render Value at Risk metrics."""
    st.markdown("### 📉 Value at Risk")

    var = dashboard_data.var_metrics
    if var is None:
        st.info("VaR metrics not available.")
        return

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "VaR (95%)",
            f"${abs(var.var_95):,.0f}",
            f"{var.var_95_pct:.2%} of portfolio",
            delta_color="off"
        )
    with col2:
        st.metric(
            "VaR (99%)",
            f"${abs(var.var_99):,.0f}",
            f"{var.var_99_pct:.2%} of portfolio",
            delta_color="off"
        )
    with col3:
        st.metric(
            "CVaR (95%)",
            f"${abs(var.cvar_95):,.0f}",
            f"{var.cvar_95_pct:.2%} of portfolio",
            delta_color="off"
        )

    # VaR visualization
    with st.expander("VaR Distribution", expanded=False):
        if var.returns_distribution is not None:
            fig = go.Figure()

            # Histogram of returns
            fig.add_trace(go.Histogram(
                x=var.returns_distribution,
                nbinsx=50,
                name="Return Distribution",
                marker_color="rgba(99, 110, 250, 0.6)"
            ))

            # VaR lines
            fig.add_vline(x=var.var_95_pct, line_dash="dash", line_color="orange",
                          annotation_text=f"VaR 95%: {var.var_95_pct:.2%}")
            fig.add_vline(x=var.var_99_pct, line_dash="dash", line_color="red",
                          annotation_text=f"VaR 99%: {var.var_99_pct:.2%}")

            fig.update_layout(
                title="Daily Return Distribution with VaR",
                xaxis_title="Daily Return",
                yaxis_title="Frequency",
                height=300,
                margin=dict(l=0, r=0, t=40, b=0)
            )

            st.plotly_chart(fig, use_container_width=True)


# =============================================================================
# Concentration Analysis
# =============================================================================

def render_concentration(dashboard_data, positions):
    """Render concentration analysis."""
    st.markdown("### 🎯 Concentration Analysis")

    cm = dashboard_data.concentration_metrics
    if cm is None:
        st.info("Concentration metrics not available.")
        return

    col1, col2 = st.columns([1, 2])

    with col1:
        st.metric("Largest Position", f"{cm.largest_position_symbol}", f"{cm.largest_position_weight:.1%}")
        st.metric("Top 5 Concentration", f"{cm.top5_weight:.1%}")
        st.metric("Largest Sector", cm.largest_sector_name, f"{cm.largest_sector_weight:.1%}")
        st.metric("HHI (Diversification)", f"{cm.herfindahl_index:.3f}")

    with col2:
        # Position weights pie chart
        df = pd.DataFrame(positions)
        fig = px.pie(
            df,
            values="market_value",
            names="symbol",
            title="Position Weights",
            hole=0.4
        )
        fig.update_layout(height=300, margin=dict(l=0, r=0, t=40, b=0))
        st.plotly_chart(fig, use_container_width=True)

    # Sector breakdown
    sector_data = {}
    for p in positions:
        sector = p.get("sector", "Unknown")
        sector_data[sector] = sector_data.get(sector, 0) + p.get("market_value", 0)

    total = sum(sector_data.values())
    sector_df = pd.DataFrame([
        {"Sector": k, "Value": v, "Weight": v/total if total > 0 else 0}
        for k, v in sector_data.items()
    ])

    config = st.session_state.risk_config
    fig = px.bar(
        sector_df.sort_values("Value", ascending=True),
        y="Sector",
        x="Weight",
        orientation="h",
        title="Sector Exposure"
    )
    fig.add_vline(x=config.max_sector_pct, line_dash="dash", line_color="red",
                  annotation_text=f"Limit: {config.max_sector_pct:.0%}")
    fig.update_layout(height=300, margin=dict(l=0, r=0, t=40, b=0))
    st.plotly_chart(fig, use_container_width=True)


# =============================================================================
# Stress Tests
# =============================================================================

def render_stress_tests(dashboard_data, portfolio_value):
    """Render stress test results."""
    st.markdown("### 🔥 Stress Tests")

    results = dashboard_data.stress_test_results
    if not results:
        st.info("No stress test results available.")
        return

    # Create dataframe for display
    stress_df = pd.DataFrame([
        {
            "Scenario": r.scenario_name,
            "Impact ($)": r.portfolio_impact_dollars,
            "Impact (%)": r.portfolio_impact_pct,
            "Worst Position": r.worst_position_symbol,
            "Worst Impact": r.worst_position_impact_pct,
            "Surviving Value": r.surviving_portfolio_value,
        }
        for r in results
    ])

    # Waterfall chart of stress impacts
    fig = go.Figure(go.Waterfall(
        name="Stress Impact",
        orientation="v",
        x=stress_df["Scenario"],
        y=stress_df["Impact ($)"],
        textposition="outside",
        text=[f"${v:,.0f}" for v in stress_df["Impact ($)"]],
        connector={"line": {"color": "rgb(63, 63, 63)"}},
        decreasing={"marker": {"color": "#EF553B"}},
        increasing={"marker": {"color": "#00CC96"}},
    ))

    fig.update_layout(
        title="Portfolio Impact by Stress Scenario",
        height=400,
        margin=dict(l=0, r=0, t=40, b=0)
    )
    st.plotly_chart(fig, use_container_width=True)

    # Detailed table
    with st.expander("Stress Test Details", expanded=False):
        display_df = stress_df.copy()
        display_df["Impact ($)"] = display_df["Impact ($)"].apply(lambda x: f"${x:,.0f}")
        display_df["Impact (%)"] = display_df["Impact (%)"].apply(lambda x: f"{x:.1%}")
        display_df["Worst Impact"] = display_df["Worst Impact"].apply(lambda x: f"{x:.1%}" if pd.notna(x) else "-")
        display_df["Surviving Value"] = display_df["Surviving Value"].apply(lambda x: f"${x:,.0f}")
        st.dataframe(display_df, use_container_width=True, hide_index=True)


# =============================================================================
# Alerts Panel
# =============================================================================

def render_alerts(dashboard_data):
    """Render active alerts panel."""
    st.markdown("### 🚨 Active Alerts")

    alerts = dashboard_data.active_alerts
    if not alerts:
        st.success("No active alerts. All risk metrics within limits.")
        return

    for alert in alerts:
        level_colors = {
            "info": "blue",
            "warning": "orange",
            "critical": "red",
            "emergency": "darkred"
        }
        color = level_colors.get(alert.level, "gray")
        icon = {"info": "ℹ️", "warning": "⚠️", "critical": "🔴", "emergency": "🚨"}.get(alert.level, "⚪")

        st.markdown(f"""
        <div style="padding: 0.75rem; margin: 0.5rem 0; background: {color}11;
                    border-left: 3px solid {color}; border-radius: 4px;">
            <strong>{icon} [{alert.level.upper()}] {alert.category.title()}</strong><br>
            <span style="color: #666;">{alert.message}</span><br>
            <small style="color: #999;">
                Metric: {alert.metric_name} = {alert.metric_value:.4f} | Threshold: {alert.threshold:.4f}
            </small>
        </div>
        """, unsafe_allow_html=True)


# =============================================================================
# Limit Utilization
# =============================================================================

def render_limit_utilization(dashboard_data):
    """Render limit utilization gauges."""
    st.markdown("### 📏 Limit Utilization")

    col1, col2, col3, col4 = st.columns(4)

    limits = [
        ("Position Limit", dashboard_data.position_limit_util, col1),
        ("Sector Limit", dashboard_data.sector_limit_util, col2),
        ("Beta Limit", dashboard_data.beta_limit_util, col3),
        ("VaR Limit", dashboard_data.var_limit_util, col4),
    ]

    for name, util, col in limits:
        with col:
            util_pct = min(util, 1.5)  # Cap at 150% for display
            color = "green" if util < 0.8 else "orange" if util < 1.0 else "red"

            fig = go.Figure(go.Indicator(
                mode="gauge+number",
                value=util * 100,
                title={'text': name},
                gauge={
                    'axis': {'range': [0, 150]},
                    'bar': {'color': color},
                    'steps': [
                        {'range': [0, 80], 'color': "lightgreen"},
                        {'range': [80, 100], 'color': "lightyellow"},
                        {'range': [100, 150], 'color': "lightcoral"},
                    ],
                    'threshold': {
                        'line': {'color': "red", 'width': 2},
                        'thickness': 0.75,
                        'value': 100
                    }
                },
                number={'suffix': "%"}
            ))
            fig.update_layout(height=200, margin=dict(l=20, r=20, t=40, b=0))
            st.plotly_chart(fig, use_container_width=True)


# =============================================================================
# Configuration Panel
# =============================================================================

def render_config_panel():
    """Render risk configuration panel."""
    st.markdown("### ⚙️ Risk Configuration")

    config = st.session_state.risk_config

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**Position Limits**")
        max_pos = st.slider("Max Position %", 5, 30, int(config.max_position_pct * 100)) / 100
        max_sector = st.slider("Max Sector %", 20, 50, int(config.max_sector_pct * 100)) / 100
        max_top5 = st.slider("Max Top 5 %", 40, 80, int(config.max_top5_pct * 100)) / 100

    with col2:
        st.markdown("**Stop-Loss & Drawdown**")
        stop_loss = st.slider("Position Stop Loss %", 5, 30, int(abs(config.position_stop_loss) * 100)) / 100
        dd_warning = st.slider("Drawdown Warning %", 3, 10, int(abs(config.portfolio_drawdown_warning) * 100)) / 100
        dd_reduce = st.slider("Drawdown Reduce %", 8, 20, int(abs(config.portfolio_drawdown_reduce) * 100)) / 100

    with col3:
        st.markdown("**Risk Limits**")
        max_beta = st.slider("Max Portfolio Beta", 1.0, 2.0, config.max_portfolio_beta, 0.1)
        max_vol = st.slider("Max Volatility %", 20, 50, int(config.max_portfolio_volatility * 100)) / 100
        var_max = st.slider("Max VaR %", 3, 10, int(config.var_max_pct * 100)) / 100

    if st.button("Update Configuration", type="primary"):
        st.session_state.risk_config = RiskConfig(
            max_position_pct=max_pos,
            max_sector_pct=max_sector,
            max_top5_pct=max_top5,
            position_stop_loss=-stop_loss,
            portfolio_drawdown_warning=-dd_warning,
            portfolio_drawdown_reduce=-dd_reduce,
            max_portfolio_beta=max_beta,
            max_portfolio_volatility=max_vol,
            var_max_pct=var_max,
        )
        st.session_state.risk_monitor = RiskMonitor(config=st.session_state.risk_config)
        st.success("Configuration updated!")
        st.rerun()


# =============================================================================
# PRD-65: Shock Propagation
# =============================================================================

def render_shock_propagation():
    """Render shock propagation analysis."""
    st.markdown("### 💥 Shock Propagation Analysis")
    st.caption("Analyze how factor shocks cascade through portfolio via correlations")

    engine = ShockPropagationEngine()

    col1, col2 = st.columns([1, 2])

    with col1:
        st.markdown("**Initial Shock**")
        shock_factor = st.selectbox(
            "Factor",
            ["market", "rates", "credit", "volatility", "growth", "value", "momentum", "quality"]
        )
        shock_magnitude = st.slider("Magnitude", -0.20, 0.20, -0.10, 0.01, format="%.2f")
        max_hops = st.slider("Max Propagation Hops", 1, 5, 2)

        # Demo position exposures
        position_exposures = {
            "AAPL": {shock_factor: 1.2, "market": 1.1, "growth": 0.8},
            "MSFT": {shock_factor: 1.0, "market": 1.0, "quality": 0.9},
            "NVDA": {shock_factor: 1.5, "market": 1.3, "momentum": 1.2},
            "JPM": {shock_factor: 0.8, "market": 1.0, "value": 1.1},
            "XOM": {shock_factor: 0.5, "market": 0.9, "value": 1.0},
        }
        position_values = {"AAPL": 18500, "MSFT": 15000, "NVDA": 12000, "JPM": 9500, "XOM": 6000}
        portfolio_value = sum(position_values.values())

    with col2:
        if st.button("Run Shock Propagation", type="primary"):
            initial_shocks = [FactorShock(factor=shock_factor, magnitude=shock_magnitude)]

            result = engine.propagate_shock(
                initial_shocks=initial_shocks,
                position_exposures=position_exposures,
                position_values=position_values,
                portfolio_value=portfolio_value,
                max_hops=max_hops
            )

            # Display results
            col2a, col2b, col2c = st.columns(3)
            with col2a:
                st.metric("Total Impact", f"{result.total_impact_pct:.2%}")
            with col2b:
                st.metric("Amplification", f"{result.amplification_factor:.2f}x")
            with col2c:
                st.metric("Worst Position", f"{result.worst_position}")

            # Position impacts chart
            impacts = {ps.symbol: ps.total_impact_pct for ps in result.position_shocks}
            fig = go.Figure(go.Bar(
                x=list(impacts.keys()),
                y=list(impacts.values()),
                marker_color=["red" if v < 0 else "green" for v in impacts.values()]
            ))
            fig.update_layout(
                title="Position Impacts",
                xaxis_title="Position",
                yaxis_title="Impact (%)",
                yaxis_tickformat=".1%",
                height=300
            )
            st.plotly_chart(fig, use_container_width=True)

            # Contagion trace
            st.markdown("**Contagion Paths**")
            paths = engine.trace_contagion(shock_factor, shock_magnitude, max_hops)
            for path in paths[:5]:
                st.write(f"→ {' → '.join(path.path)} (total: {path.total_magnitude:.3f})")


# =============================================================================
# PRD-65: Drawdown Analysis
# =============================================================================

def render_drawdown_analysis():
    """Render drawdown analysis."""
    st.markdown("### 📉 Drawdown Analysis")
    st.caption("Analyze drawdown patterns, underwater periods, and conditional drawdown")

    analyzer = DrawdownAnalyzer()

    # Generate demo portfolio values
    np.random.seed(42)
    n_days = 504  # 2 years
    dates = pd.date_range(end=datetime.now(), periods=n_days, freq='D')
    returns = np.random.normal(0.0003, 0.015, n_days)

    # Add some drawdown events
    returns[100:130] = np.random.normal(-0.01, 0.02, 30)  # First drawdown
    returns[250:300] = np.random.normal(-0.008, 0.018, 50)  # Second drawdown
    returns[400:420] = np.random.normal(-0.015, 0.025, 20)  # Third drawdown

    values = 100000 * np.cumprod(1 + returns)

    col1, col2 = st.columns([2, 1])

    with col1:
        # Underwater curve
        underwater = analyzer.compute_underwater_curve(values.tolist(), "Portfolio")

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=dates,
            y=underwater.drawdowns,
            fill='tozeroy',
            fillcolor='rgba(255, 0, 0, 0.3)',
            line=dict(color='red'),
            name='Drawdown'
        ))
        fig.update_layout(
            title="Underwater Curve",
            xaxis_title="Date",
            yaxis_title="Drawdown",
            yaxis_tickformat=".1%",
            height=300
        )
        st.plotly_chart(fig, use_container_width=True)

        # Portfolio value with peaks
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=dates, y=values, name='Portfolio', line=dict(color='blue')
        ))
        fig2.add_trace(go.Scatter(
            x=dates, y=underwater.running_max, name='High-Water Mark',
            line=dict(color='green', dash='dash')
        ))
        fig2.update_layout(
            title="Portfolio Value vs High-Water Mark",
            yaxis_title="Value ($)",
            height=300
        )
        st.plotly_chart(fig2, use_container_width=True)

    with col2:
        # Drawdown metrics
        metrics = analyzer.compute_metrics(values.tolist(), returns.tolist(), "Portfolio")

        st.metric("Max Drawdown", f"{metrics.max_drawdown:.2%}")
        st.metric("Current Drawdown", f"{metrics.current_drawdown:.2%}")
        st.metric("Avg Duration (days)", f"{metrics.avg_duration:.0f}")
        st.metric("% Time Underwater", f"{metrics.pct_time_underwater:.1%}")
        st.metric("Calmar Ratio", f"{metrics.calmar_ratio:.2f}")
        st.metric("Ulcer Index", f"{metrics.ulcer_index:.4f}")

        # Drawdown events
        st.markdown("**Drawdown Events**")
        events = analyzer.identify_drawdown_events(values.tolist(), "Portfolio")
        for i, evt in enumerate(events[:5], 1):
            st.write(f"{i}. {evt.max_drawdown:.1%} over {evt.duration} days")


# =============================================================================
# PRD-65: Recovery Estimation
# =============================================================================

def render_recovery_estimation():
    """Render recovery time estimation."""
    st.markdown("### 🔄 Recovery Estimation")
    st.caption("Estimate time to recover from current drawdown")

    estimator = RecoveryEstimator(n_simulations=500)

    col1, col2 = st.columns([1, 2])

    with col1:
        st.markdown("**Current State**")
        current_drawdown = st.slider("Current Drawdown %", -50, -1, -15, 1) / 100
        drift = st.slider("Expected Daily Return (bps)", 0, 20, 3) / 10000
        volatility = st.slider("Daily Volatility (%)", 0.5, 4.0, 1.5, 0.1) / 100

        method = st.radio("Estimation Method", ["Monte Carlo", "Analytical"])

    with col2:
        if st.button("Estimate Recovery", type="primary"):
            if method == "Monte Carlo":
                estimate = estimator.monte_carlo_estimate(
                    current_drawdown=current_drawdown,
                    drift=drift,
                    volatility=volatility,
                    symbol="Portfolio"
                )
            else:
                estimate = estimator.analytical_estimate(
                    current_drawdown=current_drawdown,
                    drift=drift,
                    volatility=volatility,
                    symbol="Portfolio"
                )

            col2a, col2b, col2c = st.columns(3)
            with col2a:
                st.metric("Expected Days", f"{estimate.expected_days:.0f}")
            with col2b:
                st.metric("Median Days", f"{estimate.median_days:.0f}")
            with col2c:
                st.metric("90th Percentile", f"{estimate.days_90th_pctile:.0f}")

            # Recovery probability chart
            probs = {
                "30 days": estimate.probability_30d,
                "90 days": estimate.probability_90d,
                "180 days": estimate.probability_180d,
            }
            fig = go.Figure(go.Bar(
                x=list(probs.keys()),
                y=list(probs.values()),
                marker_color=['#ff6b6b', '#feca57', '#48dbfb'],
                text=[f"{v:.0%}" for v in probs.values()],
                textposition='outside'
            ))
            fig.update_layout(
                title="Recovery Probability by Horizon",
                yaxis_title="Probability",
                yaxis_tickformat=".0%",
                yaxis_range=[0, 1.1],
                height=300
            )
            st.plotly_chart(fig, use_container_width=True)

            st.info(f"**Confidence:** {estimate.recovery_confidence.title()} | **Method:** {estimate.method}")

        # Breakeven analysis
        st.markdown("---")
        st.markdown("**Breakeven Analysis**")
        current_value = st.number_input("Current Value ($)", 10000, 1000000, 85000, 1000)
        peak_value = st.number_input("Peak Value ($)", 10000, 1000000, 100000, 1000)

        if current_value < peak_value:
            breakeven = estimator.breakeven_analysis(current_value, peak_value, drift)
            st.write(f"Required Gain: **{breakeven.required_gain_pct:.1%}**")
            st.write(f"Days to Breakeven: **{breakeven.days_to_breakeven:.0f}**")
            if breakeven.is_deep_hole:
                st.warning("Significant compounding effect - recovery may take longer than linear estimate")


# =============================================================================
# PRD-65: Scenario Builder
# =============================================================================

def render_scenario_builder():
    """Render custom scenario builder."""
    st.markdown("### 🔧 Scenario Builder")
    st.caption("Build custom stress scenarios from templates or macro shocks")

    builder = ScenarioBuilder()

    tab1, tab2, tab3 = st.tabs(["From Template", "Custom Build", "Combined"])

    with tab1:
        st.markdown("**Build from Pre-defined Template**")

        templates = builder.list_templates()
        template_names = [t["name"] for t in templates]

        col1, col2 = st.columns([1, 2])

        with col1:
            selected = st.selectbox("Template", template_names)
            severity = st.slider("Severity Multiplier", 0.5, 2.0, 1.0, 0.1)

            if st.button("Build Scenario", key="build_template"):
                # Find template key
                template_key = [k for k, v in SCENARIO_TEMPLATES.items() if v.name == selected][0]
                scenario = builder.from_template(template_key, severity)

                st.session_state.built_scenario = scenario

        with col2:
            if "built_scenario" in st.session_state:
                scenario = st.session_state.built_scenario

                st.markdown(f"**{scenario.name}**")
                st.write(scenario.description)

                col2a, col2b, col2c = st.columns(3)
                with col2a:
                    st.metric("Market Shock", f"{scenario.market_shock:.1%}")
                with col2b:
                    st.metric("Severity Score", f"{scenario.severity_score:.0f}/100")
                with col2c:
                    st.metric("Vol Multiplier", f"{scenario.volatility_multiplier:.2f}x")

                # Sector impacts
                if scenario.sector_rotations:
                    sectors = {r.sector: r.impact_pct for r in scenario.sector_rotations}
                    fig = go.Figure(go.Bar(
                        y=list(sectors.keys()),
                        x=list(sectors.values()),
                        orientation='h',
                        marker_color=["red" if v < 0 else "green" for v in sectors.values()]
                    ))
                    fig.update_layout(
                        title="Sector Impacts",
                        xaxis_tickformat=".0%",
                        height=250
                    )
                    st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.markdown("**Build from Macro Shocks**")

        from src.risk import MacroShock

        col1, col2 = st.columns(2)

        with col1:
            rate_shock = st.slider("Interest Rate Shock (%)", -2.0, 2.0, 0.5, 0.1) / 100
            inflation = st.slider("Inflation Shock (%)", -2.0, 4.0, 1.0, 0.1) / 100

        with col2:
            growth = st.slider("Growth Shock (%)", -5.0, 3.0, -1.0, 0.1) / 100
            dollar = st.slider("Dollar Shock (%)", -10.0, 10.0, 2.0, 0.5) / 100

        if st.button("Build Custom Scenario", key="build_custom"):
            shocks = []
            if abs(rate_shock) > 0.001:
                shocks.append(MacroShock(
                    variable="interest_rates",
                    magnitude=abs(rate_shock),
                    direction="up" if rate_shock > 0 else "down"
                ))
            if abs(inflation) > 0.001:
                shocks.append(MacroShock(
                    variable="inflation",
                    magnitude=abs(inflation),
                    direction="up" if inflation > 0 else "down"
                ))
            if abs(growth) > 0.001:
                shocks.append(MacroShock(
                    variable="growth",
                    magnitude=abs(growth),
                    direction="up" if growth > 0 else "down"
                ))

            if shocks:
                custom = builder.from_macro_shocks(shocks, "Custom Macro Scenario")
                validation = builder.validate_scenario(custom)

                st.markdown(f"**Severity Score:** {validation['severity_score']:.0f}/100")
                st.markdown(f"**Components:** {validation['n_components']}")

                if not validation['valid']:
                    for issue in validation['issues']:
                        st.warning(issue)

                if custom.sector_rotations:
                    sectors = {r.sector: r.impact_pct for r in custom.sector_rotations}
                    st.dataframe(pd.DataFrame([
                        {"Sector": k, "Impact": f"{v:.1%}"}
                        for k, v in sectors.items()
                    ]), hide_index=True)

    with tab3:
        st.markdown("**Combine Multiple Scenarios**")
        st.info("Select templates to combine with custom weights")

        selected_templates = st.multiselect(
            "Templates to Combine",
            list(SCENARIO_TEMPLATES.keys()),
            default=["recession", "rate_shock"]
        )

        if len(selected_templates) >= 2:
            weights = []
            cols = st.columns(len(selected_templates))
            for i, (name, col) in enumerate(zip(selected_templates, cols)):
                with col:
                    w = st.number_input(f"{name} weight", 0.0, 1.0, 1.0 / len(selected_templates), 0.1, key=f"w_{name}")
                    weights.append(w)

            if st.button("Combine Scenarios"):
                scenarios = [builder.from_template(t) for t in selected_templates]
                combined = builder.combine_scenarios(scenarios, weights, "Combined Stress Scenario")

                st.metric("Combined Market Shock", f"{combined.market_shock:.1%}")
                st.metric("Combined Severity", f"{combined.severity_score:.0f}/100")


# =============================================================================
# Main Page
# =============================================================================

def main():
    """Main risk dashboard page."""
    st.title("🛡️ Risk Management")

    if not RISK_AVAILABLE:
        st.error("Risk module is not available. Please check installation.")
        return

    init_session_state()

    # Sidebar
    with st.sidebar:
        st.markdown("## Risk Dashboard")
        st.markdown("---")

        demo_mode = st.toggle("Demo Mode", value=st.session_state.demo_mode)
        st.session_state.demo_mode = demo_mode

        if st.button("Refresh Analysis", type="primary"):
            if demo_mode:
                positions, returns, benchmark_returns, portfolio_value = get_demo_data()

                dashboard = st.session_state.risk_monitor.update(
                    positions=positions,
                    returns=returns,
                    benchmark_returns=benchmark_returns,
                    portfolio_value=portfolio_value,
                )
                st.session_state.risk_dashboard_data = dashboard
                st.session_state.demo_positions = positions
                st.session_state.demo_portfolio_value = portfolio_value
                st.success("Analysis complete!")
                st.rerun()
            else:
                st.info("Connect to live portfolio for real-time analysis")

        st.markdown("---")
        st.markdown("### Quick Stats")
        if st.session_state.risk_dashboard_data:
            d = st.session_state.risk_dashboard_data
            st.metric("Status", d.overall_status.upper())
            st.metric("Recovery", d.recovery_state)
            st.metric("Size Multiplier", f"{d.position_size_multiplier:.0%}")

    # Run initial analysis if no data
    if st.session_state.risk_dashboard_data is None and st.session_state.demo_mode:
        positions, returns, benchmark_returns, portfolio_value = get_demo_data()
        dashboard = st.session_state.risk_monitor.update(
            positions=positions,
            returns=returns,
            benchmark_returns=benchmark_returns,
            portfolio_value=portfolio_value,
        )
        st.session_state.risk_dashboard_data = dashboard
        st.session_state.demo_positions = positions
        st.session_state.demo_portfolio_value = portfolio_value

    dashboard_data = st.session_state.risk_dashboard_data
    positions = st.session_state.get("demo_positions", [])
    portfolio_value = st.session_state.get("demo_portfolio_value", 100000)

    # Main content
    render_status_header(dashboard_data)

    if dashboard_data:
        st.markdown("---")

        # Tabs for different views
        tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
            "📊 Metrics", "📉 VaR", "🎯 Concentration", "🔥 Stress Tests",
            "💥 Shock Propagation", "📉 Drawdown", "🔄 Recovery", "🔧 Scenarios", "⚙️ Config"
        ])

        with tab1:
            render_portfolio_metrics(dashboard_data)
            st.markdown("---")
            render_limit_utilization(dashboard_data)

        with tab2:
            render_var_metrics(dashboard_data, portfolio_value)

        with tab3:
            render_concentration(dashboard_data, positions)

        with tab4:
            render_stress_tests(dashboard_data, portfolio_value)

        with tab5:
            render_shock_propagation()

        with tab6:
            render_drawdown_analysis()

        with tab7:
            render_recovery_estimation()

        with tab8:
            render_scenario_builder()

        with tab9:
            render_config_panel()

        # Alerts at bottom
        st.markdown("---")
        render_alerts(dashboard_data)

    # Risk report download
    if dashboard_data and st.session_state.risk_monitor:
        st.markdown("---")
        col1, col2 = st.columns([3, 1])
        with col2:
            report = st.session_state.risk_monitor.generate_risk_report()
            st.download_button(
                "📄 Download Risk Report",
                data=report,
                file_name=f"risk_report_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                mime="text/plain"
            )



main()
