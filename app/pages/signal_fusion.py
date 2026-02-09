"""Signal Fusion Dashboard (PRD-147).

4 tabs: Signal Scanner, Fusion Results, Recommendations, Agent Config.
"""

try:
    import streamlit as st
    st.set_page_config(page_title="Signal Fusion", layout="wide")
except Exception:
    import streamlit as st

from src.signal_fusion import (
    AgentConfig,
    FusionAgent,
    FusionConfig,
    RecommenderConfig,
    SignalSource,
)

st.title("Signal Fusion Agent")
st.caption("Autonomous signal fusion -- collect, fuse, and recommend")

# ── Session state defaults ────────────────────────────────────────────

if "sf_agent" not in st.session_state:
    st.session_state.sf_agent = FusionAgent()
if "sf_last_state" not in st.session_state:
    st.session_state.sf_last_state = None

agent: FusionAgent = st.session_state.sf_agent

tab1, tab2, tab3, tab4 = st.tabs([
    "Signal Scanner",
    "Fusion Results",
    "Recommendations",
    "Agent Config",
])

# ── Tab 1: Signal Scanner ────────────────────────────────────────────

with tab1:
    st.subheader("Signal Scanner")

    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("Run Scan", type="primary", use_container_width=True):
            state = agent.scan()
            st.session_state.sf_last_state = state
            st.toast(f"Scan complete: {state.signals_collected} signals collected")

    state = st.session_state.sf_last_state
    if state is not None:
        m1, m2, m3 = st.columns(3)
        m1.metric("Signals Collected", state.signals_collected)
        m2.metric("Fusions Produced", state.fusions_produced)
        m3.metric("Recommendations", len(state.recommendations))

        if state.signals_collected > 0:
            st.markdown("**Collected Signals by Source**")
            # Build a table of signals from the last scan
            rows = []
            for rec in state.recommendations:
                fused = rec.fused_signal
                for src in fused.agreeing_sources + fused.dissenting_sources:
                    rows.append({
                        "Symbol": fused.symbol,
                        "Source": src,
                        "Direction": fused.direction,
                    })
            if rows:
                st.dataframe(rows, use_container_width=True)
            else:
                st.info("No signal details available for this scan.")
    else:
        st.info("Click 'Run Scan' to collect signals from all sources.")

# ── Tab 2: Fusion Results ────────────────────────────────────────────

with tab2:
    st.subheader("Fusion Results")

    state = st.session_state.sf_last_state
    if state is not None and state.recommendations:
        fusion_rows = []
        for rec in state.recommendations:
            f = rec.fused_signal
            fusion_rows.append({
                "Symbol": f.symbol,
                "Direction": f.direction,
                "Composite Score": round(f.composite_score, 1),
                "Confidence": f"{f.confidence:.0%}",
                "Sources": f.source_count,
                "Agreeing": len(f.agreeing_sources),
                "Dissenting": len(f.dissenting_sources),
            })
        st.dataframe(fusion_rows, use_container_width=True)

        st.markdown("**Agreement Distribution**")
        chart_data = {row["Symbol"]: row["Agreeing"] for row in fusion_rows}
        st.bar_chart(chart_data)
    else:
        st.info("Run a scan first to see fusion results.")

# ── Tab 3: Recommendations ───────────────────────────────────────────

with tab3:
    st.subheader("Trade Recommendations")

    state = st.session_state.sf_last_state
    if state is not None and state.recommendations:
        for i, rec in enumerate(state.recommendations, 1):
            badge_color = {
                "STRONG_BUY": "green",
                "BUY": "blue",
                "HOLD": "orange",
                "SELL": "red",
                "STRONG_SELL": "red",
            }.get(rec.action, "gray")

            col_a, col_b, col_c = st.columns([1, 1, 2])
            with col_a:
                st.markdown(f"**#{i} {rec.symbol}**")
                st.markdown(f":{badge_color}[{rec.action}]")
            with col_b:
                st.metric("Position Size", f"{rec.position_size_pct:.1f}%")
                st.metric("Stop Loss", f"{rec.stop_loss_pct:.1f}%")
            with col_c:
                st.metric("Composite Score", f"{rec.fused_signal.composite_score:+.1f}")
                st.metric("Take Profit", f"{rec.take_profit_pct:.1f}%")

            with st.expander(f"Reasoning for {rec.symbol}"):
                st.write(rec.reasoning)
                st.write(f"**Time Horizon:** {rec.time_horizon}")
                st.write(f"**Risk Level:** {rec.risk_level}")
            st.divider()
    else:
        st.info("Run a scan to generate recommendations.")

# ── Tab 4: Agent Config ──────────────────────────────────────────────

with tab4:
    st.subheader("Agent Configuration")

    st.markdown("**Source Weights**")
    weights = {}
    for source in SignalSource:
        weights[source] = st.slider(
            f"{source.value}",
            min_value=0.0,
            max_value=1.0,
            value=0.15,
            step=0.05,
            key=f"weight_{source.value}",
        )

    st.markdown("**Recommender Settings**")
    c1, c2 = st.columns(2)
    with c1:
        min_conf = st.slider("Min Confidence", 0.0, 1.0, 0.5, 0.05)
        max_pos = st.number_input("Max Positions", 1, 50, 10)
    with c2:
        scan_interval = st.number_input("Scan Interval (min)", 1, 120, 15)
        auto_exec = st.toggle("Auto-Execute", value=False)

    if st.button("Apply Config", type="primary"):
        fusion_config = FusionConfig(source_weights=weights)
        recommender_config = RecommenderConfig(
            min_confidence=min_conf,
            max_positions=max_pos,
        )
        agent_config = AgentConfig(
            scan_interval_minutes=scan_interval,
            auto_execute=auto_exec,
        )
        st.session_state.sf_agent = FusionAgent(
            agent_config=agent_config,
            fusion_config=fusion_config,
            recommender_config=recommender_config,
        )
        st.toast("Configuration applied successfully!")
