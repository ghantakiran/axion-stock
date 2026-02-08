"""AI Research Reports Dashboard."""

import streamlit as st
import pandas as pd

try:
    st.set_page_config(page_title="AI Research", layout="wide")
except st.errors.StreamlitAPIException:
    pass

st.title("🔬 AI Research Reports")

# Try to import research module
try:
    from src.research import (
        ResearchEngine, Rating, MoatRating, RiskLevel,
        FinancialMetrics, ValuationSummary,
    )
    RESEARCH_AVAILABLE = True
except ImportError as e:
    RESEARCH_AVAILABLE = False
    st.error(f"Research module not available: {e}")


def get_demo_data(symbol: str) -> tuple[dict, dict, dict]:
    """Get demo financial and market data."""
    # Demo data for popular stocks
    stock_data = {
        "AAPL": {
            "name": "Apple Inc.",
            "sector": "Technology",
            "revenue": 383e9,
            "revenue_growth": 0.08,
            "gross_margin": 0.45,
            "operating_margin": 0.30,
            "net_margin": 0.25,
            "eps": 6.13,
            "eps_growth": 0.09,
            "total_assets": 352e9,
            "total_equity": 62e9,
            "total_debt": 111e9,
            "cash": 62e9,
            "price": 185.0,
            "beta": 1.28,
            "shares": 15.5e9,
            "market_cap": 2.87e12,
        },
        "MSFT": {
            "name": "Microsoft Corporation",
            "sector": "Technology",
            "revenue": 211e9,
            "revenue_growth": 0.12,
            "gross_margin": 0.69,
            "operating_margin": 0.42,
            "net_margin": 0.35,
            "eps": 9.81,
            "eps_growth": 0.15,
            "total_assets": 411e9,
            "total_equity": 206e9,
            "total_debt": 47e9,
            "cash": 80e9,
            "price": 378.0,
            "beta": 0.92,
            "shares": 7.4e9,
            "market_cap": 2.8e12,
        },
        "GOOGL": {
            "name": "Alphabet Inc.",
            "sector": "Technology",
            "revenue": 307e9,
            "revenue_growth": 0.10,
            "gross_margin": 0.56,
            "operating_margin": 0.27,
            "net_margin": 0.22,
            "eps": 5.80,
            "eps_growth": 0.12,
            "total_assets": 402e9,
            "total_equity": 256e9,
            "total_debt": 14e9,
            "cash": 111e9,
            "price": 141.0,
            "beta": 1.05,
            "shares": 12.5e9,
            "market_cap": 1.76e12,
        },
    }
    
    # Default data
    data = stock_data.get(symbol.upper(), stock_data["AAPL"])
    
    financial_data = {
        "revenue": data["revenue"],
        "revenue_growth": data["revenue_growth"],
        "gross_margin": data["gross_margin"],
        "operating_margin": data["operating_margin"],
        "net_margin": data["net_margin"],
        "eps": data["eps"],
        "eps_growth": data["eps_growth"],
        "total_assets": data["total_assets"],
        "total_equity": data["total_equity"],
        "total_debt": data["total_debt"],
        "cash": data["cash"],
        "operating_income": data["revenue"] * data["operating_margin"],
        "net_income": data["revenue"] * data["net_margin"],
        "operating_cash_flow": data["revenue"] * data["net_margin"] * 1.2,
        "market_cap": data["market_cap"],
    }
    
    market_data = {
        "price": data["price"],
        "beta": data["beta"],
        "shares_outstanding": data["shares"],
        "sector": data["sector"],
        "market_cap": data["market_cap"],
        "market_size": 500e9,
        "market_share": 0.20,
        "market_growth": 0.08,
    }
    
    peer_data = {
        "MSFT": {"pe": 35, "ev_ebitda": 24, "ps": 12, "growth": 0.12},
        "GOOGL": {"pe": 25, "ev_ebitda": 16, "ps": 6, "growth": 0.10},
        "META": {"pe": 27, "ev_ebitda": 14, "ps": 7, "growth": 0.15},
        "AMZN": {"pe": 45, "ev_ebitda": 18, "ps": 3, "growth": 0.11},
    }
    
    return financial_data, market_data, peer_data, data["name"]


def render_report_summary(report):
    """Render report summary section."""
    # Rating badge
    rating_colors = {
        "strong_buy": "#48bb78",
        "buy": "#68d391",
        "hold": "#ecc94b",
        "sell": "#fc8181",
        "strong_sell": "#e53e3e",
    }
    color = rating_colors.get(report.rating.value, "#718096")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(
            f"""<div style="background:{color}; color:white; padding:10px 20px; 
            border-radius:5px; text-align:center; font-weight:bold;">
            {report.rating.value.replace('_', ' ').upper()}</div>""",
            unsafe_allow_html=True
        )
    
    col2.metric("Current Price", f"${report.current_price:.2f}")
    col3.metric("Price Target", f"${report.price_target:.2f}")
    col4.metric("Upside", f"{report.upside_pct:.1f}%")
    
    # Executive summary
    st.markdown("---")
    st.subheader("Executive Summary")
    st.write(report.executive_summary)
    
    if report.key_takeaways:
        st.markdown("**Key Takeaways:**")
        for takeaway in report.key_takeaways:
            st.markdown(f"- {takeaway}")


