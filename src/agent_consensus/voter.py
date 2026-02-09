"""Vote collection from AI agents on trade signals.

Each panel agent evaluates a trade signal using deterministic rule-based
logic and returns a structured vote with decision, confidence, reasoning,
risk assessment, and optional parameter adjustments.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# Data classes
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class AgentVote:
    """A single agent's vote on a trade signal."""

    agent_type: str
    decision: str  # "approve", "reject", "abstain"
    confidence: float  # 0.0-1.0
    reasoning: str
    risk_assessment: str  # "low", "medium", "high", "extreme"
    suggested_adjustments: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        self.confidence = max(0.0, min(1.0, self.confidence))
        if self.decision not in ("approve", "reject", "abstain"):
            raise ValueError(f"Invalid decision: {self.decision}")
        if self.risk_assessment not in ("low", "medium", "high", "extreme"):
            raise ValueError(f"Invalid risk_assessment: {self.risk_assessment}")

    def to_dict(self) -> dict:
        return {
            "agent_type": self.agent_type,
            "decision": self.decision,
            "confidence": round(self.confidence, 4),
            "reasoning": self.reasoning,
            "risk_assessment": self.risk_assessment,
            "suggested_adjustments": self.suggested_adjustments,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class VoterConfig:
    """Configuration for vote collection."""

    panel_agents: list[str] = field(
        default_factory=lambda: [
            "alpha_strategist",
            "risk_sentinel",
            "momentum_rider",
            "portfolio_architect",
            "market_scout",
        ]
    )
    require_risk_sentinel: bool = True
    vote_timeout_seconds: float = 30.0
    min_reasoning_length: int = 10


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════


def _get_field(obj: object, key: str, default: object = None) -> object:
    """Retrieve a field from a dict or an object attribute."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _signal_dict(signal: object) -> dict:
    """Normalise a signal to a plain dict."""
    if isinstance(signal, dict):
        return signal
    if hasattr(signal, "to_dict"):
        return signal.to_dict()
    return {}


# ═══════════════════════════════════════════════════════════════════════
# Vote Collector
# ═══════════════════════════════════════════════════════════════════════


class VoteCollector:
    """Collects deterministic rule-based votes from a panel of agents.

    Each agent evaluates a trade signal using its own criteria and
    returns a structured :class:`AgentVote`.  The rule-based approach
    ensures full testability without requiring LLM inference.
    """

    # Signal types considered strong by momentum-oriented agents
    STRONG_SIGNAL_TYPES = {
        "cloud_cross_bullish",
        "cloud_cross_bearish",
        "trend_aligned_long",
        "trend_aligned_short",
        "mtf_confluence",
    }

    # Bounce signals are treated with more skepticism
    BOUNCE_SIGNAL_TYPES = {
        "cloud_bounce_long",
        "cloud_bounce_short",
    }

    def __init__(self, config: Optional[VoterConfig] = None) -> None:
        self.config = config or VoterConfig()
        # Guarantee risk_sentinel is on the panel when required
        if (
            self.config.require_risk_sentinel
            and "risk_sentinel" not in self.config.panel_agents
        ):
            self.config.panel_agents.append("risk_sentinel")

    # ── public API ────────────────────────────────────────────────────

    def collect_votes(
        self,
        signal: object,
        market_context: Optional[dict] = None,
    ) -> list[AgentVote]:
        """Collect votes from all panel agents for *signal*.

        Parameters
        ----------
        signal:
            A ``TradeSignal`` instance (or compatible dict) carrying at
            minimum ``ticker``, ``direction``, ``conviction``,
            ``entry_price``, ``stop_loss``, ``target_price``, and
            ``signal_type``.
        market_context:
            Optional dict of extra context (e.g. sector, volume, news).

        Returns
        -------
        list[AgentVote]
            One vote per panel agent.
        """
        ctx = market_context or {}
        votes: list[AgentVote] = []

        for agent_type in self.config.panel_agents:
            method = getattr(self, f"_vote_{agent_type}", None)
            if method is None:
                logger.warning("No rule for agent %s — skipping", agent_type)
                continue
            vote = method(signal, ctx)
            votes.append(vote)

        return votes

    def get_vote_prompt(self, signal: object, agent_type: str) -> str:
        """Build a human-readable evaluation prompt for an agent.

        This is exposed publicly so dashboards or tests can inspect the
        prompt that *would* be sent to an LLM-backed agent.
        """
        sd = _signal_dict(signal)
        return (
            f"You are {agent_type}. Evaluate the following trade signal:\n"
            f"  Ticker: {sd.get('ticker', 'N/A')}\n"
            f"  Direction: {sd.get('direction', 'N/A')}\n"
            f"  Signal type: {sd.get('signal_type', 'N/A')}\n"
            f"  Conviction: {sd.get('conviction', 'N/A')}/100\n"
            f"  Entry: {sd.get('entry_price', 'N/A')}\n"
            f"  Stop loss: {sd.get('stop_loss', 'N/A')}\n"
            f"  Target: {sd.get('target_price', 'N/A')}\n\n"
            "Respond with JSON: {decision, confidence, reasoning, "
            "risk_assessment, suggested_adjustments}"
        )

    # ── per-agent rule engines ────────────────────────────────────────

    def _vote_alpha_strategist(self, signal: object, ctx: dict) -> AgentVote:
        """Alpha Strategist: approves conviction >= 60, rejects < 40."""
        conviction = int(_get_field(signal, "conviction", 0))
        direction = str(_get_field(signal, "direction", "long"))

        if conviction >= 60:
            decision, conf = "approve", min(0.5 + conviction / 200, 1.0)
            reasoning = (
                f"Signal conviction {conviction}/100 meets threshold. "
                f"Proceeding with {direction} bias."
            )
            risk = "medium" if conviction < 80 else "low"
        elif conviction < 40:
            decision, conf = "reject", 0.7
            reasoning = f"Conviction {conviction}/100 too low for execution."
            risk = "high"
        else:
            decision, conf = "abstain", 0.4
            reasoning = (
                f"Conviction {conviction}/100 is borderline — "
                "need additional confirmation."
            )
            risk = "medium"

        return AgentVote(
            agent_type="alpha_strategist",
            decision=decision,
            confidence=conf,
            reasoning=reasoning,
            risk_assessment=risk,
        )

    def _vote_value_oracle(self, signal: object, ctx: dict) -> AgentVote:
        """Value Oracle: checks risk/reward ratio (target/entry > 1.5)."""
        entry = float(_get_field(signal, "entry_price", 0) or 0)
        target = float(_get_field(signal, "target_price", 0) or 0)
        stop = float(_get_field(signal, "stop_loss", 0) or 0)
        direction = str(_get_field(signal, "direction", "long"))

        if entry > 0 and target > 0:
            if direction == "long":
                reward = target - entry
                risk_amt = entry - stop if stop > 0 else entry * 0.05
            else:
                reward = entry - target
                risk_amt = stop - entry if stop > 0 else entry * 0.05
            rr_ratio = reward / risk_amt if risk_amt > 0 else 0.0
        else:
            rr_ratio = 0.0

        if rr_ratio >= 1.5:
            decision, conf = "approve", min(0.5 + rr_ratio / 10, 1.0)
            reasoning = (
                f"Risk/reward ratio {rr_ratio:.2f} exceeds 1.5x threshold. "
                "Favorable value proposition."
            )
            risk = "low" if rr_ratio >= 3.0 else "medium"
        else:
            decision, conf = "reject", 0.6
            reasoning = (
                f"Risk/reward ratio {rr_ratio:.2f} below 1.5x minimum. "
                "Insufficient margin of safety."
            )
            risk = "high"

        return AgentVote(
            agent_type="value_oracle",
            decision=decision,
            confidence=conf,
            reasoning=reasoning,
            risk_assessment=risk,
        )

    def _vote_growth_hunter(self, signal: object, ctx: dict) -> AgentVote:
        """Growth Hunter: favours long signals, skeptical of shorts."""
        direction = str(_get_field(signal, "direction", "long"))
        conviction = int(_get_field(signal, "conviction", 50))

        if direction == "long":
            decision = "approve"
            conf = min(0.6 + conviction / 250, 1.0)
            reasoning = (
                f"Long signal aligns with growth thesis. "
                f"Conviction {conviction}/100 supports entry."
            )
            risk = "low" if conviction >= 70 else "medium"
        else:
            decision = "abstain"
            conf = 0.35
            reasoning = (
                "Short bias runs counter to growth orientation. "
                "Abstaining rather than blocking."
            )
            risk = "medium"

        return AgentVote(
            agent_type="growth_hunter",
            decision=decision,
            confidence=conf,
            reasoning=reasoning,
            risk_assessment=risk,
        )

    def _vote_momentum_rider(self, signal: object, ctx: dict) -> AgentVote:
        """Momentum Rider: approves cloud_cross / trend_aligned, skeptical of bounces."""
        sig_type = str(_get_field(signal, "signal_type", ""))
        # Normalise enum values
        if hasattr(sig_type, "value"):
            sig_type = sig_type.value
        conviction = int(_get_field(signal, "conviction", 50))

        if sig_type in self.STRONG_SIGNAL_TYPES:
            decision, conf = "approve", min(0.65 + conviction / 300, 1.0)
            reasoning = (
                f"Signal type '{sig_type}' indicates strong momentum. "
                "Trend continuation expected."
            )
            risk = "low" if conviction >= 75 else "medium"
        elif sig_type in self.BOUNCE_SIGNAL_TYPES:
            decision, conf = "abstain", 0.35
            reasoning = (
                f"Bounce signal '{sig_type}' has lower reliability. "
                "Waiting for trend confirmation."
            )
            risk = "medium"
        else:
            decision, conf = "approve", 0.5
            reasoning = (
                f"Signal type '{sig_type}' is acceptable. "
                "Moderate momentum support."
            )
            risk = "medium"

        return AgentVote(
            agent_type="momentum_rider",
            decision=decision,
            confidence=conf,
            reasoning=reasoning,
            risk_assessment=risk,
        )

    def _vote_income_architect(self, signal: object, ctx: dict) -> AgentVote:
        """Income Architect: conservative — rejects conviction < 70."""
        conviction = int(_get_field(signal, "conviction", 0))

        if conviction >= 70:
            decision, conf = "approve", 0.6
            reasoning = (
                f"Conviction {conviction}/100 meets conservative threshold. "
                "Signal quality sufficient for income strategy overlay."
            )
            risk = "low" if conviction >= 85 else "medium"
        else:
            decision, conf = "reject", 0.65
            reasoning = (
                f"Conviction {conviction}/100 below 70 — "
                "too speculative for income-focused allocation."
            )
            risk = "high"

        return AgentVote(
            agent_type="income_architect",
            decision=decision,
            confidence=conf,
            reasoning=reasoning,
            risk_assessment=risk,
        )

    def _vote_risk_sentinel(self, signal: object, ctx: dict) -> AgentVote:
        """Risk Sentinel: rejects if stop distance > 5% or extreme risk."""
        entry = float(_get_field(signal, "entry_price", 0) or 0)
        stop = float(_get_field(signal, "stop_loss", 0) or 0)
        direction = str(_get_field(signal, "direction", "long"))

        if entry > 0 and stop > 0:
            if direction == "long":
                stop_distance_pct = (entry - stop) / entry
            else:
                stop_distance_pct = (stop - entry) / entry
        else:
            stop_distance_pct = 0.10  # Assume high risk if unknown

        if stop_distance_pct > 0.05:
            decision, conf = "reject", 0.85
            reasoning = (
                f"Stop distance {stop_distance_pct:.1%} exceeds 5% max. "
                "Position risk too large for portfolio constraints."
            )
            risk = "extreme" if stop_distance_pct > 0.08 else "high"
        elif stop_distance_pct > 0.03:
            decision, conf = "approve", 0.55
            reasoning = (
                f"Stop distance {stop_distance_pct:.1%} within limits but elevated. "
                "Recommend reduced position size."
            )
            risk = "medium"
            suggested = {"position_size_pct": 0.03}
            return AgentVote(
                agent_type="risk_sentinel",
                decision=decision,
                confidence=conf,
                reasoning=reasoning,
                risk_assessment=risk,
                suggested_adjustments=suggested,
            )
        else:
            decision, conf = "approve", 0.75
            reasoning = (
                f"Stop distance {stop_distance_pct:.1%} well within 5% limit. "
                "Risk profile acceptable."
            )
            risk = "low"

        return AgentVote(
            agent_type="risk_sentinel",
            decision=decision,
            confidence=conf,
            reasoning=reasoning,
            risk_assessment=risk,
        )

    def _vote_portfolio_architect(self, signal: object, ctx: dict) -> AgentVote:
        """Portfolio Architect: checks if implied position size is reasonable."""
        conviction = int(_get_field(signal, "conviction", 50))
        implied_pct = conviction / 1000  # e.g. 80 conviction -> 8% position

        if implied_pct <= 0.10:
            decision, conf = "approve", 0.6
            reasoning = (
                f"Implied position size {implied_pct:.1%} is within portfolio "
                "allocation guidelines."
            )
            risk = "low" if implied_pct <= 0.05 else "medium"
        else:
            decision, conf = "reject", 0.7
            reasoning = (
                f"Implied position size {implied_pct:.1%} exceeds 10% "
                "concentration limit. Reduce or split."
            )
            risk = "high"

        return AgentVote(
            agent_type="portfolio_architect",
            decision=decision,
            confidence=conf,
            reasoning=reasoning,
            risk_assessment=risk,
        )

    def _vote_options_strategist(self, signal: object, ctx: dict) -> AgentVote:
        """Options Strategist: approves with options overlay adjustments."""
        direction = str(_get_field(signal, "direction", "long"))
        conviction = int(_get_field(signal, "conviction", 50))
        entry = float(_get_field(signal, "entry_price", 0) or 0)

        if direction == "long":
            overlay = "long_call_spread"
            strike_offset = 0.02
        else:
            overlay = "long_put_spread"
            strike_offset = -0.02

        decision, conf = "approve", 0.55
        reasoning = (
            f"Recommending {overlay} overlay to define risk. "
            f"Conviction {conviction}/100 supports directional bias."
        )
        adjustments = {
            "options_overlay": overlay,
            "strike_offset_pct": strike_offset,
        }
        if entry > 0:
            adjustments["suggested_strike"] = round(entry * (1 + strike_offset), 2)

        return AgentVote(
            agent_type="options_strategist",
            decision=decision,
            confidence=conf,
            reasoning=reasoning,
            risk_assessment="medium",
            suggested_adjustments=adjustments,
        )

    def _vote_market_scout(self, signal: object, ctx: dict) -> AgentVote:
        """Market Scout: generally approves with medium confidence."""
        ticker = str(_get_field(signal, "ticker", "UNKNOWN"))
        conviction = int(_get_field(signal, "conviction", 50))

        decision, conf = "approve", 0.50
        reasoning = (
            f"Market conditions for {ticker} appear supportive. "
            f"Signal conviction {conviction}/100 noted."
        )
        risk = "low" if conviction >= 70 else "medium"

        return AgentVote(
            agent_type="market_scout",
            decision=decision,
            confidence=conf,
            reasoning=reasoning,
            risk_assessment=risk,
        )

    def _vote_research_analyst(self, signal: object, ctx: dict) -> AgentVote:
        """Research Analyst: approves strong signal types, scrutinises weak ones."""
        sig_type = str(_get_field(signal, "signal_type", ""))
        if hasattr(sig_type, "value"):
            sig_type = sig_type.value
        conviction = int(_get_field(signal, "conviction", 50))

        is_strong = sig_type in self.STRONG_SIGNAL_TYPES
        if is_strong and conviction >= 55:
            decision, conf = "approve", 0.65
            reasoning = (
                f"Signal type '{sig_type}' is well-supported by historical data. "
                f"Conviction {conviction}/100 confirms directional edge."
            )
            risk = "low" if conviction >= 75 else "medium"
        elif conviction >= 70:
            decision, conf = "approve", 0.5
            reasoning = (
                f"High conviction {conviction}/100 compensates for moderate "
                f"signal type '{sig_type}'."
            )
            risk = "medium"
        else:
            decision, conf = "reject", 0.55
            reasoning = (
                f"Signal type '{sig_type}' with conviction {conviction}/100 "
                "lacks sufficient statistical support."
            )
            risk = "high"

        return AgentVote(
            agent_type="research_analyst",
            decision=decision,
            confidence=conf,
            reasoning=reasoning,
            risk_assessment=risk,
        )
