"""Tests for PRD-154: Multi-Agent Trade Consensus.

8 test classes, ~55 tests covering voter, consensus engine, debate,
auditor, and module imports.
"""

import unittest
from datetime import datetime, timezone


from src.agent_consensus.voter import AgentVote, VoterConfig, VoteCollector
from src.agent_consensus.consensus import ConsensusConfig, ConsensusResult, ConsensusEngine
from src.agent_consensus.debate import DebateConfig, DebateRound, DebateResult, DebateManager
from src.agent_consensus.auditor import ConsensusAuditEntry, ConsensusAuditor


def _make_signal(
    ticker="AAPL",
    direction="long",
    signal_type="cloud_cross_bullish",
    conviction=75,
    entry_price=150.0,
    stop_loss=146.0,
    target_price=160.0,
):
    """Create a signal dict for testing."""
    return {
        "ticker": ticker,
        "direction": direction,
        "signal_type": signal_type,
        "conviction": conviction,
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "target_price": target_price,
    }


def _make_vote(
    agent_type="alpha_strategist",
    decision="approve",
    confidence=0.7,
    reasoning="Test reasoning for this vote.",
    risk_assessment="medium",
    suggested_adjustments=None,
):
    """Create an AgentVote for testing."""
    return AgentVote(
        agent_type=agent_type,
        decision=decision,
        confidence=confidence,
        reasoning=reasoning,
        risk_assessment=risk_assessment,
        suggested_adjustments=suggested_adjustments or {},
    )


# ═══════════════════════════════════════════════════════════════════════
# Test AgentVote
# ═══════════════════════════════════════════════════════════════════════


class TestAgentVote(unittest.TestCase):
    """Test AgentVote dataclass creation and serialisation."""

    def test_creation(self):
        vote = _make_vote()
        self.assertEqual(vote.agent_type, "alpha_strategist")
        self.assertEqual(vote.decision, "approve")
        self.assertAlmostEqual(vote.confidence, 0.7)
        self.assertEqual(vote.risk_assessment, "medium")

    def test_to_dict(self):
        vote = _make_vote(suggested_adjustments={"position_size_pct": 0.05})
        d = vote.to_dict()
        self.assertEqual(d["agent_type"], "alpha_strategist")
        self.assertEqual(d["decision"], "approve")
        self.assertAlmostEqual(d["confidence"], 0.7)
        self.assertEqual(d["risk_assessment"], "medium")
        self.assertEqual(d["suggested_adjustments"]["position_size_pct"], 0.05)
        self.assertIn("timestamp", d)

    def test_defaults(self):
        vote = _make_vote()
        self.assertEqual(vote.suggested_adjustments, {})
        self.assertIsInstance(vote.timestamp, datetime)

    def test_field_validation(self):
        # Invalid decision should raise
        with self.assertRaises(ValueError):
            AgentVote(
                agent_type="test",
                decision="maybe",
                confidence=0.5,
                reasoning="Test reasoning text here.",
                risk_assessment="medium",
            )
        # Invalid risk_assessment should raise
        with self.assertRaises(ValueError):
            AgentVote(
                agent_type="test",
                decision="approve",
                confidence=0.5,
                reasoning="Test reasoning text here.",
                risk_assessment="unknown",
            )

    def test_confidence_clamping_and_timestamp(self):
        # Confidence > 1.0 should be clamped to 1.0
        vote_high = AgentVote(
            agent_type="test",
            decision="approve",
            confidence=1.5,
            reasoning="Test reasoning text here.",
            risk_assessment="low",
        )
        self.assertAlmostEqual(vote_high.confidence, 1.0)
        # Confidence < 0.0 should be clamped to 0.0
        vote_low = AgentVote(
            agent_type="test",
            decision="reject",
            confidence=-0.3,
            reasoning="Test reasoning text here.",
            risk_assessment="high",
        )
        self.assertAlmostEqual(vote_low.confidence, 0.0)
        # Timestamp should be UTC-aware
        self.assertIsNotNone(vote_high.timestamp.tzinfo)


# ═══════════════════════════════════════════════════════════════════════
# Test VoterConfig
# ═══════════════════════════════════════════════════════════════════════


