"""Contract validation engine with violation tracking."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from .config import FieldType, ValidationLevel, ViolationType
from .schema import DataContract, FieldDefinition, SchemaVersion


@dataclass
class ContractViolation:
    """A single contract violation record."""
    violation_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    contract_id: str = ""
    violation_type: ViolationType = ViolationType.MISSING_FIELD
    field_name: str = ""
    expected: str = ""
    actual: str = ""
    severity: str = "error"
    message: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "violation_id": self.violation_id,
            "contract_id": self.contract_id,
            "violation_type": self.violation_type.value,
            "field_name": self.field_name,
            "expected": self.expected,
            "actual": self.actual,
            "severity": self.severity,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ValidationResult:
    """Result of validating data against a contract."""
    valid: bool = True
    violations: List[ContractViolation] = field(default_factory=list)
    warnings: List[ContractViolation] = field(default_factory=list)
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    records_checked: int = 0
    completeness: float = 1.0

    @property
    def violation_count(self) -> int:
        return len(self.violations)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "violations": [v.to_dict() for v in self.violations],
            "warnings": [w.to_dict() for w in self.warnings],
            "checked_at": self.checked_at.isoformat(),
            "records_checked": self.records_checked,
            "completeness": self.completeness,
        }


# Python type mapping for validation
_FIELD_TYPE_MAP = {
    FieldType.STRING: str,
    FieldType.INTEGER: int,
    FieldType.FLOAT: (int, float),
    FieldType.BOOLEAN: bool,
    FieldType.DATETIME: datetime,
    FieldType.LIST: list,
    FieldType.MAP: dict,
    FieldType.ENUM: str,
}


class ContractValidator:
    """Validates data records against data contracts.

    Supports field-level type checking, constraint validation,
    freshness monitoring, and completeness scoring.
    """

    def __init__(self, validation_level: ValidationLevel = ValidationLevel.STRICT):
        self._validation_level = validation_level
        self._violation_log: List[ContractViolation] = []

    @property
    def validation_level(self) -> ValidationLevel:
        return self._validation_level

    @property
    def violation_log(self) -> List[ContractViolation]:
        return list(self._violation_log)

    def validate(self, data: Dict[str, Any], contract: DataContract) -> ValidationResult:
        """Validate a data record against a contract's schema.

        Checks:
        1. Missing required fields
        2. Type mismatches
        3. Constraint violations
        """
        result = ValidationResult(records_checked=1)

        if not contract.schema_version:
            return result

        schema = contract.schema_version
        violations = []
        warnings = []

        for field_def in schema.fields:
            if field_def.name not in data:
                if field_def.required:
                    v = ContractViolation(
                        contract_id=contract.contract_id,
                        violation_type=ViolationType.MISSING_FIELD,
                        field_name=field_def.name,
                        expected="present",
                        actual="missing",
                        severity="error",
                        message=f"Required field '{field_def.name}' is missing",
                    )
                    violations.append(v)
                continue

            # Validate field value
            field_violations = self.validate_field(
                data[field_def.name], field_def, contract.contract_id
            )
            for fv in field_violations:
                if self._validation_level == ValidationLevel.STRICT:
                    violations.append(fv)
                elif self._validation_level == ValidationLevel.WARN:
                    fv.severity = "warning"
                    warnings.append(fv)
                # PERMISSIVE: drop violations silently

        # Check for extra fields (schema drift)
        if self._validation_level == ValidationLevel.STRICT:
            known_fields = {f.name for f in schema.fields}
            for key in data:
                if key not in known_fields:
                    v = ContractViolation(
                        contract_id=contract.contract_id,
                        violation_type=ViolationType.SCHEMA_DRIFT,
                        field_name=key,
                        expected="not present",
                        actual="present",
                        severity="warning",
                        message=f"Unexpected field '{key}' not in schema",
                    )
                    warnings.append(v)

        # Compute completeness
        result.completeness = self.validate_completeness(data, schema)
        result.violations = violations
        result.warnings = warnings
        result.valid = len(violations) == 0

        # Log violations
        self._violation_log.extend(violations)

        return result

    def validate_batch(
        self,
        records: List[Dict[str, Any]],
        contract: DataContract,
    ) -> ValidationResult:
        """Validate multiple records against a contract."""
        all_violations = []
        all_warnings = []
        total_completeness = 0.0

        for record in records:
            r = self.validate(record, contract)
            all_violations.extend(r.violations)
            all_warnings.extend(r.warnings)
            total_completeness += r.completeness

        avg_completeness = total_completeness / len(records) if records else 1.0

        return ValidationResult(
            valid=len(all_violations) == 0,
            violations=all_violations,
            warnings=all_warnings,
            records_checked=len(records),
            completeness=avg_completeness,
        )

    def validate_field(
        self,
        value: Any,
        field_def: FieldDefinition,
        contract_id: str = "",
    ) -> List[ContractViolation]:
        """Validate a single field value against its definition.

        Checks type and constraints.
        """
        violations = []

        # Type check
        expected_type = _FIELD_TYPE_MAP.get(field_def.field_type)
        if expected_type is not None and value is not None:
            # bool is subclass of int, handle specially
            if field_def.field_type == FieldType.INTEGER and isinstance(value, bool):
                violations.append(
                    ContractViolation(
                        contract_id=contract_id,
                        violation_type=ViolationType.TYPE_MISMATCH,
                        field_name=field_def.name,
                        expected=field_def.field_type.value,
                        actual=type(value).__name__,
                        severity="error",
                        message=f"Field '{field_def.name}' expected {field_def.field_type.value}, got {type(value).__name__}",
                    )
                )
            elif field_def.field_type == FieldType.BOOLEAN:
                if not isinstance(value, bool):
                    violations.append(
                        ContractViolation(
                            contract_id=contract_id,
                            violation_type=ViolationType.TYPE_MISMATCH,
                            field_name=field_def.name,
                            expected=field_def.field_type.value,
                            actual=type(value).__name__,
                            severity="error",
                            message=f"Field '{field_def.name}' expected {field_def.field_type.value}, got {type(value).__name__}",
                        )
                    )
            elif not isinstance(value, expected_type):
                violations.append(
                    ContractViolation(
                        contract_id=contract_id,
                        violation_type=ViolationType.TYPE_MISMATCH,
                        field_name=field_def.name,
                        expected=field_def.field_type.value,
                        actual=type(value).__name__,
                        severity="error",
                        message=f"Field '{field_def.name}' expected {field_def.field_type.value}, got {type(value).__name__}",
                    )
                )
                return violations  # Skip constraint checks if type is wrong

        # Constraint checks
        constraint_violations = self.validate_constraints(
            value, field_def.constraints, field_def.name, contract_id
        )
        violations.extend(constraint_violations)

        return violations

    def validate_constraints(
        self,
        value: Any,
        constraints: Dict[str, Any],
        field_name: str = "",
        contract_id: str = "",
    ) -> List[ContractViolation]:
        """Validate a value against a set of constraints.

        Supported constraints:
        - min_value, max_value: numeric range
        - min_length, max_length: string/list length
        - pattern: regex pattern match (strings)
        - allowed_values: enum-like list of permitted values
        - not_null: value must not be None
        """
        violations = []

        if not constraints:
            return violations

        # min_value
        if "min_value" in constraints and value is not None:
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                if value < constraints["min_value"]:
                    violations.append(
                        ContractViolation(
                            contract_id=contract_id,
                            violation_type=ViolationType.CONSTRAINT_VIOLATION,
                            field_name=field_name,
                            expected=f">= {constraints['min_value']}",
                            actual=str(value),
                            severity="error",
                            message=f"Field '{field_name}' value {value} below minimum {constraints['min_value']}",
                        )
                    )

        # max_value
        if "max_value" in constraints and value is not None:
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                if value > constraints["max_value"]:
                    violations.append(
                        ContractViolation(
                            contract_id=contract_id,
                            violation_type=ViolationType.CONSTRAINT_VIOLATION,
                            field_name=field_name,
                            expected=f"<= {constraints['max_value']}",
                            actual=str(value),
                            severity="error",
                            message=f"Field '{field_name}' value {value} above maximum {constraints['max_value']}",
                        )
                    )

        # min_length
        if "min_length" in constraints and value is not None:
            if hasattr(value, "__len__"):
                if len(value) < constraints["min_length"]:
                    violations.append(
                        ContractViolation(
                            contract_id=contract_id,
                            violation_type=ViolationType.CONSTRAINT_VIOLATION,
                            field_name=field_name,
                            expected=f"length >= {constraints['min_length']}",
                            actual=str(len(value)),
                            severity="error",
                            message=f"Field '{field_name}' length {len(value)} below minimum {constraints['min_length']}",
                        )
                    )

        # max_length
        if "max_length" in constraints and value is not None:
            if hasattr(value, "__len__"):
                if len(value) > constraints["max_length"]:
                    violations.append(
                        ContractViolation(
                            contract_id=contract_id,
                            violation_type=ViolationType.CONSTRAINT_VIOLATION,
                            field_name=field_name,
                            expected=f"length <= {constraints['max_length']}",
                            actual=str(len(value)),
                            severity="error",
                            message=f"Field '{field_name}' length {len(value)} above maximum {constraints['max_length']}",
                        )
                    )

        # pattern (regex)
        if "pattern" in constraints and isinstance(value, str):
            import re
            if not re.match(constraints["pattern"], value):
                violations.append(
                    ContractViolation(
                        contract_id=contract_id,
                        violation_type=ViolationType.CONSTRAINT_VIOLATION,
                        field_name=field_name,
                        expected=f"matches pattern '{constraints['pattern']}'",
                        actual=value,
                        severity="error",
                        message=f"Field '{field_name}' does not match pattern '{constraints['pattern']}'",
                    )
                )

        # allowed_values
        if "allowed_values" in constraints and value is not None:
            if value not in constraints["allowed_values"]:
                violations.append(
                    ContractViolation(
                        contract_id=contract_id,
                        violation_type=ViolationType.CONSTRAINT_VIOLATION,
                        field_name=field_name,
                        expected=f"one of {constraints['allowed_values']}",
                        actual=str(value),
                        severity="error",
                        message=f"Field '{field_name}' value '{value}' not in allowed values",
                    )
                )

        # not_null
        if constraints.get("not_null") and value is None:
            violations.append(
                ContractViolation(
                    contract_id=contract_id,
                    violation_type=ViolationType.CONSTRAINT_VIOLATION,
                    field_name=field_name,
                    expected="not null",
                    actual="null",
                    severity="error",
                    message=f"Field '{field_name}' must not be null",
                )
            )

        return violations

    def validate_freshness(
        self,
        timestamp: datetime,
        sla_seconds: float,
    ) -> bool:
        """Check if a timestamp is within the freshness SLA.

        Returns True if the data is fresh enough.
        Handles both naive and timezone-aware timestamps.
        """
        if timestamp.tzinfo is None:
            # Compare naive-to-naive to avoid local/UTC mismatch
            now = datetime.now()
        else:
            now = datetime.now(timezone.utc)
        age = (now - timestamp).total_seconds()
        return age <= sla_seconds

    def validate_completeness(
        self,
        data: Dict[str, Any],
        schema: SchemaVersion,
    ) -> float:
        """Calculate the completeness ratio of a record against a schema.

        Returns a float between 0.0 and 1.0 representing the fraction
        of required fields that are present and non-null.
        """
        required = schema.required_fields()
        if not required:
            return 1.0

        present = sum(
            1 for f in required
            if f.name in data and data[f.name] is not None
        )
        return present / len(required)

    def violation_statistics(
        self,
        contract_id: Optional[str] = None,
        period_hours: int = 24,
    ) -> Dict[str, Any]:
        """Get violation statistics for a contract over a period.

        Returns counts by violation type, total count, and timeframe.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=period_hours)

        relevant = [
            v for v in self._violation_log
            if v.timestamp >= cutoff
            and (contract_id is None or v.contract_id == contract_id)
        ]

        by_type: Dict[str, int] = {}
        by_field: Dict[str, int] = {}
        for v in relevant:
            vt = v.violation_type.value
            by_type[vt] = by_type.get(vt, 0) + 1
            if v.field_name:
                by_field[v.field_name] = by_field.get(v.field_name, 0) + 1

        return {
            "total": len(relevant),
            "by_type": by_type,
            "by_field": by_field,
            "period_hours": period_hours,
            "contract_id": contract_id,
        }

    def clear_log(self) -> None:
        """Clear the violation log."""
        self._violation_log.clear()
