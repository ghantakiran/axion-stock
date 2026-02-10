"""Dividend Tracker Dashboard."""

import streamlit as st
from app.styles import inject_global_styles
import pandas as pd
from datetime import date, timedelta

try:
    st.set_page_config(page_title="Dividend Tracker", layout="wide")
except st.errors.StreamlitAPIException:
    pass

inject_global_styles()

st.title("💰 Dividend Tracker")

# Try to import dividends module
try:
    from src.dividends import (
        DividendCalendar, DividendEvent, DividendFrequency,
        DividendHolding, IncomeProjector, SafetyAnalyzer,
        GrowthAnalyzer, DRIPSimulator, TaxAnalyzer,
        FinancialMetrics, DividendStatus, SafetyRating,
        generate_sample_calendar, generate_sample_growth_data,
    )
    DIVIDENDS_AVAILABLE = True
except ImportError as e:
    DIVIDENDS_AVAILABLE = False
    st.error(f"Dividends module not available: {e}")


def get_demo_holdings() -> list[DividendHolding]:
    """Get demo dividend holdings."""
    return [
        DividendHolding(
            symbol="JNJ", company_name="Johnson & Johnson",
            shares=100, cost_basis=14000, current_price=155,
            annual_dividend=4.96, frequency=DividendFrequency.QUARTERLY,
            sector="Healthcare",
        ),
        DividendHolding(
            symbol="KO", company_name="Coca-Cola Co.",
            shares=200, cost_basis=10000, current_price=60,
            annual_dividend=1.94, frequency=DividendFrequency.QUARTERLY,
            sector="Consumer Defensive",
        ),
        DividendHolding(
            symbol="O", company_name="Realty Income",
            shares=150, cost_basis=7500, current_price=55,
            annual_dividend=3.08, frequency=DividendFrequency.MONTHLY,
            sector="Real Estate",
        ),
        DividendHolding(
            symbol="PG", company_name="Procter & Gamble",
            shares=75, cost_basis=10500, current_price=165,
            annual_dividend=4.03, frequency=DividendFrequency.QUARTERLY,
            sector="Consumer Defensive",
        ),
        DividendHolding(
            symbol="VZ", company_name="Verizon",
            shares=120, cost_basis=5400, current_price=42,
            annual_dividend=2.66, frequency=DividendFrequency.QUARTERLY,
            sector="Communication Services",
        ),
    ]


def render_calendar_tab():
    """Render dividend calendar tab."""
    st.subheader("Upcoming Dividends")
    
    calendar = generate_sample_calendar()
    
    # Get upcoming ex-dates
    upcoming = calendar.get_upcoming_ex_dates(days=30)
    
    if not upcoming:
        st.info("No upcoming ex-dividend dates")
        return
    
    # Display calendar
    data = []
    for event in upcoming:
        change_str = ""
        if event.change_pct:
            if event.change_pct > 0:
                change_str = f"↑ {event.change_pct:.1%}"
            elif event.change_pct < 0:
                change_str = f"↓ {abs(event.change_pct):.1%}"
        
        data.append({
            "Ex-Date": event.ex_dividend_date.strftime("%Y-%m-%d") if event.ex_dividend_date else "",
            "Payment": event.payment_date.strftime("%Y-%m-%d") if event.payment_date else "",
            "Symbol": event.symbol,
            "Company": event.company_name,
            "Amount": f"${event.amount:.4f}",
            "Annual": f"${event.annual_amount:.2f}",
            "Change": change_str,
            "Frequency": event.frequency.value.title(),
        })
    
    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    # Summary
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    col1.metric("Upcoming Ex-Dates", len(upcoming))
    col2.metric("This Week", len([e for e in upcoming if e.ex_dividend_date and e.ex_dividend_date <= date.today() + timedelta(days=7)]))
    col3.metric("With Increases", len([e for e in upcoming if e.change_pct and e.change_pct > 0]))


def render_income_tab():
    """Render income projections tab."""
    st.subheader("Income Projections")
    
    holdings = get_demo_holdings()
    projector = IncomeProjector()
    
    # Project income
    portfolio_income = projector.project_portfolio(holdings)
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Annual Income", f"${portfolio_income.annual_income:,.2f}")
    col2.metric("Monthly Average", f"${portfolio_income.monthly_average:,.2f}")
    col3.metric("Portfolio Yield", f"{portfolio_income.portfolio_yield:.2%}")
    col4.metric("Yield on Cost", f"{portfolio_income.weighted_yield_on_cost:.2%}")
    
    # Holdings breakdown
    st.markdown("---")
    st.markdown("**Income by Holding**")
    
    data = []
    for h in holdings:
        data.append({
            "Symbol": h.symbol,
            "Company": h.company_name,
            "Shares": h.shares,
            "Annual Div": f"${h.annual_dividend:.2f}",
            "Income": f"${h.annual_income:,.2f}",
            "Yield": f"{h.current_yield:.2%}",
            "YOC": f"{h.yield_on_cost:.2%}",
        })
    
    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    # Monthly breakdown chart
    st.markdown("---")
    st.markdown("**Monthly Income**")
    
    monthly_data = pd.DataFrame({
        "Month": list(portfolio_income.monthly_projections.keys()),
        "Income": list(portfolio_income.monthly_projections.values()),
    })
    st.bar_chart(monthly_data.set_index("Month"))


