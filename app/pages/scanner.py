"""Market Scanner Dashboard."""

import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Market Scanner", layout="wide")
st.title("🔍 Market Scanner")

# Try to import scanner module
try:
    from src.scanner import (
        ScannerEngine, Scanner, ScanCriterion, Operator,
        ScanCategory, SCAN_FIELDS,
        UnusualActivityDetector, PatternDetector,
        PRESET_SCANNERS, get_preset_scanner, get_all_presets,
        get_presets_by_category, create_scanner,
    )
    SCANNER_AVAILABLE = True
except ImportError as e:
    SCANNER_AVAILABLE = False
    st.error(f"Scanner module not available: {e}")


def get_sample_market_data():
    """Generate sample market data for demo."""
    return {
        "NVDA": {
            "name": "NVIDIA Corp.",
            "price": 800.0,
            "change": 45.0,
            "change_pct": 5.9,
            "gap_pct": 4.2,
            "volume": 60000000,
            "avg_volume": 25000000,
            "relative_volume": 2.4,
            "rsi": 72,
            "market_cap": 2.0e12,
            "sector": "Technology",
        },
        "AAPL": {
            "name": "Apple Inc.",
            "price": 185.0,
            "change": 5.0,
            "change_pct": 2.8,
            "gap_pct": 1.5,
            "volume": 80000000,
            "avg_volume": 50000000,
            "relative_volume": 1.6,
            "rsi": 55,
            "market_cap": 2.9e12,
            "sector": "Technology",
        },
        "TSLA": {
            "name": "Tesla Inc.",
            "price": 250.0,
            "change": -15.0,
            "change_pct": -5.7,
            "gap_pct": -3.5,
            "volume": 120000000,
            "avg_volume": 40000000,
            "relative_volume": 3.0,
            "rsi": 28,
            "market_cap": 800e9,
            "sector": "Consumer Cyclical",
        },
        "MSFT": {
            "name": "Microsoft Corp.",
            "price": 378.0,
            "change": 8.0,
            "change_pct": 2.2,
            "gap_pct": 1.0,
            "volume": 25000000,
            "avg_volume": 22000000,
            "relative_volume": 1.14,
            "rsi": 58,
            "market_cap": 2.8e12,
            "sector": "Technology",
        },
        "META": {
            "name": "Meta Platforms",
            "price": 480.0,
            "change": 25.0,
            "change_pct": 5.5,
            "gap_pct": 3.8,
            "volume": 30000000,
            "avg_volume": 15000000,
            "relative_volume": 2.0,
            "rsi": 68,
            "market_cap": 1.2e12,
            "sector": "Technology",
        },
        "AMZN": {
            "name": "Amazon.com Inc.",
            "price": 178.0,
            "change": 3.0,
            "change_pct": 1.7,
            "gap_pct": 0.5,
            "volume": 45000000,
            "avg_volume": 40000000,
            "relative_volume": 1.12,
            "rsi": 52,
            "market_cap": 1.9e12,
            "sector": "Consumer Cyclical",
        },
        "XOM": {
            "name": "Exxon Mobil",
            "price": 105.0,
            "change": -2.5,
            "change_pct": -2.3,
            "gap_pct": -1.8,
            "volume": 15000000,
            "avg_volume": 12000000,
            "relative_volume": 1.25,
            "rsi": 42,
            "market_cap": 450e9,
            "sector": "Energy",
        },
        "JPM": {
            "name": "JPMorgan Chase",
            "price": 195.0,
            "change": 4.0,
            "change_pct": 2.1,
            "gap_pct": 1.2,
            "volume": 12000000,
            "avg_volume": 10000000,
            "relative_volume": 1.2,
            "rsi": 60,
            "market_cap": 560e9,
            "sector": "Financial",
        },
    }


def render_preset_scans_tab():
    """Render preset scans tab."""
    st.subheader("Pre-Built Scanners")
    
    engine = ScannerEngine()
    market_data = get_sample_market_data()
    
    # Category filter
    categories = [
        ("All", None),
        ("Price Action", ScanCategory.PRICE_ACTION),
        ("Volume", ScanCategory.VOLUME),
        ("Technical", ScanCategory.TECHNICAL),
        ("Momentum", ScanCategory.MOMENTUM),
    ]
    
    selected_cat = st.selectbox(
        "Category",
        options=[c[0] for c in categories],
    )
    
    cat_filter = next((c[1] for c in categories if c[0] == selected_cat), None)
    
    if cat_filter:
        presets = get_presets_by_category(cat_filter)
    else:
        presets = get_all_presets()
    
    # Scanner selector
    scanner_options = {s.name: s for s in presets}
    selected_scanner_name = st.selectbox(
        "Select Scanner",
        options=list(scanner_options.keys()),
    )
    
    scanner = scanner_options[selected_scanner_name]
    st.info(scanner.description)
    
    # Run scan
    if st.button("Run Scan", type="primary"):
        results = engine.run_scan(scanner, market_data)
        
        st.markdown(f"### Results ({len(results)} matches)")
        
        if not results:
            st.info("No matches found")
        else:
            data = []
            for r in results:
                data.append({
                    "Symbol": r.symbol,
                    "Company": r.company_name,
                    "Price": f"${r.price:.2f}",
                    "Change": f"{r.change_pct:+.1f}%",
                    "Volume": f"{r.volume/1e6:.1f}M",
                    "Rel Vol": f"{r.relative_volume:.1f}x",
                    "Signal": f"{r.signal_strength:.0f}",
                    "Criteria": ", ".join(r.matched_criteria[:2]),
                })
            
            df = pd.DataFrame(data)
            st.dataframe(df, use_container_width=True, hide_index=True)


