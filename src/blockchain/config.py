"""Blockchain Settlement Configuration."""

from dataclasses import dataclass
from enum import Enum


class BlockchainNetwork(Enum):
    """Supported blockchain networks."""
    ETHEREUM = "ethereum"
    POLYGON = "polygon"
    ARBITRUM = "arbitrum"
    OPTIMISM = "optimism"
    BASE = "base"
    SOLANA = "solana"
    AVALANCHE = "avalanche"


class SettlementStatus(Enum):
    """Settlement lifecycle status."""
    INITIATED = "initiated"
    PENDING = "pending"
    CONFIRMING = "confirming"
    SETTLED = "settled"
    FAILED = "failed"
    REVERTED = "reverted"
    CANCELLED = "cancelled"


class TokenStandard(Enum):
    """Token standards."""
    ERC20 = "erc20"
    ERC721 = "erc721"
    ERC1155 = "erc1155"
    SPL = "spl"
    NATIVE = "native"


class SettlementType(Enum):
    """Types of settlement."""
    INSTANT = "instant"
    DEFERRED = "deferred"
    ATOMIC_SWAP = "atomic_swap"
    DVP = "dvp"  # Delivery vs Payment
    BATCH = "batch"


# Network configurations
NETWORK_CONFIGS = {
    BlockchainNetwork.ETHEREUM: {
        "chain_id": 1,
        "block_time_seconds": 12,
        "confirmations_required": 12,
        "native_token": "ETH",
    },
    BlockchainNetwork.POLYGON: {
        "chain_id": 137,
        "block_time_seconds": 2,
        "confirmations_required": 64,
        "native_token": "MATIC",
    },
    BlockchainNetwork.ARBITRUM: {
        "chain_id": 42161,
        "block_time_seconds": 0.3,
        "confirmations_required": 1,
        "native_token": "ETH",
    },
    BlockchainNetwork.SOLANA: {
        "chain_id": 0,
        "block_time_seconds": 0.4,
        "confirmations_required": 32,
        "native_token": "SOL",
    },
}


@dataclass
class BlockchainConfig:
    """Blockchain settlement configuration."""
    enabled: bool = True
    default_network: BlockchainNetwork = BlockchainNetwork.ETHEREUM
    max_gas_price_gwei: float = 100.0
    settlement_timeout_seconds: int = 3600
    auto_retry_failed: bool = True
    max_retries: int = 3
    batch_settlement_threshold: int = 10
    require_confirmation: bool = True


DEFAULT_BLOCKCHAIN_CONFIG = BlockchainConfig()
