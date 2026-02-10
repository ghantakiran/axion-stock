"""PRD-63: Regime-Aware Signals Dashboard."""

import streamlit as st
from app.styles import inject_global_styles
import pandas as pd
from datetime import datetime, timezone, timedelta
import random

from src.regime_signals import (
    RegimeType,
    SignalType,
    SignalDirection,
    DetectionMethod,
    TrendDirection,
    VolatilityLevel,
    SignalOutcome,
    REGIME_PARAMETERS,
    RegimeState,
    RegimeSignal,
    SignalPerformance,
    RegimeDetector,
    SignalGenerator,
    ParameterOptimizer,
    PerformanceTracker,
)

try:
    st.set_page_config(page_title="Regime-Aware Signals", layout="wide")
except st.errors.StreamlitAPIException:
    pass

inject_global_styles()

st.title("Regime-Aware Signals")

# Initialize managers
if "regime_detector" not in st.session_state:
    st.session_state.regime_detector = RegimeDetector()
if "signal_generator" not in st.session_state:
    st.session_state.signal_generator = SignalGenerator()
if "param_optimizer" not in st.session_state:
    st.session_state.param_optimizer = ParameterOptimizer()
if "perf_tracker" not in st.session_state:
    st.session_state.perf_tracker = PerformanceTracker()

detector = st.session_state.regime_detector
generator = st.session_state.signal_generator
optimizer = st.session_state.param_optimizer
tracker = st.session_state.perf_tracker


def generate_sample_prices(symbol: str, days: int = 100) -> list[float]:
    """Generate sample price data."""
    random.seed(hash(symbol))
    prices = [100.0]
    for _ in range(days - 1):
        change = random.gauss(0.001, 0.02)
        prices.append(prices[-1] * (1 + change))
    return prices


# --- Sidebar ---
st.sidebar.header("Settings")

symbol = st.sidebar.text_input("Symbol", "AAPL")
lookback_days = st.sidebar.slider("Lookback Days", 30, 200, 100)

detection_method = st.sidebar.selectbox(
    "Detection Method",
    [m.value for m in DetectionMethod],
    format_func=lambda x: x.replace("_", " ").title()
)

# Generate sample data
prices = generate_sample_prices(symbol, lookback_days)

# Detect regime
regime_state = detector.detect_regime(
    symbol,
    prices,
    method=DetectionMethod(detection_method)
)

# --- Main Content ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Current Regime", "Signals", "Performance", "Parameters", "History"
])

# --- Tab 1: Current Regime ---
with tab1:
    st.subheader("Current Market Regime")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Regime", regime_state.regime_type.value.replace("_", " ").title())
    col2.metric("Confidence", f"{regime_state.confidence:.1%}")
    col3.metric(
        "Trend",
        regime_state.trend_direction.value.title() if regime_state.trend_direction else "N/A"
    )
    col4.metric(
        "Volatility",
        regime_state.volatility_level.value.title() if regime_state.volatility_level else "N/A"
    )

    col5, col6, col7 = st.columns(3)
    col5.metric("Duration", f"{regime_state.regime_duration_days} days")
    col6.metric("Trend Strength", f"{regime_state.trend_strength:.1%}" if regime_state.trend_strength else "N/A")
    col7.metric(
        "Transition Prob",
        f"{regime_state.transition_probability:.1%}" if regime_state.transition_probability else "N/A"
    )

    # Regime description
    st.markdown("---")
    st.markdown("#### Regime Characteristics")

    regime_params = REGIME_PARAMETERS.get(regime_state.regime_type.value, {})
    preferred_signals = regime_params.get("preferred_signals", [])

    st.write(f"**Preferred Signal Types:** {', '.join([s.value for s in preferred_signals])}")
    st.write(f"**Position Size Factor:** {regime_params.get('position_size_factor', 1.0):.1f}x")
    st.write(f"**Stop Loss (ATR):** {regime_params.get('stop_loss_atr', 2.0):.1f}")
    st.write(f"**Take Profit (ATR):** {regime_params.get('take_profit_atr', 4.0):.1f}")

    # Regime distribution chart
    st.markdown("#### Regime Distribution")

    stats = detector.get_regime_statistics(symbol)
    if stats.get("regime_distribution"):
        dist_df = pd.DataFrame([
            {"Regime": k.replace("_", " ").title(), "Count": v}
            for k, v in stats["regime_distribution"].items()
        ])
        st.bar_chart(dist_df.set_index("Regime"))

