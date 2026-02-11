"""Advanced Stock Screener Dashboard."""

import streamlit as st
from app.styles import inject_global_styles
import pandas as pd

try:
    st.set_page_config(page_title="Stock Screener", layout="wide")
except st.errors.StreamlitAPIException:
    pass

inject_global_styles()

st.title("🔍 Advanced Stock Screener")

# Try to import screener module
try:
    from src.screener import (
        ScreenerEngine, Screen, FilterCondition, CustomFormula,
        Operator, FilterCategory, FILTER_REGISTRY,
        get_preset_screens, PRESET_SCREENS,
    )
    SCREENER_AVAILABLE = True
except ImportError as e:
    SCREENER_AVAILABLE = False
    st.error(f"Screener module not available: {e}")


def get_demo_stock_data() -> dict:
    """Get demo stock data for screening."""
    return {
        "AAPL": {"name": "Apple Inc.", "sector": "Technology", "price": 185.0, "market_cap": 2.9e12,
                 "pe_ratio": 28.0, "pb_ratio": 45.0, "dividend_yield": 0.5, "revenue_growth": 8.0,
                 "gross_margin": 45.0, "operating_margin": 30.0, "roe": 150.0, "roic": 45.0,
                 "debt_to_equity": 1.5, "current_ratio": 1.0, "rsi_14": 55.0, "beta": 1.28},
        "MSFT": {"name": "Microsoft Corporation", "sector": "Technology", "price": 378.0, "market_cap": 2.8e12,
                 "pe_ratio": 35.0, "pb_ratio": 12.0, "dividend_yield": 0.8, "revenue_growth": 12.0,
                 "gross_margin": 69.0, "operating_margin": 42.0, "roe": 38.0, "roic": 28.0,
                 "debt_to_equity": 0.3, "current_ratio": 1.8, "rsi_14": 62.0, "beta": 0.92},
        "GOOGL": {"name": "Alphabet Inc.", "sector": "Technology", "price": 141.0, "market_cap": 1.76e12,
                  "pe_ratio": 24.0, "pb_ratio": 6.0, "dividend_yield": 0.0, "revenue_growth": 10.0,
                  "gross_margin": 56.0, "operating_margin": 27.0, "roe": 25.0, "roic": 22.0,
                  "debt_to_equity": 0.1, "current_ratio": 2.1, "rsi_14": 58.0, "beta": 1.05},
        "AMZN": {"name": "Amazon.com Inc.", "sector": "Technology", "price": 178.0, "market_cap": 1.85e12,
                 "pe_ratio": 60.0, "pb_ratio": 8.5, "dividend_yield": 0.0, "revenue_growth": 11.0,
                 "gross_margin": 47.0, "operating_margin": 6.0, "roe": 15.0, "roic": 10.0,
                 "debt_to_equity": 0.6, "current_ratio": 1.0, "rsi_14": 52.0, "beta": 1.15},
        "JNJ": {"name": "Johnson & Johnson", "sector": "Healthcare", "price": 155.0, "market_cap": 380e9,
                "pe_ratio": 12.0, "pb_ratio": 5.5, "dividend_yield": 3.0, "revenue_growth": 5.0,
                "gross_margin": 68.0, "operating_margin": 25.0, "roe": 20.0, "roic": 15.0,
                "debt_to_equity": 0.4, "current_ratio": 1.2, "rsi_14": 45.0, "beta": 0.55},
        "JPM": {"name": "JPMorgan Chase", "sector": "Financial", "price": 195.0, "market_cap": 560e9,
                "pe_ratio": 11.0, "pb_ratio": 1.7, "dividend_yield": 2.3, "revenue_growth": 8.0,
                "gross_margin": 0.0, "operating_margin": 35.0, "roe": 15.0, "roic": 12.0,
                "debt_to_equity": 1.2, "current_ratio": 0.0, "rsi_14": 60.0, "beta": 1.05},
        "XOM": {"name": "Exxon Mobil", "sector": "Energy", "price": 105.0, "market_cap": 420e9,
                "pe_ratio": 8.0, "pb_ratio": 1.8, "dividend_yield": 3.5, "revenue_growth": -5.0,
                "gross_margin": 35.0, "operating_margin": 15.0, "roe": 18.0, "roic": 12.0,
                "debt_to_equity": 0.2, "current_ratio": 1.4, "rsi_14": 38.0, "beta": 0.95},
        "PG": {"name": "Procter & Gamble", "sector": "Consumer Defensive", "price": 165.0, "market_cap": 390e9,
               "pe_ratio": 25.0, "pb_ratio": 7.5, "dividend_yield": 2.4, "revenue_growth": 4.0,
               "gross_margin": 52.0, "operating_margin": 22.0, "roe": 32.0, "roic": 18.0,
               "debt_to_equity": 0.6, "current_ratio": 0.8, "rsi_14": 50.0, "beta": 0.45},
        "V": {"name": "Visa Inc.", "sector": "Financial", "price": 280.0, "market_cap": 580e9,
              "pe_ratio": 30.0, "pb_ratio": 14.0, "dividend_yield": 0.8, "revenue_growth": 10.0,
              "gross_margin": 80.0, "operating_margin": 65.0, "roe": 45.0, "roic": 30.0,
              "debt_to_equity": 0.5, "current_ratio": 1.5, "rsi_14": 65.0, "beta": 0.95},
        "UNH": {"name": "UnitedHealth Group", "sector": "Healthcare", "price": 520.0, "market_cap": 480e9,
                "pe_ratio": 22.0, "pb_ratio": 6.0, "dividend_yield": 1.4, "revenue_growth": 12.0,
                "gross_margin": 25.0, "operating_margin": 8.0, "roe": 25.0, "roic": 15.0,
                "debt_to_equity": 0.7, "current_ratio": 0.8, "rsi_14": 55.0, "beta": 0.65},
    }


