"""PRD-71: Compliance & Audit System.

Revision ID: 057
Revises: 056
"""

from alembic import op
import sqlalchemy as sa

revision = "057"
down_revision = "056"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Compliance rules
    op.create_table(
        "compliance_rules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("rule_type", sa.String(30), nullable=False),  # position_limit, sector_limit, concentration, etc.
        # Rule parameters
        sa.Column("parameters", sa.JSON(), nullable=True),
        sa.Column("severity", sa.String(20), server_default="'warning'"),  # info, warning, critical
        # Scope
        sa.Column("applies_to_accounts", sa.JSON(), nullable=True),  # Array of account IDs, null = all
        sa.Column("applies_to_symbols", sa.JSON(), nullable=True),  # Array of symbols, null = all
        # Status
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("is_blocking", sa.Boolean(), server_default="false"),  # Block trade if violated
        # Timestamps
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), onupdate=sa.func.now()),
    )

    # Restricted securities
    op.create_table(
        "restricted_securities",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("reason", sa.String(100), nullable=False),  # insider, regulatory, risk_limit, etc.
        sa.Column("restriction_type", sa.String(20), nullable=False),  # all, buy_only, sell_only
        # Details
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("added_by", sa.String(36), nullable=True),
        sa.Column("added_by_name", sa.String(100), nullable=True),
        # Validity period
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),  # null = indefinite
        # Status
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        # Timestamps
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), onupdate=sa.func.now()),
    )

    # Compliance violations
    op.create_table(
        "compliance_violations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("rule_id", sa.String(36), sa.ForeignKey("compliance_rules.id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_id", sa.String(36), nullable=True),
        # Violation details
        sa.Column("rule_name", sa.String(100), nullable=False),
        sa.Column("violation_type", sa.String(30), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),  # info, warning, critical
        sa.Column("details", sa.JSON(), nullable=True),
        # Context
        sa.Column("symbol", sa.String(20), nullable=True),
        sa.Column("action", sa.String(20), nullable=True),  # buy, sell
        sa.Column("quantity", sa.Integer(), nullable=True),
        sa.Column("price", sa.Float(), nullable=True),
        # Resolution
        sa.Column("is_resolved", sa.Boolean(), server_default="false"),
        sa.Column("resolved_by", sa.String(36), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        # Was trade blocked?
        sa.Column("trade_blocked", sa.Boolean(), server_default="false"),
        # Timestamps
        sa.Column("timestamp", sa.DateTime(), server_default=sa.func.now()),
    )

    # Audit logs
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(36), nullable=True),
        sa.Column("user_email", sa.String(200), nullable=True),
        # Action
        sa.Column("action", sa.String(50), nullable=False),  # login, order_submit, strategy_create, etc.
        sa.Column("action_category", sa.String(30), nullable=True),  # auth, trading, strategy, account, admin
        # Resource
        sa.Column("resource_type", sa.String(30), nullable=True),  # order, account, strategy, user
        sa.Column("resource_id", sa.String(36), nullable=True),
        # Details
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("changes", sa.JSON(), nullable=True),  # Before/after for updates
        # Status
        sa.Column("status", sa.String(20), nullable=False),  # success, failure, warning
        sa.Column("error_message", sa.Text(), nullable=True),
        # Context
        sa.Column("ip_address", sa.String(45), nullable=True),  # IPv6 compatible
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("session_id", sa.String(36), nullable=True),
        # Timestamps
        sa.Column("timestamp", sa.DateTime(), server_default=sa.func.now()),
    )

    # Pre-trade check results (for audit trail)
    op.create_table(
        "pretrade_checks",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("account_id", sa.String(36), nullable=True),
        sa.Column("order_id", sa.String(36), nullable=True),
        # Trade details
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("action", sa.String(10), nullable=False),  # buy, sell
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("price", sa.Float(), nullable=True),
        # Results
        sa.Column("checks_run", sa.JSON(), nullable=True),  # Array of check results
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("blocking_violations", sa.Integer(), server_default="0"),
        sa.Column("warnings", sa.Integer(), server_default="0"),
        # Outcome
        sa.Column("trade_allowed", sa.Boolean(), nullable=False),
        sa.Column("override_by", sa.String(36), nullable=True),  # If override was applied
        sa.Column("override_reason", sa.Text(), nullable=True),
        # Timestamps
        sa.Column("timestamp", sa.DateTime(), server_default=sa.func.now()),
    )

    # Compliance reports (regulatory filings)
    op.create_table(
        "compliance_reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("report_type", sa.String(30), nullable=False),  # best_execution, 13f, form_adv, audit_summary
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        # Content
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=True),
        sa.Column("data", sa.JSON(), nullable=True),
        # Status
        sa.Column("status", sa.String(20), nullable=False),  # draft, final, submitted
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("submitted_to", sa.String(100), nullable=True),  # SEC, FINRA, etc.
        # Timestamps
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), onupdate=sa.func.now()),
    )

    # Indexes
    op.create_index("ix_compliance_rules_owner_id", "compliance_rules", ["owner_id"])
    op.create_index("ix_compliance_rules_rule_type", "compliance_rules", ["rule_type"])
    op.create_index("ix_restricted_securities_owner_id", "restricted_securities", ["owner_id"])
    op.create_index("ix_restricted_securities_symbol", "restricted_securities", ["symbol"])
    op.create_index("ix_compliance_violations_user_id", "compliance_violations", ["user_id"])
    op.create_index("ix_compliance_violations_timestamp", "compliance_violations", ["timestamp"])
    op.create_index("ix_compliance_violations_resolved", "compliance_violations", ["is_resolved"])
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_timestamp", "audit_logs", ["timestamp"])
    op.create_index("ix_audit_logs_resource", "audit_logs", ["resource_type", "resource_id"])
    op.create_index("ix_pretrade_checks_user_id", "pretrade_checks", ["user_id"])
    op.create_index("ix_pretrade_checks_timestamp", "pretrade_checks", ["timestamp"])
    op.create_index("ix_compliance_reports_user_id", "compliance_reports", ["user_id"])

    # Unique constraint for one active restriction per symbol per user
    op.create_unique_constraint(
        "uq_restricted_security_active",
        "restricted_securities",
        ["owner_id", "symbol"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_restricted_security_active", "restricted_securities")
    op.drop_index("ix_compliance_reports_user_id")
    op.drop_index("ix_pretrade_checks_timestamp")
    op.drop_index("ix_pretrade_checks_user_id")
    op.drop_index("ix_audit_logs_resource")
    op.drop_index("ix_audit_logs_timestamp")
    op.drop_index("ix_audit_logs_action")
    op.drop_index("ix_audit_logs_user_id")
    op.drop_index("ix_compliance_violations_resolved")
    op.drop_index("ix_compliance_violations_timestamp")
    op.drop_index("ix_compliance_violations_user_id")
    op.drop_index("ix_restricted_securities_symbol")
    op.drop_index("ix_restricted_securities_owner_id")
    op.drop_index("ix_compliance_rules_rule_type")
    op.drop_index("ix_compliance_rules_owner_id")
    op.drop_table("compliance_reports")
    op.drop_table("pretrade_checks")
    op.drop_table("audit_logs")
    op.drop_table("compliance_violations")
    op.drop_table("restricted_securities")
    op.drop_table("compliance_rules")
