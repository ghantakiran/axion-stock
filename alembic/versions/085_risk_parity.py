"""PRD-85: Risk Parity & Volatility Targeting.

Revision ID: 085
Revises: 084
"""

from alembic import op
import sqlalchemy as sa

revision = "085"
down_revision = "084"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Risk parity allocation snapshots
    op.create_table(
        "risk_parity_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("portfolio_id", sa.String(36), nullable=False, index=True),
        sa.Column("method", sa.String(30), nullable=False),
        sa.Column("weights", sa.JSON(), nullable=False),
        sa.Column("risk_contributions", sa.JSON(), nullable=False),
        sa.Column("portfolio_volatility", sa.Float(), nullable=True),
        sa.Column("max_contribution_diff", sa.Float(), nullable=True),
        sa.Column("n_assets", sa.Integer(), nullable=False),
        sa.Column("computed_at", sa.DateTime(), server_default=sa.func.now(), index=True),
    )

    # Volatility targeting adjustment log
    op.create_table(
        "vol_target_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("portfolio_id", sa.String(36), nullable=False, index=True),
        sa.Column("target_volatility", sa.Float(), nullable=False),
        sa.Column("realized_volatility", sa.Float(), nullable=False),
        sa.Column("scaling_factor", sa.Float(), nullable=False),
        sa.Column("prev_weights", sa.JSON(), nullable=True),
        sa.Column("new_weights", sa.JSON(), nullable=True),
        sa.Column("adjusted_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("vol_target_history")
    op.drop_table("risk_parity_snapshots")