# --- Tab 2: Signals ---
with tab2:
    st.subheader("Generated Signals")

    if st.button("Generate Signals"):
        result = generator.generate_signals(symbol, prices)

        st.info(f"Generated {len(result.signals)} signals in {result.generation_time_ms:.1f}ms")

        if result.signals:
            signal_data = []
            for signal in result.signals:
                signal_data.append({
                    "Type": signal.signal_type.value.replace("_", " ").title(),
                    "Direction": signal.direction.value.title(),
                    "Strength": f"{signal.strength:.1%}",
                    "Confidence": f"{signal.confidence:.1%}",
                    "Entry": f"${signal.entry_price:.2f}" if signal.entry_price else "N/A",
                    "Stop Loss": f"${signal.stop_loss:.2f}" if signal.stop_loss else "N/A",
                    "Take Profit": f"${signal.take_profit:.2f}" if signal.take_profit else "N/A",
                    "R:R": f"{signal.risk_reward_ratio:.2f}" if signal.risk_reward_ratio else "N/A",
                })

            st.dataframe(
                pd.DataFrame(signal_data),
                use_container_width=True,
                hide_index=True
            )

            # Signal details
            st.markdown("#### Signal Details")
            for i, signal in enumerate(result.signals):
                with st.expander(f"{signal.signal_type.value} - {signal.direction.value}"):
                    st.write(f"**Indicators Used:** {', '.join(signal.indicators_used)}")
                    st.write(f"**Parameters:** {signal.parameters}")
                    if signal.notes:
                        st.write(f"**Notes:** {signal.notes}")
                    st.write(f"**Expires:** {signal.expires_at}")

                    if st.button("Track Signal", key=f"track_{signal.signal_id}"):
                        tracker.start_tracking(signal)
                        st.success("Started tracking signal")
        else:
            st.warning("No signals generated for current conditions")

    # Active signals
    st.markdown("---")
    st.markdown("#### Active Signals")

    active = tracker.get_active_signals(symbol)
    if active:
        active_data = []
        for perf in active:
            active_data.append({
                "Symbol": perf.symbol,
                "Type": perf.signal_type.value,
                "Direction": perf.direction.value,
                "Entry": f"${perf.entry_price:.2f}",
                "Max Favorable": f"{perf.max_favorable:.2f}" if perf.max_favorable else "N/A",
                "Max Adverse": f"{perf.max_adverse:.2f}" if perf.max_adverse else "N/A",
                "Opened": perf.opened_at.strftime("%Y-%m-%d %H:%M"),
            })

        st.dataframe(pd.DataFrame(active_data), use_container_width=True, hide_index=True)
    else:
        st.info("No active signals being tracked")

# --- Tab 3: Performance ---
with tab3:
    st.subheader("Signal Performance")

    # Summary stats
    summary = tracker.get_summary_stats()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Completed", summary.get("total_completed", 0))
    col2.metric("Win Rate", f"{summary.get('win_rate', 0):.1%}")
    col3.metric("Avg Return", f"{summary.get('avg_return', 0):.2f}%")
    col4.metric("Profit Factor", f"{summary.get('profit_factor', 0):.2f}")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Wins", summary.get("wins", 0))
    col6.metric("Losses", summary.get("losses", 0))
    col7.metric("Best Return", f"{summary.get('best_return', 0):.2f}%")
    col8.metric("Worst Return", f"{summary.get('worst_return', 0):.2f}%")

    # Performance by regime
    st.markdown("---")
    st.markdown("#### Performance by Regime")

    regime_accuracy = tracker.get_accuracy_by_regime()
    if regime_accuracy:
        regime_df = pd.DataFrame([
            {
                "Regime": k.replace("_", " ").title(),
                "Signals": v["total_signals"],
                "Win Rate": f"{v['win_rate']:.1%}",
                "Avg Return": f"{v['avg_return']:.2f}%",
            }
            for k, v in regime_accuracy.items()
        ])
        st.dataframe(regime_df, use_container_width=True, hide_index=True)
    else:
        st.info("No performance data yet")

    # Performance by signal type
    st.markdown("#### Performance by Signal Type")

    signal_accuracy = tracker.get_accuracy_by_signal_type()
    if signal_accuracy:
        signal_df = pd.DataFrame([
            {
                "Signal Type": k.replace("_", " ").title(),
                "Signals": v["total_signals"],
                "Win Rate": f"{v['win_rate']:.1%}",
                "Avg Return": f"{v['avg_return']:.2f}%",
            }
            for k, v in signal_accuracy.items()
        ])
        st.dataframe(signal_df, use_container_width=True, hide_index=True)
    else:
        st.info("No performance data yet")

    # Recent signals
    st.markdown("---")
    st.markdown("#### Recent Signals")

    recent = tracker.get_recent_signals(10)
    if recent:
        recent_data = []
        for perf in recent:
            recent_data.append({
                "Symbol": perf.symbol,
                "Type": perf.signal_type.value,
                "Direction": perf.direction.value,
                "Regime": perf.regime_type.value,
                "Return": f"{perf.return_pct:.2f}%" if perf.return_pct else "N/A",
                "Outcome": perf.outcome.value,
                "Duration": f"{perf.duration_hours:.1f}h" if perf.duration_hours else "N/A",
            })

        st.dataframe(pd.DataFrame(recent_data), use_container_width=True, hide_index=True)

