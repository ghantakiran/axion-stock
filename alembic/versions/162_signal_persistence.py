"""PRD-162: Signal Persistence.

Revision ID: 162
Revises: 161
Create Date: 2025-02-09
"""

from alembic import op
import sqlalchemy as sa

revision = "162"
down_revision = "161"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Persistent signals: durable store for every generated signal
    op.create_table(
        "persistent_signals",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("signal_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("source", sa.String(30), nullable=False, index=True),
        sa.Column("ticker", sa.String(20), nullable=False, index=True),
        sa.Column("direction", sa.String(10), nullable=False, index=True),
        sa.Column("strength", sa.Float),
        sa.Column("confidence", sa.Float),
        sa.Column("status", sa.String(20), nullable=False, index=True),
        sa.Column("fusion_id", sa.String(50), index=True),
        sa.Column("execution_id", sa.String(50), index=True),
        sa.Column("source_metadata", sa.Text),
        sa.Column("signal_time", sa.DateTime(timezone=True), index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Persistent fusions: combined multi-source signal records
    op.create_table(
        "persistent_fusions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("fusion_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("ticker", sa.String(20), nullable=False, index=True),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("composite_score", sa.Float),
        sa.Column("confidence", sa.Float),
        sa.Column("source_count", sa.Integer),
        sa.Column("agreement_ratio", sa.Float),
        sa.Column("input_signal_ids", sa.Text),
        sa.Column("source_weights_used", sa.Text),
        sa.Column("fusion_time", sa.DateTime(timezone=True), index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Persistent risk decisions: audit trail of risk gate outcomes
    op.create_table(
        "persistent_risk_decisions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("decision_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("signal_id", sa.String(50), index=True),
        sa.Column("fusion_id", sa.String(50), index=True),
        sa.Column("approved", sa.Boolean),
        sa.Column("rejection_reason", sa.Text),
        sa.Column("checks_run", sa.Text),
        sa.Column("checks_passed", sa.Text),
        sa.Column("checks_failed", sa.Text),
        sa.Column("account_snapshot", sa.Text),
        sa.Column("decision_time", sa.DateTime(timezone=True), index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Persistent executions: fill records for executed orders
    op.create_table(
        "persistent_executions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("execution_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("signal_id", sa.String(50), index=True),
        sa.Column("fusion_id", sa.String(50), index=True),
        sa.Column("decision_id", sa.String(50), index=True),
        sa.Column("ticker", sa.String(20), nullable=False, index=True),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("order_type", sa.String(20)),
        sa.Column("quantity", sa.Float),
        sa.Column("fill_price", sa.Float),
        sa.Column("requested_price", sa.Float),
        sa.Column("slippage", sa.Float),
        sa.Column("broker", sa.String(30)),
        sa.Column("status", sa.String(20), nullable=False, index=True),
        sa.Column("config_snapshot", sa.Text),
        sa.Column("fill_time", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("persistent_executions")
    op.drop_table("persistent_risk_decisions")
    op.drop_table("persistent_fusions")
    op.drop_table("persistent_signals")