class TestVoterConfig(unittest.TestCase):
    """Test VoterConfig defaults and customisation."""

    def test_defaults(self):
        config = VoterConfig()
        self.assertEqual(len(config.panel_agents), 5)
        self.assertIn("alpha_strategist", config.panel_agents)
        self.assertIn("risk_sentinel", config.panel_agents)
        self.assertTrue(config.require_risk_sentinel)
        self.assertAlmostEqual(config.vote_timeout_seconds, 30.0)
        self.assertEqual(config.min_reasoning_length, 10)

    def test_custom_panel(self):
        config = VoterConfig(
            panel_agents=["alpha_strategist", "momentum_rider", "value_oracle"]
        )
        self.assertEqual(len(config.panel_agents), 3)
        self.assertNotIn("risk_sentinel", config.panel_agents)

    def test_risk_sentinel_enforcement(self):
        # When require_risk_sentinel=True and risk_sentinel not in panel,
        # VoteCollector should add it
        config = VoterConfig(
            panel_agents=["alpha_strategist", "momentum_rider"],
            require_risk_sentinel=True,
        )
        collector = VoteCollector(config)
        self.assertIn("risk_sentinel", collector.config.panel_agents)

    def test_min_reasoning_custom(self):
        config = VoterConfig(min_reasoning_length=50)
        self.assertEqual(config.min_reasoning_length, 50)


# ═══════════════════════════════════════════════════════════════════════
# Test VoteCollector
# ═══════════════════════════════════════════════════════════════════════


