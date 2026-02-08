"""PRD-116: Disaster Recovery — Replication Monitor.

Replica health tracking, lag monitoring, and automatic failover detection.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from .config import BackupConfig, ReplicaStatus


@dataclass
class Replica:
    """A database replica with health metadata."""

    replica_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    name: str = ""
    host: str = ""
    port: int = 5432
    status: ReplicaStatus = ReplicaStatus.HEALTHY
    lag_seconds: float = 0.0
    last_sync: Optional[datetime] = None
    bytes_behind: int = 0
    is_primary: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReplicationEvent:
    """An event in the replication timeline."""

    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    replica_id: str = ""
    event_type: str = ""  # lag_alert, failover, sync, disconnect
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class ReplicationMonitor:
    """Monitor for database replication health."""

    def __init__(self, config: Optional[BackupConfig] = None) -> None:
        self.config = config or BackupConfig()
        self._replicas: dict[str, Replica] = {}
        self._events: list[ReplicationEvent] = []
        self._topology: dict[str, list[str]] = {}  # primary -> [replica_ids]

    @property
    def replicas(self) -> dict[str, Replica]:
        return dict(self._replicas)

    def register_replica(
        self,
        name: str,
        host: str,
        port: int = 5432,
        is_primary: bool = False,
    ) -> Replica:
        """Register a replica for monitoring."""
        replica = Replica(
            name=name,
            host=host,
            port=port,
            is_primary=is_primary,
            last_sync=datetime.now(timezone.utc),
        )
        self._replicas[replica.replica_id] = replica

        if is_primary:
            self._topology[replica.replica_id] = []

        return replica

    def update_replica_status(
        self,
        replica_id: str,
        lag_seconds: float,
        bytes_behind: int = 0,
    ) -> Optional[Replica]:
        """Update replica lag metrics and derive status."""
        replica = self._replicas.get(replica_id)
        if replica is None:
            return None

        replica.lag_seconds = lag_seconds
        replica.bytes_behind = bytes_behind
        replica.last_sync = datetime.now(timezone.utc)

        threshold = self.config.replica_lag_threshold_seconds
        if lag_seconds <= threshold * 0.5:
            replica.status = ReplicaStatus.HEALTHY
        elif lag_seconds <= threshold:
            replica.status = ReplicaStatus.LAGGING
            self._record_event(replica_id, "lag_alert", {
                "lag_seconds": lag_seconds,
                "threshold": threshold,
            })
        else:
            replica.status = ReplicaStatus.STALE
            self._record_event(replica_id, "stale_alert", {
                "lag_seconds": lag_seconds,
                "threshold": threshold,
            })

        return replica

    def disconnect_replica(self, replica_id: str) -> bool:
        """Mark a replica as disconnected."""
        replica = self._replicas.get(replica_id)
        if replica is None:
            return False
        replica.status = ReplicaStatus.DISCONNECTED
        self._record_event(replica_id, "disconnect", {})
        return True

    def set_topology(self, primary_id: str, replica_ids: list[str]) -> bool:
        """Set the replication topology (primary -> replicas)."""
        if primary_id not in self._replicas:
            return False
        for rid in replica_ids:
            if rid not in self._replicas:
                return False
        self._topology[primary_id] = list(replica_ids)
        return True

    def get_topology(self) -> dict[str, list[str]]:
        """Get the current replication topology."""
        return dict(self._topology)

    def detect_failover_candidate(self) -> Optional[Replica]:
        """Find the best replica for failover (lowest lag, healthy)."""
        candidates = [
            r for r in self._replicas.values()
            if not r.is_primary and r.status in (ReplicaStatus.HEALTHY, ReplicaStatus.LAGGING)
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda r: r.lag_seconds)

    def execute_failover(self, replica_id: str) -> dict[str, Any]:
        """Promote a replica to primary (simulated)."""
        replica = self._replicas.get(replica_id)
        if replica is None:
            return {"success": False, "error": "Replica not found"}
        if replica.is_primary:
            return {"success": False, "error": "Already primary"}

        # Demote current primary
        for r in self._replicas.values():
            if r.is_primary:
                r.is_primary = False
                self._record_event(r.replica_id, "demoted", {})
                break

        replica.is_primary = True
        replica.lag_seconds = 0.0
        replica.status = ReplicaStatus.HEALTHY
        self._topology[replica.replica_id] = []
        self._record_event(replica_id, "failover", {"promoted_to": "primary"})

        return {"success": True, "new_primary": replica.replica_id}

    def get_health_summary(self) -> dict[str, Any]:
        """Get overall replication health summary."""
        replicas = list(self._replicas.values())
        status_counts: dict[str, int] = {}
        for r in replicas:
            status_counts[r.status.value] = status_counts.get(r.status.value, 0) + 1

        max_lag = max((r.lag_seconds for r in replicas), default=0.0)
        avg_lag = (
            sum(r.lag_seconds for r in replicas) / len(replicas)
            if replicas
            else 0.0
        )

        return {
            "total_replicas": len(replicas),
            "status_counts": status_counts,
            "max_lag_seconds": round(max_lag, 2),
            "avg_lag_seconds": round(avg_lag, 2),
            "primary_count": sum(1 for r in replicas if r.is_primary),
            "events_count": len(self._events),
        }

    def get_events(
        self,
        replica_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[ReplicationEvent]:
        """Get replication events with optional filter."""
        events = self._events
        if replica_id is not None:
            events = [e for e in events if e.replica_id == replica_id]
        return events[-limit:]

    def _record_event(
        self, replica_id: str, event_type: str, details: dict[str, Any],
    ) -> None:
        """Record a replication event."""
        event = ReplicationEvent(
            replica_id=replica_id,
            event_type=event_type,
            details=details,
        )
        self._events.append(event)
