"""Economic Calendar Dashboard."""

import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta

st.set_page_config(page_title="Economic Calendar", layout="wide")
st.title("📅 Economic Calendar")

# Try to import economic module
try:
    from src.economic import (
        EconomicCalendar, EconomicEvent, ImpactLevel, EventCategory, Country,
        HistoryAnalyzer, ImpactAnalyzer,
        FedWatcher, RateDecision,
        EconomicAlertManager, create_default_alerts,
        generate_sample_calendar, generate_sample_history, generate_sample_fed_data,
        CATEGORY_INFO,
    )
    ECONOMIC_AVAILABLE = True
except ImportError as e:
    ECONOMIC_AVAILABLE = False
    st.error(f"Economic module not available: {e}")


def render_calendar_tab():
    """Render main calendar tab."""
    st.subheader("Upcoming Economic Events")
    
    calendar = generate_sample_calendar()
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        days_ahead = st.selectbox(
            "Time Range",
            options=[7, 14, 30],
            format_func=lambda x: f"Next {x} days",
        )
    
    with col2:
        impact_filter = st.selectbox(
            "Impact Level",
            options=["All", "High", "Medium", "Low"],
        )
    
    with col3:
        country_filter = st.selectbox(
            "Country",
            options=["All", "US", "EU", "UK"],
        )
    
    # Get events
    min_impact = None
    if impact_filter != "All":
        min_impact = ImpactLevel(impact_filter.lower())
    
    country = None
    if country_filter != "All":
        country = Country(country_filter)
    
    events = calendar.get_upcoming(
        days=days_ahead,
        min_impact=min_impact,
        country=country,
    )
    
    if not events:
        st.info("No events found for the selected filters")
        return
    
    # Display events
    st.markdown(f"### {len(events)} Events")
    
    # Group by date
    events_by_date = {}
    for event in events:
        if event.release_date:
            if event.release_date not in events_by_date:
                events_by_date[event.release_date] = []
            events_by_date[event.release_date].append(event)
    
    for event_date in sorted(events_by_date.keys()):
        day_name = event_date.strftime("%A, %B %d")
        if event_date == date.today():
            day_name += " (Today)"
        elif event_date == date.today() + timedelta(days=1):
            day_name += " (Tomorrow)"
        
        st.markdown(f"#### {day_name}")
        
        data = []
        for event in events_by_date[event_date]:
            impact_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(event.impact.value, "⚪")
            time_str = event.release_time.strftime("%H:%M") if event.release_time else "TBA"
            
            data.append({
                "Time": time_str,
                "Impact": impact_icon,
                "Event": event.name,
                "Previous": f"{event.previous}{event.unit}" if event.previous else "-",
                "Forecast": f"{event.forecast}{event.unit}" if event.forecast else "-",
                "Actual": f"{event.actual}{event.unit}" if event.actual else "-",
            })
        
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True, hide_index=True)


def render_history_tab():
    """Render historical analysis tab."""
    st.subheader("Historical Analysis")
    
    analyzer = generate_sample_history()
    
    # Event selector
    event_options = ["Non-Farm Payrolls", "CPI"]
    selected_event = st.selectbox("Select Event", options=event_options)
    
    # Get stats
    stats = analyzer.get_stats(selected_event)
    
    if stats.total_releases == 0:
        st.info("No historical data available")
        return
    
    # Display stats
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Releases", stats.total_releases)
    
    with col2:
        st.metric("Beat Rate", f"{stats.beat_rate:.0f}%")
    
    with col3:
        st.metric("Avg Surprise", f"{stats.avg_surprise_pct:.1f}%")
    
    with col4:
        st.metric("Avg SPX Reaction", f"{stats.avg_spx_reaction:+.2f}%")
    
    st.markdown("---")
    
    # Historical releases
    st.markdown("**Recent Releases:**")
    
    history = analyzer.get_history(selected_event, limit=10)
    
    data = []
    for release in history:
        data.append({
            "Date": release.release_date.strftime("%Y-%m-%d") if release.release_date else "-",
            "Actual": f"{release.actual:.1f}",
            "Forecast": f"{release.forecast:.1f}",
            "Surprise": f"{release.surprise:+.1f}",
            "SPX 1H": f"{release.spx_1h_change:+.2f}%",
            "VIX": f"{release.vix_change:+.1f}",
        })
    
    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    # Typical reactions
    st.markdown("---")
    st.markdown("**Typical Market Reactions:**")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**On Beat:**")
        beat_reaction = analyzer.get_typical_reaction(selected_event, "beat")
        st.write(f"• SPX: {beat_reaction['avg_spx']:+.2f}%")
        st.write(f"• VIX: {beat_reaction['avg_vix']:+.1f}")
        st.write(f"• Count: {beat_reaction['count']}")
    
    with col2:
        st.markdown("**On Miss:**")
        miss_reaction = analyzer.get_typical_reaction(selected_event, "miss")
        st.write(f"• SPX: {miss_reaction['avg_spx']:+.2f}%")
        st.write(f"• VIX: {miss_reaction['avg_vix']:+.1f}")
        st.write(f"• Count: {miss_reaction['count']}")


