"""PRD-97: GIPS Performance Report.

Revision ID: 097
Revises: 096
"""

from alembic import op
import sqlalchemy as sa

revision = "097"
down_revision = "096"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Annual composite performance records
    op.create_table(
        "gips_composite_periods",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("composite_id", sa.String(36), nullable=False, index=True),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("gross_return", sa.Float(), nullable=False),
        sa.Column("net_return", sa.Float(), nullable=False),
        sa.Column("benchmark_return", sa.Float(), nullable=True),
        sa.Column("n_portfolios", sa.Integer(), nullable=False),
        sa.Column("composite_assets", sa.Float(), nullable=True),
        sa.Column("firm_assets", sa.Float(), nullable=True),
        sa.Column("pct_firm_assets", sa.Float(), nullable=True),
        sa.Column("dispersion", sa.Float(), nullable=True),
        sa.Column("composite_3yr_std", sa.Float(), nullable=True),
        sa.Column("benchmark_3yr_std", sa.Float(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Compliance validation audit trail
    op.create_table(
        "gips_compliance_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("composite_id", sa.String(36), nullable=False, index=True),
        sa.Column("overall_compliant", sa.Boolean(), nullable=False),
        sa.Column("pass_rate", sa.Float(), nullable=True),
        sa.Column("n_checks", sa.Integer(), nullable=False),
        sa.Column("n_errors", sa.Integer(), nullable=True),
        sa.Column("n_warnings", sa.Integer(), nullable=True),
        sa.Column("check_details", sa.JSON(), nullable=True),
        sa.Column("checked_at", sa.DateTime(), server_default=sa.func.now(), index=True),
    )


def downgrade() -> None:
    op.drop_table("gips_compliance_logs")
    op.drop_table("gips_composite_periods")
