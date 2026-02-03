"""PRD-55: Regime Detection.

Revision ID: 041
Revises: 040
"""

from alembic import op
import sqlalchemy as sa

revision = "041"
down_revision = "040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Regime detections
    op.create_table(
        "regime_detections",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("detection_date", sa.Date(), nullable=False),
        sa.Column("method", sa.String(20), nullable=False),
        sa.Column("regime", sa.String(20), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("duration", sa.Integer(), nullable=True),
        sa.Column("probabilities_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Regime transition matrices
    op.create_table(
        "regime_transitions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("computed_date", sa.Date(), nullable=False),
        sa.Column("from_regime", sa.String(20), nullable=False),
        sa.Column("to_regime", sa.String(20), nullable=False),
        sa.Column("probability", sa.Float(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Regime statistics
    op.create_table(
        "regime_statistics",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("computed_date", sa.Date(), nullable=False),
        sa.Column("regime", sa.String(20), nullable=False),
        sa.Column("avg_return", sa.Float(), nullable=False),
        sa.Column("volatility", sa.Float(), nullable=False),
        sa.Column("avg_duration", sa.Float(), nullable=False),
        sa.Column("frequency", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Regime allocations
    op.create_table(
        "regime_allocations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("allocation_date", sa.Date(), nullable=False),
        sa.Column("regime", sa.String(20), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("weights_json", sa.Text(), nullable=False),
        sa.Column("blended_weights_json", sa.Text(), nullable=False),
        sa.Column("expected_return", sa.Float(), nullable=True),
        sa.Column("expected_risk", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("regime_allocations")
    op.drop_table("regime_statistics")
    op.drop_table("regime_transitions")
    op.drop_table("regime_detections")
