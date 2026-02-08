"""PRD-95: Correlation Manager.

Revision ID: 095
Revises: 094
"""

from alembic import op
import sqlalchemy as sa

revision = "095"
down_revision = "094"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Regime-specific correlation breakdowns
    op.create_table(
        "correlation_breakdowns",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("regime", sa.String(20), nullable=False, index=True),
        sa.Column("avg_correlation", sa.Float(), nullable=False),
        sa.Column("max_correlation", sa.Float(), nullable=True),
        sa.Column("min_correlation", sa.Float(), nullable=True),
        sa.Column("n_assets", sa.Integer(), nullable=False),
        sa.Column("eigenvalues", sa.JSON(), nullable=True),
        sa.Column("computed_at", sa.DateTime(), server_default=sa.func.now(), index=True),
    )

    # Correlation shift alert log
    op.create_table(
        "correlation_alerts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("symbol_a", sa.String(20), nullable=True),
        sa.Column("symbol_b", sa.String(20), nullable=True),
        sa.Column("alert_type", sa.String(30), nullable=False),
        sa.Column("old_correlation", sa.Float(), nullable=True),
        sa.Column("new_correlation", sa.Float(), nullable=True),
        sa.Column("regime_from", sa.String(20), nullable=True),
        sa.Column("regime_to", sa.String(20), nullable=True),
        sa.Column("detected_at", sa.DateTime(), server_default=sa.func.now(), index=True),
    )


def downgrade() -> None:
    op.drop_table("correlation_alerts")
    op.drop_table("correlation_breakdowns")