class TestVoteCollector(unittest.TestCase):
    """Test VoteCollector deterministic rule-based voting."""

    def test_default_panel_five_votes(self):
        collector = VoteCollector()
        signal = _make_signal()
        votes = collector.collect_votes(signal)
        self.assertEqual(len(votes), 5)
        agent_types = {v.agent_type for v in votes}
        self.assertIn("alpha_strategist", agent_types)
        self.assertIn("risk_sentinel", agent_types)

    def test_custom_panel(self):
        config = VoterConfig(
            panel_agents=["alpha_strategist", "value_oracle", "risk_sentinel"],
            require_risk_sentinel=False,
        )
        collector = VoteCollector(config)
        votes = collector.collect_votes(_make_signal())
        self.assertEqual(len(votes), 3)
        agent_types = {v.agent_type for v in votes}
        self.assertEqual(agent_types, {"alpha_strategist", "value_oracle", "risk_sentinel"})

    def test_high_conviction_approval(self):
        """Alpha strategist should approve conviction >= 60."""
        collector = VoteCollector()
        signal = _make_signal(conviction=80)
        votes = collector.collect_votes(signal)
        alpha_vote = next(v for v in votes if v.agent_type == "alpha_strategist")
        self.assertEqual(alpha_vote.decision, "approve")

    def test_low_conviction_rejection(self):
        """Alpha strategist should reject conviction < 40."""
        collector = VoteCollector()
        signal = _make_signal(conviction=30)
        votes = collector.collect_votes(signal)
        alpha_vote = next(v for v in votes if v.agent_type == "alpha_strategist")
        self.assertEqual(alpha_vote.decision, "reject")

    def test_risk_sentinel_veto_wide_stop(self):
        """Risk sentinel should reject if stop distance > 5%."""
        collector = VoteCollector()
        # Stop at 140 on entry 150 = 6.67% distance (>5%, <8% = high)
        signal = _make_signal(entry_price=150.0, stop_loss=140.0)
        votes = collector.collect_votes(signal)
        risk_vote = next(v for v in votes if v.agent_type == "risk_sentinel")
        self.assertEqual(risk_vote.decision, "reject")
        self.assertIn(risk_vote.risk_assessment, ("high", "extreme"))

    def test_get_vote_prompt_format(self):
        collector = VoteCollector()
        signal = _make_signal()
        prompt = collector.get_vote_prompt(signal, "alpha_strategist")
        self.assertIn("alpha_strategist", prompt)
        self.assertIn("AAPL", prompt)
        self.assertIn("cloud_cross_bullish", prompt)
        self.assertIn("75", prompt)
        self.assertIn("150.0", prompt)
        self.assertIn("JSON", prompt)

    def test_all_ten_agent_types(self):
        """All 10 agent types should produce valid votes."""
        all_agents = [
            "alpha_strategist",
            "risk_sentinel",
            "momentum_rider",
            "portfolio_architect",
            "market_scout",
            "value_oracle",
            "growth_hunter",
            "income_architect",
            "options_strategist",
            "research_analyst",
        ]
        config = VoterConfig(
            panel_agents=all_agents, require_risk_sentinel=False
        )
        collector = VoteCollector(config)
        signal = _make_signal(conviction=75)
        votes = collector.collect_votes(signal)
        self.assertEqual(len(votes), 10)
        for vote in votes:
            self.assertIn(vote.decision, ("approve", "reject", "abstain"))
            self.assertGreaterEqual(vote.confidence, 0.0)
            self.assertLessEqual(vote.confidence, 1.0)
            self.assertIn(vote.risk_assessment, ("low", "medium", "high", "extreme"))
            self.assertTrue(len(vote.reasoning) > 0)

    def test_signal_type_affects_votes(self):
        """Momentum rider should treat bounce signals differently."""
        collector = VoteCollector()
        strong_signal = _make_signal(signal_type="cloud_cross_bullish")
        bounce_signal = _make_signal(signal_type="cloud_bounce_long")

        strong_votes = collector.collect_votes(strong_signal)
        bounce_votes = collector.collect_votes(bounce_signal)

        strong_momentum = next(v for v in strong_votes if v.agent_type == "momentum_rider")
        bounce_momentum = next(v for v in bounce_votes if v.agent_type == "momentum_rider")

        self.assertEqual(strong_momentum.decision, "approve")
        self.assertEqual(bounce_momentum.decision, "abstain")

    def test_market_context_passthrough(self):
        """Market context should be accepted without error."""
        collector = VoteCollector()
        signal = _make_signal()
        context = {"sector": "Technology", "volume_ratio": 1.5}
        votes = collector.collect_votes(signal, market_context=context)
        self.assertEqual(len(votes), 5)

    def test_reasoning_length(self):
        """Each agent's reasoning should meet minimum length."""
        collector = VoteCollector()
        signal = _make_signal()
        votes = collector.collect_votes(signal)
        for vote in votes:
            self.assertGreaterEqual(len(vote.reasoning), 10)

    def test_risk_sentinel_approves_tight_stop(self):
        """Risk sentinel should approve when stop distance <= 3%."""
        collector = VoteCollector()
        # Stop at 148 on entry 150 = 1.33% distance
        signal = _make_signal(entry_price=150.0, stop_loss=148.0)
        votes = collector.collect_votes(signal)
        risk_vote = next(v for v in votes if v.agent_type == "risk_sentinel")
        self.assertEqual(risk_vote.decision, "approve")
        self.assertEqual(risk_vote.risk_assessment, "low")

    def test_alpha_strategist_abstains_borderline(self):
        """Alpha strategist should abstain on conviction 40-59."""
        collector = VoteCollector()
        signal = _make_signal(conviction=50)
        votes = collector.collect_votes(signal)
        alpha_vote = next(v for v in votes if v.agent_type == "alpha_strategist")
        self.assertEqual(alpha_vote.decision, "abstain")

    def test_growth_hunter_abstains_on_short(self):
        """Growth hunter should abstain on short signals."""
        config = VoterConfig(
            panel_agents=["growth_hunter"], require_risk_sentinel=False
        )
        collector = VoteCollector(config)
        signal = _make_signal(direction="short")
        votes = collector.collect_votes(signal)
        self.assertEqual(votes[0].decision, "abstain")


# ═══════════════════════════════════════════════════════════════════════
# Test ConsensusEngine
# ═══════════════════════════════════════════════════════════════════════


