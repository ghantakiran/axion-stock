"""Sector Rotation Dashboard."""

import streamlit as st
import pandas as pd
from datetime import date

try:
    st.set_page_config(page_title="Sector Rotation", layout="wide")
except st.errors.StreamlitAPIException:
    pass

st.title("🔄 Sector Rotation Analysis")

# Try to import sectors module
try:
    from src.sectors import (
        SectorRankings, SectorName, Trend, CyclePhase,
        RotationDetector, SignalStrength,
        CycleAnalyzer,
        RecommendationEngine, Recommendation, Conviction,
        SECTOR_ETFS, SECTOR_CHARACTERISTICS, BENCHMARK_WEIGHTS,
        generate_sample_rankings, generate_sample_cycle,
    )
    SECTORS_AVAILABLE = True
except ImportError as e:
    SECTORS_AVAILABLE = False
    st.error(f"Sectors module not available: {e}")


def render_rankings_tab():
    """Render sector rankings tab."""
    st.subheader("Sector Performance Rankings")
    
    rankings = generate_sample_rankings()
    
    # Timeframe selector
    timeframe = st.selectbox(
        "Sort By",
        ["Momentum Score", "1 Day", "1 Week", "1 Month", "3 Month", "Relative Strength"],
    )
    
    sort_map = {
        "Momentum Score": "momentum",
        "1 Day": "change_1d",
        "1 Week": "change_1w",
        "1 Month": "change_1m",
        "3 Month": "change_3m",
        "Relative Strength": "rs",
    }
    
    sectors = rankings.get_top_sectors(11, by=sort_map[timeframe])
    
    # Build table
    data = []
    for i, s in enumerate(sectors):
        trend_icon = {"up": "🟢", "down": "🔴", "neutral": "🟡"}.get(s.trend.value, "⚪")
        rs_color = "🟢" if s.rs_ratio > 1.0 else "🔴" if s.rs_ratio < 1.0 else "🟡"
        
        data.append({
            "Rank": i + 1,
            "Sector": s.name.value,
            "ETF": s.etf_symbol,
            "Trend": trend_icon,
            "1D": f"{s.change_1d:+.1f}%",
            "1W": f"{s.change_1w:+.1f}%",
            "1M": f"{s.change_1m:+.1f}%",
            "3M": f"{s.change_3m:+.1f}%",
            "RS": f"{rs_color} {s.rs_ratio:.2f}",
            "Score": f"{s.momentum_score:.1f}",
        })
    
    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    # Summary metrics
    st.markdown("---")
    st.markdown("### Market Summary")
    
    col1, col2, col3, col4 = st.columns(4)
    
    spread = rankings.get_performance_spread()
    correlations = rankings.get_sector_correlations()
    
    with col1:
        st.metric("1M Spread", f"{spread['spread_1m']:.1f}%")
    
    with col2:
        st.metric("Uptrending", f"{correlations['sectors_uptrending']}/11")
    
    with col3:
        st.metric("Market Breadth", f"{correlations['market_breadth']:.0f}%")
    
    with col4:
        outperf = len(rankings.get_outperformers())
        st.metric("Outperforming", f"{outperf}/11")


def render_rotation_tab():
    """Render rotation detection tab."""
    st.subheader("Sector Rotation Signals")
    
    rankings = generate_sample_rankings()
    detector = RotationDetector(rankings)
    
    signals = detector.detect_rotation()
    summary = detector.get_rotation_summary()
    
    # Direction indicator
    direction = summary["direction"]
    direction_icon = {"Risk-On": "🟢", "Risk-Off": "🔴", "Mixed": "🟡"}.get(direction, "⚪")
    
    st.markdown(f"### Market Direction: {direction_icon} **{direction}**")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Leading Sectors:**")
        for sector in summary["top_sectors"]:
            st.write(f"• {sector}")
    
    with col2:
        st.markdown("**Lagging Sectors:**")
        for sector in summary["bottom_sectors"]:
            st.write(f"• {sector}")
    
    st.markdown("---")
    
    # Rotation signals
    if signals:
        st.markdown(f"### {len(signals)} Rotation Signals")
        
        for signal in signals[:10]:
            strength_icon = {
                SignalStrength.STRONG: "🔴",
                SignalStrength.MODERATE: "🟡",
                SignalStrength.WEAK: "🟢",
            }.get(signal.signal_strength, "⚪")
            
            st.markdown(f"""
            {strength_icon} **{signal.from_sector.value}** → **{signal.to_sector.value}**
            
            RS Change: {signal.rs_change:.1%} | Confidence: {signal.confidence:.0f}%
            
            ---
            """)
    else:
        st.info("No significant rotation signals detected")
    
    # Active patterns
    patterns = detector.get_active_patterns()
    if patterns:
        st.markdown("### Active Patterns")
        for pattern in patterns:
            st.success(f"**{pattern.name}**: {pattern.description} (Confidence: {pattern.confidence:.0f}%)")


