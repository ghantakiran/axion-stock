"""Tests for PRD-116: Disaster Recovery & Automated Backup System."""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone

from src.backup import (
    BackupType,
    BackupStatus,
    StorageBackend,
    StorageTier,
    RecoveryStatus,
    ReplicaStatus,
    DataSource,
    RetentionPolicy,
    BackupConfig,
    BackupArtifact,
    BackupJob,
    BackupEngine,
    RecoveryStep,
    RecoveryPlan,
    RecoveryResult,
    RecoveryManager,
    Replica,
    ReplicationEvent,
    ReplicationMonitor,
    RecoveryDrill,
    SLAReport,
    BackupMonitor,
)


class TestBackupConfig:
    """Tests for backup configuration."""

    def setup_method(self):
        self.config = BackupConfig()

    def test_default_config(self):
        assert self.config.storage_backend == StorageBackend.LOCAL
        assert self.config.compression_enabled is True
        assert self.config.encryption_enabled is True
        assert self.config.max_concurrent_jobs == 2

    def test_retention_policy_defaults(self):
        policy = self.config.retention_policy
        assert policy.hot_days == 7
        assert policy.warm_days == 30
        assert policy.cold_days == 90

    def test_custom_config(self):
        config = BackupConfig(
            storage_backend=StorageBackend.S3,
            compression_enabled=False,
            rto_target_minutes=30,
        )
        assert config.storage_backend == StorageBackend.S3
        assert config.compression_enabled is False
        assert config.rto_target_minutes == 30

    def test_default_sources(self):
        assert DataSource.POSTGRESQL in self.config.default_sources
        assert DataSource.REDIS in self.config.default_sources

    def test_enums(self):
        assert BackupType.FULL.value == "full"
        assert BackupStatus.RUNNING.value == "running"
        assert StorageBackend.GLACIER.value == "glacier"
        assert StorageTier.COLD.value == "cold"
        assert RecoveryStatus.VALIDATING.value == "validating"
        assert ReplicaStatus.LAGGING.value == "lagging"
        assert DataSource.TIMESCALEDB.value == "timescaledb"

    def test_retention_policy_custom(self):
        policy = RetentionPolicy(hot_days=3, warm_days=14, cold_days=60)
        assert policy.hot_days == 3
        assert policy.max_hot_count == 7  # default


