"""Blockchain Settlement Data Models."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import uuid4

from src.blockchain.config import (
    BlockchainNetwork,
    SettlementStatus,
    TokenStandard,
    SettlementType,
)


def _generate_id() -> str:
    return str(uuid4())


@dataclass
class BlockchainTransaction:
    """A blockchain transaction."""
    id: str = field(default_factory=_generate_id)
    tx_hash: str = ""
    network: BlockchainNetwork = BlockchainNetwork.ETHEREUM
    from_address: str = ""
    to_address: str = ""
    value: float = 0.0
    token_address: Optional[str] = None
    token_standard: TokenStandard = TokenStandard.NATIVE
    gas_used: int = 0
    gas_price_gwei: float = 0.0
    block_number: Optional[int] = None
    confirmations: int = 0
    status: SettlementStatus = SettlementStatus.PENDING
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def gas_cost_eth(self) -> float:
        """Gas cost in ETH."""
        return (self.gas_used * self.gas_price_gwei) / 1e9

    @property
    def is_confirmed(self) -> bool:
        return self.status == SettlementStatus.SETTLED

    @property
    def is_pending(self) -> bool:
        return self.status in [SettlementStatus.PENDING, SettlementStatus.CONFIRMING]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tx_hash": self.tx_hash,
            "network": self.network.value,
            "from_address": self.from_address,
            "to_address": self.to_address,
            "value": self.value,
            "gas_cost_eth": round(self.gas_cost_eth, 8),
            "confirmations": self.confirmations,
            "status": self.status.value,
            "block_number": self.block_number,
        }


@dataclass
class SettlementRecord:
    """Record of a trade settlement on-chain."""
    id: str = field(default_factory=_generate_id)
    trade_id: str = ""
    settlement_type: SettlementType = SettlementType.INSTANT
    network: BlockchainNetwork = BlockchainNetwork.ETHEREUM
    status: SettlementStatus = SettlementStatus.INITIATED
    amount: float = 0.0
    asset_symbol: str = ""
    sender: str = ""
    receiver: str = ""
    tx_hash: Optional[str] = None
    block_number: Optional[int] = None
    gas_cost: float = 0.0
    settlement_time_seconds: Optional[float] = None
    retries: int = 0
    error_message: Optional[str] = None
    initiated_at: datetime = field(default_factory=datetime.now)
    settled_at: Optional[datetime] = None

    @property
    def is_complete(self) -> bool:
        return self.status == SettlementStatus.SETTLED

    @property
    def is_failed(self) -> bool:
        return self.status in [SettlementStatus.FAILED, SettlementStatus.REVERTED]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "trade_id": self.trade_id,
            "settlement_type": self.settlement_type.value,
            "network": self.network.value,
            "status": self.status.value,
            "amount": self.amount,
            "asset_symbol": self.asset_symbol,
            "tx_hash": self.tx_hash,
            "gas_cost": self.gas_cost,
            "settlement_time_seconds": self.settlement_time_seconds,
            "retries": self.retries,
        }


@dataclass
class SmartContractInfo:
    """Smart contract deployment information."""
    address: str = ""
    network: BlockchainNetwork = BlockchainNetwork.ETHEREUM
    name: str = ""
    version: str = "1.0"
    abi_hash: str = ""
    deployer: str = ""
    deployed_at: Optional[int] = None  # Block number
    is_verified: bool = False
    is_active: bool = True

    def to_dict(self) -> dict:
        return {
            "address": self.address,
            "network": self.network.value,
            "name": self.name,
            "version": self.version,
            "is_verified": self.is_verified,
            "is_active": self.is_active,
        }


@dataclass
class TokenTransfer:
    """Token transfer details."""
    token_address: str = ""
    token_symbol: str = ""
    token_standard: TokenStandard = TokenStandard.ERC20
    from_address: str = ""
    to_address: str = ""
    amount: float = 0.0
    decimals: int = 18
    tx_hash: str = ""
    block_number: Optional[int] = None
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def raw_amount(self) -> int:
        """Amount in smallest unit (wei-equivalent)."""
        return int(self.amount * (10 ** self.decimals))

    def to_dict(self) -> dict:
        return {
            "token_symbol": self.token_symbol,
            "token_standard": self.token_standard.value,
            "from": self.from_address,
            "to": self.to_address,
            "amount": self.amount,
            "tx_hash": self.tx_hash,
        }


@dataclass
class AtomicSwap:
    """Atomic swap between two parties."""
    id: str = field(default_factory=_generate_id)
    initiator: str = ""
    participant: str = ""
    send_asset: str = ""
    send_amount: float = 0.0
    receive_asset: str = ""
    receive_amount: float = 0.0
    secret_hash: str = ""
    timelock: int = 3600  # seconds
    status: SettlementStatus = SettlementStatus.INITIATED
    network: BlockchainNetwork = BlockchainNetwork.ETHEREUM
    initiated_at: datetime = field(default_factory=datetime.now)

    @property
    def exchange_rate(self) -> float:
        if self.send_amount == 0:
            return 0.0
        return self.receive_amount / self.send_amount

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "initiator": self.initiator,
            "participant": self.participant,
            "send": f"{self.send_amount} {self.send_asset}",
            "receive": f"{self.receive_amount} {self.receive_asset}",
            "exchange_rate": round(self.exchange_rate, 6),
            "status": self.status.value,
            "timelock": self.timelock,
        }


@dataclass
class SettlementSummary:
    """Summary of settlement activity."""
    total_settlements: int = 0
    completed: int = 0
    pending: int = 0
    failed: int = 0
    total_volume: float = 0.0
    total_gas_cost: float = 0.0
    avg_settlement_time: float = 0.0
    success_rate: float = 0.0

    def to_dict(self) -> dict:
        return {
            "total_settlements": self.total_settlements,
            "completed": self.completed,
            "pending": self.pending,
            "failed": self.failed,
            "total_volume": round(self.total_volume, 2),
            "total_gas_cost": round(self.total_gas_cost, 8),
            "avg_settlement_time": round(self.avg_settlement_time, 1),
            "success_rate": round(self.success_rate, 2),
        }
