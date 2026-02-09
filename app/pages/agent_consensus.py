"""Agent Consensus Dashboard (PRD-154).

Four-tab Streamlit dashboard for multi-agent trade consensus,
vote visualization, debate monitoring, and audit trail.
"""

import streamlit as st

from src.agent_consensus.voter import VoterConfig, VoteCollector
from src.agent_consensus.consensus import ConsensusConfig, ConsensusEngine
from src.agent_consensus.debate import DebateManager
from src.agent_consensus.auditor import ConsensusAuditor

st.header("Agent Consensus")
st.caption("PRD-154 · Multi-agent trade signal voting & consensus engine")

tab1, tab2, tab3, tab4 = st.tabs([
    "Vote", "Consensus", "Debate", "Audit",
])

# ── Tab 1: Vote ──────────────────────────────────────────────────────

with tab1:
    st.subheader("Agent Voting Panel")

    col1, col2 = st.columns(2)
    with col1:
        ticker = st.text_input("Ticker", "AAPL", key="vote_ticker")
        direction = st.selectbox("Direction", ["long", "short"], key="vote_dir")
        conviction = st.slider("Conviction", 0, 100, 75, key="vote_conv")
    with col2:
        entry = st.number_input("Entry Price", value=150.0, key="vote_entry")
        stop = st.number_input("Stop Loss", value=146.0, key="vote_stop")
        target = st.number_input("Target Price", value=160.0, key="vote_target")

    signal_type = st.selectbox("Signal Type", [
        "cloud_cross_bullish", "cloud_cross_bearish",
        "cloud_flip_bullish", "cloud_flip_bearish",
        "cloud_bounce_long", "cloud_bounce_short",
        "trend_aligned_long", "trend_aligned_short",
        "momentum_exhaustion", "mtf_confluence",
    ], key="vote_sigtype")

    if st.button("Collect Votes", key="collect"):
        signal = {
            "ticker": ticker, "direction": direction,
            "signal_type": signal_type, "conviction": conviction,
            "entry_price": entry, "stop_loss": stop, "target_price": target,
        }
        vc = VoteCollector()
        votes = vc.collect_votes(signal)

        for v in votes:
            icon = {"approve": "✅", "reject": "❌", "abstain": "⚪"}.get(
                v.decision, "⚪"
            )
            risk_icon = {"low": "🟢", "medium": "🟡", "high": "🟠", "extreme": "🔴"}.get(
                v.risk_assessment, "⚪"
            )
            st.write(
                f"{icon} **{v.agent_type}**: {v.decision} "
                f"(conf={v.confidence:.0%}) {risk_icon} "
                f"— {v.reasoning[:80]}"
            )

# ── Tab 2: Consensus ─────────────────────────────────────────────────

with tab2:
    st.subheader("Consensus Engine")

    threshold = st.slider("Approval Threshold", 0.3, 0.9, 0.6, key="cons_thresh")
    veto_enabled = st.checkbox("Enable Risk Sentinel Veto", True, key="cons_veto")

    demo_signal = {
        "ticker": "NVDA", "direction": "long",
        "signal_type": "trend_aligned_long", "conviction": 70,
        "entry_price": 800.0, "stop_loss": 780.0, "target_price": 850.0,
    }

    if st.button("Run Consensus", key="run_cons"):
        vc = VoteCollector()
        votes = vc.collect_votes(demo_signal)

        veto_agents = ["risk_sentinel"] if veto_enabled else []
        ce = ConsensusEngine(ConsensusConfig(
            approval_threshold=threshold,
            veto_agents=veto_agents,
        ))
        result = ce.evaluate(votes)

        decision_icons = {"execute": "🟢", "reject": "🔴", "hold": "🟡"}
        icon = decision_icons.get(result.decision, "⚪")
        st.markdown(f"### {icon} {result.decision.upper()}")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Approval Rate", f"{result.approval_rate:.0%}")
        m2.metric("Weighted Score", f"{result.weighted_score:.3f}")
        m3.metric("Confidence", f"{result.confidence:.0%}")
        m4.metric("Vetoed", "Yes" if result.vetoed else "No")

        m5, m6, m7, m8 = st.columns(4)
        m5.metric("Approve", result.approve_count)
        m6.metric("Reject", result.reject_count)
        m7.metric("Abstain", result.abstain_count)
        m8.metric("Risk", result.risk_assessment)

