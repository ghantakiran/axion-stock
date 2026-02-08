"""PRD-93: Multi-Account Management.

Revision ID: 093
Revises: 092
"""

from alembic import op
import sqlalchemy as sa

revision = "093"
down_revision = "092"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Per-account tax summary snapshots
    op.create_table(
        "account_tax_reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(36), nullable=False, index=True),
        sa.Column("tax_year", sa.Integer(), nullable=False, index=True),
        sa.Column("realized_stcg", sa.Float(), server_default="0"),
        sa.Column("realized_ltcg", sa.Float(), server_default="0"),
        sa.Column("dividend_income", sa.Float(), server_default="0"),
        sa.Column("interest_income", sa.Float(), server_default="0"),
        sa.Column("wash_sale_disallowed", sa.Float(), server_default="0"),
        sa.Column("estimated_tax", sa.Float(), nullable=True),
        sa.Column("generated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Household-level analytics aggregation
    op.create_table(
        "household_analytics",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), nullable=False, index=True),
        sa.Column("total_accounts", sa.Integer(), nullable=False),
        sa.Column("total_value", sa.Float(), nullable=False),
        sa.Column("total_cash", sa.Float(), nullable=False),
        sa.Column("taxable_pct", sa.Float(), nullable=True),
        sa.Column("tax_deferred_pct", sa.Float(), nullable=True),
        sa.Column("tax_free_pct", sa.Float(), nullable=True),
        sa.Column("ytd_return_pct", sa.Float(), nullable=True),
        sa.Column("snapshot_date", sa.DateTime(), server_default=sa.func.now(), index=True),
    )


def downgrade() -> None:
    op.drop_table("household_analytics")
    op.drop_table("account_tax_reports")
