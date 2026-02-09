"""Live Signal-to-Trade Pipeline tables.

Revision ID: 149
Revises: 148
Create Date: 2026-02-09
"""

from alembic import op
import sqlalchemy as sa

revision = "149"
down_revision = "148"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Pipeline orders log
    op.create_table(
        "pipeline_orders",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("order_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False, index=True),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("order_type", sa.String(20), nullable=False),
        sa.Column("qty", sa.Float, nullable=False),
        sa.Column("limit_price", sa.Float),
        sa.Column("stop_price", sa.Float),
        sa.Column("asset_type", sa.String(20)),
        sa.Column("signal_type", sa.String(20), nullable=False, index=True),
        sa.Column("confidence", sa.Float),
        sa.Column("position_size_pct", sa.Float),
        sa.Column("stop_loss_pct", sa.Float),
        sa.Column("take_profit_pct", sa.Float),
        sa.Column("time_horizon", sa.String(20)),
        sa.Column("risk_level", sa.String(20)),
        sa.Column("reasoning", sa.Text),
        sa.Column("source_data_json", sa.Text),
        # Pipeline result fields
        sa.Column("status", sa.String(20), nullable=False, index=True),
        sa.Column("rejection_reason", sa.Text),
        sa.Column("broker_name", sa.String(50)),
        sa.Column("fill_price", sa.Float),
        sa.Column("fill_qty", sa.Float),
        sa.Column("fee", sa.Float),
        sa.Column("latency_ms", sa.Float),
        sa.Column("stages_json", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Position tracking
    op.create_table(
        "pipeline_positions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(20), unique=True, index=True, nullable=False),
        sa.Column("qty", sa.Float, nullable=False),
        sa.Column("avg_entry_price", sa.Float, nullable=False),
        sa.Column("current_price", sa.Float),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("signal_type", sa.String(20)),
        sa.Column("stop_loss_price", sa.Float),
        sa.Column("target_price", sa.Float),
        sa.Column("unrealized_pnl", sa.Float),
        sa.Column("order_ids_json", sa.Text),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Reconciliation records
    op.create_table(
        "pipeline_reconciliations",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("record_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("order_id", sa.String(50), index=True, nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False, index=True),
        sa.Column("expected_price", sa.Float),
        sa.Column("actual_price", sa.Float),
        sa.Column("expected_qty", sa.Float),
        sa.Column("actual_qty", sa.Float),
        sa.Column("slippage_pct", sa.Float),
        sa.Column("fill_ratio", sa.Float),
        sa.Column("broker_name", sa.String(50)),
        sa.Column("latency_ms", sa.Float),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("pipeline_reconciliations")
    op.drop_table("pipeline_positions")
    op.drop_table("pipeline_orders")
