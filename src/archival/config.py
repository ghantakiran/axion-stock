"""Configuration for data archival and GDPR compliance."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class StorageTier(str, Enum):
    """Storage tier classification for data lifecycle."""
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"
    ARCHIVE = "archive"
    DELETED = "deleted"


class ArchivalFormat(str, Enum):
    """Supported archival output formats."""
    PARQUET = "parquet"
    CSV = "csv"
    JSON_LINES = "json_lines"


class GDPRRequestType(str, Enum):
    """GDPR data subject request types."""
    DELETION = "deletion"
    EXPORT = "export"
    RECTIFICATION = "rectification"
    ACCESS = "access"


class GDPRRequestStatus(str, Enum):
    """Status of a GDPR request through its lifecycle."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


@dataclass
class ArchivalConfig:
    """Master configuration for the archival and GDPR system."""

    default_format: ArchivalFormat = ArchivalFormat.PARQUET
    compression: str = "gzip"
    storage_path: str = "archive/"
    max_batch_size: int = 100_000
    enable_gdpr: bool = True
    deletion_audit: bool = True
    hot_retention_days: int = 90
    warm_retention_days: int = 365
    cold_retention_days: int = 2555
