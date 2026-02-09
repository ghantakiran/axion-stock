"""Signal Store — in-memory + optional DB persistence for signal records.

Provides thread-safe CRUD operations for the full signal audit trail.
In-memory mode is used during testing and backtesting; DB mode for production.
"""

from __future__ import annotations

import logging
import threading
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from src.signal_persistence.models import (
    ExecutionRecord,
    FusionRecord,
    PersistenceConfig,
    RiskDecisionRecord,
    SignalRecord,
    SignalStatus,
)

logger = logging.getLogger(__name__)


class SignalStore:
    """Centralized store for all signal pipeline records.

    Thread-safe via a reentrant lock. Supports both in-memory and
    DB-backed persistence (DB writes are optional and non-blocking).

    Args:
        config: PersistenceConfig with retention and batch settings.

    Example:
        store = SignalStore()
        store.save_signal(signal_record)
        store.save_fusion(fusion_record)
        store.link_signal_to_fusion(signal_id, fusion_id)
        signals = store.get_signals_by_ticker("AAPL", limit=50)
    """

    def __init__(self, config: PersistenceConfig | None = None) -> None:
        self.config = config or PersistenceConfig()
        self._lock = threading.RLock()

        # Primary stores (keyed by ID)
        self._signals: dict[str, SignalRecord] = {}
        self._fusions: dict[str, FusionRecord] = {}
        self._decisions: dict[str, RiskDecisionRecord] = {}
        self._executions: dict[str, ExecutionRecord] = {}

        # Indexes for fast lookup
        self._signals_by_ticker: dict[str, list[str]] = defaultdict(list)
        self._signals_by_source: dict[str, list[str]] = defaultdict(list)
        self._signals_by_status: dict[SignalStatus, list[str]] = defaultdict(list)
        self._fusions_by_ticker: dict[str, list[str]] = defaultdict(list)
        self._executions_by_ticker: dict[str, list[str]] = defaultdict(list)

    # ── Signal CRUD ──────────────────────────────────────────────────

    def save_signal(self, record: SignalRecord) -> str:
        """Persist a signal record. Returns signal_id."""
        with self._lock:
            self._signals[record.signal_id] = record
            self._signals_by_ticker[record.ticker].append(record.signal_id)
            self._signals_by_source[record.source].append(record.signal_id)
            self._signals_by_status[record.status].append(record.signal_id)
        logger.debug("Saved signal %s for %s", record.signal_id[:8], record.ticker)
        return record.signal_id

    def get_signal(self, signal_id: str) -> Optional[SignalRecord]:
        """Get a signal by ID."""
        with self._lock:
            return self._signals.get(signal_id)

    def update_signal_status(
        self, signal_id: str, status: SignalStatus
    ) -> bool:
        """Update the status of a signal. Returns True if found."""
        with self._lock:
            record = self._signals.get(signal_id)
            if record is None:
                return False
            old_status = record.status
            record.status = status
            # Update status index
            if signal_id in self._signals_by_status.get(old_status, []):
                self._signals_by_status[old_status].remove(signal_id)
            self._signals_by_status[status].append(signal_id)
            return True

    def get_signals_by_ticker(
        self, ticker: str, limit: int = 100
    ) -> list[SignalRecord]:
        """Get recent signals for a ticker, newest first."""
        with self._lock:
            ids = self._signals_by_ticker.get(ticker, [])
            records = [self._signals[sid] for sid in ids if sid in self._signals]
            records.sort(key=lambda r: r.timestamp, reverse=True)
            return records[:limit]

    def get_signals_by_source(
        self, source: str, limit: int = 100
    ) -> list[SignalRecord]:
        """Get recent signals from a specific source."""
        with self._lock:
            ids = self._signals_by_source.get(source, [])
            records = [self._signals[sid] for sid in ids if sid in self._signals]
            records.sort(key=lambda r: r.timestamp, reverse=True)
            return records[:limit]

    def get_signals_by_status(self, status: SignalStatus) -> list[SignalRecord]:
        """Get all signals with a given status."""
        with self._lock:
            ids = self._signals_by_status.get(status, [])
            return [self._signals[sid] for sid in ids if sid in self._signals]

    # ── Fusion CRUD ──────────────────────────────────────────────────

    def save_fusion(self, record: FusionRecord) -> str:
        """Persist a fusion record. Returns fusion_id."""
        with self._lock:
            self._fusions[record.fusion_id] = record
            self._fusions_by_ticker[record.ticker].append(record.fusion_id)
        logger.debug("Saved fusion %s for %s", record.fusion_id[:8], record.ticker)
        return record.fusion_id

    def get_fusion(self, fusion_id: str) -> Optional[FusionRecord]:
        """Get a fusion record by ID."""
        with self._lock:
            return self._fusions.get(fusion_id)

    def get_fusions_by_ticker(
        self, ticker: str, limit: int = 50
    ) -> list[FusionRecord]:
        """Get recent fusions for a ticker."""
        with self._lock:
            ids = self._fusions_by_ticker.get(ticker, [])
            records = [self._fusions[fid] for fid in ids if fid in self._fusions]
            records.sort(key=lambda r: r.timestamp, reverse=True)
            return records[:limit]

    # ── Risk Decision CRUD ───────────────────────────────────────────

    def save_decision(self, record: RiskDecisionRecord) -> str:
        """Persist a risk decision record. Returns decision_id."""
        with self._lock:
            self._decisions[record.decision_id] = record
        logger.debug(
            "Saved risk decision %s: %s",
            record.decision_id[:8],
            "approved" if record.approved else "rejected",
        )
        return record.decision_id

    def get_decision(self, decision_id: str) -> Optional[RiskDecisionRecord]:
        """Get a risk decision by ID."""
        with self._lock:
            return self._decisions.get(decision_id)

    def get_decisions_for_signal(self, signal_id: str) -> list[RiskDecisionRecord]:
        """Get all risk decisions for a given signal."""
        with self._lock:
            return [
                d for d in self._decisions.values() if d.signal_id == signal_id
            ]

    # ── Execution CRUD ───────────────────────────────────────────────

    def save_execution(self, record: ExecutionRecord) -> str:
        """Persist an execution record. Returns execution_id."""
        with self._lock:
            self._executions[record.execution_id] = record
            self._executions_by_ticker[record.ticker].append(record.execution_id)
        logger.debug(
            "Saved execution %s: %s %s @ %.2f",
            record.execution_id[:8],
            record.direction,
            record.ticker,
            record.fill_price,
        )
        return record.execution_id

    def get_execution(self, execution_id: str) -> Optional[ExecutionRecord]:
        """Get an execution record by ID."""
        with self._lock:
            return self._executions.get(execution_id)

    def get_executions_by_ticker(
        self, ticker: str, limit: int = 50
    ) -> list[ExecutionRecord]:
        """Get recent executions for a ticker."""
        with self._lock:
            ids = self._executions_by_ticker.get(ticker, [])
            records = [self._executions[eid] for eid in ids if eid in self._executions]
            records.sort(key=lambda r: r.created_at, reverse=True)
            return records[:limit]

    # ── Linking ──────────────────────────────────────────────────────

    def link_signal_to_fusion(self, signal_id: str, fusion_id: str) -> bool:
        """Link a signal to its fusion record."""
        with self._lock:
            record = self._signals.get(signal_id)
            if record is None:
                return False
            record.fusion_id = fusion_id
            record.status = SignalStatus.FUSED
            return True

    def link_signal_to_execution(self, signal_id: str, execution_id: str) -> bool:
        """Link a signal to its execution record."""
        with self._lock:
            record = self._signals.get(signal_id)
            if record is None:
                return False
            record.execution_id = execution_id
            record.status = SignalStatus.EXECUTED
            return True

    # ── Pipeline trace ───────────────────────────────────────────────

    def get_full_trace(self, signal_id: str) -> dict:
        """Get the complete audit trail for a signal.

        Returns a dict with signal, fusion, decision, and execution records,
        forming the full pipeline trace from generation to execution.
        """
        with self._lock:
            signal = self._signals.get(signal_id)
            if signal is None:
                return {"error": f"Signal {signal_id} not found"}

            fusion = None
            if signal.fusion_id:
                fusion = self._fusions.get(signal.fusion_id)

            decisions = [
                d for d in self._decisions.values() if d.signal_id == signal_id
            ]

            execution = None
            if signal.execution_id:
                execution = self._executions.get(signal.execution_id)

            return {
                "signal": signal.to_dict(),
                "fusion": fusion.to_dict() if fusion else None,
                "risk_decisions": [d.to_dict() for d in decisions],
                "execution": execution.to_dict() if execution else None,
            }

    # ── Expiry ───────────────────────────────────────────────────────

    def expire_stale_signals(self) -> int:
        """Mark signals older than max_signal_age_seconds as expired.

        Returns the count of newly expired signals.
        """
        now = datetime.now(timezone.utc)
        expired_count = 0
        with self._lock:
            for record in self._signals.values():
                if record.status == SignalStatus.GENERATED:
                    age = (now - record.timestamp).total_seconds()
                    if age > self.config.max_signal_age_seconds:
                        record.status = SignalStatus.EXPIRED
                        expired_count += 1
        if expired_count > 0:
            logger.info("Expired %d stale signals", expired_count)
        return expired_count

    # ── Stats ────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Get summary statistics for the store."""
        with self._lock:
            status_counts = {}
            for status in SignalStatus:
                status_counts[status.value] = len(
                    self._signals_by_status.get(status, [])
                )
            return {
                "total_signals": len(self._signals),
                "total_fusions": len(self._fusions),
                "total_decisions": len(self._decisions),
                "total_executions": len(self._executions),
                "signals_by_status": status_counts,
                "unique_tickers": len(self._signals_by_ticker),
                "unique_sources": len(self._signals_by_source),
            }
