"""Tests for Blockchain Settlement Integration."""

import pytest
from src.blockchain.config import (
    BlockchainNetwork,
    SettlementStatus,
    TokenStandard,
    SettlementType,
    BlockchainConfig,
    NETWORK_CONFIGS,
    DEFAULT_BLOCKCHAIN_CONFIG,
)
from src.blockchain.models import (
    BlockchainTransaction,
    SettlementRecord,
    SmartContractInfo,
    TokenTransfer,
    AtomicSwap,
    SettlementSummary,
)
from src.blockchain.settlement import SettlementEngine
from src.blockchain.monitor import TransactionMonitor


# ── Config Tests ──


class TestBlockchainEnums:
    def test_networks(self):
        assert BlockchainNetwork.ETHEREUM.value == "ethereum"
        assert len(BlockchainNetwork) == 7

    def test_settlement_status(self):
        assert SettlementStatus.SETTLED.value == "settled"
        assert len(SettlementStatus) == 7

    def test_token_standards(self):
        assert TokenStandard.ERC20.value == "erc20"
        assert TokenStandard.SPL.value == "spl"

    def test_settlement_types(self):
        assert SettlementType.ATOMIC_SWAP.value == "atomic_swap"
        assert SettlementType.DVP.value == "dvp"

    def test_network_configs(self):
        eth = NETWORK_CONFIGS[BlockchainNetwork.ETHEREUM]
        assert eth["chain_id"] == 1
        assert eth["confirmations_required"] == 12

    def test_default_config(self):
        cfg = DEFAULT_BLOCKCHAIN_CONFIG
        assert cfg.enabled is True
        assert cfg.default_network == BlockchainNetwork.ETHEREUM
        assert cfg.max_retries == 3


# ── Model Tests ──


class TestBlockchainTransaction:
    def test_gas_cost_eth(self):
        tx = BlockchainTransaction(gas_used=21000, gas_price_gwei=30)
        assert abs(tx.gas_cost_eth - 0.00063) < 0.0001

    def test_is_confirmed(self):
        tx = BlockchainTransaction(status=SettlementStatus.SETTLED)
        assert tx.is_confirmed

    def test_is_pending(self):
        tx = BlockchainTransaction(status=SettlementStatus.PENDING)
        assert tx.is_pending

    def test_confirming_is_pending(self):
        tx = BlockchainTransaction(status=SettlementStatus.CONFIRMING)
        assert tx.is_pending

    def test_to_dict(self):
        tx = BlockchainTransaction(tx_hash="0xabc", value=1.5)
        d = tx.to_dict()
        assert d["tx_hash"] == "0xabc"
        assert d["value"] == 1.5


class TestSettlementRecord:
    def test_is_complete(self):
        r = SettlementRecord(status=SettlementStatus.SETTLED)
        assert r.is_complete

    def test_is_failed(self):
        r = SettlementRecord(status=SettlementStatus.FAILED)
        assert r.is_failed

    def test_reverted_is_failed(self):
        r = SettlementRecord(status=SettlementStatus.REVERTED)
        assert r.is_failed

    def test_to_dict(self):
        r = SettlementRecord(trade_id="T1", amount=1000, asset_symbol="USDC")
        d = r.to_dict()
        assert d["trade_id"] == "T1"
        assert d["amount"] == 1000


class TestSmartContractInfo:
    def test_to_dict(self):
        sc = SmartContractInfo(address="0x123", name="Settlement", is_verified=True)
        d = sc.to_dict()
        assert d["address"] == "0x123"
        assert d["is_verified"] is True


class TestTokenTransfer:
    def test_raw_amount(self):
        t = TokenTransfer(amount=1.5, decimals=18)
        assert t.raw_amount == 1500000000000000000

    def test_raw_amount_6_decimals(self):
        t = TokenTransfer(amount=100, decimals=6)
        assert t.raw_amount == 100000000

    def test_to_dict(self):
        t = TokenTransfer(token_symbol="USDC", amount=100)
        d = t.to_dict()
        assert d["token_symbol"] == "USDC"


class TestAtomicSwap:
    def test_exchange_rate(self):
        swap = AtomicSwap(send_amount=1, receive_amount=50000, send_asset="BTC", receive_asset="USDC")
        assert swap.exchange_rate == 50000

    def test_exchange_rate_zero(self):
        swap = AtomicSwap(send_amount=0)
        assert swap.exchange_rate == 0.0

    def test_to_dict(self):
        swap = AtomicSwap(initiator="0xA", participant="0xB", send_asset="ETH", send_amount=10)
        d = swap.to_dict()
        assert d["initiator"] == "0xA"