def render_fed_tab():
    """Render Fed Watch tab."""
    st.subheader("Fed Watch")
    
    fed = generate_sample_fed_data()
    
    # Current rate
    current_rate = fed.get_current_rate()
    st.metric("Current Fed Funds Rate", f"{current_rate:.2f}%")
    
    st.markdown("---")
    
    # Next meeting
    next_meeting = fed.get_next_meeting()
    if next_meeting:
        st.markdown("### Next FOMC Meeting")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.write(f"**Date:** {next_meeting.meeting_date}")
        
        with col2:
            st.write(f"**Type:** {next_meeting.meeting_type}")
        
        with col3:
            st.write(f"**SEP:** {'Yes' if next_meeting.has_projections else 'No'}")
        
        # Rate expectations
        exp = fed.get_expectations(next_meeting.meeting_date)
        if exp:
            st.markdown("**Rate Expectations:**")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("P(Hike)", f"{exp.prob_hike_25 + exp.prob_hike_50:.0f}%")
            
            with col2:
                st.metric("P(Hold)", f"{exp.prob_hold:.0f}%")
            
            with col3:
                st.metric("P(Cut)", f"{exp.prob_cut_25 + exp.prob_cut_50:.0f}%")
    
    st.markdown("---")
    
    # Upcoming meetings
    st.markdown("### FOMC Calendar")
    
    upcoming = fed.get_upcoming_meetings(limit=6)
    
    data = []
    for meeting in upcoming:
        data.append({
            "Date": meeting.meeting_date.strftime("%b %d, %Y") if meeting.meeting_date else "-",
            "Type": meeting.meeting_type,
            "SEP": "✓" if meeting.has_projections else "",
        })
    
    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    
    # Rate history
    st.markdown("### Recent Decisions")
    
    past = fed.get_past_meetings(limit=5)
    
    data = []
    for meeting in past:
        decision_icon = {
            RateDecision.HIKE: "⬆️",
            RateDecision.CUT: "⬇️",
            RateDecision.HOLD: "➡️",
        }.get(meeting.rate_decision, "-")
        
        data.append({
            "Date": meeting.meeting_date.strftime("%b %d, %Y") if meeting.meeting_date else "-",
            "Decision": f"{decision_icon} {meeting.rate_decision.value.title() if meeting.rate_decision else '-'}",
            "Rate": f"{meeting.rate_after:.2f}%" if meeting.rate_after else "-",
            "Tone": meeting.statement_tone.title() if meeting.statement_tone else "-",
        })
    
    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, hide_index=True)


def render_impact_tab():
    """Render market impact tab."""
    st.subheader("Market Impact Analysis")
    
    calendar = generate_sample_calendar()
    history = generate_sample_history()
    analyzer = ImpactAnalyzer(history)
    
    # Get upcoming high-impact events
    events = calendar.get_upcoming(days=14, min_impact=ImpactLevel.HIGH)
    
    if not events:
        st.info("No high-impact events in the next 14 days")
        return
    
    # Event selector
    event_names = [f"{e.name} ({e.release_date})" for e in events]
    selected_idx = st.selectbox(
        "Select Event",
        options=range(len(events)),
        format_func=lambda i: event_names[i],
    )
    
    event = events[selected_idx]
    impact = analyzer.analyze_event(event)
    
    st.markdown("---")
    
    # Impact metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        vol_indicator = {"HIGH": "🔴 High", "MEDIUM": "🟡 Medium", "LOW": "🟢 Low"}
        st.metric("Impact Level", vol_indicator.get(event.impact.value.upper(), event.impact.value))
    
    with col2:
        st.metric("Expected Volatility", f"{impact.expected_volatility:.1f}x")
    
    with col3:
        st.metric("Typical Move", f"±{abs(impact.historical_avg_move):.2f}%")
    
    st.markdown("---")
    
    # Pre-event notes
    st.markdown("**Trading Notes:**")
    for note in impact.pre_event_notes:
        st.write(note)
    
    st.markdown("---")
    
    # Sector impacts
    if impact.sector_impacts:
        st.markdown("**Sector Sensitivity:**")
        
        data = []
        for sector, sensitivity in sorted(impact.sector_impacts.items(), key=lambda x: x[1], reverse=True):
            bar = "█" * int(sensitivity * 5)
            data.append({
                "Sector": sector,
                "Sensitivity": f"{sensitivity:.1f}x",
                "Impact": bar,
            })
        
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True, hide_index=True)


def render_sidebar():
    """Render sidebar with today's events."""
    st.sidebar.header("Today's Events")
    
    calendar = generate_sample_calendar()
    today_events = calendar.get_today()
    
    if not today_events:
        st.sidebar.info("No events today")
    else:
        for event in today_events:
            impact_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(event.impact.value, "⚪")
            time_str = event.release_time.strftime("%H:%M") if event.release_time else "TBA"
            st.sidebar.write(f"{impact_icon} **{time_str}** - {event.name}")
    
    st.sidebar.markdown("---")
    st.sidebar.header("Quick Links")
    st.sidebar.markdown("• [Fed Calendar](https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm)")
    st.sidebar.markdown("• [BLS Releases](https://www.bls.gov/schedule/)")


def main():
    if not ECONOMIC_AVAILABLE:
        return
    
    # Sidebar
    render_sidebar()
    
    # Main tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📅 Calendar",
        "📊 History",
        "🏛️ Fed Watch",
        "📈 Impact",
    ])
    
    with tab1:
        render_calendar_tab()
    
    with tab2:
        render_history_tab()
    
    with tab3:
        render_fed_tab()
    
    with tab4:
        render_impact_tab()


if __name__ == "__main__":
    main()