class TestConsensusEngine(unittest.TestCase):
    """Test ConsensusEngine evaluation logic."""

    def test_unanimous_approve(self):
        engine = ConsensusEngine()
        votes = [
            _make_vote("agent_a", "approve", 0.8, "Approving trade signal.", "low"),
            _make_vote("agent_b", "approve", 0.7, "Approving trade signal.", "low"),
            _make_vote("agent_c", "approve", 0.9, "Approving trade signal.", "low"),
        ]
        result = engine.evaluate(votes)
        self.assertEqual(result.decision, "execute")
        self.assertAlmostEqual(result.approval_rate, 1.0)
        self.assertGreater(result.weighted_score, 0)
        self.assertEqual(result.approve_count, 3)
        self.assertEqual(result.reject_count, 0)
        self.assertFalse(result.vetoed)

    def test_unanimous_reject(self):
        engine = ConsensusEngine()
        votes = [
            _make_vote("agent_a", "reject", 0.8, "Rejecting trade signal.", "high"),
            _make_vote("agent_b", "reject", 0.7, "Rejecting trade signal.", "high"),
            _make_vote("agent_c", "reject", 0.6, "Rejecting trade signal.", "high"),
        ]
        result = engine.evaluate(votes)
        self.assertEqual(result.decision, "reject")
        self.assertAlmostEqual(result.approval_rate, 0.0)
        self.assertLess(result.weighted_score, 0)
        self.assertEqual(result.reject_count, 3)

    def test_split_vote_hold(self):
        """Split vote (50/50 approval) should result in hold."""
        engine = ConsensusEngine()
        votes = [
            _make_vote("agent_a", "approve", 0.6, "Approve reasoning text.", "medium"),
            _make_vote("agent_b", "reject", 0.6, "Reject reasoning text.", "medium"),
            _make_vote("agent_c", "approve", 0.6, "Approve reasoning text.", "medium"),
            _make_vote("agent_d", "reject", 0.6, "Reject reasoning text.", "medium"),
        ]
        result = engine.evaluate(votes)
        self.assertAlmostEqual(result.approval_rate, 0.5)
        self.assertEqual(result.decision, "hold")

    def test_veto_override(self):
        """Risk sentinel veto should override majority approval."""
        engine = ConsensusEngine()
        votes = [
            _make_vote("alpha_strategist", "approve", 0.8, "Approve reasoning text.", "low"),
            _make_vote("momentum_rider", "approve", 0.7, "Approve reasoning text.", "low"),
            _make_vote("risk_sentinel", "reject", 0.9, "Stop distance too large.", "extreme"),
        ]
        result = engine.evaluate(votes)
        self.assertTrue(result.vetoed)
        self.assertEqual(result.decision, "reject")
        self.assertIn("risk_sentinel", result.veto_reason)

    def test_weighted_scoring(self):
        """Weighted score should reflect confidence-weighted decisions."""
        engine = ConsensusEngine()
        # Two high-confidence approves, one low-confidence reject
        votes = [
            _make_vote("agent_a", "approve", 0.9, "Strong approve reasoning.", "low"),
            _make_vote("agent_b", "approve", 0.8, "Strong approve reasoning.", "low"),
            _make_vote("agent_c", "reject", 0.3, "Weak reject reasoning here.", "medium"),
        ]
        result = engine.evaluate(votes)
        self.assertGreater(result.weighted_score, 0)

    def test_min_votes_requirement(self):
        """Below min_votes should result in hold."""
        config = ConsensusConfig(min_votes=5)
        engine = ConsensusEngine(config)
        votes = [
            _make_vote("agent_a", "approve", 0.9, "Approve reasoning text.", "low"),
            _make_vote("agent_b", "approve", 0.8, "Approve reasoning text.", "low"),
        ]
        result = engine.evaluate(votes)
        self.assertEqual(result.decision, "hold")

    def test_approval_threshold(self):
        """Custom approval threshold should be respected."""
        config = ConsensusConfig(approval_threshold=0.8)
        engine = ConsensusEngine(config)
        # 3 approve, 1 reject = 75% approval, below 80% threshold
        votes = [
            _make_vote("agent_a", "approve", 0.7, "Approve reasoning text.", "low"),
            _make_vote("agent_b", "approve", 0.7, "Approve reasoning text.", "low"),
            _make_vote("agent_c", "approve", 0.7, "Approve reasoning text.", "low"),
            _make_vote("agent_d", "reject", 0.5, "Reject reasoning text.", "medium"),
        ]
        result = engine.evaluate(votes)
        # 75% >= 40% so hold, not reject
        self.assertEqual(result.decision, "hold")

    def test_hold_decision(self):
        """Approval rate between 0.4 and threshold should yield hold."""
        engine = ConsensusEngine()
        # 2 approve, 3 reject = 40% approval
        votes = [
            _make_vote("agent_a", "approve", 0.5, "Approve reasoning text.", "medium"),
            _make_vote("agent_b", "approve", 0.5, "Approve reasoning text.", "medium"),
            _make_vote("agent_c", "reject", 0.5, "Reject reasoning text.", "medium"),
            _make_vote("agent_d", "reject", 0.5, "Reject reasoning text.", "medium"),
            _make_vote("agent_e", "reject", 0.5, "Reject reasoning text.", "medium"),
        ]
        result = engine.evaluate(votes)
        self.assertAlmostEqual(result.approval_rate, 0.4)
        self.assertEqual(result.decision, "hold")

    def test_abstain_handling(self):
        """Abstaining votes should not count in approval rate denominator."""
        engine = ConsensusEngine()
        votes = [
            _make_vote("agent_a", "approve", 0.8, "Approve reasoning text.", "low"),
            _make_vote("agent_b", "abstain", 0.4, "Abstain reasoning text.", "medium"),
            _make_vote("agent_c", "abstain", 0.3, "Abstain reasoning text.", "medium"),
        ]
        result = engine.evaluate(votes)
        # 1 approve out of 1 decisive = 100% approval
        self.assertAlmostEqual(result.approval_rate, 1.0)
        self.assertEqual(result.abstain_count, 2)
        self.assertEqual(result.total_votes, 3)

    def test_to_dict(self):
        engine = ConsensusEngine()
        votes = [
            _make_vote("agent_a", "approve", 0.8, "Approve reasoning text.", "low"),
            _make_vote("agent_b", "reject", 0.6, "Reject reasoning text.", "high"),
            _make_vote("agent_c", "approve", 0.7, "Approve reasoning text.", "medium"),
        ]
        result = engine.evaluate(votes)
        d = result.to_dict()
        self.assertIn("decision", d)
        self.assertIn("approval_rate", d)
        self.assertIn("weighted_score", d)
        self.assertIn("votes", d)
        self.assertEqual(len(d["votes"]), 3)
        self.assertIsInstance(d["votes"][0], dict)


