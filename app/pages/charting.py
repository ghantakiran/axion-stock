"""PRD-62: Advanced Charting Dashboard."""

import streamlit as st
from app.styles import inject_global_styles
import pandas as pd
from datetime import datetime, timezone, timedelta

from src.charting import (
    ChartType,
    Timeframe,
    DrawingType,
    IndicatorCategory,
    LineStyle,
    ChartConfig,
    DEFAULT_CHART_CONFIG,
    ChartLayout,
    Drawing,
    IndicatorConfig,
    OHLCV,
    IndicatorResult,
    IndicatorEngine,
    DrawingManager,
    LayoutManager,
)

try:
    st.set_page_config(page_title="Advanced Charting", layout="wide")
except st.errors.StreamlitAPIException:
    pass

inject_global_styles()

st.title("Advanced Charting")

# Initialize managers
if "indicator_engine" not in st.session_state:
    st.session_state.indicator_engine = IndicatorEngine()
if "drawing_manager" not in st.session_state:
    st.session_state.drawing_manager = DrawingManager()
if "layout_manager" not in st.session_state:
    st.session_state.layout_manager = LayoutManager()
if "current_user" not in st.session_state:
    st.session_state.current_user = "demo_user"

indicator_engine = st.session_state.indicator_engine
drawing_manager = st.session_state.drawing_manager
layout_manager = st.session_state.layout_manager
current_user = st.session_state.current_user

# Generate sample data
def generate_sample_data(symbol: str, days: int = 100) -> list[OHLCV]:
    """Generate sample OHLCV data."""
    import random
    random.seed(hash(symbol))

    data = []
    base_price = 150.0

    for i in range(days):
        timestamp = datetime.now(timezone.utc) - timedelta(days=days - i)
        open_price = base_price + random.uniform(-2, 2)
        high_price = open_price + random.uniform(0, 3)
        low_price = open_price - random.uniform(0, 3)
        close_price = low_price + random.uniform(0, high_price - low_price)
        volume = random.randint(1000000, 50000000)

        data.append(OHLCV(
            timestamp=timestamp,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=volume,
        ))

        base_price = close_price + random.uniform(-1, 1)

    return data

# --- Sidebar ---
st.sidebar.header("Chart Settings")

symbol = st.sidebar.text_input("Symbol", "AAPL")

chart_type = st.sidebar.selectbox(
    "Chart Type",
    [ct.value for ct in ChartType],
    index=0,
    format_func=lambda x: x.replace("_", " ").title()
)

timeframe = st.sidebar.selectbox(
    "Timeframe",
    [tf.value for tf in Timeframe],
    index=6,  # D1
    format_func=lambda x: x.upper()
)

# Layout selection
user_layouts = layout_manager.get_layouts(current_user)
layout_names = ["New Layout"] + [l.name for l in user_layouts]
selected_layout = st.sidebar.selectbox("Layout", layout_names)

if selected_layout == "New Layout":
    new_layout_name = st.sidebar.text_input("Layout Name", "My Chart")
    if st.sidebar.button("Create Layout"):
        layout = layout_manager.create_layout(
            user_id=current_user,
            name=new_layout_name,
            symbol=symbol,
            timeframe=Timeframe(timeframe),
            chart_type=ChartType(chart_type),
        )
        st.sidebar.success(f"Created layout: {new_layout_name}")
        st.rerun()

# --- Main Content ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Chart", "Indicators", "Drawings", "Layouts", "Templates"
])

# Generate sample data for the symbol
sample_data = generate_sample_data(symbol)

# --- Tab 1: Chart ---
with tab1:
    st.subheader(f"{symbol} - {timeframe.upper()} {chart_type.replace('_', ' ').title()}")

    # Price metrics
    if sample_data:
        latest = sample_data[-1]
        prev = sample_data[-2] if len(sample_data) > 1 else latest
        change = latest.close - prev.close
        change_pct = (change / prev.close) * 100

        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Open", f"${latest.open:.2f}")
        col2.metric("High", f"${latest.high:.2f}")
        col3.metric("Low", f"${latest.low:.2f}")
        col4.metric("Close", f"${latest.close:.2f}", f"{change_pct:+.2f}%")
        col5.metric("Volume", f"{latest.volume:,.0f}")

    # Chart visualization (placeholder - would use plotly/lightweight-charts in production)
    st.markdown("#### Price Chart")

    chart_df = pd.DataFrame([
        {
            "Date": d.timestamp.strftime("%Y-%m-%d"),
            "Open": d.open,
            "High": d.high,
            "Low": d.low,
            "Close": d.close,
            "Volume": d.volume,
        }
        for d in sample_data[-50:]  # Last 50 bars
    ])

    st.line_chart(chart_df.set_index("Date")["Close"])

    # Volume
    st.markdown("#### Volume")
    st.bar_chart(chart_df.set_index("Date")["Volume"])

    # Active indicators
    st.markdown("#### Active Indicators")
    active_layouts = [l for l in user_layouts if l.symbol == symbol]
    if active_layouts:
        for layout in active_layouts:
            for ind in layout.indicators:
                if ind.is_visible:
                    result = indicator_engine.calculate(ind.name, sample_data, ind.params)
                    st.write(f"**{ind.name}** ({ind.params})")

                    # Display latest values
                    for series_name, values in result.values.items():
                        latest_val = values[-1] if values else None
                        if latest_val is not None and latest_val == latest_val:  # Not NaN
                            st.write(f"  - {series_name}: {latest_val:.2f}")
    else:
        st.info("No indicators configured. Add indicators in the Indicators tab.")