class TestBackupEngine:
    """Tests for the backup engine."""

    def setup_method(self):
        self.config = BackupConfig()
        self.engine = BackupEngine(self.config)

    def test_create_full_backup(self):
        job = self.engine.create_backup(BackupType.FULL)
        assert job.status == BackupStatus.COMPLETED
        assert job.backup_type == BackupType.FULL
        assert len(job.artifacts) == 2  # postgresql + redis
        assert job.total_size_bytes > 0
        assert job.duration_seconds >= 0

    def test_create_incremental_backup(self):
        job = self.engine.create_backup(BackupType.INCREMENTAL)
        assert job.status == BackupStatus.COMPLETED
        assert job.backup_type == BackupType.INCREMENTAL

    def test_create_snapshot_backup(self):
        job = self.engine.create_backup(BackupType.SNAPSHOT)
        assert job.status == BackupStatus.COMPLETED

    def test_backup_with_custom_sources(self):
        sources = [DataSource.POSTGRESQL, DataSource.FILESYSTEM]
        job = self.engine.create_backup(sources=sources)
        assert len(job.artifacts) == 2
        source_types = {a.source for a in job.artifacts}
        assert DataSource.POSTGRESQL in source_types
        assert DataSource.FILESYSTEM in source_types

    def test_backup_artifact_checksums(self):
        job = self.engine.create_backup()
        for artifact in job.artifacts:
            assert len(artifact.checksum) == 64  # sha256 hex
            assert artifact.compressed is True
            assert artifact.encrypted is True

    def test_backup_without_compression(self):
        config = BackupConfig(compression_enabled=False)
        engine = BackupEngine(config)
        job = engine.create_backup()
        for artifact in job.artifacts:
            assert artifact.compressed is False

    def test_backup_without_encryption(self):
        config = BackupConfig(encryption_enabled=False)
        engine = BackupEngine(config)
        job = engine.create_backup()
        for artifact in job.artifacts:
            assert artifact.encrypted is False

    def test_max_concurrent_jobs(self):
        config = BackupConfig(max_concurrent_jobs=1)
        engine = BackupEngine(config)
        # First job completes immediately (simulated)
        j1 = engine.create_backup()
        assert j1.status == BackupStatus.COMPLETED
        # No real concurrency issue in sync code, test the limit path
        # by checking the logic works
        assert engine.get_statistics()["completed"] >= 1

    def test_get_job(self):
        job = self.engine.create_backup()
        retrieved = self.engine.get_job(job.job_id)
        assert retrieved is not None
        assert retrieved.job_id == job.job_id

    def test_get_job_not_found(self):
        assert self.engine.get_job("nonexistent") is None

    def test_list_jobs(self):
        self.engine.create_backup(BackupType.FULL)
        self.engine.create_backup(BackupType.INCREMENTAL)
        jobs = self.engine.list_jobs()
        assert len(jobs) == 2

    def test_list_jobs_filter_by_status(self):
        self.engine.create_backup()
        jobs = self.engine.list_jobs(status=BackupStatus.COMPLETED)
        assert all(j.status == BackupStatus.COMPLETED for j in jobs)

    def test_list_jobs_filter_by_type(self):
        self.engine.create_backup(BackupType.FULL)
        self.engine.create_backup(BackupType.INCREMENTAL)
        full_jobs = self.engine.list_jobs(backup_type=BackupType.FULL)
        assert all(j.backup_type == BackupType.FULL for j in full_jobs)

    def test_list_jobs_limit(self):
        for _ in range(5):
            self.engine.create_backup()
        jobs = self.engine.list_jobs(limit=3)
        assert len(jobs) == 3

    def test_schedule_backup(self):
        schedule = self.engine.schedule_backup(
            "nightly", BackupType.FULL, "0 2 * * *"
        )
        assert schedule["name"] == "nightly"
        assert schedule["cron"] == "0 2 * * *"
        assert schedule["enabled"] is True

    def test_list_schedules(self):
        self.engine.schedule_backup("daily", BackupType.FULL, "0 2 * * *")
        self.engine.schedule_backup("hourly", BackupType.INCREMENTAL, "0 * * * *")
        schedules = self.engine.list_schedules()
        assert len(schedules) == 2

    def test_delete_schedule(self):
        self.engine.schedule_backup("daily", BackupType.FULL, "0 2 * * *")
        assert self.engine.delete_schedule("daily") is True
        assert self.engine.delete_schedule("nonexistent") is False
        assert len(self.engine.list_schedules()) == 0

    def test_enforce_retention_expires_old(self):
        job = self.engine.create_backup()
        # Simulate old backup
        job.completed_at = datetime.now(timezone.utc) - timedelta(days=10)
        job.storage_tier = StorageTier.HOT
        expired = self.engine.enforce_retention()
        assert expired["hot"] == 1
        assert job.status == BackupStatus.EXPIRED

    def test_enforce_retention_keeps_fresh(self):
        job = self.engine.create_backup()
        # Fresh backup should not expire
        expired = self.engine.enforce_retention()
        assert expired["hot"] == 0
        assert job.status == BackupStatus.COMPLETED

    def test_get_statistics(self):
        self.engine.create_backup()
        self.engine.create_backup()
        stats = self.engine.get_statistics()
        assert stats["total_jobs"] == 2
        assert stats["completed"] == 2
        assert stats["failed"] == 0
        assert stats["success_rate"] == 100.0
        assert stats["total_size_bytes"] > 0

    def test_statistics_empty(self):
        stats = self.engine.get_statistics()
        assert stats["total_jobs"] == 0
        assert stats["success_rate"] == 0.0

    def test_backup_metadata(self):
        job = self.engine.create_backup(metadata={"triggered_by": "cron"})
        assert job.metadata["triggered_by"] == "cron"

    def test_storage_tier_assignment(self):
        job = self.engine.create_backup(storage_tier=StorageTier.WARM)
        assert job.storage_tier == StorageTier.WARM


