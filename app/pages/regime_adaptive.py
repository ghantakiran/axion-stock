"""Regime-Adaptive Strategy Dashboard (PRD-155).

Four-tab Streamlit dashboard for regime profiles, config adaptation,
performance tuning, and regime transition monitoring.
"""

import streamlit as st

from src.regime_adaptive.profiles import ProfileRegistry
from src.regime_adaptive.adapter import AdapterConfig, RegimeAdapter
from src.regime_adaptive.tuner import PerformanceTuner
from src.regime_adaptive.monitor import RegimeMonitor

st.header("Regime-Adaptive Strategy")
st.caption("PRD-155 · Dynamic parameter adjustment based on market regimes")

tab1, tab2, tab3, tab4 = st.tabs([
    "Profiles", "Adaptation", "Tuning", "Monitor",
])

# ── Tab 1: Profiles ──────────────────────────────────────────────────

with tab1:
    st.subheader("Strategy Profiles by Regime")

    registry = ProfileRegistry()
    profiles = registry.get_all_profiles()

    for regime, profile in profiles.items():
        with st.expander(f"{'🟢' if regime == 'bull' else '🔴' if regime == 'bear' else '🟡' if regime == 'sideways' else '🟣'} {profile.name}"):
            c1, c2, c3 = st.columns(3)
            c1.metric("Max Risk/Trade", f"{profile.max_risk_per_trade:.0%}")
            c2.metric("Max Positions", profile.max_concurrent_positions)
            c3.metric("Daily Loss Limit", f"{profile.daily_loss_limit:.0%}")

            c4, c5, c6 = st.columns(3)
            c4.metric("R:R Target", f"{profile.reward_to_risk_target:.1f}")
            c5.metric("Min Conviction", profile.min_conviction)
            c6.metric("Size Multiplier", f"{profile.position_size_multiplier:.1f}x")

            st.write(f"**Time Stop:** {profile.time_stop_minutes}min | **Trailing:** {profile.trailing_stop_cloud}")
            st.write(f"**Scale-in:** {'Yes' if profile.scale_in_enabled else 'No'} | **Loss Threshold:** {profile.consecutive_loss_threshold}")
            st.write(f"**Preferred:** {', '.join(profile.preferred_signal_types[:3])}")
            st.write(f"**Avoid:** {', '.join(profile.avoid_signal_types[:3])}")

    st.divider()
    st.subheader("Blended Profile Preview")
    blend_regime = st.selectbox("Regime", ["bull", "bear", "crisis"], key="blend_reg")
    blend_conf = st.slider("Confidence", 0.3, 1.0, 0.55, key="blend_conf")
    blended = registry.get_blended_profile(blend_regime, blend_conf)
    st.write(f"**{blended.name}** — risk={blended.max_risk_per_trade:.1%}, "
             f"positions={blended.max_concurrent_positions}, "
             f"min_conviction={blended.min_conviction}")

# ── Tab 2: Adaptation ────────────────────────────────────────────────

with tab2:
    st.subheader("Config Adaptation")

    regime = st.selectbox("Current Regime", ["bull", "bear", "sideways", "crisis"], key="adapt_reg")
    confidence = st.slider("Regime Confidence", 0.3, 1.0, 0.8, key="adapt_conf")

    # Default executor config
    default_config = {
        "max_risk_per_trade": 0.05,
        "max_concurrent_positions": 10,
        "daily_loss_limit": 0.10,
        "max_single_stock_exposure": 0.15,
        "max_sector_exposure": 0.30,
        "reward_to_risk_target": 2.0,
        "time_stop_minutes": 120,
        "trailing_stop_cloud": "pullback",
        "scale_in_enabled": True,
        "consecutive_loss_threshold": 3,
    }

    if st.button("Adapt Config", key="run_adapt"):
        adapter = RegimeAdapter()
        adaptation = adapter.adapt(default_config, regime, confidence)

        st.write(f"**Profile Used:** {adaptation.profile_used}")
        st.write(f"**Changes:** {len(adaptation.changes)}")

        for change in adaptation.changes:
            direction = "↑" if str(change.get("new_value", "")) > str(change.get("old_value", "")) else "↓"
            st.write(
                f"  {direction} **{change['field']}**: "
                f"`{change['old_value']}` → `{change['new_value']}` "
                f"— {change['reason']}"
            )

    st.divider()
    st.subheader("Signal Filtering")

    demo_signals = [
        {"signal_type": "cloud_cross_bullish", "ticker": "AAPL", "conviction": 75},
        {"signal_type": "cloud_bounce_short", "ticker": "TSLA", "conviction": 60},
        {"signal_type": "trend_aligned_long", "ticker": "MSFT", "conviction": 80},
        {"signal_type": "momentum_exhaustion", "ticker": "GOOG", "conviction": 55},
    ]

    if st.button("Filter Signals", key="filter_sig"):
        adapter = RegimeAdapter()
        filtered = adapter.filter_signals(demo_signals, regime, confidence)
        st.write(f"**{len(filtered)}/{len(demo_signals)}** signals passed filter")
        for sig in filtered:
            boost = sig.get("regime_boost", 0.0)
            icon = "⬆️" if boost > 0 else "➡️"
            st.write(f"  {icon} {sig['signal_type']} ({sig['ticker']}) boost={boost:.1f}")

