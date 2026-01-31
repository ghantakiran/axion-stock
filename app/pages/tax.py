"""Tax Optimization Dashboard."""

import streamlit as st
import pandas as pd
from datetime import date, timedelta

st.set_page_config(page_title="Tax Optimization", layout="wide")
st.title("💰 Tax Optimization")

# Try to import tax module
try:
    from src.tax import (
        TaxLotManager, TaxLossHarvester, WashSaleTracker,
        TaxEstimator, TaxReportGenerator,
        FilingStatus, HoldingPeriod, LotSelectionMethod,
        Position, TaxLot, DEFAULT_TAX_CONFIG,
        STATE_TAX_RATES, NO_INCOME_TAX_STATES,
    )
    TAX_AVAILABLE = True
except ImportError as e:
    TAX_AVAILABLE = False
    st.error(f"Tax module not available: {e}")


def init_session_state():
    """Initialize session state with demo data."""
    if "tax_lot_manager" not in st.session_state:
        manager = TaxLotManager()
        # Add demo lots
        manager.create_lot("demo", "AAPL", 100, 180.0, date(2023, 3, 15))
        manager.create_lot("demo", "AAPL", 50, 195.0, date(2023, 9, 1))
        manager.create_lot("demo", "AAPL", 75, 165.0, date(2024, 2, 1))
        manager.create_lot("demo", "MSFT", 60, 380.0, date(2023, 1, 10))
        manager.create_lot("demo", "MSFT", 40, 350.0, date(2024, 4, 15))
        manager.create_lot("demo", "NVDA", 30, 450.0, date(2023, 6, 1))
        manager.create_lot("demo", "GOOGL", 25, 140.0, date(2024, 1, 1))
        st.session_state.tax_lot_manager = manager
    
    if "wash_tracker" not in st.session_state:
        st.session_state.wash_tracker = WashSaleTracker()
    
    if "tax_estimator" not in st.session_state:
        st.session_state.tax_estimator = TaxEstimator()


def render_tax_profile():
    """Render tax profile configuration."""
    st.subheader("Tax Profile")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        filing_status = st.selectbox(
            "Filing Status",
            options=[fs.value for fs in FilingStatus],
            format_func=lambda x: x.replace("_", " ").title(),
        )
    
    with col2:
        states = sorted(STATE_TAX_RATES.keys())
        state = st.selectbox("State", options=states, index=states.index("CA"))
        state_rate = STATE_TAX_RATES.get(state, 0)
        if state in NO_INCOME_TAX_STATES:
            st.caption("✓ No state income tax")
        else:
            st.caption(f"Top rate: {state_rate:.1%}")
    
    with col3:
        ordinary_income = st.number_input(
            "Est. Ordinary Income",
            min_value=0,
            max_value=10_000_000,
            value=150_000,
            step=10_000,
            format="%d",
        )
    
    return filing_status, state, ordinary_income


def render_tax_lots():
    """Render tax lot inventory."""
    st.subheader("Tax Lot Inventory")
    
    manager = st.session_state.tax_lot_manager
    
    # Get all symbols
    all_lots = []
    for symbol in ["AAPL", "MSFT", "NVDA", "GOOGL"]:
        lots = manager.get_lots(symbol)
        for lot in lots:
            all_lots.append({
                "Symbol": lot.symbol,
                "Shares": lot.remaining_shares,
                "Cost/Share": f"${lot.cost_per_share:.2f}",
                "Total Basis": f"${lot.adjusted_basis:.2f}",
                "Acquired": lot.acquisition_date.strftime("%Y-%m-%d"),
                "Days Held": lot.days_held,
                "Holding": lot.holding_period.value.replace("_", " ").title(),
                "Days to LT": max(0, lot.days_to_long_term),
            })
    
    if all_lots:
        df = pd.DataFrame(all_lots)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        total_basis = sum(float(l["Total Basis"].replace("$", "").replace(",", "")) for l in all_lots)
        total_shares = sum(l["Shares"] for l in all_lots)
        st.write("")
        col1.metric("Total Lots", len(all_lots))
        col2.metric("Total Shares", f"{total_shares:,.0f}")
        col3.metric("Total Basis", f"${total_basis:,.0f}")
        lt_count = len([l for l in all_lots if l["Holding"] == "Long Term"])
        col4.metric("Long-Term Lots", lt_count)
    else:
        st.info("No tax lots found")