# --- Tab 2: Indicators ---
with tab2:
    st.subheader("Technical Indicators")

    # Available indicators by category
    all_indicators = indicator_engine.get_available_indicators()

    col1, col2 = st.columns([1, 2])

    with col1:
        st.markdown("#### Add Indicator")

        category = st.selectbox(
            "Category",
            [c.value for c in IndicatorCategory],
            format_func=lambda x: x.replace("_", " ").title()
        )

        category_indicators = [
            ind for ind in all_indicators
            if ind["category"] == category
        ]

        selected_indicator = st.selectbox(
            "Indicator",
            [ind["id"] for ind in category_indicators],
            format_func=lambda x: next(
                (ind["name"] for ind in category_indicators if ind["id"] == x), x
            )
        )

        # Show params for selected indicator
        if selected_indicator:
            ind_def = next(
                (ind for ind in category_indicators if ind["id"] == selected_indicator),
                None
            )
            if ind_def and ind_def.get("params"):
                st.markdown("**Parameters**")
                params = {}
                for param_name, default_value in ind_def["params"].items():
                    if isinstance(default_value, int):
                        params[param_name] = st.number_input(
                            param_name.replace("_", " ").title(),
                            value=default_value,
                            min_value=1,
                        )
                    elif isinstance(default_value, float):
                        params[param_name] = st.number_input(
                            param_name.replace("_", " ").title(),
                            value=default_value,
                            min_value=0.1,
                            step=0.1,
                        )

                color = st.color_picker("Color", "#2196F3")

                if st.button("Add Indicator"):
                    config = IndicatorConfig(
                        indicator_id=f"{selected_indicator}_{datetime.now().timestamp()}",
                        name=selected_indicator,
                        params=params,
                        color=color,
                    )
                    # Add to current layout if exists
                    if user_layouts:
                        layout_manager.add_indicator(
                            current_user,
                            user_layouts[0].layout_id,
                            config
                        )
                        st.success(f"Added {selected_indicator}")
                        st.rerun()

    with col2:
        st.markdown("#### Indicator Preview")

        if selected_indicator:
            result = indicator_engine.calculate(selected_indicator, sample_data)

            st.write(f"**{result.name}** - {'Overlay' if result.is_overlay else 'Separate Panel'}")

            # Display indicator data
            preview_data = {}
            for series_name, values in result.values.items():
                preview_data[series_name] = values[-20:]  # Last 20 values

            preview_df = pd.DataFrame(preview_data)
            preview_df.index = [d.timestamp.strftime("%m/%d") for d in sample_data[-20:]]

            st.line_chart(preview_df)

            # Stats
            for series_name, values in result.values.items():
                valid_values = [v for v in values if v == v]  # Remove NaN
                if valid_values:
                    st.write(f"{series_name}: Latest={valid_values[-1]:.2f}, "
                             f"Min={min(valid_values):.2f}, Max={max(valid_values):.2f}")

    # Active indicators list
    st.markdown("---")
    st.markdown("#### Active Indicators")

    if user_layouts:
        for layout in user_layouts:
            if layout.indicators:
                st.write(f"**{layout.name}**")
                for ind in layout.indicators:
                    col_a, col_b, col_c = st.columns([3, 1, 1])
                    col_a.write(f"{ind.name} ({ind.params})")
                    col_b.write(f"Visible: {ind.is_visible}")
                    if col_c.button("Remove", key=f"rm_{ind.indicator_id}"):
                        layout_manager.remove_indicator(
                            current_user, layout.layout_id, ind.indicator_id
                        )
                        st.rerun()

