"""PRD-173: Strategy Pipeline Integration.

Revision ID: 173
Revises: 172
Create Date: 2025-02-09
"""

from alembic import op
import sqlalchemy as sa

revision = "173"
down_revision = "172"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "strategy_decisions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("decision_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("ticker", sa.String(20), index=True, nullable=False),
        sa.Column("selected_strategy", sa.String(30), nullable=False),
        sa.Column("regime", sa.String(20)),
        sa.Column("adx_value", sa.Float),
        sa.Column("confidence", sa.Float),
        sa.Column("reasoning", sa.Text),
        sa.Column("decided_at", sa.DateTime(timezone=True), index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("strategy_decisions")
