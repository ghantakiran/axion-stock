"""EMA Cloud Signals — Live signal feed, scanner, cloud charts, and signal history."""

import json
import sys
import os
from datetime import datetime, timezone

import streamlit as st
from app.styles import inject_global_styles

try:
    st.set_page_config(page_title="EMA Cloud Signals", layout="wide")
except st.errors.StreamlitAPIError:
    pass

inject_global_styles()

# ── Path Setup ────────────────────────────────────────────────────────

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

st.title("EMA Cloud Signals")
st.caption("Ripster EMA Cloud signal engine — 4 cloud layers, 10 signal types, multi-timeframe confluence")

# ── Imports ───────────────────────────────────────────────────────────

import numpy as np
import pandas as pd

from src.ema_signals.clouds import CloudConfig, CloudState, EMACloudCalculator, EMASignalConfig
from src.ema_signals.conviction import ConvictionScorer
from src.ema_signals.detector import SignalDetector, SignalType, TradeSignal
from src.ema_signals.mtf import MTFEngine
from src.ema_signals.scanner import UniverseScanner, DEFAULT_TICKERS

# ── Session State Init ────────────────────────────────────────────────

if "ema_config" not in st.session_state:
    st.session_state["ema_config"] = EMASignalConfig()
if "ema_signals_cache" not in st.session_state:
    st.session_state["ema_signals_cache"] = []
if "ema_scan_tickers" not in st.session_state:
    st.session_state["ema_scan_tickers"] = DEFAULT_TICKERS[:20]

# ── Sidebar ───────────────────────────────────────────────────────────

st.sidebar.header("Signal Settings")

conviction_min = st.sidebar.slider(
    "Min Conviction to Display",
    min_value=0, max_value=100, value=25, step=5,
)

selected_timeframes = st.sidebar.multiselect(
    "Active Timeframes",
    options=["1m", "5m", "10m", "1h", "1d"],
    default=["5m", "10m", "1h"],
)

signal_direction = st.sidebar.radio(
    "Direction Filter",
    options=["All", "Long", "Short"],
    index=0,
)

# ── Main Tabs ─────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4 = st.tabs([
    "Live Signals",
    "Scanner",
    "Cloud Charts",
    "Signal History",
])

# ═══════════════════════════════════════════════════════════════════════
# Tab 1: Live Signals
# ═══════════════════════════════════════════════════════════════════════

