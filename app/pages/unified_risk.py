"""Unified Risk Center Dashboard (PRD-163).

4 tabs: Risk Assessment, Correlation Guard, VaR Sizing, Regime Limits.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import streamlit as st
from app.styles import inject_global_styles

try:
    st.set_page_config(page_title="Unified Risk Center", page_icon="🛡️", layout="wide")
except Exception:
    pass

inject_global_styles()
st.title("🛡️ Unified Risk Center")
st.caption("Consolidated risk assessment with correlation, VaR, and regime-adaptive limits")

import numpy as np
import pandas as pd

# ═══════════════════════════════════════════════════════════════════════
# Demo Data
# ═══════════════════════════════════════════════════════════════════════

np.random.seed(163)
TICKERS = ["AAPL", "MSFT", "NVDA", "TSLA", "META", "GOOGL", "AMZN", "AMD"]
REGIMES = ["low_vol", "normal", "high_vol", "crisis"]
CURRENT_REGIME = "normal"

# Positions
positions = pd.DataFrame({
    "Ticker": TICKERS,
    "Side": ["long"] * 6 + ["short"] * 2,
    "Market Value ($)": [18500, 15200, 22100, 9800, 13400, 11600, 7200, 8900],
    "Weight (%)": [14.6, 12.0, 17.4, 7.7, 10.6, 9.2, 5.7, 7.0],
    "Unrealized P&L ($)": [1250, -340, 3820, -1100, 890, 560, 420, -180],
    "Sector": ["Tech", "Tech", "Tech", "Auto", "Tech", "Tech", "Consumer", "Tech"],
})

# Correlation matrix
corr_values = np.array([
    [1.00, 0.82, 0.76, 0.45, 0.71, 0.79, 0.55, 0.73],
    [0.82, 1.00, 0.69, 0.38, 0.74, 0.81, 0.60, 0.66],
    [0.76, 0.69, 1.00, 0.51, 0.63, 0.65, 0.42, 0.85],
    [0.45, 0.38, 0.51, 1.00, 0.41, 0.36, 0.29, 0.48],
    [0.71, 0.74, 0.63, 0.41, 1.00, 0.72, 0.58, 0.60],
    [0.79, 0.81, 0.65, 0.36, 0.72, 1.00, 0.62, 0.61],
    [0.55, 0.60, 0.42, 0.29, 0.58, 0.62, 1.00, 0.39],
    [0.73, 0.66, 0.85, 0.48, 0.60, 0.61, 0.39, 1.00],
])
corr_df = pd.DataFrame(corr_values, index=TICKERS, columns=TICKERS)

# ═══════════════════════════════════════════════════════════════════════
# Tabs
# ═══════════════════════════════════════════════════════════════════════

tab1, tab2, tab3, tab4 = st.tabs([
    "Risk Assessment",
    "Correlation Guard",
    "VaR Sizing",
    "Regime Limits",
])

# ── Tab 1: Risk Assessment ────────────────────────────────────────────

with tab1:
    st.subheader("Current Unified Risk Assessment")

    # Top-level metrics
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Daily P&L", "+$2,140", "+1.7%")
    m2.metric("Open Positions", "8")
    m3.metric("Current Regime", CURRENT_REGIME.replace("_", " ").title())
    m4.metric("Portfolio VaR (95%)", "-$3,420")

    st.divider()

    m5, m6, m7, m8 = st.columns(4)
    m5.metric("Gross Leverage", "1.24x")
    m6.metric("Net Exposure", "68.8%")
    m7.metric("Max Position", "17.4%", "NVDA")
    m8.metric("Sector Concentration", "85.5%", "Tech")

    st.divider()
    st.subheader("Position Summary")
    st.dataframe(positions, use_container_width=True)

    st.divider()
    st.subheader("Risk Warnings")
    st.warning("Tech sector concentration at 85.5% exceeds 60% limit -- consider diversification")
    st.warning("NVDA position weight 17.4% exceeds single-name limit of 15%")
    st.info("Regime: NORMAL -- standard risk multipliers active")


# ── Tab 2: Correlation Guard ──────────────────────────────────────────

with tab2:
    st.subheader("Position Correlation Matrix")

    # Display as styled dataframe (heatmap-style)
    st.dataframe(
        corr_df.style.background_gradient(cmap="RdYlGn_r", vmin=0, vmax=1)
        .format("{:.2f}"),
        use_container_width=True,
    )

    st.divider()
    st.subheader("Highly Correlated Pairs (r > 0.75)")
    pairs = []
    for i in range(len(TICKERS)):
        for j in range(i + 1, len(TICKERS)):
            if corr_values[i][j] > 0.75:
                pairs.append({
                    "Pair": f"{TICKERS[i]} / {TICKERS[j]}",
                    "Correlation": round(corr_values[i][j], 2),
                    "Combined Weight (%)": round(
                        positions.iloc[i]["Weight (%)"] + positions.iloc[j]["Weight (%)"], 1
                    ),
                    "Risk Level": "High" if corr_values[i][j] > 0.80 else "Elevated",
                })
    if pairs:
        pairs_df = pd.DataFrame(pairs).sort_values("Correlation", ascending=False)
        st.dataframe(pairs_df, use_container_width=True)
    else:
        st.info("No highly correlated pairs found.")

    st.divider()
    st.subheader("Correlation Clusters")
    st.markdown("""
    | Cluster | Tickers | Avg Intra-Correlation | Combined Weight |
    |---------|---------|----------------------|-----------------|
    | **Tech Core** | AAPL, MSFT, GOOGL | 0.81 | 35.8% |
    | **Semiconductor** | NVDA, AMD | 0.85 | 24.4% |
    | **Growth** | META, AMZN | 0.58 | 16.3% |
    | **Standalone** | TSLA | -- | 7.7% |
    """)

    m1, m2 = st.columns(2)
    m1.metric("Portfolio-Wide Avg Correlation", "0.60")
    m2.metric("Correlated Pairs (r > 0.75)", f"{len(pairs)}")


# ── Tab 3: VaR Sizing ────────────────────────────────────────────────

with tab3:
    st.subheader("Value at Risk & Position Sizing")

    confidence = st.selectbox(
        "Confidence Level", ["90%", "95%", "99%"], index=1, key="var_conf"
    )
    holding_period = st.selectbox(
        "Holding Period", ["1 day", "5 days", "10 days"], index=0, key="var_hold"
    )

    st.divider()

    # VaR metrics based on selection
    var_table = {
        "90%": {"1 day": 2180, "5 days": 4870, "10 days": 6890},
        "95%": {"1 day": 3420, "5 days": 7650, "10 days": 10810},
        "99%": {"1 day": 5810, "5 days": 12990, "10 days": 18370},
    }
    cvar_table = {
        "90%": {"1 day": 2950, "5 days": 6590, "10 days": 9320},
        "95%": {"1 day": 4610, "5 days": 10310, "10 days": 14570},
        "99%": {"1 day": 7840, "5 days": 17530, "10 days": 24780},
    }

    var_val = var_table[confidence][holding_period]
    cvar_val = cvar_table[confidence][holding_period]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric(f"VaR ({confidence})", f"-${var_val:,}")
    m2.metric(f"CVaR ({confidence})", f"-${cvar_val:,}")
    m3.metric("Portfolio Value", "$126,700")
    m4.metric("VaR as % of Portfolio", f"{var_val / 126700 * 100:.1f}%")

    st.divider()
    st.subheader("Max Position Size Recommendations")
    sizing_data = {
        "Ticker": TICKERS,
        "Current Weight (%)": [14.6, 12.0, 17.4, 7.7, 10.6, 9.2, 5.7, 7.0],
        "Volatility (ann.)": ["28.2%", "24.1%", "42.5%", "55.8%", "32.6%", "22.9%", "27.4%", "45.3%"],
        "Max Recommended (%)": [15.0, 15.0, 10.0, 7.5, 12.5, 15.0, 15.0, 9.0],
        "Action": [
            "OK", "OK", "REDUCE by 7.4%", "OK",
            "OK", "OK", "OK", "OK",
        ],
    }
    st.dataframe(pd.DataFrame(sizing_data), use_container_width=True)

    st.divider()
    st.subheader("VaR by Position")
    per_position_var = {
        "Ticker": TICKERS,
        "Marginal VaR ($)": [520, 430, 940, 540, 440, 380, 200, 410],
        "Component VaR ($)": [480, 410, 870, 380, 410, 360, 170, 390],
        "VaR Contribution (%)": [14.0, 12.0, 25.4, 11.1, 12.0, 10.5, 5.0, 11.4],
    }
    st.dataframe(pd.DataFrame(per_position_var), use_container_width=True)


# ── Tab 4: Regime Limits ──────────────────────────────────────────────

with tab4:
    st.subheader("Regime-Adaptive Risk Limits")

    # Current regime indicator
    regime_colors = {
        "low_vol": "🟢",
        "normal": "🟡",
        "high_vol": "🟠",
        "crisis": "🔴",
    }
    icon = regime_colors.get(CURRENT_REGIME, "⚪")
    st.markdown(f"### Current Regime: {icon} {CURRENT_REGIME.replace('_', ' ').title()}")

    m1, m2, m3 = st.columns(3)
    m1.metric("VIX Level", "18.4")
    m2.metric("Market Breadth", "62%")
    m3.metric("Regime Confidence", "84%")

    st.divider()
    st.subheader("Regime Profile Table")

    regime_profiles = pd.DataFrame({
        "Regime": ["Low Vol", "Normal", "High Vol", "Crisis"],
        "Max Positions": [15, 10, 7, 3],
        "Max Single Position (%)": [20.0, 15.0, 10.0, 5.0],
        "Max Sector Conc. (%)": [80.0, 60.0, 40.0, 25.0],
        "Max Leverage": ["2.0x", "1.5x", "1.0x", "0.5x"],
        "Size Multiplier": [1.2, 1.0, 0.7, 0.3],
        "Stop Loss Tightening": ["0%", "0%", "+25%", "+50%"],
        "VIX Range": ["< 15", "15 - 25", "25 - 35", "> 35"],
    })
    st.dataframe(regime_profiles, use_container_width=True)

    st.divider()
    st.subheader("Current Limit Compliance")

    # Look up current regime row
    current_profile = regime_profiles[regime_profiles["Regime"] == "Normal"].iloc[0]

    compliance_data = {
        "Limit": [
            "Max Positions", "Max Single Position", "Max Sector Concentration",
            "Max Leverage", "Daily Loss Limit",
        ],
        "Regime Limit": [
            str(current_profile["Max Positions"]),
            f"{current_profile['Max Single Position (%)']}%",
            f"{current_profile['Max Sector Conc. (%)']}%",
            current_profile["Max Leverage"],
            "$5,000",
        ],
        "Current Value": ["8", "17.4%", "85.5%", "1.24x", "$0 (no loss)"],
        "Status": ["PASS", "FAIL", "FAIL", "PASS", "PASS"],
    }
    compliance_df = pd.DataFrame(compliance_data)
    st.dataframe(compliance_df, use_container_width=True)

    fail_count = compliance_df[compliance_df["Status"] == "FAIL"].shape[0]
    if fail_count > 0:
        st.error(f"{fail_count} limit(s) breached under current regime -- review positions")
    else:
        st.success("All limits within compliance under current regime.")

    st.divider()
    st.subheader("Regime Transition History")
    transitions = pd.DataFrame({
        "Date": ["2025-03-15", "2025-03-28", "2025-04-02", "2025-04-08"],
        "From": ["low_vol", "normal", "high_vol", "normal"],
        "To": ["normal", "high_vol", "normal", "normal"],
        "VIX at Transition": [15.2, 26.1, 24.3, 18.4],
        "Action Taken": [
            "Reduced max leverage to 1.5x",
            "Reduced positions to 7, tightened stops",
            "Relaxed back to normal limits",
            "No change (same regime)",
        ],
    })
    st.dataframe(transitions, use_container_width=True)
