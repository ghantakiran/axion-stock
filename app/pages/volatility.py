"""Volatility Analysis Dashboard."""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

try:
    st.set_page_config(page_title="Volatility Analysis", layout="wide")
except st.errors.StreamlitAPIException:
    pass

st.title("Volatility Analysis")

# --- Sidebar ---
st.sidebar.header("Volatility Settings")
symbol = st.sidebar.text_input("Symbol", "AAPL")
method = st.sidebar.selectbox("Method", ["Historical", "EWMA", "Parkinson", "Garman-Klass"])
window = st.sidebar.selectbox("Window", ["1 Week", "1 Month", "3 Months", "6 Months", "1 Year"], index=1)

# --- Main Content ---
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "Overview", "Surface", "Term Structure", "Regime",
    "SVI Calibration", "Skew Analytics", "Term Model", "Vol Signals",
])

# --- Tab 1: Overview ---
with tab1:
    st.subheader("Volatility Overview")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Historical Vol (21d)", "18.5%")
    col2.metric("EWMA Vol", "19.2%")
    col3.metric("Parkinson Vol", "17.8%")
    col4.metric("Garman-Klass Vol", "18.1%")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Percentile", "42nd")
    col6.metric("IV (30d)", "22.3%")
    col7.metric("Vol Risk Premium", "3.8%")
    col8.metric("Regime", "Normal")

    st.markdown("#### Volatility Cone")
    cone_data = pd.DataFrame({
        "Window": ["1W", "2W", "1M", "2M", "3M", "6M", "1Y"],
        "5th": [10.2, 11.5, 12.8, 13.5, 14.0, 14.8, 15.2],
        "25th": [14.5, 15.2, 15.8, 16.2, 16.5, 16.8, 17.0],
        "50th": [18.0, 18.5, 19.0, 19.2, 19.5, 19.8, 20.0],
        "75th": [22.5, 22.0, 21.5, 21.2, 21.0, 20.8, 20.5],
        "95th": [30.5, 28.8, 27.2, 26.0, 25.5, 24.8, 24.0],
        "Current": [18.5, 17.8, 18.5, 19.0, 18.8, 19.2, 19.5],
    })
    st.dataframe(cone_data, use_container_width=True, hide_index=True)

# --- Tab 2: Surface ---
with tab2:
    st.subheader("Volatility Surface")

    col1, col2, col3 = st.columns(3)
    col1.metric("ATM Vol (30d)", "22.3%")
    col2.metric("25d Skew", "-3.2%")
    col3.metric("25d Butterfly", "1.8%")

    st.markdown("#### Smile (30-Day)")
    smile_data = pd.DataFrame({
        "Moneyness": [0.85, 0.90, 0.95, 1.00, 1.05, 1.10, 1.15],
        "Strike": [170.0, 180.0, 190.0, 200.0, 210.0, 220.0, 230.0],
        "IV": [0.298, 0.265, 0.235, 0.223, 0.232, 0.248, 0.270],
    })
    st.dataframe(smile_data, use_container_width=True, hide_index=True)

    st.markdown("#### ATM Term Structure")
    ts_data = pd.DataFrame({
        "Tenor": ["1W", "2W", "1M", "2M", "3M", "6M"],
        "ATM IV": [0.245, 0.235, 0.223, 0.228, 0.232, 0.240],
        "Realized": [0.185, 0.190, 0.185, 0.188, 0.192, 0.195],
        "VRP": [0.060, 0.045, 0.038, 0.040, 0.040, 0.045],
    })
    st.dataframe(ts_data, use_container_width=True, hide_index=True)

