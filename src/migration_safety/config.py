"""Configuration for migration safety & reversibility."""

import copy
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class Severity(str, Enum):
    """Severity levels for migration issues."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class MigrationDirection(str, Enum):
    """Direction of migration execution."""

    UPGRADE = "upgrade"
    DOWNGRADE = "downgrade"


class MigrationStatus(str, Enum):
    """Status of a migration execution."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class RuleCategory(str, Enum):
    """Categories for lint rules."""

    SAFETY = "safety"
    REVERSIBILITY = "reversibility"
    PERFORMANCE = "performance"
    BEST_PRACTICE = "best_practice"


@dataclass
class RuleConfig:
    """Configuration for a single lint rule."""

    rule_id: str
    name: str
    description: str
    severity: Severity = Severity.WARNING
    category: RuleCategory = RuleCategory.SAFETY
    enabled: bool = True

    def __post_init__(self):
        if isinstance(self.severity, str):
            self.severity = Severity(self.severity)
        if isinstance(self.category, str):
            self.category = RuleCategory(self.category)


# Default lint rules
DEFAULT_RULES: Dict[str, RuleConfig] = {
    "MS001": RuleConfig(
        rule_id="MS001",
        name="missing_downgrade",
        description="Migration file has no downgrade implementation",
        severity=Severity.ERROR,
        category=RuleCategory.REVERSIBILITY,
    ),
    "MS002": RuleConfig(
        rule_id="MS002",
        name="destructive_operation",
        description="Migration contains destructive operations (DROP TABLE/COLUMN)",
        severity=Severity.CRITICAL,
        category=RuleCategory.SAFETY,
    ),
    "MS003": RuleConfig(
        rule_id="MS003",
        name="data_migration_in_schema",
        description="Migration mixes data manipulation with schema changes",
        severity=Severity.WARNING,
        category=RuleCategory.BEST_PRACTICE,
    ),
    "MS004": RuleConfig(
        rule_id="MS004",
        name="missing_index",
        description="Table creation without indexes on foreign key columns",
        severity=Severity.WARNING,
        category=RuleCategory.PERFORMANCE,
    ),
    "MS005": RuleConfig(
        rule_id="MS005",
        name="empty_migration",
        description="Migration has empty upgrade function",
        severity=Severity.INFO,
        category=RuleCategory.BEST_PRACTICE,
    ),
    "MS006": RuleConfig(
        rule_id="MS006",
        name="no_revision_id",
        description="Migration file lacks revision identifier",
        severity=Severity.ERROR,
        category=RuleCategory.SAFETY,
    ),
}


@dataclass
class MigrationSafetyConfig:
    """Configuration for migration safety framework."""

    rules: Dict[str, RuleConfig] = field(default_factory=lambda: copy.deepcopy(DEFAULT_RULES))
    alembic_versions_dir: str = "alembic/versions"
    fail_on_error: bool = True
    fail_on_critical: bool = True
    max_issues_before_fail: int = 10
    require_downgrade: bool = True
    block_destructive_ops: bool = False
    allowed_destructive_tables: List[str] = field(default_factory=list)
    db_connection_timeout: int = 10
    schema_validation_enabled: bool = True

    def get_rule(self, rule_id: str) -> Optional[RuleConfig]:
        """Get rule configuration by ID."""
        return self.rules.get(rule_id)

    def enable_rule(self, rule_id: str) -> bool:
        """Enable a specific rule."""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = True
            return True
        return False

    def disable_rule(self, rule_id: str) -> bool:
        """Disable a specific rule."""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = False
            return True
        return False

    def get_enabled_rules(self) -> Dict[str, RuleConfig]:
        """Get only enabled rules."""
        return {k: v for k, v in self.rules.items() if v.enabled}

    def add_rule(self, rule: RuleConfig) -> None:
        """Add a custom rule."""
        self.rules[rule.rule_id] = rule

    def get_rules_by_severity(self, severity: Severity) -> List[RuleConfig]:
        """Get rules filtered by severity."""
        return [r for r in self.rules.values() if r.severity == severity and r.enabled]

    def get_rules_by_category(self, category: RuleCategory) -> List[RuleConfig]:
        """Get rules filtered by category."""
        return [r for r in self.rules.values() if r.category == category and r.enabled]