# ── Tab 3: Tuning ────────────────────────────────────────────────────

with tab3:
    st.subheader("Performance-Based Tuning")

    st.markdown("""
    The tuner monitors recent trade performance and automatically
    tightens risk parameters after consecutive losses, or loosens
    them after a winning streak with good win rate.
    """)

    tuner = PerformanceTuner()

    # Simulate a losing streak
    if st.button("Simulate Losing Streak", key="sim_loss"):
        for pnl in [-0.02, -0.01, -0.03, -0.015]:
            tuner.record_trade(pnl)
        result = tuner.tune({
            "max_risk_per_trade": 0.05,
            "daily_loss_limit": 0.10,
            "max_concurrent_positions": 10,
            "reward_to_risk_target": 2.0,
        })
        st.write(f"**Tightened:** {result.is_tightened} | **Factor:** {result.overall_factor:.2f}")
        for adj in result.adjustments:
            st.write(f"  ↓ {adj.field}: {adj.original_value} → {adj.adjusted_value} ({adj.reason})")

    # Simulate a winning streak
    if st.button("Simulate Winning Streak", key="sim_win"):
        tuner2 = PerformanceTuner()
        for pnl in [0.03, 0.02, 0.04, 0.015, 0.025, 0.01]:
            tuner2.record_trade(pnl)
        result = tuner2.tune({
            "max_risk_per_trade": 0.05,
            "daily_loss_limit": 0.10,
            "max_concurrent_positions": 10,
            "reward_to_risk_target": 2.0,
        })
        st.write(f"**Loosened:** {result.is_loosened} | **Factor:** {result.overall_factor:.2f}")
        for adj in result.adjustments:
            st.write(f"  ↑ {adj.field}: {adj.original_value} → {adj.adjusted_value} ({adj.reason})")

# ── Tab 4: Monitor ───────────────────────────────────────────────────

with tab4:
    st.subheader("Regime Transition Monitor")

    monitor = RegimeMonitor()

    # Simulate regime transitions
    transitions = [
        ("sideways", 0.7, "ensemble"),
        ("bull", 0.8, "hmm"),
        ("bull", 0.85, "ensemble"),
        ("bear", 0.65, "clustering"),
        ("crisis", 0.9, "ensemble"),
    ]

    for reg, conf, method in transitions:
        t = monitor.update(reg, conf, method)
        if t:
            st.write(f"🔄 **{t.from_regime}** → **{t.to_regime}** (conf={t.confidence:.0%}, method={t.method})")

    state = monitor.get_state()
    status_icons = {"bull": "🟢", "bear": "🔴", "sideways": "🟡", "crisis": "🟣"}
    icon = status_icons.get(state.current_regime, "⚪")

    st.markdown(f"### {icon} Current: {state.current_regime.upper()}")

    m1, m2, m3 = st.columns(3)
    m1.metric("Confidence", f"{state.current_confidence:.0%}")
    m2.metric("Transitions (1h)", state.transitions_last_hour)
    m3.metric("Circuit Breaker", "ACTIVE" if state.is_circuit_broken else "Normal")

    freq = monitor.get_transition_frequency()
    if freq:
        st.divider()
        st.subheader("Transition Frequency")
        for pair, count in sorted(freq.items(), key=lambda x: -x[1]):
            st.write(f"  {pair}: {count}x")