def render_filter_builder():
    """Render the filter builder UI."""
    st.subheader("Build Your Screen")
    
    # Get all filters grouped by category
    categories = {}
    for f in FILTER_REGISTRY.get_all_filters():
        cat = f.category.value
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(f)
    
    # Filter selector
    filters = []
    
    num_filters = st.number_input("Number of filters", min_value=1, max_value=10, value=2)
    
    for i in range(int(num_filters)):
        st.markdown(f"**Filter {i + 1}**")
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            # Category selection
            category = st.selectbox(
                f"Category {i + 1}",
                options=list(categories.keys()),
                key=f"cat_{i}"
            )
            
            # Filter selection within category
            filter_options = [(f.filter_id, f.name) for f in categories[category]]
            selected_filter = st.selectbox(
                f"Filter {i + 1}",
                options=[f[0] for f in filter_options],
                format_func=lambda x: next(f[1] for f in filter_options if f[0] == x),
                key=f"filter_{i}"
            )
        
        with col2:
            operator = st.selectbox(
                f"Operator {i + 1}",
                options=["gte", "lte", "gt", "lt", "eq", "between"],
                format_func=lambda x: {"gte": ">=", "lte": "<=", "gt": ">", "lt": "<", "eq": "=", "between": "Between"}[x],
                key=f"op_{i}"
            )
        
        with col3:
            value = st.number_input(f"Value {i + 1}", key=f"val_{i}")
            value2 = None
            if operator == "between":
                value2 = st.number_input(f"Value 2 {i + 1}", key=f"val2_{i}")
        
        filters.append(FilterCondition(
            filter_id=selected_filter,
            operator=Operator(operator),
            value=value,
            value2=value2,
        ))
    
    return filters


def render_preset_screens():
    """Render preset screen selection."""
    st.subheader("Preset Screens")
    
    presets = get_preset_screens()
    
    # Group by tag
    value_screens = [p for p in presets if "value" in p.tags]
    growth_screens = [p for p in presets if "growth" in p.tags]
    quality_screens = [p for p in presets if "quality" in p.tags or "defensive" in p.tags]
    technical_screens = [p for p in presets if "technical" in p.tags or "momentum" in p.tags]
    dividend_screens = [p for p in presets if "dividend" in p.tags]
    
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Value**")
        for s in value_screens[:3]:
            if st.button(s.name, key=f"preset_val_{s.screen_id}"):
                return s

        st.markdown("**Growth**")
        for s in growth_screens[:3]:
            if st.button(s.name, key=f"preset_grw_{s.screen_id}"):
                return s

    with col2:
        st.markdown("**Quality**")
        for s in quality_screens[:3]:
            if st.button(s.name, key=f"preset_qual_{s.screen_id}"):
                return s

        st.markdown("**Dividend**")
        for s in dividend_screens[:3]:
            if st.button(s.name, key=f"preset_div_{s.screen_id}"):
                return s
    
    return None