# --- Tab 3: Drawings ---
with tab3:
    st.subheader("Drawing Tools")

    col1, col2 = st.columns([1, 2])

    with col1:
        st.markdown("#### Create Drawing")

        drawing_type = st.selectbox(
            "Drawing Type",
            [dt.value for dt in DrawingType],
            format_func=lambda x: x.replace("_", " ").title()
        )

        draw_color = st.color_picker("Color", "#2196F3", key="draw_color")
        line_width = st.slider("Line Width", 1, 5, 1)

        # Drawing-specific inputs
        if drawing_type == DrawingType.HORIZONTAL_LINE.value:
            price_level = st.number_input("Price Level", value=150.0, step=0.5)
            if st.button("Add Horizontal Line"):
                drawing = drawing_manager.create_horizontal_line(
                    symbol=symbol,
                    price=price_level,
                    color=draw_color,
                    line_width=line_width,
                )
                drawing_manager.add_drawing("default", drawing)
                st.success("Added horizontal line")

        elif drawing_type == DrawingType.TRENDLINE.value:
            st.write("Click two points on chart to draw trendline")
            start_price = st.number_input("Start Price", value=145.0)
            end_price = st.number_input("End Price", value=155.0)
            extend_right = st.checkbox("Extend Right")

            if st.button("Add Trendline"):
                start_time = datetime.now(timezone.utc) - timedelta(days=30)
                end_time = datetime.now(timezone.utc)
                drawing = drawing_manager.create_trendline(
                    symbol=symbol,
                    start=(start_time, start_price),
                    end=(end_time, end_price),
                    color=draw_color,
                    line_width=line_width,
                    extend_right=extend_right,
                )
                drawing_manager.add_drawing("default", drawing)
                st.success("Added trendline")

        elif drawing_type == DrawingType.FIBONACCI_RETRACEMENT.value:
            swing_high = st.number_input("Swing High", value=160.0)
            swing_low = st.number_input("Swing Low", value=140.0)
            show_prices = st.checkbox("Show Prices", value=True)

            if st.button("Add Fibonacci"):
                start_time = datetime.now(timezone.utc) - timedelta(days=30)
                end_time = datetime.now(timezone.utc)
                drawing = drawing_manager.create_fibonacci_retracement(
                    symbol=symbol,
                    start=(start_time, swing_low),
                    end=(end_time, swing_high),
                    show_prices=show_prices,
                )
                drawing_manager.add_drawing("default", drawing)
                st.success("Added Fibonacci retracement")

                # Show levels
                levels = drawing_manager.calculate_fib_levels(swing_low, swing_high)
                st.markdown("**Fibonacci Levels:**")
                for level, price in levels.items():
                    st.write(f"  {level*100:.1f}%: ${price:.2f}")

    with col2:
        st.markdown("#### Active Drawings")

        drawings = drawing_manager.get_drawings("default", symbol)

        if drawings:
            drawing_data = []
            for d in drawings:
                drawing_data.append({
                    "ID": d.drawing_id[:8],
                    "Type": d.drawing_type.value.replace("_", " ").title(),
                    "Points": len(d.points),
                    "Color": d.style.color,
                    "Visible": d.is_visible,
                    "Locked": d.is_locked,
                })

            st.dataframe(
                pd.DataFrame(drawing_data),
                use_container_width=True,
                hide_index=True
            )

            # Bulk actions
            col_a, col_b, col_c = st.columns(3)
            if col_a.button("Clear All"):
                drawing_manager.clear_drawings("default", symbol)
                st.success("Cleared all drawings")
                st.rerun()
        else:
            st.info("No drawings on this chart")

        # Drawing statistics
        st.markdown("#### Statistics")
        stats = drawing_manager.get_stats()
        st.json(stats)

