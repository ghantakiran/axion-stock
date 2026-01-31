"""Earnings Calendar & Analysis Dashboard."""

import streamlit as st
import pandas as pd
from datetime import date, timedelta

st.set_page_config(page_title="Earnings Calendar", layout="wide")
st.title("📅 Earnings Calendar & Analysis")

# Try to import earnings module
try:
    from src.earnings import (
        EarningsCalendar, EarningsEvent, EarningsTime,
        EstimateTracker, HistoryAnalyzer, QualityAnalyzer,
        ReactionAnalyzer, EarningsAlertManager,
        generate_sample_calendar, generate_sample_estimates,
        generate_sample_history, FinancialData,
        SurpriseType, QualityRating,
    )
    EARNINGS_AVAILABLE = True
except ImportError as e:
    EARNINGS_AVAILABLE = False
    st.error(f"Earnings module not available: {e}")


def render_calendar_tab():
    """Render earnings calendar tab."""
    st.subheader("Upcoming Earnings")
    
    calendar = generate_sample_calendar()
    
    # View selector
    col1, col2 = st.columns([1, 3])
    with col1:
        days_ahead = st.selectbox("View", options=[7, 14, 30], index=0)
    
    # Get upcoming events
    upcoming = calendar.get_upcoming(days=days_ahead)
    
    if not upcoming:
        st.info("No earnings scheduled in this period")
        return
    
    # Summary
    st.metric("Total Earnings", len(upcoming))
    
    # Calendar view
    data = []
    for event in upcoming:
        surprise_str = ""
        if event.is_reported and event.surprise_type:
            if event.surprise_type == SurpriseType.BEAT:
                surprise_str = "✅ Beat"
            elif event.surprise_type == SurpriseType.MISS:
                surprise_str = "❌ Miss"
            else:
                surprise_str = "➖ Met"
        
        data.append({
            "Date": event.report_date.strftime("%a %m/%d") if event.report_date else "",
            "Time": event.report_time.value.upper(),
            "Symbol": event.symbol,
            "Company": event.company_name,
            "EPS Est": f"${event.eps_estimate:.2f}" if event.eps_estimate else "-",
            "Rev Est": f"${event.revenue_estimate/1e9:.1f}B" if event.revenue_estimate else "-",
            "Result": surprise_str,
        })
    
    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    # Today's earnings
    st.markdown("---")
    st.subheader("Today's Earnings")
    
    today_events = calendar.get_day(date.today())
    if today_events:
        bmo = [e for e in today_events if e.report_time == EarningsTime.BEFORE_MARKET]
        amc = [e for e in today_events if e.report_time == EarningsTime.AFTER_MARKET]
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Before Market Open**")
            for e in bmo:
                st.write(f"• {e.symbol} ({e.company_name})")
        with col2:
            st.markdown("**After Market Close**")
            for e in amc:
                st.write(f"• {e.symbol} ({e.company_name})")
    else:
        st.info("No earnings scheduled for today")


def render_estimates_tab():
    """Render estimates tracking tab."""
    st.subheader("Analyst Estimates")
    
    tracker = generate_sample_estimates()
    
    # Symbol selector
    symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA"]
    selected = st.selectbox("Select Symbol", options=symbols)
    
    estimate = tracker.get_estimate(selected, "Q4 2025")
    
    if not estimate:
        st.warning("No estimates available")
        return
    
    # Display estimates
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**EPS Estimates**")
        st.metric("Consensus", f"${estimate.eps_consensus:.2f}")
        st.write(f"High: ${estimate.eps_high:.2f}")
        st.write(f"Low: ${estimate.eps_low:.2f}")
        st.write(f"Analysts: {estimate.eps_num_analysts}")
    
    with col2:
        st.markdown("**Revenue Estimates**")
        st.metric("Consensus", f"${estimate.revenue_consensus/1e9:.1f}B")
        st.write(f"High: ${estimate.revenue_high/1e9:.1f}B")
        st.write(f"Low: ${estimate.revenue_low/1e9:.1f}B")
    
    with col3:
        st.markdown("**Revisions (30 days)**")
        st.write(f"⬆️ Up: {estimate.eps_revisions_up}")
        st.write(f"⬇️ Down: {estimate.eps_revisions_down}")
        
        trend = estimate.revision_trend
        if trend == "positive":
            st.success("Trend: Positive")
        elif trend == "negative":
            st.error("Trend: Negative")
        else:
            st.info("Trend: Neutral")
    
    # YoY comparison
    if estimate.eps_year_ago:
        st.markdown("---")
        st.markdown("**Year-over-Year Comparison**")
        
        yoy = tracker.compare_to_year_ago(selected, "Q4 2025")
        
        col1, col2 = st.columns(2)
        with col1:
            if yoy.get("eps_growth"):
                st.metric(
                    "EPS Growth",
                    f"{yoy['eps_growth']:.1%}",
                    f"vs ${estimate.eps_year_ago:.2f} last year"
                )
        with col2:
            if yoy.get("revenue_growth"):
                st.metric(
                    "Revenue Growth",
                    f"{yoy['revenue_growth']:.1%}"
                )