class TestRecoveryManager:
    """Tests for the recovery manager."""

    def setup_method(self):
        self.config = BackupConfig()
        self.engine = BackupEngine(self.config)
        self.recovery = RecoveryManager(self.engine, self.config)

    def test_generate_plan(self):
        job = self.engine.create_backup()
        plan = self.recovery.generate_plan(job.job_id)
        assert plan is not None
        assert plan.backup_job_id == job.job_id
        assert len(plan.steps) > 0
        assert plan.estimated_total_seconds > 0

    def test_generate_plan_not_found(self):
        plan = self.recovery.generate_plan("nonexistent")
        assert plan is None

    def test_plan_includes_decrypt_decompress_steps(self):
        job = self.engine.create_backup()
        plan = self.recovery.generate_plan(job.job_id)
        descriptions = [s.description for s in plan.steps]
        assert any("Decrypt" in d for d in descriptions)
        assert any("Decompress" in d for d in descriptions)

    def test_plan_without_encryption(self):
        config = BackupConfig(encryption_enabled=False)
        engine = BackupEngine(config)
        recovery = RecoveryManager(engine, config)
        job = engine.create_backup()
        plan = recovery.generate_plan(job.job_id)
        descriptions = [s.description for s in plan.steps]
        assert not any("Decrypt" in d for d in descriptions)

    def test_execute_recovery(self):
        job = self.engine.create_backup()
        result = self.recovery.execute_recovery(job.job_id)
        assert result.status == RecoveryStatus.COMPLETE
        assert result.integrity_valid is True
        assert result.steps_completed == result.steps_total

    def test_execute_recovery_not_found(self):
        result = self.recovery.execute_recovery("nonexistent")
        assert result.status == RecoveryStatus.FAILED
        assert "not found" in result.error_message

    def test_execute_recovery_dry_run(self):
        job = self.engine.create_backup()
        result = self.recovery.execute_recovery(job.job_id, dry_run=True)
        assert result.status == RecoveryStatus.COMPLETE
        assert result.validation_details["mode"] == "dry_run"

    def test_get_recovery(self):
        job = self.engine.create_backup()
        result = self.recovery.execute_recovery(job.job_id)
        retrieved = self.recovery.get_recovery(result.recovery_id)
        assert retrieved is not None
        assert retrieved.recovery_id == result.recovery_id

    def test_list_recoveries(self):
        j1 = self.engine.create_backup()
        j2 = self.engine.create_backup()
        self.recovery.execute_recovery(j1.job_id)
        self.recovery.execute_recovery(j2.job_id)
        results = self.recovery.list_recoveries()
        assert len(results) == 2

    def test_point_in_time_recovery(self):
        job = self.engine.create_backup()
        target = datetime.now(timezone.utc) + timedelta(minutes=1)
        result = self.recovery.point_in_time_recovery(target)
        assert result.status == RecoveryStatus.COMPLETE

    def test_point_in_time_no_backup(self):
        target = datetime.now(timezone.utc) - timedelta(days=365)
        result = self.recovery.point_in_time_recovery(target)
        assert result.status == RecoveryStatus.FAILED

    def test_recovery_validation_details(self):
        job = self.engine.create_backup()
        result = self.recovery.execute_recovery(job.job_id)
        assert "checks" in result.validation_details
        assert result.validation_details["valid"] is True


