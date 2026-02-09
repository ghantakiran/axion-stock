"""Consensus engine that aggregates agent votes into a trade decision.

Supports weighted voting, veto power for designated agents, and
configurable approval thresholds. Produces a single ConsensusResult
that downstream components use to gate trade execution.
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

from src.agent_consensus.voter import AgentVote

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class ConsensusConfig:
    """Tunable parameters for the consensus engine."""

    approval_threshold: float = 0.6
    min_votes: int = 3
    require_risk_approval: bool = True
    conviction_weight: float = 0.3
    veto_agents: list[str] = field(default_factory=lambda: ["risk_sentinel"])
    weighted_voting: bool = True


# ═══════════════════════════════════════════════════════════════════════
# Result
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class ConsensusResult:
    """Outcome of the consensus evaluation."""

    decision: str  # "execute", "reject", "hold"
    approval_rate: float  # 0.0 - 1.0
    weighted_score: float  # -1.0 to +1.0
    confidence: float  # average confidence of voters
    total_votes: int
    approve_count: int
    reject_count: int
    abstain_count: int
    vetoed: bool
    veto_reason: Optional[str]
    risk_assessment: str  # consensus risk level
    suggested_adjustments: dict
    votes: list[AgentVote]

    def to_dict(self) -> dict:
        return {
            "decision": self.decision,
            "approval_rate": round(self.approval_rate, 4),
            "weighted_score": round(self.weighted_score, 4),
            "confidence": round(self.confidence, 4),
            "total_votes": self.total_votes,
            "approve_count": self.approve_count,
            "reject_count": self.reject_count,
            "abstain_count": self.abstain_count,
            "vetoed": self.vetoed,
            "veto_reason": self.veto_reason,
            "risk_assessment": self.risk_assessment,
            "suggested_adjustments": self.suggested_adjustments,
            "votes": [v.to_dict() for v in self.votes],
        }


# ═══════════════════════════════════════════════════════════════════════
# Engine
# ═══════════════════════════════════════════════════════════════════════


class ConsensusEngine:
    """Evaluate a set of :class:`AgentVote` objects and produce a decision.

    Steps
    -----
    1. Validate minimum vote count.
    2. Check for veto by any ``veto_agents``.
    3. Compute approval rate (abstains excluded from denominator).
    4. Compute weighted score (approve = +conf, reject = -conf).
    5. Determine majority risk assessment.
    6. Merge suggested adjustments from approving agents.
    7. Apply decision logic: vetoed -> reject, threshold -> execute,
       borderline -> hold, else -> reject.
    """

    def __init__(self, config: Optional[ConsensusConfig] = None) -> None:
        self.config = config or ConsensusConfig()

    def evaluate(self, votes: list[AgentVote]) -> ConsensusResult:
        """Aggregate *votes* into a :class:`ConsensusResult`."""
        approve_count = sum(1 for v in votes if v.decision == "approve")
        reject_count = sum(1 for v in votes if v.decision == "reject")
        abstain_count = sum(1 for v in votes if v.decision == "abstain")
        total = len(votes)

        # ── veto check ────────────────────────────────────────────────
        vetoed = False
        veto_reason: Optional[str] = None
        for v in votes:
            if v.agent_type in self.config.veto_agents and v.decision == "reject":
                vetoed = True
                veto_reason = f"{v.agent_type} veto: {v.reasoning}"
                break

        # ── approval rate (abstains excluded) ─────────────────────────
        decisive = approve_count + reject_count
        approval_rate = approve_count / decisive if decisive > 0 else 0.0

        # ── weighted score ────────────────────────────────────────────
        weighted_score = self._compute_weighted_score(votes)

        # ── average confidence ────────────────────────────────────────
        confidences = [v.confidence for v in votes]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        # ── risk assessment (majority vote) ───────────────────────────
        risk_assessment = self._majority_risk(votes)

        # ── merge suggested adjustments ───────────────────────────────
        merged_adjustments = self._merge_adjustments(votes)

        # ── decision logic ────────────────────────────────────────────
        if total < self.config.min_votes:
            decision = "hold"
            logger.info(
                "Insufficient votes (%d < %d) — holding",
                total,
                self.config.min_votes,
            )
        elif vetoed:
            decision = "reject"
            logger.info("Consensus vetoed: %s", veto_reason)
        elif approval_rate >= self.config.approval_threshold and weighted_score > 0:
            decision = "execute"
        elif approval_rate >= 0.4:
            decision = "hold"
        else:
            decision = "reject"

        result = ConsensusResult(
            decision=decision,
            approval_rate=approval_rate,
            weighted_score=weighted_score,
            confidence=avg_confidence,
            total_votes=total,
            approve_count=approve_count,
            reject_count=reject_count,
            abstain_count=abstain_count,
            vetoed=vetoed,
            veto_reason=veto_reason,
            risk_assessment=risk_assessment,
            suggested_adjustments=merged_adjustments,
            votes=votes,
        )

        logger.info(
            "Consensus: decision=%s approval=%.1f%% weighted=%.3f vetoed=%s",
            decision,
            approval_rate * 100,
            weighted_score,
            vetoed,
        )
        return result

    # ── internal helpers ──────────────────────────────────────────────

    def _compute_weighted_score(self, votes: list[AgentVote]) -> float:
        """Compute a normalised weighted score in [-1, +1].

        Each approve contributes +confidence, each reject -confidence,
        abstains contribute 0.  The raw sum is normalised by the number
        of non-abstaining votes so that the score remains bounded.
        """
        raw = 0.0
        decisive_count = 0
        for v in votes:
            if v.decision == "approve":
                raw += v.confidence
                decisive_count += 1
            elif v.decision == "reject":
                raw -= v.confidence
                decisive_count += 1

        if decisive_count == 0:
            return 0.0
        return max(-1.0, min(1.0, raw / decisive_count))

    @staticmethod
    def _majority_risk(votes: list[AgentVote]) -> str:
        """Return the most common risk_assessment across voters."""
        if not votes:
            return "medium"
        counter: Counter[str] = Counter(v.risk_assessment for v in votes)
        return counter.most_common(1)[0][0]

    @staticmethod
    def _merge_adjustments(votes: list[AgentVote]) -> dict:
        """Merge suggested_adjustments from approving voters (last wins)."""
        merged: dict = {}
        for v in votes:
            if v.decision == "approve" and v.suggested_adjustments:
                merged.update(v.suggested_adjustments)
        return merged