def render_results(result):
    """Render screen results."""
    st.subheader(f"Results: {result.matches} matches")
    st.caption(f"Screened {result.total_universe} stocks in {result.execution_time_ms:.1f}ms")
    
    if not result.stocks:
        st.info("No stocks match your criteria.")
        return
    
    # Convert to DataFrame
    rows = []
    for match in result.stocks:
        row = {
            "Symbol": match.symbol,
            "Name": match.name,
            "Sector": match.sector,
            "Price": f"${match.price:.2f}",
            "Market Cap": f"${match.market_cap/1e9:.1f}B",
        }
        # Add key metrics
        for key in ["pe_ratio", "dividend_yield", "revenue_growth", "roe"]:
            if key in match.metrics:
                val = match.metrics[key]
                if key in ["dividend_yield", "revenue_growth"]:
                    row[key.replace("_", " ").title()] = f"{val:.1f}%"
                else:
                    row[key.replace("_", " ").title()] = f"{val:.1f}"
        rows.append(row)
    
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)


def render_custom_formula():
    """Render custom formula input."""
    st.subheader("Custom Formula")
    
    st.markdown("""
    Create custom screening formulas using:
    - Variables: `pe_ratio`, `roe`, `revenue_growth`, etc.
    - Operators: `>`, `<`, `>=`, `<=`, `==`, `and`, `or`
    - Functions: `abs()`, `min()`, `max()`, `sqrt()`
    """)
    
    formula = st.text_input(
        "Formula",
        value="pe_ratio < 20 and roe > 15",
        help="Example: pe_ratio < 20 and revenue_growth > 10"
    )
    
    if formula:
        return CustomFormula(name="Custom", expression=formula)
    return None


def main():
    if not SCREENER_AVAILABLE:
        return
    
    # Initialize engine
    engine = ScreenerEngine()
    stock_data = get_demo_stock_data()
    
    # Tabs
    tab1, tab2, tab3 = st.tabs(["🔍 Build Screen", "📋 Presets", "📊 Custom Formula"])
    
    screen = None
    
    with tab1:
        st.markdown("Build a custom screen with multiple filters.")
        
        # Universe filters
        col1, col2 = st.columns(2)
        with col1:
            sectors = st.multiselect(
                "Sectors",
                options=["Technology", "Healthcare", "Financial", "Energy", "Consumer Defensive"],
                default=[]
            )
        with col2:
            min_cap = st.number_input("Min Market Cap ($B)", value=0.0) * 1e9
        
        # Filter builder
        filters = render_filter_builder()
        
        if st.button("Run Screen", type="primary", key="run_custom"):
            screen = Screen(
                name="Custom Screen",
                filters=filters,
                sectors=sectors if sectors else [],
                market_cap_min=min_cap if min_cap > 0 else None,
            )
    
    with tab2:
        selected_preset = render_preset_screens()
        if selected_preset:
            screen = selected_preset
            st.success(f"Selected: {selected_preset.name}")
            st.write(selected_preset.description)
            
            if st.button("Run Preset Screen", type="primary"):
                pass  # Screen is already set
    
    with tab3:
        formula = render_custom_formula()
        
        if st.button("Run Formula Screen", type="primary", key="run_formula"):
            if formula:
                screen = Screen(
                    name="Formula Screen",
                    filters=[],
                    custom_formulas=[formula],
                )
    
    # Run screen and show results
    if screen:
        with st.spinner("Running screen..."):
            # Validate
            is_valid, errors = engine.validate_screen(screen)
            if not is_valid:
                for error in errors:
                    st.error(error)
            else:
                result = engine.run_screen(screen, stock_data)
                render_results(result)
    
    # Sidebar - Available filters
    with st.sidebar:
        st.header("Available Filters")
        
        search = st.text_input("Search filters")
        
        if search:
            matches = FILTER_REGISTRY.search_filters(search)
            for f in matches[:10]:
                st.markdown(f"**{f.name}** ({f.category.value})")
                st.caption(f.description)
        else:
            st.markdown("Search for specific filters or browse by category.")
            
            for cat in FilterCategory:
                with st.expander(cat.value.replace("_", " ").title()):
                    filters = FILTER_REGISTRY.get_filters_by_category(cat)
                    for f in filters[:5]:
                        st.markdown(f"- **{f.name}**: {f.description[:50]}...")



main()
