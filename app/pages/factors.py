"""Factor Engine Dashboard.

4 tabs: Factor Overview, Factor Builder, Performance Analysis, Factor Registry.
Displays factor categories (Value, Momentum, Quality, Growth, Volatility, Technical),
individual factor scores, and composite rankings.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import streamlit as st
from app.styles import inject_global_styles

try:
    st.set_page_config(page_title="Factor Engine", page_icon="", layout="wide")
except Exception:
    pass

inject_global_styles()
st.title("Factor Engine")
st.caption("Multi-factor model with 12+ factors across 6 categories and regime awareness")

import numpy as np
import pandas as pd

# ---- Try importing real module ----
_module_available = False
try:
    from src.factors import (
        Factor,
        FactorCategory,
        FactorRegistry,
        ValueFactors,
        MomentumFactors,
        QualityFactors,
        GrowthFactors,
        VolatilityFactors,
        TechnicalFactors,
    )
    from src.factors.registry import create_default_registry
    _module_available = True
except ImportError:
    st.warning("Factor engine module (src.factors) is not available. Showing demo data.")

# =====================================================================
# Demo Data
# =====================================================================

np.random.seed(42)

TICKERS = ["AAPL", "MSFT", "NVDA", "TSLA", "META", "GOOGL", "AMZN", "AMD", "JPM", "V"]

CATEGORIES = {
    "value": {
        "description": "Identify undervalued stocks relative to fundamentals",
        "weight": 0.20,
        "factors": [
            ("earnings_yield", "EBIT / Enterprise Value"),
            ("fcf_yield", "Free Cash Flow / Market Cap"),
            ("book_to_market", "Book Value / Market Cap"),
            ("ev_ebitda", "Enterprise Value / EBITDA (inverted)"),
            ("dividend_yield", "Annual Dividend / Price"),
            ("earnings_pe", "Trailing P/E (inverted)"),
        ],
    },
    "momentum": {
        "description": "Capture price momentum and trend strength",
        "weight": 0.20,
        "factors": [
            ("mom_12_1", "12-month minus 1-month momentum"),
            ("mom_6_1", "6-month minus 1-month momentum"),
            ("mom_3m", "3-month momentum"),
            ("high_52w", "52-week high proximity"),
            ("earnings_momentum", "Earnings surprise momentum"),
        ],
    },
    "quality": {
        "description": "Select high-quality, profitable companies",
        "weight": 0.20,
        "factors": [
            ("roe", "Return on Equity"),
            ("roa", "Return on Assets"),
            ("roic", "Return on Invested Capital"),
            ("gross_profit_assets", "Gross Profit / Total Assets"),
            ("accruals", "Accruals ratio"),
            ("debt_equity", "Debt / Equity (inverted)"),
        ],
    },
    "growth": {
        "description": "Identify high-growth companies",
        "weight": 0.15,
        "factors": [
            ("revenue_growth", "Year-over-year revenue growth"),
            ("eps_growth", "EPS growth rate"),
            ("fcf_growth", "Free cash flow growth"),
            ("growth_acceleration", "Growth rate acceleration"),
        ],
    },
    "volatility": {
        "description": "Low-volatility and risk-adjusted factors",
        "weight": 0.10,
        "factors": [
            ("realized_vol", "Realized volatility (inverted)"),
            ("idio_vol", "Idiosyncratic volatility"),
            ("beta", "Market beta"),
            ("downside_beta", "Downside beta"),
            ("max_drawdown", "Maximum drawdown"),
        ],
    },
    "technical": {
        "description": "Price-based technical indicators",
        "weight": 0.15,
        "factors": [
            ("rsi", "Relative Strength Index"),
            ("macd", "MACD signal"),
            ("volume_trend", "Volume trend ratio"),
            ("price_vs_sma", "Price vs 50-day SMA"),
        ],
    },
}

# Generate demo factor scores (percentile rank 0-1 for each ticker)
demo_scores = {}
for cat_name, cat_info in CATEGORIES.items():
    factor_names = [f[0] for f in cat_info["factors"]]
    demo_scores[cat_name] = pd.DataFrame(
        np.random.uniform(0.1, 0.95, size=(len(TICKERS), len(factor_names))),
        index=TICKERS,
        columns=factor_names,
    ).round(3)

# Composite scores per category
composite_scores = pd.DataFrame(index=TICKERS)
for cat_name, scores_df in demo_scores.items():
    composite_scores[cat_name] = scores_df.mean(axis=1).round(3)

# Overall composite
weights = {cat: info["weight"] for cat, info in CATEGORIES.items()}
total_w = sum(weights.values())
composite_scores["overall"] = sum(
    composite_scores[cat] * (w / total_w) for cat, w in weights.items()
).round(3)
composite_scores = composite_scores.sort_values("overall", ascending=False)

# =====================================================================
# Tabs
# =====================================================================

tab1, tab2, tab3, tab4 = st.tabs([
    "Factor Overview",
    "Factor Builder",
    "Performance Analysis",
    "Factor Registry",
])

# -- Tab 1: Factor Overview -------------------------------------------------

with tab1:
    st.subheader("Factor Overview")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Factor Categories", len(CATEGORIES))
    m2.metric("Total Factors", sum(len(c["factors"]) for c in CATEGORIES.values()))
    m3.metric("Universe Size", len(TICKERS))
    m4.metric("Top Ranked", composite_scores.index[0])

    st.divider()

    # Category-level composite scores
    st.subheader("Composite Factor Scores by Ticker")
    display_df = composite_scores.copy()
    display_df.columns = [c.replace("_", " ").title() for c in display_df.columns]
    st.dataframe(
        display_df.style.background_gradient(cmap="RdYlGn", vmin=0, vmax=1).format("{:.3f}"),
        use_container_width=True,
    )

    st.divider()

    st.subheader("Category Weights")
    weights_df = pd.DataFrame({
        "Category": [c.replace("_", " ").title() for c in CATEGORIES.keys()],
        "Weight (%)": [info["weight"] * 100 for info in CATEGORIES.values()],
        "Description": [info["description"] for info in CATEGORIES.values()],
        "Factor Count": [len(info["factors"]) for info in CATEGORIES.values()],
    })
    st.dataframe(weights_df, use_container_width=True)

    st.divider()

    st.subheader("Overall Composite Ranking")
    ranking_chart = composite_scores["overall"].sort_values(ascending=True)
    st.bar_chart(ranking_chart)


# -- Tab 2: Factor Builder --------------------------------------------------

with tab2:
    st.subheader("Factor Builder")
    st.markdown("Explore individual factor scores and build custom composites.")

    col1, col2 = st.columns(2)
    with col1:
        selected_category = st.selectbox(
            "Select Category",
            list(CATEGORIES.keys()),
            format_func=lambda x: x.replace("_", " ").title(),
            key="fb_category",
        )
    with col2:
        selected_ticker = st.selectbox(
            "Select Ticker", TICKERS, key="fb_ticker",
        )

    st.divider()

    cat_info = CATEGORIES[selected_category]
    cat_scores = demo_scores[selected_category]

    st.subheader(f"{selected_category.replace('_', ' ').title()} Factors")
    st.caption(cat_info["description"])

    # Show all factor scores for selected category
    st.dataframe(
        cat_scores.style.background_gradient(cmap="RdYlGn", vmin=0, vmax=1).format("{:.3f}"),
        use_container_width=True,
    )

    st.divider()

    # Detail for selected ticker
    st.subheader(f"{selected_ticker} - {selected_category.replace('_', ' ').title()} Breakdown")
    ticker_scores = cat_scores.loc[selected_ticker]
    factor_detail = pd.DataFrame({
        "Factor": [f[0].replace("_", " ").title() for f in cat_info["factors"]],
        "Description": [f[1] for f in cat_info["factors"]],
        "Score": ticker_scores.values.round(3),
        "Percentile": [f"{s:.0%}" for s in ticker_scores.values],
    })
    st.dataframe(factor_detail, use_container_width=True)

    st.divider()

    # Custom weight builder
    st.subheader("Custom Weight Adjustment")
    st.markdown("Adjust category weights to build a custom composite.")

    custom_weights = {}
    cols = st.columns(len(CATEGORIES))
    for i, (cat_name, cat_data) in enumerate(CATEGORIES.items()):
        with cols[i]:
            custom_weights[cat_name] = st.slider(
                cat_name.replace("_", " ").title(),
                0.0, 1.0,
                cat_data["weight"],
                0.05,
                key=f"cw_{cat_name}",
            )

    if st.button("Recalculate Composite", type="primary", use_container_width=True):
        total_cw = sum(custom_weights.values())
        if total_cw > 0:
            custom_composite = sum(
                composite_scores[cat] * (w / total_cw)
                for cat, w in custom_weights.items()
            ).round(3)
            custom_result = pd.DataFrame({
                "Ticker": TICKERS,
                "Custom Composite": custom_composite.values,
            }).sort_values("Custom Composite", ascending=False)
            st.dataframe(custom_result, use_container_width=True)
        else:
            st.error("Total weight must be greater than 0.")


# -- Tab 3: Performance Analysis -------------------------------------------

with tab3:
    st.subheader("Factor Performance Analysis")

    # Simulated factor return data
    periods = ["1M", "3M", "6M", "1Y", "3Y"]
    perf_data = {
        "Category": [c.replace("_", " ").title() for c in CATEGORIES.keys()],
        "1M (%)": np.round(np.random.uniform(-2, 4, len(CATEGORIES)), 2),
        "3M (%)": np.round(np.random.uniform(-3, 8, len(CATEGORIES)), 2),
        "6M (%)": np.round(np.random.uniform(-5, 15, len(CATEGORIES)), 2),
        "1Y (%)": np.round(np.random.uniform(-8, 25, len(CATEGORIES)), 2),
        "3Y Ann. (%)": np.round(np.random.uniform(2, 18, len(CATEGORIES)), 2),
        "Sharpe": np.round(np.random.uniform(0.3, 1.8, len(CATEGORIES)), 2),
        "Max DD (%)": np.round(np.random.uniform(-25, -5, len(CATEGORIES)), 1),
    }
    perf_df = pd.DataFrame(perf_data)

    m1, m2, m3, m4 = st.columns(4)
    best_1y = perf_df.loc[perf_df["1Y (%)"].idxmax()]
    m1.metric("Best 1Y Factor", best_1y["Category"], f"{best_1y['1Y (%)']:+.1f}%")
    best_sharpe = perf_df.loc[perf_df["Sharpe"].idxmax()]
    m2.metric("Best Sharpe", best_sharpe["Category"], f"{best_sharpe['Sharpe']:.2f}")
    m3.metric("Avg Sharpe", f"{perf_df['Sharpe'].mean():.2f}")
    m4.metric("Avg Max DD", f"{perf_df['Max DD (%)'].mean():.1f}%")

    st.divider()

    st.dataframe(perf_df, use_container_width=True)

    st.divider()

    st.subheader("Factor Correlation Matrix")
    factor_corr = np.array([
        [1.00, -0.35, 0.42, -0.18, 0.15, 0.08],
        [-0.35, 1.00, 0.10, 0.55, -0.22, 0.68],
        [0.42, 0.10, 1.00, 0.25, 0.30, -0.05],
        [-0.18, 0.55, 0.25, 1.00, -0.10, 0.40],
        [0.15, -0.22, 0.30, -0.10, 1.00, -0.15],
        [0.08, 0.68, -0.05, 0.40, -0.15, 1.00],
    ])
    cat_labels = [c.replace("_", " ").title() for c in CATEGORIES.keys()]
    corr_df = pd.DataFrame(factor_corr, index=cat_labels, columns=cat_labels)
    st.dataframe(
        corr_df.style.background_gradient(cmap="RdYlGn_r", vmin=-1, vmax=1).format("{:.2f}"),
        use_container_width=True,
    )

    st.divider()

    st.subheader("Quintile Spread Returns")
    st.markdown("Long Q1 (top quintile) minus Short Q5 (bottom quintile) annualized returns.")
    quintile_data = pd.DataFrame({
        "Category": cat_labels,
        "Q1 Return (%)": np.round(np.random.uniform(8, 22, len(CATEGORIES)), 1),
        "Q5 Return (%)": np.round(np.random.uniform(-5, 5, len(CATEGORIES)), 1),
    })
    quintile_data["Spread (%)"] = (quintile_data["Q1 Return (%)"] - quintile_data["Q5 Return (%)"]).round(1)
    st.dataframe(quintile_data, use_container_width=True)

    spread_chart = quintile_data.set_index("Category")["Spread (%)"].sort_values(ascending=True)
    st.bar_chart(spread_chart)


# -- Tab 4: Factor Registry ------------------------------------------------

with tab4:
    st.subheader("Factor Registry")
    st.markdown("Complete catalog of all registered factors.")

    if _module_available:
        try:
            registry = create_default_registry()
            st.success(f"Registry loaded: {registry.total_factor_count()} factors across {len(registry.categories)} categories")
            all_factors = registry.list_factors()
        except Exception as e:
            st.warning(f"Could not initialize registry: {e}. Showing demo data.")
            all_factors = None
    else:
        all_factors = None

    m1, m2, m3 = st.columns(3)
    m1.metric("Categories", len(CATEGORIES))
    m2.metric("Total Factors", sum(len(c["factors"]) for c in CATEGORIES.values()))
    m3.metric("Regime Aware", "Yes")

    st.divider()

    # Full factor catalog
    catalog_rows = []
    for cat_name, cat_info in CATEGORIES.items():
        for fname, fdesc in cat_info["factors"]:
            catalog_rows.append({
                "Category": cat_name.replace("_", " ").title(),
                "Factor": fname.replace("_", " ").title(),
                "Description": fdesc,
                "Weight": cat_info["weight"],
            })

    catalog_df = pd.DataFrame(catalog_rows)

    filter_cat = st.selectbox(
        "Filter by Category",
        ["All"] + list(CATEGORIES.keys()),
        format_func=lambda x: x.replace("_", " ").title() if x != "All" else "All",
        key="reg_filter",
    )

    if filter_cat != "All":
        catalog_df = catalog_df[catalog_df["Category"] == filter_cat.replace("_", " ").title()]

    st.dataframe(catalog_df, use_container_width=True)

    st.divider()

    st.subheader("Factor Computation Pipeline")
    st.markdown("""
    | Step | Operation | Description |
    |------|-----------|-------------|
    | 1 | **Raw Extraction** | Extract raw factor values from price & fundamental data |
    | 2 | **Winsorization** | Clip extreme values at 1st/99th percentile |
    | 3 | **Percentile Ranking** | Convert to cross-sectional percentile ranks (0-1) |
    | 4 | **Category Composite** | Weighted average within each category |
    | 5 | **Overall Composite** | Weighted average across categories |
    | 6 | **Regime Adjustment** | Tilt weights based on current market regime |
    """)
