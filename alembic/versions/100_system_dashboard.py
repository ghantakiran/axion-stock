"""PRD-100: System Dashboard.

Revision ID: 100
Revises: 099
"""

from alembic import op
import sqlalchemy as sa

revision = "100"
down_revision = "099"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Periodic health check records
    op.create_table(
        "system_health_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("overall_status", sa.String(20), nullable=False, index=True),
        sa.Column("n_services", sa.Integer(), nullable=False),
        sa.Column("n_healthy", sa.Integer(), nullable=True),
        sa.Column("n_degraded", sa.Integer(), nullable=True),
        sa.Column("n_down", sa.Integer(), nullable=True),
        sa.Column("cpu_usage", sa.Float(), nullable=True),
        sa.Column("memory_usage", sa.Float(), nullable=True),
        sa.Column("disk_usage", sa.Float(), nullable=True),
        sa.Column("requests_per_minute", sa.Float(), nullable=True),
        sa.Column("avg_response_time_ms", sa.Float(), nullable=True),
        sa.Column("cache_hit_rate", sa.Float(), nullable=True),
        sa.Column("stale_data_sources", sa.Integer(), nullable=True),
        sa.Column("service_details", sa.JSON(), nullable=True),
        sa.Column("captured_at", sa.DateTime(), server_default=sa.func.now(), index=True),
    )

    # System alert history
    op.create_table(
        "system_alert_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("level", sa.String(20), nullable=False, index=True),
        sa.Column("service", sa.String(30), nullable=False, index=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("metric_name", sa.String(50), nullable=True),
        sa.Column("metric_value", sa.Float(), nullable=True),
        sa.Column("threshold", sa.Float(), nullable=True),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("acknowledged", sa.Boolean(), default=False),
        sa.Column("acknowledged_by", sa.String(100), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), index=True),
    )


def downgrade() -> None:
    op.drop_table("system_alert_log")
    op.drop_table("system_health_snapshots")
