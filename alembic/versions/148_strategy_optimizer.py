"""Adaptive Strategy Optimizer tables.

Revision ID: 148
Revises: 147
Create Date: 2026-02-09
"""

from alembic import op
import sqlalchemy as sa

revision = "148"
down_revision = "147"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Optimization run history
    op.create_table(
        "strategy_optimization_runs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("param_space_json", sa.Text),
        sa.Column("best_params_json", sa.Text),
        sa.Column("best_score", sa.Float, nullable=False),
        sa.Column("generations_run", sa.Integer, nullable=False),
        sa.Column("convergence", sa.Float),
        sa.Column("regime", sa.String(20)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Drift check history
    op.create_table(
        "strategy_drift_checks",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("check_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("current_sharpe", sa.Float),
        sa.Column("baseline_sharpe", sa.Float),
        sa.Column("sharpe_delta", sa.Float),
        sa.Column("current_drawdown", sa.Float),
        sa.Column("recommendation", sa.String(50)),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("strategy_drift_checks")
    op.drop_table("strategy_optimization_runs")