class TestReplicationMonitor:
    """Tests for the replication monitor."""

    def setup_method(self):
        self.config = BackupConfig(replica_lag_threshold_seconds=30.0)
        self.monitor = ReplicationMonitor(self.config)

    def test_register_replica(self):
        replica = self.monitor.register_replica("primary", "db1.local", is_primary=True)
        assert replica.name == "primary"
        assert replica.is_primary is True
        assert replica.status == ReplicaStatus.HEALTHY

    def test_register_multiple_replicas(self):
        self.monitor.register_replica("primary", "db1.local", is_primary=True)
        self.monitor.register_replica("replica1", "db2.local")
        self.monitor.register_replica("replica2", "db3.local")
        assert len(self.monitor.replicas) == 3

    def test_update_status_healthy(self):
        replica = self.monitor.register_replica("r1", "host1")
        self.monitor.update_replica_status(replica.replica_id, lag_seconds=5.0)
        assert replica.status == ReplicaStatus.HEALTHY

    def test_update_status_lagging(self):
        replica = self.monitor.register_replica("r1", "host1")
        self.monitor.update_replica_status(replica.replica_id, lag_seconds=20.0)
        assert replica.status == ReplicaStatus.LAGGING

    def test_update_status_stale(self):
        replica = self.monitor.register_replica("r1", "host1")
        self.monitor.update_replica_status(replica.replica_id, lag_seconds=60.0)
        assert replica.status == ReplicaStatus.STALE

    def test_update_nonexistent_replica(self):
        result = self.monitor.update_replica_status("fake", lag_seconds=1.0)
        assert result is None

    def test_disconnect_replica(self):
        replica = self.monitor.register_replica("r1", "host1")
        assert self.monitor.disconnect_replica(replica.replica_id) is True
        assert replica.status == ReplicaStatus.DISCONNECTED

    def test_disconnect_nonexistent(self):
        assert self.monitor.disconnect_replica("fake") is False

    def test_set_topology(self):
        primary = self.monitor.register_replica("primary", "db1", is_primary=True)
        r1 = self.monitor.register_replica("r1", "db2")
        r2 = self.monitor.register_replica("r2", "db3")
        success = self.monitor.set_topology(
            primary.replica_id, [r1.replica_id, r2.replica_id]
        )
        assert success is True
        topo = self.monitor.get_topology()
        assert len(topo[primary.replica_id]) == 2

    def test_set_topology_invalid_primary(self):
        assert self.monitor.set_topology("fake", []) is False

    def test_detect_failover_candidate(self):
        self.monitor.register_replica("primary", "db1", is_primary=True)
        r1 = self.monitor.register_replica("r1", "db2")
        r2 = self.monitor.register_replica("r2", "db3")
        self.monitor.update_replica_status(r1.replica_id, lag_seconds=5.0)
        self.monitor.update_replica_status(r2.replica_id, lag_seconds=2.0)
        candidate = self.monitor.detect_failover_candidate()
        assert candidate is not None
        assert candidate.replica_id == r2.replica_id  # lowest lag

    def test_detect_failover_no_candidates(self):
        self.monitor.register_replica("primary", "db1", is_primary=True)
        assert self.monitor.detect_failover_candidate() is None

    def test_execute_failover(self):
        primary = self.monitor.register_replica("primary", "db1", is_primary=True)
        r1 = self.monitor.register_replica("r1", "db2")
        result = self.monitor.execute_failover(r1.replica_id)
        assert result["success"] is True
        assert r1.is_primary is True
        assert primary.is_primary is False

    def test_execute_failover_already_primary(self):
        primary = self.monitor.register_replica("primary", "db1", is_primary=True)
        result = self.monitor.execute_failover(primary.replica_id)
        assert result["success"] is False

    def test_execute_failover_not_found(self):
        result = self.monitor.execute_failover("fake")
        assert result["success"] is False

    def test_get_health_summary(self):
        self.monitor.register_replica("primary", "db1", is_primary=True)
        r1 = self.monitor.register_replica("r1", "db2")
        self.monitor.update_replica_status(r1.replica_id, lag_seconds=3.0)
        summary = self.monitor.get_health_summary()
        assert summary["total_replicas"] == 2
        assert summary["primary_count"] == 1
        assert "status_counts" in summary

    def test_get_events(self):
        r1 = self.monitor.register_replica("r1", "db2")
        self.monitor.update_replica_status(r1.replica_id, lag_seconds=25.0)
        events = self.monitor.get_events()
        assert len(events) > 0
        assert events[0].event_type == "lag_alert"

    def test_get_events_filtered(self):
        r1 = self.monitor.register_replica("r1", "db2")
        r2 = self.monitor.register_replica("r2", "db3")
        self.monitor.update_replica_status(r1.replica_id, lag_seconds=25.0)
        self.monitor.update_replica_status(r2.replica_id, lag_seconds=25.0)
        events = self.monitor.get_events(replica_id=r1.replica_id)
        assert all(e.replica_id == r1.replica_id for e in events)