def render_custom_scan_tab():
    """Render custom scan builder tab."""
    st.subheader("Custom Scan Builder")
    
    engine = ScannerEngine()
    market_data = get_sample_market_data()
    
    # Build criteria
    st.markdown("**Add Criteria:**")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        field = st.selectbox(
            "Field",
            options=list(SCAN_FIELDS.keys()),
            format_func=lambda x: SCAN_FIELDS[x],
        )
    
    with col2:
        operator = st.selectbox(
            "Operator",
            options=[
                ("Greater Than", Operator.GT),
                ("Less Than", Operator.LT),
                ("Between", Operator.BETWEEN),
                ("Greater or Equal", Operator.GTE),
                ("Less or Equal", Operator.LTE),
            ],
            format_func=lambda x: x[0],
        )
    
    with col3:
        if operator[1] == Operator.BETWEEN:
            val1 = st.number_input("Min Value", value=0.0)
            val2 = st.number_input("Max Value", value=100.0)
            value = (val1, val2)
        else:
            value = st.number_input("Value", value=0.0)
    
    # Store criteria in session
    if "custom_criteria" not in st.session_state:
        st.session_state.custom_criteria = []
    
    if st.button("Add Criterion"):
        st.session_state.custom_criteria.append({
            "field": field,
            "operator": operator[1],
            "value": value,
        })
    
    # Show current criteria
    if st.session_state.custom_criteria:
        st.markdown("**Current Criteria:**")
        for i, c in enumerate(st.session_state.custom_criteria):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.write(f"{i+1}. {SCAN_FIELDS[c['field']]} {c['operator'].value} {c['value']}")
            with col2:
                if st.button("❌", key=f"del_{i}"):
                    st.session_state.custom_criteria.pop(i)
                    st.rerun()
        
        if st.button("Clear All"):
            st.session_state.custom_criteria = []
            st.rerun()
    
    # Run custom scan
    if st.session_state.custom_criteria and st.button("Run Custom Scan", type="primary"):
        criteria = [
            (c["field"], c["operator"], c["value"])
            for c in st.session_state.custom_criteria
        ]
        
        scanner = create_scanner("Custom Scan", criteria)
        results = engine.run_scan(scanner, market_data)
        
        st.markdown(f"### Results ({len(results)} matches)")
        
        if not results:
            st.info("No matches found")
        else:
            data = []
            for r in results:
                data.append({
                    "Symbol": r.symbol,
                    "Company": r.company_name,
                    "Price": f"${r.price:.2f}",
                    "Change": f"{r.change_pct:+.1f}%",
                    "Volume": f"{r.volume/1e6:.1f}M",
                    "Sector": r.sector,
                })
            
            df = pd.DataFrame(data)
            st.dataframe(df, use_container_width=True, hide_index=True)


def render_unusual_activity_tab():
    """Render unusual activity tab."""
    st.subheader("Unusual Activity Detection")
    
    detector = UnusualActivityDetector()
    market_data = get_sample_market_data()
    
    # Create historical data
    historical_data = {
        symbol: {
            "avg_volume": data["avg_volume"],
            "std_volume": data["avg_volume"] * 0.3,
            "avg_daily_change": 1.5,
            "std_daily_change": 1.0,
        }
        for symbol, data in market_data.items()
    }
    
    if st.button("Scan for Unusual Activity", type="primary"):
        activities = detector.scan(market_data, historical_data)
        
        if not activities:
            st.info("No unusual activity detected")
        else:
            st.markdown(f"### Detected {len(activities)} Unusual Activities")
            
            # Volume surges
            volume_surges = detector.get_top_volume_surges(10)
            if volume_surges:
                st.markdown("**Volume Surges:**")
                for a in volume_surges:
                    st.write(f"• **{a.symbol}**: {a.description} (Change: {a.change_pct:+.1f}%)")
            
            # Price spikes
            price_spikes = detector.get_top_movers(10)
            if price_spikes:
                st.markdown("**Price Spikes:**")
                for a in price_spikes:
                    st.write(f"• **{a.symbol}**: {a.description}")
            
            # Gaps
            gaps = detector.get_gaps(10)
            if gaps:
                st.markdown("**Significant Gaps:**")
                for a in gaps:
                    st.write(f"• **{a.symbol}**: {a.description}")


def render_quick_scans_sidebar():
    """Render quick scans in sidebar."""
    st.sidebar.header("Quick Scans")
    
    engine = ScannerEngine()
    market_data = get_sample_market_data()
    
    quick_scans = ["gap_up", "volume_spike", "rsi_oversold", "big_gainers"]
    
    for scan_name in quick_scans:
        scanner = get_preset_scanner(scan_name)
        if scanner:
            if st.sidebar.button(f"▶️ {scanner.name}", key=f"quick_{scan_name}"):
                results = engine.run_scan(scanner, market_data)
                
                st.sidebar.markdown(f"**{len(results)} matches:**")
                for r in results[:5]:
                    st.sidebar.write(f"• {r.symbol} ({r.change_pct:+.1f}%)")
                
                if len(results) > 5:
                    st.sidebar.caption(f"...and {len(results)-5} more")


def main():
    if not SCANNER_AVAILABLE:
        return
    
    # Sidebar quick scans
    render_quick_scans_sidebar()
    
    # Main tabs
    tab1, tab2, tab3 = st.tabs([
        "📊 Preset Scans",
        "🛠️ Custom Scan",
        "⚡ Unusual Activity",
    ])
    
    with tab1:
        render_preset_scans_tab()
    
    with tab2:
        render_custom_scan_tab()
    
    with tab3:
        render_unusual_activity_tab()


if __name__ == "__main__":
    main()
