"""Tests for PRD-118: Data Archival & GDPR Compliance."""

from datetime import datetime, timedelta

import pytest

from src.archival.config import (
    StorageTier,
    ArchivalFormat,
    GDPRRequestType,
    GDPRRequestStatus,
    ArchivalConfig,
)
from src.archival.engine import ArchivalJob, ArchivalEngine
from src.archival.retention import RetentionPolicy, RetentionManager
from src.archival.gdpr import GDPRRequest, GDPRManager
from src.archival.lifecycle import TierStats, DataLifecycleManager


# ── Config Tests ──────────────────────────────────────────────────────


class TestArchivalConfig:
    def test_storage_tier_enum(self):
        assert len(StorageTier) == 5
        assert StorageTier.HOT.value == "hot"
        assert StorageTier.WARM.value == "warm"
        assert StorageTier.COLD.value == "cold"
        assert StorageTier.ARCHIVE.value == "archive"
        assert StorageTier.DELETED.value == "deleted"

    def test_archival_format_enum(self):
        assert len(ArchivalFormat) == 3
        assert ArchivalFormat.PARQUET.value == "parquet"
        assert ArchivalFormat.CSV.value == "csv"
        assert ArchivalFormat.JSON_LINES.value == "json_lines"

    def test_gdpr_request_type_enum(self):
        assert len(GDPRRequestType) == 4
        assert GDPRRequestType.DELETION.value == "deletion"
        assert GDPRRequestType.EXPORT.value == "export"
        assert GDPRRequestType.RECTIFICATION.value == "rectification"
        assert GDPRRequestType.ACCESS.value == "access"

    def test_gdpr_request_status_enum(self):
        assert len(GDPRRequestStatus) == 5
        assert GDPRRequestStatus.PENDING.value == "pending"
        assert GDPRRequestStatus.COMPLETED.value == "completed"
        assert GDPRRequestStatus.REJECTED.value == "rejected"

    def test_default_config(self):
        cfg = ArchivalConfig()
        assert cfg.default_format == ArchivalFormat.PARQUET
        assert cfg.compression == "gzip"
        assert cfg.storage_path == "archive/"
        assert cfg.max_batch_size == 100_000
        assert cfg.enable_gdpr is True
        assert cfg.deletion_audit is True
        assert cfg.hot_retention_days == 90
        assert cfg.warm_retention_days == 365
        assert cfg.cold_retention_days == 2555

    def test_custom_config(self):
        cfg = ArchivalConfig(
            default_format=ArchivalFormat.CSV,
            compression="snappy",
            max_batch_size=50_000,
            hot_retention_days=30,
        )
        assert cfg.default_format == ArchivalFormat.CSV
        assert cfg.compression == "snappy"
        assert cfg.max_batch_size == 50_000
        assert cfg.hot_retention_days == 30


# ── Archival Engine Tests ─────────────────────────────────────────────