class TestSettlementSummary:
    def test_to_dict(self):
        s = SettlementSummary(total_settlements=10, completed=8, pending=1, failed=1, success_rate=80)
        d = s.to_dict()
        assert d["success_rate"] == 80


# ── Settlement Engine Tests ──


class TestSettlementEngine:
    def setup_method(self):
        self.engine = SettlementEngine()

    def test_initiate_settlement(self):
        record = self.engine.initiate_settlement(
            trade_id="T1", amount=1000, asset_symbol="USDC",
            sender="0xA", receiver="0xB",
        )
        assert record.status == SettlementStatus.INITIATED
        assert record.amount == 1000

    def test_submit_settlement(self):
        record = self.engine.initiate_settlement("T1", 1000, "USDC", "0xA", "0xB")
        updated = self.engine.submit_settlement(record.id)
        assert updated.status == SettlementStatus.PENDING

    def test_submit_non_initiated_raises(self):
        record = self.engine.initiate_settlement("T1", 1000, "USDC", "0xA", "0xB")
        self.engine.submit_settlement(record.id)
        with pytest.raises(ValueError, match="not in INITIATED"):
            self.engine.submit_settlement(record.id)

    def test_confirm_settlement(self):
        record = self.engine.initiate_settlement("T1", 1000, "USDC", "0xA", "0xB")
        confirmed = self.engine.confirm_settlement(record.id, tx_hash="0xabc", block_number=100, gas_cost=0.001)
        assert confirmed.is_complete
        assert confirmed.tx_hash == "0xabc"
        assert confirmed.gas_cost == 0.001
        assert confirmed.settlement_time_seconds is not None

    def test_fail_settlement(self):
        record = self.engine.initiate_settlement("T1", 1000, "USDC", "0xA", "0xB")
        failed = self.engine.fail_settlement(record.id, "out of gas")
        assert failed.is_failed
        assert failed.error_message == "out of gas"
        assert failed.retries == 1

    def test_retry_settlement(self):
        record = self.engine.initiate_settlement("T1", 1000, "USDC", "0xA", "0xB")
        self.engine.fail_settlement(record.id, "error")
        retried = self.engine.retry_settlement(record.id)
        assert retried.status == SettlementStatus.PENDING
        assert retried.error_message is None

    def test_retry_max_exceeded(self):
        config = BlockchainConfig(max_retries=1)
        engine = SettlementEngine(config)
        record = engine.initiate_settlement("T1", 1000, "USDC", "0xA", "0xB")
        engine.fail_settlement(record.id, "error")
        with pytest.raises(ValueError, match="exceeded max retries"):
            engine.retry_settlement(record.id)

    def test_retry_non_failed_raises(self):
        record = self.engine.initiate_settlement("T1", 1000, "USDC", "0xA", "0xB")
        with pytest.raises(ValueError, match="not in a failed state"):
            self.engine.retry_settlement(record.id)

    def test_get_settlement(self):
        record = self.engine.initiate_settlement("T1", 1000, "USDC", "0xA", "0xB")
        retrieved = self.engine.get_settlement(record.id)
        assert retrieved is not None
        assert retrieved.trade_id == "T1"

    def test_get_settlement_not_found(self):
        assert self.engine.get_settlement("nonexistent") is None

    def test_get_by_status(self):
        self.engine.initiate_settlement("T1", 100, "USDC", "0xA", "0xB")
        self.engine.initiate_settlement("T2", 200, "USDC", "0xA", "0xB")
        initiated = self.engine.get_settlements_by_status(SettlementStatus.INITIATED)
        assert len(initiated) == 2

    def test_atomic_swap(self):
        swap = self.engine.initiate_atomic_swap(
            initiator="0xA", participant="0xB",
            send_asset="ETH", send_amount=1,
            receive_asset="USDC", receive_amount=3000,
            secret_hash="abc123",
        )
        assert swap.exchange_rate == 3000

    def test_complete_swap(self):
        swap = self.engine.initiate_atomic_swap(
            "0xA", "0xB", "ETH", 1, "USDC", 3000,
        )
        completed = self.engine.complete_swap(swap.id)
        assert completed.status == SettlementStatus.SETTLED

    def test_summary_empty(self):
        summary = self.engine.get_summary()
        assert summary.total_settlements == 0

    def test_summary_with_data(self):
        r1 = self.engine.initiate_settlement("T1", 1000, "USDC", "0xA", "0xB")
        r2 = self.engine.initiate_settlement("T2", 2000, "USDC", "0xC", "0xD")
        self.engine.confirm_settlement(r1.id, gas_cost=0.001)
        self.engine.fail_settlement(r2.id, "error")
        summary = self.engine.get_summary()
        assert summary.total_settlements == 2
        assert summary.completed == 1
        assert summary.failed == 1
        assert summary.success_rate == 50.0

    def test_estimate_gas(self):
        estimate = self.engine.estimate_gas(BlockchainNetwork.ETHEREUM)
        assert estimate["network"] == "ethereum"
        assert estimate["estimated_gas"] == 65000
        assert estimate["confirmations_required"] == 12

    def test_settlement_not_found_raises(self):
        with pytest.raises(ValueError):
            self.engine.submit_settlement("nonexistent")

    def test_network_override(self):
        record = self.engine.initiate_settlement(
            "T1", 1000, "USDC", "0xA", "0xB",
            network=BlockchainNetwork.POLYGON,
        )
        assert record.network == BlockchainNetwork.POLYGON


