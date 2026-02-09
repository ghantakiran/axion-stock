"""TradingView Scanner Dashboard.

Live market screening powered by TradingView with 15 preset scans,
custom filters, streaming mode, and cross-scanner integration.
"""

import streamlit as st
import pandas as pd
from datetime import datetime

try:
    st.set_page_config(page_title="TradingView Scanner", layout="wide")
except st.errors.StreamlitAPIError:
    pass

st.title(":material/travel_explore: TradingView Scanner")

try:
    from src.tv_scanner import (
        TVScannerEngine, TVScannerConfig, TVDataBridge,
        AssetClass, TVScanCategory, TVFilterCriterion,
        PRESET_TV_SCANS, get_tv_presets_by_category, get_all_tv_presets,
    )
    TV_AVAILABLE = True
except ImportError as e:
    TV_AVAILABLE = False
    st.error(f"TradingView Scanner module not available: {e}")


def _format_market_cap(val):
    """Format market cap as human-readable string."""
    if val is None:
        return "N/A"
    if val >= 1e12:
        return f"${val / 1e12:.2f}T"
    if val >= 1e9:
        return f"${val / 1e9:.2f}B"
    if val >= 1e6:
        return f"${val / 1e6:.1f}M"
    return f"${val:,.0f}"


def _results_to_dataframe(results):
    """Convert list of TVScanResult to a display DataFrame."""
    rows = []
    for r in results:
        rows.append({
            "Symbol": r.symbol,
            "Company": r.company_name or "",
            "Price": r.price,
            "Change %": r.change_pct,
            "Volume": r.volume,
            "Rel. Volume": r.relative_volume,
            "RSI": r.rsi,
            "TV Rating": r.tv_rating,
            "Signal Strength": r.signal_strength,
            "Market Cap": _format_market_cap(r.market_cap),
            "P/E Ratio": r.pe_ratio,
            "Sector": r.sector or "",
            "Perf Week": r.perf_week,
            "Perf Month": r.perf_month,
        })
    return pd.DataFrame(rows)