with tab1:
    st.subheader("Real-Time Signal Feed")

    col1, col2, col3, col4 = st.columns(4)
    cached_signals = st.session_state.get("ema_signals_cache", [])

    with col1:
        st.metric("Total Signals", len(cached_signals))
    with col2:
        high_conv = len([s for s in cached_signals if s.get("conviction", 0) >= 75])
        st.metric("High Conviction", high_conv)
    with col3:
        long_count = len([s for s in cached_signals if s.get("direction") == "long"])
        st.metric("Long Signals", long_count)
    with col4:
        short_count = len([s for s in cached_signals if s.get("direction") == "short"])
        st.metric("Short Signals", short_count)

    st.divider()

    if cached_signals:
        # Filter
        display_signals = cached_signals
        if signal_direction == "Long":
            display_signals = [s for s in display_signals if s.get("direction") == "long"]
        elif signal_direction == "Short":
            display_signals = [s for s in display_signals if s.get("direction") == "short"]

        display_signals = [s for s in display_signals if s.get("conviction", 0) >= conviction_min]

        if display_signals:
            df_signals = pd.DataFrame(display_signals)
            display_cols = ["ticker", "signal_type", "direction", "timeframe",
                            "conviction", "entry_price", "stop_loss"]
            available_cols = [c for c in display_cols if c in df_signals.columns]
            st.dataframe(
                df_signals[available_cols].sort_values("conviction", ascending=False),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No signals match current filters.")
    else:
        st.info("No signals cached. Run a scan from the Scanner tab to generate signals.")

    # Manual quick scan
    st.divider()
    quick_ticker = st.text_input("Quick Scan Ticker", value="AAPL", key="quick_scan_ticker")
    quick_tf = st.selectbox("Timeframe", options=["1d", "1h", "10m", "5m", "1m"], key="quick_scan_tf")

    if st.button("Scan Now", key="quick_scan_btn"):
        with st.spinner(f"Scanning {quick_ticker} on {quick_tf}..."):
            try:
                from src.ema_signals.data_feed import DataFeed

                feed = DataFeed()
                df = feed.get_bars(quick_ticker, quick_tf)

                if df.empty:
                    st.warning(f"No data available for {quick_ticker}/{quick_tf}")
                else:
                    detector = SignalDetector()
                    signals = detector.detect(df, quick_ticker, quick_tf)
                    scorer = ConvictionScorer()

                    for sig in signals:
                        vol_data = UniverseScanner._compute_volume_data(df)
                        body_ratio = UniverseScanner._compute_body_ratio(df)
                        sig.metadata["body_ratio"] = body_ratio
                        score = scorer.score(sig, vol_data)
                        sig.conviction = score.total

                    if signals:
                        sig_dicts = [s.to_dict() for s in signals]
                        st.session_state["ema_signals_cache"].extend(sig_dicts)
                        st.success(f"Found {len(signals)} signals for {quick_ticker}")
                        st.dataframe(
                            pd.DataFrame(sig_dicts)[
                                ["signal_type", "direction", "conviction", "entry_price", "stop_loss"]
                            ],
                            use_container_width=True,
                            hide_index=True,
                        )
                    else:
                        st.info(f"No signals detected for {quick_ticker}/{quick_tf}")

                    # Show cloud states
                    calc = EMACloudCalculator()
                    states = calc.get_cloud_states(df)
                    st.write("**Current Cloud States:**")
                    for cs in states:
                        emoji = "🟢" if cs.is_bullish else "🔴"
                        pos = "above" if cs.price_above else ("inside" if cs.price_inside else "below")
                        st.write(
                            f"  {emoji} **{cs.cloud_name.title()}**: "
                            f"EMA {cs.short_ema:.2f}/{cs.long_ema:.2f} | "
                            f"Price {pos} | Thickness: {cs.thickness:.4f}"
                        )
            except Exception as e:
                st.error(f"Scan failed: {e}")


# ═══════════════════════════════════════════════════════════════════════
# Tab 2: Scanner
# ═══════════════════════════════════════════════════════════════════════

with tab2:
    st.subheader("Universe Scanner")

    col1, col2 = st.columns([2, 1])

    with col1:
        scan_tickers_input = st.text_area(
            "Scan Universe (comma-separated)",
            value=", ".join(st.session_state["ema_scan_tickers"]),
            height=100,
        )

    with col2:
        scan_timeframes = st.multiselect(
            "Timeframes to Scan",
            options=["1m", "5m", "10m", "1h", "1d"],
            default=["1d"],
            key="scanner_tfs",
        )
        top_n = st.number_input("Show Top N", min_value=5, max_value=50, value=20)

    if st.button("Run Full Scan", type="primary", key="full_scan_btn"):
        tickers = [t.strip().upper() for t in scan_tickers_input.split(",") if t.strip()]
        st.session_state["ema_scan_tickers"] = tickers

        with st.spinner(f"Scanning {len(tickers)} tickers across {len(scan_timeframes)} timeframes..."):
            try:
                scanner = UniverseScanner()
                all_signals = scanner.scan_all(tickers, scan_timeframes)
                ranked = scanner.rank_by_conviction(all_signals, top_n=top_n)

                sig_dicts = [s.to_dict() for s in ranked]
                st.session_state["ema_signals_cache"] = sig_dicts

                st.success(f"Scan complete: {len(all_signals)} total signals, showing top {len(ranked)}")

                if sig_dicts:
                    df_results = pd.DataFrame(sig_dicts)
                    display_cols = ["ticker", "signal_type", "direction", "timeframe",
                                    "conviction", "entry_price", "stop_loss"]
                    available_cols = [c for c in display_cols if c in df_results.columns]
                    st.dataframe(
                        df_results[available_cols],
                        use_container_width=True,
                        hide_index=True,
                    )

                    # Signal heatmap: ticker × signal type
                    st.subheader("Signal Heatmap")
                    if len(df_results) > 1:
                        heatmap_data = df_results.pivot_table(
                            index="ticker", columns="signal_type",
                            values="conviction", aggfunc="max", fill_value=0,
                        )
                        st.dataframe(
                            heatmap_data.style.background_gradient(cmap="RdYlGn", axis=None),
                            use_container_width=True,
                        )

            except Exception as e:
                st.error(f"Scan failed: {e}")

    # Default universe info
    with st.expander("Default Scan Universe"):
        st.write(f"**{len(DEFAULT_TICKERS)} tickers**: {', '.join(DEFAULT_TICKERS)}")


# ═══════════════════════════════════════════════════════════════════════
# Tab 3: Cloud Charts
# ═══════════════════════════════════════════════════════════════════════

with tab3:
    st.subheader("EMA Cloud Charts")

    col1, col2 = st.columns([1, 1])
    with col1:
        chart_ticker = st.text_input("Ticker", value="AAPL", key="chart_ticker")
    with col2:
        chart_tf = st.selectbox(
            "Timeframe",
            options=["1d", "1h", "10m", "5m", "1m"],
            key="chart_tf",
        )

    if st.button("Load Chart", key="load_chart_btn"):
        with st.spinner(f"Loading {chart_ticker} {chart_tf} chart..."):
            try:
                from src.ema_signals.data_feed import DataFeed

                feed = DataFeed()
                df = feed.get_bars(chart_ticker, chart_tf)

                if df.empty:
                    st.warning(f"No data for {chart_ticker}/{chart_tf}")
                else:
                    calc = EMACloudCalculator()
                    cloud_df = calc.compute_clouds(df)

                    try:
                        import plotly.graph_objects as go
                        from plotly.subplots import make_subplots

                        fig = make_subplots(
                            rows=2, cols=1, shared_xaxes=True,
                            vertical_spacing=0.03, row_heights=[0.75, 0.25],
                        )

                        # Candlestick
                        fig.add_trace(
                            go.Candlestick(
                                x=cloud_df.index,
                                open=cloud_df["open"],
                                high=cloud_df["high"],
                                low=cloud_df["low"],
                                close=cloud_df["close"],
                                name="Price",
                            ),
                            row=1, col=1,
                        )

                        # EMA Cloud layers as filled areas
                        cloud_colors = {
                            "fast": ("rgba(0,188,212,0.3)", "EMA 5/12"),
                            "pullback": ("rgba(255,235,59,0.2)", "EMA 8/9"),
                            "trend": ("rgba(156,39,176,0.2)", "EMA 20/21"),
                            "macro": ("rgba(244,67,54,0.15)", "EMA 34/50"),
                        }

                        config = CloudConfig()
                        for cloud_name, short_p, long_p in config.get_pairs():
                            color, label = cloud_colors[cloud_name]
                            short_col = f"ema_{short_p}"
                            long_col = f"ema_{long_p}"

                            fig.add_trace(
                                go.Scatter(
                                    x=cloud_df.index, y=cloud_df[short_col],
                                    line=dict(width=1), name=f"{label} Short",
                                    showlegend=False,
                                ),
                                row=1, col=1,
                            )
                            fig.add_trace(
                                go.Scatter(
                                    x=cloud_df.index, y=cloud_df[long_col],
                                    line=dict(width=1), name=label,
                                    fill="tonexty", fillcolor=color,
                                ),
                                row=1, col=1,
                            )

                        # Volume
                        colors = [
                            "green" if c >= o else "red"
                            for c, o in zip(cloud_df["close"], cloud_df["open"])
                        ]
                        fig.add_trace(
                            go.Bar(
                                x=cloud_df.index, y=cloud_df["volume"],
                                marker_color=colors, name="Volume",
                                showlegend=False,
                            ),
                            row=2, col=1,
                        )

                        fig.update_layout(
                            title=f"{chart_ticker} — EMA Cloud ({chart_tf})",
                            xaxis_rangeslider_visible=False,
                            height=700,
                            template="plotly_dark",
                        )

                        st.plotly_chart(fig, use_container_width=True)

                    except ImportError:
                        # Fallback: simple line chart
                        st.line_chart(cloud_df[["close", "ema_5", "ema_12", "ema_20", "ema_50"]])

                    # Cloud state summary
                    states = calc.get_cloud_states(cloud_df)
                    cols = st.columns(4)
                    for i, cs in enumerate(states):
                        with cols[i]:
                            emoji = "🟢" if cs.is_bullish else "🔴"
                            st.metric(
                                f"{emoji} {cs.cloud_name.title()}",
                                f"{cs.short_ema:.2f} / {cs.long_ema:.2f}",
                                delta=f"{'Bullish' if cs.is_bullish else 'Bearish'}",
                            )

            except Exception as e:
                st.error(f"Chart failed: {e}")


# ═══════════════════════════════════════════════════════════════════════
# Tab 4: Signal History
# ═══════════════════════════════════════════════════════════════════════

with tab4:
    st.subheader("Signal History")

    cached = st.session_state.get("ema_signals_cache", [])

    if cached:
        df_hist = pd.DataFrame(cached)

        # Filters
        col1, col2, col3 = st.columns(3)
        with col1:
            hist_tickers = st.multiselect(
                "Filter by Ticker",
                options=sorted(df_hist["ticker"].unique()) if "ticker" in df_hist.columns else [],
                key="hist_ticker_filter",
            )
        with col2:
            hist_types = st.multiselect(
                "Filter by Signal Type",
                options=sorted(df_hist["signal_type"].unique()) if "signal_type" in df_hist.columns else [],
                key="hist_type_filter",
            )
        with col3:
            hist_min_conv = st.slider("Min Conviction", 0, 100, 0, key="hist_conv_filter")

        filtered = df_hist
        if hist_tickers:
            filtered = filtered[filtered["ticker"].isin(hist_tickers)]
        if hist_types:
            filtered = filtered[filtered["signal_type"].isin(hist_types)]
        if hist_min_conv > 0:
            filtered = filtered[filtered["conviction"] >= hist_min_conv]

        st.dataframe(filtered, use_container_width=True, hide_index=True)

        # Summary stats
        st.divider()
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Signals", len(filtered))
        with col2:
            if "conviction" in filtered.columns and not filtered.empty:
                st.metric("Avg Conviction", f"{filtered['conviction'].mean():.1f}")
        with col3:
            if "signal_type" in filtered.columns and not filtered.empty:
                st.metric("Unique Signal Types", filtered["signal_type"].nunique())

        if st.button("Clear Signal History", key="clear_history"):
            st.session_state["ema_signals_cache"] = []
            st.rerun()
    else:
        st.info("No signal history. Run a scan to generate signals.")

    # Cloud config reference
    with st.expander("EMA Cloud Configuration Reference"):
        config = CloudConfig()
        st.write("**Cloud Layers:**")
        st.write(f"- Fast: EMA {config.fast_short}/{config.fast_long}")
        st.write(f"- Pullback: EMA {config.pullback_short}/{config.pullback_long}")
        st.write(f"- Trend: EMA {config.trend_short}/{config.trend_long}")
        st.write(f"- Macro: EMA {config.macro_short}/{config.macro_long}")

        st.write("\n**Signal Types:**")
        for st_type in SignalType:
            st.write(f"- `{st_type.value}`")

        st.write("\n**Conviction Levels:**")
        st.write("- High (75-100): Auto-execute, full size")
        st.write("- Medium (50-74): Auto-execute, reduced size")
        st.write("- Low (25-49): Log only")
        st.write("- None (<25): Discarded")
