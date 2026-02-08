"""PRD-64: Liquidity Risk Analytics Dashboard."""

import streamlit as st
import pandas as pd
from datetime import datetime, timezone

from src.liquidity import (
    LiquidityTier,
    ImpactModel,
    OrderSide,
    SpreadComponent,
    TIER_THRESHOLDS,
    LiquidityScorer,
    SpreadAnalyzer,
    ImpactEstimator,
    SlippageTracker,
)

try:
    st.set_page_config(page_title="Liquidity Risk Analytics", layout="wide")
except st.errors.StreamlitAPIException:
    pass

st.title("Liquidity Risk Analytics")

# Initialize managers
if "liq_scorer" not in st.session_state:
    st.session_state.liq_scorer = LiquidityScorer()
if "spread_analyzer" not in st.session_state:
    st.session_state.spread_analyzer = SpreadAnalyzer()
if "impact_estimator" not in st.session_state:
    st.session_state.impact_estimator = ImpactEstimator()
if "slippage_tracker" not in st.session_state:
    st.session_state.slippage_tracker = SlippageTracker()

scorer = st.session_state.liq_scorer
spreads = st.session_state.spread_analyzer
impact = st.session_state.impact_estimator
slippage = st.session_state.slippage_tracker

# --- Sidebar ---
st.sidebar.header("Settings")
symbol = st.sidebar.text_input("Symbol", "AAPL")
avg_volume = st.sidebar.number_input("Avg Daily Volume", value=50_000_000, step=1_000_000)
avg_spread = st.sidebar.number_input("Avg Spread (bps)", value=3.0, step=0.5)
market_cap = st.sidebar.number_input("Market Cap ($B)", value=150, step=10) * 1_000_000_000
volatility = st.sidebar.slider("Annualized Volatility", 0.05, 1.0, 0.25, 0.05)

# Score the symbol
score = scorer.score(
    symbol=symbol,
    avg_daily_volume=avg_volume,
    avg_spread_bps=avg_spread,
    market_cap=market_cap,
    volatility=volatility,
)

# --- Main Content ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Liquidity Score", "Spread Analysis", "Market Impact", "Slippage", "Portfolio"
])

# --- Tab 1: Liquidity Score ---
with tab1:
    st.subheader(f"Liquidity Score: {symbol}")

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Composite Score", f"{score.composite_score:.1f}/100")
    col2.metric("Volume Score", f"{score.volume_score:.1f}")
    col3.metric("Spread Score", f"{score.spread_score:.1f}")
    col4.metric("Depth Score", f"{score.depth_score:.1f}")
    col5.metric("Volatility Score", f"{score.volatility_score:.1f}")

    st.markdown(f"**Liquidity Tier:** {score.liquidity_tier.value.replace('_', ' ').title()}")

    # Score breakdown chart
    st.markdown("#### Score Breakdown")
    score_df = pd.DataFrame([{
        "Component": "Volume",
        "Score": score.volume_score,
        "Weight": "30%",
    }, {
        "Component": "Spread",
        "Score": score.spread_score,
        "Weight": "25%",
    }, {
        "Component": "Depth",
        "Score": score.depth_score,
        "Weight": "20%",
    }, {
        "Component": "Volatility",
        "Score": score.volatility_score,
        "Weight": "25%",
    }])

    st.bar_chart(score_df.set_index("Component")["Score"])

    # Tier thresholds
    st.markdown("#### Tier Thresholds")
    tier_data = []
    for tier_name, (low, high) in TIER_THRESHOLDS.items():
        tier_data.append({
            "Tier": tier_name.replace("_", " ").title(),
            "Min Score": low,
            "Max Score": high,
            "Current": "Yes" if score.liquidity_tier.value == tier_name else "",
        })
    st.dataframe(pd.DataFrame(tier_data), use_container_width=True, hide_index=True)

