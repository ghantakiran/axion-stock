"""Configuration validation with schema-based rules and startup reports."""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .config import ConfigNamespace
from .config_store import ConfigStore

logger = logging.getLogger(__name__)


class ValidationSeverity(str, Enum):
    """Severity of a validation issue."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class ValidationRule:
    """A single config validation rule."""

    rule_id: str
    key: str
    namespace: ConfigNamespace
    description: str = ""
    severity: ValidationSeverity = ValidationSeverity.ERROR
    required: bool = False
    value_type: Optional[type] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    allowed_values: Optional[List[Any]] = None
    custom_validator: Optional[Callable[[Any], bool]] = None


@dataclass
class ValidationIssue:
    """A single validation issue found during validation."""

    rule_id: str
    key: str
    severity: ValidationSeverity
    message: str

    def __str__(self) -> str:
        return f"[{self.severity.value.upper()}] {self.rule_id}: {self.key} - {self.message}"


@dataclass
class ValidationReport:
    """Report from running config validation."""

    issues: List[ValidationIssue] = field(default_factory=list)
    rules_checked: int = 0
    keys_validated: int = 0

    @property
    def is_valid(self) -> bool:
        """True if no errors found."""
        return not any(
            i.severity == ValidationSeverity.ERROR for i in self.issues
        )

    @property
    def error_count(self) -> int:
        return sum(
            1 for i in self.issues if i.severity == ValidationSeverity.ERROR
        )

    @property
    def warning_count(self) -> int:
        return sum(
            1 for i in self.issues if i.severity == ValidationSeverity.WARNING
        )

    @property
    def info_count(self) -> int:
        return sum(
            1 for i in self.issues if i.severity == ValidationSeverity.INFO
        )

    def summary(self) -> Dict[str, Any]:
        """Summary of the validation report."""
        return {
            "valid": self.is_valid,
            "rules_checked": self.rules_checked,
            "keys_validated": self.keys_validated,
            "errors": self.error_count,
            "warnings": self.warning_count,
            "info": self.info_count,
            "total_issues": len(self.issues),
        }


class ConfigValidator:
    """Validates configuration against defined rules.

    Supports required keys, type checking, range validation,
    allowed values, and custom validator functions.
    """

    def __init__(self):
        self._rules: List[ValidationRule] = []

    def add_rule(self, rule: ValidationRule) -> None:
        """Add a validation rule."""
        self._rules.append(rule)

    def remove_rule(self, rule_id: str) -> bool:
        """Remove a rule by ID."""
        before = len(self._rules)
        self._rules = [r for r in self._rules if r.rule_id != rule_id]
        return len(self._rules) < before

    def validate(self, store: ConfigStore) -> ValidationReport:
        """Run all validation rules against the config store."""
        report = ValidationReport()
        validated_keys = set()

        for rule in self._rules:
            report.rules_checked += 1
            value = store.get(rule.key, rule.namespace)
            validated_keys.add(f"{rule.namespace.value}.{rule.key}")

            if value is None:
                if rule.required:
                    report.issues.append(ValidationIssue(
                        rule_id=rule.rule_id,
                        key=f"{rule.namespace.value}.{rule.key}",
                        severity=rule.severity,
                        message="Required config key is missing",
                    ))
                continue

            if rule.value_type is not None:
                if not isinstance(value, rule.value_type):
                    report.issues.append(ValidationIssue(
                        rule_id=rule.rule_id,
                        key=f"{rule.namespace.value}.{rule.key}",
                        severity=rule.severity,
                        message=f"Expected type {rule.value_type.__name__}, "
                                f"got {type(value).__name__}",
                    ))
                    continue

            if rule.min_value is not None and isinstance(value, (int, float)):
                if value < rule.min_value:
                    report.issues.append(ValidationIssue(
                        rule_id=rule.rule_id,
                        key=f"{rule.namespace.value}.{rule.key}",
                        severity=rule.severity,
                        message=f"Value {value} is below minimum {rule.min_value}",
                    ))

            if rule.max_value is not None and isinstance(value, (int, float)):
                if value > rule.max_value:
                    report.issues.append(ValidationIssue(
                        rule_id=rule.rule_id,
                        key=f"{rule.namespace.value}.{rule.key}",
                        severity=rule.severity,
                        message=f"Value {value} exceeds maximum {rule.max_value}",
                    ))

            if rule.allowed_values is not None:
                if value not in rule.allowed_values:
                    report.issues.append(ValidationIssue(
                        rule_id=rule.rule_id,
                        key=f"{rule.namespace.value}.{rule.key}",
                        severity=rule.severity,
                        message=f"Value '{value}' not in allowed: {rule.allowed_values}",
                    ))

            if rule.custom_validator is not None:
                try:
                    if not rule.custom_validator(value):
                        report.issues.append(ValidationIssue(
                            rule_id=rule.rule_id,
                            key=f"{rule.namespace.value}.{rule.key}",
                            severity=rule.severity,
                            message="Custom validation failed",
                        ))
                except Exception as e:
                    report.issues.append(ValidationIssue(
                        rule_id=rule.rule_id,
                        key=f"{rule.namespace.value}.{rule.key}",
                        severity=ValidationSeverity.ERROR,
                        message=f"Custom validator raised: {e}",
                    ))

        report.keys_validated = len(validated_keys)
        logger.info(
            "Config validation: %d rules, %d issues (%d errors)",
            report.rules_checked, len(report.issues), report.error_count,
        )
        return report

    def get_rules(self) -> List[ValidationRule]:
        """Get all validation rules."""
        return list(self._rules)

    def clear(self) -> None:
        """Clear all rules."""
        self._rules.clear()
