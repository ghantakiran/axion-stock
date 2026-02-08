"""PRD-68: Multi-Account Management.

Revision ID: 068
Revises: 067
"""

from alembic import op
import sqlalchemy as sa

revision = "068"
down_revision = "067"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Account transfer history
    op.create_table(
        "account_transfers",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("from_account_id", sa.String(36), nullable=False, index=True),
        sa.Column("to_account_id", sa.String(36), nullable=False, index=True),
        sa.Column("symbol", sa.String(20), nullable=True),
        sa.Column("quantity", sa.Float(), nullable=True),
        sa.Column("transfer_type", sa.String(30), nullable=False),
        sa.Column("amount", sa.Float(), nullable=True),
        sa.Column("reason", sa.String(200), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, default="completed"),
        sa.Column("initiated_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Account performance benchmarks
    op.create_table(
        "account_benchmarks",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("account_id", sa.String(36), nullable=False, index=True),
        sa.Column("benchmark_date", sa.Date(), nullable=False),
        sa.Column("benchmark_symbol", sa.String(20), nullable=False),
        sa.Column("account_return_pct", sa.Float(), nullable=True),
        sa.Column("benchmark_return_pct", sa.Float(), nullable=True),
        sa.Column("active_return_pct", sa.Float(), nullable=True),
        sa.Column("tracking_error", sa.Float(), nullable=True),
        sa.Column("information_ratio", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("account_benchmarks")
    op.drop_table("account_transfers")