def render_safety_tab():
    """Render dividend safety tab."""
    st.subheader("Dividend Safety Analysis")
    
    st.info("Analyze dividend safety for a stock using financial metrics.")
    
    # Sample analysis
    if st.button("Analyze Sample (JNJ)"):
        analyzer = SafetyAnalyzer()
        
        metrics = FinancialMetrics(
            eps=10.50,
            dividend_per_share=4.96,
            free_cash_flow=20e9,
            total_dividends_paid=12e9,
            shares_outstanding=2.4e9,
            total_debt=35e9,
            ebitda=30e9,
            interest_expense=1.5e9,
            current_assets=50e9,
            current_liabilities=40e9,
        )
        
        safety = analyzer.analyze("JNJ", metrics)
        
        # Display results
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Safety Score", f"{safety.safety_score:.0f}/100")
            
            rating_colors = {
                SafetyRating.VERY_SAFE: "🟢",
                SafetyRating.SAFE: "🟢",
                SafetyRating.MODERATE: "🟡",
                SafetyRating.RISKY: "🟠",
                SafetyRating.DANGEROUS: "🔴",
            }
            st.write(f"Rating: {rating_colors.get(safety.safety_rating, '')} {safety.safety_rating.value.replace('_', ' ').title()}")
        
        with col2:
            st.metric("Payout Ratio", f"{safety.payout_ratio:.1%}")
            st.metric("Coverage Ratio", f"{safety.coverage_ratio:.1f}x")
        
        with col3:
            st.metric("Cash Payout", f"{safety.cash_payout_ratio:.1%}")
            st.metric("Debt/EBITDA", f"{safety.debt_to_ebitda:.1f}x")
        
        # Red flags
        if safety.red_flags:
            st.markdown("---")
            st.markdown("**⚠️ Red Flags**")
            for flag in safety.red_flags:
                st.write(f"• {flag}")
        else:
            st.success("✓ No red flags detected")


def render_growth_tab():
    """Render dividend growth tab."""
    st.subheader("Dividend Growth Analysis")
    
    analyzer = generate_sample_growth_data()
    
    # Display aristocrats/kings
    st.markdown("**Dividend Aristocrats & Kings**")
    
    symbols = ["JNJ", "KO", "PG", "AAPL", "MSFT"]
    data = []
    
    for symbol in symbols:
        growth = analyzer.get_growth(symbol)
        if growth:
            status_icons = {
                DividendStatus.KING: "👑",
                DividendStatus.ARISTOCRAT: "🏆",
                DividendStatus.ACHIEVER: "⭐",
                DividendStatus.CONTENDER: "📈",
                DividendStatus.CHALLENGER: "🌱",
                DividendStatus.NONE: "",
            }
            
            data.append({
                "Symbol": symbol,
                "Status": f"{status_icons.get(growth.status, '')} {growth.status.value.title()}",
                "Streak": f"{growth.consecutive_increases} years",
                "1Y Growth": f"{growth.cagr_1y:.1%}" if growth.cagr_1y else "-",
                "5Y CAGR": f"{growth.cagr_5y:.1%}" if growth.cagr_5y else "-",
                "Current Div": f"${growth.current_annual_dividend:.2f}",
            })
    
    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    st.markdown("""
    **Legend:**
    - 👑 King: 50+ years of consecutive increases
    - 🏆 Aristocrat: 25+ years
    - ⭐ Achiever: 10+ years
    - 📈 Contender: 5-9 years
    """)


