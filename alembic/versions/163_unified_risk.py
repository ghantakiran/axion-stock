"""PRD-163: Unified Risk.

Revision ID: 163
Revises: 162
Create Date: 2025-02-09
"""

from alembic import op
import sqlalchemy as sa

revision = "163"
down_revision = "162"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Correlation snapshots: periodic portfolio correlation matrices
    op.create_table(
        "correlation_snapshots",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("snapshot_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("tickers", sa.Text),
        sa.Column("matrix_json", sa.Text),
        sa.Column("clusters", sa.Text),
        sa.Column("max_correlation", sa.Float),
        sa.Column("concentration_score", sa.Float),
        sa.Column("position_count", sa.Integer),
        sa.Column("computed_at", sa.DateTime(timezone=True), index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Unified risk assessments: consolidated risk gate verdicts
    op.create_table(
        "unified_risk_assessments",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("assessment_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("ticker", sa.String(20), nullable=False, index=True),
        sa.Column("approved", sa.Boolean),
        sa.Column("rejection_reason", sa.Text),
        sa.Column("daily_pnl", sa.Float),
        sa.Column("daily_pnl_pct", sa.Float),
        sa.Column("regime", sa.String(20)),
        sa.Column("concentration_score", sa.Float),
        sa.Column("portfolio_var_pct", sa.Float),
        sa.Column("max_position_size", sa.Float),
        sa.Column("circuit_breaker_status", sa.String(20)),
        sa.Column("kill_switch_active", sa.Boolean),
        sa.Column("warnings", sa.Text),
        sa.Column("checks_run", sa.Text),
        sa.Column("assessed_at", sa.DateTime(timezone=True), index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("unified_risk_assessments")
    op.drop_table("correlation_snapshots")
