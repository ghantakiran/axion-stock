"""Blockchain Settlement Engine."""

import logging
from datetime import datetime
from typing import Optional

from src.blockchain.config import (
    BlockchainConfig,
    BlockchainNetwork,
    SettlementStatus,
    SettlementType,
    NETWORK_CONFIGS,
    DEFAULT_BLOCKCHAIN_CONFIG,
)
from src.blockchain.models import (
    SettlementRecord,
    BlockchainTransaction,
    AtomicSwap,
    SettlementSummary,
)

logger = logging.getLogger(__name__)


class SettlementEngine:
    """Manages blockchain settlement lifecycle.

    Features:
    - Initiate settlements (instant, deferred, atomic swap, DVP, batch)
    - Track settlement status through lifecycle
    - Retry failed settlements
    - Gas estimation
    - Settlement summary reporting
    """

    def __init__(self, config: Optional[BlockchainConfig] = None):
        self.config = config or DEFAULT_BLOCKCHAIN_CONFIG
        self._settlements: dict[str, SettlementRecord] = {}
        self._transactions: dict[str, BlockchainTransaction] = {}
        self._swaps: dict[str, AtomicSwap] = {}

    def initiate_settlement(
        self,
        trade_id: str,
        amount: float,
        asset_symbol: str,
        sender: str,
        receiver: str,
        settlement_type: SettlementType = SettlementType.INSTANT,
        network: Optional[BlockchainNetwork] = None,
    ) -> SettlementRecord:
        """Initiate a new settlement.

        Args:
            trade_id: Associated trade ID.
            amount: Settlement amount.
            asset_symbol: Asset being settled.
            sender: Sender address.
            receiver: Receiver address.
            settlement_type: Type of settlement.
            network: Blockchain network (defaults to config).

        Returns:
            SettlementRecord.
        """
        network = network or self.config.default_network

        record = SettlementRecord(
            trade_id=trade_id,
            settlement_type=settlement_type,
            network=network,
            status=SettlementStatus.INITIATED,
            amount=amount,
            asset_symbol=asset_symbol,
            sender=sender,
            receiver=receiver,
        )

        self._settlements[record.id] = record
        logger.info(
            "Settlement initiated: %s | %s %s | %s -> %s",
            record.id, amount, asset_symbol, sender[:10], receiver[:10],
        )

        return record

    def submit_settlement(self, settlement_id: str) -> SettlementRecord:
        """Submit a settlement for on-chain execution.

        Args:
            settlement_id: Settlement ID to submit.

        Returns:
            Updated SettlementRecord.

        Raises:
            ValueError: If settlement not found.
        """
        record = self._settlements.get(settlement_id)
        if not record:
            raise ValueError(f"Settlement {settlement_id} not found")

        if record.status != SettlementStatus.INITIATED:
            raise ValueError(f"Settlement {settlement_id} is not in INITIATED state")

        record.status = SettlementStatus.PENDING

        # Simulate transaction creation
        tx = BlockchainTransaction(
            network=record.network,
            from_address=record.sender,
            to_address=record.receiver,
            value=record.amount,
            status=SettlementStatus.PENDING,
        )
        self._transactions[tx.id] = tx
        record.tx_hash = tx.tx_hash or tx.id

        return record

    def confirm_settlement(
        self,
        settlement_id: str,
        tx_hash: str = "",
        block_number: int = 0,
        gas_cost: float = 0.0,
    ) -> SettlementRecord:
        """Mark a settlement as confirmed/settled.

        Args:
            settlement_id: Settlement ID.
            tx_hash: Transaction hash.
            block_number: Block number.
            gas_cost: Gas cost in native token.

        Returns:
            Updated SettlementRecord.
        """
        record = self._settlements.get(settlement_id)
        if not record:
            raise ValueError(f"Settlement {settlement_id} not found")

        now = datetime.now()
        record.status = SettlementStatus.SETTLED
        record.tx_hash = tx_hash or record.tx_hash
        record.block_number = block_number
        record.gas_cost = gas_cost
        record.settled_at = now
        record.settlement_time_seconds = (now - record.initiated_at).total_seconds()

        return record

    def fail_settlement(
        self,
        settlement_id: str,
        error_message: str = "",
    ) -> SettlementRecord:
        """Mark a settlement as failed.

        Args:
            settlement_id: Settlement ID.
            error_message: Error description.

        Returns:
            Updated SettlementRecord.
        """
        record = self._settlements.get(settlement_id)
        if not record:
            raise ValueError(f"Settlement {settlement_id} not found")

        record.status = SettlementStatus.FAILED
        record.error_message = error_message
        record.retries += 1

        return record

    def retry_settlement(self, settlement_id: str) -> SettlementRecord:
        """Retry a failed settlement.

        Args:
            settlement_id: Settlement ID to retry.

        Returns:
            Updated SettlementRecord.

        Raises:
            ValueError: If settlement not found or max retries exceeded.
        """
        record = self._settlements.get(settlement_id)
        if not record:
            raise ValueError(f"Settlement {settlement_id} not found")

        if not record.is_failed:
            raise ValueError(f"Settlement {settlement_id} is not in a failed state")

        if record.retries >= self.config.max_retries:
            raise ValueError(
                f"Settlement {settlement_id} exceeded max retries ({self.config.max_retries})"
            )

        record.status = SettlementStatus.PENDING
        record.error_message = None

        return record

    def initiate_atomic_swap(
        self,
        initiator: str,
        participant: str,
        send_asset: str,
        send_amount: float,
        receive_asset: str,
        receive_amount: float,
        secret_hash: str = "",
        timelock: int = 3600,
        network: Optional[BlockchainNetwork] = None,
    ) -> AtomicSwap:
        """Initiate an atomic swap.

        Args:
            initiator: Initiator address.
            participant: Participant address.
            send_asset: Asset being sent.
            send_amount: Amount being sent.
            receive_asset: Asset being received.
            receive_amount: Amount being received.
            secret_hash: Hash of the secret for HTLC.
            timelock: Timelock in seconds.
            network: Blockchain network.

        Returns:
            AtomicSwap record.
        """
        swap = AtomicSwap(
            initiator=initiator,
            participant=participant,
            send_asset=send_asset,
            send_amount=send_amount,
            receive_asset=receive_asset,
            receive_amount=receive_amount,
            secret_hash=secret_hash,
            timelock=timelock,
            network=network or self.config.default_network,
        )

        self._swaps[swap.id] = swap
        return swap

    def complete_swap(self, swap_id: str) -> AtomicSwap:
        """Complete an atomic swap."""
        swap = self._swaps.get(swap_id)
        if not swap:
            raise ValueError(f"Swap {swap_id} not found")
        swap.status = SettlementStatus.SETTLED
        return swap

    def get_settlement(self, settlement_id: str) -> Optional[SettlementRecord]:
        """Get a settlement by ID."""
        return self._settlements.get(settlement_id)

    def get_settlements_by_status(
        self, status: SettlementStatus,
    ) -> list[SettlementRecord]:
        """Get settlements filtered by status."""
        return [s for s in self._settlements.values() if s.status == status]

    def get_summary(self) -> SettlementSummary:
        """Get settlement activity summary."""
        settlements = list(self._settlements.values())
        if not settlements:
            return SettlementSummary()

        completed = [s for s in settlements if s.is_complete]
        pending = [s for s in settlements if s.status in [
            SettlementStatus.INITIATED, SettlementStatus.PENDING, SettlementStatus.CONFIRMING,
        ]]
        failed = [s for s in settlements if s.is_failed]

        avg_time = 0.0
        if completed:
            times = [s.settlement_time_seconds for s in completed if s.settlement_time_seconds]
            avg_time = sum(times) / len(times) if times else 0.0

        return SettlementSummary(
            total_settlements=len(settlements),
            completed=len(completed),
            pending=len(pending),
            failed=len(failed),
            total_volume=sum(s.amount for s in settlements),
            total_gas_cost=sum(s.gas_cost for s in completed),
            avg_settlement_time=avg_time,
            success_rate=len(completed) / len(settlements) * 100 if settlements else 0,
        )

    def estimate_gas(self, network: BlockchainNetwork) -> dict:
        """Estimate gas costs for a settlement on given network.

        Args:
            network: Blockchain network.

        Returns:
            Dict with gas estimates.
        """
        net_config = NETWORK_CONFIGS.get(network, {})
        block_time = net_config.get("block_time_seconds", 12)
        confirmations = net_config.get("confirmations_required", 12)

        # Estimates for a standard ERC20 transfer
        estimated_gas = 65000
        gas_price = min(30.0, self.config.max_gas_price_gwei)

        return {
            "network": network.value,
            "estimated_gas": estimated_gas,
            "gas_price_gwei": gas_price,
            "estimated_cost_eth": (estimated_gas * gas_price) / 1e9,
            "confirmations_required": confirmations,
            "estimated_time_seconds": block_time * confirmations,
        }