# --- Tab 2: Spread Analysis ---
with tab2:
    st.subheader("Bid-Ask Spread Analysis")

    col1, col2 = st.columns([1, 2])

    with col1:
        st.markdown("#### Record Spread")
        bid = st.number_input("Bid Price", value=149.95, step=0.01)
        ask = st.number_input("Ask Price", value=150.05, step=0.01)
        bid_sz = st.number_input("Bid Size", value=1000, step=100)
        ask_sz = st.number_input("Ask Size", value=800, step=100)

        if st.button("Record Spread"):
            snap = spreads.record_spread(symbol, bid, ask, bid_sz, ask_sz)
            st.success(f"Recorded spread: {snap.spread_bps:.1f} bps")

    with col2:
        st.markdown("#### Spread Statistics")
        stats = spreads.get_spread_statistics(symbol)
        if stats.get("data_points", 0) > 0:
            col_a, col_b, col_c = st.columns(3)
            col_a.metric("Avg Spread", f"{stats['avg_spread_bps']:.1f} bps")
            col_b.metric("Min Spread", f"{stats['min_spread_bps']:.1f} bps")
            col_c.metric("Max Spread", f"{stats['max_spread_bps']:.1f} bps")
        else:
            st.info("Record some spreads to see statistics")

        # Decomposition
        decomp = spreads.decompose_spread(symbol, volatility=volatility)
        if decomp:
            st.markdown("#### Spread Decomposition")
            for component, value in decomp.items():
                if component != "total_spread_bps":
                    st.write(f"**{component.replace('_', ' ').title()}:** {value:.1f} bps")

# --- Tab 3: Market Impact ---
with tab3:
    st.subheader("Market Impact Estimation")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown("#### Estimate Impact")
        order_shares = st.number_input("Order Size (shares)", value=10000, step=1000)
        order_side = st.selectbox("Side", ["buy", "sell"])
        impact_model = st.selectbox(
            "Model",
            [m.value for m in ImpactModel],
            format_func=lambda x: x.replace("_", " ").title()
        )

        if st.button("Estimate"):
            est = impact.estimate_impact(
                symbol=symbol,
                order_size_shares=order_shares,
                price=150.0,
                side=OrderSide(order_side),
                avg_daily_volume=avg_volume,
                volatility=volatility,
                liquidity_tier=score.liquidity_tier,
                model=ImpactModel(impact_model),
            )

            col_a, col_b, col_c = st.columns(3)
            col_a.metric("Total Impact", f"{est.estimated_impact_bps:.1f} bps")
            col_b.metric("Temp Impact", f"{est.temporary_impact_bps:.1f} bps")
            col_c.metric("Perm Impact", f"{est.permanent_impact_bps:.1f} bps")

            st.write(f"**Estimated Cost:** ${est.estimated_cost:.2f}")
            st.write(f"**Participation Rate:** {est.participation_rate:.4%}")
            st.write(f"**Confidence:** {est.confidence:.1%}")

    with col2:
        st.markdown("#### Optimal Execution")
        total_shares = st.number_input("Total Shares to Execute", value=100000, step=10000)

        if st.button("Find Optimal"):
            result = impact.estimate_optimal_execution(
                symbol=symbol,
                total_shares=total_shares,
                price=150.0,
                avg_daily_volume=avg_volume,
                volatility=volatility,
                liquidity_tier=score.liquidity_tier,
            )

            if result.get("optimal_strategy"):
                opt = result["optimal_strategy"]
                st.write(f"**Optimal Slices:** {opt['slices']}")
                st.write(f"**Shares per Slice:** {opt['shares_per_slice']:,}")
                st.write(f"**Avg Impact:** {opt['avg_impact_bps']:.1f} bps")
                st.write(f"**Total Cost:** ${opt['total_cost']:.2f}")

            if result.get("all_strategies"):
                strat_df = pd.DataFrame(result["all_strategies"])
                st.line_chart(strat_df.set_index("slices")["total_cost"])

