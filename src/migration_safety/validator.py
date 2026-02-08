"""Migration validator using AST-based analysis."""

import ast
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from .config import MigrationSafetyConfig, Severity

logger = logging.getLogger(__name__)

# Patterns for destructive operations
DESTRUCTIVE_PATTERNS = [
    "drop_table",
    "drop_column",
    "drop_index",
    "drop_constraint",
]

# Patterns for data manipulation operations
DATA_MIGRATION_PATTERNS = [
    "execute",
    "bulk_insert",
]

# SQL keywords suggesting data manipulation
DATA_SQL_KEYWORDS = [
    "INSERT",
    "UPDATE",
    "DELETE",
    "TRUNCATE",
]

# Patterns indicating foreign key columns (naming convention)
FK_COLUMN_PATTERNS = re.compile(r"(\w+_id)\b")


@dataclass
class ValidationResult:
    """Result of validating a single migration file."""

    file_path: str
    revision: Optional[str] = None
    down_revision: Optional[str] = None
    has_upgrade: bool = False
    has_downgrade: bool = False
    has_destructive_ops: bool = False
    destructive_ops: List[str] = field(default_factory=list)
    has_data_migration: bool = False
    data_migration_ops: List[str] = field(default_factory=list)
    missing_indexes: List[str] = field(default_factory=list)
    is_empty_upgrade: bool = False
    is_empty_downgrade: bool = False
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def is_safe(self) -> bool:
        """Check if migration passes all safety checks."""
        return (
            self.has_downgrade
            and not self.has_destructive_ops
            and len(self.errors) == 0
        )

    @property
    def safety_score(self) -> float:
        """Calculate a safety score from 0.0 to 1.0."""
        score = 1.0
        if not self.has_downgrade:
            score -= 0.4
        if self.has_destructive_ops:
            score -= 0.3
        if self.has_data_migration:
            score -= 0.1
        if self.missing_indexes:
            score -= 0.1
        if self.is_empty_upgrade:
            score -= 0.05
        score -= len(self.errors) * 0.05
        return max(0.0, min(1.0, score))


