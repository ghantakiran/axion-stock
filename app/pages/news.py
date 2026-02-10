"""News & Events Dashboard."""

import streamlit as st
from app.styles import inject_global_styles
import pandas as pd
from datetime import date, datetime, timedelta, timezone

try:
    st.set_page_config(page_title="News & Events", layout="wide")
except st.errors.StreamlitAPIException:
    pass

inject_global_styles()

st.title("📰 News & Events")

# Try to import news module
try:
    from src.news import (
        NewsFeedManager, EarningsCalendar, EconomicCalendar,
        SECFilingsTracker, CorporateEventsTracker, NewsAlertManager,
        NewsArticle, EarningsEvent, EconomicEvent, SECFiling,
        DividendEvent, InsiderTransaction,
        NewsCategory, NewsSource, ReportTime, EventImportance,
        EconomicCategory, FilingType, DividendFrequency,
        AlertTrigger,
    )
    NEWS_AVAILABLE = True
except ImportError as e:
    NEWS_AVAILABLE = False
    st.error(f"News module not available: {e}")


def init_session_state():
    """Initialize session state with demo data."""
    if "news_feed" not in st.session_state:
        manager = NewsFeedManager()
        
        # Add demo articles
        articles = [
            ("AAPL beats Q4 earnings expectations, revenue up 8%", "AAPL", NewsCategory.EARNINGS, 0.7),
            ("Fed signals potential rate cut in March meeting", "", NewsCategory.MACRO, 0.3),
            ("MSFT announces $10B AI investment partnership", "MSFT", NewsCategory.PRODUCT, 0.6),
            ("TSLA misses delivery estimates for Q4", "TSLA", NewsCategory.EARNINGS, -0.5),
            ("NVDA stock surges on data center demand", "NVDA", NewsCategory.ANALYST, 0.8),
            ("Amazon expands same-day delivery network", "AMZN", NewsCategory.PRODUCT, 0.4),
            ("Google faces DOJ antitrust trial verdict", "GOOGL", NewsCategory.REGULATORY, -0.3),
            ("META launches new VR headset at lower price", "META", NewsCategory.PRODUCT, 0.5),
        ]
        
        for i, (headline, symbol, category, sentiment) in enumerate(articles):
            manager.add_article(NewsArticle(
                headline=headline,
                summary=f"Full story about {headline.lower()}...",
                source=list(NewsSource)[i % len(list(NewsSource))],
                symbols=[symbol] if symbol else [],
                categories=[category],
                sentiment_score=sentiment,
                published_at=datetime.now(timezone.utc) - timedelta(hours=i * 2),
                is_breaking=(i == 0),
            ))
        
        st.session_state.news_feed = manager
    
    if "earnings_calendar" not in st.session_state:
        calendar = EarningsCalendar()
        
        # Add upcoming earnings
        earnings_data = [
            ("AAPL", "Apple Inc.", 5, ReportTime.AMC, 2.10, 120e9),
            ("MSFT", "Microsoft Corp", 8, ReportTime.AMC, 2.75, 65e9),
            ("GOOGL", "Alphabet Inc.", 12, ReportTime.AMC, 1.65, 85e9),
            ("AMZN", "Amazon.com Inc.", 3, ReportTime.AMC, 0.85, 155e9),
            ("NVDA", "NVIDIA Corp", 15, ReportTime.AMC, 5.00, 28e9),
        ]
        
        for symbol, name, days, time, eps_est, rev_est in earnings_data:
            calendar.add_event(EarningsEvent(
                symbol=symbol,
                company_name=name,
                report_date=date.today() + timedelta(days=days),
                report_time=time,
                fiscal_quarter=f"Q1 2024",
                eps_estimate=eps_est,
                revenue_estimate=rev_est,
                num_analysts=25,
            ))
        
        st.session_state.earnings_calendar = calendar
    
    if "economic_calendar" not in st.session_state:
        calendar = EconomicCalendar()
        
        # Add economic events
        econ_data = [
            ("FOMC Meeting", EconomicCategory.CENTRAL_BANK, 3, EventImportance.HIGH),
            ("Non-Farm Payrolls", EconomicCategory.EMPLOYMENT, 7, EventImportance.HIGH),
            ("CPI", EconomicCategory.INFLATION, 10, EventImportance.HIGH),
            ("Retail Sales", EconomicCategory.GROWTH, 5, EventImportance.MEDIUM),
            ("Initial Jobless Claims", EconomicCategory.EMPLOYMENT, 2, EventImportance.MEDIUM),
            ("GDP (Q4)", EconomicCategory.GROWTH, 14, EventImportance.HIGH),
        ]
        
        for name, category, days, importance in econ_data:
            calendar.add_event(EconomicEvent(
                name=name,
                category=category,
                country="US",
                release_date=datetime.now(timezone.utc) + timedelta(days=days),
                importance=importance,
            ))
        
        st.session_state.economic_calendar = calendar
    
    if "sec_tracker" not in st.session_state:
        st.session_state.sec_tracker = SECFilingsTracker()
    
    if "corporate_events" not in st.session_state:
        tracker = CorporateEventsTracker()
        
        # Add dividends
        for symbol, amount in [("AAPL", 0.24), ("MSFT", 0.75), ("JNJ", 1.24)]:
            tracker.add_dividend(DividendEvent(
                symbol=symbol,
                ex_date=date.today() + timedelta(days=10),
                amount=amount,
                frequency=DividendFrequency.QUARTERLY,
            ))
        
        st.session_state.corporate_events = tracker


