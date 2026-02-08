"""PRD-120: Deployment Strategies & Rollback Automation — Traffic Management."""

import hashlib
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class TrafficSplit:
    """Describes how traffic is split between two versions."""

    deployment_id: str = ""
    version_a: str = ""
    version_b: str = ""
    percent_a: float = 100.0
    percent_b: float = 0.0
    strategy: str = "weighted"
    updated_at: datetime = field(default_factory=datetime.utcnow)


class TrafficManager:
    """Controls traffic routing between deployment versions."""

    def __init__(self):
        self._splits: Dict[str, TrafficSplit] = {}
        self._shadow_targets: Dict[str, str] = {}
        self._lock = threading.Lock()

    def set_split(
        self,
        deployment_id: str,
        version_a: str,
        version_b: str,
        percent_b: float = 0.0,
    ) -> TrafficSplit:
        """Configure a traffic split for a deployment."""
        percent_b = max(0.0, min(100.0, percent_b))
        with self._lock:
            split = TrafficSplit(
                deployment_id=deployment_id,
                version_a=version_a,
                version_b=version_b,
                percent_a=100.0 - percent_b,
                percent_b=percent_b,
                updated_at=datetime.utcnow(),
            )
            self._splits[deployment_id] = split
            logger.info(
                "Traffic split for %s: %s=%.1f%% / %s=%.1f%%",
                deployment_id,
                version_a,
                split.percent_a,
                version_b,
                split.percent_b,
            )
            return split

    def shift_traffic(
        self, deployment_id: str, increment: float
    ) -> TrafficSplit:
        """Increase traffic to version_b by the given increment percentage."""
        with self._lock:
            split = self._splits.get(deployment_id)
            if split is None:
                raise KeyError(f"No traffic split for deployment {deployment_id}")
            new_b = min(100.0, split.percent_b + increment)
            split.percent_b = new_b
            split.percent_a = 100.0 - new_b
            split.updated_at = datetime.utcnow()
            logger.info(
                "Shifted traffic for %s: %s=%.1f%% / %s=%.1f%%",
                deployment_id,
                split.version_a,
                split.percent_a,
                split.version_b,
                split.percent_b,
            )
            return split

    def get_split(self, deployment_id: str) -> Optional[TrafficSplit]:
        """Retrieve the traffic split for a deployment."""
        return self._splits.get(deployment_id)

    def route_request(self, deployment_id: str, request_id: str) -> str:
        """Deterministically route a request to version_a or version_b.

        Uses a hash of the request_id to achieve consistent routing — the
        same request_id always routes to the same version for a given split.
        """
        split = self._splits.get(deployment_id)
        if split is None:
            raise KeyError(f"No traffic split for deployment {deployment_id}")

        # Deterministic hash-based routing
        hash_val = int(
            hashlib.sha256(request_id.encode()).hexdigest(), 16
        )
        bucket = hash_val % 10000  # 0.01% granularity
        threshold = split.percent_b * 100  # scale to 10000

        if bucket < threshold:
            return split.version_b
        return split.version_a

    def enable_shadow(self, deployment_id: str, shadow_version: str) -> bool:
        """Enable shadow traffic mirroring to a version."""
        with self._lock:
            self._shadow_targets[deployment_id] = shadow_version
            logger.info(
                "Shadow traffic enabled for %s -> %s",
                deployment_id,
                shadow_version,
            )
            return True

    def disable_shadow(self, deployment_id: str) -> bool:
        """Disable shadow traffic mirroring."""
        with self._lock:
            removed = self._shadow_targets.pop(deployment_id, None)
            if removed:
                logger.info("Shadow traffic disabled for %s", deployment_id)
                return True
            return False

    def drain_to_version(
        self, deployment_id: str, version: str
    ) -> TrafficSplit:
        """Send 100% of traffic to the specified version."""
        with self._lock:
            split = self._splits.get(deployment_id)
            if split is None:
                raise KeyError(f"No traffic split for deployment {deployment_id}")

            if version == split.version_b:
                split.percent_b = 100.0
                split.percent_a = 0.0
            else:
                split.percent_a = 100.0
                split.percent_b = 0.0
            split.updated_at = datetime.utcnow()
            logger.info(
                "Drained all traffic for %s to version %s",
                deployment_id,
                version,
            )
            return split

    def get_routing_stats(self) -> dict:
        """Return summary of all active traffic splits."""
        splits = list(self._splits.values())
        return {
            "total_splits": len(splits),
            "shadow_targets": len(self._shadow_targets),
            "splits": [
                {
                    "deployment_id": s.deployment_id,
                    "version_a": s.version_a,
                    "version_b": s.version_b,
                    "percent_a": s.percent_a,
                    "percent_b": s.percent_b,
                }
                for s in splits
            ],
        }

    def reset(self) -> None:
        """Clear all traffic splits (for testing)."""
        with self._lock:
            self._splits.clear()
            self._shadow_targets.clear()
