"""Multi-Asset Dashboard."""

import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="Multi-Asset", layout="wide")
st.title("Multi-Asset Portfolio")

# --- Sidebar ---
st.sidebar.header("Asset Classes")
enable_crypto = st.sidebar.checkbox("Crypto", value=True)
enable_futures = st.sidebar.checkbox("Futures", value=True)
enable_intl = st.sidebar.checkbox("International", value=True)
template = st.sidebar.selectbox(
    "Template",
    ["Custom", "Conservative", "Balanced", "Growth", "Aggressive", "Ray Dalio"],
)

# --- Main Content ---
tab1, tab2, tab3, tab4 = st.tabs([
    "Allocation", "Crypto", "Futures", "Risk",
])

# --- Tab 1: Cross-Asset Allocation ---
with tab1:
    st.subheader("Cross-Asset Allocation")

    if template != "Custom":
        from src.multi_asset.config import CROSS_ASSET_TEMPLATES
        tpl = CROSS_ASSET_TEMPLATES.get(template.lower().replace(" ", "_"), {})
        if tpl:
            alloc_df = pd.DataFrame([
                {"Asset Class": ac.value.replace("_", " ").title(), "Weight": f"{w:.0%}"}
                for ac, w in tpl.items() if w > 0
            ])
            st.dataframe(alloc_df, use_container_width=True, hide_index=True)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Value", "$362,600")
    col2.metric("YTD Return", "+9.1%")
    col3.metric("Sharpe", "1.42")
    col4.metric("Max Drawdown", "-6.8%")

    st.markdown("#### Position Summary (Demo)")
    positions_data = pd.DataFrame([
        {"Symbol": "AAPL", "Class": "US Equity", "Weight": "12.3%", "P&L": "+$2,400"},
        {"Symbol": "BTC", "Class": "Crypto", "Weight": "8.5%", "P&L": "+$5,200"},
        {"Symbol": "ESH25", "Class": "Futures", "Weight": "15.0%", "P&L": "+$1,800"},
        {"Symbol": "VOD.L", "Class": "Intl Equity", "Weight": "4.2%", "P&L": "-$320"},
        {"Symbol": "TLT", "Class": "Fixed Income", "Weight": "20.0%", "P&L": "+$900"},
        {"Symbol": "GLD", "Class": "Commodity", "Weight": "7.5%", "P&L": "+$1,100"},
    ])
    st.dataframe(positions_data, use_container_width=True, hide_index=True)

# --- Tab 2: Crypto ---
with tab2:
    st.subheader("Crypto Factor Scores")

    if enable_crypto:
        crypto_data = pd.DataFrame([
            {"Symbol": "BTC", "Price": "$45,000", "Value": "0.72", "Momentum": "0.85",
             "Quality": "0.68", "Network": "0.91", "Composite": "0.79"},
            {"Symbol": "ETH", "Price": "$3,200", "Value": "0.65", "Momentum": "0.78",
             "Quality": "0.82", "Network": "0.75", "Composite": "0.75"},
            {"Symbol": "SOL", "Price": "$120", "Value": "0.45", "Momentum": "0.92",
             "Quality": "0.61", "Network": "0.58", "Composite": "0.65"},
        ])
        st.dataframe(crypto_data, use_container_width=True, hide_index=True)

        st.markdown("#### On-Chain Metrics")
        onchain_data = pd.DataFrame([
            {"Metric": "NVT Ratio", "BTC": "28.5", "ETH": "18.2"},
            {"Metric": "MVRV", "BTC": "1.52", "ETH": "1.28"},
            {"Metric": "Active Addresses (24h)", "BTC": "820K", "ETH": "520K"},
            {"Metric": "TVL", "BTC": "N/A", "ETH": "$52B"},
        ])
        st.dataframe(onchain_data, use_container_width=True, hide_index=True)
    else:
        st.info("Enable crypto in the sidebar to view crypto data.")

# --- Tab 3: Futures ---
with tab3:
    st.subheader("Futures Positions")

    if enable_futures:
        col1, col2, col3 = st.columns(3)
        col1.metric("Margin Used", "$38,200")
        col2.metric("Margin Available", "$61,800")
        col3.metric("Utilization", "38.2%")

        futures_data = pd.DataFrame([
            {"Contract": "ESH25", "Name": "E-mini S&P 500", "Qty": "2",
             "Entry": "5,050", "Current": "5,120", "P&L": "+$7,000",
             "Margin": "$25,300"},
            {"Contract": "GCM25", "Name": "Gold", "Qty": "1",
             "Entry": "2,050", "Current": "2,080", "P&L": "+$3,000",
             "Margin": "$10,000"},
        ])
        st.dataframe(futures_data, use_container_width=True, hide_index=True)

        st.markdown("#### Contract Specs")
        from src.multi_asset.config import DEFAULT_CONTRACT_SPECS
        specs_data = pd.DataFrame([
            {"Root": s.symbol, "Name": s.name, "Multiplier": f"${s.multiplier:,.0f}",
             "Tick": f"${s.tick_value:.2f}", "Margin": f"${s.margin_initial:,.0f}"}
            for s in list(DEFAULT_CONTRACT_SPECS.values())[:8]
        ])
        st.dataframe(specs_data, use_container_width=True, hide_index=True)
    else:
        st.info("Enable futures in the sidebar to view futures data.")

# --- Tab 4: Risk ---
with tab4:
    st.subheader("Unified Risk Dashboard")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Portfolio VaR (95%)", "-1.8%")
    col2.metric("Portfolio VaR (99%)", "-2.6%")
    col3.metric("Leverage", "1.15x")
    col4.metric("Correlation Regime", "Normal")

    st.markdown("#### Risk Contribution by Asset Class")
    risk_data = pd.DataFrame([
        {"Asset Class": "US Equity", "Weight": "40%", "Risk Contribution": "52%"},
        {"Asset Class": "Crypto", "Weight": "10%", "Risk Contribution": "22%"},
        {"Asset Class": "Futures", "Weight": "15%", "Risk Contribution": "12%"},
        {"Asset Class": "Fixed Income", "Weight": "25%", "Risk Contribution": "8%"},
        {"Asset Class": "Commodity", "Weight": "10%", "Risk Contribution": "6%"},
    ])
    st.dataframe(risk_data, use_container_width=True, hide_index=True)

    st.markdown("#### Currency Exposure")
    fx_data = pd.DataFrame([
        {"Currency": "USD", "Exposure": "82%", "Hedge": "N/A"},
        {"Currency": "GBP", "Exposure": "8%", "Hedge": "None"},
        {"Currency": "EUR", "Exposure": "6%", "Hedge": "None"},
        {"Currency": "JPY", "Exposure": "4%", "Hedge": "Recommended"},
    ])
    st.dataframe(fx_data, use_container_width=True, hide_index=True)
