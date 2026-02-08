"""Blockchain Transaction Monitor."""

import logging
from typing import Optional
from datetime import datetime

from src.blockchain.config import (
    BlockchainNetwork,
    SettlementStatus,
    NETWORK_CONFIGS,
)
from src.blockchain.models import BlockchainTransaction

logger = logging.getLogger(__name__)


class TransactionMonitor:
    """Monitors blockchain transactions for confirmation.

    Features:
    - Track transaction confirmations
    - Detect reverted transactions
    - Alert on stuck/pending transactions
    - Network health monitoring
    """

    def __init__(self):
        self._watched: dict[str, BlockchainTransaction] = {}
        self._alerts: list[dict] = []

    def watch(self, tx: BlockchainTransaction) -> None:
        """Start watching a transaction."""
        self._watched[tx.id] = tx

    def update_confirmations(
        self,
        tx_id: str,
        confirmations: int,
        block_number: Optional[int] = None,
    ) -> BlockchainTransaction:
        """Update confirmation count for a watched transaction.

        Args:
            tx_id: Transaction ID.
            confirmations: Current confirmation count.
            block_number: Block number where tx was included.

        Returns:
            Updated transaction.

        Raises:
            ValueError: If transaction not found.
        """
        tx = self._watched.get(tx_id)
        if not tx:
            raise ValueError(f"Transaction {tx_id} not watched")

        tx.confirmations = confirmations
        if block_number:
            tx.block_number = block_number

        # Check if fully confirmed
        net_config = NETWORK_CONFIGS.get(tx.network, {})
        required = net_config.get("confirmations_required", 12)

        if confirmations >= required:
            tx.status = SettlementStatus.SETTLED
        elif confirmations > 0:
            tx.status = SettlementStatus.CONFIRMING

        return tx

    def mark_reverted(self, tx_id: str, reason: str = "") -> BlockchainTransaction:
        """Mark a transaction as reverted.

        Args:
            tx_id: Transaction ID.
            reason: Revert reason.

        Returns:
            Updated transaction.
        """
        tx = self._watched.get(tx_id)
        if not tx:
            raise ValueError(f"Transaction {tx_id} not watched")

        tx.status = SettlementStatus.REVERTED
        self._alerts.append({
            "type": "revert",
            "tx_id": tx_id,
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
        })

        return tx

    def get_pending(self) -> list[BlockchainTransaction]:
        """Get all pending transactions."""
        return [
            tx for tx in self._watched.values()
            if tx.is_pending
        ]

    def get_confirmed(self) -> list[BlockchainTransaction]:
        """Get all confirmed transactions."""
        return [
            tx for tx in self._watched.values()
            if tx.is_confirmed
        ]

    def get_alerts(self) -> list[dict]:
        """Get all monitoring alerts."""
        return list(self._alerts)

    def clear_alerts(self) -> None:
        """Clear all alerts."""
        self._alerts.clear()

    def get_watched_count(self) -> int:
        """Get number of watched transactions."""
        return len(self._watched)

    def unwatch(self, tx_id: str) -> bool:
        """Stop watching a transaction."""
        if tx_id in self._watched:
            del self._watched[tx_id]
            return True
        return False