def render_news_feed():
    """Render the news feed tab."""
    st.subheader("📰 Latest News")
    
    news = st.session_state.news_feed
    
    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        symbol_filter = st.text_input("Filter by Symbol", placeholder="e.g., AAPL")
    with col2:
        category_filter = st.selectbox(
            "Category",
            options=["All"] + [c.value.title() for c in NewsCategory],
        )
    with col3:
        sentiment_filter = st.selectbox(
            "Sentiment",
            options=["All", "Positive", "Negative"],
        )
    
    # Get filtered articles
    categories = None
    if category_filter != "All":
        categories = [NewsCategory(category_filter.lower())]
    
    min_sent = None
    max_sent = None
    if sentiment_filter == "Positive":
        min_sent = 0.2
    elif sentiment_filter == "Negative":
        max_sent = -0.2
    
    articles = news.get_feed(
        symbols=[symbol_filter.upper()] if symbol_filter else None,
        categories=categories,
        min_sentiment=min_sent,
        max_sentiment=max_sent,
        limit=20,
    )
    
    if articles:
        for article in articles:
            with st.container():
                col1, col2 = st.columns([5, 1])
                
                with col1:
                    # Breaking badge
                    prefix = "🔴 BREAKING: " if article.is_breaking else ""
                    st.markdown(f"**{prefix}{article.headline}**")
                    st.caption(
                        f"{article.source.value.title()} • "
                        f"{article.symbols[0] if article.symbols else 'Market'} • "
                        f"{article.age_hours:.0f}h ago"
                    )
                
                with col2:
                    # Sentiment indicator
                    if article.sentiment_score > 0.2:
                        st.markdown("🟢 Positive")
                    elif article.sentiment_score < -0.2:
                        st.markdown("🔴 Negative")
                    else:
                        st.markdown("⚪ Neutral")
                
                st.divider()
    else:
        st.info("No articles match your filters")
    
    # Sentiment summary
    st.markdown("---")
    st.subheader("📊 Sentiment Summary")
    summary = news.get_sentiment_summary(days=7)
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Articles", summary["total_articles"])
    col2.metric("Avg Sentiment", f"{summary['average_sentiment']:.2f}")
    col3.metric("Positive", f"{summary.get('positive_pct', 0):.0f}%")
    col4.metric("Negative", f"{summary.get('negative_pct', 0):.0f}%")