class TestArchivalEngine:
    def setup_method(self):
        self.engine = ArchivalEngine()

    def test_create_job(self):
        start = datetime(2024, 1, 1)
        end = datetime(2024, 3, 31)
        job = self.engine.create_job("price_bars", start, end)
        assert job.table_name == "price_bars"
        assert job.status == "pending"
        assert job.date_range_start == start
        assert job.date_range_end == end
        assert job.format == ArchivalFormat.PARQUET
        assert job.records_archived == 0

    def test_create_job_custom_format(self):
        start = datetime(2024, 1, 1)
        end = datetime(2024, 6, 30)
        job = self.engine.create_job("trade_orders", start, end, format=ArchivalFormat.CSV)
        assert job.format == ArchivalFormat.CSV

    def test_execute_job(self):
        start = datetime(2024, 1, 1)
        end = datetime(2024, 3, 31)
        job = self.engine.create_job("price_bars", start, end)
        result = self.engine.execute_job(job.job_id)
        assert result.status == "completed"
        assert result.records_archived > 0
        assert result.bytes_written > 0
        assert result.storage_path != ""
        assert result.started_at is not None
        assert result.completed_at is not None

    def test_execute_nonexistent_job(self):
        with pytest.raises(ValueError, match="not found"):
            self.engine.execute_job("nonexistent-id")

    def test_get_job(self):
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 31)
        job = self.engine.create_job("financials", start, end)
        retrieved = self.engine.get_job(job.job_id)
        assert retrieved is not None
        assert retrieved.job_id == job.job_id

    def test_get_job_not_found(self):
        assert self.engine.get_job("nonexistent") is None

    def test_list_jobs_all(self):
        self.engine.create_job("t1", datetime(2024, 1, 1), datetime(2024, 2, 1))
        self.engine.create_job("t2", datetime(2024, 1, 1), datetime(2024, 2, 1))
        assert len(self.engine.list_jobs()) == 2

    def test_list_jobs_filter_table(self):
        self.engine.create_job("t1", datetime(2024, 1, 1), datetime(2024, 2, 1))
        self.engine.create_job("t2", datetime(2024, 1, 1), datetime(2024, 2, 1))
        assert len(self.engine.list_jobs(table_name="t1")) == 1

    def test_list_jobs_filter_status(self):
        job = self.engine.create_job("t1", datetime(2024, 1, 1), datetime(2024, 2, 1))
        self.engine.execute_job(job.job_id)
        self.engine.create_job("t2", datetime(2024, 1, 1), datetime(2024, 2, 1))
        assert len(self.engine.list_jobs(status="completed")) == 1
        assert len(self.engine.list_jobs(status="pending")) == 1

    def test_restore_from_archive(self):
        job = self.engine.create_job("t1", datetime(2024, 1, 1), datetime(2024, 3, 31))
        self.engine.execute_job(job.job_id)
        result = self.engine.restore_from_archive(job.job_id)
        assert result["status"] == "restored"
        assert result["records"] > 0
        assert result["table_name"] == "t1"

    def test_restore_pending_job_fails(self):
        job = self.engine.create_job("t1", datetime(2024, 1, 1), datetime(2024, 3, 31))
        with pytest.raises(ValueError, match="not in completed state"):
            self.engine.restore_from_archive(job.job_id)

    def test_get_catalog(self):
        job = self.engine.create_job("t1", datetime(2024, 1, 1), datetime(2024, 3, 31))
        self.engine.execute_job(job.job_id)
        catalog = self.engine.get_catalog()
        assert len(catalog) == 1

    def test_get_storage_stats(self):
        job = self.engine.create_job("t1", datetime(2024, 1, 1), datetime(2024, 6, 30))
        self.engine.execute_job(job.job_id)
        stats = self.engine.get_storage_stats()
        assert stats["total_jobs"] == 1
        assert stats["completed_jobs"] == 1
        assert stats["total_bytes"] > 0
        assert stats["total_records"] > 0

    def test_reset(self):
        self.engine.create_job("t1", datetime(2024, 1, 1), datetime(2024, 2, 1))
        self.engine.reset()
        assert len(self.engine.list_jobs()) == 0
        assert self.engine.get_storage_stats()["total_jobs"] == 0


# ── Retention Manager Tests ───────────────────────────────────────────


