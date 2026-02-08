"""PRD-65: Portfolio Stress Testing.

Revision ID: 065
Revises: 064
"""

from alembic import op
import sqlalchemy as sa

revision = "065"
down_revision = "064"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Stress test run history
    op.create_table(
        "stress_test_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=True, index=True),
        sa.Column("run_date", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("scenario_name", sa.String(100), nullable=False),
        sa.Column("scenario_type", sa.String(30), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("portfolio_value", sa.Float(), nullable=True),
        sa.Column("total_impact_pct", sa.Float(), nullable=True),
        sa.Column("total_impact_usd", sa.Float(), nullable=True),
        sa.Column("amplification_factor", sa.Float(), nullable=True),
        sa.Column("positions_affected", sa.Integer(), nullable=True),
        sa.Column("is_systemic", sa.Boolean(), default=False),
        sa.Column("worst_position", sa.String(30), nullable=True),
        sa.Column("worst_impact_pct", sa.Float(), nullable=True),
        sa.Column("factor_contributions", sa.Text(), nullable=True),
        sa.Column("parameters", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Drawdown alert configurations
    op.create_table(
        "drawdown_alert_configs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False, index=True),
        sa.Column("symbol", sa.String(20), nullable=True),
        sa.Column("alert_name", sa.String(100), nullable=False),
        sa.Column("drawdown_threshold", sa.Float(), nullable=False),
        sa.Column("duration_threshold_days", sa.Integer(), nullable=True),
        sa.Column("severity", sa.String(20), default="warning"),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("last_triggered_at", sa.DateTime(), nullable=True),
        sa.Column("trigger_count", sa.Integer(), default=0),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("drawdown_alert_configs")
    op.drop_table("stress_test_runs")