# --- Tab 3: Term Structure ---
with tab3:
    st.subheader("Realized Vol Term Structure")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Shape", "Contango")
    col2.metric("Slope", "+0.02%/day")
    col3.metric("Short-Term Vol", "18.5%")
    col4.metric("Long-Term Vol", "19.5%")

    st.markdown("#### Multi-Window Realized Vol")
    rv_data = pd.DataFrame({
        "Window": ["5d", "10d", "21d", "42d", "63d", "126d", "252d"],
        "Realized Vol": ["18.5%", "17.8%", "18.5%", "19.0%", "18.8%", "19.2%", "19.5%"],
        "Percentile": ["42%", "38%", "42%", "48%", "45%", "50%", "52%"],
        "vs 1Y Avg": ["-1.0%", "-1.7%", "-1.0%", "-0.5%", "-0.7%", "-0.3%", "0.0%"],
    })
    st.dataframe(rv_data, use_container_width=True, hide_index=True)

    st.markdown("#### IV vs RV Spread")
    spread_data = pd.DataFrame({
        "Tenor": ["1M", "2M", "3M", "6M"],
        "Implied Vol": ["22.3%", "22.8%", "23.2%", "24.0%"],
        "Realized Vol": ["18.5%", "19.0%", "18.8%", "19.2%"],
        "Spread": ["3.8%", "3.8%", "4.4%", "4.8%"],
        "Assessment": ["Normal", "Normal", "Elevated", "Elevated"],
    })
    st.dataframe(spread_data, use_container_width=True, hide_index=True)

# --- Tab 4: Regime ---
with tab4:
    st.subheader("Volatility Regime")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Current Regime", "Normal")
    col2.metric("Z-Score", "0.15")
    col3.metric("Percentile", "42nd")
    col4.metric("Days in Regime", "28")

    st.markdown("#### Regime History")
    regime_data = pd.DataFrame([
        {"Date": "2026-01-31", "Regime": "Normal", "Vol": "18.5%",
         "Z-Score": 0.15, "Percentile": "42%", "Changed": "No"},
        {"Date": "2026-01-03", "Regime": "Normal", "Vol": "17.2%",
         "Z-Score": -0.10, "Percentile": "38%", "Changed": "Yes"},
        {"Date": "2025-12-15", "Regime": "High", "Vol": "28.5%",
         "Z-Score": 1.85, "Percentile": "88%", "Changed": "Yes"},
        {"Date": "2025-11-01", "Regime": "Normal", "Vol": "19.0%",
         "Z-Score": 0.25, "Percentile": "52%", "Changed": "No"},
    ])
    st.dataframe(regime_data, use_container_width=True, hide_index=True)

    st.markdown("#### Regime Distribution (1Y)")
    dist_data = pd.DataFrame([
        {"Regime": "Low", "Fraction": "18%", "Days": "~45"},
        {"Regime": "Normal", "Fraction": "58%", "Days": "~146"},
        {"Regime": "High", "Fraction": "20%", "Days": "~50"},
        {"Regime": "Extreme", "Fraction": "4%", "Days": "~11"},
    ])
    st.dataframe(dist_data, use_container_width=True, hide_index=True)

# --- Tab 5: SVI Calibration ---
with tab5:
    st.subheader("SVI Surface Calibration")
    st.markdown("Stochastic Volatility Inspired (SVI) parametric surface fitting.")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Global RMSE", "0.008")
    col2.metric("Slices Fitted", "5")
    col3.metric("Points Fitted", "45")
    col4.metric("Fit Quality", "Excellent")

    svi_df = pd.DataFrame([
        {"Tenor": "7d", "a": 0.035, "b": 0.12, "rho": -0.35,
         "m": 0.00, "sigma": 0.18, "ATM Vol": "24.5%", "RMSE": 0.006},
        {"Tenor": "30d", "a": 0.040, "b": 0.10, "rho": -0.30,
         "m": 0.00, "sigma": 0.20, "ATM Vol": "22.3%", "RMSE": 0.008},
        {"Tenor": "60d", "a": 0.045, "b": 0.11, "rho": -0.28,
         "m": 0.00, "sigma": 0.21, "ATM Vol": "22.8%", "RMSE": 0.007},
        {"Tenor": "90d", "a": 0.050, "b": 0.10, "rho": -0.27,
         "m": 0.00, "sigma": 0.22, "ATM Vol": "23.2%", "RMSE": 0.009},
        {"Tenor": "180d", "a": 0.055, "b": 0.09, "rho": -0.25,
         "m": 0.00, "sigma": 0.23, "ATM Vol": "24.0%", "RMSE": 0.010},
    ])
    st.dataframe(svi_df, use_container_width=True, hide_index=True)

    # SVI surface heatmap
    moneyness = np.linspace(0.85, 1.15, 20)
    tenors = np.array([7, 30, 60, 90, 180])
    k = np.log(moneyness)
    iv_grid = np.zeros((len(tenors), len(k)))
    for i, t in enumerate(tenors):
        a, b, rho, sigma = 0.04 + 0.003 * i, 0.10, -0.30 + 0.02 * i, 0.20
        var = a + b * (rho * k + np.sqrt(k ** 2 + sigma ** 2))
        iv_grid[i] = np.sqrt(np.maximum(var, 0.001) / (t / 365.0))

    fig = go.Figure(data=go.Heatmap(
        z=iv_grid * 100, x=np.round(moneyness, 2), y=tenors,
        colorscale="Viridis", colorbar_title="IV (%)",
    ))
    fig.update_layout(
        title="Calibrated IV Surface",
        xaxis_title="Moneyness (K/S)",
        yaxis_title="Tenor (days)",
        height=350, margin=dict(l=0, r=0, t=40, b=0),
    )
    st.plotly_chart(fig, use_container_width=True)