class MigrationValidator:
    """Validates migration files using AST parsing and static analysis."""

    def __init__(self, config: Optional[MigrationSafetyConfig] = None):
        self.config = config or MigrationSafetyConfig()
        self._results: Dict[str, ValidationResult] = {}

    def validate_file(self, file_path: str) -> ValidationResult:
        """Validate a single migration file."""
        result = ValidationResult(file_path=file_path)

        if not os.path.exists(file_path):
            result.errors.append(f"File not found: {file_path}")
            self._results[file_path] = result
            return result

        try:
            with open(file_path, "r") as f:
                source = f.read()
        except Exception as e:
            result.errors.append(f"Cannot read file: {e}")
            self._results[file_path] = result
            return result

        # Parse AST
        try:
            tree = ast.parse(source, filename=file_path)
        except SyntaxError as e:
            result.errors.append(f"Syntax error: {e}")
            self._results[file_path] = result
            return result

        # Extract module-level assignments (revision, down_revision)
        self._extract_revisions(tree, result)

        # Analyze upgrade function
        upgrade_func = self._find_function(tree, "upgrade")
        if upgrade_func:
            result.has_upgrade = True
            result.is_empty_upgrade = self._is_empty_function(upgrade_func)
            result.has_destructive_ops = self._check_destructive_ops(upgrade_func)
            result.destructive_ops = self._get_destructive_ops(upgrade_func)
            result.has_data_migration = self._check_data_migration(upgrade_func, source)
            result.data_migration_ops = self._get_data_migration_ops(upgrade_func, source)
            result.missing_indexes = self._check_missing_indexes(upgrade_func, source)
        else:
            result.errors.append("No upgrade() function found")

        # Analyze downgrade function
        downgrade_func = self._find_function(tree, "downgrade")
        if downgrade_func:
            result.has_downgrade = not self._is_empty_function(downgrade_func)
            result.is_empty_downgrade = self._is_empty_function(downgrade_func)
        else:
            result.has_downgrade = False
            if self.config.require_downgrade:
                result.errors.append("No downgrade() function found")

        self._results[file_path] = result
        return result

    def validate_directory(self, directory: str) -> Dict[str, ValidationResult]:
        """Validate all migration files in a directory."""
        results = {}
        if not os.path.isdir(directory):
            logger.error("Directory not found: %s", directory)
            return results

        for filename in sorted(os.listdir(directory)):
            if filename.endswith(".py") and not filename.startswith("__"):
                file_path = os.path.join(directory, filename)
                results[file_path] = self.validate_file(file_path)

        return results

    def get_results(self) -> Dict[str, ValidationResult]:
        """Get all validation results."""
        return dict(self._results)

    def get_unsafe_migrations(self) -> List[ValidationResult]:
        """Get list of migrations that failed safety checks."""
        return [r for r in self._results.values() if not r.is_safe]

    def get_summary(self) -> Dict:
        """Get summary statistics of all validations."""
        total = len(self._results)
        safe = sum(1 for r in self._results.values() if r.is_safe)
        with_downgrade = sum(1 for r in self._results.values() if r.has_downgrade)
        with_destructive = sum(1 for r in self._results.values() if r.has_destructive_ops)
        with_data_migration = sum(1 for r in self._results.values() if r.has_data_migration)
        with_missing_indexes = sum(1 for r in self._results.values() if len(r.missing_indexes) > 0)

        avg_score = (
            sum(r.safety_score for r in self._results.values()) / total
            if total > 0
            else 0.0
        )

        return {
            "total_migrations": total,
            "safe_migrations": safe,
            "unsafe_migrations": total - safe,
            "with_downgrade": with_downgrade,
            "without_downgrade": total - with_downgrade,
            "with_destructive_ops": with_destructive,
            "with_data_migration": with_data_migration,
            "with_missing_indexes": with_missing_indexes,
            "average_safety_score": round(avg_score, 3),
        }

    # ── Private helpers ─────────────────────────────────────────────

    def _extract_revisions(self, tree: ast.Module, result: ValidationResult) -> None:
        """Extract revision and down_revision from module-level assignments."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        if target.id == "revision":
                            result.revision = self._get_assign_value(node.value)
                        elif target.id == "down_revision":
                            result.down_revision = self._get_assign_value(node.value)

    def _get_assign_value(self, node: ast.expr) -> Optional[str]:
        """Extract string value from an assignment."""
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        return None

    def _find_function(self, tree: ast.Module, name: str) -> Optional[ast.FunctionDef]:
        """Find a top-level function definition by name."""
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.FunctionDef) and node.name == name:
                return node
        return None

    def _is_empty_function(self, func: ast.FunctionDef) -> bool:
        """Check if a function body is empty (only pass or docstring)."""
        body = func.body
        if not body:
            return True

        meaningful = []
        for stmt in body:
            # Skip docstrings
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str):
                continue
            # Skip pass statements
            if isinstance(stmt, ast.Pass):
                continue
            meaningful.append(stmt)

        return len(meaningful) == 0

    def _check_destructive_ops(self, func: ast.FunctionDef) -> bool:
        """Check if the function contains destructive operations."""
        return len(self._get_destructive_ops(func)) > 0

    def _get_destructive_ops(self, func: ast.FunctionDef) -> List[str]:
        """Get list of destructive operations in a function."""
        ops = []
        for node in ast.walk(func):
            if isinstance(node, ast.Call):
                func_name = self._get_call_name(node)
                if func_name and any(pat in func_name.lower() for pat in DESTRUCTIVE_PATTERNS):
                    ops.append(func_name)
            # Also check string constants for raw SQL
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                val = node.value.upper()
                if "DROP TABLE" in val or "DROP COLUMN" in val:
                    ops.append(f"raw_sql:{node.value[:50]}")
        return ops

    def _check_data_migration(self, func: ast.FunctionDef, source: str) -> bool:
        """Check if the function contains data migration operations."""
        return len(self._get_data_migration_ops(func, source)) > 0

    def _get_data_migration_ops(self, func: ast.FunctionDef, source: str) -> List[str]:
        """Get list of data migration operations."""
        ops = []
        for node in ast.walk(func):
            if isinstance(node, ast.Call):
                func_name = self._get_call_name(node)
                if func_name and any(pat in func_name.lower() for pat in DATA_MIGRATION_PATTERNS):
                    ops.append(func_name)
            # Check string constants for SQL DML
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                val = node.value.upper().strip()
                for keyword in DATA_SQL_KEYWORDS:
                    if val.startswith(keyword) or f" {keyword} " in val:
                        ops.append(f"sql:{keyword}")
                        break
        return ops

    def _check_missing_indexes(self, func: ast.FunctionDef, source: str) -> List[str]:
        """Check for missing indexes on FK-like columns in create_table calls."""
        missing = []

        for node in ast.walk(func):
            if isinstance(node, ast.Call):
                func_name = self._get_call_name(node)
                if func_name and "create_table" in func_name.lower():
                    # Collect FK column names and indexed column names
                    fk_columns: Set[str] = set()
                    indexed_columns: Set[str] = set()

                    for arg in node.args[1:]:  # Skip table name
                        col_name = self._extract_column_name(arg)
                        if col_name:
                            if FK_COLUMN_PATTERNS.match(col_name):
                                fk_columns.add(col_name)
                            if self._has_index_kwarg(arg):
                                indexed_columns.add(col_name)

                    for kw in node.keywords:
                        if isinstance(kw.value, ast.Call):
                            col_name = self._extract_column_name(kw.value)
                            if col_name and FK_COLUMN_PATTERNS.match(col_name):
                                fk_columns.add(col_name)
                                if self._has_index_kwarg(kw.value):
                                    indexed_columns.add(col_name)

                    unindexed_fk = fk_columns - indexed_columns
                    missing.extend(sorted(unindexed_fk))

        return missing

    def _extract_column_name(self, node: ast.expr) -> Optional[str]:
        """Extract column name from a Column() call argument."""
        if isinstance(node, ast.Call):
            if node.args:
                first_arg = node.args[0]
                if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                    return first_arg.value
        return None

    def _has_index_kwarg(self, node: ast.expr) -> bool:
        """Check if a Column() call has index=True."""
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg == "index" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                    return True
                if kw.arg == "primary_key" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                    return True
        return False

    def _get_call_name(self, node: ast.Call) -> Optional[str]:
        """Get the function name from a Call node."""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            parts = []
            current = node.func
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            return ".".join(reversed(parts))
        return None