# --- Tab 4: Parameters ---
with tab4:
    st.subheader("Regime Parameters")

    # Select regime
    selected_regime = st.selectbox(
        "Select Regime",
        [r.value for r in RegimeType],
        format_func=lambda x: x.replace("_", " ").title()
    )

    params = REGIME_PARAMETERS.get(selected_regime, {})

    st.markdown("#### Current Parameters")

    param_data = []
    for key, value in params.items():
        if key == "preferred_signals":
            continue
        param_data.append({
            "Parameter": key.replace("_", " ").title(),
            "Default Value": value,
            "Optimized Value": optimizer.get_optimized_value(
                RegimeType(selected_regime),
                SignalType.MOMENTUM,
                "general",
                key
            ),
        })

    st.dataframe(pd.DataFrame(param_data), use_container_width=True, hide_index=True)

    # Optimization
    st.markdown("---")
    st.markdown("#### Parameter Optimization")

    if st.button("Run Optimization"):
        optimized = optimizer.optimize_parameters(RegimeType(selected_regime))

        if optimized:
            st.success(f"Optimized {len(optimized)} parameters")
            st.json(optimized)
        else:
            st.warning("Not enough performance data for optimization")

    # Optimization stats
    opt_stats = optimizer.get_performance_stats(RegimeType(selected_regime))
    if opt_stats.get("total_signals", 0) > 0:
        st.markdown("#### Optimization Data")
        col1, col2, col3 = st.columns(3)
        col1.metric("Sample Size", opt_stats["total_signals"])
        col2.metric("Win Rate", f"{opt_stats['win_rate']:.1%}")
        col3.metric("Avg Return", f"{opt_stats['avg_return']:.2f}%")

    if st.button("Reset Optimization"):
        count = optimizer.reset_optimization(RegimeType(selected_regime))
        st.info(f"Reset {count} parameters")

# --- Tab 5: History ---
with tab5:
    st.subheader("Regime History")

    history = detector.get_regime_history(symbol, limit=50)

    if history:
        history_data = []
        for state in history:
            history_data.append({
                "Timestamp": state.timestamp.strftime("%Y-%m-%d %H:%M"),
                "Regime": state.regime_type.value.replace("_", " ").title(),
                "Confidence": f"{state.confidence:.1%}",
                "Trend": state.trend_direction.value if state.trend_direction else "N/A",
                "Volatility": state.volatility_level.value if state.volatility_level else "N/A",
                "Duration": state.regime_duration_days,
            })

        st.dataframe(
            pd.DataFrame(history_data),
            use_container_width=True,
            hide_index=True
        )

        # Regime transitions
        st.markdown("#### Regime Transitions")

        transitions = []
        for i in range(1, len(history)):
            if history[i].regime_type != history[i-1].regime_type:
                transitions.append({
                    "Timestamp": history[i].timestamp.strftime("%Y-%m-%d"),
                    "From": history[i-1].regime_type.value.replace("_", " ").title(),
                    "To": history[i].regime_type.value.replace("_", " ").title(),
                })

        if transitions:
            st.dataframe(pd.DataFrame(transitions), use_container_width=True, hide_index=True)
        else:
            st.info("No regime transitions detected")
    else:
        st.info("No regime history available")

# --- Statistics ---
st.markdown("---")
st.markdown("### System Statistics")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("#### Regime Types")
    for regime in RegimeType:
        st.write(f"- {regime.value.replace('_', ' ').title()}")

with col2:
    st.markdown("#### Signal Types")
    for signal in SignalType:
        st.write(f"- {signal.value.replace('_', ' ').title()}")

with col3:
    st.markdown("#### Detection Methods")
    for method in DetectionMethod:
        st.write(f"- {method.value.replace('_', ' ').title()}")
