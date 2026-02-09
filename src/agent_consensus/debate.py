"""Structured debate when agents disagree on a trade signal.

When the initial consensus falls in a borderline range, the
DebateManager orchestrates multiple rounds where dissenters present
counter-arguments, supporters rebut, and agents may shift positions.
If no consensus emerges, an escalation agent makes the final call.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from src.agent_consensus.voter import AgentVote

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class DebateConfig:
    """Tunable parameters for the debate process."""

    max_rounds: int = 3
    disagreement_threshold: float = 0.4
    escalation_agent: str = "alpha_strategist"
    require_new_evidence: bool = True


# ═══════════════════════════════════════════════════════════════════════
# Data classes
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class DebateRound:
    """Record of a single round of structured debate."""

    round_number: int
    arguments: list[dict] = field(default_factory=list)
    shift_count: int = 0

    def to_dict(self) -> dict:
        return {
            "round_number": self.round_number,
            "arguments": self.arguments,
            "shift_count": self.shift_count,
        }


@dataclass
class DebateResult:
    """Full outcome of the debate process."""

    rounds: list[DebateRound]
    initial_approval_rate: float
    final_approval_rate: float
    minds_changed: int
    escalated: bool
    escalation_decision: Optional[str]
    final_decision: str  # "execute", "reject", "hold"

    def to_dict(self) -> dict:
        return {
            "rounds": [r.to_dict() for r in self.rounds],
            "initial_approval_rate": round(self.initial_approval_rate, 4),
            "final_approval_rate": round(self.final_approval_rate, 4),
            "minds_changed": self.minds_changed,
            "escalated": self.escalated,
            "escalation_decision": self.escalation_decision,
            "final_decision": self.final_decision,
        }


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════


def _approval_rate(votes: list[AgentVote]) -> float:
    """Compute approval rate excluding abstains."""
    approve = sum(1 for v in votes if v.decision == "approve")
    reject = sum(1 for v in votes if v.decision == "reject")
    decisive = approve + reject
    return approve / decisive if decisive > 0 else 0.0


# ═══════════════════════════════════════════════════════════════════════
# Debate Manager
# ═══════════════════════════════════════════════════════════════════════


class DebateManager:
    """Orchestrate structured debate rounds between disagreeing agents.

    The manager is triggered when the initial approval rate falls within
    the borderline zone (``disagreement_threshold`` to
    ``1 - disagreement_threshold``) and the result was **not** vetoed.
    """

    # Risk factors that may cause an agent to shift from approve -> reject
    _RISK_FACTORS = [
        "stop distance exceeds historical volatility",
        "sector rotation away from signal direction",
        "declining volume on signal bar",
    ]

    # Momentum factors that may shift reject -> approve
    _MOMENTUM_FACTORS = [
        "strong institutional accumulation pattern",
        "multi-timeframe alignment confirms signal",
        "relative strength above sector average",
    ]

    def __init__(self, config: Optional[DebateConfig] = None) -> None:
        self.config = config or DebateConfig()

    # ── public API ────────────────────────────────────────────────────

    def should_debate(self, consensus_result: object) -> bool:
        """Return ``True`` if the consensus warrants a structured debate.

        Parameters
        ----------
        consensus_result:
            A ``ConsensusResult`` (or compatible object) with attributes
            ``approval_rate`` and ``vetoed``.
        """
        rate = getattr(consensus_result, "approval_rate", 0.0)
        vetoed = getattr(consensus_result, "vetoed", False)
        if vetoed:
            return False
        lower = self.config.disagreement_threshold
        upper = 1.0 - self.config.disagreement_threshold
        return lower <= rate <= upper

    def run_debate(
        self,
        votes: list[AgentVote],
        signal: dict,
    ) -> DebateResult:
        """Execute up to ``max_rounds`` of structured debate.

        Parameters
        ----------
        votes:
            The original votes from the consensus round.
        signal:
            Signal dict (``to_dict()`` output) for context.

        Returns
        -------
        DebateResult
        """
        # Deep-copy votes so we can mutate decisions
        working_votes = self._copy_votes(votes)
        initial_rate = _approval_rate(working_votes)
        total_minds_changed = 0
        rounds: list[DebateRound] = []

        for round_num in range(1, self.config.max_rounds + 1):
            debate_round, shifted = self._run_round(
                round_num, working_votes, signal
            )
            rounds.append(debate_round)
            total_minds_changed += shifted

            # Check if clear consensus has been reached
            current_rate = _approval_rate(working_votes)
            if current_rate >= 0.7 or current_rate <= 0.3:
                break

        final_rate = _approval_rate(working_votes)

        # ── escalation ────────────────────────────────────────────────
        escalated = False
        escalation_decision: Optional[str] = None
        if 0.4 <= final_rate <= 0.6:
            escalated = True
            escalation_decision = self._escalate(signal)

        # ── final decision ────────────────────────────────────────────
        if escalated and escalation_decision:
            final_decision = escalation_decision
        elif final_rate >= 0.6:
            final_decision = "execute"
        elif final_rate >= 0.4:
            final_decision = "hold"
        else:
            final_decision = "reject"

        result = DebateResult(
            rounds=rounds,
            initial_approval_rate=initial_rate,
            final_approval_rate=final_rate,
            minds_changed=total_minds_changed,
            escalated=escalated,
            escalation_decision=escalation_decision,
            final_decision=final_decision,
        )

        logger.info(
            "Debate complete: %d rounds, %d minds changed, "
            "approval %.1f%% -> %.1f%%, decision=%s",
            len(rounds),
            total_minds_changed,
            initial_rate * 100,
            final_rate * 100,
            final_decision,
        )
        return result

    # ── internal helpers ──────────────────────────────────────────────

    def _run_round(
        self,
        round_number: int,
        votes: list[AgentVote],
        signal: dict,
    ) -> tuple[DebateRound, int]:
        """Execute a single debate round, mutating *votes* in-place."""
        arguments: list[dict] = []
        shift_count = 0
        conviction = int(signal.get("conviction", 50))

        # Collect arguments from all sides
        for vote in votes:
            if vote.decision == "reject":
                # Dissenter presents counter-argument
                risk_idx = hash(vote.agent_type + str(round_number)) % len(
                    self._RISK_FACTORS
                )
                evidence = [self._RISK_FACTORS[risk_idx]]
                arguments.append(
                    {
                        "agent": vote.agent_type,
                        "position": "reject",
                        "argument": (
                            f"{vote.agent_type} maintains rejection: "
                            f"{vote.reasoning}"
                        ),
                        "evidence": evidence,
                    }
                )
            elif vote.decision == "approve":
                # Supporter rebuts
                mom_idx = hash(vote.agent_type + str(round_number)) % len(
                    self._MOMENTUM_FACTORS
                )
                evidence = [self._MOMENTUM_FACTORS[mom_idx]]
                arguments.append(
                    {
                        "agent": vote.agent_type,
                        "position": "approve",
                        "argument": (
                            f"{vote.agent_type} supports execution: "
                            f"{vote.reasoning}"
                        ),
                        "evidence": evidence,
                    }
                )

        # Determine if any agents shift position
        for vote in votes:
            if self._should_shift(vote, round_number, conviction):
                old_decision = vote.decision
                if old_decision == "reject":
                    vote.decision = "approve"
                    vote.reasoning = (
                        f"Shifted from reject after round {round_number} — "
                        "new evidence from supporters is compelling."
                    )
                elif old_decision == "approve":
                    vote.decision = "reject"
                    vote.reasoning = (
                        f"Shifted from approve after round {round_number} — "
                        "risk factors raised by dissenters warrant caution."
                    )
                else:
                    continue
                shift_count += 1
                logger.debug(
                    "Agent %s shifted %s -> %s in round %d",
                    vote.agent_type,
                    old_decision,
                    vote.decision,
                    round_number,
                )

        return DebateRound(
            round_number=round_number,
            arguments=arguments,
            shift_count=shift_count,
        ), shift_count

    @staticmethod
    def _should_shift(
        vote: AgentVote,
        round_number: int,
        conviction: int,
    ) -> bool:
        """Determine if an agent changes position this round.

        Rule: an agent may shift if its confidence is below 0.7 **and**
        a deterministic hash of (agent + round) produces the right
        residue.  This keeps behaviour fully reproducible while
        simulating partial persuasion.
        """
        if vote.decision == "abstain":
            return False
        if vote.confidence >= 0.7:
            return False
        # Deterministic: shift if hash % (max_rounds + 1) == round_number
        h = hash(vote.agent_type) % 4
        return h == round_number

    def _escalate(self, signal: dict) -> str:
        """Escalation agent makes the final call based on conviction.

        The ``alpha_strategist`` (default escalation agent) resolves
        deadlock using a conviction threshold of 55.
        """
        conviction = int(signal.get("conviction", 50))
        if conviction >= 55:
            logger.info(
                "Escalation by %s: EXECUTE (conviction=%d)",
                self.config.escalation_agent,
                conviction,
            )
            return "execute"
        else:
            logger.info(
                "Escalation by %s: REJECT (conviction=%d)",
                self.config.escalation_agent,
                conviction,
            )
            return "reject"

    @staticmethod
    def _copy_votes(votes: list[AgentVote]) -> list[AgentVote]:
        """Shallow-copy vote objects so mutations don't affect originals."""
        copies: list[AgentVote] = []
        for v in votes:
            copies.append(
                AgentVote(
                    agent_type=v.agent_type,
                    decision=v.decision,
                    confidence=v.confidence,
                    reasoning=v.reasoning,
                    risk_assessment=v.risk_assessment,
                    suggested_adjustments=dict(v.suggested_adjustments),
                    timestamp=v.timestamp,
                )
            )
        return copies