def render_history_tab():
    """Render earnings history tab."""
    st.subheader("Earnings History")
    
    analyzer = generate_sample_history()
    
    # Symbol selector
    history = analyzer.get_history("AAPL")
    
    if not history:
        st.warning("No history available")
        return
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("EPS Beat Rate", f"{history.beat_rate_eps:.0%}")
    col2.metric("Rev Beat Rate", f"{history.beat_rate_revenue:.0%}")
    col3.metric("Avg EPS Surprise", f"{history.avg_surprise_eps:.1%}")
    col4.metric("Consecutive Beats", history.consecutive_beats)
    
    # Quarterly history table
    st.markdown("---")
    st.markdown("**Quarterly Results**")
    
    data = []
    for q in history.quarters:
        surprise_icon = ""
        if q.surprise_type == SurpriseType.BEAT:
            surprise_icon = "✅"
        elif q.surprise_type == SurpriseType.MISS:
            surprise_icon = "❌"
        else:
            surprise_icon = "➖"
        
        data.append({
            "Quarter": q.fiscal_quarter,
            "Date": q.report_date.strftime("%Y-%m-%d") if q.report_date else "",
            "EPS Est": f"${q.eps_estimate:.2f}",
            "EPS Act": f"${q.eps_actual:.2f}",
            "Surprise": f"{q.eps_surprise_pct:.1%} {surprise_icon}",
            "1D Move": f"{q.price_change_1d:.1%}",
            "5D Move": f"{q.price_change_5d:.1%}",
        })
    
    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    # Pattern analysis
    pattern = analyzer.get_surprise_pattern("AAPL")
    if pattern:
        st.markdown("---")
        st.markdown("**Pattern Analysis**")
        st.write(f"Pattern: **{pattern.get('pattern', 'unknown').replace('_', ' ').title()}**")
        st.write(f"Beats: {pattern.get('beats', 0)} | Meets: {pattern.get('meets', 0)} | Misses: {pattern.get('misses', 0)}")


def render_quality_tab():
    """Render earnings quality tab."""
    st.subheader("Earnings Quality Analysis")
    
    st.info("Enter financial data or select a sample stock to analyze earnings quality.")
    
    # Sample data
    if st.button("Analyze Sample (High Quality)"):
        data = FinancialData(
            revenue=100e9,
            gross_profit=40e9,
            net_income=20e9,
            operating_cash_flow=25e9,
            receivables=15e9,
            current_assets=50e9,
            total_assets=200e9,
            ppe=80e9,
            total_liabilities=100e9,
            depreciation=10e9,
            sga_expense=10e9,
            revenue_prior=90e9,
            gross_profit_prior=36e9,
            receivables_prior=12e9,
            current_assets_prior=45e9,
            total_assets_prior=180e9,
            ppe_prior=75e9,
            depreciation_prior=9e9,
            sga_expense_prior=9e9,
        )
        
        analyzer = QualityAnalyzer()
        quality = analyzer.analyze("SAMPLE", data)
        
        # Display results
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Overall Quality Score", f"{quality.overall_quality_score:.0f}/100")
            
            rating_color = {
                QualityRating.HIGH: "🟢",
                QualityRating.MEDIUM: "🟡",
                QualityRating.LOW: "🟠",
                QualityRating.WARNING: "🔴",
            }
            st.write(f"Rating: {rating_color.get(quality.quality_rating, '')} {quality.quality_rating.value.title()}")
        
        with col2:
            st.metric("Beneish M-Score", f"{quality.beneish_m_score:.2f}")
            if quality.is_manipulation_risk:
                st.error("⚠️ Manipulation Risk Detected")
            else:
                st.success("✓ No Manipulation Risk")
        
        with col3:
            st.metric("Cash Conversion", f"{quality.cash_conversion:.2f}x")
            st.metric("Accruals Ratio", f"{quality.accruals_ratio:.1%}")
        
        # Red flags
        if quality.red_flags:
            st.markdown("---")
            st.markdown("**⚠️ Red Flags**")
            for flag in quality.red_flags:
                st.write(f"• {flag}")
        
        # M-Score components
        st.markdown("---")
        with st.expander("M-Score Components"):
            components = {
                "DSRI (Days Sales Receivable Index)": quality.dsri,
                "GMI (Gross Margin Index)": quality.gmi,
                "AQI (Asset Quality Index)": quality.aqi,
                "SGI (Sales Growth Index)": quality.sgi,
                "DEPI (Depreciation Index)": quality.depi,
                "SGAI (SGA Expense Index)": quality.sgai,
                "LVGI (Leverage Index)": quality.lvgi,
                "TATA (Total Accruals/Total Assets)": quality.tata,
            }
            
            for name, value in components.items():
                st.write(f"• {name}: {value:.3f}")


def render_alerts_tab():
    """Render earnings alerts tab."""
    st.subheader("Earnings Alerts")
    
    calendar = generate_sample_calendar()
    manager = EarningsAlertManager()
    
    # Check for upcoming alerts
    upcoming = calendar.get_upcoming(days=7)
    alerts = manager.check_upcoming_earnings(upcoming)
    
    st.write(f"**{len(alerts)} Active Alerts**")
    
    if not alerts:
        st.info("No alerts at this time")
        return
    
    for alert in alerts:
        with st.container():
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"**{alert.title}**")
                st.write(alert.message)
            with col2:
                st.caption(alert.alert_type.value.title())
            st.markdown("---")


def main():
    if not EARNINGS_AVAILABLE:
        return
    
    # Tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📅 Calendar",
        "📊 Estimates",
        "📈 History",
        "✅ Quality",
        "🔔 Alerts",
    ])
    
    with tab1:
        render_calendar_tab()
    
    with tab2:
        render_estimates_tab()
    
    with tab3:
        render_history_tab()
    
    with tab4:
        render_quality_tab()
    
    with tab5:
        render_alerts_tab()


if __name__ == "__main__":
    main()
