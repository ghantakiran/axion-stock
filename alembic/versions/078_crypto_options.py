"""PRD-78: Crypto Options Platform.

Revision ID: 078
Revises: 077
"""

from alembic import op
import sqlalchemy as sa

revision = "078"
down_revision = "077"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Crypto option contracts
    op.create_table(
        "crypto_option_contracts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("underlying", sa.String(20), nullable=False, index=True),
        sa.Column("option_type", sa.String(10), nullable=False),
        sa.Column("strike", sa.Float(), nullable=False),
        sa.Column("expiry", sa.Date(), nullable=False, index=True),
        sa.Column("contract_size", sa.Float(), server_default="1.0"),
        sa.Column("exchange", sa.String(30), nullable=False),
        sa.Column("settlement", sa.String(20), nullable=False),
        sa.Column("instrument_name", sa.String(100), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Crypto funding rate history
    op.create_table(
        "crypto_funding_rates",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("underlying", sa.String(20), nullable=False, index=True),
        sa.Column("exchange", sa.String(30), nullable=False),
        sa.Column("rate", sa.Float(), nullable=False),
        sa.Column("annualized_rate", sa.Float(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), server_default=sa.func.now(), index=True),
    )


def downgrade() -> None:
    op.drop_table("crypto_funding_rates")
    op.drop_table("crypto_option_contracts")
