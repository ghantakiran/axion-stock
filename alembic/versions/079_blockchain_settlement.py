"""PRD-79: Blockchain Settlement Integration.

Revision ID: 079
Revises: 078
"""

from alembic import op
import sqlalchemy as sa

revision = "079"
down_revision = "078"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Blockchain settlement records
    op.create_table(
        "blockchain_settlements",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("trade_id", sa.String(36), nullable=False, index=True),
        sa.Column("settlement_type", sa.String(20), nullable=False),
        sa.Column("network", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, index=True),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("asset_symbol", sa.String(20), nullable=False),
        sa.Column("sender", sa.String(100), nullable=False),
        sa.Column("receiver", sa.String(100), nullable=False),
        sa.Column("tx_hash", sa.String(100), nullable=True, index=True),
        sa.Column("block_number", sa.BigInteger(), nullable=True),
        sa.Column("gas_cost", sa.Float(), nullable=True),
        sa.Column("settlement_time_seconds", sa.Float(), nullable=True),
        sa.Column("retries", sa.Integer(), server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("initiated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("settled_at", sa.DateTime(), nullable=True),
    )

    # Blockchain transaction monitoring
    op.create_table(
        "blockchain_transactions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tx_hash", sa.String(100), nullable=True, index=True),
        sa.Column("network", sa.String(30), nullable=False),
        sa.Column("from_address", sa.String(100), nullable=True),
        sa.Column("to_address", sa.String(100), nullable=True),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("token_address", sa.String(100), nullable=True),
        sa.Column("gas_used", sa.Integer(), nullable=True),
        sa.Column("gas_price_gwei", sa.Float(), nullable=True),
        sa.Column("block_number", sa.BigInteger(), nullable=True),
        sa.Column("confirmations", sa.Integer(), server_default="0"),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("timestamp", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("blockchain_transactions")
    op.drop_table("blockchain_settlements")