class TestBackupMonitor:
    """Tests for the backup monitor."""

    def setup_method(self):
        self.config = BackupConfig(rpo_target_minutes=15, rto_target_minutes=60)
        self.engine = BackupEngine(self.config)
        self.monitor = BackupMonitor(self.engine, self.config)

    def test_check_freshness_no_backups(self):
        result = self.monitor.check_backup_freshness()
        assert result["fresh"] is False
        assert result["last_backup"] is None

    def test_check_freshness_fresh(self):
        self.engine.create_backup()
        result = self.monitor.check_backup_freshness()
        assert result["fresh"] is True
        assert result["age_minutes"] is not None

    def test_check_freshness_stale(self):
        job = self.engine.create_backup()
        # Make backup appear old
        job.completed_at = datetime.now(timezone.utc) - timedelta(minutes=30)
        result = self.monitor.check_backup_freshness()
        assert result["fresh"] is False

    def test_check_storage_capacity_healthy(self):
        self.engine.create_backup()
        result = self.monitor.check_storage_capacity(max_bytes=10 * 1024**3)
        assert result["healthy"] is True
        assert result["utilization_pct"] < 1.0

    def test_check_storage_capacity_critical(self):
        self.engine.create_backup()
        result = self.monitor.check_storage_capacity(max_bytes=100)
        assert result["healthy"] is False

    def test_schedule_drill(self):
        job = self.engine.create_backup()
        drill = self.monitor.schedule_drill(job.job_id)
        assert drill.backup_job_id == job.job_id
        assert drill.scheduled_at is not None

    def test_execute_drill(self):
        job = self.engine.create_backup()
        drill = self.monitor.schedule_drill(job.job_id)
        result = self.monitor.execute_drill(drill.drill_id)
        assert result is not None
        assert result.executed_at is not None
        assert result.duration_seconds > 0

    def test_execute_drill_rto_met(self):
        job = self.engine.create_backup()
        drill = self.monitor.schedule_drill(job.job_id)
        result = self.monitor.execute_drill(drill.drill_id)
        # Simulated 45s is well under 60min RTO
        assert result.rto_met is True

    def test_execute_drill_not_found(self):
        result = self.monitor.execute_drill("fake")
        assert result is None

    def test_list_drills(self):
        j1 = self.engine.create_backup()
        j2 = self.engine.create_backup()
        self.monitor.schedule_drill(j1.job_id)
        self.monitor.schedule_drill(j2.job_id)
        drills = self.monitor.list_drills()
        assert len(drills) == 2

    def test_generate_sla_report(self):
        self.engine.create_backup()
        self.engine.create_backup()
        report = self.monitor.generate_sla_report()
        assert report.total_backups == 2
        assert report.backup_success_rate == 100.0
        assert report.rto_target_minutes == 60

    def test_sla_report_empty(self):
        report = self.monitor.generate_sla_report()
        assert report.total_backups == 0
        assert report.backup_success_rate == 0.0

    def test_get_alerts(self):
        self.monitor.check_backup_freshness()  # triggers alert (no backups)
        alerts = self.monitor.get_alerts()
        assert len(alerts) >= 1
        assert alerts[0]["severity"] == "critical"

    def test_clear_alerts(self):
        self.monitor.check_backup_freshness()
        count = self.monitor.clear_alerts()
        assert count >= 1
        assert len(self.monitor.get_alerts()) == 0

    def test_get_dashboard_data(self):
        self.engine.create_backup()
        data = self.monitor.get_dashboard_data()
        assert "freshness" in data
        assert "statistics" in data
        assert "recent_drills" in data
        assert "alerts" in data


class TestDataclasses:
    """Tests for dataclass models."""

    def test_backup_artifact(self):
        artifact = BackupArtifact(source=DataSource.POSTGRESQL, size_bytes=1024)
        assert artifact.artifact_id  # auto-generated
        assert artifact.source == DataSource.POSTGRESQL

    def test_backup_job(self):
        job = BackupJob(backup_type=BackupType.FULL)
        assert job.job_id
        assert job.status == BackupStatus.PENDING
        assert job.created_at is not None

    def test_recovery_step(self):
        step = RecoveryStep(step_number=1, description="Stop services")
        assert step.completed is False

    def test_recovery_plan(self):
        plan = RecoveryPlan(backup_job_id="abc123")
        assert plan.plan_id
        assert plan.backup_job_id == "abc123"

    def test_recovery_result(self):
        result = RecoveryResult(status=RecoveryStatus.IDLE)
        assert result.recovery_id
        assert result.integrity_valid is False

    def test_replica(self):
        replica = Replica(name="r1", host="db.local")
        assert replica.replica_id
        assert replica.status == ReplicaStatus.HEALTHY

    def test_replication_event(self):
        event = ReplicationEvent(event_type="lag_alert")
        assert event.event_id
        assert event.timestamp is not None

    def test_recovery_drill(self):
        drill = RecoveryDrill(backup_job_id="job123")
        assert drill.drill_id
        assert drill.success is False

    def test_sla_report(self):
        report = SLAReport(rto_target_minutes=30)
        assert report.report_id
        assert report.rto_target_minutes == 30