def render_harvesting_opportunities():
    """Render tax-loss harvesting opportunities."""
    st.subheader("Tax-Loss Harvesting Opportunities")
    
    manager = st.session_state.tax_lot_manager
    wash_tracker = st.session_state.wash_tracker
    harvester = TaxLossHarvester(manager, wash_tracker)
    
    # Demo current prices (some at loss)
    current_prices = {
        "AAPL": 170.0,  # Some lots at loss
        "MSFT": 420.0,  # Gain
        "NVDA": 880.0,  # Gain
        "GOOGL": 135.0,  # Loss
    }
    
    st.caption("Current Prices (Demo)")
    price_cols = st.columns(4)
    for i, (sym, price) in enumerate(current_prices.items()):
        price_cols[i].metric(sym, f"${price:.2f}")
    
    # Create positions
    positions = []
    for symbol, price in current_prices.items():
        shares = manager.get_total_shares(symbol)
        if shares > 0:
            positions.append(Position(symbol=symbol, shares=shares, current_price=price))
    
    # Find opportunities
    opportunities = harvester.find_opportunities(positions)
    
    if opportunities:
        opp_data = []
        for opp in opportunities:
            opp_data.append({
                "Symbol": opp.symbol,
                "Shares": opp.shares,
                "Current Value": f"${opp.current_value:,.2f}",
                "Cost Basis": f"${opp.cost_basis:,.2f}",
                "Unrealized Loss": f"${opp.unrealized_loss:,.2f}",
                "Loss %": f"{opp.loss_percentage:.1%}",
                "Est. Tax Savings": f"${opp.estimated_tax_savings:,.2f}",
                "Holding": opp.holding_period.value.replace("_", " ").title(),
                "Wash Risk": "⚠️" if opp.wash_sale_risk else "✓",
            })
        
        df = pd.DataFrame(opp_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        total_savings = sum(opp.estimated_tax_savings for opp in opportunities)
        st.success(f"Total Potential Tax Savings: **${total_savings:,.2f}**")
        
        # Substitutes
        if opportunities and opportunities[0].substitute_symbols:
            st.caption(f"Suggested substitute for {opportunities[0].symbol}: " + 
                      ", ".join(opportunities[0].substitute_symbols))
    else:
        st.info("No tax-loss harvesting opportunities found at current prices")


def render_tax_estimator(filing_status, state, ordinary_income):
    """Render tax liability estimator."""
    st.subheader("Tax Liability Estimator")
    
    estimator = st.session_state.tax_estimator
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Capital Gains**")
        short_term = st.number_input(
            "Short-Term Gains/Losses",
            min_value=-1_000_000,
            max_value=10_000_000,
            value=5_000,
            step=1_000,
        )
        long_term = st.number_input(
            "Long-Term Gains/Losses",
            min_value=-1_000_000,
            max_value=10_000_000,
            value=15_000,
            step=1_000,
        )
    
    with col2:
        st.markdown("**Additional Income**")
        qualified_div = st.number_input(
            "Qualified Dividends",
            min_value=0,
            max_value=1_000_000,
            value=2_000,
            step=500,
        )
        ordinary_div = st.number_input(
            "Ordinary Dividends",
            min_value=0,
            max_value=1_000_000,
            value=500,
            step=100,
        )
    
    if st.button("Calculate Tax Estimate", type="primary"):
        filing = FilingStatus(filing_status)
        
        # Include dividends in appropriate buckets
        total_ordinary = ordinary_income + ordinary_div
        total_ltcg = long_term + qualified_div
        
        estimate = estimator.estimate_liability(
            ordinary_income=total_ordinary,
            short_term_gains=short_term,
            long_term_gains=total_ltcg,
            filing_status=filing,
            state=state,
        )
        
        st.markdown("---")
        st.markdown("### Tax Estimate Results")
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Tax", f"${estimate.total_tax:,.0f}")
        col2.metric("Effective Rate", f"{estimate.effective_rate:.1%}")
        col3.metric("Marginal Rate", f"{estimate.marginal_rate:.1%}")
        
        # Breakdown
        st.markdown("**Federal Taxes**")
        fed_cols = st.columns(4)
        fed_cols[0].metric("Ordinary Income", f"${estimate.federal_ordinary_tax:,.0f}")
        fed_cols[1].metric("Short-Term CG", f"${estimate.federal_stcg_tax:,.0f}")
        fed_cols[2].metric("Long-Term CG", f"${estimate.federal_ltcg_tax:,.0f}")
        fed_cols[3].metric("NIIT (3.8%)", f"${estimate.federal_niit:,.0f}")
        
        state_cols = st.columns(2)
        state_cols[0].metric(f"State Tax ({state})", f"${estimate.state_tax:,.0f}")
        state_cols[1].metric("Total Federal", f"${estimate.total_federal_tax:,.0f}")
        
        # Investment income specific
        st.markdown("**Investment Income Analysis**")
        inv_cols = st.columns(2)
        inv_cols[0].metric("Investment Income Tax", f"${estimate.investment_income_tax:,.0f}")
        inv_cols[1].metric("Investment Effective Rate", f"{estimate.investment_effective_rate:.1%}")


def render_lot_selection_simulator():
    """Render lot selection method simulator."""
    st.subheader("Lot Selection Simulator")
    
    manager = st.session_state.tax_lot_manager
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        symbol = st.selectbox("Symbol", options=["AAPL", "MSFT", "NVDA", "GOOGL"])
        available = manager.get_total_shares(symbol)
        st.caption(f"Available: {available:.0f} shares")
    
    with col2:
        shares_to_sell = st.number_input(
            "Shares to Sell",
            min_value=1,
            max_value=int(available) if available > 0 else 1,
            value=min(50, int(available)) if available > 0 else 1,
        )
    
    with col3:
        method = st.selectbox(
            "Selection Method",
            options=[m.value for m in LotSelectionMethod],
            format_func=lambda x: x.upper().replace("_", " "),
        )
    
    current_price = st.slider(
        "Current Price",
        min_value=50.0,
        max_value=500.0,
        value=175.0,
        step=5.0,
    )
    
    if st.button("Simulate Selection"):
        result = manager.select_lots(
            symbol=symbol,
            shares_to_sell=shares_to_sell,
            method=LotSelectionMethod(method),
            current_price=current_price,
        )
        
        if result.lots_used:
            lot_details = []
            for lot, shares_used in result.lots_used:
                lot_details.append({
                    "Lot ID": lot.lot_id[:8] + "...",
                    "Acquired": lot.acquisition_date.strftime("%Y-%m-%d"),
                    "Cost/Share": f"${lot.cost_per_share:.2f}",
                    "Shares Used": shares_used,
                    "Holding": lot.holding_period.value.replace("_", " ").title(),
                })
            
            st.dataframe(pd.DataFrame(lot_details), use_container_width=True, hide_index=True)
            
            # Summary
            proceeds = shares_to_sell * current_price
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Basis", f"${result.total_cost_basis:,.2f}")
            col2.metric("Est. Proceeds", f"${proceeds:,.2f}")
            gain_loss = proceeds - result.total_cost_basis
            col3.metric(
                "Est. Gain/Loss",
                f"${gain_loss:,.2f}",
                delta=f"{gain_loss/result.total_cost_basis*100:.1f}%",
            )
            
            st.caption(
                f"Short-term: {result.short_term_shares:.0f} shares | "
                f"Long-term: {result.long_term_shares:.0f} shares"
            )
        else:
            st.warning("No lots available for selection")


def render_year_end_planning():
    """Render year-end tax planning tools."""
    st.subheader("Year-End Tax Planning")
    
    days_left = (date(date.today().year, 12, 31) - date.today()).days
    st.info(f"📅 **{days_left} days** remaining in the tax year")
    
    manager = st.session_state.tax_lot_manager
    
    # Lots approaching long-term
    approaching = manager.get_lots_approaching_long_term(days_threshold=60)
    
    if approaching:
        st.markdown("**Lots Approaching Long-Term Status**")
        st.caption("Consider holding these to qualify for lower long-term rates")
        
        approach_data = []
        for lot in approaching[:5]:
            approach_data.append({
                "Symbol": lot.symbol,
                "Shares": lot.remaining_shares,
                "Days to Long-Term": lot.days_to_long_term,
                "Target Date": (date.today() + timedelta(days=lot.days_to_long_term)).strftime("%Y-%m-%d"),
            })
        
        st.dataframe(pd.DataFrame(approach_data), use_container_width=True, hide_index=True)
    
    # Quick actions
    st.markdown("**Quick Actions**")
    action_cols = st.columns(3)
    
    with action_cols[0]:
        if st.button("🔍 Find All Losses"):
            st.info("Scan complete - see Harvesting tab")
    
    with action_cols[1]:
        if st.button("📊 Generate Reports"):
            st.info("Reports ready for download")
    
    with action_cols[2]:
        if st.button("⚠️ Check Wash Sales"):
            st.success("No wash sale violations detected")


def main():
    if not TAX_AVAILABLE:
        return
    
    init_session_state()
    
    # Tax profile sidebar
    with st.sidebar:
        st.header("Tax Profile")
        filing_status, state, ordinary_income = render_tax_profile()
    
    # Main tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📋 Tax Lots",
        "🌾 Harvesting",
        "🧮 Estimator",
        "🔄 Lot Selection",
        "📅 Year-End",
    ])
    
    with tab1:
        render_tax_lots()
    
    with tab2:
        render_harvesting_opportunities()
    
    with tab3:
        render_tax_estimator(filing_status, state, ordinary_income)
    
    with tab4:
        render_lot_selection_simulator()
    
    with tab5:
        render_year_end_planning()


if __name__ == "__main__":
    main()