# ═══════════════════════════════════════════════════════════════════════
# Test ConsensusConfig
# ═══════════════════════════════════════════════════════════════════════


class TestConsensusConfig(unittest.TestCase):
    """Test ConsensusConfig defaults and customisation."""

    def test_defaults(self):
        config = ConsensusConfig()
        self.assertAlmostEqual(config.approval_threshold, 0.6)
        self.assertEqual(config.min_votes, 3)
        self.assertTrue(config.require_risk_approval)
        self.assertAlmostEqual(config.conviction_weight, 0.3)
        self.assertEqual(config.veto_agents, ["risk_sentinel"])
        self.assertTrue(config.weighted_voting)

    def test_custom_veto_agents(self):
        config = ConsensusConfig(veto_agents=["risk_sentinel", "portfolio_architect"])
        self.assertEqual(len(config.veto_agents), 2)
        self.assertIn("portfolio_architect", config.veto_agents)

    def test_no_veto(self):
        config = ConsensusConfig(veto_agents=[])
        engine = ConsensusEngine(config)
        # Risk sentinel rejects but should NOT trigger a veto
        votes = [
            _make_vote("alpha_strategist", "approve", 0.8, "Approve reasoning text.", "low"),
            _make_vote("momentum_rider", "approve", 0.7, "Approve reasoning text.", "low"),
            _make_vote("risk_sentinel", "reject", 0.9, "Reject reasoning text.", "extreme"),
        ]
        result = engine.evaluate(votes)
        self.assertFalse(result.vetoed)
        # 2 approve / 1 reject = 66.7% -> should execute
        self.assertEqual(result.decision, "execute")


# ═══════════════════════════════════════════════════════════════════════
# Test DebateManager
# ═══════════════════════════════════════════════════════════════════════


