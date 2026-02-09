"""Signal Recorder — high-level API for recording pipeline events.

Provides convenient methods that create the correct record type,
link records together, and persist them through the SignalStore.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from src.signal_persistence.models import (
    ExecutionRecord,
    FusionRecord,
    PersistenceConfig,
    RiskDecisionRecord,
    SignalRecord,
    SignalStatus,
)
from src.signal_persistence.store import SignalStore

logger = logging.getLogger(__name__)


class SignalRecorder:
    """High-level recorder for the signal pipeline.

    Wraps SignalStore with convenience methods that handle record creation,
    linking, and status transitions automatically.

    Args:
        store: The underlying SignalStore (created if not provided).
        config: PersistenceConfig for the store.

    Example:
        recorder = SignalRecorder()

        # When a signal is generated
        signal_id = recorder.record_signal(
            source="ema_cloud", ticker="AAPL",
            direction="bullish", strength=78.5, confidence=0.85
        )

        # When fusion happens
        fusion_id = recorder.record_fusion(
            ticker="AAPL", input_signal_ids=[signal_id],
            direction="bullish", composite_score=72.3, confidence=0.78
        )

        # When risk gate decides
        decision_id = recorder.record_risk_decision(
            signal_id=signal_id, fusion_id=fusion_id,
            approved=True, checks_run=["daily_loss", "max_positions", ...]
        )

        # When execution happens
        exec_id = recorder.record_execution(
            signal_id=signal_id, fusion_id=fusion_id,
            decision_id=decision_id, ticker="AAPL",
            direction="long", quantity=100, fill_price=185.50
        )
    """

    def __init__(
        self,
        store: SignalStore | None = None,
        config: PersistenceConfig | None = None,
    ) -> None:
        self.store = store or SignalStore(config)

    def record_signal(
        self,
        source: str,
        ticker: str,
        direction: str,
        strength: float,
        confidence: float = 0.5,
        signal_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Record a raw signal generation event.

        Returns:
            The signal_id of the persisted record.
        """
        record = SignalRecord(
            source=source,
            ticker=ticker,
            direction=direction,
            strength=strength,
            confidence=confidence,
            source_metadata=metadata or {},
            status=SignalStatus.GENERATED,
        )
        if signal_id:
            record.signal_id = signal_id
        return self.store.save_signal(record)

    def record_fusion(
        self,
        ticker: str,
        input_signal_ids: list[str],
        direction: str,
        composite_score: float,
        confidence: float,
        source_count: int = 0,
        agreement_ratio: float = 0.0,
        source_weights_used: dict[str, float] | None = None,
    ) -> str:
        """Record a fusion decision and link input signals.

        Returns:
            The fusion_id of the persisted record.
        """
        record = FusionRecord(
            ticker=ticker,
            input_signal_ids=list(input_signal_ids),
            direction=direction,
            composite_score=composite_score,
            confidence=confidence,
            source_count=source_count or len(input_signal_ids),
            agreement_ratio=agreement_ratio,
            source_weights_used=source_weights_used or {},
        )
        fusion_id = self.store.save_fusion(record)

        # Link each input signal to this fusion
        for sig_id in input_signal_ids:
            self.store.link_signal_to_fusion(sig_id, fusion_id)

        return fusion_id

    def record_risk_decision(
        self,
        signal_id: str,
        approved: bool,
        fusion_id: str | None = None,
        rejection_reason: str | None = None,
        checks_run: list[str] | None = None,
        checks_passed: list[str] | None = None,
        checks_failed: list[dict[str, str]] | None = None,
        account_snapshot: dict[str, Any] | None = None,
    ) -> str:
        """Record a risk gate decision.

        Returns:
            The decision_id of the persisted record.
        """
        record = RiskDecisionRecord(
            signal_id=signal_id,
            fusion_id=fusion_id,
            approved=approved,
            rejection_reason=rejection_reason,
            checks_run=checks_run or [],
            checks_passed=checks_passed or [],
            checks_failed=checks_failed or [],
            account_snapshot=account_snapshot or {},
        )
        decision_id = self.store.save_decision(record)

        # Update signal status
        new_status = SignalStatus.RISK_APPROVED if approved else SignalStatus.RISK_REJECTED
        self.store.update_signal_status(signal_id, new_status)

        return decision_id

    def record_execution(
        self,
        signal_id: str,
        ticker: str,
        direction: str,
        quantity: float,
        fill_price: float,
        fusion_id: str | None = None,
        decision_id: str | None = None,
        order_type: str = "market",
        requested_price: float = 0.0,
        broker: str = "alpaca",
        status: str = "filled",
        config_snapshot: dict[str, Any] | None = None,
    ) -> str:
        """Record a trade execution.

        Returns:
            The execution_id of the persisted record.
        """
        slippage = fill_price - requested_price if requested_price > 0 else 0.0

        record = ExecutionRecord(
            signal_id=signal_id,
            fusion_id=fusion_id,
            decision_id=decision_id,
            ticker=ticker,
            direction=direction,
            order_type=order_type,
            quantity=quantity,
            fill_price=fill_price,
            requested_price=requested_price,
            slippage=slippage,
            broker=broker,
            status=status,
            fill_timestamp=datetime.now(timezone.utc) if status == "filled" else None,
            config_snapshot=config_snapshot or {},
        )
        execution_id = self.store.save_execution(record)

        # Link signal to execution
        self.store.link_signal_to_execution(signal_id, execution_id)

        return execution_id

    def get_pipeline_trace(self, signal_id: str) -> dict:
        """Get the complete audit trail for a signal."""
        return self.store.get_full_trace(signal_id)

    def get_stats(self) -> dict:
        """Get store statistics."""
        return self.store.get_stats()
