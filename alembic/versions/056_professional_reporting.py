"""PRD-70: Professional Reporting.

Revision ID: 056
Revises: 055
"""

from alembic import op
import sqlalchemy as sa

revision = "056"
down_revision = "055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Report templates
    op.create_table(
        "report_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("report_type", sa.String(30), nullable=False),  # performance, holdings, attribution, trade_activity, custom
        # Template configuration
        sa.Column("sections", sa.JSON(), nullable=True),  # Array of section configs
        sa.Column("metrics", sa.JSON(), nullable=True),  # Which metrics to include
        sa.Column("charts", sa.JSON(), nullable=True),  # Chart configurations
        sa.Column("filters", sa.JSON(), nullable=True),  # Default filters
        # Branding
        sa.Column("logo_url", sa.String(500), nullable=True),
        sa.Column("company_name", sa.String(100), nullable=True),
        sa.Column("primary_color", sa.String(20), nullable=True),
        sa.Column("footer_text", sa.Text(), nullable=True),
        # Status
        sa.Column("is_default", sa.Boolean(), server_default="false"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        # Timestamps
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), onupdate=sa.func.now()),
    )

    # Generated reports
    op.create_table(
        "generated_reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_id", sa.String(36), nullable=True),
        sa.Column("template_id", sa.String(36), sa.ForeignKey("report_templates.id", ondelete="SET NULL"), nullable=True),
        # Report info
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("report_type", sa.String(30), nullable=False),
        sa.Column("format", sa.String(10), nullable=False),  # pdf, excel, html
        # Period
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("period_type", sa.String(20), nullable=True),  # daily, weekly, monthly, quarterly, annual, custom
        # Content
        sa.Column("file_path", sa.String(500), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True),  # SHA-256 for integrity
        # Metadata
        sa.Column("parameters", sa.JSON(), nullable=True),  # Generation parameters
        sa.Column("metrics_snapshot", sa.JSON(), nullable=True),  # Captured metrics
        # Status
        sa.Column("status", sa.String(20), nullable=False),  # pending, generating, completed, failed
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("generation_time_ms", sa.Integer(), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )

    # Scheduled reports
    op.create_table(
        "scheduled_reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_id", sa.String(36), nullable=True),
        sa.Column("template_id", sa.String(36), sa.ForeignKey("report_templates.id", ondelete="SET NULL"), nullable=True),
        # Schedule info
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("frequency", sa.String(20), nullable=False),  # daily, weekly, monthly, quarterly
        sa.Column("day_of_week", sa.Integer(), nullable=True),  # 0-6 for weekly
        sa.Column("day_of_month", sa.Integer(), nullable=True),  # 1-31 for monthly
        sa.Column("time_of_day", sa.String(10), nullable=True),  # HH:MM
        sa.Column("timezone", sa.String(50), server_default="'UTC'"),
        # Report config
        sa.Column("report_type", sa.String(30), nullable=False),
        sa.Column("format", sa.String(10), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=True),
        # Distribution
        sa.Column("recipients", sa.JSON(), nullable=True),  # Array of email addresses
        sa.Column("send_empty", sa.Boolean(), server_default="false"),  # Send even if no data
        # Status
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("next_run_at", sa.DateTime(), nullable=True),
        sa.Column("run_count", sa.Integer(), server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), onupdate=sa.func.now()),
    )

    # Report distributions (email delivery log)
    op.create_table(
        "report_distributions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("report_id", sa.String(36), sa.ForeignKey("generated_reports.id", ondelete="CASCADE"), nullable=False),
        sa.Column("schedule_id", sa.String(36), sa.ForeignKey("scheduled_reports.id", ondelete="SET NULL"), nullable=True),
        # Recipient info
        sa.Column("recipient_email", sa.String(200), nullable=False),
        sa.Column("recipient_name", sa.String(100), nullable=True),
        # Status
        sa.Column("status", sa.String(20), nullable=False),  # pending, sent, delivered, failed, bounced
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(), nullable=True),
        sa.Column("opened_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        # Tracking
        sa.Column("message_id", sa.String(100), nullable=True),  # Email provider message ID
        # Timestamps
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Report sections (custom sections for templates)
    op.create_table(
        "report_sections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("template_id", sa.String(36), sa.ForeignKey("report_templates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("section_type", sa.String(30), nullable=False),  # summary, holdings, trades, chart, text, metrics
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("is_visible", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # White-label configurations
    op.create_table(
        "report_branding",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        # Branding
        sa.Column("company_name", sa.String(100), nullable=False),
        sa.Column("logo_url", sa.String(500), nullable=True),
        sa.Column("primary_color", sa.String(20), server_default="'#007bff'"),
        sa.Column("secondary_color", sa.String(20), server_default="'#6c757d'"),
        sa.Column("accent_color", sa.String(20), server_default="'#28a745'"),
        # Text
        sa.Column("header_text", sa.Text(), nullable=True),
        sa.Column("footer_text", sa.Text(), nullable=True),
        sa.Column("disclaimer", sa.Text(), nullable=True),
        # Contact
        sa.Column("contact_email", sa.String(200), nullable=True),
        sa.Column("contact_phone", sa.String(50), nullable=True),
        sa.Column("website", sa.String(200), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        # Status
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        # Timestamps
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), onupdate=sa.func.now()),
    )

    # Indexes
    op.create_index("ix_report_templates_owner_id", "report_templates", ["owner_id"])
    op.create_index("ix_generated_reports_user_id", "generated_reports", ["user_id"])
    op.create_index("ix_generated_reports_account_id", "generated_reports", ["account_id"])
    op.create_index("ix_generated_reports_created_at", "generated_reports", ["created_at"])
    op.create_index("ix_scheduled_reports_user_id", "scheduled_reports", ["user_id"])
    op.create_index("ix_scheduled_reports_next_run", "scheduled_reports", ["next_run_at"])
    op.create_index("ix_report_distributions_report_id", "report_distributions", ["report_id"])
    op.create_index("ix_report_sections_template_id", "report_sections", ["template_id"])
    op.create_index("ix_report_branding_user_id", "report_branding", ["user_id"])

    # Unique constraint for one branding per user
    op.create_unique_constraint(
        "uq_report_branding_user",
        "report_branding",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_report_branding_user", "report_branding")
    op.drop_index("ix_report_branding_user_id")
    op.drop_index("ix_report_sections_template_id")
    op.drop_index("ix_report_distributions_report_id")
    op.drop_index("ix_scheduled_reports_next_run")
    op.drop_index("ix_scheduled_reports_user_id")
    op.drop_index("ix_generated_reports_created_at")
    op.drop_index("ix_generated_reports_account_id")
    op.drop_index("ix_generated_reports_user_id")
    op.drop_index("ix_report_templates_owner_id")
    op.drop_table("report_branding")
    op.drop_table("report_sections")
    op.drop_table("report_distributions")
    op.drop_table("scheduled_reports")
    op.drop_table("generated_reports")
    op.drop_table("report_templates")
