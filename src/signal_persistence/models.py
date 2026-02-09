"""Data models for signal persistence.

Immutable record types for every stage of the signal pipeline:
Signal → Fusion → RiskDecision → Execution
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class SignalStatus(str, Enum):
    """Lifecycle status of a signal through the pipeline."""

    GENERATED = "generated"       # Raw signal created
    COLLECTED = "collected"       # Picked up by collector
    FUSED = "fused"               # Passed through fusion engine
    RISK_APPROVED = "risk_approved"   # Passed risk gate
    RISK_REJECTED = "risk_rejected"   # Rejected by risk gate
    EXECUTING = "executing"       # Order submitted
    EXECUTED = "executed"         # Fill confirmed
    EXPIRED = "expired"           # Signal aged out (beyond max_signal_age)
    CANCELLED = "cancelled"       # Manually cancelled


@dataclass
class PersistenceConfig:
    """Configuration for the signal persistence layer.

    Attributes:
        max_signal_age_seconds: Signals older than this are marked expired.
        batch_size: Number of records to flush in one DB write.
        enable_db: Whether to persist to database (False = in-memory only).
        retention_days: How long to keep signal records before archival.
    """

    max_signal_age_seconds: int = 300
    batch_size: int = 50
    enable_db: bool = False
    retention_days: int = 90


@dataclass
class SignalRecord:
    """Immutable record of a raw signal at the point of generation.

    This is the atomic unit of the audit trail — every signal gets one,
    regardless of whether it's later fused, rejected, or executed.

    Attributes:
        signal_id: Unique identifier (UUID).
        source: Which system generated this (ema_cloud, social, etc.).
        ticker: Instrument symbol.
        direction: bullish / bearish / neutral.
        strength: Signal strength 0-100.
        confidence: Source self-reported confidence 0.0-1.0.
        timestamp: When the signal was generated.
        status: Current pipeline status.
        source_metadata: Arbitrary data from the source system.
        fusion_id: ID of the FusionRecord (set after fusion).
        execution_id: ID of the ExecutionRecord (set after execution).
    """

    signal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: str = ""
    ticker: str = ""
    direction: str = "neutral"
    strength: float = 0.0
    confidence: float = 0.5
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: SignalStatus = SignalStatus.GENERATED
    source_metadata: dict[str, Any] = field(default_factory=dict)
    fusion_id: Optional[str] = None
    execution_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "source": self.source,
            "ticker": self.ticker,
            "direction": self.direction,
            "strength": round(self.strength, 2),
            "confidence": round(self.confidence, 3),
            "timestamp": self.timestamp.isoformat(),
            "status": self.status.value,
            "source_metadata": self.source_metadata,
            "fusion_id": self.fusion_id,
            "execution_id": self.execution_id,
        }


@dataclass
class FusionRecord:
    """Record of a signal fusion decision.

    Captures the exact inputs, weights, and output of each fusion,
    enabling post-hoc analysis of why a particular recommendation was made.

    Attributes:
        fusion_id: Unique identifier.
        ticker: Symbol being fused.
        input_signal_ids: IDs of all signals that were fused.
        direction: Consensus direction from fusion.
        composite_score: Fused score -100 to +100.
        confidence: Overall fusion confidence 0.0-1.0.
        source_count: Number of unique sources.
        agreement_ratio: Fraction of sources agreeing.
        source_weights_used: Snapshot of weights at fusion time.
        timestamp: When fusion was computed.
    """

    fusion_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ticker: str = ""
    input_signal_ids: list[str] = field(default_factory=list)
    direction: str = "neutral"
    composite_score: float = 0.0
    confidence: float = 0.0
    source_count: int = 0
    agreement_ratio: float = 0.0
    source_weights_used: dict[str, float] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "fusion_id": self.fusion_id,
            "ticker": self.ticker,
            "input_signal_ids": self.input_signal_ids,
            "direction": self.direction,
            "composite_score": round(self.composite_score, 2),
            "confidence": round(self.confidence, 3),
            "source_count": self.source_count,
            "agreement_ratio": round(self.agreement_ratio, 3),
            "source_weights_used": {
                k: round(v, 4) for k, v in self.source_weights_used.items()
            },
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class RiskDecisionRecord:
    """Record of a risk gate decision for audit trail.

    Captures every check that was run and whether it passed,
    plus the final approved/rejected verdict.

    Attributes:
        decision_id: Unique identifier.
        signal_id: The signal being validated.
        fusion_id: The fusion record (if signal came via fusion).
        approved: Whether the signal passed all checks.
        rejection_reason: Why it was rejected (None if approved).
        checks_run: List of check names that were executed.
        checks_passed: List of check names that passed.
        checks_failed: List of check names that failed (with reasons).
        account_snapshot: Point-in-time account state used for validation.
        timestamp: When the decision was made.
    """

    decision_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    signal_id: str = ""
    fusion_id: Optional[str] = None
    approved: bool = False
    rejection_reason: Optional[str] = None
    checks_run: list[str] = field(default_factory=list)
    checks_passed: list[str] = field(default_factory=list)
    checks_failed: list[dict[str, str]] = field(default_factory=list)
    account_snapshot: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "signal_id": self.signal_id,
            "fusion_id": self.fusion_id,
            "approved": self.approved,
            "rejection_reason": self.rejection_reason,
            "checks_run": self.checks_run,
            "checks_passed": self.checks_passed,
            "checks_failed": self.checks_failed,
            "account_snapshot": self.account_snapshot,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ExecutionRecord:
    """Record of a trade execution linked back to its originating signal.

    The final link in the audit chain: Signal → Fusion → Risk → Execution.
    This is what trade attribution reads to decompose P&L.

    Attributes:
        execution_id: Unique identifier (also the idempotency key).
        signal_id: Originating signal.
        fusion_id: Fusion record that produced the recommendation.
        decision_id: Risk decision that approved this execution.
        ticker: Instrument traded.
        direction: long / short.
        order_type: market / limit / stop / stop_limit.
        quantity: Number of shares/contracts.
        fill_price: Actual fill price.
        requested_price: Price when order was submitted.
        slippage: fill_price - requested_price (signed).
        broker: Which broker executed (alpaca, ibkr, etc.).
        status: pending / filled / partial / rejected / cancelled.
        fill_timestamp: When the fill was confirmed.
        created_at: When the record was created.
        config_snapshot: ExecutorConfig values at execution time.
    """

    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    signal_id: str = ""
    fusion_id: Optional[str] = None
    decision_id: Optional[str] = None
    ticker: str = ""
    direction: str = "long"
    order_type: str = "market"
    quantity: float = 0.0
    fill_price: float = 0.0
    requested_price: float = 0.0
    slippage: float = 0.0
    broker: str = ""
    status: str = "pending"
    fill_timestamp: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    config_snapshot: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "signal_id": self.signal_id,
            "fusion_id": self.fusion_id,
            "decision_id": self.decision_id,
            "ticker": self.ticker,
            "direction": self.direction,
            "order_type": self.order_type,
            "quantity": self.quantity,
            "fill_price": round(self.fill_price, 4),
            "requested_price": round(self.requested_price, 4),
            "slippage": round(self.slippage, 6),
            "broker": self.broker,
            "status": self.status,
            "fill_timestamp": self.fill_timestamp.isoformat() if self.fill_timestamp else None,
            "created_at": self.created_at.isoformat(),
            "config_snapshot": self.config_snapshot,
        }
