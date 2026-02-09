"""Smart Multi-Broker Execution.

Revision ID: 146
Revises: 145
Create Date: 2025-02-08
"""

from alembic import op
import sqlalchemy as sa

revision = "146"
down_revision = "145"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Multi-broker connections registry
    op.create_table(
        "multi_broker_connections",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("broker_name", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("asset_types", sa.Text),
        sa.Column("fee_json", sa.Text),
        sa.Column("priority", sa.Integer, server_default="0"),
        sa.Column("latency_ms", sa.Float),
        sa.Column("last_sync", sa.DateTime(timezone=True)),
        sa.Column("error_message", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Multi-broker route decisions log
    op.create_table(
        "multi_broker_routes",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("order_id", sa.String(50), index=True, nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False, index=True),
        sa.Column("asset_type", sa.String(20), nullable=False),
        sa.Column("routed_to", sa.String(50), nullable=False),
        sa.Column("reason", sa.Text),
        sa.Column("score", sa.Float),
        sa.Column("fee", sa.Float),
        sa.Column("latency_ms", sa.Float),
        sa.Column("failover", sa.Boolean, server_default="false"),
        sa.Column("failover_from", sa.String(50)),
        sa.Column("status", sa.String(20)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("multi_broker_routes")
    op.drop_table("multi_broker_connections")