# ── Monitor Tests ──


class TestTransactionMonitor:
    def setup_method(self):
        self.monitor = TransactionMonitor()

    def test_watch_transaction(self):
        tx = BlockchainTransaction(tx_hash="0xabc")
        self.monitor.watch(tx)
        assert self.monitor.get_watched_count() == 1

    def test_update_confirmations(self):
        tx = BlockchainTransaction(tx_hash="0xabc")
        self.monitor.watch(tx)
        updated = self.monitor.update_confirmations(tx.id, 5, block_number=100)
        assert updated.confirmations == 5
        assert updated.status == SettlementStatus.CONFIRMING

    def test_fully_confirmed(self):
        tx = BlockchainTransaction(tx_hash="0xabc", network=BlockchainNetwork.ETHEREUM)
        self.monitor.watch(tx)
        updated = self.monitor.update_confirmations(tx.id, 12)
        assert updated.status == SettlementStatus.SETTLED

    def test_update_not_watched_raises(self):
        with pytest.raises(ValueError):
            self.monitor.update_confirmations("nonexistent", 5)

    def test_mark_reverted(self):
        tx = BlockchainTransaction(tx_hash="0xabc")
        self.monitor.watch(tx)
        reverted = self.monitor.mark_reverted(tx.id, "insufficient balance")
        assert reverted.status == SettlementStatus.REVERTED

    def test_revert_creates_alert(self):
        tx = BlockchainTransaction(tx_hash="0xabc")
        self.monitor.watch(tx)
        self.monitor.mark_reverted(tx.id, "error")
        alerts = self.monitor.get_alerts()
        assert len(alerts) == 1
        assert alerts[0]["type"] == "revert"

    def test_get_pending(self):
        tx1 = BlockchainTransaction(status=SettlementStatus.PENDING)
        tx2 = BlockchainTransaction(status=SettlementStatus.SETTLED)
        self.monitor.watch(tx1)
        self.monitor.watch(tx2)
        pending = self.monitor.get_pending()
        assert len(pending) == 1

    def test_get_confirmed(self):
        tx1 = BlockchainTransaction(status=SettlementStatus.PENDING)
        tx2 = BlockchainTransaction(status=SettlementStatus.SETTLED)
        self.monitor.watch(tx1)
        self.monitor.watch(tx2)
        confirmed = self.monitor.get_confirmed()
        assert len(confirmed) == 1

    def test_clear_alerts(self):
        tx = BlockchainTransaction()
        self.monitor.watch(tx)
        self.monitor.mark_reverted(tx.id, "err")
        self.monitor.clear_alerts()
        assert len(self.monitor.get_alerts()) == 0

    def test_unwatch(self):
        tx = BlockchainTransaction()
        self.monitor.watch(tx)
        assert self.monitor.unwatch(tx.id) is True
        assert self.monitor.get_watched_count() == 0

    def test_unwatch_not_found(self):
        assert self.monitor.unwatch("nonexistent") is False


# ── Module Import Test ──


class TestBlockchainModuleImports:
    def test_top_level_imports(self):
        from src.blockchain import (
            SettlementEngine,
            TransactionMonitor,
            BlockchainNetwork,
            SettlementRecord,
        )
        assert SettlementEngine is not None
        assert TransactionMonitor is not None