def render_financial_analysis(financial):
    """Render financial analysis section."""
    st.subheader("📊 Financial Analysis")
    
    if not financial:
        st.info("Financial analysis not available")
        return
    
    m = financial.metrics
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Revenue (TTM)", f"${m.revenue_ttm/1e9:.1f}B")
    col2.metric("Revenue Growth", f"{m.revenue_growth_yoy:.1%}")
    col3.metric("Operating Margin", f"{m.operating_margin:.1%}")
    col4.metric("Net Margin", f"{m.net_margin:.1%}")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("EPS", f"${m.eps_ttm:.2f}")
    col2.metric("ROE", f"{m.roe:.1%}")
    col3.metric("Debt/Equity", f"{m.debt_to_equity:.2f}x")
    col4.metric("FCF Margin", f"{m.fcf_margin:.1%}")
    
    # Quality scores
    st.markdown("**Quality Scores:**")
    col1, col2, col3 = st.columns(3)
    col1.progress(financial.earnings_quality_score / 100, f"Earnings Quality: {financial.earnings_quality_score:.0f}")
    col2.progress(financial.balance_sheet_strength / 100, f"Balance Sheet: {financial.balance_sheet_strength:.0f}")
    col3.progress(financial.cash_flow_quality / 100, f"Cash Flow: {financial.cash_flow_quality:.0f}")
    
    # Strengths & Concerns
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Strengths:**")
        for s in financial.strengths[:5]:
            st.markdown(f"✅ {s}")
    with col2:
        st.markdown("**Concerns:**")
        for c in financial.concerns[:5]:
            st.markdown(f"⚠️ {c}")


def render_valuation(valuation):
    """Render valuation section."""
    st.subheader("💰 Valuation")
    
    if not valuation:
        st.info("Valuation not available")
        return
    
    col1, col2, col3 = st.columns(3)
    col1.metric("DCF Value", f"${valuation.dcf_value:.2f}")
    col2.metric("Comparable Value", f"${valuation.comparable_value:.2f}")
    col3.metric("Fair Value", f"${valuation.fair_value:.2f}")
    
    st.markdown(f"**Valuation Range:** ${valuation.valuation_range_low:.2f} - ${valuation.valuation_range_high:.2f}")
    st.markdown(f"**Confidence:** {valuation.confidence:.0%}")
    
    # DCF details
    if valuation.dcf:
        with st.expander("DCF Details"):
            dcf = valuation.dcf
            st.markdown(f"- WACC: {dcf.wacc:.1%}")
            st.markdown(f"- Terminal Growth: {dcf.terminal_growth_rate:.1%}")
            st.markdown(f"- Enterprise Value: ${dcf.enterprise_value/1e9:.1f}B")
            st.markdown(f"- Equity Value: ${dcf.equity_value/1e9:.1f}B")


def render_competitive(competitive):
    """Render competitive analysis section."""
    st.subheader("🏆 Competitive Analysis")
    
    if not competitive:
        st.info("Competitive analysis not available")
        return
    
    col1, col2, col3 = st.columns(3)
    
    moat_color = {"wide": "🟢", "narrow": "🟡", "none": "🔴"}.get(competitive.moat_rating.value, "⚪")
    col1.markdown(f"**Moat Rating:** {moat_color} {competitive.moat_rating.value.title()}")
    col2.markdown(f"**Market Position:** {competitive.market_position.title()}")
    col3.markdown(f"**Moat Trend:** {competitive.moat_trend.value.title()}")
    
    if competitive.moat_sources:
        st.markdown(f"**Moat Sources:** {', '.join(competitive.moat_sources)}")
    
    # SWOT
    st.markdown("**SWOT Analysis:**")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Strengths:**")
        for s in competitive.strengths[:4]:
            st.markdown(f"- {s}")
        st.markdown("**Opportunities:**")
        for o in competitive.opportunities[:4]:
            st.markdown(f"- {o}")
    with col2:
        st.markdown("**Weaknesses:**")
        for w in competitive.weaknesses[:4]:
            st.markdown(f"- {w}")
        st.markdown("**Threats:**")
        for t in competitive.threats[:4]:
            st.markdown(f"- {t}")


