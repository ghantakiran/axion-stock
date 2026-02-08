"""Configuration enums and dataclasses for Data Contracts & Schema Governance."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class ContractStatus(str, Enum):
    """Status of a data contract."""
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


class CompatibilityMode(str, Enum):
    """Schema compatibility mode."""
    BACKWARD = "backward"
    FORWARD = "forward"
    FULL = "full"
    NONE = "none"


class FieldType(str, Enum):
    """Supported field types in data contracts."""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATETIME = "datetime"
    LIST = "list"
    MAP = "map"
    ENUM = "enum"


class ViolationType(str, Enum):
    """Types of contract violations."""
    MISSING_FIELD = "missing_field"
    TYPE_MISMATCH = "type_mismatch"
    CONSTRAINT_VIOLATION = "constraint_violation"
    SCHEMA_DRIFT = "schema_drift"
    FRESHNESS = "freshness"
    COMPLETENESS = "completeness"


class ValidationLevel(str, Enum):
    """Validation strictness level."""
    STRICT = "strict"
    WARN = "warn"
    PERMISSIVE = "permissive"


@dataclass
class ContractConfig:
    """Configuration for contract validation behavior."""
    compatibility_mode: CompatibilityMode = CompatibilityMode.BACKWARD
    validation_level: ValidationLevel = ValidationLevel.STRICT
    max_violations_per_hour: int = 100
    alert_on_violation: bool = True
    track_schema_drift: bool = True
    auto_deprecate_after_days: int = 90
    retention_days: int = 365