# --- Tab 4: Layouts ---
with tab4:
    st.subheader("Chart Layouts")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown("#### My Layouts")

        layouts = layout_manager.get_layouts(current_user)

        if layouts:
            for layout in layouts:
                with st.expander(f"{layout.name} {'(Default)' if layout.is_default else ''}"):
                    st.write(f"**Symbol:** {layout.symbol or 'Any'}")
                    st.write(f"**Timeframe:** {layout.timeframe.value}")
                    st.write(f"**Chart Type:** {layout.chart_type.value}")
                    st.write(f"**Indicators:** {len(layout.indicators)}")
                    st.write(f"**Drawings:** {len(layout.drawings)}")
                    st.write(f"**Created:** {layout.created_at.strftime('%Y-%m-%d')}")

                    col_a, col_b, col_c = st.columns(3)
                    if col_a.button("Set Default", key=f"def_{layout.layout_id}"):
                        layout_manager.set_default_layout(current_user, layout.layout_id)
                        st.success("Set as default")
                        st.rerun()

                    if col_b.button("Duplicate", key=f"dup_{layout.layout_id}"):
                        layout_manager.duplicate_layout(
                            current_user, layout.layout_id, f"{layout.name} (Copy)"
                        )
                        st.success("Duplicated layout")
                        st.rerun()

                    if col_c.button("Delete", key=f"del_{layout.layout_id}"):
                        layout_manager.delete_layout(current_user, layout.layout_id)
                        st.success("Deleted layout")
                        st.rerun()
        else:
            st.info("No layouts saved. Create one from the sidebar.")

    with col2:
        st.markdown("#### Create New Layout")

        with st.form("new_layout_form"):
            name = st.text_input("Layout Name", "My Analysis")
            description = st.text_area("Description", "")
            layout_symbol = st.text_input("Symbol", symbol)
            layout_tf = st.selectbox(
                "Timeframe",
                [tf.value for tf in Timeframe],
                index=6
            )
            layout_ct = st.selectbox(
                "Chart Type",
                [ct.value for ct in ChartType]
            )

            submitted = st.form_submit_button("Create Layout")
            if submitted:
                new_layout = layout_manager.create_layout(
                    user_id=current_user,
                    name=name,
                    symbol=layout_symbol,
                    timeframe=Timeframe(layout_tf),
                    chart_type=ChartType(layout_ct),
                    description=description,
                )
                st.success(f"Created layout: {name}")
                st.rerun()

        st.markdown("#### Save as Template")
        if layouts:
            layout_to_save = st.selectbox(
                "Select Layout",
                [l.layout_id for l in layouts],
                format_func=lambda x: next(
                    (l.name for l in layouts if l.layout_id == x), x
                )
            )
            template_name = st.text_input("Template Name", "My Template")
            template_category = st.selectbox(
                "Category",
                ["Trading", "Analysis", "Custom"]
            )

            if st.button("Save as Template"):
                template = layout_manager.save_layout_as_template(
                    current_user,
                    layout_to_save,
                    template_name,
                    template_category
                )
                if template:
                    st.success(f"Saved template: {template_name}")

# --- Tab 5: Templates ---
with tab5:
    st.subheader("Chart Templates")

    # Featured templates
    st.markdown("#### Featured Templates")

    featured = layout_manager.get_featured_templates()

    cols = st.columns(3)
    for i, template in enumerate(featured):
        with cols[i % 3]:
            with st.container():
                st.markdown(f"**{template.name}**")
                st.write(template.description)
                st.write(f"Category: {template.category}")
                st.write(f"Indicators: {len(template.indicators)}")
                st.write(f"Used: {template.usage_count} times")

                if template.rating_count > 0:
                    st.write(f"Rating: {template.rating:.1f}/5 ({template.rating_count} reviews)")

                if st.button("Apply", key=f"apply_{template.template_id}"):
                    if layouts:
                        layout_manager.apply_template(
                            current_user,
                            layouts[0].layout_id,
                            template.template_id
                        )
                        st.success(f"Applied {template.name}")
                        st.rerun()
                    else:
                        st.warning("Create a layout first")

    # All templates
    st.markdown("---")
    st.markdown("#### All Templates")

    all_templates = layout_manager.get_templates()

    template_data = []
    for t in all_templates:
        template_data.append({
            "Name": t.name,
            "Category": t.category,
            "Indicators": len(t.indicators),
            "Usage": t.usage_count,
            "Rating": f"{t.rating:.1f}" if t.rating_count > 0 else "N/A",
            "Featured": "Yes" if t.is_featured else "No",
        })

    st.dataframe(
        pd.DataFrame(template_data),
        use_container_width=True,
        hide_index=True
    )

    # Rate a template
    st.markdown("#### Rate Template")
    template_to_rate = st.selectbox(
        "Template",
        [t.template_id for t in all_templates],
        format_func=lambda x: next(
            (t.name for t in all_templates if t.template_id == x), x
        )
    )
    rating = st.slider("Rating", 1, 5, 4)

    if st.button("Submit Rating"):
        layout_manager.rate_template(template_to_rate, rating)
        st.success("Rating submitted")
        st.rerun()

# --- Statistics ---
st.markdown("---")
st.markdown("### Statistics")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("#### Layout Stats")
    layout_stats = layout_manager.get_stats(current_user)
    for key, value in layout_stats.items():
        st.metric(key.replace("_", " ").title(), value)

with col2:
    st.markdown("#### Drawing Stats")
    drawing_stats = drawing_manager.get_stats()
    for key, value in drawing_stats.items():
        if isinstance(value, dict):
            st.write(f"**{key.replace('_', ' ').title()}:**")
            for k, v in value.items():
                st.write(f"  - {k}: {v}")
        else:
            st.metric(key.replace("_", " ").title(), value)

with col3:
    st.markdown("#### Available Indicators")
    indicators = indicator_engine.get_available_indicators()
    by_category = {}
    for ind in indicators:
        cat = ind["category"]
        by_category[cat] = by_category.get(cat, 0) + 1

    for cat, count in by_category.items():
        st.metric(cat.replace("_", " ").title(), count)
