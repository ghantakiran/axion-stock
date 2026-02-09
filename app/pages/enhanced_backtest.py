"""Enhanced Backtesting Dashboard (PRD-167).

4 tabs: Monte Carlo, Market Impact, Survivorship Filter, Gap Risk.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import streamlit as st
from app.styles import inject_global_styles

try:
    st.set_page_config(page_title="Enhanced Backtesting", page_icon="🔬", layout="wide")
except Exception:
    pass

inject_global_styles()
st.title("🔬 Enhanced Backtesting")
st.caption("Production-grade backtesting with survivorship bias, market impact, Monte Carlo, and gap risk")

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# ═══════════════════════════════════════════════════════════════════════
# Demo Data
# ═══════════════════════════════════════════════════════════════════════

np.random.seed(167)

# Monte Carlo simulation data
n_paths = 1000
n_days = 252
initial_equity = 100_000
daily_returns = np.random.normal(0.0004, 0.015, (n_paths, n_days))
equity_paths = initial_equity * np.cumprod(1 + daily_returns, axis=1)
final_equities = equity_paths[:, -1]

# Percentile paths for fan chart
percentiles = [5, 25, 50, 75, 95]
percentile_paths = {}
for p in percentiles:
    percentile_paths[f"P{p}"] = np.percentile(equity_paths, p, axis=0)

# Drawdown calculations per path
max_drawdowns = []
for i in range(n_paths):
    peak = np.maximum.accumulate(equity_paths[i])
    dd = (equity_paths[i] - peak) / peak
    max_drawdowns.append(float(np.min(dd)))
max_drawdowns = np.array(max_drawdowns)

# Survivorship filter data
surv_tickers = [
    "AAPL", "MSFT", "NVDA", "TSLA", "META", "GOOGL", "AMZN", "AMD",
    "INTC", "GE", "ENRN", "LMND", "BBBY", "WISH", "PLTR",
]
surv_statuses = [
    "Active", "Active", "Active", "Active", "Active", "Active", "Active", "Active",
    "Active", "Active", "Delisted", "Active", "Delisted", "Active", "Active",
]
surv_listed_dates = [
    "1980-12-12", "1986-03-13", "1999-01-22", "2010-06-29", "2012-05-18",
    "2004-08-19", "1997-05-15", "1969-09-01", "1971-10-13", "1892-04-15",
    "1987-08-17", "2020-01-08", "2002-06-01", "2020-12-16", "2020-09-30",
]
surv_prices = np.random.uniform(5, 600, len(surv_tickers))
surv_volumes = np.random.randint(100_000, 50_000_000, len(surv_tickers))
passes_filter = [
    s == "Active" and p > 10 and v > 500_000
    for s, p, v in zip(surv_statuses, surv_prices, surv_volumes)
]

# Gap risk data
gap_tickers_pool = ["AAPL", "MSFT", "NVDA", "TSLA", "META", "GOOGL", "AMZN", "AMD", "JPM", "V"]
n_gaps = 30
gap_tickers = np.random.choice(gap_tickers_pool, n_gaps)
gap_pcts = np.random.normal(0, 3.5, n_gaps)
gap_types = np.where(np.abs(gap_pcts) > 5, "Extreme", np.where(np.abs(gap_pcts) > 2, "Large", "Normal"))
prev_closes = np.random.uniform(100, 500, n_gaps)
gap_opens = prev_closes * (1 + gap_pcts / 100)
stop_fills = np.where(
    gap_pcts < -2,
    gap_opens * (1 - np.random.uniform(0, 0.005, n_gaps)),
    gap_opens,
)
stop_slippage = np.where(
    gap_pcts < -2,
    np.abs((stop_fills - (prev_closes * 0.98)) / (prev_closes * 0.98) * 100),
    np.zeros(n_gaps),
)

# ═══════════════════════════════════════════════════════════════════════
# Dashboard Tabs
# ═══════════════════════════════════════════════════════════════════════

tab1, tab2, tab3, tab4 = st.tabs([
    "Monte Carlo",
    "Market Impact",
    "Survivorship Filter",
    "Gap Risk",
])


# ── Tab 1: Monte Carlo ────────────────────────────────────────────────

with tab1:
    st.subheader("Monte Carlo Simulation Results")

    prob_profit = float(np.mean(final_equities > initial_equity))
    prob_ruin = float(np.mean(final_equities < initial_equity * 0.5))
    median_final = float(np.median(final_equities))
    worst_dd = float(np.min(max_drawdowns))

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Probability of Profit", f"{prob_profit:.1%}")
    m2.metric("Probability of Ruin (<50%)", f"{prob_ruin:.1%}")
    m3.metric("Median Final Equity", f"${median_final:,.0f}")
    m4.metric("Worst-Case Drawdown", f"{worst_dd:.1%}")

    st.divider()
    st.subheader("Final Equity Distribution")
    hist_df = pd.DataFrame({"Final Equity ($)": final_equities})
    st.bar_chart(
        hist_df["Final Equity ($)"].value_counts(bins=50).sort_index()
    )

    st.divider()
    st.subheader("Confidence Interval Fan Chart")

    fan_df = pd.DataFrame(percentile_paths)
    st.line_chart(fan_df)

    st.divider()
    st.subheader("Summary Statistics")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Mean Final Equity", f"${np.mean(final_equities):,.0f}")
        st.metric("5th Percentile", f"${np.percentile(final_equities, 5):,.0f}")
        st.metric("25th Percentile", f"${np.percentile(final_equities, 25):,.0f}")
    with col2:
        st.metric("Std Dev", f"${np.std(final_equities):,.0f}")
        st.metric("75th Percentile", f"${np.percentile(final_equities, 75):,.0f}")
        st.metric("95th Percentile", f"${np.percentile(final_equities, 95):,.0f}")


# ── Tab 2: Market Impact ──────────────────────────────────────────────

with tab2:
    st.subheader("Convex Market Impact Model")

    col1, col2, col3 = st.columns(3)
    with col1:
        order_size = st.slider("Order Size (shares)", 100, 50_000, 5_000, step=100, key="impact_size")
    with col2:
        daily_volume = st.slider("Daily Volume (shares)", 100_000, 10_000_000, 1_000_000, step=100_000, key="impact_vol")
    with col3:
        volatility = st.slider("Volatility (%)", 1.0, 10.0, 3.0, step=0.5, key="impact_vola")

    participation = order_size / daily_volume
    sigma = volatility / 100
    ref_price = 150.0

    # Convex impact model: impact = sigma * sqrt(participation) * constant
    temporary_impact_bps = sigma * np.sqrt(participation) * 1000 * 5
    permanent_impact_bps = temporary_impact_bps * 0.3
    spread_bps = 2.0
    total_impact_bps = temporary_impact_bps + permanent_impact_bps + spread_bps

    effective_price = ref_price * (1 + total_impact_bps / 10000)
    slippage_dollars = (effective_price - ref_price) * order_size

    st.divider()

    impact_table = pd.DataFrame({
        "Component": ["Total Impact", "Temporary", "Permanent", "Spread"],
        "Impact (bps)": [
            f"{total_impact_bps:.1f}",
            f"{temporary_impact_bps:.1f}",
            f"{permanent_impact_bps:.1f}",
            f"{spread_bps:.1f}",
        ],
    })
    st.dataframe(impact_table, use_container_width=True)

    m1, m2, m3 = st.columns(3)
    m1.metric("Effective Price", f"${effective_price:.4f}")
    m2.metric("Reference Price", f"${ref_price:.2f}")
    m3.metric("Total Slippage", f"${slippage_dollars:,.2f}")

    st.divider()
    st.subheader("Impact vs Order Size (Convex Curve)")

    order_sizes = np.arange(100, 50_001, 500)
    participations = order_sizes / daily_volume
    impacts = sigma * np.sqrt(participations) * 1000 * 5 + sigma * np.sqrt(participations) * 1000 * 5 * 0.3 + 2.0
    impact_curve_df = pd.DataFrame({
        "Total Impact (bps)": impacts,
    }, index=order_sizes)
    st.line_chart(impact_curve_df)


# ── Tab 3: Survivorship Filter ────────────────────────────────────────

with tab3:
    st.subheader("Survivorship Bias Filter")

    active_count = sum(1 for s in surv_statuses if s == "Active")
    delisted_count = sum(1 for s in surv_statuses if s == "Delisted")
    filtered_out = sum(1 for p in passes_filter if not p)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Listings", len(surv_tickers))
    m2.metric("Active", active_count)
    m3.metric("Delisted", delisted_count)
    m4.metric("Filtered Out", filtered_out)

    st.divider()

    surv_df = pd.DataFrame({
        "Ticker": surv_tickers,
        "Listed Date": surv_listed_dates,
        "Status": surv_statuses,
        "Price": [f"${p:.2f}" for p in surv_prices],
        "Volume": [f"{v:,}" for v in surv_volumes],
        "Passes Filter": passes_filter,
    })
    st.dataframe(surv_df, use_container_width=True)

    st.divider()
    st.subheader("Filter Criteria")
    with st.expander("Active filter rules"):
        st.markdown("""
        - **Status**: Must be Active (not Delisted)
        - **Price**: Must be > $10 (penny stock filter)
        - **Volume**: Must be > 500,000 shares/day (liquidity filter)
        """)

    col1, col2 = st.columns(2)
    with col1:
        st.info(
            f"**{sum(passes_filter)}** tickers pass all filters and are included in the backtest universe"
        )
    with col2:
        st.warning(
            f"**{filtered_out}** tickers filtered out to avoid survivorship bias"
        )


# ── Tab 4: Gap Risk ──────────────────────────────────────────────────

with tab4:
    st.subheader("Gap Risk Simulation")

    avg_gap = float(np.mean(np.abs(gap_pcts)))
    max_adverse = float(np.min(gap_pcts))
    adverse_gaps = gap_pcts[gap_pcts < -2]
    avg_stop_slip = float(np.mean(stop_slippage[stop_slippage > 0])) if np.any(stop_slippage > 0) else 0.0

    m1, m2, m3 = st.columns(3)
    m1.metric("Avg Gap %", f"{avg_gap:.2f}%")
    m2.metric("Max Adverse Gap", f"{max_adverse:.2f}%")
    m3.metric("Stop Slippage Impact", f"{avg_stop_slip:.2f}%")

    st.divider()
    st.subheader("Gap Events")

    gap_df = pd.DataFrame({
        "Ticker": gap_tickers,
        "Gap %": [f"{g:+.2f}%" for g in gap_pcts],
        "Gap Type": gap_types,
        "Prev Close": [f"${p:.2f}" for p in prev_closes],
        "Gap Open": [f"${o:.2f}" for o in gap_opens],
        "Stop Fill": [f"${f:.2f}" for f in stop_fills],
        "Slippage %": [f"{s:.2f}%" for s in stop_slippage],
    })
    st.dataframe(gap_df, use_container_width=True)

    st.divider()
    st.subheader("Gap Magnitude Distribution")
    gap_hist_df = pd.DataFrame({"Gap %": gap_pcts})
    st.bar_chart(gap_hist_df["Gap %"].value_counts(bins=20).sort_index())

    st.divider()
    st.subheader("Gap Type Breakdown")
    normal_count = sum(1 for g in gap_types if g == "Normal")
    large_count = sum(1 for g in gap_types if g == "Large")
    extreme_count = sum(1 for g in gap_types if g == "Extreme")

    col1, col2, col3 = st.columns(3)
    col1.metric("Normal Gaps", normal_count)
    col2.metric("Large Gaps (>2%)", large_count)
    col3.metric("Extreme Gaps (>5%)", extreme_count)