if TV_AVAILABLE:
    # Initialize engine in session state
    if "tv_engine" not in st.session_state:
        st.session_state.tv_engine = TVScannerEngine()

    engine = st.session_state.tv_engine

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Preset Scans", "Custom Scan", "Live Stream",
        "Cross-Scanner", "Field Explorer",
    ])

    # ── Tab 1: Preset Scans ─────────────────────────────────────────
    with tab1:
        st.subheader("Preset Scans")
        st.caption("Select a category and preset, then click Run to scan TradingView's live market data.")

        col1, col2 = st.columns([1, 2])
        with col1:
            categories = [c.value for c in TVScanCategory]
            selected_cat = st.selectbox("Category", categories, key="tv_preset_cat")

        with col2:
            cat_enum = TVScanCategory(selected_cat)
            presets = get_tv_presets_by_category(cat_enum)
            preset_names = {p.name: p.description for p in presets}
            if preset_names:
                selected_preset = st.selectbox(
                    "Preset",
                    list(preset_names.keys()),
                    format_func=lambda x: f"{x} — {preset_names[x][:60]}",
                    key="tv_preset_name",
                )
            else:
                selected_preset = None
                st.info("No presets in this category.")

        if selected_preset and st.button("Run Scan", key="tv_run_preset", type="primary"):
            with st.spinner(f"Running {selected_preset}..."):
                report = engine.run_preset(selected_preset)

            if report.error:
                st.error(f"Scan error: {report.error}")
            else:
                st.success(
                    f"Found **{report.total_results}** results in "
                    f"**{report.execution_time_ms:.0f}ms**"
                )
                if report.results:
                    df = _results_to_dataframe(report.results)
                    st.dataframe(df, use_container_width=True, height=500)

                    # Summary metrics
                    mcol1, mcol2, mcol3, mcol4 = st.columns(4)
                    avg_strength = sum(r.signal_strength for r in report.results) / len(report.results)
                    rsi_vals = [r.rsi for r in report.results if r.rsi is not None]
                    avg_rsi = sum(rsi_vals) / len(rsi_vals) if rsi_vals else 0
                    mcol1.metric("Results", report.total_results)
                    mcol2.metric("Avg Signal", f"{avg_strength:.1f}")
                    mcol3.metric("Avg RSI", f"{avg_rsi:.1f}")
                    mcol4.metric("Scan Time", f"{report.execution_time_ms:.0f}ms")

    # ── Tab 2: Custom Scan ──────────────────────────────────────────
    with tab2:
        st.subheader("Custom Scan Builder")
        st.caption("Build a custom scan with your own filters.")

        asset_options = [ac.value for ac in AssetClass]
        custom_asset = st.selectbox("Asset Class", asset_options, key="tv_custom_asset")

        st.markdown("**Filters** (add up to 5)")
        operators = ["gt", "lt", "gte", "lte", "eq", "between"]
        common_fields = [
            "close", "change", "volume", "relative_volume_10d_calc",
            "RSI", "MACD.macd", "SMA20", "SMA50", "SMA200",
            "market_cap_basic", "price_earnings_ttm", "dividend_yield_recent",
            "Recommend.All", "Perf.W", "Perf.1M",
        ]

        criteria_list = []
        for i in range(3):
            cols = st.columns([2, 1, 1, 1])
            with cols[0]:
                field = st.selectbox(f"Field {i+1}", common_fields, key=f"tv_cf_{i}")
            with cols[1]:
                op = st.selectbox(f"Op {i+1}", operators, key=f"tv_co_{i}")
            with cols[2]:
                val = st.number_input(f"Value {i+1}", value=0.0, key=f"tv_cv_{i}")
            with cols[3]:
                val2 = None
                if op == "between":
                    val2 = st.number_input(f"Value2 {i+1}", value=100.0, key=f"tv_cv2_{i}")

            if val != 0.0 or op == "eq":
                criteria_list.append(TVFilterCriterion(field, op, val, val2))

        if st.button("Run Custom Scan", key="tv_run_custom", type="primary") and criteria_list:
            with st.spinner("Running custom scan..."):
                report = engine.run_custom_scan(
                    criteria=criteria_list,
                    asset_class=AssetClass(custom_asset),
                )
            if report.error:
                st.error(f"Scan error: {report.error}")
            else:
                st.success(f"Found **{report.total_results}** results")
                if report.results:
                    df = _results_to_dataframe(report.results)
                    st.dataframe(df, use_container_width=True, height=400)

    # ── Tab 3: Live Stream ──────────────────────────────────────────
    with tab3:
        st.subheader("Live Streaming Scans")
        st.caption("Auto-refresh scan results at regular intervals.")

        stream_presets = list(PRESET_TV_SCANS.keys())
        stream_preset = st.selectbox("Preset to Stream", stream_presets, key="tv_stream_preset")
        interval = st.selectbox("Refresh Interval", [10, 30, 60], format_func=lambda x: f"{x}s", key="tv_stream_int")

        if "tv_streaming" not in st.session_state:
            st.session_state.tv_streaming = False

        col_start, col_stop = st.columns(2)
        with col_start:
            if st.button("Start Stream", key="tv_stream_start"):
                st.session_state.tv_streaming = True
        with col_stop:
            if st.button("Stop Stream", key="tv_stream_stop"):
                st.session_state.tv_streaming = False

        if st.session_state.tv_streaming:
            placeholder = st.empty()
            # Run a single scan refresh (Streamlit will re-run on interval via auto-rerun)
            engine.clear_cache()
            report = engine.run_preset(stream_preset)
            if report.error:
                placeholder.error(f"Stream error: {report.error}")
            elif report.results:
                with placeholder.container():
                    st.caption(f"Last update: {datetime.now().strftime('%H:%M:%S')} | {report.total_results} results")
                    df = _results_to_dataframe(report.results)
                    st.dataframe(df, use_container_width=True, height=400)

    # ── Tab 4: Cross-Scanner ────────────────────────────────────────
    with tab4:
        st.subheader("Cross-Scanner Integration")
        st.caption("Feed TradingView scan results into EMA conviction scoring or other modules.")

        cross_preset = st.selectbox(
            "Source Preset",
            list(PRESET_TV_SCANS.keys()),
            key="tv_cross_preset",
        )

        output_format = st.radio(
            "Output Format",
            ["Scanner Format", "Screener Format", "EMA Symbol List"],
            key="tv_cross_fmt",
        )

        if st.button("Run & Convert", key="tv_cross_run", type="primary"):
            with st.spinner("Running scan..."):
                report = engine.run_preset(cross_preset)

            if report.error:
                st.error(f"Scan error: {report.error}")
            elif report.results:
                bridge = TVDataBridge()
                if output_format == "Scanner Format":
                    data = bridge.to_scanner_format(report)
                    st.json({k: v for k, v in list(data.items())[:10]})
                    st.info(f"Total symbols: {len(data)}")
                elif output_format == "Screener Format":
                    data = bridge.to_screener_format(report)
                    st.json({k: v for k, v in list(data.items())[:10]})
                    st.info(f"Total symbols: {len(data)}")
                else:
                    symbols = bridge.to_ema_scan_list(report)
                    st.code(", ".join(symbols[:50]))
                    st.info(f"Total symbols: {len(symbols)}")

    # ── Tab 5: Field Explorer ───────────────────────────────────────
    with tab5:
        st.subheader("Field Explorer")
        st.caption("Search TradingView's 13,000+ available fields by keyword.")

        search_col1, search_col2 = st.columns([2, 1])
        with search_col1:
            query = st.text_input("Search fields", placeholder="e.g. RSI, volume, earnings", key="tv_field_search")
        with search_col2:
            search_asset = st.selectbox("Asset Class", [ac.value for ac in AssetClass], key="tv_field_asset")

        if query:
            results = engine.search_fields(query, AssetClass(search_asset))
            if results:
                st.success(f"Found {len(results)} matching fields")
                st.dataframe(pd.DataFrame({"Field Name": results}), use_container_width=True)
            else:
                st.warning("No fields found. Try a different search term.")

        st.divider()
        st.subheader("Available Presets")
        preset_data = []
        for p in get_all_tv_presets():
            preset_data.append({
                "Name": p.name,
                "Category": p.category.value if p.category else "",
                "Asset": p.asset_class.value,
                "Filters": len(p.criteria),
                "Description": p.description[:80],
            })
        st.dataframe(pd.DataFrame(preset_data), use_container_width=True)
else:
    st.info("Install the tv_scanner module to use this page.")