# --- Tab 6: Skew Analytics ---
with tab6:
    st.subheader("Skew Analytics")
    st.markdown("Risk reversal, butterfly spreads, and skew regime classification.")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("25d Risk Reversal", "+5.8%")
    col2.metric("25d Butterfly", "+1.2%")
    col3.metric("Skew Regime", "Normal")
    col4.metric("Skew Z-Score", "0.45")

    skew_df = pd.DataFrame([
        {"Tenor": "7d", "Put Vol": "28.2%", "ATM Vol": "24.5%",
         "Call Vol": "22.8%", "RR": "+5.4%", "Butterfly": "+0.9%"},
        {"Tenor": "30d", "Put Vol": "26.5%", "ATM Vol": "22.3%",
         "Call Vol": "20.7%", "RR": "+5.8%", "Butterfly": "+1.3%"},
        {"Tenor": "60d", "Put Vol": "27.0%", "ATM Vol": "22.8%",
         "Call Vol": "21.5%", "RR": "+5.5%", "Butterfly": "+1.5%"},
        {"Tenor": "90d", "Put Vol": "27.5%", "ATM Vol": "23.2%",
         "Call Vol": "22.0%", "RR": "+5.5%", "Butterfly": "+1.6%"},
    ])
    st.dataframe(skew_df, use_container_width=True, hide_index=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Skew Term Structure**")
        tenors = [7, 30, 60, 90, 180]
        rr_vals = [5.4, 5.8, 5.5, 5.5, 4.8]
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=tenors, y=rr_vals, mode="lines+markers", name="Risk Reversal",
            line=dict(color="steelblue"),
        ))
        fig.update_layout(
            title="Risk Reversal by Tenor",
            xaxis_title="Tenor (days)", yaxis_title="RR (%)",
            height=300, margin=dict(l=0, r=0, t=40, b=0),
        )
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.markdown("**Skew Regime History**")
        regime_hist = pd.DataFrame([
            {"Date": "2026-02-03", "Regime": "Normal", "RR": "+5.8%", "Confidence": "50%"},
            {"Date": "2026-01-15", "Regime": "Panic", "RR": "+9.2%", "Confidence": "82%"},
            {"Date": "2025-12-20", "Regime": "Normal", "RR": "+5.0%", "Confidence": "55%"},
        ])
        st.dataframe(regime_hist, use_container_width=True, hide_index=True)