# --- Tab 4: Slippage ---
with tab4:
    st.subheader("Slippage Analysis")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown("#### Record Slippage")
        slip_size = st.number_input("Order Size", value=5000, step=500, key="slip_size")
        slip_side = st.selectbox("Side", ["buy", "sell"], key="slip_side")
        expected = st.number_input("Expected Price", value=150.00, step=0.01)
        executed = st.number_input("Executed Price", value=150.05, step=0.01)
        mkt_vol = st.number_input("Market Volume", value=avg_volume, step=1_000_000, key="mkt_vol")

        if st.button("Record"):
            rec = slippage.record_slippage(
                symbol=symbol,
                side=OrderSide(slip_side),
                order_size=slip_size,
                expected_price=expected,
                executed_price=executed,
                market_volume=mkt_vol,
            )
            st.success(f"Recorded: {rec.slippage_bps:.1f} bps (${rec.slippage_cost:.2f})")

    with col2:
        st.markdown("#### Slippage Forecast")
        forecast_size = st.number_input("Forecast Order Size", value=10000, step=1000)

        forecast = slippage.forecast_slippage(
            symbol=symbol,
            order_size=forecast_size,
            price=150.0,
            side=OrderSide.BUY,
            avg_daily_volume=avg_volume,
        )

        st.write(f"**Estimated Slippage:** {forecast['estimated_slippage_bps']:.1f} bps")
        st.write(f"**Estimated Cost:** ${forecast['estimated_cost']:.2f}")
        st.write(f"**Confidence:** {forecast['confidence']:.1%}")
        st.write(f"**Model:** {forecast['model']}")

    # Statistics
    st.markdown("---")
    st.markdown("#### Slippage Statistics")
    slip_stats = slippage.get_slippage_statistics(symbol)
    if slip_stats.get("total_records", 0) > 0:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Avg Slippage", f"{slip_stats['avg_slippage_bps']:.1f} bps")
        col2.metric("Max Slippage", f"{slip_stats['max_slippage_bps']:.1f} bps")
        col3.metric("Total Cost", f"${slip_stats['total_slippage_cost']:.2f}")
        col4.metric("Positive %", f"{slip_stats['positive_slippage_pct']:.0%}")
    else:
        st.info("Record some slippage data to see statistics")

# --- Tab 5: Portfolio ---
with tab5:
    st.subheader("Portfolio Liquidity")

    st.markdown("#### Score Multiple Symbols")

    symbols_input = st.text_input("Symbols (comma-separated)", "AAPL, MSFT, GOOGL, AMZN, TSLA")
    symbols = [s.strip() for s in symbols_input.split(",")]

    sample_holdings = {
        "AAPL": {"avg_daily_volume": 50_000_000, "avg_spread_bps": 3.0, "value": 500_000, "volatility": 0.25},
        "MSFT": {"avg_daily_volume": 30_000_000, "avg_spread_bps": 4.0, "value": 400_000, "volatility": 0.22},
        "GOOGL": {"avg_daily_volume": 20_000_000, "avg_spread_bps": 5.0, "value": 300_000, "volatility": 0.28},
        "AMZN": {"avg_daily_volume": 40_000_000, "avg_spread_bps": 3.5, "value": 350_000, "volatility": 0.30},
        "TSLA": {"avg_daily_volume": 80_000_000, "avg_spread_bps": 6.0, "value": 200_000, "volatility": 0.50},
    }

    if st.button("Score Portfolio"):
        holdings = {s: sample_holdings.get(s, {
            "avg_daily_volume": 5_000_000,
            "avg_spread_bps": 15.0,
            "value": 100_000,
            "volatility": 0.30,
        }) for s in symbols}

        result = scorer.score_portfolio(holdings)

        st.metric("Portfolio Score", f"{result['portfolio_score']:.1f}/100")
        st.write(f"**Portfolio Tier:** {result['portfolio_tier'].replace('_', ' ').title()}")

        if result.get("symbol_scores"):
            score_data = []
            for sym, s in result["symbol_scores"].items():
                score_data.append({
                    "Symbol": sym,
                    "Score": f"{s['composite_score']:.1f}",
                    "Tier": s["liquidity_tier"].replace("_", " ").title(),
                    "Volume": f"{s.get('avg_daily_volume', 0):,.0f}",
                    "Spread (bps)": f"{s.get('avg_spread_bps', 0):.1f}",
                })
            st.dataframe(pd.DataFrame(score_data), use_container_width=True, hide_index=True)

        if result.get("illiquid_holdings"):
            st.warning(f"Illiquid holdings: {', '.join(result['illiquid_holdings'])}")