def render_earnings_calendar():
    """Render the earnings calendar tab."""
    st.subheader("📅 Earnings Calendar")
    
    calendar = st.session_state.earnings_calendar
    
    # View options
    view = st.radio("View", ["Upcoming", "This Week", "By Symbol"], horizontal=True)
    
    if view == "Upcoming":
        days = st.slider("Days Ahead", 7, 30, 14)
        events = calendar.get_upcoming(days=days)
    elif view == "This Week":
        events = calendar.get_this_week()
    else:
        symbol = st.text_input("Symbol", value="AAPL").upper()
        events = calendar.get_for_symbol(symbol, quarters=8)
    
    if events:
        data = []
        for e in events:
            data.append({
                "Symbol": e.symbol,
                "Company": e.company_name[:20] + "..." if len(e.company_name) > 20 else e.company_name,
                "Date": e.report_date.strftime("%Y-%m-%d"),
                "Time": e.report_time.value.upper(),
                "Quarter": e.fiscal_quarter,
                "EPS Est": f"${e.eps_estimate:.2f}" if e.eps_estimate else "-",
                "EPS Act": f"${e.eps_actual:.2f}" if e.eps_actual else "-",
                "Surprise": f"{e.eps_surprise_pct:.1f}%" if e.eps_surprise_pct else "-",
            })
        
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Stats
        st.markdown("---")
        col1, col2 = st.columns(2)
        col1.metric("Upcoming Reports", len([e for e in events if not e.is_reported]))
        col2.metric("Reported", len([e for e in events if e.is_reported]))
    else:
        st.info("No earnings events found")


def render_economic_calendar():
    """Render the economic calendar tab."""
    st.subheader("🌍 Economic Calendar")
    
    calendar = st.session_state.economic_calendar
    
    # Filters
    col1, col2 = st.columns(2)
    with col1:
        importance = st.selectbox(
            "Minimum Importance",
            options=["All", "High", "Medium"],
        )
    with col2:
        days = st.slider("Days Ahead", 7, 30, 14)
    
    min_imp = None
    if importance == "High":
        min_imp = EventImportance.HIGH
    elif importance == "Medium":
        min_imp = EventImportance.MEDIUM
    
    events = calendar.get_upcoming(days=days, min_importance=min_imp)
    
    if events:
        data = []
        for e in events:
            imp_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(e.importance.value, "⚪")
            data.append({
                "Event": e.name,
                "Date": e.release_date.strftime("%Y-%m-%d %H:%M"),
                "Category": e.category.value.replace("_", " ").title(),
                "Country": e.country,
                "Importance": f"{imp_emoji} {e.importance.value.title()}",
                "Forecast": f"{e.forecast}{e.unit}" if e.forecast else "-",
                "Previous": f"{e.previous}{e.unit}" if e.previous else "-",
            })
        
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # High impact events
        high_impact = [e for e in events if e.importance == EventImportance.HIGH]
        if high_impact:
            st.markdown("---")
            st.warning(f"⚠️ {len(high_impact)} high-impact events in the next {days} days")
    else:
        st.info("No economic events found")


def render_sec_filings():
    """Render the SEC filings tab."""
    st.subheader("📋 SEC Filings")
    
    tracker = st.session_state.sec_tracker
    
    # Demo data notice
    st.info("SEC filings integration requires API connection. Showing demo interface.")
    
    # Search
    col1, col2 = st.columns(2)
    with col1:
        symbol = st.text_input("Symbol", value="AAPL", key="sec_symbol").upper()
    with col2:
        form_type = st.selectbox(
            "Form Type",
            options=["All", "10-K", "10-Q", "8-K", "4 (Insider)"],
        )
    
    # Demo filings
    demo_filings = [
        {"Symbol": symbol, "Form": "10-Q", "Filed": "2024-01-15", "Description": "Quarterly Report"},
        {"Symbol": symbol, "Form": "8-K", "Filed": "2024-01-10", "Description": "Current Report - Material Event"},
        {"Symbol": symbol, "Form": "4", "Filed": "2024-01-08", "Description": "Insider Transaction"},
    ]
    
    st.dataframe(pd.DataFrame(demo_filings), use_container_width=True, hide_index=True)
    
    # Insider transactions
    st.markdown("---")
    st.subheader("👔 Recent Insider Transactions")
    
    insider_data = [
        {"Symbol": "AAPL", "Insider": "Tim Cook (CEO)", "Type": "Sell", "Shares": "50,000", "Value": "$8.7M", "Date": "2024-01-05"},
        {"Symbol": "MSFT", "Insider": "Satya Nadella (CEO)", "Type": "Sell", "Shares": "30,000", "Value": "$11.4M", "Date": "2024-01-03"},
        {"Symbol": "NVDA", "Insider": "Jensen Huang (CEO)", "Type": "Sell", "Shares": "100,000", "Value": "$48.5M", "Date": "2024-01-02"},
    ]
    
    st.dataframe(pd.DataFrame(insider_data), use_container_width=True, hide_index=True)


