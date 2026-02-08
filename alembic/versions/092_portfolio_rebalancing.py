"""PRD-92: Portfolio Rebalancing.

Revision ID: 092
Revises: 091
"""

from alembic import op
import sqlalchemy as sa

revision = "092"
down_revision = "091"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Pre/post rebalance performance comparison
    op.create_table(
        "rebalance_performance_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("plan_id", sa.String(36), nullable=False, index=True),
        sa.Column("pre_drift_max", sa.Float(), nullable=True),
        sa.Column("post_drift_max", sa.Float(), nullable=True),
        sa.Column("trades_executed", sa.Integer(), server_default="0"),
        sa.Column("total_cost", sa.Float(), nullable=True),
        sa.Column("tax_impact", sa.Float(), nullable=True),
        sa.Column("rebalanced_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Drift threshold breach alerts
    op.create_table(
        "drift_alert_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("portfolio_id", sa.String(36), nullable=False, index=True),
        sa.Column("symbol", sa.String(20), nullable=True),
        sa.Column("drift_pct", sa.Float(), nullable=False),
        sa.Column("threshold_pct", sa.Float(), nullable=False),
        sa.Column("is_critical", sa.Boolean(), server_default="0"),
        sa.Column("detected_at", sa.DateTime(), server_default=sa.func.now(), index=True),
    )


def downgrade() -> None:
    op.drop_table("drift_alert_history")
    op.drop_table("rebalance_performance_log")
