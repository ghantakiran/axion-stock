"""Portfolio Optimizer Dashboard."""

import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="Portfolio Optimizer", layout="wide")
st.title("Portfolio Optimizer")

# --- Sidebar ---
st.sidebar.header("Optimization Settings")

method = st.sidebar.selectbox(
    "Method",
    ["Max Sharpe", "Min Variance", "Risk Parity", "HRP", "Black-Litterman"],
)
template = st.sidebar.selectbox(
    "Template",
    ["Custom", "Aggressive Alpha", "Balanced Factor", "Quality Income",
     "Momentum Rider", "Value Contrarian", "Low Volatility", "Risk Parity", "All-Weather"],
)
portfolio_value = st.sidebar.number_input("Portfolio Value ($)", value=100_000, step=10_000)
max_weight = st.sidebar.slider("Max Position Size (%)", 3, 25, 10) / 100
max_positions = st.sidebar.slider("Max Positions", 5, 50, 20)
max_sector_pct = st.sidebar.slider("Max Sector (%)", 15, 50, 35) / 100

# --- Main Content ---
tab1, tab2, tab3, tab4 = st.tabs([
    "Optimize", "Portfolio X-Ray", "Tax Management", "What-If Analysis",
])

# --- Tab 1: Optimize ---
with tab1:
    st.subheader("Portfolio Construction")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Optimization Method:** " + method)
        st.markdown(f"**Template:** {template}")
        st.markdown(f"**Constraints:** max weight={max_weight:.0%}, "
                    f"max positions={max_positions}, max sector={max_sector_pct:.0%}")

    with col2:
        st.markdown("**Portfolio Value:** ${:,.0f}".format(portfolio_value))

    if st.button("Run Optimization", type="primary"):
        with st.spinner("Optimizing portfolio..."):
            try:
                from src.optimizer.objectives import (
                    MeanVarianceOptimizer,
                    RiskParityOptimizer,
                    HRPOptimizer,
                )

                # Generate synthetic data for demo
                n = max_positions
                symbols = [f"STOCK_{i:02d}" for i in range(n)]
                rng = np.random.RandomState(42)
                A = rng.randn(n, n) * 0.01
                cov_data = A @ A.T + np.eye(n) * 0.001
                cov_matrix = pd.DataFrame(cov_data, index=symbols, columns=symbols)
                expected_returns = pd.Series(rng.rand(n) * 0.15 + 0.03, index=symbols)

                if method == "Max Sharpe":
                    opt = MeanVarianceOptimizer()
                    result = opt.max_sharpe(expected_returns, cov_matrix,
                                           max_weight=max_weight)
                elif method == "Min Variance":
                    opt = MeanVarianceOptimizer()
                    result = opt.min_variance(cov_matrix, max_weight=max_weight)
                elif method == "Risk Parity":
                    opt = RiskParityOptimizer()
                    result = opt.optimize(cov_matrix, max_weight=max_weight)
                elif method == "HRP":
                    opt = HRPOptimizer()
                    returns_df = pd.DataFrame(
                        rng.randn(252, n) * 0.02, columns=symbols,
                    )
                    result = opt.optimize(returns_df)
                else:
                    from src.optimizer.black_litterman import BlackLittermanModel
                    bl = BlackLittermanModel()
                    mkt_w = pd.Series(1.0 / n, index=symbols)
                    bl_result = bl.compute_posterior(cov_matrix, mkt_w, views=[])
                    opt = MeanVarianceOptimizer()
                    result = opt.max_sharpe(bl_result.posterior_returns, cov_matrix,
                                           max_weight=max_weight)

                # Display results
                st.success(f"Optimization converged: {result.converged}")

                col_a, col_b, col_c, col_d = st.columns(4)
                col_a.metric("Expected Return", f"{result.expected_return:.1%}")
                col_b.metric("Volatility", f"{result.expected_volatility:.1%}")
                col_c.metric("Sharpe Ratio", f"{result.sharpe_ratio:.2f}")
                col_d.metric("Positions", str(sum(1 for w in result.weights.values() if w > 0.001)))

                # Weights table
                weights_df = pd.DataFrame([
                    {"Symbol": s, "Weight": f"{w:.2%}", "Value": f"${w * portfolio_value:,.0f}"}
                    for s, w in sorted(result.weights.items(), key=lambda x: -x[1])
                    if w > 0.001
                ])
                st.dataframe(weights_df, use_container_width=True, hide_index=True)

            except Exception as e:
                st.error(f"Optimization failed: {e}")

# --- Tab 2: Portfolio X-Ray ---
with tab2:
    st.subheader("Portfolio X-Ray")
    st.info("Load or optimize a portfolio to view the X-ray analysis.")

    # Demo X-ray
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Sector Allocation")
        demo_sectors = {
            "Technology": 0.283, "Healthcare": 0.181, "Financials": 0.142,
            "Consumer": 0.128, "Industrials": 0.114, "Energy": 0.071, "Other": 0.081,
        }
        sector_df = pd.DataFrame([
            {"Sector": s, "Weight": f"{w:.1%}"}
            for s, w in demo_sectors.items()
        ])
        st.dataframe(sector_df, use_container_width=True, hide_index=True)

    with col2:
        st.markdown("#### Risk Metrics")
        risk_data = {
            "Beta": "1.08", "Volatility": "14.2%", "Sharpe": "1.67",
            "Max Drawdown": "-6.2%", "VaR (95%)": "-1.8%",
        }
        for metric, value in risk_data.items():
            st.metric(metric, value)

    st.markdown("#### Concentration")
    conc_col1, conc_col2, conc_col3 = st.columns(3)
    conc_col1.metric("Top 5 Weight", "41.2%")
    conc_col2.metric("HHI", "612")
    conc_col3.metric("Effective N", "16.3")

# --- Tab 3: Tax Management ---
with tab3:
    st.subheader("Tax-Loss Harvesting")
    st.info("Connect portfolio positions to identify tax-loss harvesting opportunities.")

    st.markdown("#### Harvest Candidates (Demo)")
    harvest_data = pd.DataFrame([
        {"Symbol": "XOM", "Unrealized Loss": "-$4,000", "Tax Savings": "$1,480",
         "Replacement": "CVX", "Wash Sale Risk": "No"},
        {"Symbol": "AAPL", "Unrealized Loss": "-$3,000", "Tax Savings": "$1,110",
         "Replacement": "MSFT", "Wash Sale Risk": "No"},
    ])
    st.dataframe(harvest_data, use_container_width=True, hide_index=True)

    st.markdown("#### Tax-Aware Rebalance Preview")
    st.markdown("Trades are ordered to sell losers first, defer near-LT-threshold gains.")

# --- Tab 4: What-If ---
with tab4:
    st.subheader("What-If Analysis")
    st.markdown("Explore how changes to your portfolio affect risk and return.")

    col1, col2 = st.columns(2)
    with col1:
        add_symbol = st.text_input("Add/Increase", placeholder="e.g. NVDA")
        add_pct = st.slider("Change (%)", -10, 10, 5, key="add_pct")

    with col2:
        reduce_symbol = st.text_input("Reduce/Remove", placeholder="e.g. AAPL")
        reduce_pct = st.slider("Change (%)", -10, 10, -5, key="reduce_pct")

    if st.button("Analyze Impact"):
        st.markdown("#### Impact Analysis")
        impact_col1, impact_col2, impact_col3 = st.columns(3)
        impact_col1.metric("Risk Change", "+0.3%", delta="0.3%")
        impact_col2.metric("Return Change", "+0.5%", delta="0.5%")
        impact_col3.metric("Sharpe Change", "+0.02", delta="0.02")
