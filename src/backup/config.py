"""PRD-116: Disaster Recovery & Automated Backup — Configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class BackupType(str, Enum):
    """Type of backup."""

    FULL = "full"
    INCREMENTAL = "incremental"
    SNAPSHOT = "snapshot"


class BackupStatus(str, Enum):
    """Status of a backup job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


class StorageBackend(str, Enum):
    """Storage backend for backups."""

    LOCAL = "local"
    S3 = "s3"
    AZURE_BLOB = "azure_blob"
    GLACIER = "glacier"


class StorageTier(str, Enum):
    """Storage tier for backup retention."""

    HOT = "hot"
    WARM = "warm"
    COLD = "cold"


class RecoveryStatus(str, Enum):
    """Status of a recovery operation."""

    IDLE = "idle"
    PLANNING = "planning"
    RESTORING = "restoring"
    VALIDATING = "validating"
    COMPLETE = "complete"
    FAILED = "failed"


class ReplicaStatus(str, Enum):
    """Status of a database replica."""

    HEALTHY = "healthy"
    LAGGING = "lagging"
    STALE = "stale"
    DISCONNECTED = "disconnected"


class DataSource(str, Enum):
    """Data source for backup."""

    POSTGRESQL = "postgresql"
    REDIS = "redis"
    FILESYSTEM = "filesystem"
    TIMESCALEDB = "timescaledb"


@dataclass
class RetentionPolicy:
    """Backup retention policy per tier."""

    hot_days: int = 7
    warm_days: int = 30
    cold_days: int = 90
    max_hot_count: int = 7
    max_warm_count: int = 30
    max_cold_count: int = 12


@dataclass
class BackupConfig:
    """Configuration for the backup system."""

    storage_backend: StorageBackend = StorageBackend.LOCAL
    storage_path: str = "/backups"
    compression_enabled: bool = True
    encryption_enabled: bool = True
    encryption_key: Optional[str] = None
    retention_policy: RetentionPolicy = field(default_factory=RetentionPolicy)
    max_concurrent_jobs: int = 2
    default_sources: list[DataSource] = field(
        default_factory=lambda: [DataSource.POSTGRESQL, DataSource.REDIS]
    )
    health_check_interval_seconds: int = 60
    replica_lag_threshold_seconds: float = 30.0
    rto_target_minutes: int = 60
    rpo_target_minutes: int = 15