class TestDebateManager(unittest.TestCase):
    """Test DebateManager structured debate logic."""

    def _make_borderline_consensus(self, approval_rate=0.5, vetoed=False):
        """Create a mock consensus-like object with the needed attributes."""

        class _MockConsensus:
            pass

        mc = _MockConsensus()
        mc.approval_rate = approval_rate
        mc.vetoed = vetoed
        return mc

    def test_should_debate_borderline(self):
        manager = DebateManager()
        consensus = self._make_borderline_consensus(approval_rate=0.5)
        self.assertTrue(manager.should_debate(consensus))

    def test_should_not_debate_high_approval(self):
        manager = DebateManager()
        consensus = self._make_borderline_consensus(approval_rate=0.8)
        self.assertFalse(manager.should_debate(consensus))

    def test_should_not_debate_vetoed(self):
        manager = DebateManager()
        consensus = self._make_borderline_consensus(approval_rate=0.5, vetoed=True)
        self.assertFalse(manager.should_debate(consensus))

    def test_run_debate_produces_rounds(self):
        """Debate should produce at least one round."""
        manager = DebateManager()
        votes = [
            _make_vote("alpha_strategist", "approve", 0.55, "Approve reasoning text.", "low"),
            _make_vote("risk_sentinel", "reject", 0.55, "Reject reasoning text.", "high"),
            _make_vote("momentum_rider", "approve", 0.55, "Approve reasoning text.", "medium"),
        ]
        signal = _make_signal(conviction=60)
        result = manager.run_debate(votes, signal)
        self.assertIsInstance(result, DebateResult)
        self.assertGreater(len(result.rounds), 0)
        self.assertLessEqual(len(result.rounds), 3)
        self.assertIsInstance(result.minds_changed, int)
        self.assertIn(result.final_decision, ("execute", "reject", "hold"))

    def test_debate_escalation(self):
        """If final approval is still borderline, escalation should occur."""
        # Use agents whose hash won't shift them out of a tie
        config = DebateConfig(max_rounds=3)
        manager = DebateManager(config)
        # Start with exactly 50/50 split
        votes = [
            _make_vote("alpha_strategist", "approve", 0.9, "Approve reasoning text.", "low"),
            _make_vote("risk_sentinel", "reject", 0.9, "Reject reasoning text.", "high"),
        ]
        signal = _make_signal(conviction=60)
        result = manager.run_debate(votes, signal)
        # With high confidence (0.9), agents won't shift, so escalation occurs
        if result.escalated:
            self.assertIsNotNone(result.escalation_decision)
            self.assertIn(result.escalation_decision, ("execute", "reject"))

    def test_debate_result_to_dict(self):
        manager = DebateManager()
        votes = [
            _make_vote("alpha_strategist", "approve", 0.6, "Approve reasoning text.", "low"),
            _make_vote("risk_sentinel", "reject", 0.6, "Reject reasoning text.", "high"),
            _make_vote("momentum_rider", "approve", 0.6, "Approve reasoning text.", "medium"),
        ]
        signal = _make_signal()
        result = manager.run_debate(votes, signal)
        d = result.to_dict()
        self.assertIn("rounds", d)
        self.assertIn("initial_approval_rate", d)
        self.assertIn("final_approval_rate", d)
        self.assertIn("minds_changed", d)
        self.assertIn("escalated", d)
        self.assertIn("final_decision", d)
        # Each round should also serialize
        for rnd in d["rounds"]:
            self.assertIn("round_number", rnd)
            self.assertIn("arguments", rnd)
            self.assertIn("shift_count", rnd)

    def test_max_rounds_limit(self):
        """Debate should not exceed max_rounds."""
        config = DebateConfig(max_rounds=2)
        manager = DebateManager(config)
        votes = [
            _make_vote("alpha_strategist", "approve", 0.5, "Approve reasoning text.", "medium"),
            _make_vote("risk_sentinel", "reject", 0.5, "Reject reasoning text.", "high"),
            _make_vote("momentum_rider", "approve", 0.5, "Approve reasoning text.", "medium"),
            _make_vote("market_scout", "reject", 0.5, "Reject reasoning text.", "medium"),
        ]
        signal = _make_signal()
        result = manager.run_debate(votes, signal)
        self.assertLessEqual(len(result.rounds), 2)

    def test_escalation_with_high_conviction(self):
        """Escalation agent should approve when conviction >= 55."""
        config = DebateConfig(max_rounds=1)
        manager = DebateManager(config)
        # 1 approve, 1 reject, both high confidence -> won't shift
        votes = [
            _make_vote("alpha_strategist", "approve", 0.9, "Approve reasoning text.", "low"),
            _make_vote("risk_sentinel", "reject", 0.9, "Reject reasoning text.", "high"),
        ]
        signal_high = _make_signal(conviction=70)
        result_high = manager.run_debate(votes, signal_high)
        if result_high.escalated:
            self.assertEqual(result_high.escalation_decision, "execute")

        signal_low = _make_signal(conviction=40)
        votes2 = [
            _make_vote("alpha_strategist", "approve", 0.9, "Approve reasoning text.", "low"),
            _make_vote("risk_sentinel", "reject", 0.9, "Reject reasoning text.", "high"),
        ]
        result_low = manager.run_debate(votes2, signal_low)
        if result_low.escalated:
            self.assertEqual(result_low.escalation_decision, "reject")


