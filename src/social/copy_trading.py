"""Copy trading engine.

Manages copy relationships, position mirroring, and P&L tracking.
"""

import logging
from typing import Optional

from src.social.config import (
    CopyStatus,
    CopyMode,
    CopyConfig,
    SocialConfig,
    DEFAULT_SOCIAL_CONFIG,
)
from src.social.models import CopyRelationship, _utc_now

logger = logging.getLogger(__name__)


class CopyTradingEngine:
    """Manages copy trading relationships and trade mirroring.

    Features:
    - Start/stop/pause copy relationships
    - Allocation scaling (fixed, percentage, proportional)
    - Max loss protection with auto-stop
    - Copy delay for review
    - P&L tracking per relationship
    """

    def __init__(self, config: Optional[SocialConfig] = None) -> None:
        self.config = config or DEFAULT_SOCIAL_CONFIG
        self._relationships: dict[str, CopyRelationship] = {}

    def start_copying(
        self,
        copier_user_id: str,
        leader_user_id: str,
        strategy_id: str,
        mode: CopyMode = CopyMode.FIXED_AMOUNT,
        allocation_amount: float = 1000.0,
        max_loss_pct: Optional[float] = None,
        copy_delay_seconds: int = 0,
    ) -> CopyRelationship:
        """Start copying a trader's strategy.

        Args:
            copier_user_id: User who wants to copy.
            leader_user_id: Trader being copied.
            strategy_id: Strategy to copy.
            mode: Allocation mode.
            allocation_amount: Fixed amount or percentage.
            max_loss_pct: Maximum loss before auto-stop.
            copy_delay_seconds: Delay before executing copies.

        Returns:
            Created CopyRelationship.

        Raises:
            ValueError: If limits exceeded or self-copy attempted.
        """
        if copier_user_id == leader_user_id:
            raise ValueError("Cannot copy yourself")

        # Check allocation limits
        copy_config = self.config.copy
        if mode == CopyMode.PERCENTAGE and allocation_amount > copy_config.max_allocation_pct * 100:
            raise ValueError(
                f"Percentage exceeds max ({copy_config.max_allocation_pct * 100}%)"
            )

        if mode == CopyMode.FIXED_AMOUNT and allocation_amount < copy_config.min_allocation_usd:
            raise ValueError(
                f"Amount below minimum (${copy_config.min_allocation_usd})"
            )

        # Check concurrent copy limit
        active_copies = self.get_active_copies(copier_user_id)
        if len(active_copies) >= copy_config.max_concurrent_copies:
            raise ValueError(
                f"Exceeded max concurrent copies ({copy_config.max_concurrent_copies})"
            )

        # Check for duplicate
        for rel in active_copies:
            if rel.leader_user_id == leader_user_id and rel.strategy_id == strategy_id:
                raise ValueError("Already copying this strategy from this trader")

        relationship = CopyRelationship(
            copier_user_id=copier_user_id,
            leader_user_id=leader_user_id,
            strategy_id=strategy_id,
            mode=mode,
            allocation_amount=allocation_amount,
            max_loss_pct=max_loss_pct or copy_config.default_stop_loss_pct,
            copy_delay_seconds=copy_delay_seconds,
        )

        self._relationships[relationship.copy_id] = relationship
        logger.info(
            "User %s started copying %s (strategy %s)",
            copier_user_id, leader_user_id, strategy_id,
        )
        return relationship

    def stop_copying(self, copy_id: str) -> Optional[CopyRelationship]:
        """Stop a copy relationship.

        Args:
            copy_id: Copy relationship ID.

        Returns:
            Updated relationship, or None if not found.
        """
        rel = self._relationships.get(copy_id)
        if not rel:
            return None

        rel.stop()
        logger.info("Stopped copy relationship %s", copy_id)
        return rel

    def pause_copying(self, copy_id: str) -> Optional[CopyRelationship]:
        """Pause a copy relationship.

        Args:
            copy_id: Copy relationship ID.

        Returns:
            Updated relationship, or None if not found.
        """
        rel = self._relationships.get(copy_id)
        if not rel:
            return None

        rel.pause()
        return rel

    def resume_copying(self, copy_id: str) -> Optional[CopyRelationship]:
        """Resume a paused copy relationship.

        Args:
            copy_id: Copy relationship ID.

        Returns:
            Updated relationship, or None if not found.
        """
        rel = self._relationships.get(copy_id)
        if not rel:
            return None

        rel.resume()
        return rel

    def get_relationship(self, copy_id: str) -> Optional[CopyRelationship]:
        """Get a copy relationship by ID."""
        return self._relationships.get(copy_id)

    def get_active_copies(self, copier_user_id: str) -> list[CopyRelationship]:
        """Get active copy relationships for a copier.

        Args:
            copier_user_id: Copier user ID.

        Returns:
            List of active relationships.
        """
        return [
            r for r in self._relationships.values()
            if r.copier_user_id == copier_user_id
            and r.status in (CopyStatus.ACTIVE, CopyStatus.PAUSED)
        ]

    def get_copiers(self, leader_user_id: str) -> list[CopyRelationship]:
        """Get all users copying a leader.

        Args:
            leader_user_id: Leader user ID.

        Returns:
            List of copy relationships.
        """
        return [
            r for r in self._relationships.values()
            if r.leader_user_id == leader_user_id
            and r.status == CopyStatus.ACTIVE
        ]

    def record_copied_trade(
        self,
        copy_id: str,
        pnl: float,
    ) -> Optional[CopyRelationship]:
        """Record a copied trade's P&L.

        Args:
            copy_id: Copy relationship ID.
            pnl: P&L from the trade.

        Returns:
            Updated relationship, or None if not found.
        """
        rel = self._relationships.get(copy_id)
        if not rel:
            return None

        rel.record_trade(pnl)

        # Check max loss
        if rel.check_max_loss():
            logger.warning(
                "Copy %s hit max loss (%.1f%%), auto-stopped",
                copy_id, rel.max_loss_pct * 100,
            )

        return rel

    def compute_copy_size(
        self,
        copy_id: str,
        leader_position_pct: float,
        leader_portfolio_value: float,
    ) -> float:
        """Compute the position size for a copied trade.

        Args:
            copy_id: Copy relationship ID.
            leader_position_pct: Leader's position as % of portfolio.
            leader_portfolio_value: Leader's total portfolio value.

        Returns:
            Dollar amount to allocate.
        """
        rel = self._relationships.get(copy_id)
        if not rel or rel.status != CopyStatus.ACTIVE:
            return 0.0

        if rel.mode == CopyMode.FIXED_AMOUNT:
            # Scale proportionally within fixed allocation
            return rel.allocation_amount * leader_position_pct

        elif rel.mode == CopyMode.PERCENTAGE:
            # allocation_amount is a percentage (e.g., 10 = 10%)
            pct = rel.allocation_amount / 100.0
            return pct * leader_portfolio_value * leader_position_pct

        elif rel.mode == CopyMode.PROPORTIONAL:
            # Mirror exact percentage
            return rel.allocation_amount * leader_position_pct

        return 0.0

    def get_stats(self) -> dict:
        """Get copy trading statistics.

        Returns:
            Stats dict.
        """
        all_rels = list(self._relationships.values())
        active = [r for r in all_rels if r.status == CopyStatus.ACTIVE]
        return {
            "total_relationships": len(all_rels),
            "active": len(active),
            "paused": sum(1 for r in all_rels if r.status == CopyStatus.PAUSED),
            "stopped": sum(1 for r in all_rels if r.status == CopyStatus.STOPPED),
            "max_loss_stopped": sum(
                1 for r in all_rels if r.status == CopyStatus.MAX_LOSS_HIT
            ),
            "total_trades_copied": sum(r.total_trades_copied for r in all_rels),
            "total_pnl": sum(r.total_pnl for r in all_rels),
        }
