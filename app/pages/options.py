"""Options Trading Dashboard.

Provides:
- Options pricing calculator with Greeks
- Strategy builder with payoff diagrams
- Volatility surface visualization
- Probability of profit analysis
- Unusual activity scanner
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
from app.styles import inject_global_styles
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta

# Page config
try:
    st.set_page_config(
        page_title="Axion Options Platform",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded",
    )
except st.errors.StreamlitAPIException:
    pass

inject_global_styles()


# Import options module
try:
    from src.options import (
        OptionsPricingEngine,
        OptionPrice,
        OptionLeg,
        StrategyBuilder,
        StrategyAnalysis,
        StrategyType,
        VolatilitySurfaceBuilder,
        VolAnalytics,
        UnusualActivityDetector,
        ActivitySignal,
        OptionsConfig,
    )
    OPTIONS_AVAILABLE = True
except ImportError as e:
    OPTIONS_AVAILABLE = False
    st.error(f"Options module not available: {e}")


# =============================================================================
# Session State
# =============================================================================

def init_session_state():
    """Initialize session state."""
    if "pricing_engine" not in st.session_state:
        st.session_state.pricing_engine = OptionsPricingEngine()
    if "strategy_builder" not in st.session_state:
        st.session_state.strategy_builder = StrategyBuilder()
    if "current_strategy" not in st.session_state:
        st.session_state.current_strategy = None


# =============================================================================
# Options Pricing Calculator
# =============================================================================

def render_pricing_calculator():
    """Render the options pricing calculator."""
    st.markdown("### 🧮 Options Pricing Calculator")

    col1, col2 = st.columns([1, 2])

    with col1:
        st.markdown("**Input Parameters**")

        spot = st.number_input("Underlying Price ($)", value=100.0, min_value=0.01, step=1.0)
        strike = st.number_input("Strike Price ($)", value=100.0, min_value=0.01, step=1.0)
        dte = st.number_input("Days to Expiration", value=30, min_value=1, max_value=730, step=1)
        iv = st.slider("Implied Volatility (%)", min_value=5, max_value=150, value=25) / 100
        r = st.slider("Risk-Free Rate (%)", min_value=0.0, max_value=10.0, value=5.0) / 100
        option_type = st.selectbox("Option Type", ["call", "put"])
        model = st.selectbox("Pricing Model", ["Black-Scholes", "Binomial", "Monte Carlo"])

        calc_button = st.button("Calculate", type="primary")

    with col2:
        if calc_button:
            engine = st.session_state.pricing_engine
            T = dte / 365.0

            model_map = {
                "Black-Scholes": "black_scholes",
                "Binomial": "binomial",
                "Monte Carlo": "monte_carlo",
            }

            result = engine.price_option(
                S=spot, K=strike, T=T, r=r, sigma=iv,
                option_type=option_type, model=model_map[model]
            )

            # Display results
            st.markdown("**Option Valuation**")

            metrics_col1, metrics_col2, metrics_col3 = st.columns(3)

            with metrics_col1:
                st.metric("Option Price", f"${result.price:.2f}")
                st.metric("Delta", f"{result.delta:.4f}")

            with metrics_col2:
                st.metric("Gamma", f"{result.gamma:.4f}")
                st.metric("Theta", f"${result.theta:.4f}/day")

            with metrics_col3:
                st.metric("Vega", f"${result.vega:.4f}/1%")
                st.metric("Rho", f"${result.rho:.4f}/1%")

            # Intrinsic vs time value
            intrinsic = max(spot - strike, 0) if option_type == "call" else max(strike - spot, 0)
            time_value = result.price - intrinsic

            st.markdown("---")
            col_a, col_b = st.columns(2)
            with col_a:
                st.metric("Intrinsic Value", f"${intrinsic:.2f}")
            with col_b:
                st.metric("Time Value", f"${time_value:.2f}")

            # Sensitivity chart
            st.markdown("**Price Sensitivity**")

            # Price vs underlying
            underlyings = np.linspace(spot * 0.8, spot * 1.2, 50)
            prices = []
            for S in underlyings:
                p = engine.black_scholes(S, strike, T, r, iv, option_type)
                prices.append(p.price)

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=underlyings, y=prices,
                mode='lines', name='Option Price',
                line=dict(color='blue', width=2)
            ))
            fig.add_vline(x=spot, line_dash="dash", line_color="gray",
                          annotation_text="Current")
            fig.add_vline(x=strike, line_dash="dot", line_color="red",
                          annotation_text="Strike")
            fig.update_layout(
                title="Option Price vs Underlying",
                xaxis_title="Underlying Price ($)",
                yaxis_title="Option Price ($)",
                height=350,
            )
            st.plotly_chart(fig, use_container_width=True)


# =============================================================================
# Strategy Builder
# =============================================================================

def render_strategy_builder():
    """Render the strategy builder."""
    st.markdown("### 🔨 Strategy Builder")

    col1, col2 = st.columns([1, 2])

    with col1:
        spot = st.number_input("Underlying Price", value=100.0, min_value=0.01, key="strat_spot")
        iv = st.slider("IV (%)", 5, 100, 25, key="strat_iv") / 100
        dte = st.number_input("DTE", value=30, min_value=1, key="strat_dte")

        strategy_type = st.selectbox("Strategy", [
            "Long Call",
            "Long Put",
            "Bull Call Spread",
            "Bear Put Spread",
            "Iron Condor",
            "Iron Butterfly",
            "Straddle",
            "Strangle",
        ])

        # Strategy-specific parameters
        if strategy_type in ["Bull Call Spread", "Bear Put Spread"]:
            width = st.number_input("Spread Width ($)", value=5.0, min_value=1.0)
        elif strategy_type == "Iron Condor":
            put_width = st.number_input("Put Wing Offset ($)", value=10.0)
            call_width = st.number_input("Call Wing Offset ($)", value=10.0)
            wing_width = st.number_input("Wing Width ($)", value=5.0)
        elif strategy_type == "Iron Butterfly":
            wing_width = st.number_input("Wing Width ($)", value=10.0)
        elif strategy_type == "Strangle":
            put_offset = st.number_input("Put Offset ($)", value=5.0)
            call_offset = st.number_input("Call Offset ($)", value=5.0)
        else:
            strike = st.number_input("Strike ($)", value=spot, key="strat_strike")

        build_button = st.button("Analyze Strategy", type="primary")

    with col2:
        if build_button:
            builder = st.session_state.strategy_builder

            # Build strategy legs
            if strategy_type == "Long Call":
                legs = builder.build_long_call(spot, strike, dte, iv)
            elif strategy_type == "Long Put":
                legs = builder.build_long_put(spot, strike, dte, iv)
            elif strategy_type == "Bull Call Spread":
                legs = builder.build_bull_call_spread(spot, width, dte, iv)
            elif strategy_type == "Bear Put Spread":
                legs = builder.build_bear_put_spread(spot, width, dte, iv)
            elif strategy_type == "Iron Condor":
                legs = builder.build_iron_condor(spot, put_width, call_width, wing_width, dte, iv)
            elif strategy_type == "Iron Butterfly":
                legs = builder.build_iron_butterfly(spot, wing_width, dte, iv)
            elif strategy_type == "Straddle":
                legs = builder.build_straddle(spot, spot, dte, iv)
            elif strategy_type == "Strangle":
                legs = builder.build_strangle(spot, put_offset, call_offset, dte, iv)
            else:
                legs = []

            if legs:
                analysis = builder.analyze(legs, spot, iv, name=strategy_type)
                st.session_state.current_strategy = analysis

                # Display analysis
                st.markdown(f"**{strategy_type} Analysis**")

                m1, m2, m3, m4 = st.columns(4)
                with m1:
                    st.metric("Max Profit", f"${analysis.max_profit:,.0f}")
                with m2:
                    st.metric("Max Loss", f"${analysis.max_loss:,.0f}")
                with m3:
                    st.metric("PoP", f"{analysis.probability_of_profit:.1%}")
                with m4:
                    st.metric("Risk/Reward", f"{analysis.risk_reward_ratio:.2f}:1")

                m5, m6, m7, m8 = st.columns(4)
                with m5:
                    st.metric("Net Premium", f"${analysis.net_debit_credit:,.0f}")
                with m6:
                    st.metric("Capital Required", f"${analysis.capital_required:,.0f}")
                with m7:
                    st.metric("Breakeven(s)", ", ".join(f"${b}" for b in analysis.breakeven_points))
                with m8:
                    st.metric("Max Ann. Return", f"{analysis.annualized_return_max:.0%}")

                # Greeks
                st.markdown("**Net Greeks**")
                g1, g2, g3, g4 = st.columns(4)
                with g1:
                    st.metric("Delta", f"{analysis.net_delta:.3f}")
                with g2:
                    st.metric("Gamma", f"{analysis.net_gamma:.4f}")
                with g3:
                    st.metric("Theta", f"${analysis.net_theta:.2f}/day")
                with g4:
                    st.metric("Vega", f"${analysis.net_vega:.2f}/1%")

                # Payoff diagram
                payoff = builder.payoff_diagram(legs, spot)

                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=payoff.prices, y=payoff.pnl,
                    mode='lines', name='P&L at Expiration',
                    line=dict(color='blue', width=2),
                    fill='tozeroy',
                    fillcolor='rgba(0, 100, 200, 0.2)',
                ))
                fig.add_hline(y=0, line_dash="solid", line_color="gray")
                fig.add_vline(x=spot, line_dash="dash", line_color="green",
                              annotation_text=f"Current: ${spot}")

                for be in analysis.breakeven_points:
                    fig.add_vline(x=be, line_dash="dot", line_color="orange",
                                  annotation_text=f"BE: ${be}")

                fig.update_layout(
                    title=f"{strategy_type} Payoff Diagram",
                    xaxis_title="Underlying Price at Expiration ($)",
                    yaxis_title="Profit/Loss ($)",
                    height=400,
                )
                st.plotly_chart(fig, use_container_width=True)

                # Legs table
                with st.expander("Strategy Legs", expanded=False):
                    legs_data = []
                    for leg in legs:
                        legs_data.append({
                            "Type": leg.option_type.upper(),
                            "Strike": f"${leg.strike:.0f}",
                            "Premium": f"${leg.premium:.2f}",
                            "Qty": leg.quantity,
                            "Delta": f"{leg.greeks.delta:.3f}" if leg.greeks else "-",
                        })
                    st.dataframe(pd.DataFrame(legs_data), use_container_width=True)


# =============================================================================
# IV Analysis
# =============================================================================

def render_iv_analysis():
    """Render IV analysis section."""
    st.markdown("### 📊 Implied Volatility Analysis")

    # Generate demo IV surface data
    np.random.seed(42)

    moneyness = np.linspace(0.85, 1.15, 15)
    dtes = np.array([7, 14, 30, 60, 90, 180])

    # Create IV surface with smile
    iv_surface = np.zeros((len(dtes), len(moneyness)))
    for i, d in enumerate(dtes):
        base_iv = 0.20 + 0.05 * np.sqrt(d / 30)  # Term structure
        smile = 0.15 * (moneyness - 1.0) ** 2  # Smile
        skew = -0.10 * (moneyness - 1.0)  # Skew
        iv_surface[i, :] = base_iv + smile + skew + np.random.normal(0, 0.01, len(moneyness))

    # 3D surface plot
    fig = go.Figure(data=[go.Surface(
        x=moneyness,
        y=dtes,
        z=iv_surface * 100,  # Convert to percentage
        colorscale='Viridis',
        colorbar_title='IV (%)',
    )])
    fig.update_layout(
        title='Implied Volatility Surface',
        scene=dict(
            xaxis_title='Moneyness (K/S)',
            yaxis_title='Days to Expiration',
            zaxis_title='IV (%)',
        ),
        height=500,
    )
    st.plotly_chart(fig, use_container_width=True)

    # IV Analytics
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Volatility Metrics**")
        atm_iv = iv_surface[2, 7] * 100  # 30 DTE, ATM
        st.metric("ATM IV (30d)", f"{atm_iv:.1f}%")
        st.metric("IV Skew (25d)", f"{(iv_surface[2, 3] - iv_surface[2, 11]) * 100:.1f}%")
        st.metric("IV Rank", "62%")
        st.metric("IV Percentile", "58%")

    with col2:
        st.markdown("**Term Structure**")
        term_df = pd.DataFrame({
            "DTE": dtes,
            "ATM IV": [f"{iv_surface[i, 7] * 100:.1f}%" for i in range(len(dtes))],
        })
        st.dataframe(term_df, use_container_width=True, hide_index=True)


# =============================================================================
# Unusual Activity
# =============================================================================

def render_unusual_activity():
    """Render unusual activity scanner."""
    st.markdown("### 🔥 Unusual Options Activity")

    # Demo activity data
    activity_data = [
        {"Symbol": "NVDA", "Type": "CALL", "Strike": "$140", "Exp": "Feb 21",
         "Volume": "45,200", "OI": "8,100", "Premium": "$12.5M", "Signal": "SWEEP", "Severity": "🔴"},
        {"Symbol": "AAPL", "Type": "PUT", "Strike": "$170", "Exp": "Feb 14",
         "Volume": "22,100", "OI": "3,400", "Premium": "$4.2M", "Signal": "BLOCK", "Severity": "🟠"},
        {"Symbol": "TSLA", "Type": "CALL", "Strike": "$280", "Exp": "Mar 21",
         "Volume": "18,700", "OI": "5,200", "Premium": "$8.1M", "Signal": "VOL SPIKE", "Severity": "🟡"},
        {"Symbol": "META", "Type": "CALL", "Strike": "$600", "Exp": "Feb 21",
         "Volume": "15,400", "OI": "2,100", "Premium": "$6.8M", "Signal": "OI SURGE", "Severity": "🟡"},
        {"Symbol": "MSFT", "Type": "PUT", "Strike": "$400", "Exp": "Feb 28",
         "Volume": "12,300", "OI": "4,500", "Premium": "$3.1M", "Signal": "IV SPIKE", "Severity": "🟠"},
    ]

    df = pd.DataFrame(activity_data)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Severity": st.column_config.TextColumn("Level"),
        }
    )

    # Summary stats
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Signals", "47")
    with col2:
        st.metric("Bullish Flow", "$42.8M", "+12%")
    with col3:
        st.metric("Bearish Flow", "$18.3M", "-5%")
    with col4:
        st.metric("Net Sentiment", "BULLISH")


# =============================================================================
# Main Page
# =============================================================================

def main():
    """Main options dashboard page."""
    st.title("📈 Options Trading Platform")

    if not OPTIONS_AVAILABLE:
        st.error("Options module is not available. Please check installation.")
        return

    init_session_state()

    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "🧮 Pricing Calculator",
        "🔨 Strategy Builder",
        "📊 IV Analysis",
        "🔥 Unusual Activity",
    ])

    with tab1:
        render_pricing_calculator()

    with tab2:
        render_strategy_builder()

    with tab3:
        render_iv_analysis()

    with tab4:
        render_unusual_activity()



main()