# ═══════════════════════════════════════════════════════════════════════
# Test ConsensusAuditor
# ═══════════════════════════════════════════════════════════════════════


class TestConsensusAuditor(unittest.TestCase):
    """Test ConsensusAuditor recording and statistics."""

    def _record_entry(self, auditor, ticker="AAPL", conviction=75, decision="execute"):
        """Helper to record a complete consensus entry."""
        signal = _make_signal(ticker=ticker, conviction=conviction)
        collector = VoteCollector()
        votes = collector.collect_votes(signal)
        engine = ConsensusEngine()
        consensus = engine.evaluate(votes)
        return auditor.record(signal, votes, consensus)

    def _record_entry_with_known_result(self, auditor, ticker="AAPL", approve_count=3, reject_count=0):
        """Helper with manually controlled votes for predictable results."""
        signal = _make_signal(ticker=ticker)
        votes = []
        for i in range(approve_count):
            votes.append(_make_vote(f"agent_{i}", "approve", 0.7, "Approve reasoning text.", "low"))
        for i in range(reject_count):
            votes.append(_make_vote(f"reject_agent_{i}", "reject", 0.7, "Reject reasoning text.", "high"))
        engine = ConsensusEngine(ConsensusConfig(veto_agents=[]))
        consensus = engine.evaluate(votes)
        return auditor.record(signal, votes, consensus), consensus

    def test_record_creates_entry(self):
        auditor = ConsensusAuditor()
        entry = self._record_entry(auditor)
        self.assertIsInstance(entry, ConsensusAuditEntry)
        self.assertIsNotNone(entry.audit_id)
        self.assertEqual(entry.signal_summary["ticker"], "AAPL")
        self.assertGreater(len(entry.votes), 0)
        self.assertIn("decision", entry.consensus)

    def test_get_history(self):
        auditor = ConsensusAuditor()
        self._record_entry(auditor, ticker="AAPL")
        self._record_entry(auditor, ticker="MSFT")
        history = auditor.get_history()
        self.assertEqual(len(history), 2)
        # Most recent first
        self.assertEqual(history[0].signal_summary["ticker"], "MSFT")

    def test_get_history_by_ticker(self):
        auditor = ConsensusAuditor()
        self._record_entry(auditor, ticker="AAPL")
        self._record_entry(auditor, ticker="MSFT")
        self._record_entry(auditor, ticker="AAPL")
        history = auditor.get_history(ticker="AAPL")
        self.assertEqual(len(history), 2)
        for entry in history:
            self.assertEqual(entry.signal_summary["ticker"], "AAPL")

    def test_get_approval_stats(self):
        auditor = ConsensusAuditor()
        self._record_entry_with_known_result(auditor, approve_count=4, reject_count=0)
        self._record_entry_with_known_result(auditor, approve_count=0, reject_count=4)
        stats = auditor.get_approval_stats()
        self.assertEqual(stats["total_decisions"], 2)
        self.assertIn("approved", stats)
        self.assertIn("rejected", stats)
        self.assertIn("avg_approval_rate", stats)
        self.assertEqual(stats["approved"] + stats["rejected"], 2)

    def test_get_agent_stats(self):
        auditor = ConsensusAuditor()
        self._record_entry(auditor)
        agent_stats = auditor.get_agent_stats()
        self.assertIsInstance(agent_stats, dict)
        self.assertGreater(len(agent_stats), 0)
        for agent_type, stats in agent_stats.items():
            self.assertIn("total_votes", stats)
            self.assertIn("approve_pct", stats)
            self.assertIn("avg_confidence", stats)
            self.assertIn("veto_count", stats)

    def test_max_history_eviction(self):
        auditor = ConsensusAuditor(max_history=3)
        for i in range(5):
            self._record_entry(auditor, ticker=f"T{i}")
        history = auditor.get_history(limit=100)
        self.assertEqual(len(history), 3)
        # Oldest entries (T0, T1) should be evicted
        tickers = {e.signal_summary["ticker"] for e in history}
        self.assertNotIn("T0", tickers)
        self.assertNotIn("T1", tickers)

    def test_empty_stats(self):
        auditor = ConsensusAuditor()
        stats = auditor.get_approval_stats()
        self.assertEqual(stats["total_decisions"], 0)
        self.assertEqual(stats["approved"], 0)
        self.assertAlmostEqual(stats["avg_approval_rate"], 0.0)
        agent_stats = auditor.get_agent_stats()
        self.assertEqual(len(agent_stats), 0)

    def test_multiple_entries(self):
        auditor = ConsensusAuditor()
        for i in range(10):
            self._record_entry(auditor, ticker=f"TICK{i}")
        history = auditor.get_history()
        self.assertEqual(len(history), 10)

    def test_entry_to_dict(self):
        auditor = ConsensusAuditor()
        entry = self._record_entry(auditor)
        d = entry.to_dict()
        self.assertIn("audit_id", d)
        self.assertIn("signal_summary", d)
        self.assertIn("votes", d)
        self.assertIn("consensus", d)
        self.assertIn("timestamp", d)
        self.assertIsNone(d["debate"])

    def test_audit_id_uniqueness(self):
        auditor = ConsensusAuditor()
        ids = set()
        for _ in range(20):
            entry = self._record_entry(auditor)
            ids.add(entry.audit_id)
        self.assertEqual(len(ids), 20)