# --- Tab 7: Term Model ---
with tab7:
    st.subheader("Term Structure Model (Nelson-Siegel)")
    st.markdown("Parametric term structure fitting with carry/roll-down analysis.")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Long-Term Vol (beta0)", "22.5%")
    col2.metric("Slope (beta1)", "-2.5%")
    col3.metric("Curvature (beta2)", "+0.8%")
    col4.metric("Fit RMSE", "0.003")

    # Nelson-Siegel fitted curve
    tenors_plot = np.linspace(5, 365, 100)
    beta0, beta1, beta2, tau = 0.225, -0.025, 0.008, 90.0
    x = tenors_plot / tau
    ex = np.exp(-x)
    fitted_vol = beta0 + beta1 * (1 - ex) / x + beta2 * ((1 - ex) / x - ex)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=tenors_plot, y=fitted_vol * 100, mode="lines", name="Fitted",
        line=dict(color="steelblue"),
    ))
    # Observed points
    obs_tenors = [7, 30, 60, 90, 180, 365]
    obs_vols = [24.5, 22.3, 22.8, 23.2, 24.0, 22.5]
    fig.add_trace(go.Scatter(
        x=obs_tenors, y=obs_vols, mode="markers", name="Observed",
        marker=dict(size=10, color="red"),
    ))
    fig.update_layout(
        title="Nelson-Siegel Term Structure Fit",
        xaxis_title="Tenor (days)", yaxis_title="Vol (%)",
        height=300, margin=dict(l=0, r=0, t=40, b=0),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("**Carry & Roll-Down Analysis**")
    carry_df = pd.DataFrame([
        {"Tenor": "30d", "IV": "22.3%", "RV": "18.5%", "Carry": "+3.8%",
         "Roll-Down": "+0.2%", "Total PnL": "+160 bps", "Signal": "Sell Vol"},
        {"Tenor": "60d", "IV": "22.8%", "RV": "19.0%", "Carry": "+3.8%",
         "Roll-Down": "+0.1%", "Total PnL": "+220 bps", "Signal": "Sell Vol"},
        {"Tenor": "90d", "IV": "23.2%", "RV": "18.8%", "Carry": "+4.4%",
         "Roll-Down": "+0.0%", "Total PnL": "+270 bps", "Signal": "Sell Vol"},
    ])
    st.dataframe(carry_df, use_container_width=True, hide_index=True)

# --- Tab 8: Vol Signals ---
with tab8:
    st.subheader("Volatility Regime Signals")
    st.markdown("Trading signals from vol-of-vol, mean reversion, and regime transitions.")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Vol-of-Vol", "1.2%", "42nd pctl")
    col2.metric("MR Z-Score", "0.15")
    col3.metric("MR Signal", "Neutral")
    col4.metric("Composite", "Neutral")

    signals_df = pd.DataFrame([
        {"Symbol": "AAPL", "VoV Pctl": "42%", "MR Z": "+0.15",
         "MR Signal": "Neutral", "Regime": "Normal", "Composite": "Neutral",
         "Action": "Hold"},
        {"Symbol": "NVDA", "VoV Pctl": "78%", "MR Z": "+1.8",
         "MR Signal": "Sell Vol", "Regime": "High", "Composite": "Risk Off",
         "Action": "Add Hedges"},
        {"Symbol": "TSLA", "VoV Pctl": "85%", "MR Z": "+2.2",
         "MR Signal": "Sell Vol", "Regime": "High", "Composite": "Strong Risk Off",
         "Action": "Reduce Exposure"},
        {"Symbol": "MSFT", "VoV Pctl": "18%", "MR Z": "-1.6",
         "MR Signal": "Buy Vol", "Regime": "Low", "Composite": "Risk On",
         "Action": "Reduce Hedges"},
    ])
    st.dataframe(signals_df, use_container_width=True, hide_index=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Transition Signal Map**")
        trans_df = pd.DataFrame([
            {"From": "Low", "To": "High", "Type": "Spike", "Signal": "Risk Off", "Strength": 0.7},
            {"From": "Normal", "To": "Extreme", "Type": "Spike", "Signal": "Risk Off", "Strength": 0.9},
            {"From": "Extreme", "To": "Normal", "Type": "Normalization", "Signal": "Risk On", "Strength": 0.6},
            {"From": "High", "To": "Normal", "Type": "De-escalation", "Signal": "Risk On", "Strength": 0.4},
        ])
        st.dataframe(trans_df, use_container_width=True, hide_index=True)
    with col2:
        st.markdown("**Mean Reversion Half-Life**")
        st.markdown("- **AAPL**: 18 days")
        st.markdown("- **NVDA**: 12 days")
        st.markdown("- **TSLA**: 8 days (fast mean-reverting)")
        st.markdown("- **MSFT**: 25 days")
        st.markdown("")
        st.markdown("*Shorter half-life = faster mean reversion = "
                     "more actionable signals.*")
