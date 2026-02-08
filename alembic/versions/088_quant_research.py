"""PRD-88: Quantitative Research Tools.

Revision ID: 088
Revises: 087
"""

from alembic import op
import sqlalchemy as sa

revision = "088"
down_revision = "087"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Research report storage
    op.create_table(
        "research_reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("symbol", sa.String(20), nullable=False, index=True),
        sa.Column("report_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("valuation_target", sa.Float(), nullable=True),
        sa.Column("recommendation", sa.String(20), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_by", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), index=True),
    )

    # Alpha signal generation audit trail
    op.create_table(
        "alpha_signal_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("signal_type", sa.String(50), nullable=False, index=True),
        sa.Column("symbol", sa.String(20), nullable=True, index=True),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("strength", sa.Float(), nullable=True),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("regime", sa.String(20), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("generated_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("alpha_signal_log")
    op.drop_table("research_reports")
