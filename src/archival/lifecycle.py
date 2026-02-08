"""Data lifecycle management across storage tiers."""

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from .config import ArchivalConfig, StorageTier

logger = logging.getLogger(__name__)

# Cost model per tier (USD per GB per month)
DEFAULT_TIER_COSTS = {
    StorageTier.HOT: 0.023,
    StorageTier.WARM: 0.0125,
    StorageTier.COLD: 0.004,
    StorageTier.ARCHIVE: 0.00099,
    StorageTier.DELETED: 0.0,
}


@dataclass
class TierStats:
    """Statistics for a single storage tier."""

    tier: StorageTier = StorageTier.HOT
    record_count: int = 0
    bytes_used: int = 0
    table_count: int = 0
    cost_per_gb_month: float = 0.0


class DataLifecycleManager:
    """Manages data distribution and cost across storage tiers."""

    def __init__(self, config: Optional[ArchivalConfig] = None):
        self._config = config or ArchivalConfig()
        self._tier_stats: Dict[StorageTier, TierStats] = {}
        self._transitions: List[dict] = []
        self._lock = threading.Lock()

    def record_tier_stats(
        self,
        tier: StorageTier,
        records: int,
        bytes_used: int,
        tables: int,
        cost_per_gb: float = 0.0,
    ) -> None:
        """Record or update statistics for a storage tier."""
        with self._lock:
            effective_cost = cost_per_gb if cost_per_gb > 0 else DEFAULT_TIER_COSTS.get(tier, 0.0)
            self._tier_stats[tier] = TierStats(
                tier=tier,
                record_count=records,
                bytes_used=bytes_used,
                table_count=tables,
                cost_per_gb_month=effective_cost,
            )
            logger.info(
                "Updated tier stats for %s: %d records, %d bytes, %d tables",
                tier.value, records, bytes_used, tables,
            )

    def get_tier_stats(self) -> Dict[StorageTier, TierStats]:
        """Return statistics for all tiers."""
        return dict(self._tier_stats)

    def get_total_cost(self) -> float:
        """Calculate total monthly storage cost across all tiers."""
        total = 0.0
        for stats in self._tier_stats.values():
            gb_used = stats.bytes_used / (1024 ** 3)
            total += gb_used * stats.cost_per_gb_month
        return total

    def get_cost_by_tier(self) -> dict:
        """Return monthly cost breakdown by tier."""
        costs = {}
        for tier, stats in self._tier_stats.items():
            gb_used = stats.bytes_used / (1024 ** 3)
            costs[tier.value] = {
                "bytes_used": stats.bytes_used,
                "gb_used": round(gb_used, 4),
                "cost_per_gb_month": stats.cost_per_gb_month,
                "monthly_cost": round(gb_used * stats.cost_per_gb_month, 4),
            }
        return costs

    def transition_data(
        self,
        table_name: str,
        from_tier: StorageTier,
        to_tier: StorageTier,
        records: int,
        bytes_moved: int,
    ) -> dict:
        """Record a data transition between tiers."""
        with self._lock:
            transition = {
                "table_name": table_name,
                "from_tier": from_tier.value,
                "to_tier": to_tier.value,
                "records": records,
                "bytes_moved": bytes_moved,
                "timestamp": datetime.utcnow().isoformat(),
            }
            self._transitions.append(transition)

            # Update tier stats if they exist
            if from_tier in self._tier_stats:
                self._tier_stats[from_tier].record_count = max(
                    0, self._tier_stats[from_tier].record_count - records
                )
                self._tier_stats[from_tier].bytes_used = max(
                    0, self._tier_stats[from_tier].bytes_used - bytes_moved
                )

            if to_tier in self._tier_stats:
                self._tier_stats[to_tier].record_count += records
                self._tier_stats[to_tier].bytes_used += bytes_moved
            else:
                self._tier_stats[to_tier] = TierStats(
                    tier=to_tier,
                    record_count=records,
                    bytes_used=bytes_moved,
                    table_count=1,
                    cost_per_gb_month=DEFAULT_TIER_COSTS.get(to_tier, 0.0),
                )

            logger.info(
                "Transitioned %d records (%d bytes) from %s to %s for table %s",
                records, bytes_moved, from_tier.value, to_tier.value, table_name,
            )
            return transition

    def get_transitions(self, table_name: Optional[str] = None) -> List[dict]:
        """Return transition history, optionally filtered by table."""
        if table_name:
            return [t for t in self._transitions if t["table_name"] == table_name]
        return list(self._transitions)

    def get_optimization_recommendations(self) -> List[dict]:
        """Generate cost optimization recommendations based on current tier distribution."""
        recommendations = []

        hot_stats = self._tier_stats.get(StorageTier.HOT)
        warm_stats = self._tier_stats.get(StorageTier.WARM)
        cold_stats = self._tier_stats.get(StorageTier.COLD)

        if hot_stats and hot_stats.bytes_used > 100 * (1024 ** 3):  # > 100 GB in hot
            hot_gb = hot_stats.bytes_used / (1024 ** 3)
            potential_savings = hot_gb * (
                DEFAULT_TIER_COSTS[StorageTier.HOT] - DEFAULT_TIER_COSTS[StorageTier.WARM]
            )
            recommendations.append({
                "recommendation": "Move older data from HOT to WARM tier",
                "detail": f"{hot_gb:.1f} GB in HOT storage exceeds 100 GB threshold",
                "savings": round(potential_savings, 2),
                "priority": "high",
            })

        if warm_stats and warm_stats.bytes_used > 500 * (1024 ** 3):  # > 500 GB in warm
            warm_gb = warm_stats.bytes_used / (1024 ** 3)
            potential_savings = warm_gb * (
                DEFAULT_TIER_COSTS[StorageTier.WARM] - DEFAULT_TIER_COSTS[StorageTier.COLD]
            )
            recommendations.append({
                "recommendation": "Move aged data from WARM to COLD tier",
                "detail": f"{warm_gb:.1f} GB in WARM storage exceeds 500 GB threshold",
                "savings": round(potential_savings, 2),
                "priority": "medium",
            })

        if cold_stats and cold_stats.bytes_used > 1000 * (1024 ** 3):  # > 1 TB in cold
            cold_gb = cold_stats.bytes_used / (1024 ** 3)
            potential_savings = cold_gb * (
                DEFAULT_TIER_COSTS[StorageTier.COLD] - DEFAULT_TIER_COSTS[StorageTier.ARCHIVE]
            )
            recommendations.append({
                "recommendation": "Archive data from COLD to ARCHIVE tier",
                "detail": f"{cold_gb:.1f} GB in COLD storage exceeds 1 TB threshold",
                "savings": round(potential_savings, 2),
                "priority": "low",
            })

        if not recommendations:
            recommendations.append({
                "recommendation": "No optimization needed",
                "detail": "Current tier distribution is within optimal thresholds",
                "savings": 0.0,
                "priority": "info",
            })

        return recommendations

    def get_storage_summary(self) -> dict:
        """Return a comprehensive storage summary."""
        total_bytes = sum(s.bytes_used for s in self._tier_stats.values())
        total_records = sum(s.record_count for s in self._tier_stats.values())
        total_cost = self.get_total_cost()

        tier_breakdown = {}
        for tier, stats in self._tier_stats.items():
            tier_breakdown[tier.value] = {
                "records": stats.record_count,
                "bytes": stats.bytes_used,
                "tables": stats.table_count,
                "cost_per_gb_month": stats.cost_per_gb_month,
            }

        return {
            "total_bytes": total_bytes,
            "total_records": total_records,
            "total_monthly_cost": round(total_cost, 4),
            "tier_count": len(self._tier_stats),
            "transition_count": len(self._transitions),
            "tier_breakdown": tier_breakdown,
        }

    def reset(self) -> None:
        """Reset all manager state."""
        with self._lock:
            self._tier_stats.clear()
            self._transitions.clear()
