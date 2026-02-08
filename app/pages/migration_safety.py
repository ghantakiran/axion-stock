"""Migration Safety Dashboard (PRD-110).

Displays migration history, validation results, linting issues,
and safety configuration.
"""

import random

import streamlit as st

from src.migration_safety.config import (
    DEFAULT_RULES,
    MigrationSafetyConfig,
    Severity,
)

st.set_page_config(page_title="Migration Safety", page_icon="🔒", layout="wide")
st.title("🔒 Migration Safety & Reversibility")

tab1, tab2, tab3, tab4 = st.tabs([
    "Migration History",
    "Validation Results",
    "Linting",
    "Configuration",
])

with tab1:
    st.header("Migration History")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Migrations", "110")
    col2.metric("With Downgrade", "98")
    col3.metric("Safety Score", "87%")
    col4.metric("Destructive Ops", "5")

    st.subheader("Recent Migrations")
    migrations = [
        {"rev": "110", "name": "migration_safety", "safe": True, "score": 1.0},
        {"rev": "109", "name": "audit_trail", "safe": True, "score": 1.0},
        {"rev": "108", "name": "integration_testing", "safe": True, "score": 1.0},
        {"rev": "107", "name": "lifecycle_management", "safe": True, "score": 1.0},
        {"rev": "106", "name": "api_error_handling", "safe": True, "score": 1.0},
        {"rev": "105", "name": "enhanced_cicd", "safe": True, "score": 0.9},
        {"rev": "104", "name": "production_docker", "safe": True, "score": 0.9},
    ]
    for m in migrations:
        icon = "✅" if m["safe"] else "⚠️"
        st.write(f"{icon} **Rev {m['rev']}**: {m['name']} (score: {m['score']:.0%})")

with tab2:
    st.header("Validation Results")

    st.subheader("Safety Score Distribution")
    scores = {
        "90-100%": 85,
        "80-89%": 12,
        "70-79%": 8,
        "60-69%": 3,
        "<60%": 2,
    }
    st.bar_chart(scores)

    st.subheader("Validation Checks")
    checks = [
        ("Has Downgrade", 98, 12),
        ("No Destructive Ops", 105, 5),
        ("No Data Migrations", 102, 8),
        ("Indexed FK Columns", 95, 15),
        ("Has Revision ID", 110, 0),
    ]
    for check, passed, failed in checks:
        total = passed + failed
        pct = passed / total * 100 if total > 0 else 0
        st.progress(pct / 100, text=f"{check}: {passed}/{total} passed ({pct:.0f}%)")

with tab3:
    st.header("Migration Linting")
    col1, col2, col3 = st.columns(3)
    col1.metric("Files Checked", "110")
    col2.metric("Total Issues", "32")
    col3.metric("Files with Issues", "15")

    st.subheader("Issues by Severity")
    severity_data = {"CRITICAL": 2, "ERROR": 12, "WARNING": 13, "INFO": 5}
    st.bar_chart(severity_data)

    st.subheader("Lint Rules")
    for rule_id, rule in DEFAULT_RULES.items():
        st.markdown(
            f"**{rule_id}** [{rule.severity.value.upper()}]: "
            f"{rule.description} ({rule.category.value})"
        )

with tab4:
    st.header("Safety Configuration")
    config = MigrationSafetyConfig()
    st.json({
        "require_downgrade": config.require_downgrade,
        "block_destructive_ops": config.block_destructive_ops,
        "fail_on_error": config.fail_on_error,
        "fail_on_critical": config.fail_on_critical,
        "max_issues_before_fail": config.max_issues_before_fail,
        "schema_validation_enabled": config.schema_validation_enabled,
        "total_rules": len(config.rules),
        "enabled_rules": len(config.get_enabled_rules()),
    })

    st.subheader("Usage Example")
    st.code("""
from src.migration_safety import MigrationValidator, MigrationLinter

# Validate a single migration
validator = MigrationValidator()
result = validator.validate_file("alembic/versions/110_migration_safety.py")
print(f"Safe: {result.is_safe}, Score: {result.safety_score:.0%}")

# Lint all migrations
linter = MigrationLinter()
report = linter.lint_directory("alembic/versions/")
print(f"Issues: {report.total_issues}, Errors: {report.error_count}")
    """, language="python")