# ── Tab 3: Debate ────────────────────────────────────────────────────

with tab3:
    st.subheader("Structured Debate")

    st.markdown("""
    When agents disagree (approval rate between 40-60%), a structured
    debate process runs up to 3 rounds where agents can shift positions
    based on counter-arguments. If no consensus emerges, the escalation
    agent (alpha_strategist) makes the final call.
    """)

    if st.button("Simulate Debate", key="sim_debate"):
        # Create a borderline signal
        sig = {
            "ticker": "MSFT", "direction": "long",
            "signal_type": "cloud_flip_bullish", "conviction": 55,
            "entry_price": 400.0, "stop_loss": 392.0, "target_price": 420.0,
        }
        vc = VoteCollector(VoterConfig(
            panel_agents=["alpha_strategist", "growth_hunter",
                          "income_architect", "research_analyst", "market_scout"],
        ))
        votes = vc.collect_votes(sig)
        ce = ConsensusEngine(ConsensusConfig(veto_agents=[]))
        result = ce.evaluate(votes)

        dm = DebateManager()
        if dm.should_debate(result):
            debate = dm.run_debate(votes, sig)
            st.write(f"**Rounds:** {len(debate.rounds)}")
            st.write(f"**Minds Changed:** {debate.minds_changed}")
            st.write(f"**Escalated:** {debate.escalated}")
            st.write(f"**Final Decision:** {debate.final_decision}")
            st.write(f"**Approval:** {debate.initial_approval_rate:.0%} → {debate.final_approval_rate:.0%}")

            for r in debate.rounds:
                with st.expander(f"Round {r.round_number} ({r.shift_count} shifts)"):
                    for arg in r.arguments:
                        st.write(f"  **{arg['agent']}** ({arg['position']}): {arg['argument'][:100]}")
        else:
            st.info(f"No debate needed — approval rate {result.approval_rate:.0%}")

# ── Tab 4: Audit ─────────────────────────────────────────────────────

with tab4:
    st.subheader("Audit Trail")

    auditor = ConsensusAuditor()

    # Simulate a few decisions
    vc = VoteCollector()
    ce = ConsensusEngine()
    for sig in [
        {"ticker": "AAPL", "direction": "long", "signal_type": "cloud_cross_bullish",
         "conviction": 80, "entry_price": 150, "stop_loss": 146, "target_price": 160},
        {"ticker": "TSLA", "direction": "short", "signal_type": "cloud_bounce_short",
         "conviction": 45, "entry_price": 200, "stop_loss": 215, "target_price": 180},
        {"ticker": "NVDA", "direction": "long", "signal_type": "trend_aligned_long",
         "conviction": 90, "entry_price": 800, "stop_loss": 780, "target_price": 850},
    ]:
        votes = vc.collect_votes(sig)
        result = ce.evaluate(votes)
        auditor.record(sig, votes, result)

    stats = auditor.get_approval_stats()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Decisions", stats["total_decisions"])
    m2.metric("Approved", stats["approved"])
    m3.metric("Rejected", stats["rejected"])
    m4.metric("Vetoed", stats["vetoed"])

    st.metric("Avg Approval Rate", f"{stats['avg_approval_rate']:.0%}")

    st.divider()
    st.subheader("Per-Agent Statistics")
    agent_stats = auditor.get_agent_stats()
    for agent, data in sorted(agent_stats.items()):
        st.write(
            f"**{agent}**: {data['total_votes']} votes, "
            f"{data['approve_pct']:.0%} approve, "
            f"avg conf {data['avg_confidence']:.0%}"
        )