class TestRetentionManager:
    def setup_method(self):
        self.mgr = RetentionManager()

    def test_add_policy(self):
        policy = self.mgr.add_policy("price_bars", hot_days=30, warm_days=180, cold_days=730)
        assert policy.table_name == "price_bars"
        assert policy.hot_days == 30
        assert policy.warm_days == 180
        assert policy.cold_days == 730

    def test_add_policy_with_delete(self):
        policy = self.mgr.add_policy("temp_data", delete_after=400, description="Temporary")
        assert policy.delete_after_days == 400
        assert policy.description == "Temporary"

    def test_get_policy(self):
        self.mgr.add_policy("price_bars")
        assert self.mgr.get_policy("price_bars") is not None
        assert self.mgr.get_policy("nonexistent") is None

    def test_evaluate_table_hot(self):
        self.mgr.add_policy("t1", hot_days=90, warm_days=365, cold_days=2555)
        result = self.mgr.evaluate_table("t1", 30)
        assert result["current_tier"] == "hot"
        assert result["next_transition"]["to_tier"] == "warm"

    def test_evaluate_table_warm(self):
        self.mgr.add_policy("t1", hot_days=90, warm_days=365, cold_days=2555)
        result = self.mgr.evaluate_table("t1", 200)
        assert result["current_tier"] == "warm"

    def test_evaluate_table_cold(self):
        self.mgr.add_policy("t1", hot_days=90, warm_days=365, cold_days=2555)
        result = self.mgr.evaluate_table("t1", 500)
        assert result["current_tier"] == "cold"

    def test_evaluate_table_archive(self):
        self.mgr.add_policy("t1", hot_days=90, warm_days=365, cold_days=2555)
        result = self.mgr.evaluate_table("t1", 3000)
        assert result["current_tier"] == "archive"

    def test_evaluate_table_deleted(self):
        self.mgr.add_policy("t1", hot_days=30, warm_days=90, cold_days=365, delete_after=400)
        result = self.mgr.evaluate_table("t1", 450)
        assert result["current_tier"] == "deleted"
        assert result["action_needed"] == "delete"

    def test_evaluate_no_policy(self):
        result = self.mgr.evaluate_table("unknown", 100)
        assert result["action_needed"] == "no_policy"

    def test_set_legal_hold(self):
        self.mgr.add_policy("t1")
        assert self.mgr.set_legal_hold("t1", "Legal investigation") is True
        policy = self.mgr.get_policy("t1")
        assert policy.legal_hold is True

    def test_set_legal_hold_no_policy(self):
        assert self.mgr.set_legal_hold("unknown", "reason") is False

    def test_legal_hold_prevents_deletion(self):
        self.mgr.add_policy("t1", hot_days=30, warm_days=90, cold_days=365, delete_after=400)
        self.mgr.set_legal_hold("t1", "investigation")
        result = self.mgr.evaluate_table("t1", 500)
        # Legal hold should force cold tier instead of deleted
        assert result["current_tier"] == "cold"

    def test_release_legal_hold(self):
        self.mgr.add_policy("t1")
        self.mgr.set_legal_hold("t1", "reason")
        assert self.mgr.release_legal_hold("t1") is True
        assert self.mgr.get_policy("t1").legal_hold is False

    def test_release_no_hold(self):
        self.mgr.add_policy("t1")
        assert self.mgr.release_legal_hold("t1") is False

    def test_get_policies(self):
        self.mgr.add_policy("t1")
        self.mgr.add_policy("t2")
        assert len(self.mgr.get_policies()) == 2

    def test_get_holds(self):
        self.mgr.add_policy("t1")
        self.mgr.add_policy("t2")
        self.mgr.set_legal_hold("t1", "reason")
        holds = self.mgr.get_holds()
        assert len(holds) == 1
        assert "t1" in holds

    def test_get_expiring_data(self):
        self.mgr.add_policy("t1", delete_after=20)
        self.mgr.add_policy("t2", delete_after=500)
        expiring = self.mgr.get_expiring_data(within_days=30)
        assert len(expiring) == 1
        assert expiring[0]["table_name"] == "t1"

    def test_get_expiring_data_legal_hold_excluded(self):
        self.mgr.add_policy("t1", delete_after=20)
        self.mgr.set_legal_hold("t1", "hold")
        expiring = self.mgr.get_expiring_data(within_days=30)
        assert len(expiring) == 0

    def test_reset(self):
        self.mgr.add_policy("t1")
        self.mgr.set_legal_hold("t1", "reason")
        self.mgr.reset()
        assert len(self.mgr.get_policies()) == 0
        assert len(self.mgr.get_holds()) == 0


# ── GDPR Manager Tests ───────────────────────────────────────────────


