"""PRD-177: Multi-Strategy Bot.

Revision ID: 177
Revises: 176
Create Date: 2025-02-09
"""

from alembic import op
import sqlalchemy as sa

revision = "177"
down_revision = "176"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "strategy_registry",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("strategy_name", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("category", sa.String(30)),
        sa.Column("is_enabled", sa.Boolean, default=True),
        sa.Column("config_json", sa.Text),
        sa.Column("registered_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "strategy_signals",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("signal_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("strategy_name", sa.String(50), index=True, nullable=False),
        sa.Column("ticker", sa.String(20), index=True, nullable=False),
        sa.Column("direction", sa.String(10)),
        sa.Column("conviction", sa.Float),
        sa.Column("entry_price", sa.Float),
        sa.Column("stop_loss", sa.Float),
        sa.Column("target_price", sa.Float),
        sa.Column("generated_at", sa.DateTime(timezone=True), index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("strategy_signals")
    op.drop_table("strategy_registry")
