"""Multi-Agent Trade Consensus (PRD-154).

Allows multiple AI agents to vote on trade signals and reach consensus
on whether to execute. Bridges the agent system (PRD-131) with the
trade executor (PRD-135) through structured voting, consensus evaluation,
structured debate, and full audit trails.
"""

from src.agent_consensus.voter import (
    AgentVote,
    VoterConfig,
    VoteCollector,
)
from src.agent_consensus.consensus import (
    ConsensusConfig,
    ConsensusResult,
    ConsensusEngine,
)
from src.agent_consensus.debate import (
    DebateConfig,
    DebateRound,
    DebateResult,
    DebateManager,
)
from src.agent_consensus.auditor import (
    ConsensusAuditEntry,
    ConsensusAuditor,
)

__all__ = [
    # Voter
    "AgentVote",
    "VoterConfig",
    "VoteCollector",
    # Consensus
    "ConsensusConfig",
    "ConsensusResult",
    "ConsensusEngine",
    # Debate
    "DebateConfig",
    "DebateRound",
    "DebateResult",
    "DebateManager",
    # Auditor
    "ConsensusAuditEntry",
    "ConsensusAuditor",
]