def render_drip_tab():
    """Render DRIP simulation tab."""
    st.subheader("DRIP Simulation")
    st.write("See how dividend reinvestment can compound your wealth.")
    
    simulator = DRIPSimulator()
    
    # Input parameters
    col1, col2 = st.columns(2)
    
    with col1:
        symbol = st.text_input("Symbol", value="KO")
        initial_shares = st.number_input("Initial Shares", value=100, min_value=1)
        initial_price = st.number_input("Current Price ($)", value=60.0, min_value=1.0)
    
    with col2:
        initial_dividend = st.number_input("Annual Dividend ($)", value=1.94, min_value=0.01)
        years = st.slider("Years", 5, 40, 20)
        div_growth = st.slider("Dividend Growth (%)", 0, 15, 5) / 100
    
    if st.button("Run Simulation", type="primary"):
        result = simulator.simulate(
            symbol=symbol,
            initial_shares=initial_shares,
            initial_price=initial_price,
            initial_dividend=initial_dividend,
            years=years,
            dividend_growth_rate=div_growth,
            price_growth_rate=0.07,
        )
        
        # Results
        st.markdown("---")
        col1, col2, col3, col4 = st.columns(4)
        
        col1.metric(
            "Final Shares",
            f"{result.final_shares:,.1f}",
            f"+{result.final_shares - initial_shares:,.1f}"
        )
        col2.metric(
            "Final Value",
            f"${result.final_value:,.0f}",
            f"+{result.total_return_pct:.0%}"
        )
        col3.metric(
            "Annual Income",
            f"${result.final_annual_income:,.0f}",
        )
        col4.metric(
            "Total Dividends",
            f"${result.total_dividends_received:,.0f}",
        )
        
        # Year-by-year chart
        st.markdown("---")
        chart_data = pd.DataFrame({
            "Year": [y.year for y in result.yearly_projections],
            "Value": [y.ending_value for y in result.yearly_projections],
            "Income": [y.dividends_received for y in result.yearly_projections],
        })
        
        st.line_chart(chart_data.set_index("Year")["Value"])
        
        # Comparison
        st.markdown("---")
        comparison = simulator.compare_scenarios(
            symbol=symbol,
            initial_shares=initial_shares,
            initial_price=initial_price,
            initial_dividend=initial_dividend,
            years=years,
        )
        
        st.markdown("**DRIP vs No-DRIP Comparison**")
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**With DRIP**")
            st.write(f"Final Shares: {comparison['with_drip']['final_shares']:,.1f}")
            st.write(f"Final Value: ${comparison['with_drip']['final_value']:,.0f}")
        
        with col2:
            st.markdown("**Without DRIP**")
            st.write(f"Final Shares: {comparison['without_drip']['final_shares']:,.1f}")
            st.write(f"Total Value: ${comparison['without_drip']['total_value']:,.0f}")


def render_tax_tab():
    """Render tax analysis tab."""
    st.subheader("Tax Analysis")
    
    analyzer = TaxAnalyzer()
    holdings = get_demo_holdings()
    
    # Tax parameters
    col1, col2 = st.columns(2)
    with col1:
        taxable_income = st.number_input("Taxable Income ($)", value=100000, step=10000)
    with col2:
        state_rate = st.slider("State Tax Rate (%)", 0, 15, 5) / 100
    
    if st.button("Calculate Tax Impact"):
        analysis = analyzer.analyze_portfolio(
            holdings,
            taxable_income=taxable_income,
            state_tax_rate=state_rate,
        )
        
        # Results
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        
        col1.metric("Total Dividends", f"${analysis.total_dividend_income:,.2f}")
        col2.metric("Estimated Tax", f"${analysis.total_estimated_tax:,.2f}")
        col3.metric("After-Tax Income", f"${analysis.after_tax_income:,.2f}")
        
        st.metric("Effective Tax Rate", f"{analysis.effective_tax_rate:.1%}")
        
        # Breakdown
        st.markdown("---")
        st.markdown("**Income Breakdown**")
        st.write(f"• Qualified Dividends: ${analysis.qualified_dividends:,.2f}")
        st.write(f"• Non-Qualified: ${analysis.non_qualified_dividends:,.2f}")
        
        # Comparison
        st.markdown("---")
        comparison = analyzer.compare_qualified_vs_ordinary(
            dividend_income=analysis.total_dividend_income,
            taxable_income=taxable_income,
        )
        
        st.markdown("**Qualified vs Ordinary Tax Comparison**")
        st.write(f"Tax if all Qualified: ${comparison['tax_if_qualified']:,.2f}")
        st.write(f"Tax if all Ordinary: ${comparison['tax_if_ordinary']:,.2f}")
        st.success(f"Qualified Status Saves: ${comparison['tax_savings']:,.2f}")


def main():
    if not DIVIDENDS_AVAILABLE:
        return
    
    # Tabs
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📅 Calendar",
        "💵 Income",
        "🛡️ Safety",
        "📈 Growth",
        "🔄 DRIP",
        "📋 Tax",
    ])
    
    with tab1:
        render_calendar_tab()
    
    with tab2:
        render_income_tab()
    
    with tab3:
        render_safety_tab()
    
    with tab4:
        render_growth_tab()
    
    with tab5:
        render_drip_tab()
    
    with tab6:
        render_tax_tab()



main()