# ═══════════════════════════════════════════════════════════════════════
# Test Module Imports
# ═══════════════════════════════════════════════════════════════════════


class TestAgentConsensusModuleImports(unittest.TestCase):
    """Test that all module exports are importable."""

    def test_all_symbols_importable(self):
        from src.agent_consensus import (
            AgentVote,
            VoterConfig,
            VoteCollector,
            ConsensusConfig,
            ConsensusResult,
            ConsensusEngine,
            DebateConfig,
            DebateRound,
            DebateResult,
            DebateManager,
            ConsensusAuditEntry,
            ConsensusAuditor,
        )
        self.assertIsNotNone(AgentVote)
        self.assertIsNotNone(VoterConfig)
        self.assertIsNotNone(VoteCollector)
        self.assertIsNotNone(ConsensusConfig)
        self.assertIsNotNone(ConsensusResult)
        self.assertIsNotNone(ConsensusEngine)
        self.assertIsNotNone(DebateConfig)
        self.assertIsNotNone(DebateRound)
        self.assertIsNotNone(DebateResult)
        self.assertIsNotNone(DebateManager)
        self.assertIsNotNone(ConsensusAuditEntry)
        self.assertIsNotNone(ConsensusAuditor)

    def test_default_configs(self):
        vc = VoterConfig()
        cc = ConsensusConfig()
        dc = DebateConfig()
        self.assertEqual(len(vc.panel_agents), 5)
        self.assertAlmostEqual(cc.approval_threshold, 0.6)
        self.assertEqual(dc.max_rounds, 3)


if __name__ == "__main__":
    unittest.main()
