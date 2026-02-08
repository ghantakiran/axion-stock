"""PRD-82: Tax Optimizer.

Revision ID: 082
Revises: 081
"""

from alembic import op
import sqlalchemy as sa

revision = "082"
down_revision = "081"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Tax lot inventory
    op.create_table(
        "tax_lots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("symbol", sa.String(20), nullable=False, index=True),
        sa.Column("shares", sa.Float(), nullable=False),
        sa.Column("cost_basis_per_share", sa.Float(), nullable=False),
        sa.Column("total_cost", sa.Float(), nullable=False),
        sa.Column("acquisition_date", sa.DateTime(), nullable=False),
        sa.Column("acquisition_type", sa.String(30), nullable=False),
        sa.Column("account_type", sa.String(30), nullable=False, server_default="taxable"),
        sa.Column("holding_period", sa.String(20), nullable=True),
        sa.Column("wash_sale_adjusted", sa.Boolean(), server_default="0"),
        sa.Column("adjustment_amount", sa.Float(), nullable=True),
        sa.Column("is_closed", sa.Boolean(), server_default="0"),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Tax-loss harvesting execution log
    op.create_table(
        "tax_harvest_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("symbol", sa.String(20), nullable=False, index=True),
        sa.Column("shares_sold", sa.Float(), nullable=False),
        sa.Column("sale_price", sa.Float(), nullable=False),
        sa.Column("cost_basis", sa.Float(), nullable=False),
        sa.Column("realized_loss", sa.Float(), nullable=False),
        sa.Column("tax_savings", sa.Float(), nullable=True),
        sa.Column("replacement_symbol", sa.String(20), nullable=True),
        sa.Column("wash_sale_risk", sa.Boolean(), server_default="0"),
        sa.Column("harvest_year", sa.Integer(), nullable=False, index=True),
        sa.Column("executed_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("tax_harvest_log")
    op.drop_table("tax_lots")
