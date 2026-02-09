"""PRD-134: EMA Cloud Signal Engine.

Revision ID: 134
Revises: 132
"""

from alembic import op
import sqlalchemy as sa

revision = "134"
down_revision = "132"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ema_signals",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ticker", sa.String(10), nullable=False, index=True),
        sa.Column("signal_type", sa.String(50), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("timeframe", sa.String(10), nullable=False),
        sa.Column("conviction", sa.Integer(), nullable=False),
        sa.Column("entry_price", sa.Float(), nullable=False),
        sa.Column("stop_loss", sa.Float(), nullable=True),
        sa.Column("target_price", sa.Float(), nullable=True),
        sa.Column("cloud_states_json", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            index=True,
        ),
        sa.Column("executed", sa.Boolean(), server_default="false"),
        sa.Column("execution_id", sa.String(50), nullable=True),
    )

    # Composite indexes for common query patterns
    op.create_index(
        "ix_ema_signals_ticker_created",
        "ema_signals",
        ["ticker", "created_at"],
    )
    op.create_index(
        "ix_ema_signals_conviction_executed",
        "ema_signals",
        ["conviction", "executed"],
    )


def downgrade() -> None:
    op.drop_index("ix_ema_signals_conviction_executed", table_name="ema_signals")
    op.drop_index("ix_ema_signals_ticker_created", table_name="ema_signals")
    op.drop_table("ema_signals")