def render_risk(risk):
    """Render risk assessment section."""
    st.subheader("⚠️ Risk Assessment")
    
    if not risk:
        st.info("Risk assessment not available")
        return
    
    risk_color = {
        "low": "🟢",
        "medium": "🟡", 
        "high": "🟠",
        "very_high": "🔴"
    }.get(risk.overall_risk_rating.value, "⚪")
    
    col1, col2 = st.columns(2)
    col1.markdown(f"**Overall Risk:** {risk_color} {risk.overall_risk_rating.value.replace('_', ' ').title()}")
    col2.markdown(f"**Risk Score:** {risk.risk_score:.0f}/100")
    
    st.markdown("**Key Risks:**")
    for r in risk.key_risks[:3]:
        st.markdown(f"- {r}")
    
    # Risk breakdown
    col1, col2 = st.columns(2)
    with col1:
        st.progress(risk.business_risk / 100, f"Business Risk: {risk.business_risk:.0f}")
        st.progress(risk.financial_risk / 100, f"Financial Risk: {risk.financial_risk:.0f}")
    with col2:
        st.progress(risk.operational_risk / 100, f"Operational Risk: {risk.operational_risk:.0f}")
        st.progress(risk.regulatory_risk / 100, f"Regulatory Risk: {risk.regulatory_risk:.0f}")


def render_thesis(thesis):
    """Render investment thesis section."""
    st.subheader("📝 Investment Thesis")
    
    if not thesis:
        st.info("Investment thesis not available")
        return
    
    # Scenario table
    scenarios = pd.DataFrame([
        {"Scenario": "Bull Case", "Price Target": f"${thesis.bull_price_target:.2f}", "Probability": f"{thesis.bull_probability:.0%}"},
        {"Scenario": "Base Case", "Price Target": f"${thesis.base_price_target:.2f}", "Probability": f"{thesis.base_probability:.0%}"},
        {"Scenario": "Bear Case", "Price Target": f"${thesis.bear_price_target:.2f}", "Probability": f"{thesis.bear_probability:.0%}"},
    ])
    st.dataframe(scenarios, use_container_width=True, hide_index=True)
    
    st.markdown(f"**Expected Price:** ${thesis.expected_price:.2f}")
    
    # Cases
    with st.expander("Bull Case"):
        st.write(thesis.bull_case)
        if thesis.bull_catalysts:
            st.markdown("**Catalysts:**")
            for c in thesis.bull_catalysts:
                st.markdown(f"- {c}")
    
    with st.expander("Bear Case"):
        st.write(thesis.bear_case)
        if thesis.bear_risks:
            st.markdown("**Risks:**")
            for r in thesis.bear_risks:
                st.markdown(f"- {r}")
    
    # Buy/Sell reasons
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Reasons to Buy:**")
        for r in thesis.reasons_to_buy[:5]:
            st.markdown(f"✅ {r}")
    with col2:
        st.markdown("**Reasons for Caution:**")
        for r in thesis.reasons_to_sell[:5]:
            st.markdown(f"⚠️ {r}")


def main():
    if not RESEARCH_AVAILABLE:
        return
    
    # Sidebar
    st.sidebar.header("Generate Report")
    symbol = st.sidebar.text_input("Stock Symbol", value="AAPL").upper()
    
    if st.sidebar.button("Generate Report", type="primary"):
        with st.spinner(f"Generating research report for {symbol}..."):
            try:
                # Get data
                financial_data, market_data, peer_data, company_name = get_demo_data(symbol)
                
                # Generate report
                engine = ResearchEngine()
                report = engine.generate_full_report(
                    symbol=symbol,
                    company_name=company_name,
                    financial_data=financial_data,
                    market_data=market_data,
                    peer_data=peer_data,
                )
                
                st.session_state.current_report = report
                st.success(f"Report generated for {symbol}!")
                
            except Exception as e:
                st.error(f"Error generating report: {e}")
    
    # Display report
    if "current_report" in st.session_state:
        report = st.session_state.current_report
        
        st.header(f"{report.company_name} ({report.symbol})")
        
        # Summary
        render_report_summary(report)
        
        # Tabs for sections
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📊 Financials", "💰 Valuation", "🏆 Competitive", "⚠️ Risk", "📝 Thesis"
        ])
        
        with tab1:
            render_financial_analysis(report.financial_analysis)
        
        with tab2:
            render_valuation(report.valuation)
        
        with tab3:
            render_competitive(report.competitive_analysis)
        
        with tab4:
            render_risk(report.risk_assessment)
        
        with tab5:
            render_thesis(report.investment_thesis)
        
        # Export options
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📄 Export HTML"):
                html = engine.format_report(report, "html")
                st.download_button(
                    "Download HTML",
                    html,
                    f"{report.symbol}_research_report.html",
                    "text/html"
                )
        with col2:
            if st.button("📝 Export Markdown"):
                md = engine.format_report(report, "markdown")
                st.download_button(
                    "Download Markdown",
                    md,
                    f"{report.symbol}_research_report.md",
                    "text/markdown"
                )
    else:
        st.info("Enter a stock symbol and click 'Generate Report' to get started.")
        
        # Quick picks
        st.markdown("**Quick Picks:**")
        col1, col2, col3, col4 = st.columns(4)
        if col1.button("AAPL"):
            st.session_state.quick_symbol = "AAPL"
            st.rerun()
        if col2.button("MSFT"):
            st.session_state.quick_symbol = "MSFT"
            st.rerun()
        if col3.button("GOOGL"):
            st.session_state.quick_symbol = "GOOGL"
            st.rerun()
        if col4.button("AMZN"):
            st.session_state.quick_symbol = "AMZN"
            st.rerun()



main()
