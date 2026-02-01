"""Portfolio rebalancing system tables.

Revision ID: 027
Revises: 026
Create Date: 2026-02-01

Adds:
- drift_snapshots: Drift analysis history
- rebalance_plans: Generated rebalance plans
- rebalance_trades: Individual trade records
- rebalance_schedules: Scheduler configuration and history
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "027"
down_revision = "026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drift snapshots
    op.create_table(
        "drift_snapshots",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("max_drift", sa.Float),
        sa.Column("mean_drift", sa.Float),
        sa.Column("rmse_drift", sa.Float),
        sa.Column("n_exceeding", sa.Integer),
        sa.Column("n_critical", sa.Integer),
        sa.Column("needs_rebalance", sa.Boolean),
        sa.Column("asset_drifts_json", sa.JSON),
        sa.Column("date", sa.Date),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_drift_snapshots_date", "drift_snapshots", ["date"])

    # Rebalance plans
    op.create_table(
        "rebalance_plans",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("plan_id", sa.String(32), unique=True, nullable=False),
        sa.Column("n_trades", sa.Integer),
        sa.Column("total_turnover", sa.Float),
        sa.Column("total_buy_value", sa.Float),
        sa.Column("total_sell_value", sa.Float),
        sa.Column("estimated_cost", sa.Float),
        sa.Column("estimated_tax", sa.Float),
        sa.Column("drift_before", sa.Float),
        sa.Column("drift_after", sa.Float),
        sa.Column("status", sa.String(16)),
        sa.Column("date", sa.Date),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_rebalance_plans_date", "rebalance_plans", ["date"])
    op.create_index("ix_rebalance_plans_status", "rebalance_plans", ["status"])

    # Rebalance trades
    op.create_table(
        "rebalance_trades",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("plan_id", sa.String(32), nullable=False),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("side", sa.String(4)),
        sa.Column("shares", sa.Integer),
        sa.Column("value", sa.Float),
        sa.Column("from_weight", sa.Float),
        sa.Column("to_weight", sa.Float),
        sa.Column("estimated_cost", sa.Float),
        sa.Column("tax_impact", sa.Float),
        sa.Column("is_tax_loss_harvest", sa.Boolean),
    )
    op.create_index("ix_rebalance_trades_plan", "rebalance_trades", ["plan_id"])

    # Rebalance schedules
    op.create_table(
        "rebalance_schedules",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("trigger_type", sa.String(16)),
        sa.Column("frequency", sa.String(16)),
        sa.Column("last_rebalance", sa.Date),
        sa.Column("next_scheduled", sa.Date),
        sa.Column("threshold", sa.Float),
        sa.Column("config_json", sa.JSON),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("rebalance_schedules")
    op.drop_table("rebalance_trades")
    op.drop_table("rebalance_plans")
    op.drop_table("drift_snapshots")
