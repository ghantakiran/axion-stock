"""PRD-170: Bot Pipeline Robustness.

Revision ID: 170
Revises: 167
Create Date: 2025-02-09
"""

from alembic import op
import sqlalchemy as sa

revision = "170"
down_revision = "167"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Bot pipeline state snapshots: periodic captures of bot health
    op.create_table(
        "bot_pipeline_states",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("snapshot_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("kill_switch_active", sa.Boolean, default=False),
        sa.Column("kill_switch_reason", sa.Text),
        sa.Column("circuit_breaker_status", sa.String(20)),
        sa.Column("daily_pnl", sa.Float),
        sa.Column("daily_trade_count", sa.Integer),
        sa.Column("open_positions", sa.Integer),
        sa.Column("total_signals_processed", sa.Integer),
        sa.Column("successful_executions", sa.Integer),
        sa.Column("rejection_rate", sa.Float),
        sa.Column("state_json", sa.Text),
        sa.Column("snapshot_time", sa.DateTime(timezone=True), index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Bot reconciliation reports: position sync audit trail
    op.create_table(
        "bot_reconciliation_reports",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("report_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("total_local", sa.Integer),
        sa.Column("total_broker", sa.Integer),
        sa.Column("matched_count", sa.Integer),
        sa.Column("ghost_count", sa.Integer),
        sa.Column("orphaned_count", sa.Integer),
        sa.Column("mismatch_count", sa.Integer),
        sa.Column("is_clean", sa.Boolean),
        sa.Column("details_json", sa.Text),
        sa.Column("reconciled_at", sa.DateTime(timezone=True), index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("bot_reconciliation_reports")
    op.drop_table("bot_pipeline_states")