def render_dividends():
    """Render the dividends/corporate events tab."""
    st.subheader("💰 Dividends & Corporate Events")
    
    events = st.session_state.corporate_events
    
    # Upcoming dividends
    st.markdown("**Upcoming Ex-Dividend Dates**")
    
    dividends = events.get_upcoming_dividends(days=30)
    
    if dividends:
        data = []
        for d in dividends:
            data.append({
                "Symbol": d.symbol,
                "Ex-Date": d.ex_date.strftime("%Y-%m-%d"),
                "Amount": f"${d.amount:.4f}",
                "Frequency": d.frequency.value.title(),
                "Annualized": f"${d.annualized_amount:.2f}",
            })
        
        st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
    else:
        st.info("No upcoming dividends")
    
    # Corporate events
    st.markdown("---")
    st.markdown("**Recent Corporate Events**")
    
    corp_events = [
        {"Symbol": "TSLA", "Event": "Stock Split", "Date": "2024-02-15", "Details": "3:1 split"},
        {"Symbol": "AVGO", "Event": "Acquisition", "Date": "2024-01-20", "Details": "VMware acquisition complete"},
    ]
    
    st.dataframe(pd.DataFrame(corp_events), use_container_width=True, hide_index=True)


def render_alerts():
    """Render the alerts configuration tab."""
    st.subheader("🔔 News Alerts")
    
    # Demo alerts
    st.markdown("**Your Alerts**")
    
    alerts_data = [
        {"Name": "Portfolio Earnings", "Trigger": "Earnings Announce", "Symbols": "AAPL, MSFT, GOOGL", "Status": "✅ Active"},
        {"Name": "Breaking News", "Trigger": "Breaking News", "Symbols": "All", "Status": "✅ Active"},
        {"Name": "Insider Buys", "Trigger": "Insider Transaction", "Symbols": "All", "Status": "⏸️ Paused"},
    ]
    
    st.dataframe(pd.DataFrame(alerts_data), use_container_width=True, hide_index=True)
    
    # Create new alert
    st.markdown("---")
    st.markdown("**Create New Alert**")
    
    col1, col2 = st.columns(2)
    with col1:
        alert_name = st.text_input("Alert Name", placeholder="My Alert")
        trigger = st.selectbox(
            "Trigger",
            options=[t.value.replace("_", " ").title() for t in AlertTrigger],
        )
    with col2:
        symbols = st.text_input("Symbols (comma-separated)", placeholder="AAPL, MSFT")
        channels = st.multiselect("Channels", options=["In-App", "Email", "Push"], default=["In-App"])
    
    if st.button("Create Alert", type="primary"):
        st.success(f"Alert '{alert_name}' created!")


def main():
    if not NEWS_AVAILABLE:
        return
    
    init_session_state()
    
    # Main tabs
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📰 News Feed",
        "📅 Earnings",
        "🌍 Economic",
        "📋 SEC Filings",
        "💰 Dividends",
        "🔔 Alerts",
    ])
    
    with tab1:
        render_news_feed()
    
    with tab2:
        render_earnings_calendar()
    
    with tab3:
        render_economic_calendar()
    
    with tab4:
        render_sec_filings()
    
    with tab5:
        render_dividends()
    
    with tab6:
        render_alerts()



main()
