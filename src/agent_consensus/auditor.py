"""Audit trail for multi-agent trade consensus decisions.

Records every consensus decision with its votes, signal context, and
optional debate outcome.  Provides aggregate statistics for monitoring
agent behaviour and system calibration.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from src.agent_consensus.voter import AgentVote
from src.agent_consensus.consensus import ConsensusResult
from src.agent_consensus.debate import DebateResult


# ═══════════════════════════════════════════════════════════════════════
# Audit entry
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class ConsensusAuditEntry:
    """Immutable record of a single consensus decision."""

    audit_id: str
    signal_summary: dict
    votes: list[dict]
    consensus: dict
    debate: Optional[dict] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "audit_id": self.audit_id,
            "signal_summary": self.signal_summary,
            "votes": self.votes,
            "consensus": self.consensus,
            "debate": self.debate,
            "timestamp": self.timestamp.isoformat(),
        }


# ═══════════════════════════════════════════════════════════════════════
# Auditor
# ═══════════════════════════════════════════════════════════════════════


class ConsensusAuditor:
    """Maintains an in-memory audit trail of consensus decisions.

    Parameters
    ----------
    max_history:
        Maximum number of entries to retain.  Oldest entries are
        discarded once the limit is reached.
    """

    def __init__(self, max_history: int = 1000) -> None:
        self.max_history = max_history
        self._history: list[ConsensusAuditEntry] = []

    # ── public API ────────────────────────────────────────────────────

    def record(
        self,
        signal_dict: dict,
        votes: list[AgentVote],
        consensus: ConsensusResult,
        debate: Optional[DebateResult] = None,
    ) -> ConsensusAuditEntry:
        """Record a consensus decision and return the audit entry.

        Parameters
        ----------
        signal_dict:
            Trade signal as a plain dict (typically ``signal.to_dict()``).
        votes:
            The full list of :class:`AgentVote` objects.
        consensus:
            The :class:`ConsensusResult` produced by the engine.
        debate:
            Optional :class:`DebateResult` if a debate was held.
        """
        entry = ConsensusAuditEntry(
            audit_id=str(uuid.uuid4())[:8],
            signal_summary=signal_dict,
            votes=[v.to_dict() for v in votes],
            consensus=consensus.to_dict(),
            debate=debate.to_dict() if debate else None,
        )

        self._history.append(entry)

        # Evict oldest entries if over capacity
        if len(self._history) > self.max_history:
            self._history = self._history[-self.max_history :]

        return entry

    def get_history(
        self,
        ticker: Optional[str] = None,
        limit: int = 50,
    ) -> list[ConsensusAuditEntry]:
        """Return recent audit entries, optionally filtered by ticker.

        Parameters
        ----------
        ticker:
            If provided, only entries whose signal_summary contains a
            matching ``ticker`` are returned.
        limit:
            Maximum number of entries to return (most recent first).
        """
        if ticker is not None:
            filtered = [
                e
                for e in self._history
                if e.signal_summary.get("ticker") == ticker
            ]
        else:
            filtered = list(self._history)

        # Most recent first
        return list(reversed(filtered[-limit:]))

    def get_approval_stats(self) -> dict:
        """Return aggregate statistics across all recorded decisions.

        Returns
        -------
        dict
            Keys: ``total_decisions``, ``approved``, ``rejected``,
            ``debated``, ``vetoed``, ``avg_approval_rate``.
        """
        total = len(self._history)
        if total == 0:
            return {
                "total_decisions": 0,
                "approved": 0,
                "rejected": 0,
                "debated": 0,
                "vetoed": 0,
                "avg_approval_rate": 0.0,
            }

        approved = sum(
            1 for e in self._history if e.consensus.get("decision") == "execute"
        )
        rejected = sum(
            1 for e in self._history if e.consensus.get("decision") == "reject"
        )
        debated = sum(1 for e in self._history if e.debate is not None)
        vetoed = sum(
            1 for e in self._history if e.consensus.get("vetoed") is True
        )
        avg_rate = (
            sum(e.consensus.get("approval_rate", 0.0) for e in self._history) / total
        )

        return {
            "total_decisions": total,
            "approved": approved,
            "rejected": rejected,
            "debated": debated,
            "vetoed": vetoed,
            "avg_approval_rate": round(avg_rate, 4),
        }

    def get_agent_stats(self) -> dict[str, dict]:
        """Return per-agent voting statistics.

        Returns
        -------
        dict[str, dict]
            Keyed by agent_type.  Each value contains
            ``total_votes``, ``approve_pct``, ``avg_confidence``,
            ``veto_count``.
        """
        agent_data: dict[str, dict] = {}

        for entry in self._history:
            for vote_dict in entry.votes:
                agent = vote_dict.get("agent_type", "unknown")
                if agent not in agent_data:
                    agent_data[agent] = {
                        "total_votes": 0,
                        "approve_count": 0,
                        "confidence_sum": 0.0,
                        "veto_count": 0,
                    }
                stats = agent_data[agent]
                stats["total_votes"] += 1
                if vote_dict.get("decision") == "approve":
                    stats["approve_count"] += 1
                stats["confidence_sum"] += vote_dict.get("confidence", 0.0)
                if vote_dict.get("decision") == "reject" and vote_dict.get(
                    "risk_assessment"
                ) in ("high", "extreme"):
                    stats["veto_count"] += 1

        # Convert running totals to final stats
        result: dict[str, dict] = {}
        for agent, data in agent_data.items():
            total = data["total_votes"]
            result[agent] = {
                "total_votes": total,
                "approve_pct": round(data["approve_count"] / total, 4) if total else 0.0,
                "avg_confidence": round(data["confidence_sum"] / total, 4) if total else 0.0,
                "veto_count": data["veto_count"],
            }

        return result