class TestGDPRManager:
    def setup_method(self):
        self.mgr = GDPRManager()

    def test_submit_request(self):
        req = self.mgr.submit_request("user-1", GDPRRequestType.ACCESS)
        assert req.user_id == "user-1"
        assert req.request_type == GDPRRequestType.ACCESS
        assert req.status == GDPRRequestStatus.PENDING
        assert len(req.tables_affected) > 0

    def test_submit_request_custom_tables(self):
        req = self.mgr.submit_request(
            "user-1", GDPRRequestType.DELETION,
            tables=["users", "trade_orders"],
            notes="Customer request",
        )
        assert req.tables_affected == ["users", "trade_orders"]
        assert req.notes == "Customer request"

    def test_process_request(self):
        req = self.mgr.submit_request("user-1", GDPRRequestType.EXPORT)
        result = self.mgr.process_request(req.request_id)
        assert result.status == GDPRRequestStatus.COMPLETED
        assert result.records_affected > 0
        assert result.completed_at is not None
        assert result.audit_proof is not None

    def test_process_deletion_creates_log(self):
        req = self.mgr.submit_request("user-1", GDPRRequestType.DELETION)
        self.mgr.process_request(req.request_id)
        log = self.mgr.get_deletion_log()
        assert len(log) == 1
        assert log[0]["user_id"] == "user-1"
        assert log[0]["audit_proof"] is not None

    def test_process_nonexistent_request(self):
        with pytest.raises(ValueError, match="not found"):
            self.mgr.process_request("nonexistent")

    def test_process_already_completed(self):
        req = self.mgr.submit_request("user-1", GDPRRequestType.ACCESS)
        self.mgr.process_request(req.request_id)
        with pytest.raises(ValueError, match="cannot be processed"):
            self.mgr.process_request(req.request_id)

    def test_get_request(self):
        req = self.mgr.submit_request("user-1", GDPRRequestType.ACCESS)
        retrieved = self.mgr.get_request(req.request_id)
        assert retrieved is not None
        assert retrieved.request_id == req.request_id

    def test_get_request_not_found(self):
        assert self.mgr.get_request("nonexistent") is None

    def test_list_requests_all(self):
        self.mgr.submit_request("user-1", GDPRRequestType.ACCESS)
        self.mgr.submit_request("user-2", GDPRRequestType.DELETION)
        assert len(self.mgr.list_requests()) == 2

    def test_list_requests_filter_user(self):
        self.mgr.submit_request("user-1", GDPRRequestType.ACCESS)
        self.mgr.submit_request("user-2", GDPRRequestType.DELETION)
        assert len(self.mgr.list_requests(user_id="user-1")) == 1

    def test_list_requests_filter_status(self):
        req = self.mgr.submit_request("user-1", GDPRRequestType.ACCESS)
        self.mgr.process_request(req.request_id)
        self.mgr.submit_request("user-2", GDPRRequestType.DELETION)
        assert len(self.mgr.list_requests(status=GDPRRequestStatus.COMPLETED)) == 1
        assert len(self.mgr.list_requests(status=GDPRRequestStatus.PENDING)) == 1

    def test_list_requests_filter_type(self):
        self.mgr.submit_request("user-1", GDPRRequestType.ACCESS)
        self.mgr.submit_request("user-2", GDPRRequestType.DELETION)
        result = self.mgr.list_requests(request_type=GDPRRequestType.DELETION)
        assert len(result) == 1
        assert result[0].user_id == "user-2"

    def test_generate_export(self):
        export = self.mgr.generate_export("user-1")
        assert export["user_id"] == "user-1"
        assert export["total_records"] > 0
        assert len(export["tables"]) > 0
        assert export["format"] == "json"

    def test_generate_compliance_report_empty(self):
        report = self.mgr.generate_compliance_report()
        assert report["total_requests"] == 0
        assert report["deletion_count"] == 0

    def test_generate_compliance_report_with_data(self):
        req1 = self.mgr.submit_request("user-1", GDPRRequestType.ACCESS)
        req2 = self.mgr.submit_request("user-2", GDPRRequestType.DELETION)
        self.mgr.process_request(req1.request_id)
        self.mgr.process_request(req2.request_id)
        report = self.mgr.generate_compliance_report()
        assert report["total_requests"] == 2
        assert report["by_type"]["access"] == 1
        assert report["by_type"]["deletion"] == 1
        assert report["by_status"]["completed"] == 2
        assert report["deletion_count"] == 1
        assert report["total_records_affected"] > 0

    def test_get_deletion_log_by_user(self):
        req1 = self.mgr.submit_request("user-1", GDPRRequestType.DELETION)
        req2 = self.mgr.submit_request("user-2", GDPRRequestType.DELETION)
        self.mgr.process_request(req1.request_id)
        self.mgr.process_request(req2.request_id)
        log = self.mgr.get_deletion_log(user_id="user-1")
        assert len(log) == 1
        assert log[0]["user_id"] == "user-1"

    def test_reject_request(self):
        req = self.mgr.submit_request("user-1", GDPRRequestType.RECTIFICATION)
        assert self.mgr.reject_request(req.request_id, "Insufficient verification") is True
        updated = self.mgr.get_request(req.request_id)
        assert updated.status == GDPRRequestStatus.REJECTED
        assert "Insufficient verification" in updated.notes

    def test_reject_nonexistent(self):
        assert self.mgr.reject_request("nonexistent", "reason") is False

    def test_reject_already_completed(self):
        req = self.mgr.submit_request("user-1", GDPRRequestType.ACCESS)
        self.mgr.process_request(req.request_id)
        assert self.mgr.reject_request(req.request_id, "reason") is False

    def test_reset(self):
        req = self.mgr.submit_request("user-1", GDPRRequestType.DELETION)
        self.mgr.process_request(req.request_id)
        self.mgr.reset()
        assert len(self.mgr.list_requests()) == 0
        assert len(self.mgr.get_deletion_log()) == 0


# ── Data Lifecycle Manager Tests ──────────────────────────────────────


