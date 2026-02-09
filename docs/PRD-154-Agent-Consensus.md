# PRD-154: Multi-Agent Trade Consensus

## Overview
Enables multiple AI agents to vote on trade signals before execution. Each agent evaluates the signal through its specialized lens (value, growth, momentum, risk, etc.) and casts an approve/reject/abstain vote. A consensus engine aggregates votes, and a structured debate process resolves disagreements.

## Architecture
```
TradeSignal → VoteCollector → panel of 5-10 agents
                    ↓
              AgentVote[] → ConsensusEngine → ConsensusResult
                    ↓                              ↓
              (borderline?) ──yes──→ DebateManager → DebateResult
                    ↓                              ↓
              ConsensusAuditor → audit trail + statistics
```

## Components

### Vote Collector (`voter.py`)
- **Panel selection**: Configurable 5-agent default panel with risk_sentinel always included
- **Deterministic rules**: Each of 10 agent types has specific voting logic based on signal parameters
- **Vote prompt generation**: Structured prompts for future LLM integration
- **Agent specializations**: alpha_strategist (conviction-based), risk_sentinel (stop distance), momentum_rider (signal type), etc.

### Consensus Engine (`consensus.py`)
- **Weighted voting**: Agent confidence weights the score (-1 to +1)
- **Veto mechanism**: risk_sentinel rejection overrides majority
- **Three-outcome decision**: execute (>60% approval), hold (40-60%), reject (<40%)
- **Configurable thresholds**: approval_threshold, min_votes, veto_agents

### Debate Manager (`debate.py`)
- **Structured rounds**: Up to 3 rounds of argument/counter-argument
- **Position shifting**: Agents with low confidence may change votes
- **Escalation**: alpha_strategist breaks deadlock using conviction threshold
- **Deterministic**: Reproducible debate outcomes for testing

### Consensus Auditor (`auditor.py`)
- **Full audit trail**: Every decision recorded with votes, consensus, and debate
- **Per-agent statistics**: Approval rate, confidence, veto count per agent
- **Aggregate stats**: Total decisions, approval/rejection/debate rates
- **History filtering**: By ticker, with configurable limits

## Database Tables
- `consensus_decisions`: Decision log with signal context, vote counts, and outcome
- `consensus_agent_votes`: Per-agent vote history with reasoning

## Dashboard
4-tab Streamlit interface:
1. **Vote**: Interactive signal input with agent voting visualization
2. **Consensus**: Threshold configuration with live consensus evaluation
3. **Debate**: Debate simulation with round-by-round argument display
4. **Audit**: Decision history with per-agent statistics

## Integration Points
- **agents** (PRD-131): Uses AgentType enum values for panel selection
- **ema_signals** (PRD-134): Evaluates TradeSignal objects
- **trade_executor** (PRD-135): Consensus gates signal execution
- **signal_fusion** (PRD-147): Can feed fused signals into consensus