def render_cycle_tab():
    """Render business cycle tab."""
    st.subheader("Business Cycle Analysis")
    
    analyzer = generate_sample_cycle()
    cycle = analyzer.get_current_cycle()
    
    if not cycle:
        st.warning("No cycle analysis available")
        return
    
    # Current phase
    phase_name = cycle.current_phase.value.replace("_", " ").title()
    st.markdown(f"### Current Phase: **{phase_name}**")
    st.markdown(f"*Confidence: {cycle.phase_confidence:.0f}%*")
    
    st.info(analyzer.get_phase_description())
    
    st.markdown("---")
    
    # Economic indicators
    st.markdown("### Economic Indicators")
    
    col1, col2, col3, col4 = st.columns(4)
    
    trend_icon = lambda t: {"up": "📈", "down": "📉", "neutral": "➡️"}.get(t.value, "➡️")
    
    with col1:
        st.metric("GDP", trend_icon(cycle.gdp_trend))
    
    with col2:
        st.metric("Employment", trend_icon(cycle.employment_trend))
    
    with col3:
        st.metric("Inflation", trend_icon(cycle.inflation_trend))
    
    with col4:
        st.metric("Yield Curve", trend_icon(cycle.yield_curve_trend))
    
    st.markdown("---")
    
    # Sector implications
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### Favored Sectors")
        for sector in cycle.overweight_sectors:
            st.success(f"✓ {sector.value}")
    
    with col2:
        st.markdown("### Unfavored Sectors")
        for sector in cycle.underweight_sectors:
            st.error(f"✗ {sector.value}")
    
    # Next phase prediction
    st.markdown("---")
    next_phase, prob = analyzer.predict_next_phase()
    st.markdown(f"**Next Phase Prediction:** {next_phase.value.replace('_', ' ').title()} ({prob*100:.0f}% probability)")


def render_recommendations_tab():
    """Render recommendations tab."""
    st.subheader("Sector Recommendations")
    
    rankings = generate_sample_rankings()
    cycle_analyzer = generate_sample_cycle()
    engine = RecommendationEngine(rankings, cycle_analyzer)
    
    recommendations = engine.generate_recommendations()
    
    # Summary
    overweight = engine.get_overweight_sectors()
    underweight = engine.get_underweight_sectors()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Overweight", len(overweight))
    
    with col2:
        neutral_count = 11 - len(overweight) - len(underweight)
        st.metric("Neutral", neutral_count)
    
    with col3:
        st.metric("Underweight", len(underweight))
    
    st.markdown("---")
    
    # Recommendations table
    st.markdown("### All Recommendations")
    
    data = []
    for rec in recommendations:
        rec_icon = {
            Recommendation.OVERWEIGHT: "🟢 OW",
            Recommendation.NEUTRAL: "🟡 N",
            Recommendation.UNDERWEIGHT: "🔴 UW",
        }.get(rec.recommendation, "N")
        
        conv_icon = {
            Conviction.HIGH: "★★★",
            Conviction.MEDIUM: "★★",
            Conviction.LOW: "★",
        }.get(rec.conviction, "★")
        
        data.append({
            "Sector": rec.sector.value,
            "ETF": rec.etf_symbol,
            "Rating": rec_icon,
            "Conviction": conv_icon,
            "Score": f"{rec.overall_score:.0f}",
            "Momentum": f"{rec.momentum_score:.0f}",
            "RS": f"{rec.relative_strength_score:.0f}",
            "Cycle": f"{rec.cycle_alignment_score:.0f}",
            "Target Wt": f"{rec.target_weight*100:.1f}%",
            "Active Wt": f"{rec.active_weight*100:+.1f}%",
        })
    
    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    # Top picks
    st.markdown("---")
    st.markdown("### Top Picks")
    
    for rec in overweight[:3]:
        with st.expander(f"**{rec.sector.value}** ({rec.etf_symbol}) - Score: {rec.overall_score:.0f}"):
            for rationale in rec.rationale:
                st.write(f"• {rationale}")


def render_sidebar():
    """Render sidebar."""
    st.sidebar.header("Quick View")
    
    rankings = generate_sample_rankings()
    
    st.sidebar.markdown("### Top 3 Sectors")
    for s in rankings.get_top_sectors(3):
        st.sidebar.write(f"🟢 {s.name.value}: {s.change_1m:+.1f}%")
    
    st.sidebar.markdown("### Bottom 3 Sectors")
    for s in rankings.get_bottom_sectors(3):
        st.sidebar.write(f"🔴 {s.name.value}: {s.change_1m:+.1f}%")
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Sector ETFs")
    for name, etf in list(SECTOR_ETFS.items())[:6]:
        st.sidebar.caption(f"{etf}: {name.value}")


def main():
    if not SECTORS_AVAILABLE:
        return
    
    # Sidebar
    render_sidebar()
    
    # Main tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Rankings",
        "🔄 Rotation",
        "📈 Cycle",
        "💡 Recommendations",
    ])
    
    with tab1:
        render_rankings_tab()
    
    with tab2:
        render_rotation_tab()
    
    with tab3:
        render_cycle_tab()
    
    with tab4:
        render_recommendations_tab()



main()