class TestDataLifecycleManager:
    def setup_method(self):
        self.mgr = DataLifecycleManager()

    def test_record_tier_stats(self):
        self.mgr.record_tier_stats(StorageTier.HOT, 10000, 5_000_000, 5)
        stats = self.mgr.get_tier_stats()
        assert StorageTier.HOT in stats
        assert stats[StorageTier.HOT].record_count == 10000
        assert stats[StorageTier.HOT].bytes_used == 5_000_000

    def test_record_tier_stats_custom_cost(self):
        self.mgr.record_tier_stats(StorageTier.WARM, 5000, 2_000_000, 3, cost_per_gb=0.015)
        stats = self.mgr.get_tier_stats()
        assert stats[StorageTier.WARM].cost_per_gb_month == 0.015

    def test_get_total_cost(self):
        self.mgr.record_tier_stats(StorageTier.HOT, 1000, 1024 ** 3, 1)  # 1 GB
        cost = self.mgr.get_total_cost()
        assert cost > 0
        assert cost == pytest.approx(0.023, rel=0.01)

    def test_get_cost_by_tier(self):
        self.mgr.record_tier_stats(StorageTier.HOT, 1000, 1024 ** 3, 1)
        self.mgr.record_tier_stats(StorageTier.COLD, 500, 1024 ** 3, 1)
        costs = self.mgr.get_cost_by_tier()
        assert "hot" in costs
        assert "cold" in costs
        assert costs["hot"]["monthly_cost"] > costs["cold"]["monthly_cost"]

    def test_transition_data(self):
        self.mgr.record_tier_stats(StorageTier.HOT, 10000, 5_000_000, 5)
        result = self.mgr.transition_data("price_bars", StorageTier.HOT, StorageTier.WARM, 3000, 1_500_000)
        assert result["from_tier"] == "hot"
        assert result["to_tier"] == "warm"
        assert result["records"] == 3000
        # HOT stats should decrease
        stats = self.mgr.get_tier_stats()
        assert stats[StorageTier.HOT].record_count == 7000
        assert stats[StorageTier.WARM].record_count == 3000

    def test_transition_creates_tier_if_needed(self):
        result = self.mgr.transition_data("t1", StorageTier.HOT, StorageTier.COLD, 100, 50_000)
        stats = self.mgr.get_tier_stats()
        assert StorageTier.COLD in stats
        assert stats[StorageTier.COLD].record_count == 100

    def test_get_transitions(self):
        self.mgr.transition_data("t1", StorageTier.HOT, StorageTier.WARM, 100, 50_000)
        self.mgr.transition_data("t2", StorageTier.WARM, StorageTier.COLD, 200, 100_000)
        assert len(self.mgr.get_transitions()) == 2

    def test_get_transitions_filter(self):
        self.mgr.transition_data("t1", StorageTier.HOT, StorageTier.WARM, 100, 50_000)
        self.mgr.transition_data("t2", StorageTier.WARM, StorageTier.COLD, 200, 100_000)
        assert len(self.mgr.get_transitions(table_name="t1")) == 1

    def test_get_optimization_recommendations_no_data(self):
        recs = self.mgr.get_optimization_recommendations()
        assert len(recs) == 1
        assert recs[0]["recommendation"] == "No optimization needed"

    def test_get_optimization_recommendations_large_hot(self):
        self.mgr.record_tier_stats(StorageTier.HOT, 1_000_000, 200 * (1024 ** 3), 10)
        recs = self.mgr.get_optimization_recommendations()
        assert any("HOT to WARM" in r["recommendation"] for r in recs)
        assert any(r["savings"] > 0 for r in recs)

    def test_get_storage_summary(self):
        self.mgr.record_tier_stats(StorageTier.HOT, 10000, 5_000_000, 5)
        self.mgr.record_tier_stats(StorageTier.WARM, 5000, 2_000_000, 3)
        summary = self.mgr.get_storage_summary()
        assert summary["total_bytes"] == 7_000_000
        assert summary["total_records"] == 15000
        assert summary["tier_count"] == 2
        assert "hot" in summary["tier_breakdown"]
        assert "warm" in summary["tier_breakdown"]

    def test_get_storage_summary_empty(self):
        summary = self.mgr.get_storage_summary()
        assert summary["total_bytes"] == 0
        assert summary["total_records"] == 0
        assert summary["tier_count"] == 0

    def test_reset(self):
        self.mgr.record_tier_stats(StorageTier.HOT, 1000, 100_000, 1)
        self.mgr.transition_data("t1", StorageTier.HOT, StorageTier.WARM, 100, 10_000)
        self.mgr.reset()
        assert len(self.mgr.get_tier_stats()) == 0
        assert len(self.mgr.get_transitions()) == 0
